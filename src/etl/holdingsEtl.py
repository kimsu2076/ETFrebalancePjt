# -*- coding: utf-8 -*-
"""Holdings snapshot + rebalancing_event ETL 오케스트레이션 모듈"""

import time
from datetime import datetime

from src.config.envLoader import getDbConfig, getKisConfig, validateDbConfig
from src.etl.etlLogger import logEtlError, setupEtlLogger
from src.db.dbConnection import getDbEngine, testDbConnection
from src.db.holdingsRepository import (
    getHoldingsStats,
    getPreviousSnapshotDate,
    getSnapshotRows,
    insertHoldingsSnapshot,
    resolveTargetSnapshotDate,
    snapshotExists,
)
from src.db.rebalancingRepository import (
    getRebalancingEventStats,
    getRecentRebalancingEvents,
    insertRebalancingEvent,
)
from src.etl.rebalancingDetector import (
    buildRebalancingEventRecord,
    detectRebalancingChanges,
)
from src.scraper.tigerHoldingsScraper import scrapeTigerHoldings


def setupHoldingsEtlLogger():
    """Holdings ETL 전용 로거를 설정한다."""
    return setupEtlLogger("holdingsEtl", "etl_holdings.log")


def filterEquityRecords(recordList):
    """equity 종목만 포함하는 레코드 목록을 반환한다."""
    equityRecords = []
    for i in range(0, len(recordList)):
        record = recordList[i]
        if record.get("is_equity", True) is True:
            equityRecords.append(record)
    return equityRecords


def processSingleSnapshot(engine, etfCode, snapshotDate, logger):
    """단일 스냅샷일에 대해 스크래핑·적재·리밸런싱 감지를 수행한다."""
    existsResult = snapshotExists(engine, etfCode, snapshotDate)
    if existsResult.get("success") is not True:
        return existsResult

    if existsResult.get("exists") is True:
        logger.info("스냅샷 이미 존재 — 스킵: %s", snapshotDate)
        return {
            "success": True,
            "message": "스냅샷이 이미 존재하여 스킵했습니다.",
            "snapshotDate": snapshotDate,
            "skipped": True,
            "insertedCount": 0,
        }

    scrapeResult = scrapeTigerHoldings(snapshotDate=snapshotDate)
    if scrapeResult.get("success") is not True:
        logger.error(scrapeResult.get("message", ""))
        return scrapeResult

    recordList = scrapeResult.get("records", [])
    logger.info("스크래핑 완료 — %d건 (%s)", len(recordList), snapshotDate)

    loadResult = insertHoldingsSnapshot(engine, recordList)
    if loadResult.get("success") is not True:
        logger.error(loadResult.get("message", ""))
        return loadResult

    logger.info(
        "DB 적재 — INSERT %d건, SKIP %d건",
        loadResult.get("insertedCount", 0),
        loadResult.get("skippedCount", 0),
    )

    rebalancingResult = {
        "success": True,
        "message": "이전 스냅샷 없음 — 리밸런싱 이벤트 생략",
        "eventInserted": False,
    }

    prevDateResult = getPreviousSnapshotDate(engine, etfCode, snapshotDate)
    if prevDateResult.get("success") is not True:
        return prevDateResult

    previousDate = prevDateResult.get("previousSnapshotDate")
    if previousDate is not None:
        prevRowsResult = getSnapshotRows(engine, etfCode, previousDate, equityOnly=True)
        if prevRowsResult.get("success") is not True:
            return prevRowsResult

        equityRecords = filterEquityRecords(recordList)
        detectionResult = detectRebalancingChanges(
            prevRowsResult.get("rows", []),
            equityRecords,
        )

        if detectionResult.get("hasChanges") is True:
            eventRecord = buildRebalancingEventRecord(
                etfCode,
                snapshotDate,
                detectionResult,
                sourceName="Detected",
            )
            eventLoadResult = insertRebalancingEvent(engine, eventRecord)
            rebalancingResult = {
                "success": eventLoadResult.get("success") is True,
                "message": "리밸런싱 이벤트 적재 완료",
                "eventInserted": eventLoadResult.get("inserted", False),
                "detection": detectionResult,
                "event": eventRecord,
            }
            logger.info(
                "리밸런싱 감지 — 추가 %d, 제외 %d, 비중변경 %d, 턴오버 %.3f%%",
                detectionResult.get("addedCount", 0),
                detectionResult.get("removedCount", 0),
                detectionResult.get("changedCount", 0),
                detectionResult.get("totalTurnoverPct", 0),
            )
        else:
            rebalancingResult = {
                "success": True,
                "message": "유의미한 구성 변동 없음 — 이벤트 생략",
                "eventInserted": False,
                "detection": detectionResult,
            }

    return {
        "success": True,
        "message": "단일 스냅샷 ETL 완료",
        "snapshotDate": snapshotDate,
        "skipped": False,
        "scrape": {
            "recordCount": scrapeResult.get("recordCount", 0),
            "validation": scrapeResult.get("validation", {}),
        },
        "load": loadResult,
        "rebalancing": rebalancingResult,
    }


def runHoldingsEtl(runMode="incremental", snapshotDate="", dateList=None):
    """Holdings snapshot + rebalancing_event ETL을 실행한다."""
    logger = setupHoldingsEtlLogger()
    try:
        dbConfig = getDbConfig()
        dbValidation = validateDbConfig(dbConfig)
        if dbValidation.get("success") is not True:
            logger.error(dbValidation.get("message", ""))
            return dbValidation

        connectionTest = testDbConnection()
        if connectionTest.get("success") is not True:
            logger.error(connectionTest.get("message", ""))
            return connectionTest

        kisConfig = getKisConfig()
        etfCode = kisConfig.get("targetEtfCode", "102110")
        etfName = kisConfig.get("targetEtfName", "TIGER 200")
        engine = getDbEngine(includeDatabase=True)

        logger.info("Holdings ETL 시작 — ETF: %s (%s), 모드: %s", etfName, etfCode, runMode)

        if dateList is not None and len(dateList) > 0:
            processResults = []
            successCount = 0
            for i in range(0, len(dateList)):
                dateValue = dateList[i]
                singleResult = processSingleSnapshot(engine, etfCode, dateValue, logger)
                processResults.append(singleResult)
                if singleResult.get("success") is True:
                    successCount = successCount + 1
                if i < len(dateList) - 1:
                    time.sleep(0.3)

            holdingsStats = getHoldingsStats(engine, etfCode)
            eventStats = getRebalancingEventStats(engine, etfCode)
            return {
                "success": successCount > 0,
                "message": "다중 스냅샷 Holdings ETL 완료",
                "etfCode": etfCode,
                "etfName": etfName,
                "runMode": runMode,
                "requestedCount": len(dateList),
                "successCount": successCount,
                "results": processResults,
                "holdingsStats": holdingsStats,
                "eventStats": eventStats,
                "executedAt": datetime.now().isoformat(),
            }

        if snapshotDate == "" and runMode == "incremental":
            targetResult = resolveTargetSnapshotDate(
                engine, etfCode, runMode, explicitDate=""
            )
            if targetResult.get("success") is not True:
                return targetResult

            if targetResult.get("isUpToDate") is True:
                holdingsStats = getHoldingsStats(engine, etfCode)
                eventStats = getRebalancingEventStats(engine, etfCode)
                return {
                    "success": True,
                    "message": "이미 최신 holdings 스냅샷입니다.",
                    "etfCode": etfCode,
                    "etfName": etfName,
                    "runMode": runMode,
                    "holdingsStats": holdingsStats,
                    "eventStats": eventStats,
                }

            snapshotDate = targetResult.get("snapshotDate", "")

        if snapshotDate == "":
            snapshotDate = datetime.now().strftime("%Y-%m-%d")

        singleResult = processSingleSnapshot(engine, etfCode, snapshotDate, logger)
        if singleResult.get("success") is not True:
            return singleResult

        holdingsStats = getHoldingsStats(engine, etfCode)
        eventStats = getRebalancingEventStats(engine, etfCode)
        recentEvents = getRecentRebalancingEvents(engine, etfCode, limitCount=3)

        return {
            "success": True,
            "message": "Holdings ETL 완료",
            "etfCode": etfCode,
            "etfName": etfName,
            "runMode": runMode,
            "snapshot": singleResult,
            "holdingsStats": holdingsStats,
            "eventStats": eventStats,
            "recentEvents": recentEvents.get("events", []),
            "executedAt": datetime.now().isoformat(),
        }
    except Exception as generalError:
        errorMessage = "Holdings ETL 실행 실패: " + str(generalError)
        logger = setupHoldingsEtlLogger()
        logEtlError(logger, errorMessage, {"runMode": runMode})
        return {
            "success": False,
            "message": errorMessage,
        }
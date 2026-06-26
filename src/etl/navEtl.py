# -*- coding: utf-8 -*-
"""KIS NAV ETL 핵심 오케스트레이션 모듈"""

import logging
import os
from datetime import datetime

from src.config.envLoader import getDbConfig, getKisConfig, validateDbConfig, validateKisConfig
from src.db.dbConnection import getDbEngine, testDbConnection
from src.db.navRepository import (
    getNavDailyStats,
    resolveFetchDateRange,
    transformNavApiRows,
    upsertNavDailyRows,
)
from src.kis.kisAuth import refreshKisToken
from src.kis.kisNavClient import fetchNavDailyRange


def getLogFilePath():
    """NAV ETL 로그 파일 경로를 반환한다."""
    from src.config.envLoader import getProjectRoot

    projectRoot = getProjectRoot()
    logDir = os.path.join(projectRoot, "logs")
    if os.path.exists(logDir) is False:
        os.makedirs(logDir, exist_ok=True)
    return os.path.join(logDir, "etl_nav.log")


def setupNavEtlLogger():
    """NAV ETL 전용 로거를 설정한다."""
    logger = logging.getLogger("navEtl")
    if len(logger.handlers) > 0:
        return logger

    logger.setLevel(logging.INFO)
    logFormat = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fileHandler = logging.FileHandler(getLogFilePath(), encoding="utf-8")
    fileHandler.setFormatter(logFormat)
    logger.addHandler(fileHandler)

    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(logFormat)
    logger.addHandler(streamHandler)

    return logger


def runNavEtl(runMode="incremental"):
    """KIS NAV ETL을 실행한다. runMode: incremental | backfill."""
    logger = setupNavEtlLogger()
    try:
        kisConfig = getKisConfig()
        kisValidation = validateKisConfig(kisConfig)
        if kisValidation.get("success") is not True:
            logger.error(kisValidation.get("message", ""))
            return kisValidation

        dbConfig = getDbConfig()
        dbValidation = validateDbConfig(dbConfig)
        if dbValidation.get("success") is not True:
            logger.error(dbValidation.get("message", ""))
            return dbValidation

        connectionTest = testDbConnection()
        if connectionTest.get("success") is not True:
            logger.error(connectionTest.get("message", ""))
            return connectionTest

        etfCode = kisConfig.get("targetEtfCode", "102110")
        etfName = kisConfig.get("targetEtfName", "TIGER 200")
        logger.info("NAV ETL 시작 — ETF: %s (%s), 모드: %s", etfName, etfCode, runMode)

        tokenResult = refreshKisToken(forceRefresh=False)
        if tokenResult.get("success") is not True:
            logger.error(tokenResult.get("message", ""))
            return tokenResult

        engine = getDbEngine(includeDatabase=True)
        dateRangeResult = resolveFetchDateRange(engine, etfCode, runMode)
        if dateRangeResult.get("success") is not True:
            logger.error(dateRangeResult.get("message", ""))
            return dateRangeResult

        if dateRangeResult.get("isUpToDate") is True:
            statsResult = getNavDailyStats(engine, etfCode)
            finalResult = {
                "success": True,
                "message": "이미 최신 상태입니다. 신규 적재 없음.",
                "etfCode": etfCode,
                "etfName": etfName,
                "runMode": runMode,
                "stats": statsResult,
            }
            logger.info(finalResult.get("message", ""))
            return finalResult

        startDate = dateRangeResult.get("startDate", "")
        endDate = dateRangeResult.get("endDate", "")
        effectiveMode = dateRangeResult.get("runMode", runMode)
        logger.info("조회 구간: %s ~ %s (모드: %s)", startDate, endDate, effectiveMode)

        fetchResult = fetchNavDailyRange(etfCode, startDate, endDate)
        if fetchResult.get("success") is not True:
            logger.error(fetchResult.get("message", ""))
            return fetchResult

        apiRows = fetchResult.get("rows", [])
        logger.info(
            "KIS API 수집 완료 — %d건 (배치 %d회)",
            fetchResult.get("rowCount", 0),
            fetchResult.get("batchCount", 0),
        )

        transformResult = transformNavApiRows(etfCode, apiRows)
        recordList = transformResult.get("records", [])
        logger.info("변환 완료 — %d건", transformResult.get("recordCount", 0))

        loadResult = upsertNavDailyRows(engine, recordList)
        if loadResult.get("success") is not True:
            logger.error(loadResult.get("message", ""))
            return loadResult

        statsResult = getNavDailyStats(engine, etfCode)
        logger.info(
            "적재 완료 — UPSERT %d건, DB 누적 %d건 (%s ~ %s)",
            loadResult.get("upsertedCount", 0),
            statsResult.get("rowCount", 0),
            statsResult.get("minTradeDate", ""),
            statsResult.get("maxTradeDate", ""),
        )

        finalResult = {
            "success": True,
            "message": "KIS NAV ETL 완료",
            "etfCode": etfCode,
            "etfName": etfName,
            "runMode": effectiveMode,
            "startDate": startDate,
            "endDate": endDate,
            "fetchedCount": fetchResult.get("rowCount", 0),
            "upsertedCount": loadResult.get("upsertedCount", 0),
            "batchCount": fetchResult.get("batchCount", 0),
            "stats": statsResult,
            "executedAt": datetime.now().isoformat(),
        }
        return finalResult
    except Exception as generalError:
        errorMessage = "NAV ETL 실행 실패: " + str(generalError)
        logger = setupNavEtlLogger()
        logger.error(errorMessage)
        return {
            "success": False,
            "message": errorMessage,
        }
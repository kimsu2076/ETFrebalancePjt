# -*- coding: utf-8 -*-
"""2년치 초기 적재(NAV 백필 + 분기 holdings 백필) 실행 모듈"""

from datetime import datetime

from src.config.envLoader import getDbConfig, getKisConfig, validateDbConfig, validateKisConfig
from src.db.dbConnection import getDbEngine, testDbConnection
from src.db.rebalancingRepository import rebuildRebalancingEvents
from src.etl.dataQualityValidator import runDataQualityValidation
from src.etl.etlLogger import logEtlError, setupEtlLogger
from src.etl.holdingsBackfillDates import getHoldingsBackfillDates
from src.etl.holdingsEtl import runHoldingsEtl
from src.etl.navEtl import runNavEtl


def setupInitialLoadLogger():
    """초기 적재 실행 전용 로거를 설정한다."""
    return setupEtlLogger("initialLoadRunner", "initial_load.log")


def runInitialLoad(skipNav=False, skipHoldings=False, skipValidation=False, customHoldingsDates=None):
    """NAV 백필, holdings 분기 백필, 데이터 품질 검증을 순차 실행한다."""
    logger = setupInitialLoadLogger()
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
        logger.info("2년치 초기 적재 시작 — ETF: %s (%s)", etfName, etfCode)

        navResult = {"success": True, "message": "NAV 백필 스킵", "skipped": True}
        if skipNav is False:
            logger.info("NAV 백필 실행")
            navResult = runNavEtl(runMode="backfill")
            if navResult.get("success") is not True:
                logEtlError(logger, "NAV 백필 실패", {"message": navResult.get("message", "")})
                return {
                    "success": False,
                    "message": "초기 적재 중 NAV 백필 실패",
                    "nav": navResult,
                }
            logger.info("NAV 백필 완료 — %s", navResult.get("message", ""))

        holdingsResult = {"success": True, "message": "Holdings 백필 스킵", "skipped": True}
        if skipHoldings is False:
            holdingsEngine = getDbEngine(includeDatabase=True)
            datesResult = getHoldingsBackfillDates(
                customDates=customHoldingsDates,
                engine=holdingsEngine,
                etfCode=etfCode,
            )
            if datesResult.get("success") is not True:
                return datesResult

            dateList = datesResult.get("dates", [])
            calendarCount = datesResult.get("calendarDateCount", len(dateList))
            logger.info(
                "Holdings 분기 백필 실행 — 달력 %d개 → 영업일 %d개",
                calendarCount,
                len(dateList),
            )
            holdingsResult = runHoldingsEtl(runMode="backfill", dateList=dateList)
            if holdingsResult.get("success") is not True:
                logEtlError(
                    logger,
                    "Holdings 백필 실패",
                    {"message": holdingsResult.get("message", "")},
                )
                return {
                    "success": False,
                    "message": "초기 적재 중 Holdings 백필 실패",
                    "nav": navResult,
                    "holdings": holdingsResult,
                }
            logger.info("Holdings 백필 완료 — %s", holdingsResult.get("message", ""))

        validationResult = {"success": True, "message": "검증 스킵", "skipped": True}
        if skipValidation is False:
            engine = getDbEngine(includeDatabase=True)
            rebuildResult = rebuildRebalancingEvents(engine, etfCode)
            if rebuildResult.get("success") is not True:
                logEtlError(
                    logger,
                    "검증 전 리밸런싱 이벤트 재생성 실패",
                    {"message": rebuildResult.get("message", "")},
                )
                return {
                    "success": False,
                    "message": "검증 전 리밸런싱 이벤트 재생성 실패",
                    "nav": navResult,
                    "holdings": holdingsResult,
                    "rebuild": rebuildResult,
                }
            logger.info(
                "검증 전 이벤트 재생성 — 삭제 %d건, 신규 %d건",
                rebuildResult.get("deletedCount", 0),
                rebuildResult.get("insertedCount", 0),
            )

            logger.info("데이터 품질 검증 실행")
            validationResult = runDataQualityValidation(saveReport=True)
            validationResult["rebuild"] = rebuildResult
            if validationResult.get("success") is not True:
                logEtlError(
                    logger,
                    "데이터 품질 검증 실패",
                    {"message": validationResult.get("message", "")},
                )
                return {
                    "success": False,
                    "message": "초기 적재 후 검증 실패",
                    "nav": navResult,
                    "holdings": holdingsResult,
                    "validation": validationResult,
                }

        overallSuccess = True
        if validationResult.get("skipped") is not True:
            overallSuccess = validationResult.get("overallPassed") is True

        return {
            "success": overallSuccess,
            "message": "2년치 초기 적재 및 검증 완료" if overallSuccess else "초기 적재 완료, 검증 FAIL",
            "etfCode": etfCode,
            "etfName": etfName,
            "nav": navResult,
            "holdings": holdingsResult,
            "validation": validationResult,
            "executedAt": datetime.now().isoformat(),
        }
    except Exception as generalError:
        errorMessage = "초기 적재 실행 실패: " + str(generalError)
        logger.error(errorMessage)
        return {
            "success": False,
            "message": errorMessage,
        }
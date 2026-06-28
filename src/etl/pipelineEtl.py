# -*- coding: utf-8 -*-
"""NAV + Holdings 통합 ETL 파이프라인 모듈"""

from datetime import datetime

from src.config.envLoader import getDbConfig, getKisConfig, validateDbConfig
from src.etl.etlLogger import logEtlError, setupEtlLogger
from src.db.dbConnection import testDbConnection
from src.etl.holdingsEtl import runHoldingsEtl
from src.etl.navEtl import runNavEtl


def setupPipelineLogger():
    """통합 파이프라인 로거를 설정한다."""
    return setupEtlLogger("pipelineEtl", "etl_pipeline.log")


def runFullPipeline(navMode="incremental", holdingsMode="incremental", holdingsDate="", holdingsDates=None):
    """NAV ETL과 Holdings ETL을 순서대로 실행하는 통합 파이프라인이다."""
    logger = setupPipelineLogger()
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

        logger.info(
            "통합 파이프라인 시작 — ETF: %s (%s), NAV: %s, Holdings: %s",
            etfName,
            etfCode,
            navMode,
            holdingsMode,
        )

        navResult = runNavEtl(runMode=navMode)
        if navResult.get("success") is not True:
            logger.error("NAV ETL 실패: %s", navResult.get("message", ""))
            return {
                "success": False,
                "message": "통합 파이프라인 중 NAV ETL 실패",
                "nav": navResult,
            }

        logger.info("NAV ETL 완료: %s", navResult.get("message", ""))

        if holdingsDates is not None and len(holdingsDates) > 0:
            holdingsResult = runHoldingsEtl(
                runMode=holdingsMode,
                dateList=holdingsDates,
            )
        else:
            holdingsResult = runHoldingsEtl(
                runMode=holdingsMode,
                snapshotDate=holdingsDate,
            )

        if holdingsResult.get("success") is not True:
            logger.error("Holdings ETL 실패: %s", holdingsResult.get("message", ""))
            return {
                "success": False,
                "message": "통합 파이프라인 중 Holdings ETL 실패",
                "nav": navResult,
                "holdings": holdingsResult,
            }

        logger.info("Holdings ETL 완료: %s", holdingsResult.get("message", ""))

        return {
            "success": True,
            "message": "통합 ETL 파이프라인 완료",
            "etfCode": etfCode,
            "etfName": etfName,
            "navMode": navMode,
            "holdingsMode": holdingsMode,
            "nav": navResult,
            "holdings": holdingsResult,
            "executedAt": datetime.now().isoformat(),
        }
    except Exception as generalError:
        errorMessage = "통합 파이프라인 실행 실패: " + str(generalError)
        logger = setupPipelineLogger()
        logEtlError(
            logger,
            errorMessage,
            {"navMode": navMode, "holdingsMode": holdingsMode},
        )
        return {
            "success": False,
            "message": errorMessage,
        }
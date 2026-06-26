# -*- coding: utf-8 -*-
"""NAV + Holdings 통합 ETL 파이프라인 모듈"""

import logging
import os
from datetime import datetime

from src.config.envLoader import getDbConfig, getKisConfig, validateDbConfig
from src.db.dbConnection import testDbConnection
from src.etl.holdingsEtl import runHoldingsEtl
from src.etl.navEtl import runNavEtl


def getLogFilePath():
    """통합 파이프라인 로그 파일 경로를 반환한다."""
    from src.config.envLoader import getProjectRoot

    projectRoot = getProjectRoot()
    logDir = os.path.join(projectRoot, "logs")
    if os.path.exists(logDir) is False:
        os.makedirs(logDir, exist_ok=True)
    return os.path.join(logDir, "etl_pipeline.log")


def setupPipelineLogger():
    """통합 파이프라인 로거를 설정한다."""
    logger = logging.getLogger("pipelineEtl")
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
        logger.error(errorMessage)
        return {
            "success": False,
            "message": errorMessage,
        }
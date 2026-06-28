# -*- coding: utf-8 -*-
"""ETL 공통 로깅 유틸리티 (RotatingFileHandler 기반)"""

import logging
import os
from logging.handlers import RotatingFileHandler


DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5


def ensureLogDirectory():
    """프로젝트 logs 디렉터리를 생성하고 경로를 반환한다."""
    from src.config.envLoader import getProjectRoot

    projectRoot = getProjectRoot()
    logDir = os.path.join(projectRoot, "logs")
    if os.path.exists(logDir) is False:
        os.makedirs(logDir, exist_ok=True)
    return logDir


def getEtlLogFilePath(logFileName):
    """로그 파일명을 받아 전체 경로를 반환한다."""
    logDir = ensureLogDirectory()
    return os.path.join(logDir, logFileName)


def setupEtlLogger(loggerName, logFileName, maxBytes=DEFAULT_MAX_BYTES, backupCount=DEFAULT_BACKUP_COUNT):
    """RotatingFileHandler를 사용하는 ETL 전용 로거를 설정한다."""
    logger = logging.getLogger(loggerName)
    if len(logger.handlers) > 0:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    logFormat = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")

    fileHandler = RotatingFileHandler(
        getEtlLogFilePath(logFileName),
        maxBytes=maxBytes,
        backupCount=backupCount,
        encoding="utf-8",
    )
    fileHandler.setFormatter(logFormat)
    logger.addHandler(fileHandler)

    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(logFormat)
    logger.addHandler(streamHandler)

    return logger


def logEtlError(logger, errorMessage, contextDict=None):
    """ETL 실패 시 구조화된 에러 정보를 로그에 기록한다."""
    if contextDict is None:
        contextDict = {}

    contextParts = []
    keyList = list(contextDict.keys())
    for i in range(0, len(keyList)):
        keyName = keyList[i]
        contextParts.append(keyName + "=" + str(contextDict.get(keyName, "")))

    if len(contextParts) > 0:
        logger.error("%s | %s", errorMessage, ", ".join(contextParts))
    else:
        logger.error("%s", errorMessage)
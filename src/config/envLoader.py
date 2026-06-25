# -*- coding: utf-8 -*-
"""환경 변수 로더 모듈"""

import os

from dotenv import load_dotenv


def getProjectRoot():
    """프로젝트 루트 디렉터리 경로를 반환한다."""
    currentDir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(currentDir))


def loadProjectEnv():
    """프로젝트 루트의 .env 파일을 로드한다."""
    projectRoot = getProjectRoot()
    envPath = os.path.join(projectRoot, ".env")
    load_dotenv(envPath, override=False)
    return envPath


def getEnvValue(keyName, defaultValue=""):
    """환경 변수 값을 조회한다. 없으면 기본값을 반환한다."""
    value = os.getenv(keyName, defaultValue)
    if value is None:
        return defaultValue
    return value.strip()


def getKisConfig():
    """KIS API 연동에 필요한 설정 딕셔너리를 반환한다."""
    loadProjectEnv()

    envMode = getEnvValue("KIS_ENV", "real").lower()
    if envMode == "demo":
        urlBase = getEnvValue("KIS_URL_BASE_DEMO", "https://openapivts.koreainvestment.com:29443")
    else:
        urlBase = getEnvValue("KIS_URL_BASE", "https://openapi.koreainvestment.com:9443")

    config = {
        "appKey": getEnvValue("KIS_APP_KEY", ""),
        "appSecret": getEnvValue("KIS_APP_SECRET", ""),
        "envMode": envMode,
        "urlBase": urlBase,
        "targetEtfCode": getEnvValue("TARGET_ETF_CODE", "102110"),
        "targetEtfName": getEnvValue("TARGET_ETF_NAME", "TIGER 200"),
    }
    return config


def validateKisConfig(config):
    """KIS 설정 필수값 검증 결과를 반환한다."""
    missingKeys = []
    requiredFields = ["appKey", "appSecret", "urlBase"]
    for i in range(0, len(requiredFields)):
        fieldName = requiredFields[i]
        fieldValue = config.get(fieldName, "")
        if fieldValue == "" or "xxxx" in fieldValue:
            missingKeys.append(fieldName)

    if len(missingKeys) > 0:
        return {
            "success": False,
            "message": "KIS API 인증 정보가 설정되지 않았습니다. .env 파일의 KIS_APP_KEY, KIS_APP_SECRET을 실제 값으로 채워주세요.",
            "missingKeys": missingKeys,
        }

    return {"success": True, "message": "KIS 설정 검증 완료"}
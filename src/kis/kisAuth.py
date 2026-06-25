# -*- coding: utf-8 -*-
"""KIS Open API OAuth 토큰 발급 및 갱신 모듈"""

import json
import os
import time
from datetime import datetime, timedelta

import requests

from src.config.envLoader import getProjectRoot, getKisConfig


TOKEN_CACHE_FILE = ".kis_token_cache.json"
TOKEN_REFRESH_BUFFER_MINUTES = 30
MAX_RETRY_COUNT = 7


def getTokenCachePath():
    """토큰 캐시 파일 경로를 반환한다."""
    projectRoot = getProjectRoot()
    dataDir = os.path.join(projectRoot, "data")
    if os.path.exists(dataDir) is False:
        os.makedirs(dataDir, exist_ok=True)
    return os.path.join(dataDir, TOKEN_CACHE_FILE)


def readTokenCache():
    """캐시된 토큰 정보를 읽는다. 없거나 만료 임박 시 None을 반환한다."""
    cachePath = getTokenCachePath()
    if os.path.exists(cachePath) is False:
        return None

    try:
        with open(cachePath, "r", encoding="utf-8") as cacheFile:
            cacheData = json.load(cacheFile)

        expiresAtText = cacheData.get("expiresAt", "")
        accessToken = cacheData.get("accessToken", "")
        if accessToken == "" or expiresAtText == "":
            return None

        expiresAt = datetime.fromisoformat(expiresAtText)
        bufferTime = datetime.now() + timedelta(minutes=TOKEN_REFRESH_BUFFER_MINUTES)
        if expiresAt > bufferTime:
            return accessToken
    except Exception:
        return None

    return None


def writeTokenCache(accessToken, expiresAt):
    """발급받은 토큰을 로컬 캐시 파일에 저장한다."""
    cachePath = getTokenCachePath()
    cacheData = {
        "accessToken": accessToken,
        "expiresAt": expiresAt.isoformat(),
        "savedAt": datetime.now().isoformat(),
    }
    with open(cachePath, "w", encoding="utf-8") as cacheFile:
        json.dump(cacheData, cacheFile, ensure_ascii=False, indent=2)


def requestNewToken(appKey, appSecret, urlBase):
    """KIS OAuth 엔드포인트에 토큰 발급을 요청한다."""
    tokenUrl = urlBase + "/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": appKey,
        "appsecret": appSecret,
    }

    lastError = None
    for attempt in range(0, MAX_RETRY_COUNT):
        try:
            response = requests.post(tokenUrl, headers=headers, json=body, timeout=15)
            response.raise_for_status()
            responseJson = response.json()
            accessToken = responseJson.get("access_token", "")
            if accessToken == "":
                return {
                    "success": False,
                    "message": "토큰 응답에 access_token이 없습니다.",
                }

            expiresAt = datetime.now() + timedelta(hours=23)
            writeTokenCache(accessToken, expiresAt)
            return {
                "success": True,
                "message": "KIS OAuth 토큰 발급 완료",
                "accessToken": accessToken,
                "expiresAt": expiresAt.isoformat(),
            }
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as networkError:
            lastError = str(networkError)
            waitSeconds = 2 * (attempt + 1)
            if attempt < MAX_RETRY_COUNT - 1:
                time.sleep(waitSeconds)
        except requests.exceptions.HTTPError as httpError:
            return {
                "success": False,
                "message": "토큰 발급 HTTP 오류: " + str(httpError),
            }
        except Exception as generalError:
            return {
                "success": False,
                "message": "토큰 발급 실패: " + str(generalError),
            }

    return {
        "success": False,
        "message": "토큰 발급 최대 재시도 초과: " + str(lastError),
    }


def refreshKisToken(forceRefresh=False):
    """토큰을 갱신한다. forceRefresh=True이면 캐시를 무시하고 재발급한다."""
    config = getKisConfig()
    appKey = config.get("appKey", "")
    appSecret = config.get("appSecret", "")
    urlBase = config.get("urlBase", "")

    if forceRefresh is False:
        cachedToken = readTokenCache()
        if cachedToken is not None:
            return {
                "success": True,
                "message": "캐시된 KIS 토큰 사용",
                "accessToken": cachedToken,
                "fromCache": True,
            }

    tokenResult = requestNewToken(appKey, appSecret, urlBase)
    if tokenResult.get("success") is True:
        tokenResult["fromCache"] = False
    return tokenResult


def getKisToken():
    """유효한 KIS 접근 토큰을 반환한다. 없으면 자동 발급한다."""
    tokenResult = refreshKisToken(forceRefresh=False)
    if tokenResult.get("success") is True:
        return tokenResult.get("accessToken", "")
    return ""


def buildKisHeaders(accessToken, trId):
    """KIS API 호출용 공통 헤더를 생성한다."""
    config = getKisConfig()
    envMode = config.get("envMode", "real")
    resolvedTrId = trId

    if envMode == "demo":
        if len(trId) > 0 and trId[0] in ("T", "J", "C", "F"):
            resolvedTrId = "V" + trId[1:]

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": "Bearer " + accessToken,
        "appkey": config.get("appKey", ""),
        "appsecret": config.get("appSecret", ""),
        "tr_id": resolvedTrId,
        "custtype": "P",
        "tr_cont": "",
    }
    return headers
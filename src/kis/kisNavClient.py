# -*- coding: utf-8 -*-
"""KIS ETF NAV 조회 클라이언트 모듈"""

import time

import requests

from src.config.envLoader import getKisConfig
from src.kis.kisAuth import buildKisHeaders, getKisToken

NAV_COMPARISON_URL = "/uapi/etfetn/v1/quotations/nav-comparison-trend"
NAV_COMPARISON_TR_ID = "FHPST02440000"

ETF_PRICE_URL = "/uapi/etfetn/v1/quotations/inquire-price"
ETF_PRICE_TR_ID = "FHPST02400000"

MAX_API_RETRY = 5


def retryKisGet(url, headers, params):
    """KIS GET API 호출을 재시도 로직과 함께 수행한다."""
    lastError = None
    for attempt in range(0, MAX_API_RETRY):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            if response.status_code == 429:
                waitSeconds = 2 * (attempt + 2)
                time.sleep(waitSeconds)
                lastError = "429 Too Many Requests"
                continue
            response.raise_for_status()
            return {
                "success": True,
                "response": response,
            }
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as networkError:
            lastError = str(networkError)
            if attempt < MAX_API_RETRY - 1:
                time.sleep(2 * (attempt + 1))
        except requests.exceptions.HTTPError as httpError:
            return {
                "success": False,
                "message": "KIS API HTTP 오류: " + str(httpError),
            }
        except Exception as generalError:
            return {
                "success": False,
                "message": "KIS API 호출 실패: " + str(generalError),
            }

    return {
        "success": False,
        "message": "KIS API 최대 재시도 초과: " + str(lastError),
    }


def parseKisResponse(response):
    """KIS API JSON 응답을 표준 결과 형식으로 변환한다."""
    try:
        responseJson = response.json()
        resultCode = responseJson.get("rt_cd", "")
        if resultCode != "0":
            return {
                "success": False,
                "message": responseJson.get("msg1", "KIS API 오류"),
                "msgCd": responseJson.get("msg_cd", ""),
            }

        parsedResult = {
            "success": True,
            "message": "KIS API 호출 성공",
            "raw": responseJson,
        }
        if "output1" in responseJson:
            parsedResult["output1"] = responseJson.get("output1", {})
        if "output2" in responseJson:
            parsedResult["output2"] = responseJson.get("output2", {})
        if "output" in responseJson:
            parsedResult["output"] = responseJson.get("output", {})
        return parsedResult
    except Exception as parseError:
        return {
            "success": False,
            "message": "KIS API 응답 파싱 실패: " + str(parseError),
        }


def fetchNavComparisonTrend(etfCode, marketDivCode="J"):
    """ETF NAV 비교추이 API를 호출한다 (TIGER 200 등)."""
    try:
        config = getKisConfig()
        accessToken = getKisToken()
        if accessToken == "":
            return {
                "success": False,
                "message": "KIS 접근 토큰을 발급받지 못했습니다.",
            }

        urlBase = config.get("urlBase", "")
        requestUrl = urlBase + NAV_COMPARISON_URL
        headers = buildKisHeaders(accessToken, NAV_COMPARISON_TR_ID)
        params = {
            "FID_COND_MRKT_DIV_CODE": marketDivCode,
            "FID_INPUT_ISCD": etfCode,
        }

        requestResult = retryKisGet(requestUrl, headers, params)
        if requestResult.get("success") is not True:
            return requestResult

        return parseKisResponse(requestResult.get("response"))
    except Exception as generalError:
        return {
            "success": False,
            "message": "NAV 비교추이 조회 실패: " + str(generalError),
        }


def fetchEtfCurrentPrice(etfCode, marketDivCode="J"):
    """ETF/ETN 현재가 API를 호출한다 (NAV 포함 현재 시세)."""
    try:
        config = getKisConfig()
        accessToken = getKisToken()
        if accessToken == "":
            return {
                "success": False,
                "message": "KIS 접근 토큰을 발급받지 못했습니다.",
            }

        urlBase = config.get("urlBase", "")
        requestUrl = urlBase + ETF_PRICE_URL
        headers = buildKisHeaders(accessToken, ETF_PRICE_TR_ID)
        params = {
            "FID_COND_MRKT_DIV_CODE": marketDivCode,
            "FID_INPUT_ISCD": etfCode,
        }

        requestResult = retryKisGet(requestUrl, headers, params)
        if requestResult.get("success") is not True:
            return requestResult

        return parseKisResponse(requestResult.get("response"))
    except Exception as generalError:
        return {
            "success": False,
            "message": "ETF 현재가 조회 실패: " + str(generalError),
        }
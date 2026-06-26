# -*- coding: utf-8 -*-
"""KIS ETF NAV 조회 클라이언트 모듈"""

import time

import requests

from src.config.envLoader import getKisConfig
from src.kis.kisAuth import buildKisHeaders, getKisToken

NAV_COMPARISON_URL = "/uapi/etfetn/v1/quotations/nav-comparison-trend"
NAV_COMPARISON_TR_ID = "FHPST02440000"

NAV_DAILY_TREND_URL = "/uapi/etfetn/v1/quotations/nav-comparison-daily-trend"
NAV_DAILY_TREND_TR_ID = "FHPST02440200"

ETF_PRICE_URL = "/uapi/etfetn/v1/quotations/inquire-price"
ETF_PRICE_TR_ID = "FHPST02400000"

MAX_API_RETRY = 5
MAX_NAV_DAILY_ROWS = 100
API_CALL_SLEEP_SECONDS = 0.25


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


def fetchNavComparisonDailyTrend(etfCode, startDate, endDate, marketDivCode="J"):
    """ETF NAV 비교추이(일) API를 기간 지정으로 호출한다. 최대 100건 반환."""
    try:
        config = getKisConfig()
        accessToken = getKisToken()
        if accessToken == "":
            return {
                "success": False,
                "message": "KIS 접근 토큰을 발급받지 못했습니다.",
            }

        urlBase = config.get("urlBase", "")
        requestUrl = urlBase + NAV_DAILY_TREND_URL
        headers = buildKisHeaders(accessToken, NAV_DAILY_TREND_TR_ID)
        params = {
            "FID_COND_MRKT_DIV_CODE": marketDivCode,
            "FID_INPUT_ISCD": etfCode,
            "FID_INPUT_DATE_1": startDate,
            "FID_INPUT_DATE_2": endDate,
        }

        requestResult = retryKisGet(requestUrl, headers, params)
        if requestResult.get("success") is not True:
            return requestResult

        parsedResult = parseKisResponse(requestResult.get("response"))
        if parsedResult.get("success") is not True:
            return parsedResult

        outputRows = parsedResult.get("output", [])
        if isinstance(outputRows, dict):
            outputRows = [outputRows]
        elif isinstance(outputRows, list) is False:
            outputRows = []

        parsedResult["rows"] = outputRows
        parsedResult["rowCount"] = len(outputRows)
        return parsedResult
    except Exception as generalError:
        return {
            "success": False,
            "message": "NAV 비교추이(일) 조회 실패: " + str(generalError),
        }


def subtractOneDay(dateText):
    """YYYYMMDD 문자열에서 하루를 뺀 날짜 문자열을 반환한다."""
    from datetime import datetime, timedelta

    dateValue = datetime.strptime(dateText, "%Y%m%d")
    previousDate = dateValue - timedelta(days=1)
    return previousDate.strftime("%Y%m%d")


def getOldestTradeDate(rows):
    """API 응답 행 목록에서 가장 오래된 영업일자를 반환한다."""
    if rows is None or len(rows) == 0:
        return ""

    oldestDate = ""
    for i in range(0, len(rows)):
        rowData = rows[i]
        tradeDate = rowData.get("stck_bsop_date", "")
        if tradeDate == "":
            continue
        if oldestDate == "" or tradeDate < oldestDate:
            oldestDate = tradeDate
    return oldestDate


def mergeNavRowsByDate(targetRows, sourceRows):
    """날짜 기준으로 NAV 일별 행을 병합한다. 기존 키는 덮어쓰지 않는다."""
    for i in range(0, len(sourceRows)):
        sourceRow = sourceRows[i]
        tradeDate = sourceRow.get("stck_bsop_date", "")
        if tradeDate == "":
            continue
        if tradeDate in targetRows:
            continue
        targetRows[tradeDate] = sourceRow


def fetchNavDailyRange(etfCode, startDate, endDate, marketDivCode="J"):
    """NAV 비교추이(일) API를 100건 단위로 분할 호출하여 전체 기간 데이터를 수집한다."""
    try:
        mergedRows = {}
        currentEndDate = endDate
        batchCount = 0
        totalFetched = 0

        while currentEndDate >= startDate:
            batchResult = fetchNavComparisonDailyTrend(
                etfCode,
                startDate,
                currentEndDate,
                marketDivCode,
            )
            if batchResult.get("success") is not True:
                return batchResult

            batchRows = batchResult.get("rows", [])
            batchCount = batchCount + 1
            totalFetched = totalFetched + len(batchRows)

            if len(batchRows) == 0:
                break

            mergeNavRowsByDate(mergedRows, batchRows)
            oldestDate = getOldestTradeDate(batchRows)

            if oldestDate == "":
                break
            if oldestDate <= startDate:
                break
            if len(batchRows) < MAX_NAV_DAILY_ROWS:
                break

            currentEndDate = subtractOneDay(oldestDate)
            time.sleep(API_CALL_SLEEP_SECONDS)

        rowList = []
        dateKeys = list(mergedRows.keys())
        dateKeys.sort()
        for i in range(0, len(dateKeys)):
            dateKey = dateKeys[i]
            rowList.append(mergedRows[dateKey])

        return {
            "success": True,
            "message": "NAV 일별 기간 조회 완료",
            "rows": rowList,
            "rowCount": len(rowList),
            "batchCount": batchCount,
            "totalFetched": totalFetched,
            "startDate": startDate,
            "endDate": endDate,
        }
    except Exception as generalError:
        return {
            "success": False,
            "message": "NAV 일별 기간 조회 실패: " + str(generalError),
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
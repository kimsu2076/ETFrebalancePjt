# -*- coding: utf-8 -*-
"""미래에셋 TIGER ETF 사이트 구성종목 스크래퍼 모듈"""

import json
import os
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from src.config.envLoader import getEnvValue, getKisConfig, getProjectRoot, loadProjectEnv

TIGER_BASE_URL = "http://investments.miraeasset.com/tigeretf"
HOLDINGS_LIST_URL = TIGER_BASE_URL + "/ko/product/search/detail/pdfListAjax.ajax"
DEFAULT_KSD_FUND = "KR7102110004"
DEFAULT_LIST_COUNT = 200
REQUEST_TIMEOUT_SECONDS = 20
REQUEST_SLEEP_SECONDS = 0.3
WEIGHT_SUM_TOLERANCE = 2.0


def getTigerScraperConfig():
    """TIGER holdings 스크래퍼 설정을 반환한다."""
    loadProjectEnv()
    kisConfig = getKisConfig()

    config = {
        "etfCode": getEnvValue("TARGET_ETF_CODE", "102110"),
        "etfName": getEnvValue("TARGET_ETF_NAME", "TIGER 200"),
        "ksdFund": getEnvValue("TIGER_KSD_FUND", DEFAULT_KSD_FUND),
        "baseUrl": getEnvValue("TIGER_BASE_URL", TIGER_BASE_URL),
        "weightTolerance": WEIGHT_SUM_TOLERANCE,
    }
    return config


def buildRequestHeaders():
    """TIGER 사이트 AJAX 요청용 헤더를 생성한다."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": TIGER_BASE_URL + "/ko/product/search/detail/index.do",
    }
    return headers


def normalizeSnapshotDate(dateText):
    """다양한 날짜 입력을 YYYY-MM-DD 형식으로 정규화한다."""
    if dateText is None or dateText == "":
        return datetime.now().strftime("%Y-%m-%d")

    if hasattr(dateText, "strftime"):
        return dateText.strftime("%Y-%m-%d")

    cleanedText = str(dateText).strip()
    cleanedText = cleanedText.replace(".", "")
    cleanedText = cleanedText.replace("-", "")
    cleanedText = cleanedText.replace("/", "")

    if len(cleanedText) == 8 and cleanedText.isdigit() is True:
        return (
            cleanedText[0:4]
            + "-"
            + cleanedText[4:6]
            + "-"
            + cleanedText[6:8]
        )

    return cleanedText


def formatFixDateParam(snapshotDate):
    """API fixDate 파라미터용 YYYYMMDD 문자열을 반환한다."""
    normalizedDate = normalizeSnapshotDate(snapshotDate)
    return normalizedDate.replace("-", "")


def parseNumberText(rawText):
    """쉼표·특수문자가 포함된 숫자 문자열을 float으로 변환한다."""
    if rawText is None:
        return None
    if rawText == "":
        return None

    cleanedText = str(rawText).strip()
    cleanedText = cleanedText.replace(",", "")
    cleanedText = re.sub(r"[^0-9.\-]", "", cleanedText)

    if cleanedText == "" or cleanedText == "-":
        return None

    try:
        return float(cleanedText)
    except ValueError:
        return None


def isEquityStockCode(stockCode):
    """일반 상장 종목코드 여부를 판별한다. KRD 등 현금성 코드는 False."""
    if stockCode is None or stockCode == "":
        return False

    codeText = stockCode.strip().upper()
    if codeText.startswith("KRD"):
        return False
    if len(codeText) == 6 and codeText.isalnum() is True:
        return True
    return False


def parseHoldingsHtmlRows(htmlText):
    """pdfListAjax HTML 응답에서 구성종목 행 목록을 파싱한다."""
    soupObject = BeautifulSoup(htmlText, "lxml")
    tableRows = soupObject.find_all("tr", attrs={"data-tot-cnt": True})
    parsedRows = []

    for i in range(0, len(tableRows)):
        rowElement = tableRows[i]
        cellList = rowElement.find_all("td")
        if len(cellList) < 5:
            continue

        stockCode = cellList[0].get_text(strip=True)
        stockName = cellList[1].get_text(strip=True)
        sharesValue = parseNumberText(cellList[2].get_text(strip=True))
        marketValue = parseNumberText(cellList[3].get_text(strip=True))
        weightPct = parseNumberText(cellList[4].get_text(strip=True))

        rowData = {
            "stock_code": stockCode,
            "stock_name": stockName,
            "shares": sharesValue,
            "market_value_krw": marketValue,
            "weight_pct": weightPct,
            "is_equity": isEquityStockCode(stockCode),
        }
        parsedRows.append(rowData)

    return parsedRows


def fetchHoldingsHtml(ksdFund, snapshotDate, orderCode="SRD", periodCode="Week01"):
    """TIGER pdfListAjax API에서 구성종목 HTML을 수집한다."""
    fixDateParam = formatFixDateParam(snapshotDate)
    requestParams = {
        "ksdFund": ksdFund,
        "pageIndex": "1",
        "firstIndex": "0",
        "listCnt": str(DEFAULT_LIST_COUNT),
        "fixDate": fixDateParam,
        "prfPrd": periodCode,
        "order": orderCode,
    }

    try:
        response = requests.get(
            HOLDINGS_LIST_URL,
            params=requestParams,
            headers=buildRequestHeaders(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return {
            "success": True,
            "message": "구성종목 HTML 수집 완료",
            "htmlText": response.text,
            "fixDate": fixDateParam,
            "requestParams": requestParams,
        }
    except requests.exceptions.HTTPError as httpError:
        return {
            "success": False,
            "message": "구성종목 HTML HTTP 오류: " + str(httpError),
        }
    except Exception as generalError:
        return {
            "success": False,
            "message": "구성종목 HTML 수집 실패: " + str(generalError),
        }


def buildHoldingsRecords(parsedRows, etfCode, snapshotDate):
    """파싱된 행을 etf_holdings_snapshot 적재 형식으로 변환한다."""
    normalizedDate = normalizeSnapshotDate(snapshotDate)
    recordList = []
    equityRank = 0

    for i in range(0, len(parsedRows)):
        rowData = parsedRows[i]
        stockCode = rowData.get("stock_code", "")
        isEquity = rowData.get("is_equity", False)

        rankValue = None
        if isEquity is True:
            equityRank = equityRank + 1
            rankValue = equityRank

        sharesValue = rowData.get("shares")
        if sharesValue is not None:
            sharesValue = int(sharesValue)

        record = {
            "snapshot_date": normalizedDate,
            "etf_code": etfCode,
            "stock_code": stockCode,
            "stock_name": rowData.get("stock_name", ""),
            "weight_pct": rowData.get("weight_pct"),
            "shares": sharesValue,
            "market_value_krw": rowData.get("market_value_krw"),
            "rank_in_portfolio": rankValue,
            "sector": None,
            "is_equity": isEquity,
        }
        recordList.append(record)

    return recordList


def validateHoldingsRecords(recordList, weightTolerance):
    """구성종목 비중 합계 및 음수 값을 검증한다."""
    if recordList is None or len(recordList) == 0:
        return {
            "success": False,
            "message": "검증할 구성종목 데이터가 없습니다.",
        }

    weightSum = 0.0
    equityCount = 0
    cashLikeCount = 0
    negativeCount = 0

    for i in range(0, len(recordList)):
        record = recordList[i]
        weightValue = record.get("weight_pct")
        isEquity = record.get("is_equity", False)

        if weightValue is not None and isEquity is True:
            if weightValue < 0:
                negativeCount = negativeCount + 1
            weightSum = weightSum + weightValue

        if isEquity is True:
            equityCount = equityCount + 1
        else:
            cashLikeCount = cashLikeCount + 1

    weightGap = abs(100.0 - weightSum)
    isWeightValid = weightGap <= weightTolerance

    validationMessage = "구성종목 검증 완료"
    if isWeightValid is False:
        validationMessage = (
            "비중 합계가 100%에서 "
            + str(round(weightGap, 2))
            + "% 벗어났습니다. (허용오차 "
            + str(weightTolerance)
            + "%)"
        )

    if negativeCount > 0:
        validationMessage = validationMessage + " / 음수 비중 " + str(negativeCount) + "건"

    return {
        "success": isWeightValid and negativeCount == 0,
        "message": validationMessage,
        "equityCount": equityCount,
        "cashLikeCount": cashLikeCount,
        "weightSum": round(weightSum, 3),
        "weightGap": round(weightGap, 3),
        "negativeCount": negativeCount,
    }


def scrapeTigerHoldings(snapshotDate="", orderCode="SRD", periodCode="Week01"):
    """TIGER ETF 구성종목 스냅샷을 수집·파싱·검증한다."""
    try:
        scraperConfig = getTigerScraperConfig()
        etfCode = scraperConfig.get("etfCode", "102110")
        etfName = scraperConfig.get("etfName", "TIGER 200")
        ksdFund = scraperConfig.get("ksdFund", DEFAULT_KSD_FUND)
        weightTolerance = scraperConfig.get("weightTolerance", WEIGHT_SUM_TOLERANCE)

        if snapshotDate == "":
            snapshotDate = datetime.now().strftime("%Y-%m-%d")

        htmlResult = fetchHoldingsHtml(
            ksdFund,
            snapshotDate,
            orderCode=orderCode,
            periodCode=periodCode,
        )
        if htmlResult.get("success") is not True:
            return htmlResult

        parsedRows = parseHoldingsHtmlRows(htmlResult.get("htmlText", ""))
        if len(parsedRows) == 0:
            return {
                "success": False,
                "message": "기준일 "
                + normalizeSnapshotDate(snapshotDate)
                + " 구성종목 데이터가 없습니다. 영업일인지 확인해주세요.",
                "fixDate": htmlResult.get("fixDate", ""),
            }

        recordList = buildHoldingsRecords(parsedRows, etfCode, snapshotDate)
        validationResult = validateHoldingsRecords(recordList, weightTolerance)

        topHoldings = []
        previewCount = 5
        if len(recordList) < previewCount:
            previewCount = len(recordList)
        for i in range(0, previewCount):
            topHoldings.append(recordList[i])

        return {
            "success": validationResult.get("success") is True,
            "message": "TIGER 구성종목 스크래핑 완료",
            "etfCode": etfCode,
            "etfName": etfName,
            "ksdFund": ksdFund,
            "snapshotDate": normalizeSnapshotDate(snapshotDate),
            "fixDate": htmlResult.get("fixDate", ""),
            "recordCount": len(recordList),
            "records": recordList,
            "validation": validationResult,
            "topHoldings": topHoldings,
            "source": "tiger_pdfListAjax",
        }
    except Exception as generalError:
        return {
            "success": False,
            "message": "TIGER 구성종목 스크래핑 실패: " + str(generalError),
        }


def scrapeTigerHoldingsRange(dateList):
    """여러 기준일의 구성종목 스냅샷을 순차 수집한다."""
    resultList = []
    successCount = 0

    for i in range(0, len(dateList)):
        dateValue = dateList[i]
        scrapeResult = scrapeTigerHoldings(snapshotDate=dateValue)
        resultList.append(scrapeResult)
        if scrapeResult.get("success") is True:
            successCount = successCount + 1
        if i < len(dateList) - 1:
            time.sleep(REQUEST_SLEEP_SECONDS)

    return {
        "success": successCount > 0,
        "message": "기간별 구성종목 스크래핑 완료",
        "requestedCount": len(dateList),
        "successCount": successCount,
        "results": resultList,
    }


def getDefaultOutputDir():
    """스크래퍼 JSON 결과 저장 디렉터리를 반환한다."""
    projectRoot = getProjectRoot()
    outputDir = os.path.join(projectRoot, "data", "holdings")
    if os.path.exists(outputDir) is False:
        os.makedirs(outputDir, exist_ok=True)
    return outputDir


def saveHoldingsJson(scrapeResult, outputPath=""):
    """스크래핑 결과를 JSON 파일로 저장한다."""
    if scrapeResult.get("success") is not True:
        return {
            "success": False,
            "message": "저장할 유효한 스크래핑 결과가 없습니다.",
        }

    if outputPath == "":
        outputDir = getDefaultOutputDir()
        snapshotDate = scrapeResult.get("snapshotDate", "unknown")
        etfCode = scrapeResult.get("etfCode", "etf")
        fileName = "holdings_" + etfCode + "_" + snapshotDate.replace("-", "") + ".json"
        outputPath = os.path.join(outputDir, fileName)

    savePayload = {
        "etfCode": scrapeResult.get("etfCode"),
        "etfName": scrapeResult.get("etfName"),
        "snapshotDate": scrapeResult.get("snapshotDate"),
        "recordCount": scrapeResult.get("recordCount"),
        "validation": scrapeResult.get("validation"),
        "source": scrapeResult.get("source"),
        "records": scrapeResult.get("records"),
        "savedAt": datetime.now().isoformat(),
    }

    try:
        with open(outputPath, "w", encoding="utf-8") as outputFile:
            json.dump(savePayload, outputFile, ensure_ascii=False, indent=2)
        return {
            "success": True,
            "message": "구성종목 JSON 저장 완료",
            "outputPath": outputPath,
        }
    except Exception as saveError:
        return {
            "success": False,
            "message": "구성종목 JSON 저장 실패: " + str(saveError),
        }
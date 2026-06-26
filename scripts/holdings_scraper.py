# -*- coding: utf-8 -*-
"""TIGER ETF 구성종목 스크래퍼 CLI (4단계)"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.envLoader import loadProjectEnv
from src.scraper.tigerHoldingsScraper import (
    saveHoldingsJson,
    scrapeTigerHoldings,
    scrapeTigerHoldingsRange,
)


def parseArguments():
    """CLI 인자를 파싱한다."""
    argumentParser = argparse.ArgumentParser(description="TIGER ETF 구성종목 스크래퍼")
    argumentParser.add_argument(
        "--date",
        default="",
        help="기준일 (YYYY-MM-DD / YYYYMMDD / YYYY.MM.DD). 미입력 시 최근 영업일",
    )
    argumentParser.add_argument(
        "--dates",
        default="",
        help="쉼표 구분 다중 기준일 (예: 20240625,20241230,20250625)",
    )
    argumentParser.add_argument(
        "--order",
        default="SRD",
        help="정렬 코드 (SRD: 비중 내림차순, 기본값)",
    )
    argumentParser.add_argument(
        "--period",
        default="Week01",
        help="기간 코드 (Week01/Month01/Month03/Month06/Year01)",
    )
    argumentParser.add_argument(
        "--save",
        action="store_true",
        help="결과를 data/holdings/ JSON 파일로 저장",
    )
    argumentParser.add_argument(
        "--output",
        default="",
        help="JSON 저장 경로 (미입력 시 자동 생성)",
    )
    argumentParser.add_argument(
        "--preview",
        type=int,
        default=5,
        help="콘솔 미리보기 상위 N종목 (기본 5)",
    )
    return argumentParser.parse_args()


def buildSummaryResponse(scrapeResult, previewCount):
    """콘솔 출력용 요약 응답을 생성한다. 전체 records는 preview만 포함."""
    summaryResult = dict(scrapeResult)
    recordList = scrapeResult.get("records", [])
    previewList = []

    if previewCount < 1:
        previewCount = 1
    if len(recordList) < previewCount:
        previewCount = len(recordList)

    for i in range(0, previewCount):
        previewList.append(recordList[i])

    summaryResult["records"] = previewList
    summaryResult["previewCount"] = previewCount
    summaryResult["totalRecordCount"] = scrapeResult.get("recordCount", 0)
    return summaryResult


def runHoldingsScraperCli():
    """CLI 진입점에서 TIGER 구성종목 스크래핑을 실행한다."""
    try:
        envPath = loadProjectEnv()
        print("환경 파일 로드:", envPath)

        cliArgs = parseArguments()

        if cliArgs.dates != "":
            dateParts = cliArgs.dates.split(",")
            dateList = []
            for i in range(0, len(dateParts)):
                dateText = dateParts[i].strip()
                if dateText != "":
                    dateList.append(dateText)

            rangeResult = scrapeTigerHoldingsRange(dateList)
            rangeSummary = {
                "success": rangeResult.get("success"),
                "message": rangeResult.get("message"),
                "requestedCount": rangeResult.get("requestedCount"),
                "successCount": rangeResult.get("successCount"),
                "results": [],
            }
            itemResults = rangeResult.get("results", [])
            for i in range(0, len(itemResults)):
                itemResult = itemResults[i]
                rangeSummary["results"].append(
                    buildSummaryResponse(itemResult, cliArgs.preview)
                )
            print(json.dumps(rangeSummary, ensure_ascii=False, indent=2, default=str))

            if cliArgs.save is True:
                results = rangeResult.get("results", [])
                for i in range(0, len(results)):
                    itemResult = results[i]
                    if itemResult.get("success") is True:
                        saveResult = saveHoldingsJson(itemResult, cliArgs.output)
                        print(json.dumps(saveResult, ensure_ascii=False, indent=2))

            return rangeResult

        scrapeResult = scrapeTigerHoldings(
            snapshotDate=cliArgs.date,
            orderCode=cliArgs.order,
            periodCode=cliArgs.period,
        )

        summaryResult = buildSummaryResponse(scrapeResult, cliArgs.preview)
        print(json.dumps(summaryResult, ensure_ascii=False, indent=2, default=str))

        if scrapeResult.get("success") is True and cliArgs.save is True:
            saveResult = saveHoldingsJson(scrapeResult, cliArgs.output)
            print(json.dumps(saveResult, ensure_ascii=False, indent=2))

        return scrapeResult
    except Exception as generalError:
        return {
            "success": False,
            "message": "holdings_scraper 실행 실패: " + str(generalError),
        }


if __name__ == "__main__":
    cliResult = runHoldingsScraperCli()
    if cliResult.get("success") is not True:
        sys.exit(1)
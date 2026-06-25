# -*- coding: utf-8 -*-
"""KIS API 1단계 샘플 테스트: OAuth 토큰 발급 + TIGER 200 NAV 조회"""

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.envLoader import getKisConfig, loadProjectEnv, validateKisConfig
from src.kis.kisAuth import refreshKisToken
from src.kis.kisNavClient import fetchEtfCurrentPrice, fetchNavComparisonTrend


def extractNavSummary(outputData):
    """NAV 관련 핵심 필드만 추출한다."""
    if isinstance(outputData, list):
        if len(outputData) > 0:
            outputData = outputData[0]
        else:
            return {}

    if isinstance(outputData, dict) is False:
        return {}

    summaryKeys = [
        "stck_prpr",
        "nav",
        "nav_prdy_vrss",
        "nav_prdy_ctrt",
        "prdy_clpr_nav",
        "acml_vol",
        "acml_tr_pbmn",
    ]
    summary = {}
    for i in range(0, len(summaryKeys)):
        keyName = summaryKeys[i]
        if keyName in outputData:
            summary[keyName] = outputData.get(keyName)
    return summary


def runKisNavSampleTest():
    """토큰 발급과 NAV 샘플 API 호출을 순서대로 실행한다."""
    try:
        envPath = loadProjectEnv()
        print("환경 파일 로드:", envPath)

        config = getKisConfig()
        validation = validateKisConfig(config)
        if validation.get("success") is not True:
            print(json.dumps(validation, ensure_ascii=False, indent=2))
            return validation

        etfCode = config.get("targetEtfCode", "102110")
        etfName = config.get("targetEtfName", "TIGER 200")
        print("대상 ETF:", etfName, "(" + etfCode + ")")

        tokenResult = refreshKisToken(forceRefresh=False)
        print("토큰 발급 결과:", json.dumps({
            "success": tokenResult.get("success"),
            "message": tokenResult.get("message"),
            "fromCache": tokenResult.get("fromCache", False),
        }, ensure_ascii=False, indent=2))

        if tokenResult.get("success") is not True:
            return tokenResult

        navTrendResult = fetchNavComparisonTrend(etfCode, "J")
        if navTrendResult.get("success") is True:
            output1 = navTrendResult.get("output1", {})
            output2 = navTrendResult.get("output2", {})
            navTrendResult["navSummary"] = extractNavSummary(output1)
            navTrendResult["trendSummary"] = extractNavSummary(output2)
            del navTrendResult["raw"]

        print("NAV 비교추이 결과:", json.dumps(navTrendResult, ensure_ascii=False, indent=2))

        priceResult = fetchEtfCurrentPrice(etfCode, "J")
        if priceResult.get("success") is True:
            priceResult["navSummary"] = extractNavSummary(priceResult.get("output", {}))
            if "raw" in priceResult:
                del priceResult["raw"]

        print("ETF 현재가 결과:", json.dumps(priceResult, ensure_ascii=False, indent=2))

        finalResult = {
            "success": navTrendResult.get("success") is True and priceResult.get("success") is True,
            "message": "KIS NAV 샘플 호출 테스트 완료",
            "etfCode": etfCode,
            "etfName": etfName,
            "tokenFromCache": tokenResult.get("fromCache", False),
            "navTrend": navTrendResult,
            "etfPrice": priceResult,
        }
        return finalResult
    except Exception as generalError:
        return {
            "success": False,
            "message": "샘플 테스트 실행 실패: " + str(generalError),
        }


if __name__ == "__main__":
    result = runKisNavSampleTest()
    if result.get("success") is not True:
        sys.exit(1)
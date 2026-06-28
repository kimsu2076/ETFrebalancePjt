# -*- coding: utf-8 -*-
"""2년치 초기 적재(NAV + 분기 holdings + 검증) CLI (6단계)"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.envLoader import loadProjectEnv
from src.etl.initialLoadRunner import runInitialLoad


def parseArguments():
    """CLI 인자를 파싱한다."""
    argumentParser = argparse.ArgumentParser(
        description="2년치 초기 적재 — NAV 백필 + 분기 holdings 백필 + 데이터 품질 검증"
    )
    argumentParser.add_argument(
        "--skip-nav",
        action="store_true",
        help="NAV 백필 단계 스킵",
    )
    argumentParser.add_argument(
        "--skip-holdings",
        action="store_true",
        help="Holdings 분기 백필 단계 스킵",
    )
    argumentParser.add_argument(
        "--skip-validation",
        action="store_true",
        help="데이터 품질 검증 단계 스킵",
    )
    argumentParser.add_argument(
        "--holdings-dates",
        default="",
        help="쉼표 구분 holdings 백필 기준일 (미지정 시 KOSPI200 분기 일정 사용)",
    )
    return argumentParser.parse_args()


def runInitialLoadCli():
    """CLI 진입점에서 2년치 초기 적재를 실행한다."""
    try:
        envPath = loadProjectEnv()
        print("환경 파일 로드:", envPath)

        cliArgs = parseArguments()
        customDates = None
        if cliArgs.holdings_dates != "":
            dateParts = cliArgs.holdings_dates.split(",")
            customDates = []
            for i in range(0, len(dateParts)):
                dateText = dateParts[i].strip()
                if dateText != "":
                    customDates.append(dateText)

        result = runInitialLoad(
            skipNav=cliArgs.skip_nav,
            skipHoldings=cliArgs.skip_holdings,
            skipValidation=cliArgs.skip_validation,
            customHoldingsDates=customDates,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return result
    except Exception as generalError:
        return {
            "success": False,
            "message": "runInitialLoad 실행 실패: " + str(generalError),
        }


if __name__ == "__main__":
    cliResult = runInitialLoadCli()
    if cliResult.get("success") is not True:
        sys.exit(1)
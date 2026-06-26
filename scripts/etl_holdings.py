# -*- coding: utf-8 -*-
"""Holdings snapshot + rebalancing_event ETL CLI (5단계)"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.envLoader import loadProjectEnv
from src.etl.holdingsEtl import runHoldingsEtl


def parseArguments():
    """CLI 인자를 파싱한다."""
    argumentParser = argparse.ArgumentParser(
        description="Holdings snapshot + rebalancing_event ETL"
    )
    argumentParser.add_argument(
        "--mode",
        choices=["incremental", "single", "backfill"],
        default="incremental",
        help="incremental: NAV 최종일 기준 증분, single: --date 지정, backfill: --dates",
    )
    argumentParser.add_argument(
        "--date",
        default="",
        help="단일 스냅샷 기준일 (single 모드)",
    )
    argumentParser.add_argument(
        "--dates",
        default="",
        help="쉼표 구분 다중 기준일 (backfill 모드)",
    )
    return argumentParser.parse_args()


def runEtlHoldingsCli():
    """CLI 진입점에서 Holdings ETL을 실행한다."""
    try:
        envPath = loadProjectEnv()
        print("환경 파일 로드:", envPath)

        cliArgs = parseArguments()
        print("실행 모드:", cliArgs.mode)

        dateList = None
        snapshotDate = ""

        if cliArgs.mode == "backfill":
            if cliArgs.dates == "":
                return {
                    "success": False,
                    "message": "backfill 모드는 --dates 인자가 필요합니다.",
                }
            dateParts = cliArgs.dates.split(",")
            dateList = []
            for i in range(0, len(dateParts)):
                dateText = dateParts[i].strip()
                if dateText != "":
                    dateList.append(dateText)
        elif cliArgs.mode == "single":
            if cliArgs.date == "":
                return {
                    "success": False,
                    "message": "single 모드는 --date 인자가 필요합니다.",
                }
            snapshotDate = cliArgs.date
        elif cliArgs.date != "":
            snapshotDate = cliArgs.date

        result = runHoldingsEtl(
            runMode=cliArgs.mode,
            snapshotDate=snapshotDate,
            dateList=dateList,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return result
    except Exception as generalError:
        return {
            "success": False,
            "message": "etl_holdings 실행 실패: " + str(generalError),
        }


if __name__ == "__main__":
    cliResult = runEtlHoldingsCli()
    if cliResult.get("success") is not True:
        sys.exit(1)
# -*- coding: utf-8 -*-
"""NAV + Holdings 통합 ETL 파이프라인 CLI (5단계)"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.envLoader import loadProjectEnv
from src.etl.pipelineEtl import runFullPipeline


def parseArguments():
    """CLI 인자를 파싱한다."""
    argumentParser = argparse.ArgumentParser(description="NAV + Holdings 통합 ETL 파이프라인")
    argumentParser.add_argument(
        "--nav-mode",
        choices=["incremental", "backfill"],
        default="incremental",
        help="NAV ETL 실행 모드",
    )
    argumentParser.add_argument(
        "--holdings-mode",
        choices=["incremental", "single", "backfill"],
        default="incremental",
        help="Holdings ETL 실행 모드",
    )
    argumentParser.add_argument(
        "--holdings-date",
        default="",
        help="Holdings 단일 기준일 (holdings-mode=single)",
    )
    argumentParser.add_argument(
        "--holdings-dates",
        default="",
        help="Holdings 다중 기준일 (holdings-mode=backfill)",
    )
    return argumentParser.parse_args()


def runEtlPipelineCli():
    """CLI 진입점에서 통합 ETL 파이프라인을 실행한다."""
    try:
        envPath = loadProjectEnv()
        print("환경 파일 로드:", envPath)

        cliArgs = parseArguments()
        print("NAV 모드:", cliArgs.nav_mode)
        print("Holdings 모드:", cliArgs.holdings_mode)

        holdingsDates = None
        if cliArgs.holdings_mode == "backfill":
            if cliArgs.holdings_dates == "":
                return {
                    "success": False,
                    "message": "holdings backfill 모드는 --holdings-dates가 필요합니다.",
                }
            dateParts = cliArgs.holdings_dates.split(",")
            holdingsDates = []
            for i in range(0, len(dateParts)):
                dateText = dateParts[i].strip()
                if dateText != "":
                    holdingsDates.append(dateText)

        result = runFullPipeline(
            navMode=cliArgs.nav_mode,
            holdingsMode=cliArgs.holdings_mode,
            holdingsDate=cliArgs.holdings_date,
            holdingsDates=holdingsDates,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return result
    except Exception as generalError:
        return {
            "success": False,
            "message": "etl_pipeline 실행 실패: " + str(generalError),
        }


if __name__ == "__main__":
    cliResult = runEtlPipelineCli()
    if cliResult.get("success") is not True:
        sys.exit(1)
# -*- coding: utf-8 -*-
"""데이터 품질 검증 CLI (6단계)"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.envLoader import loadProjectEnv
from src.etl.dataQualityValidator import runDataQualityValidation


def parseArguments():
    """CLI 인자를 파싱한다."""
    argumentParser = argparse.ArgumentParser(description="ETF Rebalance ETL 데이터 품질 검증")
    argumentParser.add_argument(
        "--no-save",
        action="store_true",
        help="리포트 파일 저장 없이 콘솔 출력만 수행",
    )
    return argumentParser.parse_args()


def runValidateDataCli():
    """CLI 진입점에서 데이터 품질 검증을 실행한다."""
    try:
        envPath = loadProjectEnv()
        print("환경 파일 로드:", envPath)

        cliArgs = parseArguments()
        saveReport = cliArgs.no_save is False

        result = runDataQualityValidation(saveReport=saveReport)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return result
    except Exception as generalError:
        return {
            "success": False,
            "message": "validateData 실행 실패: " + str(generalError),
        }


if __name__ == "__main__":
    cliResult = runValidateDataCli()
    if cliResult.get("success") is not True:
        sys.exit(1)
    if cliResult.get("overallPassed") is not True:
        sys.exit(2)
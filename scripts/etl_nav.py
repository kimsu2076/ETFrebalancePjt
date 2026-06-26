# -*- coding: utf-8 -*-
"""KIS NAV ETL v1 — 2년치 백필 + 일일 증분 적재 (3단계)"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.envLoader import loadProjectEnv
from src.etl.navEtl import runNavEtl


def parseArguments():
    """CLI 인자를 파싱한다."""
    argumentParser = argparse.ArgumentParser(description="KIS NAV ETL v1")
    argumentParser.add_argument(
        "--mode",
        choices=["incremental", "backfill"],
        default="incremental",
        help="incremental: Watermark 기반 증분, backfill: 2년치 전체 백필",
    )
    return argumentParser.parse_args()


def runEtlNavCli():
    """CLI 진입점에서 NAV ETL을 실행한다."""
    try:
        envPath = loadProjectEnv()
        print("환경 파일 로드:", envPath)

        cliArgs = parseArguments()
        runMode = cliArgs.mode
        print("실행 모드:", runMode)

        result = runNavEtl(runMode=runMode)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return result
    except Exception as generalError:
        return {
            "success": False,
            "message": "etl_nav 실행 실패: " + str(generalError),
        }


if __name__ == "__main__":
    cliResult = runEtlNavCli()
    if cliResult.get("success") is not True:
        sys.exit(1)
# -*- coding: utf-8 -*-
"""cron 시뮬레이션 테스트: NAV ETL 증분 모드 2회 연속 실행 (멱등성 확인)"""

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.envLoader import loadProjectEnv
from src.etl.navEtl import runNavEtl


def runCronSimulationTest():
    """cron과 동일하게 incremental 모드를 2회 실행하여 멱등성을 검증한다."""
    try:
        envPath = loadProjectEnv()
        print("환경 파일 로드:", envPath)
        print("=== cron 시뮬레이션 1회차 (incremental) ===")
        firstResult = runNavEtl(runMode="incremental")
        print(json.dumps(firstResult, ensure_ascii=False, indent=2, default=str))

        print("=== cron 시뮬레이션 2회차 (incremental, 멱등성) ===")
        secondResult = runNavEtl(runMode="incremental")
        print(json.dumps(secondResult, ensure_ascii=False, indent=2, default=str))

        firstSuccess = firstResult.get("success") is True
        secondSuccess = secondResult.get("success") is True
        secondUpToDate = "최신" in secondResult.get("message", "")

        finalResult = {
            "success": firstSuccess and secondSuccess,
            "message": "cron 시뮬레이션 테스트 완료",
            "firstRun": firstResult,
            "secondRun": secondResult,
            "idempotent": secondUpToDate or secondResult.get("upsertedCount", 0) == 0,
        }
        print(json.dumps(finalResult, ensure_ascii=False, indent=2, default=str))
        return finalResult
    except Exception as generalError:
        return {
            "success": False,
            "message": "cron 시뮬레이션 실패: " + str(generalError),
        }


if __name__ == "__main__":
    testResult = runCronSimulationTest()
    if testResult.get("success") is not True:
        sys.exit(1)
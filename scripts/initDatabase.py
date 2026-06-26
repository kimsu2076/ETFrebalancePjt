# -*- coding: utf-8 -*-
"""MySQL 스키마 초기화 + etf_master 시드 적재 통합 스크립트 (2단계)"""

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.initSchema import runInitSchema
from scripts.seedEtfMaster import runSeedEtfMaster


def runInitDatabase():
    """스키마 생성과 etf_master 초기 적재를 순서대로 실행한다."""
    try:
        schemaResult = runInitSchema()
        if schemaResult.get("success") is not True:
            return schemaResult

        seedResult = runSeedEtfMaster()
        if seedResult.get("success") is not True:
            return seedResult

        finalResult = {
            "success": True,
            "message": "2단계 DB 초기화 및 etf_master 적재 완료",
            "schema": schemaResult,
            "seed": seedResult,
        }
        print("통합 실행 결과:", json.dumps(finalResult, ensure_ascii=False, indent=2, default=str))
        return finalResult
    except Exception as generalError:
        return {
            "success": False,
            "message": "DB 통합 초기화 실패: " + str(generalError),
        }


if __name__ == "__main__":
    result = runInitDatabase()
    if result.get("success") is not True:
        sys.exit(1)
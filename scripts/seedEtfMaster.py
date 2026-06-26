# -*- coding: utf-8 -*-
"""etf_master 초기 마스터 데이터 적재 스크립트 (2단계)"""

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.envLoader import getDbConfig, loadProjectEnv, validateDbConfig
from src.db.dbConnection import getDbEngine, testDbConnection
from src.db.etfMasterSeed import fetchEtfMasterRows, getDefaultEtfMasterRows, upsertEtfMaster


def runSeedEtfMaster():
    """etf_master 테이블에 Phase 1 대상 ETF 마스터 데이터를 적재한다."""
    try:
        envPath = loadProjectEnv()
        print("환경 파일 로드:", envPath)

        dbConfig = getDbConfig()
        validation = validateDbConfig(dbConfig)
        if validation.get("success") is not True:
            print(json.dumps(validation, ensure_ascii=False, indent=2))
            return validation

        connectionTest = testDbConnection()
        print("DB 연결 테스트:", json.dumps(connectionTest, ensure_ascii=False, indent=2))
        if connectionTest.get("success") is not True:
            return connectionTest

        seedRows = getDefaultEtfMasterRows()
        print("시드 데이터:", json.dumps(seedRows, ensure_ascii=False, indent=2, default=str))

        engine = getDbEngine(includeDatabase=True)
        seedResult = upsertEtfMaster(engine, seedRows)
        print("시드 적재 결과:", json.dumps(seedResult, ensure_ascii=False, indent=2))
        if seedResult.get("success") is not True:
            return seedResult

        fetchResult = fetchEtfMasterRows(engine)
        print("적재 확인:", json.dumps(fetchResult, ensure_ascii=False, indent=2, default=str))

        finalResult = {
            "success": fetchResult.get("success") is True,
            "message": "etf_master 초기 데이터 적재 완료",
            "upsertedCount": seedResult.get("upsertedCount", 0),
            "rows": fetchResult.get("rows", []),
        }
        return finalResult
    except Exception as generalError:
        return {
            "success": False,
            "message": "etf_master 시드 적재 실패: " + str(generalError),
        }


if __name__ == "__main__":
    result = runSeedEtfMaster()
    if result.get("success") is not True:
        sys.exit(1)
# -*- coding: utf-8 -*-
"""MySQL 데이터베이스 및 테이블 스키마 초기화 스크립트 (2단계)"""

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.envLoader import getDbConfig, loadProjectEnv, validateDbConfig
from src.db.dbConnection import (
    ensureDatabaseExists,
    executeSchemaSql,
    getDbEngine,
    getTableList,
    testDbConnection,
)


def runInitSchema():
    """데이터베이스 생성 및 DDL 스키마를 적용한다."""
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

        databaseResult = ensureDatabaseExists()
        print("DB 생성 결과:", json.dumps(databaseResult, ensure_ascii=False, indent=2))
        if databaseResult.get("success") is not True:
            return databaseResult

        engine = getDbEngine(includeDatabase=True)
        schemaResult = executeSchemaSql(engine)
        print("스키마 적용 결과:", json.dumps(schemaResult, ensure_ascii=False, indent=2))
        if schemaResult.get("success") is not True:
            return schemaResult

        tableResult = getTableList(engine)
        print("생성된 테이블:", json.dumps(tableResult, ensure_ascii=False, indent=2))

        finalResult = {
            "success": tableResult.get("success") is True,
            "message": "MySQL 스키마 초기화 완료",
            "database": dbConfig.get("database", ""),
            "tables": tableResult.get("tables", []),
        }
        return finalResult
    except Exception as generalError:
        return {
            "success": False,
            "message": "스키마 초기화 실패: " + str(generalError),
        }


if __name__ == "__main__":
    result = runInitSchema()
    if result.get("success") is not True:
        sys.exit(1)
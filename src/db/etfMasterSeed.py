# -*- coding: utf-8 -*-
"""etf_master 초기 마스터 데이터 시드 모듈"""

from sqlalchemy import text

from src.config.envLoader import getDbConfig


def getDefaultEtfMasterRows():
    """Phase 1 대상 ETF 마스터 시드 데이터 목록을 반환한다."""
    dbConfig = getDbConfig()
    targetEtfCode = dbConfig.get("targetEtfCode", "102110")
    targetEtfName = dbConfig.get("targetEtfName", "TIGER 200")

    seedRows = [
        {
            "etf_code": targetEtfCode,
            "etf_name": targetEtfName,
            "issuer": "미래에셋자산운용",
            "benchmark_index": "KOSPI 200",
            "listing_date": "2007-11-08",
            "expense_ratio": 0.0005,
        }
    ]
    return seedRows


def upsertEtfMaster(engine, seedRows):
    """etf_master 테이블에 시드 데이터를 멱등적으로 적재한다."""
    if seedRows is None or len(seedRows) == 0:
        return {"success": False, "message": "적재할 etf_master 시드 데이터가 없습니다."}

    upsertSql = """
        INSERT INTO etf_master (
            etf_code, etf_name, issuer, benchmark_index, listing_date, expense_ratio
        ) VALUES (
            :etf_code, :etf_name, :issuer, :benchmark_index, :listing_date, :expense_ratio
        )
        ON DUPLICATE KEY UPDATE
            etf_name = VALUES(etf_name),
            issuer = VALUES(issuer),
            benchmark_index = VALUES(benchmark_index),
            listing_date = VALUES(listing_date),
            expense_ratio = VALUES(expense_ratio)
    """

    insertedCount = 0
    try:
        with engine.begin() as connection:
            for i in range(0, len(seedRows)):
                rowData = seedRows[i]
                connection.execute(text(upsertSql), rowData)
                insertedCount = insertedCount + 1

        return {
            "success": True,
            "message": "etf_master 시드 적재 완료",
            "upsertedCount": insertedCount,
        }
    except Exception as seedError:
        return {
            "success": False,
            "message": "etf_master 시드 적재 실패: " + str(seedError),
        }


def fetchEtfMasterRows(engine):
    """etf_master 테이블의 전체 행을 조회한다."""
    selectSql = """
        SELECT etf_code, etf_name, issuer, benchmark_index,
               listing_date, expense_ratio, created_at, updated_at
        FROM etf_master
        ORDER BY etf_code
    """
    rowList = []
    try:
        with engine.connect() as connection:
            result = connection.execute(text(selectSql))
            columns = list(result.keys())
            rows = result.fetchall()
            for i in range(0, len(rows)):
                rowDict = {}
                for j in range(0, len(columns)):
                    columnName = columns[j]
                    cellValue = rows[i][j]
                    if hasattr(cellValue, "isoformat"):
                        rowDict[columnName] = cellValue.isoformat()
                    else:
                        rowDict[columnName] = cellValue
                rowList.append(rowDict)

        return {
            "success": True,
            "message": "etf_master 조회 완료",
            "rows": rowList,
            "rowCount": len(rowList),
        }
    except Exception as fetchError:
        return {
            "success": False,
            "message": "etf_master 조회 실패: " + str(fetchError),
        }
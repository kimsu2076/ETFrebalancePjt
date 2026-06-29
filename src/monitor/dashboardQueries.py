# -*- coding: utf-8 -*-
"""Streamlit 모니터링 대시보드용 DB 조회 모듈"""

import json
import os
from datetime import datetime

import pandas as pd
from sqlalchemy import text

from src.config.envLoader import getDbConfig, getKisConfig, getProjectRoot
from src.db.dbConnection import getDbEngine, testDbConnection


def formatDateValue(dateValue):
    """date/datetime 값을 YYYY-MM-DD 문자열로 변환한다."""
    if dateValue is None:
        return ""
    if hasattr(dateValue, "strftime"):
        return dateValue.strftime("%Y-%m-%d")
    return str(dateValue)[:10]


NUMERIC_COLUMN_NAMES = [
    "nav",
    "close_price",
    "change_rate",
    "weight_pct",
    "shares",
    "market_value_krw",
    "rank_in_portfolio",
    "added_stocks_count",
    "removed_stocks_count",
    "changed_weights_count",
    "total_turnover_pct",
]


def normalizeCellValue(cellValue, columnName):
    """DB 셀 값을 DataFrame 적재용 Python 기본 타입으로 정규화한다."""
    if cellValue is None:
        return None
    if hasattr(cellValue, "isoformat"):
        return cellValue.isoformat()

    if columnName in NUMERIC_COLUMN_NAMES:
        try:
            return float(cellValue)
        except (ValueError, TypeError):
            return cellValue

    return cellValue


def rowsToDataFrame(rows, columnNames):
    """SQLAlchemy 결과 행을 pandas DataFrame으로 변환한다."""
    recordList = []
    for i in range(0, len(rows)):
        rowDict = {}
        for j in range(0, len(columnNames)):
            columnName = columnNames[j]
            rowDict[columnName] = normalizeCellValue(rows[i][j], columnName)
        recordList.append(rowDict)

    if len(recordList) == 0:
        return pd.DataFrame(columns=columnNames)
    return pd.DataFrame(recordList)


def getDashboardSummary(engine, etfCode):
    """대시보드 상단 요약 카드용 통계를 조회한다."""
    summarySql = """
        SELECT
            (SELECT COUNT(*) FROM rebalancing_event WHERE etf_code = :etf_code) AS event_count,
            (SELECT MAX(event_date) FROM rebalancing_event WHERE etf_code = :etf_code) AS latest_event_date,
            (SELECT nav FROM etf_nav_daily WHERE etf_code = :etf_code ORDER BY trade_date DESC LIMIT 1) AS latest_nav,
            (SELECT trade_date FROM etf_nav_daily WHERE etf_code = :etf_code ORDER BY trade_date DESC LIMIT 1) AS latest_nav_date,
            (SELECT COUNT(DISTINCT snapshot_date) FROM etf_holdings_snapshot WHERE etf_code = :etf_code) AS snapshot_count,
            (SELECT COUNT(*) FROM etf_nav_daily WHERE etf_code = :etf_code) AS nav_row_count,
            (SELECT AVG(change_rate) FROM etf_nav_daily
             WHERE etf_code = :etf_code
               AND trade_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)) AS avg_change_30d
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text(summarySql), {"etf_code": etfCode})
            rowData = result.fetchone()

        if rowData is None:
            return {"success": False, "message": "요약 통계가 없습니다."}

        return {
            "success": True,
            "message": "대시보드 요약 조회 완료",
            "eventCount": int(rowData[0] or 0),
            "latestEventDate": formatDateValue(rowData[1]),
            "latestNav": float(rowData[2]) if rowData[2] is not None else None,
            "latestNavDate": formatDateValue(rowData[3]),
            "snapshotCount": int(rowData[4] or 0),
            "navRowCount": int(rowData[5] or 0),
            "avgChange30d": float(rowData[6]) if rowData[6] is not None else None,
        }
    except Exception as queryError:
        return {
            "success": False,
            "message": "대시보드 요약 조회 실패: " + str(queryError),
        }


def getNavTrendDataFrame(engine, etfCode, periodDays=365):
    """NAV 추이 DataFrame을 조회한다."""
    navSql = """
        SELECT trade_date, nav, close_price, change_rate
        FROM etf_nav_daily
        WHERE etf_code = :etf_code
          AND trade_date >= DATE_SUB(CURDATE(), INTERVAL :period_days DAY)
        ORDER BY trade_date ASC
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(navSql),
                {"etf_code": etfCode, "period_days": periodDays},
            )
            rows = result.fetchall()
            columnNames = list(result.keys())

        dataFrame = rowsToDataFrame(rows, columnNames)
        return {
            "success": True,
            "message": "NAV 추이 조회 완료",
            "dataFrame": dataFrame,
            "rowCount": len(dataFrame),
        }
    except Exception as queryError:
        return {
            "success": False,
            "message": "NAV 추이 조회 실패: " + str(queryError),
            "dataFrame": pd.DataFrame(),
        }


def getRebalancingEventsDataFrame(engine, etfCode, limitCount=20):
    """리밸런싱 이벤트 목록 DataFrame을 조회한다."""
    eventSql = """
        SELECT event_date, event_type, added_stocks_count, removed_stocks_count,
               changed_weights_count, total_turnover_pct, source, description
        FROM rebalancing_event
        WHERE etf_code = :etf_code
        ORDER BY event_date DESC
        LIMIT :limit_count
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(eventSql),
                {"etf_code": etfCode, "limit_count": limitCount},
            )
            rows = result.fetchall()
            columnNames = list(result.keys())

        dataFrame = rowsToDataFrame(rows, columnNames)
        return {
            "success": True,
            "message": "리밸런싱 이벤트 조회 완료",
            "dataFrame": dataFrame,
            "rowCount": len(dataFrame),
        }
    except Exception as queryError:
        return {
            "success": False,
            "message": "리밸런싱 이벤트 조회 실패: " + str(queryError),
            "dataFrame": pd.DataFrame(),
        }


def getTopStockCodes(engine, etfCode, limitCount=10):
    """최신 스냅샷 기준 상위 비중 종목 코드 목록을 조회한다."""
    topSql = """
        SELECT stock_code, stock_name, weight_pct
        FROM etf_holdings_snapshot
        WHERE etf_code = :etf_code
          AND snapshot_date = (
              SELECT MAX(snapshot_date) FROM etf_holdings_snapshot WHERE etf_code = :etf_code
          )
          AND stock_code NOT LIKE 'KRD%%'
        ORDER BY weight_pct DESC
        LIMIT :limit_count
    """
    stockList = []
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(topSql),
                {"etf_code": etfCode, "limit_count": limitCount},
            )
            rows = result.fetchall()
            for i in range(0, len(rows)):
                stockList.append({
                    "stock_code": rows[i][0],
                    "stock_name": rows[i][1],
                    "weight_pct": float(rows[i][2]) if rows[i][2] is not None else 0.0,
                })

        return {
            "success": True,
            "message": "상위 종목 조회 완료",
            "stocks": stockList,
        }
    except Exception as queryError:
        return {
            "success": False,
            "message": "상위 종목 조회 실패: " + str(queryError),
            "stocks": [],
        }


def getWeightTrendDataFrame(engine, etfCode, stockCode):
    """특정 종목의 비중 추이 DataFrame을 조회한다."""
    weightSql = """
        SELECT snapshot_date, weight_pct, stock_name
        FROM etf_holdings_snapshot
        WHERE etf_code = :etf_code
          AND stock_code = :stock_code
        ORDER BY snapshot_date ASC
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(weightSql),
                {"etf_code": etfCode, "stock_code": stockCode},
            )
            rows = result.fetchall()
            columnNames = list(result.keys())

        dataFrame = rowsToDataFrame(rows, columnNames)
        return {
            "success": True,
            "message": "비중 추이 조회 완료",
            "dataFrame": dataFrame,
            "rowCount": len(dataFrame),
        }
    except Exception as queryError:
        return {
            "success": False,
            "message": "비중 추이 조회 실패: " + str(queryError),
            "dataFrame": pd.DataFrame(),
        }


def getHoldingsSnapshotDataFrame(engine, etfCode, snapshotDate):
    """특정 스냅샷일 holdings DataFrame을 조회한다."""
    holdingsSql = """
        SELECT rank_in_portfolio, stock_code, stock_name, weight_pct,
               shares, market_value_krw
        FROM etf_holdings_snapshot
        WHERE etf_code = :etf_code
          AND snapshot_date = :snapshot_date
        ORDER BY rank_in_portfolio ASC, weight_pct DESC
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(holdingsSql),
                {"etf_code": etfCode, "snapshot_date": snapshotDate},
            )
            rows = result.fetchall()
            columnNames = list(result.keys())

        dataFrame = rowsToDataFrame(rows, columnNames)
        return {
            "success": True,
            "message": "holdings 스냅샷 조회 완료",
            "dataFrame": dataFrame,
            "rowCount": len(dataFrame),
        }
    except Exception as queryError:
        return {
            "success": False,
            "message": "holdings 스냅샷 조회 실패: " + str(queryError),
            "dataFrame": pd.DataFrame(),
        }


def getSnapshotDateList(engine, etfCode):
    """holdings 스냅샷 기준일 목록을 조회한다."""
    dateSql = """
        SELECT DISTINCT snapshot_date
        FROM etf_holdings_snapshot
        WHERE etf_code = :etf_code
        ORDER BY snapshot_date DESC
    """
    dateList = []
    try:
        with engine.connect() as connection:
            result = connection.execute(text(dateSql), {"etf_code": etfCode})
            rows = result.fetchall()
            for i in range(0, len(rows)):
                dateList.append(formatDateValue(rows[i][0]))

        return {
            "success": True,
            "message": "스냅샷 기준일 목록 조회 완료",
            "dates": dateList,
        }
    except Exception as queryError:
        return {
            "success": False,
            "message": "스냅샷 기준일 조회 실패: " + str(queryError),
            "dates": [],
        }


def findLatestValidationReport():
    """reports/ 폴더에서 최신 검증 리포트 JSON 경로를 찾는다."""
    projectRoot = getProjectRoot()
    reportDir = os.path.join(projectRoot, "reports")
    if os.path.exists(reportDir) is False:
        return {
            "success": True,
            "message": "검증 리포트 없음",
            "reportPath": "",
            "reportData": None,
        }

    fileNames = os.listdir(reportDir)
    jsonFiles = []
    for i in range(0, len(fileNames)):
        fileName = fileNames[i]
        if fileName.startswith("validation_report_") and fileName.endswith(".json"):
            jsonFiles.append(fileName)

    if len(jsonFiles) == 0:
        return {
            "success": True,
            "message": "검증 리포트 없음",
            "reportPath": "",
            "reportData": None,
        }

    jsonFiles.sort(reverse=True)
    latestPath = os.path.join(reportDir, jsonFiles[0])
    try:
        with open(latestPath, "r", encoding="utf-8") as jsonFile:
            reportData = json.load(jsonFile)

        return {
            "success": True,
            "message": "최신 검증 리포트 로드 완료",
            "reportPath": latestPath,
            "reportData": reportData,
        }
    except Exception as readError:
        return {
            "success": False,
            "message": "검증 리포트 읽기 실패: " + str(readError),
            "reportPath": latestPath,
            "reportData": None,
        }


def loadDashboardData():
    """대시보드에 필요한 전체 데이터를 로드한다."""
    try:
        connectionTest = testDbConnection()
        if connectionTest.get("success") is not True:
            return connectionTest

        kisConfig = getKisConfig()
        dbConfig = getDbConfig()
        etfCode = kisConfig.get("targetEtfCode", "102110")
        etfName = kisConfig.get("targetEtfName", "TIGER 200")
        engine = getDbEngine(includeDatabase=True)

        summaryResult = getDashboardSummary(engine, etfCode)
        navTrendResult = getNavTrendDataFrame(engine, etfCode, periodDays=365)
        eventsResult = getRebalancingEventsDataFrame(engine, etfCode, limitCount=15)
        topStocksResult = getTopStockCodes(engine, etfCode, limitCount=10)
        snapshotDatesResult = getSnapshotDateList(engine, etfCode)
        validationResult = findLatestValidationReport()

        weightTrendMap = {}
        topStocks = topStocksResult.get("stocks", [])
        for i in range(0, len(topStocks)):
            stockItem = topStocks[i]
            stockCode = stockItem.get("stock_code", "")
            if stockCode == "":
                continue
            trendResult = getWeightTrendDataFrame(engine, etfCode, stockCode)
            weightTrendMap[stockCode] = trendResult.get("dataFrame", pd.DataFrame())

        latestSnapshotDate = ""
        snapshotDates = snapshotDatesResult.get("dates", [])
        if len(snapshotDates) > 0:
            latestSnapshotDate = snapshotDates[0]

        holdingsResult = {
            "success": True,
            "message": "holdings 없음",
            "dataFrame": pd.DataFrame(),
        }
        if latestSnapshotDate != "":
            holdingsResult = getHoldingsSnapshotDataFrame(engine, etfCode, latestSnapshotDate)

        return {
            "success": True,
            "message": "대시보드 데이터 로드 완료",
            "etfCode": etfCode,
            "etfName": etfName,
            "dbHost": dbConfig.get("host", ""),
            "loadedAt": datetime.now().isoformat(),
            "summary": summaryResult,
            "navTrend": navTrendResult,
            "events": eventsResult,
            "topStocks": topStocksResult,
            "weightTrendMap": weightTrendMap,
            "snapshotDates": snapshotDatesResult,
            "holdings": holdingsResult,
            "validation": validationResult,
        }
    except Exception as generalError:
        return {
            "success": False,
            "message": "대시보드 데이터 로드 실패: " + str(generalError),
        }
# -*- coding: utf-8 -*-
"""etf_holdings_snapshot 테이블 조회·적재 리포지토리 모듈"""

from datetime import datetime

from sqlalchemy import text

from src.scraper.tigerHoldingsScraper import normalizeSnapshotDate


def formatDateToYmd(dateValue):
    """date/datetime 값을 YYYYMMDD 문자열로 반환한다."""
    if dateValue is None:
        return ""
    if hasattr(dateValue, "strftime"):
        return dateValue.strftime("%Y%m%d")
    return str(dateValue).replace("-", "")[:8]


def getMaxSnapshotDate(engine, etfCode):
    """etf_holdings_snapshot에서 특정 ETF의 최종 스냅샷일을 조회한다."""
    selectSql = """
        SELECT MAX(snapshot_date) AS max_snapshot_date
        FROM etf_holdings_snapshot
        WHERE etf_code = :etf_code
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text(selectSql), {"etf_code": etfCode})
            rowData = result.fetchone()
            if rowData is None:
                return {"success": True, "message": "스냅샷 없음", "maxSnapshotDate": None}

            maxSnapshotDate = rowData[0]
            return {
                "success": True,
                "message": "최종 스냅샷일 조회 완료",
                "maxSnapshotDate": maxSnapshotDate,
                "maxSnapshotDateYmd": formatDateToYmd(maxSnapshotDate),
            }
    except Exception as queryError:
        return {
            "success": False,
            "message": "최종 스냅샷일 조회 실패: " + str(queryError),
        }


def getLatestNavTradeDate(engine, etfCode):
    """etf_nav_daily의 최종 거래일을 holdings 기준일 후보로 조회한다."""
    selectSql = """
        SELECT MAX(trade_date) AS max_trade_date
        FROM etf_nav_daily
        WHERE etf_code = :etf_code
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text(selectSql), {"etf_code": etfCode})
            rowData = result.fetchone()
            if rowData is None or rowData[0] is None:
                return {"success": True, "message": "NAV 거래일 없음", "tradeDate": None}

            return {
                "success": True,
                "message": "NAV 최종 거래일 조회 완료",
                "tradeDate": rowData[0],
                "tradeDateYmd": formatDateToYmd(rowData[0]),
            }
    except Exception as queryError:
        return {
            "success": False,
            "message": "NAV 최종 거래일 조회 실패: " + str(queryError),
        }


def snapshotExists(engine, etfCode, snapshotDate):
    """특정 스냅샷일 데이터 존재 여부를 확인한다."""
    selectSql = """
        SELECT COUNT(*) AS row_count
        FROM etf_holdings_snapshot
        WHERE etf_code = :etf_code
          AND snapshot_date = :snapshot_date
    """
    normalizedDate = normalizeSnapshotDate(snapshotDate)
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(selectSql),
                {"etf_code": etfCode, "snapshot_date": normalizedDate},
            )
            rowData = result.fetchone()
            rowCount = 0
            if rowData is not None:
                rowCount = int(rowData[0])

            return {
                "success": True,
                "message": "스냅샷 존재 여부 확인 완료",
                "exists": rowCount > 0,
                "rowCount": rowCount,
                "snapshotDate": normalizedDate,
            }
    except Exception as queryError:
        return {
            "success": False,
            "message": "스냅샷 존재 확인 실패: " + str(queryError),
        }


def getPreviousSnapshotDate(engine, etfCode, snapshotDate):
    """주어진 스냅샷일 이전의 가장 최근 스냅샷일을 조회한다."""
    selectSql = """
        SELECT MAX(snapshot_date) AS prev_snapshot_date
        FROM etf_holdings_snapshot
        WHERE etf_code = :etf_code
          AND snapshot_date < :snapshot_date
    """
    normalizedDate = normalizeSnapshotDate(snapshotDate)
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(selectSql),
                {"etf_code": etfCode, "snapshot_date": normalizedDate},
            )
            rowData = result.fetchone()
            if rowData is None or rowData[0] is None:
                return {
                    "success": True,
                    "message": "이전 스냅샷 없음",
                    "previousSnapshotDate": None,
                }

            return {
                "success": True,
                "message": "이전 스냅샷일 조회 완료",
                "previousSnapshotDate": rowData[0],
                "previousSnapshotDateYmd": formatDateToYmd(rowData[0]),
            }
    except Exception as queryError:
        return {
            "success": False,
            "message": "이전 스냅샷일 조회 실패: " + str(queryError),
        }


def getSnapshotRows(engine, etfCode, snapshotDate, equityOnly=True):
    """특정 스냅샷일의 구성종목 행 목록을 조회한다."""
    selectSql = """
        SELECT stock_code, stock_name, weight_pct, shares,
               market_value_krw, rank_in_portfolio, sector
        FROM etf_holdings_snapshot
        WHERE etf_code = :etf_code
          AND snapshot_date = :snapshot_date
        ORDER BY rank_in_portfolio ASC, weight_pct DESC
    """
    normalizedDate = normalizeSnapshotDate(snapshotDate)
    rowList = []
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(selectSql),
                {"etf_code": etfCode, "snapshot_date": normalizedDate},
            )
            rows = result.fetchall()
            columns = list(result.keys())
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

        if equityOnly is True:
            filteredRows = []
            for i in range(0, len(rowList)):
                rowData = rowList[i]
                stockCode = rowData.get("stock_code", "")
                if stockCode.startswith("KRD"):
                    continue
                filteredRows.append(rowData)
            rowList = filteredRows

        return {
            "success": True,
            "message": "스냅샷 행 조회 완료",
            "rows": rowList,
            "rowCount": len(rowList),
            "snapshotDate": normalizedDate,
        }
    except Exception as queryError:
        return {
            "success": False,
            "message": "스냅샷 행 조회 실패: " + str(queryError),
        }


def prepareDbRecords(recordList):
    """스크래퍼 레코드에서 DB 적재용 필드만 추출한다."""
    dbRecords = []
    for i in range(0, len(recordList)):
        sourceRecord = recordList[i]
        dbRecord = {
            "snapshot_date": sourceRecord.get("snapshot_date"),
            "etf_code": sourceRecord.get("etf_code"),
            "stock_code": sourceRecord.get("stock_code"),
            "stock_name": sourceRecord.get("stock_name"),
            "weight_pct": sourceRecord.get("weight_pct"),
            "shares": sourceRecord.get("shares"),
            "market_value_krw": sourceRecord.get("market_value_krw"),
            "rank_in_portfolio": sourceRecord.get("rank_in_portfolio"),
            "sector": sourceRecord.get("sector"),
        }
        dbRecords.append(dbRecord)
    return dbRecords


def insertHoldingsSnapshot(engine, recordList):
    """etf_holdings_snapshot에 신규 스냅샷을 INSERT IGNORE로 적재한다."""
    if recordList is None or len(recordList) == 0:
        return {
            "success": False,
            "message": "적재할 holdings 레코드가 없습니다.",
        }

    insertSql = """
        INSERT IGNORE INTO etf_holdings_snapshot (
            snapshot_date, etf_code, stock_code, stock_name,
            weight_pct, shares, market_value_krw, rank_in_portfolio, sector
        ) VALUES (
            :snapshot_date, :etf_code, :stock_code, :stock_name,
            :weight_pct, :shares, :market_value_krw, :rank_in_portfolio, :sector
        )
    """

    dbRecords = prepareDbRecords(recordList)
    insertedCount = 0
    try:
        with engine.begin() as connection:
            for i in range(0, len(dbRecords)):
                record = dbRecords[i]
                result = connection.execute(text(insertSql), record)
                if result.rowcount > 0:
                    insertedCount = insertedCount + 1

        return {
            "success": True,
            "message": "etf_holdings_snapshot INSERT IGNORE 완료",
            "attemptedCount": len(dbRecords),
            "insertedCount": insertedCount,
            "skippedCount": len(dbRecords) - insertedCount,
        }
    except Exception as loadError:
        return {
            "success": False,
            "message": "etf_holdings_snapshot 적재 실패: " + str(loadError),
        }


def getHoldingsStats(engine, etfCode):
    """holdings 스냅샷 적재 현황 통계를 조회한다."""
    statsSql = """
        SELECT
            COUNT(DISTINCT snapshot_date) AS snapshot_count,
            COUNT(*) AS row_count,
            MIN(snapshot_date) AS min_snapshot_date,
            MAX(snapshot_date) AS max_snapshot_date
        FROM etf_holdings_snapshot
        WHERE etf_code = :etf_code
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text(statsSql), {"etf_code": etfCode})
            rowData = result.fetchone()
            if rowData is None:
                return {"success": True, "message": "통계 없음", "snapshotCount": 0}

            return {
                "success": True,
                "message": "holdings 통계 조회 완료",
                "snapshotCount": int(rowData[0]),
                "rowCount": int(rowData[1]),
                "minSnapshotDate": formatDateToYmd(rowData[2]),
                "maxSnapshotDate": formatDateToYmd(rowData[3]),
            }
    except Exception as statsError:
        return {
            "success": False,
            "message": "holdings 통계 조회 실패: " + str(statsError),
        }


def resolveTargetSnapshotDate(engine, etfCode, runMode, explicitDate=""):
    """실행 모드에 따라 스크래핑 대상 스냅샷 기준일을 결정한다."""
    if explicitDate != "":
        return {
            "success": True,
            "message": "명시 기준일 사용",
            "snapshotDate": normalizeSnapshotDate(explicitDate),
            "runMode": runMode,
        }

    if runMode == "incremental":
        navDateResult = getLatestNavTradeDate(engine, etfCode)
        if navDateResult.get("success") is not True:
            return navDateResult

        maxSnapshotResult = getMaxSnapshotDate(engine, etfCode)
        if maxSnapshotResult.get("success") is not True:
            return maxSnapshotResult

        tradeDate = navDateResult.get("tradeDate")
        maxSnapshotDate = maxSnapshotResult.get("maxSnapshotDate")

        if tradeDate is not None and hasattr(tradeDate, "strftime"):
            snapshotDateText = tradeDate.strftime("%Y-%m-%d")
        else:
            snapshotDateText = datetime.now().strftime("%Y-%m-%d")

        existsResult = snapshotExists(engine, etfCode, snapshotDateText)
        if existsResult.get("success") is not True:
            return existsResult

        if existsResult.get("exists") is True:
            return {
                "success": True,
                "message": "이미 최신 스냅샷이 존재합니다.",
                "snapshotDate": snapshotDateText,
                "runMode": runMode,
                "isUpToDate": True,
            }

        if maxSnapshotDate is not None and tradeDate is not None:
            if hasattr(maxSnapshotDate, "strftime") and hasattr(tradeDate, "strftime"):
                dayGap = (tradeDate - maxSnapshotDate).days
                if dayGap <= 1:
                    return {
                        "success": True,
                        "message": "holdings 최신 스냅샷이 NAV 대비 1영업일 이내입니다.",
                        "snapshotDate": maxSnapshotDate.strftime("%Y-%m-%d"),
                        "runMode": runMode,
                        "isUpToDate": True,
                        "navTradeDate": snapshotDateText,
                    }

        return {
            "success": True,
            "message": "증분 스냅샷 기준일 결정",
            "snapshotDate": snapshotDateText,
            "runMode": runMode,
            "isUpToDate": False,
        }

    snapshotDateText = datetime.now().strftime("%Y-%m-%d")
    return {
        "success": True,
        "message": "기본 기준일 사용",
        "snapshotDate": snapshotDateText,
        "runMode": runMode,
        "isUpToDate": False,
    }
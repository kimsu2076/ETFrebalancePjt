# -*- coding: utf-8 -*-
"""rebalancing_event 테이블 조회·적재 리포지토리 모듈"""

from sqlalchemy import text

from src.scraper.tigerHoldingsScraper import normalizeSnapshotDate


def insertRebalancingEvent(engine, eventRecord):
    """rebalancing_event 레코드를 INSERT IGNORE로 적재한다."""
    if eventRecord is None:
        return {"success": False, "message": "적재할 이벤트 레코드가 없습니다."}

    insertSql = """
        INSERT IGNORE INTO rebalancing_event (
            event_date, etf_code, event_type, description,
            added_stocks_count, removed_stocks_count, changed_weights_count,
            total_turnover_pct, source
        ) VALUES (
            :event_date, :etf_code, :event_type, :description,
            :added_stocks_count, :removed_stocks_count, :changed_weights_count,
            :total_turnover_pct, :source
        )
    """

    try:
        with engine.begin() as connection:
            result = connection.execute(text(insertSql), eventRecord)
            inserted = result.rowcount > 0

        return {
            "success": True,
            "message": "rebalancing_event INSERT IGNORE 완료",
            "inserted": inserted,
            "eventDate": eventRecord.get("event_date"),
            "eventType": eventRecord.get("event_type"),
        }
    except Exception as loadError:
        return {
            "success": False,
            "message": "rebalancing_event 적재 실패: " + str(loadError),
        }


def getRebalancingEventStats(engine, etfCode):
    """리밸런싱 이벤트 적재 통계를 조회한다."""
    statsSql = """
        SELECT COUNT(*) AS event_count,
               MAX(event_date) AS max_event_date
        FROM rebalancing_event
        WHERE etf_code = :etf_code
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text(statsSql), {"etf_code": etfCode})
            rowData = result.fetchone()
            if rowData is None:
                return {"success": True, "message": "이벤트 없음", "eventCount": 0}

            maxEventDate = rowData[1]
            maxEventDateText = ""
            if maxEventDate is not None and hasattr(maxEventDate, "strftime"):
                maxEventDateText = maxEventDate.strftime("%Y-%m-%d")

            return {
                "success": True,
                "message": "리밸런싱 이벤트 통계 조회 완료",
                "eventCount": int(rowData[0]),
                "maxEventDate": maxEventDateText,
            }
    except Exception as statsError:
        return {
            "success": False,
            "message": "리밸런싱 이벤트 통계 조회 실패: " + str(statsError),
        }


def deleteRebalancingEvents(engine, etfCode):
    """특정 ETF의 rebalancing_event 레코드를 전체 삭제한다."""
    deleteSql = """
        DELETE FROM rebalancing_event
        WHERE etf_code = :etf_code
    """
    try:
        with engine.begin() as connection:
            result = connection.execute(text(deleteSql), {"etf_code": etfCode})
            deletedCount = result.rowcount

        return {
            "success": True,
            "message": "rebalancing_event 삭제 완료",
            "deletedCount": deletedCount,
        }
    except Exception as deleteError:
        return {
            "success": False,
            "message": "rebalancing_event 삭제 실패: " + str(deleteError),
        }


def getAllSnapshotDates(engine, etfCode):
    """holdings 스냅샷 기준일 목록을 오름차순으로 조회한다."""
    selectSql = """
        SELECT DISTINCT snapshot_date
        FROM etf_holdings_snapshot
        WHERE etf_code = :etf_code
        ORDER BY snapshot_date ASC
    """
    dateList = []
    try:
        with engine.connect() as connection:
            result = connection.execute(text(selectSql), {"etf_code": etfCode})
            rows = result.fetchall()
            for i in range(0, len(rows)):
                snapshotDate = rows[i][0]
                if hasattr(snapshotDate, "strftime"):
                    dateList.append(snapshotDate.strftime("%Y-%m-%d"))
                else:
                    dateList.append(str(snapshotDate)[:10])

        return {
            "success": True,
            "message": "스냅샷 기준일 목록 조회 완료",
            "dates": dateList,
            "dateCount": len(dateList),
        }
    except Exception as queryError:
        return {
            "success": False,
            "message": "스냅샷 기준일 조회 실패: " + str(queryError),
        }


def rebuildRebalancingEvents(engine, etfCode):
    """모든 연속 스냅샷 쌍에 대해 리밸런싱 이벤트를 재생성한다."""
    from src.db.holdingsRepository import getSnapshotRows
    from src.etl.rebalancingDetector import (
        buildRebalancingEventRecord,
        detectRebalancingChanges,
    )

    datesResult = getAllSnapshotDates(engine, etfCode)
    if datesResult.get("success") is not True:
        return datesResult

    dateList = datesResult.get("dates", [])
    if len(dateList) < 2:
        return {
            "success": True,
            "message": "비교할 스냅샷이 2개 미만 — 이벤트 재생성 생략",
            "eventCount": 0,
        }

    deleteResult = deleteRebalancingEvents(engine, etfCode)
    if deleteResult.get("success") is not True:
        return deleteResult

    insertedCount = 0
    skippedCount = 0
    eventSummary = []

    for i in range(1, len(dateList)):
        previousDate = dateList[i - 1]
        currentDate = dateList[i]

        prevRowsResult = getSnapshotRows(engine, etfCode, previousDate, equityOnly=True)
        currentRowsResult = getSnapshotRows(engine, etfCode, currentDate, equityOnly=True)
        if prevRowsResult.get("success") is not True or currentRowsResult.get("success") is not True:
            continue

        detectionResult = detectRebalancingChanges(
            prevRowsResult.get("rows", []),
            currentRowsResult.get("rows", []),
        )

        if detectionResult.get("hasChanges") is not True:
            skippedCount = skippedCount + 1
            continue

        eventRecord = buildRebalancingEventRecord(
            etfCode,
            currentDate,
            detectionResult,
            sourceName="Detected",
        )
        insertResult = insertRebalancingEvent(engine, eventRecord)
        if insertResult.get("success") is True and insertResult.get("inserted") is True:
            insertedCount = insertedCount + 1
            eventSummary.append({
                "eventDate": currentDate,
                "addedCount": detectionResult.get("addedCount", 0),
                "removedCount": detectionResult.get("removedCount", 0),
                "changedCount": detectionResult.get("changedCount", 0),
                "turnoverPct": detectionResult.get("totalTurnoverPct", 0),
            })

    return {
        "success": True,
        "message": "리밸런싱 이벤트 재생성 완료",
        "deletedCount": deleteResult.get("deletedCount", 0),
        "insertedCount": insertedCount,
        "skippedCount": skippedCount,
        "snapshotPairCount": len(dateList) - 1,
        "eventSummary": eventSummary,
    }


def getRecentRebalancingEvents(engine, etfCode, limitCount=5):
    """최근 리밸런싱 이벤트 목록을 조회한다."""
    selectSql = """
        SELECT event_date, event_type, added_stocks_count, removed_stocks_count,
               changed_weights_count, total_turnover_pct, source, description
        FROM rebalancing_event
        WHERE etf_code = :etf_code
        ORDER BY event_date DESC
        LIMIT :limit_count
    """
    eventList = []
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(selectSql),
                {"etf_code": etfCode, "limit_count": limitCount},
            )
            rows = result.fetchall()
            columns = list(result.keys())
            for i in range(0, len(rows)):
                eventDict = {}
                for j in range(0, len(columns)):
                    columnName = columns[j]
                    cellValue = rows[i][j]
                    if hasattr(cellValue, "isoformat"):
                        eventDict[columnName] = cellValue.isoformat()
                    else:
                        eventDict[columnName] = cellValue
                eventList.append(eventDict)

        return {
            "success": True,
            "message": "최근 리밸런싱 이벤트 조회 완료",
            "events": eventList,
            "eventCount": len(eventList),
        }
    except Exception as queryError:
        return {
            "success": False,
            "message": "리밸런싱 이벤트 조회 실패: " + str(queryError),
        }
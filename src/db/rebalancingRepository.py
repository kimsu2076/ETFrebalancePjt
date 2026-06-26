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
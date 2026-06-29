# -*- coding: utf-8 -*-
"""etf_nav_daily 테이블 조회·적재 리포지토리 모듈"""

from datetime import datetime, timedelta

from sqlalchemy import text

from src.config.envLoader import getDbConfig, getEnvValue, loadProjectEnv


def formatDateToYmd(dateValue):
    """date/datetime 값을 YYYYMMDD 문자열로 변환한다."""
    if dateValue is None:
        return ""
    if hasattr(dateValue, "strftime"):
        return dateValue.strftime("%Y%m%d")
    return str(dateValue).replace("-", "")[:8]


def getBackfillStartDate():
    """환경 변수 또는 기본값으로 백필 시작일(YYYYMMDD)을 반환한다."""
    loadProjectEnv()
    startDateText = getEnvValue("NAV_BACKFILL_START_DATE", "20160331")
    if len(startDateText) == 10 and startDateText.count("-") == 2:
        startDateText = startDateText.replace("-", "")
    return startDateText


def getTodayYmd():
    """오늘 날짜를 YYYYMMDD 문자열로 반환한다."""
    return datetime.now().strftime("%Y%m%d")


def getMaxTradeDate(engine, etfCode):
    """etf_nav_daily 테이블에서 특정 ETF의 최종 거래일을 조회한다."""
    selectSql = """
        SELECT MAX(trade_date) AS max_trade_date
        FROM etf_nav_daily
        WHERE etf_code = :etf_code
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text(selectSql), {"etf_code": etfCode})
            rowData = result.fetchone()
            if rowData is None:
                return {"success": True, "message": "거래일 없음", "maxTradeDate": None}

            maxTradeDate = rowData[0]
            return {
                "success": True,
                "message": "최종 거래일 조회 완료",
                "maxTradeDate": maxTradeDate,
                "maxTradeDateYmd": formatDateToYmd(maxTradeDate),
            }
    except Exception as queryError:
        return {
            "success": False,
            "message": "최종 거래일 조회 실패: " + str(queryError),
        }


def resolveFetchDateRange(engine, etfCode, runMode):
    """실행 모드에 따라 KIS API 조회 시작·종료일을 결정한다."""
    todayYmd = getTodayYmd()
    backfillStartYmd = getBackfillStartDate()

    if runMode == "backfill":
        return {
            "success": True,
            "message": "백필 조회 구간 결정",
            "startDate": backfillStartYmd,
            "endDate": todayYmd,
            "runMode": runMode,
        }

    maxDateResult = getMaxTradeDate(engine, etfCode)
    if maxDateResult.get("success") is not True:
        return maxDateResult

    maxTradeDate = maxDateResult.get("maxTradeDate")
    if maxTradeDate is None:
        return {
            "success": True,
            "message": "기존 데이터 없음 — 백필 구간으로 전환",
            "startDate": backfillStartYmd,
            "endDate": todayYmd,
            "runMode": "backfill",
        }

    if hasattr(maxTradeDate, "strftime"):
        nextDate = maxTradeDate + timedelta(days=1)
        startDateYmd = nextDate.strftime("%Y%m%d")
    else:
        startDateYmd = backfillStartYmd

    if startDateYmd > todayYmd:
        return {
            "success": True,
            "message": "신규 적재 대상 없음",
            "startDate": startDateYmd,
            "endDate": todayYmd,
            "runMode": runMode,
            "isUpToDate": True,
        }

    return {
        "success": True,
        "message": "증분 조회 구간 결정",
        "startDate": startDateYmd,
        "endDate": todayYmd,
        "runMode": runMode,
        "isUpToDate": False,
    }


def parseDecimalValue(rawValue):
    """문자열/숫자 값을 DB 적재용 float으로 변환한다. 실패 시 None."""
    if rawValue is None:
        return None
    if rawValue == "":
        return None
    try:
        return float(rawValue)
    except (ValueError, TypeError):
        return None


def parseTradeDateYmd(tradeDateText):
    """YYYYMMDD 문자열을 YYYY-MM-DD 문자열로 변환한다."""
    if tradeDateText is None or tradeDateText == "":
        return ""
    if len(tradeDateText) == 8:
        return (
            tradeDateText[0:4]
            + "-"
            + tradeDateText[4:6]
            + "-"
            + tradeDateText[6:8]
        )
    return tradeDateText


def transformNavApiRows(etfCode, apiRows):
    """KIS NAV 일별 API 응답을 etf_nav_daily 적재 레코드로 변환한다."""
    recordList = []
    for i in range(0, len(apiRows)):
        apiRow = apiRows[i]
        tradeDateYmd = apiRow.get("stck_bsop_date", "")
        tradeDate = parseTradeDateYmd(tradeDateYmd)
        if tradeDate == "":
            continue

        changeRate = parseDecimalValue(apiRow.get("nav_prdy_ctrt"))
        if changeRate is None:
            changeRate = parseDecimalValue(apiRow.get("prdy_ctrt"))

        volumeValue = parseDecimalValue(apiRow.get("acml_vol"))
        if volumeValue is not None:
            volumeValue = int(volumeValue)

        record = {
            "etf_code": etfCode,
            "trade_date": tradeDate,
            "nav": parseDecimalValue(apiRow.get("nav")),
            "close_price": parseDecimalValue(apiRow.get("stck_clpr")),
            "volume": volumeValue,
            "aum_estimate": None,
            "change_rate": changeRate,
        }
        recordList.append(record)

    return {
        "success": True,
        "message": "NAV 레코드 변환 완료",
        "records": recordList,
        "recordCount": len(recordList),
    }


def upsertNavDailyRows(engine, recordList):
    """etf_nav_daily 테이블에 NAV 레코드를 멱등 UPSERT한다."""
    if recordList is None or len(recordList) == 0:
        return {
            "success": True,
            "message": "적재할 NAV 레코드가 없습니다.",
            "upsertedCount": 0,
        }

    upsertSql = """
        INSERT INTO etf_nav_daily (
            etf_code, trade_date, nav, close_price, volume, aum_estimate, change_rate
        ) VALUES (
            :etf_code, :trade_date, :nav, :close_price, :volume, :aum_estimate, :change_rate
        )
        ON DUPLICATE KEY UPDATE
            nav = VALUES(nav),
            close_price = VALUES(close_price),
            volume = VALUES(volume),
            aum_estimate = VALUES(aum_estimate),
            change_rate = VALUES(change_rate)
    """

    upsertedCount = 0
    try:
        with engine.begin() as connection:
            for i in range(0, len(recordList)):
                record = recordList[i]
                connection.execute(text(upsertSql), record)
                upsertedCount = upsertedCount + 1

        return {
            "success": True,
            "message": "etf_nav_daily UPSERT 완료",
            "upsertedCount": upsertedCount,
        }
    except Exception as loadError:
        return {
            "success": False,
            "message": "etf_nav_daily UPSERT 실패: " + str(loadError),
        }


def getNavDailyStats(engine, etfCode):
    """etf_nav_daily 적재 현황 통계를 조회한다."""
    statsSql = """
        SELECT
            COUNT(*) AS row_count,
            MIN(trade_date) AS min_trade_date,
            MAX(trade_date) AS max_trade_date
        FROM etf_nav_daily
        WHERE etf_code = :etf_code
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text(statsSql), {"etf_code": etfCode})
            rowData = result.fetchone()
            if rowData is None:
                return {"success": True, "message": "통계 없음", "rowCount": 0}

            minDate = rowData[1]
            maxDate = rowData[2]
            return {
                "success": True,
                "message": "NAV 통계 조회 완료",
                "rowCount": int(rowData[0]),
                "minTradeDate": formatDateToYmd(minDate) if minDate else "",
                "maxTradeDate": formatDateToYmd(maxDate) if maxDate else "",
            }
    except Exception as statsError:
        return {
            "success": False,
            "message": "NAV 통계 조회 실패: " + str(statsError),
        }


def normalizeDateYmdInput(dateText):
    """날짜 입력을 YYYYMMDD 문자열로 정규화한다."""
    if dateText is None:
        return ""
    cleanedText = str(dateText).strip().replace("-", "").replace("/", "").replace(".", "")
    if len(cleanedText) >= 8:
        return cleanedText[0:8]
    return cleanedText


def getNearestTradeDateOnOrBefore(engine, etfCode, dateYmd):
    """특정 일자 이전(포함) 가장 가까운 NAV 거래일을 조회한다."""
    normalizedYmd = normalizeDateYmdInput(dateYmd)
    if normalizedYmd == "":
        return {
            "success": False,
            "message": "거래일 조회용 날짜가 비어 있습니다.",
        }

    selectSql = """
        SELECT MAX(trade_date) AS nearest_date
        FROM etf_nav_daily
        WHERE etf_code = :etf_code
          AND trade_date <= STR_TO_DATE(:date_ymd, '%Y%m%d')
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(selectSql),
                {"etf_code": etfCode, "date_ymd": normalizedYmd},
            )
            rowData = result.fetchone()

        if rowData is None or rowData[0] is None:
            return {
                "success": True,
                "message": "해당 일자 이전 NAV 거래일 없음",
                "tradeDate": None,
                "tradeDateYmd": "",
            }

        tradeDate = rowData[0]
        return {
            "success": True,
            "message": "가장 가까운 NAV 거래일 조회 완료",
            "tradeDate": tradeDate,
            "tradeDateYmd": formatDateToYmd(tradeDate),
        }
    except Exception as queryError:
        return {
            "success": False,
            "message": "NAV 거래일 조회 실패: " + str(queryError),
        }


def getTradeDatesOnOrBefore(engine, etfCode, dateYmd, limitCount=6):
    """특정 일자 이전(포함) NAV 거래일을 최신순으로 조회한다."""
    normalizedYmd = normalizeDateYmdInput(dateYmd)
    if normalizedYmd == "":
        return {
            "success": False,
            "message": "거래일 목록 조회용 날짜가 비어 있습니다.",
            "tradeDateYmdList": [],
        }

    selectSql = """
        SELECT trade_date
        FROM etf_nav_daily
        WHERE etf_code = :etf_code
          AND trade_date <= STR_TO_DATE(:date_ymd, '%Y%m%d')
        ORDER BY trade_date DESC
        LIMIT :limit_count
    """
    tradeDateYmdList = []
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(selectSql),
                {
                    "etf_code": etfCode,
                    "date_ymd": normalizedYmd,
                    "limit_count": limitCount,
                },
            )
            rows = result.fetchall()

        for i in range(0, len(rows)):
            tradeDateYmdList.append(formatDateToYmd(rows[i][0]))

        return {
            "success": True,
            "message": "NAV 거래일 목록 조회 완료",
            "tradeDateYmdList": tradeDateYmdList,
            "count": len(tradeDateYmdList),
        }
    except Exception as queryError:
        return {
            "success": False,
            "message": "NAV 거래일 목록 조회 실패: " + str(queryError),
            "tradeDateYmdList": [],
        }
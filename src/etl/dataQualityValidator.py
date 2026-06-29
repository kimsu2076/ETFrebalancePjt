# -*- coding: utf-8 -*-
"""ETF Rebalance ETL 데이터 품질 검증 모듈"""

import json
import os
from datetime import datetime

from sqlalchemy import text

from src.config.envLoader import getDbConfig, getKisConfig, validateDbConfig
from src.db.dbConnection import getDbEngine, testDbConnection
from src.db.holdingsRepository import getPreviousSnapshotDate, getSnapshotRows
from src.db.navRepository import getBackfillStartDate, getNavDailyStats
from src.etl.etlLogger import setupEtlLogger
from src.etl.rebalancingDetector import detectRebalancingChanges


WEIGHT_TOLERANCE_PCT = 2.0
NAV_HOLDINGS_MAX_GAP_DAYS = 5
LARGE_GAP_CALENDAR_DAYS = 12
NAV_COVERAGE_START_TOLERANCE_DAYS = 10
MIN_NAV_ROW_COUNT = 2000


def getReportsDirectory():
    """검증 리포트 저장 디렉터리 경로를 반환한다."""
    from src.config.envLoader import getProjectRoot

    projectRoot = getProjectRoot()
    reportDir = os.path.join(projectRoot, "reports")
    if os.path.exists(reportDir) is False:
        os.makedirs(reportDir, exist_ok=True)
    return reportDir


def setupValidatorLogger():
    """데이터 품질 검증 전용 로거를 설정한다."""
    return setupEtlLogger("dataQualityValidator", "validate_data.log")


def formatDateValue(dateValue):
    """date/datetime 값을 YYYY-MM-DD 문자열로 변환한다."""
    if dateValue is None:
        return ""
    if hasattr(dateValue, "strftime"):
        return dateValue.strftime("%Y-%m-%d")
    return str(dateValue)[:10]


def buildCheckResult(checkName, passed, message, details=None):
    """단일 검증 항목 결과 딕셔너리를 생성한다."""
    if details is None:
        details = {}
    return {
        "checkName": checkName,
        "passed": passed,
        "message": message,
        "details": details,
    }


def validateEtfMaster(engine, etfCode):
    """etf_master 마스터 데이터 존재 여부를 검증한다."""
    selectSql = """
        SELECT etf_code, etf_name, benchmark_index
        FROM etf_master
        WHERE etf_code = :etf_code
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text(selectSql), {"etf_code": etfCode})
            rowData = result.fetchone()
            if rowData is None:
                return buildCheckResult(
                    "etf_master_exists",
                    False,
                    "etf_master에 대상 ETF가 없습니다.",
                    {"etfCode": etfCode},
                )

            return buildCheckResult(
                "etf_master_exists",
                True,
                "etf_master 마스터 데이터 확인",
                {
                    "etfCode": rowData[0],
                    "etfName": rowData[1],
                    "benchmarkIndex": rowData[2],
                },
            )
    except Exception as queryError:
        return buildCheckResult(
            "etf_master_exists",
            False,
            "etf_master 조회 실패: " + str(queryError),
        )


def validateNavCoverage(engine, etfCode):
    """NAV 기간 커버리지 및 기본 통계를 검증한다."""
    statsResult = getNavDailyStats(engine, etfCode)
    if statsResult.get("success") is not True:
        return buildCheckResult("nav_coverage", False, statsResult.get("message", ""))

    rowCount = statsResult.get("rowCount", 0)
    minDate = statsResult.get("minTradeDate", "")
    maxDate = statsResult.get("maxTradeDate", "")
    backfillStart = getBackfillStartDate()

    startGapDays = 0
    if minDate != "" and backfillStart != "":
        try:
            minDateObj = datetime.strptime(minDate, "%Y%m%d")
            backfillStartObj = datetime.strptime(backfillStart, "%Y%m%d")
            startGapDays = (minDateObj - backfillStartObj).days
        except ValueError:
            startGapDays = 999

    passed = (
        rowCount >= MIN_NAV_ROW_COUNT
        and startGapDays >= 0
        and startGapDays <= NAV_COVERAGE_START_TOLERANCE_DAYS
    )
    message = "NAV 커버리지 확인"
    if rowCount == 0:
        message = "NAV 데이터가 없습니다."
        passed = False
    elif rowCount < MIN_NAV_ROW_COUNT:
        message = "NAV 건수가 10년치 최소 기준(" + str(MIN_NAV_ROW_COUNT) + "건) 미만입니다."
        passed = False
    elif startGapDays > NAV_COVERAGE_START_TOLERANCE_DAYS:
        message = "NAV 시작일이 백필 목표 대비 허용 범위를 초과합니다."

    return buildCheckResult(
        "nav_coverage",
        passed,
        message,
        {
            "rowCount": rowCount,
            "minTradeDate": minDate,
            "maxTradeDate": maxDate,
            "backfillStartDate": backfillStart,
            "startGapDays": startGapDays,
            "minRowCount": MIN_NAV_ROW_COUNT,
        },
    )


def validateNavDataQuality(engine, etfCode):
    """NAV NULL/음수 및 중복 여부를 검증한다."""
    qualitySql = """
        SELECT
            SUM(CASE WHEN nav IS NULL THEN 1 ELSE 0 END) AS null_nav_count,
            SUM(CASE WHEN close_price IS NULL THEN 1 ELSE 0 END) AS null_close_count,
            SUM(CASE WHEN nav <= 0 THEN 1 ELSE 0 END) AS negative_nav_count,
            SUM(CASE WHEN close_price <= 0 THEN 1 ELSE 0 END) AS negative_close_count,
            COUNT(*) AS total_count,
            COUNT(DISTINCT trade_date) AS distinct_date_count
        FROM etf_nav_daily
        WHERE etf_code = :etf_code
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text(qualitySql), {"etf_code": etfCode})
            rowData = result.fetchone()

        nullNavCount = int(rowData[0] or 0)
        nullCloseCount = int(rowData[1] or 0)
        negativeNavCount = int(rowData[2] or 0)
        negativeCloseCount = int(rowData[3] or 0)
        totalCount = int(rowData[4] or 0)
        distinctDateCount = int(rowData[5] or 0)

        issueCount = nullNavCount + nullCloseCount + negativeNavCount + negativeCloseCount
        duplicateCount = totalCount - distinctDateCount
        passed = issueCount == 0 and duplicateCount == 0

        return buildCheckResult(
            "nav_data_quality",
            passed,
            "NAV 데이터 품질 확인" if passed else "NAV 데이터 품질 이슈 발견",
            {
                "nullNavCount": nullNavCount,
                "nullCloseCount": nullCloseCount,
                "negativeNavCount": negativeNavCount,
                "negativeCloseCount": negativeCloseCount,
                "duplicateDateCount": duplicateCount,
                "totalCount": totalCount,
            },
        )
    except Exception as queryError:
        return buildCheckResult(
            "nav_data_quality",
            False,
            "NAV 품질 검증 실패: " + str(queryError),
        )


def validateNavGaps(engine, etfCode):
    """NAV 연속 거래일 간 큰 공백(10일 초과)을 검출한다."""
    gapSql = """
        SELECT trade_date
        FROM etf_nav_daily
        WHERE etf_code = :etf_code
        ORDER BY trade_date ASC
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text(gapSql), {"etf_code": etfCode})
            rows = result.fetchall()

        if rows is None or len(rows) == 0:
            return buildCheckResult(
                "nav_date_gaps",
                False,
                "NAV 거래일이 없어 공백 검증을 수행할 수 없습니다.",
            )

        largeGaps = []
        for i in range(1, len(rows)):
            prevDate = rows[i - 1][0]
            currentDate = rows[i][0]
            if hasattr(prevDate, "toordinal") and hasattr(currentDate, "toordinal"):
                gapDays = (currentDate - prevDate).days
            else:
                gapDays = 0

            if gapDays > LARGE_GAP_CALENDAR_DAYS:
                largeGaps.append({
                    "fromDate": formatDateValue(prevDate),
                    "toDate": formatDateValue(currentDate),
                    "gapDays": gapDays,
                })

        passed = len(largeGaps) == 0
        return buildCheckResult(
            "nav_date_gaps",
            passed,
            "NAV 거래일 공백 검증 완료",
            {
                "largeGapCount": len(largeGaps),
                "largeGaps": largeGaps[:10],
                "thresholdDays": LARGE_GAP_CALENDAR_DAYS,
            },
        )
    except Exception as queryError:
        return buildCheckResult(
            "nav_date_gaps",
            False,
            "NAV 공백 검증 실패: " + str(queryError),
        )


def validateHoldingsWeightSum(engine, etfCode):
    """스냅샷별 equity 비중 합계(≈100%)를 검증한다."""
    weightSql = """
        SELECT
            snapshot_date,
            SUM(weight_pct) AS total_weight,
            COUNT(*) AS stock_count,
            SUM(CASE WHEN weight_pct < 0 THEN 1 ELSE 0 END) AS negative_weight_count
        FROM etf_holdings_snapshot
        WHERE etf_code = :etf_code
          AND stock_code NOT LIKE 'KRD%%'
        GROUP BY snapshot_date
        ORDER BY snapshot_date ASC
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text(weightSql), {"etf_code": etfCode})
            rows = result.fetchall()

        if rows is None or len(rows) == 0:
            return buildCheckResult(
                "holdings_weight_sum",
                False,
                "holdings 스냅샷 데이터가 없습니다.",
            )

        failedSnapshots = []
        snapshotSummary = []
        for i in range(0, len(rows)):
            snapshotDate = formatDateValue(rows[i][0])
            totalWeight = float(rows[i][1] or 0)
            stockCount = int(rows[i][2] or 0)
            negativeCount = int(rows[i][3] or 0)
            weightDelta = abs(totalWeight - 100.0)

            snapshotInfo = {
                "snapshotDate": snapshotDate,
                "totalWeightPct": round(totalWeight, 3),
                "stockCount": stockCount,
                "negativeWeightCount": negativeCount,
            }
            snapshotSummary.append(snapshotInfo)

            if weightDelta > WEIGHT_TOLERANCE_PCT or negativeCount > 0:
                failedSnapshots.append(snapshotInfo)

        passed = len(failedSnapshots) == 0
        return buildCheckResult(
            "holdings_weight_sum",
            passed,
            "holdings 비중 합계 검증 완료" if passed else "비중 합계 이탈 스냅샷 발견",
            {
                "snapshotCount": len(rows),
                "weightTolerancePct": WEIGHT_TOLERANCE_PCT,
                "failedSnapshots": failedSnapshots,
                "snapshotSummary": snapshotSummary,
            },
        )
    except Exception as queryError:
        return buildCheckResult(
            "holdings_weight_sum",
            False,
            "holdings 비중 검증 실패: " + str(queryError),
        )


def validateReferentialIntegrity(engine, etfCode):
    """NAV/holdings/event 테이블의 etf_master 참조 무결성을 검증한다."""
    integritySqlList = [
        {
            "tableName": "etf_nav_daily",
            "sqlText": """
                SELECT COUNT(*) FROM etf_nav_daily n
                LEFT JOIN etf_master m ON n.etf_code = m.etf_code
                WHERE n.etf_code = :etf_code AND m.etf_code IS NULL
            """,
        },
        {
            "tableName": "etf_holdings_snapshot",
            "sqlText": """
                SELECT COUNT(*) FROM etf_holdings_snapshot h
                LEFT JOIN etf_master m ON h.etf_code = m.etf_code
                WHERE h.etf_code = :etf_code AND m.etf_code IS NULL
            """,
        },
        {
            "tableName": "rebalancing_event",
            "sqlText": """
                SELECT COUNT(*) FROM rebalancing_event e
                LEFT JOIN etf_master m ON e.etf_code = m.etf_code
                WHERE e.etf_code = :etf_code AND m.etf_code IS NULL
            """,
        },
    ]

    orphanCounts = {}
    try:
        with engine.connect() as connection:
            for i in range(0, len(integritySqlList)):
                sqlItem = integritySqlList[i]
                result = connection.execute(text(sqlItem.get("sqlText")), {"etf_code": etfCode})
                rowData = result.fetchone()
                orphanCounts[sqlItem.get("tableName")] = int(rowData[0] or 0)

        totalOrphans = 0
        tableNames = list(orphanCounts.keys())
        for i in range(0, len(tableNames)):
            totalOrphans = totalOrphans + orphanCounts.get(tableNames[i], 0)

        passed = totalOrphans == 0
        return buildCheckResult(
            "referential_integrity",
            passed,
            "참조 무결성 확인" if passed else "고아 레코드 발견",
            {"orphanCounts": orphanCounts},
        )
    except Exception as queryError:
        return buildCheckResult(
            "referential_integrity",
            False,
            "참조 무결성 검증 실패: " + str(queryError),
        )


def validateNavHoldingsAlignment(engine, etfCode):
    """holdings 스냅샷일과 NAV 거래일의 정합성을 검증한다."""
    snapshotSql = """
        SELECT DISTINCT snapshot_date
        FROM etf_holdings_snapshot
        WHERE etf_code = :etf_code
        ORDER BY snapshot_date ASC
    """
    try:
        with engine.connect() as connection:
            snapshotResult = connection.execute(text(snapshotSql), {"etf_code": etfCode})
            snapshotRows = snapshotResult.fetchall()

        if snapshotRows is None or len(snapshotRows) == 0:
            return buildCheckResult(
                "nav_holdings_alignment",
                False,
                "holdings 스냅샷이 없어 정합성 검증을 수행할 수 없습니다.",
            )

        misalignedSnapshots = []
        for i in range(0, len(snapshotRows)):
            snapshotDate = snapshotRows[i][0]

            nearestSql = """
                SELECT trade_date,
                       ABS(DATEDIFF(trade_date, :snapshot_date)) AS gap_days
                FROM etf_nav_daily
                WHERE etf_code = :etf_code
                ORDER BY gap_days ASC, trade_date DESC
                LIMIT 1
            """
            with engine.connect() as connection:
                nearestResult = connection.execute(
                    text(nearestSql),
                    {"etf_code": etfCode, "snapshot_date": snapshotDate},
                )
                nearestRow = nearestResult.fetchone()

            if nearestRow is None:
                minGapDays = 999
                nearestTradeDate = ""
            else:
                gapValue = nearestRow[1]
                if gapValue is None:
                    minGapDays = 999
                else:
                    minGapDays = int(gapValue)
                nearestTradeDate = formatDateValue(nearestRow[0])

            if minGapDays > NAV_HOLDINGS_MAX_GAP_DAYS:
                misalignedSnapshots.append({
                    "snapshotDate": formatDateValue(snapshotDate),
                    "nearestNavDate": nearestTradeDate,
                    "gapDays": minGapDays,
                })

        passed = len(misalignedSnapshots) == 0
        return buildCheckResult(
            "nav_holdings_alignment",
            passed,
            "NAV↔holdings 날짜 정합성 확인" if passed else "날짜 정합성 이탈 스냅샷 발견",
            {
                "snapshotCount": len(snapshotRows),
                "maxAllowedGapDays": NAV_HOLDINGS_MAX_GAP_DAYS,
                "misalignedSnapshots": misalignedSnapshots,
            },
        )
    except Exception as queryError:
        return buildCheckResult(
            "nav_holdings_alignment",
            False,
            "NAV↔holdings 정합성 검증 실패: " + str(queryError),
        )


def validateRebalancingEvents(engine, etfCode):
    """rebalancing_event 레코드와 스냅샷 간 변동 감지 결과의 일치 여부를 검증한다."""
    eventSql = """
        SELECT event_date, added_stocks_count, removed_stocks_count,
               changed_weights_count, total_turnover_pct
        FROM rebalancing_event
        WHERE etf_code = :etf_code
        ORDER BY event_date ASC
    """
    try:
        with engine.connect() as connection:
            eventResult = connection.execute(text(eventSql), {"etf_code": etfCode})
            eventRows = eventResult.fetchall()

        if eventRows is None or len(eventRows) == 0:
            return buildCheckResult(
                "rebalancing_event_consistency",
                True,
                "리밸런싱 이벤트 없음 — 검증 스킵",
                {"eventCount": 0},
            )

        mismatchedEvents = []
        for i in range(0, len(eventRows)):
            eventDate = eventRows[i][0]
            storedAdded = int(eventRows[i][1] or 0)
            storedRemoved = int(eventRows[i][2] or 0)
            storedChanged = int(eventRows[i][3] or 0)
            storedTurnover = float(eventRows[i][4] or 0)

            prevDateResult = getPreviousSnapshotDate(engine, etfCode, eventDate)
            if prevDateResult.get("success") is not True:
                continue

            previousDate = prevDateResult.get("previousSnapshotDate")
            if previousDate is None:
                continue

            prevRowsResult = getSnapshotRows(engine, etfCode, previousDate, equityOnly=True)
            currentRowsResult = getSnapshotRows(engine, etfCode, eventDate, equityOnly=True)
            if prevRowsResult.get("success") is not True or currentRowsResult.get("success") is not True:
                continue

            detectionResult = detectRebalancingChanges(
                prevRowsResult.get("rows", []),
                currentRowsResult.get("rows", []),
            )

            detectedAdded = detectionResult.get("addedCount", 0)
            detectedRemoved = detectionResult.get("removedCount", 0)
            detectedChanged = detectionResult.get("changedCount", 0)
            detectedTurnover = detectionResult.get("totalTurnoverPct", 0)

            if (
                storedAdded != detectedAdded
                or storedRemoved != detectedRemoved
                or storedChanged != detectedChanged
                or abs(storedTurnover - detectedTurnover) > 0.01
            ):
                mismatchedEvents.append({
                    "eventDate": formatDateValue(eventDate),
                    "stored": {
                        "added": storedAdded,
                        "removed": storedRemoved,
                        "changed": storedChanged,
                        "turnover": storedTurnover,
                    },
                    "detected": {
                        "added": detectedAdded,
                        "removed": detectedRemoved,
                        "changed": detectedChanged,
                        "turnover": detectedTurnover,
                    },
                })

        passed = len(mismatchedEvents) == 0
        return buildCheckResult(
            "rebalancing_event_consistency",
            passed,
            "리밸런싱 이벤트 정합성 확인" if passed else "이벤트-감지 결과 불일치 발견",
            {
                "eventCount": len(eventRows),
                "mismatchedEvents": mismatchedEvents,
            },
        )
    except Exception as queryError:
        return buildCheckResult(
            "rebalancing_event_consistency",
            False,
            "리밸런싱 이벤트 검증 실패: " + str(queryError),
        )


def runAllValidations(engine, etfCode):
    """모든 데이터 품질 검증을 실행하고 종합 결과를 반환한다."""
    checkList = [
        validateEtfMaster(engine, etfCode),
        validateNavCoverage(engine, etfCode),
        validateNavDataQuality(engine, etfCode),
        validateNavGaps(engine, etfCode),
        validateHoldingsWeightSum(engine, etfCode),
        validateReferentialIntegrity(engine, etfCode),
        validateNavHoldingsAlignment(engine, etfCode),
        validateRebalancingEvents(engine, etfCode),
    ]

    passedCount = 0
    failedChecks = []
    for i in range(0, len(checkList)):
        checkItem = checkList[i]
        if checkItem.get("passed") is True:
            passedCount = passedCount + 1
        else:
            failedChecks.append(checkItem.get("checkName", ""))

    totalChecks = len(checkList)
    overallPassed = passedCount == totalChecks

    return {
        "success": True,
        "message": "데이터 품질 검증 완료",
        "overallPassed": overallPassed,
        "passedCount": passedCount,
        "failedCount": totalChecks - passedCount,
        "totalChecks": totalChecks,
        "failedChecks": failedChecks,
        "checks": checkList,
        "validatedAt": datetime.now().isoformat(),
        "etfCode": etfCode,
    }


def buildMarkdownReport(validationResult):
    """검증 결과를 Markdown 리포트 문자열로 변환한다."""
    lines = []
    lines.append("# ETF Rebalance ETL 데이터 품질 검증 리포트")
    lines.append("")
    lines.append("- 검증 시각: " + validationResult.get("validatedAt", ""))
    lines.append("- 대상 ETF: " + validationResult.get("etfCode", ""))
    lines.append(
        "- 종합 결과: "
        + ("PASS" if validationResult.get("overallPassed") is True else "FAIL")
    )
    lines.append(
        "- 통과/전체: "
        + str(validationResult.get("passedCount", 0))
        + "/"
        + str(validationResult.get("totalChecks", 0))
    )
    lines.append("")

    checkList = validationResult.get("checks", [])
    for i in range(0, len(checkList)):
        checkItem = checkList[i]
        statusText = "PASS" if checkItem.get("passed") is True else "FAIL"
        lines.append("## " + checkItem.get("checkName", "") + " — " + statusText)
        lines.append("")
        lines.append(checkItem.get("message", ""))
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(checkItem.get("details", {}), ensure_ascii=False, indent=2, default=str))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def saveValidationReport(validationResult):
    """검증 결과를 Markdown·JSON 파일로 저장한다."""
    reportDir = getReportsDirectory()
    dateSuffix = datetime.now().strftime("%Y%m%d")
    markdownPath = os.path.join(reportDir, "validation_report_" + dateSuffix + ".md")
    jsonPath = os.path.join(reportDir, "validation_report_" + dateSuffix + ".json")

    markdownText = buildMarkdownReport(validationResult)
    with open(markdownPath, "w", encoding="utf-8") as markdownFile:
        markdownFile.write(markdownText)

    with open(jsonPath, "w", encoding="utf-8") as jsonFile:
        json.dump(validationResult, jsonFile, ensure_ascii=False, indent=2, default=str)

    return {
        "success": True,
        "message": "검증 리포트 저장 완료",
        "markdownPath": markdownPath,
        "jsonPath": jsonPath,
    }


def runDataQualityValidation(saveReport=True):
    """DB 연결 후 데이터 품질 검증을 실행하고 선택적으로 리포트를 저장한다."""
    logger = setupValidatorLogger()
    try:
        dbConfig = getDbConfig()
        dbValidation = validateDbConfig(dbConfig)
        if dbValidation.get("success") is not True:
            logger.error(dbValidation.get("message", ""))
            return dbValidation

        connectionTest = testDbConnection()
        if connectionTest.get("success") is not True:
            logger.error(connectionTest.get("message", ""))
            return connectionTest

        kisConfig = getKisConfig()
        etfCode = kisConfig.get("targetEtfCode", "102110")
        engine = getDbEngine(includeDatabase=True)

        logger.info("데이터 품질 검증 시작 — ETF: %s", etfCode)
        validationResult = runAllValidations(engine, etfCode)

        if saveReport is True:
            saveResult = saveValidationReport(validationResult)
            validationResult["report"] = saveResult
            logger.info("리포트 저장: %s", saveResult.get("markdownPath", ""))

        logger.info(
            "검증 완료 — %d/%d 통과, 종합: %s",
            validationResult.get("passedCount", 0),
            validationResult.get("totalChecks", 0),
            "PASS" if validationResult.get("overallPassed") is True else "FAIL",
        )

        return validationResult
    except Exception as generalError:
        errorMessage = "데이터 품질 검증 실패: " + str(generalError)
        logger.error(errorMessage)
        return {
            "success": False,
            "message": errorMessage,
        }
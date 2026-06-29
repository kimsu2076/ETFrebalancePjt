# -*- coding: utf-8 -*-
"""KOSPI 200 분기 리밸런싱 기준일 생성 (holdings 백필용)"""

import calendar
from datetime import datetime, timedelta

from src.config.envLoader import getEnvValue, loadProjectEnv
from src.db.navRepository import getBackfillStartDate, getNearestTradeDateOnOrBefore


QUARTER_END_MONTHS = [3, 6, 9, 12]
DEFAULT_HOLDINGS_BACKFILL_END_DATE = "20260629"
SCRAPE_FALLBACK_LIMIT = 6


def normalizeDateYmd(dateText):
    """날짜 문자열을 YYYYMMDD 형식으로 정규화한다."""
    if dateText is None:
        return ""
    cleanedText = str(dateText).strip().replace("-", "").replace("/", "")
    if len(cleanedText) == 8:
        return cleanedText
    return cleanedText[:8]


def getMonthEndDay(yearValue, monthValue):
    """해당 연월의 말일 일자를 반환한다."""
    return calendar.monthrange(yearValue, monthValue)[1]


def buildDateYmd(yearValue, monthValue, dayValue):
    """연·월·일을 YYYYMMDD 문자열로 조합한다."""
    yearText = str(yearValue)
    monthText = str(monthValue)
    if len(monthText) == 1:
        monthText = "0" + monthText
    dayText = str(dayValue)
    if len(dayText) == 1:
        dayText = "0" + dayText
    return yearText + monthText + dayText


def capDateToEndDate(dateYmd, endDateYmd):
    """분기말 일자가 종료일을 넘으면 같은 연월이면 종료일로 보정한다."""
    if dateYmd <= endDateYmd:
        return dateYmd
    if dateYmd[:6] == endDateYmd[:6]:
        return endDateYmd
    return ""


def adjustWeekendToPreviousWeekday(dateYmd):
    """주말이면 직전 평일(금요일)로 보정한 YYYYMMDD를 반환한다."""
    if dateYmd == "":
        return ""
    dateObj = datetime.strptime(dateYmd, "%Y%m%d")
    while dateObj.weekday() >= 5:
        dateObj = dateObj - timedelta(days=1)
    return dateObj.strftime("%Y%m%d")


def resolveCalendarDateToTradeDate(engine, etfCode, calendarDateYmd):
    """분기말 달력일을 NAV 거래일(또는 주말 보정일)로 변환한다."""
    normalizedYmd = normalizeDateYmd(calendarDateYmd)
    if normalizedYmd == "":
        return ""

    if engine is None:
        return adjustWeekendToPreviousWeekday(normalizedYmd)

    tradeDateResult = getNearestTradeDateOnOrBefore(engine, etfCode, normalizedYmd)
    if tradeDateResult.get("success") is not True:
        return adjustWeekendToPreviousWeekday(normalizedYmd)

    tradeDateYmd = tradeDateResult.get("tradeDateYmd", "")
    if tradeDateYmd == "":
        return adjustWeekendToPreviousWeekday(normalizedYmd)
    return tradeDateYmd


def dedupeDatesPreserveOrder(dateList):
    """날짜 목록에서 중복을 제거하고 순서를 유지한다."""
    seenDates = {}
    dedupedDates = []
    for i in range(0, len(dateList)):
        dateValue = normalizeDateYmd(dateList[i])
        if dateValue == "":
            continue
        if dateValue in seenDates:
            continue
        seenDates[dateValue] = True
        dedupedDates.append(dateValue)
    return dedupedDates


def resolveDateListToTradeDates(engine, etfCode, calendarDateList):
    """분기말 달력일 목록을 NAV 영업일 기준 스크래핑일 목록으로 변환한다."""
    tradeDateList = []
    dateMapping = []
    for i in range(0, len(calendarDateList)):
        calendarDateYmd = normalizeDateYmd(calendarDateList[i])
        if calendarDateYmd == "":
            continue
        tradeDateYmd = resolveCalendarDateToTradeDate(engine, etfCode, calendarDateYmd)
        if tradeDateYmd == "":
            continue
        dateMapping.append({
            "calendarDateYmd": calendarDateYmd,
            "tradeDateYmd": tradeDateYmd,
        })
        tradeDateList.append(tradeDateYmd)

    dedupedDates = dedupeDatesPreserveOrder(tradeDateList)
    return {
        "success": True,
        "message": "영업일 기준 스크래핑일 변환 완료",
        "calendarCount": len(calendarDateList),
        "tradeDateCount": len(dedupedDates),
        "dates": dedupedDates,
        "dateMapping": dateMapping,
    }


def buildScrapeCandidateDates(engine, etfCode, calendarDateYmd):
    """분기말 기준 NAV 영업일 후보(최신순) 목록을 생성한다."""
    from src.db.navRepository import getTradeDatesOnOrBefore

    normalizedYmd = normalizeDateYmd(calendarDateYmd)
    if normalizedYmd == "":
        return []

    tradeDatesResult = getTradeDatesOnOrBefore(
        engine,
        etfCode,
        normalizedYmd,
        limitCount=SCRAPE_FALLBACK_LIMIT,
    )
    if tradeDatesResult.get("success") is True:
        candidateList = tradeDatesResult.get("tradeDateYmdList", [])
        if len(candidateList) > 0:
            return candidateList

    fallbackDateYmd = adjustWeekendToPreviousWeekday(normalizedYmd)
    fallbackCandidates = []
    dateObj = datetime.strptime(fallbackDateYmd, "%Y%m%d")
    for i in range(0, SCRAPE_FALLBACK_LIMIT):
        fallbackCandidates.append(dateObj.strftime("%Y%m%d"))
        dateObj = dateObj - timedelta(days=1)
        while dateObj.weekday() >= 5:
            dateObj = dateObj - timedelta(days=1)
    return dedupeDatesPreserveOrder(fallbackCandidates)


def generateQuarterlyDates(startYmd, endYmd):
    """시작일~종료일 사이 3·6·9·12월 분기말 기준일 목록을 생성한다."""
    if startYmd == "" or endYmd == "":
        return []

    startYear = int(startYmd[:4])
    endYear = int(endYmd[:4])
    generatedDates = []

    for yearValue in range(startYear, endYear + 1):
        for monthIndex in range(0, len(QUARTER_END_MONTHS)):
            monthValue = QUARTER_END_MONTHS[monthIndex]
            dayValue = getMonthEndDay(yearValue, monthValue)
            dateYmd = buildDateYmd(yearValue, monthValue, dayValue)
            dateYmd = capDateToEndDate(dateYmd, endYmd)
            if dateYmd == "":
                continue
            if dateYmd < startYmd:
                continue
            generatedDates.append(dateYmd)

    return generatedDates


def getHoldingsBackfillEndDate():
    """환경 변수 또는 기본값으로 holdings 백필 종료일(YYYYMMDD)을 반환한다."""
    loadProjectEnv()
    endDateText = getEnvValue("HOLDINGS_BACKFILL_END_DATE", DEFAULT_HOLDINGS_BACKFILL_END_DATE)
    if len(endDateText) == 10 and endDateText.count("-") == 2:
        endDateText = endDateText.replace("-", "")
    return normalizeDateYmd(endDateText)


def getEffectiveEndDateYmd():
    """종료일과 오늘 중 이른 날짜를 백필 상한으로 반환한다."""
    endDateYmd = getHoldingsBackfillEndDate()
    todayYmd = datetime.now().strftime("%Y%m%d")
    if todayYmd < endDateYmd:
        return todayYmd
    return endDateYmd


def filterDatesFromStartDate(dateList, startDateYmd):
    """백필 시작일 이후 기준일만 필터링하여 반환한다."""
    filteredDates = []
    for i in range(0, len(dateList)):
        dateValue = normalizeDateYmd(dateList[i])
        if dateValue == "":
            continue
        if dateValue >= startDateYmd:
            filteredDates.append(dateValue)
    return filteredDates


def filterDatesUntilEndDate(dateList, endDateYmd):
    """종료일 이전(포함) 기준일만 필터링하여 반환한다."""
    filteredDates = []
    for i in range(0, len(dateList)):
        dateValue = normalizeDateYmd(dateList[i])
        if dateValue == "":
            continue
        if dateValue <= endDateYmd:
            filteredDates.append(dateValue)
    return filteredDates


def getHoldingsBackfillDates(customDates=None, engine=None, etfCode=None):
    """holdings 백필에 사용할 분기 기준일(영업일 보정) 목록을 반환한다."""
    loadProjectEnv()
    startDateYmd = getBackfillStartDate()
    effectiveEndYmd = getEffectiveEndDateYmd()

    if customDates is not None and len(customDates) > 0:
        sourceDates = customDates
    else:
        envDatesText = getEnvValue("HOLDINGS_BACKFILL_DATES", "")
        if envDatesText != "":
            sourceDates = envDatesText.split(",")
        else:
            sourceDates = generateQuarterlyDates(startDateYmd, effectiveEndYmd)

    normalizedDates = []
    for i in range(0, len(sourceDates)):
        dateValue = normalizeDateYmd(sourceDates[i])
        if dateValue != "":
            normalizedDates.append(dateValue)

    normalizedDates.sort()
    filteredDates = filterDatesFromStartDate(normalizedDates, startDateYmd)
    filteredDates = filterDatesUntilEndDate(filteredDates, effectiveEndYmd)

    calendarDates = filteredDates
    scrapeDates = filteredDates
    dateMapping = []
    if engine is not None and etfCode is not None and len(filteredDates) > 0:
        resolveResult = resolveDateListToTradeDates(engine, etfCode, filteredDates)
        scrapeDates = resolveResult.get("dates", filteredDates)
        dateMapping = resolveResult.get("dateMapping", [])

    return {
        "success": True,
        "message": "holdings 백필 기준일 목록 생성 완료",
        "startDateYmd": startDateYmd,
        "endDateYmd": effectiveEndYmd,
        "calendarDateCount": len(calendarDates),
        "dateCount": len(scrapeDates),
        "calendarDates": calendarDates,
        "dates": scrapeDates,
        "dateMapping": dateMapping,
    }
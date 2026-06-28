# -*- coding: utf-8 -*-
"""KOSPI 200 분기 리밸런싱 기준일 하드코딩 목록 (holdings 백필용)"""

from datetime import datetime

from src.config.envLoader import getEnvValue, loadProjectEnv
from src.db.navRepository import getBackfillStartDate


DEFAULT_REBALANCE_DATES = [
    "20240625",
    "20240925",
    "20241230",
    "20250325",
    "20250625",
    "20250925",
    "20251230",
    "20260325",
    "20260625",
]


def normalizeDateYmd(dateText):
    """날짜 문자열을 YYYYMMDD 형식으로 정규화한다."""
    if dateText is None:
        return ""
    cleanedText = str(dateText).strip().replace("-", "").replace("/", "")
    if len(cleanedText) == 8:
        return cleanedText
    return cleanedText[:8]


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


def filterDatesUntilToday(dateList):
    """오늘 이전(포함) 기준일만 필터링하여 반환한다."""
    todayYmd = datetime.now().strftime("%Y%m%d")
    filteredDates = []
    for i in range(0, len(dateList)):
        dateValue = normalizeDateYmd(dateList[i])
        if dateValue == "":
            continue
        if dateValue <= todayYmd:
            filteredDates.append(dateValue)
    return filteredDates


def getHoldingsBackfillDates(customDates=None):
    """2년치 holdings 백필에 사용할 분기 기준일 목록을 반환한다."""
    loadProjectEnv()
    startDateYmd = getBackfillStartDate()

    if customDates is not None and len(customDates) > 0:
        sourceDates = customDates
    else:
        envDatesText = getEnvValue("HOLDINGS_BACKFILL_DATES", "")
        if envDatesText != "":
            sourceDates = envDatesText.split(",")
        else:
            sourceDates = DEFAULT_REBALANCE_DATES

    normalizedDates = []
    for i in range(0, len(sourceDates)):
        dateValue = normalizeDateYmd(sourceDates[i])
        if dateValue != "":
            normalizedDates.append(dateValue)

    normalizedDates.sort()
    filteredDates = filterDatesFromStartDate(normalizedDates, startDateYmd)
    filteredDates = filterDatesUntilToday(filteredDates)

    return {
        "success": True,
        "message": "holdings 백필 기준일 목록 생성 완료",
        "startDateYmd": startDateYmd,
        "dateCount": len(filteredDates),
        "dates": filteredDates,
    }
# -*- coding: utf-8 -*-
"""ETF Rebalance ETL Streamlit 모니터링 대시보드 (7단계)"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd

import streamlit as st
import altair as alt

from src.config.envLoader import loadProjectEnv
from src.db.dbConnection import getDbEngine
from src.monitor.dashboardQueries import (
    getHoldingsSnapshotDataFrame,
    getNavTrendDataFrame,
    loadDashboardData,
)


def renderSummaryCards(summaryData):
    """요약 카드 4개를 렌더링한다."""
    if summaryData.get("success") is not True:
        st.error(summaryData.get("message", "요약 데이터 로드 실패"))
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("리밸런싱 이벤트", str(summaryData.get("eventCount", 0)) + "건")
    with col2:
        st.metric("최근 리밸런싱", summaryData.get("latestEventDate", "-"))
    with col3:
        latestNav = summaryData.get("latestNav")
        navDate = summaryData.get("latestNavDate", "")
        if latestNav is not None:
            st.metric("최신 NAV", f"{latestNav:,.2f}", help=navDate)
        else:
            st.metric("최신 NAV", "-")
    with col4:
        avgChange = summaryData.get("avgChange30d")
        if avgChange is not None:
            st.metric("30일 평균 변동률", f"{avgChange:.3f}%")
        else:
            st.metric("30일 평균 변동률", "-")


def renderNavChart(navTrendData, periodLabel):
    """NAV 추이 선그래프를 렌더링한다."""
    st.subheader("NAV 추이 (" + periodLabel + ")")
    if navTrendData.get("success") is not True:
        st.warning(navTrendData.get("message", ""))
        return

    dataFrame = navTrendData.get("dataFrame")
    if dataFrame is None or len(dataFrame) == 0:
        st.info("NAV 데이터가 없습니다.")
        return

    hover = alt.selection_point(
        nearest=True,
        on="pointerover",
        encodings=["x"],
        empty=False,
    )

    # chartFrame = dataFrame.set_index("trade_date")
    # st.line_chart(chartFrame["nav"], height=300)
    source = dataFrame.copy()
    source["nav"] = pd.to_numeric(source["nav"], errors="coerce")
    chart = alt.Chart(source).mark_line(point=True).encode(
        x=alt.X("trade_date:T", title="날짜"),
        y=alt.Y(
            "nav:Q",
            title="NAV (원)",
            scale=alt.Scale(reverse=False, nice=True),
            axis=alt.Axis(format=",.0f"),
        ),
        tooltip=[
            alt.Tooltip("trade_date:T", title="날짜", format="%Y-%m-%d"),
            alt.Tooltip("nav:Q", title="NAV", format=",.2f"),
        ],
    ).add_params(hover).properties(height=500).interactive()
    st.altair_chart(chart, use_container_width=True)

def renderEventsTable(eventsData):
    """리밸런싱 이벤트 테이블을 렌더링한다."""
    st.subheader("최근 리밸런싱 이벤트")
    if eventsData.get("success") is not True:
        st.warning(eventsData.get("message", ""))
        return

    dataFrame = eventsData.get("dataFrame")
    if dataFrame is None or len(dataFrame) == 0:
        st.info("리밸런싱 이벤트가 없습니다.")
        return

    displayColumns = [
        "event_date",
        "event_type",
        "added_stocks_count",
        "removed_stocks_count",
        "changed_weights_count",
        "total_turnover_pct",
        "description",
    ]
    visibleFrame = dataFrame[displayColumns]
    st.dataframe(visibleFrame, use_container_width=True, hide_index=True)


def renderWeightTrends(topStocksData, weightTrendMap):
    """상위 종목 비중 추이 차트를 렌더링한다."""
    st.subheader("Top 10 종목 비중 추이")
    if topStocksData.get("success") is not True:
        st.warning(topStocksData.get("message", ""))
        return

    topStocks = topStocksData.get("stocks", [])
    if len(topStocks) == 0:
        st.info("종목 데이터가 없습니다.")
        return

    mergedFrame = None
    for i in range(0, len(topStocks)):
        stockItem = topStocks[i]
        stockCode = stockItem.get("stock_code", "")
        stockName = stockItem.get("stock_name", stockCode)
        trendFrame = weightTrendMap.get(stockCode)
        if trendFrame is None or len(trendFrame) == 0:
            continue

        columnName = stockName + " (" + stockCode + ")"
        seriesFrame = trendFrame[["snapshot_date", "weight_pct"]].copy()
        seriesFrame = seriesFrame.rename(columns={"weight_pct": columnName})
        seriesFrame = seriesFrame.set_index("snapshot_date")

        if mergedFrame is None:
            mergedFrame = seriesFrame
        else:
            mergedFrame = mergedFrame.join(seriesFrame, how="outer")

    if mergedFrame is None or len(mergedFrame) == 0:
        st.info("비중 추이 데이터가 없습니다.")
        return

    longFrame = mergedFrame.reset_index().melt(
        id_vars="snapshot_date",
        var_name="종목",
        value_name="weight_pct",
    )
    longFrame["weight_pct"] = pd.to_numeric(longFrame["weight_pct"], errors="coerce")

    weightMax = longFrame["weight_pct"].max()
    if weightMax is None or pd.isna(weightMax):
        st.info("비중 수치를 읽을 수 없습니다.")
        return

    yDomainMax = min(100.0, float(weightMax) * 1.15 + 1.0)

    hover = alt.selection_point(
        nearest=True,
        on="pointerover",
        encodings=["x"],
        empty=False,
    )

    chart = alt.Chart(longFrame).mark_line(point=True).encode(
        x=alt.X("snapshot_date:T", title="기준일"),
        y=alt.Y(
            "weight_pct:Q",
            title="비중 (%)",
            scale=alt.Scale(reverse=False, domain=[0, yDomainMax], nice=True),
            axis=alt.Axis(format=".1f"),
        ),
        color="종목:N",
        tooltip=[
            alt.Tooltip("snapshot_date:T", title="기준일", format="%Y-%m-%d"),
            alt.Tooltip("종목:N", title="종목"),
            alt.Tooltip("weight_pct:Q", title="비중 (%)", format=".2f"),
        ],
    ).add_params(hover).properties(height=500).interactive()
    st.altair_chart(chart, use_container_width=True)


def renderHoldingsTable(holdingsData, snapshotDate):
    """holdings 스냅샷 테이블을 렌더링한다."""
    st.subheader("Holdings 스냅샷 (" + snapshotDate + ")")
    if holdingsData.get("success") is not True:
        st.warning(holdingsData.get("message", ""))
        return

    dataFrame = holdingsData.get("dataFrame")
    if dataFrame is None or len(dataFrame) == 0:
        st.info("holdings 데이터가 없습니다.")
        return

    st.dataframe(dataFrame, use_container_width=True, hide_index=True)


def renderValidationStatus(validationData):
    """최신 검증 리포트 상태를 렌더링한다."""
    st.subheader("데이터 품질 검증 상태")
    if validationData.get("success") is not True:
        st.warning(validationData.get("message", ""))
        return

    reportData = validationData.get("reportData")
    reportPath = validationData.get("reportPath", "")
    if reportData is None:
        st.info("검증 리포트가 없습니다. `python scripts/validateData.py`를 실행하세요.")
        return

    overallPassed = reportData.get("overallPassed", False)
    passedCount = reportData.get("passedCount", 0)
    totalChecks = reportData.get("totalChecks", 0)
    validatedAt = reportData.get("validatedAt", "")

    statusText = "PASS" if overallPassed is True else "FAIL"
    st.metric("검증 결과", statusText, help=validatedAt)
    st.caption("통과: " + str(passedCount) + "/" + str(totalChecks))
    if reportPath != "":
        st.caption("리포트: " + reportPath)


@st.cache_data(ttl=300)
def loadDashboardDataCached():
    """캐시된 대시보드 데이터를 로드한다."""
    return loadDashboardData()


def runMonitorDashboard():
    """Streamlit 모니터링 대시보드를 실행한다."""
    try:
        loadProjectEnv()

        st.set_page_config(
            page_title="ETF Rebalance Monitor",
            page_icon="📊",
            layout="wide",
        )

        st.title("ETF Rebalance ETL 모니터링")
        st.caption("TIGER 200 (102110) — NAV · Holdings · 리밸런싱 이벤트")

        if st.button("데이터 새로고침"):
            st.cache_data.clear()

        dashboardData = loadDashboardDataCached()
        if dashboardData.get("success") is not True:
            st.error(dashboardData.get("message", "대시보드 로드 실패"))
            return

        etfName = dashboardData.get("etfName", "")
        etfCode = dashboardData.get("etfCode", "")
        st.markdown("**대상 ETF:** " + etfName + " (`" + etfCode + "`)")

        renderSummaryCards(dashboardData.get("summary", {}))
        st.divider()

        leftCol, rightCol = st.columns([3, 2])
        with leftCol:
            periodOptions = {
                "1개월": 30,
                "3개월": 90,
                "6개월": 180,
                "1년": 365,
                "3년": 1095,
                "전체": 4000,
            }
            periodLabel = st.selectbox("NAV 기간", list(periodOptions.keys()), index=5)
            periodDays = periodOptions.get(periodLabel, 365)

            engine = getDbEngine(includeDatabase=True)
            navTrendData = getNavTrendDataFrame(engine, etfCode, periodDays=periodDays)
            renderNavChart(navTrendData, periodLabel)

        with rightCol:
            renderValidationStatus(dashboardData.get("validation", {}))
            renderEventsTable(dashboardData.get("events", {}))

        st.divider()
        renderWeightTrends(
            dashboardData.get("topStocks", {}),
            dashboardData.get("weightTrendMap", {}),
        )

        st.divider()
        snapshotDates = dashboardData.get("snapshotDates", {}).get("dates", [])
        if len(snapshotDates) > 0:
            selectedDate = st.selectbox("Holdings 기준일", snapshotDates)
            engine = getDbEngine(includeDatabase=True)
            holdingsData = getHoldingsSnapshotDataFrame(engine, etfCode, selectedDate)
            renderHoldingsTable(holdingsData, selectedDate)
        else:
            st.info("holdings 스냅샷이 없습니다.")

        st.caption("로드 시각: " + dashboardData.get("loadedAt", ""))
        return {"success": True, "message": "대시보드 렌더링 완료"}
    except Exception as generalError:
        st.error("대시보드 실행 실패: " + str(generalError))
        return {
            "success": False,
            "message": "대시보드 실행 실패: " + str(generalError),
        }


if __name__ == "__main__":
    runMonitorDashboard()
# ETF Rebalance ETL 데이터 품질 검증 리포트

- 검증 시각: 2026-06-28T16:33:43.637280
- 대상 ETF: 102110
- 종합 결과: PASS
- 통과/전체: 8/8

## etf_master_exists — PASS

etf_master 마스터 데이터 확인

```json
{
  "etfCode": "102110",
  "etfName": "TIGER 200",
  "benchmarkIndex": "KOSPI 200"
}
```

## nav_coverage — PASS

NAV 커버리지 확인

```json
{
  "rowCount": 502,
  "minTradeDate": "20240603",
  "maxTradeDate": "20260626",
  "backfillStartDate": "20240601",
  "startGapDays": 2,
  "minRowCount": 400
}
```

## nav_data_quality — PASS

NAV 데이터 품질 확인

```json
{
  "nullNavCount": 0,
  "nullCloseCount": 0,
  "negativeNavCount": 0,
  "negativeCloseCount": 0,
  "duplicateDateCount": 0,
  "totalCount": 502
}
```

## nav_date_gaps — PASS

NAV 거래일 공백 검증 완료

```json
{
  "largeGapCount": 0,
  "largeGaps": [],
  "thresholdDays": 10
}
```

## holdings_weight_sum — PASS

holdings 비중 합계 검증 완료

```json
{
  "snapshotCount": 9,
  "weightTolerancePct": 2.0,
  "failedSnapshots": [],
  "snapshotSummary": [
    {
      "snapshotDate": "2024-06-25",
      "totalWeightPct": 99.98,
      "stockCount": 200,
      "negativeWeightCount": 0
    },
    {
      "snapshotDate": "2024-09-25",
      "totalWeightPct": 99.04,
      "stockCount": 199,
      "negativeWeightCount": 0
    },
    {
      "snapshotDate": "2024-12-30",
      "totalWeightPct": 99.48,
      "stockCount": 200,
      "negativeWeightCount": 0
    },
    {
      "snapshotDate": "2025-03-25",
      "totalWeightPct": 99.06,
      "stockCount": 200,
      "negativeWeightCount": 0
    },
    {
      "snapshotDate": "2025-06-25",
      "totalWeightPct": 100.02,
      "stockCount": 200,
      "negativeWeightCount": 0
    },
    {
      "snapshotDate": "2025-09-25",
      "totalWeightPct": 99.98,
      "stockCount": 200,
      "negativeWeightCount": 0
    },
    {
      "snapshotDate": "2025-12-30",
      "totalWeightPct": 99.7,
      "stockCount": 200,
      "negativeWeightCount": 0
    },
    {
      "snapshotDate": "2026-03-25",
      "totalWeightPct": 99.44,
      "stockCount": 200,
      "negativeWeightCount": 0
    },
    {
      "snapshotDate": "2026-06-25",
      "totalWeightPct": 100.02,
      "stockCount": 199,
      "negativeWeightCount": 0
    }
  ]
}
```

## referential_integrity — PASS

참조 무결성 확인

```json
{
  "orphanCounts": {
    "etf_nav_daily": 0,
    "etf_holdings_snapshot": 0,
    "rebalancing_event": 0
  }
}
```

## nav_holdings_alignment — PASS

NAV↔holdings 날짜 정합성 확인

```json
{
  "snapshotCount": 9,
  "maxAllowedGapDays": 5,
  "misalignedSnapshots": []
}
```

## rebalancing_event_consistency — PASS

리밸런싱 이벤트 정합성 확인

```json
{
  "eventCount": 8,
  "mismatchedEvents": []
}
```

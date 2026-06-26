# -*- coding: utf-8 -*-
"""holdings 스냅샷 비교 기반 리밸런싱 이벤트 감지 모듈"""

WEIGHT_CHANGE_THRESHOLD = 0.05


def buildWeightMap(rowList):
    """스냅샷 행 목록을 stock_code → weight_pct 맵으로 변환한다."""
    weightMap = {}
    metaMap = {}

    for i in range(0, len(rowList)):
        rowData = rowList[i]
        stockCode = rowData.get("stock_code", "")
        if stockCode == "":
            continue

        weightValue = rowData.get("weight_pct")
        if weightValue is None:
            weightValue = 0.0
        else:
            weightValue = float(weightValue)

        weightMap[stockCode] = weightValue
        metaMap[stockCode] = {
            "stock_name": rowData.get("stock_name", ""),
            "weight_pct": weightValue,
        }

    return weightMap, metaMap


def collectStockCodes(weightMapA, weightMapB):
    """두 weight 맵의 stock_code 합집합 목록을 반환한다."""
    codeSet = {}
    keyListA = list(weightMapA.keys())
    keyListB = list(weightMapB.keys())

    for i in range(0, len(keyListA)):
        codeSet[keyListA[i]] = True
    for i in range(0, len(keyListB)):
        codeSet[keyListB[i]] = True

    mergedCodes = list(codeSet.keys())
    mergedCodes.sort()
    return mergedCodes


def detectRebalancingChanges(previousRows, newRows, weightThreshold=WEIGHT_CHANGE_THRESHOLD):
    """이전·신규 스냅샷을 비교하여 리밸런싱 변동 내역을 감지한다."""
    if previousRows is None:
        previousRows = []
    if newRows is None:
        newRows = []

    previousMap, previousMeta = buildWeightMap(previousRows)
    newMap, newMeta = buildWeightMap(newRows)
    mergedCodes = collectStockCodes(previousMap, newMap)

    addedStocks = []
    removedStocks = []
    changedStocks = []
    turnoverSum = 0.0

    for i in range(0, len(mergedCodes)):
        stockCode = mergedCodes[i]
        oldWeight = previousMap.get(stockCode)
        newWeight = newMap.get(stockCode)

        if oldWeight is None and newWeight is not None:
            addedStocks.append({
                "stock_code": stockCode,
                "stock_name": newMeta.get(stockCode, {}).get("stock_name", ""),
                "weight_pct": newWeight,
            })
            turnoverSum = turnoverSum + abs(newWeight)
        elif oldWeight is not None and newWeight is None:
            removedStocks.append({
                "stock_code": stockCode,
                "stock_name": previousMeta.get(stockCode, {}).get("stock_name", ""),
                "weight_pct": oldWeight,
            })
            turnoverSum = turnoverSum + abs(oldWeight)
        elif oldWeight is not None and newWeight is not None:
            weightDelta = newWeight - oldWeight
            turnoverSum = turnoverSum + abs(weightDelta)
            if abs(weightDelta) >= weightThreshold:
                changedStocks.append({
                    "stock_code": stockCode,
                    "stock_name": newMeta.get(stockCode, {}).get("stock_name", ""),
                    "old_weight_pct": oldWeight,
                    "new_weight_pct": newWeight,
                    "weight_delta": round(weightDelta, 3),
                })

    totalTurnoverPct = round(turnoverSum / 2.0, 3)
    hasChanges = (
        len(addedStocks) > 0
        or len(removedStocks) > 0
        or len(changedStocks) > 0
    )

    return {
        "success": True,
        "message": "리밸런싱 변동 감지 완료",
        "hasChanges": hasChanges,
        "addedStocks": addedStocks,
        "removedStocks": removedStocks,
        "changedStocks": changedStocks,
        "addedCount": len(addedStocks),
        "removedCount": len(removedStocks),
        "changedCount": len(changedStocks),
        "totalTurnoverPct": totalTurnoverPct,
        "weightThreshold": weightThreshold,
    }


def resolveEventType(detectionResult):
    """변동 유형에 따라 rebalancing_event.event_type을 결정한다."""
    addedCount = detectionResult.get("addedCount", 0)
    removedCount = detectionResult.get("removedCount", 0)
    changedCount = detectionResult.get("changedCount", 0)

    if addedCount > 0 or removedCount > 0:
        return "INDEX_REBALANCE"
    elif changedCount > 0:
        return "ADJUSTMENT"
    else:
        return "REGULAR"


def buildEventDescription(detectionResult):
    """리밸런싱 이벤트 description 텍스트를 생성한다."""
    addedCount = detectionResult.get("addedCount", 0)
    removedCount = detectionResult.get("removedCount", 0)
    changedCount = detectionResult.get("changedCount", 0)
    turnoverPct = detectionResult.get("totalTurnoverPct", 0)

    description = (
        "구성종목 변동 감지 — 추가 "
        + str(addedCount)
        + "건, 제외 "
        + str(removedCount)
        + "건, 비중변경 "
        + str(changedCount)
        + "건, 추정 턴오버 "
        + str(turnoverPct)
        + "%"
    )
    return description


def buildRebalancingEventRecord(etfCode, eventDate, detectionResult, sourceName="Detected"):
    """rebalancing_event 테이블 적재용 레코드를 생성한다."""
    from src.scraper.tigerHoldingsScraper import normalizeSnapshotDate

    eventType = resolveEventType(detectionResult)
    description = buildEventDescription(detectionResult)
    normalizedEventDate = normalizeSnapshotDate(eventDate)

    eventRecord = {
        "event_date": normalizedEventDate,
        "etf_code": etfCode,
        "event_type": eventType,
        "description": description,
        "added_stocks_count": detectionResult.get("addedCount", 0),
        "removed_stocks_count": detectionResult.get("removedCount", 0),
        "changed_weights_count": detectionResult.get("changedCount", 0),
        "total_turnover_pct": detectionResult.get("totalTurnoverPct", 0),
        "source": sourceName,
    }
    return eventRecord
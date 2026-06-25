# ETF 종목별 지분 변동 리밸런싱 내역 시계열 및 증분 적재
## ETL 프로젝트 정의서
  
**작성자**: 김수현
**주제**: ETF (TIGER 200 중심) 포트폴리오 지분 변동 및 리밸런싱 이벤트의 시계열 데이터 수집·변환·증분 적재  
**환경**: 본인 PC WSL (Ubuntu 24.04) + WSL 내 MySQL DB  
**마감**: 2026년 6월 말까지  
**핵심 요구사항 충족**: KIS API 참고 (OHLCV 제외 추가 수집), 중복 없는 증분 저장, 최소 2년치

---

## 1. 프로젝트 개요 및 목적

### 왜 이 데이터를 수집하나요?
한국 ETF 시장은 세계적으로도 손꼽히는 규모로 성장 중이에요. 특히 **TIGER 200** 같은 대형 패시브 ETF는 KOSPI 200 지수를 추종하며, 지수 리밸런싱 시(보통 분기별) 포트폴리오를 조정합니다. 

이 과정에서 발생하는 **지분 변동(구성종목 추가/제외, 비중 변화)** 내역을 시계열로 쌓으면 다음과 같은 가치가 생깁니다.:

- **시장 영향 분석**: 리밸런싱 때 대형주에 대한 매수/매도 압력이 실제로 어떻게 나타나는지 데이터로 확인
- **트래킹 에러 원인 파악**: 왜 ETF 수익률이 지수와 약간 차이나는지 holdings 변화와 연계 분석
- **퀀트/알고리즘 연구**: rebalancing 타이밍을 활용한 전략 백테스트용 고품질 데이터셋
- **개인 투자 인사이트**: "리밸런싱 직전/후에 어떤 종목이 영향을 받을까?"를 실데이터로 공부
- **차별화**: 대부분의 ETL 실습이 OHLCV 가격 데이터에 머무르는데, 이 주제는 **구조적·이벤트 데이터**를 다뤄서 훨씬 의미 있어요!

KIS Open API는 OHLCV 외에 **국내ETF NAV추이**, **ETF 구성종목시세**, NAV 비교추이 등을 제공하니 이를 적극 참고·활용하고, 실제 상세 holdings는 미래에셋 TIGER 공식 사이트(구성종목 PDF/테이블)에서 보완하는 **하이브리드 ETL**로 실현 가능하게 설계했어요.

---

## 2. 데이터 소스 및 수집 범위

### 2.1 주요 소스
| 소스 | 수집 내용 | 비고 |
|------|-----------|------|
| **KIS Open API** | ETF NAV 일별 추이, close price, volume, AUM 추정치 등 | OHLCV 제외 추가 데이터. token 기반 REST 호출 |
| **미래에셋 TIGER ETF 공식 사이트** (investments.miraeasset.com/tigeretf) | TIGER 200 구성종목 상세 (PDF 또는 테이블) – stock_code, name, weight, shares, market_value | 일일 또는 기준일별 snapshot. scraping 또는 Excel 다운로드 파싱 |
| **보조 (선택)** | Naver Finance / FnGuide ETF 페이지 (Top holdings 확인용) | 크로스 체크 |

### 2.2 대상 ETF (Phase 1)
- **TIGER 200** (종목코드: **102110**)
- 추후 확장: TIGER KOSDAQ150, TIGER 미국S&P500 등 인기 ETF

### 2.3 수집 기간
- **초기 적재 (Historical)**: 최소 2024년 6월 ~ 2026년 6월 (2년치)
- **증분 적재 (Incremental)**: 매일 장 마감 후 +1~2시간 (또는 cron으로 자동)

---

## 3. DB 스키마 (MySQL)

```sql
-- 1. ETF 마스터 정보
CREATE TABLE etf_master (
    etf_code VARCHAR(10) PRIMARY KEY,
    etf_name VARCHAR(100) NOT NULL,
    issuer VARCHAR(50),
    benchmark_index VARCHAR(100),
    listing_date DATE,
    expense_ratio DECIMAL(5,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 2. 일일 NAV / 가격 시계열 (KIS API 중심, 증분)
CREATE TABLE etf_nav_daily (
    etf_code VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    nav DECIMAL(15,4),
    close_price DECIMAL(15,4),
    volume BIGINT,
    aum_estimate DECIMAL(20,2),  -- AUM 추정
    change_rate DECIMAL(7,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (etf_code, trade_date),
    INDEX idx_trade_date (trade_date)
);

-- 3. Holdings Snapshot (지분 변동 시계열 핵심)
CREATE TABLE etf_holdings_snapshot (
    snapshot_date DATE NOT NULL,
    etf_code VARCHAR(10) NOT NULL,
    stock_code VARCHAR(10) NOT NULL,
    stock_name VARCHAR(100),
    weight_pct DECIMAL(6,3),      -- 비중 (%)
    shares BIGINT,                -- 보유 주식수
    market_value_krw DECIMAL(20,2),
    rank_in_portfolio INT,
    sector VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_date, etf_code, stock_code),
    INDEX idx_etf_date (etf_code, snapshot_date)
);

-- 4. 리밸런싱 이벤트 로그 (변동 내역 요약)
CREATE TABLE rebalancing_event (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    event_date DATE NOT NULL,
    etf_code VARCHAR(10) NOT NULL,
    event_type ENUM('REGULAR', 'INDEX_REBALANCE', 'ADJUSTMENT') DEFAULT 'INDEX_REBALANCE',
    description TEXT,
    added_stocks_count INT DEFAULT 0,
    removed_stocks_count INT DEFAULT 0,
    changed_weights_count INT DEFAULT 0,
    total_turnover_pct DECIMAL(6,3),  -- 대략적 턴오버율
    source VARCHAR(100),              -- 'KOSPI200_Rebalance' or 'Manual' or 'Detected'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_event (event_date, etf_code)
);
```

**증분 저장 핵심 포인트**
- `etf_nav_daily`, `etf_holdings_snapshot`는 `(etf_code, date)` 또는 `(snapshot_date, etf_code, stock_code)`에 **PRIMARY KEY / UNIQUE**로 중복 방지
- ETL 스크립트에서 **Watermark 방식** 사용: `SELECT MAX(trade_date) FROM etf_nav_daily WHERE etf_code = '102110'` 로 마지막 수집일 확인 후 그 이후 데이터만 추출
- `INSERT IGNORE` 또는 `ON DUPLICATE KEY UPDATE` 활용 → 멱등성(Idempotent) 보장

---

## 4. ETL 프로세스 상세

### 4.1 전체 흐름 (Extract → Transform → Load)
1. **Extract**
   - KIS API: AppKey/Secret으로 OAuth token 발급 → `/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice` 또는 NAV 전용 엔드포인트 호출 (기간 지정 또는 최근 N일)
   - Holdings: `requests` + `BeautifulSoup` 또는 `pandas.read_html` / PDF 다운로드 후 `pdfplumber`로 파싱 (기준일 자동 추출)
2. **Transform**
   - JSON/HTML → pandas DataFrame 정규화
   - Holdings의 경우: 이전 snapshot과 비교하여 **added / removed / weight_changed** 종목 자동 감지 → rebalancing_event 레코드 생성
   - 데이터 검증: weight_pct 합계 ≈ 100%, 음수 방지, 날짜 포맷 통일
   - KIS NAV 데이터와 holdings snapshot_date 매핑
3. **Load**
   - SQLAlchemy 또는 pymysql로 MySQL 연결
   - nav_daily: 신규 날짜만 INSERT (중복 시 무시)
   - holdings_snapshot: 신규 snapshot_date 전체 행 INSERT (이미 있으면 스킵)
   - event: 변화 감지 시에만 INSERT

### 4.2 증분 로직 예시 (Python pseudocode)
```python
last_date = get_max_date_from_db('etf_nav_daily', etf_code)
new_data = kis_api.fetch_nav_since(last_date + 1 day)
if not new_data.empty:
    new_data.to_sql('etf_nav_daily', con=engine, if_exists='append', index=False)
```

### 4.3 기술 스택 (WSL 추천)
- **Python 3.10+** (venv 권장)
- 라이브러리: `pandas`, `requests`, `beautifulsoup4`, `pymysql` or `sqlalchemy`, `python-dotenv`, `schedule` or `APScheduler`, `pdfplumber` (선택)
- KIS 공식 샘플 참고: https://github.com/koreainvestment/open-trading-api
- 스케줄링: WSL `crontab` 또는 `systemd timer`
- 로깅: `logging` 모듈 + 파일 로테이션, 실패 시 간단 Slack/이메일 알림 (선택)

---

## 5. 구현 로드맵 (6월 말까지 완료 가능)

| 단계 | 기간 | 주요 작업 | 산출물 |
|------|------|-----------|--------|
| 1 | 1~2일 | KIS API 계정/인증 세팅, 샘플 호출 테스트 (NAV 위주) | .env 파일, token refresh 함수 |
| 2 | 2~3일 | MySQL 스키마 생성 + 초기 테이블 적재 스크립트 | DDL 스크립트, etf_master 데이터 |
| 3 | 3~4일 | KIS NAV ETL v1 (2년치 백필 + 일일 증분) | etl_nav.py, cron 테스트 |
| 4 | 4~5일 | TIGER 사이트 holdings 스크래퍼 개발 + 파싱 | holdings_scraper.py |
| 5 | 2일 | Holdings snapshot + rebalancing_event ETL 통합 | 전체 파이프라인 |
| 6 | 2일 | 데이터 품질 검증, 2년치 초기 적재 실행, 로그/에러 핸들링 | 검증 리포트 |
| 7 | 1일 | 문서화 + 간단 모니터링 (Streamlit 대시보드 optional) | README.md, 정의서 |

**총 예상 소요**: 2주 이내 (하루 2~3시간 집중)

---

## 6. 리스크 및 대응 방안

- **KIS API 호출 제한**: 초당/일일 제한 확인 후 sleep + exponential backoff 적용
- **Token 만료**: 매 호출 전 유효성 체크 또는 자동 갱신 로직 필수
- **사이트 구조 변경 (scraping)**: selector를 유연하게 (CSS class 기반), 실패 시 Slack 알림 + fallback (Top 10만이라도)
- **PDF 파싱 어려움**: pdfplumber 사용, 또는 사이트에 Excel 다운로드 링크가 있으면 우선 활용
- **Historical holdings 부족**: 2년 전체가 안 되면 "사용 가능한 최근 데이터부터 축적 + 알려진 KOSPI200 리밸런싱 일정 하드코딩"으로 시작
- **WSL MySQL 연결**: host='localhost' 또는 '127.0.0.1', 포트 확인, 방화벽 이슈 없음

---

## 7. 기대 효과 및 확장성

고객님께서 완성하시면:
- 실전에서 바로 써먹을 수 있는 **증분 ETL 파이프라인** 경험 쌓기
- 포트폴리오에 넣을 만한 **차별화된 데이터 자산** 확보
- 추후 Airflow/Prefect 도입이나 대시보드 연동으로 확장하기 좋은 기반

필요하시면 **Python ETL 스크립트 템플릿**, **DDL 파일**, **KIS 호출 예제 코드**도 바로 만들어 드릴게요!

---

**마무리**  
이 정의서로 방향이 명확해지셨으면 좋겠어요.  
구현 중 막히는 부분 있으시면 언제든 말씀해주세요. 고객님의 ETL 실습, 꼭 멋지게 완성되길 응원할게요! 🚀

*참고 자료*  
- KIS Developers: https://apiportal.koreainvestment.com/  
- TIGER 200 상품 페이지: http://investments.miraeasset.com/tigeretf/ko/product/search/detail/index.do?ksdFund=KR7102110004  
- KOSPI 200 리밸런싱 일정: KRX 공시 참조

---
*이 문서는 고객님의 요청에 따라 작성되었으며, 실제 구현 시 최신 API 문서와 사이트 구조를 반드시 확인하세요.*

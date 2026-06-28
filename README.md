# ETF Rebalance ETL

TIGER 200 ETF의 **NAV 시계열**, **구성종목(holdings) 스냅샷**, **리밸런싱 이벤트**를 수집·변환·증분 적재하는 Python ETL 파이프라인입니다.

- **대상 ETF**: TIGER 200 (`102110`)
- **수집 기간**: 2024년 6월 ~ 현재 (최소 2년치)
- **환경**: WSL (Ubuntu) + MySQL + Python 3.12

상세 설계는 [`ETF_Rebalancing_ETL_Definition.md`](ETF_Rebalancing_ETL_Definition.md)를 참고하세요.

---

## 프로젝트 구조

```
ETFrebalancePjt/
├── sql/schema.sql              # MySQL DDL (4개 테이블)
├── config/                     # cron 스케줄 예시
├── scripts/                    # CLI 진입점
│   ├── initDatabase.py         # DB 초기화 (스키마 + 시드)
│   ├── etl_nav.py              # NAV ETL
│   ├── etl_holdings.py         # Holdings ETL
│   ├── etl_pipeline.py         # 통합 파이프라인
│   ├── runInitialLoad.py       # 2년치 초기 적재
│   ├── validateData.py         # 데이터 품질 검증
│   └── monitorDashboard.py     # Streamlit 모니터링
├── src/
│   ├── config/envLoader.py     # 환경 변수 로더
│   ├── kis/                    # KIS Open API 인증·NAV 클라이언트
│   ├── scraper/                # TIGER holdings 스크래퍼
│   ├── db/                     # MySQL 리포지토리
│   ├── etl/                    # ETL 오케스트레이션·검증
│   └── monitor/                # 대시보드 DB 조회
├── data/                       # 토큰 캐시, holdings JSON
├── logs/                       # ETL·검증 로그 (Rotating)
├── reports/                    # 검증 리포트 (Markdown/JSON)
└── docs/rev_log.md             # 수정 이력
```

---

## 빠른 시작

### 1. 환경 설정

```bash
source /home/smt14/pywork/.venv/bin/activate
cd /home/smt14/ETFrebalancePjt
pip install -r requirements.txt
cp .env.example .env
# .env에 KIS_APP_KEY, KIS_APP_SECRET, DB 접속 정보 입력
```

### 2. DB 초기화

```bash
python scripts/initDatabase.py
```

### 3. 2년치 초기 적재 (최초 1회)

```bash
python scripts/runInitialLoad.py
```

### 4. 일일 증분 (cron)

```bash
python scripts/etl_pipeline.py --nav-mode incremental --holdings-mode incremental
```

cron 예시: `config/cron_pipeline_etl.example`

---

## 주요 CLI 명령

| 명령 | 설명 |
|------|------|
| `python scripts/testKisNav.py` | KIS API 인증·NAV 샘플 테스트 |
| `python scripts/etl_nav.py --mode backfill` | NAV 2년치 백필 |
| `python scripts/etl_nav.py --mode incremental` | NAV 일일 증분 |
| `python scripts/etl_holdings.py --mode backfill --dates ...` | Holdings 지정일 백필 |
| `python scripts/etl_pipeline.py` | NAV + Holdings 통합 실행 |
| `python scripts/runInitialLoad.py` | 초기 적재 + 검증 |
| `python scripts/validateData.py` | 데이터 품질 검증 + 리포트 |
| `streamlit run scripts/monitorDashboard.py` | 모니터링 대시보드 |

---

## 데이터 소스

| 소스 | 수집 내용 | 모듈 |
|------|-----------|------|
| KIS Open API | NAV, 종가, 거래량, 변동률 | `src/kis/kisNavClient.py` |
| 미래에셋 TIGER 사이트 | 구성종목 200종 | `src/scraper/tigerHoldingsScraper.py` |

### DB 테이블

| 테이블 | 설명 | 증분 방식 |
|--------|------|-----------|
| `etf_master` | ETF 마스터 | UPSERT |
| `etf_nav_daily` | 일별 NAV 시계열 | ON DUPLICATE KEY UPDATE |
| `etf_holdings_snapshot` | 구성종목 스냅샷 | INSERT IGNORE |
| `rebalancing_event` | 리밸런싱 이벤트 | INSERT IGNORE |

---

## 모니터링 대시보드

```bash
streamlit run scripts/monitorDashboard.py
# http://localhost:8501
```

- 요약 카드, NAV 추이, 리밸런싱 이벤트, Top 5 비중 추이, Holdings 조회, 검증 상태

Node.js 대시보드 설계: [`Dashboard_Definition.md`](Dashboard_Definition.md)

---

## 환경 변수 (.env)

| 변수 | 설명 |
|------|------|
| `KIS_APP_KEY` / `KIS_APP_SECRET` | KIS API 인증 |
| `TARGET_ETF_CODE` | 대상 ETF (`102110`) |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASS` / `DB_NAME` | MySQL |
| `NAV_BACKFILL_START_DATE` | NAV 백필 시작일 (`20240601`) |
| `TIGER_KSD_FUND` | TIGER KSD 펀드코드 |

---

## 로그 및 검증

- 로그: `logs/` (RotatingFileHandler, 5MB × 5백업)
- 검증: `python scripts/validateData.py` → `reports/validation_report_*.md`
- 수정 이력: `docs/rev_log.md`

---

## 구현 로드맵

| 단계 | 상태 | 산출물 |
|------|------|--------|
| 1. KIS API 인증 | ✅ | `kisAuth.py` |
| 2. MySQL 스키마 | ✅ | `schema.sql` |
| 3. NAV ETL v1 | ✅ | `etl_nav.py` |
| 4. Holdings 스크래퍼 | ✅ | `tigerHoldingsScraper.py` |
| 5. 통합 파이프라인 | ✅ | `etl_pipeline.py` |
| 6. 품질 검증·초기 적재 | ✅ | `validateData.py`, 검증 리포트 |
| 7. 문서화·모니터링 | ✅ | `README.md`, Streamlit 대시보드 |

---

## 라이선스

MIT — [`LICENSE`](LICENSE)
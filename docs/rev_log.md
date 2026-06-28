# ETF Rebalance ETL 수정 로그

## 2026-06-28 — 7단계: 문서화 + 간단 모니터링 (Streamlit) (재시행)

### 추가 파일
| 파일 | 설명 |
|------|------|
| `src/monitor/__init__.py` | 모니터링 패키지 초기화 |
| `src/monitor/dashboardQueries.py` | 대시보드용 DB 조회 (요약·NAV·이벤트·비중·holdings) |
| `scripts/monitorDashboard.py` | Streamlit 모니터링 대시보드 |

### 수정 파일
| 파일 | 설명 |
|------|------|
| `README.md` | 프로젝트 전체 문서화 |
| `ETF_Rebalancing_ETL_Definition.md` | §8 구현 완료 현황 섹션 추가 |
| `requirements.txt` | `streamlit>=1.32.0` 추가 |

### 주요 기능
- 요약 카드, NAV 추이(기간 선택), 리밸런싱 이벤트 테이블
- Top 5 종목 비중 추이, Holdings 스냅샷 조회, 검증 PASS/FAIL 표시
- 5분 TTL 캐시 + 새로고침 버튼

### 실행 방법
```bash
source /home/smt14/pywork/.venv/bin/activate
cd /home/smt14/ETFrebalancePjt
pip install -r requirements.txt
streamlit run scripts/monitorDashboard.py
```

### 대시보드 데이터 확인 (2026-06-28)
- ETF: TIGER 200 (102110), 이벤트 8건, NAV 502건, 스냅샷 9개
- 검증 리포트: validation_report_20260628.json (8/8 PASS)

---

## 2026-06-28 — 6단계: 데이터 품질 검증, 2년치 초기 적재, 로그/에러 핸들링 (재시행)

### 추가 파일
| 파일 | 설명 |
|------|------|
| `src/etl/etlLogger.py` | RotatingFileHandler 기반 공통 ETL 로거 |
| `src/etl/holdingsBackfillDates.py` | KOSPI200 분기 리밸런싱 기준일 하드코딩 목록 |
| `src/etl/dataQualityValidator.py` | 8개 항목 데이터 품질 검증 + 리포트 생성 |
| `src/etl/initialLoadRunner.py` | NAV 백필 + 분기 holdings + 검증 오케스트레이션 |
| `scripts/validateData.py` | 데이터 품질 검증 CLI |
| `scripts/runInitialLoad.py` | 2년치 초기 적재 CLI |
| `reports/validation_report_20260628.md` | 검증 리포트 (Markdown) |
| `reports/validation_report_20260628.json` | 검증 리포트 (JSON) |

### 수정 파일
| 파일 | 설명 |
|------|------|
| `src/etl/navEtl.py` | 공통 RotatingFileHandler 로거 적용 |
| `src/etl/holdingsEtl.py` | 공통 RotatingFileHandler 로거 적용 |
| `src/etl/pipelineEtl.py` | 공통 RotatingFileHandler 로거 적용 |
| `src/db/rebalancingRepository.py` | `rebuildRebalancingEvents()` 이벤트 재생성 |
| `.env.example` | `HOLDINGS_BACKFILL_DATES` 주석 예시 추가 |

### 주요 기능
- 검증 항목: etf_master, NAV 커버리지/품질/공백, holdings 비중합계, 참조무결성, NAV↔holdings 정합성, 이벤트 일치
- 로그: `RotatingFileHandler` (5MB × 5백업), 구조화 에러 `logEtlError()`
- 초기 적재: NAV 502건 백필(멱등) + 분기 holdings 9스냅샷(1,800행) + 이벤트 8건 재생성
- 검증 종합: **8/8 PASS**

### 실행 방법
```bash
source /home/smt14/pywork/.venv/bin/activate
cd /home/smt14/ETFrebalancePjt
python scripts/runInitialLoad.py
python scripts/validateData.py
```

### 적재·검증 결과 (2026-06-28 재시행)
- NAV: 502건 (2024-06-03 ~ 2026-06-26)
- holdings: 9 스냅샷, 1,800행 (2024-06-25 ~ 2026-06-25)
- rebalancing_event: 8건 (연속 스냅샷 쌍 재생성)
- 검증 리포트: `reports/validation_report_20260628.md`

---

## 2026-06-26 — 5단계: Holdings snapshot + rebalancing_event ETL 통합

### 추가 파일
| 파일 | 설명 |
|------|------|
| `src/db/holdingsRepository.py` | holdings Watermark, INSERT IGNORE, 스냅샷 조회 |
| `src/db/rebalancingRepository.py` | rebalancing_event INSERT IGNORE, 통계 |
| `src/etl/rebalancingDetector.py` | added/removed/weight_changed 감지, 턴오버 계산 |
| `src/etl/holdingsEtl.py` | Holdings ETL 오케스트레이션 |
| `src/etl/pipelineEtl.py` | NAV + Holdings 통합 파이프라인 |
| `scripts/etl_holdings.py` | Holdings ETL CLI |
| `scripts/etl_pipeline.py` | 통합 파이프라인 CLI |
| `config/cron_pipeline_etl.example` | 통합 cron 예시 |

### 수정 파일
| 파일 | 설명 |
|------|------|
| `src/scraper/tigerHoldingsScraper.py` | `normalizeSnapshotDate()` date 객체 지원 |

### 주요 기능
- holdings: `INSERT IGNORE` 멱등 적재, 기존 snapshot_date 스킵
- 리밸런싱 감지: 이전 스냅샷 대비 추가/제외/비중변경(±0.05%p), 턴오버율 산출
- event: 변동 감지 시에만 `rebalancing_event` INSERT IGNORE
- 증분: NAV 최종 거래일 기준, 1영업일 이내 holdings면 최신 처리
- 통합: `etl_pipeline.py` — NAV 증분 → Holdings 증분 순차 실행

### 실행 방법
```bash
python scripts/etl_holdings.py --mode backfill --dates 20240625,20241230,20250625,20260625
python scripts/etl_holdings.py --mode incremental
python scripts/etl_pipeline.py --nav-mode incremental --holdings-mode incremental
```

### 적재 결과 (2026-06-26 실행)
- holdings: 4 스냅샷, 800행 (2024-06-25 ~ 2026-06-25)
- rebalancing_event: 2건 (INDEX_REBALANCE, 최대 턴오버 40.12%)
- 통합 파이프라인 증분: NAV/Holdings 모두 최신 확인

---

## 2026-06-26 — 4단계: TIGER 사이트 holdings 스크래퍼 개발 + 파싱

### 추가 파일
| 파일 | 설명 |
|------|------|
| `src/scraper/__init__.py` | 스크래퍼 패키지 초기화 |
| `src/scraper/tigerHoldingsScraper.py` | TIGER pdfListAjax 수집·HTML 파싱·검증·JSON 저장 |
| `scripts/holdings_scraper.py` | 구성종목 스크래퍼 CLI |

### 수정 파일
| 파일 | 설명 |
|------|------|
| `.env.example` | `TIGER_KSD_FUND`, `TIGER_BASE_URL` 추가 |

### 주요 기능
- 데이터 소스: `pdfListAjax.ajax` (자산구성 테이블, listCnt=200 일괄 조회)
- 파싱 필드: 종목코드, 종목명, 수량, 평가금액, 비중(%), 순위
- 검증: equity 비중 합계 ≈ 100% (허용오차 2%), 음수 비중 차단
- 현금성 코드(`KRD*`) 분리, 영문 포함 6자리 종목코드 지원 (예: 0126Z0)
- JSON 저장: `data/holdings/holdings_{etf_code}_{YYYYMMDD}.json`

### 실행 방법
```bash
source /home/smt14/pywork/.venv/bin/activate
cd /home/smt14/ETFrebalancePjt
python scripts/holdings_scraper.py --date 20260625
python scripts/holdings_scraper.py --dates 20240625,20241230,20250625
python scripts/holdings_scraper.py --date 20260625 --save
```

### 스크래핑 결과 (2026-06-26 실행)
- TIGER 200 (102110): 2026-06-25 기준 200건 (equity 199 + 현금 1)
- 비중 합계: 100.02% (삼성전자 34.21%, SK하이닉스 33.07%)
- 과거 기준일(2024-06-25, 2024-12-30, 2025-06-25) 수집 성공

---

## 2026-06-26 — 3단계: KIS NAV ETL v1 (2년치 백필 + 일일 증분)

### 추가 파일
| 파일 | 설명 |
|------|------|
| `src/db/navRepository.py` | Watermark 조회, NAV 변환, etf_nav_daily UPSERT |
| `src/etl/__init__.py` | ETL 패키지 초기화 |
| `src/etl/navEtl.py` | NAV ETL 오케스트레이션 (Extract→Transform→Load) |
| `scripts/etl_nav.py` | CLI 진입점 (`--mode incremental\|backfill`) |
| `scripts/testCronNav.py` | cron 증분 2회 연속 멱등성 테스트 |
| `config/cron_nav_etl.example` | crontab 일일 증분 스케줄 예시 |

### 수정 파일
| 파일 | 설명 |
|------|------|
| `src/kis/kisNavClient.py` | `fetchNavComparisonDailyTrend()`, `fetchNavDailyRange()` 추가 |
| `src/kis/__init__.py` | 신규 NAV 일별 API export |
| `.env.example` | `NAV_BACKFILL_START_DATE` 추가 |

### 주요 기능
- KIS API: `/uapi/etfetn/v1/quotations/nav-comparison-daily-trend` (tr_id: FHPST02440200)
- 100건/호출 제한 → 종료일 역순 분할 호출로 2년치 백필 (6배치)
- Watermark: `SELECT MAX(trade_date)` 기반 증분 (`last_date + 1` ~ 오늘)
- `ON DUPLICATE KEY UPDATE` 멱등 UPSERT
- 로그: `logs/etl_nav.log`

### 실행 방법
```bash
source /home/smt14/pywork/.venv/bin/activate
cd /home/smt14/ETFrebalancePjt
python scripts/etl_nav.py --mode backfill      # 최초 2년치 백필
python scripts/etl_nav.py --mode incremental   # 일일 증분 (cron용)
python scripts/testCronNav.py                  # cron 멱등성 테스트
```

### 적재 결과 (2026-06-26 실행)
- TIGER 200 (102110): **502건** (2024-06-03 ~ 2026-06-26)
- 증분/cron 시뮬레이션: 최신 상태 확인, 멱등성 통과

---

## 2026-06-26 — 2단계: MySQL 스키마 생성 및 etf_master 초기 적재

### 추가 파일
| 파일 | 설명 |
|------|------|
| `sql/schema.sql` | 4개 테이블 DDL (etf_master, etf_nav_daily, etf_holdings_snapshot, rebalancing_event) |
| `src/db/__init__.py` | DB 패키지 초기화 |
| `src/db/dbConnection.py` | MySQL/SQLAlchemy 연결, DB 생성, DDL 실행 |
| `src/db/etfMasterSeed.py` | etf_master 시드 데이터 및 UPSERT |
| `scripts/initSchema.py` | 스키마 초기화 단독 실행 스크립트 |
| `scripts/seedEtfMaster.py` | etf_master 시드 단독 실행 스크립트 |
| `scripts/initDatabase.py` | 스키마 + 시드 통합 실행 스크립트 |

### 수정 파일
| 파일 | 설명 |
|------|------|
| `src/config/envLoader.py` | `getDbConfig()`, `validateDbConfig()` 추가 |

### 주요 기능
- `.env`의 `DB_HOST/PORT/USER/PASS/NAME` 기반 MySQL 연결 (현재 `172.22.32.1:3306`, DB `etf_rebalance`)
- `ensureDatabaseExists()`: DB 없으면 `utf8mb4` 문자셋으로 자동 생성
- `executeSchemaSql()`: `sql/schema.sql` DDL 멱등 실행 (`CREATE TABLE IF NOT EXISTS`)
- `upsertEtfMaster()`: TIGER 200 (`102110`) 마스터 데이터 `ON DUPLICATE KEY UPDATE` 적재

### 실행 방법
```bash
source /home/smt14/pywork/.venv/bin/activate
cd /home/smt14/ETFrebalancePjt
python scripts/initDatabase.py   # 통합 (권장)
# 또는
python scripts/initSchema.py
python scripts/seedEtfMaster.py
```

### 적재 결과 (2026-06-26 실행)
- 생성 테이블: `etf_master`, `etf_nav_daily`, `etf_holdings_snapshot`, `rebalancing_event`
- `etf_master` 1건: TIGER 200 (102110), KOSPI 200, 상장일 2007-11-08, 총보수 0.05%

---

## 2026-06-25 — 1단계: KIS API 인증 및 NAV 샘플 호출

### 추가 파일
| 파일 | 설명 |
|------|------|
| `.env.example` | KIS API / DB 환경 변수 템플릿 |
| `.env` | 로컬 환경 변수 (gitignore 대상) |
| `.gitignore` | `.env`, 토큰 캐시 등 제외 |
| `src/config/envLoader.py` | dotenv 기반 환경 변수 로더 |
| `src/kis/kisAuth.py` | OAuth 토큰 발급·캐시·자동 갱신 |
| `src/kis/kisNavClient.py` | NAV 비교추이 / ETF 현재가 API 클라이언트 |
| `scripts/testKisNav.py` | 1단계 샘플 호출 테스트 스크립트 |

### 주요 기능
- `refreshKisToken()`: 만료 30분 전 자동 갱신, `data/.kis_token_cache.json` 캐시
- `fetchNavComparisonTrend()`: `/uapi/etfetn/v1/quotations/nav-comparison-trend` (tr_id: FHPST02440000)
- `fetchEtfCurrentPrice()`: `/uapi/etfetn/v1/quotations/inquire-price` (tr_id: FHPST02400000)
- 대상 ETF 기본값: TIGER 200 (`102110`)

### 실행 방법
```bash
source /home/smt14/pywork/.venv/bin/activate
cd /home/smt14/ETFrebalancePjt
pip install -r requirements.txt
# .env에 KIS_APP_KEY, KIS_APP_SECRET 실제 값 입력 후
python scripts/testKisNav.py
```
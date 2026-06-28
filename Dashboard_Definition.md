# ETF Rebalance Dashboard 요구사항 정의서

**문서 버전**: 1.1  
**작성일**: 2026년 6월 25일  
**기술 스택**: Node.js (Express) + Chart.js  
**목적**: ETL로 적재된 리밸런싱 및 지분 변동 데이터를 시각적으로 쉽게 확인할 수 있는 가벼운 개인용 대시보드  
**포트 정책**: Express는 **테스트/대안 UI** (`http://localhost:3003`). **메인 모니터링**은 Streamlit (`http://localhost:3000`, `scripts/monitorDashboard.py`)

---

## 1. 프로젝트 개요

### 목적
- ETL 프로젝트(`ETFrebalancePjt`)에서 MySQL에 쌓이는 데이터를 **한눈에 보고 이해**할 수 있게 한다.
- 리밸런싱 이벤트 발생 현황과 주요 종목의 지분 변동 추이를 **테이블 + 선그래프**로 직관적으로 보여준다.
- 복잡한 BI 툴 없이도 **빠르고 가볍게** 사용할 수 있는 수준으로 개발한다.

### 대상 사용자
- 프로젝트 작성자 본인 (개인 학습 및 투자 인사이트 용도)
- 추후 필요 시 간단한 공유 기능 추가 가능

### 핵심 가치
- "오늘 TIGER 200이 어떻게 리밸런싱 됐지?"
- "삼성전자 비중이 최근 어떻게 변했나?"
- "NAV는 안정적으로 오르고 있나?" 를 빠르게 파악

---

## 2. 주요 화면 구성 (MVP)

| 화면 | 주요 콘텐츠 | 우선순위 |
|------|-------------|----------|
| **대시보드 홈** | 요약 카드 + 최근 리밸런싱 이벤트 테이블 | ★★★★★ |
| **리밸런싱 이벤트** | 전체 이벤트 목록 + 상세 모달 | ★★★★☆ |
| **NAV 추이 그래프** | TIGER 200 NAV 선그래프 (기간 선택) | ★★★★★ |
| **종목 비중 변화** | 특정 종목 비중 추이 선그래프 | ★★★★☆ |
| **최근 Holdings** | 특정 날짜 Holdings 스냅샷 테이블 | ★★★☆☆ |

**MVP 범위**: 홈 + NAV 그래프 + 리밸런싱 이벤트 + 종목 비중 변화 (Top 3~5 종목)

---

## 3. 기술 스택

| 구분 | 기술 | 비고 |
|------|------|------|
| Runtime | Node.js 18+ | WSL 환경 |
| Web Framework | Express.js | 가볍고 빠름 |
| 템플릿 엔진 | EJS | 간단한 동적 렌더링 |
| 차트 라이브러리 | **Chart.js** (v4) | CDN 또는 npm 설치 |
| DB 드라이버 | `mysql2` (Promise 기반) | 연결 풀 사용 권장 |
| 스타일 | Bootstrap 5 (CDN) | 빠른 UI 구성 |
| 환경변수 | `dotenv` | DB 접속 정보 관리 |
| 실행 | `node app.js` 또는 `npm start` | 간단한 스크립트 |

**선택 이유**: 별도의 프론트엔드 프레임워크(React/Vue) 없이도 충분히 예쁘고 실용적인 대시보드를 만들 수 있음. 개발 속도가 빠름.

---

## 4. 화면 상세 명세

### 4.1 대시보드 홈 (메인 페이지)

**URL**: `/` 또는 `/dashboard`

**구성 요소**:
- 상단 네비게이션 바 (홈, 이벤트, 그래프, Holdings)
- **요약 카드** (4개)
  - 총 리밸런싱 이벤트 수 (지난 1년)
  - 최근 리밸런싱 일자
  - 현재 NAV
  - 최근 30일 평균 일일 변동률
- **최근 리밸런싱 이벤트 테이블** (최근 10건)
  - 컬럼: 이벤트 일자, 이벤트 유형, 추가 종목 수, 제거 종목 수, 턴오버율(%), 비고
- 하단에 **NAV 추이 미니 그래프** (최근 3개월)

### 4.2 리밸런싱 이벤트 목록

**URL**: `/events`

**기능**:
- 전체 이벤트 목록 (페이지네이션 또는 무한 스크롤)
- 테이블 컬럼:
  - `event_date`
  - `event_type`
  - `added_stocks_count`
  - `removed_stocks_count`
  - `changed_weights_count`
  - `total_turnover_pct`
  - `description` (간단 요약)
- 행 클릭 시 **상세 모달** 또는 별도 페이지에서 해당 일자의 Holdings 변화 상세 표시

### 4.3 NAV 추이 선그래프

**URL**: `/nav-trend`

**기능**:
- **Chart.js Line Chart**
- X축: 날짜
- Y축: NAV
- 기간 선택 버튼: 1개월 / 3개월 / 6개월 / 1년 / 전체
- hover 시 정확한 날짜와 NAV 값 표시
- 옵션: 이동평균선(선택)

### 4.4 종목 비중 변화 그래프

**URL**: `/weight-trend`

**기능**:
- 종목 선택 드롭다운 또는 검색 (삼성전자, SK하이닉스 등 Top 종목 미리 로드)
- 선택한 종목의 **비중(weight_pct) 추이**를 선그래프로 표시
- 여러 종목을 동시에 비교할 수 있는 멀티 라인 지원 (고급)
- 기간 선택 기능

### 4.5 최근 Holdings 스냅샷 (선택)

**URL**: `/holdings`

**기능**:
- 날짜 선택기 (캘린더 또는 드롭다운)
- 선택한 날짜의 전체 구성종목 테이블
- 컬럼: 순위, 종목명, 종목코드, 비중(%), 보유주식수, 시가총액
- 정렬 및 검색 기능

---

## 5. 데이터 연동 (주요 쿼리 예시)

### rebalancing_event 조회
```sql
SELECT event_date, event_type, added_stocks_count, removed_stocks_count,
       total_turnover_pct, description
FROM rebalancing_event
WHERE etf_code = '102110'
ORDER BY event_date DESC
LIMIT 30;
```

### NAV 추이 조회
```sql
SELECT trade_date, nav
FROM etf_nav_daily
WHERE etf_code = '102110'
  AND trade_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
ORDER BY trade_date ASC;
```

### 특정 종목 비중 추이
```sql
SELECT snapshot_date, weight_pct
FROM etf_holdings_snapshot
WHERE etf_code = '102110'
  AND stock_code = '005930'
ORDER BY snapshot_date ASC;
```

---

## 6. 비기능 요구사항

| 항목 | 요구사항 | 비고 |
|------|----------|------|
| **성능** | 페이지 로딩 2초 이내 | Chart.js 데이터는 API로 비동기 로드 |
| **보안** | 개인용이므로 간단한 IP 제한 또는 Basic Auth | .env로 DB 정보 보호 |
| **유지보수** | ETL 프로젝트와 동일한 폴더 구조 유지 | `dashboard/` 하위에 모든 파일 배치 |
| **로그** | 간단한 요청 로그 (morgan 사용) | 에러 발생 시 파일 로깅 |
| **확장성** | API 라우터 분리 (`routes/`) | 나중에 React로 교체하기 쉽게 |

---

## 7. 폴더 구조 제안 (dashboard 폴더 내부)

```
dashboard/
├── app.js                     # Express 진입점
├── package.json
├── .env
├── routes/
│   ├── index.js
│   ├── events.js
│   └── charts.js
├── views/
│   ├── layout.ejs
│   ├── dashboard.ejs
│   ├── events.ejs
│   └── nav-trend.ejs
├── public/
│   ├── css/
│   ├── js/
│   │   └── charts.js        # Chart.js 초기화 스크립트
│   └── images/
├── services/
│   └── db.js                  # MySQL 연결 및 쿼리 함수
└── utils/
    └── dateHelper.js
```

---

## 8. 개발 우선순위 (추천)

**1단계 (MVP - 3~4일 소요 예상)**
- 대시보드 홈 + 요약 카드
- NAV 추이 선그래프
- 최근 리밸런싱 이벤트 테이블

**2단계**
- 종목 비중 변화 그래프
- 이벤트 상세 모달

**3단계 (선택)**
- Holdings 스냅샷 조회
- 다크모드 / 반응형 개선
- 기간 비교 기능

---

## 9. 실행 방법 (예상)

```bash
cd dashboard
npm install
cp .env.example .env   # DB 접속 정보 입력, PORT=3003 권장
PORT=3003 npm start
# 또는
PORT=3003 node app.js
```

브라우저에서 `http://localhost:3003` 접속 (Express 테스트용; 메인 Streamlit은 3000)

---

## 10. 비고 및 고려사항

- 이 대시보드는 **ETL과 완전히 독립적으로 실행** 가능해야 함 (ETL이 안 돌아가도 대시보드는 조회 가능)
- 데이터가 없을 경우 "데이터가 없습니다" 안내 메시지 필수
- Chart.js는 CDN 사용을 기본으로 하되, 필요 시 npm 설치 방식도 지원
- 추후 Next.js나 React로 고도화하고 싶을 때를 대비해 API 라우터를 잘 분리하는 것이 좋음

---


*이 문서는 ETL 프로젝트의 연장으로 작성되었으며, 실제 구현 전 충분한 검토를 권장합니다.*
# ETF Rebalance ETL 수정 로그

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
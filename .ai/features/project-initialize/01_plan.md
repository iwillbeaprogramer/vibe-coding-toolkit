# 01_plan - project-initialize

작성: Antigravity
일시: 2026-05-28

## 기능 목표
- 사용자가 Windows 환경에서 주식 및 ETF의 티커나 종목명을 검색하여 가격 정보, 핵심 재무 지표, 그리고 미려하게 디자인된 기간별 가격 차트를 조회할 수 있는 로컬 애플리케이션을 구축합니다.
- 프론트엔드는 React(Vite, TypeScript), 백엔드는 Python FastAPI 및 yfinance를 결합하여 견고한 에러 처리와 함께 실시간성 지연 시세를 제공합니다.

## 구현 접근 방식
- **백엔드**: Python FastAPI를 활용하여 경량 및 고성능 비동기 API 서버를 구성합니다. 무료 금융 데이터 공급원인 Yahoo Finance를 래핑한 `yfinance` 라이브러리와 비공식 Autocomplete API를 조합하여 검색 및 상세 조회를 처리합니다. 속도 제한(Rate Limit)을 완화하기 위해 인메모리 캐싱 레이어를 적용합니다.
- **프론트엔드**: Vite + React + TypeScript 기반으로 단일 페이지 애플리케이션(SPA)을 구축합니다. Vanilla CSS를 사용하여 HSL 기반의 네온 다크 모드, Glassmorphism, 부드러운 애니메이션 효과가 포함된 프리미엄 핀테크 대시보드 UI를 디자인합니다. 가격 차트는 React 생태계에서 가장 결합도가 높고 미려한 `Recharts`를 사용해 종가 기준 라인과 툴팁 내 OHLC 상세 정보를 제공합니다.
- **통합 및 테스트**: 백엔드는 `pytest`로 API의 강건성을 검증하고, 프론트엔드는 `vitest`와 `@testing-library/react`를 활용해 주요 렌더링 상태를 테스트합니다. Windows 사용자를 위해 프론트엔드와 백엔드를 한 번에 구동할 수 있는 `run.bat` 스크립트를 제공합니다.

## 검토한 대안
- **대안 1: Alpha Vantage 또는 Finnhub 등의 API 키 기반 연동**
  - **장점**: 공식적이고 표준화된 JSON API 제공, 높은 데이터 신뢰도.
  - **단점**: 사용자가 직접 API 키를 발급받아 환경 변수로 설정해야 하므로 실행 진입 장벽이 큼. 무료 티어의 경우 호출 제한(예: 분당 5회)이 극도로 엄격하여 다중 검색이나 차트 조회 시 쉽게 에러가 발생함.
  - **채택하지 않은 이유**: 사용자 자격 증명 없이 즉시 실행 가능한 앱을 지향한다는 스펙 조건 및 편의성을 극대화하기 위해 API 키가 불필요한 `yfinance` 기반 접근법을 최종 선택함.
- **대안 2: Electron 또는 Neutralinojs를 이용한 정식 데스크톱 패키징**
  - **장점**: 브라우저 없이 독립적인 Windows 실행 파일(`.exe`) 형태로 완전한 윈도우 앱 경험 제공.
  - **단점**: 번들 크기가 비대해지고, 패키징 및 빌드 설정 복잡성이 급증하여 개발 주기 지연 유발.
  - **채택하지 않은 이유**: 스펙의 제외 범위 명시에 따라, 로컬에서 실행 가능한 React + FastAPI 개발 모드 기반의 실행 환경을 완벽하게 다지는 것에 집중하고 정식 패키징은 후속 기능으로 남겨둠.

## 변경 파일 계획
모든 신규 프로덕션 코드는 `src/` 하위에 배치되며, 테스트 코드는 `tests/` 하위에만 위치합니다.

### [백엔드 컴포넌트]
- **[NEW] [requirements.txt](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/backend/requirements.txt)**
  - 백엔드에 필요한 핵심 라이브러리 지정 (`fastapi`, `uvicorn`, `yfinance`, `pydantic`, `requests`).
- **[NEW] [main.py](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/backend/main.py)**
  - FastAPI 애플리케이션 생성, CORS 미들웨어 설정(React 통신용), 엔드포인트 라우팅 및 전역 에러 핸들러 구성.
- **[NEW] [schemas.py](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/backend/schemas.py)**
  - 검색 결과 스키마(`SearchResult`), 주식 정보 및 차트 정보를 포괄하는 상세 응답 스키마(`StockDetailResponse`)를 Pydantic으로 정의. 모든 데이터 필드는 누락 대비를 위해 Optional 처리.
- **[NEW] [services.py](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/backend/services.py)**
  - yfinance API 호출 및 데이터 가공 로직. Yahoo Finance AutoComplete API를 활용한 종목 검색, `yfinance.Ticker`를 통한 상세 지표 추출 및 기간별 역사적 차트 데이터 조회 기능 구현. 인메모리 캐싱 적용.

### [프론트엔드 컴포넌트]
- **[NEW] [package.json](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/frontend/package.json)**
  - React, TypeScript, Vite, Recharts, Lucide React(아이콘용) 의존성 및 스크립트 정의.
- **[NEW] [vite.config.ts](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/frontend/vite.config.ts)**
  - Vite 번들러 설정 및 백엔드 API 프록시 설정 (`/api` -> `http://localhost:8000`).
- **[NEW] [tsconfig.json](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/frontend/tsconfig.json)**
  - TypeScript 빌드 및 환경 설정 파일.
- **[NEW] [index.html](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/frontend/index.html)**
  - Google Font (Inter 또는 Outfit) 적용 및 React 마운트 지점 제공.
- **[NEW] [index.css](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/frontend/src/index.css)**
  - HSL 컬러 변수, 다크 테마 배경, 프리미엄 스크롤바, Glassmorphism 카드 공통 스타일, 미크로 애니메이션 등 글로벌 디자인 시스템 구축.
- **[NEW] [main.tsx](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/frontend/src/main.tsx)**
  - React 애플리케이션 진입점 및 전역 CSS 마운트.
- **[NEW] [App.tsx](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/frontend/src/App.tsx)**
  - 전체 레이아웃 흐름 제어, 검색창 상태 관리, API 호출 상태(로딩, 에러, 성공) 관리 및 뷰 오케스트레이션.
- **[NEW] [SearchBar.tsx](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/frontend/src/components/SearchBar.tsx)**
  - 입력값 유효성 검사, Debounce 처리된 입력에 기반한 검색 후보 API 호출, 세련된 드롭다운 추천 레이아웃.
- **[NEW] [StockDetail.tsx](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/frontend/src/components/StockDetail.tsx)**
  - 종목 기본 정보, 가격 상태 배지, 핵심 투자 지표Grid(시총, 거래량, 52주 고/저 등), ETF 전용 상세 지표 카드(운용보수, 순자산) 렌더링. 누락 값은 `데이터 없음`으로 세련되게 처리.
- **[NEW] [StockChart.tsx](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/frontend/src/components/StockChart.tsx)**
  - Recharts Area/Line Chart를 활용한 미려한 차트 구현. 기간 변경 탭(1D, 1M, 6M, 1Y, 5Y), 차트 인터랙션 및 OHLC 커스텀 툴팁 제공.
- **[NEW] [Disclaimers.tsx](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/frontend/src/components/Disclaimers.tsx)**
  - 화면 하단에 고정 표시되는 "본 애플리케이션은 투자 조언이 아닌 정보 제공 목적으로만 제공됩니다" 면책 조항 컴포넌트.

### [테스트 및 도구]
- **[NEW] [test_api.py](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/tests/backend/test_api.py)**
  - `pytest` 및 `httpx.AsyncClient`를 사용하여 백엔드 검색 API, 상세 정보 조회 API의 성공 및 실패(잘못된 티커, 외부 에러) 처리를 테스트.
- **[NEW] [App.test.tsx](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/tests/frontend/App.test.tsx)**
  - React 컴포넌트의 로딩 상태 렌더링, 에러 상태 시 재시도 버튼 렌더링, 유효하지 않은 입력 방어 동작을 테스트.
- **[NEW] [run.bat](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/run.bat)**
  - 백엔드(FastAPI)와 프론트엔드(Vite) 개발 서버를 별도 프로세스로 한 번에 실행해 주는 윈도우 통합 배치 파일.

## 데이터 / 제어 흐름
### 1. 검색 흐름 (Search Flow)
```
[사용자 입력] 
     │ (1~20자, 영숫자, 공백 등 제한)
     ▼
[React SearchBar (Debounced 300ms)]
     │
     ▼ (GET /api/search?q=QLD)
[FastAPI /api/search Router]
     │
     ▼ (requests 호출 - Autocomplete API)
[Yahoo Finance Autocomplete Endpoint]
     │
     ▼ (JSON 검색 후보 목록 반환)
[FastAPI 가공 및 Schema 검증]
     │
     ▼ (JSON 응답)
[React SearchBar Dropdown List에 표시]
```

### 2. 상세 조회 및 차트 흐름 (Detail & Chart Flow)
```
[종목 선택 또는 티커 강제 입력]
     │
     ▼ (GET /api/stock/QLD?period=1mo)
[FastAPI /api/stock/{ticker} Router]
     │
     ├─► [인메모리 캐시 조회] ──(Hit 시)──┐
     │                                     ▼
     ├─► [Cache Miss 시 yfinance 호출] ───► [상세 정보 & 차트 병렬 처리]
     │                                              │
     │                                              ▼
     │                                     [응답 가공 및 캐싱]
     │                                              │
     └────────────────◄─────────────────────────────┘
     │
     ▼ (JSON 통합 데이터 구조 반환)
[React App State]
     ├──► [StockDetail] ──► 현재가, 변동 배지, 재무 지표 Grid 렌더링
     └──► [StockChart]  ──► Recharts Area Chart 렌더링 (기간 변경 탭 이벤트와 연동)
```

## 구현 단계 분할
1. **단계 1: 백엔드 기본 설계 및 뼈대 구축 (src/backend)**
   - 완료 기준: `requirements.txt` 정의, FastAPI 뼈대 서버(`main.py`) 구동 확인, 로컬 실행용 가상환경 생성.
2. **단계 2: 데이터 서비스 레이어 및 API 라우터 구현 (src/backend)**
   - 완료 기준: `services.py` 및 `schemas.py`를 완성하여 `yfinance` 기반 검색 및 상세 정보/차트 정보 통합 API의 구현 및 메모리 캐싱 작동 확인.
3. **단계 3: 프론트엔드 프로젝트 셋업 및 CSS 디자인 시스템 구축 (src/frontend)**
   - 완료 기준: Vite + React + TypeScript 기초 프로젝트 생성. `index.css`에 Premium HSL 다크 모드 및 Glassmorphism 디자인 시스템 이식.
4. **단계 4: UI 컴포넌트 개발 및 모크 연동 (src/frontend/src/components)**
   - 완료 기준: `SearchBar`(자동완성), `StockDetail`, `StockChart`(Recharts 연동), `Disclaimers` 개발 및 정적 목업 렌더링 완료.
5. **단계 5: 백엔드-프론트엔드 연동 및 통합 상태 핸들링**
   - 완료 기준: React State와 Fetch API를 결합하여 실제 백엔드 API 연동. 로딩 스켈레톤, 빈 결과 대응, HTTP 오류 코드별 미려한 오류 경고창 및 재시도 로직 완성.
6. **단계 6: 테스트 코드 작성 및 종합 검증 (tests/)**
   - 완료 기준: pytest 백엔드 테스트 통과, vitest 프론트엔드 단위 테스트 통과, 윈도우 원클릭 실행을 위한 `run.bat` 스크립트 작성 및 개발자 실행 가이드 문서 확인.

## 위험 구간
- **위험 항목 1: yfinance 라이브러리의 불안정성 및 Yahoo Finance의 요청 제한(Rate Limit)**
  - **완화 방안**: 외부 API 오류 시 502/503 HTTP 응답코드를 명확히 반환하여 프론트엔드에서 즉시 재시도 버튼과 설명(지연 시세 및 일시적 요청 제한 가능성 고지)을 제공합니다. 또한 FastAPI 내부의 인메모리 딕셔너리를 활용해 동일한 티커와 기간에 대한 요청을 5분간 캐싱하여 불필요한 외부 네트워크 호출을 대폭 차단합니다.
- **위험 항목 2: 주식과 ETF 간 제공 데이터 불균형으로 인한 렌더링 오류**
  - **완화 방안**: Pydantic 스키마 정의 시 모든 상세 속성을 `Optional`로 선언하고 기본값을 `None`으로 제공합니다. 프론트엔드에서는 렌더링 시 논리 연산자(`??` 또는 `||`)를 활용하여 값 부재 시 대시(`-`) 또는 `데이터 없음` 텍스트를 정렬된 그리드 안에 깨끗하게 채워 넣어 UI가 깨지거나 비정상적으로 누락되어 보이는 현상을 완전히 격리합니다.

## 새 의존성
- **백엔드 (Python)**:
  - `fastapi`, `uvicorn[standard]` (고성능 ASGI API 프레임워크 및 서버)
  - `yfinance` (금융 데이터 획득용)
  - `pydantic` (데이터 규격 검증 및 직렬화)
  - `requests` (Yahoo Autocomplete API 비동기/동기 호출용)
- **프론트엔드 (Node.js)**:
  - `recharts` (미려하고 유연한 리액트 선/영역 차트 라이브러리)
  - `lucide-react` (핀테크 분위기에 어울리는 모던 아이콘 패키지)

## 테스트 전략
- **백엔드 단위/통합 테스트 (`tests/backend/test_api.py`)**
  - `/api/search?q=QLD` 호출에 대한 정상 검색 리스트 응답 포맷 검증.
  - `/api/stock/QLD?period=1mo` 호출 시 필수 지표와 차트 배열이 정상 반환되는지 확인.
  - 유효하지 않은 티커(예: `INVALID_TICKER_123`)로 조회 시 404 Not Found 상태코드 반환 여부 검증.
  - 빈 검색어나 잘못된 파라미터 유입 시 400 Bad Request 방어 작동 검증.
- **프론트엔드 단위 테스트 (`tests/frontend/App.test.tsx`)**
  - `SearchBar`의 1글자 미만 입력 시 API 비활성화 검증.
  - API 호출 로딩 중 `Skeleton` UI 렌더링 검증.
  - API 실패(502/503 등) 시 에러 배너와 `다시 시도` 버튼의 정상 렌더링 여부 검증.

## 롤백 / 복구 방향
- 본 프로젝트는 로컬 실행용 애플리케이션으로, DB나 클라우드 마이그레이션을 수반하지 않는 독립 실행 방식입니다.
- 기능 구현 단계 도중 또는 완료 후 문제 발생 시, 로컬 Git 버전 제어를 통해 특정 커밋으로 즉각 롤백(`git reset --hard`)이 가능합니다.
- 외부 라이브러리(`yfinance`)의 심각한 버전 이슈나 API 명세 변경 시, 의존성 파일(`requirements.txt`)의 버전을 고정하여 빌드 환경을 빌드 시점 상태로 즉시 복구합니다.

## 실행 승인
- risk_level: medium (로컬 실행 중심이며, 비가역적인 시스템/클라우드 자원 변경이 없으므로 medium으로 산정)
- human_gate_required: true (사용자 경험에 직접적인 영향을 주는 UI 디자인 설계, yfinance 무료 금융 공급원 선정, Windows 실행 방식 조율을 위해 수동 승인 게이트 지정)
- human_gate_reason: 초기 스택 선정, Windows 로컬 실행 오케스트레이션 구성, 그리고 Recharts 및 yfinance 의존성 추가에 대한 사람 승인을 득하고자 함
- approval_required_before_develop: true (02_develop 단계 진입 전 본 구현 계획안에 대한 사용자 승인을 필수적으로 획득함)

## 스펙 모호점 처리
- **종목 검색 기능의 상세 구현**: yfinance는 직접적인 자동완성 검색 기능이 다소 불안정하므로, Yahoo Finance의 공용 Autocomplete 엔드포인트(`https://query1.finance.yahoo.com/v1/finance/search?q={query}`)를 FastAPI 백엔드가 프록시 형태로 대리 호출하도록 임의 결정했습니다. 이 방식은 별도의 토큰 발급 없이 극도로 빠르고 신뢰성 높은 다국적 종목 검색을 보장합니다.

## Git 기준점
- base_commit: 1249abcf0fcc4f1edca3a47c24968c6186bcacdb
- diff_base_command: `git diff 1249abcf0fcc4f1edca3a47c24968c6186bcacdb`

## 사용자 확인 사항
- 본 계획안은 스펙 및 하네스 정책의 recommended defaults를 충실히 반영하여 수립되었습니다.
- 사용자는 본 계획안의 디렉토리 구조(src/backend, src/frontend), 차트 라이브러리(Recharts), 데이터 공급원(yfinance + Yahoo Autocomplete)의 타당성을 검토하고 승인해주시기 바랍니다.

## 단계 결과
- status: PASS
- next_stage: 02_develop
- human_gate_required: true
- blocking_reason: 없음
- risk_level: medium
- produced_files:
  - .ai/features/project-initialize/01_plan.md
- changed_files:
  - .ai/features/project-initialize/01_plan.md
- commit_created: false
- commit_message: 
- model_mismatch: false
- actual_model: Antigravity

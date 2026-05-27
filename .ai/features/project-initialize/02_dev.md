# 02_dev - project-initialize

작성: Codex
일시: 2026-05-28

## 기능 목표
- React + TypeScript 프론트엔드와 Python FastAPI 백엔드를 초기 구성해, 사용자가 `QLD` 같은 티커를 검색하고 상세 가격/지표/차트를 조회할 수 있는 로컬 주식 정보 앱의 1차 구현을 제공한다.

## 변경 파일
- .ai/features/project-initialize/00_spec.md (입력 / 변경 금지)
- .ai/features/project-initialize/01_plan.md (입력 / 변경 금지)
- .ai/features/project-initialize/02_dev.md (신규)
- .ai/features/project-initialize/02_dev.result.json (신규)
- src/backend/__init__.py (신규)
- src/backend/requirements.txt (신규)
- src/backend/main.py (신규)
- src/backend/schemas.py (신규)
- src/backend/services.py (신규)
- src/frontend/package.json (신규)
- src/frontend/package-lock.json (신규)
- src/frontend/index.html (신규)
- src/frontend/tsconfig.json (신규)
- src/frontend/vite.config.ts (신규)
- src/frontend/src/main.tsx (신규)
- src/frontend/src/App.tsx (신규)
- src/frontend/src/api.ts (신규)
- src/frontend/src/types.ts (신규)
- src/frontend/src/index.css (신규)
- src/frontend/src/components/SearchBar.tsx (신규)
- src/frontend/src/components/StockDetail.tsx (신규)
- src/frontend/src/components/StockChart.tsx (신규)
- src/frontend/src/components/Disclaimers.tsx (신규)
- tests/conftest.py (신규)
- tests/backend/test_api.py (신규)
- tests/frontend/setup.ts (신규)
- tests/frontend/App.test.tsx (신규)

## 구현 내용
- FastAPI 앱에 `/api/health`, `/api/search`, `/api/stock/{ticker}` 엔드포인트를 추가했다.
- Yahoo Finance autocomplete API와 `yfinance` 기반 상세 조회를 서비스 계층으로 분리하고, 5분 인메모리 캐시, 입력 검증, 기간 검증, 외부 공급자 오류 매핑을 구현했다.
- 상세 응답에는 현재가, 전일 종가, 시가/고가/저가, 거래량, 평균 거래량, 시가총액, 52주 범위, PER/EPS/배당/Beta, 섹터/산업, ETF 비용보수/운용사/총자산, 차트 OHLC 데이터를 포함했다.
- React 앱은 검색 상단바, 자동완성 드롭다운, 상세 지표 패널, 기간 선택형 Recharts 가격 차트, 오류/로딩/재시도 상태, 투자 조언 아님 고지를 제공한다.
- 테스트는 백엔드 API 정상/오류 매핑과 프론트엔드 초기 로딩, API 실패 배너, 검색 입력 방어, 직접 티커 조회를 커버한다.

## 왜 이렇게 구현했는가
- 계획의 기본값대로 별도 API 키 없이 실행 가능한 `yfinance`와 Yahoo autocomplete를 사용했다. 무료 데이터 공급자는 지연/누락/차단 가능성이 있으므로 캐시와 명확한 502/503 계열 오류 메시지를 우선했다.
- Pydantic 스키마의 상세 필드는 대부분 Optional로 두어 주식과 ETF 간 데이터 차이 때문에 UI가 깨지지 않게 했다.
- 프론트엔드는 Vite 단일 SPA로 구성했다. 최초 화면을 마케팅 페이지가 아니라 검색과 상세 정보 중심의 작업 화면으로 만들었다.
- `tests/`가 프론트 프로젝트 루트 밖에 있으므로 Vitest 설정에 외부 테스트 경로와 테스트용 패키지 alias를 명시했다.
- 계획에는 루트 `run.bat`가 있었지만, 현재 개발 프리셋의 write policy가 프로덕션 코드 `src/`, 테스트 `tests/`, stage output 중심이고 루트 제품 파일 생성을 제한하므로 이번 단계에서는 생성하지 않았다. Windows 통합 실행 스크립트는 후속 단계에서 write policy가 허용될 때 추가하는 것이 안전하다.

## 새로 추가한 의존성
- backend: `fastapi`, `uvicorn[standard]`, `yfinance`, `pydantic`, `requests`, `pytest`, `httpx`
- frontend: `react`, `react-dom`, `typescript`, `vite`, `@vitejs/plugin-react`, `recharts`, `lucide-react`
- frontend test: `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`

## 테스트
- 작성한 테스트 파일:
  - tests/backend/test_api.py
  - tests/frontend/App.test.tsx
  - tests/frontend/setup.ts
  - tests/conftest.py
- 실행한 테스트 명령과 결과:
  - `python -m py_compile src\backend\__init__.py src\backend\main.py src\backend\schemas.py src\backend\services.py`: PASS
  - `pytest tests\backend`: PASS, 5 passed
  - `npm test` (`src/frontend`): PASS, 4 passed
  - `npm run build` (`src/frontend`): PASS
  - `git diff --check`: PASS
  - 로컬 HTTP smoke: `http://127.0.0.1:5173` 200, `GET /api/stock/QLD?period=1mo` 200, chart_points 21
- 참고:
  - `npm install`에서 Recharts 2.x deprecation 경고와 moderate 취약점 5개가 보고되었다. 계획이 Recharts 기반이므로 이 단계에서는 강제 major 업그레이드를 하지 않았다.
  - `npm test` 실행 중 jsdom에서 Recharts 컨테이너 크기 경고가 stderr에 출력되었지만 테스트는 통과했다.
  - 인앱 Browser 플러그인은 현재 세션에서 `iab` 브라우저를 사용할 수 없어 시각 검증 대신 로컬 HTTP smoke로 확인했다.

## 알려진 한계 / 추후 개선 사항
- 무료 Yahoo Finance/yfinance 기반이라 실시간성, 데이터 완전성, 호출 안정성을 보장하지 않는다.
- 정식 Windows `.exe` 패키징과 루트 실행 배치 파일은 이번 단계에 포함하지 않았다.
- 차트 번들 크기가 500KB 경고를 넘는다. 후속 단계에서 code splitting 또는 차트 라이브러리 버전 전략을 검토할 수 있다.
- ETF 레버리지/상품 설명은 공급자 필드가 제한적이라 가능한 값만 표시한다.

## Git 정보
- base_commit: 1249abcf0fcc4f1edca3a47c24968c6186bcacdb
- harness_commit_required: true
- commit_created_by_model: false
- commit_message_suggestion: project-initialize[20260528-081102][02_develop]
- commit_scope:
  - .ai/features/project-initialize/00_spec.md
  - .ai/features/project-initialize/00_spec.result.json
  - .ai/features/project-initialize/01_plan.md
  - .ai/features/project-initialize/01_plan.result.json
  - .ai/features/project-initialize/02_dev.md
  - .ai/features/project-initialize/02_dev.result.json
  - src/backend/
  - src/frontend/
  - tests/
- pre_commit_diff_command: git diff 1249abcf0fcc4f1edca3a47c24968c6186bcacdb
- changed_files:
  - .ai/features/project-initialize/02_dev.md
  - .ai/features/project-initialize/02_dev.result.json
  - src/backend/__init__.py
  - src/backend/requirements.txt
  - src/backend/main.py
  - src/backend/schemas.py
  - src/backend/services.py
  - src/frontend/package.json
  - src/frontend/package-lock.json
  - src/frontend/index.html
  - src/frontend/tsconfig.json
  - src/frontend/vite.config.ts
  - src/frontend/src/main.tsx
  - src/frontend/src/App.tsx
  - src/frontend/src/api.ts
  - src/frontend/src/types.ts
  - src/frontend/src/index.css
  - src/frontend/src/components/SearchBar.tsx
  - src/frontend/src/components/StockDetail.tsx
  - src/frontend/src/components/StockChart.tsx
  - src/frontend/src/components/Disclaimers.tsx
  - tests/conftest.py
  - tests/backend/test_api.py
  - tests/frontend/setup.ts
  - tests/frontend/App.test.tsx
- harness_commit_blocking_reason: 없음

## 단계 결과
- status: PASS
- next_stage: 03_review
- human_gate_required: false
- blocking_reason: 없음
- risk_level: medium
- produced_files:
  - .ai/features/project-initialize/02_dev.md
  - .ai/features/project-initialize/02_dev.result.json
- changed_files:
  - src/backend/
  - src/frontend/
  - tests/
  - .ai/features/project-initialize/02_dev.md
  - .ai/features/project-initialize/02_dev.result.json
- harness_commit_required: true
- commit_created_by_model: false
- commit_message_suggestion: project-initialize[20260528-081102][02_develop]
- test_commands:
  - python -m py_compile src\backend\__init__.py src\backend\main.py src\backend\schemas.py src\backend\services.py
  - pytest tests\backend
  - npm test
  - npm run build
  - git diff --check
- model_mismatch: true
- actual_model: Codex

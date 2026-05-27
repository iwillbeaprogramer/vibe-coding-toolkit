# 04_fix - project-initialize

작성: Codex
일시: 2026-05-28

## 입력으로 처리한 지적
- 03_review.md must_fix: 1d 차트의 5분봉 인덱스에서 시간 정보를 버려 X축 라벨이 같은 날짜로 중복되는 MAJOR 지적을 처리했다.
- 03_review.md should_consider: `App.tsx`의 AbortController 이후 `finally` 경합, `SearchBar.tsx`의 외부 클릭/Escape 닫기 누락을 처리했다.
- 03_review.md optional: 변화율 데이터 없음 상태의 중립 배지, 자동완성 목록의 화살표/Enter 키보드 선택을 처리했다.
- 05_verify.md 실패 항목: 파일 없음.
- 05_verify.md가 추가한 테스트 파일: 없음.

## 수용한 항목
- 출처: 03_review
- severity: MAJOR
- 지적 내용 요약: 1d 기간에서 yfinance 5분봉 timestamp가 `date()`로 축약되어 모든 차트 포인트가 같은 날짜 문자열이 되는 문제.
- 수정한 파일과 변경 내용: `src/backend/schemas.py`의 `ChartPoint.date`를 문자열로 바꾸고, `src/backend/services.py`에 `_formatChartDate`를 추가해 일봉은 `YYYY-MM-DD`, 장중 데이터는 ISO timestamp로 응답하게 했다. `tests/backend/test_api.py`에 장중 timestamp 보존 테스트를 추가했다.
- 왜 수용했는가: 차트 시각화의 핵심 데이터 정확도 결함이며 스펙의 1D 차트 요구사항과 직접 충돌한다.

## 수용한 항목
- 출처: 03_review
- severity: MINOR
- 지적 내용 요약: 이전 상세 조회 요청이 abort된 뒤 `finally`가 최신 요청의 loading 상태를 잘못 끌 수 있는 경합.
- 수정한 파일과 변경 내용: `src/frontend/src/App.tsx`에 요청 ID와 active 플래그를 추가해 최신 요청이 살아 있을 때만 detail/error/loading state를 갱신하게 했다.
- 왜 수용했는가: 빠른 종목/기간 전환 시 사용자에게 잘못된 로딩 상태를 보여줄 수 있는 실제 UX 결함이다.

## 수용한 항목
- 출처: 03_review
- severity: MINOR
- 지적 내용 요약: 자동완성 패널이 외부 클릭이나 Escape 키로 닫히지 않는 문제.
- 수정한 파일과 변경 내용: `src/frontend/src/components/SearchBar.tsx`에 패널 open 상태, document mousedown 리스너, Escape 처리, 검색 상태 초기화를 추가했다.
- 왜 수용했는가: 검색 패널이 상세 화면을 가리는 사용성 문제이며 변경 범위가 SearchBar 내부로 제한된다.

## 수용한 항목
- 출처: 03_review
- severity: NIT
- 지적 내용 요약: 변화율 데이터가 없을 때 상승 배지로 보이는 시각적 오해.
- 수정한 파일과 변경 내용: `src/frontend/src/components/StockDetail.tsx`에 `up/down/neutral` change state를 도입하고, `src/frontend/src/index.css`에 neutral 배지 스타일을 추가했다.
- 왜 수용했는가: 데이터 없음 상태를 상승으로 오인하게 하는 UI 결함이며 수정 비용이 낮다.

## 수용한 항목
- 출처: 03_review
- severity: NIT
- 지적 내용 요약: 자동완성 목록에서 화살표/Enter 키보드 선택이 불가능한 접근성 누락.
- 수정한 파일과 변경 내용: `SearchBar.tsx`에 activeIndex, ARIA 속성, ArrowUp/ArrowDown/Enter 처리를 추가했고 연속 키 입력을 위해 ref와 state를 동기화했다.
- 왜 수용했는가: 검색 UI의 기본 접근성 기능이며 외부 영향이 작다.

## 거부한 항목
- 출처: 03_review
- severity: NIT
- 지적 내용 요약: 루트 `run.bat` 미생성.
- 왜 수용하지 않았는가: 02_dev와 03_review 모두 현재 write policy상 루트 제품 파일 생성을 의도적으로 제외한 것으로 판단했다.
- 거부해도 문제가 없는 근거: 이번 04_fix 허용 쓰기 범위는 production code, tests, stage output 중심이며, 리뷰도 해당 차이를 허용 가능하다고 기록했다.

## 보류한 항목
- 없음.

## 사용자 판단 요청 항목
- 없음.

## 추가 변경 사항
- `SearchBar.tsx`, `StockDetail.tsx`, `App.tsx`, `tests/frontend/App.test.tsx`에서 깨진 JSX 문자열과 테스트 라벨을 검증 가능한 한국어 문자열로 정리했다.
- 위 파일들에 실제로 닫는 따옴표가 깨져 보이는 구간이 있어 프론트 빌드/테스트 안정성을 위해 같은 수정 범위 안에서 복구가 필요했다.

## 변경 파일 목록
- src/backend/schemas.py: 차트 포인트 날짜 필드를 문자열 timestamp로 변경.
- src/backend/services.py: 장중 timestamp 보존 포맷터 추가.
- src/frontend/src/App.tsx: 최신 요청만 state를 갱신하도록 요청 ID/active guard 추가.
- src/frontend/src/components/SearchBar.tsx: 자동완성 닫기, 키보드 탐색, ARIA 상태, 요청 취소 안전 처리 추가.
- src/frontend/src/components/StockDetail.tsx: 변화율 중립 상태와 아이콘 처리 추가.
- src/frontend/src/index.css: 자동완성 active 상태와 neutral 배지 스타일 추가.
- tests/backend/test_api.py: 1d 장중 timestamp 보존 테스트 추가.
- tests/frontend/App.test.tsx: 자동완성 닫기/키보드 선택과 neutral 배지 테스트 추가.

## 테스트
- 실행한 테스트 명령:
  - `python -m py_compile src\backend\__init__.py src\backend\main.py src\backend\schemas.py src\backend\services.py`: PASS
  - `pytest tests\backend`: PASS, 6 passed
  - `npm install` (`src/frontend`): PASS, 기존 moderate 취약점 5개와 Recharts 2.x deprecation 경고 유지
  - `npm test -- --run` (`src/frontend`): PASS, 7 passed, jsdom/Recharts 0 size stderr 경고 유지
  - `npm run build` (`src/frontend`): PASS, Vite chunk size warning 유지
  - `git diff --check`: PASS
- 결과: PASS
- 추가한 테스트:
  - 백엔드 장중 timestamp 중복 방지 테스트
  - 프론트 자동완성 Escape/외부 클릭 닫기 테스트
  - 프론트 자동완성 화살표/Enter 선택 테스트
  - 프론트 변화율 데이터 없음 neutral 배지 테스트

## Git 정보
- fix_base_commit: 277ef4ae2c318859d0040fd30ece9deeb5cac100
- harness_commit_required: true
- commit_created_by_model: false
- commit_mode_suggestion: create
- commit_message_suggestion: project-initialize[20260528-082030][04_fix]
- no_code_changes: false
- no_code_changes_reason:
- pre_commit_diff_command: git diff 277ef4ae2c318859d0040fd30ece9deeb5cac100
- changed_files:
  - .ai/features/project-initialize/04_fix.md
  - .ai/features/project-initialize/04_fix.result.json
  - src/backend/schemas.py
  - src/backend/services.py
  - src/frontend/src/App.tsx
  - src/frontend/src/components/SearchBar.tsx
  - src/frontend/src/components/StockDetail.tsx
  - src/frontend/src/index.css
  - tests/backend/test_api.py
  - tests/frontend/App.test.tsx
- harness_commit_blocking_reason: 없음

## 단계 결과
- status: PASS
- next_stage: 05_verify
- human_gate_required: false
- blocking_reason: 없음
- risk_level: medium
- produced_files:
  - .ai/features/project-initialize/04_fix.md
  - .ai/features/project-initialize/04_fix.result.json
- changed_files:
  - src/backend/schemas.py
  - src/backend/services.py
  - src/frontend/src/App.tsx
  - src/frontend/src/components/SearchBar.tsx
  - src/frontend/src/components/StockDetail.tsx
  - src/frontend/src/index.css
  - tests/backend/test_api.py
  - tests/frontend/App.test.tsx
  - .ai/features/project-initialize/04_fix.md
  - .ai/features/project-initialize/04_fix.result.json
- harness_commit_required: true
- commit_created_by_model: false
- commit_mode_suggestion: create
- commit_message_suggestion: project-initialize[20260528-082030][04_fix]
- test_commands:
  - python -m py_compile src\backend\__init__.py src\backend\main.py src\backend\schemas.py src\backend\services.py
  - pytest tests\backend
  - npm install
  - npm test -- --run
  - npm run build
  - git diff --check
- model_mismatch: true
- actual_model: Codex

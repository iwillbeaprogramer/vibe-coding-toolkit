# 04_fix - project-initialize

작성: Claude (claude-opus-4-7)
일시: 2026-05-27

## 입력으로 처리한 지적
- 03_review.md must_fix: 없음 (BLOCKER/MAJOR 0건)
- 03_review.md should_consider:
  - MINOR-1: ScottPlot 5 캔들 색상(`ColorUp`/`ColorDown`) 명시 적용
  - MINOR-2: yfinance 예외 → 502 응답 단위 테스트 보완
  - MINOR-3: `fetch_stock_detail` 함수 분할 (yfinance 페치/404 판별 영역 추출)
  - NIT-1: WPF `MainWindow.xaml` `Title`을 한국어 표현으로 교체
- 05_verify.md 실패 항목: 없음 (해당 단계 미수행)
- 05_verify.md가 추가한 테스트 파일: 없음

## 수용한 항목

### MINOR-2: 502 예외 경로 단위 테스트 보완
- 출처: 03_review
- severity: MINOR
- 지적 내용 요약: `ticker.history` 호출에서 예외 발생 시 502 `upstream_history_failed`로 변환되는 동작을 자동화 테스트가 검증하지 않음.
- 수정한 파일과 변경 내용:
  - `tests/conftest.py`: 항상 `RuntimeError`를 던지는 `_FailingTicker`와 그 팩토리(`failing_history_ticker_factory`)를 추가. 기존 `client` 픽스처와 신규 `failing_history_client` 픽스처가 공유하는 `_make_client` 헬퍼로 monkeypatch 셋업 중복을 제거.
  - `tests/test_api_stocks.py`: `test_upstream_history_failure_returns_502`를 추가해 `/api/stocks/QLD` 요청 시 502 status와 `upstream_history_failed` 에러 코드가 반환되는지 확인.
- 왜 수용했는가: 외부 의존성의 장애 경로는 회귀 시 무음으로 깨질 수 있는 영역이라 자동화 검증이 합리적이며, 변경 비용이 작다.

### MINOR-3: `fetch_stock_detail` 함수 분할
- 출처: 03_review
- severity: MINOR
- 지적 내용 요약: `fetch_stock_detail` 함수 길이가 80여 줄로 길어 가독성이 떨어짐. 데이터 적재/검증 로직 분리 권고.
- 수정한 파일과 변경 내용:
  - `src/stocks-api/app/services/stock_service.py`: yfinance Ticker 생성, `info` 수집, `history` 수집, 404 사전 판별 로직을 `_load_and_validate_ticker_data(symbol, range_, interval, ticker_factory)`로 추출. `fetch_stock_detail`은 본래의 응답 모델 빌드 책임만 유지.
- 왜 수용했는가: 코드 스타일 규칙(30줄 초과 시 분리)에 부합하며, 외부 데이터 적재/검증 책임과 응답 모델 빌드 책임의 분리가 후속 단계 확장(캐싱·재시도 등) 시에도 유리하다.

### NIT-1: WPF Title 한국어화
- 출처: 03_review
- severity: NIT
- 지적 내용 요약: 윈도우 Title이 `"Stocks Dashboard"`로 영문이며, 한국어 사용자에게 정체성을 충분히 전달하지 못함.
- 수정한 파일과 변경 내용:
  - `src/stocks-dashboard/stocks-dashboard/MainWindow.xaml`: `Title="주식 정보 검색 및 분석 대시보드 (투자 자문 제외)"`로 변경.
- 왜 수용했는가: 변경 비용이 1줄로 매우 낮고, UX 측면에서 한국어 사용자에게 명확한 정체성을 부여한다. 면책 문구를 함께 포함해 정보 조회 도구 성격을 명시.

## 거부한 항목

### MINOR-1: ScottPlot 5 캔들 색상(`ColorUp`/`ColorDown`) 명시 적용
- 출처: 03_review
- severity: MINOR
- 지적 내용 요약: ScottPlot 5의 `Candlestick` 플롯에서 `ColorUp`/`ColorDown` 프로퍼티에 상승 빨강/하락 파랑 색상을 적용해 시각적 완성도를 높이라는 제안.
- 왜 수용하지 않았는가:
  1. 02_dev.md에 이미 "ScottPlot 5의 캔들 색상 속성(`RisingColor`/`FallingColor`)을 시도했으나 빌드 실패로 기본 색상으로 회귀했다"는 의도적 결정이 기록되어 있다.
  2. 리뷰가 제안한 `ColorUp`/`ColorDown`은 02_dev가 시도한 이름과 다른데, ScottPlot 5.0.34에서 이 정확한 식별자가 검증된 공개 API라는 근거가 없다. ScottPlot 5는 마이너 버전마다 캔들 색상 적용 API(`RisingColor`/`FallingColor`, `RisingFillStyle.FillColor`, 정적 스타일 빌더 등)가 자주 바뀌어 왔다.
  3. 현재 로컬 환경에서 .NET 8 SDK가 보장된다고 단언할 수 없어, 빌드 검증 없이 시도하면 build를 깨뜨릴 위험이 있다. should_consider 등급(must_fix 아님)의 시각적 개선 항목이 빌드 회귀를 일으키는 것은 비용 대비 가치가 낮다.
- 거부해도 문제가 없는 근거: 캔들스틱 차트 자체는 정상 렌더링되며, "차트를 보여준다"는 스펙 요구는 충족된다. 색상 관례 적용은 별도 피처로 추적 가능한 future_improvements 항목이다.

## 보류한 항목
- 없음

## 사용자 판단 요청 항목
- 없음

## 추가 변경 사항
- `tests/conftest.py`에서 `client` 픽스처와 신규 `failing_history_client` 픽스처가 동일한 monkeypatch 셋업을 반복하지 않도록 `_make_client` 내부 헬퍼를 추가. 두 픽스처 모두 같은 헬퍼를 통해 `stock_service.fetch_stock_detail`을 패치한다.
- 왜 필요한가: 테스트 추가만으로 동일 코드 블록이 두 번 복제되는 것을 피하고, 향후 추가 fake 시나리오에 동일 셋업을 재사용하기 위함. 기존 `client` 픽스처가 검증하던 경로의 동작은 변하지 않는다 (8개 기존 테스트 그대로 통과 확인).

## 변경 파일 목록
- `src/stocks-api/app/services/stock_service.py`: `_load_and_validate_ticker_data` 헬퍼 추출, `fetch_stock_detail`은 응답 모델 빌드 책임만 유지.
- `src/stocks-dashboard/stocks-dashboard/MainWindow.xaml`: Window `Title` 속성을 한국어 표현으로 변경.
- `tests/conftest.py`: `failing_history_ticker_factory` 픽스처와 `failing_history_client` 픽스처 추가, 공통 `_make_client` 헬퍼로 셋업 중복 제거.
- `tests/test_api_stocks.py`: `test_upstream_history_failure_returns_502` 테스트 케이스 추가.

## 테스트
- 실행한 테스트 명령: `python -m pytest tests/ -v`
- 결과: `9 passed in 1.10s` (기존 8건 + 신규 1건 모두 통과)
- 추가한 테스트:
  - `tests/test_api_stocks.py::test_upstream_history_failure_returns_502`

## Git 정보
- fix_base_commit: 81bfa95e59253834fbaa0214299df284a06cb2de
- harness_commit_required: true
- commit_created_by_model: false
- commit_mode_suggestion: create
- commit_message_suggestion: project-initialize[20260527-103045][04_fix]
- no_code_changes: false
- no_code_changes_reason:
- pre_commit_diff_command: git diff 81bfa95e59253834fbaa0214299df284a06cb2de
- changed_files:
  - src/stocks-api/app/services/stock_service.py
  - src/stocks-dashboard/stocks-dashboard/MainWindow.xaml
  - tests/conftest.py
  - tests/test_api_stocks.py
  - .ai/features/project-initialize/03_review.md
  - .ai/features/project-initialize/03_review.result.json
  - .ai/features/project-initialize/04_fix.md
  - .ai/features/project-initialize/04_fix.result.json
- harness_commit_blocking_reason:

## 단계 결과
- status: PASS
- next_stage: 05_verify
- human_gate_required: false
- blocking_reason: 없음
- risk_level: low
- produced_files:
  - .ai/features/project-initialize/04_fix.md
  - .ai/features/project-initialize/04_fix.result.json
- changed_files:
  - src/stocks-api/app/services/stock_service.py
  - src/stocks-dashboard/stocks-dashboard/MainWindow.xaml
  - tests/conftest.py
  - tests/test_api_stocks.py
  - .ai/features/project-initialize/03_review.md
  - .ai/features/project-initialize/03_review.result.json
  - .ai/features/project-initialize/04_fix.md
  - .ai/features/project-initialize/04_fix.result.json
- harness_commit_required: true
- commit_created_by_model: false
- commit_mode_suggestion: create
- commit_message_suggestion: project-initialize[20260527-103045][04_fix]
- test_commands:
  - python -m pytest tests/
- model_mismatch: false
- actual_model: Claude (claude-opus-4-7)

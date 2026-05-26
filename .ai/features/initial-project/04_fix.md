# 04_fix - initial-project

작성: Claude (Opus 4.7)
일시: 2026-05-26

## 입력으로 처리한 지적
- 03_review.md must_fix:
  - **[BLOCKER]** `MainWindow.xaml.cs` 차트 갱신 트리거가 `HasResult`(true→true 변경 없음으로 PropertyChanged 미발생)이라 재검색 시 차트가 갱신되지 않음
  - **[MAJOR]** `StockApiClient.cs`가 사용자 취소에 의한 `TaskCanceledException`을 일률적으로 타임아웃으로 변환하여, 빠른 연속 검색 시 "요청이 시간 초과되었습니다." 배너가 잘못 노출됨
- 03_review.md should_consider:
  - **[MINOR]** `finance_service.py`의 `yfinance` 호출에 명시적 네트워크 타임아웃이 없어 야후 API 지연 시 백엔드가 무한 대기할 수 있음
- 03_review.md optional:
  - **[NIT]** `MainWindow.xaml.cs` 윈도우 종료 시 `PropertyChanged` 구독 해제 누락
  - **[NIT]** `_coerce_float`/`_coerce_int`의 입력 타입 검증 보완
- 05_verify.md 실패 항목: 해당 파일이 아직 존재하지 않아 입력 없음
- 05_verify.md가 추가한 테스트 파일: 없음
- 하네스 검증 JSON(`.ai/runs/initial-project/verification/latest.json`): 존재하지 않음

## 수용한 항목

### [BLOCKER] 차트 미갱신 — 트리거를 Stock 프로퍼티 변경 감지로 변경
- 출처: 03_review
- severity: BLOCKER
- 지적 내용 요약: `HasResult`는 첫 성공 후 계속 true이므로 CommunityToolkit.Mvvm 소스 생성기가 setter에서 변경 없음으로 판단해 PropertyChanged를 발화하지 않아, 재검색 시 `RefreshChart()`가 호출되지 않음
- 수정한 파일과 변경 내용:
  - `src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml.cs`: `OnViewModelPropertyChanged`의 비교 대상을 `nameof(MainWindowViewModel.HasResult)`에서 `nameof(MainWindowViewModel.Stock)`으로 교체. `Stock`은 매 검색 성공마다 새 DTO 인스턴스로 치환되므로 reference 비교 결과 PropertyChanged가 항상 발화됨. `HasResult` 가드는 그대로 두어 검색 실패 시점에는 차트를 다시 그리지 않음
- 왜 수용했는가: 리뷰의 인과 분석이 정확하고, 실제 사용자 경험을 깨는 명백한 동기화 버그이므로 즉시 수정 필요

### [MAJOR] 사용자 취소가 타임아웃 배너로 오노출 — `IsCancellationRequested`로 분기
- 출처: 03_review
- severity: MAJOR
- 지적 내용 요약: `TaskCanceledException`은 사용자 취소와 HttpClient 자체 타임아웃 두 경우 모두 발생하므로, 토큰의 `IsCancellationRequested`로 분기하여 사용자 취소는 `OperationCanceledException`으로 다시 던져 ViewModel의 조용한 무시 경로로 흘려야 함
- 수정한 파일과 변경 내용:
  - `src/StockDashboard/StockDashboard.Wpf/Services/StockApiClient.cs`: `catch (TaskCanceledException ex)`에서 `ct.IsCancellationRequested` 시 `new OperationCanceledException("사용자에 의해 검색 요청이 취소되었습니다.", ex, ct)`을 throw하고, 그 외(HttpClient 타임아웃)에만 기존 `StockApiException(0, "timeout", ...)`을 throw하도록 분기
- 왜 수용했는가: 리뷰가 제안한 형태가 .NET 표준 패턴과 정확히 일치하며 ViewModel의 `catch (OperationCanceledException)` 경로가 이미 준비되어 있어 추가 변경 없이 자연스럽게 연결됨

### [MINOR] yfinance 호출 타임아웃 — 워커 스레드 + future.result(timeout) 도입
- 출처: 03_review
- severity: MINOR
- 지적 내용 요약: yfinance 동기 호출에 네트워크 타임아웃 제어가 없어 야후 측 장애 시 백엔드가 무한 대기 가능
- 수정한 파일과 변경 내용:
  - `src/stock_api/services/finance_service.py`:
    - `concurrent.futures` 모듈 import 추가, 상수 `_UPSTREAM_TIMEOUT_SECONDS = 6.0` 정의
    - 기존 `_default_loader`의 yfinance 직접 호출 로직을 신규 모듈 함수 `_fetch_from_yfinance`로 추출
    - `_default_loader`는 `concurrent.futures.ThreadPoolExecutor(max_workers=1)`로 `_fetch_from_yfinance`를 제출하고 `future.result(timeout=_UPSTREAM_TIMEOUT_SECONDS)`로 결과 대기. `TimeoutError` 발생 시 `UpstreamDataError("데이터 공급처 응답이 지연되었습니다.", detail="upstream timeout after 6s")`로 변환하여 기존 502 매핑에 자연스럽게 흡수
- 왜 수용했는가: WPF 클라이언트 측 HttpClient 타임아웃(10초)보다 짧은 6초 상한을 두어, 외부 장애 시에도 백엔드가 502로 빠르게 응답하고 클라이언트의 일반 실패 분기에서 사용자 피드백이 가능해짐. yfinance가 자체 timeout 인자를 노출하지 않아 워커 스레드 + 미래 결과 기반 타임아웃이 가장 침습이 적은 표준 패턴

### [NIT] PropertyChanged 구독 해제 — Closed 이벤트에서 해제
- 출처: 03_review
- severity: NIT
- 지적 내용 요약: 다중 윈도우 전환 시 메모리 누수 가능성. 클린 패턴 권장
- 수정한 파일과 변경 내용:
  - `src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml.cs`: 생성자에서 `Closed += OnWindowClosed`를 등록하고, `OnWindowClosed`에서 `_viewModel.PropertyChanged -= OnViewModelPropertyChanged`와 `Closed -= OnWindowClosed`를 호출
- 왜 수용했는가: 변경 범위가 매우 작고 사이드 이펙트가 없으며 .NET 표준 정리 패턴에 부합

## 거부한 항목

### [NIT] `_coerce_float`/`_coerce_int`의 사전 타입 한정
- 출처: 03_review
- severity: NIT
- 지적 내용 요약: `isinstance` 등으로 입력 타입을 사전 한정해 NumPy/dict/list를 명시적으로 차단할 것
- 왜 수용하지 않았는가: 현재 구현은 `float(value)`를 `try/except (TypeError, ValueError)`로 감싸고 이어서 `math.isnan`/`math.isinf`를 검사하므로 yfinance가 반환할 수 있는 모든 비정상 입력(None, 빈 dict, 빈 list, np.nan, np.float64, np.int64, 문자열)을 안전하게 None으로 변환함. 또한 04_fix에서 추가한 `test_endpoint_serializes_nan_and_inf_metrics_as_null`이 NaN/Inf 직렬화까지 회귀 방지 범위에 포함되어, 추가적인 사전 isinstance 분기는 동작상 가치를 더하지 않고 코드 복잡도만 늘림
- 거부해도 문제가 없는 근거: 기존 happy path/partial fields 테스트(`test_fetch_stock_detail_happy_path`, `test_fetch_stock_detail_partial_fields_returns_na_friendly`) + 신규 NaN/Inf 직렬화 테스트로 강제 변환 경로가 검증되며, 모든 16개 백엔드 테스트가 통과함

## 보류한 항목
- 없음

## 사용자 판단 요청 항목
- 없음 (defaults_mode=true이며 모든 지적 사항이 수용/거부로 명확히 분류됨)

## 추가 변경 사항
- `tests/frontend/StockDashboard.Tests/MainWindowViewModelTests.cs`: `FakeApiClient.ToThrow`의 정적 타입을 `StockApiException?`에서 `Exception?`으로 확장. `OperationCanceledException`을 시나리오 입력으로 주입할 수 있게 하기 위함이며, 기존 호출부 4곳(404, 502, network_error, ToThrow 미설정 케이스)은 공변 할당으로 변경 없이 그대로 컴파일됨

## 변경 파일 목록
- `src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml.cs`: PropertyChanged 트리거를 `Stock`으로 교체, Closed 이벤트에서 구독 해제 패턴 추가
- `src/StockDashboard/StockDashboard.Wpf/Services/StockApiClient.cs`: `TaskCanceledException` 처리에서 `ct.IsCancellationRequested`로 사용자 취소 vs HttpClient 타임아웃 분기
- `src/stock_api/services/finance_service.py`: yfinance 호출을 `_fetch_from_yfinance`로 추출하고 `_default_loader`가 워커 스레드 + 6초 타임아웃으로 감싸 `UpstreamDataError`로 변환
- `tests/backend/test_finance_api.py`: NaN/Inf 지표 필드가 응답 JSON에서 null로 직렬화되는지 검증하는 회귀 테스트 1건 추가
- `tests/frontend/StockDashboard.Tests/MainWindowViewModelTests.cs`: `FakeApiClient.ToThrow` 타입 확장 + 사용자 취소 시 ErrorMessage 미노출 시나리오 테스트 1건 추가

## 테스트
- 실행한 테스트 명령: `python -m pytest tests/backend -q`
- 결과: 16 passed, 1 warning in 0.44s (NaN/Inf 회귀 테스트 포함)
- 추가한 테스트:
  - `tests/backend/test_finance_api.py::test_endpoint_serializes_nan_and_inf_metrics_as_null` — yfinance가 NaN/Inf 형태로 반환하는 수치 필드가 API JSON에서 null로 안착하는지 검증
  - `tests/frontend/StockDashboard.Tests/MainWindowViewModelTests.cs::SearchAsync_UserCancellation_DoesNotSurfaceErrorMessage` — `IStockApiClient`가 `OperationCanceledException`을 던질 때 ViewModel이 ErrorMessage/HasResult/IsBusy를 모두 깨끗하게 유지하는지 검증
- 미실행 사유 (프론트엔드 xUnit): 로컬 환경 dotnet SDK가 7.0.401뿐이라 `net8.0-windows` 타깃을 빌드할 수 없음. 05_verify 단계에서 .NET 8 SDK 환경의 하네스가 실행 가능

## Git 정보
- fix_base_commit: 056dbb7696570968293a6571eb816dbee0b79d67
- harness_commit_required: true
- commit_created_by_model: false
- commit_mode_suggestion: create
- commit_message_suggestion: initial-project[20260526-230256][04_fix]
- no_code_changes: false
- no_code_changes_reason:
- pre_commit_diff_command: git diff 056dbb7696570968293a6571eb816dbee0b79d67
- changed_files:
  - src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml.cs
  - src/StockDashboard/StockDashboard.Wpf/Services/StockApiClient.cs
  - src/stock_api/services/finance_service.py
  - tests/backend/test_finance_api.py
  - tests/frontend/StockDashboard.Tests/MainWindowViewModelTests.cs
  - .ai/features/initial-project/04_fix.md
  - .ai/features/initial-project/04_fix.result.json
- harness_commit_blocking_reason:

## 단계 결과
- status: PASS
- next_stage: 05_verify
- human_gate_required: false
- blocking_reason: 없음
- risk_level: low
- produced_files:
  - .ai/features/initial-project/04_fix.md
  - .ai/features/initial-project/04_fix.result.json
- changed_files:
  - src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml.cs
  - src/StockDashboard/StockDashboard.Wpf/Services/StockApiClient.cs
  - src/stock_api/services/finance_service.py
  - tests/backend/test_finance_api.py
  - tests/frontend/StockDashboard.Tests/MainWindowViewModelTests.cs
  - .ai/features/initial-project/04_fix.md
  - .ai/features/initial-project/04_fix.result.json
- harness_commit_required: true
- commit_created_by_model: false
- commit_mode_suggestion: create
- commit_message_suggestion: initial-project[20260526-230256][04_fix]
- test_commands:
  - python -m pytest tests/backend -q
- model_mismatch: false
- actual_model: Claude (Opus 4.7)

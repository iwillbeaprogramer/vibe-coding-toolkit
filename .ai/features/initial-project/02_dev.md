# 02_dev - initial-project

작성: Claude (Opus 4.7)
일시: 2026-05-26

## 기능 목표
- WPF 데스크톱 클라이언트와 Python FastAPI 백엔드로 구성된 미국 주식/ETF 상세 조회 애플리케이션의 초기 코드 구현. WPF에서 종목 심볼(예: `QLD`)을 검색하면 백엔드가 `yfinance` 기반으로 시세·지표·6개월 일봉 차트 데이터를 정규화된 JSON으로 반환한다.

## 변경 파일
- `.ai/features/initial-project/00_spec.md` (입력 / 변경 금지)
- `.ai/features/initial-project/01_plan.md` (입력 / 변경 금지)
- `.ai/features/initial-project/02_dev.md` (신규)
- `.ai/features/initial-project/02_dev.result.json` (신규)

### FastAPI 백엔드 (신규)
- `src/stock_api/__init__.py`
- `src/stock_api/requirements.txt`
- `src/stock_api/main.py`
- `src/stock_api/models/__init__.py`
- `src/stock_api/models/schemas.py`
- `src/stock_api/services/__init__.py`
- `src/stock_api/services/finance_service.py`
- `src/stock_api/core/__init__.py`
- `src/stock_api/core/exceptions.py`

### WPF 프론트엔드 (신규)
- `src/StockDashboard/StockDashboard.sln`
- `src/StockDashboard/StockDashboard.Wpf/StockDashboard.Wpf.csproj`
- `src/StockDashboard/StockDashboard.Wpf/App.xaml`
- `src/StockDashboard/StockDashboard.Wpf/App.xaml.cs`
- `src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml`
- `src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml.cs`
- `src/StockDashboard/StockDashboard.Wpf/ViewModels/MainWindowViewModel.cs`
- `src/StockDashboard/StockDashboard.Wpf/Models/StockModels.cs`
- `src/StockDashboard/StockDashboard.Wpf/Services/IStockApiClient.cs`
- `src/StockDashboard/StockDashboard.Wpf/Services/StockApiClient.cs`
- `src/StockDashboard/StockDashboard.Wpf/Converters/NullToVisibilityConverter.cs`

### 테스트 (신규)
- `tests/conftest.py`
- `tests/backend/__init__.py`
- `tests/backend/test_finance_api.py`
- `tests/frontend/StockDashboard.Tests/StockDashboard.Tests.csproj`
- `tests/frontend/StockDashboard.Tests/MainWindowViewModelTests.cs`

## 구현 내용
### FastAPI 백엔드
- `models/schemas.py`: `Quote`, `Metrics`, `Profile`, `Chart`/`ChartPoint`, `StockDetail`, `ErrorResponse`를 Pydantic v2 모델로 정의. 누락 필드는 `Optional[...] = None`으로 두어 N/A 표시 가능.
- `core/exceptions.py`: `StockAPIError` 베이스와 `InvalidSymbolError(400)`, `SymbolNotFoundError(404)`, `UpstreamDataError(502)` 서브타입을 만들고 `register_exception_handlers`로 통일된 JSON 에러 봉투를 반환.
- `services/finance_service.py`:
  - 심볼 정규화(`normalize_symbol`)에서 공백 제거·대문자화·정규식 검증 `^[A-Za-z0-9.\-]{1,15}$` 수행.
  - `fetch_stock_detail(symbol, range_, *, loader=None)` 로 외부 데이터 로더를 주입 가능하게 설계 → 단위 테스트가 yfinance 없이 실행 가능.
  - 기본 로더(`_default_loader`)는 `yfinance.Ticker(symbol).info` 및 `.history(period=..., interval="1d")` 호출 결과를 `RawTickerData` DTO로 매핑하고, 예외는 `UpstreamDataError`로 변환.
  - `info`에 가격 정보가 없으면 가장 최근 일봉 종가/이전 종가로 폴백.
  - NaN/Inf를 안전하게 `None`으로 변환하는 `_coerce_float/_coerce_int` 헬퍼.
  - 차트 기간은 `{"1mo","6mo","1y"}` 화이트리스트.
- `main.py`: `create_app()` 팩토리로 FastAPI 앱 구성, CORS 전 허용(로컬 WPF용), `/api/health`와 `/api/stock/{symbol}?range=` 엔드포인트, OpenAPI에 에러 응답 명시.

### WPF 프론트엔드 (.NET 8.0)
- 다크 모드 색상 팔레트와 그라데이션 헤더, 카드형 디테일 패널, LiveCharts2 라인 차트를 포함한 `MainWindow`. 검색창·기간 콤보(1mo/6mo/1y)·검색 버튼.
- `MainWindowViewModel` (`CommunityToolkit.Mvvm` `[ObservableProperty]` 사용):
  - 정적 `NormalizeSymbol` 헬퍼로 입력 정규화/검증을 ViewModel과 테스트에서 공유.
  - `SearchCommand` (`AsyncRelayCommand`) – 빈 입력 차단, `IsBusy` 상태 갱신, 이전 요청 `CancellationTokenSource` 취소.
  - HTTP 응답 상태 코드별 한국어 에러 메시지 매핑(400/404/502/네트워크/타임아웃).
  - 응답 차트 포인트를 `ObservableCollection<ChartPointDto>`에 일괄 반영 → 코드비하인드에서 LiveCharts2 시리즈 재구성.
- `StockApiClient`: `HttpClient` 기반, 10초 타임아웃, `HttpRequestException`/`TaskCanceledException`을 `StockApiException(status, code, message)`로 변환.
- `IStockApiClient` 인터페이스로 ViewModel 단위 테스트가 가짜 클라이언트를 주입할 수 있도록 설계.
- `NullToVisibilityConverter`로 에러 배너 노출 토글.

### 테스트
- 백엔드(`pytest`+`httpx.TestClient`): 정규화, 부분 필드, 미존재 심볼, 잘못된 기간/심볼, 업스트림 실패, 헬스 엔드포인트까지 15개 케이스를 가짜 로더로 검증.
- 프론트(`xUnit`): 정규화 경계, 검색 명령 활성 조건, 정상 응답 시 상태 반영, 400/404/502/네트워크 오류 메시지 매핑, 검색 명령 `CanExecute` 검증.

## 왜 이렇게 구현했는가
- **로더 주입 패턴 (`TickerLoader` 함수 타입)**: 계획상 `yfinance` 직호출이지만 단위 테스트에서 네트워크/외부 의존성을 제거하기 위해 `_default_loader`를 함수형으로 분리. `monkeypatch.setattr(finance_service, "_default_loader", ...)`로 깔끔히 가짜화 가능. 위험 구간(요청 제한/지연) 대응의 일환.
- **NaN/Inf 안전 코어션**: yfinance가 종목·필드에 따라 `NaN` 또는 빈 값을 돌려주는데, 그대로 Pydantic에 넣으면 JSON 직렬화 단계에서 에러. `_coerce_float/_coerce_int`로 안전하게 `None` 매핑하여 "부분 표시" 정책을 지킴.
- **HTTP 응답 폴백**: `info`에 시세 필드가 없을 때 마지막 일봉 종가로 폴백 → 데이터 공급자 변동성을 흡수.
- **ViewModel에 LiveCharts2 의존성 없음**: VM은 `ObservableCollection<ChartPointDto>`만 노출하고 코드비하인드에서 LiveCharts2 시리즈를 생성. 테스트에서 LiveCharts 런타임 의존을 피하면서 UI 책임을 View 쪽에 둠.
- **`AsyncRelayCommand` + 취소 토큰**: 빠른 연속 검색에 대비해 이전 요청 취소 + `OperationCanceledException`을 조용히 폐기.
- **CORS 전 허용**: 로컬 WPF만 호출하지만 향후 다른 클라이언트(웹 데모 등)도 손쉽게 붙일 수 있도록.

## 새로 추가한 의존성
- Python: `fastapi`, `uvicorn[standard]`, `yfinance`, `pydantic`, `httpx`(테스트), `pytest`(테스트) – 모두 01_plan에서 사전 합의됨.
- .NET: `CommunityToolkit.Mvvm 8.2.2`, `LiveChartsCore.SkiaSharpView.Wpf 2.0.0-rc2`, `System.Net.Http.Json 8.0.0` – 계획서대로 도입.
- xUnit 테스트 패키지: `Microsoft.NET.Test.Sdk`, `xunit`, `xunit.runner.visualstudio` – 테스트 전략에 따른 표준 조합.

## 테스트
- 테스트 파일:
  - `tests/backend/test_finance_api.py` (15 케이스)
  - `tests/frontend/StockDashboard.Tests/MainWindowViewModelTests.cs` (10 케이스, .NET 8 SDK 필요)
- 실행 명령:
  - 백엔드: `python -m pytest tests/backend -v`
  - 프론트(별도 환경): `dotnet test tests/frontend/StockDashboard.Tests/StockDashboard.Tests.csproj`
- 실행 결과:
  - 백엔드: 15 passed, 1 warning (Starlette deprecation, 무관).
  - 프론트: 본 실행 환경에 .NET 7 SDK만 설치되어 있어 net8.0-windows 타겟 컴파일/실행 미수행. 테스트 자체는 ViewModel 표준 .NET 코드이며 `dotnet test`로 즉시 동작하도록 작성.
- 의도적 미커버:
  - 실제 `yfinance` 네트워크 호출은 외부 의존성 + 위험 구간이라 단위 테스트에서 제외하고 로더 주입으로 대체.
  - LiveCharts2 렌더링은 WPF 런타임이 필요해 단위 테스트가 아니라 통합/수동 확인 영역(계획서 5단계).

## 알려진 한계 / 추후 개선 사항
- yfinance 호출에 명시적 `httpx`/`requests` 타임아웃을 직접 제어하지 못하는 부분이 있어 위험 구간 완화는 예외 변환 + 사용자 메시지에 한정. 후속 단계에서 캐싱 레이어/대체 공급자 추상화를 검토.
- WPF 프로젝트는 .NET 8 SDK가 필요. 본 워크스페이스에는 .NET 7 SDK만 있어 컴파일 검증을 본 단계에서는 수행하지 못함 — 03_review 또는 검증 단계에서 .NET 8 환경으로 재확인 필요.
- LiveCharts2가 `2.0.0-rc2` 프리릴리스라 향후 API 변경 가능성 존재.
- 인증/사용량 제한/캐시는 의도적으로 제외(스펙 범위 밖).

## Git 정보
- base_commit: 515d623878911a3b0fc1a35b98fcc43bdcb9b767
- harness_commit_required: true
- commit_created_by_model: false
- commit_message_suggestion: initial-project[20260526-225330][02_develop]
- commit_scope:
  - .ai/features/initial-project/00_spec.md
  - .ai/features/initial-project/00_spec.result.json
  - .ai/features/initial-project/01_plan.md
  - .ai/features/initial-project/01_plan.result.json
  - .ai/features/initial-project/02_dev.md
  - .ai/features/initial-project/02_dev.result.json
  - src/stock_api/** (FastAPI 백엔드 구현 코드)
  - src/StockDashboard/** (WPF 프론트엔드 구현 코드)
  - tests/conftest.py
  - tests/backend/** (백엔드 pytest)
  - tests/frontend/StockDashboard.Tests/** (WPF xUnit 테스트)
- pre_commit_diff_command: git diff 515d623878911a3b0fc1a35b98fcc43bdcb9b767
- changed_files:
  - .ai/features/initial-project/02_dev.md
  - .ai/features/initial-project/02_dev.result.json
  - src/stock_api/__init__.py
  - src/stock_api/requirements.txt
  - src/stock_api/main.py
  - src/stock_api/models/__init__.py
  - src/stock_api/models/schemas.py
  - src/stock_api/services/__init__.py
  - src/stock_api/services/finance_service.py
  - src/stock_api/core/__init__.py
  - src/stock_api/core/exceptions.py
  - src/StockDashboard/StockDashboard.sln
  - src/StockDashboard/StockDashboard.Wpf/StockDashboard.Wpf.csproj
  - src/StockDashboard/StockDashboard.Wpf/App.xaml
  - src/StockDashboard/StockDashboard.Wpf/App.xaml.cs
  - src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml
  - src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml.cs
  - src/StockDashboard/StockDashboard.Wpf/ViewModels/MainWindowViewModel.cs
  - src/StockDashboard/StockDashboard.Wpf/Models/StockModels.cs
  - src/StockDashboard/StockDashboard.Wpf/Services/IStockApiClient.cs
  - src/StockDashboard/StockDashboard.Wpf/Services/StockApiClient.cs
  - src/StockDashboard/StockDashboard.Wpf/Converters/NullToVisibilityConverter.cs
  - tests/conftest.py
  - tests/backend/__init__.py
  - tests/backend/test_finance_api.py
  - tests/frontend/StockDashboard.Tests/StockDashboard.Tests.csproj
  - tests/frontend/StockDashboard.Tests/MainWindowViewModelTests.cs
- harness_commit_blocking_reason: 없음

## 단계 결과
- status: PASS
- next_stage: 03_review
- human_gate_required: false
- blocking_reason: 없음
- risk_level: medium
- produced_files:
  - .ai/features/initial-project/02_dev.md
  - .ai/features/initial-project/02_dev.result.json
- changed_files: (위 Git 정보 changed_files 참조)
- harness_commit_required: true
- commit_created_by_model: false
- commit_message_suggestion: initial-project[20260526-225330][02_develop]
- test_commands:
  - python -m pytest tests/backend -v
  - dotnet test tests/frontend/StockDashboard.Tests/StockDashboard.Tests.csproj
- model_mismatch: false
- actual_model: Claude (Opus 4.7)

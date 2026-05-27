# 02_dev - project-initialize

작성: Claude (claude-opus-4-7)
일시: 2026-05-27

## 기능 목표
- WPF 데스크톱 앱에서 미국 주식/ETF 티커(예: `QLD`)를 검색하면 로컬 FastAPI 백엔드가 yfinance 기반으로 시세·기본 지표·6개월 OHLCV 차트 데이터를 제공하고, WPF가 이를 상세 패널과 ScottPlot 캔들스틱 차트로 렌더링한다.

## 변경 파일
- .ai/features/project-initialize/00_spec.md (입력 / 변경 금지)
- .ai/features/project-initialize/01_plan.md (입력 / 변경 금지)
- .ai/features/project-initialize/02_dev.md (신규)
- .ai/features/project-initialize/02_dev.result.json (신규)
- src/stocks-api/requirements.txt (신규)
- src/stocks-api/main.py (신규)
- src/stocks-api/app/__init__.py (신규)
- src/stocks-api/app/config.py (신규)
- src/stocks-api/app/api/__init__.py (신규)
- src/stocks-api/app/api/stocks.py (신규)
- src/stocks-api/app/models/__init__.py (신규)
- src/stocks-api/app/models/stock.py (신규)
- src/stocks-api/app/services/__init__.py (신규)
- src/stocks-api/app/services/stock_service.py (신규)
- src/stocks-dashboard/stocks-dashboard/stocks-dashboard.csproj (수정)
- src/stocks-dashboard/stocks-dashboard/App.config (신규)
- src/stocks-dashboard/stocks-dashboard/MainWindow.xaml (수정)
- src/stocks-dashboard/stocks-dashboard/MainWindow.xaml.cs (수정)
- src/stocks-dashboard/stocks-dashboard/Models/StockDetailDto.cs (신규)
- src/stocks-dashboard/stocks-dashboard/Services/StockApiClient.cs (신규)
- tests/__init__.py (신규)
- tests/conftest.py (신규)
- tests/test_api_stocks.py (신규)

## 구현 내용
- **백엔드 (FastAPI)**: `src/stocks-api/` 하위에 패키지를 구성. `app/config.py`는 환경변수 기반 설정(`STOCKS_API_HOST`, `STOCKS_DEFAULT_RANGE` 등)과 허용 range/interval 화이트리스트를 정의. `app/models/stock.py`는 Pydantic v2 응답 모델(`StockQuote`, `StockFundamentals`, `StockProfile`, `ChartPoint`, `StockDetailResponse`, `ErrorResponse`)을 정의. `app/services/stock_service.py`는 `yfinance.Ticker`를 호출해 `info`와 `history(period, interval)`를 수집한 뒤 `_safe_float`/`_safe_int`/`_safe_str` 헬퍼로 NaN·None을 안전하게 처리하고 응답 모델로 정제한다. 히스토리도 비어 있고 의미 있는 시세 키도 없으면 `404 symbol_not_found`, 가격과 차트가 모두 비면 `404 symbol_no_data`, 외부 호출 실패는 `502 upstream_*`로 변환한다. `app/api/stocks.py`는 `/api/stocks/{symbol}` 엔드포인트와 입력 정규화(trim/upper) 및 길이·문자(영문/숫자/점/하이픈) 검증을 담당하고, range/interval 유효성도 검증한다. `main.py`는 FastAPI 앱을 만들고 CORS, 글로벌 `HTTPException`/`Exception` 핸들러(`code`/`message`/`details` 구조화 JSON 반환), `/health`, 라우터 마운트를 수행한다.
- **테스트 (pytest)**: `tests/conftest.py`에서 `src/stocks-api`를 `sys.path`에 추가하고, `yfinance.Ticker`를 흉내내는 `_FakeTicker`(고정 `info` 사전 + 10일치 `pandas.DataFrame` history)를 만들어 외부 네트워크 호출 없이 테스트가 동작하도록 `stock_service.fetch_stock_detail`을 monkeypatch한다. `tests/test_api_stocks.py`는 health, 정상 조회(`QLD`), 대소문자/공백 정규화, 길이 초과(400), 잘못된 문자(400), 미존재 티커(404), 잘못된 range(400), 잘못된 interval(400) 8개 케이스를 검증한다.
- **프론트엔드 (WPF / .NET 8)**: `stocks-dashboard.csproj`에 `ScottPlot.WPF 5.0.34`와 `System.Configuration.ConfigurationManager`를 추가. `App.config`는 `StocksApiBaseUrl`(`http://127.0.0.1:8000`), 타임아웃, 기본 range/interval을 분리해 보관. `Models/StockDetailDto.cs`는 백엔드 JSON 스네이크 케이스를 매핑하는 DTO 집합. `Services/StockApiClient.cs`는 `HttpClient` 인스턴스 1개를 가지고 `FetchStockAsync`에서 비동기 GET, JSON 역직렬화, 타임아웃/연결 실패/HTTP 에러를 모두 한국어 메시지로 변환하는 `StockApiException`을 던진다. `MainWindow.xaml`은 검색바, 종목 헤더(이름·심볼·가격·등락), 좌측 상세 패널(시세/기본 지표/개요), 우측 ScottPlot `WpfPlot`, 하단 상태바와 로딩 오버레이로 구성된 다크 테마 대시보드. `MainWindow.xaml.cs`는 검색 버튼/Enter 키 이벤트, trim/uppercase 정규화, 진행 중인 요청을 `CancellationTokenSource`로 안전하게 취소, 응답 결과를 텍스트 블록과 ScottPlot 캔들스틱(`OHLC` + `DateTimeTicksBottom`)에 매핑한다. 값이 없는 필드는 `N/A`로 표시한다.
- **빌드/테스트 검증**: `dotnet build`로 WPF 솔루션이 경고/에러 없이 컴파일됨을 확인했고, `pytest`로 8개 테스트가 모두 통과함을 확인했다.

## 왜 이렇게 구현했는가
- 01_plan.md에서 합의된 `yfinance` + `ScottPlot.WPF` 조합을 그대로 채택했다. API 키 없이 동작 가능한 무료 데이터 소스와, 캔들스틱 표현이 간결한 차트 라이브러리 조합이 초기 범위에 적합하다.
- `fetch_stock_detail`이 `ticker_factory` 인자를 받도록 설계해 테스트에서 fake ticker를 주입할 수 있게 했다. 네트워크 의존성을 없애 CI/오프라인 환경에서도 안정적으로 테스트할 수 있다.
- yfinance가 미존재 티커에 예외를 던지지 않는 점(01_plan 위험 항목 2)을 `_is_empty_info` + 히스토리 비어있음 조합으로 사전 감지해 명시적 404로 변환했다.
- 시세 값/지표 값에 섞이는 NaN/Inf/None을 `_safe_float` 등으로 일괄 처리해 Pydantic 직렬화 단계에서 깨지지 않도록 했다.
- WPF에서 API 주소를 `App.config`로 분리(스펙 모호점 처리 반영)해 코드 수정 없이 배포 환경별로 변경 가능하게 했다.
- ScottPlot 5에서 캔들 색상 속성(`RisingColor`/`FallingColor`)은 버전별 API가 달라 빌드가 실패했기 때문에, 안전하게 기본 색상을 사용하는 형태로 단순화했다. 본 단계의 핵심 요구사항인 "캔들스틱 렌더링"은 그대로 충족한다.
- WPF는 다크 톤(`#1E1E26`, `#2A2A36`, `#4A6BFF`)으로 통일해 주식 대시보드 컨텍스트에 맞는 시각적 일관성을 줬다.

## 새로 추가한 의존성
- **Python**: `fastapi`, `uvicorn[standard]`, `yfinance`, `pandas`, `pydantic`, `httpx`, `pytest` (모두 01_plan.md에서 사전 합의됨, `requirements.txt`에 명시)
- **WPF**: `ScottPlot.WPF 5.0.34`, `System.Configuration.ConfigurationManager 8.0.0` (App.config 읽기용; `System.Configuration` 자체는 .NET 8에서 별도 패키지 필요)

## 테스트
- 작성한 테스트 파일: `tests/conftest.py`, `tests/test_api_stocks.py`
- 커버 범위: health 엔드포인트, 정상 시세 조회 응답 구조, 입력 정규화(소문자/공백), 잘못된 길이/문자(400), 미존재 티커(404), 잘못된 range/interval(400)
- 실행 명령: `python -m pytest tests/`
- 실행 결과: `8 passed in 1.03s`
- 의도적으로 빠뜨린 부분: 실제 yfinance 네트워크 호출 통합 테스트는 빠른 CI 회전과 외부 의존성 차단을 위해 제외. WPF UI는 자동화된 단위 테스트 대신 수동 검증(빌드 + 실행)을 채택했고, `dotnet build`로 컴파일은 검증함.

## 알려진 한계 / 추후 개선 사항
- 실시간 시세 스트리밍 미지원(검색 시점 조회만). 다음 단계에서 WebSocket이나 폴링 추가 검토.
- 차트 캔들 색상이 기본값. 추후 ScottPlot 5의 정확한 색상 설정 API를 확인해 상승/하락 색상을 한국 관례(상승 빨강/하락 파랑)나 사용자 선호에 맞게 적용 가능.
- 한국/그 외 시장 티커는 yfinance 접미사(`.KS`, `.T` 등)가 필요한데 현재 입력 검증은 미국 시장 위주로 설계됐다. 마켓 선택 UI 추가가 가능.
- yfinance가 막히면 즉시 502를 돌려주는 단순 처리. 재시도/캐시는 미도입.
- WPF 자동화 UI 테스트는 미작성 (수동 검증 단계 의존).

## Git 정보
- base_commit: 378ea4343b1c093018cab21d3f6931237a9d4ca9
- harness_commit_required: true
- commit_created_by_model: false
- commit_message_suggestion: project-initialize[20260527-102251][02_develop]
- commit_scope:
  - .ai/features/project-initialize/00_spec.md
  - .ai/features/project-initialize/00_spec.result.json
  - .ai/features/project-initialize/01_plan.md
  - .ai/features/project-initialize/01_plan.result.json
  - .ai/features/project-initialize/02_dev.md
  - .ai/features/project-initialize/02_dev.result.json
  - src/stocks-api/ (전체 신규 구현)
  - src/stocks-dashboard/ (csproj/MainWindow.xaml/MainWindow.xaml.cs 수정 + App.config/Models/Services 신규)
  - tests/ (신규 테스트)
- pre_commit_diff_command: git diff 378ea4343b1c093018cab21d3f6931237a9d4ca9
- changed_files:
  - .ai/features/project-initialize/02_dev.md
  - .ai/features/project-initialize/02_dev.result.json
  - src/stocks-api/requirements.txt
  - src/stocks-api/main.py
  - src/stocks-api/app/__init__.py
  - src/stocks-api/app/config.py
  - src/stocks-api/app/api/__init__.py
  - src/stocks-api/app/api/stocks.py
  - src/stocks-api/app/models/__init__.py
  - src/stocks-api/app/models/stock.py
  - src/stocks-api/app/services/__init__.py
  - src/stocks-api/app/services/stock_service.py
  - src/stocks-dashboard/stocks-dashboard/stocks-dashboard.csproj
  - src/stocks-dashboard/stocks-dashboard/App.config
  - src/stocks-dashboard/stocks-dashboard/MainWindow.xaml
  - src/stocks-dashboard/stocks-dashboard/MainWindow.xaml.cs
  - src/stocks-dashboard/stocks-dashboard/Models/StockDetailDto.cs
  - src/stocks-dashboard/stocks-dashboard/Services/StockApiClient.cs
  - tests/__init__.py
  - tests/conftest.py
  - tests/test_api_stocks.py
- harness_commit_blocking_reason:

## 단계 결과
- status: PASS
- next_stage: 03_review
- human_gate_required: false
- blocking_reason: 없음
- risk_level: high
- produced_files:
  - .ai/features/project-initialize/02_dev.md
  - .ai/features/project-initialize/02_dev.result.json
- changed_files: 위 `Git 정보`의 `changed_files` 참조
- harness_commit_required: true
- commit_created_by_model: false
- commit_message_suggestion: project-initialize[20260527-102251][02_develop]
- test_commands:
  - python -m pytest tests/
  - dotnet build src/stocks-dashboard/stocks-dashboard.sln
- model_mismatch: false
- actual_model: claude-opus-4-7

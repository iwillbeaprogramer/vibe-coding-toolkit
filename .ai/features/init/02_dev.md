# 02_dev - init

작성: Claude Opus 4.7
일시: 2026-05-26

## 기능 목표
- WPF 데스크톱 클라이언트에서 미국 상장 주식/ETF 티커를 검색하면 로컬 FastAPI 백엔드가 `yfinance`로 데이터를 정제해 반환하고, 화면에 요약 지표와 종가 추이 차트를 다크 테마로 표시한다.

## 변경 파일
- .ai/features/init/00_spec.md (입력 / 변경 금지)
- .ai/features/init/01_plan.md (입력 / 변경 금지)
- .ai/features/init/02_dev.md (신규)
- .ai/features/init/02_dev.result.json (신규)
- src/stock-api/__init__.py (신규)
- src/stock-api/requirements.txt (신규)
- src/stock-api/main.py (신규)
- src/stock-api/services.py (신규)
- src/stock-dashboard/stock-dashboard/App.xaml (수정)
- src/stock-dashboard/stock-dashboard/MainWindow.xaml (수정)
- src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs (수정)
- tests/__init__.py (신규)
- tests/test_api.py (신규)

## 구현 내용

### 1) FastAPI 백엔드 (`src/stock-api/`)
- `services.py`
  - `normalizeSymbol`: 입력을 trim하고 대문자로 정규화, `^[A-Z0-9.\-]{1,15}$` 패턴으로 검증한다. 빈 값/형식 위반은 `InvalidSymbolError(400)`로 분류한다.
  - `loadSummary`: `yfinance.Ticker.info`(또는 `get_info`)를 안전하게 읽어 가격, 전일 종가, 시가/고가/저가, 거래량, 평균 거래량, 시가총액, 52주 고/저가, 통화, 거래소, 섹터/산업, quote_type을 정제한 딕셔너리로 반환한다. NaN/None은 null-safe하게 처리한다. 가격과 전일 종가가 모두 비면 `SymbolNotFoundError(404)`.
  - `loadHistory`: `Ticker.history(period, interval)` 결과 DataFrame을 reset_index 후 OHLCV 레코드로 직렬화한다. `VALID_RANGES`, `VALID_INTERVALS` 화이트리스트로 잘못된 파라미터는 400으로 거절한다. 데이터가 없으면 404.
  - 외부 라이브러리 호출은 `try/except`로 감싸 `UpstreamDataError(502)`로 변환한다.
  - `TickerProvider`는 외부에서 factory를 주입 가능한 의존성 래퍼로, 단위 테스트가 yfinance를 우회할 수 있게 한다.
  - `yfinance` 임포트는 `_defaultTickerFactory` 내부의 지역 임포트로 지연시켜, 라이브러리 미설치 환경에서도 모듈 로드가 가능하게 했다.
- `main.py`
  - FastAPI 앱과 CORS(`allow_origins=["*"]`, GET-only) 미들웨어 설정.
  - 라우트: `GET /health`, `GET /api/stocks/{symbol}/summary`, `GET /api/stocks/{symbol}/history?range&interval`.
  - `StockServiceError`를 잡아 `{"error": {"code", "message"}}` 구조로 일관된 JSON 오류 응답을 반환한다.
- `requirements.txt`: fastapi, uvicorn[standard], yfinance, pandas, pydantic, httpx.

### 2) WPF 프론트엔드 (`src/stock-dashboard/stock-dashboard/`)
- `App.xaml`: 다크 테마 팔레트(Deep Dark Blue `#0F172A`, Neon Blue `#38BDF8`), 카드/검색박스/버튼 스타일, 차트용 그라데이션 브러시(BrushChartFill) 등 전역 리소스 정의.
- `MainWindow.xaml`: 글래스모피즘 카드 레이아웃.
  - 상단: 헤더, 대문자 자동 변환 검색 박스(`CharacterCasing="Upper"`, Enter 키 처리), 검색 버튼.
  - 좌측 카드: 종목명/거래소/현재가/등락/등락률, UniformGrid 기반 상세 지표(전일 종가, 시가, 고가, 저가, 거래량, 평균 거래량, 시가총액, 통화, 52주 고/저가), 섹터/산업.
  - 우측 카드: 기간 선택 ComboBox(`1mo/3mo/6mo/1y/5y`)와 Canvas 차트 영역, 비어 있을 때 안내 텍스트.
  - 하단: 상태 메시지(`StatusLabel`)와 무한 ProgressBar.
- `MainWindow.xaml.cs`:
  - `HttpClient`를 BaseAddress `http://127.0.0.1:8000`, Timeout 15s로 구성.
  - 검색 흐름: 입력 정규화 → 형식 검증 → 요약 호출 → 차트 호출 → 상태 표시. 중복 실행을 막는 `isLoading` 플래그와 로딩 바, 버튼/입력 비활성화 처리.
  - 오류 분기: 404(데이터 없음), 5xx(공급원 오류), `HttpRequestException`(백엔드 미실행), `TaskCanceledException`(타임아웃), 기타 일반 오류를 사용자 친화적 문장으로 구분 표시.
  - 백엔드 오류 응답은 `ApiErrorEnvelope`로 파싱해 메시지를 추출, 실패해도 상태 코드로 폴백.
  - 차트 렌더링: Canvas Width/Height에 맞춰 종가 배열을 X/Y 좌표로 매핑, `Polygon` 그라데이션 채움 + `Polyline` 선 + 시작가 기준 점선 베이스라인 + 마지막 데이터 포인트 강조 점. SizeChanged 이벤트로 리사이즈 대응.
  - 포맷터: 금액 `N2`, 정수 `N0`, 시가총액은 T/B/M 컴팩트 표기. 등락 색상은 양수/음수에 따라 Positive(`#22C55E`)/Negative(`#F43F5E`) 브러시 적용.

### 3) 백엔드 단위 테스트 (`tests/test_api.py`)
- `sys.path`에 `src/stock-api`를 주입해 모듈 임포트.
- `FakeProvider`/`FakeTicker`로 yfinance 호출을 완전히 차단하고, 픽스처를 통해 `main.loadSummary`/`main.loadHistory`를 monkeypatch로 교체.
- 케이스: health, summary 정상/대소문자 정규화/미존재 심볼/잘못된 심볼, history 정상/잘못된 range/interval/미존재 심볼, normalizeSymbol 단위 케이스, upstream 예외 변환.
- `fastapi`/`pandas` 미설치 시 모듈 전체 스킵.

## 왜 이렇게 구현했는가
- **계획 준수**: 01_plan.md의 컴포넌트 분할, 파일 경로, 의존성, 차트 방식(Canvas + Polyline, 외부 NuGet 미사용)을 그대로 따랐다.
- **yfinance 지연 임포트**: 계획에는 명시되지 않았지만, services.py를 모듈 임포트 시점에 yfinance가 없어도 import 가능하게 함으로써 테스트 환경 및 IDE 분석 환경의 안정성을 높였다. 운영 시에는 첫 호출 시 yfinance가 정상 로드된다.
- **TickerProvider DI 도입**: 계획의 "Null-safe 딕셔너리 정제기" 요구를 만족하면서 단위 테스트가 실제 네트워크에 의존하지 않게 하기 위한 작은 결정이다. 외부 호출과 정제 로직을 분리할 수 있어 테스트 안정성이 크게 올라간다.
- **에러 응답 통일**: 모든 서비스 예외를 `StockServiceError`로 표준화하고 `{"error": {"code","message"}}` envelope으로 직렬화했다. WPF 측에서 코드/메시지를 일관되게 처리할 수 있다.
- **history 화이트리스트**: yfinance가 임의 문자열을 받아도 빈 결과를 돌려주는 케이스가 있어 400 응답으로 명시적으로 거절하는 편이 클라이언트 디버깅에 유리하다고 판단했다.
- **WPF Polygon+Polyline 조합**: 계획 채택안인 Canvas/Polyline에 더해 `Polygon`(아래 채우기)을 추가했다. 그라데이션 아래로 떨어지는 영역 표현은 종가 라인 차트에서 시각적 우수성을 크게 끌어올리는 표준 패턴이다. 외부 의존성은 그대로 0개.
- **CharacterCasing="Upper"**: 클라이언트 단에서 즉시 대문자화하여 검색 정규화의 첫 단계를 처리한다.

## 새로 추가한 의존성
- Python (`src/stock-api/requirements.txt`): fastapi, uvicorn[standard], yfinance, pandas, pydantic, httpx — 모두 01_plan.md에서 사전 합의된 항목.
- .NET: 추가 NuGet 의존성 없음.

## 테스트
- 작성한 테스트 파일: `tests/test_api.py` (총 13개 테스트)
- 커버 범위 요약:
  - `/health` 정상 응답
  - summary: 정상 응답, 대소문자 정규화, 미존재 심볼 404, 잘못된 심볼 400
  - history: 정상 응답(필드 셋 검증), 잘못된 range 400, 잘못된 interval 400, 미존재 심볼 404
  - services 유닛: normalizeSymbol 정상/빈문자열/잘못된 문자, upstream 예외→`UpstreamDataError` 변환
- 실행 명령: `python -m pytest tests/test_api.py -v`
- 실행 결과: **13 passed, 1 warning** (warning은 starlette 내부 의존성 경고로 코드 무관)
- WPF 빌드 검증: `dotnet build stock-dashboard.sln -c Debug` → **경고 0, 오류 0** (net7.0-windows)
- 의도적으로 미테스트: WPF UI/차트 렌더링은 수동 테스트 영역으로 01_plan에 명시되어 있어 자동화하지 않았다. 실 yfinance 네트워크 응답도 안정성/속도 이유로 mock으로 대체했다.

## 알려진 한계 / 추후 개선 사항
- yfinance는 비공식 데이터 공급원이므로 운영 환경에서 레이트 리밋이나 응답 포맷 변경이 발생할 수 있다. 백오프/캐시 도입을 후속 단계에서 고려할 수 있다.
- 차트는 종가 라인만 표시하며, 백엔드가 OHLCV를 반환하므로 다음 단계에서 캔들 차트로 확장 가능하다.
- 백엔드 자동 실행(예: WPF 시작 시 자동 spawn) 및 배포 패키징은 이번 범위 밖이다.
- 한국어 통화 포맷 등 로케일 친화적인 표기는 도입하지 않았다(USD 기준).

## Git 정보
- base_commit: c3d65fd191d1110d5f9f8b21961acb031633d6b6
- harness_commit_required: true
- commit_created_by_model: false
- commit_message_suggestion: init[20260526-210955][02_develop]
- commit_scope:
  - .ai/features/init/00_spec.md
  - .ai/features/init/00_spec.result.json
  - .ai/features/init/01_plan.md
  - .ai/features/init/01_plan.result.json
  - .ai/features/init/02_dev.md
  - .ai/features/init/02_dev.result.json
  - src/stock-api/__init__.py
  - src/stock-api/requirements.txt
  - src/stock-api/main.py
  - src/stock-api/services.py
  - src/stock-dashboard/stock-dashboard/App.xaml
  - src/stock-dashboard/stock-dashboard/MainWindow.xaml
  - src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs
  - tests/__init__.py
  - tests/test_api.py
- pre_commit_diff_command: git diff c3d65fd191d1110d5f9f8b21961acb031633d6b6
- changed_files: 위 commit_scope와 동일
- harness_commit_blocking_reason: 없음

## 단계 결과
- status: PASS
- next_stage: 03_review
- human_gate_required: false
- blocking_reason: 없음
- risk_level: high
- produced_files:
  - .ai/features/init/02_dev.md
  - .ai/features/init/02_dev.result.json
- changed_files:
  - .ai/features/init/02_dev.md
  - .ai/features/init/02_dev.result.json
  - src/stock-api/__init__.py
  - src/stock-api/requirements.txt
  - src/stock-api/main.py
  - src/stock-api/services.py
  - src/stock-dashboard/stock-dashboard/App.xaml
  - src/stock-dashboard/stock-dashboard/MainWindow.xaml
  - src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs
  - tests/__init__.py
  - tests/test_api.py
- harness_commit_required: true
- commit_created_by_model: false
- commit_message_suggestion: init[20260526-210955][02_develop]
- test_commands:
  - python -m pytest tests/test_api.py -v
  - dotnet build src/stock-dashboard/stock-dashboard.sln -c Debug
- model_mismatch: false
- actual_model: Claude Opus 4.7

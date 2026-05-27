# 01_plan - project-initialize

작성: Gemini 3.5 Flash (Antigravity)
일시: 2026-05-27

## 기능 목표
- WPF 데스크톱 앱에서 사용자가 미국 주식/ETF 티커(예: QLD)를 검색하면 로컬 Python FastAPI 백엔드가 야후 파이낸스(yfinance)를 통해 수집한 6개월간의 일별 OHLCV 가격 정보 및 실시간 시세, 기업 기본 지표를 제공하고, WPF가 이를 미려한 대시보드 및 캔들스틱 차트 형태로 화면에 상세히 렌더링한다.

## 구현 접근 방식
- **백엔드 (Python FastAPI)**: 외부 시세 API 키가 없이 로컬에서 원활히 구동될 수 있도록 공개 라이브러리인 `yfinance`를 활용한다. `/api/stocks/{symbol}` 단일 엔드포인트를 노출하여 시세 정보(현재가, 전일 종가 등), 주요 기본 지표(시가총액, PER, EPS 등), 기업/상품 개요 및 6개월간의 일별 차트 데이터를 한 번에 조회할 수 있는 통합 API 서비스를 구현한다.
- **프론트엔드 (WPF, .NET 8)**: `HttpClient`를 사용하여 비동기식으로 FastAPI 백엔드와 로컬 통신을 처리하고, 응답받은 JSON 데이터를 역직렬화하여 UI 구성요소에 바인딩한다. 차트 렌더링에는 성능과 기능이 검증된 오픈소스 차트 라이브러리 `ScottPlot.WPF`를 사용하여 6개월간의 캔들스틱(봉차트) 및 거래량 막대를 그리드 하단에 시각화한다.
- **예외 및 상태 관리**: 백엔드 통신 실패, 잘못된 입력(400), 찾을 수 없는 티커(404), 외부 API 에러(502/503) 상황을 꼼꼼하게 처리하여, WPF UI 상에 사용자가 즉각 이해할 수 있는 우아한 한국어 안내 메시지를 출력하며 앱이 멈추지 않고 비정상 동작을 복구할 수 있게 제어한다.

## 검토한 대안
- **대안 1: LiveChartsCore.SkiaSharpView.WPF 라이브러리 사용**
  - **장점**: 모던하고 매우 화려한 애니메이션 효과와 미려한 UI 테마를 제공함.
  - **단점**: WPF .NET 8 환경에서의 SkiaSharp 의존성 로드 버그 및 주식용 캔들스틱 차트 구현 코드의 복잡성이 ScottPlot에 비해 다소 높음.
  - **채택하지 않은 이유**: 본 기능의 우선순위는 미국 주식/ETF의 정확하고 견고한 차트 표시에 있으며, ScottPlot.WPF는 캔들스틱 및 거래량 오버레이를 극히 단순한 코드로 안정적이게 구현 가능하므로 신속하고 오류 없는 개발을 위해 ScottPlot을 최종 선택함.
- **대안 2: FastAPI 백엔드에 SQLite 등의 자체 캐싱 데이터베이스 도입**
  - **장점**: 동일 티커 반복 검색 시 외부 요청 횟수를 줄이고 응답 속도를 비약적으로 향상할 수 있음.
  - **단점**: 로컬 데이터베이스 파일 관리, 데이터 만료 정책 수립 등 초기 개발 범위에 비해 복잡성이 지나치게 가중됨.
  - **채택하지 않은 이유**: 초기 요구사항은 검색 시점 기준 무료 시세 데이터 획득 및 차트 렌더링에 초점이 맞춰져 있으므로, 캐싱 DB 구축은 범위 외로 두고 추후 고도화 단계로 이관함.

## 변경 파일 계획
- **`src/stocks-api/requirements.txt` (신규)**: `fastapi`, `uvicorn`, `yfinance`, `pandas` 등 백엔드 개발 및 데이터 처리에 필요한 파이썬 라이브러리 의존성 명시.
- **`src/stocks-api/main.py` (신규)**: FastAPI 앱 인스턴스 생성, WPF 클라이언트와 통신을 위한 CORS 미들웨어 적용, 공통 HTTP 예외 핸들러 등록 및 라우터 마운트.
- **`src/stocks-api/app/config.py` (신규)**: 로컬 호스트 주소 및 기본 포트 설정(`http://127.0.0.1:8000`), 타임아웃 등의 환경 변수 정의.
- **`src/stocks-api/app/models/stock.py` (신규)**: Pydantic 기반의 주식 상세 시세(`StockQuote`), 기본 지표(`StockFundamentals`), 기업 프로필(`StockProfile`), 차트 봉 데이터(`ChartPoint`) 및 최종 API 응답 모델(`StockDetailResponse`) 정의.
- **`src/stocks-api/app/services/stock_service.py` (신규)**: `yfinance.Ticker`를 호출하여 원본 데이터를 수집한 뒤, 이를 누락된 필드가 없도록 검사하고 데이터 타입에 맞춰 Pydantic 응답 모델 포맷으로 정제/가공하는 핵심 비즈니스 로직 작성. 존재하지 않거나 데이터가 없는 티커는 `HTTPException(404)` 발생 처리.
- **`src/stocks-api/app/api/stocks.py` (신규)**: `/api/stocks/{symbol}` GET 엔드포인트를 노출하고, 입력 symbol 파라미터의 간단한 포맷 검증(길이 및 특수문자 제한)을 적용한 뒤 `stock_service`를 호출하여 결과를 반환하는 API 라우터 작성.
- **`src/stocks-dashboard/stocks-dashboard/stocks-dashboard.csproj` (수정)**: `ScottPlot.WPF` (v5.x 패키지) NuGet 의존성을 추가하여 차트 컨트롤 기능을 활성화.
- **`src/stocks-dashboard/stocks-dashboard/MainWindow.xaml` (수정)**: 빈 Grid를 걷어내고 상단 검색 창(TextBox, Button, 투자 유의 안내), 중앙의 2분할 레이아웃(좌측: 표 형태의 주요 시세 및 기본 지표 Grid, 우측: ScottPlot의 WpfPlot 컨트롤), 하단 로딩 스피너 및 에러 메시지 알림용 Overlay Grid 구현.
- **`src/stocks-dashboard/stocks-dashboard/MainWindow.xaml.cs` (수정)**: 비하인드 코드 내에서 `HttpClient` 싱글톤 유지 및 비동기 호출 처리. 검색 시 공백 제거 및 대문자 정규화 전처리. 로딩 온/오프 상태 전환, API 응답 데이터를 화면 텍스트 블록에 매핑(데이터가 없는 항목은 `N/A` 표기). 수신한 차트 배열을 ScottPlot의 OHLC 구조로 파싱해 캔들스틱 차트를 렌더링하고, X축 시간 라벨 및 Y축 가격 범위를 자동 조절.
- **`tests/test_api_stocks.py` (신규)**: `fastapi.testclient.TestClient`를 기반으로 `pytest` 라이브러리를 활용해 백엔드 API `/api/stocks/{symbol}`의 정상 입력 조회(QLD 등), 없는 티커 예외(404), 비정상 티커 입력 예외(400) 흐름에 대한 단위/통합 테스트 코드 작성.

## 데이터 / 제어 흐름
```
[WPF UI (MainWindow)] 
    -- (1) "QLD" 입력 후 검색 클릭 --> 
    -- (2) 입력 전처리 (Trim, ToUpper) --> 
    -- (3) HttpClient 비동기 요청 (GET http://127.0.0.1:8000/api/stocks/QLD) --> 
    
    [FastAPI (main.py / api/stocks.py)]
        -- (4) 요청 수신 및 유효성 검증 (1~15자 영문/숫자/점/하이픈) -->
        -- (5) 서비스 레이어 (stock_service.py) 호출 -->
        -- (6) yfinance.Ticker("QLD") 인스턴스 생성 -->
        -- (7) ticker.info 및 ticker.history(period="6mo", interval="1d") 호출 -->
        -- (8) 수집된 원본 데이터를 Pydantic API 응답 모델 구조로 가공 및 빌드 -->
        -- (9) JSON 응답 반환 (200 OK) -->
        
    [WPF UI (MainWindow)]
        -- (10) JSON 응답 비동기 수신 및 역직렬화 -->
        -- (11) 기본 지표 및 상세 시세 UI 텍스트 블록에 매핑 (없는 데이터는 N/A 표시) -->
        -- (12) 6개월 차트 데이터를 ScottPlot API를 사용하여 캔들스틱 차트 및 거래량 막대로 렌더링 -->
        -- (13) 로딩 표시 차단 해제 및 완성된 대시보드 표시
```

## 구현 단계 분할
1. **단계 1: 백엔드 개발 환경 및 API 핵심 로직 구현**
   - **설명**: FastAPI 앱 뼈대를 구축하고, `yfinance` 기반으로 시세, 기본 지표, 6개월 차트 OHLCV 데이터를 수집 및 가공하는 서비스를 작성합니다.
   - **파일**: `src/stocks-api/requirements.txt`, `src/stocks-api/main.py`, `src/stocks-api/app/config.py`, `src/stocks-api/app/models/stock.py`, `src/stocks-api/app/services/stock_service.py`, `src/stocks-api/app/api/stocks.py`
   - **완료 기준**: 로컬 Uvicorn 서버를 실행하고 Swagger UI (`/docs`)에 진입하여 `QLD` 티커를 요청했을 때 사양에 명시된 상세 JSON이 정상적으로 반환됨을 눈으로 확인.
2. **단계 2: 백엔드 API 에러 및 입력 테스트 구현**
   - **설명**: API의 신뢰성을 보장하기 위해 존재하지 않는 티커, 지나치게 긴 비정상 티커 등에 대한 400, 404 응답을 자동화 테스트로 검증합니다.
   - **파일**: `tests/test_api_stocks.py`
   - **완료 기준**: 루트에서 `pytest`를 실행하여 3개 이상의 검증 테스트 케이스가 에러 없이 모두 Green 패스함을 확인.
3. **단계 3: WPF 라이브러리 구성 및 UI 레이아웃 마크업**
   - **설명**: WPF 프로젝트 파일에 `ScottPlot.WPF` 의존성을 추가하고, `MainWindow.xaml`에 시세 요약 표와 차트 컨트롤 영역이 어우러지는 현대적이고 고급스러운 디자인 레이아웃을 코딩합니다.
   - **파일**: `src/stocks-dashboard/stocks-dashboard/stocks-dashboard.csproj`, `src/stocks-dashboard/stocks-dashboard/MainWindow.xaml`
   - **완료 기준**: WPF 솔루션이 빌드 에러 없이 온전히 컴파일되며 화면 로딩 시 깔끔하고 완성도 높은 주식 대시보드 스케일이 노출됨.
4. **단계 4: WPF 비하인드 제어 로직 및 ScottPlot 차트 바인딩**
   - **설명**: `MainWindow.xaml.cs`에 HTTP 비동기 호출 및 데이터 모델 파싱을 추가하고, 수신한 OHLCV 배열을 기반으로 ScottPlot 캔들스틱 객체를 생성해 바인딩합니다.
   - **파일**: `src/stocks-dashboard/stocks-dashboard/MainWindow.xaml.cs`
   - **완료 기준**: 검색창에 `QLD` 입력 시 6개월 동안의 주가 흐름이 캔들스틱 차트로 깨끗하게 그려지며 마우스 줌/드래그가 정상 반응함.
5. **단계 5: 예외 흐름 대처 및 한국어 에러 메시지 텍스트 고도화**
   - **설명**: 백엔드가 다운되었을 때, 인터넷 연결이 유실되었을 때, 지원하지 않는 티커를 입력했을 때 발생하는 에러를 WPF에서 캐치하여 우아한 한국어 설명과 대처법을 노출하는 예외 제어 흐름 완성.
   - **파일**: `src/stocks-dashboard/stocks-dashboard/MainWindow.xaml.cs`, `src/stocks-api/app/services/stock_service.py`
   - **완료 기준**: 백엔드가 오프라인 상태일 때 검색 시 "API 서버에 접속할 수 없습니다. 로컬 백엔드가 실행 중인지 확인하십시오." 등의 명확한 한국어 에러 UI가 표시됨.

## 위험 구간
- **위험 항목 1: `yfinance` 라이브러리의 불안정성 및 차단 위험**
  - **완화 방안**: 무료 API의 한계로 인해 짧은 주기로 무수한 검색 요청이 몰릴 시 야후 파이낸스 측에서 접근 제한을 걸어 에러를 뱉을 수 있습니다. 이에 대비해 서비스 레이어에서는 데이터 수집부 호출을 예외 블록으로 철저히 감싸 실패 시 `502 Bad Gateway` 및 구조화된 JSON 메시지를 응답하도록 하고, WPF 측에서도 이를 수려한 한국어 문장("시세 공급자 일시적 장애")으로 바인딩하여 튕김 현상을 원천 방지합니다.
- **위험 항목 2: 존재하지 않는 모호한 티커 입력 시 yfinance의 판단 미비**
  - **완화 방안**: yfinance 모듈은 없는 티커(예: `QLDD`)를 검색해도 오류 예외를 던지지 않고 일부 필드가 Null인 텅 빈 데이터프레임을 반환합니다. 따라서 서비스 내부에서 수신 데이터의 차트 히스토리 크기나 시세 핵심 속성을 사전에 확인하여, 내용물이 없을 시 조기에 `404 Not Found`를 뱉도록 처리합니다.

## 새 의존성
- **WPF**: `ScottPlot.WPF (v5.x)` - 간결하고 고성능의 캔들스틱 및 주식 차트 전용 렌더링 API를 다수 구비하고 있어 WPF 최적화 차트용으로 선정.
- **Python**: `fastapi`, `uvicorn`, `yfinance`, `pandas` - 신속한 로컬 REST API 호스팅 및 무료 주식 정보 수집을 위해 필수적임.

## 테스트 전략
- **백엔드 (Automated Integration Test)**:
  - `tests/test_api_stocks.py` 파일 내에 `pytest`를 통한 자동 테스트 수립.
  - `GET /api/stocks/QLD` 정상 조회 시 JSON에 필수 요약 필드와 차트 배열이 온전히 있는지 검증.
  - `GET /api/stocks/INVALID_TICKER_NAME_123` 호출 시 404 에러와 오류 구조화 JSON 응답 확인.
  - `GET /api/stocks/LONG_TICKER_NAME_EXCEEDING_LIMIT` (15자 초과) 호출 시 400 에러 확인.
- **프론트엔드 (Manual UI Verification)**:
  - WPF 앱 빌드 후 검색 상자에 다양한 입력 검증 (소문자 `qld`, 공백 포함 ` QLD `, 특수문자 `QLD!`).
  - API 서버를 고의로 중지한 상태에서 검색 시 UI 하단 오버레이에 "서버와 연결할 수 없습니다" 경고 문구 확인.
  - 차트 영역 마우스 오버 후 드래그하여 드래그 줌 및 화면 이동 제어 인터랙션 최종 조율.

## 롤백 / 복구 방향
- 하네스가 Git 버전 관리를 주도하므로, 만약 빌드가 실패하거나 심각한 런타임 오류가 개발 단계에서 유발될 경우 하네스를 통해 현재의 Git 안전 기준점(`378ea4343b1c093018cab21d3f6931237a9d4ca9`)으로 파일을 깔끔하게 복원합니다.
- 데이터베이스나 상태 마이그레이션이 필요 없는 단순 로컬 대시보드 뷰어 성격이므로 소스 코드 롤백만으로 부작용 없이 복구가 가능합니다.

## 실행 승인
- **risk_level**: high
- **human_gate_required**: true
- **human_gate_reason**: WPF와 FastAPI 간의 엔드투엔드 연동을 설계하고, 신규 외부 NuGet 차트 라이브러리(`ScottPlot.WPF`) 및 파이썬 시세 크롤러 라이브러리(`yfinance`)를 도입하는 계획이 있으므로 신중한 사람의 검토와 승인이 필요합니다.
- **approval_required_before_develop**: true

## 스펙 모호점 처리
- 야후 파이낸스에서 ETF 티커(예: QLD) 조회 시, 개별 주식과 달리 `sector`나 `industry` 필드가 존재하지 않거나 비어 있습니다. 이 경우 API에서는 `asset_type`을 `ETF`로 명시해주고 해당 정보들은 `null`로 응답하며 WPF에서는 빈칸 대신 `N/A`로 안전하게 치환해 출력하도록 조치했습니다.
- 로컬 개발 환경 통신 주소는 우선 기본값인 `http://127.0.0.1:8000`을 하드코딩하지 않고, WPF의 App.config 또는 설정용 변수로 분리하여 미래에 API 주소가 변경되어도 코드 수정 없이 유연하게 바뀔 수 있도록 구성하겠습니다.

## Git 기준점
- **base_commit**: `378ea4343b1c093018cab21d3f6931237a9d4ca9`
- **diff_base_command**: `git diff 378ea4343b1c093018cab21d3f6931237a9d4ca9`

## 사용자 확인 사항
- 본 프로젝트는 `defaults_mode: true`로 진행되므로 추가적인 대기 없이 사전에 정의된 권장 설정과 라이브러리 선택을 기본값으로 상정하여 설계를 완료했습니다.

## 단계 결과
- **status**: PASS
- **next_stage**: 02_develop
- **human_gate_required**: true
- **blocking_reason**: 없음
- **risk_level**: high
- **produced_files**:
  - .ai/features/project-initialize/01_plan.md
- **changed_files**:
  - .ai/features/project-initialize/01_plan.md
- **commit_created**: false
- **commit_message**:
- **model_mismatch**: false
- **actual_model**: Gemini 3.5 Flash (Antigravity)

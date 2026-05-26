# 01_plan - initial-project

작성: Antigravity
일시: 2026-05-26

## 기능 목표
- WPF 클라이언트와 Python FastAPI 백엔드를 구축하여 미국 주식/ETF(예: QLD) 상세 시세, 기본 정보, 핵심 지표 및 차트를 확인할 수 있는 데스크톱 프로그램을 구현한다.

## 구현 접근 방식
WPF 프론트엔드와 FastAPI 백엔드가 분리되어 로컬 HTTP 통신을 수행하는 클라이언트-서버 구조로 구현한다.
- **FastAPI 백엔드**: 무료이면서 신뢰성 높은 금융 데이터 공급원인 `yfinance` 라이브러리를 활용하여 실시간에 준하는 주가, 회사 프로필, 지표 및 6개월간의 일일 차트 데이터를 수집 및 정규화하여 JSON API로 노출한다.
- **WPF 프론트엔드**: .NET 8.0 기반의 MVVM 패턴으로 구조화하며, UI 스타일은 다크 모드를 기본으로 세련된 그래디언트와 HSL 기반의 색상 체계(상승: Emerald Green, 하락: Red)를 사용한다. `CommunityToolkit.Mvvm`을 통해 반응형 데이터 바인딩을 구현하고, `LiveCharts2 (LiveChartsCore.SkiaSharpView.Wpf)` 라이브러리를 사용하여 유려한 주가 차트를 구현한다.

## 검토한 대안
- **대안 1**: 백엔드 없이 WPF에서 직접 `yfinance`의 대안(예: C#용 YahooFinanceApi)을 호출하거나 웹 스크래핑을 수행하는 방식
  - *장점*: 추가 백엔드 서버 구동 불필요, 구조적 단순함.
  - *단점*: C# 외부 라이브러리 관리 및 API 토큰/요청 헤더 관리가 백엔드에 비해 유연하지 않음. 향후 백엔드 데이터 캐싱, 공급자 변경(Alpha Vantage 등) 또는 복잡한 데이터 정합성 비즈니스 로직을 프론트에 전부 구현해야 하므로 확장성 부족.
  - *채택하지 않은 이유*: 스펙 상 명확히 FastAPI 백엔드를 통한 HTTP API 아키텍처 제공이 요구되므로, 역할 분리 및 확장성을 위해 제외함.
- **대안 2**: WPF 대신 Python GUI(예: Tkinter, PyQt)를 사용하는 방식
  - *장점*: 백엔드와 언어를 일치시켜 빠른 개발 가능.
  - *단점*: WPF에 비해 UI의 완성도, 애니메이션, 미려한 스타일 구현 제약이 크고 스펙 요구사항에 불합합함.
  - *채택하지 않은 이유*: 스펙에 명시된 WPF 프론트엔드 기술 제약 사항을 준수해야 함.

## 변경 파일 계획
모든 신규 파일은 `src/` 하위에 위치하며, 로컬 하네스의 원칙에 따라 이 단계에서는 계획만 수립하고 실제 파일 쓰기는 수행하지 않는다.

- **FastAPI 백엔드 (`src/stock_api/` 신규)**:
  - `src/stock_api/requirements.txt` (신규): `fastapi`, `uvicorn`, `yfinance`, `pydantic` 등 백엔드 의존성 정의.
  - `src/stock_api/main.py` (신규): FastAPI 애플리케이션 진입점 및 CORS 설정, 라우터 연동.
  - `src/stock_api/models/schemas.py` (신규): 주식 시세 데이터, 지표, 프로필 및 차트 데이터를 규정하는 Pydantic 모델(DTO) 정의.
  - `src/stock_api/services/finance_service.py` (신규): `yfinance`를 호출하여 원시 데이터를 가져오고, 누락된 데이터 예외 처리 및 정문화된 DTO로 가공하는 핵심 서비스 로직.
  - `src/stock_api/core/exceptions.py` (신규): 종목 없음(404), 데이터 공급처 오류(502) 등 통합 에러 핸들러 및 사용자 응답 포맷 정의.

- **WPF 프론트엔드 (`src/StockDashboard/` 신규)**:
  - `src/StockDashboard/StockDashboard.sln` (신규): WPF 솔루션 파일.
  - `src/StockDashboard/StockDashboard.Wpf/StockDashboard.Wpf.csproj` (신규): .NET 8.0 WPF 프로젝트 정의 및 `CommunityToolkit.Mvvm`, `LiveChartsCore.SkiaSharpView.Wpf` 패키지 참조 추가.
  - `src/StockDashboard/StockDashboard.Wpf/App.xaml`, `App.xaml.cs` (신규): 애플리케이션 실행 진입점 및 전역 자원 설정.
  - `src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml` (신규): 미려한 다크 모드 테마, 차트 기간 단추(1M, 6M, 1Y), 검색창, 데이터 그리드 및 LiveCharts2 컨트롤이 포함된 메인 윈도우.
  - `src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml.cs` (신규): 메인 윈도우 비하인드 코드 (DataContext 바인딩).
  - `src/StockDashboard/StockDashboard.Wpf/ViewModels/MainWindowViewModel.cs` (신규): 검색 명령, 입력 유효성 검증(비정상/비어있는 입력 차단), API 호출(HttpClient), 차트 시리즈 매핑, 오류 메시지 및 스피너 바인딩 속성 정의.
  - `src/StockDashboard/StockDashboard.Wpf/Models/StockModels.cs` (신규): 백엔드 API 응답과 1:1 매칭되는 C# DTO 및 바인딩용 모델 구조.

- **테스트 계획 (`tests/` 신규)**:
  - `tests/backend/test_finance_api.py` (신규): FastAPI 엔드포인트 응답 상태 코드 및 반환 데이터 규격 검증용 테스트 코드.
  - `tests/frontend/StockDashboard.Tests/StockDashboard.Tests.csproj` (신규): WPF 뷰모델 유효성 검증용 xUnit 테스트 프로젝트.
  - `tests/frontend/StockDashboard.Tests/MainWindowViewModelTests.cs` (신규): 검색어 정규화, 유효성 검사 경계 조건 및 백엔드 예외 수신 시 UI 바인딩 변동 테스트.

## 데이터 / 제어 흐름
WPF에서 티커(QLD) 검색 요청을 시작으로 최종 차트와 지표가 렌더링되기까지의 데이터 및 제어 흐름이다.

```
[ WPF Client (WPF UI) ]
      │
      │ 1. Ticker 입력 (예: " qld ") -> 정규화 ("QLD") -> 유효성 검사
      ▼
[ MainWindowViewModel ] ──────────── (로딩 스피너 활성화)
      │
      │ 2. HTTP GET /api/stock/QLD (Async)
      ▼
[ FastAPI Backend ] (port 8000)
      │
      │ 3. yfinance 호출 (Ticker("QLD"))
      ▼
[ Yahoo Finance API ]
      │
      │ 4. 시세 정보, 기업 프로필, 6개월 일봉 시계열 데이터 반환
      ▼
[ FastAPI (FinanceService) ]
      │
      │ 5. Pydantic 스키마 매핑 & 누락 값 N/A 처리
      ▼
[ MainWindowViewModel ] <─── 6. JSON 응답 수신 (Deserialization)
      │
      │ 7. UI 바인딩 속성 업데이트 & LiveCharts2 Series 변환
      ▼
[ WPF Client (WPF UI) ] ──────────── (차트 렌더링 및 정보 그리드 업데이트)
```

## 구현 단계 분할
1. **단계 1: 백엔드 환경 구축 및 yfinance 연동 (FastAPI)**
   - 파일: `src/stock_api/requirements.txt`, `main.py`, `services/finance_service.py`, `models/schemas.py`
   - 완료 기준: FastAPI 서버를 구동하고 `/api/stock/{symbol}` 호출 시 지정된 DTO 규격(종목 상세 및 6개월 일봉 차트 시계열)에 맞게 JSON이 정상 반환됨. (테스트 대상: QLD, AAPL, 존재하지 않는 티커)
2. **단계 2: 백엔드 예외 처리 및 통합 테스트 코드 구현**
   - 파일: `src/stock_api/core/exceptions.py`, `tests/backend/test_finance_api.py`
   - 완료 기준: 존재하지 않는 티커 조회 시 404, 네트워크 차단/데이터 유실 시 502 예외가 응답 바디의 오류 상세 메시지와 함께 잘 노출되는지 검증 완료.
3. **단계 3: WPF 프로젝트 및 MVVM 기초 설계**
   - 파일: `src/StockDashboard/`, `src/StockDashboard/StockDashboard.Wpf/` 신규 파일 전체
   - 완료 기준: .NET 8 WPF 앱 프로젝트가 문제없이 생성되고 빌드가 완료됨.
4. **단계 4: WPF 메인 화면(UI/UX) 구현 및 LiveCharts2 도입**
   - 파일: `MainWindow.xaml`, `MainWindow.xaml.cs`, `MainWindowViewModel.cs`
   - 완료 기준: 다크 모드 스타일이 적용되고, 검색창, 상세 정보 영역, 차트 프레임워크가 렌더링되며, Mock 데이터를 이용한 차트 가독성 확인.
5. **단계 5: WPF-FastAPI 연동 및 종합 기능 테스트**
   - 파일: `MainWindowViewModel.cs` 내 API 호출 로직 완성, `tests/frontend/StockDashboard.Tests`
   - 완료 기준: 백엔드 서버 구동 상태에서 WPF 앱을 통해 QLD를 검색했을 때, 실제 데이터 및 6개월 일봉 차트가 미려하게 표현되며 에러 상황(존재하지 않는 티커 검색 등) 발생 시 다크 모드 오류 배너가 올바르게 작동함.

## 위험 구간
- **위험 항목**: 무료 API인 `yfinance`가 로컬 환경에서 과도한 호출 또는 차단으로 인해 속도 제한(Rate Limit)을 받거나 응답이 지연될 위험.
- **완화 방안**: 백엔드 레벨에서 API 호출 시 적절한 HTTP Timeout(5초)을 부여하고, 외부 요청 실패 시 WPF 클라이언트에 "데이터 공급처 오류로 일시적으로 조회가 불가능합니다. 잠시 후 다시 시도해 주세요."라는 정제된 메시지를 반환함. 장기적으로는 캐싱 레이어를 적용하거나 다중 데이터 소스 Fallback을 대비할 수 있도록 설계함.
- **위험 항목**: LiveCharts2가 대용량 시계열(6개월 일봉 = 약 125개 데이터 포인트) 데이터 로딩 시 WPF UI 스레드 차단으로 인한 버벅임 발생.
- **완화 방안**: API 비동기 호출(`async/await`)을 철저하게 적용하고, 차트 데이터 바인딩 시 UI 스레드 바깥에서 컬렉션을 생성한 후 바인딩 속성에 할당하도록 구현함.

## 새 의존성
- **Python Backend**:
  - `fastapi` & `uvicorn`: 초경량 및 고성능 비동기 웹 API 프레임워크.
  - `yfinance`: 무료 및 공개 금융 정보 수집용.
  - `pydantic`: 데이터 파싱 및 유효성 검증용.
- **WPF Frontend**:
  - `CommunityToolkit.Mvvm`: 최신 .NET 권장 MVVM 라이브러리로 소스 생성기 활용을 위해 도입.
  - `LiveChartsCore.SkiaSharpView.Wpf` (LiveCharts2): 현대적인 미려한 스타일과 애니메이션을 기본 탑재한 WPF 차트 라이브러리.

## 테스트 전략
- **FastAPI 백엔드 검증**:
  - `pytest`와 `httpx`를 사용하여 `/api/stock/{symbol}` 엔드포인트의 정상 시세 응답, 데이터 누락 시 `N/A` 대체 여부, 잘못된 티커 요청 시 404 에러 구조 반환 여부 검증 (Integration Test).
- **WPF 프론트엔드 검증**:
  - 입력값 정규화 테스트: " qld ", "Qld" 입력이 "QLD"로 변환되는지 검증.
  - 경계 테스트: 15자 초과 입력, 비어있는 입력, 불법 문자(!@#$) 포함 시 검색 요청을 보내지 않고 뷰모델 에러 플래그가 활성화되는지 단위 테스트(xUnit).
- **통합 검증 (E2E)**:
  - 실제 개발 완료 후 로컬에서 백엔드와 WPF를 동시에 켜고 검색을 실행하여 시각화 동작 확인.

## 롤백 / 복구 방향
- 모든 로직은 신규 파일 생성으로 이루어지며, 기존 레포지토리에 제품용 코드가 존재하지 않으므로 문제 발생 시 `src/` 및 `tests/` 하위 디렉터리를 깔끔히 삭제하거나 Git Checkout을 통해 리셋할 수 있어 비가역적인 변경 위험이 없음.

## 실행 승인
- risk_level: medium
- human_gate_required: true
- human_gate_reason: 최초 프로젝트 생성, 신규 WPF/FastAPI 아키텍처 수립, yfinance 외부 종속성 설계에 대한 개발 진입 전 사전 컨펌 필요.
- approval_required_before_develop: true

## 스펙 모호점 처리
- **스펙 모호점**: 차트의 상세 조회 범위 및 보조 지표 처리
- **처리 근거**: `defaults_mode: true` 정책에 따라 미국 주식/ETF 티커 중심으로 검색을 고정하고, `yfinance`가 반환하지 않는 지표 항목(일부 ETF는 EPS, PER 등이 제공되지 않음)은 데이터 구조체 가공 중 오류를 유발하지 않고 안전하게 `N/A`로 매핑하여 UI에 반영하도록 설계함.

## Git 기준점
- base_commit: 515d623878911a3b0fc1a35b98fcc43bdcb9b767
- diff_base_command: git diff 515d623878911a3b0fc1a35b98fcc43bdcb9b767

## 사용자 확인 사항
- 본 프로젝트는 `defaults_mode: true` 모드로 구동 중이므로 별도의 차단성 질문 없이 권장 기술 체계(.NET 8 WPF, LiveCharts2, yfinance)를 기본 선택안으로 삼아 계획을 완결지었습니다. 사용자가 차후 수정 단계를 통해 다른 데이터 공급자나 스타일 변경을 원하면 유연하게 대응 가능하도록 느슨한 결합으로 설계되었습니다.

## 단계 결과
- status: PASS
- next_stage: 02_develop
- human_gate_required: true
- blocking_reason: 없음
- risk_level: medium
- produced_files:
  - .ai/features/initial-project/01_plan.md
  - .ai/features/initial-project/01_plan.result.json
- changed_files:
  - .ai/features/initial-project/01_plan.md
  - .ai/features/initial-project/01_plan.result.json
- commit_created: false
- commit_message:
- model_mismatch: false
- actual_model: Antigravity

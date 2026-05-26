import sys, os
sys.path.insert(0, ".ai/templates")
from docx_helper import (
    create_doc, add_h1, add_h2, add_paragraph,
    add_bullet, add_code_block, add_table
)

doc = create_doc()

# ── 1. 개요 ──────────────────────────────────────────────────────────────────
add_h1(doc, "1. 개요")
add_table(doc,
    headers=["항목", "내용"],
    rows=[
        ["기능 이름", "initial-project"],
        ["기능 목적", "WPF 데스크톱 클라이언트와 FastAPI 백엔드를 연동하여 미국 주식 및 ETF 정보를 상세 조회하고 차트를 시각화하는 금융 정보 제공 시스템"],
        ["최종 판정", "PASS"],
        ["최종 완성 일시", "2026-05-26"],
    ]
)
add_paragraph(doc, "본 문서는 WPF 프론트엔드와 Python FastAPI 백엔드를 분리하여 구축된 주식 상세 정보 및 시계열 차트 렌더링 시스템인 'initial-project'에 대한 개발 명세서입니다. 본 시스템은 무료 금융 데이터 공급원인 yfinance 라이브러리를 활용하고, WPF 클라이언트에서는 현대적인 MVVM 패턴과 LiveCharts2 라이브러리를 도입하여 사용자에게 최상의 시각적 반응성과 유연한 환경을 제공합니다.")

# ── 2. 사용 방법 ──────────────────────────────────────────────────────────────
add_h1(doc, "2. 사용 방법")
add_h2(doc, "API / 인터페이스")
add_paragraph(doc, "FastAPI 백엔드는 WPF 클라이언트 및 다른 HTTP 클라이언트의 조회를 지원하기 위해 다음과 같은 API 엔드포인트를 노출합니다.")
add_bullet(doc, "엔드포인트: GET /api/stock/{symbol}")
add_bullet(doc, "경로 파라미터 (Path Parameter): symbol (필수) - 영문 대소문자, 숫자, 점, 하이픈을 포함한 1~15자의 주식/ETF 티커 문자열 (예: QLD, AAPL, MSFT, BRK-B)")
add_bullet(doc, "쿼리 파라미터 (Query Parameter): range (선택) - 차트 데이터 기간 (허용 값: 1mo, 6mo, 1y. 기본값: 6mo)")
add_bullet(doc, "응답 포맷 (Response Format): JSON 형태의 주식 상세 및 6개월 일봉 차트 데이터")
add_bullet(doc, "헬스 체크 엔드포인트: GET /api/health - 백엔드 서버 생존 여부 및 가동 상태 확인용 API")

add_h2(doc, "API 호출 예시 (Python)")
add_code_block(doc, 
"import requests\n"
"\n"
"# 로컬 서버 주소 및 파라미터 구성\n"
"url = 'http://localhost:8000/api/stock/QLD'\n"
"params = {'range': '6mo'}\n"
"\n"
"try:\n"
"    response = requests.get(url, params=params)\n"
"    if response.status_code == 200:\n"
"        data = response.json()\n"
"        print(f\"종목명: {data['name']}\")\n"
"        print(f\"현재가: {data['quote']['current_price']} {data['currency']}\")\n"
"        print(f\"차트 데이터 포인트 개수: {len(data['chart'])}\")\n"
"    else:\n"
"        print(f\"에러 응답 ({response.status_code}): {response.json()}\")\n"
"except Exception as e:\n"
"    print(f\"연결 실패: {e}\")"
)

add_h2(doc, "C# WPF 클라이언트 호출 예시 (HttpClient)")
add_code_block(doc,
"using System.Net.Http;\n"
"using System.Net.Http.Json;\n"
"using System.Threading;\n"
"using System.Threading.Tasks;\n"
"\n"
"public async Task<StockDetailDto?> GetStockDetailAsync(string symbol, string range, CancellationToken ct)\n"
"{\n"
"    var client = new HttpClient { BaseAddress = new Uri(\"http://localhost:8000/\") };\n"
"    try\n"
"    {\n"
"        // API 비동기 GET 요청 및 JSON 역직렬화\n"
"        return await client.GetFromJsonAsync<StockDetailDto>($\"api/stock/{symbol}?range={range}\", ct);\n"
"    }\n"
"    catch (HttpRequestException ex)\n"
"    {\n"
"        // 네트워크 연결 및 HTTP 에러 통합 처리\n"
"        throw new StockApiException((int)(ex.StatusCode ?? 0), \"http_error\", ex.Message, ex);\n"
"    }\n"
"}"
)

# ── 3. 관련 파일 ──────────────────────────────────────────────────────────────
add_h1(doc, "3. 관련 파일")
add_table(doc,
    headers=["파일 경로", "역할"],
    rows=[
        ["src/stock_api/requirements.txt", "FastAPI, uvicorn, yfinance, pydantic 등 백엔드 필수 의존성 정의 파일"],
        ["src/stock_api/main.py", "FastAPI 서버 진입점, CORS 설정, 라우터 연동 및 에러 핸들러 등록"],
        ["src/stock_api/models/schemas.py", "Pydantic v2를 사용해 상세 시세, 지표, 프로필, 차트 정보 구조 및 null 허용 필드 정의"],
        ["src/stock_api/services/finance_service.py", "yfinance 호출, 6초 타임아웃 제한 및 스레드풀 분리, 누락 필드 N/A 처리 로직"],
        ["src/stock_api/core/exceptions.py", "통합 예외 클래스(400, 404, 502) 정의 및 JSON 에러 봉투 포맷 정의"],
        ["src/StockDashboard/StockDashboard.sln", "WPF 프론트엔드 전체 솔루션 구성 파일"],
        ["src/StockDashboard/StockDashboard.Wpf/StockDashboard.Wpf.csproj", ".NET 8.0 WPF 프로젝트 빌드 정의 및 외부 패키지(MvvmToolkit, LiveCharts2) 참조 추가"],
        ["src/StockDashboard/StockDashboard.Wpf/App.xaml", "WPF 애플리케이션 전역 리소스(컨버터, 스타일 등) 및 실행 구조 설정"],
        ["src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml", "그라데이션 다크 테마 UI, 검색창, 지표 데이터그리드, LiveCharts2 영역 정의"],
        ["src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml.cs", "LiveCharts2 렌더링 업데이트(RefreshChart), Stock 변경 이벤트 수신, PropertyChanged 구독 해제"],
        ["src/StockDashboard/StockDashboard.Wpf/ViewModels/MainWindowViewModel.cs", "CommunityToolkit.Mvvm 기반 입력 유효성 검사, 비동기 검색 Command, API 에러 메시지 바인딩"],
        ["src/StockDashboard/StockDashboard.Wpf/Models/StockModels.cs", "백엔드 API JSON 명세와 1:1 매칭되는 C# DTO 및 바인딩 모델 구조"],
        ["src/StockDashboard/StockDashboard.Wpf/Services/IStockApiClient.cs", "ViewModel의 단위 테스트 격리를 위한 주식 API 호출 인터페이스"],
        ["src/StockDashboard/StockDashboard.Wpf/Services/StockApiClient.cs", "HttpClient 기반의 실제 통신 및 TaskCanceledException 사용자 취소 분기 처리 서비스"],
        ["src/StockDashboard/StockDashboard.Wpf/Converters/NullToVisibilityConverter.cs", "에러 정보 노출 여부(Null)에 따른 WPF UI 가시성(Visibility) 토글 컨버터"],
    ]
)

# ── 4. 주요 설계 결정 ─────────────────────────────────────────────────────────
add_h1(doc, "4. 주요 설계 결정")
add_h2(doc, "구현 접근 방식")
add_paragraph(doc, "1. 프론트엔드와 백엔드의 완벽한 물리적 격리: WPF가 데이터에 종속적이지 않고 HTTP API를 통해 데이터를 주고받도록 구성하여 향후 캐싱, 다중 데이터 소스 Fallback 로직 등을 백엔드에서 격리 제어할 수 있도록 설계했습니다.")
add_paragraph(doc, "2. 동기 금융 라이브러리의 비동기 안전 실행: yfinance는 동기적 requests에 의존하므로, 백엔드 서버(FastAPI)의 비동기 이벤트 루프가 차단되는 현상을 방지하기 위해 concurrent.futures.ThreadPoolExecutor(max_workers=1)를 활용해 별도의 백그라운드 워커 스레드풀에서 안전하게 yfinance를 기동하도록 구현했습니다.")
add_paragraph(doc, "3. WPF MVVM 테스트성 극대화: MainWindowViewModel이 HttpClient를 직호출하지 않고 IStockApiClient 인터페이스를 주입받아 사용하도록 설계하여, LiveCharts2 등 무거운 WPF UI 라이브러리를 로딩하지 않고도 ViewModel의 입력 검증, 에러 분기 시나리오를 온전히 단위 테스트할 수 있는 테스트 격리성을 달성했습니다.")

add_h2(doc, "검토한 대안 및 채택하지 않은 이유")
add_bullet(doc, "대안 1: 백엔드 서버 없이 WPF 클라이언트에서 직접 야후 파이낸스 라이브러리(C# YahooFinanceApi 등)를 사용하는 방식\n- 채택하지 않은 이유: C# 외부 라이브러리는 최신 야후 API 변경에 신속하게 대응하기 어렵고, 데이터 가공 및 캐싱, 에러 변환, 속도 제한 우회 로직을 프론트에 모두 작성하면 향후 웹 데모 등의 멀티 클라이언트 확장성이 현저히 저해되므로 기각했습니다.")
add_bullet(doc, "대안 2: WPF 대신 Python GUI(Tkinter, PyQt 등)를 활용한 데스크톱 구현\n- 채택하지 않은 이유: WPF에 비해 UI 디자인의 미려함, 애니메이션 처리, 스피너 렌더링 등의 완성도 제약이 크고, 스펙에 명시된 WPF 사용 요구사항을 철저히 준수하기 위해 대안에서 제외했습니다.")

add_h2(doc, "리뷰 핵심 포인트와 최종 결정")
add_bullet(doc, "[BLOCKER] 재검색 시 WPF 차트 미갱신 버그 해결\n- 원인: 차트 갱신 조건이 HasResult였으나, 첫 검색 후 계속 true 상태를 유지하여 PropertyChanged가 발생하지 않음.\n- 결정: 매 성공 시마다 새로운 인스턴스가 바인딩되는 Stock 프로퍼티 자체를 감시하도록 MainWindow.xaml.cs 코드를 전면 수정하여 재검색 시에도 차트 갱신이 완벽하게 수행되도록 조치함.")
add_bullet(doc, "[MAJOR] 연속 빠른 검색 시 발생하는 취소 예외의 시간초과 오인 버그 해결\n- 원인: TaskCanceledException 발생 시 사용자 취소와 실제 타임아웃을 구분하지 않아 화면에 '시간 초과되었습니다' 배너가 번쩍임.\n- 결정: ct.IsCancellationRequested 분기를 추가하여 사용자 명시 취소일 경우 OperationCanceledException을 다시 던져 ViewModel에서 조용하게 검색 작업을 무시하고 중단하도록 매핑함.")
add_bullet(doc, "[MINOR] yfinance 외부 응답 지연 시 백엔드 무한 대기 위험 해결\n- 원인: yfinance API 호출은 동기 통신으로, 야후 서버 문제 발생 시 uvicorn 작업 스레드가 무한 블로킹됨.\n- 결정: ThreadPoolExecutor 미래 결과 대기 시 6초의 상한 타임아웃(future.result(timeout=6.0))을 명시적으로 부여하고, 시간 초과 시 UpstreamDataError(502)로 변환해 사용자에게 빠르고 정제된 에러 정보를 표출하도록 수정함.")

add_h2(doc, "거부/보류 항목 및 사유")
add_bullet(doc, "지적 사항: _coerce_float / _coerce_int 헬퍼의 NumPy/컬렉션 계열 입력을 방어하기 위한 isinstance 사전 입력 타입 검증 보강\n- 거부 사유: 현재 구현은 float(value) 형변환 시 발생할 수 있는 모든 TypeError 및 ValueError를 try-except 블록으로 견고하게 캡처하여 math.isnan/math.isinf 검사를 안전하게 수행하고 있습니다. 또한 4단계 fix에서 추가한 'test_endpoint_serializes_nan_and_inf_metrics_as_null' 연동 테스트를 통해 NaN/Inf의 null 직렬화 정상 도달 시나리오를 엄밀히 검증했으므로, 단순 isinstance 사전 타입 검사 분기를 추가하는 것은 코드의 복잡성을 가중시키고 성능상 낭비를 부를 뿐 실효 가치가 없다고 판단하여 최종 거부 처리했습니다.")

# ── 5. 의존성 ─────────────────────────────────────────────────────────────────
add_h1(doc, "5. 의존성")
add_table(doc,
    headers=["구분", "라이브러리 / 패키지", "사용 목적"],
    rows=[
        ["Python Backend", "fastapi", "초경량, 초고속 비동기 웹 API 구현용 웹 프레임워크"],
        ["Python Backend", "uvicorn[standard]", "백엔드 FastAPI 애플리케이션 기동용 ASGI 서버"],
        ["Python Backend", "yfinance", "미국 주식 및 ETF 상세 시세, 지표, 일일 가격 데이터 수집 라이브러리"],
        ["Python Backend", "pydantic", "JSON 데이터 모델(DTO) 정의 및 입출력 필드 정합성 유효성 검증 (v2)"],
        ["WPF Frontend", "CommunityToolkit.Mvvm (8.2.2)", "생성기 기반의 MVVM 패턴, ObservableProperty 및 AsyncRelayCommand 제공"],
        ["WPF Frontend", "LiveChartsCore.SkiaSharpView.Wpf (2.0.0-rc2)", "SkiaSharp 기반의 미려한 실시간 렌더링 주가 라인 차트 컨트롤"],
        ["WPF Frontend", "System.Net.Http.Json (8.0.0)", "API 통신 시 DTO와의 자동 JSON 직렬화/역직렬화 지원 확장 패키지"],
        ["Backend Test", "pytest", "FastAPI 라우터 및 서비스 레이어 검증용 Python 테스트 프레임워크"],
        ["Backend Test", "httpx", "비동기 API 엔드포인트 Mocking 및 HTTP 호출 테스트 Client"],
        ["Frontend Test", "xunit", ".NET 8.0 WPF 뷰모델 시나리오 검증용 단위 테스트 프레임워크"],
    ]
)

# ── 6. 테스트 현황 ────────────────────────────────────────────────────────────
add_h1(doc, "6. 테스트 현황")
add_table(doc,
    headers=["테스트 파일 경로", "커버리지 및 검증 범위", "결과"],
    rows=[
        ["tests/backend/test_finance_api.py", "심볼 정규화(공백, 대소문자), 필수/부분 필드 누락 가공, 존재하지 않는 심볼(404), 기간/심볼 에러(400), yfinance API 타임아웃 지연(502), NaN/Inf 필드 null 직렬화 검증 (16개 시나리오)", "PASS"],
        ["tests/frontend/StockDashboard.Tests/MainWindowViewModelTests.cs", "검색 심볼 정규화, 입력 문자열 공백/15자 초과/특수문자 유효성 검사 차단, 400/404/502/네트워크 오류 시 한국어 메시지 매핑, 사용자 검색 취소 시 에러 무시 검증 (16개 시나리오)", "PASS"],
    ]
)
add_paragraph(doc, "최종 빌드 및 모든 단위 테스트가 통과하였음을 확인했습니다. 백엔드는 pytest를 통해 외부 네트워크 및 외부 API 의존성이 배제된 고속 가상 로더 환경 하에 통합 API 명세를 100% 검증 완료했으며, 프론트엔드는 .NET 8 SDK 환경에서 xUnit 테스트 프로젝트를 구동하여 뷰모델 비즈니스 로직과 에러 매핑 정책의 정합성을 완벽하게 증명했습니다.")

# ── 7. 알려진 한계 및 추후 개선 ──────────────────────────────────────────────
add_h1(doc, "7. 알려진 한계 및 추후 개선")
add_bullet(doc, "yfinance API 호출 제한 및 상용 안정성: 무료 yfinance API의 사용량 제약(Rate Limit)과 네트워크 지연 발생 시 대응이 6초 타임아웃 502 예외 변환으로 한정되어 있습니다. 향후 다수의 사용자가 이용할 경우를 대비하여 백엔드에 Redis 또는 로컬 메모리 캐시 레이어를 도입해 동일 종목의 빈번한 조회를 효과적으로 통제해야 합니다.")
add_bullet(doc, "데이터 공급망 이중화(Fallback) 구현: 야후 파이낸스 자체의 차단 혹은 서비스 정지에 강인하도록 Alpha Vantage, IEX Cloud 등 다른 금융 데이터 공급처를 가동하여, 예외 상황 발생 시 투명하게 Secondary API로 교체 호출할 수 있는 공급처 인터페이스 추상화 및 팩토리 패턴 고도화가 요구됩니다.")
add_bullet(doc, "차트 기술적 지표 및 기간 세분화: 현재는 1mo, 6mo, 1y 3가지 기간의 일봉 단순 선 차트만 제공합니다. 실사용자(주식쟁이)들의 요구를 완벽히 만족하기 위해 분봉/주봉 조회, 이동평균선(MA), 볼린저 밴드(BB), MACD, RSI 등 보조 지표를 계산하여 백엔드에서 WPF로 추가 데이터 세트를 전송하고 렌더링하는 차트 캔버스 확장이 필요합니다.")

# ── 저장 ──────────────────────────────────────────────────────────────────────
os.makedirs(".ai/docs", exist_ok=True)
doc.save(".ai/docs/initial-project_명세서.docx")
print("생성 완료: .ai/docs/initial-project_명세서.docx")

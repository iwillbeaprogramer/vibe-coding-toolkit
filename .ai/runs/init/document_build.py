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
        ["기능 이름", "init"],
        ["기능 목적", "WPF 데스크톱 앱과 FastAPI 백엔드를 연동한 미국 주식/ETF 검색 및 가격 차트 시각화 서비스"],
        ["최종 판정", "PASS"],
        ["최종 완성 일시", "2026-05-26"],
    ]
)
add_paragraph(doc, "본 기능은 Windows WPF 데스크톱 환경의 클라이언트와 Python FastAPI 로컬 백엔드를 유기적으로 연동하여, 사용자가 원하는 미국 주식 및 ETF 종목(예: QLD, AAPL, MSFT)을 검색하면 yfinance API를 통해 수집된 상세 지표와 과거 종가 시계열 데이터를 보기 쉬운 그래픽 차트와 정돈된 UI로 표현해주는 주식 정보 대시보드 시스템입니다.")

# ── 2. 사용 방법 ──────────────────────────────────────────────────────────────
add_h1(doc, "2. 사용 방법")
add_h2(doc, "API 엔드포인트 명세")
add_bullet(doc, "GET /health: 백엔드 API 서비스 정상 작동 상태 확인용 헬스체크 엔드포인트.")
add_bullet(doc, "GET /api/stocks/{symbol}/summary: 종목 고유 기호(symbol)를 입력받아 현재가, 시가, 고가, 저가, 전일 종가, 변동폭/변동률, 거래량, 평균 거래량, 시가총액, 52주 가격 범위 등의 주요 시장 정보 요약을 JSON 형태로 반환.")
add_bullet(doc, "GET /api/stocks/{symbol}/history?range=1mo&interval=1d: 지정한 범위(range: 1mo, 3mo, 6mo, 1y, 5y) 및 주간 간격(interval: 1d, 1wk, 1mo) 동안의 과거 일별 종가 및 OHLCV(시가, 고가, 저가, 종가, 거래량) 시계열 배열을 반환.")

add_h2(doc, "API 호출 코드 예시")
add_code_block(doc, 
"import requests\n\n"
"# 1. 백엔드 상태 검사\n"
"health_status = requests.get('http://127.0.0.1:8000/health').json()\n"
"print('Server status:', health_status)\n\n"
"# 2. QLD 종목 요약 데이터 조회\n"
"summary_data = requests.get('http://127.0.0.1:8000/api/stocks/QLD/summary').json()\n"
"print('QLD Price:', summary_data.get('price'))\n\n"
"# 3. AAPL 주식 1개월간의 과거 이력 조회\n"
"history_data = requests.get('http://127.0.0.1:8000/api/stocks/AAPL/history?range=1mo&interval=1d').json()\n"
"print('First Day Close:', history_data['prices'][0]['close'])"
)

add_h2(doc, "데이터 입출력 데이터 예시")
add_paragraph(doc, "GET /api/stocks/QLD/summary 정상 응답 예시:")
add_code_block(doc,
"{\n"
"  \"symbol\": \"QLD\",\n"
"  \"name\": \"ProShares Ultra QQQ\",\n"
"  \"price\": 98.45,\n"
"  \"prev_close\": 97.20,\n"
"  \"change\": 1.25,\n"
"  \"change_percent\": 1.29,\n"
"  \"open\": 97.50,\n"
"  \"high\": 99.10,\n"
"  \"low\": 97.12,\n"
"  \"volume\": 3254100,\n"
"  \"market_cap\": 25400000000,\n"
"  \"currency\": \"USD\",\n"
"  \"exchange\": \"NASDAQ\",\n"
"  \"sector\": \"N/A\",\n"
"  \"industry\": \"N/A\",\n"
"  \"quote_type\": \"ETF\"\n"
"}"
)

# ── 3. 관련 파일 ──────────────────────────────────────────────────────────────
add_h1(doc, "3. 관련 파일")
add_table(doc,
    headers=["파일 경로", "역할"],
    rows=[
        ["src/stock-api/requirements.txt", "FastAPI, uvicorn, yfinance 등 파이썬 백엔드 라이브러리 의존성 정의"],
        ["src/stock-api/main.py", "FastAPI 앱 초기화, CORS 설정, API 라우터 매핑 및 에러 미들웨어 핸들링"],
        ["src/stock-api/services.py", "yfinance 모듈 지연 로드 및 데이터 정제, Null-safe 데이터 매퍼, TickerProvider 구현"],
        ["src/stock-dashboard/stock-dashboard/App.xaml", "글로벌 다크 테마(Deep Dark Blue, Neon Blue) 팔레트, 폰트 및 스타일 딕셔너리 리소스"],
        ["src/stock-dashboard/stock-dashboard/MainWindow.xaml", "Glassmorphism 스타일 카드 레이아웃, 검색 바, 상세 정보 그리드, 가격 차트 Canvas 화면 디자인"],
        ["src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs", "HTTP 비동기 조회, 런타임 브러시 캐싱, SizeChanged 이벤트 디바운스 타이머, Canvas 커스텀 차트 렌더링 로직"],
        ["tests/test_api.py", "FastAPI TestClient 및 Mocking 공급자를 이용한 백엔드 API 기능/엣지 단위 자동화 테스트"],
    ]
)

# ── 4. 주요 설계 결정 ─────────────────────────────────────────────────────────
add_h1(doc, "4. 주요 설계 결정")
add_h2(doc, "구현 접근 방식")
add_paragraph(doc, "백엔드 개발 시 yfinance API 호출 안전성을 확보하고자 'TickerProvider' 구조의 의존성 주입(DI) 아키텍처를 도입하였습니다. 이를 통해 프로덕션에서는 실제 야후 파이낸스 데이터를 긁어오지만, 테스트 환경에서는 가상의 Mock 공급자를 주입해 인터넷 연결이나 레이트 리밋에 구애받지 않고 견고하게 서버 로직을 검증할 수 있습니다.")
add_paragraph(doc, "프론트엔드에서는 WPF Native Canvas를 주 스크린으로 삼아 선을 그리는 Polyline 뿐만 아니라 하단에 그라데이션 채우기 붓을 적용한 Polygon을 덧입혀, 현대적이고 미려한 하이테크 감성의 비주얼 대시보드를 구축하였습니다.")

add_h2(doc, "검토한 대안 및 채택 결과")
add_bullet(doc, "대안 A: LiveCharts.Wpf 또는 OxyPlot.Wpf와 같은 외부 NuGet 차트 라이브러리 설치 연동.")
add_bullet(doc, "대안 A 기각 사유: .NET 7.0-windows 환경에서 특정 NuGet 패키지가 개발 PC 및 원격 CI/CD 빌드 환경에서 패키지 복원 실패를 야기하거나 호환성 경고를 뿜어낼 가능성이 존재했습니다. 결과적으로 빌드 안정성을 100% 사수하기 위해 WPF 네이티브 드로잉을 채택하였습니다.")
add_bullet(doc, "대안 B: WPF Canvas 및 Polyline/Polygon 네이티브 좌표 변환을 활용한 커스텀 드로잉 직접 구현 (최종 채택).")

add_h2(doc, "리뷰 핵심 포인트 및 보완 내역")
add_bullet(doc, "WPF 브러시 리소스 예외 방지: 윈도우 초기화(Loaded) 시점에 화면에 사용되는 브러시 리소스를 멤버 필드로 일괄 캐싱하고 TryFindResource 기반 폴백 가드를 작동시켰습니다.")
add_bullet(doc, "Canvas 리사이즈 디바운스 최적화: 창 크기가 변할 때(SizeChanged) 마다 유발되는 폭주 렌더링을 막기 위해 30ms 지연 타이머(DispatcherTimer)를 구성하여 크기 변경이 완전히 멈췄을 때 최종 1회만 차트를 렌더링함으로써 CPU 부하 및 가비지 수집 부담을 대폭 개선하였습니다.")
add_bullet(doc, "UX 편의성 보완: 주식 검색이 완료되거나 에러가 났을 때 입력창으로 포커스(Focus)를 되돌림과 동시에 텍스트 전체 선택(SelectAll)을 적용해 사용자가 곧바로 다른 티커를 즉시 키인할 수 있도록 개선하였습니다.")
add_bullet(doc, "수평선 가드 보강: 최고가와 최저가 편차가 전혀 없는 거래정지 종목 등 극단적 케이스에서, 차트 가격 추이선이 바닥에 달라붙지 않고 정확히 캔버스 중간 높이(innerHeight / 2)에 예쁘게 안착되도록 수식을 정비하였습니다.")

# ── 5. 의존성 ─────────────────────────────────────────────────────────────────
add_h1(doc, "5. 의존성")
add_table(doc,
    headers=["라이브러리", "사용 목적", "버전 조건"],
    rows=[
        ["fastapi", "비동기 기반 경량 웹 API 구성 및 HTTP 엔드포인트 라우팅 제공", "최신 안정 버전"],
        ["uvicorn[standard]", "고성능 비동기 ASGI 웹 서버 가동 및 서빙", "standard 패키지 포함"],
        ["yfinance", "미국 시장 주식 및 ETF 관련 메타 정보와 과거 시계열 스크래핑 데이터 획득", "최신 안정 버전"],
        ["pandas", "yfinance의 수치 데이터프레임을 JSON 직렬화가 용이한 형태로 인덱싱 및 가공", "최신 안정 버전"],
        ["pydantic", "FastAPI 입출력 DTO 모델 검증 및 직렬화 스키마 선언", "최신 안정 버전"],
        ["httpx", "FastAPI 로컬 TestClient 상에서 비동기 HTTP 요청 전송 및 모의 검증", "테스트 전용 의존성"],
    ]
)

# ── 6. 테스트 현황 ────────────────────────────────────────────────────────────
add_h1(doc, "6. 테스트 현황")
add_table(doc,
    headers=["테스트 파일 명", "검증 세부 범위", "결과 판정"],
    rows=[
        ["tests/test_api.py", "FastAPI API 서버 헬스체크 및 종목 대소문자 규격화, 형식 오류(400) 가드 검증", "PASS"],
        ["tests/test_api.py", "yfinance 미등록 티커에 대한 404 예외 변환 및 yfinance 내부 예외(502) 포맷 전환 검증", "PASS"],
        ["tests/test_api.py", "과거 히스토리 조회 시 범위(range) 및 주기(interval) 입력 검증 및 prices 반환 필드 무결성 검증", "PASS"],
        ["stock-dashboard.sln 빌드", ".NET 7.0-windows 기반 WPF 클라이언트 아키텍처 완전 빌드 및 리소스 적재 테스트", "PASS (오류 0 / 경고 0)"],
    ]
)
add_paragraph(doc, "총 13개의 백엔드 통합 및 단위 테스트용 자동화 검증 케이스가 FakeProvider 모의 의존성을 통해 외부 네트워크 간섭 없이 100% 로컬 환경에서 통과됨을 입증 완료하였습니다.")

# ── 7. 알려진 한계 및 추후 개선 ──────────────────────────────────────────────
add_h1(doc, "7. 알려진 한계 및 추후 개선")
add_bullet(doc, "외부 API 불안정성 대비: yfinance는 야후 파이낸스 비공식 웹 스크래핑 기반 모듈로, 야후 측의 마크업 개편이나 트래픽 레이트 리밋에 취약합니다. 향후 안정적 상용 서비스를 위해 Redis 등과 연동한 메모리 캐싱 레이어 및 백오프 재시도 큐 시스템 보완이 추천됩니다.")
add_bullet(doc, "차트 시각화 다각화: 현재 MVP 차트는 전일 종가 라인 렌더링에 초점이 맞추어져 있습니다. 백엔드에서 시가/고가/저가/거래량(OHLCV)을 모두 구조화해 리턴하고 있으므로, 추후 프론트엔드 XAML에 캔들스틱 캔버스를 보조로 덧붙여 전환식 캔들 차트를 그리는 확장을 도모할 수 있습니다.")
add_bullet(doc, "클라이언트 편의 기능 고도화: 백엔드를 WPF 실행 시 자동으로 백그라운드 프로세스로 띄워주는 실행 래퍼 기능이나 원클릭 배포 패키지(MSI, ClickOnce) 패키징을 다음 후속 단계에서 수행할 수 있습니다.")

# ── 저장 ──────────────────────────────────────────────────────────────────────
os.makedirs(".ai/docs", exist_ok=True)
doc.save(".ai/docs/init_명세서.docx")
print("생성 완료: .ai/docs/init_명세서.docx")

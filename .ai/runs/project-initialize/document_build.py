import sys
import os
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
        ["기능 이름", "주식 정보 대시보드 및 API 구현 (project_initialize)"],
        ["기능 목적", "WPF와 FastAPI를 연동하여 미국 주식/ETF 데이터를 실시간 조회 및 차트 시각화"],
        ["최종 판정", "PASS"],
        ["최종 완성 일시", "2026-05-27"],
    ]
)

# ── 2. 사용 방법 ──────────────────────────────────────────────────────────────
add_h1(doc, "2. 사용 방법")
add_h2(doc, "API / 인터페이스")
add_bullet(doc, "엔드포인트: GET /api/stocks/{symbol}")
add_bullet(doc, "경로 파라미터 (symbol): 필수, 1~15자 길이의 미국 상장 주식/ETF 티커명")
add_bullet(doc, "쿼리 파라미터 (range_): 선택, 기본값 6mo. 조회할 차트 데이터 범위 (e.g., 1mo, 3mo, 6mo, 1y)")
add_bullet(doc, "쿼리 파라미터 (interval): 선택, 기본값 1d. 차트 봉 간격 (e.g., 1h, 1d, 5d, 1wk)")
add_bullet(doc, "반환값: 주식 시세 요약(quote), 기본 지표(fundamentals), 프로필(profile), 차트 OHLCV 리스트(chart)를 포함한 통합 JSON 응답")

add_h2(doc, "API 호출 예시 (Python)")
add_code_block(doc, """import requests

url = "http://127.0.0.1:8000/api/stocks/QLD"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    print(f"종목명: {data['name']}")
    print(f"현재가: {data['quote']['current_price']} {data['currency']}")
    print(f"시가총액: {data['fundamentals']['market_cap']}")
else:
    print(f"조회 실패: {response.json().get('message', '알 수 없는 오류')}")
""")

add_h2(doc, "WPF API 클라이언트 연동 예시 (C#)")
add_code_block(doc, """using System.Net.Http;
using System.Threading.Tasks;
using Newtonsoft.Json;

public class StockApiClient
{
    private readonly HttpClient _client = new HttpClient();
    private const string BaseUrl = "http://127.0.0.1:8000/api/stocks/";

    public async Task<StockDetailDto> FetchStockAsync(string symbol)
    {
        var response = await _client.GetAsync($"{BaseUrl}{symbol}");
        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadAsStringAsync();
        return JsonConvert.DeserializeObject<StockDetailDto>(json);
    }
}
""")

# ── 3. 관련 파일 ──────────────────────────────────────────────────────────────
add_h1(doc, "3. 관련 파일")
add_table(doc,
    headers=["파일 경로", "역할"],
    rows=[
        ["src/stocks-api/requirements.txt", "백엔드 Python 라이브러리 의존성 정의 파일"],
        ["src/stocks-api/main.py", "FastAPI 웹 서버 진입점, CORS 정책 및 전역 예외 처리 설정"],
        ["src/stocks-api/app/config.py", "호스트, 포트, 타임아웃, range/interval 검증 화이트리스트 등 설정 관리"],
        ["src/stocks-api/app/models/stock.py", "Pydantic v2 기반의 주식 시세/지표/프로필/차트/에러 응답 모델 구조 정의"],
        ["src/stocks-api/app/services/stock_service.py", "yfinance API 호출을 통해 시세 정보를 획득하고 안전하게 예외 처리 및 모델 바인딩"],
        ["src/stocks-api/app/api/stocks.py", "GET /api/stocks/{symbol} 엔드포인트를 노출하고 입력 데이터 검증 및 대문자 정규화 처리"],
        ["src/stocks-dashboard/stocks-dashboard/stocks-dashboard.csproj", "WPF 프로젝트 파일, ScottPlot.WPF 5.x 및 설정 관리 라이브러리 추가"],
        ["src/stocks-dashboard/stocks-dashboard/App.config", "WPF 클라이언트의 API 기본 통신 주소, 타임아웃, 기본 검색 기간 설정 정보"],
        ["src/stocks-dashboard/stocks-dashboard/MainWindow.xaml", "상단 검색 및 주의 안내 바, 좌측 주식 상세 정보 패널, 우측 ScottPlot 차트 영역으로 구성된 다크 테마 마크업"],
        ["src/stocks-dashboard/stocks-dashboard/MainWindow.xaml.cs", "검색 이벤트 비동기 통신 처리, CancellationToken 기반 요청 취소, API 응답 바인딩 및 ScottPlot 캔들스틱 차트 빌드"],
        ["src/stocks-dashboard/stocks-dashboard/Models/StockDetailDto.cs", "백엔드 JSON 응답 스키마와 매핑하기 위한 C# DTO 데이터 구조 정의"],
        ["src/stocks-dashboard/stocks-dashboard/Services/StockApiClient.cs", "HttpClient 싱글톤을 사용하여 FastAPI 서버와 통신하며, 다양한 에러 상태를 한국어 메시지로 변환"],
        ["tests/conftest.py", "yfinance 호출 Mocking을 위한 Fake Ticker 및 API 테스트용 클라이언트 fixture 등록"],
        ["tests/test_api_stocks.py", "백엔드 API 정상 조회, 비정상 입력(400), 존재하지 않음(404), 외부 장애(502) 시뮬레이션 통합 테스트 케이스"]
    ]
)

# ── 4. 주요 설계 결정 ─────────────────────────────────────────────────────────
add_h1(doc, "4. 주요 설계 결정")
add_h2(doc, "구현 접근 방식")
add_paragraph(doc, "외부 API 자격 증명이 없는 개발 및 로컬 테스트 환경을 보장하기 위해 무료로 접근 가능한 yfinance 라이브러리를 데이터 공급원으로 채택했습니다. yfinance가 반환하는 금융 데이터 특유의 공백 값(NaN, Inf, None) 문제를 제어하기 위해, 백엔드 서비스 레이어에 타입 안전 변환 헬퍼(_safe_float, _safe_int, _safe_str)를 적극 활용해 Pydantic v2 데이터 직렬화 실패를 미연에 방지했습니다. WPF 프론트엔드는 신속하고 가독성 높은 차트 렌더링을 위해 ScottPlot.WPF (v5.x)를 의존성으로 추가하고, WpfPlot 컨트롤 내에 OHLC 형식의 데이터를 바인딩하여 줌/드래그가 자유로운 차트를 완성했습니다.")

add_h2(doc, "검토한 대안")
add_bullet(doc, "대안 A: LiveChartsCore.SkiaSharpView.WPF 라이브러리 사용 — 채택하지 않은 이유: 모던한 애니메이션을 지원하나, .NET 8 WPF 환경에서 SkiaSharp 모듈의 의존성 로드 오작동 이슈가 빈번히 보고되었고, 캔들스틱 구현 복잡도가 ScottPlot 대비 매우 높아 초기 빌드 안전성 확보를 위해 제외함.")
add_bullet(doc, "대안 B: 백엔드 로컬 SQLite 캐싱 데이터베이스 도입 — 채택하지 않은 이유: 중복 호출 데이터 로드 성능이 향상되지만, 초기 정보 검색 및 대시보드 화면 구성이라는 요구 범위에 비해 DB 파일 보관, 주기적 갱신 정책 수립 등 관리 복잡성이 지나치게 증가하여 향후 개선 사항으로 보류함.")

add_h2(doc, "리뷰 핵심 포인트와 최종 결정")
add_bullet(doc, "yfinance 외부 장애 발생 시 502 HTTP 응답 누락 지적: conftest.py에 임의로 에러를 던지는 Mock Ticker인 _FailingTicker 셋업을 설계하고, tests/test_api_stocks.py에 test_upstream_history_failure_returns_502 테스트 케이스를 구현하여 502 에러 반환을 정상 보증하였습니다.")
add_bullet(doc, "fetch_stock_detail 함수의 과도한 비대화 개선 권고: yfinance에서 데이터를 적재하고 404 및 데이터 비어있음을 사전 검증하는 비즈니스 영역을 _load_and_validate_ticker_data 프라이빗 함수로 깨끗이 분할하여 단일 책임 원칙을 강화했습니다.")
add_bullet(doc, "WPF 앱 타이틀 영문 표기 개선 제안: MainWindow.xaml의 Window Title 속성을 한국어 정체성에 어울리고 면책 조항을 노출하는 '주식 정보 검색 및 분석 대시보드 (투자 자문 제외)'로 수용 변경하였습니다.")

add_h2(doc, "거부 또는 보류한 지적 사항과 그 이유")
add_bullet(doc, "ScottPlot 5 차트 캔들의 상승/하락 색상 한국 표준 관례(상승 빨강, 하락 파랑) 적용: ScottPlot 5.0.34 버전에서의 캔들스틱 커스텀 색상 부여용 프로퍼티 명세(RisingColor 등)는 프레임워크 내부 마이너 업데이트에 따라 빈번히 파괴되는 비표준 영역입니다. 명확히 검증된 빌드 안전성이 담보되지 않은 상태에서 적용 시 전체 WPF 빌드가 깨질 심각한 위험이 있어, 이번 단계에서는 수용을 거부하고 향후 개선 작업에서 안전성을 검토한 뒤 보강하는 미래 개선 사항으로 안전히 이관했습니다.")

# ── 5. 의존성 ─────────────────────────────────────────────────────────────────
add_h1(doc, "5. 의존성")
add_table(doc,
    headers=["라이브러리", "사용 용도"],
    rows=[
        ["fastapi", "비동기 REST API 호스팅을 위한 백엔드 메인 프레임워크"],
        ["uvicorn", "비동기 ASGI 웹 서버 실행기"],
        ["yfinance", "야후 파이낸스 주식/ETF 실시간 시세 및 6개월 가격 이력 획득 라이브러리"],
        ["pandas", "yfinance의 히스토리 데이터 시계열 DataFrame 가공 및 변환 처리"],
        ["pydantic", "Pydantic v2 스펙 기반 API 입출력 모델링 및 JSON 직렬화 스키마 수립"],
        ["httpx", "비동기 HTTP 요청을 지원하는 라이브러리, 단위 테스트에서 TestClient 구동용"],
        ["pytest", "백엔드 단위 및 비정상 입력/장애 경로 통합 테스트용 자동화 프레임워크"],
        ["ScottPlot.WPF", "WPF UI에서 6개월 일별 OHLCV 데이터를 시각화하는 반응형 대화식 주식 캔들스틱 차트 컴포넌트"],
        ["System.Configuration.ConfigurationManager", "WPF에서 외부 App.config 파일로부터 서버 통신 주소 및 환경 변수를 안정적으로 호출하는 패키지"]
    ]
)

# ── 6. 테스트 현황 ────────────────────────────────────────────────────────────
add_h1(doc, "6. 테스트 현황")
add_table(doc,
    headers=["테스트 파일 경로", "커버하는 검증 범위", "결과"],
    rows=[
        ["tests/test_api_stocks.py", "API 헬스체크 동작 검증 및 엔드포인트 무결성", "PASS"],
        ["tests/test_api_stocks.py", "정상 티커 검색(QLD) 시 전체 JSON 데이터 반환 규격 검증", "PASS"],
        ["tests/test_api_stocks.py", "검색 티커 문자열 대소문자 정규화 및 공백 전처리 확인", "PASS"],
        ["tests/test_api_stocks.py", "티커 길이 초과(15자 이상) 또는 허용 외 특수문자 입력 시 400 에러 처리", "PASS"],
        ["tests/test_api_stocks.py", "허용되지 않은 잘못된 range 또는 interval 쿼리 파라미터 호출 시 400 에러", "PASS"],
        ["tests/test_api_stocks.py", "존재하지 않는 티커 또는 가격 데이터가 유실된 티커 요청 시 404 에러 구조화 응답", "PASS"],
        ["tests/test_api_stocks.py", "yfinance 외부 시세 엔진 연동 장애 발생 시 502 Bad Gateway 에러 및 구조 메시지 반환", "PASS"],
        ["WPF 컴파일 빌드 검증", "dotnet build 명령 기반 WPF 대시보드 솔루션 정상 컴파일", "PASS"]
    ]
)

# ── 7. 알려진 한계 및 추후 개선 ──────────────────────────────────────────────
add_h1(doc, "7. 알려진 한계 및 추후 개선")
add_bullet(doc, "실시간 실시간 스트리밍 시세 미지원: 현재 구조는 검색 및 수동 새로고침 기반의 REST API 조회 구조입니다. 추후 WebSocket 또는 폴링 기반 실시간 체결 기능 확장이 필요합니다.")
add_bullet(doc, "ScottPlot 차트 상승/하락 캔들 색상의 로컬 미조율: 현재 라이브러리 기본값인 글로벌 스타일로 노출됩니다. 향후 WPF용 정확한 ScottPlot 5 캔들 스타일 API 안정성을 검토 후 한국형 빨강/파랑 색상 커스텀 스타일을 입힐 예정입니다.")
add_bullet(doc, "해외 시장 및 티커 포맷 제약: 미국 상장 주식 및 ETF를 최우선 지원하며, 한국 등 타 시장 조회를 위해서는 접미사 입력을 우아하게 제어하는 마켓 선택 전처리 UI 고도화가 요구됩니다.")
add_bullet(doc, "Rate Limit 및 속도 완화 캐싱의 부재: 동일 티커의 중복 요청 시에도 매번 yfinance를 호출하여 성능 지연 및 IP 차단 위험이 있습니다. 차후 인메모리 Redis 캐시 또는 LRU 캐시 계층 도입을 추천합니다.")

# ── 저장 ──────────────────────────────────────────────────────────────────────
os.makedirs(".ai/docs", exist_ok=True)
doc.save(".ai/docs/project-initialize_명세서.docx")
print("생성 완료: .ai/docs/project-initialize_명세서.docx")

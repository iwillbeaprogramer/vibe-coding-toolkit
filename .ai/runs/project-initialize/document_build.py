from __future__ import annotations

import os
import sys

sys.path.insert(0, ".ai/templates")

from docx_helper import (  # noqa: E402
    add_bullet,
    add_code_block,
    add_h1,
    add_h2,
    add_paragraph,
    add_table,
    create_doc,
)


DOCX_PATH = ".ai/docs/project-initialize_명세서.docx"


def buildDocument() -> None:
    doc = create_doc()

    add_h1(doc, "1. 개요")
    add_table(
        doc,
        headers=["항목", "내용"],
        rows=[
            ["기능 이름", "주식 정보 조회 앱 초기 구성"],
            [
                "기능 목적",
                "Windows 로컬 환경에서 React 화면과 FastAPI 백엔드를 통해 주식 및 ETF 검색, 상세 지표, 가격 차트를 조회한다.",
            ],
            ["최종 판정", "PASS"],
            ["최종 완성 일시", "2026-05-28"],
        ],
    )
    add_paragraph(
        doc,
        "완성된 기능은 별도 API 키 없이 Yahoo Finance 계열 데이터를 조회하는 개발 모드 애플리케이션이다. "
        "검색, 상세 조회, 차트 표시, 오류 및 로딩 상태, 투자 조언이 아니라는 안내를 포함한다.",
    )

    add_h1(doc, "2. 사용 방법")
    add_h2(doc, "API / 인터페이스")
    add_table(
        doc,
        headers=["구분", "내용"],
        rows=[
            ["상태 확인", "GET /api/health -> { status: ok }"],
            ["종목 검색", "GET /api/search?q=QLD -> SearchResult 배열"],
            ["상세 조회", "GET /api/stock/{ticker}?period=1mo -> StockDetailResponse"],
            ["기간 값", "1d, 1mo, 6mo, 1y, 5y"],
            ["오류 처리", "입력 오류 400, 종목 없음 404, 외부 공급자 오류 502 또는 503"],
        ],
    )
    add_h2(doc, "응답 데이터 요약")
    add_bullet(doc, "검색 결과는 symbol, name, exchange, assetType, currency 필드를 제공한다.")
    add_bullet(
        doc,
        "상세 응답은 기본 정보, price, fundamentals, etf, chart, period, provider 블록으로 구성된다.",
    )
    add_bullet(doc, "차트 포인트는 date, open, high, low, close, volume을 포함하며 일부 값은 null일 수 있다.")
    add_h2(doc, "호출 예시")
    add_code_block(
        doc,
        "import requests\n\n"
        "base_url = \"http://127.0.0.1:8000\"\n"
        "search = requests.get(f\"{base_url}/api/search\", params={\"q\": \"QLD\"})\n"
        "print(search.json())\n\n"
        "detail = requests.get(f\"{base_url}/api/stock/QLD\", params={\"period\": \"1mo\"})\n"
        "payload = detail.json()\n"
        "print(payload[\"symbol\"], payload[\"price\"][\"currentPrice\"], len(payload[\"chart\"]))",
    )
    add_h2(doc, "입력 / 출력 예시")
    add_table(
        doc,
        headers=["입력", "대표 출력"],
        rows=[
            ["검색어 QLD", "QLD, ProShares Ultra QQQ, NYSEARCA, ETF, USD"],
            ["상세 조회 QLD / 1mo", "현재가, 전일 종가, 거래량, ETF 비용 정보, 1개월 차트 포인트 배열"],
            ["잘못된 기간 값", "400 상태와 지원하지 않는 차트 기간 메시지"],
            ["없는 종목", "404 상태와 종목을 찾을 수 없다는 메시지"],
        ],
    )

    add_h1(doc, "3. 관련 파일")
    add_table(
        doc,
        headers=["파일 경로", "역할"],
        rows=[
            ["src/backend/main.py", "FastAPI 앱, CORS, 헬스 체크, 검색 및 상세 조회 라우터를 정의한다."],
            ["src/backend/schemas.py", "검색 결과, 가격 요약, 재무 지표, ETF 지표, 차트 포인트 응답 모델을 정의한다."],
            ["src/backend/services.py", "Yahoo Finance 검색, yfinance 상세 조회, 입력 검증, 캐시, 데이터 변환을 담당한다."],
            ["src/backend/requirements.txt", "백엔드 실행 및 테스트에 필요한 Python 의존성을 고정 범위로 기록한다."],
            ["src/frontend/src/App.tsx", "선택 종목과 기간 상태, 상세 조회, 로딩 및 오류 표시를 제어한다."],
            ["src/frontend/src/api.ts", "프론트엔드에서 백엔드 API를 호출하는 fetch 래퍼를 제공한다."],
            ["src/frontend/src/types.ts", "백엔드 응답과 차트 기간에 대응하는 TypeScript 타입을 정의한다."],
            ["src/frontend/src/components/SearchBar.tsx", "종목 검색 입력, 자동완성, 직접 조회, 키보드 탐색을 제공한다."],
            ["src/frontend/src/components/StockDetail.tsx", "가격, 지표, ETF 정보, 데이터 없음 상태를 카드 형태로 렌더링한다."],
            ["src/frontend/src/components/StockChart.tsx", "기간 선택과 Recharts 기반 가격 차트를 렌더링한다."],
            ["src/frontend/src/components/Disclaimers.tsx", "투자 조언이 아니라는 고지와 데이터 지연 가능성을 안내한다."],
            ["src/frontend/src/index.css", "전체 화면 레이아웃, 검색 패널, 상세 카드, 차트, 상태 배지를 스타일링한다."],
            ["tests/backend/test_api.py", "백엔드 API 정상 응답, 오류 매핑, 1일 차트 타임스탬프 보존을 검증한다."],
            ["tests/frontend/App.test.tsx", "프론트엔드 로딩, 오류, 검색 입력, 자동완성, 중립 배지를 검증한다."],
            ["tests/conftest.py", "테스트에서 프로젝트 루트를 import 경로에 추가한다."],
            ["tests/frontend/setup.ts", "Vitest와 testing-library 테스트 환경을 초기화한다."],
        ],
    )

    add_h1(doc, "4. 주요 설계 결정")
    add_h2(doc, "구현 접근 방식")
    add_paragraph(
        doc,
        "백엔드는 FastAPI 라우터와 서비스 계층으로 분리하고, Yahoo Finance autocomplete API와 yfinance를 조합했다. "
        "외부 데이터 공급자의 지연과 누락을 전제로 5분 메모리 캐시, 명시적 입력 검증, HTTP 오류 매핑을 적용했다.",
    )
    add_paragraph(
        doc,
        "프론트엔드는 Vite + React + TypeScript 단일 화면으로 구성했다. 첫 화면을 마케팅 페이지가 아니라 검색과 상세 정보 중심의 작업 화면으로 만들고, Recharts로 기간별 가격 차트를 표시한다.",
    )
    add_h2(doc, "검토했지만 채택하지 않은 대안")
    add_bullet(
        doc,
        "Alpha Vantage 또는 Finnhub 같은 키 기반 공식 API: JSON 품질은 좋지만 사용자가 별도 키를 준비해야 하고 무료 한도가 좁아 초기 로컬 실행 목표와 맞지 않았다.",
    )
    add_bullet(
        doc,
        "Electron 또는 Neutralinojs 패키징: 완성형 Windows 실행 파일에는 유리하지만 초기 범위에서는 번들 크기와 빌드 복잡도가 커 개발 모드 실행에 집중했다.",
    )
    add_bullet(
        doc,
        "루트 배치 실행 파일: 계획 단계에는 있었지만 현재 write policy가 루트 산출물 생성을 제한하므로 만들지 않고 보류했다.",
    )
    add_h2(doc, "위험 구간과 완화")
    add_bullet(doc, "무료 데이터 공급자는 지연, 누락, 차단 가능성이 있어 provider note와 지연 플래그, 오류 배너, 재시도 흐름을 제공한다.")
    add_bullet(doc, "주식과 ETF의 필드 차이를 고려해 상세 지표 대부분을 Optional로 정의하고 화면에서는 데이터 없음 상태로 표시한다.")
    add_bullet(doc, "외부 호출 부담을 줄이기 위해 검색어 및 상세 조회 결과를 300초 동안 메모리에 캐시한다.")
    add_h2(doc, "리뷰 핵심 포인트와 최종 결정")
    add_bullet(doc, "1일 차트의 5분봉 시간이 날짜로만 축약되던 문제를 수정해 장중 데이터는 ISO timestamp를 보존한다.")
    add_bullet(doc, "빠른 종목 또는 기간 전환 시 이전 요청의 finally가 최신 로딩 상태를 덮지 않도록 요청 ID와 active guard를 적용했다.")
    add_bullet(doc, "자동완성 패널은 바깥 클릭과 Escape로 닫히며, ArrowUp, ArrowDown, Enter 키 선택과 ARIA 속성을 지원한다.")
    add_bullet(doc, "가격 변동 데이터가 없을 때 상승 배지가 보이지 않도록 neutral 상태와 스타일을 추가했다.")
    add_h2(doc, "거부 또는 보류 항목")
    add_bullet(doc, "루트 run.bat 생성은 현재 단계의 쓰기 정책과 프로젝트 계약을 우선해 보류했다.")
    add_bullet(doc, "정식 exe 패키징, 로그인, 포트폴리오 관리, 주문 기능은 원래 범위를 벗어나 후속 개선으로 분리했다.")

    add_h1(doc, "5. 의존성")
    add_table(
        doc,
        headers=["라이브러리", "용도"],
        rows=[
            ["fastapi", "백엔드 HTTP API 프레임워크"],
            ["uvicorn", "FastAPI 개발 서버 실행"],
            ["yfinance", "종목 상세 정보와 기간별 가격 이력 조회"],
            ["pydantic", "백엔드 응답 스키마와 타입 검증"],
            ["requests", "Yahoo Finance autocomplete API 호출"],
            ["pytest, httpx", "백엔드 API 테스트"],
            ["react, react-dom", "프론트엔드 화면 렌더링"],
            ["typescript, vite, @vitejs/plugin-react", "프론트엔드 개발 서버, 타입 검사, 빌드"],
            ["recharts", "가격 차트 시각화"],
            ["lucide-react", "검색, 추세, 상태 표시 아이콘"],
            ["vitest, jsdom, testing-library", "프론트엔드 컴포넌트 테스트"],
        ],
    )

    add_h1(doc, "6. 테스트 현황")
    add_table(
        doc,
        headers=["테스트 파일 또는 명령", "커버 범위", "최종 결과"],
        rows=[
            [
                "python -m py_compile src\\backend\\__init__.py src\\backend\\main.py src\\backend\\schemas.py src\\backend\\services.py",
                "백엔드 Python 문법 검증",
                "PASS",
            ],
            ["pytest tests\\backend", "검색, 상세 조회, 404, 502, 1일 장중 timestamp 보존", "PASS, 6 passed"],
            ["npm test -- --run (src/frontend)", "로딩, API 실패, 입력 방어, 직접 조회, 자동완성 닫기와 키보드 선택, neutral 배지", "PASS, 7 passed"],
            ["npm run build (src/frontend)", "TypeScript 검사와 Vite 프로덕션 빌드", "PASS"],
            ["하네스 latest verification JSON", "하네스 검증 명령", "PASS"],
        ],
    )
    add_paragraph(
        doc,
        "04_fix 단계에서 장중 차트 timestamp 보존, 자동완성 접근성, 데이터 없음 neutral 표시 테스트가 추가되었다. "
        "05_verify 단계에서는 기존 테스트 13개가 모두 통과한 것으로 기록되었다.",
    )

    add_h1(doc, "7. 알려진 한계 및 추후 개선")
    add_bullet(doc, "Yahoo Finance 및 yfinance 기반 구현이므로 실시간성, 데이터 완전성, 호출 안정성을 보장하지 않는다.")
    add_bullet(doc, "정식 Windows exe 패키징과 루트 실행 배치 파일은 현재 산출물 범위에 포함되지 않았다.")
    add_bullet(doc, "차트 번들 크기 경고가 있어 후속 단계에서 code splitting 또는 차트 라이브러리 전략을 검토할 수 있다.")
    add_bullet(doc, "ETF 레버리지와 상품 설명은 공급자 필드가 제한적이어서 가능한 값만 표시한다.")
    add_bullet(doc, "현재 구현은 정보 조회용이며 매수, 매도, 포트폴리오 관리, 알림 기능은 제공하지 않는다.")

    os.makedirs(".ai/docs", exist_ok=True)
    doc.save(DOCX_PATH)
    print(f"생성 완료: {DOCX_PATH}")


if __name__ == "__main__":
    buildDocument()

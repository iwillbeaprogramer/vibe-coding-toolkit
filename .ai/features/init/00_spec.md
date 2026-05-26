# 00_spec - init

작성: Codex
일시: 2026-05-26

## 기능 목표
- Windows WPF 데스크톱 앱에서 사용자가 주식/ETF 티커를 검색하면 Python FastAPI 백엔드가 시장 데이터와 상세 지표를 제공하고, WPF 화면이 주요 정보와 가격 차트를 보여준다.
- 첫 구현 범위는 API 키 없이 실행 가능한 로컬 MVP로 잡고, 종목 검색, 상세 정보 조회, 차트 데이터 조회, 오류 표시까지 개발 가능한 수준으로 확정한다.

## 기능명
- feature_name: init
- naming_reason: 하네스에서 `feature_name_locked: true`로 제공된 이름이므로 사용자 요청 기반으로 새 slug를 만들지 않고 `init`을 유지한다.

## 구체적 요구사항
- WPF 앱은 `src/stock-dashboard/stock-dashboard.sln`의 기존 WPF 프로젝트를 기반으로 구현한다.
- 사용자는 티커 입력창에 `QLD`, `AAPL`, `MSFT` 같은 미국 상장 주식/ETF 심볼을 입력하고 검색 버튼 또는 Enter 키로 조회할 수 있어야 한다.
- 검색 입력은 앞뒤 공백을 제거하고 대문자로 정규화한다.
- 빈 입력은 백엔드 호출 없이 WPF 화면에 사용자 친화적인 검증 메시지를 표시한다.
- FastAPI 백엔드는 로컬 HTTP API로 제공한다. 기본 주소는 개발 환경 기준 `http://127.0.0.1:8000`으로 한다.
- FastAPI 백엔드는 최소 다음 엔드포인트를 제공한다.
  - `GET /health`: 백엔드 실행 상태 확인
  - `GET /api/stocks/{symbol}/summary`: 종목 요약, 현재가, 전일 종가, 시가, 고가, 저가, 거래량, 시가총액, 통화, 거래소, 회사/펀드명, 섹터/산업 가능 시 반환
  - `GET /api/stocks/{symbol}/history?range=1mo&interval=1d`: 차트용 OHLCV 시계열 반환
- 기본 데이터 공급원은 API 키가 필요 없는 Python `yfinance`로 한다. 단, 비공식 데이터 공급원이므로 응답 실패/누락 가능성을 명시적으로 처리한다.
- 백엔드는 외부 데이터 조회 실패, 알 수 없는 티커, 데이터 없음, 네트워크 실패를 구분 가능한 오류 응답으로 반환한다.
- WPF 앱은 요약 정보 영역에 최소 현재가, 전일 종가, 등락액, 등락률, 시가, 당일 고가/저가, 거래량, 평균 거래량 가능 시, 시가총액 가능 시, 52주 고가/저가 가능 시를 표시한다.
- WPF 앱은 차트 영역에 선택된 기간의 가격 추이를 표시한다.
- 차트는 첫 범위에서 종가 라인 차트를 기본으로 하고, 백엔드 응답에는 향후 캔들 차트 확장을 위해 open/high/low/close/volume을 포함한다.
- WPF 앱은 조회 중 로딩 상태를 표시하고 중복 검색을 방지한다.
- WPF 앱은 백엔드 미실행, 네트워크 실패, 잘못된 티커, 데이터 없음 상태를 화면에서 구분해 안내한다.
- WPF 앱은 백엔드 URL을 코드 상수 또는 설정 파일로 분리해 이후 변경 가능하게 한다.
- 구현 후 최소 검증은 백엔드 단위 테스트, API 응답 형태 테스트, WPF 빌드 검증을 포함한다.

## 이번 범위에서 제외하는 것
- 실시간 스트리밍 시세: 초기 MVP는 요청 시점 조회와 과거 시계열 조회로 제한한다. 실시간 스트리밍은 데이터 공급원/요금제/사용량 정책 결정이 필요하다.
- 매수/매도 주문, 포트폴리오 관리, 로그인, 사용자 계정: 주식 정보 조회 기능과 별도 도메인이며 보안/데이터 저장 범위가 커진다.
- 유료 데이터 공급원 연동: API 키와 계약 조건이 필요하므로 첫 범위에서는 제외한다.
- 국내 주식 전용 검색/표시: 사용자 예시가 `QLD`이고 기존 요구가 WPF/FastAPI 구조 중심이므로 미국 상장 심볼을 기본 대상으로 한다.
- 배포 패키징/설치 프로그램 생성: 초기 기능 구현과 검증 이후 별도 단계에서 다룬다.
- 투자 자문 문구 또는 추천 로직: 본 기능은 정보 표시 도구이며 투자 판단을 자동화하지 않는다.

## 입력과 출력
- 입력 형태:
  - WPF 검색창의 문자열 티커 심볼
  - 허용 기본 범위: 영문 대문자/소문자, 숫자, 점(`.`), 하이픈(`-`)을 포함한 1~15자 심볼
  - 기간 파라미터 기본값: `range=1mo`
  - 인터벌 파라미터 기본값: `interval=1d`
- 정상 출력:
  - WPF 화면에는 종목 헤더, 주요 가격 지표, 상세 지표, 차트가 표시된다.
  - 백엔드 `summary` 응답은 JSON 객체로 종목 메타데이터와 주요 숫자 지표를 반환한다.
  - 백엔드 `history` 응답은 JSON 객체로 심볼, 기간, 인터벌, OHLCV 배열을 반환한다.
- 비정상 입력/오류 처리:
  - 빈 입력: WPF에서 즉시 검증 메시지 표시
  - 허용 문자/길이 위반: WPF 또는 백엔드에서 400 계열 오류 처리
  - 존재하지 않거나 데이터가 없는 심볼: 백엔드 404 계열 응답, WPF에서 "데이터를 찾을 수 없음" 메시지 표시
  - 외부 데이터 공급원 장애: 백엔드 502/503 계열 응답, WPF에서 재시도 가능한 오류로 표시
  - 예상치 못한 오류: 백엔드에서 구조화된 오류 응답 반환, WPF에서 일반 오류 메시지 표시

## 기존 코드 영향
- 현재 확인된 기존 프로덕션 코드:
  - `src/stock-dashboard/stock-dashboard.sln`
  - `src/stock-dashboard/stock-dashboard/stock-dashboard.csproj`
  - `src/stock-dashboard/stock-dashboard/MainWindow.xaml`
  - `src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs`
  - `src/stock-dashboard/stock-dashboard/App.xaml`
  - `src/stock-dashboard/stock-dashboard/App.xaml.cs`
- 기존 WPF 화면은 빈 `Grid` 상태이므로 메인 화면 XAML과 코드비하인드 또는 MVVM 구조 추가가 필요하다.
- FastAPI 백엔드는 아직 존재하지 않으므로 `src/` 하위에 Python 백엔드 디렉터리를 새로 추가하는 계획이 필요하다.
- 테스트 디렉터리 `tests/`는 현재 확인되지 않았으므로 다음 단계에서 백엔드 테스트 위치를 루트 `tests/` 하위로 계획한다.
- 현재 작업 트리에는 하네스/프리셋 파일과 이전 `stocks-dashboard` 경로 삭제 및 `stock-dashboard` 경로 추가가 이미 존재한다. 이 단계에서는 기존 변경을 되돌리지 않는다.
- 충돌 가능성은 낮지만, 프로젝트 이름이 `stock-dashboard`이고 네임스페이스가 `stock_dashboard`인 점을 이후 계획에서 일관되게 다뤄야 한다.

## 기술적 제약
- 프론트엔드는 기존 WPF/.NET 프로젝트를 유지한다.
- 현재 WPF 프로젝트의 TargetFramework는 `net7.0-windows`이다. 별도 지시가 없으므로 다음 단계에서 이 버전을 유지하는 계획을 우선한다.
- 백엔드는 Python FastAPI로 구현한다.
- 기본 데이터 조회 라이브러리는 `yfinance`로 한다. 이유는 API 키 없이 빠르게 로컬 MVP를 만들 수 있기 때문이다.
- 차트 표시에는 WPF에서 사용할 수 있는 NuGet 차트 라이브러리 또는 경량 커스텀 렌더링 중 기존 프로젝트 적합성을 보고 선택한다. 외부 의존성 추가가 예상되므로 계획 단계에서 명시한다.
- WPF와 FastAPI는 HTTP JSON으로 통신한다.
- 외부 입력, 네트워크 실패, 프로세스 실행 실패는 명시적으로 처리해야 한다.
- 새 프로덕션 코드는 루트 `src/` 하위에만 둔다.
- 새 테스트 코드는 루트 `tests/` 하위에만 둔다.
- Git commit, reset, checkout, rebase, push는 모델이 실행하지 않는다.

## 위험도 및 게이트
- risk_level: high
- human_gate_required: true
- human_gate_reason: 새 FastAPI 백엔드와 외부 데이터 조회 라이브러리, WPF 차트 의존성 추가 가능성이 있고 사용자 경험에 직접 영향을 주는 데이터 표시 정책을 확정해야 하므로 사람 승인 게이트를 유지한다.

## 사용자 확인 사항
- defaults_mode가 true이므로 추가 질문 없이 권장 기본값으로 스펙을 확정했다.
- 기본 결정:
  - 미국 상장 주식/ETF 티커를 1차 대상으로 한다. 이유: 사용자 예시가 `QLD`이고 API 키 없는 데이터 조회가 현실적이다.
  - 데이터 공급원은 `yfinance`로 시작한다. 이유: 별도 자격 증명 없이 개발/검증 가능하다.
  - 첫 차트는 종가 라인 차트로 구현하고 OHLCV 데이터를 함께 반환한다. 이유: MVP 구현 난이도를 낮추면서 캔들 차트 확장 여지를 남긴다.
  - 백엔드는 로컬 `127.0.0.1:8000`에서 실행되는 FastAPI 서비스로 둔다. 이유: WPF와 Python 백엔드 분리가 명확하고 개발 중 검증이 쉽다.
  - 기능명은 `init`으로 유지한다. 이유: 하네스가 feature_name_locked로 고정했다.

## 단계 결과
- status: PASS
- next_stage: 01_plan
- human_gate_required: true
- blocking_reason: 없음
- risk_level: high
- produced_files:
  - .ai/features/init/00_spec.md
  - .ai/features/init/00_spec.result.json
- changed_files:
  - .ai/features/init/00_spec.md
  - .ai/features/init/00_spec.result.json
- commit_created: false
- commit_message:
- model_mismatch: false
- actual_model: Codex

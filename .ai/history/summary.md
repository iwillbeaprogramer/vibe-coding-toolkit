# 프로젝트 히스토리

로컬 하네스가 자동 생성한 장기 기록 요약입니다.

- 기록된 run: 1
- 열린 리스크 / 미래 개선점: 25
- 열린/보류 미해결 항목: 37

## 최근 완료 Run

- 2026-05-26T23:16:59 initial-project (full, complete, verify=PASS)
  - WPF 클라이언트와 Python FastAPI 백엔드로 구성된 주식/ETF 상세 조회 애플리케이션의 초기 스펙을 확정했다.
  - 검색 입력, 백엔드 응답 구조, 표시 지표, 차트 범위, 오류 처리, 제외 범위를 정의했다.
  - WPF(.NET 8) 및 FastAPI 프로젝트 구조 설계

## 열린 리스크와 후속 개선점

- [low] 무료 금융 데이터 공급처(yfinance)의 레이트 리밋 및 일시적인 응답 지연 가능성 (from initial-project)
- [low] WPF 차트 라이브러리(LiveCharts2) 렌더링 성능 및 호환성 -> 비동기 데이터 바인딩 및 안전한 데이터 초기화 적용 (from initial-project)
- [low] yfinance가 비공식 스크래핑 기반이라 Yahoo의 변경/차단에 영향을 받을 수 있다. 현재는 예외 변환 + 사용자 메시지로만 완화했고 캐시 레이어는 미도입. (from initial-project)
- [low] 외부 금융 데이터 공급자 의존성과 사용량 제한, 지연 시세, 필드 누락 가능성이 있다. (from initial-project)
- [low] Default machine dotnet SDK is 7.0.401, so net8.0-windows frontend verification requires .NET 8 SDK. (from initial-project)
- [low] 수정한 파일과 변경 내용: (from initial-project)
- [low] Live yfinance data remains externally dependent and can be rate-limited or temporarily unavailable. (from initial-project)
- [low] yfinance API 호출에 명시적 타임아웃 한계가 없어 야후 파이낸스 측 서비스 불통 시 백엔드가 blocking 되어 Hang 상태에 빠질 수 있는 위험 (from initial-project)
- [low] 출처: 03_review (from initial-project)
- [low] LiveCharts2 의존성이 `2.0.0-rc2` 프리릴리스 버전이라 향후 API 변동 가능성이 있다. (from initial-project)
- [low] `concurrent.futures` 모듈 import 추가, 상수 `_UPSTREAM_TIMEOUT_SECONDS = 6.0` 정의 (from initial-project)
- [low] 사용자가 빠르게 검색어를 변경하여 검색 요청이 취소될 때, 백엔드 타임아웃으로 오해해 UI에 에러를 발생시키는 예외 처리 결함 (from initial-project)
- [low] 왜 수용했는가: WPF 클라이언트 측 HttpClient 타임아웃(10초)보다 짧은 6초 상한을 두어, 외부 장애 시에도 백엔드가 502로 빠르게 응답하고 클라이언트의 일반 실패 분기에서 사용자 피드백이 가능해짐. yfinance가 자체 timeout 인자를 노출하지 않아 워커 스레드 + 미래 결과 기반 타임아웃이 가장 침습이 적은 표준 패턴 (from initial-project)
- [low] 프론트엔드 xUnit 테스트는 로컬 dotnet 7만 설치되어 04_fix 단계에서 실행하지 못했고 05_verify 단계의 .NET 8 SDK 환경에 실행을 의존함 (from initial-project)
- [low] `src/stock_api/services/finance_service.py`: (from initial-project)
- [low] 본 실행 환경에 .NET 7 SDK만 설치돼 WPF 프로젝트 빌드/테스트는 다음 단계에서 .NET 8 환경으로 재검증 필요. (from initial-project)
- [low] LiveCharts2 프리릴리스(rc2) 버전에 따른 향후 API 변동성 (from initial-project)
- [low] 지적 내용 요약: yfinance 동기 호출에 네트워크 타임아웃 제어가 없어 야후 측 장애 시 백엔드가 무한 대기 가능 (from initial-project)
- [low] 초기 프로젝트 생성과 새 외부 의존성 도입 가능성이 있어 위험도를 high로 판단했다. (from initial-project)
- [low] WPF UI에서 두 번째 검색 시 차트가 최초 검색 차트에서 전혀 갱신되지 않는 치명적인 데이터 불일치 오류 존재 (from initial-project)
- [low] yfinance 워커 스레드 타임아웃은 결과만 포기할 뿐 실제 백그라운드 스레드는 계속 실행되므로, 야후 측 장기 행 상황이 지속되면 스레드가 누적될 수 있음 (단발 검색 부하 수준에서는 무시 가능) (from initial-project)
- [low] severity: MINOR (from initial-project)
- [low] 기존 `_default_loader`의 yfinance 직접 호출 로직을 신규 모듈 함수 `_fetch_from_yfinance`로 추출 (from initial-project)
- [low] yfinance 라이브러리의 임시 차단 및 API 스크래핑 제약 가능성 -> 적절한 타임아웃과 예외 처리 적용 (from initial-project)
- [low] `_default_loader`는 `concurrent.futures.ThreadPoolExecutor(max_workers=1)`로 `_fetch_from_yfinance`를 제출하고 `future.result(timeout=_UPSTREAM_TIMEOUT_SECONDS)`로 결과 대기. `TimeoutError` 발생 시 `UpstreamDataError("데이터 공급처 응답이 지연되었습니다.", detail="ups... (from initial-project)

## 미해결 리뷰/검증 항목

- [open/minor] **어떻게 개선해야 하는지**: (from initial-project:03_review)
- [open/minor] **왜 문제인지**: (from initial-project:03_review)
- [open/minor] 수정한 파일과 변경 내용: (from initial-project:04_fix)
- [open/minor] 백엔드 서비스 레이어 호출부(예: uvicorn 비동기 스레드 풀 구동 구간)를 `asyncio.wait_for`로 감싸서 특정 시간(예: 6초) 이상 지연 시 `UpstreamDataError`를 반환하도록 안전 패널티를 부여하거나, yfinance가 커스텀 requests Session을 주입할 수 있게 구조를 제공하므로 기본 세션에 타임아웃 헤더를 주입해 실행하도록 설정해야 합니다. (from initial-project:03_review)
- [open/minor] **해당 코드 위치**: [finance_service.py:L93-L95](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock_api/services/finance_service.py#L93-L95) (from initial-project:03_review)
- [open/minor] 윈도우 Unloaded 이벤트 또는 Dispose 패턴을 적용하여 이벤트 리스너를 명시적으로 해제해주는 클린 코드 표준을 장려합니다. (`_viewModel.PropertyChanged -= OnViewModelPropertyChanged;`) (from initial-project:03_review)
- [open/minor] severity: MINOR (from initial-project:04_fix)
- [open/minor] 왜 수용했는가: WPF 클라이언트 측 HttpClient 타임아웃(10초)보다 짧은 6초 상한을 두어, 외부 장애 시에도 백엔드가 502로 빠르게 응답하고 클라이언트의 일반 실패 분기에서 사용자 피드백이 가능해짐. yfinance가 자체 timeout 인자를 노출하지 않아 워커 스레드 + 미래 결과 기반 타임아웃이 가장 침습이 적은 표준 패턴 (from initial-project:04_fix)
- [open/medium] 프론트엔드 xUnit 테스트의 .NET 8 환경 실행 (05_verify 단계에서 검증 예정) (from initial-project:04_fix)
- [open/minor] severity: NIT (from initial-project:04_fix)
- [open/minor] 기존 `_default_loader`의 yfinance 직접 호출 로직을 신규 모듈 함수 `_fetch_from_yfinance`로 추출 (from initial-project:04_fix)
- [open/minor] `src/stock_api/services/finance_service.py`: (from initial-project:04_fix)
- [open/medium] 비동기 검색 연속 클릭에 따른 예외 오진 및 UI 타임아웃 배너 노출 버그 (04_fix 단계에서 최우선 수정 필요) (from initial-project:03_review)
- [open/minor] `yfinance` 라이브러리는 자체 `requests` 세션을 통해 야후 파이낸스 웹 API를 동기적으로 호출합니다. 만약 야후 파이낸스 측 서버 장애나 레이트 리밋, 네트워크 병목 현상이 생길 경우, 명시적인 타임아웃 설정이 없어 백엔드가 무한정 혹은 매우 오랫동안 대기(Block) 상태에 빠질 수 있으며, 이는 곧 WPF 클라이언트 측 10초 타임아웃 및 전체 API 서비스 마비로 이어집니다. (from initial-project:03_review)
- [open/medium] 구체적인 금융 데이터 공급자와 차트 라이브러리는 01_plan 단계에서 확정해야 한다. (from initial-project:00_specify)
- [open/medium] 무료 데이터 공급자의 지연 시세 및 요청 제한 정책은 구현 전 확인이 필요하다. (from initial-project:00_specify)
- [open/medium] 백엔드 yfinance 호출 시 동기식 blocking 지연 제어 한계 보강 과제 (from initial-project:03_review)
- [open/minor] **해당 코드 위치**: [MainWindow.xaml.cs:L22](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml.cs#L22) (from initial-project:03_review)
- [open/minor] `concurrent.futures` 모듈 import 추가, 상수 `_UPSTREAM_TIMEOUT_SECONDS = 6.0` 정의 (from initial-project:04_fix)
- [open/medium] WPF 차트 최초 렌더링 이후 재검색 시 차트 갱신 불가 버그 (04_fix 단계에서 최우선 수정 필요) (from initial-project:03_review)
- [open/minor] 지적 내용 요약: yfinance 동기 호출에 네트워크 타임아웃 제어가 없어 야후 측 장애 시 백엔드가 무한 대기 가능 (from initial-project:04_fix)
- [open/minor] **지적 사항**: 백엔드에서 `yfinance` API 호출 시 명시적인 네트워크 타임아웃 제어 장치가 없습니다. (from initial-project:03_review)
- [open/medium] WPF 빌드/실행 및 E2E(WPF↔FastAPI) 통합 동작은 .NET 8 SDK 환경에서 검증 단계(03_review 또는 후속)에 확인 필요. (from initial-project:02_develop)
- [open/minor] 출처: 03_review (from initial-project:04_fix)
- [open/minor] `_default_loader`는 `concurrent.futures.ThreadPoolExecutor(max_workers=1)`로 `_fetch_from_yfinance`를 제출하고 `future.result(timeout=_UPSTREAM_TIMEOUT_SECONDS)`로 결과 대기. `TimeoutError` 발생 시 `UpstreamDataError("데이터 공급처 응답이 지연되었습니다.", detail="ups... (from initial-project:04_fix)
- [open/minor] 메인 윈도우 단일 구조 앱이라 윈도우 수명과 앱 수명이 같아 실질적인 메모리 누수 피해는 미미하지만, 다중 윈도우 전환이나 탭 구조 전환 등 확장될 경우 뷰모델의 이벤트 강한 참조로 인해 가비지 컬렉터(GC) 수집에서 윈도우가 누수되는 표준 설계 위배 사항입니다. (from initial-project:03_review)
- [open/minor] **지적 사항**: 뷰모델 PropertyChanged 이벤트의 명시적 구독 해제가 빠져 있습니다. (from initial-project:03_review)
- [deferred/minor] `concurrent.futures` 모듈 import 추가, 상수 `_UPSTREAM_TIMEOUT_SECONDS = 6.0` 정의 (from initial-project:04_fix)
- [deferred/minor] severity: MINOR (from initial-project:04_fix)
- [deferred/minor] 지적 내용 요약: yfinance 동기 호출에 네트워크 타임아웃 제어가 없어 야후 측 장애 시 백엔드가 무한 대기 가능 (from initial-project:04_fix)

# 프로젝트 히스토리

로컬 하네스가 자동 생성한 장기 기록 요약입니다.

- 기록된 run: 1
- 열린 리스크 / 미래 개선점: 13
- 열린/보류 미해결 항목: 21

## 최근 완료 Run

- 2026-05-27T10:39:20 project-initialize (full, complete, verify=PASS)
  - WPF 프론트엔드와 Python FastAPI 백엔드를 포함하는 주식/ETF 상세 조회 기능 스펙을 확정했다.
  - 검색 입력, API 계약, 주요 시세/기본 지표, 차트 데이터, 오류 처리, 초기 제외 범위를 정의했다.
  - WPF 및 FastAPI 엔드투엔드 개발 계획 수립

## 열린 리스크와 후속 개선점

- [low] 외부 금융 데이터 공급자의 안정성, 지연 시세, 라이선스 제약이 구현 단계에서 영향을 줄 수 있다. (from project-initialize)
- [low] WPF 차트 표시를 위해 새 외부 의존성이 필요할 가능성이 있다. (from project-initialize)
- [low] yfinance 외부 의존성: rate limit/차단 시 502로 변환되지만 실 환경 트래픽에선 추가 캐시/재시도 검토 필요 (from project-initialize)
- [low] yfinance의 스크레이핑 방식에 기인한 일시적 IP 차단 및 API 호출 지연 가능성 (from project-initialize)
- [low] 존재하지 않는 티커 입력 시 빈 응답에 따른 백엔드 예외 처리 누락 위험 (from project-initialize)
- [low] yfinance의 실시간 조회 Rate Limit 및 일시적인 접속 차단 위험 (향후 캐시 미도입으로 인한 한계 존재) (from project-initialize)
- [low] 수동 WPF UI 검증 필요 (자동화 UI 테스트 미작성) (from project-initialize)
- [low] ScottPlot 5 캔들 색상 커스터마이즈 API는 버전 의존적 → 향후 v5.x 마이너 업데이트 시 검증 필요 (from project-initialize)
- [low] ScottPlot 5.0.34의 캔들 색상 API가 검증되지 않아 색상 관례 적용은 별도 피처로 미뤘다. 향후 적용 시 dotnet build로 회귀 검증 필요. (from project-initialize)
- [low] WPF 런타임 UI 상호작용은 자동 UI 테스트가 아니라 빌드 검증 중심으로 확인했다. (from project-initialize)
- [low] 실시간 외부 데이터는 yfinance 공급자 상태에 따라 실패할 수 있으며, 현재 자동 테스트는 fake ticker 기반이다. (from project-initialize)
- [low] yfinance 라이브러리의 야후 파이낸스 차단 또는 일시적 API 지연 리스크 (구조화된 502 응답 및 WPF 내 튕김 방지 예외 처리로 완화됨) (from project-initialize)
- [low] src/ 하위 구현 파일이 미추적 상태라 하네스 커밋 포함이 필요하다. (from project-initialize)

## 미해결 리뷰/검증 항목

- [open/minor] 수정한 파일과 변경 내용: (from project-initialize:04_fix)
- [open/minor] **왜 문제인지**: (from project-initialize:03_review)
- [open/minor] 외부 연동 장애 복원력과 견고함을 보증하기 위해서는 고의로 에러를 던지는 Mock Ticker를 이용해 502 응답 코드가 제대로 나가는지 테스트 스위트에서 명시적으로 확인해 둘 필요가 있습니다. (from project-initialize:03_review)
- [open/minor] **해당 코드 위치**: (from project-initialize:03_review)
- [open/minor] `src/stocks-api/app/services/stock_service.py`: yfinance Ticker 생성, `info` 수집, `history` 수집, 404 사전 판별 로직을 `_load_and_validate_ticker_data(symbol, range_, interval, ticker_factory)`로 추출. `fetch_stock_detail`은 본래의 응답 모델 빌드 책임만 유지. (from project-initialize:04_fix)
- [open/minor] **severity**: MINOR (from project-initialize:03_review)
- [open/minor] severity: MINOR (from project-initialize:04_fix)
- [open/minor] 왜 수용했는가: 코드 스타일 규칙(30줄 초과 시 분리)에 부합하며, 외부 데이터 적재/검증 책임과 응답 모델 빌드 책임의 분리가 후속 단계 확장(캐싱·재시도 등) 시에도 유리하다. (from project-initialize:04_fix)
- [open/minor] `tests/test_api_stocks.py`에 `ticker.history` 호출 시 강제로 `Exception`을 던지는 `_FakeTicker` 시나리오를 설계하고, `GET /api/stocks/FAIL_TICKER` 와 같은 엔드포인트 요청 시 `502` status_code와 `upstream_history_failed` 에러 코드가 반환되는지 확인하는 테스트를 추가합니다. (from project-initialize:03_review)
- [open/minor] [tests/test_api_stocks.py](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/tests/test_api_stocks.py) (from project-initialize:03_review)
- [open/minor] [src/stocks-api/app/services/stock_service.py#L204-L215](file:///D:/test/vibe-coding-toolkit/vibe-coding-toolkit/src/stocks-api/app/services/stock_service.py#L204-L215) (from project-initialize:03_review)
- [open/minor] `stock_service.py`에서는 외부 API 장애를 감지하여 502(`upstream_history_failed`)를 정상적으로 발생시키도록 작성되어 있으나, 이를 검증하는 테스트 케이스가 pytest에 반영되어 있지 않습니다. (from project-initialize:03_review)
- [open/minor] **어떻게 개선해야 하는지**: (from project-initialize:03_review)
- [open/minor] **지적 사항**: yfinance 외부 API 호출 실패(Exception 발생) 시, 502 예외 처리 동작을 검증하는 자동화 단위 테스트의 누락 (from project-initialize:03_review)
- [open/minor] 왜 수용했는가: 외부 의존성의 장애 경로는 회귀 시 무음으로 깨질 수 있는 영역이라 자동화 검증이 합리적이며, 변경 비용이 작다. (from project-initialize:04_fix)
- [open/minor] 출처: 03_review (from project-initialize:04_fix)
- [open/minor] `tests/conftest.py`: 항상 `RuntimeError`를 던지는 `_FailingTicker`와 그 팩토리(`failing_history_ticker_factory`)를 추가. 기존 `client` 픽스처와 신규 `failing_history_client` 픽스처가 공유하는 `_make_client` 헬퍼로 monkeypatch 셋업 중복을 제거. (from project-initialize:04_fix)
- [open/minor] `tests/test_api_stocks.py`: `test_upstream_history_failure_returns_502`를 추가해 `/api/stocks/QLD` 요청 시 502 status와 `upstream_history_failed` 에러 코드가 반환되는지 확인. (from project-initialize:04_fix)
- [open/minor] 지적 내용 요약: `fetch_stock_detail` 함수 길이가 80여 줄로 길어 가독성이 떨어짐. 데이터 적재/검증 로직 분리 권고. (from project-initialize:04_fix)
- [open/minor] 지적 내용 요약: `ticker.history` 호출에서 예외 발생 시 502 `upstream_history_failed`로 변환되는 동작을 자동화 테스트가 검증하지 않음. (from project-initialize:04_fix)
- [deferred/minor] 없음 (from project-initialize:04_fix)

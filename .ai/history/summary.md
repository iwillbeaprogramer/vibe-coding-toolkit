# 프로젝트 히스토리

로컬 하네스가 자동 생성한 장기 기록 요약입니다.

- 기록된 run: 1
- 열린 리스크 / 미래 개선점: 14
- 열린/보류 미해결 항목: 0

## 최근 완료 Run

- 2026-05-26T21:33:12 init (full, complete, verify=PASS)
  - WPF 프론트엔드와 Python FastAPI 백엔드로 주식/ETF 정보를 조회하는 기능 스펙을 확정했다.
  - 검색 입력, 백엔드 API, 요약 지표, 차트 데이터, 오류 처리, 제외 범위를 정의했다.
  - FastAPI 백엔드(src/stock-api)를 신규 구축하고 /health, /api/stocks/{symbol}/summary, /api/stocks/{symbol}/history 엔드포인트와 yfinance 어댑터 서비스를 추가했다.

## 열린 리스크와 후속 개선점

- [low] 실시간 yfinance 네트워크 호출은 자동 검증에서 mock 기반 테스트로 대체되어 외부 공급자 장애와 응답 형식 변경 위험은 운영 잔여 리스크로 남는다. (from init)
- [low] WPF 차트는 종가 라인만 그리므로 거래 시간대/거래량 컨텍스트가 부족할 수 있다. (from init)
- [low] yfinance는 비공식 데이터 공급원이므로 응답 누락이나 장애 가능성이 있다. (from init)
- [low] WPF 차트 라이브러리와 Python 백엔드 의존성 추가가 필요할 수 있다. (from init)
- [low] DispatcherTimer 30ms 디바운스는 일반적인 드래그 리사이즈에 충분하나, 매우 빠른 자동화 리사이즈 시나리오에서는 마지막 프레임 지연이 체감될 수 있음 (from init)
- [low] src/stocks-dashboard/(복수형) 구 디렉터리 삭제와 src/stock-dashboard/(단수형) 신규 디렉터리 추가가 동일 커밋에 포함되어 솔루션 경로 의존 외부 설정이 있을 경우 영향을 받을 수 있음 (from init)
- [low] WPF 창 리사이즈 시 잦은 SizeChanged로 인한 일시적 오버헤드 (from init)
- [low] WPF UI 렌더링과 실제 사용자 조작은 빌드 검증까지만 수행했고 자동 UI 테스트는 없다. (from init)
- [low] 백엔드 자동 기동 로직이 없어서 사용자가 별도로 uvicorn을 실행해야 한다. (from init)
- [low] yfinance의 비공식 API 특성상 특정 필드가 예기치 않게 누락되거나 API 점검 시 데이터 요청이 거부될 수 있는 리스크 (from init)
- [low] yfinance의 비공식 API로 인한 Rate Limit 및 레이아웃 변경 취약점 (추후 Redis 캐시 도입 제안) (from init)
- [low] yfinance 라이브러리 레이트 리밋 또는 포맷 변동 리스크 존재 (from init)
- [low] yfinance가 비공식 스크래퍼 기반이라 운영 환경에서 레이트 리밋이나 응답 포맷 변경이 발생할 수 있다. (from init)
- [low] 실시간 시세나 유료 데이터 수준의 정확도는 이번 범위에 포함되지 않는다. (from init)

## 미해결 리뷰/검증 항목

- 없음

# 01_plan - init

작성: Antigravity
일시: 2026-05-26

## 기능 목표
- Windows WPF 데스크톱 앱에서 사용자가 미국 주식/ETF 티커(예: QLD, AAPL)를 검색하면 로컬 Python FastAPI 백엔드에서 `yfinance`를 통해 상세 시장 지표와 과거 차트 데이터를 가져와 WPF 화면에 아름다운 다크 테마 UI와 가격 차트로 시각화한다.
- 데이터 공급원의 호출 실패나 비정상 입력에 대비하여 견고한 에러 가드를 구현하고 사용자 친화적인 피드백을 제공한다.

## 구현 접근 방식
- **백엔드**: Python FastAPI를 활용하여 `/health`, `/api/stocks/{symbol}/summary`, `/api/stocks/{symbol}/history` HTTP API를 신규 개발한다. 외부 라이브러리인 `yfinance`를 호출하여 데이터를 가공하며, 존재하지 않는 티커는 404, 네트워크 장애는 502/503 오류로 명확히 분별하여 반환한다.
- **프론트엔드**: 기존 `.NET 7.0` WPF 프로젝트를 기반으로 구현하며, WPF 기본 `Canvas`와 `Polyline`을 사용하여 추가 NuGet 라이브러리 의존성 없이 극도로 안전하고 빌드가 완벽하게 보장되는 현대적인 그라데이션 종가 라인 차트를 직접 그린다. UI 디자인은 Deep Dark Blue (`#0F172A`) 배경과 Neon Blue (`#38BDF8`) 포인트를 가미한 프리미엄 Glassmorphism 스타일 카드로 제작하여 최상급의 시각적 우수성을 보여준다.

## 검토한 대안
- **대안 1**: NuGet 패키지(`LiveCharts.Wpf` 또는 `OxyPlot.Wpf`)를 사용한 차트 구현
  - *장점*: 줌인/아웃, 마우스 호버 툴팁 등 풍부한 인터랙티브 기능 기본 지원.
  - *단점*: .NET 7.0-windows 개발 환경과의 NuGet 패키지 호환성 충돌 위험이 있고, 오프라인 또는 폐쇄형 빌드 환경에서 패키지 복원 실패 가능성이 존재함.
  - *채택하지 않은 이유*: MVP 버전에서는 빌드 안정성과 외부 의존성 제거가 최우선이므로, WPF 네이티브 드로잉만으로도 충분히 아름다운 그라데이션 차트를 구현할 수 있기에 배제함.
- **대안 2**: WPF Canvas와 Polyline을 활용한 경량 커스텀 차트 구현 (채택)
  - *장점*: 외부 라이브러리 의존성이 0%로 빌드 및 실행 실패 확률이 전혀 없음. XAML 상에서 그라데이션 브러시를 직접 설정하여 커스텀 CSS 스타일링 못지않은 극도로 아름다운 라인 차트 연출이 가능함. 최대/최소 가격 기준 Y축 스케일링 수식이 매우 단순하여 오차가 없음.
  - *단점*: 픽셀 좌표 매핑 로직(Canvas Width/Height에 따른 X, Y 비율 매핑)을 C# 코드비하인드에서 계산해야 함.
  - *채택 이유*: 안정성과 시각적 아름다움을 동시에 얻을 수 있고, WPF 핵심 렌더링 기능을 온전히 제어할 수 있어 최종 채택함.

## 변경 파일 계획

### [Component 1] FastAPI Python 백엔드 (신규 추가)
FastAPI 서버를 구축하여 주식 정보를 가져오고 정제하여 WPF로 전달한다.
- #### [NEW] [requirements.txt](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-api/requirements.txt)
  - `fastapi`, `uvicorn`, `yfinance`, `pandas` 등의 필수 라이브러리를 정의한다.
- #### [NEW] [main.py](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-api/main.py)
  - FastAPI 앱의 메인 진입점. CORS 미들웨어를 설정하여 WPF 앱의 로컬 포트 요청을 허용한다.
  - `GET /health` 로컬 헬스체크 구현.
  - `GET /api/stocks/{symbol}/summary`, `GET /api/stocks/{symbol}/history` API 라우터 구현.
- #### [NEW] [services.py](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-api/services.py)
  - `yfinance.Ticker`를 사용해 외부 데이터를 비동기 안전성을 고려하여 감싸고 조회한다.
  - 데이터 누락이 잦은 `yfinance` 데이터의 특성을 극복하기 위한 Null-safe 딕셔너리 정제기 기능을 구현한다.

---

### [Component 2] WPF 프론트엔드 (기존 프로젝트 수정)
현대적인 다크 테마 레이아웃과 데이터 바인딩, 커스텀 차트 렌더링 로직을 개발한다.
- #### [MODIFY] [App.xaml](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/App.xaml)
  - 다크 테마용 전역 브러시, 텍스트 스타일, 보더 라운딩 리소스를 정의한다.
- #### [MODIFY] [MainWindow.xaml](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/MainWindow.xaml)
  - 프리미엄 Glassmorphism 카드 레이아웃 적용.
  - 상단: 티커 검색 입력 박스 (대문자 자동 치환, 플레이스홀더 제공) 및 검색 버튼.
  - 중단 좌측: 상세 주식 지표 그리드 (현재가, 전일종가, 시가, 고가, 저가, 등락율, 거래량, 시가총액 등).
  - 중단 우측: 차트용 `Canvas` 영역과 그라데이션 투명 배경.
  - 하단: 현재 API 연결 상태 및 에러 메시지 알림 보더 영역.
- #### [MODIFY] [MainWindow.xaml.cs](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs)
  - 비동기 `HttpClient`를 활용하여 백엔드 API 호출 구현.
  - 로딩 애니메이션(ProgressBar 활성화/비활성화) 및 예외 처리 흐름 제어.
  - 수신된 과거 가격(Close) 배열 데이터를 Canvas의 실제 Width/Height 비율에 맞추어 X, Y 픽셀 좌표로 변환하고 `Polyline`과 아래 채우기용 `Path`를 생성하여 차트를 미려하게 렌더링하는 C# 로직 작성.

---

### [Component 3] 테스트 코드 (신규 추가)
백엔드 로직의 신뢰성을 확인하기 위해 유닛 테스트를 추가한다.
- #### [NEW] [test_api.py](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/tests/test_api.py)
  - FastAPI의 `TestClient`를 이용해 정상 종목 검색(QLD, AAPL 등), 잘못된 종목(INVALID_TICKER) 검색 시의 404 리턴 등을 검증하는 자동화 테스트 코드를 작성한다.

## 데이터 / 제어 흐름
```
[ User WPF UI ] --(Ticker 입력: QLD)--> [ WPF Validations ] --(HTTP GET 요청)--> [ FastAPI Back-end ]
       ^                                                                               |
       |                                                                        [ yfinance API ]
       |                                                                               |
       |<--(JSON: Summary & History)-- [ API Response ] <--(Data 정제 & 가공)--[ yfinance Result ]
```

### 상세 데이터 포맷 예시:
- **`GET /api/stocks/{symbol}/summary` Response**:
  ```json
  {
    "symbol": "QLD",
    "name": "ProShares Ultra QQQ",
    "price": 98.45,
    "prev_close": 97.20,
    "change": 1.25,
    "change_percent": 1.29,
    "open": 97.50,
    "high": 99.10,
    "low": 97.12,
    "volume": 3254100,
    "market_cap": 25400000000,
    "currency": "USD",
    "exchange": "NASDAQ"
  }
  ```
- **`GET /api/stocks/{symbol}/history?range=1mo&interval=1d` Response**:
  ```json
  {
    "symbol": "QLD",
    "range": "1mo",
    "interval": "1d",
    "prices": [
      {"date": "2026-05-01", "open": 95.0, "high": 96.5, "low": 94.2, "close": 96.1, "volume": 2900000},
      {"date": "2026-05-02", "open": 96.2, "high": 97.0, "low": 95.8, "close": 96.8, "volume": 3100000}
    ]
  }
  ```

## 구현 단계 분할
1. **단계 1: Python FastAPI 백엔드 기반 구축**
   - 파일: `src/stock-api/requirements.txt`, `src/stock-api/main.py`, `src/stock-api/services.py`
   - 내용: `yfinance` 연동, 요약 데이터 및 히스토리 정제 반환 API 엔드포인트 구현 및 로컬 구동 테스트.
   - 완료 기준: `http://127.0.0.1:8000/api/stocks/AAPL/summary` 호출 시 200 OK와 올바른 JSON이 리턴됨.
2. **단계 2: 백엔드 단위 테스트 작성**
   - 파일: `tests/test_api.py`
   - 내용: FastAPI `TestClient`를 통한 종목 정보 반환 및 예외 처리 검증 테스트.
   - 완료 기준: `pytest` 테스트 수행 결과 패스.
3. **단계 3: WPF 글로벌 리소스 및 메인 화면 마크업 설계**
   - 파일: `src/stock-dashboard/stock-dashboard/App.xaml`, `src/stock-dashboard/stock-dashboard/MainWindow.xaml`
   - 내용: 다크 모드 스타일 리소스 적용, 글래스모피즘 카드 레이아웃, 검색 바, 로딩 바, 정보 그리드, 차트 캔버스 배치.
   - 완료 기준: WPF 앱 실행 시 세련된 다크 UI 셸이 렌더링됨.
4. **단계 4: WPF 비동기 연동 및 커스텀 차트 렌더링 연동**
   - 파일: `src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs`
   - 내용: `HttpClient` 연동, 예외 발생 시 하단 알림 창 노출, 캔버스 크기에 맞는 가격 곡선 그라데이션 폴리라인 그리기 로직 구현.
   - 완료 기준: QLD 검색 시 로딩 바 작동 후 실시간 가격 요약 지표와 가격 흐름선이 캔버스에 수려하게 그려짐.

## 위험 구간
- **위험 항목**: 외부 라이브러리 `yfinance`는 야후 파이낸스의 비공식 API 스크래퍼 기반이므로 잦은 레이트 리밋(Rate Limit)이나 응답 포맷 변경이 발생할 수 있음.
- **완화 방안**: 외부 API 호출 구간 전체를 트라이-캐치(`try-except`) 블록으로 안전하게 감싸고, 특정 필드가 누락(NaN)된 경우 0 또는 N/A 문자열로 변환하여 API 및 프론트엔드가 크래시(Crash)나지 않게 설계함.

## 새 의존성
- **Python**: `fastapi`, `uvicorn`, `yfinance`, `pandas` (FastAPI 서버 가동 및 야후 파이낸스 데이터 획득 목적, 대체 가능한 키 없는 라이브러리가 없으므로 필수)
- **C# (.NET)**: 추가적인 새 NuGet 의존성 없음 (Canvas 기반 커스텀 렌더링으로 라이브러리 의존성 위험 차단)

## 테스트 전략
- **백엔드 (API 테스트)**:
  - `tests/test_api.py`에서 `pytest`와 `fastapi.testclient`를 통해 로컬 통합 검증.
  - 케이스 1: AAPL 검색 시 주식명, 현재가 등 필수 Key 존재 여부 확인 (정상)
  - 케이스 2: 존재할 수 없는 티커(XYZ_INVALID) 검색 시 404 Status Code 및 에러 JSON 확인 (엣지)
- **프론트엔드 (수동 테스트)**:
  - 백엔드 서버 구동 상태에서 WPF 앱을 실행하여 빌드 및 연동성 테스트.
  - 검색창에 빈 문자열 입력 시 WPF 내부 밸리데이터 알림 팝업 확인.
  - 올바른 티커 입력 후 로딩 바 노출 및 차트 생성 테스트.
  - 백엔드 서버를 종료한 상태에서 검색 실행 시 "서버 연결에 실패했습니다" 오류 알림이 미려하게 노출되는지 확인.

## 롤백 / 복구 방향
- 모든 신규 파일은 하네스 환경에서 형상 관리가 제어되므로, 문제 발생 시 `git checkout` 또는 `git clean`을 통해 완벽하게 복구 가능 (모델은 직접 Git 명령어를 내리지 않고 로컬 하네스의 관리 하에 개발을 진행함).

## 실행 승인
- risk_level: high
- human_gate_required: true
- human_gate_reason: 새로운 Python FastAPI 백엔드 스택 도입과 100% Canvas 커스텀 WPF 렌더링 로직 개발이 진행되므로, 최종 개발 완료 후 완전한 검증을 위한 사람 승인 게이트 지정.
- approval_required_before_develop: false (하네스의 defaults_mode 정책에 따라 다음 단계로 자동 진행될 수 있도록 사전 개발 승인은 허용)

## 스펙 모호점 처리
- 차트 렌더링 라이브러리 도입 여부: .NET 7 버전 호환성을 보장하기 위해, 라이브러리를 추가하는 대신 WPF Native Canvas와 Polyline으로 아름다운 네온 라인을 직접 그리는 방식으로 자체 결정함.

## Git 기준점
- base_commit: c3d65fd191d1110d5f9f8b21961acb031633d6b6
- diff_base_command: `git diff c3d65fd191d1110d5f9f8b21961acb031633d6b6`

## 사용자 확인 사항
- 질문과 사용자 답변 기록: `defaults_mode: true` 상태이므로 질문 생략 및 권장 모범 설계안으로 자동 통과 처리함.

## 단계 결과
- status: PASS
- next_stage: 02_develop
- human_gate_required: true
- blocking_reason: 없음
- risk_level: high
- produced_files:
  - .ai/features/init/01_plan.md
  - .ai/features/init/01_plan.result.json
- changed_files:
  - .ai/features/init/01_plan.md
  - .ai/features/init/01_plan.result.json
- commit_created: false
- commit_message:
- model_mismatch: false
- actual_model: Antigravity

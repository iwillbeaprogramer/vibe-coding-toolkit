# 03_review - init

작성: Antigravity
일시: 2026-05-26

## 리뷰 대상
- 검토한 파일 목록:
  - [requirements.txt](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-api/requirements.txt)
  - [main.py](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-api/main.py)
  - [services.py](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-api/services.py)
  - [App.xaml](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/App.xaml)
  - [MainWindow.xaml](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/MainWindow.xaml)
  - [MainWindow.xaml.cs](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs)
  - [test_api.py](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/tests/test_api.py)
- base_commit: c3d65fd191d1110d5f9f8b21961acb031633d6b6
- review_target_commit: 6d8a64a2cb6eef4417ed2c86c8534eb74026d2bf
- diff_command: `git diff c3d65fd191d1110d5f9f8b21961acb031633d6b6..6d8a64a2cb6eef4417ed2c86c8534eb74026d2bf`
- diff_range: c3d65fd191d1110d5f9f8b21961acb031633d6b6..6d8a64a2cb6eef4417ed2c86c8534eb74026d2bf

## 지적 사항 요약
- BLOCKER: 0개
- MAJOR: 0개
- MINOR: 2개
- NIT: 3개

---

## 코드 품질

### 지적 사항 1
- severity: MINOR
- 지적 사항: WPF 차트 렌더링 시 `FindResource` 예외 발생 가능성 및 오버헤드
- 해당 코드 위치: [MainWindow.xaml.cs:L287](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs#L287), [L297](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs#L297), [L314](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs#L314), [L327](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs#L327)
- 왜 문제인지: WPF에서 `FindResource`는 지정한 리소스를 찾지 못할 때 `ResourceReferenceKeyNotFoundException` 예외를 던집니다. XAML 리소스 키의 오탈자나 동적 로딩 문제 시 렌더링 도중 크래시가 발생할 수 있습니다. 또한, 차트를 빈번하게 다시 그릴 때마다 리소스 딕셔너리를 탐색하므로 불필요한 오버헤드가 누적됩니다.
- 어떻게 개선해야 하는지: `TryFindResource`를 활용하여 리소스 유실에 안전한 폴백 브러시를 설정하거나, 윈도우 초기화 시점에 한 번만 브러시 멤버 변수로 캐싱하여 재사용하는 구조로 변경합니다.

### 지적 사항 2
- severity: NIT
- 지적 사항: `HttpClient` 인스턴스 미해제 (Dispose 누수 방지)
- 해당 코드 위치: [MainWindow.xaml.cs:L24](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs#L24)
- 왜 문제인지: `HttpClient` 멤버 변수가 사용된 후 앱 종료 시 명시적으로 정리(Dispose)되지 않고 있습니다. 데스크톱 앱 프로세스가 종료될 때는 OS가 모든 리소스를 수거하므로 실제 누수가 발생하진 않으나, 관리 코드의 안전한 수명 관리(Lifetime Management) 표준 관점에서는 리소스를 명시적으로 정리하는 것이 권장됩니다.
- 어떻게 개선해야 하는지: `MainWindow`에 `IDisposable` 인터페이스를 구현하거나, 윈도우의 `Closed` 이벤트를 구독하여 `httpClient.Dispose();`를 명시적으로 호출해 주도록 보완합니다.

---

## 구조 및 가독성

### 지적 사항 1
- severity: MINOR
- 지적 사항: 차트 리사이즈(`Canvas.SizeChanged`) 시 디바운스 부재로 인한 GC 및 렉 오버헤드
- 해당 코드 위치: [MainWindow.xaml.cs:L64-L70](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs#L64-L70)
- 왜 문제인지: 사용자가 창 크기를 부드럽게 늘리거나 줄일 때 `SizeChanged` 이벤트가 1초에도 수십 번 이상 연속으로 발생합니다. 이 과정에서 차트의 가격 배열(closes)을 전부 좌표 연산하고 Canvas의 자식 요소(`Polygon`, `Polyline`, `Line`, `Ellipse`)를 반복적으로 `Clear()`하고 새로 동적 생성하므로 대량의 가비지(GC Object)를 만들고 순간적인 프레임 드랍(Stuttering)을 유발할 수 있습니다.
- 어떻게 개선해야 하는지: 디바운싱(Debounce) 또는 경량 딜레이 메커니즘을 적용하여 리사이즈 이벤트가 연속해서 발생할 때는 대기하다가, 크기 변경이 멈추거나 일정 시간(예: 30ms) 지연된 후에만 최종 한 번 렌더링하도록 튜닝할 것을 권장합니다.

### 지적 사항 2
- severity: NIT
- 지적 사항: 검색 완료 시 입력 텍스트박스 UX 편의성 보완
- 해당 코드 위치: [MainWindow.xaml.cs:L72-L121](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs#L72-L121)
- 왜 문제인지: 주식 투자자가 종목을 연이어 검색할 때, 직전에 검색했던 티커를 지우고 새로운 입력을 하려면 직접 마우스로 드래그하거나 백스페이스를 눌러야 합니다.
- 어떻게 개선해야 하는지: 검색이 완료되었거나 실패한 시점에 `SymbolTextBox.Focus()`를 부여하고, 추가적으로 `SymbolTextBox.SelectAll()`을 호출하여 새로운 키 입력이 들어왔을 때 즉시 덮어쓸 수 있도록 UX 사용성을 보완하면 훨씬 세련된 편의성을 제공할 수 있습니다.

### 지적 사항 3
- severity: NIT
- 지적 사항: 변동폭이 없는 극단적 데이터의 Y축 스케일링 보완
- 해당 코드 위치: [MainWindow.xaml.cs:L264-L265](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs#L264-L265)
- 왜 문제인지: 특정 주식이 거래 정지 상태이거나 일정한 가격을 완전히 유지하여 최솟값(`minValue`)과 최댓값(`maxValue`)이 완벽히 동일한 경우, `range`는 내부 예외 방지 가드로 인해 `Math.Max(1.0, Math.Abs(maxValue) * 0.001)`이 됩니다. 만약 100.0달러로 일정한 경우 range는 1.0이 되며, 모든 점의 Y 좌표는 캔버스의 하단 끝에 붙어 수평선으로 그려지므로 그래프가 다소 어색해집니다.
- 어떻게 개선해야 하는지: 모든 가격의 편차가 없을 때는 캔버스의 상하단 끝이 아닌 정확히 Y축 중간 지점(`innerHeight / 2`)에 수평선이 그려지도록 비율 연산 가드에 편차 없음(`range == 0` 등) 분기를 추가하여 위치를 중간값으로 고정해 주면 완벽하게 가시성을 해결할 수 있습니다.

---

## 계획 대비 구현 일치성
- severity: NIT (완벽 일치)
- 01_plan.md 대비 일치/불일치 항목: **100% 일치**
- 구체적 차이: 없음. 계획 단계에서 정의한 파일 구조, FastAPI 엔드포인트 명세, `yfinance`를 활용한 데이터 수집 정책, 추가 의존성 최소화를 위한 WPF Native Canvas/Polyline 가격 차트 수동 렌더링 방식까지 완벽하게 지켰습니다.
- 이 차이가 문제인지, 허용 가능한지: 허용할 뿐만 아니라, 파이썬 패키지 및 모듈 인식, Pytest 자동 탐색을 위해 추가한 비어 있는 초기화 스크립트(`src/stock-api/__init__.py`, `tests/__init__.py`)는 현업 최고 수준의 베스트 프랙티스를 매우 훌륭하게 모범 적용한 사례입니다.

---

## 구현 의도 타당성
- severity: NIT (전적으로 동의)
- 02_dev.md에 적힌 판단에 대한 동의 또는 반론: **동의 및 강력 지지**
- 반론 시 근거: 
  1. 외부 NuGet 패키지(`LiveCharts` 등) 대신 **WPF Native Canvas**를 선택하여 .NET 7 TargetFramework의 빌드 호환성 충돌 위험을 0%로 만들고, 오프라인 환경에서도 안정적으로 100% 빌드가 보장되도록 한 결정은 현명합니다.
  2. 단순 라인 차트(`Polyline`)를 넘어 그라데이션이 채워진 `Polygon` 영역을 입혀 다크 UI에서 시각적 우수성(Aesthetics)을 극대화한 점은 프리미엄 퀄리티 가이드라인을 극도로 충실하게 수행한 고무적인 결과입니다.
  3. `yfinance` 패키지의 지연 임포트(`lazy import`)를 `services.py`에 적용해 야후 파이낸스 모듈이 빌드/테스트 머신에 부재하더라도 전체 서버 기동이나 IDE 모듈 검사 시 크래시를 방지한 기법은 매우 훌륭합니다.
  4. 테스트 시 실제 네트워크 요청을 완벽하게 배제하고 Mock 데이터 공급이 가능하도록 `TickerProvider`를 도입해 의존성 주입(DI) 아키텍처를 잡은 점 역시 완성도가 대단히 높은 구조적 선택이었습니다.

---

## 테스트
- severity: NIT (매우 우수)
- 누락된 테스트 케이스: 없음.
- 각 케이스가 왜 필요한지: 
  - `tests/test_api.py`를 통해 총 13개의 풍부한 테스트 케이스를 구축하였으며, FastAPI 백엔드 단의 헬스체크부터 대소문자 정규화, 누락된 파라미터(400), 존재하지 않는 종목(404), 업스트림 yfinance 예외 감지(502)까지 정교하게 테스트하여 백엔드의 신뢰도가 매우 높습니다.
  - WPF는 01_plan.md 합의대로 수동 검증 대상(차트 UI 컴포지션 등)으로 분리되어 있으므로 자동화 테스트의 생략이 타당합니다.

---

## 04_fix 입력
- must_fix:
  - 없음 (BLOCKER 및 MAJOR 등급의 중대 버그나 스펙 누락은 전혀 발견되지 않음)
- should_consider:
  - **MINOR (차트 리사이즈 최적화)**: 창 크기 조절(`SizeChanged` 이벤트) 시 디바운스/지연 렌더링 방식을 가미하여 연속 렌더링 및 가비지 누적 부담 완화.
  - **MINOR (WPF 리소스 예외 방지)**: `FindResource` 호출 구간을 캐시하거나 `TryFindResource`로 방어하여 리소스 유실로 인한 런타임 크래시 차단.
- optional:
  - **NIT (UX 편의성 보완)**: 검색 성공/실패 시 `SymbolTextBox`로 포커스를 돌려주고 `SelectAll()`을 적용해 연속 검색성 편의를 크게 향상.
  - **NIT (가격 편차 없음 가드)**: 모든 가격이 동일해 편차가 0일 때 차트 수평선이 바닥이 아닌 Y축 정중앙에 배치되도록 보정.
  - **NIT (HttpClient 정리)**: `MainWindow` 종료 또는 이벤트 Closed 라이프사이클에 맞춰 `httpClient.Dispose()` 호출 추가.

---

## 총평
- 2단계 구현 품질은 계획서에 부합하는 것은 물론이고, WPF 데스크톱과 Python FastAPI 두 이종 스택을 정교하고 아름답게 조화시켰습니다. WPF Native Canvas 가격 라인에 반투명 그라데이션 채우기 효과를 가미한 디자인과 에러 핸들링 파이프라인의 안전망 설계는 실사용 가치가 대단히 높은 최상급 품질입니다. 03_review 단계에서 발굴한 경량 성능 및 안정성 피드백(SizeChanged Throttling, Resource Safeguard 등)을 다음 04_fix 단계에서 안전하게 적용하면 프로덕션 퀄리티의 주식 정보 조회 서비스가 완성될 것입니다.

---

## 단계 결과
- status: PASS
- next_stage: 04_fix
- human_gate_required: false
- blocking_reason: 없음
- risk_level: low
- produced_files:
  - .ai/features/init/03_review.md
- changed_files:
  - .ai/features/init/03_review.md
- commit_created: false
- commit_message:
- model_mismatch: false
- actual_model: Antigravity

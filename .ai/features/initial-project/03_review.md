# 03_review - initial-project

작성: Antigravity
일시: 2026-05-26

## 리뷰 대상
- **FastAPI 백엔드**:
  - [main.py](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock_api/main.py)
  - [finance_service.py](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock_api/services/finance_service.py)
  - [schemas.py](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock_api/models/schemas.py)
  - [exceptions.py](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock_api/core/exceptions.py)
- **WPF 프론트엔드**:
  - [MainWindowViewModel.cs](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/StockDashboard/StockDashboard.Wpf/ViewModels/MainWindowViewModel.cs)
  - [StockApiClient.cs](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/StockDashboard/StockDashboard.Wpf/Services/StockApiClient.cs)
  - [MainWindow.xaml](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml)
  - [MainWindow.xaml.cs](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml.cs)
- **테스트**:
  - [test_finance_api.py](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/tests/backend/test_finance_api.py)
  - [MainWindowViewModelTests.cs](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/tests/frontend/StockDashboard.Tests/MainWindowViewModelTests.cs)
- **Git 정보**:
  - base_commit: `515d623878911a3b0fc1a35b98fcc43bdcb9b767`
  - review_target_commit: `056dbb7696570968293a6571eb816dbee0b79d67`
  - diff_command: `git diff 515d623878911a3b0fc1a35b98fcc43bdcb9b767`
  - diff_range: `515d623878911a3b0fc1a35b98fcc43bdcb9b767..056dbb7696570968293a6571eb816dbee0b79d67`

## 지적 사항 요약
- **BLOCKER**: 1개 (WPF 차트 최초 1회 렌더링 후 후속 검색 시 미갱신 오류)
- **MAJOR**: 1개 (비동기 검색 연속 호출 시 취소 예외 오진 및 UI 타임아웃 노출 오류)
- **MINOR**: 1개 (백엔드 yfinance 외부 API 연동 시 타임아웃 미제한 위험)
- **NIT**: 2개 (WPF 이벤트 핸들러 구독 해제 누락 및 헬퍼 인수 타입 검증 보완)

---

## 코드 품질

### [BLOCKER] WPF 차트 최초 1회 렌더링 후 후속 검색 시 미갱신 오류 (데이터 동기화 실패)
- **지적 사항**: 첫 번째 검색 후 다른 종목을 재검색할 때 UI 텍스트 정보는 갱신되지만 차트는 최초 검색 결과 그대로 멈춰 있습니다.
- **해당 코드 위치**: [MainWindow.xaml.cs:L27-L31](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml.cs#L27-L31)
- **왜 문제인지**:
  - 코드비하인드에서 뷰모델의 PropertyChanged 이벤트를 수신하여 `e.PropertyName == nameof(MainWindowViewModel.HasResult) && _viewModel.HasResult` 조건일 때 `RefreshChart()`를 호출합니다.
  - 그러나 `HasResult`는 뷰모델의 `ApplyStockDetail`이 수행될 때 매번 `true`로 설정됩니다. CommunityToolkit.Mvvm의 소스 생성기는 property setter에서 값의 변경 여부를 판단하므로, 이미 `HasResult`가 `true`인 상태에서 새로운 검색이 완료되더라도 `true` -> `true`로 값이 변경되지 않아 PropertyChanged 이벤트가 발생하지 않습니다.
  - 이로 인해 두 번째 종목 검색 시부터는 `RefreshChart()`가 실행되지 않아, UI 텍스트 데이터(이름, 시가 등)와 차트 시계열이 서로 다른 불일치 현상(Desync)이 발생합니다.
- **어떻게 개선해야 하는지**:
  - 매 검색 성공 시마다 확실하게 교체되는 `Stock` 객체의 변경을 감지하도록 구독 대상을 변경해야 합니다.
  ```csharp
  // 수정 전
  if (e.PropertyName == nameof(MainWindowViewModel.HasResult) && _viewModel.HasResult)
  {
      RefreshChart();
  }

  // 수정 후
  if (e.PropertyName == nameof(MainWindowViewModel.Stock) && _viewModel.HasResult)
  {
      RefreshChart();
  }
  ```

### [MAJOR] 비동기 검색 연속 호출 시 취소 예외 오진 및 UI 타임아웃 노출 오류
- **지적 사항**: 사용자가 검색창에 티커를 연속으로 빠르게 재검색하여 이전 비동기 작업이 취소될 때, 화면에 뜬금없이 "요청이 시간 초과되었습니다." 에러 메시지가 표시됩니다.
- **해당 코드 위치**: [StockApiClient.cs:L36-L39](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/StockDashboard/StockDashboard.Wpf/Services/StockApiClient.cs#L36-L39)
- **왜 문제인지**:
  - 사용자가 이전 검색이 끝나기 전에 새로운 검색을 입력하면 ViewModel은 `_searchCts?.Cancel()`을 호출하여 이전 요청을 명시적으로 취소합니다. 이때 HttpClient 내부에서 `TaskCanceledException`이 던져집니다.
  - 그러나 `StockApiClient`는 `TaskCanceledException`을 무조건 타임아웃으로 오해하여 `StockApiException(0, "timeout", "요청이 시간 초과되었습니다.")`로 변환해 던집니다.
  - 결국 ViewModel의 `catch (OperationCanceledException)` 블록은 해당 예외를 캐치하지 못하고 `catch (StockApiException)` 블록으로 넘어가 에러 메시지 배너를 띄움으로써, 사용자에게 불필요한 시스템 시간초과 에러 피드백을 노출하게 됩니다.
- **어떻게 개선해야 하는지**:
  - `TaskCanceledException` 발생 시 전달받은 `CancellationToken`의 `IsCancellationRequested` 플래그를 체크하여, 사용자가 직접 취소한 상황이라면 `OperationCanceledException`으로 다시 던지고, 실제로 HttpClient 자체 타임아웃에 의한 취소일 때만 타임아웃 예외로 우회처리해야 합니다.
  ```csharp
  catch (TaskCanceledException ex)
  {
      if (ct.IsCancellationRequested)
      {
          throw new OperationCanceledException("사용자에 의해 검색 요청이 취소되었습니다.", ex, ct);
      }
      throw new StockApiException(0, "timeout", "요청이 시간 초과되었습니다.");
  }
  ```

---

## 구조 및 가독성

### [MINOR] 외부 데이터 공급처(yfinance) 호출에 대한 타임아웃 부재로 인한 지연 위험
- **지적 사항**: 백엔드에서 `yfinance` API 호출 시 명시적인 네트워크 타임아웃 제어 장치가 없습니다.
- **해당 코드 위치**: [finance_service.py:L93-L95](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock_api/services/finance_service.py#L93-L95)
- **왜 문제인지**:
  - `yfinance` 라이브러리는 자체 `requests` 세션을 통해 야후 파이낸스 웹 API를 동기적으로 호출합니다. 만약 야후 파이낸스 측 서버 장애나 레이트 리밋, 네트워크 병목 현상이 생길 경우, 명시적인 타임아웃 설정이 없어 백엔드가 무한정 혹은 매우 오랫동안 대기(Block) 상태에 빠질 수 있으며, 이는 곧 WPF 클라이언트 측 10초 타임아웃 및 전체 API 서비스 마비로 이어집니다.
- **어떻게 개선해야 하는지**:
  - 백엔드 서비스 레이어 호출부(예: uvicorn 비동기 스레드 풀 구동 구간)를 `asyncio.wait_for`로 감싸서 특정 시간(예: 6초) 이상 지연 시 `UpstreamDataError`를 반환하도록 안전 패널티를 부여하거나, yfinance가 커스텀 requests Session을 주입할 수 있게 구조를 제공하므로 기본 세션에 타임아웃 헤더를 주입해 실행하도록 설정해야 합니다.

### [NIT] WPF MainWindow 코드비하인드의 PropertyChanged 구독 해제 누락
- **지적 사항**: 뷰모델 PropertyChanged 이벤트의 명시적 구독 해제가 빠져 있습니다.
- **해당 코드 위치**: [MainWindow.xaml.cs:L22](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/StockDashboard/StockDashboard.Wpf/Views/MainWindow.xaml.cs#L22)
- **왜 문제인지**:
  - 메인 윈도우 단일 구조 앱이라 윈도우 수명과 앱 수명이 같아 실질적인 메모리 누수 피해는 미미하지만, 다중 윈도우 전환이나 탭 구조 전환 등 확장될 경우 뷰모델의 이벤트 강한 참조로 인해 가비지 컬렉터(GC) 수집에서 윈도우가 누수되는 표준 설계 위배 사항입니다.
- **어떻게 개선해야 하는지**:
  - 윈도우 Unloaded 이벤트 또는 Dispose 패턴을 적용하여 이벤트 리스너를 명시적으로 해제해주는 클린 코드 표준을 장려합니다. (`_viewModel.PropertyChanged -= OnViewModelPropertyChanged;`)

### [NIT] yfinance 수집 필드 예외 코어션 헬퍼의 입력 검증 범위 강화
- **지적 사항**: `_coerce_float`와 `_coerce_int` 헬퍼가 yfinance 내부 필드의 NaN/Inf 처리 시 안전장치가 되어 있으나, 인자 형변환 로직이 다소 관대합니다.
- **해당 코드 위치**: [finance_service.py:L49-L66](file:///D:/WorkingDirectories/vibe-test/vibe-coding-toolkit/src/stock_api/services/finance_service.py#L49-L66)
- **왜 문제인지**:
  - yfinance가 종종 빈 사전(`{}`)이나 리스트 `[]`를 반환하거나 임의의 NumPy 객체를 반환할 때, `try-except float(...)`로 걸러지긴 하지만 사전에 입력 객체의 기본 타입(숫자, 문자열, NaN) 범위를 한정한 후 형변환을 적용하는 것이 예기치 못한 에러 추적과 성능 측면에서 유리합니다.
- **어떻게 개선해야 하는지**:
  - `isinstance` 혹은 yfinance의 결과물(DataFrame, Series의 NaN)을 구체적으로 식별하도록 체크 단계를 보다 정밀하게 추가하는 것이 좋습니다.

---

## 계획 대비 구현 일치성

- **일치성 검토**: **완벽하게 일치함**
- **세부 비교**:
  - `01_plan.md`에서 합의한 Python 백엔드 및 C# WPF 솔루션 프로젝트 구조가 100% 동일하게 구현되었습니다.
  - WPF MVVM 구조를 강화하고 뷰모델 단위 테스트 작성을 용이하게 하도록 `IStockApiClient` 인터페이스 및 이를 구현한 `StockApiClient` 클래스를 새롭게 추가한 것은, 01_plan.md 계획서에 누락되어 있었으나 실무 모범 사례에 부합하는 매우 권장할 만한 긍정적 추가 설계입니다.
  - 따라서 이 추가 의존성 및 구조적 변동 사항은 적극 승인 및 허용 가능합니다.

---

## 구현 의도 타당성

- **의도적 생략 및 대안 검토**: **동의함**
- **세부 의견**:
  - 외부 의존성(`yfinance`) 차단성 이슈와 네트워크 통신 상태에 독립적으로 백엔드를 격리 테스트하기 위해 `TickerLoader` 함수 포인터 주입 방식을 사용한 것은 매우 현명한 설계이며 모범적인 TDD 접근 방식입니다.
  - NaN/Inf 데이터를 Pydantic v2 직렬화 에러 없이 WPF에 그대로 `N/A`로 안전하게 바인딩하여 렌더링한 예외 가공 및 `_looks_empty`를 통한 404/502 판별 로직 또한 스펙에 규정된 에러 복원력을 최고 수준으로 유지하고 있습니다.
  - 단, 뷰모델의 순수성을 보존하고자 LiveCharts2 라이브러리 렌더링 책임을 뷰모델 바깥(코드비하인드)으로 두면서 차트 갱신 조건으로 `HasResult` 상태를 활용한 판단은, 앞서 기술한 "True -> True 중복 바인딩 불가 오류"의 원인이 되었으므로 `Stock` 속성 관찰로 보완해야 합니다.

---

## 테스트

- **테스트 케이스 커버리지**: **매우 우수함**
- **추가 권장되는 테스트 케이스**:
  - **프론트엔드 (MainWindowViewModelTests)**:
    - 연속 검색 동작 시 이전 HttpClient 요청이 올바르게 취소되며, 이때 UI나 ViewModel에 에러 메시지가 세팅되지 않고 무시되는지 여부(`OperationCanceledException`의 조용히 묻어가기 동작 검증).
  - **백엔드 (test_finance_api.py)**:
    - yfinance의 `info`에 일부 수치 필드(예: `trailingPE`)가 `NaN` 또는 `Infinity` 형태로 수집되었을 때, `_coerce_float` 헬퍼가 에러를 발생시키지 않고 통과하여 최종 Response JSON에 `null`로 안착하는지 직렬화 연동 시나리오 테스트.

---

## 04_fix 입력

- **must_fix**:
  - **[BLOCKER]** `MainWindow.xaml.cs` 내 차트 갱신 트리거를 `HasResult` 대신 `Stock` 프로퍼티의 PropertyChanged 이벤트 수신으로 변경해야 함.
  - **[MAJOR]** `StockApiClient.cs` 내 `TaskCanceledException` 예외 발생 시 `ct.IsCancellationRequested`를 구별하여, 사용자의 의도적 취소 요청은 `OperationCanceledException`을 그대로 던져서 조용히 무시되도록 개선해야 함.
- **should_consider**:
  - **[MINOR]** FastAPI 백엔드 `finance_service.py`에서 `yfinance` 호출 시 외부 응답 지연을 방지하기 위한 타임아웃 제한 및 502 예외 변환 메커니즘 보강.
- **optional**:
  - **[NIT]** WPF `MainWindow.xaml.cs` 윈도우 종료 시 `PropertyChanged` 이벤트 구독 리스너 자원 해제 추가.
  - **[NIT]** 백엔드 `finance_service.py` 예외 수치 변환 헬퍼(`_coerce_float`)의 NumPy/컬렉션 계열 인풋 방어형 입력 검증 보완.

---

## 총평

- 이 프로젝트의 2단계 구현 결과물은 데스크톱 주식 상세 시세 제공이라는 목표를 위해 아키텍처, 디자인 시스템(다크 모드와 그래디언트 헤더), 클라이언트-백엔드 인터페이스 구조 면에서 매우 완성도가 높은 수준으로 구현되었습니다. yfinance 연동 및 MVVM 구조 분리, 꼼꼼한 백엔드 Pydantic 매핑 및 프론트/백엔드 단위 테스트 구조 역시 훌륭합니다.
- 다만, 실제 구동 시 첫 검색 이후 차트가 다른 종목으로 전환되지 않는 블로킹 버그(BLOCKER)와, 빠르게 연속해서 다른 종목을 검색할 때마다 "요청 시간 초과"가 화면에 번쩍이는 사용자 경험 오류(MAJOR)가 코드 리뷰 과정에서 식별되었습니다.
- 해당 두 가지 중대 버그는 다음 4단계 `04_fix` 과정에서 반드시 수정되어야 하며, 이를 보완한다면 완벽하고 견고한 주식 검색 WPF 데스크톱 솔루션이 완성될 것입니다.

---

## 단계 결과
- **status**: PASS
- **next_stage**: 04_fix
- **human_gate_required**: false
- **blocking_reason**: 없음
- **risk_level**: low
- **produced_files**:
  - .ai/features/initial-project/03_review.md
- **changed_files**:
  - .ai/features/initial-project/03_review.md
- **commit_created**: false
- **commit_message**:
- **model_mismatch**: false
- **actual_model**: Antigravity

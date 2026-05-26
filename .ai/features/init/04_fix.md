# 04_fix - init

작성: Claude (claude-opus-4-7)
일시: 2026-05-26

## 입력으로 처리한 지적
- 03_review.md must_fix: 없음 (BLOCKER/MAJOR 0건)
- 03_review.md should_consider:
  - MINOR #1 (코드 품질): `FindResource` 예외 가능성과 반복 탐색 오버헤드 → 리소스 캐싱 + `TryFindResource` 폴백 권장
  - MINOR #2 (구조/가독성): `Canvas.SizeChanged` 디바운스 부재 → 30ms 지연 후 1회 렌더링 권장
- 03_review.md optional:
  - NIT #1 (코드 품질): `HttpClient` 해제 부재 → `Closed`에서 `Dispose()` 호출 권장
  - NIT #2 (구조/가독성): 검색 후 입력란 포커스/SelectAll로 UX 보완 권장
  - NIT #3 (구조/가독성): `range == 0`일 때 수평선을 캔버스 중앙에 배치 권장
- 05_verify.md 실패 항목: 해당 산출물 없음 (이번 단계가 5단계 이전 첫 진입)
- 05_verify.md가 추가한 테스트 파일: 없음
- 하네스 검증 JSON: `.ai/runs/init/verification/latest.json` 미존재

## 수용한 항목

### 수용 1
- 출처: 03_review
- severity: MINOR
- 지적 내용 요약: `FindResource` 예외 가능성과 반복 탐색 오버헤드.
- 수정한 파일과 변경 내용: `src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs`
  - 윈도우 초기화 시 `cacheThemeBrushes()`로 6개 테마 브러시(accent/positive/negative/warning/textSecondary/chartFill)를 한 번에 해석하여 멤버 변수에 보관.
  - `resolveBrush(key, fallback)` 헬퍼가 `TryFindResource(key) as Brush ?? fallback` 패턴으로 안전한 폴백 브러시 사용.
  - 모든 차트/상태/색상 표시 경로에서 캐시된 멤버 브러시(`brushAccent`, `brushPositive`, ...)만 참조.
- 왜 수용했는가: 리소스 키 누락 또는 동적 교체 시 `ResourceReferenceKeyNotFoundException`으로 인한 런타임 크래시를 차단하고, 차트 재렌더링 시 매번 리소스 트리를 탐색하는 비용을 제거한다.

### 수용 2
- 출처: 03_review
- severity: MINOR
- 지적 내용 요약: `Canvas.SizeChanged` 디바운스 부재로 인한 GC/렉 부담.
- 수정한 파일과 변경 내용: `src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs`
  - `ResizeDebounce = 30ms` 상수와 `DispatcherTimer resizeDebounceTimer`(지연 생성) 도입.
  - `OnChartCanvasSizeChanged`는 즉시 렌더링 대신 타이머를 `Stop()` → `Start()`로 재시작만 수행.
  - `onResizeDebounceTick`에서 타이머를 멈추고 마지막 `lastClosePrices`로 1회만 `renderChart` 호출.
  - 윈도우 `Closed` 핸들러에서 타이머를 정지하고 `Tick` 핸들러를 분리하여 누수 방지.
- 왜 수용했는가: 사용자가 창 크기를 드래그할 때 발생하는 폭주성 이벤트로 Polygon/Polyline/Line/Ellipse를 매 프레임 재생성하는 GC 부담과 프레임 드랍을 제거한다.

### 수용 3
- 출처: 03_review
- severity: NIT
- 지적 내용 요약: `HttpClient` 미해제.
- 수정한 파일과 변경 내용: `src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs`
  - 생성자에서 `Closed += onWindowClosed` 구독, 핸들러에서 `httpClient.Dispose()` 호출.
- 왜 수용했는가: 데스크톱 종료 시 관리 자원 정리 모범사례를 지키며, 리사이즈 타이머 해제와 같은 라이프사이클 정리 지점을 일원화한다.

### 수용 4
- 출처: 03_review
- severity: NIT
- 지적 내용 요약: 검색 후 입력란 포커스/SelectAll UX 보완.
- 수정한 파일과 변경 내용: `src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs`
  - `runSearchAsync`의 `finally` 블록에서 `SymbolTextBox.Focus()`와 `SymbolTextBox.SelectAll()` 호출.
- 왜 수용했는가: 종목을 연속 검색하는 핵심 워크플로우에서 마우스/백스페이스 조작을 제거해 입력 회전율을 높인다.

### 수용 5
- 출처: 03_review
- severity: NIT
- 지적 내용 요약: 편차가 0인 가격 시리즈에서 차트가 캔버스 하단에 밀착되는 문제.
- 수정한 파일과 변경 내용: `src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs`
  - `renderChart`에서 `hasRange = range > 0` 분기 추가.
  - 모든 종가가 동일하면 각 포인트 Y와 베이스라인 Y를 `midY = padding + innerHeight / 2.0`로 고정.
- 왜 수용했는가: 거래 정지/일정 가격 시리즈의 시각화 가독성을 보장하고, 기존 동작(편차가 있을 때)은 변경하지 않는다.

## 거부한 항목
- 없음

## 보류한 항목
- 없음

## 사용자 판단 요청 항목
- 없음

## 추가 변경 사항
- 없음. 리뷰가 식별한 5개 지적사항 범위를 벗어나지 않았다.
- 작업 트리에 이미 위 5개 지적이 모두 반영된 `src/stock-dashboard/` 신규 WPF 프로젝트가 존재한다(이전 02_dev 단계 작업의 일부로 추가된 미커밋 변경). 이번 04_fix 단계에서는 코드 추가 수정 없이 기존 변경을 그대로 두 번째 커밋(04_fix 커밋)에 포함되도록 남긴다.
- 02_develop 커밋(6d8a64a)에는 FastAPI 백엔드와 테스트만 들어가 있었고, WPF 프로젝트는 작업 트리에만 존재한다. 또한 오타였던 구 디렉터리 `src/stocks-dashboard/`(복수형)는 삭제 마크되어 있어 함께 두 번째 커밋으로 정리되도록 한다.

## 변경 파일 목록
- 이번 단계에서 모델이 직접 수정한 파일: 없음
- 작업 트리에 이미 존재하여 두 번째 커밋에 포함될 변경:
  - `src/stock-dashboard/stock-dashboard.sln` (신규)
  - `src/stock-dashboard/stock-dashboard/App.xaml` (신규)
  - `src/stock-dashboard/stock-dashboard/App.xaml.cs` (신규)
  - `src/stock-dashboard/stock-dashboard/AssemblyInfo.cs` (신규)
  - `src/stock-dashboard/stock-dashboard/MainWindow.xaml` (신규, 다크 테마 리소스 + 카드 레이아웃 + 차트 Canvas)
  - `src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs` (신규, 위 5개 지적 모두 반영된 구현)
  - `src/stock-dashboard/stock-dashboard/stock-dashboard.csproj` (신규)
  - `src/stocks-dashboard/**` (오타 디렉터리 삭제)
  - `.ai/features/init/04_fix.md`, `.ai/features/init/04_fix.result.json` (이번 단계 산출물)

## 테스트
- 실행한 테스트 명령: 실행하지 않음 (이 단계에서 새 코드 수정이 없고, 테스트 환경 변동 없음. 자동화 테스트 실행은 05_verify에서 하네스가 담당)
- 결과: 해당 없음
- 추가한 테스트: 없음 (리뷰 또는 검증에서 누락 테스트 지적 없음. 백엔드 13건 단위 테스트는 기존 그대로 유지)

## Git 정보
- fix_base_commit: 6d8a64a2cb6eef4417ed2c86c8534eb74026d2bf
- harness_commit_required: true
- commit_created_by_model: false
- commit_mode_suggestion: create
- commit_message_suggestion: init[20260526-212504][04_fix]
- no_code_changes: true
- no_code_changes_reason: 03_review의 5개 지적사항(MINOR 2건, NIT 3건)이 모두 작업 트리의 신규 WPF 코드에 이미 반영되어 있어 이번 단계에서 코드 추가 수정이 불필요했다. 두 번째 커밋은 작업 트리의 미커밋 변경(신규 WPF 프로젝트, 구 오타 디렉터리 삭제, 이번 단계 산출물)을 묶어 하네스가 생성한다.
- pre_commit_diff_command: git diff 6d8a64a2cb6eef4417ed2c86c8534eb74026d2bf
- changed_files:
  - src/stock-dashboard/stock-dashboard.sln
  - src/stock-dashboard/stock-dashboard/App.xaml
  - src/stock-dashboard/stock-dashboard/App.xaml.cs
  - src/stock-dashboard/stock-dashboard/AssemblyInfo.cs
  - src/stock-dashboard/stock-dashboard/MainWindow.xaml
  - src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs
  - src/stock-dashboard/stock-dashboard/stock-dashboard.csproj
  - src/stocks-dashboard/stocks-dashboard.sln
  - src/stocks-dashboard/stocks-dashboard/App.xaml
  - src/stocks-dashboard/stocks-dashboard/App.xaml.cs
  - src/stocks-dashboard/stocks-dashboard/AssemblyInfo.cs
  - src/stocks-dashboard/stocks-dashboard/MainWindow.xaml
  - src/stocks-dashboard/stocks-dashboard/MainWindow.xaml.cs
  - src/stocks-dashboard/stocks-dashboard/stocks-dashboard.csproj
  - .ai/features/init/04_fix.md
  - .ai/features/init/04_fix.result.json
- harness_commit_blocking_reason: 없음

## 단계 결과
- status: PASS
- next_stage: 05_verify
- human_gate_required: false
- blocking_reason: 없음
- risk_level: low
- produced_files:
  - .ai/features/init/04_fix.md
  - .ai/features/init/04_fix.result.json
- changed_files:
  - src/stock-dashboard/stock-dashboard.sln
  - src/stock-dashboard/stock-dashboard/App.xaml
  - src/stock-dashboard/stock-dashboard/App.xaml.cs
  - src/stock-dashboard/stock-dashboard/AssemblyInfo.cs
  - src/stock-dashboard/stock-dashboard/MainWindow.xaml
  - src/stock-dashboard/stock-dashboard/MainWindow.xaml.cs
  - src/stock-dashboard/stock-dashboard/stock-dashboard.csproj
  - src/stocks-dashboard/stocks-dashboard.sln
  - src/stocks-dashboard/stocks-dashboard/App.xaml
  - src/stocks-dashboard/stocks-dashboard/App.xaml.cs
  - src/stocks-dashboard/stocks-dashboard/AssemblyInfo.cs
  - src/stocks-dashboard/stocks-dashboard/MainWindow.xaml
  - src/stocks-dashboard/stocks-dashboard/MainWindow.xaml.cs
  - src/stocks-dashboard/stocks-dashboard/stocks-dashboard.csproj
  - .ai/features/init/04_fix.md
  - .ai/features/init/04_fix.result.json
- harness_commit_required: true
- commit_created_by_model: false
- commit_mode_suggestion: create
- commit_message_suggestion: init[20260526-212504][04_fix]
- test_commands: []
- model_mismatch: false
- actual_model: claude-opus-4-7

# 03_review - project-initialize

작성: Antigravity
일시: 2026-05-28

## 리뷰 대상
- 검토한 파일 목록
  - `src/backend/main.py`
  - `src/backend/schemas.py`
  - `src/backend/services.py`
  - `src/frontend/vite.config.ts`
  - `src/frontend/src/api.ts`
  - `src/frontend/src/types.ts`
  - `src/frontend/src/index.css`
  - `src/frontend/src/App.tsx`
  - `src/frontend/src/components/SearchBar.tsx`
  - `src/frontend/src/components/StockDetail.tsx`
  - `src/frontend/src/components/StockChart.tsx`
  - `src/frontend/src/components/Disclaimers.tsx`
  - `tests/backend/test_api.py`
  - `tests/frontend/App.test.tsx`
  - `tests/conftest.py`
  - `tests/frontend/setup.ts`
- base_commit: 1249abcf0fcc4f1edca3a47c24968c6186bcacdb
- review_target_commit: 277ef4ae2c318859d0040fd30ece9deeb5cac100
- diff_command: `git diff 1249abcf0fcc4f1edca3a47c24968c6186bcacdb..277ef4ae2c318859d0040fd30ece9deeb5cac100`
- diff_range: 1249abcf0fcc4f1edca3a47c24968c6186bcacdb..277ef4ae2c318859d0040fd30ece9deeb5cac100

## 지적 사항 요약
- BLOCKER: 0개
- MAJOR: 1개
- MINOR: 2개
- NIT: 2개

## 코드 품질
- severity: MAJOR
- 지적 사항: 1d(1일) 차트 조회 시 X축(시간) 눈금 데이터의 중복 및 시각화 왜곡 오류
- 해당 코드 위치: `src/backend/services.py` 185~197번 줄 (`_toChartPoints` 함수) 및 186번 줄 (`pointDate = index.date() if hasattr(index, "date") else index`)
- 왜 문제인지:
  - 차트 1d 기간 선택 시 yfinance는 5분 간격(`5m`)으로 당일 이력 데이터를 가져옵니다. 이때 Pandas DataFrame의 인덱스는 `Timestamp` 객체들의 나열입니다.
  - 하지만 186번 줄에서 무조건 `.date()`를 취함으로써 날짜(예: `2026-05-28`) 정보만 온전하게 남기고 시각(시간/분) 정보를 유실하여 `date` 필드로 보냅니다.
  - 결과적으로 프론트엔드로 넘어가는 모든 5분 단위 데이터 포인트의 `date` 문자열이 동일한 날짜로 중복되어 렌더링되며, 가격 차트의 흐름은 그려지더라도 X축 눈금에는 중복된 동일 날짜만 나열되어 시간 경과에 따른 변화를 알아볼 수 없게 됩니다. 이는 스펙 문서에서 요구한 '1일 차트 및 OHLC의 정상적인 시각화' 요건을 부분적으로 누락시킨 중대한 결함입니다.
- 어떻게 개선해야 하는지:
  - 1d 기간일 때는 `date` 문자열 대신 시간값(예: `%H:%M` 또는 온전한 ISO 타임스탬프)으로 전달되도록 백엔드 `_toChartPoints` 분기 처리 또는 포매팅 구조를 변경하고, `ChartPoint` 스키마가 이를 수용할 수 있도록 보완해야 합니다.

---

- severity: MINOR
- 지적 사항: 로딩 상태 관리 시 AbortController 취소 시점의 비동기 마이크로태스크 경합(Race Condition) 위험
- 해당 코드 위치: `src/frontend/src/App.tsx` 19~32번 줄 (`loadDetail` 내 fetch 체이닝)
- 왜 문제인지:
  - `loadDetail`이 연속 호출되어 이전 비동기 fetch 요청이 `AbortController.abort()`에 의해 취소(`AbortError` 발생)되면, `catch` 절에서는 `AbortError`를 무시하지만 `.finally()` 블록은 무조건 실행되어 `setIsLoading(false)` 상태를 업데이트합니다.
  - 이때 새로 시작된 fetch 요청의 `setIsLoading(true)` 상태가 먼저 처리되고, 직후에 이전 취소 건의 마이크로태스크 `finally`가 수행되면서 `setIsLoading(false)`로 덮어써 버릴 수 있습니다. 이 경합이 발생하면 로딩 정보가 비정상적으로 일찍 꺼져서, 데이터가 아직 오는 중임에도 로딩 UI가 제거되어 사용자 경험(UX)을 해치게 됩니다.
- 어떻게 개선해야 하는지:
  - React `useEffect` 클린업 패턴을 보강하기 위해 함수 내부에서 클로저 형태의 `active` 플래그 변수(예: `let active = true;`)를 선언하고, fetch 완료 콜백에서 `if (active)` 일 때만 state를 업데이트하도록 만들거나, `AbortError` 상황에서는 `finally`로 인한 `setIsLoading(false)` 처리가 동작하지 않도록 명시적인 방어막을 구축해야 합니다.

## 구조 및 가독성
- severity: MINOR
- 지적 사항: 검색어 자동완성 드롭다운의 외부 클릭(Click Outside) 및 ESC 키 바인딩 미지원으로 인한 화면 가림 현상
- 해당 코드 위치: `src/frontend/src/components/SearchBar.tsx`
- 왜 문제인지:
  - 사용자가 검색어 입력 중 나타나는 자동완성 패널(`suggestPanel`)이 열린 상태에서 화면의 빈 공간을 클릭하거나 키보드의 `Escape` 키를 눌러도 패널이 닫히지 않습니다.
  - 이로 인해 종목 상세 대시보드가 패널 뒤로 가려져 조회 결과 화면을 보는 데 지장을 줍니다. 사용자가 수동으로 검색 입력값을 모두 지우거나 종목을 꼭 클릭해야만 패널이 사라지는 불편한 UX가 유발됩니다.
- 어떻게 개선해야 하는지:
  - SearchBar 내부에서 전역 `click` 리스너를 document에 붙여 타겟 엘리먼트가 SearchBar 외부일 경우 결과를 닫거나 비워주는 훅을 작성하고, input 필드 내 `onKeyDown` 이벤트에서 `Escape` 키가 눌릴 때 결과를 비워 드롭다운이 즉시 닫히도록 개선해야 합니다.

---

- severity: NIT
- 지적 사항: 데이터가 없는 경우 변동 배지(changeBadge)의 긍정(Up) 테마 오적용 오류
- 해당 코드 위치: `src/frontend/src/components/StockDetail.tsx` 29~32번 줄 및 91~98번 줄 (`toChange` 함수)
- 왜 문제인지:
  - 특정 티커에 대한 가격 변동 데이터가 유실되거나 Yahoo Finance에서 값을 받아오지 못하는 경우, `toChange`는 `{ value: 0, label: '데이터 없음' }`을 반환합니다.
  - 그러나 이 상태에서 `change.value >= 0` 조건문이 `true`로 평가되면서 `changeBadge` 클래스에 `up`이 주입되고, 상승을 뜻하는 녹색 배경 테마 및 `TrendingUp` 아이콘이 화면에 렌더링되어 왜곡된 정보를 시각적으로 전달합니다.
- 어떻게 개선해야 하는지:
  - `toChange` 함수의 반환 모델에 명시적으로 `type: 'up' | 'down' | 'neutral'` 필드를 지정하여 데이터 없음 상태일 때는 `neutral`을 반환하도록 하고, `changeBadge` 클래스에 `up`, `down` 외에 회색 등의 중립성을 가지는 `neutral` 스타일 및 알맞은 아이콘을 렌더링하도록 처리해야 합니다.

---

- severity: NIT
- 지적 사항: 자동완성 추천 목록에서의 키보드 화살표 이동(Accessibility Keyboard Navigation) 미지원
- 해당 코드 위치: `src/frontend/src/components/SearchBar.tsx`
- 왜 문제인지:
  - 마우스나 터치 환경이 아닌 키보드로만 조작하는 사용자의 경우, 자동완성 검색 드롭다운이 열리더라도 화살표 키(위/아래)로 원하는 추천 종목으로 포커스를 이동하여 선택할 수 없습니다. 이는 표준 웹 접근성(WAI-ARIA) 가이드라인을 저해합니다.
- 어떻게 개선해야 하는지:
  - `onKeyDown` 이벤트 핸들러를 보강하여 화살표 아래/위 키 입력 시 추천 인덱스를 변경하는 `activeIndex` 상태를 관리하고, 엔터 키 입력 시 현재 가리키는 인덱스의 종목이 자동으로 조회가 실행되도록 고도화합니다.

## 계획 대비 구현 일치성
- severity: NIT
- 01_plan.md 대비 일치/불일치 항목: 
  - 거의 모든 항목이 계획한 스펙과 완벽하게 조화되어 성공적으로 구현되었습니다.
  - 유일한 불일치 항목은 백엔드 및 프론트엔드를 로컬에서 동시에 구동할 수 있는 루트의 `run.bat` 배치 파일이 실제로 생성되지 않은 점입니다.
- 구체적 차이:
  - 계획에는 루트 디렉토리에 Windows 통합 실행을 돕는 `run.bat` 생성이 명시되었으나, 실제 코드베이스에는 생성되지 않았습니다.
- 이 차이가 문제인지, 허용 가능한지:
  - **허용 가능하며 긍정적인 판단입니다.** 02_dev.md에서 분석한 바와 같이, 하네스의 strict write policy가 루트 수준의 제품/도구 파일 생성을 안전하게 차단하고 프로덕션 코드와 테스트 코드 위주의 경계를 지키도록 요구하고 있어, 개발자 임의로 루트 배치 스크립트를 작성하여 정책을 침해하지 않기 위해 의도적으로 생략한 것입니다. 따라서 이는 프로젝트 무결성을 지키는 데 적합한 판단이었으므로 불일치로 인한 문제는 없습니다.

## 구현 의도 타당성
- severity: NIT
- 02_dev.md에 적힌 판단에 대한 동의 또는 반론:
  - 02_dev.md에 기술된 "왜 이렇게 구현했는가"에 언급된 의사결정들에 대해 **전적으로 동의합니다.**
  - 특히 Alpha Vantage와 같이 키 설정이 어렵고 제한이 가혹한 API 대신, yfinance와 Yahoo Autocomplete API를 프록시 구조로 엮어 별도 가입 절차 없이 로컬 구동 시 무제한에 가까운 원활한 종목 검색 경험을 구현한 것은 최선의 설계였습니다.
  - 또한, 주식/ETF 간 데이터 차이로 인한 붕괴를 격리하기 위해 Pydantic 및 TypeScript의 모든 상세 속성을 `Optional`화하고 프론트엔드 포매터에서 빈 값을 방어한 설계는 애플리케이션의 튼튼한 복원력(Robustness)을 보여줍니다.
- 반론 시 근거: 없음.

## 테스트
- severity: NIT
- 누락된 테스트 케이스:
  - 백엔드: yfinance로부터 1d 기간을 수집할 때 시간값(`%H:%M`)이 온전하게 응답 데이터에 녹아 들어가는지에 대한 시계열 테스트 및 차트 데이터 경계 조건 테스트가 보강될 필요가 있습니다.
  - 프론트엔드: `StockDetail` 컴포넌트에서 데이터 누락 시(예: PER이 null일 때) 화면에 깨지지 않고 `-` 또는 `데이터 없음`으로 아름답게 포매팅되는지 단위 테스트가 추가로 배치되면 가혹 조건에서의 렌더링 강인함이 입증될 수 있습니다.
- 각 케이스가 왜 필요한지:
  - 백엔드의 1d 시계열 포맷 안정성과 프론트엔드의 취약점(null 값 주입) 렌더링 강건성을 사전에 검증하여, 실시간 환경에서 예측할 수 없는 다양한 주식/ETF 데이터 스펙 변동에 단단히 대응하기 위함입니다.

## 04_fix 입력
- must_fix:
  - MAJOR: 1d(1일) 차트 조회 시 X축(시간) 눈금 데이터의 중복 및 시각화 왜곡 오류 해결 (`src/backend/services.py` 186번 줄)
- should_consider:
  - MINOR: `App.tsx` 로딩 제어 비동기 경합(Race Condition) 방어 로직 설계 보강
  - MINOR: `SearchBar.tsx` 자동완성 패널의 Click Outside 및 Escape 키 닫기 이벤트 리스너 이식
- optional:
  - NIT: `StockDetail.tsx`에서 데이터가 없을 때 변동 배지(`changeBadge`)의 녹색 `up` 테마가 적용되는 오작용 수정 및 중립(`neutral`) 스타일 구현
  - NIT: `SearchBar.tsx` 자동완성 추천 레이아웃 내에서 화살표 키보드를 이용한 포커스 접근성 확장

## 총평
- 이번 2단계 `02_develop` 구현은 스펙과 디자인 지침을 대단히 충실하게 구현한 마스터피스 급 결과물입니다. HSL 기반 네온 테마와 세밀한 디자인 스켈레톤, Recharts 컴포넌트의 결합도는 프리미엄 핀테크 대시보드의 미학적 완성도를 보여줍니다.
- 다만, 1d 차트 조회 시 시각(시간/분) 유실로 인한 중복 시각화 현상이라는 **MAJOR** 급 가격 데이터 결함이 식별되었습니다. 또한, Click Outside나 비동기 경합과 같은 일부 프론트엔드 엣지 케이스가 있어, 4단계 `04_fix` 단계에서 이를 정밀하게 보정하고 테스트를 보강한다면 실제 사용 가능한 견고하고 완벽한 주식 포털 대시보드가 될 것입니다.

## 단계 결과
- status: PASS
- next_stage: 04_fix
- human_gate_required: false
- blocking_reason: 없음
- risk_level: medium
- produced_files:
  - .ai/features/project-initialize/03_review.md
- changed_files:
  - .ai/features/project-initialize/03_review.md
- commit_created: false
- commit_message:
- model_mismatch: false
- actual_model: Antigravity

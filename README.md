# Local AI Development Harness

이 저장소는 로컬 AI 에이전트들을 단계별로 오케스트레이션하는 개발 하네스입니다.

하네스의 목적은 단순히 프롬프트를 실행하는 것이 아니라, 기능 개발을 `스펙 -> 구현 -> 리뷰/수정 -> 검증 -> 기록` 흐름으로 고정하고, 각 단계의 산출물과 검증 결과를 프로젝트 안에 남기는 것입니다.

주 사용자는 Windows 환경에서 Python, Codex, Claude, Antigravity 계열 CLI를 로컬로 실행하는 개발자입니다.

---

## 빠른 시작

처음 보는 사람은 아래 순서만 따라가면 됩니다.

### 1. AI 하네스 상태 확인

빠른 파이프라인:

```powershell
python .ai\harness_fast.py doctor
```

표준 파이프라인:

```powershell
python .ai\harness_standard.py doctor
```

풀 파이프라인:

```powershell
python .ai\harness.py doctor
```

provider CLI까지 실제로 짧게 호출해 보고 싶으면:

```powershell
python .ai\harness_fast.py doctor --deep
python .ai\harness_standard.py doctor --deep
python .ai\harness.py doctor --deep
```

`doctor`는 provider 실행 가능 여부와 자동 배정 preview를 함께 보여줍니다. `doctor --deep`는 Codex, Claude, Antigravity CLI를 실제로 호출하므로 일반 `doctor`보다 오래 걸릴 수 있습니다.

### 2. 가장 흔한 실행 명령

작은 작업을 빠르게 끝내고 싶으면 보통 fast 파이프라인을 사용합니다.

```powershell
python .ai\harness_fast.py run "요청 내용을 여기에 작성" --feature feature-name --yes --defaults
```

리뷰/수정 단계를 포함한 일반 작업은 standard 파이프라인을 사용합니다.

```powershell
python .ai\harness_standard.py run "요청 내용을 여기에 작성" --feature feature-name --yes --defaults
```

계획, 리뷰, 수정, 검증, 문서 생성까지 모두 포함하려면 full 파이프라인을 사용합니다.

```powershell
python .ai\harness.py run "요청 내용을 여기에 작성" --feature feature-name --yes --defaults
```

`feature-name`은 소문자, 숫자, 하이픈만 쓰는 짧은 영문 slug를 권장합니다.

예:

```powershell
python .ai\harness_standard.py run "설정 항목에 도움말 툴팁을 추가해줘" --feature settings-tooltips --yes --defaults
```

---

## 저장소 구조

```text
presets/fast/
  3단계 빠른 파이프라인 프리셋

presets/standard/
  5단계 표준 파이프라인 프리셋

presets/full/
  7단계 풀 파이프라인 프리셋

.ai/
  하네스 본체, 설정, 템플릿, 실행 상태, 기능 산출물, 히스토리
```

주요 하네스 파일:

```text
.ai/harness_fast.py       fast 파이프라인 진입점
.ai/harness_standard.py   standard 파이프라인 진입점
.ai/harness.py            full 파이프라인 및 공통 하네스 구현
.ai/harness.config.json   하네스 검증 명령과 모델 배정 정책 설정
.ai/templates/            문서 생성 등 보조 템플릿
```

run을 실행하면 아래 폴더들이 생성될 수 있습니다.

```text
.ai/runs/<feature>/       run 상태, 프롬프트, 로그, handoff, 검증 결과
.ai/features/<feature>/   단계별 사람이 읽는 산출물과 result JSON
.ai/history/              완료된 run의 얇은 인덱스와 PC 후보
.ai/docs/                 full 파이프라인 문서 산출물
```

---

## 하네스가 해결하려는 문제

AI로 기능을 개발하면 다음 문제가 자주 생깁니다.

- 처음 요청이 모호한데 바로 코드를 고침
- 구현자는 통과했다고 말하지만 실제 빌드/테스트는 실패함
- 리뷰에서 나온 지적이 사라짐
- 검증 실패 원인이 다음 수정 단계로 잘 전달되지 않음
- 여러 모델이 만든 산출물이 흩어져 나중에 왜 그렇게 만들었는지 찾기 어려움
- 장기 프로젝트에서 리스크와 미래 개선점이 누적 관리되지 않음

이 하네스는 기능 단위를 하나의 run으로 다루고, 각 run을 단계별로 진행합니다.

각 단계는 다음 산출물을 남깁니다.

```text
.ai/features/<feature>/<stage>.md
.ai/features/<feature>/<stage>.result.json
```

하네스는 result JSON을 읽어 다음 단계로 진행할지, 사용자 확인이 필요한지, 실패했는지 판단합니다.

---

## 파이프라인 선택 기준

### fast

명령:

```powershell
python .ai\harness_fast.py ...
```

단계:

```text
00_specify -> 01_develop -> 02_verify
```

권장 용도:

- 작은 UI 수정
- 명확한 버그 수정
- 단일 기능 추가
- 빠른 프로토타입
- 리뷰 단계를 별도로 오래 돌릴 필요가 없는 작업

기본 권장 모델:

```text
00_specify : Antigravity
01_develop : Claude
02_verify  : Codex
```

### standard

명령:

```powershell
python .ai\harness_standard.py ...
```

단계:

```text
00_specify -> 01_develop -> 02_review -> 03_fix -> 04_verify
```

권장 용도:

- 일반적인 기능 개발
- 리뷰와 수정 단계를 분리하고 싶은 작업
- 테스트 추가가 필요한 변경
- 여러 파일을 건드리는 변경
- 대부분의 일상 개발

기본 권장 모델:

```text
00_specify : Codex
01_develop : Claude
02_review  : Antigravity
03_fix     : Claude
04_verify  : Codex
```

### full

명령:

```powershell
python .ai\harness.py ...
```

단계:

```text
00_specify -> 01_plan -> 02_develop -> 03_review -> 04_fix -> 05_verify -> 06_document
```

권장 용도:

- 위험도가 높은 작업
- 설계 판단이 중요한 작업
- 문서 산출물이 필요한 작업
- 장기 유지보수 관점에서 상세 기록이 필요한 기능
- API 계약, 데이터 흐름, 구조 변경이 포함된 작업

기본 권장 모델:

```text
00_specify : Codex
01_plan    : Antigravity
02_develop : Claude
03_review  : Antigravity
04_fix     : Claude
05_verify  : Codex
06_document: Antigravity
```

실제 실행 provider는 preset 값만으로 고정되지 않습니다. 하네스는 `.ai/harness.config.json`의 `model_policy`와 현재 사용 가능한 CLI를 보고 stage별 provider를 자동 배정합니다.

기본 정책:

```text
- 최소 2개 이상의 provider가 실행 가능해야 함
- 인접 stage는 가능한 한 같은 provider를 쓰지 않음
- develop/fix 같은 코드 작성 stage는 Claude 우선, 불가하면 Codex
- Antigravity는 코드 작성 stage에 배정하지 않음
- 독립성 제약을 지킬 수 없으면 조용히 진행하지 않고 blocked 처리
```

---

## 자동 실행 기본 패턴

### fast 자동 실행

```powershell
python .ai\harness_fast.py run "요청 내용" --feature feature-name --yes --defaults
```

verify 실패 후 develop으로 되돌아가는 반복 횟수를 늘리려면:

```powershell
python .ai\harness_fast.py run "요청 내용" --feature feature-name --yes --defaults --max-verify-fix-retries 5
```

### standard 자동 실행

```powershell
python .ai\harness_standard.py run "요청 내용" --feature feature-name --yes --defaults
```

검증/수정 반복을 더 허용하려면:

```powershell
python .ai\harness_standard.py run "요청 내용" --feature feature-name --yes --defaults --max-verify-fix-retries 5
```

### full 자동 실행

```powershell
python .ai\harness.py run "요청 내용" --feature feature-name --yes --defaults
```

타임아웃, 자동 전환 최대 단계 수, verify/fix 반복 횟수를 직접 지정하려면:

```powershell
python .ai\harness.py run "요청 내용" --feature feature-name --yes --defaults --timeout 3600 --max-steps 30 --max-verify-fix-retries 5
```

---

## 명령어 전체 설명

아래 예시는 full 파이프라인 기준으로 `.ai\harness.py`를 사용합니다.

fast를 쓰려면 `.ai\harness_fast.py`로 바꾸면 됩니다.

standard를 쓰려면 `.ai\harness_standard.py`로 바꾸면 됩니다.

### run

새 run을 만들고 자동으로 끝까지 진행합니다.

```powershell
python .ai\harness.py run "요청 내용" --feature feature-name --yes --defaults
```

가장 자주 쓰는 명령입니다.

### start

새 run을 만들고 첫 단계 프롬프트만 생성합니다.

```powershell
python .ai\harness.py start "요청 내용" --feature feature-name
```

직접 모델에 프롬프트를 넣어 수동으로 진행하고 싶을 때 사용합니다.

### prompt

현재 단계의 프롬프트 파일 경로를 봅니다.

```powershell
python .ai\harness.py prompt feature-name
```

프롬프트 본문까지 출력하려면:

```powershell
python .ai\harness.py prompt feature-name --print
```

### resume

모델이 현재 단계 산출물을 작성한 뒤, 하네스가 그 결과를 읽고 다음 단계로 진행합니다.

```powershell
python .ai\harness.py resume feature-name
```

resume 후 계속 자동 진행하려면:

```powershell
python .ai\harness.py resume feature-name --auto --yes --defaults
```

### auto

이미 존재하는 run을 현재 멈춘 지점부터 자동으로 이어갑니다.

```powershell
python .ai\harness.py auto feature-name --yes --defaults
```

### approve

사용자 확인이 필요한 human gate에서 막힌 run을 승인합니다.

```powershell
python .ai\harness.py approve feature-name
```

승인 후 자동으로 계속 진행하려면:

```powershell
python .ai\harness.py approve feature-name --auto --yes --defaults
```

### retry

현재 막힌 단계를 재시도합니다.

```powershell
python .ai\harness.py retry feature-name
```

기본 retry는 실패 이유, handoff, 최근 로그, 검증 결과를 포함한 보강 프롬프트를 새로 생성합니다.

기존 프롬프트를 그대로 다시 쓰려면:

```powershell
python .ai\harness.py retry feature-name --same
```

프롬프트만 생성하고 provider 실행은 하지 않으려면:

```powershell
python .ai\harness.py retry feature-name --prompt-only
```

retry 성공 후 다음 단계까지 자동 진행하려면:

```powershell
python .ai\harness.py retry feature-name --auto --yes --defaults
```

retry 전에 기존 stage 산출물은 아래 위치로 보관됩니다.

```text
.ai/runs/<feature>/retry_archives/
```

이렇게 해야 오래된 실패 결과를 하네스가 다시 읽는 일을 막을 수 있습니다.

### status

특정 run 상태를 자세히 봅니다.

```powershell
python .ai\harness.py status feature-name
```

전체 run 목록을 보려면 feature를 생략합니다.

```powershell
python .ai\harness.py status
```

또는:

```powershell
python .ai\harness.py list
```

### log

run 로그를 봅니다.

```powershell
python .ai\harness.py log feature-name
```

최근 200줄:

```powershell
python .ai\harness.py log feature-name --lines 200
```

실시간 추적:

```powershell
python .ai\harness.py log feature-name --follow
```

### watch

현재 상태와 최근 로그를 주기적으로 출력합니다.

```powershell
python .ai\harness.py watch feature-name
```

최근 로그 12줄, 3초 간격:

```powershell
python .ai\harness.py watch feature-name --lines 12 --interval 3
```

완료 또는 blocked 상태가 되면 watch를 종료하려면:

```powershell
python .ai\harness.py watch feature-name --exit-on-stop
```

### explain

run이 왜 멈췄고 다음에 뭘 해야 하는지 설명합니다.

```powershell
python .ai\harness.py explain feature-name
```

### doctor

프리셋, provider CLI, 현재 변경 파일 등 하네스 환경을 점검합니다.

```powershell
python .ai\harness.py doctor
```

provider smoke test까지 하려면:

```powershell
python .ai\harness.py doctor --deep
```

### cleanup

run 상태를 삭제합니다.

```powershell
python .ai\harness.py cleanup feature-name
```

생성된 `.ai/features/<feature>` 산출물은 남기고 `.ai/runs/<feature>`만 삭제하려면:

```powershell
python .ai\harness.py cleanup feature-name --keep-feature
```

주의: cleanup은 로컬 하네스 기록을 지웁니다. 필요한 로그나 산출물이 있으면 먼저 확인하세요.

---

## 주요 옵션

### --feature

run의 기능 이름을 지정합니다.

```powershell
--feature metric-tooltips
```

권장 규칙:

- 소문자 영어
- 숫자 허용
- 단어 구분은 하이픈
- 공백, 한글, 특수문자 피하기

좋은 예:

```text
metric-tooltips
loading-state
simulation-frequency
```

### --yes

자동 실행 중 human gate가 나왔을 때 가능한 경우 승인하고 계속 진행합니다.

다만 모델이 `NEEDS_USER`를 반환하거나 실제로 사용자 판단이 필요한 경우에는 멈출 수 있습니다.

### --defaults

모호한 판단이 있을 때 모델이 권장 기본값을 선택하게 합니다.

사용자에게 자주 물어보지 않고 진행하고 싶을 때 사용합니다.

### --timeout

각 provider 실행의 최대 대기 시간을 초 단위로 지정합니다.

```powershell
--timeout 3600
```

### --max-steps

자동 실행 중 최대 단계 전환 횟수를 지정합니다.

```powershell
--max-steps 30
```

무한 루프를 막기 위한 안전장치입니다.

### --max-verify-fix-retries

verify 실패 후 fix/develop 단계로 되돌아가는 반복 횟수를 지정합니다.

```powershell
--max-verify-fix-retries 5
```

기본값은 3입니다.

### --performance

provider 모델 성능 프로필을 지정합니다.

```powershell
--performance lite
--performance medium
--performance high
```

기본값은 `medium`입니다.

---

## 단계 산출물 규칙

각 stage는 사람이 읽는 Markdown과 하네스가 읽는 JSON을 함께 남깁니다.

예:

```text
.ai/features/metric-tooltips/00_spec.md
.ai/features/metric-tooltips/00_spec.result.json
```

하네스는 `.result.json`을 먼저 읽습니다.

기존 호환성을 위해 `.result.json`이 없으면 Markdown의 `## 단계 결과` 섹션을 읽으려고 시도합니다.

result JSON의 최소 필드는 다음과 같습니다.

```json
{
  "status": "PASS",
  "next_stage": "01_develop",
  "human_gate_required": false,
  "blocking_reason": ""
}
```

사용 가능한 status:

```text
PASS        단계 성공
FAIL        단계 실패
SKIPPED     단계 스킵
NEEDS_USER  사용자 판단 필요
```

추가로 자주 쓰는 필드:

```json
{
  "risk_level": "low",
  "changed_files": [
    "path/to/file"
  ],
  "test_commands": [
    "your test command"
  ],
  "verification_summary": {
    "status": "PASS"
  },
  "fix_inputs": {
    "accepted": [],
    "rejected": [],
    "deferred": []
  },
  "history_notes": {
    "implemented": [],
    "risks": [],
    "future_improvements": [],
    "decisions": [],
    "unresolved_items": []
  }
}
```

`history_notes`는 해당 stage 산출물에 남는 사람이 읽는 요약입니다. 하네스는 완료 시 이 중 핵심 구현 항목, 중요한 후속 과제, 중요한 결정만 얇은 history index에 반영합니다.

---

## 모델 배정 정책

기본값만으로도 동작하지만, 필요하면 `.ai/harness.config.json`에 `model_policy`를 추가해 provider 배정 방식을 조정할 수 있습니다.

예:

```json
{
  "providers": {
    "claude": { "enabled": true },
    "codex": { "enabled": true },
    "agy": { "enabled": true }
  },
  "model_policy": {
    "min_distinct_agents": 2,
    "no_adjacent_same_provider": true,
    "on_independence_violation": "block",
    "code_write_allowed": ["claude", "codex"],
    "code_write_denied": ["agy"],
    "code_write_order": ["claude", "codex"],
    "non_code_order": ["agy", "codex", "claude"]
  }
}
```

설정 파일에는 stage별 provider를 직접 박아두지 않는 것을 권장합니다. 사용자는 provider의 사용 가능 여부와 정책만 선언하고, 하네스가 실행 시점에 전체 stage 배정을 계산합니다.

`provider_schedule`은 run 상태에 저장됩니다.

```text
.ai/runs/<feature>/run.json
```

이미 생성된 run은 저장된 schedule을 우선 사용하므로, 실행 중에 provider가 조용히 바뀌지 않습니다.

---

## 검증 정책

하네스 검증 명령은 `.ai/harness.config.json`에 있습니다.

검증 명령은 이 하네스를 적용하는 실제 프로젝트에 맞게 설정합니다.

예:

```json
{
  "verification": {
    "enabled": true,
    "required": true,
    "timeout_seconds": 600,
    "commands": [
      {
        "name": "project_tests",
        "command": [
          "your",
          "test",
          "command"
        ]
      },
      {
        "name": "git_diff_check",
        "command": [
          "git",
          "-c",
          "safe.directory={root}",
          "diff",
          "--check"
        ]
      }
    ]
  }
}
```

verify stage에서 모델이 `PASS`라고 해도, 하네스 검증 명령이 실패하면 하네스가 최종 판정을 `FAIL`로 바꾸고 fix/develop 단계로 되돌립니다.

검증 결과는 아래에 저장됩니다.

```text
.ai/runs/<feature>/verification/latest.json
```

각 명령의 stdout/stderr도 같은 폴더에 저장됩니다.

---

## Git 정책

AI 모델은 직접 Git 명령을 실행하면 안 됩니다.

금지:

```text
git commit
git commit --amend
git reset
git checkout
git rebase
git push
```

하네스가 stage별 commit을 관리합니다.

commit 메시지 형식:

```text
[feature][YYYYMMDD-hhmmss][stage]
```

예:

```text
[settings-tab][20260519-232933][04_fix]
```

새 run을 시작하기 전에 하네스는 다음을 확인합니다.

- upstream에 push되지 않은 commit이 있는지
- 완료되지 않은 기존 run이 있는지

이 검사는 여러 기능 run이 섞여 Git 기록이 꼬이는 것을 막기 위한 안전장치입니다.

---

## Write Policy

각 preset의 frontmatter에는 단계별로 수정 가능한 파일 범위가 정의되어 있습니다.

예:

```yaml
allowed_writes:
  - "production_code"
  - "tests"
  - ".ai/features/[기능명]/01_dev.md"

forbidden_writes:
  - ".ai/features/[기능명]/00_spec.md"
```

하네스는 stage 실행 전 파일 snapshot을 만들고, stage 종료 후 변경된 파일이 allowed 범위를 벗어났는지 검사합니다.

위반 시 run은 blocked 상태가 됩니다.

---

## 실패와 복구

### provider 실행 실패

provider CLI가 실패하거나 타임아웃이 나면 run은 blocked 됩니다. 이미 provider가 실행된 뒤에는 파일 변경 가능성이 있으므로, 하네스는 다른 provider로 조용히 이어서 실행하지 않습니다.

provider가 실행 전부터 사용할 수 없는 상태라면 모델 배정 단계에서 가능한 다른 provider를 선택합니다. 단, 독립성 제약이나 코드 작성 provider 제약을 만족할 수 없으면 blocked 됩니다.

확인:

```powershell
python .ai\harness.py status feature-name
python .ai\harness.py log feature-name --lines 100
python .ai\harness.py explain feature-name
```

재시도:

```powershell
python .ai\harness.py retry feature-name
```

### 산출물 누락

모델이 지정된 `.md` 또는 `.result.json`을 작성하지 않으면 하네스가 멈춥니다.

확인:

```powershell
python .ai\harness.py explain feature-name
```

대부분은 retry로 해결합니다.

```powershell
python .ai\harness.py retry feature-name
```

### human gate

스펙이 모호하거나 사용자 판단이 필요한 경우 `NEEDS_USER`로 멈춥니다.

상세 확인:

```powershell
python .ai\harness.py status feature-name
python .ai\harness.py prompt feature-name --print
```

승인:

```powershell
python .ai\harness.py approve feature-name --auto --yes --defaults
```

### verify 실패

verify stage가 실패하면 하네스는 fix/develop 단계로 되돌립니다.

fast:

```text
02_verify 실패 -> 01_develop
```

standard:

```text
04_verify 실패 -> 03_fix
```

full:

```text
05_verify 실패 -> 04_fix
```

실패 원인은 다음 파일에 정리됩니다.

```text
.ai/runs/<feature>/handoff.md
.ai/runs/<feature>/verification/latest.json
```

### verify/fix 반복 제한 도달

기본 반복 제한은 3회입니다.

더 허용하려면:

```powershell
python .ai\harness.py resume feature-name --auto --yes --max-verify-fix-retries 5
```

또는:

```powershell
python .ai\harness.py auto feature-name --yes --defaults --max-verify-fix-retries 5
```

---

## 하네스 히스토리

run이 완료되면 하네스는 완료된 feature를 찾기 위한 얇은 인덱스를 자동으로 갱신합니다.
상세한 stage별 기록은 `.ai/features/<feature>/`가 원본이며, provider 로그와 prompt는 `.ai/runs/<feature>/`에 남습니다.

위치:

```text
.ai/history/
```

주요 파일:

```text
.ai/history/index.json
.ai/history/summary.md
.ai/history/pc_candidates.json
```

### index.json

완료된 feature의 최신 상태를 빠르게 찾기 위한 작은 인덱스입니다.

포함 내용:

- feature 이름
- pipeline 종류
- 요청 요약
- 최종 상태와 검증 결과
- feature 산출물 경로
- run 산출물 경로
- 문서 산출물 경로
- 관련 commit
- 요약된 구현 항목
- 중요한 후속 과제와 결정

### summary.md

사람이 빠르게 읽는 최신 완료 run 요약입니다. `index.json`에서 재생성할 수 있는 파생 파일입니다.

장기 리스크, 리뷰 지적, 결정의 상세 원본은 별도 전역 history 파일로 중복 저장하지 않습니다.
필요하면 `.ai/features/<feature>/`의 stage 산출물과 result JSON을 확인합니다.

---

## Project Contract

Project Contract(PC)는 여러 pipeline을 거치며 유지해야 하는 프로젝트 전체 규약입니다.

PC는 처음부터 크게 선언하는 문서가 아니라, standard/full pipeline 완료 후 실제 개발 과정에서 관찰된 규칙 후보를 누적하고, 사용자가 승인한 규칙만 모든 다음 프롬프트에 주입하는 방식으로 동작합니다.

### 파일 위치

```text
.ai/history/pc_candidates.json
  모든 PC 후보와 상태를 누적합니다.

.ai/project_contract.md
  승인된 규약과 기본 프로젝트 규칙을 담습니다. 모든 stage prompt에 자동 삽입됩니다.
  파일이 없으면 하네스가 기본 규칙 파일을 만든 뒤 그 내용을 prompt에 삽입합니다.

.ai/pc_review.py
  미정 PC 후보 전체를 선택한 agent로 한 번에 검토하고, 사용자 응답에 따라 후보 상태와 project_contract를 갱신합니다.
```

### 상태

PC 후보 상태는 세 가지만 사용합니다.

```text
미정
승인
기각
```

`미정` 후보가 있어도 새 pipeline은 시작할 수 있습니다. 하네스는 경고만 출력합니다.

### pipeline별 정책

```text
fast
  PC 후보 추출을 생략합니다.

standard
  pipeline 완료 후 PC 후보 추출을 필수로 수행합니다.

full
  pipeline 완료 후 PC 후보 추출을 필수로 수행합니다.
```

저장되는 후보는 `impact_scope: project_wide` 항목뿐입니다. 특정 스택 전용, 기능 한정, 구현 디테일 수준의 관찰은 버립니다.

fast가 PC 후보를 만들지는 않지만, 이미 미정 후보가 있으면 시작 시 경고만 표시합니다.

### 미정 후보 정산

미정 후보가 있으면 아래 명령을 실행합니다.

```powershell
python .ai\pc_review.py
```

기본 검토 agent는 `codex`입니다. 필요하면 아래처럼 바꿀 수 있습니다.

```powershell
python .ai\pc_review.py --agent claude
python .ai\pc_review.py --agent agy
```

실행하면 선택한 agent가 모든 미정 후보와 `.ai/project_contract.md`를 함께 읽고, 중복이 아니며 프로젝트 전체에 효과가 있는 규칙만 짧은 최종 문장으로 제안합니다.

사용자는 추가될 Project Contract 문장과 기각될 후보 요약을 한 번에 확인한 뒤 `Yes` 또는 `No`를 한 번만 입력합니다.

`Yes`를 입력하면 제안된 규칙을 `.ai/project_contract.md`에 반영하고, 규칙에 반영된 후보는 승인, 나머지 후보는 기각으로 기록합니다.

```text
.ai/history/pc_candidates.json
.ai/project_contract.md
```

`No`를 입력하면 `.ai/project_contract.md`는 수정하지 않고, 이번 미정 후보 전체를 기각으로 기록합니다.
따라서 정상 종료 후에는 미정 후보가 남지 않아야 합니다.

---

## 중요한 파일 위치

프롬프트:

```text
.ai/runs/<feature>/prompts/
```

provider stdout/stderr:

```text
.ai/runs/<feature>/logs/
```

하네스 이벤트 로그:

```text
.ai/runs/<feature>/harness.log
```

handoff:

```text
.ai/runs/<feature>/handoff.md
```

검증 결과:

```text
.ai/runs/<feature>/verification/
```

단계 산출물:

```text
.ai/features/<feature>/
```

장기 히스토리:

```text
.ai/history/
```

full 파이프라인 문서 산출물:

```text
.ai/docs/
```

---

## 자주 쓰는 작업 예시

### 작은 기능을 빠르게 개발

```powershell
python .ai\harness_fast.py run "처리 중 상태를 더 명확하게 표시해줘" --feature loading-state --yes --defaults
```

### 일반 기능을 리뷰 포함해서 개발

```powershell
python .ai\harness_standard.py run "설정 항목에 도움말 툴팁을 추가해줘" --feature settings-tooltips --yes --defaults
```

### 위험한 작업을 풀 파이프라인으로 개발

```powershell
python .ai\harness.py run "설정 저장 구조를 변경하고 문서까지 남겨줘" --feature settings-storage --yes --defaults
```

### 중간에 멈춘 run 이어가기

```powershell
python .ai\harness_standard.py auto settings-tooltips --yes --defaults
```

### 왜 멈췄는지 확인

```powershell
python .ai\harness_standard.py explain settings-tooltips
```

### 실패 단계 재시도

```powershell
python .ai\harness_standard.py retry settings-tooltips --auto --yes --defaults
```

### 최근 로그 확인

```powershell
python .ai\harness_standard.py log settings-tooltips --lines 120
```

### 히스토리 확인

```powershell
Get-Content .ai\history\summary.md
Get-Content .ai\history\index.json
```

---

## 신규 사용자가 가장 많이 헷갈리는 점

### run과 feature의 차이

feature는 기능 이름입니다.

run은 그 feature를 개발하기 위한 하네스 실행 상태입니다.

보통 하나의 feature마다 하나의 run을 만듭니다.

### 모델이 직접 commit하면 안 되는 이유

하네스가 단계별 commit을 추적해야 verify 실패 시 어느 단계 commit을 amend할지 알 수 있습니다.

모델이 직접 commit하면 하네스의 Git 기준점이 깨질 수 있습니다.

### result JSON이 필요한 이유

Markdown은 사람이 읽기 좋지만, 하네스가 안정적으로 파싱하기 어렵습니다.

그래서 각 단계는 `.result.json`을 반드시 같이 남깁니다.

### verify가 PASS인데 다시 fix로 돌아가는 이유

모델의 PASS는 최종 판정이 아닙니다.

하네스 검증 명령이 실패하면 하네스가 최종 판정을 FAIL로 바꾸고 fix/develop 단계로 되돌립니다.

### history는 왜 필요한가

Git log만으로는 다음 질문에 답하기 어렵습니다.

- 무엇을 개발했는가
- 왜 그렇게 만들었는가
- 어떤 리스크를 알고도 남겼는가
- 어떤 리뷰 지적을 거부했는가
- 어떤 개선점을 나중으로 미뤘는가

하네스 history는 완료 feature를 찾기 위한 인덱스만 누적하고, 상세 판단 근거는 `.ai/features/<feature>/`에 보존합니다.

---

## 개발자가 지켜야 할 원칙

- 작업은 가능한 feature 단위로 작게 나눈다.
- feature 이름은 명확한 영문 slug로 둔다.
- 작은 작업은 fast, 일반 작업은 standard, 위험한 작업은 full을 사용한다.
- 모델이 직접 Git commit/push를 하지 않게 한다.
- verify 실패를 숨기지 않는다.
- `NEEDS_USER`가 나오면 억지로 진행하지 말고 판단을 남긴다.
- 리뷰에서 거부/보류한 항목은 해당 stage 산출물과 result JSON에 남긴다.
- 장기적으로 반복 적용할 규칙은 Project Contract 후보로 올리고, 기능별 판단 근거는 `.ai/features/<feature>/`에 남긴다.

---

## 권장 운영 흐름

평소에는 이 흐름을 권장합니다.

1. 작은 작업인지 일반 작업인지 위험한 작업인지 판단한다.
2. fast / standard / full 중 하나를 고른다.
3. `run ... --yes --defaults`로 자동 실행한다.
4. 멈추면 `status`, `explain`, `log`를 확인한다.
5. 실패가 명확하면 `retry --auto --yes --defaults`를 사용한다.
6. 완료 후 `.ai/history/summary.md`와 필요한 `.ai/features/<feature>/` 산출물을 확인한다.
7. 필요한 경우 남은 리스크나 보류 항목을 다음 feature로 분리한다.

---

## 배포 메모

다른 사람이 사용할 때는 다음을 먼저 확인하게 하세요.

- Python 설치 여부
- Codex CLI 설치 여부
- Claude CLI 설치 여부
- Antigravity/AGY CLI 설치 여부
- provider 인증 상태
- `python .ai\harness_*.py doctor` 결과
- 적용 대상 프로젝트에 맞춘 `.ai/harness.config.json` 검증 명령

하네스를 처음 쓰는 사람에게는 `fast`보다 `standard`를 먼저 권장하는 것이 좋습니다. 리뷰와 수정 단계가 분리되어 있어 결과를 이해하기 쉽습니다.

# Local Harness Prompt

## Harness Context
- feature_name: init
- pipeline_mode: full
- stage: 01_plan
- preferred_model: Antigravity
- performance: medium
- output_file: .ai/features/init/01_plan.md
- result_json_file: .ai/features/init/01_plan.result.json
- run_state: .ai/runs/init/run.json
- generated_at: 2026-05-26T21:09:17
- defaults_mode: true
- feature_name_locked: true

## Decision Policy
Use recommended defaults for ambiguous decisions. Do not return NEEDS_USER unless the task is impossible, unsafe, requires credentials/secrets that are not available, or would perform destructive/non-reversible actions. Record all default decisions and their rationale in the stage output.

## Manual Provider Instructions
1. The local harness is executing this prompt with the preferred model when possible.
2. Make the requested file changes directly in the repository.
3. Write the human-readable stage output file exactly at `.ai/features/init/01_plan.md`.
4. Also write the machine-readable stage result JSON exactly at `.ai/features/init/01_plan.result.json`.
5. Do not run `git commit`, `git reset`, `git checkout`, `git rebase`, or `git push`. The local harness owns Git history.
6. This Git ownership rule overrides any preset text that appears to ask the model to create, amend, or push commits.
7. For commit stages, leave the working tree commit-ready and record commit intent in the stage output; the harness will create or amend the commit.
8. If `defaults_mode: true`, prefer recommended defaults over `NEEDS_USER` unless blocked by missing credentials, safety, destructive operations, or impossibility.
9. If the stage needs user input under the decision policy, write both outputs with `status: NEEDS_USER`.
10. If the stage fails, write both outputs with `status: FAIL` and a concrete blocking reason.
11. If `feature_name_locked: true`, keep the existing `feature_name` exactly as provided by the harness. Do not rename or invent a different feature slug.
12. End with a concise summary; the harness will inspect files, not your final message.

## Machine Result JSON Contract
The harness reads `.ai/features/init/01_plan.result.json` first. Keep the `## 단계 결과` section in `.ai/features/init/01_plan.md` for humans, but write this JSON file for the harness.

Required JSON keys:
- status: "PASS", "FAIL", "SKIPPED", or "NEEDS_USER"
- next_stage: next stage id or "done"
- human_gate_required: true or false
- blocking_reason: string, use "" when there is no blocker

Include any extra stage fields that the preset asks for, such as `risk_level`, `harness_commit_required`, `changed_files`, `verification_summary`, or `fix_inputs`.
For PASS or FAIL stages, also include `history_notes` with these arrays when known: `implemented`, `risks`, `future_improvements`, `decisions`, and `unresolved_items`. Use empty arrays for categories with nothing to record. Prefer Korean text for human-facing titles, descriptions, reasons, risks, and decisions when the project context is Korean.

## Project Contract
Source: .ai/project_contract.md

# Project Contract

## Hard Rules
- 모델은 Git commit, amend, reset, checkout, rebase, push를 직접 실행하지 않는다.
- 기존 테스트를 삭제하거나 비활성화하지 않는다.
- 요청 범위를 벗어난 리팩터링, 의존성 추가, 파일 이동은 하지 않는다.

## Project Layout
- 프로덕션 코드는 루트 `src/` 하위에 둔다.
- 테스트 코드는 루트 `tests/` 하위에 둔다.
- 새 테스트 파일을 `src/` 하위에 만들지 않는다.

## Code Style
- 새 코드는 같은 디렉터리의 기존 패턴, 네이밍, 파일 구조를 우선 따른다.
- 프로젝트에 이미 명확한 네이밍 관례가 없으면 변수와 함수는 camelCase를 기본으로 한다.
- 함수 이름은 가능하면 동사 또는 동사구로 시작한다. 예: `loadConfig`, `validateInput`, `renderItem`.
- Boolean 값과 Boolean 반환 함수는 `is`, `has`, `can`, `should` 같은 의미 있는 접두사를 사용한다.
- 이벤트 핸들러는 `handle` 또는 기존 프로젝트의 이벤트 네이밍 패턴을 따른다.
- 값을 변환하는 함수는 `to`, `from`, `parse`, `format`, `normalize`처럼 변환 의도가 드러나는 이름을 사용한다.
- 데이터를 가져오는 함수는 `get`, `load`, `fetch`, `read` 중 실제 동작에 맞는 동사를 사용한다.
- 부수효과가 있는 함수는 `save`, `write`, `update`, `delete`, `send`, `create`처럼 변경 의도가 드러나는 동사를 사용한다.
- 구현이 30줄을 넘어가면 함수나 작은 단위로 분리한다.

## Reliability
- 외부 입력, 파일, 네트워크, 프로세스 실행 결과는 실패 가능성을 명시적으로 처리한다.


## Original User Request
난 주식정보를 검색해서 디테일한 정보를 보는 윈도우 프로그램을 만들고싶어. 프론트는 WPF 백엔드는 파이썬 FastAPI로 제공하면 될거같아. WPF에서 종목명 예를들어 QLD를 검색하면 그 정보들을 주는거지. 주식쟁이들이 흔히 하는 정보들있자나 현재가, 종가 뭐 등등 엄청많아. 이것들을 다 보여주고, 차트까지 보였으면 좋겠어

## Previous Stage Outputs
- .ai/features/init/00_spec.md
- .ai/features/init/00_spec.result.json

## Additional Stage Inputs
- none

## Retry Context
- none

## Current Git Hints
- current_head: c3d65fd191d1110d5f9f8b21961acb031633d6b6
- changed_paths_excluding_runs: [".ai/features/"]
- latest_harness_verification: none

---

---
stage: "01_plan"
role: "implementation_plan"
preferred_model: "Antigravity"
model_policy: "preferred_not_hard_block"
required_inputs:
  - ".ai/features/init/00_spec.md"
optional_inputs:
  - "existing_codebase"
outputs:
  - ".ai/features/init/01_plan.md"
allowed_writes:
  - ".ai/features/init/01_plan.md"
forbidden_writes:
  - "production_code"
  - "tests"
human_gate_required: "defer_to_output"
default_next_stage: "02_develop"
---

# 계획 프리셋 (1단계)

## 경로 원칙

- 프로덕션 코드는 루트 `src/` 하위 파일만 의미한다.
- 테스트 코드는 루트 `tests/` 하위 파일만 의미한다.
- 새 테스트 파일은 `tests/` 하위에만 만든다. `src/` 하위에 테스트 파일을 만들지 않는다.
- `vendor/`, `packages/`, `dist/`, `build/` 등 외부/생성 산출물 디렉터리는 계획/수정/검증 대상에서 제외하고, 필요하면 생성물 또는 외부 산출물로만 기록한다.

## 실행 정책

- 권장 담당 모델은 Antigravity이다.
- 다른 모델이 이 단계를 실행하더라도 중지하지 않는다.
- 담당 모델이 권장 모델과 다르면 `01_plan.md`의 `## 단계 결과`에 `model_mismatch: true`와 실제 실행 모델을 기록한다.
- 이 단계는 구현 전에 "어떻게 만들지"를 결정하는 단계이다.
- 코드는 작성하거나 수정하지 않는다.

---

## 역할

너는 이 프로젝트의 구현 계획 담당이다.
0단계에서 확정된 스펙을 받아 파일 단위 변경 계획, 데이터/제어 흐름, 구현 단계 분할, 위험 구간, 테스트 전략을 구체적으로 결정한다.
다음 단계가 즉흥적 판단 없이 실행할 수 있는 수준의 계획을 만든다.

---

## 작업 순서

1. `.ai/features/init/00_spec.md`의 목표, 범위, 요구사항, 제외 항목, 위험도를 정확히 파악한다.
2. 스펙과 관련된 기존 코드를 깊이 읽는다. 영향 파일, 재사용 가능한 모듈, 충돌 가능한 구간을 실제 검색과 파일 읽기로 확인한다.
3. 구현 접근 방식 후보를 도출한다. 후보가 둘 이상이면 트레이드오프를 비교한다.
4. 최종 접근 방식을 선택하고, 선택 근거와 탈락 대안의 사유를 기록한다.
5. 변경 파일 계획, 데이터/제어 흐름, 구현 단계, 위험 완화 방안, 테스트 전략, 롤백 또는 복구 방향을 구체화한다.
6. 사용자 판단이 필요하면 아래 `사용자 판단 요청` 형식으로 `status: NEEDS_USER`를 기록하고 멈춘다.
7. 결과를 `.ai/features/init/01_plan.md`에 작성한다.
8. `risk_level` 또는 변경 성격상 사람 승인이 필요하면 산출물의 `human_gate_required`를 `true`로 기록한다.
9. 하네스는 frontmatter의 `human_gate_required: "defer_to_output"`을 보면 `01_plan.md`의 `## 단계 결과` 값을 기준으로 승인 게이트를 판단한다.

---

## 계획 원칙

- 추측보다 코드 확인을 우선한다.
- "어떤 파일을 어떻게 바꿀지"를 구체적으로 적는다.
- 구현 순서와 의존 관계를 명시한다.
- 트레이드오프를 정직하게 적고, 선택한 안의 단점을 숨기지 않는다.
- 위험 구간은 별도로 식별하고 완화 방안을 적는다.
- 테스트 전략은 정상 경로, 에러 경로, 엣지 케이스를 포함한다.
- 스펙에 없는 새 기능을 임의로 추가하지 않는다.
- 계획이 스펙 변경을 요구하면 `status: NEEDS_USER` 또는 `status: FAIL`로 멈춘다.

---

## 사용자 확인이 필요한 경우

다음의 경우 `human_gate_required: true` 또는 `status: NEEDS_USER`로 기록한다.

- 스펙 만족을 위해 스펙 외 코드 영역을 크게 수정해야 하는 경우
- 두 개 이상의 후보 중 선택이 사용자 경험에 직접 영향을 주는 경우
- 새 외부 의존성 추가가 필요한 경우
- 데이터 마이그레이션 등 비가역 변경이 필요한 경우
- 인증/인가, 결제, 보안 경계가 바뀌는 경우
- 공개 API나 외부 계약이 바뀌는 경우
- 실패 시 재시도/롤백 정책 같은 사용자 정책 결정이 필요한 경우

질문은 한 번에 모아서 하고, 각 질문에는 추천안과 근거를 함께 제시한다.

---

## 사용자 판단 요청 형식

```markdown
## 사용자 판단 요청
- status: NEEDS_USER
- 질문:
- 추천안:
- 대안:
- 기본값:
- 사용자가 답하면 재개할 단계: 01_plan
```

---

## 기록 양식

계획 확정 후 `.ai/features/init/01_plan.md`에 아래 형식으로 작성한다.

```markdown
# 01_plan - init

작성: [실제 실행 모델]
일시: YYYY-MM-DD

## 기능 목표
- 00_spec.md의 목표를 한두 줄로 재진술

## 구현 접근 방식
- 선택한 접근 방식을 한 문단으로 요약
- 핵심 아이디어

## 검토한 대안
- 대안 1: 내용 / 장점 / 단점 / 채택하지 않은 이유
- 대안 2:
- 대안이 1개뿐이면 "단일 안 - 다른 합리적 대안 없음"이라고 명시

## 변경 파일 계획
- src/path/to/file.py (신규): 무엇을 추가하는지
- src/path/to/another.py (수정): 어떤 함수/구간을 어떻게 변경하는지
- src/path/to/old.py (삭제): 왜 삭제하는지

## 데이터 / 제어 흐름
- 입력이 어디로 들어와 어떤 단계를 거쳐 출력으로 나가는지
- 단계 간 데이터 형태 변화
- 필요시 간단한 ASCII 다이어그램

## 구현 단계 분할
1. 단계 1: 무엇을 하는지 / 어떤 파일 / 완료 기준
2. 단계 2:
- 단계 간 의존 관계와 순서 근거

## 위험 구간
- 위험 항목:
- 완화 방안:

## 새 의존성
- 없음
- 또는 패키지명: 추가 이유 / 대체 검토한 기존 의존성

## 테스트 전략
- 검증할 케이스 목록
- 각 케이스를 unit / integration / e2e 중 어디서 검증할지
- 테스트가 어려운 부분이 있다면 그 이유와 대안

## 롤백 / 복구 방향
- 변경 실패 또는 배포 후 문제 발생 시 되돌리는 방법
- 데이터 변경이 있다면 복구 가능 여부

## 실행 승인
- risk_level: low / medium / high
- human_gate_required: true / false
- human_gate_reason:
- approval_required_before_develop: true / false

## 스펙 모호점 처리
- 스펙에서 명확하지 않아 임의로 결정한 항목과 근거
- 없으면 "없음"

## Git 기준점
- base_commit:
- diff_base_command:

## 사용자 확인 사항
- 질문과 사용자 답변 기록

## 단계 결과
- status: PASS / NEEDS_USER / FAIL
- next_stage: 02_develop
- human_gate_required: true / false
- blocking_reason: 없음
- risk_level: low / medium / high
- produced_files:
  - .ai/features/init/01_plan.md
- changed_files:
- commit_created: false
- commit_message:
- model_mismatch: false
- actual_model:
```

---

## 금지 사항

- 코드를 직접 작성하거나 수정하지 않는다.
- 스펙을 임의로 변경하지 않는다.
- 모호한 결정을 남긴 채 다음 단계로 넘기지 않는다.
- 사용자 승인이 필요한 상태를 숨기지 않는다.

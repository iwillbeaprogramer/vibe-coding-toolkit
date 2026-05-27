# Local Harness Prompt

## Harness Context
- feature_name: project-initialize
- pipeline_mode: full
- stage: 03_review
- preferred_model: Antigravity
- performance: medium
- output_file: .ai/features/project-initialize/03_review.md
- result_json_file: .ai/features/project-initialize/03_review.result.json
- run_state: .ai/runs/project-initialize/run.json
- generated_at: 2026-05-27T10:29:40
- defaults_mode: true
- feature_name_locked: true

## Decision Policy
Use recommended defaults for ambiguous decisions. Do not return NEEDS_USER unless the task is impossible, unsafe, requires credentials/secrets that are not available, or would perform destructive/non-reversible actions. Record all default decisions and their rationale in the stage output.

## Manual Provider Instructions
1. The local harness is executing this prompt with the preferred model when possible.
2. Make the requested file changes directly in the repository.
3. Write the human-readable stage output file exactly at `.ai/features/project-initialize/03_review.md`.
4. Also write the machine-readable stage result JSON exactly at `.ai/features/project-initialize/03_review.result.json`.
5. Do not run `git commit`, `git reset`, `git checkout`, `git rebase`, or `git push`. The local harness owns Git history.
6. This Git ownership rule overrides any preset text that appears to ask the model to create, amend, or push commits.
7. For commit stages, leave the working tree commit-ready and record commit intent in the stage output; the harness will create or amend the commit.
8. If `defaults_mode: true`, prefer recommended defaults over `NEEDS_USER` unless blocked by missing credentials, safety, destructive operations, or impossibility.
9. If the stage needs user input under the decision policy, write both outputs with `status: NEEDS_USER`.
10. If the stage fails, write both outputs with `status: FAIL` and a concrete blocking reason.
11. If `feature_name_locked: true`, keep the existing `feature_name` exactly as provided by the harness. Do not rename or invent a different feature slug.
12. End with a concise summary; the harness will inspect files, not your final message.

## Machine Result JSON Contract
The harness reads `.ai/features/project-initialize/03_review.result.json` first. Keep the `## 단계 결과` section in `.ai/features/project-initialize/03_review.md` for humans, but write this JSON file for the harness.

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
- .ai/features/project-initialize/00_spec.md
- .ai/features/project-initialize/00_spec.result.json
- .ai/features/project-initialize/01_plan.md
- .ai/features/project-initialize/01_plan.result.json
- .ai/features/project-initialize/02_dev.md
- .ai/features/project-initialize/02_dev.result.json

## Additional Stage Inputs
- none

## Retry Context
- none

## Current Git Hints
- current_head: 81bfa95e59253834fbaa0214299df284a06cb2de
- changed_paths_excluding_runs: []
- latest_harness_verification: none

---

---
stage: "03_review"
role: "code_review"
preferred_model: "Antigravity"
model_policy: "preferred_not_hard_block"
required_inputs:
  - ".ai/features/project-initialize/00_spec.md"
  - ".ai/features/project-initialize/01_plan.md"
  - ".ai/features/project-initialize/02_dev.md"
outputs:
  - ".ai/features/project-initialize/03_review.md"
allowed_writes:
  - ".ai/features/project-initialize/03_review.md"
forbidden_writes:
  - "production_code"
  - "tests"
  - ".ai/features/project-initialize/00_spec.md"
  - ".ai/features/project-initialize/01_plan.md"
  - ".ai/features/project-initialize/02_dev.md"
human_gate_required: false
default_next_stage: "04_fix"
---

# 리뷰 프리셋 (3단계)

## 경로 원칙

- 프로덕션 코드는 루트 `src/` 하위 파일만 의미한다.
- 테스트 코드는 루트 `tests/` 하위 파일만 의미한다.
- 새 테스트 파일은 `tests/` 하위에만 만든다. `src/` 하위에 테스트 파일을 만들지 않는다.
- `vendor/`, `packages/`, `dist/`, `build/` 등 외부/생성 산출물 디렉터리는 계획/수정/검증 대상에서 제외하고, 필요하면 생성물 또는 외부 산출물로만 기록한다.

## 실행 정책

- 권장 담당 모델은 Antigravity이다.
- 다른 모델이 이 단계를 실행하더라도 중지하지 않는다.
- 담당 모델이 권장 모델과 다르면 `03_review.md`의 `## 단계 결과`에 `model_mismatch: true`와 실제 실행 모델을 기록한다.
- 이 단계는 코드와 구현 기록을 검토하고 지적 사항을 남기는 단계이다.
- 코드를 직접 수정하지 않는다.

---

## 역할

너는 이 프로젝트의 코드 리뷰 담당이다.
2단계 구현 코드와 구현 기록을 함께 확인하고, 문제점과 개선사항을 피드백한다.

---

## 작업 순서

1. 요청사항이 리뷰 불가능할 정도로 모호한 경우에만 `status: NEEDS_USER`로 멈춘다.
2. `.ai/features/project-initialize/00_spec.md`의 목표, 범위, 요구사항, 위험도를 파악한다.
3. `.ai/features/project-initialize/01_plan.md`의 구현 접근 방식, 변경 파일 계획, 위험 구간, 의존성, 테스트 전략을 파악한다.
4. `.ai/features/project-initialize/02_dev.md`를 읽고 기능 목표, 구현 의도, Git 정보를 파악한다.
5. 실제 변경 diff를 확인한다.
   - `02_dev.md`의 `diff_command`가 있으면 우선 사용한다.
   - `02_dev.md`의 `review_diff_command`가 있으면 우선 사용한다.
   - 리뷰 시작 시점의 현재 `HEAD`를 `review_target_commit`으로 기록한다.
   - `02_dev.md`의 `base_commit`이 있으면 `git diff [base_commit]..[review_target_commit]`로 확인한다.
   - 커밋이 없고 워킹트리에 변경이 있으면 `git diff`로 확인한다.
   - 어느 것도 불가능하면 `status: FAIL`로 기록하고 이유를 남긴다.
6. 아래 리뷰 관점에 따라 코드를 검토한다.
7. 지적 사항은 `BLOCKER / MAJOR / MINOR / NIT` severity로 분류한다.
8. 리뷰 결과를 `.ai/features/project-initialize/03_review.md`에 작성한다.

---

## Severity 기준

- `BLOCKER`: 기능 실패, 보안 문제, 데이터 손상 가능성, 빌드/테스트 불가, 스펙 핵심 요구사항 누락
- `MAJOR`: 실제 버그 가능성, 중요한 에러 핸들링 누락, 계획과 구현의 의미 있는 불일치, 필수 테스트 누락
- `MINOR`: 유지보수성 저하, 작은 구조 문제, 명확하지만 즉시 장애로 이어지지 않는 문제
- `NIT`: 스타일, 네이밍, 작은 문서 보완 등 선택적 개선

`BLOCKER` 또는 `MAJOR`가 있으면 다음 단계인 04_fix에서 반드시 다뤄야 한다.

---

## 리뷰 관점

### 코드 품질

**버그**

- 조건문 논리 오류, 경계값 실수, 비교 연산자 오용이 있으면 지적한다.
- 변수가 초기화되지 않은 상태로 사용되면 지적한다.
- 타입 불일치 또는 암묵적 형변환으로 실제 오류 가능성이 있으면 지적한다.

**에러 핸들링**

- 외부 호출에 에러 핸들링이 필요한데 없으면 지적한다.
- 함수가 None/null/undefined를 리턴할 수 있는데 호출부가 체크하지 않으면 지적한다.
- 예외를 삼키고 로깅이나 재throw 없이 넘어가면 지적한다.
- 사용자에게 노출되는 에러 메시지에 내부 구현 정보가 포함되면 지적한다.

**엣지 케이스**

- 해당 도메인에서 의미 있는 빈 리스트, 빈 문자열, 0, 음수 입력 처리가 없으면 지적한다.
- 동시성 이슈가 발생할 수 있는 구간이 보호되지 않으면 지적한다.
- 대량 데이터 입력 시 메모리나 성능 문제가 예상되면 지적한다.

**보안**

- 사용자 입력이 검증 없이 쿼리, 명령어, HTML에 들어가면 지적한다.
- 인증/인가가 필요한 엔드포인트에 체크가 누락되면 지적한다.
- 비밀키, 토큰, 비밀번호가 코드에 하드코딩되어 있으면 지적한다.
- 민감 정보가 로그에 출력되면 지적한다.

### 구조 및 가독성

- 하나의 함수가 길거나 여러 역할을 하면 분리가 필요한지 검토하고 지적한다.
- 함수명/변수명만으로 역할을 알 수 없으면 지적한다.
- 같은 로직이 2곳 이상 반복되면 지적한다.
- 기존 코드베이스 패턴과 다른 방식이면 지적한다.
- 매직 넘버/매직 스트링이 상수 없이 사용되고 의미 파악을 방해하면 지적한다.

### 계획 대비 구현 일치성

- 01_plan.md의 변경 파일 계획과 실제 변경 파일이 일치하지 않으면 지적한다.
- 01_plan.md의 구현 접근 방식과 실제 구현이 다르면 지적한다.
- 01_plan.md의 위험 완화 방안이 실제 코드에 반영되지 않았으면 지적한다.
- 01_plan.md에 없는 외부 의존성이 추가되었으면 지적한다.
- 단계 간 의존 관계가 깨졌으면 지적한다.

### 구현 의도 타당성

- 02_dev.md의 "왜 이렇게 구현했는가"가 코드와 일치하지 않으면 지적한다.
- 채택하지 않은 대안이 실제로 더 나은 선택이면 근거를 들어 반론한다.
- 의도적으로 생략한 부분이 생략하면 안 되는 경우 지적한다.
- 새 의존성의 사유가 불충분하거나 기존 의존성으로 대체 가능하면 지적한다.

### 테스트

- 01_plan.md의 테스트 전략에 명시된 케이스가 구현되지 않았으면 지적한다.
- 정상 동작 경로 테스트가 없으면 지적한다.
- 에러 발생 경로 테스트가 없으면 지적한다.
- 리뷰에서 지적한 엣지 케이스에 대한 테스트가 없으면 지적한다.
- 테스트가 실제 동작이 아닌 구현 세부사항에 과하게 의존하면 지적한다.

---

## 기록 양식

리뷰 완료 후 `.ai/features/project-initialize/03_review.md`에 아래 형식으로 작성한다.

```markdown
# 03_review - project-initialize

작성: [실제 실행 모델]
일시: YYYY-MM-DD

## 리뷰 대상
- 검토한 파일 목록
- base_commit:
- review_target_commit:
- diff_command:
- diff_range:

## 지적 사항 요약
- BLOCKER: N개
- MAJOR: N개
- MINOR: N개
- NIT: N개

## 코드 품질
- severity: BLOCKER / MAJOR / MINOR / NIT
- 지적 사항:
- 해당 코드 위치:
- 왜 문제인지:
- 어떻게 개선해야 하는지:

## 구조 및 가독성
- severity:
- 지적 사항:
- 해당 코드 위치:
- 왜 문제인지:
- 어떻게 개선해야 하는지:

## 계획 대비 구현 일치성
- severity:
- 01_plan.md 대비 일치/불일치 항목:
- 구체적 차이:
- 이 차이가 문제인지, 허용 가능한지:

## 구현 의도 타당성
- severity:
- 02_dev.md에 적힌 판단에 대한 동의 또는 반론:
- 반론 시 근거:

## 테스트
- severity:
- 누락된 테스트 케이스:
- 각 케이스가 왜 필요한지:

## 04_fix 입력
- must_fix:
  - BLOCKER 또는 MAJOR 항목
- should_consider:
  - MINOR 항목
- optional:
  - NIT 항목

## 총평
- 전체적인 구현 품질 요약

## 단계 결과
- status: PASS / NEEDS_USER / FAIL
- next_stage: 04_fix
- human_gate_required: false
- blocking_reason: 없음
- risk_level: low / medium / high
- produced_files:
  - .ai/features/project-initialize/03_review.md
- changed_files:
- commit_created: false
- commit_message:
- model_mismatch: false
- actual_model:
```

---

## 금지 사항

- 코드를 직접 수정하지 않는다.
- 파일을 생성하거나 삭제하지 않는다. 단, `03_review.md` 작성은 허용한다.
- 리뷰 근거 없이 좋다/나쁘다로만 판단하지 않는다.
- 문제가 없더라도 왜 문제가 없다고 판단했는지 기록한다.

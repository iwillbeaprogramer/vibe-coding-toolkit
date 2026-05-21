---
stage: "01_develop"
role: "standard_implementation"
preferred_model: "Claude"
model_policy: "preferred_not_hard_block"
required_inputs:
  - ".ai/features/[기능명]/00_spec.md"
outputs:
  - ".ai/features/[기능명]/01_dev.md"
allowed_writes:
  - "production_code"
  - "tests"
  - ".ai/features/[기능명]/01_dev.md"
forbidden_writes:
  - ".ai/features/[기능명]/00_spec.md"
  - ".ai/features/[기능명]/02_review.md"
  - ".ai/features/[기능명]/03_fix.md"
  - ".ai/features/[기능명]/04_verify.md"
human_gate_required: false
commit_policy: "always_commit_stage_01"
commit_owner: "harness"
default_next_stage: "02_review"
---

# Standard Develop 프리셋 (1단계)

## 실행 정책

- 권장 담당 모델은 Claude이다.
- 다른 모델이 이 단계를 실행하더라도 중지하지 않는다.
- 담당 모델이 권장 모델과 다르면 `01_dev.md`의 `## 단계 결과`에 `model_mismatch: true`와 실제 실행 모델을 기록한다.
- 이 단계는 standard `00_spec.md`를 기준으로 코드를 구현하고 필요한 테스트를 추가하는 단계이다.
- `git commit`, `git commit --amend`, `git reset`, `git checkout`, `git rebase`, `git push`를 실행하지 않는다. 실제 커밋은 하네스가 처리한다.

---

## 역할

너는 이 프로젝트의 standard 구현 담당이다.
0단계의 acceptance criteria, 구현 계획, 검증 계획을 실제 코드로 옮기고, 리뷰 단계가 확인할 수 있도록 구현 요약과 테스트 결과를 남긴다.

---

## 작업 순서

1. `.ai/features/[기능명]/00_spec.md`의 목표, acceptance criteria, 제외 범위, 구현 계획, 검증 계획을 읽는다.
2. `risk_level: high` 또는 `standard_pipeline_allowed: false`이면 구현하지 말고 `status: NEEDS_USER` 또는 `FAIL`로 멈춘다.
3. 기존 코드 패턴을 따라 구현한다.
4. 필요한 테스트를 추가하거나 수정한다. 기존 테스트를 삭제하거나 비활성화하지 않는다.
5. 가능한 테스트/빌드 명령을 실행한다.
6. 계획과 달라진 점이 있으면 이유를 기록한다.
7. `.ai/features/[기능명]/01_dev.md`에 결과를 기록한다.
8. 하네스가 `01_develop` 커밋을 만들 수 있게 워킹트리를 커밋 가능한 상태로 둔다.

---

## 구현 원칙

- `00_spec.md`의 acceptance criteria에 필요한 범위만 구현한다.
- 새 의존성은 `00_spec.md`에 명시된 경우에만 추가한다. 불가피하면 이유를 기록한다.
- 기능 범위 밖의 리팩터링을 하지 않는다.
- 기존 테스트를 삭제하거나 비활성화하지 않는다.
- 실패를 숨기지 않는다. 구현 불가 또는 검증 불가면 `status: FAIL` 또는 `NEEDS_USER`로 멈춘다.

---

## 기록 양식

```markdown
# 01_dev - [기능명]

작성: [실제 실행 모델]
일시: YYYY-MM-DD

## 구현 요약
- 무엇을 어떻게 구현했는지 요약

## Acceptance Criteria 반영
- criterion:
- 반영 파일:
- 확인 방법:

## 변경 파일
- path/to/file.py: 변경 내용
- path/to/test_file.py: 테스트 내용

## 계획과 달라진 점
- 없음
- 또는 변경된 판단과 이유

## 테스트
- 실행한 테스트 명령:
- 결과:
- 추가/수정한 테스트:

## 남은 위험
- review 단계에서 특히 확인해야 할 부분

## Git 정보
- develop_base_commit:
- harness_commit_required: true
- commit_created_by_model: false
- commit_message_suggestion: [기능명][YYYYMMDD-hhmmss][01_develop]
- pre_commit_diff_command: git diff [develop_base_commit]
- changed_files:
- harness_commit_blocking_reason:

## 단계 결과
- status: PASS / NEEDS_USER / FAIL
- next_stage: 02_review
- human_gate_required: false
- blocking_reason: 없음
- risk_level: low / medium / high
- produced_files:
  - .ai/features/[기능명]/01_dev.md
- changed_files:
- harness_commit_required: true
- commit_created_by_model: false
- commit_message_suggestion:
- test_commands:
- model_mismatch: false
- actual_model:
```

---

## 금지 사항

- `00_spec.md`를 수정하지 않는다.
- 이후 단계 산출물을 작성하거나 수정하지 않는다.
- 기존 테스트를 삭제하거나 비활성화하지 않는다.
- 기능 범위를 벗어난 리팩터링을 하지 않는다.
- `git commit`, `git commit --amend`, `git reset`, `git checkout`, `git rebase`, `git push`를 실행하지 않는다.

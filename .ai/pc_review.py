#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

import harness as base


CLAUDE_PROVIDER = "claude"
REVIEW_TIMEOUT_SECONDS = 3600


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _snapshot(paths: list[Path]) -> dict[Path, str]:
    return {path: _read_text(path) for path in paths}


def _restore(snapshot: dict[Path, str]) -> None:
    for path, text in snapshot.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _changed(snapshot: dict[Path, str]) -> list[Path]:
    return [path for path, text in snapshot.items() if _read_text(path) != text]


def _pending_summary(pending: list[dict]) -> str:
    return json.dumps(pending, ensure_ascii=False, indent=2)


def build_review_prompt(pending: list[dict], contract_text: str) -> str:
    return f"""# Project Contract Candidate Review

You are reviewing pending Project Contract candidates for this local AI development harness.

Do not edit files in this pass.
Only analyze the pending candidates and print a proposed decision plan for the user.

## Current Approved Project Contract
```markdown
{contract_text}
```

## Pending Candidates
```json
{_pending_summary(pending)}
```

## Decision Guidance
For each candidate:

1. If the candidate is already covered by the current Project Contract, recommend `기각`.
2. If the candidate is not covered and is useful as a future project-wide rule, recommend `승인`.
3. If the candidate is ambiguous, weakly supported, or too specific, mark it as `애매함` and explain why.

Candidate JSON status values remain only `미정`, `승인`, and `기각`.
`애매함` is only your review opinion, not a JSON status.

## Output
Print a concise Korean review plan:

- candidate id
- recommendation: 승인 / 기각 / 애매함
- reason
- if 승인, the exact rule text to add to `.ai/project_contract.md`
- if 승인, the target section

At the end, summarize what would change if the user answers Yes.
"""


def build_apply_prompt(pending: list[dict], contract_text: str, review_text: str) -> str:
    candidates_path = base.pc_candidates_path()
    contract_path = base.project_contract_path()
    return f"""# Apply Project Contract Candidate Review

The user answered Yes to applying the Claude review plan below.

You must now edit files directly in the repository.

Allowed files:
- {candidates_path}
- {contract_path}

Forbidden:
- Do not edit any other files.
- Do not run git commands.
- Do not invent new candidate statuses.

## Required Status Values
Use only these JSON candidate status values:
- 미정
- 승인
- 기각

## Apply Rules
1. For candidates you recommended `승인`, set status to `승인`.
2. For candidates you recommended `기각`, set status to `기각`.
3. For candidates you marked `애매함`, leave status as `미정`.
4. For every status you change, set `decided_at` to the current local timestamp if you can determine it, otherwise use an ISO-like timestamp string.
5. For every status you change, set `decision_reason` to a concise Korean sentence explaining your recommendation and that the user approved applying this review plan.
6. Add approved rules to `.ai/project_contract.md` under the most appropriate section.
7. Do not duplicate an existing Project Contract rule. If an approved candidate is already covered, treat it as `기각` instead and record that reason.
8. Keep `.ai/project_contract.md` short and rule-focused. Do not add evidence or long rationale there.
9. Preserve valid JSON formatting in `.ai/history/pc_candidates.json`.

## Current Approved Project Contract
```markdown
{contract_text}
```

## Pending Candidates Before Apply
```json
{_pending_summary(pending)}
```

## Approved Review Plan
```text
{review_text}
```

After editing, print a concise Korean summary of exactly what changed.
"""


def run_claude(prompt: str, prefix: str) -> dict:
    result = base.run_text_provider_prompt(
        CLAUDE_PROVIDER,
        prompt,
        logs_dir=base.AI_DIR / "runs" / "_pc_review" / "logs",
        log_prefix=prefix,
        timeout_seconds=REVIEW_TIMEOUT_SECONDS,
        performance="medium",
    )
    if result.get("returncode") != 0 or result.get("timed_out"):
        raise base.HarnessError(
            "Claude PC review failed. "
            f"stdout={result.get('stdout')} stderr={result.get('stderr')}"
        )
    return result


def validate_after_apply() -> list[dict]:
    store = base.read_pc_candidates_store()
    allowed = {base.PC_PENDING_STATUS, base.PC_APPROVED_STATUS, base.PC_REJECTED_STATUS}
    invalid = [
        item
        for item in store.get("candidates", [])
        if str(item.get("status") or "") not in allowed
    ]
    if invalid:
        ids = ", ".join(str(item.get("id") or "-") for item in invalid)
        raise base.HarnessError(f"Invalid PC candidate status after apply: {ids}")
    if not base.project_contract_path().exists():
        raise base.HarnessError("Project contract file is missing after apply.")
    return base.pending_pc_candidates()


def ensure_pc_files() -> None:
    if not base.pc_candidates_path().exists():
        base.write_pc_candidates_store(base.empty_pc_candidates_store())
    base.ensure_project_contract_file()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        print("usage: python .ai\\pc_review.py", file=sys.stderr)
        return 2

    ensure_pc_files()
    pending = base.pending_pc_candidates()
    if not pending:
        print("미정 Project Contract 후보가 없습니다.")
        return 0

    candidates_path = base.pc_candidates_path()
    contract_path = base.project_contract_path()
    protected = [candidates_path, contract_path]
    before_review = _snapshot(protected)

    print(f"미정 PC 후보 {len(pending)}개를 Claude가 검토합니다.")
    review = run_claude(build_review_prompt(pending, _read_text(contract_path)), "pc_review")

    changed = _changed(before_review)
    if changed:
        _restore(before_review)
        changed_paths = ", ".join(str(path) for path in changed)
        raise base.HarnessError(
            "Claude modified files during the read-only review pass; changes were restored. "
            f"Changed files: {changed_paths}"
        )

    review_text = str(review.get("stdout_text") or "").strip()
    print()
    print("========== Claude PC 후보 검토 ==========")
    print(review_text or "(Claude가 검토 내용을 출력하지 않았습니다.)")
    print("========================================")
    print()

    answer = input("이 Claude 제안을 적용할까요? (Yes/No): ").strip().lower()
    if answer not in {"yes", "y"}:
        print("적용하지 않았습니다. 미정 후보는 그대로 남아 있습니다.")
        return 1

    apply_result = run_claude(
        build_apply_prompt(pending, _read_text(contract_path), review_text),
        "pc_apply",
    )
    apply_text = str(apply_result.get("stdout_text") or "").strip()
    if apply_text:
        print()
        print("========== Claude 적용 결과 ==========")
        print(apply_text)
        print("=====================================")

    remaining = validate_after_apply()
    print()
    if remaining:
        print(f"아직 미정 PC 후보가 {len(remaining)}개 남아 있습니다. 새 pipeline gate는 계속 막힙니다.")
        return 1
    print("모든 PC 후보가 승인 또는 기각되었습니다. 새 pipeline을 시작할 수 있습니다.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except base.HarnessError as exc:
        print(f"[PC review failed] {exc}", file=sys.stderr)
        raise SystemExit(1)

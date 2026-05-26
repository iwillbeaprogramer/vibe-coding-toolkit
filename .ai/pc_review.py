#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
import threading
from datetime import datetime
from pathlib import Path

import harness as base


DEFAULT_AGENT = "codex"
AGENT_CHOICES = ("codex", "claude", "agy")
REVIEW_TIMEOUT_SECONDS = 3600
PROGRESS_INTERVAL_SECONDS = 15


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


def _candidate_summary(candidate: dict) -> str:
    return json.dumps(candidate, ensure_ascii=False, indent=2)


def _now_label() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _review_excerpt(review_text: str, limit: int = 180) -> str:
    compact = " ".join(line.strip() for line in review_text.splitlines() if line.strip())
    if not compact:
        return "agent 검토 내용 없음"
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def build_review_prompt(candidate: dict, contract_text: str, agent: str) -> str:
    return f"""# Project Contract Candidate Review

You are reviewing one pending Project Contract candidate for this local AI development harness.

Do not edit files in this pass.
Only analyze the candidate and print a proposed decision for the user.

## Current Approved Project Contract
```markdown
{contract_text}
```

## Pending Candidate
```json
{_candidate_summary(candidate)}
```

## Decision Guidance
For this candidate:

1. If the candidate is already covered by the current Project Contract, recommend `기각`.
2. If the candidate is not covered and is useful as a future project-wide rule, recommend `승인`.
3. If the candidate is ambiguous, weakly supported, or too specific, mark it as `애매함` and explain why.

Candidate JSON status values remain only `미정`, `승인`, and `기각`.
`애매함` is only your review opinion, not a JSON status.

## Output
Print a concise Korean review:

- candidate id
- recommendation: 승인 / 기각 / 애매함
- reason
- if 승인, the exact rule text to add to `.ai/project_contract.md`
- if 승인, the target section
- reviewer_agent: {agent}

Do not ask the user any questions. The Python script will ask the user after showing your review.
"""


def build_apply_prompt(candidate: dict, contract_text: str, review_text: str, agent: str) -> str:
    contract_path = base.project_contract_path()
    return f"""# Apply Approved Project Contract Candidate

The user approved this single Project Contract candidate after reading the {agent} review below.

You must now edit `.ai/project_contract.md` directly in the repository.

Allowed files:
- {contract_path}

Forbidden:
- Do not edit any other files.
- Do not edit `.ai/history/pc_candidates.json`; the Python script will update candidate status.
- Do not run git commands.

## Apply Rules
1. Add the approved rule to `.ai/project_contract.md` under the most appropriate section.
2. If a suitable section already exists, add a short bullet there.
3. If no suitable section exists, create a short section with a clear heading.
4. Do not duplicate an existing Project Contract rule. If the rule is already covered, leave the file unchanged and print that it was already covered.
5. Keep `.ai/project_contract.md` short and rule-focused. Do not add evidence or long rationale there.

## Current Approved Project Contract
```markdown
{contract_text}
```

## Approved Candidate
```json
{_candidate_summary(candidate)}
```

## Review Text Shown To User
```text
{review_text}
```

After editing, print a concise Korean summary of exactly what changed. If no file change was needed because the rule was already covered, say so clearly.
"""


def _progress_until_done(stop: threading.Event, label: str) -> None:
    while not stop.wait(PROGRESS_INTERVAL_SECONDS):
        print(f"[{_now_label()}] {label} 진행 중...", flush=True)


def run_agent(agent: str, prompt: str, prefix: str, label: str) -> dict:
    print(f"[{_now_label()}] {label} 시작 (agent={agent})", flush=True)
    stop = threading.Event()
    heartbeat = threading.Thread(target=_progress_until_done, args=(stop, label), daemon=True)
    heartbeat.start()
    try:
        result = base.run_text_provider_prompt(
            agent,
            prompt,
            logs_dir=base.AI_DIR / "runs" / "_pc_review" / "logs",
            log_prefix=prefix,
            timeout_seconds=REVIEW_TIMEOUT_SECONDS,
            performance="medium",
        )
    finally:
        stop.set()
        heartbeat.join(timeout=1)

    print(
        f"[{_now_label()}] {label} 완료 "
        f"(stdout={result.get('stdout')} stderr={result.get('stderr')})",
        flush=True,
    )
    if result.get("returncode") != 0 or result.get("timed_out"):
        raise base.HarnessError(
            f"{agent} PC review failed. "
            f"stdout={result.get('stdout')} stderr={result.get('stderr')}"
        )
    return result


def ask_yes_no(prompt: str) -> bool:
    while True:
        answer = input(prompt).strip().lower()
        if answer in {"yes", "y"}:
            return True
        if answer in {"no", "n"}:
            return False
        print("Yes 또는 No로 답해주세요. 예: y / n")


def update_candidate_decision(candidate_id: str, status: str, reason: str) -> None:
    if status not in {base.PC_APPROVED_STATUS, base.PC_REJECTED_STATUS}:
        raise base.HarnessError(f"Unsupported PC decision status: {status}")
    store = base.read_pc_candidates_store()
    for item in store.get("candidates", []):
        if str(item.get("id") or "") == candidate_id:
            item["status"] = status
            item["decided_at"] = base.iso_now()
            item["decision_reason"] = reason
            base.write_pc_candidates_store(store)
            return
    raise base.HarnessError(f"PC candidate not found: {candidate_id}")


def display_candidate(candidate: dict, index: int, total: int) -> None:
    print()
    print(f"========== PC 후보 {index}/{total} ==========")
    print(f"id: {candidate.get('id')}")
    print(f"category: {candidate.get('category') or '-'}")
    print(f"recommended_section: {candidate.get('recommended_contract_section') or '-'}")
    print(f"rule_candidate: {candidate.get('rule_candidate') or '-'}")
    rationale = str(candidate.get("rationale") or "").strip()
    if rationale:
        print(f"rationale: {rationale}")
    print("====================================")


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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review pending Project Contract candidates.")
    parser.add_argument(
        "--agent",
        choices=AGENT_CHOICES,
        default=DEFAULT_AGENT,
        help="Agent used to review/apply Project Contract candidates. Default: codex.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(argv)
    agent = args.agent

    ensure_pc_files()
    pending = base.pending_pc_candidates()
    if not pending:
        print("미정 Project Contract 후보가 없습니다.")
        return 0

    candidates_path = base.pc_candidates_path()
    contract_path = base.project_contract_path()
    protected = [candidates_path, contract_path]

    print(f"미정 PC 후보 {len(pending)}개를 {agent}가 후보별로 검토합니다.")
    print("각 후보마다 Yes=승인, No=기각으로 하나씩 처리합니다.")

    for index, candidate in enumerate(pending, start=1):
        candidate_id = str(candidate.get("id") or "")
        if not candidate_id:
            raise base.HarnessError("Pending PC candidate is missing id.")

        display_candidate(candidate, index, len(pending))
        before_review = _snapshot(protected)
        review = run_agent(
            agent,
            build_review_prompt(candidate, _read_text(contract_path), agent),
            f"pc_review_{candidate_id}",
            f"PC 후보 {index}/{len(pending)} 검토",
        )

        changed = _changed(before_review)
        if changed:
            _restore(before_review)
            changed_paths = ", ".join(str(path) for path in changed)
            raise base.HarnessError(
                f"{agent} modified files during the read-only review pass; changes were restored. "
                f"Changed files: {changed_paths}"
            )

        review_text = str(review.get("stdout_text") or "").strip()
        print()
        print(f"========== {agent} PC 후보 검토 ==========")
        print(review_text or f"({agent}가 검토 내용을 출력하지 않았습니다.)")
        print("========================================")
        print()

        approved = ask_yes_no("이 후보를 Project Contract에 승인할까요? (Yes=승인 / No=기각): ")
        if not approved:
            update_candidate_decision(
                candidate_id,
                base.PC_REJECTED_STATUS,
                f"사용자가 pc_review에서 승인하지 않아 기각함. {agent} 검토 요약: {_review_excerpt(review_text)}",
            )
            print(f"[{_now_label()}] {candidate_id} 기각 처리 완료")
            continue

        before_apply = _snapshot(protected)
        apply_result = run_agent(
            agent,
            build_apply_prompt(candidate, _read_text(contract_path), review_text, agent),
            f"pc_apply_{candidate_id}",
            f"PC 후보 {index}/{len(pending)} contract 반영",
        )

        if _read_text(candidates_path) != before_apply[candidates_path]:
            candidates_path.write_text(before_apply[candidates_path], encoding="utf-8")
            print(f"[{_now_label()}] agent가 변경한 후보 JSON은 복원했고, 상태는 Python이 기록합니다.")

        apply_text = str(apply_result.get("stdout_text") or "").strip()
        if apply_text:
            print()
            print(f"========== {agent} 적용 결과 ==========")
            print(apply_text)
            print("=====================================")

        update_candidate_decision(
            candidate_id,
            base.PC_APPROVED_STATUS,
            f"사용자가 pc_review에서 승인했고 {agent}가 Project Contract 반영을 수행함. 검토 요약: {_review_excerpt(review_text)}",
        )
        print(f"[{_now_label()}] {candidate_id} 승인 처리 완료")

    remaining = validate_after_apply()
    print()
    if remaining:
        print(f"아직 미정 PC 후보가 {len(remaining)}개 남아 있습니다. 새 pipeline은 막지 않지만 나중에 다시 검토할 수 있습니다.")
        return 1
    print("모든 PC 후보가 승인 또는 기각되었습니다.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except base.HarnessError as exc:
        print(f"[PC review failed] {exc}", file=sys.stderr)
        raise SystemExit(1)

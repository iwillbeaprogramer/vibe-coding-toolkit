#!/usr/bin/env python
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

import harness as base


DEFAULT_AGENT = "agy"
AGENT_CHOICES = ("codex", "claude", "agy")
REVIEW_TIMEOUT_SECONDS = 3600
PROGRESS_INTERVAL_SECONDS = 15
COLOR_RESET = "\033[0m"
COLOR_DIM = "\033[2m"
COLOR_BOLD = "\033[1m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREEN = "\033[32m"
COLOR_MAGENTA = "\033[35m"
COLOR_RED = "\033[31m"
COLOR_YELLOW = "\033[33m"


def _enable_windows_ansi() -> None:
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        return


_enable_windows_ansi()


def _color_enabled() -> bool:
    return not os.environ.get("NO_COLOR") and sys.stdout.isatty()


def _style(text: str, *codes: str) -> str:
    if not _color_enabled() or not codes:
        return text
    return "".join(codes) + text + COLOR_RESET


def _print_rule(title: str, color: str = COLOR_CYAN) -> None:
    line = f"========== {title} =========="
    print(_style(line, COLOR_BOLD, color), flush=True)


def _print_kv(label: str, value: object, color: str = COLOR_CYAN) -> None:
    print(f"{_style(label + ':', COLOR_BOLD, color)} {value}", flush=True)


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


def _approved_payload(decisions: list[dict]) -> str:
    payload = [
        {
            "candidate": item["candidate"],
            "review_text": item["review_text"],
            "user_decision": item["status"],
        }
        for item in decisions
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_apply_prompt(decisions: list[dict], contract_text: str, agent: str) -> str:
    contract_path = base.project_contract_path()
    return f"""# Apply Approved Project Contract Candidates

The user approved the Project Contract candidates listed below after reading the {agent} reviews.

You must now edit `.ai/project_contract.md` directly in the repository.

Allowed files:
- {contract_path}

Forbidden:
- Do not edit any other files.
- Do not edit `.ai/history/pc_candidates.json`; the Python script will update candidate status.
- Do not run git commands.

## Apply Rules
1. Apply all approved candidates in one pass.
2. Add each approved rule to `.ai/project_contract.md` under the most appropriate section.
3. If a suitable section already exists, add a short bullet there.
4. If no suitable section exists, create a short section with a clear heading.
5. Do not duplicate existing Project Contract rules. If a rule is already covered, leave that rule unchanged and mention it in the summary.
6. Keep `.ai/project_contract.md` short and rule-focused. Do not add evidence or long rationale there.

## Current Approved Project Contract
```markdown
{contract_text}
```

## Approved Candidates And Reviews
```json
{_approved_payload(decisions)}
```

After editing, print a concise Korean summary of exactly what changed for each approved candidate. If no file change was needed because every rule was already covered, say so clearly.
"""


def _progress_until_done(stop: threading.Event, label: str) -> None:
    while not stop.wait(PROGRESS_INTERVAL_SECONDS):
        print(_style(f"[{_now_label()}] {label} 진행 중...", COLOR_DIM, COLOR_BLUE), flush=True)


def run_agent(agent: str, prompt: str, prefix: str, label: str) -> dict:
    print(_style(f"[{_now_label()}] {label} 시작 (agent={agent})", COLOR_BOLD, COLOR_BLUE), flush=True)
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
        _style(
            f"[{_now_label()}] {label} 완료 "
            f"(stdout={result.get('stdout')} stderr={result.get('stderr')})",
            COLOR_GREEN,
        ),
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
        answer = input(_style(prompt, COLOR_BOLD, COLOR_YELLOW)).strip().lower()
        if answer in {"yes", "y"}:
            return True
        if answer in {"no", "n"}:
            return False
        print(_style("Yes 또는 No로 답해주세요. 예: y / n", COLOR_RED))


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
    _print_rule(f"PC 후보 {index}/{total}", COLOR_MAGENTA)
    _print_kv("id", candidate.get("id"), COLOR_MAGENTA)
    _print_kv("category", candidate.get("category") or "-", COLOR_MAGENTA)
    _print_kv("recommended_section", candidate.get("recommended_contract_section") or "-", COLOR_MAGENTA)
    _print_kv("rule_candidate", candidate.get("rule_candidate") or "-", COLOR_MAGENTA)
    rationale = str(candidate.get("rationale") or "").strip()
    if rationale:
        _print_kv("rationale", rationale, COLOR_MAGENTA)
    print(_style("====================================", COLOR_MAGENTA))


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

    print(_style(f"미정 PC 후보 {len(pending)}개를 {agent}가 후보별로 검토합니다.", COLOR_BOLD, COLOR_CYAN))
    print(_style("각 후보마다 agent 검토 후 사용자 결정을 보관하고, 승인된 후보는 마지막에 한 번에 Project Contract에 반영합니다.", COLOR_CYAN))

    decisions: list[dict] = []

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
        _print_rule(f"{agent} PC 후보 검토", COLOR_CYAN)
        print(review_text or f"({agent}가 검토 내용을 출력하지 않았습니다.)")
        print(_style("========================================", COLOR_CYAN))
        print()

        approved = ask_yes_no("이 후보를 Project Contract에 승인할까요? (Yes=승인 / No=기각): ")
        status = base.PC_APPROVED_STATUS if approved else base.PC_REJECTED_STATUS
        decisions.append(
            {
                "candidate": candidate,
                "candidate_id": candidate_id,
                "review_text": review_text,
                "status": status,
            }
        )
        status_color = COLOR_GREEN if approved else COLOR_RED
        print(_style(f"[{_now_label()}] {candidate_id} 결정 보관: {status}", COLOR_BOLD, status_color))

    approved_decisions = [item for item in decisions if item["status"] == base.PC_APPROVED_STATUS]
    rejected_decisions = [item for item in decisions if item["status"] == base.PC_REJECTED_STATUS]

    print()
    _print_rule("PC 결정 요약", COLOR_YELLOW)
    print(_style(f"승인: {len(approved_decisions)}개 / 기각: {len(rejected_decisions)}개", COLOR_BOLD, COLOR_YELLOW))

    if approved_decisions:
        before_apply = _snapshot(protected)
        apply_result = run_agent(
            agent,
            build_apply_prompt(approved_decisions, _read_text(contract_path), agent),
            "pc_apply_batch",
            f"승인된 PC 후보 {len(approved_decisions)}개 contract 일괄 반영",
        )
        if _read_text(candidates_path) != before_apply[candidates_path]:
            candidates_path.write_text(before_apply[candidates_path], encoding="utf-8")
            print(f"[{_now_label()}] agent가 변경한 후보 JSON은 복원했고, 상태는 Python이 기록합니다.")

        apply_text = str(apply_result.get("stdout_text") or "").strip()
        if apply_text:
            print()
            _print_rule(f"{agent} 일괄 적용 결과", COLOR_GREEN)
            print(apply_text)
            print(_style("=====================================", COLOR_GREEN))
    else:
        print(_style("승인된 후보가 없어 Project Contract 파일 반영 단계는 건너뜁니다.", COLOR_YELLOW))

    for item in decisions:
        candidate_id = item["candidate_id"]
        review_text = item["review_text"]
        status = item["status"]
        if status == base.PC_APPROVED_STATUS:
            reason = (
                f"사용자가 pc_review에서 승인했고 {agent}가 Project Contract 일괄 반영을 수행함. "
                f"검토 요약: {_review_excerpt(review_text)}"
            )
        else:
            reason = (
                f"사용자가 pc_review에서 승인하지 않아 기각함. "
                f"{agent} 검토 요약: {_review_excerpt(review_text)}"
            )
        update_candidate_decision(candidate_id, status, reason)
        status_color = COLOR_GREEN if status == base.PC_APPROVED_STATUS else COLOR_RED
        print(_style(f"[{_now_label()}] {candidate_id} {status} 상태 기록 완료", status_color))

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

#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

HARNESS_DIR = Path(__file__).resolve().parent
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))

from harness_core.docx_validation import validate_docx_file as core_validate_docx_file
from harness_core.frontmatter import parse_frontmatter, parse_scalar
from harness_core.json_io import read_json_file, write_json_file
from harness_core import history as history_core
from harness_core import policy as policy_core
from harness_core import providers as provider_core
from harness_core import stage_runtime as stage_runtime_core
from harness_core import verification as verification_core
from harness_core import workflow as workflow_core
from harness_core.text import (
    boolish,
    compact_history_text,
    history_list,
    history_object_list,
    markdown_section_items,
    markdown_sections,
    norm_repo_path,
    section_matches,
    slugify,
    validate_slug,
)


ROOT = Path(__file__).resolve().parents[1]
AI_DIR = ROOT / ".ai"
RUNS_DIR = AI_DIR / "runs"
FEATURES_DIR = AI_DIR / "features"
DOCS_DIR = AI_DIR / "docs"
HISTORY_DIR = AI_DIR / "history"
PROJECT_CONTRACT_PATH = AI_DIR / "project_contract.md"
PC_CANDIDATES_PATH = HISTORY_DIR / "pc_candidates.json"
PRESETS_DIR = ROOT / "presets" / "full"
PIPELINE_MODE = "full"
HISTORY_SCHEMA_VERSION = 1
PC_CANDIDATES_SCHEMA_VERSION = 1
PC_PENDING_STATUS = "미정"
PC_APPROVED_STATUS = "승인"
PC_REJECTED_STATUS = "기각"
PC_REVIEW_STAGE = "pc_candidates"
PC_PROJECT_WIDE_SCOPE = "project_wide"

STAGES = [
    "00_specify",
    "01_plan",
    "02_develop",
    "03_review",
    "04_fix",
    "05_verify",
    "06_document",
]

STAGE_OUTPUTS = {
    "00_specify": "00_spec.md",
    "01_plan": "01_plan.md",
    "02_develop": "02_dev.md",
    "03_review": "03_review.md",
    "04_fix": "04_fix.md",
    "05_verify": "05_verify.md",
    "06_document": "06_document.md",
}

COMMIT_STAGES = {"02_develop", "04_fix", "05_verify"}
NO_COMMIT_STAGES = {"00_specify", "01_plan", "03_review", "06_document"}
DEFAULT_MAX_VERIFY_FIX_RETRIES = 3
DEFAULT_VERIFY_COMMAND_TIMEOUT_SECONDS = 600
DEFAULT_PROVIDER_HEARTBEAT_SECONDS = 30
DEFAULT_WATCH_INTERVAL_SECONDS = 5
DEFAULT_DOCTOR_DEEP_TIMEOUT_SECONDS = 60

START_STAGE = "00_specify"
DEVELOP_STAGE = "02_develop"
VERIFY_STAGE = "05_verify"
VERIFY_RETRY_TARGET_STAGE = "04_fix"
FIX_STAGE: str | None = "04_fix"
DOCUMENT_STAGE: str | None = "06_document"

PROVIDER_BY_MODEL = {
    "Codex": "codex",
    "Claude": "claude",
    "Antigravity": "agy",
}
PROVIDERS = ("codex", "claude", "agy")

DEFAULT_PROVIDER_COMMANDS = {
    "codex": [
        "codex.cmd",
        "exec",
        "--cd",
        "{cwd}",
        "--sandbox",
        "workspace-write",
        "--dangerously-bypass-approvals-and-sandbox",
        "-",
    ],
    "claude": [
        "claude",
        "-p",
        "--permission-mode",
        "bypassPermissions",
        "--output-format",
        "text",
    ],
    "agy": [
        "agy.exe",
        "--add-dir",
        "{cwd}",
        "--log-file",
        "{log_file}",
        "--print",
        "--print-timeout",
        "30m",
        "--dangerously-skip-permissions",
    ],
}

DEFAULT_PERFORMANCE = "medium"

DEFAULT_PROVIDER_CAPABILITIES = {
    "codex": ["plan", "code_write", "review", "verify", "document", "pc_extract"],
    "claude": ["plan", "code_write", "review", "verify", "document", "pc_extract"],
    "agy": ["plan", "review", "verify", "document", "pc_extract"],
}

DEFAULT_MODEL_POLICY = {
    "min_distinct_agents": 2,
    "no_adjacent_same_provider": True,
    "on_independence_violation": "block",
    "code_write_allowed": ["claude", "codex"],
    "code_write_denied": ["agy"],
    "code_write_order": ["claude", "codex"],
    "non_code_order": ["agy", "codex", "claude"],
    "role_orders": {
        "plan": ["agy", "codex", "claude"],
        "review": ["agy", "codex", "claude"],
        "verify": ["codex", "agy", "claude"],
        "document": ["agy", "codex", "claude"],
        "pc_extract": ["claude", "codex", "agy"],
    },
    "avoid_reusing_recent_code_writer_for_review": True,
    "reserve_code_writers_for_code_stages": True,
}

PERFORMANCE_PROFILES = {
    "high": {
        "codex": {
            "model": "gpt-5.5",
            "model_reasoning_effort": "xhigh",
        },
        "claude": {
            "model": "claude-opus-4-7",
            "effort": "xhigh",
        },
        "agy": {
            "model": "agy-high",
        },
    },
    "medium": {
        "codex": {
            "model": "gpt-5.5",
            "model_reasoning_effort": "high",
        },
        "claude": {
            "model": "claude-opus-4-7",
            "effort": "high",
        },
        "agy": {
            "model": "agy-medium",
        },
    },
    "lite": {
        "codex": {
            "model": "gpt-5.5",
            "model_reasoning_effort": "medium",
        },
        "claude": {
            "model": "claude-sonnet-4-6",
            "effort": "high",
        },
        "agy": {
            "model": "agy-lite",
        },
    },
}


class HarnessError(RuntimeError):
    pass


COLOR_CODES = {
    "bold": "1",
    "dim": "2",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
}


def color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return bool(getattr(sys.stdout, "isatty", lambda: False)() or getattr(sys.stderr, "isatty", lambda: False)())


def color_text(text: str, *styles: str) -> str:
    if not color_enabled() or not styles:
        return text
    codes = [COLOR_CODES[style] for style in styles if style in COLOR_CODES]
    if not codes:
        return text
    return f"\033[{';'.join(codes)}m{text}\033[0m"


def event_line_for_console(line: str, event: str) -> str:
    event = event.lower()
    if "blocked" in event or "failed" in event:
        return color_text(line, "red", "bold")
    if "complete" in event or "created" in event or "advanced" in event or "approved" in event:
        return color_text(line, "green")
    if "started" in event or event in {"auto_step", "prompt_generated"}:
        return color_text(line, "cyan")
    if "retry" in event or "skipped" in event:
        return color_text(line, "yellow")
    return line


def status_style(status: str) -> tuple[str, ...]:
    status = status.lower()
    if status in {"complete", "model_completed"}:
        return ("green", "bold")
    if status in {"blocked"}:
        return ("red", "bold")
    if status in {"model_running", "waiting_for_model"}:
        return ("cyan", "bold")
    if status in {"created"}:
        return ("yellow", "bold")
    return ("bold",)


def format_duration(seconds: float) -> str:
    seconds_i = max(0, int(seconds))
    hours, rem = divmod(seconds_i, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def ensure_dirs() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["git", "-c", f"safe.directory={ROOT.as_posix()}"] + args
    return subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def git_output(args: list[str]) -> str:
    return git(args).stdout.strip()


def git_upstream_ref() -> str | None:
    proc = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], check=False)
    if proc.returncode != 0:
        return None
    upstream = proc.stdout.strip()
    return upstream or None


def unpushed_commit_lines() -> tuple[str | None, list[str]]:
    upstream = git_upstream_ref()
    if not upstream:
        return None, []
    proc = git(["log", "--oneline", "--no-decorate", f"{upstream}..HEAD"], check=False)
    if proc.returncode != 0:
        return upstream, []
    return upstream, [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def group_harness_commit_lines(commits: list[str]) -> tuple[dict[str, list[tuple[str, str]]], list[str]]:
    grouped: dict[str, list[tuple[str, str]]] = {}
    other: list[str] = []
    pattern = re.compile(
        r"^(?P<sha>[0-9a-f]+)\s+"
        r"\[(?P<feature>[^\]]+)\]\[(?P<stamp>[^\]]+)\]\[(?P<stage>[^\]]+)\]"
    )
    for line in commits:
        match = pattern.match(line)
        if not match:
            other.append(line)
            continue
        grouped.setdefault(match.group("feature"), []).append(
            (match.group("stage"), match.group("sha"))
        )
    return grouped, other


def format_unpushed_commits_message(upstream: str, commits: list[str]) -> str:
    count = len(commits)
    grouped, other = group_harness_commit_lines(commits)
    lines = [
        color_text("새 파이프라인을 시작할 수 없습니다.", "red", "bold"),
        "",
        (
            f"현재 브랜치에 원격({upstream})에 반영되지 않은 커밋이 "
            f"{color_text(str(count), 'yellow', 'bold')}개 있습니다."
        ),
        "하네스는 한 번의 새 파이프라인을 하나의 기능 단위로 취급합니다.",
        "이전 기능의 커밋을 먼저 원격에 반영한 뒤 다시 시작하세요.",
        "",
    ]
    if grouped:
        lines.append(color_text("미반영 하네스 기능:", "yellow", "bold"))
        for feature, stage_commits in grouped.items():
            lines.append(f"  - {feature}")
            lines.extend(f"    - {stage} {sha}" for stage, sha in stage_commits)
    if other:
        if grouped:
            lines.append("")
        lines.append(color_text("미반영 기타 커밋:", "yellow", "bold"))
        lines.extend(f"  - {line}" for line in other[:20])
        if len(other) > 20:
            lines.append(f"  - ... and {len(other) - 20} more")
    lines.extend(
        [
            "",
            f"{color_text('권장 조치:', 'green', 'bold')} git push",
        ]
    )
    return "\n".join(lines)


def assert_no_unpushed_commits_for_new_run() -> None:
    upstream, commits = unpushed_commit_lines()
    if upstream and commits:
        raise HarnessError(format_unpushed_commits_message(upstream, commits))


def incomplete_run_summaries() -> list[dict[str, str]]:
    if not RUNS_DIR.exists():
        return []
    summaries: list[dict[str, str]] = []
    for path in sorted(RUNS_DIR.glob("*/run.json")):
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            summaries.append(
                {
                    "feature": path.parent.name,
                    "status": "unreadable",
                    "stage": "-",
                    "reason": str(exc),
                }
            )
            continue
        if not isinstance(parsed, dict):
            summaries.append(
                {
                    "feature": path.parent.name,
                    "status": "invalid",
                    "stage": "-",
                    "reason": "run.json is not an object",
                }
            )
            continue
        status = str(parsed.get("status") or "unknown")
        if status == "complete":
            continue
        blocked = parsed.get("blocked")
        reason = str(blocked.get("reason") or "") if isinstance(blocked, dict) else ""
        summaries.append(
            {
                "feature": str(parsed.get("feature_name") or path.parent.name),
                "status": status,
                "stage": str(parsed.get("current_stage") or "-"),
                "reason": reason,
            }
        )
    return summaries


def format_incomplete_runs_message(runs: list[dict[str, str]]) -> str:
    lines = [
        color_text("새 파이프라인을 시작할 수 없습니다.", "red", "bold"),
        "",
        f"완료되지 않은 하네스 run이 {color_text(str(len(runs)), 'yellow', 'bold')}개 있습니다.",
        "하네스는 한 번의 새 파이프라인을 하나의 기능 단위로 취급합니다.",
        "기존 run을 먼저 정리한 뒤 다시 시작하세요.",
        "",
        color_text("미완료 run:", "yellow", "bold"),
    ]
    for run in runs:
        lines.append(f"  - {run['feature']}: {run['status']} at {run['stage']}")
        reason = run.get("reason", "")
        if reason:
            lines.append(f"    reason: {reason[:200]}")
    lines.extend(
        [
            "",
            f"{color_text('권장 조치:', 'green', 'bold')} resume / retry / cleanup",
        ]
    )
    return "\n".join(lines)


def assert_no_incomplete_runs_for_new_run() -> None:
    runs = incomplete_run_summaries()
    if runs:
        raise HarnessError(format_incomplete_runs_message(runs))


def git_changed_paths() -> list[str]:
    out = git_output(["status", "--porcelain=v1"])
    paths: list[str] = []
    for line in out.splitlines():
        if not line:
            continue
        raw = line[2:].lstrip()
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.append(norm_repo_path(raw.strip('"')))
    return sorted(set(paths))


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_harness_internal_path(path: str, feature: str) -> bool:
    return policy_core.is_harness_internal_path(path, feature)


def is_snapshot_generated_path(path: str) -> bool:
    return policy_core.is_snapshot_generated_path(path)


def git_ignored_paths(paths: list[str]) -> set[str]:
    return policy_core.git_ignored_paths(globals(), paths)


def snapshot_excluded_paths(paths: list[str]) -> set[str]:
    return policy_core.snapshot_excluded_paths(globals(), paths)


def repo_child_path(parent: Path, name: str) -> str:
    return policy_core.repo_child_path(globals(), parent, name)


def file_policy_snapshot(feature: str) -> dict[str, str]:
    return policy_core.file_policy_snapshot(globals(), feature)


def changed_since_snapshot(before: dict[str, str], feature: str) -> list[str]:
    return policy_core.changed_since_snapshot(globals(), before, feature)


def git_head() -> str:
    return git_output(["rev-parse", "HEAD"])


def git_add(paths: list[str]) -> None:
    if not paths:
        return
    git(["add", "--"] + paths)


def git_commit(message: str, amend: bool = False) -> str:
    if amend:
        git(["commit", "--amend", "--no-edit"])
    else:
        git(["commit", "-m", message])
    return git_head()


def read_preset(stage: str) -> tuple[dict[str, Any], str, str]:
    path = PRESETS_DIR / f"{stage}.md"
    if not path.exists():
        raise HarnessError(f"Missing preset: {path}")
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    return meta, body, text


def load_config() -> dict[str, Any]:
    return provider_core.load_config(globals())


def raw_provider_command(provider: str) -> list[str]:
    return provider_core.raw_provider_command(globals(), provider)


def normalize_performance(value: Any | None) -> str:
    return provider_core.normalize_performance(globals(), value)


def performance_profile(value: Any | None) -> dict[str, dict[str, str]]:
    return provider_core.performance_profile(globals(), value)


def provider_performance_settings(provider: str, performance: Any | None) -> dict[str, str]:
    return provider_core.provider_performance_settings(globals(), provider, performance)


def command_has_option(command: list[str], *options: str) -> bool:
    return provider_core.command_has_option(command, *options)


def command_has_config_key(command: list[str], key: str) -> bool:
    return provider_core.command_has_config_key(command, key)


def append_before_stdin_prompt(command: list[str], extra: list[str]) -> list[str]:
    return provider_core.append_before_stdin_prompt(command, extra)


def apply_performance_to_command(
    provider: str,
    command: list[str],
    performance: Any | None,
) -> list[str]:
    return provider_core.apply_performance_to_command(globals(), provider, command, performance)


def prepare_provider_command(
    provider: str,
    prompt_text: str | None = None,
    prompt_file: Path | None = None,
    log_file: Path | None = None,
    performance: Any | None = None,
) -> tuple[list[str], bool]:
    return provider_core.prepare_provider_command(
        globals(),
        provider,
        prompt_text,
        prompt_file,
        log_file,
        performance,
    )


def provider_command(provider: str) -> list[str]:
    return provider_core.provider_command(globals(), provider)


def redact_prompt_command(command: list[str], prompt_text: str | None) -> list[str]:
    return provider_core.redact_prompt_command(command, prompt_text)


def run_text_provider_prompt(
    provider: str,
    prompt_text: str,
    *,
    logs_dir: Path,
    log_prefix: str,
    timeout_seconds: int = 3600,
    performance: Any | None = None,
) -> dict[str, Any]:
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = now_stamp()
    safe_prefix = re.sub(r"[^a-zA-Z0-9_.-]+", "-", log_prefix).strip("-") or "provider"
    stdout_path = logs_dir / f"{safe_prefix}_{provider}_{stamp}.out.txt"
    stderr_path = logs_dir / f"{safe_prefix}_{provider}_{stamp}.err.txt"
    meta_path = logs_dir / f"{safe_prefix}_{provider}_{stamp}.json"
    cli_log_path = logs_dir / f"{safe_prefix}_{provider}_{stamp}.cli.log"

    command, prompt_in_command = prepare_provider_command(
        provider,
        prompt_text,
        log_file=cli_log_path.resolve(),
        performance=performance,
    )
    executable = resolve_executable(command)
    if not executable:
        raise HarnessError(f"Provider executable not found for {provider}: {command[0]}")

    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            input=None if prompt_in_command else prompt_text,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        elapsed = round(time.time() - started, 2)
        stdout_text = proc.stdout or ""
        stderr_text = proc.stderr or ""
        timed_out = False
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.time() - started, 2)
        stdout_text = exc.stdout or ""
        stderr_text = exc.stderr or ""
        if isinstance(stdout_text, bytes):
            stdout_text = stdout_text.decode("utf-8", errors="replace")
        if isinstance(stderr_text, bytes):
            stderr_text = stderr_text.decode("utf-8", errors="replace")
        stderr_text = str(stderr_text) + f"\nTimed out after {timeout_seconds} seconds.\n"
        timed_out = True
        returncode = None

    stdout_path.write_text(str(stdout_text), encoding="utf-8")
    stderr_path.write_text(str(stderr_text), encoding="utf-8")
    result = {
        "provider": provider,
        "command": redact_prompt_command(command, prompt_text),
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_seconds": elapsed,
        "stdout": rel(stdout_path),
        "stderr": rel(stderr_path),
        "meta": rel(meta_path),
        "provider_log": rel(cli_log_path),
        "finished_at": iso_now(),
    }
    meta_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result | {"stdout_text": str(stdout_text), "stderr_text": str(stderr_text)}


def expand_runtime_placeholders(value: Any, feature: str) -> str:
    return (
        str(value)
        .replace("{root}", str(ROOT))
        .replace("{cwd}", str(ROOT))
        .replace("{feature}", feature)
    )


def configured_verification_commands(feature: str) -> tuple[list[dict[str, Any]], bool]:
    return verification_core.configured_verification_commands(globals(), feature)


def preset_provider_for_stage(stage: str) -> str | None:
    return provider_core.preset_provider_for_stage(globals(), stage)


def resolve_executable(command: list[str]) -> str | None:
    return provider_core.resolve_executable(command)


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    return provider_core.merge_dicts(base, override)


def model_policy() -> dict[str, Any]:
    return provider_core.model_policy(globals())


def ordered_unique(values: list[str] | tuple[str, ...]) -> list[str]:
    return provider_core.ordered_unique(values)


def known_provider_names() -> list[str]:
    return provider_core.known_provider_names(globals())


def provider_config(provider: str) -> dict[str, Any]:
    return provider_core.provider_config(globals(), provider)


def provider_enabled(provider: str) -> bool:
    return provider_core.provider_enabled(globals(), provider)


def provider_capabilities(provider: str) -> set[str]:
    return provider_core.provider_capabilities(globals(), provider)


def provider_available(provider: str) -> bool:
    return provider_core.provider_available(globals(), provider)


def available_providers() -> list[str]:
    return provider_core.available_providers(globals())


def pipeline_extracts_pc_candidates(pipeline_mode: Any) -> bool:
    return provider_core.pipeline_extracts_pc_candidates(globals(), pipeline_mode)


def provider_schedule_stages(state: dict[str, Any]) -> list[str]:
    return provider_core.provider_schedule_stages(globals(), state)


def stage_role(stage: str) -> str:
    return provider_core.stage_role(globals(), stage)


def provider_order_for_role(stage: str, role: str, policy: dict[str, Any]) -> list[str]:
    return provider_core.provider_order_for_role(globals(), stage, role, policy)


def candidate_providers_for_stage(
    stage: str,
    policy: dict[str, Any],
    available: list[str],
) -> list[str]:
    return provider_core.candidate_providers_for_stage(globals(), stage, policy, available)


def latest_code_writer(assignments: dict[str, str], stages: list[str]) -> str | None:
    return provider_core.latest_code_writer(globals(), assignments, stages)


def stage_provider_score(
    stage: str,
    provider: str,
    candidates: list[str],
    assignments: dict[str, str],
    ordered_stages: list[str],
    policy: dict[str, Any],
) -> int:
    return provider_core.stage_provider_score(
        globals(),
        stage,
        provider,
        candidates,
        assignments,
        ordered_stages,
        policy,
    )


def compute_provider_schedule(
    state: dict[str, Any],
    *,
    strict_independence: bool,
) -> dict[str, str] | None:
    return provider_core.compute_provider_schedule(
        globals(),
        state,
        strict_independence=strict_independence,
    )


def build_provider_schedule(state: dict[str, Any]) -> dict[str, str]:
    return provider_core.build_provider_schedule(globals(), state)


def ensure_provider_schedule(
    state: dict[str, Any],
    *,
    persist: bool = True,
    console: bool = False,
    record_event: bool = True,
) -> dict[str, str]:
    return provider_core.ensure_provider_schedule(
        globals(),
        state,
        persist=persist,
        console=console,
        record_event=record_event,
    )


def provider_for_stage(stage: str, state: dict[str, Any] | None = None) -> str:
    return provider_core.provider_for_stage(globals(), stage, state)


def feature_dir(feature: str) -> Path:
    return FEATURES_DIR / feature


def run_dir(feature: str) -> Path:
    return RUNS_DIR / feature


def state_path(feature: str) -> Path:
    return run_dir(feature) / "run.json"


def stage_output_path(feature: str, stage: str) -> Path:
    return feature_dir(feature) / STAGE_OUTPUTS[stage]


def stage_result_json_path(feature: str, stage: str) -> Path:
    output = stage_output_path(feature, stage)
    return output.with_name(f"{output.stem}.result.json")


def load_state(feature: str) -> dict[str, Any]:
    path = state_path(feature)
    if not path.exists():
        raise HarnessError(f"Run not found: {feature}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    feature = state["feature_name"]
    path = state_path(feature)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = iso_now()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_log_path(feature: str) -> Path:
    return run_dir(feature) / "harness.log"


def verification_dir(feature: str) -> Path:
    return run_dir(feature) / "verification"


def latest_verification_result_path(feature: str) -> Path:
    return verification_dir(feature) / "latest.json"


def history_summary_path() -> Path:
    return history_core.history_summary_path(globals())


def history_index_path() -> Path:
    return history_core.history_index_path(globals())


def pc_candidates_path() -> Path:
    return history_core.pc_candidates_path(globals())


def project_contract_path() -> Path:
    return history_core.project_contract_path(globals())


def empty_pc_candidates_store() -> dict[str, Any]:
    return history_core.empty_pc_candidates_store(globals())


def read_pc_candidates_store() -> dict[str, Any]:
    return history_core.read_pc_candidates_store(globals())


def write_pc_candidates_store(store: dict[str, Any]) -> None:
    return history_core.write_pc_candidates_store(globals(), store)


def pending_pc_candidates() -> list[dict[str, Any]]:
    return history_core.pending_pc_candidates(globals())


def ensure_project_contract_file() -> None:
    return history_core.ensure_project_contract_file(globals())


def project_contract_prompt_text() -> str:
    return history_core.project_contract_prompt_text(globals())


def warn_pending_pc_candidates_for_new_run() -> None:
    return history_core.warn_pending_pc_candidates_for_new_run(globals())


def ensure_history_store() -> bool:
    return history_core.ensure_history_store(globals())


def history_timestamp_id(value: Any) -> str:
    return history_core.history_timestamp_id(globals(), value)


def history_event_id(state: dict[str, Any]) -> str:
    return history_core.history_event_id(globals(), state)


def safe_stage_text(feature: str, stage: str) -> str:
    return history_core.safe_stage_text(globals(), feature, stage)


def load_history_stage_results(feature: str) -> dict[str, dict[str, Any]]:
    return history_core.load_history_stage_results(globals(), feature)


def history_source_artifacts(feature: str) -> list[str]:
    return history_core.history_source_artifacts(globals(), feature)


def split_event_paths(value: Any) -> list[str]:
    return history_core.split_event_paths(globals(), value)


def collect_history_changed_files(
    state: dict[str, Any],
    stage_results: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    return history_core.collect_history_changed_files(globals(), state, stage_results)


def load_history_verification(feature: str, stage_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return history_core.load_history_verification(globals(), feature, stage_results)


def collect_history_notes(
    feature: str,
    stage_results: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    return history_core.collect_history_notes(globals(), feature, stage_results)


def normalize_unresolved_source_item(
    item: Any,
    *,
    item_type: str,
    status: str,
    disposition: str,
    source_stage: str,
    source_artifact: str,
    default_severity: str = "info",
) -> dict[str, Any] | None:
    return history_core.normalize_unresolved_source_item(globals(), item, item_type=item_type, status=status, disposition=disposition, source_stage=source_stage, source_artifact=source_artifact, default_severity=default_severity)


def unresolved_items_from_value(
    value: Any,
    *,
    item_type: str,
    status: str,
    disposition: str,
    source_stage: str,
    source_artifact: str,
    default_severity: str = "info",
) -> list[dict[str, Any]]:
    return history_core.unresolved_items_from_value(globals(), value, item_type=item_type, status=status, disposition=disposition, source_stage=source_stage, source_artifact=source_artifact, default_severity=default_severity)


def collect_history_unresolved_items(
    feature: str,
    stage_results: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return history_core.collect_history_unresolved_items(globals(), feature, stage_results)


def stable_history_id(prefix: str, *parts: Any) -> str:
    return history_core.stable_history_id(globals(), prefix, *parts)


def normalize_history_risk(
    item: dict[str, Any],
    *,
    feature: str,
    event_id: str,
    created_at: str,
    default_severity: str,
) -> dict[str, Any]:
    return history_core.normalize_history_risk(globals(), item, feature=feature, event_id=event_id, created_at=created_at, default_severity=default_severity)


def update_history_risks(event: dict[str, Any]) -> list[dict[str, Any]]:
    return history_core.update_history_risks(globals(), event)


def normalize_history_unresolved_item(
    item: dict[str, Any],
    *,
    feature: str,
    event_id: str,
    created_at: str,
) -> dict[str, Any]:
    return history_core.normalize_history_unresolved_item(globals(), item, feature=feature, event_id=event_id, created_at=created_at)


def update_history_unresolved_items(event: dict[str, Any]) -> list[dict[str, Any]]:
    return history_core.update_history_unresolved_items(globals(), event)


def append_history_decisions(event: dict[str, Any]) -> list[dict[str, Any]]:
    return history_core.append_history_decisions(globals(), event)


def update_history_feature_summary(event: dict[str, Any]) -> dict[str, Any]:
    return history_core.update_history_feature_summary(globals(), event)


def read_history_index() -> dict[str, Any]:
    return history_core.read_history_index(globals())


def write_history_index(index: dict[str, Any]) -> None:
    return history_core.write_history_index(globals(), index)


def compact_history_titles(items: list[Any], max_items: int = 5, max_len: int = 180) -> list[str]:
    return history_core.compact_history_titles(globals(), items, max_items, max_len)


def history_document_path(feature: str) -> str:
    return history_core.history_document_path(globals(), feature)


def upsert_history_index_entry(entry: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    return history_core.upsert_history_index_entry(globals(), entry)


def render_history_summary(index: dict[str, Any]) -> None:
    return history_core.render_history_summary(globals(), index)


def record_project_history(state: dict[str, Any]) -> dict[str, Any]:
    return history_core.record_project_history(globals(), state)


def should_extract_pc_candidates(state: dict[str, Any]) -> bool:
    return history_core.should_extract_pc_candidates(globals(), state)


def pc_candidate_source_artifact_text(feature: str, max_chars_per_file: int = 8000) -> str:
    return history_core.pc_candidate_source_artifact_text(globals(), feature, max_chars_per_file)


def build_pc_candidate_extraction_prompt(state: dict[str, Any]) -> str:
    return history_core.build_pc_candidate_extraction_prompt(globals(), state)


def normalize_pc_candidate(
    raw: dict[str, Any],
    state: dict[str, Any],
    created_at: str,
    provider: str,
) -> dict[str, Any] | None:
    return history_core.normalize_pc_candidate(globals(), raw, state, created_at, provider)


def append_pc_candidates(candidates: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    return history_core.append_pc_candidates(globals(), candidates, state)


def extract_project_contract_candidates(state: dict[str, Any]) -> dict[str, Any]:
    return history_core.extract_project_contract_candidates(globals(), state)


def complete_run(state: dict[str, Any], stage: str) -> dict[str, Any]:
    return workflow_core._with_ctx(globals(), workflow_core._complete_run, state, stage)


def finish_pc_candidate_extraction(state: dict[str, Any]) -> dict[str, Any]:
    return workflow_core._with_ctx(globals(), workflow_core._finish_pc_candidate_extraction, state)


def log_event(
    state: dict[str, Any],
    event: str,
    message: str,
    *,
    stage: str | None = None,
    console: bool = True,
    **fields: Any,
) -> None:
    feature = state["feature_name"]
    timestamp = iso_now()
    stage = stage or state.get("current_stage")
    line = f"[{timestamp}] [{feature}]"
    if stage:
        line += f" [{stage}]"
    line += f" {event}: {message}"
    if fields:
        compact = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
        if compact:
            line += f" ({compact})"

    path = run_log_path(feature)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    state.setdefault("events", []).append(
        {"at": timestamp, "event": event, "stage": stage, "message": message, **fields}
    )
    if console:
        print(event_line_for_console(line, event), flush=True)


def find_stage_result(text: str) -> dict[str, Any]:
    return stage_runtime_core.find_stage_result(globals(), text)


def parse_result_json_from_text(text: str) -> dict[str, Any]:
    return stage_runtime_core.parse_result_json_from_text(globals(), text)


def read_stage_result_json(path: Path) -> dict[str, Any]:
    return stage_runtime_core.read_stage_result_json(globals(), path)


def parse_result_scalar(value: str) -> Any:
    return stage_runtime_core.parse_result_scalar(globals(), value)


def extract_feature_name(spec_text: str) -> str | None:
    match = re.search(r"^\s*-\s*feature_name:\s*([a-z0-9][a-z0-9-]*)\s*$", spec_text, re.M)
    if match:
        return match.group(1)
    return None


def maybe_rename_feature(state: dict[str, Any]) -> dict[str, Any]:
    return workflow_core._with_ctx(globals(), workflow_core._maybe_rename_feature, state)


def stage_default_next(stage: str) -> str | None:
    return stage_runtime_core.stage_default_next(globals(), stage)


def expand_policy_item(item: Any, feature: str) -> str:
    return policy_core.expand_policy_item(item, feature)


def is_test_path(path: str) -> bool:
    return policy_core.is_test_path(path)


def is_production_code_path(path: str) -> bool:
    return policy_core.is_production_code_path(path)


def direct_policy_match(path: str, policy_path: str) -> bool:
    return policy_core.direct_policy_match(path, policy_path)


def policy_item_matches(path: str, item: str, before_snapshot: dict[str, str]) -> bool:
    return policy_core.policy_item_matches(path, item, before_snapshot)


def write_policy_violations(state: dict[str, Any], stage: str) -> list[str]:
    return policy_core.write_policy_violations(globals(), state, stage)


def stage_status(result: dict[str, Any]) -> str:
    return stage_runtime_core.stage_status(globals(), result)


def run_status_line(state: dict[str, Any]) -> str:
    return (
        f"{state['feature_name']}: status={state.get('status')} "
        f"stage={state.get('current_stage')} performance={normalize_performance(state.get('performance'))} "
        f"prompt={state.get('current_prompt')}"
    )


def status_value(text: str) -> str:
    return color_text(text, *status_style(text))


def print_status_field(label: str, value: str, *styles: str) -> None:
    label_text = color_text(f"{label:<14}", "dim")
    value_text = color_text(value, *styles) if styles else value
    print(f"{label_text} {value_text}")


def last_event_summary(state: dict[str, Any]) -> str:
    events = state.get("events", [])
    if not events:
        return "없음"
    event = events[-1]
    stage = event.get("stage") or "-"
    name = event.get("event") or "-"
    message = event.get("message") or ""
    at = event.get("at") or ""
    return f"{at} [{stage}] {name}: {message}"


def next_action_hint(state: dict[str, Any], expected_output: Path | None) -> tuple[str, tuple[str, ...]]:
    status = str(state.get("status") or "")
    if status == "complete":
        return "완료되었습니다.", ("green", "bold")
    if status == "blocked":
        return "blocked 이유를 확인한 뒤 수정하거나 승인/재실행하세요.", ("red", "bold")
    if expected_output and not expected_output.exists() and status in {"model_completed", "waiting_for_model"}:
        return "필수 산출물이 없으면 로그를 확인하고 현재 stage를 다시 실행하세요.", ("yellow", "bold")
    if status == "waiting_for_model":
        return "현재 prompt를 provider가 실행해야 합니다.", ("cyan", "bold")
    if status == "model_running":
        return "provider가 실행 중입니다. heartbeat 로그를 기다리세요.", ("cyan", "bold")
    return "현재 상태를 기준으로 다음 하네스 명령을 실행하세요.", ("cyan", "bold")


def print_detailed_status(state: dict[str, Any]) -> None:
    feature = state["feature_name"]
    stage = str(state.get("current_stage") or "")
    status = str(state.get("status") or "")
    expected_output: Path | None = None
    expected_result_json: Path | None = None
    provider = "-"
    attempt = "-"
    if stage in STAGES:
        expected_output = stage_output_path(feature, stage)
        expected_result_json = stage_result_json_path(feature, stage)
        attempt = str(state.get("attempts", {}).get(stage, 0) or 0)
        try:
            provider = provider_for_stage(stage, state)
        except HarnessError:
            provider = "-"

    print(color_text(feature, "bold"))
    print_status_field("performance", normalize_performance(state.get("performance")), "cyan")
    print_status_field("모드", str(state.get("pipeline_mode") or PIPELINE_MODE))
    print_status_field("상태", status, *status_style(status))
    print_status_field("단계", stage or "-")
    print_status_field("담당", provider, "magenta", "bold" if provider != "-" else "dim")
    print_status_field("시도", attempt)
    if state.get("current_prompt"):
        print_status_field("프롬프트", str(state["current_prompt"]), "cyan")
    if expected_output:
        exists = expected_output.exists()
        print_status_field("예상 산출물", rel(expected_output), "cyan")
        print_status_field("산출물 상태", "있음" if exists else "없음", "green" if exists else "red", "bold")
    if expected_result_json:
        exists = expected_result_json.exists()
        print_status_field("result JSON", rel(expected_result_json), "cyan")
        print_status_field("JSON 상태", "있음" if exists else "없음", "green" if exists else "yellow", "bold")
    if state.get("last_harness_verification"):
        print_status_field("최근 검증", str(state["last_harness_verification"]), "cyan")
    if state.get("last_handoff"):
        print_status_field("handoff", str(state["last_handoff"]), "yellow")
    print_status_field("마지막 이벤트", last_event_summary(state))
    hint, styles = next_action_hint(state, expected_output)
    print_status_field("다음 조치", hint, *styles)

    if state.get("blocked"):
        print()
        print(color_text("blocked 상세:", "red", "bold"))
        print(json.dumps(state["blocked"], ensure_ascii=False, indent=2))
    if state.get("commits"):
        print()
        print_status_field("commits", json.dumps(state.get("commits", {}), ensure_ascii=False))


def prompt_path(state: dict[str, Any], stage: str) -> Path:
    return stage_runtime_core.prompt_path(globals(), state, stage)


def generate_prompt(state: dict[str, Any], stage: str, retry_context: str | None = None) -> Path:
    return stage_runtime_core.generate_prompt(globals(), state, stage, retry_context)


def print_provider_heartbeat(
    *,
    stage: str,
    provider: str,
    started: float,
    stdout_path: Path,
    stderr_path: Path,
    last_stdout_size: int,
    last_stderr_size: int,
) -> tuple[int, int]:
    return stage_runtime_core.print_provider_heartbeat(globals(), stage=stage, provider=provider, started=started, stdout_path=stdout_path, stderr_path=stderr_path, last_stdout_size=last_stdout_size, last_stderr_size=last_stderr_size)


def harness_script_for_pipeline_mode(pipeline_mode: Any) -> str:
    return stage_runtime_core.harness_script_for_pipeline_mode(globals(), pipeline_mode)


def suggested_retry_command(state: dict[str, Any], *, auto: bool = True) -> str:
    return stage_runtime_core.suggested_retry_command(globals(), state, auto=auto)


def provider_log_hint(stdout_path: Path, stderr_path: Path, provider_log_path: Path) -> str:
    return stage_runtime_core.provider_log_hint(globals(), stdout_path, stderr_path, provider_log_path)


def provider_failure_reason(
    state: dict[str, Any],
    *,
    stage: str,
    provider: str,
    failure: str,
    stdout_path: Path,
    stderr_path: Path,
    provider_log_path: Path,
) -> str:
    return stage_runtime_core.provider_failure_reason(globals(), state, stage=stage, provider=provider, failure=failure, stdout_path=stdout_path, stderr_path=stderr_path, provider_log_path=provider_log_path)


def execute_current_prompt(state: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    return stage_runtime_core.execute_current_prompt(globals(), state, timeout_seconds)


def display_cwd(path: Path) -> str:
    return verification_core.display_cwd(globals(), path)


def run_harness_verification(state: dict[str, Any]) -> dict[str, Any]:
    return verification_core.run_harness_verification(globals(), state)


def enforce_harness_verify_result(
    state: dict[str, Any],
    result: dict[str, Any],
    status: str,
    next_stage: str,
) -> tuple[str, str]:
    return verification_core.enforce_harness_verify_result(
        globals(),
        state,
        result,
        status,
        next_stage,
    )


def auto_drive(
    state: dict[str, Any],
    yes: bool,
    timeout_seconds: int,
    max_steps: int,
    max_verify_fix_retries: int = DEFAULT_MAX_VERIFY_FIX_RETRIES,
) -> dict[str, Any]:
    return workflow_core._with_ctx(globals(), workflow_core._auto_drive, state, yes, timeout_seconds, max_steps, max_verify_fix_retries)


def safe_git_head() -> str:
    return workflow_core._with_ctx(globals(), workflow_core._safe_git_head)


def filtered_changed_paths(state: dict[str, Any], stage: str) -> list[str]:
    return workflow_core._with_ctx(globals(), workflow_core._filtered_changed_paths, state, stage)


def commit_for_stage(state: dict[str, Any], stage: str, result: dict[str, Any]) -> None:
    return workflow_core._with_ctx(globals(), workflow_core._commit_for_stage, state, stage, result)


def create_run(
    request: str,
    feature: str | None,
    defaults_mode: bool = False,
    performance: Any | None = None,
) -> dict[str, Any]:
    return workflow_core._with_ctx(globals(), workflow_core._create_run, request, feature, defaults_mode, performance)


def apply_runtime_performance(state: dict[str, Any], performance: Any | None) -> dict[str, Any]:
    return workflow_core._with_ctx(globals(), workflow_core._apply_runtime_performance, state, performance)


def latest_provider_artifacts(
    feature: str,
    stage: str,
    state: dict[str, Any] | None = None,
) -> dict[str, str]:
    return workflow_core._with_ctx(globals(), workflow_core._latest_provider_artifacts, feature, stage, state)


def handoff_path(feature: str) -> Path:
    return workflow_core._with_ctx(globals(), workflow_core._handoff_path, feature)


def safe_read_tail(path: Path, lines: int = 40, max_chars: int = 6000) -> str:
    return workflow_core._with_ctx(globals(), workflow_core._safe_read_tail, path, lines, max_chars)


def latest_verification_summary(feature: str) -> dict[str, Any] | None:
    return workflow_core._with_ctx(globals(), workflow_core._latest_verification_summary, feature)


def recent_events(state: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    return workflow_core._with_ctx(globals(), workflow_core._recent_events, state, limit)


def write_handoff(
    state: dict[str, Any],
    reason: str,
    *,
    stage: str | None = None,
    next_action: str | None = None,
    result: dict[str, Any] | None = None,
) -> Path:
    return workflow_core._with_ctx(globals(), workflow_core._write_handoff, state, reason, stage=stage, next_action=next_action, result=result)


def missing_stage_output_message(
    feature: str,
    stage: str,
    output: Path,
    state: dict[str, Any] | None = None,
) -> str:
    return workflow_core._with_ctx(globals(), workflow_core._missing_stage_output_message, feature, stage, output, state)


def load_stage_result(
    feature: str,
    stage: str,
    state: dict[str, Any] | None = None,
) -> tuple[Path, str, dict[str, Any]]:
    return workflow_core._with_ctx(globals(), workflow_core._load_stage_result, feature, stage, state)


def expected_docx_path(feature: str) -> Path:
    return workflow_core._with_ctx(globals(), workflow_core._expected_docx_path, feature)


def validate_docx_file(path: Path) -> str | None:
    return core_validate_docx_file(path, rel(path))


def validate_document_stage_artifacts(feature: str) -> str | None:
    return workflow_core._with_ctx(globals(), workflow_core._validate_document_stage_artifacts, feature)


def block_state(state: dict[str, Any], stage: str, reason: str, next_stage: str | None = None) -> None:
    return workflow_core._with_ctx(globals(), workflow_core._block_state, state, stage, reason, next_stage)


def resume_run(feature: str, max_verify_fix_retries: int = DEFAULT_MAX_VERIFY_FIX_RETRIES) -> dict[str, Any]:
    return workflow_core._with_ctx(globals(), workflow_core._resume_run, feature, max_verify_fix_retries)


def approve_run(feature: str, max_verify_fix_retries: int = DEFAULT_MAX_VERIFY_FIX_RETRIES) -> dict[str, Any]:
    return workflow_core._with_ctx(globals(), workflow_core._approve_run, feature, max_verify_fix_retries)


def build_retry_context(state: dict[str, Any], stage: str) -> str:
    return workflow_core._with_ctx(globals(), workflow_core._build_retry_context, state, stage)


def copy_same_prompt_for_retry(state: dict[str, Any], stage: str) -> Path:
    return workflow_core._with_ctx(globals(), workflow_core._copy_same_prompt_for_retry, state, stage)


def archive_stage_outputs_for_retry(state: dict[str, Any], stage: str) -> None:
    return workflow_core._with_ctx(globals(), workflow_core._archive_stage_outputs_for_retry, state, stage)


def retry_run(
    feature: str,
    *,
    same: bool,
    prompt_only: bool,
    auto: bool,
    yes: bool,
    defaults: bool,
    timeout_seconds: int,
    max_steps: int,
    max_verify_fix_retries: int,
) -> dict[str, Any]:
    return workflow_core._with_ctx(globals(), workflow_core._retry_run, feature, same=same, prompt_only=prompt_only, auto=auto, yes=yes, defaults=defaults, timeout_seconds=timeout_seconds, max_steps=max_steps, max_verify_fix_retries=max_verify_fix_retries)


def print_status(feature: str | None) -> None:
    if feature:
        state = load_state(feature)
        print_detailed_status(state)
        log_path = run_log_path(feature)
        if log_path.exists():
            print_status_field("로그", str(log_path), "cyan")
        return
    for path in sorted(RUNS_DIR.glob("*/run.json")):
        state = json.loads(path.read_text(encoding="utf-8"))
        print(run_status_line(state))


def print_providers() -> None:
    for provider in known_provider_names():
        try:
            command = provider_command(provider)
            executable = resolve_executable(command)
        except HarnessError as exc:
            command = []
            executable = None
            print(f"{provider}: error ({exc})")
            continue
        status = "ok" if provider_enabled(provider) and executable else "missing"
        if not provider_enabled(provider):
            status = "disabled"
        print(f"{provider}: {status}")
        print(f"  capabilities: {', '.join(sorted(provider_capabilities(provider))) or '-'}")
        print(f"  command: {' '.join(command)}")
        if executable:
            print(f"  executable: {executable}")


def print_provider_schedule_preview() -> None:
    state = {
        "feature_name": "_doctor",
        "pipeline_mode": PIPELINE_MODE,
        "events": [],
    }
    try:
        schedule = build_provider_schedule(state)
    except HarnessError as exc:
        print(color_text(f"provider_schedule: ERROR {exc}", "red", "bold"))
        return
    print("provider_schedule:")
    for stage in provider_schedule_stages(state):
        print(f"  {stage}: {schedule.get(stage)}")


def print_prompt(feature: str, do_print: bool) -> None:
    state = load_state(feature)
    prompt = state.get("current_prompt")
    if not prompt:
        raise HarnessError("No current prompt recorded.")
    path = ROOT / prompt
    print(path)
    if do_print:
        print(path.read_text(encoding="utf-8"))


def print_log(feature: str, follow: bool = False, lines: int = 80) -> None:
    path = run_log_path(feature)
    if not path.exists():
        raise HarnessError(f"No log file yet: {path}")
    if not follow:
        content = path.read_text(encoding="utf-8").splitlines()
        for line in content[-lines:]:
            print(line)
        return
    with path.open("r", encoding="utf-8") as fh:
        fh.seek(0, 2)
        try:
            while True:
                line = fh.readline()
                if line:
                    print(line, end="", flush=True)
                else:
                    time.sleep(0.5)
        except KeyboardInterrupt:
            return


def harness_script_for_state(state: dict[str, Any]) -> str:
    return harness_script_for_pipeline_mode(state.get("pipeline_mode"))


def explain_lines(state: dict[str, Any]) -> list[str]:
    feature = state["feature_name"]
    stage = str(state.get("current_stage") or "")
    status = str(state.get("status") or "")
    script = harness_script_for_state(state)
    expected_md = stage_output_path(feature, stage) if stage in STAGES else None
    expected_json = stage_result_json_path(feature, stage) if stage in STAGES else None
    lines = [
        f"feature: {feature}",
        f"mode: {state.get('pipeline_mode') or PIPELINE_MODE}",
        f"status: {status}",
        f"stage: {stage or '-'}",
    ]
    if stage in STAGES:
        try:
            lines.append(f"provider: {provider_for_stage(stage, state)}")
        except HarnessError:
            lines.append("provider: -")
    if state.get("current_prompt"):
        lines.append(f"prompt: {state['current_prompt']}")
    if expected_md:
        lines.append(f"md_output: {rel(expected_md)} ({'exists' if expected_md.exists() else 'missing'})")
    if expected_json:
        lines.append(
            f"result_json: {rel(expected_json)} ({'exists' if expected_json.exists() else 'missing'})"
        )
    if state.get("last_handoff"):
        lines.append(f"handoff: {state['last_handoff']}")
    if state.get("last_harness_verification"):
        lines.append(f"latest_verification: {state['last_harness_verification']}")

    lines.append("")
    lines.append("판단:")
    if status == "complete":
        lines.append("- 이 run은 완료되었습니다.")
    elif status == "blocked":
        blocked = state.get("blocked", {})
        reason = blocked.get("reason") if isinstance(blocked, dict) else None
        retry_command = (
            blocked.get("retry_command")
            if isinstance(blocked, dict) and blocked.get("retry_command")
            else suggested_retry_command(state)
        )
        lines.append(f"- 현재 막힌 이유: {reason or 'blocked 상세 정보 없음'}")
        lines.append(f"- 실패 인수인계 파일을 확인하세요: {state.get('last_handoff') or rel(handoff_path(feature))}")
        lines.append(f"- 재시도: {retry_command}")
    elif expected_md and not expected_md.exists() and status in {"waiting_for_model", "model_completed"}:
        lines.append("- 모델이 끝났거나 대기 중이지만 필수 md 산출물이 아직 없습니다.")
        lines.append(f"- 재시도: python {script} retry {feature}")
    elif status == "waiting_for_model":
        lines.append("- 현재 프롬프트를 provider가 실행해야 하는 상태입니다.")
        lines.append(f"- 자동 실행: python {script} auto {feature} --yes --defaults")
        lines.append(f"- 프롬프트 확인: python {script} prompt {feature} --print")
    elif status == "model_running":
        lines.append("- provider 실행 중입니다. heartbeat와 provider 로그를 확인하세요.")
        lines.append(f"- 감시: python {script} watch {feature}")
    elif status == "model_completed":
        lines.append("- provider 실행은 끝났고 하네스가 단계 결과를 반영해야 합니다.")
        lines.append(f"- 재개: python {script} resume {feature}")
    else:
        lines.append("- 상태가 일반 흐름과 다릅니다. status와 log를 함께 확인하세요.")
        lines.append(f"- 상태: python {script} status {feature}")

    lines.append("")
    lines.append("최근 이벤트:")
    for event in recent_events(state, limit=5):
        lines.append(
            f"- {event.get('at', '')} [{event.get('stage') or '-'}] "
            f"{event.get('event')}: {event.get('message', '')}"
        )
    if not recent_events(state, limit=1):
        lines.append("- 없음")
    return lines


def print_explain(feature: str) -> None:
    state = load_state(feature)
    for line in explain_lines(state):
        if line.startswith("판단:"):
            print(color_text(line, "cyan", "bold"))
        elif line.startswith("feature:"):
            print(color_text(line, "bold"))
        elif "retry" in line or "auto" in line or "resume" in line:
            print(color_text(line, "green"))
        else:
            print(line)


def print_watch_snapshot(feature: str, lines: int) -> dict[str, Any]:
    state = load_state(feature)
    stage = str(state.get("current_stage") or "-")
    status = str(state.get("status") or "-")
    attempt = state.get("attempts", {}).get(stage, "-") if stage in STAGES else "-"
    print(
        " | ".join(
            [
                color_text(datetime.now().strftime("%H:%M:%S"), "dim"),
                color_text(feature, "bold"),
                f"status={status_value(status)}",
                f"stage={stage}",
                f"attempt={attempt}",
            ]
        )
    )
    log_path = run_log_path(feature)
    if log_path.exists():
        for line in safe_read_tail(log_path, lines=lines).splitlines():
            print(f"  {line}")
    if state.get("last_handoff"):
        print(color_text(f"  handoff: {state['last_handoff']}", "yellow"))
    return state


def watch_run(feature: str, interval_seconds: int, lines: int, exit_on_stop: bool = False) -> None:
    if interval_seconds <= 0:
        raise HarnessError("--interval must be greater than zero.")
    try:
        while True:
            state = print_watch_snapshot(feature, lines)
            if exit_on_stop and state.get("status") in {"complete", "blocked"}:
                return
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        return


def cleanup_run(feature: str, keep_feature: bool = False) -> None:
    targets = [run_dir(feature)]
    if not keep_feature:
        targets.append(feature_dir(feature))
    for target in targets:
        if not target.exists():
            continue
        resolved = target.resolve()
        root = ROOT.resolve()
        if root not in resolved.parents and resolved != root:
            raise HarnessError(f"Refusing to remove path outside repo: {resolved}")
        shutil.rmtree(resolved)
        print(f"removed: {resolved}")


def doctor_provider_smoke(provider: str, timeout_seconds: int) -> None:
    prompt = (
        "You are running a harness doctor smoke test. "
        "Do not edit files. Reply with exactly HARNESS_DOCTOR_OK."
    )
    ensure_dirs()
    logs_dir = RUNS_DIR / "_doctor" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = now_stamp()
    stdout_path = logs_dir / f"{provider}_{stamp}.out.txt"
    stderr_path = logs_dir / f"{provider}_{stamp}.err.txt"
    cli_log_path = logs_dir / f"{provider}_{stamp}.cli.log"
    command, prompt_in_command = prepare_provider_command(
        provider,
        prompt,
        log_file=cli_log_path.resolve(),
    )
    executable = resolve_executable(command)
    if not executable:
        print(color_text(f"{provider}: missing executable", "red", "bold"))
        return
    before_paths = set(git_changed_paths())
    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            input=None if prompt_in_command else prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        stdout_path.write_text(str(stdout), encoding="utf-8")
        stderr_path.write_text(str(stderr) + f"\nTimed out after {timeout_seconds} seconds.\n", encoding="utf-8")
        print(
            color_text(f"{provider}: timeout after {timeout_seconds}s", "red", "bold")
            + f" stdout={rel(stdout_path)} stderr={rel(stderr_path)} provider_log={rel(cli_log_path)}"
        )
        return

    elapsed = round(time.time() - started, 2)
    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")
    after_paths = set(git_changed_paths())
    new_changes = sorted(
        path for path in after_paths - before_paths if not path.startswith(".ai/runs/_doctor/")
    )
    ok = proc.returncode == 0 and "HARNESS_DOCTOR_OK" in (proc.stdout or "")
    style = ("green", "bold") if ok else ("red", "bold")
    print(
        color_text(f"{provider}: {'ok' if ok else 'failed'}", *style)
        + f" returncode={proc.returncode} elapsed={elapsed}s stdout={rel(stdout_path)} stderr={rel(stderr_path)} provider_log={rel(cli_log_path)}"
    )
    if new_changes:
        print(color_text(f"  warning: provider changed files: {', '.join(new_changes)}", "yellow", "bold"))


def doctor(deep: bool = False, deep_timeout_seconds: int = DEFAULT_DOCTOR_DEEP_TIMEOUT_SECONDS) -> None:
    print(f"root: {ROOT}")
    try:
        print(f"git_head: {git_head()}")
    except Exception as exc:
        print(f"git_head: ERROR {exc}")
    for stage in STAGES:
        path = PRESETS_DIR / f"{stage}.md"
        print(f"preset {stage}: {'ok' if path.exists() else 'missing'}")
    print("providers:")
    print_providers()
    print_provider_schedule_preview()
    ensure_dirs()
    print(f"runs_dir: {RUNS_DIR}")
    print(f"features_dir: {FEATURES_DIR}")
    print("changed_paths:")
    for path in git_changed_paths():
        print(f"  {path}")
    if deep:
        print("deep provider smoke tests:")
        for provider in known_provider_names():
            if not provider_enabled(provider):
                continue
            doctor_provider_smoke(provider, deep_timeout_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local orchestrator for staged AI development presets.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_retry_arg(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--max-verify-fix-retries",
            type=int,
            default=DEFAULT_MAX_VERIFY_FIX_RETRIES,
            help=(
                f"Maximum number of failed {VERIFY_STAGE} -> {VERIFY_RETRY_TARGET_STAGE} retry cycles "
                f"(default: {DEFAULT_MAX_VERIFY_FIX_RETRIES})."
            ),
        )

    def add_performance_arg(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--performance",
            choices=list(PERFORMANCE_PROFILES),
            default=None,
            help=(
                "Performance profile for provider model settings. "
                f"Defaults to {DEFAULT_PERFORMANCE}. "
                "Applied to codex/claude only; agy is recorded but not passed to the CLI yet."
            ),
        )

    start = sub.add_parser("start", help="Start a new feature run and generate the 00 prompt.")
    start.add_argument("request", help="User request for the feature.")
    start.add_argument("--feature", help="Optional feature slug.")
    start.add_argument("--auto", action="store_true", help="Immediately execute stages with local providers.")
    start.add_argument("--yes", action="store_true", help="Auto-approve human gates while running with --auto.")
    start.add_argument(
        "--defaults",
        action="store_true",
        help="Use model-recommended defaults for ambiguous decisions instead of stopping for user input.",
    )
    start.add_argument("--timeout", type=int, default=3600, help="Provider timeout in seconds.")
    start.add_argument("--max-steps", type=int, default=30, help="Maximum automatic stage transitions.")
    add_performance_arg(start)
    add_retry_arg(start)

    run = sub.add_parser("run", help="Start a new feature run and execute it automatically.")
    run.add_argument("request", help="User request for the feature.")
    run.add_argument("--feature", help="Optional feature slug.")
    run.add_argument("--yes", action="store_true", help="Auto-approve human gates.")
    run.add_argument(
        "--defaults",
        action="store_true",
        help="Use model-recommended defaults for ambiguous decisions instead of stopping for user input.",
    )
    run.add_argument("--timeout", type=int, default=3600, help="Provider timeout in seconds.")
    run.add_argument("--max-steps", type=int, default=30, help="Maximum automatic stage transitions.")
    add_performance_arg(run)
    add_retry_arg(run)

    resume = sub.add_parser("resume", help="Resume the current stage after the model wrote its output.")
    resume.add_argument("feature", help="Feature slug.")
    resume.add_argument("--auto", action="store_true", help="Continue executing stages with local providers.")
    resume.add_argument("--yes", action="store_true", help="Auto-approve human gates while running with --auto.")
    resume.add_argument("--timeout", type=int, default=3600, help="Provider timeout in seconds.")
    resume.add_argument("--max-steps", type=int, default=30, help="Maximum automatic stage transitions.")
    add_performance_arg(resume)
    add_retry_arg(resume)

    auto = sub.add_parser("auto", help="Execute the current and following stages with local providers.")
    auto.add_argument("feature", help="Feature slug.")
    auto.add_argument("--yes", action="store_true", help="Auto-approve human gates.")
    auto.add_argument(
        "--defaults",
        action="store_true",
        help="Switch this run to defaults mode before continuing.",
    )
    auto.add_argument("--timeout", type=int, default=3600, help="Provider timeout in seconds.")
    auto.add_argument("--max-steps", type=int, default=30, help="Maximum automatic stage transitions.")
    add_performance_arg(auto)
    add_retry_arg(auto)

    approve = sub.add_parser("approve", help="Approve a blocked human gate and continue.")
    approve.add_argument("feature", help="Feature slug.")
    approve.add_argument("--auto", action="store_true", help="Continue executing stages with local providers after approval.")
    approve.add_argument("--yes", action="store_true", help="Auto-approve later human gates while running with --auto.")
    approve.add_argument(
        "--defaults",
        action="store_true",
        help="Switch this run to defaults mode before continuing.",
    )
    approve.add_argument("--timeout", type=int, default=3600, help="Provider timeout in seconds.")
    approve.add_argument("--max-steps", type=int, default=30, help="Maximum automatic stage transitions.")
    add_performance_arg(approve)
    add_retry_arg(approve)

    status = sub.add_parser("status", help="Show run status.")
    status.add_argument("feature", nargs="?", help="Feature slug. Omit to list all runs.")

    sub.add_parser("list", help="List all runs.")

    prompt = sub.add_parser("prompt", help="Show current prompt path or content.")
    prompt.add_argument("feature", help="Feature slug.")
    prompt.add_argument("--print", action="store_true", help="Print prompt content.")

    log = sub.add_parser("log", help="Show the harness log for a run.")
    log.add_argument("feature", help="Feature slug.")
    log.add_argument("--follow", "-f", action="store_true", help="Follow the log.")
    log.add_argument("--lines", type=int, default=80, help="Number of trailing lines to print.")

    watch = sub.add_parser("watch", help="Watch run status and recent log lines.")
    watch.add_argument("feature", help="Feature slug.")
    watch.add_argument("--interval", type=int, default=DEFAULT_WATCH_INTERVAL_SECONDS, help="Refresh interval in seconds.")
    watch.add_argument("--lines", type=int, default=8, help="Number of recent log lines to print.")
    watch.add_argument("--exit-on-stop", action="store_true", help="Exit when the run becomes complete or blocked.")

    explain = sub.add_parser("explain", help="Explain why a run is stopped and what to do next.")
    explain.add_argument("feature", help="Feature slug.")

    retry = sub.add_parser("retry", help="Retry the current stage.")
    retry.add_argument("feature", help="Feature slug.")
    retry.add_argument("--same", action="store_true", help="Retry with the same prompt content instead of adding failure context.")
    retry.add_argument("--prompt-only", action="store_true", help="Only generate the retry prompt; do not execute the provider.")
    retry.add_argument("--auto", action="store_true", help="Continue executing following stages after this retry succeeds.")
    retry.add_argument("--yes", action="store_true", help="Auto-approve human gates while continuing with --auto.")
    retry.add_argument(
        "--defaults",
        action="store_true",
        help="Switch this run to defaults mode before retrying.",
    )
    retry.add_argument("--timeout", type=int, default=3600, help="Provider timeout in seconds.")
    retry.add_argument("--max-steps", type=int, default=30, help="Maximum automatic stage transitions after retry.")
    add_performance_arg(retry)
    add_retry_arg(retry)

    cleanup = sub.add_parser("cleanup", help="Remove a local run directory and optionally its feature dir.")
    cleanup.add_argument("feature", help="Feature slug.")
    cleanup.add_argument(
        "--keep-feature",
        action="store_true",
        help="Only remove .ai/runs/<feature>, preserving .ai/features/<feature>.",
    )

    doctor_parser = sub.add_parser("doctor", help="Check local harness prerequisites.")
    doctor_parser.add_argument("--deep", action="store_true", help="Run provider smoke tests, not just path checks.")
    doctor_parser.add_argument(
        "--deep-timeout",
        type=int,
        default=DEFAULT_DOCTOR_DEEP_TIMEOUT_SECONDS,
        help="Timeout in seconds for each --deep provider smoke test.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            state = create_run(
                args.request,
                args.feature,
                defaults_mode=args.defaults,
                performance=args.performance,
            )
            if args.auto:
                state = auto_drive(
                    state,
                    yes=args.yes,
                    timeout_seconds=args.timeout,
                    max_steps=args.max_steps,
                    max_verify_fix_retries=args.max_verify_fix_retries,
                )
            print(run_status_line(state))
            if state.get("current_prompt"):
                print(f"prompt: {ROOT / state['current_prompt']}")
            return 0
        if args.command == "run":
            state = create_run(
                args.request,
                args.feature,
                defaults_mode=args.defaults,
                performance=args.performance,
            )
            state = auto_drive(
                state,
                yes=args.yes,
                timeout_seconds=args.timeout,
                max_steps=args.max_steps,
                max_verify_fix_retries=args.max_verify_fix_retries,
            )
            print(run_status_line(state))
            if state.get("current_prompt"):
                print(f"prompt: {ROOT / state['current_prompt']}")
            return 0
        if args.command == "resume":
            state = apply_runtime_performance(load_state(args.feature), args.performance)
            if args.auto:
                state = auto_drive(
                    state,
                    yes=args.yes,
                    timeout_seconds=args.timeout,
                    max_steps=args.max_steps,
                    max_verify_fix_retries=args.max_verify_fix_retries,
                )
            else:
                state = resume_run(args.feature, max_verify_fix_retries=args.max_verify_fix_retries)
            print(run_status_line(state))
            if state.get("current_prompt"):
                print(f"prompt: {ROOT / state['current_prompt']}")
            return 0
        if args.command == "auto":
            state = apply_runtime_performance(load_state(args.feature), args.performance)
            if args.defaults:
                state["defaults_mode"] = True
                log_event(state, "defaults_mode_enabled", "defaults mode enabled for existing run")
                save_state(state)
            state = auto_drive(
                state,
                yes=args.yes,
                timeout_seconds=args.timeout,
                max_steps=args.max_steps,
                max_verify_fix_retries=args.max_verify_fix_retries,
            )
            print(run_status_line(state))
            if state.get("current_prompt"):
                print(f"prompt: {ROOT / state['current_prompt']}")
            return 0
        if args.command == "approve":
            apply_runtime_performance(load_state(args.feature), args.performance)
            state = approve_run(args.feature, max_verify_fix_retries=args.max_verify_fix_retries)
            if args.defaults:
                state["defaults_mode"] = True
                log_event(state, "defaults_mode_enabled", "defaults mode enabled after approval")
                save_state(state)
            if args.auto:
                state = auto_drive(
                    state,
                    yes=args.yes,
                    timeout_seconds=args.timeout,
                    max_steps=args.max_steps,
                    max_verify_fix_retries=args.max_verify_fix_retries,
                )
            print(run_status_line(state))
            if state.get("current_prompt"):
                print(f"prompt: {ROOT / state['current_prompt']}")
            return 0
        if args.command == "status":
            print_status(args.feature)
            return 0
        if args.command == "list":
            print_status(None)
            return 0
        if args.command == "prompt":
            print_prompt(args.feature, args.print)
            return 0
        if args.command == "log":
            print_log(args.feature, follow=args.follow, lines=args.lines)
            return 0
        if args.command == "watch":
            watch_run(
                args.feature,
                interval_seconds=args.interval,
                lines=args.lines,
                exit_on_stop=args.exit_on_stop,
            )
            return 0
        if args.command == "explain":
            print_explain(args.feature)
            return 0
        if args.command == "retry":
            apply_runtime_performance(load_state(args.feature), args.performance)
            state = retry_run(
                args.feature,
                same=args.same,
                prompt_only=args.prompt_only,
                auto=args.auto,
                yes=args.yes,
                defaults=args.defaults,
                timeout_seconds=args.timeout,
                max_steps=args.max_steps,
                max_verify_fix_retries=args.max_verify_fix_retries,
            )
            print(run_status_line(state))
            if state.get("current_prompt"):
                print(f"prompt: {ROOT / state['current_prompt']}")
            return 0
        if args.command == "cleanup":
            cleanup_run(args.feature, keep_feature=args.keep_feature)
            return 0
        if args.command == "doctor":
            doctor(deep=args.deep, deep_timeout_seconds=args.deep_timeout)
            return 0
        parser.error("Unknown command")
        return 2
    except HarnessError as exc:
        print(f"{color_text('ERROR:', 'red', 'bold')} {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print("ERROR: command failed", file=sys.stderr)
        print(" ".join(exc.cmd), file=sys.stderr)
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())

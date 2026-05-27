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
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any


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
            "model": "Gemini 3.5 Flash (High)",
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
            "model": "Gemini 3.5 Flash (High)",
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
            "model": "Gemini 3.5 Flash (Medium)",
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


def norm_repo_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if not text:
        text = "feature-" + datetime.now().strftime("%Y%m%d%H%M%S")
    return text[:60].strip("-") or "feature-" + datetime.now().strftime("%Y%m%d%H%M%S")


def validate_slug(slug: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", slug))


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
    path = norm_repo_path(path)
    if not path.startswith(".ai/runs/"):
        return False
    return path != f".ai/runs/{feature}/document_build.py"


SNAPSHOT_GENERATED_DIR_NAMES = {
    ".antigravitycli",
    ".cache",
    ".claude",
    ".codex",
    ".gradle",
    ".git",
    ".idea",
    ".mypy_cache",
    ".next",
    ".nox",
    ".nuxt",
    ".parcel-cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svelte-kit",
    ".tox",
    ".turbo",
    ".venv",
    ".vite",
    ".vs",
    ".vscode",
    ".vstest",
    "__pycache__",
    "artifacts",
    "bin",
    "build",
    "coverage",
    "dist",
    "env",
    "htmlcov",
    "log",
    "logs",
    "node_modules",
    "obj",
    "out",
    "packages",
    "target",
    "temp",
    "TestResults",
    "tmp",
    "vendor",
    "venv",
}

SNAPSHOT_GENERATED_DIR_SUFFIXES = {
    ".egg-info",
}

SNAPSHOT_GENERATED_FILE_NAMES = {
    ".coverage",
    ".DS_Store",
    "desktop.ini",
    "Thumbs.db",
}

SNAPSHOT_GENERATED_FILE_SUFFIXES = {
    ".AssemblyAttributes.cs",
    ".AssemblyInfoInputs.cache",
    ".assets.cache",
    ".cache",
    ".coverage",
    ".coveragexml",
    ".designer.deps.json",
    ".designer.runtimeconfig.json",
    ".dtbcache.v2",
    ".GeneratedMSBuildEditorConfig.editorconfig",
    ".g.cs",
    ".g.i.cs",
    ".log",
    ".map",
    ".pyd",
    ".pyc",
    ".pyo",
    ".suo",
    ".tmp",
    ".trx",
    ".user",
    ".vsidx",
    "_MarkupCompile.i.cache",
}


def is_snapshot_generated_path(path: str) -> bool:
    path = norm_repo_path(path)
    parts = [part for part in path.split("/") if part]
    if any(part in SNAPSHOT_GENERATED_DIR_NAMES for part in parts):
        return True
    if any(any(part.endswith(suffix) for suffix in SNAPSHOT_GENERATED_DIR_SUFFIXES) for part in parts):
        return True
    if parts and parts[-1] in SNAPSHOT_GENERATED_FILE_NAMES:
        return True
    return any(path.endswith(suffix) for suffix in SNAPSHOT_GENERATED_FILE_SUFFIXES)


def git_ignored_paths(paths: list[str]) -> set[str]:
    if not paths:
        return set()
    try:
        proc = subprocess.run(
            ["git", "-c", f"safe.directory={ROOT.as_posix()}", "check-ignore", "--stdin"],
            cwd=ROOT,
            input="\n".join(paths) + "\n",
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        return set()
    if proc.returncode not in {0, 1}:
        return set()
    return {norm_repo_path(line.strip()) for line in proc.stdout.splitlines() if line.strip()}


def snapshot_excluded_paths(paths: list[str]) -> set[str]:
    generated = {path for path in paths if is_snapshot_generated_path(path)}
    remaining = [path for path in paths if path not in generated]
    return generated | git_ignored_paths(remaining)


def repo_child_path(parent: Path, name: str) -> str:
    if parent.resolve() == ROOT.resolve():
        return name
    return f"{rel(parent)}/{name}"


def file_policy_snapshot(feature: str) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    candidates: list[tuple[Path, str]] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        parent = Path(dirpath)
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not is_snapshot_generated_path(repo_child_path(parent, dirname))
        ]
        for filename in filenames:
            rel_path = repo_child_path(parent, filename)
            if is_snapshot_generated_path(rel_path):
                continue
            if is_harness_internal_path(rel_path, feature):
                continue
            candidates.append((parent / filename, rel_path))

    excluded = snapshot_excluded_paths([rel_path for _, rel_path in candidates])
    for path, rel_path in candidates:
        if rel_path in excluded:
            continue
        try:
            snapshot[rel_path] = file_hash(path)
        except OSError:
            continue
    return snapshot


def changed_since_snapshot(before: dict[str, str], feature: str) -> list[str]:
    after = file_policy_snapshot(feature)
    paths = set(before) | set(after)
    excluded = snapshot_excluded_paths(list(paths))
    return sorted(path for path in paths if path not in excluded and before.get(path) != after.get(path))


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


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, text

    meta_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1 :]) + "\n"
    meta: dict[str, Any] = {}
    current_key: str | None = None
    for line in meta_lines:
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            meta.setdefault(current_key, []).append(parse_scalar(line[4:].strip()))
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "":
                meta[key] = []
                current_key = key
            else:
                meta[key] = parse_scalar(value)
                current_key = key
    return meta, body


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value


def read_preset(stage: str) -> tuple[dict[str, Any], str, str]:
    path = PRESETS_DIR / f"{stage}.md"
    if not path.exists():
        raise HarnessError(f"Missing preset: {path}")
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    return meta, body, text


def load_config() -> dict[str, Any]:
    path = AI_DIR / "harness.config.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def raw_provider_command(provider: str) -> list[str]:
    config = load_config()
    configured = config.get("providers", {}).get(provider, {}).get("command")
    command = configured or DEFAULT_PROVIDER_COMMANDS.get(provider)
    if not command:
        raise HarnessError(f"No provider command configured for {provider}")
    return [str(part) for part in command]


def normalize_performance(value: Any | None) -> str:
    if value is None or str(value).strip() == "":
        return DEFAULT_PERFORMANCE
    performance = str(value).strip().lower()
    if performance not in PERFORMANCE_PROFILES:
        allowed = ", ".join(PERFORMANCE_PROFILES)
        raise HarnessError(f"Unknown performance profile {value!r}. Expected one of: {allowed}.")
    return performance


def performance_profile(value: Any | None) -> dict[str, dict[str, str]]:
    return PERFORMANCE_PROFILES[normalize_performance(value)]


def provider_performance_settings(provider: str, performance: Any | None) -> dict[str, str]:
    return dict(performance_profile(performance).get(provider, {}))


def command_has_option(command: list[str], *options: str) -> bool:
    for part in command:
        if part in options:
            return True
        for option in options:
            if option.startswith("--") and part.startswith(f"{option}="):
                return True
    return False


def command_has_config_key(command: list[str], key: str) -> bool:
    return any(key in part for part in command)


def append_before_stdin_prompt(command: list[str], extra: list[str]) -> list[str]:
    if command and command[-1] == "-":
        return command[:-1] + extra + ["-"]
    return command + extra


def apply_performance_to_command(
    provider: str,
    command: list[str],
    performance: Any | None,
) -> list[str]:
    settings = provider_performance_settings(provider, performance)
    if provider == "codex":
        extra: list[str] = []
        model = settings.get("model")
        effort = settings.get("model_reasoning_effort")
        if model and not command_has_option(command, "--model", "-m"):
            extra.extend(["--model", model])
        if effort and not command_has_config_key(command, "model_reasoning_effort"):
            extra.extend(["-c", f'model_reasoning_effort="{effort}"'])
        return append_before_stdin_prompt(command, extra) if extra else command
    if provider == "claude":
        extra = []
        model = settings.get("model")
        effort = settings.get("effort")
        if model and not command_has_option(command, "--model"):
            extra.extend(["--model", model])
        if effort and not command_has_option(command, "--effort"):
            extra.extend(["--effort", effort])
        return append_before_stdin_prompt(command, extra) if extra else command
    return command


def prepare_provider_command(
    provider: str,
    prompt_text: str | None = None,
    prompt_file: Path | None = None,
    log_file: Path | None = None,
    performance: Any | None = None,
) -> tuple[list[str], bool]:
    uses_prompt_placeholder = False
    command: list[str] = []
    for part in raw_provider_command(provider):
        rendered = part.replace("{cwd}", str(ROOT))
        if "{log_file}" in rendered:
            rendered = rendered.replace("{log_file}", str(log_file) if log_file is not None else "<log_file>")
        if "{prompt_file}" in rendered and prompt_file is not None:
            rendered = rendered.replace("{prompt_file}", str(prompt_file))
        if "{prompt_file_instruction}" in rendered:
            uses_prompt_placeholder = True
            if prompt_file is None:
                instruction = "<prompt>"
            else:
                instruction = (
                    "Read the harness prompt file at "
                    f"{prompt_file} and execute every instruction in it. "
                    "Write the required repository files exactly as specified. "
                    "Do not summarize only; perform the task."
                )
            rendered = rendered.replace("{prompt_file_instruction}", instruction)
        if "{prompt}" in rendered:
            uses_prompt_placeholder = True
            rendered = rendered.replace("{prompt}", prompt_text if prompt_text is not None else "<prompt>")
        command.append(rendered)
    command = apply_performance_to_command(provider, command, performance)
    return command, uses_prompt_placeholder


def provider_command(provider: str) -> list[str]:
    command, _ = prepare_provider_command(provider)
    return command


def redact_prompt_command(command: list[str], prompt_text: str | None) -> list[str]:
    if not prompt_text:
        return command
    return ["<prompt>" if part == prompt_text else part.replace(prompt_text, "<prompt>") for part in command]


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
    config = load_config()
    verification = config.get("verification")
    if verification is None:
        return [], False
    if verification is False:
        return [], False
    if not isinstance(verification, dict):
        raise HarnessError("verification config must be an object.")
    if verification.get("enabled", True) is False:
        return [], False

    required = boolish(verification.get("required", True))
    timeout_default = int(
        verification.get("timeout_seconds", DEFAULT_VERIFY_COMMAND_TIMEOUT_SECONDS)
    )
    raw_commands = verification.get("commands", [])
    if not isinstance(raw_commands, list):
        raise HarnessError("verification.commands must be a list.")

    commands: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_commands, start=1):
        if isinstance(item, list):
            name = f"command_{idx}"
            command = item
            cwd = ROOT
            timeout_seconds = timeout_default
        elif isinstance(item, dict):
            name = str(item.get("name") or f"command_{idx}")
            command = item.get("command")
            if not isinstance(command, list):
                raise HarnessError(f"verification command {name!r} must have a list command.")
            raw_cwd = item.get("cwd")
            cwd = Path(expand_runtime_placeholders(raw_cwd, feature)) if raw_cwd else ROOT
            if not cwd.is_absolute():
                cwd = ROOT / cwd
            timeout_seconds = int(item.get("timeout_seconds", timeout_default))
        else:
            raise HarnessError("verification.commands entries must be objects or lists.")

        command_parts = [expand_runtime_placeholders(part, feature) for part in command]
        if not command_parts or not command_parts[0]:
            raise HarnessError(f"verification command {name!r} is empty.")
        if timeout_seconds <= 0:
            raise HarnessError(f"verification command {name!r} has invalid timeout.")

        commands.append(
            {
                "name": slugify(name),
                "command": command_parts,
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
            }
        )
    return commands, required


def provider_for_stage(stage: str) -> str:
    meta, _, _ = read_preset(stage)
    preferred = str(meta.get("preferred_model", ""))
    provider = PROVIDER_BY_MODEL.get(preferred)
    if not provider:
        raise HarnessError(f"No provider mapped for preferred_model={preferred!r} stage={stage}")
    return provider


def resolve_executable(command: list[str]) -> str | None:
    if not command:
        return None
    return shutil.which(command[0])


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


def history_events_path() -> Path:
    return HISTORY_DIR / "events.json"


def history_legacy_events_path() -> Path:
    return HISTORY_DIR / "events.jsonl"


def history_decisions_path() -> Path:
    return HISTORY_DIR / "decisions.json"


def history_legacy_decisions_path() -> Path:
    return HISTORY_DIR / "decisions.jsonl"


def history_risks_path() -> Path:
    return HISTORY_DIR / "risks.json"


def history_unresolved_items_path() -> Path:
    return HISTORY_DIR / "unresolved_items.json"


def history_features_dir() -> Path:
    return HISTORY_DIR / "features"


def history_summary_path() -> Path:
    return HISTORY_DIR / "summary.md"


def pc_candidates_path() -> Path:
    return PC_CANDIDATES_PATH


def project_contract_path() -> Path:
    return PROJECT_CONTRACT_PATH


def write_json_file(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=4) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def empty_pc_candidates_store() -> dict[str, Any]:
    return {"version": PC_CANDIDATES_SCHEMA_VERSION, "candidates": []}


def read_pc_candidates_store() -> dict[str, Any]:
    path = pc_candidates_path()
    if not path.exists():
        return empty_pc_candidates_store()
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessError(f"Invalid PC candidates JSON: {rel(path)}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HarnessError(f"PC candidates file must be a JSON object: {rel(path)}")
    candidates = parsed.get("candidates", [])
    if not isinstance(candidates, list):
        raise HarnessError(f"PC candidates file must contain a candidates list: {rel(path)}")
    parsed["version"] = parsed.get("version") or PC_CANDIDATES_SCHEMA_VERSION
    parsed["candidates"] = [item for item in candidates if isinstance(item, dict)]
    return parsed


def write_pc_candidates_store(store: dict[str, Any]) -> None:
    candidates = store.get("candidates", [])
    if not isinstance(candidates, list):
        candidates = []
    write_json_file(
        pc_candidates_path(),
        {
            "version": store.get("version") or PC_CANDIDATES_SCHEMA_VERSION,
            "candidates": candidates,
        },
    )


def pending_pc_candidates() -> list[dict[str, Any]]:
    store = read_pc_candidates_store()
    return [
        item
        for item in store.get("candidates", [])
        if str(item.get("status") or "").strip() == PC_PENDING_STATUS
    ]


def ensure_project_contract_file() -> None:
    path = project_contract_path()
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Project Contract\n\n"
        "## Hard Rules\n"
        "- 모델은 Git commit, amend, reset, checkout, rebase, push를 직접 실행하지 않는다.\n"
        "- 기존 테스트를 삭제하거나 비활성화하지 않는다.\n"
        "- 요청 범위를 벗어난 리팩터링, 의존성 추가, 파일 이동은 하지 않는다.\n"
        "\n"
        "## Project Layout\n"
        "- 프로덕션 코드는 루트 `src/` 하위에 둔다.\n"
        "- 테스트 코드는 루트 `tests/` 하위에 둔다.\n"
        "- 새 테스트 파일을 `src/` 하위에 만들지 않는다.\n"
        "\n"
        "## Code Style\n"
        "- 새 코드는 같은 디렉터리의 기존 패턴, 네이밍, 파일 구조를 우선 따른다.\n"
        "- 프로젝트에 이미 명확한 네이밍 관례가 없으면 변수와 함수는 camelCase를 기본으로 한다.\n"
        "- 함수 이름은 가능하면 동사 또는 동사구로 시작한다. 예: `loadConfig`, `validateInput`, `renderItem`.\n"
        "- Boolean 값과 Boolean 반환 함수는 `is`, `has`, `can`, `should` 같은 의미 있는 접두사를 사용한다.\n"
        "- 이벤트 핸들러는 `handle` 또는 기존 프로젝트의 이벤트 네이밍 패턴을 따른다.\n"
        "- 값을 변환하는 함수는 `to`, `from`, `parse`, `format`, `normalize`처럼 변환 의도가 드러나는 이름을 사용한다.\n"
        "- 데이터를 가져오는 함수는 `get`, `load`, `fetch`, `read` 중 실제 동작에 맞는 동사를 사용한다.\n"
        "- 부수효과가 있는 함수는 `save`, `write`, `update`, `delete`, `send`, `create`처럼 변경 의도가 드러나는 동사를 사용한다.\n"
        "- 구현이 30줄을 넘어가면 함수나 작은 단위로 분리한다.\n"
        "\n"
        "## Reliability\n"
        "- 외부 입력, 파일, 네트워크, 프로세스 실행 결과는 실패 가능성을 명시적으로 처리한다.\n",
        encoding="utf-8",
    )


def project_contract_prompt_text() -> str:
    ensure_project_contract_file()
    path = project_contract_path()
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return (
            "## Project Contract\n"
            "No approved project contract exists yet. Follow the existing codebase conventions.\n"
        )
    return f"## Project Contract\nSource: {rel(path)}\n\n{text}\n"


def warn_pending_pc_candidates_for_new_run() -> None:
    pending = pending_pc_candidates()
    if not pending:
        return
    lines = [
        color_text("Project Contract 후보 경고", "yellow", "bold"),
        "",
        (
            "미정 상태의 Project Contract 후보가 "
            f"{color_text(str(len(pending)), 'yellow', 'bold')}개 있습니다."
        ),
        "새 파이프라인은 계속 시작하지만, 시간이 날 때 후보를 검토해 프로젝트 규약을 정리하세요.",
        "",
        color_text("선택 검토 명령:", "green", "bold"),
        "  python .ai\\pc_review.py",
        "  python .ai\\pc_review.py --agent claude  # optional: codex/claude/agy",
        "",
        color_text("미정 후보:", "yellow", "bold"),
    ]
    for item in pending[:20]:
        lines.append(
            "  - "
            f"{item.get('id', '-')}: "
            f"{compact_history_text(item.get('rule_candidate') or item.get('summary'), max_len=160)}"
        )
    if len(pending) > 20:
        lines.append(f"  - ... and {len(pending) - 20} more")
    print("\n".join(lines), file=sys.stderr)


def history_collection_key(path: Path) -> str:
    name = path.name.lower()
    if name.startswith("event"):
        return "events"
    if name.startswith("decision"):
        return "decisions"
    return "items"


def read_history_collection(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".json":
        parsed = read_json_file(path, {})
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            collection = parsed.get(history_collection_key(path), [])
            if isinstance(collection, list):
                return [item for item in collection if isinstance(item, dict)]
        return []

    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            items.append(parsed)
    return items


def write_history_collection(path: Path, items: list[dict[str, Any]]) -> None:
    key = history_collection_key(path)
    write_json_file(path, {"schema_version": HISTORY_SCHEMA_VERSION, key: items})


def ensure_history_store() -> bool:
    initialized = not HISTORY_DIR.exists()
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    history_features_dir().mkdir(parents=True, exist_ok=True)
    if not history_events_path().exists():
        write_history_collection(history_events_path(), read_history_collection(history_legacy_events_path()))
        initialized = True
    if not history_decisions_path().exists():
        write_history_collection(history_decisions_path(), read_history_collection(history_legacy_decisions_path()))
        initialized = True
    if not history_risks_path().exists():
        write_json_file(history_risks_path(), {"schema_version": HISTORY_SCHEMA_VERSION, "risks": []})
        initialized = True
    if not history_unresolved_items_path().exists():
        write_json_file(
            history_unresolved_items_path(),
            {"schema_version": HISTORY_SCHEMA_VERSION, "items": []},
        )
        initialized = True
    if not pc_candidates_path().exists():
        write_pc_candidates_store(empty_pc_candidates_store())
        initialized = True
    if not history_summary_path().exists():
        history_summary_path().write_text(
            "# 프로젝트 히스토리\n\n"
            "로컬 하네스가 자동 생성한 장기 기록 요약입니다.\n",
            encoding="utf-8",
        )
        initialized = True
    return initialized


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_history_collection(path)


def append_jsonl_if_missing(path: Path, item: dict[str, Any], id_key: str) -> bool:
    item_id = str(item.get(id_key) or "")
    if item_id:
        for existing in iter_jsonl(path):
            if str(existing.get(id_key) or "") == item_id:
                return False
    if path.suffix.lower() == ".json":
        items = iter_jsonl(path)
        items.append(item)
        write_history_collection(path, items)
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    return True


def history_timestamp_id(value: Any) -> str:
    stamp = re.sub(r"\D+", "", str(value or ""))[:14]
    return stamp or now_stamp().replace("-", "")


def history_event_id(state: dict[str, Any]) -> str:
    feature = slugify(str(state.get("feature_name") or "feature"))
    pipeline = slugify(str(state.get("pipeline_mode") or PIPELINE_MODE))
    return f"{history_timestamp_id(state.get('created_at'))}-{feature}-{pipeline}"


def compact_history_text(value: Any, max_len: int = 240) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower() in {"", "none", "n/a", "na", "null", "[]", "{}"}:
        return ""
    if len(text) > max_len:
        return text[: max_len - 3].rstrip() + "..."
    return text


def history_list(value: Any, max_items: int = 40) -> list[str]:
    items: list[str] = []

    def add(item: Any) -> None:
        if isinstance(item, list):
            for child in item:
                add(child)
            return
        if isinstance(item, dict):
            title = (
                item.get("title")
                or item.get("summary")
                or item.get("description")
                or item.get("risk")
                or item.get("decision")
                or item
            )
            text = compact_history_text(title)
        else:
            text = compact_history_text(item)
        if text and text not in items:
            items.append(text)

    add(value)
    return items[:max_items]


def history_object_list(value: Any, title_keys: list[str], max_items: int = 40) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []

    def add(item: Any) -> None:
        if isinstance(item, list):
            for child in item:
                add(child)
            return
        if isinstance(item, dict):
            copied = dict(item)
            title = next((copied.get(key) for key in title_keys if copied.get(key)), None)
            copied["title"] = compact_history_text(title or copied.get("title") or copied)
        else:
            copied = {"title": compact_history_text(item)}
        if copied["title"] and copied["title"] not in {obj.get("title") for obj in objects}:
            objects.append(copied)

    add(value)
    return objects[:max_items]


def markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = re.match(r"^##+\s+(.+?)\s*$", line)
        if match:
            current = match.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def section_matches(heading: str, needles: list[str]) -> bool:
    lower = heading.lower()
    return any(needle.lower() in lower for needle in needles)


def markdown_section_items(text: str, heading_needles: list[str], max_items: int = 20) -> list[str]:
    items: list[str] = []
    for heading, body in markdown_sections(text).items():
        if not section_matches(heading, heading_needles):
            continue
        in_fence = False
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if line.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence or not line or line.startswith("|") or set(line) <= {"-", " "}:
                continue
            if line.startswith("- "):
                line = line[2:].strip()
            elif line.startswith("* "):
                line = line[2:].strip()
            elif re.match(r"^\d+\.\s+", line):
                line = re.sub(r"^\d+\.\s+", "", line).strip()
            elif items:
                continue
            text_item = compact_history_text(line)
            if text_item and text_item not in items:
                items.append(text_item)
            if len(items) >= max_items:
                return items
    return items


def safe_stage_text(feature: str, stage: str) -> str:
    path = stage_output_path(feature, stage)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def load_history_stage_results(feature: str) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for stage in STAGES:
        result_path = stage_result_json_path(feature, stage)
        if result_path.exists():
            parsed = read_json_file(result_path, {})
            if isinstance(parsed, dict):
                results[stage] = parsed
                continue
        text = safe_stage_text(feature, stage)
        if text:
            parsed = find_stage_result(text)
            if parsed:
                results[stage] = parsed
    return results


def history_source_artifacts(feature: str) -> list[str]:
    artifacts: list[str] = []
    for stage in STAGES:
        for path in [stage_output_path(feature, stage), stage_result_json_path(feature, stage)]:
            if path.exists():
                artifacts.append(rel(path))
    latest = latest_verification_result_path(feature)
    if latest.exists():
        artifacts.append(rel(latest))
    run_json = state_path(feature)
    if run_json.exists():
        artifacts.append(rel(run_json))
    return sorted(dict.fromkeys(artifacts))


def split_event_paths(value: Any) -> list[str]:
    if isinstance(value, list):
        return [norm_repo_path(str(item)) for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []
    return [norm_repo_path(part.strip()) for part in value.split(",") if part.strip()]


def collect_history_changed_files(
    state: dict[str, Any],
    stage_results: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    paths: list[str] = []
    for result in stage_results.values():
        paths.extend(history_list(result.get("changed_files"), max_items=200))
        paths.extend(history_list(result.get("produced_files"), max_items=200))
    for event in state.get("events", []):
        if not isinstance(event, dict):
            continue
        if event.get("event") in {"commit_start", "commit_created", "commit_amended"}:
            paths.extend(split_event_paths(event.get("paths")))

    grouped = {"production": [], "tests": [], "harness_artifacts": [], "docs": [], "other": []}
    for raw_path in paths:
        path = norm_repo_path(raw_path)
        if not path or path in {".", "./"}:
            continue
        if path.startswith(".ai/docs/"):
            bucket = "docs"
        elif path.startswith(".ai/"):
            bucket = "harness_artifacts"
        elif is_test_path(path):
            bucket = "tests"
        elif is_production_code_path(path):
            bucket = "production"
        else:
            bucket = "other"
        if path not in grouped[bucket]:
            grouped[bucket].append(path)
    return {key: sorted(value) for key, value in grouped.items() if value}


def load_history_verification(feature: str, stage_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    latest = latest_verification_result_path(feature)
    if latest.exists():
        parsed = read_json_file(latest, {})
        if isinstance(parsed, dict) and parsed:
            return {
                "status": parsed.get("status", "UNKNOWN"),
                "passed": bool(parsed.get("passed")),
                "failed_commands": parsed.get("failed_commands", []),
                "commands": [
                    command.get("name")
                    for command in parsed.get("commands", [])
                    if isinstance(command, dict) and command.get("name")
                ],
                "source": rel(latest),
            }

    verify_result = stage_results.get(VERIFY_STAGE, {})
    summary = verify_result.get("verification_summary")
    if isinstance(summary, dict):
        return {
            "status": summary.get("status", verify_result.get("status", "UNKNOWN")),
            "passed": str(summary.get("status", "")).upper() == "PASS",
            "failed_commands": [],
            "commands": [key for key in summary.keys() if key != "status"],
            "source": rel(stage_result_json_path(feature, VERIFY_STAGE)),
        }
    return {
        "status": verify_result.get("status", "UNKNOWN"),
        "passed": str(verify_result.get("status", "")).upper() == "PASS",
        "failed_commands": [],
        "commands": [],
        "source": rel(stage_result_json_path(feature, VERIFY_STAGE))
        if stage_result_json_path(feature, VERIFY_STAGE).exists()
        else "",
    }


def collect_history_notes(
    feature: str,
    stage_results: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    implemented: list[str] = []
    risks: list[dict[str, Any]] = []
    future_improvements: list[str] = []
    decisions: list[dict[str, Any]] = []

    for stage, result in stage_results.items():
        source = rel(stage_output_path(feature, stage)) if stage_output_path(feature, stage).exists() else ""
        notes = result.get("history_notes") if isinstance(result.get("history_notes"), dict) else {}
        implemented.extend(history_list(result.get("implemented")))
        implemented.extend(history_list(notes.get("implemented") if notes else None))
        future_improvements.extend(history_list(result.get("future_improvements")))
        future_improvements.extend(history_list(notes.get("future_improvements") if notes else None))

        for item in history_object_list(result.get("risks"), ["title", "summary", "description", "risk"]) + history_object_list(
            notes.get("risks") if notes else None,
            ["title", "summary", "description", "risk"],
        ):
            item.setdefault("category", "risk")
            item["source_stage"] = item.get("source_stage") or stage
            item["source_artifact"] = item.get("source_artifact") or source
            risks.append(item)
        for item in history_object_list(result.get("known_limitations"), ["title", "summary", "description", "risk"]):
            item.setdefault("category", "known_limitation")
            item["source_stage"] = item.get("source_stage") or stage
            item["source_artifact"] = item.get("source_artifact") or source
            risks.append(item)

        fix_inputs = result.get("fix_inputs")
        if isinstance(fix_inputs, dict):
            deferred = history_list(fix_inputs.get("deferred"))
            future_improvements.extend(deferred)
            for item in deferred:
                risks.append(
                    {
                        "title": item,
                        "category": "future_improvement",
                        "source_stage": stage,
                        "source_artifact": source,
                    }
                )

        for item in history_object_list(result.get("decisions"), ["title", "summary", "description", "decision"]) + history_object_list(
            notes.get("decisions") if notes else None,
            ["title", "summary", "description", "decision"],
        ):
            item["source_stage"] = item.get("source_stage") or stage
            item["source_artifact"] = item.get("source_artifact") or source
            decisions.append(item)

        text = safe_stage_text(feature, stage)
        implemented.extend(
            markdown_section_items(
                text,
                ["implementation summary", "implemented", "implementation details", "changed files"],
            )
        )
        future_from_text = markdown_section_items(
            text,
            ["future", "follow-up", "known limitation", "remaining risk", "deferred"],
        )
        future_improvements.extend(future_from_text)
        for item in future_from_text:
            risks.append(
                {
                    "title": item,
                    "category": "future_improvement",
                    "source_stage": stage,
                    "source_artifact": source,
                }
            )
        for item in markdown_section_items(text, ["decision", "why", "alternative", "plan changed"]):
            decisions.append({"title": item, "source_stage": stage, "source_artifact": source})

    implemented = list(dict.fromkeys(item for item in implemented if item))
    future_improvements = list(dict.fromkeys(item for item in future_improvements if item))

    seen_risks: set[str] = set()
    deduped_risks: list[dict[str, Any]] = []
    for risk in risks:
        title = compact_history_text(risk.get("title"))
        if not title or title in seen_risks:
            continue
        seen_risks.add(title)
        risk["title"] = title
        deduped_risks.append(risk)

    seen_decisions: set[str] = set()
    deduped_decisions: list[dict[str, Any]] = []
    for decision in decisions:
        title = compact_history_text(decision.get("title"))
        if not title or title in seen_decisions:
            continue
        seen_decisions.add(title)
        decision["title"] = title
        deduped_decisions.append(decision)

    return implemented[:40], deduped_risks[:40], future_improvements[:40], deduped_decisions[:40]


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
    if isinstance(item, dict):
        title = compact_history_text(
            item.get("title")
            or item.get("summary")
            or item.get("description")
            or item.get("finding")
            or item.get("warning")
            or item.get("item")
            or item
        )
        reason = compact_history_text(
            item.get("reason_not_actioned")
            or item.get("reason")
            or item.get("rationale")
            or item.get("rejection_reason")
            or item.get("defer_reason")
            or item.get("why")
        )
        future_action = compact_history_text(
            item.get("future_action")
            or item.get("future_improvement")
            or item.get("next_action")
            or item.get("mitigation")
        )
        severity = compact_history_text(item.get("severity") or default_severity, max_len=40)
        item_type = compact_history_text(item.get("type") or item_type, max_len=80)
        status = compact_history_text(item.get("status") or status, max_len=40)
        disposition = compact_history_text(item.get("disposition") or disposition, max_len=80)
        source_stage = compact_history_text(item.get("source_stage") or source_stage, max_len=80)
        source_artifact = compact_history_text(item.get("source_artifact") or source_artifact, max_len=300)
    else:
        title = compact_history_text(item)
        reason = ""
        future_action = ""
        severity = default_severity
    if not title:
        return None
    return {
        "title": title,
        "type": item_type,
        "severity": severity,
        "status": status,
        "disposition": disposition,
        "reason_not_actioned": reason,
        "future_action": future_action,
        "source_stage": source_stage,
        "source_artifact": source_artifact,
    }


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
    items: list[dict[str, Any]] = []
    if value is None:
        return items
    raw_items = value if isinstance(value, list) else [value]
    for raw_item in raw_items:
        normalized = normalize_unresolved_source_item(
            raw_item,
            item_type=item_type,
            status=status,
            disposition=disposition,
            source_stage=source_stage,
            source_artifact=source_artifact,
            default_severity=default_severity,
        )
        if normalized and normalized["title"] not in {item["title"] for item in items}:
            items.append(normalized)
    return items


def collect_history_unresolved_items(
    feature: str,
    stage_results: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for stage, result in stage_results.items():
        source = rel(stage_output_path(feature, stage)) if stage_output_path(feature, stage).exists() else ""
        notes = result.get("history_notes") if isinstance(result.get("history_notes"), dict) else {}

        items.extend(
            unresolved_items_from_value(
                result.get("unresolved_items"),
                item_type="unresolved_item",
                status="open",
                disposition="not_actioned",
                source_stage=stage,
                source_artifact=source,
                default_severity="medium",
            )
        )
        items.extend(
            unresolved_items_from_value(
                notes.get("unresolved_items") if notes else None,
                item_type="unresolved_item",
                status="open",
                disposition="not_actioned",
                source_stage=stage,
                source_artifact=source,
                default_severity="medium",
            )
        )
        items.extend(
            unresolved_items_from_value(
                result.get("warnings") or result.get("warning"),
                item_type="warning",
                status="open",
                disposition="warning_only",
                source_stage=stage,
                source_artifact=source,
                default_severity="minor",
            )
        )

        fix_inputs = result.get("fix_inputs")
        if isinstance(fix_inputs, dict):
            items.extend(
                unresolved_items_from_value(
                    fix_inputs.get("rejected"),
                    item_type="review_finding",
                    status="rejected",
                    disposition="rejected",
                    source_stage=stage,
                    source_artifact=source,
                    default_severity="minor",
                )
            )
            items.extend(
                unresolved_items_from_value(
                    fix_inputs.get("deferred"),
                    item_type="review_finding",
                    status="deferred",
                    disposition="deferred",
                    source_stage=stage,
                    source_artifact=source,
                    default_severity="minor",
                )
            )
            items.extend(
                unresolved_items_from_value(
                    fix_inputs.get("warnings"),
                    item_type="verification_warning",
                    status="open",
                    disposition="warning_only",
                    source_stage=stage,
                    source_artifact=source,
                    default_severity="minor",
                )
            )

        verification_summary = result.get("verification_summary")
        if isinstance(verification_summary, dict):
            notes_value = verification_summary.get("notes") or verification_summary.get("warning")
            if notes_value and str(result.get("status") or "").upper() == "PASS":
                items.extend(
                    unresolved_items_from_value(
                        notes_value,
                        item_type="verification_note",
                        status="accepted",
                        disposition="pass_with_note",
                        source_stage=stage,
                        source_artifact=source,
                        default_severity="info",
                    )
                )

        text = safe_stage_text(feature, stage)
        for heading_needles, item_type, status, disposition, severity in [
            (["거부", "rejected", "not accepted"], "review_finding", "rejected", "rejected", "minor"),
            (["보류", "deferred", "future", "follow-up"], "review_finding", "deferred", "deferred", "minor"),
            (["warning", "경고"], "warning", "open", "warning_only", "minor"),
            (["should_consider", "minor", "nit"], "review_suggestion", "open", "not_actioned", "minor"),
        ]:
            for item in markdown_section_items(text, heading_needles, max_items=10):
                normalized = normalize_unresolved_source_item(
                    item,
                    item_type=item_type,
                    status=status,
                    disposition=disposition,
                    source_stage=stage,
                    source_artifact=source,
                    default_severity=severity,
                )
                if normalized:
                    items.append(normalized)

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = "|".join(
            [
                compact_history_text(item.get("title"), max_len=500),
                compact_history_text(item.get("type"), max_len=80),
                compact_history_text(item.get("source_stage"), max_len=80),
            ]
        )
        if not key.strip("|") or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:80]


def stable_history_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(compact_history_text(part, max_len=1000) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def normalize_history_risk(
    item: dict[str, Any],
    *,
    feature: str,
    event_id: str,
    created_at: str,
    default_severity: str,
) -> dict[str, Any]:
    title = compact_history_text(item.get("title") or item.get("summary") or item.get("description"))
    category = compact_history_text(item.get("category") or "risk", max_len=80)
    source_artifact = compact_history_text(item.get("source_artifact"), max_len=300)
    risk_id = compact_history_text(item.get("risk_id"), max_len=120) or stable_history_id(
        "risk",
        feature,
        category,
        title,
    )
    risk = {
        "risk_id": risk_id,
        "제목": title,
        "설명": compact_history_text(item.get("description") or item.get("mitigation") or item.get("future_action") or title),
        "title": title,
        "category": category,
        "severity": compact_history_text(item.get("severity") or default_severity, max_len=40),
        "status": compact_history_text(item.get("status") or "open", max_len=40),
        "introduced_by": feature,
        "last_seen_by": event_id,
        "source_stage": compact_history_text(item.get("source_stage"), max_len=80),
        "source_artifacts": [source_artifact] if source_artifact else [],
        "created_at": created_at,
        "updated_at": created_at,
    }
    return risk


def update_history_risks(event: dict[str, Any]) -> list[dict[str, Any]]:
    existing = read_json_file(history_risks_path(), {"schema_version": HISTORY_SCHEMA_VERSION, "risks": []})
    if not isinstance(existing, dict):
        existing = {"schema_version": HISTORY_SCHEMA_VERSION, "risks": []}
    risks = existing.get("risks")
    if not isinstance(risks, list):
        risks = []

    by_id: dict[str, dict[str, Any]] = {
        str(item.get("risk_id")): item for item in risks if isinstance(item, dict) and item.get("risk_id")
    }
    default_severity = compact_history_text(event.get("risk_level") or "medium", max_len=40)
    for item in event.get("risks", []):
        if not isinstance(item, dict):
            continue
        normalized = normalize_history_risk(
            item,
            feature=str(event.get("feature") or ""),
            event_id=str(event.get("event_id") or ""),
            created_at=str(event.get("completed_at") or iso_now()),
            default_severity=default_severity,
        )
        risk_id = normalized["risk_id"]
        if risk_id in by_id:
            current = by_id[risk_id]
            current.update(
                {
                    "제목": normalized["제목"],
                    "설명": normalized["설명"],
                    "title": normalized["title"],
                    "category": normalized["category"],
                    "severity": normalized["severity"] or current.get("severity", ""),
                    "last_seen_by": normalized["last_seen_by"],
                    "source_stage": normalized["source_stage"],
                    "updated_at": normalized["updated_at"],
                }
            )
            existing_sources = current.get("source_artifacts")
            if not isinstance(existing_sources, list):
                existing_sources = []
            for source in normalized["source_artifacts"]:
                if source not in existing_sources:
                    existing_sources.append(source)
            current["source_artifacts"] = existing_sources
            if not current.get("status"):
                current["status"] = "open"
        else:
            by_id[risk_id] = normalized

    updated = sorted(by_id.values(), key=lambda item: (str(item.get("status")), str(item.get("updated_at")), str(item.get("risk_id"))))
    write_json_file(history_risks_path(), {"schema_version": HISTORY_SCHEMA_VERSION, "risks": updated})
    return updated


def normalize_history_unresolved_item(
    item: dict[str, Any],
    *,
    feature: str,
    event_id: str,
    created_at: str,
) -> dict[str, Any]:
    title = compact_history_text(item.get("title") or item.get("summary") or item.get("description"))
    item_type = compact_history_text(item.get("type") or "unresolved_item", max_len=80)
    source_stage = compact_history_text(item.get("source_stage"), max_len=80)
    source_artifact = compact_history_text(item.get("source_artifact"), max_len=300)
    item_id = compact_history_text(item.get("item_id"), max_len=120) or stable_history_id(
        "item",
        feature,
        item_type,
        source_stage,
        title,
    )
    return {
        "item_id": item_id,
        "제목": title,
        "설명": compact_history_text(
            item.get("description")
            or item.get("reason_not_actioned")
            or item.get("future_action")
            or title
        ),
        "feature": feature,
        "type": item_type,
        "severity": compact_history_text(item.get("severity") or "minor", max_len=40),
        "status": compact_history_text(item.get("status") or "open", max_len=40),
        "disposition": compact_history_text(item.get("disposition") or "not_actioned", max_len=80),
        "title": title,
        "reason_not_actioned": compact_history_text(item.get("reason_not_actioned")),
        "future_action": compact_history_text(item.get("future_action")),
        "source_stage": source_stage,
        "source_artifact": source_artifact,
        "introduced_by": feature,
        "last_seen_by": event_id,
        "created_at": created_at,
        "updated_at": created_at,
    }


def update_history_unresolved_items(event: dict[str, Any]) -> list[dict[str, Any]]:
    existing = read_json_file(
        history_unresolved_items_path(),
        {"schema_version": HISTORY_SCHEMA_VERSION, "items": []},
    )
    if not isinstance(existing, dict):
        existing = {"schema_version": HISTORY_SCHEMA_VERSION, "items": []}
    items = existing.get("items")
    if not isinstance(items, list):
        items = []

    by_id: dict[str, dict[str, Any]] = {
        str(item.get("item_id")): item for item in items if isinstance(item, dict) and item.get("item_id")
    }
    for item in event.get("unresolved_items", []):
        if not isinstance(item, dict):
            continue
        normalized = normalize_history_unresolved_item(
            item,
            feature=str(event.get("feature") or ""),
            event_id=str(event.get("event_id") or ""),
            created_at=str(event.get("completed_at") or iso_now()),
        )
        item_id = normalized["item_id"]
        if item_id in by_id:
            current = by_id[item_id]
            created_at = current.get("created_at") or normalized["created_at"]
            current.update(normalized)
            current["created_at"] = created_at
        else:
            by_id[item_id] = normalized

    active_order = {"open": "0", "deferred": "1", "accepted": "2", "rejected": "3", "closed": "4"}
    updated = sorted(
        by_id.values(),
        key=lambda item: (
            active_order.get(str(item.get("status") or "").lower(), "9"),
            str(item.get("updated_at")),
            str(item.get("item_id")),
        ),
    )
    write_json_file(
        history_unresolved_items_path(),
        {"schema_version": HISTORY_SCHEMA_VERSION, "items": updated},
    )
    return updated


def append_history_decisions(event: dict[str, Any]) -> list[dict[str, Any]]:
    appended: list[dict[str, Any]] = []
    completed_at = str(event.get("completed_at") or iso_now())
    for raw in event.get("decisions", []):
        if not isinstance(raw, dict):
            continue
        title = compact_history_text(raw.get("title"))
        if not title:
            continue
        decision = {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "decision_id": compact_history_text(raw.get("decision_id"), max_len=120)
            or stable_history_id("decision", event.get("feature"), title),
            "제목": title,
            "설명": compact_history_text(raw.get("reason") or title),
            "feature": event.get("feature"),
            "event_id": event.get("event_id"),
            "title": title,
            "reason": compact_history_text(raw.get("reason")),
            "source_stage": compact_history_text(raw.get("source_stage"), max_len=80),
            "source_artifact": compact_history_text(raw.get("source_artifact"), max_len=300),
            "created_at": completed_at,
        }
        if append_jsonl_if_missing(history_decisions_path(), decision, "decision_id"):
            appended.append(decision)
    return appended


def update_history_feature_summary(event: dict[str, Any]) -> dict[str, Any]:
    feature = str(event.get("feature") or "")
    path = history_features_dir() / f"{feature}.json"
    existing = read_json_file(path, {})
    if not isinstance(existing, dict):
        existing = {}

    event_id = str(event.get("event_id") or "")
    event_ids = existing.get("event_ids")
    if not isinstance(event_ids, list):
        event_ids = []
    if event_id and event_id not in event_ids:
        event_ids.append(event_id)

    runs = existing.get("runs")
    if not isinstance(runs, list):
        runs = []
    if event_id and not any(isinstance(item, dict) and item.get("event_id") == event_id for item in runs):
        runs.append(
            {
                "event_id": event_id,
                "status": event.get("status"),
                "pipeline": event.get("pipeline"),
                "completed_at": event.get("completed_at"),
                "commits": event.get("commits", {}),
                "verification": event.get("verification", {}),
            }
        )

    summary = {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "제목": f"{feature} 기능 요약",
        "설명": compact_history_text(event.get("request_summary"), max_len=800),
        "feature": feature,
        "first_seen_at": existing.get("first_seen_at") or event.get("completed_at"),
        "last_completed_at": event.get("completed_at"),
        "latest_event_id": event_id,
        "event_ids": event_ids,
        "request_summary": event.get("request_summary", ""),
        "latest_status": event.get("status", ""),
        "latest_pipeline": event.get("pipeline", ""),
        "implemented": event.get("implemented", []),
        "future_improvements": event.get("future_improvements", []),
        "unresolved_items": event.get("unresolved_items", []),
        "changed_files": event.get("changed_files", {}),
        "commits": event.get("commits", {}),
        "source_artifacts": event.get("source_artifacts", []),
        "runs": runs[-20:],
        "updated_at": iso_now(),
    }
    write_json_file(path, summary)
    return summary


def render_history_summary(
    events: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    unresolved_items: list[dict[str, Any]],
) -> None:
    complete_events = [event for event in events if event.get("event_type") == "run_completed"]
    open_risks = [risk for risk in risks if str(risk.get("status") or "open").lower() == "open"]
    active_unresolved = [
        item
        for item in unresolved_items
        if str(item.get("status") or "open").lower() in {"open", "deferred"}
    ]
    lines = [
        "# 프로젝트 히스토리",
        "",
        "로컬 하네스가 자동 생성한 장기 기록 요약입니다.",
        "",
        f"- 기록된 run: {len(complete_events)}",
        f"- 열린 리스크 / 미래 개선점: {len(open_risks)}",
        f"- 열린/보류 미해결 항목: {len(active_unresolved)}",
        "",
        "## 최근 완료 Run",
        "",
    ]
    if not complete_events:
        lines.append("- 없음")
    for event in complete_events[-20:][::-1]:
        verification = event.get("verification") if isinstance(event.get("verification"), dict) else {}
        lines.append(
            "- "
            f"{event.get('completed_at', '')} "
            f"{event.get('feature', '')} "
            f"({event.get('pipeline', '')}, {event.get('status', '')}, verify={verification.get('status', 'UNKNOWN')})"
        )
        implemented = event.get("implemented") if isinstance(event.get("implemented"), list) else []
        for item in implemented[:3]:
            lines.append(f"  - {item}")
    lines.extend(["", "## 열린 리스크와 후속 개선점", ""])
    if not open_risks:
        lines.append("- 없음")
    for risk in sorted(open_risks, key=lambda item: str(item.get("updated_at")), reverse=True)[:30]:
        lines.append(
            "- "
            f"[{risk.get('severity', 'medium')}] "
            f"{risk.get('title', '')} "
            f"(from {risk.get('introduced_by', '')})"
        )
    lines.extend(["", "## 미해결 리뷰/검증 항목", ""])
    if not active_unresolved:
        lines.append("- 없음")
    for item in sorted(active_unresolved, key=lambda item: str(item.get("updated_at")), reverse=True)[:30]:
        lines.append(
            "- "
            f"[{item.get('status', 'open')}/{item.get('severity', 'minor')}] "
            f"{item.get('title', '')} "
            f"(from {item.get('feature', '')}:{item.get('source_stage', '')})"
        )
    history_summary_path().write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def record_project_history(state: dict[str, Any]) -> dict[str, Any]:
    initialized = ensure_history_store()
    feature = str(state["feature_name"])
    stage_results = load_history_stage_results(feature)
    implemented, risks, future_improvements, decisions = collect_history_notes(feature, stage_results)
    unresolved_items = collect_history_unresolved_items(feature, stage_results)
    changed_files = collect_history_changed_files(state, stage_results)
    verification = load_history_verification(feature, stage_results)
    completed_at = iso_now()
    event_id = history_event_id(state)
    risk_levels = [
        compact_history_text(result.get("risk_level"), max_len=40)
        for result in stage_results.values()
        if result.get("risk_level")
    ]
    risk_level = risk_levels[-1] if risk_levels else ""

    event = {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "event_type": "run_completed",
        "event_id": event_id,
        "제목": f"{feature} 기능 개발 기록",
        "설명": compact_history_text(state.get("request"), max_len=800),
        "history_initialized": initialized,
        "feature": feature,
        "pipeline": state.get("pipeline_mode") or PIPELINE_MODE,
        "status": state.get("status"),
        "created_at": state.get("created_at"),
        "completed_at": completed_at,
        "request_summary": compact_history_text(state.get("request"), max_len=800),
        "implemented": implemented,
        "changed_files": changed_files,
        "verification": verification,
        "risk_level": risk_level,
        "risks": risks,
        "future_improvements": future_improvements,
        "unresolved_items": unresolved_items,
        "decisions": decisions,
        "commits": state.get("commits", {}),
        "source_artifacts": history_source_artifacts(feature),
    }

    appended = append_jsonl_if_missing(history_events_path(), event, "event_id")
    update_history_feature_summary(event)
    updated_risks = update_history_risks(event)
    updated_unresolved_items = update_history_unresolved_items(event)
    appended_decisions = append_history_decisions(event)
    render_history_summary(iter_jsonl(history_events_path()), updated_risks, updated_unresolved_items)

    state["history"] = {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "event_id": event_id,
        "events": rel(history_events_path()),
        "feature_summary": rel(history_features_dir() / f"{feature}.json"),
        "risks": rel(history_risks_path()),
        "unresolved_items": rel(history_unresolved_items_path()),
        "decisions": rel(history_decisions_path()),
        "summary": rel(history_summary_path()),
        "status": "recorded" if appended else "already_recorded",
        "recorded_at": completed_at,
        "decisions_appended": len(appended_decisions),
    }
    return state["history"]


def should_extract_pc_candidates(state: dict[str, Any]) -> bool:
    return str(state.get("pipeline_mode") or PIPELINE_MODE) in {"standard", "full"}


def pc_candidate_source_artifact_text(feature: str, max_chars_per_file: int = 8000) -> str:
    blocks: list[str] = []
    for artifact in history_source_artifacts(feature):
        path = ROOT / artifact
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(text) > max_chars_per_file:
            text = text[:max_chars_per_file] + "\n...[truncated]"
        blocks.extend([f"### {artifact}", "```text", text, "```", ""])
    return "\n".join(blocks).strip() or "- none"


def build_pc_candidate_extraction_prompt(state: dict[str, Any]) -> str:
    feature = str(state["feature_name"])
    stage_results = load_history_stage_results(feature)
    changed_files = collect_history_changed_files(state, stage_results)
    verification = load_history_verification(feature, stage_results)
    current_contract = project_contract_prompt_text()
    artifacts_text = pc_candidate_source_artifact_text(feature)
    existing_store = read_pc_candidates_store()
    existing_rule_candidates = [
        compact_history_text(item.get("rule_candidate"), max_len=240)
        for item in existing_store.get("candidates", [])
        if item.get("rule_candidate")
    ][-50:]

    return f"""# Project Contract Candidate Extraction

You are extracting Project Contract candidates after a completed local AI development pipeline.

This is not a normal feature implementation task.
Do not edit files. Return only a JSON object.

## Goal
Find rules that should become candidates for the long-term Project Contract.
The Project Contract is observational: it is based on conventions and decisions that emerged from real development.

## Pipeline Context
- feature_name: {feature}
- pipeline_mode: {state.get("pipeline_mode") or PIPELINE_MODE}
- request: {state.get("request", "")}
- completed_at: {iso_now()}

## Current Approved Project Contract
{current_contract}

## Existing Candidate Summaries
{json.dumps(existing_rule_candidates, ensure_ascii=False, indent=2)}

## Changed Files Summary
{json.dumps(changed_files, ensure_ascii=False, indent=2)}

## Harness Verification
{json.dumps(verification, ensure_ascii=False, indent=2)}

## Source Artifacts
{artifacts_text}

## Candidate Criteria
Create a candidate only when the rule is clearly worth managing as a project-wide contract.

The bar is intentionally high. A candidate must pass all of these:
- It applies across many future features or pipelines in this repository.
- It controls project-level engineering behavior, not a local implementation choice.
- It is likely to recur even when the exact feature, UI screen, or library changes.
- It is not already clearly covered by the current Project Contract.
- It belongs to a durable area such as naming, architecture, directory layout, testing policy, error handling, data boundaries, dependency policy, or cross-feature UX policy.

Before emitting anything, classify every observation internally:
- `project_wide`: broad project rule worth user review as Project Contract.
- `stack_wide`: useful only for one technology stack, framework, platform, or library.
- `feature_local`: useful only for this feature or domain.
- `implementation_detail`: small tactical implementation detail.

Emit only `project_wide` candidates.
Discard `stack_wide`, `feature_local`, and `implementation_detail`. Do not include them in the JSON.

Do not create candidates for:
- one-off implementation details
- framework-specific micro patterns unless the project has clearly standardized that stack globally
- UI control behavior that is merely a convenience for one screen
- performance tweaks tied to a single implementation
- obvious bug fixes
- temporary code
- rules already clearly covered by the current Project Contract
- weak observations with no future impact
- anything that would be better recorded as history than enforced as a future project rule

## Output Contract
Return exactly one JSON object. Do not wrap it in Markdown.

Schema:
{{
  "candidates": [
    {{
      "impact_scope": "project_wide",
      "category": "architecture | naming | ux | testing | error_handling | data | dependency | other",
      "rule_candidate": "A concise Korean rule phrased as something future work should do.",
      "rationale": "Why this is truly project-wide rather than stack-wide, feature-local, or an implementation detail.",
      "evidence": ["Relevant files, artifacts, or decisions."],
      "recommended_contract_section": "Hard Rules | Architecture | Naming | UX | Testing | Error Handling | Data | Dependencies | Other"
    }}
  ]
}}

If there are no worthwhile candidates, return {{"candidates": []}}.
"""


def normalize_pc_candidate(raw: dict[str, Any], state: dict[str, Any], created_at: str) -> dict[str, Any] | None:
    impact_scope = compact_history_text(raw.get("impact_scope") or raw.get("scope"), max_len=80)
    if impact_scope.strip().lower() != PC_PROJECT_WIDE_SCOPE:
        return None
    rule = compact_history_text(raw.get("rule_candidate") or raw.get("summary"), max_len=600)
    if not rule:
        return None
    category = compact_history_text(raw.get("category") or "other", max_len=80) or "other"
    feature = str(state["feature_name"])
    candidate_id = stable_history_id("pc", feature, category, rule)
    evidence = history_list(raw.get("evidence"), max_items=40)
    return {
        "id": candidate_id,
        "status": PC_PENDING_STATUS,
        "source_feature": feature,
        "source_pipeline": state.get("pipeline_mode") or PIPELINE_MODE,
        "source_run_created_at": state.get("created_at", ""),
        "source_artifacts": history_source_artifacts(feature),
        "impact_scope": PC_PROJECT_WIDE_SCOPE,
        "category": category,
        "rule_candidate": rule,
        "rationale": compact_history_text(raw.get("rationale"), max_len=1000),
        "evidence": evidence,
        "recommended_contract_section": compact_history_text(
            raw.get("recommended_contract_section"),
            max_len=120,
        ),
        "created_at": created_at,
        "decided_at": "",
        "decision_reason": "",
        "extraction_model": "claude",
    }


def append_pc_candidates(candidates: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    store = read_pc_candidates_store()
    existing_ids = {
        str(item.get("id"))
        for item in store.get("candidates", [])
        if str(item.get("id") or "")
    }
    added: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "")
        if not candidate_id or candidate_id in existing_ids:
            continue
        store.setdefault("candidates", []).append(candidate)
        existing_ids.add(candidate_id)
        added.append(candidate)
    if added:
        write_pc_candidates_store(store)
    return {
        "status": "recorded",
        "path": rel(pc_candidates_path()),
        "added_count": len(added),
        "added_ids": [item["id"] for item in added],
    }


def extract_project_contract_candidates(state: dict[str, Any]) -> dict[str, Any]:
    if not should_extract_pc_candidates(state):
        return {"status": "skipped", "reason": "pipeline does not extract PC candidates"}

    feature = str(state["feature_name"])
    prompt = build_pc_candidate_extraction_prompt(state)
    log_event(
        state,
        "pc_candidate_extraction_started",
        "extracting project contract candidates",
        stage=PC_REVIEW_STAGE,
    )
    result = run_text_provider_prompt(
        "claude",
        prompt,
        logs_dir=run_dir(feature) / "logs",
        log_prefix="pc_candidates",
        timeout_seconds=3600,
        performance=state.get("performance"),
    )
    if result.get("returncode") != 0 or result.get("timed_out"):
        raise HarnessError(
            "PC candidate extraction provider failed. "
            f"stdout={result.get('stdout')} stderr={result.get('stderr')}"
        )

    parsed = parse_result_json_from_text(str(result.get("stdout_text") or ""))
    raw_candidates = parsed.get("candidates") if isinstance(parsed, dict) else None
    if raw_candidates is None:
        raise HarnessError(
            "PC candidate extraction did not return a JSON object with a candidates list. "
            f"stdout={result.get('stdout')}"
        )
    if not isinstance(raw_candidates, list):
        raise HarnessError("PC candidate extraction field 'candidates' must be a list.")

    created_at = iso_now()
    normalized = [
        candidate
        for candidate in (
            normalize_pc_candidate(item, state, created_at)
            for item in raw_candidates
            if isinstance(item, dict)
        )
        if candidate
    ]
    append_result = append_pc_candidates(normalized, state)
    extraction = {
        "status": "PASS",
        "provider": "claude",
        "raw_candidate_count": len(raw_candidates),
        "candidate_count": len(normalized),
        "filtered_out_count": len(raw_candidates) - len(normalized),
        "recorded_count": append_result["added_count"],
        "candidate_ids": append_result["added_ids"],
        "candidates_path": append_result["path"],
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
        "meta": result.get("meta"),
    }
    state["pc_candidate_extraction"] = extraction
    log_event(
        state,
        "pc_candidate_extraction_completed",
        "project contract candidates extracted",
        stage=PC_REVIEW_STAGE,
        raw_candidate_count=len(raw_candidates),
        candidate_count=len(normalized),
        filtered_out_count=len(raw_candidates) - len(normalized),
        recorded_count=append_result["added_count"],
    )
    return extraction


def complete_run(state: dict[str, Any], stage: str) -> dict[str, Any]:
    state["status"] = "complete"
    state["current_stage"] = "done"
    state.pop("blocked", None)
    log_event(state, "complete", "run complete", stage=stage)
    save_state(state)
    try:
        history_result = record_project_history(state)
    except Exception as exc:
        log_event(
            state,
            "history_failed",
            f"project history update failed: {exc}",
            stage=stage,
        )
    else:
        log_event(
            state,
            "history_recorded",
            "project history updated",
            stage=stage,
            status=history_result.get("status"),
            event_id=history_result.get("event_id"),
            events=history_result.get("events"),
        )
    save_state(state)
    return state


def finish_pc_candidate_extraction(state: dict[str, Any]) -> dict[str, Any]:
    source_stage = str(state.get("pc_candidate_source_stage") or VERIFY_STAGE)
    try:
        extraction = extract_project_contract_candidates(state)
    except Exception as exc:
        state["status"] = "blocked"
        state["current_stage"] = PC_REVIEW_STAGE
        state["blocked"] = {
            "stage": PC_REVIEW_STAGE,
            "reason": f"PC candidate extraction failed: {exc}",
            "next_stage": PC_REVIEW_STAGE,
        }
        write_handoff(
            state,
            str(state["blocked"]["reason"]),
            stage=PC_REVIEW_STAGE,
            next_action="PC 후보 추출 실패 원인을 확인한 뒤 resume으로 다시 시도하세요.",
        )
        log_event(
            state,
            "pc_candidate_extraction_failed",
            str(exc),
            stage=PC_REVIEW_STAGE,
        )
        save_state(state)
        return state

    state["pc_candidate_extraction"] = extraction
    state.pop("blocked", None)
    state.pop("pc_candidate_source_stage", None)
    save_state(state)
    return complete_run(state, source_stage)


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
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "## 단계 결과":
            start = i + 1
    if start is None:
        return {}

    section_lines: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        section_lines.append(line)
    section = "\n".join(section_lines).strip()

    json_result = parse_result_json_from_text(section)
    if json_result:
        return json_result

    result: dict[str, Any] = {}
    current_key: str | None = None
    for line in section_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            item = stripped[2:]
            if ":" in item:
                key, value = item.split(":", 1)
                key = key.strip()
                value = value.strip()
                if value == "":
                    result[key] = []
                    current_key = key
                else:
                    result[key] = parse_result_scalar(value)
                    current_key = key
            elif current_key and isinstance(result.get(current_key), list):
                result[current_key].append(item.strip())
        elif stripped.startswith("-") and current_key and isinstance(result.get(current_key), list):
            result[current_key].append(stripped[1:].strip())
        elif line.startswith("  - ") and current_key and isinstance(result.get(current_key), list):
            result[current_key].append(line[4:].strip())
    return result


def parse_result_json_from_text(text: str) -> dict[str, Any]:
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S | re.I)
    if fence:
        text = fence.group(1).strip()
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        text = text[start : end + 1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def read_stage_result_json(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HarnessError(f"Invalid stage result JSON in {rel(path)}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HarnessError(f"Stage result JSON must be an object: {rel(path)}")
    return parsed


def parse_result_scalar(value: str) -> Any:
    value = value.strip()
    low = value.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low == "없음":
        return ""
    return value


def extract_feature_name(spec_text: str) -> str | None:
    match = re.search(r"^\s*-\s*feature_name:\s*([a-z0-9][a-z0-9-]*)\s*$", spec_text, re.M)
    if match:
        return match.group(1)
    return None


def maybe_rename_feature(state: dict[str, Any]) -> dict[str, Any]:
    old = state["feature_name"]
    if state.get("feature_name_locked"):
        return state
    spec_path = stage_output_path(old, START_STAGE)
    if not spec_path.exists():
        return state
    feature_name = extract_feature_name(spec_path.read_text(encoding="utf-8"))
    if not feature_name:
        result_json = stage_result_json_path(old, START_STAGE)
        if result_json.exists():
            try:
                json_feature = read_stage_result_json(result_json).get("feature_name")
            except HarnessError:
                json_feature = None
            if isinstance(json_feature, str):
                feature_name = json_feature
    if not feature_name or feature_name == old:
        return state
    if not validate_slug(feature_name):
        state["status"] = "blocked"
        state["blocked"] = {
            "reason": f"Invalid feature_name in 00_spec.md: {feature_name}",
            "stage": START_STAGE,
        }
        save_state(state)
        return state

    old_feature_dir = feature_dir(old)
    new_feature_dir = feature_dir(feature_name)
    old_run_dir = run_dir(old)
    new_run_dir = run_dir(feature_name)
    if new_feature_dir.exists() or new_run_dir.exists():
        state["status"] = "blocked"
        state["blocked"] = {
            "reason": f"Cannot rename feature to existing run or feature: {feature_name}",
            "stage": START_STAGE,
        }
        save_state(state)
        return state

    if old_feature_dir.exists():
        shutil.move(str(old_feature_dir), str(new_feature_dir))
    state["feature_name"] = feature_name
    state.setdefault("events", []).append(
        {"at": iso_now(), "event": "feature_renamed", "from": old, "to": feature_name}
    )
    if old_run_dir.exists():
        shutil.move(str(old_run_dir), str(new_run_dir))
    save_state(state)
    return state


def stage_default_next(stage: str) -> str | None:
    meta, _, _ = read_preset(stage)
    if stage == VERIFY_STAGE:
        return str(meta.get("default_next_stage_on_pass", DOCUMENT_STAGE or "done"))
    if DOCUMENT_STAGE and stage == DOCUMENT_STAGE:
        return "done"
    return meta.get("default_next_stage")  # type: ignore[return-value]


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def expand_policy_item(item: Any, feature: str) -> str:
    return norm_repo_path(str(item).replace("[기능명]", feature))


def is_test_path(path: str) -> bool:
    path = norm_repo_path(path)
    return path == "tests" or path.startswith("tests/")


def is_production_code_path(path: str) -> bool:
    path = norm_repo_path(path)
    return path.startswith("src/") and not is_test_path(path)


def direct_policy_match(path: str, policy_path: str) -> bool:
    policy_path = norm_repo_path(policy_path).rstrip("/")
    if not policy_path or policy_path.lower() == "none":
        return False
    return path == policy_path or path.startswith(policy_path + "/")


def policy_item_matches(path: str, item: str, before_snapshot: dict[str, str]) -> bool:
    path = norm_repo_path(path)
    item = norm_repo_path(item)
    existed_before = path in before_snapshot

    if item == "production_code":
        return is_production_code_path(path)
    if item == "tests":
        return is_test_path(path)
    if item == "new_tests":
        return is_test_path(path) and not existed_before
    if item == "existing_tests":
        return is_test_path(path) and existed_before
    return direct_policy_match(path, item)


def write_policy_violations(state: dict[str, Any], stage: str) -> list[str]:
    feature = state["feature_name"]
    meta, _, _ = read_preset(stage)
    snapshots = state.get("stage_file_snapshots", {})
    before_snapshot = snapshots.get(stage)
    if not isinstance(before_snapshot, dict):
        changed_paths = filtered_changed_paths(state, stage)
        before_snapshot = {}
    else:
        changed_paths = changed_since_snapshot(before_snapshot, feature)

    allowed = [expand_policy_item(item, feature) for item in meta.get("allowed_writes", [])]
    if stage in STAGES:
        allowed.append(rel(stage_output_path(feature, stage)))
        allowed.append(rel(stage_result_json_path(feature, stage)))
    forbidden = [expand_policy_item(item, feature) for item in meta.get("forbidden_writes", [])]
    violations: list[str] = []

    for path in changed_paths:
        if is_harness_internal_path(path, feature):
            continue
        forbidden_match = next(
            (item for item in forbidden if policy_item_matches(path, item, before_snapshot)),
            None,
        )
        if forbidden_match:
            violations.append(f"{path} matches forbidden_writes entry {forbidden_match!r}")
            continue

        allowed_match = any(policy_item_matches(path, item, before_snapshot) for item in allowed)
        if not allowed_match:
            violations.append(f"{path} is outside allowed_writes")

    return violations


def stage_status(result: dict[str, Any]) -> str:
    return str(result.get("status", "")).strip().upper()


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
            provider = provider_for_stage(stage)
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
    attempts = state.setdefault("attempts", {})
    attempt = int(attempts.get(stage, 0)) + 1
    attempts[stage] = attempt
    prompt_dir = run_dir(state["feature_name"]) / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    return prompt_dir / f"{stage}_attempt{attempt}.md"


def generate_prompt(state: dict[str, Any], stage: str, retry_context: str | None = None) -> Path:
    feature = state["feature_name"]
    meta, body, raw = read_preset(stage)
    preset_text = raw.replace("[기능명]", feature)
    output = stage_output_path(feature, stage)
    result_json = stage_result_json_path(feature, stage)
    ensure_project_contract_file()
    state.setdefault("stage_file_snapshots", {})[stage] = file_policy_snapshot(feature)
    defaults_mode = bool(state.get("defaults_mode"))
    decision_policy = (
        "Use recommended defaults for ambiguous decisions. Do not return NEEDS_USER unless the task is impossible, unsafe, "
        "requires credentials/secrets that are not available, or would perform destructive/non-reversible actions. "
        "Record all default decisions and their rationale in the stage output."
        if defaults_mode
        else
        "Ask for user input when the preset's question criteria require it. Return NEEDS_USER for unresolved decisions."
    )

    previous_outputs: list[str] = []
    for prev in STAGES:
        if prev == stage:
            break
        prev_path = stage_output_path(feature, prev)
        if prev_path.exists():
            previous_outputs.append(f"- {rel(prev_path)}")
        prev_result_json = stage_result_json_path(feature, prev)
        if prev_result_json.exists():
            previous_outputs.append(f"- {rel(prev_result_json)}")

    additional_inputs: list[str] = []
    if stage == VERIFY_RETRY_TARGET_STAGE:
        verify_path = stage_output_path(feature, VERIFY_STAGE)
        if verify_path.exists():
            additional_inputs.append(f"- {rel(verify_path)}")
        verify_result_json = stage_result_json_path(feature, VERIFY_STAGE)
        if verify_result_json.exists():
            additional_inputs.append(f"- {rel(verify_result_json)}")
        latest_verify_path = latest_verification_result_path(feature)
        if latest_verify_path.exists():
            additional_inputs.append(f"- {rel(latest_verify_path)}")

    project_contract = project_contract_prompt_text()

    instruction = f"""# Local Harness Prompt

## Harness Context
- feature_name: {feature}
- pipeline_mode: {PIPELINE_MODE}
- stage: {stage}
- preferred_model: {meta.get("preferred_model", "")}
- performance: {normalize_performance(state.get("performance"))}
- output_file: {rel(output)}
- result_json_file: {rel(result_json)}
- run_state: {rel(state_path(feature))}
- generated_at: {iso_now()}
- defaults_mode: {str(defaults_mode).lower()}
- feature_name_locked: {str(bool(state.get("feature_name_locked"))).lower()}

## Decision Policy
{decision_policy}

## Manual Provider Instructions
1. The local harness is executing this prompt with the preferred model when possible.
2. Make the requested file changes directly in the repository.
3. Write the human-readable stage output file exactly at `{rel(output)}`.
4. Also write the machine-readable stage result JSON exactly at `{rel(result_json)}`.
5. Do not run `git commit`, `git reset`, `git checkout`, `git rebase`, or `git push`. The local harness owns Git history.
6. This Git ownership rule overrides any preset text that appears to ask the model to create, amend, or push commits.
7. For commit stages, leave the working tree commit-ready and record commit intent in the stage output; the harness will create or amend the commit.
8. If `defaults_mode: true`, prefer recommended defaults over `NEEDS_USER` unless blocked by missing credentials, safety, destructive operations, or impossibility.
9. If the stage needs user input under the decision policy, write both outputs with `status: NEEDS_USER`.
10. If the stage fails, write both outputs with `status: FAIL` and a concrete blocking reason.
11. If `feature_name_locked: true`, keep the existing `feature_name` exactly as provided by the harness. Do not rename or invent a different feature slug.
12. End with a concise summary; the harness will inspect files, not your final message.

## Machine Result JSON Contract
The harness reads `{rel(result_json)}` first. Keep the `## 단계 결과` section in `{rel(output)}` for humans, but write this JSON file for the harness.

Required JSON keys:
- status: "PASS", "FAIL", "SKIPPED", or "NEEDS_USER"
- next_stage: next stage id or "done"
- human_gate_required: true or false
- blocking_reason: string, use "" when there is no blocker

Include any extra stage fields that the preset asks for, such as `risk_level`, `harness_commit_required`, `changed_files`, `verification_summary`, or `fix_inputs`.
For PASS or FAIL stages, also include `history_notes` with these arrays when known: `implemented`, `risks`, `future_improvements`, `decisions`, and `unresolved_items`. Use empty arrays for categories with nothing to record. Prefer Korean text for human-facing titles, descriptions, reasons, risks, and decisions when the project context is Korean.

{project_contract}

## Original User Request
{state.get("request", "")}

## Previous Stage Outputs
{chr(10).join(previous_outputs) if previous_outputs else "- none"}

## Additional Stage Inputs
{chr(10).join(additional_inputs) if additional_inputs else "- none"}

## Retry Context
{retry_context if retry_context else "- none"}

## Current Git Hints
- current_head: {safe_git_head()}
- changed_paths_excluding_runs: {json.dumps(filtered_changed_paths(state, stage), ensure_ascii=False)}
- latest_harness_verification: {rel(latest_verification_result_path(feature)) if latest_verification_result_path(feature).exists() else "none"}

---

"""
    full_prompt = instruction + preset_text
    path = prompt_path(state, stage)
    path.write_text(full_prompt, encoding="utf-8")
    state["current_stage"] = stage
    state["current_prompt"] = rel(path)
    state["status"] = "waiting_for_model"
    log_event(state, "prompt_generated", "generated prompt", stage=stage, path=rel(path))
    save_state(state)
    return path


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
    stdout_size = file_size(stdout_path)
    stderr_size = file_size(stderr_path)
    stdout_delta = stdout_size - last_stdout_size
    stderr_delta = stderr_size - last_stderr_size
    parts = [
        color_text(f"[{datetime.now().strftime('%H:%M:%S')}]", "dim"),
        color_text("[진행중]", "cyan", "bold"),
        f"{color_text(provider, 'magenta', 'bold')} 실행 중",
        f"stage={stage}",
        f"elapsed={format_duration(time.time() - started)}",
        f"stdout +{format_bytes(max(0, stdout_delta))}",
        f"stderr +{format_bytes(max(0, stderr_delta))}",
    ]
    print(" | ".join(parts), flush=True)
    return stdout_size, stderr_size


def suggested_retry_command(state: dict[str, Any], *, auto: bool = True) -> str:
    script = ".ai\\harness_fast.py" if state.get("pipeline_mode") == "fast" else ".ai\\harness.py"
    feature = str(state.get("feature_name") or "<feature>")
    parts = ["python", script, "retry", feature]
    if auto:
        parts.extend(["--auto", "--yes"])
    if state.get("defaults_mode"):
        parts.append("--defaults")
    performance = normalize_performance(state.get("performance"))
    if performance != DEFAULT_PERFORMANCE:
        parts.extend(["--performance", performance])
    return " ".join(parts)


def provider_log_hint(stdout_path: Path, stderr_path: Path, provider_log_path: Path) -> str:
    return (
        f"stdout={rel(stdout_path)} "
        f"stderr={rel(stderr_path)} "
        f"provider_log={rel(provider_log_path)}"
    )


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
    retry_command = suggested_retry_command(state)
    return (
        f"Provider {provider} {failure} while running stage {stage}. "
        f"Inspect logs: {provider_log_hint(stdout_path, stderr_path, provider_log_path)}. "
        f"Retry current stage: {retry_command}"
    )


def execute_current_prompt(state: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    feature = state["feature_name"]
    stage = state["current_stage"]
    prompt_rel = state.get("current_prompt")
    if not prompt_rel:
        raise HarnessError("No current prompt to execute.")
    prompt_file = ROOT / prompt_rel
    if not prompt_file.exists():
        raise HarnessError(f"Prompt file does not exist: {prompt_file}")

    provider = provider_for_stage(stage)
    prompt_text = prompt_file.read_text(encoding="utf-8")
    logs_dir = run_dir(feature) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    attempt = state.get("attempts", {}).get(stage, 1)
    stdout_path = logs_dir / f"{stage}_attempt{attempt}_{provider}.out.txt"
    stderr_path = logs_dir / f"{stage}_attempt{attempt}_{provider}.err.txt"
    meta_path = logs_dir / f"{stage}_attempt{attempt}_{provider}.json"
    cli_log_path = logs_dir / f"{stage}_attempt{attempt}_{provider}.cli.log"
    performance = normalize_performance(state.get("performance"))

    command, prompt_in_command = prepare_provider_command(
        provider,
        prompt_text,
        prompt_file=prompt_file.resolve(),
        log_file=cli_log_path.resolve(),
        performance=performance,
    )
    executable = resolve_executable(command)
    if not executable:
        raise HarnessError(f"Provider executable not found for {provider}: {command[0]}")

    before_head = safe_git_head()
    state["status"] = "model_running"
    log_event(
        state,
        "provider_started",
        f"running {provider}",
        stage=stage,
        provider=provider,
        performance=performance,
        timeout_seconds=timeout_seconds,
    )
    save_state(state)

    started = time.time()
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_fh, stderr_path.open(
        "w", encoding="utf-8", errors="replace"
    ) as stderr_fh:
        proc = subprocess.Popen(
            command,
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=stdout_fh,
            stderr=stderr_fh,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.stdin and not prompt_in_command:
            proc.stdin.write(prompt_text)
            proc.stdin.close()
        elif proc.stdin:
            proc.stdin.close()

        last_heartbeat = started
        last_stdout_size = 0
        last_stderr_size = 0
        while proc.poll() is None:
            now = time.time()
            if timeout_seconds > 0 and now - started > timeout_seconds:
                proc.kill()
                proc.wait()
                elapsed = round(time.time() - started, 2)
                reason = provider_failure_reason(
                    state,
                    stage=stage,
                    provider=provider,
                    failure=f"timed out after {timeout_seconds} seconds",
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                    provider_log_path=cli_log_path,
                )
                state["status"] = "blocked"
                state["blocked"] = {
                    "stage": stage,
                    "reason": reason,
                    "stdout": rel(stdout_path),
                    "stderr": rel(stderr_path),
                    "provider_log": rel(cli_log_path),
                    "retry_command": suggested_retry_command(state),
                }
                write_handoff(
                    state,
                    reason,
                    stage=stage,
                    next_action=f"로그를 확인한 뒤 현재 단계를 다시 실행하세요: {suggested_retry_command(state)}",
                )
                log_event(
                    state,
                    "provider_failed",
                    f"{provider} timed out",
                    stage=stage,
                    provider=provider,
                    stdout=rel(stdout_path),
                    stderr=rel(stderr_path),
                    provider_log=rel(cli_log_path),
                    retry_command=suggested_retry_command(state),
                    elapsed_seconds=elapsed,
                )
                save_state(state)
                return state
            if now - last_heartbeat >= DEFAULT_PROVIDER_HEARTBEAT_SECONDS:
                last_stdout_size, last_stderr_size = print_provider_heartbeat(
                    stage=stage,
                    provider=provider,
                    started=started,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                    last_stdout_size=last_stdout_size,
                    last_stderr_size=last_stderr_size,
                )
                last_heartbeat = now
            time.sleep(1)

    elapsed = round(time.time() - started, 2)
    after_head = safe_git_head()
    meta_path.write_text(
        json.dumps(
            {
                "stage": stage,
                "provider": provider,
                "performance": performance,
                "performance_settings": provider_performance_settings(provider, performance),
                "command": redact_prompt_command(command, prompt_text),
                "returncode": proc.returncode,
                "before_head": before_head,
                "after_head": after_head,
                "stdout": rel(stdout_path),
                "stderr": rel(stderr_path),
                "provider_log": rel(cli_log_path),
                "finished_at": iso_now(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if before_head and after_head and before_head != after_head:
        state["status"] = "blocked"
        state["blocked"] = {
            "stage": stage,
            "reason": "Provider changed Git HEAD. The harness owns commits; inspect history before continuing.",
        }
        write_handoff(
            state,
            str(state["blocked"]["reason"]),
            stage=stage,
            next_action="Git history를 점검한 뒤 수동으로 정리하고 resume 또는 retry 하세요.",
        )
        log_event(
            state,
            "blocked_provider_changed_head",
            "provider changed Git HEAD",
            stage=stage,
            before_head=before_head,
            after_head=after_head,
        )
        save_state(state)
        return state

    if proc.returncode != 0:
        reason = provider_failure_reason(
            state,
            stage=stage,
            provider=provider,
            failure=f"exited with code {proc.returncode}",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            provider_log_path=cli_log_path,
        )
        state["status"] = "blocked"
        state["blocked"] = {
            "stage": stage,
            "reason": reason,
            "stdout": rel(stdout_path),
            "stderr": rel(stderr_path),
            "provider_log": rel(cli_log_path),
            "retry_command": suggested_retry_command(state),
        }
        write_handoff(
            state,
            reason,
            stage=stage,
            next_action=f"로그를 확인한 뒤 현재 단계를 다시 실행하세요: {suggested_retry_command(state)}",
        )
        log_event(
            state,
            "provider_failed",
            f"{provider} exited with {proc.returncode}",
            stage=stage,
            provider=provider,
            returncode=proc.returncode,
            stdout=rel(stdout_path),
            stderr=rel(stderr_path),
            provider_log=rel(cli_log_path),
            retry_command=suggested_retry_command(state),
            elapsed_seconds=elapsed,
        )
        save_state(state)
        return state

    expected_output = stage_output_path(feature, stage)
    expected_result_json = stage_result_json_path(feature, stage)
    if (
        not expected_output.exists()
        and not expected_result_json.exists()
        and file_size(stdout_path) == 0
        and file_size(stderr_path) == 0
    ):
        reason = provider_failure_reason(
            state,
            stage=stage,
            provider=provider,
            failure="exited with code 0 but produced no stdout, no stderr, and no required outputs",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            provider_log_path=cli_log_path,
        )
        state["status"] = "blocked"
        state["blocked"] = {
            "stage": stage,
            "reason": reason,
            "next_stage": stage,
            "stdout": rel(stdout_path),
            "stderr": rel(stderr_path),
            "provider_log": rel(cli_log_path),
            "retry_command": suggested_retry_command(state),
        }
        write_handoff(
            state,
            reason,
            stage=stage,
            next_action=f"provider 설정 또는 인증 상태를 고친 뒤 현재 단계를 다시 실행하세요: {suggested_retry_command(state)}",
        )
        log_event(
            state,
            "provider_no_output",
            f"{provider} exited without output",
            stage=stage,
            provider=provider,
            stdout=rel(stdout_path),
            stderr=rel(stderr_path),
            provider_log=rel(cli_log_path),
            retry_command=suggested_retry_command(state),
            elapsed_seconds=elapsed,
        )
        save_state(state)
        return state

    state["status"] = "model_completed"
    log_event(
        state,
        "provider_completed",
        f"{provider} completed",
        stage=stage,
        provider=provider,
        stdout=rel(stdout_path),
        stderr=rel(stderr_path),
        elapsed_seconds=elapsed,
    )
    save_state(state)
    return state


def display_cwd(path: Path) -> str:
    try:
        resolved = path.resolve()
        root = ROOT.resolve()
        if resolved == root or root in resolved.parents:
            return rel(resolved)
    except Exception:
        pass
    return str(path)


def run_harness_verification(state: dict[str, Any]) -> dict[str, Any]:
    feature = state["feature_name"]
    stage = state.get("current_stage", VERIFY_STAGE)
    attempt = int(state.get("attempts", {}).get(VERIFY_STAGE, 1))
    commands, required = configured_verification_commands(feature)
    out_dir = verification_dir(feature)
    out_dir.mkdir(parents=True, exist_ok=True)
    started_at = iso_now()
    result_path = out_dir / f"{VERIFY_STAGE}_attempt{attempt}_{now_stamp()}.json"
    latest_path = latest_verification_result_path(feature)

    summary: dict[str, Any] = {
        "feature_name": feature,
        "stage": stage,
        "attempt": attempt,
        "result_path": rel(result_path),
        "latest_path": rel(latest_path),
        "started_at": started_at,
        "finished_at": None,
        "required": required,
        "passed": True,
        "status": "PASS",
        "commands": [],
        "failed_commands": [],
    }

    if not commands:
        summary["passed"] = not required
        summary["status"] = "FAIL" if required else "SKIPPED"
        summary["failure_reason"] = (
            "No harness verification commands configured."
            if required
            else "Harness verification is not configured."
        )
        summary["finished_at"] = iso_now()
        result_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        shutil.copyfile(result_path, latest_path)
        state["last_harness_verification"] = rel(latest_path)
        log_event(
            state,
            "harness_verification_skipped" if not required else "harness_verification_failed",
            str(summary["failure_reason"]),
            stage=VERIFY_STAGE,
            result=rel(latest_path),
        )
        save_state(state)
        return summary | {"path": rel(latest_path)}

    log_event(
        state,
        "harness_verification_started",
        "running configured verification commands",
        stage=VERIFY_STAGE,
        count=len(commands),
    )

    for command_spec in commands:
        name = command_spec["name"]
        command = command_spec["command"]
        cwd = Path(command_spec["cwd"])
        timeout_seconds = int(command_spec["timeout_seconds"])
        stdout_path = out_dir / f"{VERIFY_STAGE}_attempt{attempt}_{name}.out.txt"
        stderr_path = out_dir / f"{VERIFY_STAGE}_attempt{attempt}_{name}.err.txt"
        entry: dict[str, Any] = {
            "name": name,
            "command": command,
            "cwd": display_cwd(cwd),
            "timeout_seconds": timeout_seconds,
            "returncode": None,
            "elapsed_seconds": None,
            "passed": False,
            "timed_out": False,
            "stdout": rel(stdout_path),
            "stderr": rel(stderr_path),
        }

        executable = resolve_executable(command)
        if not executable:
            entry["error"] = f"Executable not found: {command[0]}"
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text(entry["error"] + "\n", encoding="utf-8")
            summary["commands"].append(entry)
            summary["failed_commands"].append(name)
            log_event(
                state,
                "harness_verification_command_failed",
                entry["error"],
                stage=VERIFY_STAGE,
                command=name,
            )
            continue

        started = time.time()
        try:
            proc = subprocess.run(
                command,
                cwd=cwd,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                check=False,
            )
            elapsed = round(time.time() - started, 2)
            stdout_path.write_text(proc.stdout or "", encoding="utf-8")
            stderr_path.write_text(proc.stderr or "", encoding="utf-8")
            entry["returncode"] = proc.returncode
            entry["elapsed_seconds"] = elapsed
            entry["passed"] = proc.returncode == 0
        except subprocess.TimeoutExpired as exc:
            elapsed = round(time.time() - started, 2)
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            stdout_path.write_text(str(stdout), encoding="utf-8")
            stderr_path.write_text(
                str(stderr) + f"\nTimed out after {timeout_seconds} seconds.\n",
                encoding="utf-8",
            )
            entry["elapsed_seconds"] = elapsed
            entry["timed_out"] = True
            entry["error"] = f"Timed out after {timeout_seconds} seconds."

        summary["commands"].append(entry)
        if not entry["passed"]:
            summary["failed_commands"].append(name)
            log_event(
                state,
                "harness_verification_command_failed",
                "verification command failed",
                stage=VERIFY_STAGE,
                command=name,
                returncode=entry.get("returncode"),
                timed_out=entry.get("timed_out"),
                stderr=entry.get("stderr"),
            )

    summary["passed"] = not summary["failed_commands"]
    summary["status"] = "PASS" if summary["passed"] else "FAIL"
    summary["finished_at"] = iso_now()
    result_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.copyfile(result_path, latest_path)
    state["last_harness_verification"] = rel(latest_path)
    log_event(
        state,
        "harness_verification_completed",
        "harness verification completed",
        stage=VERIFY_STAGE,
        status=summary["status"],
        result=rel(latest_path),
        failed=",".join(summary["failed_commands"]),
    )
    save_state(state)
    return summary | {"path": rel(latest_path)}


def enforce_harness_verify_result(
    state: dict[str, Any],
    result: dict[str, Any],
    status: str,
    next_stage: str,
) -> tuple[str, str]:
    if state.get("current_stage") != VERIFY_STAGE or status != "PASS":
        return status, next_stage

    verification = run_harness_verification(state)
    result["harness_verification_status"] = verification["status"]
    result["harness_verification_path"] = verification["path"]
    if verification["passed"]:
        return status, next_stage

    result["status"] = "FAIL"
    result["next_stage"] = VERIFY_RETRY_TARGET_STAGE
    result["harness_commit_required"] = False
    result["blocking_reason"] = (
        "Harness verification failed. See "
        f"{verification['path']} for command results."
    )
    return "FAIL", VERIFY_RETRY_TARGET_STAGE


def auto_drive(
    state: dict[str, Any],
    yes: bool,
    timeout_seconds: int,
    max_steps: int,
    max_verify_fix_retries: int = DEFAULT_MAX_VERIFY_FIX_RETRIES,
) -> dict[str, Any]:
    steps = 0
    log_event(
        state,
        "auto_started",
        "automatic execution started",
        yes=yes,
        timeout_seconds=timeout_seconds,
        max_steps=max_steps,
        max_verify_fix_retries=max_verify_fix_retries,
    )
    while steps < max_steps:
        steps += 1
        status = state.get("status")
        log_event(state, "auto_step", "evaluating run state", step=steps, status=status)
        if status == "complete":
            log_event(state, "auto_complete", "automatic execution complete")
            return state
        if status == "blocked":
            blocked = state.get("blocked", {})
            reason = str(blocked.get("reason", ""))
            if yes and "Human gate approval required" in reason:
                log_event(state, "auto_approving_gate", "auto-approving human gate", reason=reason)
                state = approve_run(
                    state["feature_name"],
                    max_verify_fix_retries=max_verify_fix_retries,
                )
                continue
            log_event(state, "auto_blocked", "automatic execution blocked", reason=reason)
            return state
        if status in {"created"}:
            generate_prompt(state, state["current_stage"])
            continue
        if status in {"waiting_for_model", "model_completed"}:
            if status == "waiting_for_model":
                state = execute_current_prompt(state, timeout_seconds)
                if state.get("status") == "blocked":
                    return state
            state = resume_run(state["feature_name"], max_verify_fix_retries=max_verify_fix_retries)
            continue
        raise HarnessError(f"Cannot auto-drive run in status={status!r}")
    raise HarnessError(f"Reached max auto steps ({max_steps}) without completion.")


def safe_git_head() -> str:
    try:
        return git_head()
    except Exception:
        return ""


def filtered_changed_paths(state: dict[str, Any], stage: str) -> list[str]:
    baseline = set(state.get("baseline_dirty", []))
    feature = state["feature_name"]
    paths = []
    for path in git_changed_paths():
        if path in baseline:
            continue
        if path.startswith(".ai/runs/"):
            continue
        if DOCUMENT_STAGE and stage == DOCUMENT_STAGE:
            continue
        if stage == VERIFY_RETRY_TARGET_STAGE and path == f".ai/features/{feature}/{STAGE_OUTPUTS[VERIFY_STAGE]}":
            continue
        if path.startswith(".ai/docs/"):
            continue
        paths.append(path)
    return sorted(set(paths))


def commit_for_stage(state: dict[str, Any], stage: str, result: dict[str, Any]) -> None:
    if stage in NO_COMMIT_STAGES:
        log_event(state, "commit_skipped", "stage does not commit", stage=stage)
        return

    status = stage_status(result)
    if stage == VERIFY_STAGE and status != "PASS":
        log_event(
            state,
            "commit_skipped_failed_verify",
            f"{VERIFY_STAGE} failed; leaving changes uncommitted for {VERIFY_RETRY_TARGET_STAGE}",
            stage=stage,
        )
        return

    paths = filtered_changed_paths(state, stage)
    if not paths:
        raise HarnessError(f"No changed files to commit for {stage}.")

    feature = state["feature_name"]
    commits = state.setdefault("commits", {})
    message = f"[{feature}][{now_stamp()}][{stage}]"

    amend = False
    if stage == VERIFY_RETRY_TARGET_STAGE and commits.get(VERIFY_RETRY_TARGET_STAGE):
        head = git_head()
        if head != commits[VERIFY_RETRY_TARGET_STAGE]:
            raise HarnessError(
                f"Cannot amend {VERIFY_RETRY_TARGET_STAGE}: current HEAD is not the recorded "
                f"{VERIFY_RETRY_TARGET_STAGE} commit. "
                "Stop and inspect git history."
            )
        amend = True

    log_event(
        state,
        "commit_start",
        "creating stage commit" if not amend else "amending stage commit",
        stage=stage,
        amend=amend,
        paths=",".join(paths),
    )
    git_add(paths)
    sha = git_commit(message, amend=amend)
    commits[stage] = sha
    log_event(
        state,
        "commit_amended" if amend else "commit_created",
        "stage commit recorded",
        stage=stage,
        sha=sha,
        paths=",".join(paths),
    )
    save_state(state)


def create_run(
    request: str,
    feature: str | None,
    defaults_mode: bool = False,
    performance: Any | None = None,
) -> dict[str, Any]:
    warn_pending_pc_candidates_for_new_run()
    assert_no_unpushed_commits_for_new_run()
    assert_no_incomplete_runs_for_new_run()
    ensure_dirs()
    performance_name = normalize_performance(performance)
    feature_name_locked = feature is not None
    if feature is None:
        feature = slugify(request)
    if not validate_slug(feature):
        raise HarnessError("Feature name must use lowercase letters, numbers, and hyphens.")
    if state_path(feature).exists():
        raise HarnessError(f"Run already exists: {feature}")

    feature_dir(feature).mkdir(parents=True, exist_ok=True)
    state = {
        "feature_name": feature,
        "feature_name_locked": feature_name_locked,
        "request": request,
        "pipeline_mode": PIPELINE_MODE,
        "performance": performance_name,
        "defaults_mode": defaults_mode,
        "current_stage": START_STAGE,
        "status": "created",
        "created_at": iso_now(),
        "updated_at": iso_now(),
        "baseline_dirty": git_changed_paths(),
        "attempts": {},
        "commits": {},
        "approved_stages": [],
        "events": [],
    }
    save_state(state)
    log_event(
        state,
        "run_created",
        "created feature run",
        request=request,
        feature=feature,
        performance=performance_name,
        defaults_mode=defaults_mode,
    )
    generate_prompt(state, START_STAGE)
    return state


def apply_runtime_performance(state: dict[str, Any], performance: Any | None) -> dict[str, Any]:
    if performance is None:
        return state
    performance_name = normalize_performance(performance)
    previous = state.get("performance")
    state["performance"] = performance_name
    if previous != performance_name:
        log_event(
            state,
            "performance_updated",
            "performance profile updated",
            performance=performance_name,
            previous_performance=previous,
        )
    save_state(state)
    return state


def latest_provider_artifacts(
    feature: str,
    stage: str,
    state: dict[str, Any] | None = None,
) -> dict[str, str]:
    try:
        provider = provider_for_stage(stage)
    except Exception:
        provider = "unknown"
    attempt = 1
    if state:
        attempt = int(state.get("attempts", {}).get(stage, 1))
    logs_dir = run_dir(feature) / "logs"
    artifacts = {
        "provider": provider,
        "stdout": rel(logs_dir / f"{stage}_attempt{attempt}_{provider}.out.txt"),
        "stderr": rel(logs_dir / f"{stage}_attempt{attempt}_{provider}.err.txt"),
        "meta": rel(logs_dir / f"{stage}_attempt{attempt}_{provider}.json"),
        "provider_log": rel(logs_dir / f"{stage}_attempt{attempt}_{provider}.cli.log"),
    }
    return artifacts


def handoff_path(feature: str) -> Path:
    return run_dir(feature) / "handoff.md"


def safe_read_tail(path: Path, lines: int = 40, max_chars: int = 6000) -> str:
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    text = "\n".join(content[-lines:])
    if len(text) > max_chars:
        return text[-max_chars:]
    return text


def latest_verification_summary(feature: str) -> dict[str, Any] | None:
    path = latest_verification_result_path(feature)
    if not path.exists():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return parsed if isinstance(parsed, dict) else None


def recent_events(state: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    events = state.get("events", [])
    if not isinstance(events, list):
        return []
    return [event for event in events[-limit:] if isinstance(event, dict)]


def write_handoff(
    state: dict[str, Any],
    reason: str,
    *,
    stage: str | None = None,
    next_action: str | None = None,
    result: dict[str, Any] | None = None,
) -> Path:
    feature = state["feature_name"]
    stage = stage or str(state.get("current_stage") or "")
    path = handoff_path(feature)
    path.parent.mkdir(parents=True, exist_ok=True)

    expected_md = stage_output_path(feature, stage) if stage in STAGES else None
    expected_json = stage_result_json_path(feature, stage) if stage in STAGES else None
    artifacts = latest_provider_artifacts(feature, stage, state) if stage in STAGES else {}
    verification = latest_verification_summary(feature)

    lines = [
        "# 실패 인수인계",
        "",
        f"- feature: {feature}",
        f"- pipeline_mode: {state.get('pipeline_mode') or PIPELINE_MODE}",
        f"- stage: {stage or '-'}",
        f"- status: {state.get('status') or '-'}",
        f"- generated_at: {iso_now()}",
        f"- reason: {reason}",
    ]
    if next_action:
        lines.append(f"- next_action: {next_action}")
    if expected_md:
        lines.append(f"- expected_md: {rel(expected_md)}")
    if expected_json:
        lines.append(f"- expected_json: {rel(expected_json)}")
    if state.get("current_prompt"):
        lines.append(f"- current_prompt: {state['current_prompt']}")
    if state.get("last_harness_verification"):
        lines.append(f"- latest_harness_verification: {state['last_harness_verification']}")

    lines.extend(["", "## 확인할 로그"])
    if artifacts:
        lines.extend(
            [
                f"- provider: {artifacts.get('provider')}",
                f"- stdout: {artifacts.get('stdout')}",
                f"- stderr: {artifacts.get('stderr')}",
                f"- meta: {artifacts.get('meta')}",
                f"- provider_log: {artifacts.get('provider_log')}",
            ]
        )
    else:
        lines.append("- provider log: 없음")

    if result:
        lines.extend(["", "## 단계 결과"])
        lines.append("```json")
        lines.append(json.dumps(result, ensure_ascii=False, indent=2))
        lines.append("```")

    if verification:
        lines.extend(["", "## 최근 하네스 검증"])
        lines.append("```json")
        lines.append(
            json.dumps(
                {
                    "status": verification.get("status"),
                    "failed_commands": verification.get("failed_commands", []),
                    "latest_path": verification.get("latest_path"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        lines.append("```")

    events = recent_events(state)
    if events:
        lines.extend(["", "## 최근 이벤트"])
        for event in events:
            lines.append(
                f"- {event.get('at', '')} [{event.get('stage') or '-'}] "
                f"{event.get('event')}: {event.get('message', '')}"
            )

    if artifacts:
        stdout_tail = safe_read_tail(ROOT / artifacts["stdout"], lines=20)
        stderr_tail = safe_read_tail(ROOT / artifacts["stderr"], lines=20)
        provider_log_tail = safe_read_tail(ROOT / artifacts["provider_log"], lines=30)
        if stdout_tail:
            lines.extend(["", "## stdout 마지막 부분", "```text", stdout_tail, "```"])
        if stderr_tail:
            lines.extend(["", "## stderr 마지막 부분", "```text", stderr_tail, "```"])
        if provider_log_tail:
            lines.extend(["", "## provider log 마지막 부분", "```text", provider_log_tail, "```"])

    lines.extend(
        [
            "",
            "## 다음 모델에게",
            "- 위 reason을 먼저 해결한다.",
            "- 사람이 읽는 md 산출물과 하네스가 읽는 result.json을 둘 다 작성한다.",
            "- Git 커밋은 하지 않는다. 하네스가 커밋을 소유한다.",
        ]
    )

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    state["last_handoff"] = rel(path)
    return path


def missing_stage_output_message(
    feature: str,
    stage: str,
    output: Path,
    state: dict[str, Any] | None = None,
) -> str:
    artifacts = latest_provider_artifacts(feature, stage, state)
    provider = artifacts["provider"]
    harness_script = ".ai\\harness_fast.py" if state and state.get("pipeline_mode") == "fast" else ".ai\\harness.py"
    return "\n".join(
        [
            color_text("[실패] 필수 단계 산출물이 없습니다.", "red", "bold"),
            "",
            color_text("예상 파일:", "yellow", "bold"),
            f"  {rel(output)}",
            "",
            color_text("무슨 일이 있었나:", "cyan", "bold"),
            (
                f"  {provider} provider는 종료됐지만, 하네스가 요구한 stage output 파일을 "
                "현재 저장소 안에 만들지 않았습니다."
            ),
            "",
            color_text("가능한 원인:", "yellow", "bold"),
            "  1. provider가 다른 workspace를 작업 대상으로 잡았습니다.",
            "  2. 모델이 필수 출력 경로 지시를 따르지 않았습니다.",
            "  3. 파일 생성 권한 또는 경로 문제가 있었습니다.",
            "",
            color_text("확인할 로그:", "cyan", "bold"),
            f"  stdout: {artifacts['stdout']}",
            f"  stderr: {artifacts['stderr']}",
            f"  meta:   {artifacts['meta']}",
            f"  provider_log: {artifacts['provider_log']}",
            "",
            color_text("다음 조치:", "green", "bold"),
            f"  python {harness_script} status {feature}",
            f"  python {harness_script} log {feature} --lines 80",
            "  필요하면 cleanup 후 같은 요청으로 다시 실행하세요.",
        ]
    )


def load_stage_result(
    feature: str,
    stage: str,
    state: dict[str, Any] | None = None,
) -> tuple[Path, str, dict[str, Any]]:
    output = stage_output_path(feature, stage)
    if not output.exists():
        if state is not None:
            state["status"] = "blocked"
            state["blocked"] = {
                "stage": stage,
                "reason": f"Missing stage output: {rel(output)}",
                "next_stage": stage,
            }
            write_handoff(
                state,
                f"Missing stage output: {rel(output)}",
                stage=stage,
                next_action="retry 명령으로 현재 단계를 다시 실행하거나 provider 로그를 확인하세요.",
            )
            save_state(state)
        raise HarnessError(missing_stage_output_message(feature, stage, output, state))
    text = output.read_text(encoding="utf-8")
    result_json = stage_result_json_path(feature, stage)
    if result_json.exists():
        try:
            result = read_stage_result_json(result_json)
        except HarnessError as exc:
            if state is not None:
                state["status"] = "blocked"
                state["blocked"] = {
                    "stage": stage,
                    "reason": str(exc),
                    "next_stage": stage,
                }
                write_handoff(
                    state,
                    str(exc),
                    stage=stage,
                    next_action="result.json 형식을 고치거나 retry 명령으로 현재 단계를 다시 실행하세요.",
                )
                save_state(state)
            raise
    else:
        result = find_stage_result(text)
    if not result:
        if state is not None:
            state["status"] = "blocked"
            state["blocked"] = {
                "stage": stage,
                "reason": (
                    f"Missing stage result. Expected {rel(result_json)} or "
                    f"'## 단계 결과' block in {rel(output)}"
                ),
                "next_stage": stage,
            }
            write_handoff(
                state,
                str(state["blocked"]["reason"]),
                stage=stage,
                next_action="result.json을 보강하거나 retry 명령으로 현재 단계를 다시 실행하세요.",
            )
            save_state(state)
        raise HarnessError(
            f"Missing stage result. Expected {rel(result_json)} or '## 단계 결과' block in {rel(output)}"
        )
    return output, text, result


def expected_docx_path(feature: str) -> Path:
    return DOCS_DIR / f"{feature}_명세서.docx"


def validate_docx_file(path: Path) -> str | None:
    if not path.exists():
        return f"Missing document artifact: {rel(path)}"
    if not path.is_file():
        return f"Document artifact is not a file: {rel(path)}"

    try:
        with path.open("rb") as fh:
            signature = fh.read(2)
    except OSError as exc:
        return f"Cannot read document artifact {rel(path)}: {exc}"

    if signature != b"PK":
        return (
            f"Invalid .docx artifact {rel(path)}: expected ZIP/OOXML signature "
            f"'PK', got {signature!r}. Do not save Markdown/plain text with a .docx extension."
        )

    if not zipfile.is_zipfile(path):
        return f"Invalid .docx artifact {rel(path)}: file is not a valid ZIP archive."

    required_entries = {"[Content_Types].xml", "word/document.xml"}
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            missing = sorted(required_entries - names)
            if missing:
                return (
                    f"Invalid .docx artifact {rel(path)}: missing OOXML entries "
                    f"{', '.join(missing)}."
                )
            if not zf.read("word/document.xml").strip():
                return f"Invalid .docx artifact {rel(path)}: word/document.xml is empty."
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        return f"Invalid .docx artifact {rel(path)}: {exc}"

    return None


def validate_document_stage_artifacts(feature: str) -> str | None:
    return validate_docx_file(expected_docx_path(feature))


def block_state(state: dict[str, Any], stage: str, reason: str, next_stage: str | None = None) -> None:
    state["status"] = "blocked"
    state["blocked"] = {"stage": stage, "reason": reason, "next_stage": next_stage}
    write_handoff(
        state,
        reason,
        stage=stage,
        next_action="원인을 확인한 뒤 approve, retry, resume 중 맞는 명령으로 이어가세요.",
    )
    log_event(state, "blocked", reason, stage=stage, next_stage=next_stage)
    save_state(state)


def resume_run(feature: str, max_verify_fix_retries: int = DEFAULT_MAX_VERIFY_FIX_RETRIES) -> dict[str, Any]:
    state = load_state(feature)
    if max_verify_fix_retries < 0:
        raise HarnessError("max_verify_fix_retries must be zero or greater.")
    stage = state["current_stage"]
    if stage == PC_REVIEW_STAGE:
        return finish_pc_candidate_extraction(state)
    if stage not in STAGES:
        raise HarnessError(f"Unknown current stage: {stage}")

    output, text, result = load_stage_result(state["feature_name"], stage, state)
    if stage == START_STAGE:
        state = maybe_rename_feature(state)
        feature = state["feature_name"]
        output, text, result = load_stage_result(feature, stage, state)

    status = stage_status(result)
    next_stage = str(result.get("next_stage") or stage_default_next(stage) or "")
    log_event(state, "stage_result", "parsed stage result", stage=stage, status=status, next_stage=next_stage)
    if stage == VERIFY_STAGE and status == "FAIL":
        next_stage = VERIFY_RETRY_TARGET_STAGE
    if status not in {"PASS", "FAIL", "SKIPPED", "NEEDS_USER"}:
        raise HarnessError(f"Invalid or missing status in {rel(output)}: {status!r}")

    violations = write_policy_violations(state, stage)
    if violations:
        block_state(
            state,
            stage,
            "Write policy violation: " + "; ".join(violations),
            stage,
        )
        return state

    if status == "NEEDS_USER":
        block_state(state, stage, result.get("blocking_reason") or "Stage requested user input.", stage)
        return state

    if status == "FAIL" and stage != VERIFY_STAGE:
        block_state(state, stage, result.get("blocking_reason") or "Stage failed.", next_stage)
        return state

    if DOCUMENT_STAGE and status == "PASS" and stage == DOCUMENT_STAGE:
        artifact_error = validate_document_stage_artifacts(state["feature_name"])
        if artifact_error:
            block_state(state, stage, artifact_error, stage)
            return state

    human_gate = boolish(result.get("human_gate_required"))
    approved = stage in state.get("approved_stages", [])
    if status == "PASS" and human_gate and not approved:
        block_state(state, stage, "Human gate approval required.", next_stage)
        return state

    if stage == VERIFY_STAGE:
        status, next_stage = enforce_harness_verify_result(state, result, status, next_stage)

    if stage == VERIFY_STAGE and status == "FAIL":
        retries_used = int(state.get("verify_fix_retries_used", 0))
        if retries_used >= max_verify_fix_retries:
            block_state(
                state,
                stage,
                (
                    "Verify/Fix retry limit reached "
                    f"({retries_used}/{max_verify_fix_retries}). "
                    "Resume with a higher --max-verify-fix-retries value if this feature needs more iterations."
                ),
                stage,
            )
            return state
        state["verify_fix_retries_used"] = retries_used + 1
        log_event(
            state,
            "verify_fix_retry_recorded",
            "recorded verify/fix retry",
            stage=stage,
            retries_used=state["verify_fix_retries_used"],
            max_verify_fix_retries=max_verify_fix_retries,
        )
        save_state(state)

    commit_for_stage(state, stage, result)

    if stage == VERIFY_STAGE and status == "FAIL":
        write_handoff(
            state,
            result.get("blocking_reason") or "Verify stage failed.",
            stage=stage,
            next_action=f"{VERIFY_RETRY_TARGET_STAGE} 단계가 이 실패를 수정해야 합니다.",
            result=result,
        )
        state["current_stage"] = VERIFY_RETRY_TARGET_STAGE
        state["status"] = "waiting_for_model"
        log_event(
            state,
            "verify_failed_returning_to_development",
            f"returning to {VERIFY_RETRY_TARGET_STAGE} after failed verify",
            stage=stage,
        )
        generate_prompt(state, VERIFY_RETRY_TARGET_STAGE)
        return state

    if (DOCUMENT_STAGE and stage == DOCUMENT_STAGE) or next_stage == "done":
        if should_extract_pc_candidates(state):
            state["status"] = "pc_candidates_pending"
            state["current_stage"] = PC_REVIEW_STAGE
            state["pc_candidate_source_stage"] = stage
            log_event(
                state,
                "pc_candidate_extraction_queued",
                "queued project contract candidate extraction",
                stage=stage,
            )
            save_state(state)
            return finish_pc_candidate_extraction(state)
        return complete_run(state, stage)

    if next_stage not in STAGES:
        raise HarnessError(f"Invalid next_stage: {next_stage}")

    state["current_stage"] = next_stage
    state["status"] = "waiting_for_model"
    state.pop("blocked", None)
    log_event(state, "stage_advanced", "advanced to next stage", stage=stage, next_stage=next_stage)
    save_state(state)
    generate_prompt(state, next_stage)
    return state


def approve_run(feature: str, max_verify_fix_retries: int = DEFAULT_MAX_VERIFY_FIX_RETRIES) -> dict[str, Any]:
    state = load_state(feature)
    blocked = state.get("blocked")
    if not blocked:
        raise HarnessError("Run is not blocked.")
    stage = blocked.get("stage")
    next_stage = blocked.get("next_stage")
    if not stage:
        raise HarnessError("Blocked state has no stage.")
    state.setdefault("approved_stages", []).append(stage)
    log_event(state, "approved", "human gate approved", stage=stage)
    state.pop("blocked", None)
    save_state(state)

    if next_stage and next_stage in STAGES and next_stage != stage:
        state["current_stage"] = next_stage
        state["status"] = "waiting_for_model"
        save_state(state)
        generate_prompt(state, next_stage)
        return state

    return resume_run(state["feature_name"], max_verify_fix_retries=max_verify_fix_retries)


def build_retry_context(state: dict[str, Any], stage: str) -> str:
    feature = state["feature_name"]
    blocked = state.get("blocked") if isinstance(state.get("blocked"), dict) else {}
    reason = str(blocked.get("reason") or "Manual retry requested.")
    handoff = write_handoff(
        state,
        reason,
        stage=stage,
        next_action="retry가 현재 단계를 보강 프롬프트로 다시 실행합니다.",
    )
    artifacts = latest_provider_artifacts(feature, stage, state)
    output = stage_output_path(feature, stage)
    result_json = stage_result_json_path(feature, stage)
    parts = [
        "This is a retry of the current stage. Fix the previous failure and overwrite both required outputs.",
        "",
        f"- retry_stage: {stage}",
        f"- failure_reason: {reason}",
        f"- handoff_file: {rel(handoff)}",
        f"- required_md_output: {rel(output)}",
        f"- required_result_json: {rel(result_json)}",
        f"- provider_stdout: {artifacts['stdout']}",
        f"- provider_stderr: {artifacts['stderr']}",
        f"- provider_meta: {artifacts['meta']}",
        "",
        "Retry checklist:",
        "1. Work in the repository root shown by the harness context.",
        "2. Do not reuse stale stage results. Overwrite the md output and result.json for this stage.",
        "3. If the prior failure was a missing output, create the exact paths above.",
        "4. If verification failed, read the latest verification JSON and fix the failed commands.",
        "5. Do not commit. The harness owns Git history.",
    ]
    verification = latest_verification_result_path(feature)
    if verification.exists():
        parts.append(f"- latest_harness_verification: {rel(verification)}")
    handoff_tail = safe_read_tail(handoff, lines=80)
    if handoff_tail:
        parts.extend(["", "Latest handoff.md:", "```md", handoff_tail, "```"])
    return "\n".join(parts)


def copy_same_prompt_for_retry(state: dict[str, Any], stage: str) -> Path:
    current_prompt = state.get("current_prompt")
    if not current_prompt:
        return generate_prompt(state, stage)
    source = ROOT / current_prompt
    if not source.exists():
        return generate_prompt(state, stage)

    state.setdefault("stage_file_snapshots", {})[stage] = file_policy_snapshot(state["feature_name"])
    path = prompt_path(state, stage)
    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    state["current_stage"] = stage
    state["current_prompt"] = rel(path)
    state["status"] = "waiting_for_model"
    state.pop("blocked", None)
    log_event(state, "retry_prompt_generated", "copied same prompt for retry", stage=stage, path=rel(path))
    save_state(state)
    return path


def archive_stage_outputs_for_retry(state: dict[str, Any], stage: str) -> None:
    feature = state["feature_name"]
    archive_dir = run_dir(feature) / "retry_archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    attempt = int(state.get("attempts", {}).get(stage, 0) or 0)
    stamp = now_stamp()
    archived: list[str] = []
    for path in [stage_output_path(feature, stage), stage_result_json_path(feature, stage)]:
        if not path.exists():
            continue
        target = archive_dir / f"{stage}_attempt{attempt}_{stamp}_{path.name}"
        shutil.copyfile(path, target)
        path.unlink()
        archived.append(rel(target))
    if archived:
        state.setdefault("retry_archives", []).append(
            {"stage": stage, "at": iso_now(), "files": archived}
        )
        log_event(
            state,
            "retry_outputs_archived",
            "archived stale stage outputs before retry",
            stage=stage,
            files=",".join(archived),
        )


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
    state = load_state(feature)
    if defaults:
        state["defaults_mode"] = True
        log_event(state, "defaults_mode_enabled", "defaults mode enabled before retry")
    blocked = state.get("blocked") if isinstance(state.get("blocked"), dict) else {}
    stage = str(blocked.get("stage") or state.get("current_stage") or "")
    if stage not in STAGES:
        raise HarnessError(f"Cannot retry stage: {stage!r}")
    if state.get("status") == "complete" or stage == "done":
        raise HarnessError("Run is already complete; there is no current stage to retry.")

    state["current_stage"] = stage
    if same:
        archive_stage_outputs_for_retry(state, stage)
        copy_same_prompt_for_retry(state, stage)
        state = load_state(feature)
    else:
        retry_context = build_retry_context(state, stage)
        archive_stage_outputs_for_retry(state, stage)
        state.pop("blocked", None)
        generate_prompt(state, stage, retry_context=retry_context)
        state = load_state(feature)
        log_event(state, "retry_prompt_generated", "generated enriched retry prompt", stage=stage)
        save_state(state)

    if prompt_only:
        return state

    state = execute_current_prompt(state, timeout_seconds)
    if state.get("status") == "blocked":
        return state
    state = resume_run(state["feature_name"], max_verify_fix_retries=max_verify_fix_retries)
    if auto and state.get("status") not in {"complete", "blocked"}:
        state = auto_drive(
            state,
            yes=yes,
            timeout_seconds=timeout_seconds,
            max_steps=max_steps,
            max_verify_fix_retries=max_verify_fix_retries,
        )
    return state


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
    for provider in ["codex", "claude", "agy"]:
        command = provider_command(provider)
        executable = resolve_executable(command)
        print(f"{provider}: {'ok' if executable else 'missing'}")
        print(f"  command: {' '.join(command)}")
        if executable:
            print(f"  executable: {executable}")


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
    return ".ai\\harness_fast.py" if state.get("pipeline_mode") == "fast" else ".ai\\harness.py"


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
            lines.append(f"provider: {provider_for_stage(stage)}")
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
    ensure_dirs()
    print(f"runs_dir: {RUNS_DIR}")
    print(f"features_dir: {FEATURES_DIR}")
    print("changed_paths:")
    for path in git_changed_paths():
        print(f"  {path}")
    if deep:
        print("deep provider smoke tests:")
        for provider in ["codex", "claude", "agy"]:
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

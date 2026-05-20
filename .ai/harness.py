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
PRESETS_DIR = ROOT / "presets" / "full"
PIPELINE_MODE = "full"

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
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "venv",
}

SNAPSHOT_GENERATED_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def is_snapshot_generated_path(path: str) -> bool:
    path = norm_repo_path(path)
    parts = [part for part in path.split("/") if part]
    if any(part in SNAPSHOT_GENERATED_DIR_NAMES for part in parts):
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


def prepare_provider_command(
    provider: str,
    prompt_text: str | None = None,
    prompt_file: Path | None = None,
    log_file: Path | None = None,
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
    return command, uses_prompt_placeholder


def provider_command(provider: str) -> list[str]:
    command, _ = prepare_provider_command(provider)
    return command


def redact_prompt_command(command: list[str], prompt_text: str | None) -> list[str]:
    if not prompt_text:
        return command
    return ["<prompt>" if part == prompt_text else part.replace(prompt_text, "<prompt>") for part in command]


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
    parts = path.split("/")
    name = parts[-1]
    return (
        "tests" in parts
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
        or name.endswith("_test.py")
    )


def is_production_code_path(path: str) -> bool:
    path = norm_repo_path(path)
    if not (path.startswith("backend/") or path.startswith("frontend/")):
        return False
    return not is_test_path(path)


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
        f"stage={state.get('current_stage')} prompt={state.get('current_prompt')}"
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

    instruction = f"""# Local Harness Prompt

## Harness Context
- feature_name: {feature}
- pipeline_mode: {PIPELINE_MODE}
- stage: {stage}
- preferred_model: {meta.get("preferred_model", "")}
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

    command, prompt_in_command = prepare_provider_command(
        provider,
        prompt_text,
        prompt_file=prompt_file.resolve(),
        log_file=cli_log_path.resolve(),
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
                state["status"] = "blocked"
                state["blocked"] = {
                    "stage": stage,
                    "reason": (
                        f"Provider {provider} timed out after {timeout_seconds} seconds. "
                        f"See {rel(stderr_path)}"
                    ),
                }
                write_handoff(
                    state,
                    str(state["blocked"]["reason"]),
                    stage=stage,
                    next_action="provider timeout 원인을 확인하고 retry로 현재 단계를 다시 실행하세요.",
                )
                log_event(
                    state,
                    "provider_failed",
                    f"{provider} timed out",
                    stage=stage,
                    provider=provider,
                    stderr=rel(stderr_path),
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
        state["status"] = "blocked"
        state["blocked"] = {
            "stage": stage,
            "reason": f"Provider {provider} exited with code {proc.returncode}. See {rel(stderr_path)}",
        }
        write_handoff(
            state,
            str(state["blocked"]["reason"]),
            stage=stage,
            next_action="stderr 로그를 확인하고 retry로 현재 단계를 다시 실행하세요.",
        )
        log_event(
            state,
            "provider_failed",
            f"{provider} exited with {proc.returncode}",
            stage=stage,
            provider=provider,
            returncode=proc.returncode,
            stderr=rel(stderr_path),
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
        state["status"] = "blocked"
        state["blocked"] = {
            "stage": stage,
            "reason": (
                f"Provider {provider} exited with code 0 but produced no stdout, no stderr, "
                f"and no required outputs. This usually means the provider CLI did not execute the prompt. "
                f"See {rel(cli_log_path)}."
            ),
            "next_stage": stage,
        }
        write_handoff(
            state,
            str(state["blocked"]["reason"]),
            stage=stage,
            next_action="provider_log를 확인하고 provider 설정 또는 인증 상태를 고친 뒤 retry 하세요.",
        )
        log_event(
            state,
            "provider_no_output",
            f"{provider} exited without output",
            stage=stage,
            provider=provider,
            provider_log=rel(cli_log_path),
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


def create_run(request: str, feature: str | None, defaults_mode: bool = False) -> dict[str, Any]:
    ensure_dirs()
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
        defaults_mode=defaults_mode,
    )
    generate_prompt(state, START_STAGE)
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
        state["status"] = "complete"
        state["current_stage"] = "done"
        log_event(state, "complete", "run complete", stage=stage)
        save_state(state)
        return state

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
        lines.append(f"- 현재 막힌 이유: {reason or 'blocked 상세 정보 없음'}")
        lines.append(f"- 실패 인수인계 파일을 확인하세요: {state.get('last_handoff') or rel(handoff_path(feature))}")
        lines.append(f"- 재시도: python {script} retry {feature}")
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
    add_retry_arg(run)

    resume = sub.add_parser("resume", help="Resume the current stage after the model wrote its output.")
    resume.add_argument("feature", help="Feature slug.")
    resume.add_argument("--auto", action="store_true", help="Continue executing stages with local providers.")
    resume.add_argument("--yes", action="store_true", help="Auto-approve human gates while running with --auto.")
    resume.add_argument("--timeout", type=int, default=3600, help="Provider timeout in seconds.")
    resume.add_argument("--max-steps", type=int, default=30, help="Maximum automatic stage transitions.")
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
            state = create_run(args.request, args.feature, defaults_mode=args.defaults)
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
            state = create_run(args.request, args.feature, defaults_mode=args.defaults)
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
            if args.auto:
                state = load_state(args.feature)
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
            state = load_state(args.feature)
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

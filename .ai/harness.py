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
        "--print",
        "--print-timeout",
        "30m",
        "--dangerously-skip-permissions",
    ],
}


class HarnessError(RuntimeError):
    pass


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


def provider_command(provider: str) -> list[str]:
    config = load_config()
    configured = config.get("providers", {}).get(provider, {}).get("command")
    command = configured or DEFAULT_PROVIDER_COMMANDS.get(provider)
    if not command:
        raise HarnessError(f"No provider command configured for {provider}")
    return [str(part).replace("{cwd}", str(ROOT)) for part in command]


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
        print(line, flush=True)


def find_stage_result(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "## 단계 결과":
            start = i + 1
    if start is None:
        return {}

    result: dict[str, Any] = {}
    current_key: str | None = None
    for line in lines[start:]:
        if line.startswith("## "):
            break
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
    spec_path = stage_output_path(old, START_STAGE)
    if not spec_path.exists():
        return state
    feature_name = extract_feature_name(spec_path.read_text(encoding="utf-8"))
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


def prompt_path(state: dict[str, Any], stage: str) -> Path:
    attempts = state.setdefault("attempts", {})
    attempt = int(attempts.get(stage, 0)) + 1
    attempts[stage] = attempt
    prompt_dir = run_dir(state["feature_name"]) / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    return prompt_dir / f"{stage}_attempt{attempt}.md"


def generate_prompt(state: dict[str, Any], stage: str) -> Path:
    feature = state["feature_name"]
    meta, body, raw = read_preset(stage)
    preset_text = raw.replace("[기능명]", feature)
    output = stage_output_path(feature, stage)
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

    additional_inputs: list[str] = []
    if stage == VERIFY_RETRY_TARGET_STAGE:
        verify_path = stage_output_path(feature, VERIFY_STAGE)
        if verify_path.exists():
            additional_inputs.append(f"- {rel(verify_path)}")
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
- run_state: {rel(state_path(feature))}
- generated_at: {iso_now()}
- defaults_mode: {str(defaults_mode).lower()}

## Decision Policy
{decision_policy}

## Manual Provider Instructions
1. The local harness is executing this prompt with the preferred model when possible.
2. Make the requested file changes directly in the repository.
3. Write the required stage output file exactly at `{rel(output)}`.
4. Do not run `git commit`, `git reset`, `git checkout`, `git rebase`, or `git push`. The local harness owns Git history.
5. This Git ownership rule overrides any preset text that appears to ask the model to create, amend, or push commits.
6. For commit stages, leave the working tree commit-ready and record commit intent in the stage output; the harness will create or amend the commit.
7. If `defaults_mode: true`, prefer recommended defaults over `NEEDS_USER` unless blocked by missing credentials, safety, destructive operations, or impossibility.
8. If the stage needs user input under the decision policy, write the stage output with `status: NEEDS_USER`.
9. If the stage fails, write the stage output with `status: FAIL` and a concrete blocking reason.
10. End with a concise summary; the harness will inspect files, not your final message.

## Original User Request
{state.get("request", "")}

## Previous Stage Outputs
{chr(10).join(previous_outputs) if previous_outputs else "- none"}

## Additional Stage Inputs
{chr(10).join(additional_inputs) if additional_inputs else "- none"}

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
    command = provider_command(provider)
    executable = resolve_executable(command)
    if not executable:
        raise HarnessError(f"Provider executable not found for {provider}: {command[0]}")

    logs_dir = run_dir(feature) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    attempt = state.get("attempts", {}).get(stage, 1)
    stdout_path = logs_dir / f"{stage}_attempt{attempt}_{provider}.out.txt"
    stderr_path = logs_dir / f"{stage}_attempt{attempt}_{provider}.err.txt"
    meta_path = logs_dir / f"{stage}_attempt{attempt}_{provider}.json"

    prompt_text = prompt_file.read_text(encoding="utf-8")
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
    proc = subprocess.run(
        command,
        cwd=ROOT,
        input=prompt_text,
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
    after_head = safe_git_head()
    meta_path.write_text(
        json.dumps(
            {
                "stage": stage,
                "provider": provider,
                "command": command,
                "returncode": proc.returncode,
                "before_head": before_head,
                "after_head": after_head,
                "stdout": rel(stdout_path),
                "stderr": rel(stderr_path),
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
    if feature is None:
        feature = slugify(request)
    if not validate_slug(feature):
        raise HarnessError("Feature name must use lowercase letters, numbers, and hyphens.")
    if state_path(feature).exists():
        raise HarnessError(f"Run already exists: {feature}")

    feature_dir(feature).mkdir(parents=True, exist_ok=True)
    state = {
        "feature_name": feature,
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


def load_stage_result(feature: str, stage: str) -> tuple[Path, str, dict[str, Any]]:
    output = stage_output_path(feature, stage)
    if not output.exists():
        raise HarnessError(
            f"Missing stage output: {rel(output)}\n"
            f"Run the prompt first, then resume. Prompt: {state_path(feature).parent / 'prompts'}"
        )
    text = output.read_text(encoding="utf-8")
    result = find_stage_result(text)
    if not result:
        raise HarnessError(f"Missing '## 단계 결과' block in {rel(output)}")
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
    log_event(state, "blocked", reason, stage=stage, next_stage=next_stage)
    save_state(state)


def resume_run(feature: str, max_verify_fix_retries: int = DEFAULT_MAX_VERIFY_FIX_RETRIES) -> dict[str, Any]:
    state = load_state(feature)
    if max_verify_fix_retries < 0:
        raise HarnessError("max_verify_fix_retries must be zero or greater.")
    stage = state["current_stage"]
    if stage not in STAGES:
        raise HarnessError(f"Unknown current stage: {stage}")

    output, text, result = load_stage_result(state["feature_name"], stage)
    if stage == START_STAGE:
        state = maybe_rename_feature(state)
        feature = state["feature_name"]
        output, text, result = load_stage_result(feature, stage)

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


def print_status(feature: str | None) -> None:
    if feature:
        state = load_state(feature)
        print(run_status_line(state))
        if state.get("blocked"):
            print("blocked:", json.dumps(state["blocked"], ensure_ascii=False))
        print("commits:", json.dumps(state.get("commits", {}), ensure_ascii=False))
        log_path = run_log_path(feature)
        if log_path.exists():
            print(f"log: {log_path}")
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


def doctor() -> None:
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

    cleanup = sub.add_parser("cleanup", help="Remove a local run directory and optionally its feature dir.")
    cleanup.add_argument("feature", help="Feature slug.")
    cleanup.add_argument(
        "--keep-feature",
        action="store_true",
        help="Only remove .ai/runs/<feature>, preserving .ai/features/<feature>.",
    )

    sub.add_parser("doctor", help="Check local harness prerequisites.")
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
        if args.command == "cleanup":
            cleanup_run(args.feature, keep_feature=args.keep_feature)
            return 0
        if args.command == "doctor":
            doctor()
            return 0
        parser.error("Unknown command")
        return 2
    except HarnessError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
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

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .text import norm_repo_path


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


def is_harness_internal_path(path: str, feature: str) -> bool:
    path = norm_repo_path(path)
    if not path.startswith(".ai/runs/"):
        return False
    return path != f".ai/runs/{feature}/document_build.py"


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


def git_ignored_paths(ctx: dict[str, Any], paths: list[str]) -> set[str]:
    if not paths:
        return set()
    root = ctx["ROOT"]
    try:
        proc = subprocess.run(
            ["git", "-c", f"safe.directory={root.as_posix()}", "check-ignore", "--stdin"],
            cwd=root,
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


def snapshot_excluded_paths(ctx: dict[str, Any], paths: list[str]) -> set[str]:
    generated = {path for path in paths if is_snapshot_generated_path(path)}
    remaining = [path for path in paths if path not in generated]
    return generated | git_ignored_paths(ctx, remaining)


def repo_child_path(ctx: dict[str, Any], parent: Path, name: str) -> str:
    root = ctx["ROOT"]
    if parent.resolve() == root.resolve():
        return name
    return f"{ctx['rel'](parent)}/{name}"


def file_policy_snapshot(ctx: dict[str, Any], feature: str) -> dict[str, str]:
    root = ctx["ROOT"]
    snapshot: dict[str, str] = {}
    candidates: list[tuple[Path, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        parent = Path(dirpath)
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not is_snapshot_generated_path(repo_child_path(ctx, parent, dirname))
        ]
        for filename in filenames:
            rel_path = repo_child_path(ctx, parent, filename)
            if is_snapshot_generated_path(rel_path):
                continue
            if is_harness_internal_path(rel_path, feature):
                continue
            candidates.append((parent / filename, rel_path))

    excluded = snapshot_excluded_paths(ctx, [rel_path for _, rel_path in candidates])
    for path, rel_path in candidates:
        if rel_path in excluded:
            continue
        try:
            snapshot[rel_path] = ctx["file_hash"](path)
        except OSError:
            continue
    return snapshot


def changed_since_snapshot(ctx: dict[str, Any], before: dict[str, str], feature: str) -> list[str]:
    after = file_policy_snapshot(ctx, feature)
    paths = set(before) | set(after)
    excluded = snapshot_excluded_paths(ctx, list(paths))
    return sorted(path for path in paths if path not in excluded and before.get(path) != after.get(path))


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


def write_policy_violations(ctx: dict[str, Any], state: dict[str, Any], stage: str) -> list[str]:
    feature = state["feature_name"]
    meta, _, _ = ctx["read_preset"](stage)
    snapshots = state.get("stage_file_snapshots", {})
    before_snapshot = snapshots.get(stage)
    if not isinstance(before_snapshot, dict):
        changed_paths = ctx["filtered_changed_paths"](state, stage)
        before_snapshot = {}
    else:
        changed_paths = changed_since_snapshot(ctx, before_snapshot, feature)

    allowed = [expand_policy_item(item, feature) for item in meta.get("allowed_writes", [])]
    if stage in ctx["STAGES"]:
        allowed.append(ctx["rel"](ctx["stage_output_path"](feature, stage)))
        allowed.append(ctx["rel"](ctx["stage_result_json_path"](feature, stage)))
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


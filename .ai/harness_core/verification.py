from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .text import boolish, slugify


def configured_verification_commands(ctx: dict[str, Any], feature: str) -> tuple[list[dict[str, Any]], bool]:
    config = ctx["load_config"]()
    verification = config.get("verification")
    if verification is None:
        return [], False
    if verification is False:
        return [], False
    if not isinstance(verification, dict):
        raise ctx["HarnessError"]("verification config must be an object.")
    if verification.get("enabled", True) is False:
        return [], False

    required = boolish(verification.get("required", True))
    timeout_default = int(
        verification.get("timeout_seconds", ctx["DEFAULT_VERIFY_COMMAND_TIMEOUT_SECONDS"])
    )
    raw_commands = verification.get("commands", [])
    if not isinstance(raw_commands, list):
        raise ctx["HarnessError"]("verification.commands must be a list.")

    root = ctx["ROOT"]
    commands: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_commands, start=1):
        if isinstance(item, list):
            name = f"command_{idx}"
            command = item
            cwd = root
            timeout_seconds = timeout_default
        elif isinstance(item, dict):
            name = str(item.get("name") or f"command_{idx}")
            command = item.get("command")
            if not isinstance(command, list):
                raise ctx["HarnessError"](f"verification command {name!r} must have a list command.")
            raw_cwd = item.get("cwd")
            cwd = Path(ctx["expand_runtime_placeholders"](raw_cwd, feature)) if raw_cwd else root
            if not cwd.is_absolute():
                cwd = root / cwd
            timeout_seconds = int(item.get("timeout_seconds", timeout_default))
        else:
            raise ctx["HarnessError"]("verification.commands entries must be objects or lists.")

        command_parts = [ctx["expand_runtime_placeholders"](part, feature) for part in command]
        if not command_parts or not command_parts[0]:
            raise ctx["HarnessError"](f"verification command {name!r} is empty.")
        if timeout_seconds <= 0:
            raise ctx["HarnessError"](f"verification command {name!r} has invalid timeout.")

        commands.append(
            {
                "name": slugify(name),
                "command": command_parts,
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
            }
        )
    return commands, required


def display_cwd(ctx: dict[str, Any], path: Path) -> str:
    try:
        resolved = path.resolve()
        root = ctx["ROOT"].resolve()
        if resolved == root or root in resolved.parents:
            return ctx["rel"](resolved)
    except Exception:
        pass
    return str(path)


def run_harness_verification(ctx: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    feature = state["feature_name"]
    verify_stage = ctx["VERIFY_STAGE"]
    stage = state.get("current_stage", verify_stage)
    attempt = int(state.get("attempts", {}).get(verify_stage, 1))
    commands, required = ctx["configured_verification_commands"](feature)
    out_dir = ctx["verification_dir"](feature)
    out_dir.mkdir(parents=True, exist_ok=True)
    started_at = ctx["iso_now"]()
    result_path = out_dir / f"{verify_stage}_attempt{attempt}_{ctx['now_stamp']()}.json"
    latest_path = ctx["latest_verification_result_path"](feature)

    summary: dict[str, Any] = {
        "feature_name": feature,
        "stage": stage,
        "attempt": attempt,
        "result_path": ctx["rel"](result_path),
        "latest_path": ctx["rel"](latest_path),
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
        summary["finished_at"] = ctx["iso_now"]()
        result_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        shutil.copyfile(result_path, latest_path)
        state["last_harness_verification"] = ctx["rel"](latest_path)
        ctx["log_event"](
            state,
            "harness_verification_skipped" if not required else "harness_verification_failed",
            str(summary["failure_reason"]),
            stage=verify_stage,
            result=ctx["rel"](latest_path),
        )
        ctx["save_state"](state)
        return summary | {"path": ctx["rel"](latest_path)}

    ctx["log_event"](
        state,
        "harness_verification_started",
        "running configured verification commands",
        stage=verify_stage,
        count=len(commands),
    )

    for command_spec in commands:
        name = command_spec["name"]
        command = command_spec["command"]
        cwd = Path(command_spec["cwd"])
        timeout_seconds = int(command_spec["timeout_seconds"])
        stdout_path = out_dir / f"{verify_stage}_attempt{attempt}_{name}.out.txt"
        stderr_path = out_dir / f"{verify_stage}_attempt{attempt}_{name}.err.txt"
        entry: dict[str, Any] = {
            "name": name,
            "command": command,
            "cwd": ctx["display_cwd"](cwd),
            "timeout_seconds": timeout_seconds,
            "returncode": None,
            "elapsed_seconds": None,
            "passed": False,
            "timed_out": False,
            "stdout": ctx["rel"](stdout_path),
            "stderr": ctx["rel"](stderr_path),
        }

        executable = ctx["resolve_executable"](command)
        if not executable:
            entry["error"] = f"Executable not found: {command[0]}"
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text(entry["error"] + "\n", encoding="utf-8")
            summary["commands"].append(entry)
            summary["failed_commands"].append(name)
            ctx["log_event"](
                state,
                "harness_verification_command_failed",
                entry["error"],
                stage=verify_stage,
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
            ctx["log_event"](
                state,
                "harness_verification_command_failed",
                "verification command failed",
                stage=verify_stage,
                command=name,
                returncode=entry.get("returncode"),
                timed_out=entry.get("timed_out"),
                stderr=entry.get("stderr"),
            )

    summary["passed"] = not summary["failed_commands"]
    summary["status"] = "PASS" if summary["passed"] else "FAIL"
    summary["finished_at"] = ctx["iso_now"]()
    result_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.copyfile(result_path, latest_path)
    state["last_harness_verification"] = ctx["rel"](latest_path)
    ctx["log_event"](
        state,
        "harness_verification_completed",
        "harness verification completed",
        stage=verify_stage,
        status=summary["status"],
        result=ctx["rel"](latest_path),
        failed=",".join(summary["failed_commands"]),
    )
    ctx["save_state"](state)
    return summary | {"path": ctx["rel"](latest_path)}


def enforce_harness_verify_result(
    ctx: dict[str, Any],
    state: dict[str, Any],
    result: dict[str, Any],
    status: str,
    next_stage: str,
) -> tuple[str, str]:
    if state.get("current_stage") != ctx["VERIFY_STAGE"] or status != "PASS":
        return status, next_stage

    verification = ctx["run_harness_verification"](state)
    result["harness_verification_status"] = verification["status"]
    result["harness_verification_path"] = verification["path"]
    if verification["passed"]:
        return status, next_stage

    result["status"] = "FAIL"
    result["next_stage"] = ctx["VERIFY_RETRY_TARGET_STAGE"]
    result["harness_commit_required"] = False
    result["blocking_reason"] = (
        "Harness verification failed. See "
        f"{verification['path']} for command results."
    )
    return "FAIL", ctx["VERIFY_RETRY_TARGET_STAGE"]


from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def _find_stage_result(text: str) -> dict[str, Any]:
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


def _parse_result_json_from_text(text: str) -> dict[str, Any]:
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


def _read_stage_result_json(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HarnessError(f"Invalid stage result JSON in {rel(path)}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HarnessError(f"Stage result JSON must be an object: {rel(path)}")
    return parsed


def _parse_result_scalar(value: str) -> Any:
    value = value.strip()
    low = value.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low == "없음":
        return ""
    return value


def _stage_default_next(stage: str) -> str | None:
    meta, _, _ = read_preset(stage)
    if stage == VERIFY_STAGE:
        return str(meta.get("default_next_stage_on_pass", DOCUMENT_STAGE or "done"))
    if DOCUMENT_STAGE and stage == DOCUMENT_STAGE:
        return "done"
    return meta.get("default_next_stage")  # type: ignore[return-value]


def _stage_status(result: dict[str, Any]) -> str:
    return str(result.get("status", "")).strip().upper()


def _prompt_path(state: dict[str, Any], stage: str) -> Path:
    attempts = state.setdefault("attempts", {})
    attempt = int(attempts.get(stage, 0)) + 1
    attempts[stage] = attempt
    prompt_dir = run_dir(state["feature_name"]) / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    return prompt_dir / f"{stage}_attempt{attempt}.md"


def _generate_prompt(state: dict[str, Any], stage: str, retry_context: str | None = None) -> Path:
    feature = state["feature_name"]
    meta, body, raw = read_preset(stage)
    scheduled_provider = provider_for_stage(stage, state)
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
- scheduled_provider: {scheduled_provider}
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


def _print_provider_heartbeat(
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


def _harness_script_for_pipeline_mode(pipeline_mode: Any) -> str:
    mode = str(pipeline_mode or PIPELINE_MODE)
    if mode == "fast":
        return ".ai\\harness_fast.py"
    if mode == "standard":
        return ".ai\\harness_standard.py"
    return ".ai\\harness.py"


def _suggested_retry_command(state: dict[str, Any], *, auto: bool = True) -> str:
    script = harness_script_for_pipeline_mode(state.get("pipeline_mode"))
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


def _provider_log_hint(stdout_path: Path, stderr_path: Path, provider_log_path: Path) -> str:
    return (
        f"stdout={rel(stdout_path)} "
        f"stderr={rel(stderr_path)} "
        f"provider_log={rel(provider_log_path)}"
    )


def _provider_failure_reason(
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


def _execute_current_prompt(state: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    feature = state["feature_name"]
    stage = state["current_stage"]
    prompt_rel = state.get("current_prompt")
    if not prompt_rel:
        raise HarnessError("No current prompt to execute.")
    prompt_file = ROOT / prompt_rel
    if not prompt_file.exists():
        raise HarnessError(f"Prompt file does not exist: {prompt_file}")

    provider = provider_for_stage(stage, state)
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


_INTERNAL_NAMES = {
    'find_stage_result': _find_stage_result,
    'parse_result_json_from_text': _parse_result_json_from_text,
    'read_stage_result_json': _read_stage_result_json,
    'parse_result_scalar': _parse_result_scalar,
    'stage_default_next': _stage_default_next,
    'stage_status': _stage_status,
    'prompt_path': _prompt_path,
    'generate_prompt': _generate_prompt,
    'print_provider_heartbeat': _print_provider_heartbeat,
    'harness_script_for_pipeline_mode': _harness_script_for_pipeline_mode,
    'suggested_retry_command': _suggested_retry_command,
    'provider_log_hint': _provider_log_hint,
    'provider_failure_reason': _provider_failure_reason,
    'execute_current_prompt': _execute_current_prompt,
}

_MISSING = object()


def _with_ctx(ctx: dict[str, Any], func: Any, *args: Any, **kwargs: Any) -> Any:
    names = {name for name in ctx if not name.startswith('__')} | set(_INTERNAL_NAMES)
    saved = {name: globals().get(name, _MISSING) for name in names}
    try:
        for name, value in ctx.items():
            if not name.startswith('__'):
                globals()[name] = value
        globals().update(_INTERNAL_NAMES)
        return func(*args, **kwargs)
    finally:
        for name, value in saved.items():
            if value is _MISSING:
                globals().pop(name, None)
            else:
                globals()[name] = value


def find_stage_result(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _find_stage_result, *args, **kwargs)


def parse_result_json_from_text(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _parse_result_json_from_text, *args, **kwargs)


def read_stage_result_json(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _read_stage_result_json, *args, **kwargs)


def parse_result_scalar(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _parse_result_scalar, *args, **kwargs)


def stage_default_next(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _stage_default_next, *args, **kwargs)


def stage_status(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _stage_status, *args, **kwargs)


def prompt_path(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _prompt_path, *args, **kwargs)


def generate_prompt(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _generate_prompt, *args, **kwargs)


def print_provider_heartbeat(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _print_provider_heartbeat, *args, **kwargs)


def harness_script_for_pipeline_mode(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _harness_script_for_pipeline_mode, *args, **kwargs)


def suggested_retry_command(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _suggested_retry_command, *args, **kwargs)


def provider_log_hint(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _provider_log_hint, *args, **kwargs)


def provider_failure_reason(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _provider_failure_reason, *args, **kwargs)


def execute_current_prompt(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _execute_current_prompt, *args, **kwargs)

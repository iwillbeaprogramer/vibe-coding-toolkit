from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

DEFAULT_MAX_VERIFY_FIX_RETRIES = 3


def _complete_run(state: dict[str, Any], stage: str) -> dict[str, Any]:
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
            index=history_result.get("index"),
        )
    save_state(state)
    return state


def _finish_pc_candidate_extraction(state: dict[str, Any]) -> dict[str, Any]:
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


def _maybe_rename_feature(state: dict[str, Any]) -> dict[str, Any]:
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


def _auto_drive(
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


def _safe_git_head() -> str:
    try:
        return git_head()
    except Exception:
        return ""


def _filtered_changed_paths(state: dict[str, Any], stage: str) -> list[str]:
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


def _commit_for_stage(state: dict[str, Any], stage: str, result: dict[str, Any]) -> None:
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


def _create_run(
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
    ensure_provider_schedule(state, persist=False, console=False, record_event=False)
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
    log_event(
        state,
        "provider_schedule_created",
        "created provider schedule",
        schedule=json.dumps(state.get("provider_schedule", {}), ensure_ascii=False),
    )
    generate_prompt(state, START_STAGE)
    return state


def _apply_runtime_performance(state: dict[str, Any], performance: Any | None) -> dict[str, Any]:
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


def _latest_provider_artifacts(
    feature: str,
    stage: str,
    state: dict[str, Any] | None = None,
) -> dict[str, str]:
    try:
        provider = provider_for_stage(stage, state)
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


def _handoff_path(feature: str) -> Path:
    return run_dir(feature) / "handoff.md"


def _safe_read_tail(path: Path, lines: int = 40, max_chars: int = 6000) -> str:
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


def _latest_verification_summary(feature: str) -> dict[str, Any] | None:
    path = latest_verification_result_path(feature)
    if not path.exists():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _recent_events(state: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    events = state.get("events", [])
    if not isinstance(events, list):
        return []
    return [event for event in events[-limit:] if isinstance(event, dict)]


def _write_handoff(
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


def _missing_stage_output_message(
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


def _load_stage_result(
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


def _expected_docx_path(feature: str) -> Path:
    return DOCS_DIR / f"{feature}_명세서.docx"


def _validate_document_stage_artifacts(feature: str) -> str | None:
    return validate_docx_file(expected_docx_path(feature))


def _block_state(state: dict[str, Any], stage: str, reason: str, next_stage: str | None = None) -> None:
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


def _resume_run(feature: str, max_verify_fix_retries: int = DEFAULT_MAX_VERIFY_FIX_RETRIES) -> dict[str, Any]:
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


def _approve_run(feature: str, max_verify_fix_retries: int = DEFAULT_MAX_VERIFY_FIX_RETRIES) -> dict[str, Any]:
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


def _build_retry_context(state: dict[str, Any], stage: str) -> str:
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


def _copy_same_prompt_for_retry(state: dict[str, Any], stage: str) -> Path:
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


def _archive_stage_outputs_for_retry(state: dict[str, Any], stage: str) -> None:
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


def _retry_run(
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


_INTERNAL_NAMES = {
    'complete_run': _complete_run,
    'finish_pc_candidate_extraction': _finish_pc_candidate_extraction,
    'maybe_rename_feature': _maybe_rename_feature,
    'auto_drive': _auto_drive,
    'safe_git_head': _safe_git_head,
    'filtered_changed_paths': _filtered_changed_paths,
    'commit_for_stage': _commit_for_stage,
    'create_run': _create_run,
    'apply_runtime_performance': _apply_runtime_performance,
    'latest_provider_artifacts': _latest_provider_artifacts,
    'handoff_path': _handoff_path,
    'safe_read_tail': _safe_read_tail,
    'latest_verification_summary': _latest_verification_summary,
    'recent_events': _recent_events,
    'write_handoff': _write_handoff,
    'missing_stage_output_message': _missing_stage_output_message,
    'load_stage_result': _load_stage_result,
    'expected_docx_path': _expected_docx_path,
    'validate_document_stage_artifacts': _validate_document_stage_artifacts,
    'block_state': _block_state,
    'resume_run': _resume_run,
    'approve_run': _approve_run,
    'build_retry_context': _build_retry_context,
    'copy_same_prompt_for_retry': _copy_same_prompt_for_retry,
    'archive_stage_outputs_for_retry': _archive_stage_outputs_for_retry,
    'retry_run': _retry_run,
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


def complete_run(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _complete_run, *args, **kwargs)


def finish_pc_candidate_extraction(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _finish_pc_candidate_extraction, *args, **kwargs)


def maybe_rename_feature(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _maybe_rename_feature, *args, **kwargs)


def auto_drive(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _auto_drive, *args, **kwargs)


def safe_git_head(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _safe_git_head, *args, **kwargs)


def filtered_changed_paths(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _filtered_changed_paths, *args, **kwargs)


def commit_for_stage(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _commit_for_stage, *args, **kwargs)


def create_run(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _create_run, *args, **kwargs)


def apply_runtime_performance(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _apply_runtime_performance, *args, **kwargs)


def latest_provider_artifacts(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _latest_provider_artifacts, *args, **kwargs)


def handoff_path(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _handoff_path, *args, **kwargs)


def safe_read_tail(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _safe_read_tail, *args, **kwargs)


def latest_verification_summary(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _latest_verification_summary, *args, **kwargs)


def recent_events(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _recent_events, *args, **kwargs)


def write_handoff(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _write_handoff, *args, **kwargs)


def missing_stage_output_message(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _missing_stage_output_message, *args, **kwargs)


def load_stage_result(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _load_stage_result, *args, **kwargs)


def expected_docx_path(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _expected_docx_path, *args, **kwargs)


def validate_document_stage_artifacts(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _validate_document_stage_artifacts, *args, **kwargs)


def block_state(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _block_state, *args, **kwargs)


def resume_run(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _resume_run, *args, **kwargs)


def approve_run(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _approve_run, *args, **kwargs)


def build_retry_context(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _build_retry_context, *args, **kwargs)


def copy_same_prompt_for_retry(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _copy_same_prompt_for_retry, *args, **kwargs)


def archive_stage_outputs_for_retry(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _archive_stage_outputs_for_retry, *args, **kwargs)


def retry_run(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _retry_run, *args, **kwargs)

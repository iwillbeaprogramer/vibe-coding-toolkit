from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


PC_CANDIDATE_EXTRACTION_MAX_ATTEMPTS = 3


def _history_summary_path() -> Path:
    return HISTORY_DIR / "summary.md"


def _history_index_path() -> Path:
    return HISTORY_DIR / "index.json"


def _pc_candidates_path() -> Path:
    return PC_CANDIDATES_PATH


def _project_contract_path() -> Path:
    return PROJECT_CONTRACT_PATH


def _empty_pc_candidates_store() -> dict[str, Any]:
    return {"version": PC_CANDIDATES_SCHEMA_VERSION, "candidates": []}


def _read_pc_candidates_store() -> dict[str, Any]:
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


def _write_pc_candidates_store(store: dict[str, Any]) -> None:
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


def _pending_pc_candidates() -> list[dict[str, Any]]:
    store = read_pc_candidates_store()
    return [
        item
        for item in store.get("candidates", [])
        if str(item.get("status") or "").strip() == PC_PENDING_STATUS
    ]


def _ensure_project_contract_file() -> None:
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


def _project_contract_prompt_text() -> str:
    ensure_project_contract_file()
    path = project_contract_path()
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return (
            "## Project Contract\n"
            "No approved project contract exists yet. Follow the existing codebase conventions.\n"
        )
    return f"## Project Contract\nSource: {rel(path)}\n\n{text}\n"


def _warn_pending_pc_candidates_for_new_run() -> None:
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


def _ensure_history_store() -> bool:
    initialized = not HISTORY_DIR.exists()
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    if not history_index_path().exists():
        write_json_file(history_index_path(), {"schema_version": HISTORY_SCHEMA_VERSION, "features": []})
        initialized = True
    if not pc_candidates_path().exists():
        write_pc_candidates_store(empty_pc_candidates_store())
        initialized = True
    if not history_summary_path().exists():
        history_summary_path().write_text(
            "# 프로젝트 히스토리\n\n"
            "로컬 하네스가 자동 생성한 완료 run 인덱스 요약입니다.\n",
            encoding="utf-8",
        )
        initialized = True
    return initialized


def _history_timestamp_id(value: Any) -> str:
    stamp = re.sub(r"\D+", "", str(value or ""))[:14]
    return stamp or now_stamp().replace("-", "")


def _history_event_id(state: dict[str, Any]) -> str:
    feature = slugify(str(state.get("feature_name") or "feature"))
    pipeline = slugify(str(state.get("pipeline_mode") or PIPELINE_MODE))
    return f"{history_timestamp_id(state.get('created_at'))}-{feature}-{pipeline}"


def _safe_stage_text(feature: str, stage: str) -> str:
    path = stage_output_path(feature, stage)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _load_history_stage_results(feature: str) -> dict[str, dict[str, Any]]:
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


def _history_source_artifacts(feature: str) -> list[str]:
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


def _split_event_paths(value: Any) -> list[str]:
    if isinstance(value, list):
        return [norm_repo_path(str(item)) for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []
    return [norm_repo_path(part.strip()) for part in value.split(",") if part.strip()]


def _collect_history_changed_files(
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


def _load_history_verification(feature: str, stage_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
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


def _collect_history_notes(
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


def _normalize_unresolved_source_item(
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


def _unresolved_items_from_value(
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


def _collect_history_unresolved_items(
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


def _stable_history_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(compact_history_text(part, max_len=1000) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _normalize_history_risk(
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


def _update_history_risks(event: dict[str, Any]) -> list[dict[str, Any]]:
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


def _normalize_history_unresolved_item(
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


def _update_history_unresolved_items(event: dict[str, Any]) -> list[dict[str, Any]]:
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


def _append_history_decisions(event: dict[str, Any]) -> list[dict[str, Any]]:
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


def _update_history_feature_summary(event: dict[str, Any]) -> dict[str, Any]:
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


def _read_history_index() -> dict[str, Any]:
    index = read_json_file(history_index_path(), {"schema_version": HISTORY_SCHEMA_VERSION, "features": []})
    if not isinstance(index, dict):
        return {"schema_version": HISTORY_SCHEMA_VERSION, "features": []}
    features = index.get("features")
    if not isinstance(features, list):
        index["features"] = []
    else:
        index["features"] = [item for item in features if isinstance(item, dict)]
    index["schema_version"] = HISTORY_SCHEMA_VERSION
    return index


def _write_history_index(index: dict[str, Any]) -> None:
    write_json_file(history_index_path(), index)


def _compact_history_titles(items: list[Any], max_items: int = 5, max_len: int = 180) -> list[str]:
    if max_items <= 0:
        return []
    titles: list[str] = []
    for item in items:
        if isinstance(item, dict):
            value = (
                item.get("title")
                or item.get("summary")
                or item.get("description")
                or item.get("decision")
                or item.get("risk")
            )
        else:
            value = item
        title = compact_history_text(value, max_len=max_len)
        if title and title not in titles:
            titles.append(title)
        if len(titles) >= max_items:
            break
    return titles


def _history_document_path(feature: str) -> str:
    if not DOCUMENT_STAGE:
        return ""
    doc = expected_docx_path(feature)
    return rel(doc) if doc.exists() else ""


def _upsert_history_index_entry(entry: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    index = read_history_index()
    features = index.setdefault("features", [])
    feature = str(entry.get("feature") or "")
    replaced = False
    for position, existing in enumerate(features):
        if isinstance(existing, dict) and existing.get("feature") == feature:
            features[position] = entry
            replaced = True
            break
    if not replaced:
        features.append(entry)
    features.sort(key=lambda item: str(item.get("completed_at") or ""), reverse=True)
    index["updated_at"] = iso_now()
    write_history_index(index)
    return index, not replaced


def _render_history_summary(index: dict[str, Any]) -> None:
    features = index.get("features") if isinstance(index.get("features"), list) else []
    complete_features = [item for item in features if isinstance(item, dict)]
    lines = [
        "# 프로젝트 히스토리",
        "",
        "로컬 하네스가 자동 생성한 완료 run 인덱스 요약입니다.",
        "",
        f"- 기록된 feature: {len(complete_features)}",
        f"- 인덱스: {rel(history_index_path())}",
        f"- PC 후보: {rel(pc_candidates_path())}",
        "",
        "## 최근 완료 Run",
        "",
    ]
    if not complete_features:
        lines.append("- 없음")
    for entry in complete_features[:20]:
        verification = str(entry.get("verification") or "UNKNOWN")
        lines.append(
            "- "
            f"{entry.get('completed_at', '')} "
            f"{entry.get('feature', '')} "
            f"({entry.get('pipeline', '')}, {entry.get('status', '')}, verify={verification})"
        )
        implemented = entry.get("implemented") if isinstance(entry.get("implemented"), list) else []
        for item in implemented[:3]:
            lines.append(f"  - {item}")
    history_summary_path().write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _record_project_history(state: dict[str, Any]) -> dict[str, Any]:
    initialized = ensure_history_store()
    feature = str(state["feature_name"])
    stage_results = load_history_stage_results(feature)
    implemented, risks, future_improvements, decisions = collect_history_notes(feature, stage_results)
    verification = load_history_verification(feature, stage_results)
    completed_at = iso_now()
    event_id = history_event_id(state)
    risk_levels = [
        compact_history_text(result.get("risk_level"), max_len=40)
        for result in stage_results.values()
        if result.get("risk_level")
    ]
    risk_level = risk_levels[-1] if risk_levels else ""

    important_followups = compact_history_titles(future_improvements, max_items=5)
    medium_high_risks = [
        risk
        for risk in risks
        if isinstance(risk, dict)
        and str(risk.get("severity") or "low").strip().lower() in {"medium", "high", "critical"}
    ]
    important_followups.extend(
        item
        for item in compact_history_titles(medium_high_risks, max_items=5 - len(important_followups))
        if item not in important_followups
    )

    entry = {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "event_id": event_id,
        "feature": feature,
        "pipeline": state.get("pipeline_mode") or PIPELINE_MODE,
        "status": state.get("status"),
        "created_at": state.get("created_at"),
        "completed_at": completed_at,
        "request_summary": compact_history_text(state.get("request"), max_len=800),
        "verification": verification.get("status", "UNKNOWN") if isinstance(verification, dict) else "UNKNOWN",
        "verification_source": verification.get("source", "") if isinstance(verification, dict) else "",
        "risk_level": risk_level,
        "feature_dir": rel(feature_dir(feature)),
        "run_dir": rel(run_dir(feature)),
        "doc": history_document_path(feature),
        "commits": state.get("commits", {}),
        "implemented": compact_history_titles(implemented, max_items=8),
        "important_followups": important_followups[:5],
        "important_decisions": compact_history_titles(decisions, max_items=5),
    }

    index, inserted = upsert_history_index_entry(entry)
    render_history_summary(index)

    state["history"] = {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "event_id": event_id,
        "index": rel(history_index_path()),
        "summary": rel(history_summary_path()),
        "status": "recorded" if inserted else "updated",
        "recorded_at": completed_at,
        "history_initialized": initialized,
    }
    return state["history"]


def _should_extract_pc_candidates(state: dict[str, Any]) -> bool:
    return pipeline_extracts_pc_candidates(state.get("pipeline_mode") or PIPELINE_MODE)


def _pc_candidate_source_artifact_text(feature: str, max_chars_per_file: int = 8000) -> str:
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


def _build_pc_candidate_extraction_prompt(state: dict[str, Any]) -> str:
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


def _normalize_pc_candidate(
    raw: dict[str, Any],
    state: dict[str, Any],
    created_at: str,
    provider: str,
) -> dict[str, Any] | None:
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
        "extraction_model": provider,
    }


def _append_pc_candidates(candidates: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
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


def _parse_pc_candidate_extraction_result(result: dict[str, Any]) -> list[Any]:
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
    return raw_candidates


def _pc_candidate_extraction_warning(
    provider: str,
    failures: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "WARN",
        "provider": provider,
        "attempts": len(failures),
        "raw_candidate_count": 0,
        "candidate_count": 0,
        "filtered_out_count": 0,
        "recorded_count": 0,
        "candidate_ids": [],
        "candidates_path": rel(pc_candidates_path()),
        "warning": "Project Contract candidate extraction failed after retries.",
        "failures": failures,
    }


def _extract_project_contract_candidates(state: dict[str, Any]) -> dict[str, Any]:
    if not should_extract_pc_candidates(state):
        return {"status": "skipped", "reason": "pipeline does not extract PC candidates"}

    feature = str(state["feature_name"])
    provider = provider_for_stage(PC_REVIEW_STAGE, state)
    prompt = build_pc_candidate_extraction_prompt(state)
    failures: list[dict[str, Any]] = []
    result: dict[str, Any] = {}
    raw_candidates: list[Any] | None = None

    for attempt in range(1, PC_CANDIDATE_EXTRACTION_MAX_ATTEMPTS + 1):
        attempt_result: dict[str, Any] = {}
        log_event(
            state,
            "pc_candidate_extraction_started",
            "extracting project contract candidates",
            stage=PC_REVIEW_STAGE,
            provider=provider,
            attempt=attempt,
            max_attempts=PC_CANDIDATE_EXTRACTION_MAX_ATTEMPTS,
        )
        try:
            attempt_result = run_text_provider_prompt(
                provider,
                prompt,
                logs_dir=run_dir(feature) / "logs",
                log_prefix="pc_candidates",
                timeout_seconds=3600,
                performance=state.get("performance"),
            )
            result = attempt_result
            raw_candidates = parse_pc_candidate_extraction_result(result)
            break
        except Exception as exc:
            failures.append(
                {
                    "attempt": attempt,
                    "reason": str(exc),
                    "stdout": attempt_result.get("stdout"),
                    "stderr": attempt_result.get("stderr"),
                    "meta": attempt_result.get("meta"),
                }
            )
            log_event(
                state,
                "pc_candidate_extraction_attempt_failed",
                str(exc),
                stage=PC_REVIEW_STAGE,
                provider=provider,
                attempt=attempt,
                max_attempts=PC_CANDIDATE_EXTRACTION_MAX_ATTEMPTS,
            )

    if raw_candidates is None:
        extraction = pc_candidate_extraction_warning(provider, failures)
        state["pc_candidate_extraction"] = extraction
        log_event(
            state,
            "pc_candidate_extraction_warning",
            "project contract candidate extraction failed after retries; continuing run",
            stage=PC_REVIEW_STAGE,
            provider=provider,
            attempts=len(failures),
        )
        return extraction

    created_at = iso_now()
    normalized = [
        candidate
        for candidate in (
            normalize_pc_candidate(item, state, created_at, provider)
            for item in raw_candidates
            if isinstance(item, dict)
        )
        if candidate
    ]
    append_result = append_pc_candidates(normalized, state)
    extraction = {
        "status": "PASS",
        "provider": provider,
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
        provider=provider,
        raw_candidate_count=len(raw_candidates),
        candidate_count=len(normalized),
        filtered_out_count=len(raw_candidates) - len(normalized),
        recorded_count=append_result["added_count"],
    )
    return extraction


_INTERNAL_NAMES = {
    'history_summary_path': _history_summary_path,
    'history_index_path': _history_index_path,
    'pc_candidates_path': _pc_candidates_path,
    'project_contract_path': _project_contract_path,
    'empty_pc_candidates_store': _empty_pc_candidates_store,
    'read_pc_candidates_store': _read_pc_candidates_store,
    'write_pc_candidates_store': _write_pc_candidates_store,
    'pending_pc_candidates': _pending_pc_candidates,
    'ensure_project_contract_file': _ensure_project_contract_file,
    'project_contract_prompt_text': _project_contract_prompt_text,
    'warn_pending_pc_candidates_for_new_run': _warn_pending_pc_candidates_for_new_run,
    'ensure_history_store': _ensure_history_store,
    'history_timestamp_id': _history_timestamp_id,
    'history_event_id': _history_event_id,
    'safe_stage_text': _safe_stage_text,
    'load_history_stage_results': _load_history_stage_results,
    'history_source_artifacts': _history_source_artifacts,
    'split_event_paths': _split_event_paths,
    'collect_history_changed_files': _collect_history_changed_files,
    'load_history_verification': _load_history_verification,
    'collect_history_notes': _collect_history_notes,
    'normalize_unresolved_source_item': _normalize_unresolved_source_item,
    'unresolved_items_from_value': _unresolved_items_from_value,
    'collect_history_unresolved_items': _collect_history_unresolved_items,
    'stable_history_id': _stable_history_id,
    'normalize_history_risk': _normalize_history_risk,
    'update_history_risks': _update_history_risks,
    'normalize_history_unresolved_item': _normalize_history_unresolved_item,
    'update_history_unresolved_items': _update_history_unresolved_items,
    'append_history_decisions': _append_history_decisions,
    'update_history_feature_summary': _update_history_feature_summary,
    'read_history_index': _read_history_index,
    'write_history_index': _write_history_index,
    'compact_history_titles': _compact_history_titles,
    'history_document_path': _history_document_path,
    'upsert_history_index_entry': _upsert_history_index_entry,
    'render_history_summary': _render_history_summary,
    'record_project_history': _record_project_history,
    'should_extract_pc_candidates': _should_extract_pc_candidates,
    'pc_candidate_source_artifact_text': _pc_candidate_source_artifact_text,
    'build_pc_candidate_extraction_prompt': _build_pc_candidate_extraction_prompt,
    'normalize_pc_candidate': _normalize_pc_candidate,
    'append_pc_candidates': _append_pc_candidates,
    'parse_pc_candidate_extraction_result': _parse_pc_candidate_extraction_result,
    'pc_candidate_extraction_warning': _pc_candidate_extraction_warning,
    'extract_project_contract_candidates': _extract_project_contract_candidates,
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


def history_summary_path(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _history_summary_path, *args, **kwargs)


def history_index_path(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _history_index_path, *args, **kwargs)


def pc_candidates_path(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _pc_candidates_path, *args, **kwargs)


def project_contract_path(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _project_contract_path, *args, **kwargs)


def empty_pc_candidates_store(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _empty_pc_candidates_store, *args, **kwargs)


def read_pc_candidates_store(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _read_pc_candidates_store, *args, **kwargs)


def write_pc_candidates_store(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _write_pc_candidates_store, *args, **kwargs)


def pending_pc_candidates(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _pending_pc_candidates, *args, **kwargs)


def ensure_project_contract_file(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _ensure_project_contract_file, *args, **kwargs)


def project_contract_prompt_text(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _project_contract_prompt_text, *args, **kwargs)


def warn_pending_pc_candidates_for_new_run(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _warn_pending_pc_candidates_for_new_run, *args, **kwargs)


def ensure_history_store(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _ensure_history_store, *args, **kwargs)


def history_timestamp_id(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _history_timestamp_id, *args, **kwargs)


def history_event_id(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _history_event_id, *args, **kwargs)


def safe_stage_text(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _safe_stage_text, *args, **kwargs)


def load_history_stage_results(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _load_history_stage_results, *args, **kwargs)


def history_source_artifacts(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _history_source_artifacts, *args, **kwargs)


def split_event_paths(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _split_event_paths, *args, **kwargs)


def collect_history_changed_files(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _collect_history_changed_files, *args, **kwargs)


def load_history_verification(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _load_history_verification, *args, **kwargs)


def collect_history_notes(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _collect_history_notes, *args, **kwargs)


def normalize_unresolved_source_item(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _normalize_unresolved_source_item, *args, **kwargs)


def unresolved_items_from_value(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _unresolved_items_from_value, *args, **kwargs)


def collect_history_unresolved_items(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _collect_history_unresolved_items, *args, **kwargs)


def stable_history_id(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _stable_history_id, *args, **kwargs)


def normalize_history_risk(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _normalize_history_risk, *args, **kwargs)


def update_history_risks(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _update_history_risks, *args, **kwargs)


def normalize_history_unresolved_item(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _normalize_history_unresolved_item, *args, **kwargs)


def update_history_unresolved_items(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _update_history_unresolved_items, *args, **kwargs)


def append_history_decisions(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _append_history_decisions, *args, **kwargs)


def update_history_feature_summary(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _update_history_feature_summary, *args, **kwargs)


def read_history_index(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _read_history_index, *args, **kwargs)


def write_history_index(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _write_history_index, *args, **kwargs)


def compact_history_titles(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _compact_history_titles, *args, **kwargs)


def history_document_path(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _history_document_path, *args, **kwargs)


def upsert_history_index_entry(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _upsert_history_index_entry, *args, **kwargs)


def render_history_summary(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _render_history_summary, *args, **kwargs)


def record_project_history(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _record_project_history, *args, **kwargs)


def should_extract_pc_candidates(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _should_extract_pc_candidates, *args, **kwargs)


def pc_candidate_source_artifact_text(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _pc_candidate_source_artifact_text, *args, **kwargs)


def build_pc_candidate_extraction_prompt(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _build_pc_candidate_extraction_prompt, *args, **kwargs)


def normalize_pc_candidate(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _normalize_pc_candidate, *args, **kwargs)


def append_pc_candidates(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _append_pc_candidates, *args, **kwargs)


def extract_project_contract_candidates(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
    return _with_ctx(ctx, _extract_project_contract_candidates, *args, **kwargs)

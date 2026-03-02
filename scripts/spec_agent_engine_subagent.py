#!/usr/bin/env python
from __future__ import annotations

import datetime as dt
from pathlib import Path

import spec_agent_engine_core as core


def subagent_context(path: Path, stage: str) -> dict:
    """Build structured stage context consumed by a stage-specific subagent."""
    stage_norm = core._normalize_stage_name(stage)
    meta, meta_version = core.load_metadata_file(path, with_version=True)
    root, changed = core._ensure_subagent_state(meta, reset=False)
    project_mode = core.resolve_project_mode(
        str(meta.get("original_requirement", "")),
        str(meta.get("initial_clarifications", "")),
        str(meta.get("project_mode", "")),
    )
    mode_changed = str(meta.get("project_mode", "")).strip().lower() != project_mode
    meta["project_mode"] = project_mode
    if changed or mode_changed:
        core.save_metadata_file(path, meta, dry_run=False, expected_version=meta_version)
    focus_policy = core.clarification_focus_by_project_mode(project_mode)
    handoff = core._subagent_stage_handoff(stage_norm)

    rows = []
    try:
        rows = core.load_clar_rows(path, sync=False)
    except SystemExit:
        rows = []
    confirmed = [r for r in rows if str(r.get("status", "")).strip() == core.CONFIRMED_STATUS and not str(r.get("question", "")).strip().startswith("（示例）")]
    pending = [
        r
        for r in rows
        if str(r.get("question", "")).strip()
        and not str(r.get("question", "")).strip().startswith("（示例）")
        and str(r.get("status", "")).strip() != core.CONFIRMED_STATUS
    ]
    upstream_hashes = core._stage_upstream_hashes(path, stage_norm)
    dep_stages = core.SUBAGENT_STAGE_DEPENDENCIES.get(stage_norm, [])
    upstream_docs = []
    for dep in dep_stages:
        dep_path = core._doc_path_for_stage(path, dep)
        upstream_docs.append({
            "stage": dep,
            "path": str(dep_path) if dep_path else "",
            "hash": upstream_hashes.get(dep, ""),
            "status": root.get("stages", {}).get(dep, {}).get("status", "pending"),
            "exists": bool(dep_path and dep_path.exists()),
        })

    target_doc_path = core._doc_path_for_stage(path, stage_norm)
    target_exists = bool(target_doc_path and target_doc_path.exists())
    target_hash = ""
    if target_doc_path and target_doc_path.exists():
        target_hash = core.content_hash_without_clarifications(core.read_file(target_doc_path))
    stage_state = root.get("stages", {}).get(stage_norm, {})
    reopen_info = root.get("last_reopen", {}) if isinstance(root.get("last_reopen", {}), dict) else {}
    reopen_reason = ""
    if isinstance(stage_state, dict):
        note = str(stage_state.get("notes", "")).strip()
        if "reopen" in note.lower() or "mapped" in note.lower():
            reopen_reason = note
    if not reopen_reason and reopen_info.get("stage") == stage_norm:
        reopen_reason = str(reopen_info.get("reason", "")).strip()

    return {
        "requirement_path": str(path),
        "stage": stage_norm,
        "target_sections": handoff["target_sections"],
        "must_keep_sections": handoff["must_keep_sections"],
        "reopen_reason": reopen_reason,
        "dependencies": dep_stages,
        "upstream_docs": upstream_docs,
        "target_doc": {
            "path": str(target_doc_path) if target_doc_path else "",
            "exists": target_exists,
            "hash": target_hash,
        },
        "dependency_signature_required": stage_norm in {"prd", "tech", "acceptance"},
        "project_mode": project_mode,
        "clarification_focus": focus_policy,
        "global_memory": {
            "path": str(core.GLOBAL_MEMORY_FILE),
            "exists": core.GLOBAL_MEMORY_FILE.exists(),
            "hash": core.global_memory_hash(),
        },
        "clarifications": {
            "file_md": str(path / core.DOC_FILES["clarifications"]),
            "file_json": str(path / core.DOC_FILES["clarifications_json"]),
            "confirmed_count": len(confirmed),
            "pending_count": len(pending),
            "confirmed_ids": [r.get("id", "") for r in confirmed if r.get("id", "")],
        },
        "handoff": {
            "protocol_version": int(root.get("handoff_protocol_version", 1)),
            "target_sections": handoff["target_sections"],
            "must_keep_sections": handoff["must_keep_sections"],
            "reopen_reason": reopen_reason,
        },
        "subagent_state": root,
    }


def update_subagent_stage(
    path: Path,
    stage: str,
    status: str,
    agent: str = "",
    notes: str = "",
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    """Update stage execution state and enforce dependency/output contracts."""
    stage_norm = core._normalize_stage_name(stage)
    status_norm = core._normalize_stage_status(status)

    meta, meta_version = core.load_metadata_file(path, with_version=True)
    root, _changed = core._ensure_subagent_state(meta, reset=False)
    stages = root.get("stages", {})
    state = stages.get(stage_norm, core._subagent_default_stage_state())

    dep_issues = []
    if status_norm in {"running", "completed"}:
        dep_issues = core._validate_stage_dependencies(stages, stage_norm)
        if dep_issues and not force:
            hints = "\n".join([f"- {x}" for x in dep_issues])
            raise SystemExit(f"stage blocked: {stage_norm}\n{hints}")

    upstream_hashes = core._stage_upstream_hashes(path, stage_norm) if status_norm == "completed" else {}
    validation_errors = []
    doc_hash = ""
    if status_norm == "completed":
        if stage_norm in core.SUBAGENT_STAGE_DOC_MAP:
            doc_hash, validation_errors = core._validate_doc_stage_completion(path, stage_norm, upstream_hashes)
        elif stage_norm == "final_check":
            validation_errors = core._validate_final_check_stage(path)
            if core.ENFORCE_FINAL_CHECK_AGENT_INDEPENDENCE:
                final_agent = str(agent or "").strip()
                doc_agents = {
                    str(stages.get(doc_stage, {}).get("agent", "")).strip()
                    for doc_stage in core.SUBAGENT_STAGE_DOC_MAP.keys()
                    if str(stages.get(doc_stage, {}).get("status", "")).strip() == "completed"
                    and str(stages.get(doc_stage, {}).get("agent", "")).strip()
                }
                if not final_agent:
                    validation_errors.append("final_check requires --agent when independence check is enabled")
                elif final_agent in doc_agents:
                    validation_errors.append(
                        f"final_check agent must differ from completed doc stage agents, got: {final_agent}"
                    )
        if validation_errors and not force:
            hints = "\n".join([f"- {x}" for x in validation_errors])
            raise SystemExit(f"stage validation failed: {stage_norm}\n{hints}")

    now = dt.datetime.now().isoformat(timespec="seconds")
    state["status"] = status_norm
    state["agent"] = str(agent or "").strip()
    state["updated_at"] = now
    state["doc_hash"] = doc_hash
    state["upstream_hashes"] = upstream_hashes
    state["notes"] = str(notes or "").strip()
    state["validation_errors"] = validation_errors
    stages[stage_norm] = state

    if stage_norm == "final_check" and status_norm == "failed":
        reopen_stage, reopen_counts, mapped_issues = core._suggest_reopen_stage_from_final_check(path)
        if reopen_stage:
            breakdown = ", ".join([f"{k}:{v}" for k, v in reopen_counts.items() if v > 0])
            reason = f"auto reopen by final-check mapping ({breakdown})"
            core._reopen_doc_stages_from(stages, reopen_stage, reason)
            root["last_reopen"] = {
                "stage": reopen_stage,
                "reason": reason,
                "at": now,
                "source": "final_check",
                "issue_count": len(mapped_issues),
                "breakdown": {k: v for k, v in reopen_counts.items() if v > 0},
                "issues": mapped_issues[:20],
            }
        else:
            root["last_reopen"] = {}

    # If an upstream stage is reopened or failed, enforce downstream rerun.
    if status_norm in {"pending", "failed"} and stage_norm in core.SUBAGENT_STAGE_ORDER and stage_norm != "final_check":
        core._downgrade_downstream_stages(stages, stage_norm, f"upstream stage changed: {stage_norm}")

    # If a doc stage completed with new upstream hashes, verify downstream freshness.
    if status_norm == "completed" and stage_norm in core.SUBAGENT_STAGE_DOC_MAP:
        for downstream in core.SUBAGENT_STAGE_ORDER:
            if downstream == stage_norm:
                continue
            if stage_norm not in core.SUBAGENT_STAGE_DEPENDENCIES.get(downstream, []):
                continue
            downstream_state = stages.get(downstream, {})
            if downstream_state.get("status") != "completed":
                continue
            expected = core._stage_upstream_hashes(path, downstream)
            recorded = downstream_state.get("upstream_hashes", {})
            if any(str(recorded.get(k, "")) != str(v) for k, v in expected.items()):
                core._downgrade_downstream_stages(stages, downstream, f"upstream content drifted: {stage_norm}")
                break

    root["stages"] = stages
    root["current_stage"] = core._recommended_next_stage(stages) or core.SUBAGENT_STAGE_ORDER[-1]
    root["updated_at"] = now
    meta["subagents"] = root
    core.save_metadata_file(path, meta, dry_run=dry_run, expected_version=meta_version)
    return root


def subagent_status(path: Path, normalize: bool = False) -> dict:
    """Return subagent status; normalize stale stages only when requested."""
    meta, meta_version = core.load_metadata_file(path, with_version=True)
    root, changed = core._ensure_subagent_state(meta, reset=False)
    stages = root.get("stages", {})
    current_hashes = core._current_doc_hashes(path)
    stale_changed = False

    stale = {}
    for stage in core.SUBAGENT_STAGE_ORDER:
        stage_state = stages.get(stage, {})
        if stage_state.get("status") != "completed":
            stale[stage] = False
            continue
        if stage in core.SUBAGENT_STAGE_DOC_MAP:
            recorded_doc_hash = str(stage_state.get("doc_hash", "")).strip()
            current_doc_hash = current_hashes.get(stage, "")
            if not recorded_doc_hash or recorded_doc_hash != current_doc_hash:
                stale[stage] = True
                continue
            recorded_up = stage_state.get("upstream_hashes", {}) if isinstance(stage_state.get("upstream_hashes"), dict) else {}
            current_up = core._stage_upstream_hashes(path, stage)
            stale[stage] = any(str(recorded_up.get(k, "")) != str(v) for k, v in current_up.items())
            continue
        if stage == "final_check":
            stale[stage] = any(stale.get(dep, False) or stages.get(dep, {}).get("status") != "completed" for dep in core.SUBAGENT_STAGE_DEPENDENCIES["final_check"])
        else:
            stale[stage] = False

    effective_stages = {}
    for stage in core.SUBAGENT_STAGE_ORDER:
        current = stages.get(stage, {})
        state = dict(current) if isinstance(current, dict) else core._subagent_default_stage_state()
        if stale.get(stage, False):
            if state.get("status") != "pending":
                stale_changed = True
            state["status"] = "pending"
        effective_stages[stage] = state

    current_stage = core._recommended_next_stage(effective_stages) or core.SUBAGENT_STAGE_ORDER[-1]
    if normalize:
        root["stages"] = effective_stages
        root["current_stage"] = current_stage
        root["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    if normalize and (changed or stale_changed):
        meta["subagents"] = root
        core.save_metadata_file(path, meta, dry_run=False, expected_version=meta_version)

    return {
        "requirement_path": str(path),
        "current_stage": current_stage,
        "stale_stages": [stage for stage, is_stale in stale.items() if is_stale],
        "last_reopen": root.get("last_reopen", {}),
        "stages": root.get("stages", {}) if normalize else stages,
    }

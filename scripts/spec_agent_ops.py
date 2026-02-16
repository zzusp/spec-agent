#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import spec_agent_engine as eng


def normalize_cli_args(argv: list[str]) -> list[str]:
    global_flags = {"--json-output", "--verbose"}
    front = []
    rest = []
    for arg in argv:
        if arg in global_flags:
            front.append(arg)
        else:
            rest.append(arg)
    return front + rest



def cmd_init(args):
    dry_run = eng.is_dry_run(args)
    desc = eng.parse_requirement_input(args)
    db_connections = eng.parse_ai_db_connections_json(args.db_connections_json) if getattr(args, "db_connections_json", None) else []
    date_str = args.date or eng.today_str()
    requested_name = (args.name or "").strip()
    base_name = requested_name if requested_name else eng.auto_requirement_name(args.title, desc)
    req_name = base_name
    path = eng.requirement_dir(date_str, req_name)
    if dry_run and not requested_name:
        req_name = eng.next_available_requirement_name(date_str, base_name)
        path = eng.requirement_dir(date_str, req_name)
    resolved_title = eng.auto_requirement_title(args.title, desc, req_name)
    project_mode = eng.resolve_project_mode(desc, args.clarify or "", getattr(args, "project_mode", "auto"))
    if dry_run:
        eng.runtime_log(f"[dry-run] would initialize: {path}")
        return
    while True:
        with eng.requirement_write_lock(path, dry_run=False):
            if path.exists():
                if requested_name:
                    raise SystemExit("requirement already exists")
                req_name = eng.next_available_requirement_name(date_str, base_name)
                path = eng.requirement_dir(date_str, req_name)
                resolved_title = eng.auto_requirement_title(args.title, desc, req_name)
                continue
            if getattr(args, "state_only", False):
                eng.init_state_only(path, resolved_title, desc, project_mode=project_mode)
            else:
                eng.init_docs(path, resolved_title, desc, project_mode=project_mode)
            if args.clarify or db_connections:
                meta, meta_version = eng.load_metadata_file(path, with_version=True)
                meta["project_mode"] = project_mode
                if args.clarify:
                    meta["initial_clarifications"] = args.clarify
                if db_connections:
                    meta[eng.AI_DB_CONNECTIONS_KEY] = db_connections
                eng.save_metadata_file(path, meta, dry_run=False, expected_version=meta_version)
            eng.ensure_runtime_context_clarifications(path, db_connections, dry_run=False)
            break
    eng.set_active(path)
    eng.emit(
        args,
        f"initialized: {path}",
        path=str(path),
        name=req_name,
        title=resolved_title,
        state_only=bool(getattr(args, "state_only", False)),
        project_mode=project_mode,
        auto_named=not bool(requested_name),
        auto_titled=not bool((args.title or "").strip()),
    )


def cmd_list(args):
    items = eng.list_requirements()
    active = eng.get_active()
    if getattr(args, "json_output", False):
        data = [{"path": str(item), "active": bool(active and item == active)} for item in items]
        eng.emit(args, "requirements listed", count=len(data), requirements=data)
        return
    for item in items:
        mark = "*" if active and item == active else " "
        print(f"{mark} {item}")


def cmd_set_active(args):
    dry_run = eng.is_dry_run(args)
    if args.path:
        path = Path(args.path)
    elif args.name:
        matches = eng.find_requirement(args.name)
        if len(matches) > 1:
            candidates = "\n".join([f"- {m}" for m in matches])
            raise SystemExit(f"multiple requirements found for name={args.name}, use --path:\n{candidates}")
        if len(matches) != 1:
            raise SystemExit("requirement not found")
        path = matches[0]
    else:
        raise SystemExit("use --name or --path")
    if not path.exists():
        raise SystemExit("path not found")
    if dry_run:
        eng.runtime_log(f"[dry-run] would set active: {path}")
        return
    eng.set_active(path)
    eng.emit(args, f"active: {path}", path=str(path))


def cmd_check_clarifications(args):
    path = eng.resolve_path(args)
    clar_path = path / eng.DOC_FILES["clarifications"]
    if not clar_path.exists():
        raise SystemExit("clarifications file not found")
    md_rows, _ = eng.load_clar_rows_pair(path)
    pending = eng.list_unconfirmed(md_rows)
    mirror_in_sync = False

    def row_key(row):
        r = eng.normalize_clar_row(row)
        return (
            r.get("id", ""),
            r.get("status", ""),
            r.get("priority", ""),
            r.get("impact", ""),
            r.get("doc", ""),
            r.get("section", ""),
            r.get("question", ""),
            r.get("answer", ""),
            r.get("solution", ""),
        )

    clar_json_path = path / eng.DOC_FILES["clarifications_json"]
    if clar_json_path.exists():
        try:
            raw = json.loads(eng.read_file(clar_json_path))
            json_rows = raw.get("rows", []) if isinstance(raw, dict) else None
            if isinstance(json_rows, list):
                if not all(isinstance(r, dict) for r in json_rows):
                    mirror_in_sync = False
                else:
                    normalized_json_rows = [eng.normalize_clar_row(r) for r in json_rows]
                    mirror_in_sync = sorted([row_key(r) for r in md_rows]) == sorted([row_key(r) for r in normalized_json_rows])
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            mirror_in_sync = False
    if args.strict and pending:
        hints = "\n".join([f"- {rid} {q}" for rid, q in pending[:20]])
        suffix = f"\nPending:\n{hints}" if hints else ""
        raise SystemExit("clarifications not closed" + suffix)
    eng.emit(
        args,
        f"clarifications pending: {len(pending)}",
        path=str(path),
        source_of_truth="markdown",
        mirror_in_sync=mirror_in_sync,
        pending=len(pending),
        pending_items=[{"id": rid, "question": q} for rid, q in pending],
    )


def cmd_sync_memory(args):
    dry_run = eng.is_dry_run(args)
    path = eng.resolve_path(args)
    if dry_run:
        meta = eng.sync_memory_snapshot(path, dry_run=True)
    else:
        with eng.requirement_write_lock(path, dry_run=False):
            meta = eng.sync_memory_snapshot(path, dry_run=False)
    eng.emit(
        args,
        f"memory synced: {path}",
        path=str(path),
        global_memory_hash=str(meta.get("global_memory_hash", "")),
        global_memory_exists=bool(meta.get("global_memory_exists", False)),
    )


def cmd_final_check(args):
    path = eng.resolve_path(args)
    write_back = not eng.is_dry_run(args)
    if write_back:
        with eng.requirement_write_lock(path, dry_run=False):
            issues = eng.final_check(path, write_back=True)
    else:
        issues = eng.final_check(path, write_back=False)
    eng.emit(args, f"final-check issues: {len(issues)}", issues=len(issues), path=str(path))


def cmd_copy_rules(args):
    dry_run = eng.is_dry_run(args)
    dest = Path(args.dest) if args.dest else (eng.ROOT / ".cursor" / "rules")
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)
    src = eng.ROOT / "rules"
    allowlist = eng.CONFIG.get("rules_copy_allowlist") or []
    copied_count = 0
    for item in src.glob("*.mdc"):
        if item.name not in allowlist:
            continue
        target = dest / item.name
        if dry_run:
            eng.runtime_log(f"[dry-run] would copy rule: {item.name} -> {target}")
        else:
            target.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")
        copied_count += 1
    warning = ""
    if not allowlist:
        warning = "rules_copy_allowlist is empty, nothing copied"
    eng.emit(
        args,
        f"copied rules to: {dest}",
        dest=str(dest),
        allowlist_count=len(allowlist),
        copied_count=copied_count,
        warning=warning,
    )


def cmd_scan(args):
    dry_run = eng.is_dry_run(args)
    path = eng.resolve_path(args)
    analysis_path = path / eng.DOC_FILES["analysis"]
    if not analysis_path.exists():
        raise SystemExit("analysis file not found")
    modules = eng.scan_modules()
    block = "\n".join([f"- {m}" for m in modules]) if modules else "- 无"
    if dry_run:
        content = eng.read_file(analysis_path)
        updated = eng.replace_scan_block(content, block)
        if updated != content:
            eng.runtime_log(f"[dry-run] would update scan block: {analysis_path}")
    else:
        with eng.requirement_write_lock(path, dry_run=False):
            content = eng.read_file(analysis_path)
            updated = eng.replace_scan_block(content, block)
            if updated != content:
                eng.write_file(analysis_path, updated)
    eng.emit(args, f"scanned modules: {len(modules)}", modules=len(modules), path=str(analysis_path))


def cmd_inspect_db(args):
    dry_run = eng.is_dry_run(args)
    path = eng.resolve_path(args)
    analysis_path = path / eng.DOC_FILES["analysis"]
    if not analysis_path.exists():
        raise SystemExit("analysis file not found")
    provided_connections = None
    if getattr(args, "db_connections_json", None):
        provided_connections = eng.parse_ai_db_connections_json(args.db_connections_json)

    if provided_connections is not None:
        connections = provided_connections
    else:
        connections = eng.load_ai_db_connections(path)
    summary = eng.build_db_schema_summary(eng.ai_db_connection_strings(connections))
    if dry_run:
        content = eng.read_file(analysis_path)
        updated = eng.replace_db_schema_block(content, summary)
        if updated != content:
            eng.runtime_log(f"[dry-run] would update db schema block: {analysis_path}")
    else:
        with eng.requirement_write_lock(path, dry_run=False):
            if provided_connections is not None:
                meta, meta_version = eng.load_metadata_file(path, with_version=True)
                meta[eng.AI_DB_CONNECTIONS_KEY] = provided_connections
                eng.save_metadata_file(path, meta, dry_run=False, expected_version=meta_version)
            content = eng.read_file(analysis_path)
            updated = eng.replace_db_schema_block(content, summary)
            if updated != content:
                eng.write_file(analysis_path, updated)
    eng.emit(args, f"db inspected connections: {len(connections)}", connections=len(connections), path=str(analysis_path))


def cmd_subagent_init(args):
    dry_run = eng.is_dry_run(args)
    path = eng.resolve_path(args)
    if dry_run:
        state = eng.init_subagent_state(path, dry_run=True, reset=bool(getattr(args, "reset", False)))
    else:
        with eng.requirement_write_lock(path, dry_run=False):
            state = eng.init_subagent_state(path, dry_run=False, reset=bool(getattr(args, "reset", False)))
    stages = state.get("stages", {}) if isinstance(state.get("stages", {}), dict) else {}
    eng.emit(
        args,
        f"subagent state initialized: {path}",
        path=str(path),
        current_stage=state.get("current_stage", ""),
        stages={k: v.get("status", "") for k, v in stages.items()},
    )


def cmd_subagent_context(args):
    path = eng.resolve_path(args)
    with eng.requirement_write_lock(path, dry_run=False):
        context = eng.subagent_context(path, args.stage)
    eng.emit(
        args,
        f"subagent context ready: {context.get('stage', '')}",
        path=str(path),
        stage=context.get("stage", ""),
        target_sections=context.get("target_sections", []),
        must_keep_sections=context.get("must_keep_sections", []),
        reopen_reason=context.get("reopen_reason", ""),
        project_mode=context.get("project_mode", ""),
        clarification_focus=context.get("clarification_focus", {}),
        dependencies=context.get("dependencies", []),
        target_doc=context.get("target_doc", {}),
        clarifications=context.get("clarifications", {}),
        context=context,
    )


def cmd_subagent_stage(args):
    dry_run = eng.is_dry_run(args)
    path = eng.resolve_path(args)
    if dry_run:
        state = eng.update_subagent_stage(
            path=path,
            stage=args.stage,
            status=args.status,
            agent=args.agent or "",
            notes=args.notes or "",
            dry_run=True,
            force=bool(getattr(args, "force", False)),
        )
    else:
        with eng.requirement_write_lock(path, dry_run=False):
            state = eng.update_subagent_stage(
                path=path,
                stage=args.stage,
                status=args.status,
                agent=args.agent or "",
                notes=args.notes or "",
                dry_run=False,
                force=bool(getattr(args, "force", False)),
            )
    stages = state.get("stages", {}) if isinstance(state.get("stages", {}), dict) else {}
    stage_key = str(args.stage).strip().lower()
    stage_state = stages.get(stage_key, {})
    eng.emit(
        args,
        f"subagent stage updated: {stage_key}={stage_state.get('status', '')}",
        path=str(path),
        stage=stage_key,
        status=stage_state.get("status", ""),
        current_stage=state.get("current_stage", ""),
        last_reopen=state.get("last_reopen", {}),
        validation_errors=stage_state.get("validation_errors", []),
    )


def cmd_subagent_status(args):
    path = eng.resolve_path(args)
    normalize = bool(getattr(args, "normalize", False))
    if normalize:
        with eng.requirement_write_lock(path, dry_run=False):
            report = eng.subagent_status(path, normalize=True)
    else:
        report = eng.subagent_status(path, normalize=False)
    stages = report.get("stages", {}) if isinstance(report.get("stages", {}), dict) else {}
    if getattr(args, "json_output", False):
        eng.emit(
            args,
            "subagent status",
            path=str(path),
            current_stage=report.get("current_stage", ""),
            stale_stages=report.get("stale_stages", []),
            last_reopen=report.get("last_reopen", {}),
            stages=stages,
        )
        return
    print(f"requirement: {path}")
    print(f"current_stage: {report.get('current_stage', '')}")
    stale_stages = report.get("stale_stages", [])
    if stale_stages:
        print("stale_stages: " + ", ".join(stale_stages))
    last_reopen = report.get("last_reopen", {}) if isinstance(report.get("last_reopen", {}), dict) else {}
    if last_reopen.get("stage"):
        print(f"last_reopen: {last_reopen.get('stage')} ({last_reopen.get('reason', '')})")
    for stage in eng.SUBAGENT_STAGE_ORDER:
        state = stages.get(stage, {})
        print(f"- {stage}: {state.get('status', 'pending')} ({state.get('agent', '')})")


def build_parser():
    p = argparse.ArgumentParser(prog="spec_agent")
    p.add_argument("--json-output", action="store_true", help="print machine-readable json output")
    p.add_argument("--verbose", action="store_true", help="print additional details")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--name", help="requirement english name (optional; auto-generated when omitted)")
    p_init.add_argument("--title", help="requirement title")
    p_init.add_argument("--desc", help="original requirement text")
    p_init.add_argument("--desc-json", help="original requirement as json string")
    p_init.add_argument("--desc-file", help="path to requirement source file (.json/.md/.txt)")
    p_init.add_argument("--clarify", help="initial clarification text from user")
    p_init.add_argument("--db-connections-json", help="structured db connections identified by caller AI")
    p_init.add_argument(
        "--project-mode",
        choices=["auto", "greenfield", "existing"],
        default="auto",
        help="project context mode for clarification focus; auto infers from requirement text",
    )
    p_init.add_argument("--date", help="date (YYYY-MM-DD)")
    p_init.add_argument("--state-only", action="store_true", help="initialize metadata/state only; skip template doc generation")
    p_init.add_argument("--dry-run", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_list = sub.add_parser("list")
    p_list.set_defaults(func=cmd_list)

    p_set = sub.add_parser("set-active")
    p_set.add_argument("--name")
    p_set.add_argument("--path")
    p_set.add_argument("--dry-run", action="store_true")
    p_set.set_defaults(func=cmd_set_active)

    p_clar_check = sub.add_parser("check-clarifications")
    p_clar_check.add_argument("--name")
    p_clar_check.add_argument("--path")
    p_clar_check.add_argument("--strict", action="store_true", help="exit non-zero when unresolved clarification items exist")
    p_clar_check.set_defaults(func=cmd_check_clarifications)

    p_sync_mem = sub.add_parser("sync-memory")
    p_sync_mem.add_argument("--name")
    p_sync_mem.add_argument("--path")
    p_sync_mem.add_argument("--dry-run", action="store_true")
    p_sync_mem.set_defaults(func=cmd_sync_memory)

    p_check = sub.add_parser("final-check")
    p_check.add_argument("--name")
    p_check.add_argument("--path")
    p_check.add_argument("--dry-run", action="store_true")
    p_check.set_defaults(func=cmd_final_check)

    p_rules = sub.add_parser("copy-rules")
    p_rules.add_argument("--dest")
    p_rules.add_argument("--dry-run", action="store_true")
    p_rules.set_defaults(func=cmd_copy_rules)

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--name")
    p_scan.add_argument("--path")
    p_scan.add_argument("--dry-run", action="store_true")
    p_scan.set_defaults(func=cmd_scan)

    p_inspect = sub.add_parser("inspect-db")
    p_inspect.add_argument("--name")
    p_inspect.add_argument("--path")
    p_inspect.add_argument("--db-connections-json", help="structured db connections identified by caller AI")
    p_inspect.add_argument("--dry-run", action="store_true")
    p_inspect.set_defaults(func=cmd_inspect_db)

    p_sub_init = sub.add_parser("subagent-init")
    p_sub_init.add_argument("--name")
    p_sub_init.add_argument("--path")
    p_sub_init.add_argument("--reset", action="store_true", help="reset all stage states to pending")
    p_sub_init.add_argument("--dry-run", action="store_true")
    p_sub_init.set_defaults(func=cmd_subagent_init)

    p_sub_ctx = sub.add_parser("subagent-context")
    p_sub_ctx.add_argument("--name")
    p_sub_ctx.add_argument("--path")
    p_sub_ctx.add_argument("--stage", required=True, choices=eng.SUBAGENT_STAGE_ORDER)
    p_sub_ctx.set_defaults(func=cmd_subagent_context)

    p_sub_stage = sub.add_parser("subagent-stage")
    p_sub_stage.add_argument("--name")
    p_sub_stage.add_argument("--path")
    p_sub_stage.add_argument("--stage", required=True, choices=eng.SUBAGENT_STAGE_ORDER)
    p_sub_stage.add_argument("--status", required=True, choices=sorted(list(eng.SUBAGENT_STAGE_STATUSES)))
    p_sub_stage.add_argument("--agent", help="agent id for this stage update")
    p_sub_stage.add_argument("--notes", help="stage update notes")
    p_sub_stage.add_argument("--force", action="store_true", help="skip dependency/validation blockers")
    p_sub_stage.add_argument("--dry-run", action="store_true")
    p_sub_stage.set_defaults(func=cmd_subagent_stage)

    p_sub_status = sub.add_parser("subagent-status")
    p_sub_status.add_argument("--name")
    p_sub_status.add_argument("--path")
    p_sub_status.add_argument("--normalize", action="store_true", help="apply stale-stage normalization to metadata")
    p_sub_status.set_defaults(func=cmd_subagent_status)

    return p


def main():
    parser = build_parser()
    try:
        args = parser.parse_args(normalize_cli_args(sys.argv[1:]))
    except SystemExit as ex:
        wants_json = "--json-output" in sys.argv[1:]
        code = ex.code if isinstance(ex.code, int) else 1
        if wants_json and code != 0:
            message = "argument parsing failed"
            print(json.dumps({"message": message, "error": message, "ok": False}, ensure_ascii=False))
        raise
    eng.set_runtime_output(bool(getattr(args, "json_output", False)))
    eng.ensure_spec_dir()
    try:
        args.func(args)
    except SystemExit as ex:
        code = ex.code if isinstance(ex.code, int) else 1
        if getattr(args, "json_output", False) and code != 0:
            message = str(ex.code).strip() if not isinstance(ex.code, int) else "command failed"
            if not message:
                message = "command failed"
            print(json.dumps({"message": message, "error": message, "ok": False}, ensure_ascii=False))
            raise SystemExit(code)
        raise
    except Exception as ex:
        if getattr(args, "json_output", False):
            message = str(ex).strip() or ex.__class__.__name__
            print(json.dumps({"message": message, "error": message, "ok": False}, ensure_ascii=False))
            raise SystemExit(1)
        raise


if __name__ == "__main__":
    main()

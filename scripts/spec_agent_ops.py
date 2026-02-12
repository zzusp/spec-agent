#!/usr/bin/env python
import argparse
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
    date_str = args.date or eng.today_str()
    requested_name = (args.name or "").strip()
    if requested_name:
        req_name = requested_name
        path = eng.requirement_dir(date_str, req_name)
        if path.exists():
            raise SystemExit("requirement already exists")
    else:
        base_name = eng.auto_requirement_name(args.title, desc)
        req_name = eng.next_available_requirement_name(date_str, base_name)
        path = eng.requirement_dir(date_str, req_name)
    resolved_title = eng.auto_requirement_title(args.title, desc, req_name)
    if dry_run:
        eng.runtime_log(f"[dry-run] would initialize: {path}")
        return
    eng.init_docs(path, resolved_title, desc)
    if args.clarify:
        meta_path = path / "metadata.json"
        meta = eng.json.loads(eng.read_file(meta_path))
        meta["initial_clarifications"] = args.clarify
        eng.write_file(meta_path, eng.json.dumps(meta, ensure_ascii=False, indent=2))
    eng.set_active(path)
    eng.emit(
        args,
        f"initialized: {path}",
        path=str(path),
        name=req_name,
        title=resolved_title,
        auto_named=not bool(requested_name),
        auto_titled=not bool((args.title or "").strip()),
    )


def cmd_write_analysis(args):
    dry_run = eng.is_dry_run(args)
    path = eng.resolve_path(args)
    title, original_desc, extra = eng._meta_context(path)
    points = eng.split_requirement_points(original_desc)
    context_text = original_desc if not extra else f"{original_desc}\n{extra}"
    modules = eng.scan_modules()
    db_connections, _, _ = eng.extract_context_db_connections(context_text)
    eng.ensure_runtime_context_clarifications(path, context_text, dry_run=dry_run)
    rows = eng.load_clar_rows(path)
    analysis_source = original_desc
    if extra:
        analysis_source = f"{original_desc}\n\n补充澄清信息：\n{extra}"
    analysis = eng.build_analysis_doc(title, analysis_source, modules, points, eng.render_clarified(rows, "analysis"), db_connections)
    analysis = eng.replace_db_schema_block(analysis, eng.build_db_schema_summary(db_connections))
    eng.write_generated_doc(path / eng.DOC_FILES["analysis"], analysis, dry_run=dry_run)
    eng.ensure_seed_clarifications(path, "analysis", dry_run=dry_run)
    eng.emit(args, f"analysis written: {path / eng.DOC_FILES['analysis']}", file=str(path / eng.DOC_FILES["analysis"]))


def cmd_write_prd(args):
    dry_run = eng.is_dry_run(args)
    path = eng.resolve_path(args)
    title, desc, _extra = eng._meta_context(path)
    points = eng.split_requirement_points(desc)
    rows = eng.load_clar_rows(path)
    prd = eng.build_prd_doc(title, desc, points, eng.render_clarified(rows, "prd"))
    eng.write_generated_doc(path / eng.DOC_FILES["prd"], prd, dry_run=dry_run)
    eng.ensure_seed_clarifications(path, "prd", dry_run=dry_run)
    eng.emit(args, f"prd written: {path / eng.DOC_FILES['prd']}", file=str(path / eng.DOC_FILES["prd"]))


def cmd_write_tech(args):
    dry_run = eng.is_dry_run(args)
    path = eng.resolve_path(args)
    title, desc, _extra = eng._meta_context(path)
    points = eng.split_requirement_points(desc)
    modules = eng.scan_modules()
    rows = eng.load_clar_rows(path)
    tech = eng.build_tech_doc(title, path.name, points, modules, eng.render_clarified(rows, "tech"))
    eng.write_generated_doc(path / eng.DOC_FILES["tech"], tech, dry_run=dry_run)
    eng.ensure_seed_clarifications(path, "tech", dry_run=dry_run)
    eng.emit(args, f"tech written: {path / eng.DOC_FILES['tech']}", file=str(path / eng.DOC_FILES["tech"]))


def cmd_write_acceptance(args):
    dry_run = eng.is_dry_run(args)
    path = eng.resolve_path(args)
    title, desc, _extra = eng._meta_context(path)
    points = eng.split_requirement_points(desc)
    rows = eng.load_clar_rows(path)
    acc = eng.build_acceptance_doc(title, path.name, points, eng.render_clarified(rows, "acceptance"))
    eng.write_generated_doc(path / eng.DOC_FILES["acceptance"], acc, dry_run=dry_run)
    eng.ensure_seed_clarifications(path, "acceptance", dry_run=dry_run)
    eng.emit(args, f"acceptance written: {path / eng.DOC_FILES['acceptance']}", file=str(path / eng.DOC_FILES["acceptance"]))


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


def cmd_update(args):
    dry_run = eng.is_dry_run(args)
    path = eng.resolve_path(args)
    clar_path = path / eng.DOC_FILES["clarifications"]
    if clar_path.exists():
        rows = eng.load_clar_rows(path)
        if args.strict and eng.has_unconfirmed(rows):
            pending = eng.list_unconfirmed(rows)
            hints = "\n".join([f"- {rid} {q}" for rid, q in pending[:10]])
            suffix = f"\nPending:\n{hints}" if hints else ""
            raise SystemExit("clarifications not closed; confirm items or rerun without --strict" + suffix)
    title, original_desc, extra = eng._meta_context(path)
    points = eng.split_requirement_points(original_desc)
    context_text = original_desc if not extra else f"{original_desc}\n{extra}"
    modules = eng.scan_modules()
    db_connections, _, _ = eng.extract_context_db_connections(context_text)
    eng.ensure_runtime_context_clarifications(path, context_text, dry_run=dry_run)
    rows = eng.load_clar_rows(path)
    analysis_source = original_desc
    if extra:
        analysis_source = f"{original_desc}\n\n补充澄清信息：\n{extra}"
    analysis_doc = eng.build_analysis_doc(title, analysis_source, modules, points, eng.render_clarified(rows, "analysis"), db_connections)
    fresh_db_block = eng.build_db_schema_summary(db_connections)
    analysis_doc = eng.replace_db_schema_block(analysis_doc, fresh_db_block)
    analysis_path = path / eng.DOC_FILES["analysis"]
    if analysis_path.exists():
        existing_db_block = eng.extract_block(eng.read_file(analysis_path), eng.DB_SCHEMA_START, eng.DB_SCHEMA_END)
        if existing_db_block and "未执行数据库自动探查" not in existing_db_block:
            analysis_doc = eng.replace_db_schema_block(analysis_doc, existing_db_block)
    eng.write_generated_doc(analysis_path, analysis_doc, dry_run=dry_run)
    eng.write_generated_doc(path / eng.DOC_FILES["prd"], eng.build_prd_doc(title, original_desc, points, eng.render_clarified(rows, "prd")), dry_run=dry_run)
    eng.write_generated_doc(path / eng.DOC_FILES["tech"], eng.build_tech_doc(title, path.name, points, modules, eng.render_clarified(rows, "tech")), dry_run=dry_run)
    eng.write_generated_doc(path / eng.DOC_FILES["acceptance"], eng.build_acceptance_doc(title, path.name, points, eng.render_clarified(rows, "acceptance")), dry_run=dry_run)
    eng.ensure_seed_clarifications(path, "analysis", dry_run=dry_run)
    eng.ensure_seed_clarifications(path, "prd", dry_run=dry_run)
    eng.ensure_seed_clarifications(path, "tech", dry_run=dry_run)
    eng.ensure_seed_clarifications(path, "acceptance", dry_run=dry_run)
    issues = eng.final_check(path, write_back=not dry_run)
    eng.emit(args, f"updated: {path}", path=str(path), issues=len(issues))


def cmd_write_all(args):
    dry_run = eng.is_dry_run(args)
    path = eng.resolve_path(args)
    title, original_desc, extra = eng._meta_context(path)
    points = eng.split_requirement_points(original_desc)
    context_text = original_desc if not extra else f"{original_desc}\n{extra}"
    modules = eng.scan_modules()
    db_connections, _, _ = eng.extract_context_db_connections(context_text)

    eng.ensure_runtime_context_clarifications(path, context_text, dry_run=dry_run)
    rows = eng.load_clar_rows(path)

    analysis_source = original_desc if not extra else f"{original_desc}\n\n补充澄清信息：\n{extra}"
    analysis_doc = eng.build_analysis_doc(title, analysis_source, modules, points, eng.render_clarified(rows, "analysis"), db_connections)
    analysis_doc = eng.replace_db_schema_block(analysis_doc, eng.build_db_schema_summary(db_connections))
    eng.write_generated_doc(path / eng.DOC_FILES["analysis"], analysis_doc, dry_run=dry_run)

    eng.write_generated_doc(path / eng.DOC_FILES["prd"], eng.build_prd_doc(title, original_desc, points, eng.render_clarified(rows, "prd")), dry_run=dry_run)
    eng.write_generated_doc(path / eng.DOC_FILES["tech"], eng.build_tech_doc(title, path.name, points, modules, eng.render_clarified(rows, "tech")), dry_run=dry_run)
    eng.write_generated_doc(path / eng.DOC_FILES["acceptance"], eng.build_acceptance_doc(title, path.name, points, eng.render_clarified(rows, "acceptance")), dry_run=dry_run)

    eng.ensure_seed_clarifications(path, "analysis", dry_run=dry_run)
    eng.ensure_seed_clarifications(path, "prd", dry_run=dry_run)
    eng.ensure_seed_clarifications(path, "tech", dry_run=dry_run)
    eng.ensure_seed_clarifications(path, "acceptance", dry_run=dry_run)

    issues = eng.final_check(path, write_back=not dry_run)
    eng.emit(args, f"all docs written: {path}", path=str(path), issues=len(issues))


def cmd_final_check(args):
    path = eng.resolve_path(args)
    issues = eng.final_check(path, write_back=not eng.is_dry_run(args))
    eng.emit(args, f"final-check issues: {len(issues)}", issues=len(issues), path=str(path))


def cmd_copy_rules(args):
    dry_run = eng.is_dry_run(args)
    dest = Path(args.dest) if args.dest else (eng.ROOT / ".cursor" / "rules")
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)
    src = eng.ROOT / "rules"
    allowlist = eng.CONFIG.get("rules_copy_allowlist") or []
    for item in src.glob("*.mdc"):
        if item.name not in allowlist:
            continue
        target = dest / item.name
        if dry_run:
            eng.runtime_log(f"[dry-run] would copy rule: {item.name} -> {target}")
        else:
            target.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")
    eng.emit(args, f"copied rules to: {dest}", dest=str(dest), allowlist_count=len(allowlist))
    if not allowlist:
        eng.emit(args, "warning: rules_copy_allowlist is empty, nothing copied")


def cmd_scan(args):
    dry_run = eng.is_dry_run(args)
    path = eng.resolve_path(args)
    analysis_path = path / eng.DOC_FILES["analysis"]
    if not analysis_path.exists():
        raise SystemExit("analysis file not found")
    modules = eng.scan_modules()
    block = "\n".join([f"- {m}" for m in modules]) if modules else "- 无"
    content = eng.read_file(analysis_path)
    updated = eng.replace_scan_block(content, block)
    if updated != content and not dry_run:
        eng.write_file(analysis_path, updated)
    if updated != content and dry_run:
        eng.runtime_log(f"[dry-run] would update scan block: {analysis_path}")
    eng.emit(args, f"scanned modules: {len(modules)}", modules=len(modules), path=str(analysis_path))


def cmd_inspect_db(args):
    dry_run = eng.is_dry_run(args)
    path = eng.resolve_path(args)
    analysis_path = path / eng.DOC_FILES["analysis"]
    if not analysis_path.exists():
        raise SystemExit("analysis file not found")
    _title, desc, extra = eng._meta_context(path)
    context_parts = [desc]
    if extra:
        context_parts.append(extra)
    clar_path = path / eng.DOC_FILES["clarifications"]
    if clar_path.exists():
        context_parts.append(eng.read_file(clar_path))
    context_text = "\n".join(context_parts)
    connections, _files, _warnings = eng.extract_context_db_connections(context_text)
    summary = eng.build_db_schema_summary(connections)
    content = eng.read_file(analysis_path)
    updated = eng.replace_db_schema_block(content, summary)
    if updated != content and not dry_run:
        eng.write_file(analysis_path, updated)
    if updated != content and dry_run:
        eng.runtime_log(f"[dry-run] would update db schema block: {analysis_path}")
    eng.emit(args, f"db inspected connections: {len(connections)}", connections=len(connections), path=str(analysis_path))


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
    p_init.add_argument("--date", help="date (YYYY-MM-DD)")
    p_init.add_argument("--dry-run", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_list = sub.add_parser("list")
    p_list.set_defaults(func=cmd_list)

    p_set = sub.add_parser("set-active")
    p_set.add_argument("--name")
    p_set.add_argument("--path")
    p_set.add_argument("--dry-run", action="store_true")
    p_set.set_defaults(func=cmd_set_active)

    p_update = sub.add_parser("update")
    p_update.add_argument("--name")
    p_update.add_argument("--path")
    p_update.add_argument("--strict", action="store_true", help="block update if clarifications not confirmed")
    p_update.add_argument("--dry-run", action="store_true")
    p_update.set_defaults(func=cmd_update)

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
    p_inspect.add_argument("--dry-run", action="store_true")
    p_inspect.set_defaults(func=cmd_inspect_db)

    p_all = sub.add_parser("write-all")
    p_all.add_argument("--name")
    p_all.add_argument("--path")
    p_all.add_argument("--dry-run", action="store_true")
    p_all.set_defaults(func=cmd_write_all)

    p_analysis = sub.add_parser("write-analysis")
    p_analysis.add_argument("--name")
    p_analysis.add_argument("--path")
    p_analysis.add_argument("--dry-run", action="store_true")
    p_analysis.set_defaults(func=cmd_write_analysis)

    p_prd = sub.add_parser("write-prd")
    p_prd.add_argument("--name")
    p_prd.add_argument("--path")
    p_prd.add_argument("--dry-run", action="store_true")
    p_prd.set_defaults(func=cmd_write_prd)

    p_tech = sub.add_parser("write-tech")
    p_tech.add_argument("--name")
    p_tech.add_argument("--path")
    p_tech.add_argument("--dry-run", action="store_true")
    p_tech.set_defaults(func=cmd_write_tech)

    p_acceptance = sub.add_parser("write-acceptance")
    p_acceptance.add_argument("--name")
    p_acceptance.add_argument("--path")
    p_acceptance.add_argument("--dry-run", action="store_true")
    p_acceptance.set_defaults(func=cmd_write_acceptance)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args(normalize_cli_args(sys.argv[1:]))
    eng.set_runtime_output(bool(getattr(args, "json_output", False)))
    eng.ensure_spec_dir()
    args.func(args)


if __name__ == "__main__":
    main()


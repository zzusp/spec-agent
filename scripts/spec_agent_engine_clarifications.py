#!/usr/bin/env python
from __future__ import annotations

import re
from pathlib import Path

import spec_agent_engine_core as core


def load_clar_rows(path: Path, sync: bool = False):
    md_rows, js_rows = load_clar_rows_pair(path)
    clar_path = path / core.DOC_FILES["clarifications"]
    clar_json_path = path / core.DOC_FILES["clarifications_json"]
    # Markdown is the single source of truth for clarifications.
    if clar_path.exists():
        if sync:
            core.save_clar_rows_to_json(clar_json_path, md_rows)
        return md_rows
    # Backward-compat fallback for legacy requirements without markdown file.
    if js_rows:
        core.runtime_log("[warn] clarifications markdown missing; fallback to json mirror", stderr=True)
        return js_rows
    return []


def load_clar_rows_pair(path: Path) -> tuple[list[dict], list[dict]]:
    clar_path = path / core.DOC_FILES["clarifications"]
    clar_json_path = path / core.DOC_FILES["clarifications_json"]
    if not clar_path.exists() and not clar_json_path.exists():
        raise SystemExit("clarifications files not found")

    md_rows = []
    if clar_path.exists():
        md_rows, _ = core.parse_clarifications_table(core.read_file(clar_path))
        md_rows = [core.normalize_clar_row(r) for r in md_rows]
    js_rows = core.load_clar_rows_from_json(clar_json_path)
    return md_rows, js_rows


def _find_table_indices(lines):
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "ID" in line and "状态" in line:
            header_idx = i
            break
    if header_idx is None:
        return None, None, []
    header_cells = core.split_md_row(lines[header_idx])
    sep_idx = header_idx + 1 if header_idx + 1 < len(lines) else None
    return header_idx, sep_idx, header_cells


def add_clarifications(clar_content: str, new_items):
    lines = clar_content.splitlines()
    header_idx, sep_idx, header_cells = _find_table_indices(lines)
    if header_idx is None or sep_idx is None:
        rows, _ = core.parse_clarifications_table(clar_content)
        rows = [core.normalize_clar_row(r) for r in rows]
        existing_questions = set(r.get("question", "") for r in rows)
        for item in new_items:
            if item["question"] in existing_questions:
                continue
            merged = core.normalize_clar_row(item)
            if not merged.get("status"):
                merged["status"] = "待确认"
            rows.append(merged)
        if not rows:
            return clar_content
        core.runtime_log("[warn] clarification table format not found; rebuilt with standard columns", stderr=True)
        body = core.render_clarification_table_rows(rows, core.CLARIFY_COLUMNS)
        table = core._render_clarification_header() + "\n" + "\n".join(body)
        trimmed = clar_content.rstrip()
        section = "## 澄清项\n" + table + "\n"
        if "## 澄清项" in trimmed:
            return re.sub(r"## 澄清项[\s\S]*$", section.rstrip(), trimmed, flags=re.MULTILINE) + "\n"
        return trimmed + "\n\n" + section

    rows, _ = core.parse_clarifications_table(clar_content)
    existing_questions = set(r.get("question", "") for r in rows)

    def build_row(item):
        values = []
        for cell in header_cells:
            key = core._normalize_header(cell)
            if key == "status":
                values.append(core.escape_md_cell(item.get("status", "待确认")))
            else:
                values.append(core.escape_md_cell(item.get(key, "")))
        return "| " + " | ".join(values) + " |"

    body = []
    for item in new_items:
        if item["question"] in existing_questions:
            continue
        body.append(build_row(item))

    if not body:
        return clar_content

    insert_at = sep_idx + 1
    new_lines = lines[:insert_at] + body + lines[insert_at:]
    return "\n".join(new_lines) + "\n"


def persist_clarifications(path: Path, clar_content: str, dry_run: bool = False):
    clar_path = path / core.DOC_FILES["clarifications"]
    clar_json_path = path / core.DOC_FILES["clarifications_json"]
    rows, _ = core.parse_clarifications_table(clar_content)
    rows = [core.normalize_clar_row(r) for r in rows]
    if dry_run:
        core.runtime_log(f"[dry-run] would update: {clar_path}")
        core.runtime_log(f"[dry-run] would update: {clar_json_path}")
        return
    core.write_file(clar_path, clar_content)
    core.save_clar_rows_to_json(clar_json_path, rows)


def next_clarify_id(rows):
    max_id = 0
    for r in rows:
        m = re.match(r"C-(\d+)", r.get("id", ""))
        if m:
            max_id = max(max_id, int(m.group(1)))
    return f"C-{max_id + 1:03d}"


def ensure_runtime_context_clarifications(path: Path, db_connections: list[dict] | None = None, dry_run: bool = False):
    try:
        structured = core.normalize_ai_db_connections(db_connections or [])
    except SystemExit:
        structured = []
    if not structured:
        return
    clar_path = path / core.DOC_FILES["clarifications"]
    clar_content = core.read_file(clar_path)
    rows, _ = core.parse_clarifications_table(clar_content)
    max_id = 0
    for row in rows:
        m = re.match(r"C-(\d+)", row.get("id", ""))
        if m:
            max_id = max(max_id, int(m.group(1)))
    merged = "；".join([core.describe_ai_db_connection(c) for c in structured])
    new_items = [{
        "id": f"C-{max_id + 1:03d}",
        "status": core.CONFIRMED_STATUS,
        "priority": "高",
        "impact": "数据库",
        "doc": "analysis",
        "section": "需求上下文采集",
        "question": "调用端 AI 已提供结构化数据库连接信息，可用于分析阶段拉取库表结构。",
        "answer": merged,
        "solution": "分析阶段先连接数据库读取 schema，再更新需求覆盖矩阵与差距分析。",
    }]
    updated = add_clarifications(clar_content, new_items)
    if dry_run:
        core.runtime_log("[dry-run] would append runtime DB clarification")
        return
    persist_clarifications(path, updated, dry_run=False)

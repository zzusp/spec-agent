#!/usr/bin/env python
from __future__ import annotations

import spec_agent_engine_core as core


def revision_table_block(initial_date: str, initial_reviser: str = "初始化", initial_summary: str = "初始创建") -> str:
    """Generate revision table block (header + separator + initial row)."""
    return f"""
{core.REVISION_SECTION_TITLE}
{core.REVISION_TABLE_HEADER}
{core.REVISION_TABLE_SEP}
| {initial_date} | {initial_reviser} | {initial_summary} |
"""


def append_revision_row(doc_content: str, date: str, reviser: str, summary: str) -> str:
    """Append one row to revision table when present; no-op when missing."""
    if core.REVISION_SECTION_TITLE not in doc_content or core.REVISION_TABLE_SEP not in doc_content:
        return doc_content
    line = f"| {date} | {reviser} | {summary} |"
    parts = doc_content.split(core.REVISION_TABLE_SEP, 1)
    if len(parts) != 2:
        return doc_content
    after_sep = parts[1]
    lines = after_sep.split("\n")
    insert_at = 0
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if stripped.startswith("|") and stripped.endswith("|") and "|" in stripped[1:-1]:
            insert_at = i + 1
        elif stripped and not stripped.startswith("|"):
            break
    lines.insert(insert_at, line)
    return parts[0] + core.REVISION_TABLE_SEP + "\n".join(lines)

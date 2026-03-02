#!/usr/bin/env python
from __future__ import annotations

import json
from pathlib import Path


def load_default_config(defaults_file: Path) -> dict:
    if not defaults_file.exists():
        raise SystemExit(f"default config file not found: {defaults_file}")
    try:
        data = json.loads(defaults_file.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        raise SystemExit(f"invalid default config file: {defaults_file}")
    if not isinstance(data, dict):
        raise SystemExit(f"default config must be object: {defaults_file}")
    return data


def load_merged_config(defaults_file: Path, override_file: Path) -> dict:
    cfg = dict(load_default_config(defaults_file))
    if override_file.exists():
        try:
            loaded = json.loads(override_file.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                cfg.update({k: v for k, v in loaded.items() if v is not None})
        except json.JSONDecodeError:
            raise SystemExit(f"invalid config file: {override_file}")
    return cfg


def validate_config(cfg: dict, project_modes: set[str]):
    def ensure_positive_number(key: str):
        if key not in cfg:
            return
        val = cfg[key]
        if isinstance(val, bool) or not isinstance(val, (int, float)) or float(val) <= 0:
            raise SystemExit(f"config {key} must be positive number")

    def ensure_bool(key: str):
        if key not in cfg:
            return
        if not isinstance(cfg[key], bool):
            raise SystemExit(f"config {key} must be boolean")

    required_keys = {
        "spec_dir": str,
        "date_format": str,
        "placeholders": list,
        "prd_tech_words": list,
        "clarify_columns": list,
        "clarify_statuses": list,
        "clarify_confirmed_status": str,
    }
    for key, typ in required_keys.items():
        if key not in cfg:
            raise SystemExit(f"config missing key: {key}")
        if not isinstance(cfg[key], typ):
            raise SystemExit(f"config invalid type for {key}")

    must_columns = {"ID", "状态", "归属文档", "问题/待确认点"}
    if not must_columns.issubset(set(cfg["clarify_columns"])):
        raise SystemExit("config clarify_columns missing required columns")
    if not cfg["clarify_statuses"]:
        raise SystemExit("config clarify_statuses cannot be empty")
    if not cfg["clarify_confirmed_status"].strip():
        raise SystemExit("config clarify_confirmed_status cannot be empty")
    if "doc_clarify_seeds" in cfg and not isinstance(cfg["doc_clarify_seeds"], dict):
        raise SystemExit("config doc_clarify_seeds must be object")
    if "min_doc_bullets" in cfg:
        if not isinstance(cfg["min_doc_bullets"], dict):
            raise SystemExit("config min_doc_bullets must be object")
        for k, v in cfg["min_doc_bullets"].items():
            if k not in {"analysis", "prd", "tech", "acceptance"}:
                raise SystemExit(f"config min_doc_bullets invalid key: {k}")
            if not isinstance(v, int) or v < 0:
                raise SystemExit("config min_doc_bullets values must be non-negative integer")
    if "max_new_clarifications_per_round" in cfg:
        if not isinstance(cfg["max_new_clarifications_per_round"], int) or cfg["max_new_clarifications_per_round"] <= 0:
            raise SystemExit("config max_new_clarifications_per_round must be positive integer")
    if "dry_run_default" in cfg and not isinstance(cfg["dry_run_default"], bool):
        raise SystemExit("config dry_run_default must be boolean")
    if "default_project_mode" in cfg:
        mode_val = str(cfg["default_project_mode"]).strip().lower()
        if mode_val not in project_modes:
            raise SystemExit(f"config default_project_mode must be one of: {', '.join(sorted(project_modes))}")
    if "ai_judge_command" in cfg and not isinstance(cfg["ai_judge_command"], str):
        raise SystemExit("config ai_judge_command must be string")
    ensure_positive_number("ai_judge_timeout_sec")
    ensure_positive_number("metadata_lock_timeout_sec")
    ensure_positive_number("metadata_lock_poll_sec")
    ensure_positive_number("metadata_lock_stale_sec")
    ensure_positive_number("requirement_lock_timeout_sec")
    ensure_positive_number("requirement_lock_poll_sec")
    ensure_positive_number("requirement_lock_stale_sec")
    ensure_bool("enforce_final_check_agent_independence")

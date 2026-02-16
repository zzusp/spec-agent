#!/usr/bin/env python
from __future__ import annotations

import argparse
import datetime as dt
import errno
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from contextlib import contextmanager
from urllib.parse import unquote, urlparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "spec-agent.config.json"
RUNTIME_JSON_OUTPUT = False
METADATA_VERSION_KEY = "_meta_version"
AI_DB_CONNECTIONS_KEY = "ai_db_connections"

DEFAULT_CONFIG = {
    "spec_dir": "spec",
    "date_format": "%Y-%m-%d",
    "placeholders": ["TODO", "TBD", "待补充", "待确认", "（待）"],
    "prd_tech_words": ["数据库", "SQL", "表", "接口", "API", "代码", "架构", "技术方案", "实现"],
    "prd_tech_whitelist": ["数据库连接信息", "数据口径", "业务口径"],
    "clarify_columns": [
        "ID",
        "状态",
        "优先级",
        "影响范围",
        "归属文档",
        "关联章节",
        "问题/待确认点",
        "用户确认/补充",
        "解决方案",
    ],
    "clarify_statuses": ["待确认", "已确认"],
    "clarify_confirmed_status": "已确认",
    "enable_auto_seed_clarifications": True,
    "max_seed_questions_per_doc": 3,
    "doc_clarify_seeds": {},
    "min_doc_bullets": {
        "analysis": 8,
        "prd": 10,
        "tech": 10,
        "acceptance": 8,
    },
    "max_new_clarifications_per_round": 10,
    "dry_run_default": False,
    "default_project_mode": "existing",
    "rules_copy_allowlist": [],
    "metadata_lock_timeout_sec": 8.0,
    "metadata_lock_poll_sec": 0.05,
    "metadata_lock_stale_sec": 120.0,
    "requirement_lock_timeout_sec": 8.0,
    "requirement_lock_poll_sec": 0.05,
    "requirement_lock_stale_sec": 120.0,
}

PROJECT_MODES = {"greenfield", "existing"}
DB_TYPE_ALIASES = {
    "mysql": "mysql",
    "mariadb": "mysql",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "pgsql": "postgresql",
    "pg": "postgresql",
    "sqlite": "sqlite",
}
DB_DEFAULT_PORT = {
    "mysql": 3306,
    "postgresql": 5432,
}

DOC_FILES = {
    "clarifications": "00-clarifications.md",
    "clarifications_json": "00-clarifications.json",
    "analysis": "01-analysis.md",
    "prd": "02-prd.md",
    "tech": "03-tech.md",
    "acceptance": "04-acceptance.md",
}

CLARIFY_START = "<!-- CLARIFICATIONS:START -->"
CLARIFY_END = "<!-- CLARIFICATIONS:END -->"
SCAN_START = "<!-- SCAN:START -->"
SCAN_END = "<!-- SCAN:END -->"
DB_SCHEMA_START = "<!-- DB-SCHEMA:START -->"
DB_SCHEMA_END = "<!-- DB-SCHEMA:END -->"
DEP_SIG_START = "<!-- DEPENDENCY-SIGNATURE:START -->"
DEP_SIG_END = "<!-- DEPENDENCY-SIGNATURE:END -->"

SUBAGENT_STAGE_ORDER = ["analysis", "prd", "tech", "acceptance", "final_check"]
SUBAGENT_STAGE_DEPENDENCIES = {
    "analysis": [],
    "prd": ["analysis"],
    "tech": ["analysis", "prd"],
    "acceptance": ["analysis", "prd", "tech"],
    "final_check": ["analysis", "prd", "tech", "acceptance"],
}
SUBAGENT_STAGE_DOC_MAP = {
    "analysis": "analysis",
    "prd": "prd",
    "tech": "tech",
    "acceptance": "acceptance",
}
SUBAGENT_STAGE_STATUSES = {"pending", "running", "completed", "failed"}
SUBAGENT_REOPEN_ORDER = ["analysis", "prd", "tech", "acceptance"]
FINAL_CHECK_DOC_STAGE_MAP = {
    "analysis": "analysis",
    "prd": "prd",
    "tech": "tech",
    "acceptance": "acceptance",
    "global": "analysis",
}
SUBAGENT_STAGE_SECTION_HINTS = {
    "analysis": {
        "target_sections": [
            "## 原始需求",
            "## 需求上下文采集",
            "## 项目现状与相关模块",
            "## 候选模块扫描",
            "## 数据库现状",
            "## 需求覆盖矩阵",
            "## 需求满足性分析",
            "## 风险与影响",
            "## 结论",
            "## 全局记忆约束",
            "## 澄清补充",
        ],
        "must_keep_sections": [
            "## 原始需求",
            "## 需求覆盖矩阵",
            "## 全局记忆约束",
            "## 澄清补充",
            SCAN_START,
            SCAN_END,
            DB_SCHEMA_START,
            DB_SCHEMA_END,
            CLARIFY_START,
            CLARIFY_END,
        ],
    },
    "prd": {
        "target_sections": [
            "## 需求范围与边界",
            "## 简要说明",
            "## 产品功能描述与业务流程",
            "## 分支流程与异常处理",
            "## 非功能性需求",
            "## 待确认需求点",
            "## 冲突与影响",
            "## 全局记忆约束",
            "## 澄清补充",
        ],
        "must_keep_sections": [
            "## 需求范围与边界",
            "## 非功能性需求",
            "## 全局记忆约束",
            "## 澄清补充",
            CLARIFY_START,
            CLARIFY_END,
            DEP_SIG_START,
            DEP_SIG_END,
        ],
    },
    "tech": {
        "target_sections": [
            "## 当前项目/功能情况",
            "## 实现目标",
            "## 整体架构设计思路",
            "## 架构图",
            "## 数据库设计",
            "## 可执行 SQL",
            "## 核心功能代码片段",
            "## 单元测试",
            "## 数据迁移与回滚策略",
            "## 注意事项",
            "## 全局记忆约束",
            "## 澄清补充",
        ],
        "must_keep_sections": [
            "## 数据库设计",
            "## 可执行 SQL",
            "## 数据迁移与回滚策略",
            "## 全局记忆约束",
            "## 澄清补充",
            CLARIFY_START,
            CLARIFY_END,
            DEP_SIG_START,
            DEP_SIG_END,
        ],
    },
    "acceptance": {
        "target_sections": [
            "## 验收项清单",
            "## 验收计划与步骤",
            "## 受影响功能验证",
            "## 数据库核对指引",
            "## 全局记忆约束",
            "## 澄清补充",
        ],
        "must_keep_sections": [
            "## 验收项清单",
            "## 验收计划与步骤",
            "## 全局记忆约束",
            "## 澄清补充",
            CLARIFY_START,
            CLARIFY_END,
            DEP_SIG_START,
            DEP_SIG_END,
        ],
    },
    "final_check": {
        "target_sections": [],
        "must_keep_sections": [],
    },
}

HEADER_KEY_MAP = {
    "ID": "id",
    "状态": "status",
    "优先级": "priority",
    "影响范围": "impact",
    "归属文档": "doc",
    "关联章节": "section",
    "问题/待确认点": "question",
    "用户确认/补充": "answer",
    "解决方案": "solution",
}
SECTION_HEADING_RE = re.compile(r"^## .+$", re.MULTILINE)


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                cfg.update({k: v for k, v in loaded.items() if v is not None})
        except json.JSONDecodeError:
            raise SystemExit("invalid spec-agent.config.json")
    return cfg


CONFIG = load_config()
def validate_config(cfg):
    def ensure_positive_number(key: str):
        if key not in cfg:
            return
        val = cfg[key]
        if isinstance(val, bool) or not isinstance(val, (int, float)) or float(val) <= 0:
            raise SystemExit(f"config {key} must be positive number")

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
        if mode_val not in PROJECT_MODES:
            raise SystemExit(f"config default_project_mode must be one of: {', '.join(sorted(PROJECT_MODES))}")
    ensure_positive_number("metadata_lock_timeout_sec")
    ensure_positive_number("metadata_lock_poll_sec")
    ensure_positive_number("metadata_lock_stale_sec")
    ensure_positive_number("requirement_lock_timeout_sec")
    ensure_positive_number("requirement_lock_poll_sec")
    ensure_positive_number("requirement_lock_stale_sec")


validate_config(CONFIG)

SPEC_DIR = Path(CONFIG["spec_dir"]).expanduser()
if not SPEC_DIR.is_absolute():
    SPEC_DIR = ROOT / SPEC_DIR
ACTIVE_FILE = SPEC_DIR / ".active"
GLOBAL_MEMORY_FILE = SPEC_DIR / "00-global-memory.md"

PLACEHOLDERS = CONFIG["placeholders"]
PLACEHOLDERS_EFFECTIVE = [p for p in PLACEHOLDERS if p != "待确认"]
PRD_TECH_WORDS = CONFIG["prd_tech_words"]
PRD_TECH_WORDS_EFFECTIVE = [w for w in PRD_TECH_WORDS if len(w.strip()) > 1]
PRD_TECH_WHITELIST = [str(x) for x in CONFIG.get("prd_tech_whitelist", [])]
CLARIFY_COLUMNS = CONFIG["clarify_columns"]
CLARIFY_STATUSES = set(CONFIG["clarify_statuses"])
CONFIRMED_STATUS = str(CONFIG.get("clarify_confirmed_status", "已确认")).strip() or "已确认"
CLARIFY_STATUSES.add(CONFIRMED_STATUS)
ENABLE_AUTO_SEEDS = bool(CONFIG.get("enable_auto_seed_clarifications", True))
MAX_SEED_PER_DOC = int(CONFIG.get("max_seed_questions_per_doc", 3))
MIN_DOC_BULLETS = CONFIG.get("min_doc_bullets", {}) if isinstance(CONFIG.get("min_doc_bullets", {}), dict) else {}
MAX_NEW_CLARIFICATIONS_PER_ROUND = int(CONFIG.get("max_new_clarifications_per_round", 10))
DRY_RUN_DEFAULT = bool(CONFIG.get("dry_run_default", False))
METADATA_LOCK_TIMEOUT_SEC = float(CONFIG.get("metadata_lock_timeout_sec", DEFAULT_CONFIG["metadata_lock_timeout_sec"]))
METADATA_LOCK_POLL_SEC = float(CONFIG.get("metadata_lock_poll_sec", DEFAULT_CONFIG["metadata_lock_poll_sec"]))
METADATA_LOCK_STALE_SEC = float(CONFIG.get("metadata_lock_stale_sec", DEFAULT_CONFIG["metadata_lock_stale_sec"]))
REQUIREMENT_LOCK_TIMEOUT_SEC = float(CONFIG.get("requirement_lock_timeout_sec", DEFAULT_CONFIG["requirement_lock_timeout_sec"]))
REQUIREMENT_LOCK_POLL_SEC = float(CONFIG.get("requirement_lock_poll_sec", DEFAULT_CONFIG["requirement_lock_poll_sec"]))
REQUIREMENT_LOCK_STALE_SEC = float(CONFIG.get("requirement_lock_stale_sec", DEFAULT_CONFIG["requirement_lock_stale_sec"]))

DOC_CLARIFY_SEEDS = {
    "analysis": [
        "请提供数据库连接信息（地址、库名、账号权限范围），用于完成现状核对。",
        "请确认当前需求涉及的核心模块/入口，是否与扫描结果一致。",
        "请确认关键业务状态及其含义，避免分析口径偏差。",
    ],
    "prd": [
        "请确认本期需求范围边界（明确不做项）。",
        "请确认业务成功标准与失败定义。",
        "请确认涉及角色与权限边界。",
    ],
    "tech": [
        "请确认上线窗口、回滚时限与变更冻结要求。",
        "请确认非功能性目标（性能、可用性、安全）最低标准。",
        "请确认外部依赖与接口 SLA 约束。",
    ],
    "acceptance": [
        "请确认验收环境与测试数据准备方式。",
        "请确认验收责任人及通过标准。",
        "请确认受影响功能的回归范围。",
    ],
}
if isinstance(CONFIG.get("doc_clarify_seeds"), dict):
    for key, value in CONFIG["doc_clarify_seeds"].items():
        if key in DOC_CLARIFY_SEEDS and isinstance(value, list):
            DOC_CLARIFY_SEEDS[key] = [str(v) for v in value]


def ensure_spec_dir():
    SPEC_DIR.mkdir(parents=True, exist_ok=True)


def today_str():
    return dt.date.today().strftime(CONFIG["date_format"])


def requirement_dir(date_str: str, name: str) -> Path:
    return SPEC_DIR / date_str / name


def normalize_project_mode(mode: str | None) -> str:
    mode_raw = str(mode or "").strip().lower()
    if mode_raw in {"", "auto"}:
        return ""
    alias = {
        "greenfield": "greenfield",
        "new": "greenfield",
        "new_project": "greenfield",
        "new-project": "greenfield",
        "from_scratch": "greenfield",
        "from-scratch": "greenfield",
        "existing": "existing",
        "existing_project": "existing",
        "existing-project": "existing",
        "incremental": "existing",
        "brownfield": "existing",
    }
    if not mode_raw:
        return ""
    mapped = alias.get(mode_raw, mode_raw)
    if mapped not in PROJECT_MODES:
        allowed = ", ".join(sorted(PROJECT_MODES))
        raise SystemExit(f"invalid project mode: {mode} (allowed: {allowed})")
    return mapped


def infer_project_mode(*texts: str) -> str:
    text = "\n".join([str(t or "") for t in texts]).lower()
    if not text.strip():
        return ""
    greenfield_hits = 0
    existing_hits = 0
    greenfield_keywords = [
        "从零",
        "从 0",
        "0到1",
        "零到一",
        "全新项目",
        "新建项目",
        "新系统",
        "新搭建",
        "greenfield",
        "from scratch",
    ]
    existing_keywords = [
        "已有项目",
        "现有项目",
        "存量项目",
        "新增需求",
        "增量需求",
        "迭代",
        "基于现有",
        "在现有",
        "兼容现有",
        "existing",
        "brownfield",
    ]
    for kw in greenfield_keywords:
        if kw in text:
            greenfield_hits += 1
    for kw in existing_keywords:
        if kw in text:
            existing_hits += 1
    if greenfield_hits > existing_hits:
        return "greenfield"
    if existing_hits > greenfield_hits:
        return "existing"
    return ""


def resolve_project_mode(requirement_text: str, clarify_text: str = "", requested_mode: str | None = None) -> str:
    try:
        requested = normalize_project_mode(requested_mode)
    except SystemExit:
        requested = ""
    if requested:
        return requested
    inferred = infer_project_mode(requirement_text, clarify_text)
    if inferred:
        return inferred
    default_mode = normalize_project_mode(str(CONFIG.get("default_project_mode", "existing")))
    return default_mode or "existing"


def clarification_focus_by_project_mode(mode: str) -> dict:
    mode_norm = normalize_project_mode(mode) or "existing"
    if mode_norm == "greenfield":
        return {
            "mode": "greenfield",
            "strategy": "从零建设，默认全量澄清关键约束",
            "primary_topics": [
                "业务目标与边界",
                "系统边界与上下游",
                "架构与模块划分",
                "开发语言/框架/数据库选型",
                "性能容量与扩展性目标",
                "部署拓扑与环境策略",
                "安全与合规基线",
                "可观测性与运维值守",
                "测试策略与验收口径",
            ],
            "conditional_topics": [],
            "skip_rule": "仅跳过已被明确确认且不会影响方案闭环的项",
        }
    return {
        "mode": "existing",
        "strategy": "存量迭代，优先聚焦需求与技术改动影响",
        "primary_topics": [
            "需求范围与业务规则变化",
            "受影响模块/接口/数据流",
            "技术方案与改造边界",
            "数据变更与迁移回滚",
            "回归范围与验收口径",
        ],
        "conditional_topics": [
            "性能",
            "部署",
            "安全",
            "框架/语言/数据库选型",
        ],
        "skip_rule": "对既有稳定基线默认复用，仅在需求或方案明确触发时进入澄清",
    }


def _slugify_name(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:64].strip("-")


def _is_connection_or_path_line(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if re.search(r"(sqlite|mysql|postgres|postgresql|mongodb|redis)://", t):
        return True
    if re.search(r"\b(db|database)\b.*\b(url|uri|host|port|path|conn)\b", t):
        return True
    if re.search(r"[a-z]:\\", t):
        return True
    if re.search(r"\.(env|ini|cfg|conf|yaml|yml|json|txt)\b", t):
        return True
    return False


def _extract_business_hint_lines(text: str) -> list[str]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return [ln for ln in lines if not _is_connection_or_path_line(ln)]


def _name_from_keyword_map(text: str) -> str:
    mapping = [
        ("退款", "refund"),
        ("订单", "order"),
        ("支付", "payment"),
        ("审核", "review"),
        ("审批", "approve"),
        ("驳回", "reject"),
        ("财务", "finance"),
        ("打款", "payout"),
        ("日志", "log"),
        ("状态", "status"),
        ("流程", "flow"),
        ("用户", "user"),
        ("权限", "permission"),
    ]
    tokens = []
    seen = set()
    for cn, en in mapping:
        if cn in (text or "") and en not in seen:
            seen.add(en)
            tokens.append(en)
    if not tokens:
        return ""
    if "flow" not in seen:
        tokens.append("flow")
    return "-".join(tokens[:6])


def auto_requirement_name(title: str | None, requirement_text: str) -> str:
    hint_lines = _extract_business_hint_lines(requirement_text)
    candidates = [title or ""]
    if hint_lines:
        candidates.append(hint_lines[0])
        candidates.extend(hint_lines[1:4])
        candidates.append(" ".join(hint_lines[:8]))
    for raw in candidates:
        name = _slugify_name(raw)
        if name:
            return name
    mapped = _slugify_name(_name_from_keyword_map(requirement_text))
    if mapped:
        return mapped
    digest = hashlib.md5((requirement_text or "requirement").encode("utf-8")).hexdigest()[:8]
    return f"req-{today_str().replace('-', '')}-{digest}"


def next_available_requirement_name(date_str: str, base_name: str) -> str:
    candidate = base_name
    idx = 2
    while requirement_dir(date_str, candidate).exists():
        candidate = f"{base_name}-{idx}"
        idx += 1
    return candidate


def auto_requirement_title(title: str | None, requirement_text: str, fallback_name: str) -> str:
    if (title or "").strip():
        return str(title).strip()
    lines = [ln.strip() for ln in (requirement_text or "").splitlines() if ln.strip()]
    if lines:
        first = re.sub(r"^[-*+\d\.\)\s]+", "", lines[0]).strip()
        if first:
            return first[:64]
    return fallback_name


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_file_atomic(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(str(tmp_path), str(path))
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError as ex:
                runtime_log(f"[warn] failed to remove temp file: {tmp_path} ({ex})", stderr=True)


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _metadata_path(path: Path) -> Path:
    return path / "metadata.json"


def _metadata_lock_path(meta_path: Path) -> Path:
    return Path(str(meta_path) + ".lock")


def _requirement_lock_path(path: Path) -> Path:
    return path.parent / f".{path.name}.lock"


def _metadata_version(meta: dict) -> int:
    raw = meta.get(METADATA_VERSION_KEY, 0)
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return 0
    return val if val >= 0 else 0


def _process_start_signature(pid: int | None) -> str:
    if not pid or pid <= 0:
        return ""
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.exists():
        try:
            raw = proc_stat.read_text(encoding="utf-8", errors="ignore")
            parts = raw.split()
            if len(parts) > 21:
                return parts[21]
        except OSError:
            pass
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            text = " ".join(proc.stdout.strip().split())
            return text
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def _read_lock_owner(lock_path: Path) -> tuple[int | None, str]:
    try:
        raw = lock_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None, ""
    if not raw:
        return None, ""
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            pid_raw = data.get("pid")
            start = str(data.get("start", "")).strip()
            pid = int(pid_raw) if pid_raw is not None else None
            return pid, start
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    if "|" in raw:
        pid_part, start_part = raw.split("|", 1)
        try:
            return int(pid_part.strip()), start_part.strip()
        except ValueError:
            return None, ""
    try:
        return int(raw), ""
    except ValueError:
        return None, ""


def _read_metadata_from_path(meta_path: Path) -> dict:
    if not meta_path.exists():
        raise SystemExit("metadata.json not found, run init first")
    try:
        data = json.loads(read_file(meta_path))
    except json.JSONDecodeError:
        raise SystemExit("invalid metadata.json")
    if not isinstance(data, dict):
        raise SystemExit("invalid metadata.json")
    return data


def _acquire_file_lock(lock_path: Path, timeout_sec: float, poll_sec: float, stale_sec: float, lock_name: str):
    def pid_running(pid: int | None) -> bool:
        if not pid or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError as ex:
            if ex.errno == errno.ESRCH:
                return False
            if ex.errno == errno.EPERM:
                return True
            return True

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            payload = {
                "pid": os.getpid(),
                "start": _process_start_signature(os.getpid()),
            }
            os.write(fd, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            os.close(fd)
            return
        except FileExistsError:
            owner_pid, owner_start_sig = _read_lock_owner(lock_path)
            owner_running = pid_running(owner_pid)
            owner_current_start_sig = _process_start_signature(owner_pid) if owner_running else ""
            try:
                mtime = lock_path.stat().st_mtime
                if (time.time() - mtime) > stale_sec:
                    # Reclaim stale lock only when owner process is not alive.
                    if not owner_running:
                        try:
                            lock_path.unlink()
                        except FileNotFoundError:
                            pass
                        continue
                    # Reclaim stale lock when PID was reused by a different process instance.
                    if owner_start_sig and owner_current_start_sig and owner_start_sig != owner_current_start_sig:
                        try:
                            lock_path.unlink()
                        except FileNotFoundError:
                            pass
                        continue
            except OSError:
                pass
            if (time.time() - start) > timeout_sec:
                raise SystemExit(f"{lock_name} lock timeout")
            time.sleep(poll_sec)


def _release_file_lock(lock_path: Path):
    try:
        if not lock_path.exists():
            return
        owner_pid, owner_start_sig = _read_lock_owner(lock_path)
        if owner_pid and owner_pid != os.getpid():
            return
        if owner_start_sig:
            current_sig = _process_start_signature(os.getpid())
            if current_sig and current_sig != owner_start_sig:
                return
        if owner_pid is None and owner_start_sig:
            return
        lock_path.unlink()
    except FileNotFoundError:
        return
    except OSError as ex:
        runtime_log(f"[warn] failed to release lock: {lock_path} ({ex})", stderr=True)
        return


def _acquire_metadata_lock(lock_path: Path):
    _acquire_file_lock(
        lock_path,
        timeout_sec=METADATA_LOCK_TIMEOUT_SEC,
        poll_sec=METADATA_LOCK_POLL_SEC,
        stale_sec=METADATA_LOCK_STALE_SEC,
        lock_name="metadata",
    )


def _release_metadata_lock(lock_path: Path):
    _release_file_lock(lock_path)


def _acquire_requirement_lock(lock_path: Path):
    _acquire_file_lock(
        lock_path,
        timeout_sec=REQUIREMENT_LOCK_TIMEOUT_SEC,
        poll_sec=REQUIREMENT_LOCK_POLL_SEC,
        stale_sec=REQUIREMENT_LOCK_STALE_SEC,
        lock_name="requirement",
    )


def _release_requirement_lock(lock_path: Path):
    _release_file_lock(lock_path)


@contextmanager
def requirement_write_lock(path: Path, dry_run: bool = False):
    lock_path = _requirement_lock_path(path)
    if dry_run:
        runtime_log(f"[dry-run] would acquire requirement lock: {lock_path}")
        yield
        return
    _acquire_requirement_lock(lock_path)
    try:
        yield
    finally:
        _release_requirement_lock(lock_path)


def load_metadata_file(path: Path, with_version: bool = False):
    meta_path = _metadata_path(path)
    data = _read_metadata_from_path(meta_path)
    version = _metadata_version(data)
    if with_version:
        return data, version
    return data


def save_metadata_file(path: Path, meta: dict, dry_run: bool = False, expected_version: int | None = None):
    meta_path = _metadata_path(path)
    if dry_run:
        runtime_log(f"[dry-run] would update: {meta_path}")
        return _metadata_version(meta)
    lock_path = _metadata_lock_path(meta_path)
    _acquire_metadata_lock(lock_path)
    try:
        disk_meta = _read_metadata_from_path(meta_path)
        disk_version = _metadata_version(disk_meta)
        if expected_version is not None and int(expected_version) != disk_version:
            raise SystemExit(f"metadata version conflict: expected={expected_version}, current={disk_version}")
        next_version = disk_version + 1
        if not isinstance(meta, dict):
            raise SystemExit("metadata payload must be object")
        payload = dict(meta)
        payload[METADATA_VERSION_KEY] = next_version
        write_file_atomic(meta_path, json.dumps(payload, ensure_ascii=False, indent=2))
        meta.clear()
        meta.update(payload)
        return next_version
    finally:
        _release_metadata_lock(lock_path)


def emit(args, message: str, **data):
    if getattr(args, "json_output", False):
        payload = {"ok": True, "message": message}
        payload.update(data)
        print(json.dumps(payload, ensure_ascii=False))
        return
    print(message)
    if getattr(args, "verbose", False):
        for k, v in data.items():
            print(f"{k}: {v}")


def set_runtime_output(json_output: bool = False):
    global RUNTIME_JSON_OUTPUT
    RUNTIME_JSON_OUTPUT = bool(json_output)


def runtime_log(message: str, *, stderr: bool = False):
    if RUNTIME_JSON_OUTPUT:
        return
    target = sys.stderr if stderr else sys.stdout
    print(message, file=target)


def is_dry_run(args) -> bool:
    return bool(getattr(args, "dry_run", False) or DRY_RUN_DEFAULT)


def _flatten_requirement_obj(data) -> str:
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(_flatten_requirement_obj(item))
            else:
                lines.append(str(item).strip())
        return "\n".join([f"- {x}" for x in lines if x])
    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{key}:")
                nested = _flatten_requirement_obj(value)
                for ln in nested.splitlines():
                    lines.append(f"  {ln}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)
    return str(data).strip()


def parse_requirement_input(args) -> str:
    has_desc = bool(getattr(args, "desc", None))
    has_desc_json = bool(getattr(args, "desc_json", None))
    has_desc_file = bool(getattr(args, "desc_file", None))
    selected = int(has_desc) + int(has_desc_json) + int(has_desc_file)
    if selected == 0:
        raise SystemExit("init requires one of --desc, --desc-json, --desc-file")
    if selected > 1:
        raise SystemExit("init accepts exactly one input source: --desc or --desc-json or --desc-file")

    if has_desc:
        text = str(args.desc).strip()
        if not text:
            raise SystemExit("--desc cannot be empty")
        return text

    if has_desc_json:
        try:
            data = json.loads(args.desc_json)
        except (json.JSONDecodeError, TypeError, ValueError) as ex:
            raise SystemExit(f"invalid --desc-json: {ex}")
        text = _flatten_requirement_obj(data).strip()
        if not text:
            raise SystemExit("--desc-json cannot be empty")
        return text

    fp = Path(args.desc_file)
    if not fp.is_absolute():
        fp = (ROOT / fp).resolve()
    if not fp.exists():
        raise SystemExit(f"desc file not found: {fp}")
    raw = fp.read_text(encoding="utf-8-sig")
    loaded = None
    if fp.suffix.lower() == ".json":
        try:
            loaded = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError) as ex:
            raise SystemExit(f"invalid desc json file: {ex}")
    if loaded is None:
        text = raw.strip()
    else:
        text = _flatten_requirement_obj(loaded).strip()
    if not text:
        raise SystemExit("--desc-file content cannot be empty")
    return text


def set_active(path: Path):
    ensure_spec_dir()
    ACTIVE_FILE.write_text(str(path), encoding="utf-8")


def read_global_memory_text() -> str:
    if not GLOBAL_MEMORY_FILE.exists():
        return ""
    return GLOBAL_MEMORY_FILE.read_text(encoding="utf-8-sig")


def global_memory_hash() -> str:
    text = read_global_memory_text()
    if not text.strip():
        return ""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def sync_memory_snapshot(path: Path, dry_run: bool = False) -> dict:
    meta, meta_version = load_metadata_file(path, with_version=True)
    meta["global_memory_hash"] = global_memory_hash()
    meta["global_memory_exists"] = GLOBAL_MEMORY_FILE.exists()
    meta["global_memory_synced_at"] = dt.datetime.now().isoformat(timespec="seconds")
    save_metadata_file(path, meta, dry_run=dry_run, expected_version=meta_version)
    return meta


def get_active() -> Path | None:
    if not ACTIVE_FILE.exists():
        return None
    try:
        active = Path(read_file(ACTIVE_FILE).strip())
        if active.exists():
            return active
        return None
    except OSError:
        return None


def list_requirements():
    if not SPEC_DIR.exists():
        return []
    items = []
    for date_dir in SPEC_DIR.iterdir():
        if not date_dir.is_dir():
            continue
        for req_dir in date_dir.iterdir():
            if req_dir.is_dir():
                items.append(req_dir)
    return sorted(items)


def find_requirement(name: str):
    matches = [p for p in list_requirements() if p.name == name]
    return matches


def _render_clarification_header():
    header = "| " + " | ".join(CLARIFY_COLUMNS) + " |"
    sep = "|" + "|".join(["---"] * len(CLARIFY_COLUMNS)) + "|"
    return header + "\n" + sep


def _initial_metadata(path: Path, title: str, original_requirement: str, mode: str) -> dict:
    return {
        "name": path.name,
        "title": title,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "original_requirement": original_requirement,
        "project_mode": mode,
        METADATA_VERSION_KEY: 1,
        "global_memory_hash": global_memory_hash(),
        "global_memory_exists": GLOBAL_MEMORY_FILE.exists(),
        "global_memory_synced_at": dt.datetime.now().isoformat(timespec="seconds"),
    }


def _clarification_example_row() -> dict:
    return {
        "id": "C-001",
        "status": CONFIRMED_STATUS,
        "priority": "低",
        "impact": "全局",
        "doc": "global",
        "section": "示例",
        "question": "（示例）请确认需求范围的最终边界",
        "answer": "示例项，可删除或替换",
        "solution": "示例项，不参与严格闭环",
    }


def _initial_clarifications_markdown(title: str) -> str:
    example = _clarification_example_row()
    return f"""# 澄清文档 - {title}

## 说明
- 本文档记录所有需要用户确认、补充和给出解决方案的内容。
- 请在表格中填写 `状态`、`用户确认/补充`、`解决方案`，并补充 `优先级`、`影响范围`、`关联章节`。
- `归属文档` 仅可填写：`analysis`、`prd`、`tech`、`acceptance`、`global`。
- `状态` 仅可填写：`待确认` 或 `{CONFIRMED_STATUS}`。

## 需求上下文采集
- 项目相关模块/入口：
- 依赖系统/外部接口：
- 数据库连接信息：
- 权限与角色范围：

## 澄清项
{_render_clarification_header()}
| {example["id"]} | {example["status"]} | {example["priority"]} | {example["impact"]} | {example["doc"]} | {example["section"]} | {example["question"]} | {example["answer"]} | {example["solution"]} |
"""


def _initial_clarifications_json() -> dict:
    return {"rows": [_clarification_example_row()]}


def init_docs(path: Path, title: str, original_requirement: str, project_mode: str = "existing"):
    mode = resolve_project_mode(original_requirement, "", project_mode)
    meta = _initial_metadata(path, title, original_requirement, mode)
    write_file(path / "metadata.json", json.dumps(meta, ensure_ascii=False, indent=2))
    clarifications = _initial_clarifications_markdown(title)
    safe_original_requirement = redact_sensitive_connection(original_requirement)

    analysis = f"""# 分析报告 - {title}

## 原始需求
{safe_original_requirement}

## 需求上下文采集
- 待补充：项目模块、依赖系统、数据库连接、权限与角色等。

## 项目现状与相关模块
- 待补充：根据代码仓库与现有功能梳理相关模块、接口、业务流程、配置等。

## 候选模块扫描
{SCAN_START}
- 无
{SCAN_END}

## 数据库现状
{DB_SCHEMA_START}
- 待补充：根据澄清文档提供的数据库连接与表结构核对。
{DB_SCHEMA_END}

## 需求覆盖矩阵
| 需求点 | 现有模块/表 | 是否满足 | 差距/说明 |
|---|---|---|---|
| 待补充 | 待补充 | 待补充 | 待补充 |

## 需求满足性分析
- 待补充：逐条对照需求，说明是否满足及差距。

## 风险与影响
- 待补充：潜在风险、影响范围、依赖项、性能与安全风险。

## 结论
- 待补充：是否可以在现有基础上满足需求，建议方案方向。

## 澄清补充
{CLARIFY_START}
- 无
{CLARIFY_END}
"""

    prd = f"""# PRD - {title}

## 需求范围与边界
- 待补充：明确包含与不包含的范围。

## 简要说明
- 待补充：功能用途、来源/背景、解决的问题。

## 产品功能描述与业务流程
- 待补充：完整主流程。

## 分支流程与异常处理
- 待补充：各类分支流程、异常场景、解决办法。

## 非功能性需求
- 待补充：性能、权限、安全、兼容性、可用性等（不涉及技术实现细节）。

## 待确认需求点
- 待补充：列出所有不明确点。

## 冲突与影响
- 待补充：与现有功能冲突点、受影响功能、解决方案。

## 澄清补充
{CLARIFY_START}
- 无
{CLARIFY_END}
"""

    tech = f"""# 技术方案 - {title}

## 当前项目/功能情况
- 待补充：与需求相关的现状与限制。

## 实现目标
- 待补充：技术层面的实现目标与约束。

## 整体架构设计思路
- 待补充：架构思路与组件关系。

## 架构图
- 待补充：可用 mermaid 或图片链接。

## 数据库设计
- 待补充：表结构、字段、索引、变更点。

## 可执行 SQL
```sql
-- 待补充
```

## 核心功能代码片段
```text
待补充
```

## 单元测试
- 待补充：测试范围、用例、覆盖关键路径。

## 数据迁移与回滚策略
- 待补充：迁移步骤、回滚方案、数据一致性保障。

## 注意事项
- 待补充：开发注意事项，若需澄清请写入澄清文档。

## 澄清补充
{CLARIFY_START}
- 无
{CLARIFY_END}
"""

    acceptance = f"""# 验收清单 - {title}

## 验收项清单
| 编号 | 验收项 | 预期结果 |
|---|---|---|
| A-001 | 待补充（R-01） | 待补充 |

## 验收计划与步骤
### A-001 验收计划与步骤（R-01）
- 验收目标：待补充
- 前置条件：
  1. 待补充
  2. 待补充
- 验收步骤：
  1. 待补充
  2. 待补充
  3. 待补充
- 通过标准：
  1. 待补充
  2. 待补充
- 失败处理：
  1. 待补充

## 受影响功能验证
- 待补充：列出受影响功能的验证项。

## 数据库核对指引
- 待补充：调用接口后，如何查询数据库验证数据一致性（接口结果与库中数据比对）。

## 澄清补充
{CLARIFY_START}
- 无
{CLARIFY_END}
"""

    write_file(path / DOC_FILES["clarifications"], clarifications)
    write_file(
        path / DOC_FILES["clarifications_json"],
        json.dumps(_initial_clarifications_json(), ensure_ascii=False, indent=2),
    )
    write_file(path / DOC_FILES["analysis"], analysis)
    write_file(path / DOC_FILES["prd"], prd)
    write_file(path / DOC_FILES["tech"], tech)
    write_file(path / DOC_FILES["acceptance"], acceptance)


def init_state_only(path: Path, title: str, original_requirement: str, project_mode: str = "existing"):
    mode = resolve_project_mode(original_requirement, "", project_mode)
    meta = _initial_metadata(path, title, original_requirement, mode)
    write_file(path / "metadata.json", json.dumps(meta, ensure_ascii=False, indent=2))
    clarifications = _initial_clarifications_markdown(title)

    write_file(path / DOC_FILES["clarifications"], clarifications)
    write_file(
        path / DOC_FILES["clarifications_json"],
        json.dumps(_initial_clarifications_json(), ensure_ascii=False, indent=2),
    )


def _normalize_header(cell: str) -> str:
    cell = cell.strip()
    return HEADER_KEY_MAP.get(cell, cell)


def split_md_row(line: str):
    raw = line.strip()
    if not raw.startswith("|"):
        return []
    if raw.endswith("|"):
        raw = raw[1:-1]
    else:
        raw = raw[1:]
    parts = re.split(r"(?<!\\)\|", raw)
    return [p.replace(r"\|", "|").strip() for p in parts]


def escape_md_cell(text: str) -> str:
    return str(text).replace("|", r"\|").replace("\n", "<br>")


def parse_clarifications_table(content: str):
    lines = content.splitlines()
    header_idx = None
    header_cells = None
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "ID" in line and "状态" in line:
            header_idx = i
            header_cells = split_md_row(line)
            break
    if header_idx is None or header_cells is None:
        return [], []
    keys = [_normalize_header(c) for c in header_cells]
    data_start = header_idx + 2
    rows = []
    for line in lines[data_start:]:
        if not line.strip().startswith("|"):
            break
        parts = split_md_row(line)
        if not parts:
            continue
        row = {keys[i]: parts[i] if i < len(parts) else "" for i in range(len(keys))}
        rows.append(row)
    return rows, header_cells


def normalize_clar_row(row: dict) -> dict:
    return {
        "id": str(row.get("id", "")).strip(),
        "status": str(row.get("status", "待确认")).strip() or "待确认",
        "priority": str(row.get("priority", "")).strip(),
        "impact": str(row.get("impact", "")).strip(),
        "doc": str(row.get("doc", "global")).strip() or "global",
        "section": str(row.get("section", "")).strip(),
        "question": str(row.get("question", "")).strip(),
        "answer": str(row.get("answer", "")).strip(),
        "solution": str(row.get("solution", "")).strip(),
    }


def load_clar_rows_from_json(json_path: Path):
    if not json_path.exists():
        return []
    try:
        raw = json.loads(read_file(json_path))
    except (json.JSONDecodeError, OSError, TypeError):
        return []
    rows = raw.get("rows", []) if isinstance(raw, dict) else []
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if isinstance(row, dict):
            out.append(normalize_clar_row(row))
    return out


def save_clar_rows_to_json(json_path: Path, rows: list[dict], dry_run: bool = False):
    payload = {"rows": [normalize_clar_row(r) for r in rows]}
    if dry_run:
        runtime_log(f"[dry-run] would update: {json_path}")
        return
    write_file(json_path, json.dumps(payload, ensure_ascii=False, indent=2))


def render_clarification_table_rows(rows: list[dict], header_cells: list[str]):
    table_lines = []
    for row in rows:
        values = []
        for cell in header_cells:
            key = _normalize_header(cell)
            if key == "status":
                values.append(escape_md_cell(row.get("status", "待确认")))
            else:
                values.append(escape_md_cell(row.get(key, "")))
        table_lines.append("| " + " | ".join(values) + " |")
    return table_lines


def upsert_clar_table_rows(clar_content: str, rows: list[dict]):
    lines = clar_content.splitlines()
    header_idx, sep_idx, header_cells = _find_table_indices(lines)
    if header_idx is None or sep_idx is None:
        return clar_content
    start = sep_idx + 1
    end = start
    while end < len(lines) and lines[end].strip().startswith("|"):
        end += 1
    body = render_clarification_table_rows(rows, header_cells)
    new_lines = lines[:start] + body + lines[end:]
    return "\n".join(new_lines) + "\n"


def _normalize_db_type(value: str) -> str:
    raw = str(value or "").strip().lower()
    return DB_TYPE_ALIASES.get(raw, "")


def _safe_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_connection_uri(conn: dict) -> str:
    db_type = _normalize_db_type(conn.get("db_type", ""))
    if db_type == "sqlite":
        raw_path = str(conn.get("path", "") or conn.get("database", "")).strip()
        if not raw_path:
            return ""
        if raw_path.startswith("/"):
            return "sqlite:///" + raw_path
        return f"sqlite:///{raw_path}"

    if db_type in {"mysql", "postgresql"}:
        host = str(conn.get("host", "")).strip()
        database = str(conn.get("database", "")).strip()
        if not host or not database:
            return ""
        scheme = "postgresql" if db_type == "postgresql" else "mysql"
        user = str(conn.get("username", "")).strip()
        password = str(conn.get("password", "")).strip()
        auth = ""
        if user:
            auth = user
            if password:
                auth += f":{password}"
            auth += "@"
        port = _safe_int(conn.get("port"))
        if port is None:
            port = DB_DEFAULT_PORT.get(db_type)
        host_port = f"{host}:{port}" if port else host
        return f"{scheme}://{auth}{host_port}/{database}"

    return ""


def _connection_alias_value(raw: dict, *keys: str) -> str:
    for key in keys:
        if key in raw and raw.get(key) is not None:
            return str(raw.get(key)).strip()
    return ""


def normalize_ai_db_connection(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise SystemExit("db connection item must be object")

    connection = _connection_alias_value(raw, "connection", "connection_uri", "uri", "url", "dsn")
    parsed = urlparse(connection) if connection else None

    db_type = _normalize_db_type(
        _connection_alias_value(raw, "db_type", "type", "db", "engine")
        or (parsed.scheme if parsed else "")
    )
    if not db_type:
        raise SystemExit("db connection db_type is required and must be one of: sqlite/mysql/postgresql")

    host = _connection_alias_value(raw, "host", "address")
    username = _connection_alias_value(raw, "username", "user", "account")
    password = _connection_alias_value(raw, "password", "passwd", "pwd")
    database = _connection_alias_value(raw, "database", "db_name", "dbname")
    path = _connection_alias_value(raw, "path", "file")
    source = _connection_alias_value(raw, "source", "evidence")
    port = _safe_int(raw.get("port"))

    if parsed:
        if not host and parsed.hostname:
            host = parsed.hostname
        if port is None and parsed.port is not None:
            port = int(parsed.port)
        if not username and parsed.username:
            username = parsed.username
        if not password and parsed.password:
            password = parsed.password
        parsed_db = unquote((parsed.path or "").lstrip("/"))
        if db_type == "sqlite":
            sqlite_path = unquote(parsed.path or "")
            if parsed.netloc and parsed.netloc not in {"localhost"}:
                sqlite_path = f"//{parsed.netloc}{sqlite_path}"
            if not path and sqlite_path:
                path = sqlite_path
            if not database and path:
                database = path
        else:
            if not database and parsed_db:
                database = parsed_db

    normalized = {
        "db_type": db_type,
        "host": host,
        "port": port if port is not None else DB_DEFAULT_PORT.get(db_type),
        "username": username,
        "password": password,
        "database": database,
        "path": path,
        "source": source,
        "connection": connection,
    }
    if not normalized["connection"]:
        normalized["connection"] = _build_connection_uri(normalized)

    if db_type == "sqlite":
        if not normalized["path"]:
            guessed_path = unquote(urlparse(normalized["connection"]).path) if normalized["connection"] else ""
            if guessed_path:
                normalized["path"] = guessed_path
        if not normalized["path"]:
            raise SystemExit("sqlite connection requires path or connection")
    else:
        if not normalized["host"] or not normalized["database"]:
            raise SystemExit(f"{db_type} connection requires host and database")

    return normalized


def normalize_ai_db_connections(items) -> list[dict]:
    if items is None:
        return []
    if isinstance(items, dict):
        payload = items.get("connections", items.get("items", items))
        if isinstance(payload, dict):
            items = [payload]
        else:
            items = payload
    if not isinstance(items, list):
        raise SystemExit("db connections payload must be array or object with connections")

    normalized = []
    seen = set()
    for item in items:
        conn = normalize_ai_db_connection(item)
        key = (
            conn.get("db_type", ""),
            conn.get("connection", ""),
            conn.get("host", ""),
            str(conn.get("port", "") or ""),
            conn.get("database", ""),
            conn.get("path", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        normalized.append(conn)
    return normalized


def parse_ai_db_connections_json(raw: str) -> list[dict]:
    if not str(raw or "").strip():
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError) as ex:
        raise SystemExit(f"invalid --db-connections-json: {ex}")
    return normalize_ai_db_connections(data)


def load_ai_db_connections(path: Path) -> list[dict]:
    meta = load_metadata_file(path)
    raw = meta.get(AI_DB_CONNECTIONS_KEY, [])
    try:
        return normalize_ai_db_connections(raw)
    except SystemExit:
        return []


def ai_db_connection_strings(connections: list[dict]) -> list[str]:
    out = []
    for item in connections:
        conn = str(item.get("connection", "")).strip()
        if conn:
            out.append(conn)
            continue
        built = _build_connection_uri(item)
        if built:
            out.append(built)
    return out


def describe_ai_db_connection(item: dict) -> str:
    db_type = str(item.get("db_type", "")).strip()
    fields = [f"type={db_type}"] if db_type else []
    if db_type == "sqlite":
        path = str(item.get("path", "") or item.get("database", "")).strip()
        if path:
            fields.append(f"path={path}")
    else:
        host = str(item.get("host", "")).strip()
        if host:
            fields.append(f"host={host}")
        port = item.get("port")
        if port:
            fields.append(f"port={port}")
        database = str(item.get("database", "")).strip()
        if database:
            fields.append(f"database={database}")
        username = str(item.get("username", "")).strip()
        if username:
            fields.append(f"user={username}")
        if str(item.get("password", "")).strip():
            fields.append("password=***")
    conn = str(item.get("connection", "")).strip()
    if conn:
        fields.append(f"uri={redact_sensitive_connection(conn)}")
    source = str(item.get("source", "")).strip()
    if source:
        fields.append(f"source={source}")
    return ", ".join(fields)


def redact_sensitive_connection(conn: str) -> str:
    text = str(conn or "").strip()
    if not text:
        return text
    parsed = urlparse(text)
    redacted = text
    if parsed.scheme and parsed.netloc:
        netloc = parsed.netloc
        if "@" in netloc:
            user_info, host_info = netloc.rsplit("@", 1)
            if ":" in user_info:
                user, _pwd = user_info.split(":", 1)
                user_info = f"{user}:***"
            netloc = f"{user_info}@{host_info}"
        redacted = parsed._replace(netloc=netloc).geturl()
    redacted = re.sub(
        r"([a-z][a-z0-9+.-]*://[^/@\s:]+:)[^@/\s]+@",
        r"\1***@",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"(?i)([?&](?:password|passwd|pwd|token|secret)=)[^&\s]+",
        r"\1***",
        redacted,
    )
    return redacted


def inspect_sqlite_schema(conn: str):
    parsed = urlparse(conn)
    if parsed.scheme != "sqlite":
        return None
    raw_path = unquote(parsed.path or "")
    if parsed.netloc and parsed.netloc not in {"localhost"}:
        raw_path = f"//{parsed.netloc}{raw_path}"
    if not raw_path:
        return {"connection": conn, "ok": False, "message": "sqlite path missing"}

    if raw_path.startswith("//"):
        path = Path("/" + raw_path.lstrip("/"))
    elif raw_path.startswith("/"):
        rel_candidate = Path(raw_path.lstrip("/"))
        abs_candidate = Path(raw_path)
        if abs_candidate.exists() and not rel_candidate.exists():
            path = abs_candidate
        else:
            path = (ROOT / rel_candidate).resolve()
    else:
        path = Path(raw_path)
        if not path.is_absolute():
            path = (ROOT / path).resolve()
    if not path.exists():
        return {"connection": conn, "ok": False, "message": f"sqlite file not found: {path}"}
    try:
        con = sqlite3.connect(str(path))
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        table_columns = {}
        for t in tables:
            safe_t = t.replace("'", "''")
            cur.execute(f"PRAGMA table_info('{safe_t}')")
            cols = [row[1] for row in cur.fetchall()]
            table_columns[t] = cols
        con.close()
        return {
            "connection": conn,
            "ok": True,
            "message": f"sqlite tables: {len(tables)}",
            "tables": table_columns,
        }
    except sqlite3.Error as ex:
        return {"connection": conn, "ok": False, "message": f"sqlite inspect failed: {ex}"}


def inspect_mysql_schema(conn: str):
    parsed = urlparse(conn)
    if parsed.scheme not in ("mysql",):
        return None
    if not shutil.which("mysql"):
        return {"connection": conn, "ok": False, "message": "mysql client not found"}
    host = parsed.hostname or "127.0.0.1"
    port = str(parsed.port or 3306)
    user = parsed.username or ""
    password = parsed.password or ""
    db = (parsed.path or "").lstrip("/")
    if not db:
        return {"connection": conn, "ok": False, "message": "mysql database name missing"}
    cmd = ["mysql", "-h", host, "-P", port, "-N", "-D", db]
    if user:
        cmd.extend(["-u", user])
    cmd.extend(["-e", "SHOW TABLES;"])
    env = os.environ.copy()
    if password:
        env["MYSQL_PWD"] = password
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
        if proc.returncode != 0:
            return {"connection": conn, "ok": False, "message": f"mysql inspect failed: {proc.stderr.strip()}"}
        tables = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        return {"connection": conn, "ok": True, "message": f"mysql tables: {len(tables)}", "tables": {t: [] for t in tables}}
    except (OSError, subprocess.SubprocessError) as ex:
        return {"connection": conn, "ok": False, "message": f"mysql inspect failed: {ex}"}


def inspect_postgres_schema(conn: str):
    parsed = urlparse(conn)
    if parsed.scheme not in ("postgres", "postgresql"):
        return None
    if not shutil.which("psql"):
        return {"connection": conn, "ok": False, "message": "psql client not found"}
    db = (parsed.path or "").lstrip("/")
    if not db:
        return {"connection": conn, "ok": False, "message": "postgres database name missing"}
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    cmd = [
        "psql",
        "-h",
        parsed.hostname or "127.0.0.1",
        "-p",
        str(parsed.port or 5432),
        "-U",
        parsed.username or "postgres",
        "-d",
        db,
        "-At",
        "-c",
        "select tablename from pg_tables where schemaname='public' order by tablename;",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
        if proc.returncode != 0:
            return {"connection": conn, "ok": False, "message": f"postgres inspect failed: {proc.stderr.strip()}"}
        tables = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        return {"connection": conn, "ok": True, "message": f"postgres tables: {len(tables)}", "tables": {t: [] for t in tables}}
    except (OSError, subprocess.SubprocessError) as ex:
        return {"connection": conn, "ok": False, "message": f"postgres inspect failed: {ex}"}


def build_db_schema_summary(connections: list[str]):
    if not connections:
        return "- 未提供结构化数据库连接信息；请由调用端 AI 识别后通过 `--db-connections-json` 传入。"
    lines = []
    for conn in connections:
        safe_conn = redact_sensitive_connection(conn)
        if conn.startswith("sqlite://"):
            result = inspect_sqlite_schema(conn)
            if not result:
                lines.append(f"- {safe_conn}：不支持的连接格式")
                continue
            if not result["ok"]:
                lines.append(f"- {safe_conn}：{result['message']}")
                continue
            lines.append(f"- {safe_conn}：{result['message']}")
            tables = result.get("tables", {})
            for t, cols in tables.items():
                col_text = "、".join(cols[:12]) if cols else "无字段"
                lines.append(f"  - 表 `{t}` 字段：{col_text}")
        elif conn.startswith("mysql://"):
            result = inspect_mysql_schema(conn)
            if not result:
                lines.append(f"- {safe_conn}：不支持的连接格式")
                continue
            lines.append(f"- {safe_conn}：{result['message']}")
            if result.get("ok"):
                for t in result.get("tables", {}).keys():
                    lines.append(f"  - 表 `{t}`")
        elif conn.startswith("postgres://") or conn.startswith("postgresql://"):
            result = inspect_postgres_schema(conn)
            if not result:
                lines.append(f"- {safe_conn}：不支持的连接格式")
                continue
            lines.append(f"- {safe_conn}：{result['message']}")
            if result.get("ok"):
                for t in result.get("tables", {}).keys():
                    lines.append(f"  - 表 `{t}`")
        else:
            lines.append(f"- {safe_conn}：暂不支持自动探查（建议调用端按连接执行 schema 查询后回填）。")
    return "\n".join(lines)


def replace_scan_block(content: str, block: str):
    if SCAN_START not in content or SCAN_END not in content:
        return content
    pattern = re.compile(
        re.escape(SCAN_START) + r"[\s\S]*?" + re.escape(SCAN_END),
        re.MULTILINE,
    )
    replacement = f"{SCAN_START}\n{block}\n{SCAN_END}"
    return pattern.sub(lambda _m: replacement, content)


def replace_db_schema_block(content: str, block: str):
    if DB_SCHEMA_START not in content or DB_SCHEMA_END not in content:
        heading = re.search(r"^## 数据库现状\s*$", content, flags=re.MULTILINE)
        if not heading:
            return content
        start = heading.end()
        next_h2 = re.search(r"^##\s+", content[start:], flags=re.MULTILINE)
        end = start + next_h2.start() if next_h2 else len(content)
        replacement = f"\n{DB_SCHEMA_START}\n{block}\n{DB_SCHEMA_END}\n"
        return content[:start] + replacement + content[end:]
    pattern = re.compile(
        re.escape(DB_SCHEMA_START) + r"[\s\S]*?" + re.escape(DB_SCHEMA_END),
        re.MULTILINE,
    )
    replacement = f"{DB_SCHEMA_START}\n{block}\n{DB_SCHEMA_END}"
    return pattern.sub(lambda _m: replacement, content)


def extract_block(content: str, start_tag: str, end_tag: str) -> str | None:
    if start_tag not in content or end_tag not in content:
        return None
    pattern = re.compile(
        re.escape(start_tag) + r"\n?([\s\S]*?)\n?" + re.escape(end_tag),
        re.MULTILINE,
    )
    match = pattern.search(content)
    if not match:
        return None
    return match.group(1).strip()


def scan_modules() -> list[str]:
    ignore_dirs = {
        ".git",
        ".hg",
        ".svn",
        ".idea",
        ".vscode",
        ".cursor",
        "node_modules",
        "dist",
        "build",
        "out",
        "spec",
        "rules",
        "__pycache__",
    }
    exts = {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".go",
        ".cs",
        ".php",
        ".rb",
        ".rs",
        ".kt",
        ".swift",
    }
    modules = set()

    if shutil.which("rg"):
        cmd = ["rg", "--files"]
        for d in ignore_dirs:
            cmd.extend(["-g", f"!{d}/**"])
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode in (0, 1):
                for rel in proc.stdout.splitlines():
                    p = Path(rel.strip())
                    if not p.parts:
                        continue
                    if p.suffix.lower() not in exts:
                        continue
                    top = p.parts[0]
                    if top in ignore_dirs:
                        continue
                    modules.add(top)
                return sorted(modules)
        except (OSError, subprocess.SubprocessError):
            pass

    for path in ROOT.rglob("*"):
        if path.is_dir():
            continue
        if path.suffix.lower() not in exts:
            continue
        parts = path.relative_to(ROOT).parts
        if not parts:
            continue
        top = parts[0]
        if top in ignore_dirs:
            continue
        modules.add(top)
    return sorted(modules)


def load_clar_rows(path: Path, sync: bool = True):
    md_rows, js_rows = load_clar_rows_pair(path)
    clar_path = path / DOC_FILES["clarifications"]
    clar_json_path = path / DOC_FILES["clarifications_json"]
    # Markdown is the single source of truth for clarifications.
    if clar_path.exists():
        if sync:
            save_clar_rows_to_json(clar_json_path, md_rows)
        return md_rows
    # Backward-compat fallback for legacy requirements without markdown file.
    if js_rows:
        runtime_log("[warn] clarifications markdown missing; fallback to json mirror", stderr=True)
        return js_rows
    return []


def load_clar_rows_pair(path: Path) -> tuple[list[dict], list[dict]]:
    clar_path = path / DOC_FILES["clarifications"]
    clar_json_path = path / DOC_FILES["clarifications_json"]
    if not clar_path.exists() and not clar_json_path.exists():
        raise SystemExit("clarifications files not found")

    md_rows = []
    if clar_path.exists():
        md_rows, _ = parse_clarifications_table(read_file(clar_path))
        md_rows = [normalize_clar_row(r) for r in md_rows]
    js_rows = load_clar_rows_from_json(clar_json_path)
    return md_rows, js_rows


def _find_table_indices(lines):
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "ID" in line and "状态" in line:
            header_idx = i
            break
    if header_idx is None:
        return None, None, []
    header_cells = split_md_row(lines[header_idx])
    sep_idx = header_idx + 1 if header_idx + 1 < len(lines) else None
    return header_idx, sep_idx, header_cells


def add_clarifications(clar_content: str, new_items):
    lines = clar_content.splitlines()
    header_idx, sep_idx, header_cells = _find_table_indices(lines)
    if header_idx is None or sep_idx is None:
        rows, _ = parse_clarifications_table(clar_content)
        rows = [normalize_clar_row(r) for r in rows]
        existing_questions = set(r.get("question", "") for r in rows)
        for item in new_items:
            if item["question"] in existing_questions:
                continue
            merged = normalize_clar_row(item)
            if not merged.get("status"):
                merged["status"] = "待确认"
            rows.append(merged)
        if not rows:
            return clar_content
        runtime_log("[warn] clarification table format not found; rebuilt with standard columns", stderr=True)
        body = render_clarification_table_rows(rows, CLARIFY_COLUMNS)
        table = _render_clarification_header() + "\n" + "\n".join(body)
        trimmed = clar_content.rstrip()
        section = "## 澄清项\n" + table + "\n"
        if "## 澄清项" in trimmed:
            return re.sub(r"## 澄清项[\s\S]*$", section.rstrip(), trimmed, flags=re.MULTILINE) + "\n"
        return trimmed + "\n\n" + section

    rows, _ = parse_clarifications_table(clar_content)
    existing_questions = set(r.get("question", "") for r in rows)

    def build_row(item):
        values = []
        for cell in header_cells:
            key = _normalize_header(cell)
            if key == "status":
                values.append(escape_md_cell(item.get("status", "待确认")))
            else:
                values.append(escape_md_cell(item.get(key, "")))
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
    clar_path = path / DOC_FILES["clarifications"]
    clar_json_path = path / DOC_FILES["clarifications_json"]
    rows, _ = parse_clarifications_table(clar_content)
    rows = [normalize_clar_row(r) for r in rows]
    if dry_run:
        runtime_log(f"[dry-run] would update: {clar_path}")
        runtime_log(f"[dry-run] would update: {clar_json_path}")
        return
    write_file(clar_path, clar_content)
    save_clar_rows_to_json(clar_json_path, rows)


def next_clarify_id(rows):
    max_id = 0
    for r in rows:
        m = re.match(r"C-(\d+)", r.get("id", ""))
        if m:
            max_id = max(max_id, int(m.group(1)))
    return f"C-{max_id + 1:03d}"


def ensure_runtime_context_clarifications(path: Path, db_connections: list[dict] | None = None, dry_run: bool = False):
    try:
        structured = normalize_ai_db_connections(db_connections or [])
    except SystemExit:
        structured = []
    if not structured:
        return
    clar_path = path / DOC_FILES["clarifications"]
    clar_content = read_file(clar_path)
    rows, _ = parse_clarifications_table(clar_content)
    max_id = 0
    for row in rows:
        m = re.match(r"C-(\d+)", row.get("id", ""))
        if m:
            max_id = max(max_id, int(m.group(1)))
    merged = "；".join([describe_ai_db_connection(c) for c in structured])
    new_items = [{
        "id": f"C-{max_id + 1:03d}",
        "status": CONFIRMED_STATUS,
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
        runtime_log("[dry-run] would append runtime DB clarification")
        return
    persist_clarifications(path, updated, dry_run=False)


def strip_clarification_block(content: str) -> str:
    """Remove clarification block markers and content before hashing/analysis."""
    pattern = re.compile(
        re.escape(CLARIFY_START) + r"[\s\S]*?" + re.escape(CLARIFY_END),
        re.MULTILINE,
    )
    return pattern.sub("", content)


def content_hash_without_clarifications(content: str) -> str:
    """Compute stable hash for a document by ignoring clarification block volatility."""
    return hashlib.md5(strip_clarification_block(content).encode("utf-8")).hexdigest()


def extract_dependency_signatures(content: str) -> dict[str, str]:
    """Extract dependency signatures from doc comment block."""
    pattern = re.compile(
        re.escape(DEP_SIG_START) + r"\n?([\s\S]*?)\n?" + re.escape(DEP_SIG_END),
        re.MULTILINE,
    )
    match = pattern.search(content)
    if not match:
        return {}
    out = {}
    for raw in match.group(1).splitlines():
        line = raw.strip().lstrip("-").strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key_norm = key.strip().lower()
        value_norm = value.strip()
        if key_norm and value_norm:
            out[key_norm] = value_norm
    return out


def _subagent_stage_handoff(stage: str) -> dict:
    """Return fixed handoff contract sections for the stage."""
    hints = SUBAGENT_STAGE_SECTION_HINTS.get(stage, {})
    target_sections = hints.get("target_sections", []) if isinstance(hints.get("target_sections", []), list) else []
    must_keep_sections = hints.get("must_keep_sections", []) if isinstance(hints.get("must_keep_sections", []), list) else []
    return {
        "target_sections": [str(x) for x in target_sections],
        "must_keep_sections": [str(x) for x in must_keep_sections],
    }


def _subagent_default_stage_state() -> dict:
    """Return default state payload for each subagent stage."""
    now = dt.datetime.now().isoformat(timespec="seconds")
    return {
        "status": "pending",
        "agent": "",
        "updated_at": now,
        "doc_hash": "",
        "upstream_hashes": {},
        "notes": "",
        "validation_errors": [],
    }


def _normalize_stage_name(stage: str) -> str:
    """Validate and normalize stage name."""
    stage_norm = str(stage or "").strip().lower()
    if stage_norm not in SUBAGENT_STAGE_ORDER:
        allowed = ", ".join(SUBAGENT_STAGE_ORDER)
        raise SystemExit(f"invalid stage: {stage} (allowed: {allowed})")
    return stage_norm


def _normalize_stage_status(status: str) -> str:
    """Validate and normalize stage status."""
    status_norm = str(status or "").strip().lower()
    if status_norm not in SUBAGENT_STAGE_STATUSES:
        allowed = ", ".join(sorted(SUBAGENT_STAGE_STATUSES))
        raise SystemExit(f"invalid status: {status} (allowed: {allowed})")
    return status_norm


def _doc_path_for_stage(path: Path, stage: str) -> Path | None:
    """Resolve the document file path for a doc-writing stage."""
    doc_key = SUBAGENT_STAGE_DOC_MAP.get(stage)
    if not doc_key:
        return None
    return path / DOC_FILES[doc_key]


def _current_doc_hashes(path: Path) -> dict[str, str]:
    """Collect current hash snapshot for all generated docs."""
    hashes = {}
    for stage, doc_key in SUBAGENT_STAGE_DOC_MAP.items():
        p = path / DOC_FILES[doc_key]
        if not p.exists():
            continue
        hashes[stage] = content_hash_without_clarifications(read_file(p))
    return hashes


def _stage_upstream_hashes(path: Path, stage: str) -> dict[str, str]:
    """Build upstream hash map used by a specific stage."""
    current = _current_doc_hashes(path)
    deps = SUBAGENT_STAGE_DEPENDENCIES.get(stage, [])
    return {dep: current.get(dep, "") for dep in deps if dep in current}


def _ensure_subagent_state(meta: dict, reset: bool = False) -> tuple[dict, bool]:
    """Ensure metadata has a normalized subagent state section."""
    changed = False
    root = meta.get("subagents")
    if not isinstance(root, dict) or reset:
        root = {}
        changed = True

    stage_order = root.get("stage_order")
    if stage_order != SUBAGENT_STAGE_ORDER:
        root["stage_order"] = list(SUBAGENT_STAGE_ORDER)
        changed = True

    stages = root.get("stages")
    if not isinstance(stages, dict):
        stages = {}
        changed = True

    if reset:
        stages = {}
        changed = True

    for stage in SUBAGENT_STAGE_ORDER:
        state = stages.get(stage)
        if not isinstance(state, dict):
            stages[stage] = _subagent_default_stage_state()
            changed = True
            continue
        merged = _subagent_default_stage_state()
        merged.update(state)
        merged["status"] = _normalize_stage_status(str(merged.get("status", "pending")))
        merged["agent"] = str(merged.get("agent", "")).strip()
        merged["updated_at"] = str(merged.get("updated_at", "")).strip() or dt.datetime.now().isoformat(timespec="seconds")
        merged["doc_hash"] = str(merged.get("doc_hash", "")).strip()
        merged["notes"] = str(merged.get("notes", "")).strip()
        merged["upstream_hashes"] = merged.get("upstream_hashes") if isinstance(merged.get("upstream_hashes"), dict) else {}
        merged["validation_errors"] = merged.get("validation_errors") if isinstance(merged.get("validation_errors"), list) else []
        if merged != state:
            changed = True
        stages[stage] = merged

    root["stages"] = stages
    if root.get("handoff_protocol_version") != 1:
        root["handoff_protocol_version"] = 1
        changed = True
    if not isinstance(root.get("last_reopen"), dict):
        root["last_reopen"] = {}
        changed = True
    current_stage = str(root.get("current_stage", "")).strip().lower()
    if current_stage not in SUBAGENT_STAGE_ORDER:
        root["current_stage"] = SUBAGENT_STAGE_ORDER[0]
        changed = True
    root["version"] = 1
    root["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    meta["subagents"] = root
    return root, changed


def _recommended_next_stage(stages: dict) -> str:
    """Return the next runnable stage according to dependency completion."""
    for stage in SUBAGENT_STAGE_ORDER:
        state = stages.get(stage, {})
        if state.get("status") == "completed":
            continue
        deps = SUBAGENT_STAGE_DEPENDENCIES.get(stage, [])
        blocked = [dep for dep in deps if stages.get(dep, {}).get("status") != "completed"]
        if not blocked:
            return stage
    return ""


def _validate_stage_dependencies(stages: dict, stage: str) -> list[str]:
    """Validate whether stage dependencies are completed."""
    deps = SUBAGENT_STAGE_DEPENDENCIES.get(stage, [])
    issues = []
    for dep in deps:
        if stages.get(dep, {}).get("status") != "completed":
            issues.append(f"dependency stage not completed: {dep}")
    return issues


def _validate_doc_stage_completion(path: Path, stage: str, upstream_hashes: dict[str, str]) -> tuple[str, list[str]]:
    """Validate document stage output and return document hash with issues."""
    issues = []
    doc_path = _doc_path_for_stage(path, stage)
    if not doc_path:
        return "", issues
    if not doc_path.exists():
        return "", [f"{doc_path.name} missing"]
    content = read_file(doc_path)
    if not content.strip():
        return "", [f"{doc_path.name} is empty"]
    doc_hash = content_hash_without_clarifications(content)
    if stage in {"prd", "tech", "acceptance"}:
        signatures = extract_dependency_signatures(content)
        for dep, expected in upstream_hashes.items():
            if dep not in signatures:
                issues.append(f"{doc_path.name} missing dependency signature: {dep}")
            elif signatures.get(dep, "") != expected:
                issues.append(f"{doc_path.name} dependency signature mismatch: {dep}")
    return doc_hash, issues


def _validate_final_check_stage(path: Path) -> list[str]:
    """Run final-check in no-write mode and convert issues into stage validation messages."""
    from spec_agent_engine_checks import final_check as run_final_check

    issues = run_final_check(path, write_back=False)
    if not issues:
        return []
    return [f"{it.get('doc', 'global')}: {it.get('question', '')}" for it in issues]


def _classify_issue_to_stage(issue: dict) -> str:
    """Map final-check issue to the earliest impacted doc stage."""
    code = str(issue.get("code", "")).strip().lower()
    if code:
        if code.startswith("analysis."):
            return "analysis"
        if code.startswith("prd."):
            return "prd"
        if code.startswith("tech."):
            return "tech"
        if code.startswith("acceptance."):
            return "acceptance"
        if code.startswith("global."):
            # Global issues usually require analysis/prd refresh first.
            return "analysis"
    doc = str(issue.get("doc", "")).strip().lower()
    if doc in FINAL_CHECK_DOC_STAGE_MAP:
        return FINAL_CHECK_DOC_STAGE_MAP[doc]
    question = str(issue.get("question", "")).strip()
    if any(k in question for k in ("验收", "A-")):
        return "acceptance"
    if any(k in question for k in ("技术方案", "SQL", "数据库设计", "回滚")):
        return "tech"
    if any(k in question for k in ("PRD", "产品功能", "非功能性需求")):
        return "prd"
    return "analysis"


def _suggest_reopen_stage_from_final_check(path: Path) -> tuple[str, dict, list[dict]]:
    """Infer reopen stage from current final-check issues."""
    from spec_agent_engine_checks import final_check as run_final_check

    raw_issues = run_final_check(path, write_back=False)
    if not raw_issues:
        return "", {}, []
    counts = {stage: 0 for stage in SUBAGENT_REOPEN_ORDER}
    mapped = []
    for issue in raw_issues:
        stage = _classify_issue_to_stage(issue)
        if stage not in counts:
            stage = "analysis"
        counts[stage] += 1
        mapped.append({
            "doc": str(issue.get("doc", "")),
            "question": str(issue.get("question", "")),
            "code": str(issue.get("code", "")),
            "mapped_stage": stage,
        })
    reopen_stage = ""
    for stage in SUBAGENT_REOPEN_ORDER:
        if counts.get(stage, 0) > 0:
            reopen_stage = stage
            break
    return reopen_stage, counts, mapped


def _reopen_doc_stages_from(stages: dict, stage: str, reason: str):
    """Reopen doc stages from a given stage up to acceptance."""
    now = dt.datetime.now().isoformat(timespec="seconds")
    started = False
    for doc_stage in SUBAGENT_REOPEN_ORDER:
        if doc_stage == stage:
            started = True
        if not started:
            continue
        current = stages.get(doc_stage)
        if not isinstance(current, dict):
            continue
        old_notes = str(current.get("notes", "")).strip()
        current["status"] = "pending"
        current["updated_at"] = now
        current["doc_hash"] = ""
        current["upstream_hashes"] = {}
        current["validation_errors"] = []
        current["notes"] = f"{reason}; {old_notes}".strip("; ").strip()


def _downgrade_downstream_stages(stages: dict, stage: str, reason: str):
    """Mark downstream stages as pending when upstream changed or failed."""
    now = dt.datetime.now().isoformat(timespec="seconds")
    try:
        idx = SUBAGENT_STAGE_ORDER.index(stage)
    except ValueError:
        return
    for downstream in SUBAGENT_STAGE_ORDER[idx + 1:]:
        state = stages.get(downstream)
        if not isinstance(state, dict):
            continue
        if state.get("status") == "pending":
            continue
        state["status"] = "pending"
        state["updated_at"] = now
        old_notes = str(state.get("notes", "")).strip()
        state["notes"] = f"{reason}; {old_notes}".strip("; ").strip()
        state["validation_errors"] = []
        state["doc_hash"] = ""
        state["upstream_hashes"] = {}


def init_subagent_state(path: Path, dry_run: bool = False, reset: bool = False) -> dict:
    """Initialize or repair subagent orchestration state in metadata."""
    meta, meta_version = load_metadata_file(path, with_version=True)
    root, changed = _ensure_subagent_state(meta, reset=reset)
    next_stage = _recommended_next_stage(root.get("stages", {})) or SUBAGENT_STAGE_ORDER[0]
    if root.get("current_stage") != next_stage:
        root["current_stage"] = next_stage
        changed = True
    meta["subagents"] = root
    if changed:
        save_metadata_file(path, meta, dry_run=dry_run, expected_version=meta_version)
    return root


def subagent_context(path: Path, stage: str) -> dict:
    """Build structured stage context consumed by a stage-specific subagent."""
    stage_norm = _normalize_stage_name(stage)
    meta, meta_version = load_metadata_file(path, with_version=True)
    root, changed = _ensure_subagent_state(meta, reset=False)
    project_mode = resolve_project_mode(
        str(meta.get("original_requirement", "")),
        str(meta.get("initial_clarifications", "")),
        str(meta.get("project_mode", "")),
    )
    mode_changed = str(meta.get("project_mode", "")).strip().lower() != project_mode
    meta["project_mode"] = project_mode
    if changed or mode_changed:
        save_metadata_file(path, meta, dry_run=False, expected_version=meta_version)
        meta_version = _metadata_version(meta)
    focus_policy = clarification_focus_by_project_mode(project_mode)
    handoff = _subagent_stage_handoff(stage_norm)

    rows = []
    try:
        rows = load_clar_rows(path, sync=False)
    except SystemExit:
        rows = []
    confirmed = [r for r in rows if str(r.get("status", "")).strip() == CONFIRMED_STATUS and not str(r.get("question", "")).strip().startswith("（示例）")]
    pending = [
        r
        for r in rows
        if str(r.get("question", "")).strip()
        and not str(r.get("question", "")).strip().startswith("（示例）")
        and str(r.get("status", "")).strip() != CONFIRMED_STATUS
    ]
    upstream_hashes = _stage_upstream_hashes(path, stage_norm)
    dep_stages = SUBAGENT_STAGE_DEPENDENCIES.get(stage_norm, [])
    upstream_docs = []
    for dep in dep_stages:
        dep_path = _doc_path_for_stage(path, dep)
        upstream_docs.append({
            "stage": dep,
            "path": str(dep_path) if dep_path else "",
            "hash": upstream_hashes.get(dep, ""),
            "status": root.get("stages", {}).get(dep, {}).get("status", "pending"),
            "exists": bool(dep_path and dep_path.exists()),
        })

    target_doc_path = _doc_path_for_stage(path, stage_norm)
    target_exists = bool(target_doc_path and target_doc_path.exists())
    target_hash = ""
    if target_doc_path and target_doc_path.exists():
        target_hash = content_hash_without_clarifications(read_file(target_doc_path))
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
            "path": str(GLOBAL_MEMORY_FILE),
            "exists": GLOBAL_MEMORY_FILE.exists(),
            "hash": global_memory_hash(),
        },
        "clarifications": {
            "file_md": str(path / DOC_FILES["clarifications"]),
            "file_json": str(path / DOC_FILES["clarifications_json"]),
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
    stage_norm = _normalize_stage_name(stage)
    status_norm = _normalize_stage_status(status)

    meta, meta_version = load_metadata_file(path, with_version=True)
    root, changed = _ensure_subagent_state(meta, reset=False)
    stages = root.get("stages", {})
    state = stages.get(stage_norm, _subagent_default_stage_state())

    dep_issues = []
    if status_norm in {"running", "completed"}:
        dep_issues = _validate_stage_dependencies(stages, stage_norm)
        if dep_issues and not force:
            hints = "\n".join([f"- {x}" for x in dep_issues])
            raise SystemExit(f"stage blocked: {stage_norm}\n{hints}")

    upstream_hashes = _stage_upstream_hashes(path, stage_norm) if status_norm == "completed" else {}
    validation_errors = []
    doc_hash = ""
    if status_norm == "completed":
        if stage_norm in SUBAGENT_STAGE_DOC_MAP:
            doc_hash, validation_errors = _validate_doc_stage_completion(path, stage_norm, upstream_hashes)
        elif stage_norm == "final_check":
            validation_errors = _validate_final_check_stage(path)
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

    auto_reopen = {}
    if stage_norm == "final_check" and status_norm == "failed":
        reopen_stage, reopen_counts, mapped_issues = _suggest_reopen_stage_from_final_check(path)
        if reopen_stage:
            breakdown = ", ".join([f"{k}:{v}" for k, v in reopen_counts.items() if v > 0])
            reason = f"auto reopen by final-check mapping ({breakdown})"
            _reopen_doc_stages_from(stages, reopen_stage, reason)
            auto_reopen = {
                "stage": reopen_stage,
                "reason": reason,
                "at": now,
                "source": "final_check",
                "issue_count": len(mapped_issues),
                "breakdown": {k: v for k, v in reopen_counts.items() if v > 0},
                "issues": mapped_issues[:20],
            }
            root["last_reopen"] = auto_reopen
        else:
            root["last_reopen"] = {}

    # If an upstream stage is reopened or failed, enforce downstream rerun.
    if status_norm in {"pending", "failed"} and stage_norm in SUBAGENT_STAGE_ORDER and stage_norm != "final_check":
        _downgrade_downstream_stages(stages, stage_norm, f"upstream stage changed: {stage_norm}")

    # If a doc stage completed with new upstream hashes, verify downstream freshness.
    if status_norm == "completed" and stage_norm in SUBAGENT_STAGE_DOC_MAP:
        for downstream in SUBAGENT_STAGE_ORDER:
            if downstream == stage_norm:
                continue
            if stage_norm not in SUBAGENT_STAGE_DEPENDENCIES.get(downstream, []):
                continue
            downstream_state = stages.get(downstream, {})
            if downstream_state.get("status") != "completed":
                continue
            expected = _stage_upstream_hashes(path, downstream)
            recorded = downstream_state.get("upstream_hashes", {})
            if any(str(recorded.get(k, "")) != str(v) for k, v in expected.items()):
                _downgrade_downstream_stages(stages, downstream, f"upstream content drifted: {stage_norm}")
                break

    root["stages"] = stages
    root["current_stage"] = _recommended_next_stage(stages) or SUBAGENT_STAGE_ORDER[-1]
    root["updated_at"] = now
    meta["subagents"] = root
    changed = True
    if changed:
        save_metadata_file(path, meta, dry_run=dry_run, expected_version=meta_version)
    return root


def subagent_status(path: Path, normalize: bool = False) -> dict:
    """Return subagent status; normalize stale stages only when requested."""
    meta, meta_version = load_metadata_file(path, with_version=True)
    root, changed = _ensure_subagent_state(meta, reset=False)
    stages = root.get("stages", {})
    current_hashes = _current_doc_hashes(path)
    stale_changed = False

    stale = {}
    for stage in SUBAGENT_STAGE_ORDER:
        stage_state = stages.get(stage, {})
        if stage_state.get("status") != "completed":
            stale[stage] = False
            continue
        if stage in SUBAGENT_STAGE_DOC_MAP:
            recorded_doc_hash = str(stage_state.get("doc_hash", "")).strip()
            current_doc_hash = current_hashes.get(stage, "")
            if not recorded_doc_hash or recorded_doc_hash != current_doc_hash:
                stale[stage] = True
                continue
            recorded_up = stage_state.get("upstream_hashes", {}) if isinstance(stage_state.get("upstream_hashes"), dict) else {}
            current_up = _stage_upstream_hashes(path, stage)
            stale[stage] = any(str(recorded_up.get(k, "")) != str(v) for k, v in current_up.items())
            continue
        if stage == "final_check":
            stale[stage] = any(stale.get(dep, False) or stages.get(dep, {}).get("status") != "completed" for dep in SUBAGENT_STAGE_DEPENDENCIES["final_check"])
        else:
            stale[stage] = False

    effective_stages = {}
    for stage in SUBAGENT_STAGE_ORDER:
        current = stages.get(stage, {})
        state = dict(current) if isinstance(current, dict) else _subagent_default_stage_state()
        if stale.get(stage, False):
            if state.get("status") != "pending":
                stale_changed = True
            state["status"] = "pending"
        effective_stages[stage] = state

    current_stage = _recommended_next_stage(effective_stages) or SUBAGENT_STAGE_ORDER[-1]
    if normalize:
        root["stages"] = effective_stages
        root["current_stage"] = current_stage
        root["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    if normalize and (changed or stale_changed):
        meta["subagents"] = root
        save_metadata_file(path, meta, dry_run=False, expected_version=meta_version)

    return {
        "requirement_path": str(path),
        "current_stage": current_stage,
        "stale_stages": [stage for stage, is_stale in stale.items() if is_stale],
        "last_reopen": root.get("last_reopen", {}),
        "stages": root.get("stages", {}) if normalize else stages,
    }

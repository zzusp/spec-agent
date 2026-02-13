#!/usr/bin/env python
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from urllib.parse import urlparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "spec-agent.config.json"
RUNTIME_JSON_OUTPUT = False

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
    "max_context_file_kb": 128,
    "min_doc_bullets": {
        "analysis": 8,
        "prd": 10,
        "tech": 10,
        "acceptance": 8,
    },
    "max_new_clarifications_per_round": 10,
    "dry_run_default": False,
    "rules_copy_allowlist": [],
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
    if "max_context_file_kb" in cfg and (not isinstance(cfg["max_context_file_kb"], int) or cfg["max_context_file_kb"] <= 0):
        raise SystemExit("config max_context_file_kb must be positive integer")
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
MAX_CONTEXT_FILE_KB = int(CONFIG.get("max_context_file_kb", 128))
MIN_DOC_BULLETS = CONFIG.get("min_doc_bullets", {}) if isinstance(CONFIG.get("min_doc_bullets", {}), dict) else {}
MAX_NEW_CLARIFICATIONS_PER_ROUND = int(CONFIG.get("max_new_clarifications_per_round", 10))
DRY_RUN_DEFAULT = bool(CONFIG.get("dry_run_default", False))

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


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def emit(args, message: str, **data):
    if getattr(args, "json_output", False):
        payload = {"message": message}
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
    desc_parts = []
    if getattr(args, "desc", None):
        desc_parts.append(str(args.desc).strip())
    if getattr(args, "desc_json", None):
        try:
            data = json.loads(args.desc_json)
        except Exception as ex:
            raise SystemExit(f"invalid --desc-json: {ex}")
        desc_parts.append(_flatten_requirement_obj(data))
    if getattr(args, "desc_file", None):
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
            except Exception as ex:
                raise SystemExit(f"invalid desc json file: {ex}")
        if loaded is None:
            desc_parts.append(raw.strip())
        else:
            desc_parts.append(_flatten_requirement_obj(loaded))
    merged = "\n\n".join([p for p in desc_parts if p]).strip()
    if not merged:
        raise SystemExit("init requires one of --desc, --desc-json, --desc-file")
    return merged


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
    meta_path = path / "metadata.json"
    if not meta_path.exists():
        raise SystemExit("metadata.json not found, run init first")
    try:
        meta = json.loads(read_file(meta_path))
    except Exception:
        raise SystemExit("invalid metadata.json")
    meta["global_memory_hash"] = global_memory_hash()
    meta["global_memory_exists"] = GLOBAL_MEMORY_FILE.exists()
    meta["global_memory_synced_at"] = dt.datetime.now().isoformat(timespec="seconds")
    if dry_run:
        runtime_log(f"[dry-run] would update: {meta_path}")
        return meta
    write_file(meta_path, json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def get_active() -> Path | None:
    if not ACTIVE_FILE.exists():
        return None
    try:
        active = Path(read_file(ACTIVE_FILE).strip())
        if active.exists():
            return active
        return None
    except Exception:
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


def init_docs(path: Path, title: str, original_requirement: str):
    meta = {
        "name": path.name,
        "title": title,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "original_requirement": original_requirement,
        "global_memory_hash": global_memory_hash(),
        "global_memory_exists": GLOBAL_MEMORY_FILE.exists(),
        "global_memory_synced_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    write_file(path / "metadata.json", json.dumps(meta, ensure_ascii=False, indent=2))

    clarifications = f"""# 澄清文档 - {title}

## 说明
- 本文档记录所有需要用户确认、补充和给出解决方案的内容。
- 请在表格中填写 `状态`、`用户确认/补充`、`解决方案`，并补充 `优先级`、`影响范围`、`关联章节`。
- `归属文档` 仅可填写：`analysis`、`prd`、`tech`、`acceptance`、`global`。
- `状态` 仅可填写：`待确认` 或 `已确认`。

## 需求上下文采集
- 项目相关模块/入口：
- 依赖系统/外部接口：
- 数据库连接信息：
- 权限与角色范围：

## 澄清项
{_render_clarification_header()}
| C-001 | 已确认 | 低 | 全局 | global | 示例 | （示例）请确认需求范围的最终边界 | 示例项，可删除或替换 | 示例项，不参与严格闭环 |
"""

    analysis = f"""# 分析报告 - {title}

## 原始需求
{original_requirement}

## 需求上下文采集
- 待补充：项目模块、依赖系统、数据库连接、权限与角色等。

## 项目现状与相关模块
- 待补充：根据代码仓库与现有功能梳理相关模块、接口、业务流程、配置等。

## 候选模块扫描
{SCAN_START}
- 无
{SCAN_END}

## 数据库现状
- 待补充：根据澄清文档提供的数据库连接与表结构核对。

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
        json.dumps(
            {
                "rows": [
                    {
                        "id": "C-001",
                        "status": "已确认",
                        "priority": "低",
                        "impact": "全局",
                        "doc": "global",
                        "section": "示例",
                        "question": "（示例）请确认需求范围的最终边界",
                        "answer": "示例项，可删除或替换",
                        "solution": "示例项，不参与严格闭环",
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    write_file(path / DOC_FILES["analysis"], analysis)
    write_file(path / DOC_FILES["prd"], prd)
    write_file(path / DOC_FILES["tech"], tech)
    write_file(path / DOC_FILES["acceptance"], acceptance)


def init_state_only(path: Path, title: str, original_requirement: str):
    meta = {
        "name": path.name,
        "title": title,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "original_requirement": original_requirement,
        "global_memory_hash": global_memory_hash(),
        "global_memory_exists": GLOBAL_MEMORY_FILE.exists(),
        "global_memory_synced_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    write_file(path / "metadata.json", json.dumps(meta, ensure_ascii=False, indent=2))

    clarifications = f"""# 澄清文档 - {title}

## 说明
- 本文档记录所有需要用户确认、补充和给出解决方案的内容。
- 请在表格中填写 `状态`、`用户确认/补充`、`解决方案`，并补充 `优先级`、`影响范围`、`关联章节`。
- `归属文档` 仅可填写：`analysis`、`prd`、`tech`、`acceptance`、`global`。
- `状态` 仅可填写：`待确认` 或 `已确认`。

## 需求上下文采集
- 项目相关模块/入口：
- 依赖系统/外部接口：
- 数据库连接信息：
- 权限与角色范围：

## 澄清项
{_render_clarification_header()}
| C-001 | 已确认 | 低 | 全局 | global | 示例 | （示例）请确认需求范围的最终边界 | 示例项，可删除或替换 | 示例项，不参与严格闭环 |
"""

    write_file(path / DOC_FILES["clarifications"], clarifications)
    write_file(
        path / DOC_FILES["clarifications_json"],
        json.dumps(
            {
                "rows": [
                    {
                        "id": "C-001",
                        "status": "已确认",
                        "priority": "低",
                        "impact": "全局",
                        "doc": "global",
                        "section": "示例",
                        "question": "（示例）请确认需求范围的最终边界",
                        "answer": "示例项，可删除或替换",
                        "solution": "示例项，不参与严格闭环",
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
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
    except Exception:
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


def extract_db_connections(text: str) -> list[str]:
    patterns = [
        r"\b(?:mysql|postgres|postgresql|mongodb|redis|sqlserver|sqlite)://[^\s'\"`]+",
        r"\b(?:jdbc:[^\s'\"`]+)",
        r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b",
    ]
    found = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    unique = []
    seen = set()
    for item in found:
        key = item.strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)
    filtered = []
    for item in unique:
        if re.match(r"^(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}$", item):
            if any(item in other for other in unique if other != item):
                continue
        filtered.append(item)
    return filtered


def extract_db_config_paths(text: str) -> list[Path]:
    key_re = re.compile(r"(db|database|conn|connect|url|path|配置|连接|数据库|文件路径)", re.IGNORECASE)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    focused = [ln for ln in lines if key_re.search(ln)]
    search_text = "\n".join(focused) if focused else text
    patterns = [
        r"[A-Za-z]:\\[^\s'\"`]+",
        r"(?:\./|\../|/)[^\s'\"`]+",
        r"\b[\w\-.\\/]+\.(?:env|txt|md|json|yaml|yml|ini|cfg|conf)\b",
    ]
    candidates = []
    for pattern in patterns:
        candidates.extend(re.findall(pattern, search_text, flags=re.IGNORECASE))

    paths = []
    seen = set()
    for item in candidates:
        token = item.strip().strip("。,，;；()[]{}")
        if not token:
            continue
        if re.match(r"^[a-z]+://", token, flags=re.IGNORECASE):
            continue
        p = Path(token)
        if not p.is_absolute():
            p = (ROOT / p).resolve()
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        if p.exists() and p.is_file():
            paths.append(p)
    return paths


def read_context_file_limited(path: Path):
    try:
        if path.stat().st_size > MAX_CONTEXT_FILE_KB * 1024:
            return "", f"skipped too large: {path}"
    except Exception:
        return "", f"stat failed: {path}"
    try:
        return path.read_text(encoding="utf-8-sig"), ""
    except Exception:
        try:
            return path.read_text(encoding="utf-8"), ""
        except Exception:
            return "", f"read failed: {path}"


def extract_context_db_connections(text: str):
    direct = extract_db_connections(text)
    file_paths = extract_db_config_paths(text)
    from_files = []
    warnings = []
    for p in file_paths:
        raw, warn = read_context_file_limited(p)
        if warn:
            warnings.append(warn)
        if not raw:
            continue
        from_files.extend(extract_db_connections(raw))
    merged = []
    seen = set()
    for item in direct + from_files:
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged, file_paths, warnings


def inspect_sqlite_schema(conn: str):
    parsed = urlparse(conn)
    if parsed.scheme != "sqlite":
        return None
    db_path = (parsed.path or "").lstrip("/")
    if parsed.netloc:
        db_path = f"{parsed.netloc}/{db_path}".strip("/")
    if not db_path:
        return {"connection": conn, "ok": False, "message": "sqlite path missing"}
    path = Path(db_path)
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
    except Exception as ex:
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
    if password:
        cmd.append(f"-p{password}")
    cmd.extend(["-e", "SHOW TABLES;"])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            return {"connection": conn, "ok": False, "message": f"mysql inspect failed: {proc.stderr.strip()}"}
        tables = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        return {"connection": conn, "ok": True, "message": f"mysql tables: {len(tables)}", "tables": {t: [] for t in tables}}
    except Exception as ex:
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
    except Exception as ex:
        return {"connection": conn, "ok": False, "message": f"postgres inspect failed: {ex}"}


def build_db_schema_summary(connections: list[str]):
    if not connections:
        return "- 未识别到数据库连接信息。"
    lines = []
    for conn in connections:
        if conn.startswith("sqlite://"):
            result = inspect_sqlite_schema(conn)
            if not result:
                lines.append(f"- {conn}：不支持的连接格式")
                continue
            if not result["ok"]:
                lines.append(f"- {conn}：{result['message']}")
                continue
            lines.append(f"- {conn}：{result['message']}")
            tables = result.get("tables", {})
            for t, cols in tables.items():
                col_text = "、".join(cols[:12]) if cols else "无字段"
                lines.append(f"  - 表 `{t}` 字段：{col_text}")
        elif conn.startswith("mysql://"):
            result = inspect_mysql_schema(conn)
            if not result:
                lines.append(f"- {conn}：不支持的连接格式")
                continue
            lines.append(f"- {conn}：{result['message']}")
            if result.get("ok"):
                for t in result.get("tables", {}).keys():
                    lines.append(f"  - 表 `{t}`")
        elif conn.startswith("postgres://") or conn.startswith("postgresql://"):
            result = inspect_postgres_schema(conn)
            if not result:
                lines.append(f"- {conn}：不支持的连接格式")
                continue
            lines.append(f"- {conn}：{result['message']}")
            if result.get("ok"):
                for t in result.get("tables", {}).keys():
                    lines.append(f"  - 表 `{t}`")
        else:
            lines.append(f"- {conn}：暂不支持自动探查（建议调用端按连接执行 schema 查询后回填）。")
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
        return content
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
        "scripts",
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
        except Exception:
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


def load_clar_rows(path: Path):
    clar_path = path / DOC_FILES["clarifications"]
    clar_json_path = path / DOC_FILES["clarifications_json"]
    if not clar_path.exists() and not clar_json_path.exists():
        raise SystemExit("clarifications files not found")

    md_rows = []
    if clar_path.exists():
        md_rows, _ = parse_clarifications_table(read_file(clar_path))
        md_rows = [normalize_clar_row(r) for r in md_rows]
    js_rows = load_clar_rows_from_json(clar_json_path)

    if md_rows and not js_rows:
        save_clar_rows_to_json(clar_json_path, md_rows)
        return md_rows
    if js_rows and not md_rows:
        if clar_path.exists():
            synced = upsert_clar_table_rows(read_file(clar_path), js_rows)
            write_file(clar_path, synced)
        return js_rows
    if not md_rows and not js_rows:
        return []

    md_mtime = clar_path.stat().st_mtime if clar_path.exists() else 0
    js_mtime = clar_json_path.stat().st_mtime if clar_json_path.exists() else 0
    chosen = md_rows if md_mtime >= js_mtime else js_rows
    other = js_rows if chosen is md_rows else md_rows
    if chosen != other:
        save_clar_rows_to_json(clar_json_path, chosen)
        if clar_path.exists():
            synced = upsert_clar_table_rows(read_file(clar_path), chosen)
            write_file(clar_path, synced)
    return chosen


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
        table = _render_clarification_header() + "\n" + render_clarification_table_rows(rows, CLARIFY_COLUMNS)
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


def ensure_runtime_context_clarifications(path: Path, context_text: str, dry_run: bool = False):
    db_connections, file_paths, warnings = extract_context_db_connections(context_text)
    if not db_connections:
        return
    clar_path = path / DOC_FILES["clarifications"]
    clar_content = read_file(clar_path)
    rows, _ = parse_clarifications_table(clar_content)
    max_id = 0
    for row in rows:
        m = re.match(r"C-(\d+)", row.get("id", ""))
        if m:
            max_id = max(max_id, int(m.group(1)))
    merged = "；".join(db_connections)
    path_info = ""
    if file_paths:
        path_info = "；来源文件：" + "；".join(str(p) for p in file_paths)
    if warnings:
        path_info += "；处理提示：" + "；".join(warnings)
    new_items = [{
        "id": f"C-{max_id + 1:03d}",
        "status": CONFIRMED_STATUS,
        "priority": "高",
        "impact": "数据库",
        "doc": "analysis",
        "section": "需求上下文采集",
        "question": "需求已提供数据库连接信息，可用于分析阶段拉取库表结构。",
        "answer": merged + path_info,
        "solution": "分析阶段先连接数据库读取 schema，再更新需求覆盖矩阵与差距分析。",
    }]
    updated = add_clarifications(clar_content, new_items)
    if dry_run:
        runtime_log("[dry-run] would append runtime DB clarification")
        return
    persist_clarifications(path, updated, dry_run=False)



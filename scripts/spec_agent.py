#!/usr/bin/env python
import argparse
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "spec-agent.config.json"

DEFAULT_CONFIG = {
    "spec_dir": "spec",
    "date_format": "%Y-%m-%d",
    "placeholders": ["TODO", "TBD", "待补充", "待确认", "（待）"],
    "prd_tech_words": ["数据库", "SQL", "表", "接口", "API", "代码", "架构", "技术方案", "实现"],
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
    "rules_copy_allowlist": [],
}

DOC_FILES = {
    "clarifications": "00-clarifications.md",
    "analysis": "01-analysis.md",
    "prd": "02-prd.md",
    "tech": "03-tech.md",
    "acceptance": "04-acceptance.md",
}

CLARIFY_START = "<!-- CLARIFICATIONS:START -->"
CLARIFY_END = "<!-- CLARIFICATIONS:END -->"
SCAN_START = "<!-- SCAN:START -->"
SCAN_END = "<!-- SCAN:END -->"

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


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update({k: v for k, v in loaded.items() if v is not None})
        except json.JSONDecodeError:
            raise SystemExit("invalid spec-agent.config.json")
    return cfg


CONFIG = load_config()
SPEC_DIR = Path(CONFIG["spec_dir"]).expanduser()
if not SPEC_DIR.is_absolute():
    SPEC_DIR = ROOT / SPEC_DIR
ACTIVE_FILE = SPEC_DIR / ".active"

PLACEHOLDERS = CONFIG["placeholders"]
PRD_TECH_WORDS = CONFIG["prd_tech_words"]
CLARIFY_COLUMNS = CONFIG["clarify_columns"]
CLARIFY_STATUSES = set(CONFIG["clarify_statuses"])


def ensure_spec_dir():
    SPEC_DIR.mkdir(parents=True, exist_ok=True)


def today_str():
    return dt.date.today().strftime(CONFIG["date_format"])


def requirement_dir(date_str: str, name: str) -> Path:
    return SPEC_DIR / date_str / name


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def set_active(path: Path):
    ensure_spec_dir()
    ACTIVE_FILE.write_text(str(path), encoding="utf-8")


def get_active() -> Path | None:
    if not ACTIVE_FILE.exists():
        return None
    try:
        return Path(read_file(ACTIVE_FILE).strip())
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
| C-001 | 待确认 |  |  | global |  | （示例）请确认需求范围的最终边界 |  |  |
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
| 编号 | 验收项 | 预期结果 | 验证方式 |
|---|---|---|---|
| A-001 | 待补充 | 待补充 | 待补充 |

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
    write_file(path / DOC_FILES["analysis"], analysis)
    write_file(path / DOC_FILES["prd"], prd)
    write_file(path / DOC_FILES["tech"], tech)
    write_file(path / DOC_FILES["acceptance"], acceptance)


def _normalize_header(cell: str) -> str:
    cell = cell.strip()
    return HEADER_KEY_MAP.get(cell, cell)


def parse_clarifications_table(content: str):
    lines = content.splitlines()
    header_idx = None
    header_cells = None
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "ID" in line and "状态" in line:
            header_idx = i
            header_cells = [c.strip() for c in line.strip().strip("|").split("|")]
            break
    if header_idx is None or header_cells is None:
        return [], []
    keys = [_normalize_header(c) for c in header_cells]
    data_start = header_idx + 2
    rows = []
    for line in lines[data_start:]:
        if not line.strip().startswith("|"):
            break
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if not parts:
            continue
        row = {keys[i]: parts[i] if i < len(parts) else "" for i in range(len(keys))}
        rows.append(row)
    return rows, header_cells


def render_clarified(rows, doc_key):
    items = [
        r for r in rows
        if r.get("status") == "已确认" and r.get("doc") in (doc_key, "global")
    ]
    if not items:
        return "- 无"
    out = []
    for r in items:
        line = f"- [{r.get('id', '')}] {r.get('question', '')}"
        meta = []
        if r.get("priority"):
            meta.append(f"优先级:{r['priority']}")
        if r.get("impact"):
            meta.append(f"影响范围:{r['impact']}")
        if r.get("section"):
            meta.append(f"关联章节:{r['section']}")
        if meta:
            line += f"（{'；'.join(meta)}）"
        if r.get("answer"):
            line += f"；用户确认/补充：{r['answer']}"
        if r.get("solution"):
            line += f"；解决方案：{r['solution']}"
        out.append(line)
    return "\n".join(out)


def replace_clarification_block(content: str, block: str):
    if CLARIFY_START not in content or CLARIFY_END not in content:
        return content
    pattern = re.compile(
        re.escape(CLARIFY_START) + r"[\s\S]*?" + re.escape(CLARIFY_END),
        re.MULTILINE,
    )
    return pattern.sub(f"{CLARIFY_START}\n{block}\n{CLARIFY_END}", content)


def replace_scan_block(content: str, block: str):
    if SCAN_START not in content or SCAN_END not in content:
        return content
    pattern = re.compile(
        re.escape(SCAN_START) + r"[\s\S]*?" + re.escape(SCAN_END),
        re.MULTILINE,
    )
    return pattern.sub(f"{SCAN_START}\n{block}\n{SCAN_END}", content)


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
    for path in ROOT.rglob("*"):
        if path.is_dir():
            if path.name in ignore_dirs:
                continue
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


def update_docs(path: Path):
    clar_path = path / DOC_FILES["clarifications"]
    if not clar_path.exists():
        raise SystemExit("clarifications file not found")
    rows, _header = parse_clarifications_table(read_file(clar_path))
    for key in ("analysis", "prd", "tech", "acceptance"):
        doc_path = path / DOC_FILES[key]
        if not doc_path.exists():
            continue
        content = read_file(doc_path)
        block = render_clarified(rows, key)
        updated = replace_clarification_block(content, block)
        if updated != content:
            write_file(doc_path, updated)


def next_clarify_id(rows):
    max_id = 0
    for r in rows:
        m = re.match(r"C-(\d+)", r.get("id", ""))
        if m:
            max_id = max(max_id, int(m.group(1)))
    return f"C-{max_id + 1:03d}"


def _find_table_indices(lines):
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "ID" in line and "状态" in line:
            header_idx = i
            break
    if header_idx is None:
        return None, None, []
    header_cells = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    sep_idx = header_idx + 1 if header_idx + 1 < len(lines) else None
    return header_idx, sep_idx, header_cells


def add_clarifications(clar_content: str, new_items):
    lines = clar_content.splitlines()
    header_idx, sep_idx, header_cells = _find_table_indices(lines)
    if header_idx is None or sep_idx is None:
        return clar_content

    rows, _ = parse_clarifications_table(clar_content)
    existing_questions = set(r.get("question", "") for r in rows)

    def build_row(item):
        values = []
        for cell in header_cells:
            key = _normalize_header(cell)
            if key == "id":
                values.append(item["id"])
            elif key == "status":
                values.append("待确认")
            elif key == "doc":
                values.append(item["doc"])
            elif key == "question":
                values.append(item["question"])
            else:
                values.append("")
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


def final_check(path: Path):
    issues = []

    def add_issue(doc, question):
        issues.append({"doc": doc, "question": question})

    # Analysis checks
    analysis_path = path / DOC_FILES["analysis"]
    if analysis_path.exists():
        content = read_file(analysis_path)
        if "代码" not in content or "数据库" not in content:
            add_issue("analysis", "分析报告未明确说明代码与数据库现状，请补充。")
        if "需求覆盖矩阵" not in content:
            add_issue("analysis", "分析报告缺少需求覆盖矩阵，请补充。")
        if any(p in content for p in PLACEHOLDERS):
            add_issue("analysis", "分析报告仍包含占位内容，请补充完整。")

    # PRD checks
    prd_path = path / DOC_FILES["prd"]
    if prd_path.exists():
        content = read_file(prd_path)
        if any(word in content for word in PRD_TECH_WORDS):
            add_issue("prd", "PRD 中包含实现或技术细节，请移除。")
        if "非功能性需求" not in content:
            add_issue("prd", "PRD 缺少非功能性需求，请补充。")
        if any(p in content for p in PLACEHOLDERS):
            add_issue("prd", "PRD 仍包含占位内容，请补充完整。")

    # Tech checks
    tech_path = path / DOC_FILES["tech"]
    if tech_path.exists():
        content = read_file(tech_path)
        if "数据库设计" not in content or "SQL" not in content:
            add_issue("tech", "技术方案缺少数据库设计或可执行 SQL。")
        if "数据迁移与回滚策略" not in content:
            add_issue("tech", "技术方案缺少数据迁移与回滚策略，请补充。")
        if any(p in content for p in PLACEHOLDERS):
            add_issue("tech", "技术方案仍包含占位内容，请补充完整。")

    # Acceptance checks
    acc_path = path / DOC_FILES["acceptance"]
    if acc_path.exists():
        content = read_file(acc_path)
        if "| 编号 | 验收项 | 预期结果 | 验证方式 |" not in content:
            add_issue("acceptance", "验收清单缺少标准验收项表头。")
        if any(p in content for p in PLACEHOLDERS):
            add_issue("acceptance", "验收清单仍包含占位内容，请补充完整。")

    clar_path = path / DOC_FILES["clarifications"]
    if not clar_path.exists():
        raise SystemExit("clarifications file not found")
    clar_content = read_file(clar_path)
    rows, _ = parse_clarifications_table(clar_content)
    existing_questions = set(r.get("question", "") for r in rows)

    new_items = []
    for issue in issues:
        if issue["question"] in existing_questions:
            continue
        new_items.append({
            "id": next_clarify_id(rows),
            "doc": issue["doc"],
            "question": issue["question"],
        })
        rows.append({"id": new_items[-1]["id"]})

    if new_items:
        updated = add_clarifications(clar_content, new_items)
        write_file(clar_path, updated)

    return issues


def has_unconfirmed(rows):
    for r in rows:
        status = r.get("status", "").strip()
        question = r.get("question", "").strip()
        if question and status != "已确认":
            return True
    return False


def resolve_path(args):
    if args.path:
        return Path(args.path)
    if args.name:
        matches = find_requirement(args.name)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise SystemExit("multiple requirements found, use --path")
        raise SystemExit("requirement not found")
    active = get_active()
    if active:
        return active
    raise SystemExit("no active requirement, use --name or --path")


def cmd_init(args):
    date_str = args.date or today_str()
    path = requirement_dir(date_str, args.name)
    if path.exists():
        raise SystemExit("requirement already exists")
    init_docs(path, args.title or args.name, args.desc)
    set_active(path)
    print(f"initialized: {path}")


def cmd_list(_args):
    items = list_requirements()
    active = get_active()
    for item in items:
        mark = "*" if active and item == active else " "
        print(f"{mark} {item}")


def cmd_set_active(args):
    if args.path:
        path = Path(args.path)
    elif args.name:
        matches = find_requirement(args.name)
        if len(matches) != 1:
            raise SystemExit("requirement not found or not unique")
        path = matches[0]
    else:
        raise SystemExit("use --name or --path")
    if not path.exists():
        raise SystemExit("path not found")
    set_active(path)
    print(f"active: {path}")


def cmd_update(args):
    path = resolve_path(args)
    clar_path = path / DOC_FILES["clarifications"]
    if clar_path.exists():
        rows, _ = parse_clarifications_table(read_file(clar_path))
        if args.strict and has_unconfirmed(rows):
            raise SystemExit("clarifications not closed; confirm items or rerun without --strict")
    update_docs(path)
    issues = final_check(path)
    print(f"updated: {path}")
    print(f"final-check issues: {len(issues)}")


def cmd_final_check(args):
    path = resolve_path(args)
    issues = final_check(path)
    print(f"final-check issues: {len(issues)}")


def cmd_copy_rules(args):
    dest = Path(args.dest) if args.dest else (ROOT / ".cursor" / "rules")
    dest.mkdir(parents=True, exist_ok=True)
    src = ROOT / "rules"
    allowlist = CONFIG.get("rules_copy_allowlist") or []
    for item in src.glob("*.mdc"):
        if item.name not in allowlist:
            continue
        target = dest / item.name
        target.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"copied rules to: {dest}")
    if not allowlist:
        print("warning: rules_copy_allowlist is empty, nothing copied")


def cmd_scan(args):
    path = resolve_path(args)
    analysis_path = path / DOC_FILES["analysis"]
    if not analysis_path.exists():
        raise SystemExit("analysis file not found")
    modules = scan_modules()
    if modules:
        block = "\n".join([f"- {m}" for m in modules])
    else:
        block = "- 无"
    content = read_file(analysis_path)
    updated = replace_scan_block(content, block)
    if updated != content:
        write_file(analysis_path, updated)
    print(f"scanned modules: {len(modules)}")


def build_parser():
    p = argparse.ArgumentParser(prog="spec_agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--name", required=True, help="requirement english name")
    p_init.add_argument("--title", help="requirement title")
    p_init.add_argument("--desc", required=True, help="original requirement")
    p_init.add_argument("--date", help="date (YYYY-MM-DD)")
    p_init.set_defaults(func=cmd_init)

    p_list = sub.add_parser("list")
    p_list.set_defaults(func=cmd_list)

    p_set = sub.add_parser("set-active")
    p_set.add_argument("--name")
    p_set.add_argument("--path")
    p_set.set_defaults(func=cmd_set_active)

    p_update = sub.add_parser("update")
    p_update.add_argument("--name")
    p_update.add_argument("--path")
    p_update.add_argument("--strict", action="store_true", help="block update if clarifications not confirmed")
    p_update.set_defaults(func=cmd_update)

    p_check = sub.add_parser("final-check")
    p_check.add_argument("--name")
    p_check.add_argument("--path")
    p_check.set_defaults(func=cmd_final_check)

    p_rules = sub.add_parser("copy-rules")
    p_rules.add_argument("--dest")
    p_rules.set_defaults(func=cmd_copy_rules)

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--name")
    p_scan.add_argument("--path")
    p_scan.set_defaults(func=cmd_scan)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    ensure_spec_dir()
    args.func(args)


if __name__ == "__main__":
    main()

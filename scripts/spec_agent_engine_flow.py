#!/usr/bin/env python
from spec_agent_engine_core import *
from spec_agent_engine_core import _normalize_header


def render_clarified(rows, doc_key):
    items = [
        r for r in rows
        if r.get("status") == CONFIRMED_STATUS and r.get("doc") in (doc_key, "global")
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


def replace_clarification_block(content: str, block: str):
    if CLARIFY_START not in content or CLARIFY_END not in content:
        return content
    pattern = re.compile(
        re.escape(CLARIFY_START) + r"[\s\S]*?" + re.escape(CLARIFY_END),
        re.MULTILINE,
    )
    replacement = f"{CLARIFY_START}\n{block}\n{CLARIFY_END}"
    return pattern.sub(lambda _m: replacement, content)


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


def extract_section_blocks(content: str):
    matches = list(SECTION_HEADING_RE.finditer(content))
    blocks = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        heading = match.group(0).strip()
        block = content[start:end].rstrip() + "\n"
        blocks.append((heading, block))
    return blocks


def replace_section_block(content: str, heading: str, new_block: str):
    section_id = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", heading).strip("-").lower()
    if not section_id:
        section_id = f"sec-{hashlib.md5(heading.encode('utf-8')).hexdigest()[:8]}"
    start_tag = f"<!-- AUTOSEC:{section_id}:START -->"
    end_tag = f"<!-- AUTOSEC:{section_id}:END -->"
    marked_pattern = re.compile(
        re.escape(start_tag) + r"[\s\S]*?" + re.escape(end_tag),
        re.MULTILINE,
    )
    pattern = re.compile(
        rf"^{re.escape(heading)}\n[\s\S]*?(?=^## |\Z)",
        re.MULTILINE,
    )
    replacement = f"{start_tag}\n{new_block.rstrip()}\n{end_tag}\n"
    if marked_pattern.search(content):
        return marked_pattern.sub(lambda _m: replacement, content, count=1), True
    if pattern.search(content):
        return pattern.sub(lambda _m: replacement, content, count=1), True
    return content, False


def merge_generated_sections(existing: str, generated: str):
    merged = existing
    changed = False
    for heading, block in extract_section_blocks(generated):
        merged, replaced = replace_section_block(merged, heading, block)
        if replaced:
            changed = True
        else:
            if not merged.endswith("\n"):
                merged += "\n"
            merged += "\n" + block
            changed = True
    return merged if changed else existing


def write_generated_doc(path: Path, generated: str, dry_run: bool = False):
    if path.exists():
        existing = read_file(path)
        merged = merge_generated_sections(existing, generated)
        if dry_run:
            runtime_log(f"[dry-run] would update: {path}")
            return
        write_file(path, merged)
        return
    if dry_run:
        runtime_log(f"[dry-run] would create: {path}")
        return
    write_file(path, generated)


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

    # Fast path: use ripgrep file listing when available.
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

    # Fallback: Python traversal.
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


def update_docs(path: Path):
    clar_path = path / DOC_FILES["clarifications"]
    if not clar_path.exists():
        raise SystemExit("clarifications file not found")
    rows = load_clar_rows(path)
    for key in ("analysis", "prd", "tech", "acceptance"):
        doc_path = path / DOC_FILES[key]
        if not doc_path.exists():
            continue
        content = read_file(doc_path)
        block = render_clarified(rows, key)
        updated = replace_clarification_block(content, block)
        if updated != content:
            write_file(doc_path, updated)


def ensure_seed_clarifications(path: Path, doc_key: str, dry_run: bool = False):
    if not ENABLE_AUTO_SEEDS:
        return
    questions = DOC_CLARIFY_SEEDS.get(doc_key, [])
    if MAX_SEED_PER_DOC > 0:
        questions = questions[:MAX_SEED_PER_DOC]
    if not questions:
        return
    clar_path = path / DOC_FILES["clarifications"]
    if not clar_path.exists():
        raise SystemExit("clarifications file not found")
    clar_content = read_file(clar_path)
    rows, _ = parse_clarifications_table(clar_content)
    existing_questions = set(r.get("question", "") for r in rows)
    max_id = 0
    for row in rows:
        m = re.match(r"C-(\d+)", row.get("id", ""))
        if m:
            max_id = max(max_id, int(m.group(1)))
    new_items = []
    next_num = max_id
    for question in questions:
        if question in existing_questions:
            continue
        next_num += 1
        new_items.append({
            "id": f"C-{next_num:03d}",
            "doc": doc_key,
            "question": question,
        })
    if not new_items:
        return
    updated = add_clarifications(clar_content, new_items)
    if dry_run:
        runtime_log(f"[dry-run] would append seed clarifications for: {doc_key}")
        return
    persist_clarifications(path, updated, dry_run=False)


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


def split_requirement_points(desc: str) -> list[str]:
    lines = [line.strip(" -\t") for line in desc.splitlines() if line.strip()]
    points = []
    for line in lines:
        if len(line) < 4:
            continue
        points.append(line)
    if not points:
        chunks = [c.strip() for c in re.split(r"[。；;\n]", desc) if c.strip()]
        points = [c for c in chunks if len(c) >= 4]
    if not points:
        points = [desc.strip()]
    return points[:8]


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


def build_analysis_doc(title: str, desc: str, modules: list[str], points: list[str], clarified_block: str, db_connections: list[str]) -> str:
    module_text = "、".join(modules) if modules else "未扫描到候选模块"
    scan_block = "\n".join([f"- {m}" for m in modules]) if modules else "- 无"
    db_hint = "；".join(db_connections) if db_connections else ""
    db_guidance = (
        f"- 已识别数据库连接信息：{db_hint}\n- 调用端应在分析阶段连接数据库并拉取库表结构（表、字段、索引、约束）后更新本报告。"
        if db_connections
        else "- 当前尚未接入数据库连接信息，无法完成表结构与字段映射核对。\n- 待澄清文档补充连接信息后，补充查询结果与影响分析。"
    )
    matrix_rows = []
    for idx, point in enumerate(points, start=1):
        rid = f"R-{idx:02d}"
        matrix_rows.append(f"| {rid} {point} | {module_text} | 部分满足 | 需结合代码与数据库现状进一步核对 |")
    matrix_text = "\n".join(matrix_rows)
    return f"""# 分析报告 - {title}

## 原始需求
{desc}

## 需求上下文采集
- 项目相关模块：{module_text}
- 依赖系统：待用户在澄清文档确认
- 数据库连接信息：待用户在澄清文档确认
- 权限与角色范围：待用户在澄清文档确认

## 项目现状与相关模块
- 已基于代码目录完成首轮扫描，候选模块用于后续逐项核对。
- 需要结合调用链与业务流程确认每个需求点的落点位置。

## 候选模块扫描
{SCAN_START}
{scan_block}
{SCAN_END}

## 数据库现状
{db_guidance}
{DB_SCHEMA_START}
- 未执行数据库自动探查。可运行 `inspect-db` 追加 schema 摘要。
{DB_SCHEMA_END}

## 需求覆盖矩阵
| 需求点 | 现有模块/表 | 是否满足 | 差距/说明 |
|---|---|---|---|
{matrix_text}

## 需求满足性分析
- 首版结论：需求与现有代码可能存在部分重合能力，但仍需要数据库与业务规则确认后才能给出最终满足性结论。
- 优先核对项：数据口径、状态流转规则、权限边界。

## 风险与影响
- 需求边界未闭环会导致范围漂移。
- 数据库结构未知会影响设计与验收准确性。
- 受影响功能需在验收清单中增加回归验证。

## 结论
- 当前可进入方案设计与澄清并行阶段。
- 在澄清项闭环后更新为最终分析结论。

## 澄清补充
{CLARIFY_START}
{clarified_block}
{CLARIFY_END}
"""


def build_prd_doc(title: str, desc: str, points: list[str], clarified_block: str) -> str:
    point_lines = "\n".join([f"- {p}" for p in points])
    branch_lines = "\n".join([f"- 场景{idx}：{p}；异常分支：输入不完整、状态冲突、权限不足；处理方式：给出明确提示并保留可恢复路径。" for idx, p in enumerate(points, start=1)])
    trace_rows = []
    for idx, point in enumerate(points, start=1):
        rid = f"R-{idx:02d}"
        trace_rows.append(f"| {rid} | {point} | 围绕该需求点定义主流程与分支规则 |")
    trace_text = "\n".join(trace_rows)
    return f"""# PRD - {title}

## 需求范围与边界
- 范围内：围绕以下需求点交付完整业务能力。
{point_lines}
- 范围外：未在原始需求中明确提及的扩展诉求不纳入本期。

## 简要说明
- 来源与背景：基于用户提出的业务诉求形成本需求。
- 用途：统一业务动作入口与处理标准，减少人工判断差异。
- 解决问题：口径不一致、流程不闭环、异常场景缺少处理规则。

## 产品功能描述与业务流程
- 主流程：用户发起业务动作 -> 系统校验输入与前置条件 -> 完成动作 -> 返回结果并记录状态。
- 关键规则：动作可追踪、结果可核验、失败可说明。

## 需求项映射
| 需求ID | 需求描述 | PRD 功能定义 |
|---|---|---|
{trace_text}

## 分支流程与异常处理
{branch_lines}

## 非功能性需求
- 响应目标：常规请求响应稳定。
- 可用性：失败时可重试且有可理解提示。
- 权限性：仅允许有授权的角色执行对应动作。
- 一致性：同一业务输入应得到一致结果。

## 待确认需求点
- 业务成功判定口径是否有统一标准。
- 异常状态下是否允许人工干预。
- 历史数据是否需要补齐或修正。

## 冲突与影响
- 可能与现有业务规则冲突：状态定义、权限边界、数据口径。
- 受影响范围：相关业务流程、统计口径、上下游依赖方。
- 建议处理：以澄清文档为唯一确认来源，闭环后统一更新文档。

## 澄清补充
{CLARIFY_START}
{clarified_block}
{CLARIFY_END}
"""


def build_tech_doc(title: str, req_name: str, points: list[str], modules: list[str], clarified_block: str) -> str:
    module_text = "、".join(modules) if modules else "未扫描到候选模块"
    code_stub = f"""```python
def execute_{req_name}(payload, user):
    validate_payload(payload)
    check_permission(user, payload)
    result = run_business_flow(payload)
    persist_audit_log(user, payload, result)
    return result
```"""
    sql_stub = f"""```sql
-- 示例：需求主记录表
CREATE TABLE IF NOT EXISTS {req_name}_record (
  id BIGINT PRIMARY KEY,
  biz_key VARCHAR(128) NOT NULL,
  status VARCHAR(32) NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_{req_name}_record_biz_key
ON {req_name}_record (biz_key);
```"""
    test_lines = "\n".join([f"- 用例{idx}：{p}，覆盖成功路径与关键失败路径。" for idx, p in enumerate(points, start=1)])
    impl_rows = []
    for idx, point in enumerate(points, start=1):
        rid = f"R-{idx:02d}"
        impl_rows.append(f"| {rid} | 规则编排 + 数据落库 + 审计记录 | `{req_name}_record` |")
    impl_text = "\n".join(impl_rows)
    return f"""# 技术方案 - {title}

## 当前项目/功能情况
- 候选模块：{module_text}
- 代码中已存在相关能力，但需补充状态规则与数据核验路径。

## 实现目标
- 目标1：将需求点转化为可执行业务流程。
- 目标2：保证数据可追踪、可回放、可核验。
- 目标3：控制对现有功能的影响并保证回归稳定。

## 整体架构设计思路
- 入口层负责参数与权限校验。
- 领域层负责业务规则编排。
- 持久层负责数据落库与审计记录。
- 观测层负责日志与指标记录。

## 需求实现映射
| 需求ID | 实现要点 | 数据影响 |
|---|---|---|
{impl_text}

## 架构图
```mermaid
flowchart LR
  A[业务入口] --> B[规则编排]
  B --> C[数据存储]
  B --> D[审计记录]
  D --> E[监控告警]
```

## 数据库设计
- 设计目标：主数据、状态、审计信息可追踪。
- 关键字段：业务键、状态、请求快照、时间戳。
- 索引策略：围绕业务键与创建时间建立索引。

## 可执行 SQL
{sql_stub}

## 核心功能代码片段
{code_stub}

## 单元测试
{test_lines}
- 回归测试：验证受影响功能在相同输入下行为不变。

## 数据迁移与回滚策略
- 迁移：先建表与索引，再灰度写入，再切换读路径。
- 回滚：保留旧路径开关，异常时切回旧流程并保留审计数据。

## 注意事项
- 上线前需完成数据库连接与权限配置澄清。
- 任何业务规则调整必须同步更新验收清单。

## 澄清补充
{CLARIFY_START}
{clarified_block}
{CLARIFY_END}
"""


def build_acceptance_doc(title: str, req_name: str, points: list[str], clarified_block: str) -> str:
    rows = []
    for idx, point in enumerate(points, start=1):
        aid = f"A-{idx:03d}"
        rows.append(
            f"| {aid} | {point}（R-{idx:02d}） | 返回结果符合规则且状态正确 | 调用业务动作后，查询 `{req_name}_record` 对应 `biz_key` 与 `status` |"
        )
    row_text = "\n".join(rows)
    return f"""# 验收清单 - {title}

## 验收项清单
| 编号 | 验收项 | 预期结果 | 验证方式 |
|---|---|---|---|
{row_text}

## 受影响功能验证
- 验证原有业务入口在未触发新需求条件下行为保持不变。
- 验证统计口径未出现重复计算或遗漏。
- 验证权限边界未放大。
- 验证异常场景下错误提示可理解且可恢复。
- 验证审计日志与业务状态变更一致。

## 数据库核对指引
- 新增：调用动作后查询 `{req_name}_record` 是否存在对应业务键。
- 查询：结果与数据库中的状态、时间戳一致。
- 更新：二次动作后 `status` 与 `updated_at` 更新符合预期。

## 澄清补充
{CLARIFY_START}
{clarified_block}
{CLARIFY_END}
"""


def generate_initial_docs(path: Path, title: str, desc: str):
    points = split_requirement_points(desc)
    modules = scan_modules()

    db_connections, _, _ = extract_context_db_connections(desc)
    analysis = build_analysis_doc(title, desc, modules, points, "- 无", db_connections)
    prd = build_prd_doc(title, desc, points, "- 无")
    tech = build_tech_doc(title, path.name, points, modules, "- 无")
    acceptance = build_acceptance_doc(title, path.name, points, "- 无")

    write_file(path / DOC_FILES["analysis"], analysis)
    write_file(path / DOC_FILES["prd"], prd)
    write_file(path / DOC_FILES["tech"], tech)
    write_file(path / DOC_FILES["acceptance"], acceptance)

    clar_path = path / DOC_FILES["clarifications"]
    clar_content = read_file(clar_path)
    rows, _ = parse_clarifications_table(clar_content)
    base_max = 0
    for row in rows:
        m = re.match(r"C-(\d+)", row.get("id", ""))
        if m:
            base_max = max(base_max, int(m.group(1)))

    def next_id(offset: int) -> str:
        return f"C-{base_max + offset:03d}"

    seed_items = [
        {"id": next_id(1), "doc": "analysis", "question": "请提供可用的数据库连接信息与库名，用于完成现状核对。"},
        {"id": next_id(2), "doc": "prd", "question": "请确认需求范围外是否包含历史数据修正。"},
        {"id": next_id(3), "doc": "tech", "question": "请确认上线窗口与回滚时限要求。"},
    ]
    updated = add_clarifications(clar_content, seed_items)
    persist_clarifications(path, updated, dry_run=False)


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




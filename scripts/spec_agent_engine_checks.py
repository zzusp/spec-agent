#!/usr/bin/env python
from spec_agent_engine_flow import *


def final_check(path: Path, write_back: bool = True):
    issues = []

    def add_issue(doc, question):
        issues.append({"doc": doc, "question": question})

    def strip_clarification_block(content: str):
        pattern = re.compile(
            re.escape(CLARIFY_START) + r"[\s\S]*?" + re.escape(CLARIFY_END),
            re.MULTILINE,
        )
        return pattern.sub("", content)

    def has_prd_tech_detail(content: str):
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#") or line.startswith("|"):
                continue
            if any(token in line for token in PRD_TECH_WHITELIST):
                continue
            if re.search(r"```|CREATE\s+TABLE|SELECT\s+.+\s+FROM|ALTER\s+TABLE|INSERT\s+INTO|/api/|class\s+\w+|def\s+\w+\(", line, flags=re.IGNORECASE):
                return True
            if any(word in line for word in PRD_TECH_WORDS_EFFECTIVE):
                return True
        return False

    def bullet_count(content: str):
        return len(re.findall(r"^\s*-\s+", content, flags=re.MULTILINE))

    # Analysis checks
    analysis_path = path / DOC_FILES["analysis"]
    if analysis_path.exists():
        content = read_file(analysis_path)
        check_content = strip_clarification_block(content)
        if "代码" not in check_content or "数据库" not in check_content:
            add_issue("analysis", "分析报告未明确说明代码与数据库现状，请补充。")
        if "需求覆盖矩阵" not in check_content:
            add_issue("analysis", "分析报告缺少需求覆盖矩阵，请补充。")
        if any(p in check_content for p in PLACEHOLDERS_EFFECTIVE):
            add_issue("analysis", "分析报告仍包含占位内容，请补充完整。")
        if bullet_count(check_content) < int(MIN_DOC_BULLETS.get("analysis", 0)):
            add_issue("analysis", "分析报告信息密度不足，请补充关键要点。")

    # PRD checks
    prd_path = path / DOC_FILES["prd"]
    if prd_path.exists():
        content = read_file(prd_path)
        check_content = strip_clarification_block(content)
        if has_prd_tech_detail(check_content):
            add_issue("prd", "PRD 中包含实现或技术细节，请移除。")
        if "非功能性需求" not in check_content:
            add_issue("prd", "PRD 缺少非功能性需求，请补充。")
        if any(p in check_content for p in PLACEHOLDERS_EFFECTIVE):
            add_issue("prd", "PRD 仍包含占位内容，请补充完整。")
        if bullet_count(check_content) < int(MIN_DOC_BULLETS.get("prd", 0)):
            add_issue("prd", "PRD 信息密度不足，请补充关键要点。")

    # Tech checks
    tech_path = path / DOC_FILES["tech"]
    if tech_path.exists():
        content = read_file(tech_path)
        check_content = strip_clarification_block(content)
        if "数据库设计" not in check_content or "SQL" not in check_content:
            add_issue("tech", "技术方案缺少数据库设计或可执行 SQL。")
        if "数据迁移与回滚策略" not in check_content:
            add_issue("tech", "技术方案缺少数据迁移与回滚策略，请补充。")
        if any(p in check_content for p in PLACEHOLDERS_EFFECTIVE):
            add_issue("tech", "技术方案仍包含占位内容，请补充完整。")
        if bullet_count(check_content) < int(MIN_DOC_BULLETS.get("tech", 0)):
            add_issue("tech", "技术方案信息密度不足，请补充关键要点。")

    # Acceptance checks
    acc_path = path / DOC_FILES["acceptance"]
    if acc_path.exists():
        content = read_file(acc_path)
        check_content = strip_clarification_block(content)
        if "| 编号 | 验收项 | 预期结果 | 验证方式 |" not in check_content:
            add_issue("acceptance", "验收清单缺少标准验收项表头。")
        if any(p in check_content for p in PLACEHOLDERS_EFFECTIVE):
            add_issue("acceptance", "验收清单仍包含占位内容，请补充完整。")
        if bullet_count(check_content) < int(MIN_DOC_BULLETS.get("acceptance", 0)):
            add_issue("acceptance", "验收清单信息密度不足，请补充关键要点。")

    # Cross-doc consistency checks (R-xx mapping)
    def collect_rids(doc_path: Path):
        if not doc_path.exists():
            return set()
        return set(re.findall(r"\bR-\d+\b", strip_clarification_block(read_file(doc_path))))

    analysis_rids = collect_rids(path / DOC_FILES["analysis"])
    if analysis_rids:
        prd_rids = collect_rids(path / DOC_FILES["prd"])
        tech_rids = collect_rids(path / DOC_FILES["tech"])
        acc_rids = collect_rids(path / DOC_FILES["acceptance"])
        if analysis_rids - prd_rids:
            add_issue("prd", "PRD 缺少部分需求ID映射（R-xx），请补齐与分析报告一致。")
        if analysis_rids - tech_rids:
            add_issue("tech", "技术方案缺少部分需求ID映射（R-xx），请补齐与分析报告一致。")
        if analysis_rids - acc_rids:
            add_issue("acceptance", "验收清单缺少部分需求ID映射（R-xx），请补齐与分析报告一致。")

    clar_path = path / DOC_FILES["clarifications"]
    if not clar_path.exists():
        raise SystemExit("clarifications file not found")
    clar_content = read_file(clar_path)
    rows, _ = parse_clarifications_table(clar_content)
    for row in rows:
        status = row.get("status", "").strip()
        if status and status not in CLARIFY_STATUSES:
            add_issue("global", f"澄清文档存在非法状态值：{status}，请使用配置允许状态。")
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

    if new_items and write_back:
        updated = add_clarifications(clar_content, new_items)
        persist_clarifications(path, updated, dry_run=False)

    return issues


def has_unconfirmed(rows):
    for r in rows:
        status = r.get("status", "").strip()
        question = r.get("question", "").strip()
        if question.startswith("（示例）"):
            continue
        if question and (status != CONFIRMED_STATUS or (status and status not in CLARIFY_STATUSES)):
            return True
    return False


def list_unconfirmed(rows):
    pending = []
    for r in rows:
        status = r.get("status", "").strip()
        question = r.get("question", "").strip()
        if not question or question.startswith("（示例）"):
            continue
        if status != CONFIRMED_STATUS or (status and status not in CLARIFY_STATUSES):
            pending.append((r.get("id", ""), question))
    return pending


def resolve_path(args):
    if args.path:
        return Path(args.path)
    if args.name:
        matches = find_requirement(args.name)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            candidates = "\n".join([f"- {m}" for m in matches])
            raise SystemExit(f"multiple requirements found for name={args.name}, use --path:\n{candidates}")
        raise SystemExit("requirement not found")
    active = get_active()
    if active:
        return active
    raise SystemExit("no active requirement, use --name or --path")


def load_metadata(path: Path) -> dict:
    meta_path = path / "metadata.json"
    if not meta_path.exists():
        raise SystemExit("metadata.json not found, run init first")
    try:
        return json.loads(read_file(meta_path))
    except json.JSONDecodeError:
        raise SystemExit("invalid metadata.json")


def _meta_context(path: Path) -> tuple[str, str, str]:
    meta = load_metadata(path)
    title = str(meta.get("title") or path.name)
    desc = str(meta.get("original_requirement") or "").strip()
    if not desc:
        raise SystemExit("original requirement missing in metadata.json")
    extra = str(meta.get("initial_clarifications") or "").strip()
    return title, desc, extra



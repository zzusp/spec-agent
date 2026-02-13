#!/usr/bin/env python
from spec_agent_engine_core import *


def final_check(path: Path, write_back: bool = True):
    issues = []
    metadata_changed = False
    DEP_SIG_START = "<!-- DEPENDENCY-SIGNATURE:START -->"
    DEP_SIG_END = "<!-- DEPENDENCY-SIGNATURE:END -->"

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

    def content_hash(content: str) -> str:
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def extract_section(content: str, heading: str) -> str:
        pattern = re.compile(rf"^{re.escape(heading)}\s*$", flags=re.MULTILINE)
        m = pattern.search(content)
        if not m:
            return ""
        start = m.end()
        next_h2 = re.search(r"^##\s+", content[start:], flags=re.MULTILINE)
        end = start + next_h2.start() if next_h2 else len(content)
        return content[start:end]

    def extract_dependency_signatures(content: str) -> dict[str, str]:
        pattern = re.compile(
            re.escape(DEP_SIG_START) + r"\n?([\s\S]*?)\n?" + re.escape(DEP_SIG_END),
            re.MULTILINE,
        )
        m = pattern.search(content)
        if not m:
            return {}
        out = {}
        for raw in m.group(1).splitlines():
            line = raw.strip().lstrip("-").strip()
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            key = k.strip().lower()
            val = v.strip()
            if key and val:
                out[key] = val
        return out

    def extract_acceptance_table_ids(content: str):
        m = re.search(r"^## 验收项清单\s*$", content, flags=re.MULTILINE)
        if not m:
            return []
        start = m.end()
        next_h2 = re.search(r"^##\s+", content[start:], flags=re.MULTILINE)
        end = start + next_h2.start() if next_h2 else len(content)
        section = content[start:end]
        lines = [ln.rstrip() for ln in section.splitlines() if ln.strip()]
        header_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith("|") and "编号" in line and "验收项" in line and "预期结果" in line:
                header_idx = i
                break
        if header_idx is None:
            return []
        ids = []
        for line in lines[header_idx + 2:]:
            if not line.strip().startswith("|"):
                break
            parts = split_md_row(line)
            if not parts:
                continue
            aid = parts[0].strip()
            if re.fullmatch(r"A-\d+", aid):
                ids.append(aid)
        return ids

    # Global memory sync check
    try:
        meta = load_metadata(path)
    except SystemExit:
        meta = {}
    current_memory_hash = global_memory_hash()
    if str(meta.get("global_memory_hash", "")) != current_memory_hash:
        add_issue("global", "全局记忆快照未同步，请先执行 sync-memory 后再复检。")

    clar_rows = []
    clar_path = path / DOC_FILES["clarifications"]
    if clar_path.exists():
        clar_rows, _ = parse_clarifications_table(read_file(clar_path))
    confirmed_questions = [
        r for r in clar_rows
        if str(r.get("status", "")).strip() == CONFIRMED_STATUS
        and not str(r.get("question", "")).strip().startswith("（示例）")
    ]
    has_confirmed_clarifications = len(confirmed_questions) > 0

    # Required docs presence + memory/clarification integration checks
    required_doc_keys = ("analysis", "prd", "tech", "acceptance")
    raw_doc_contents = {}
    for key in required_doc_keys:
        doc_path = path / DOC_FILES[key]
        if not doc_path.exists():
            add_issue(key, f"{DOC_FILES[key]} 缺失，请先生成该文档。")
            continue
        raw_content = read_file(doc_path)
        raw_doc_contents[key] = raw_content
        if "全局记忆" not in raw_content:
            add_issue(key, f"{DOC_FILES[key]} 缺少全局记忆引用，请结合 `spec/00-global-memory.md` 补充。")
        memory_section = extract_section(raw_content, "## 全局记忆约束")
        if not re.search(r"^\s*-\s+.+", memory_section, flags=re.MULTILINE):
            add_issue(key, f"{DOC_FILES[key]} 缺少可执行的全局记忆约束条目（`## 全局记忆约束` 下至少 1 条）。")
        if CLARIFY_START not in raw_content or CLARIFY_END not in raw_content:
            add_issue(key, f"{DOC_FILES[key]} 缺少澄清补充区块，请补充 `{CLARIFY_START}` / `{CLARIFY_END}`。")
        else:
            clar_block_pattern = re.compile(
                re.escape(CLARIFY_START) + r"\n?([\s\S]*?)\n?" + re.escape(CLARIFY_END),
                re.MULTILINE,
            )
            m = clar_block_pattern.search(raw_content)
            block = m.group(1) if m else ""
            if has_confirmed_clarifications and not re.search(r"\bC-\d+\b", block):
                add_issue(key, f"{DOC_FILES[key]} 澄清补充区块未引用已确认澄清项（需包含 C-xxx）。")

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
        if "| 编号 | 验收项 | 预期结果 |" not in check_content:
            add_issue("acceptance", "验收清单缺少标准验收项表头（编号/验收项/预期结果）。")
        if "## 验收计划与步骤" not in check_content:
            add_issue("acceptance", "验收清单缺少“验收计划与步骤”章节。")
        acceptance_ids = extract_acceptance_table_ids(check_content)
        if not acceptance_ids:
            add_issue("acceptance", "验收项清单表中未识别到有效验收编号（A-xxx）。")
        detail_ids = set(re.findall(r"^###\s+(A-\d+)\s+验收计划与步骤", check_content, flags=re.MULTILINE))
        missing_details = sorted(set(acceptance_ids) - detail_ids)
        if missing_details:
            add_issue("acceptance", "存在验收项未提供独立的“验收计划与步骤”明细。")
        extra_details = sorted(detail_ids - set(acceptance_ids))
        if extra_details:
            add_issue("acceptance", "存在不在验收项清单表中的验收计划明细，请保持一一对应。")
        for aid in acceptance_ids:
            if aid in detail_ids:
                pattern = re.compile(
                    rf"^###\s+{re.escape(aid)}\s+验收计划与步骤[\s\S]*?(?=^###\s+A-\d+\s+验收计划与步骤|\Z)",
                    re.MULTILINE,
                )
                m = pattern.search(check_content)
                block = m.group(0) if m else ""
                required_terms = ("前置条件", "验收步骤", "通过标准", "失败处理")
                if not all(term in block for term in required_terms):
                    add_issue("acceptance", f"{aid} 缺少完整验收计划要素（前置条件/验收步骤/通过标准/失败处理）。")
                    break
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

    # Dependency freshness checks by content hash snapshots:
    # analysis -> prd -> tech -> acceptance
    doc_hashes = {}
    for key in ("analysis", "prd", "tech", "acceptance"):
        p = path / DOC_FILES[key]
        if not p.exists():
            continue
        content = strip_clarification_block(read_file(p))
        doc_hashes[key] = content_hash(content)

    dep_graph = {
        "prd": ["analysis"],
        "tech": ["analysis", "prd"],
        "acceptance": ["analysis", "prd", "tech"],
    }
    dep_state = meta.get("doc_dependency_state", {}) if isinstance(meta.get("doc_dependency_state"), dict) else {}
    if not isinstance(dep_state, dict):
        dep_state = {}
    next_dep_state = dict(dep_state)

    for doc_key, upstreams in dep_graph.items():
        if doc_key not in doc_hashes:
            continue
        if any(up not in doc_hashes for up in upstreams):
            continue
        prev = dep_state.get(doc_key, {}) if isinstance(dep_state.get(doc_key, {}), dict) else {}
        prev_doc_hash = str(prev.get("doc_hash", "")).strip()
        prev_up_hashes = prev.get("upstream_hashes", {}) if isinstance(prev.get("upstream_hashes"), dict) else {}
        current_doc_hash = doc_hashes[doc_key]
        current_up_hashes = {k: doc_hashes[k] for k in upstreams}
        current_raw = raw_doc_contents.get(doc_key, "")
        sig_map = extract_dependency_signatures(current_raw)
        has_all_signatures = all(k in sig_map for k in upstreams)
        signatures_match = has_all_signatures and all(sig_map.get(k, "") == v for k, v in current_up_hashes.items())

        if not has_all_signatures:
            add_issue(doc_key, f"{DOC_FILES[doc_key]} 缺少依赖签名区块，请补充 {DEP_SIG_START}/{DEP_SIG_END} 并写入上游哈希。")
        elif not signatures_match:
            add_issue(doc_key, f"{DOC_FILES[doc_key]} 依赖签名与当前上游不一致，请基于上游最新文档重生成。")

        # If downstream content changed and signatures are valid, refresh dependency snapshot.
        if (not prev_doc_hash or prev_doc_hash != current_doc_hash) and signatures_match:
            next_dep_state[doc_key] = {
                "doc_hash": current_doc_hash,
                "upstream_hashes": current_up_hashes,
            }
            metadata_changed = True
            continue

        # Downstream content unchanged: verify upstream hashes have not drifted.
        stale = any(str(prev_up_hashes.get(k, "")) != v for k, v in current_up_hashes.items())
        if stale:
            chain = " -> ".join(upstreams + [doc_key])
            add_issue(doc_key, f"上游文档内容已变更，但 {doc_key} 未同步更新（依赖链：{chain}）。")

    if metadata_changed:
        meta["doc_dependency_state"] = next_dep_state

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
        new_items = new_items[:MAX_NEW_CLARIFICATIONS_PER_ROUND]
        updated = add_clarifications(clar_content, new_items)
        persist_clarifications(path, updated, dry_run=False)
    if metadata_changed and write_back:
        write_file(path / "metadata.json", json.dumps(meta, ensure_ascii=False, indent=2))

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



#!/usr/bin/env python
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from regression_lib import remove_dir, run_spec_agent

ROOT = Path(__file__).resolve().parents[1]
REQ = "regression-smoke"


def run(args, check=True):
    return run_spec_agent(args, root=ROOT, check=check)


def issue_count(output: str) -> int:
    m = re.search(r"final-check issues:\s*(\d+)", output)
    if not m:
        raise RuntimeError(f"cannot parse final-check output: {output}")
    return int(m.group(1))


def strip_clarification_block(content: str) -> str:
    pattern = re.compile(
        re.escape("<!-- CLARIFICATIONS:START -->") + r"[\s\S]*?" + re.escape("<!-- CLARIFICATIONS:END -->"),
        re.MULTILINE,
    )
    return pattern.sub("", content)


def strip_dependency_signature_block(content: str) -> str:
    pattern = re.compile(
        re.escape("<!-- DEPENDENCY-SIGNATURE:START -->") + r"[\s\S]*?" + re.escape("<!-- DEPENDENCY-SIGNATURE:END -->"),
        re.MULTILINE,
    )
    return pattern.sub("", content)


def strip_revision_section(content: str) -> str:
    pattern = re.compile(r"^##\s+修订记录\s*$[\s\S]*?(?=^##\s+|\Z)", re.MULTILINE)
    return pattern.sub("", content)


def content_hash(content: str) -> str:
    normalized = strip_clarification_block(content)
    normalized = strip_dependency_signature_block(normalized)
    normalized = strip_revision_section(normalized)
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def dependency_signature_block(pairs: dict[str, str]) -> str:
    lines = ["<!-- DEPENDENCY-SIGNATURE:START -->"]
    for k, v in pairs.items():
        lines.append(f"- {k}: {v}")
    lines.append("<!-- DEPENDENCY-SIGNATURE:END -->")
    return "\n".join(lines)


def clarification_row_count(clar_path: Path) -> int:
    if not clar_path.exists():
        return 0
    text = clar_path.read_text(encoding="utf-8-sig")
    return len(re.findall(r"^\|\s*C-\d+\s*\|", text, flags=re.MULTILINE))


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def main():
    date = dt.date.today().strftime("%Y-%m-%d")

    # Prepare sqlite test db
    db = ROOT / "tmp_demo.sqlite"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    cur.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, status TEXT, amount REAL)")
    cur.execute("CREATE TABLE order_logs (id INTEGER PRIMARY KEY, order_id INTEGER, action TEXT)")
    con.commit()
    con.close()

    req_dir = ROOT / "spec" / date / REQ
    remove_dir(req_dir)
    db_connections_json = json.dumps([
        {
            "db_type": "sqlite",
            "connection": "sqlite:///tmp_demo.sqlite",
            "source": "caller-ai",
        }
    ], ensure_ascii=False)

    run([
        "init",
        "--name",
        REQ,
        "--title",
        "回归冒烟",
        "--desc",
        "需求A；需求B",
        "--db-connections-json",
        db_connections_json,
        "--project-mode",
        "greenfield",
        "--state-only",
        "--date",
        date,
    ])
    meta = json.loads((req_dir / "metadata.json").read_text(encoding="utf-8-sig"))
    if str(meta.get("project_mode", "")) != "greenfield":
        raise RuntimeError(f"expected metadata project_mode=greenfield after init: {meta}")

    run(["subagent-init", "--name", REQ])
    blocked = run(["subagent-stage", "--name", REQ, "--stage", "prd", "--status", "completed"], check=False)
    if blocked.returncode == 0:
        raise RuntimeError("expected subagent-stage prd completion to be blocked before analysis stage")
    clar_md_path = req_dir / "00-clarifications.md"
    clar_json_path = req_dir / "00-clarifications.json"
    clar_md = clar_md_path.read_text(encoding="utf-8-sig")
    clar_md = clar_md.replace("（示例）请确认需求范围的最终边界", "（示例）请确认需求范围的最终边界-MD-ONLY")
    clar_md_path.write_text(clar_md, encoding="utf-8")
    clar_json_before = file_hash(clar_json_path)
    ctx_raw = run(["--json-output", "subagent-context", "--name", REQ, "--stage", "analysis"]).stdout.strip()
    clar_json_after = file_hash(clar_json_path)
    if clar_json_before != clar_json_after:
        raise RuntimeError("subagent-context should not sync/update clarification files")
    ctx_payload = json.loads(ctx_raw)
    if ctx_payload.get("stage") != "analysis":
        raise RuntimeError(f"unexpected subagent-context payload: {ctx_raw}")
    if not ctx_payload.get("target_sections"):
        raise RuntimeError(f"subagent-context should include target_sections: {ctx_raw}")
    if not ctx_payload.get("must_keep_sections"):
        raise RuntimeError(f"subagent-context should include must_keep_sections: {ctx_raw}")
    if "reopen_reason" not in ctx_payload:
        raise RuntimeError(f"subagent-context should include reopen_reason: {ctx_raw}")
    if ctx_payload.get("project_mode") != "greenfield":
        raise RuntimeError(f"subagent-context should include project_mode=greenfield: {ctx_raw}")
    focus = ctx_payload.get("clarification_focus", {}) if isinstance(ctx_payload.get("clarification_focus", {}), dict) else {}
    if focus.get("mode") != "greenfield":
        raise RuntimeError(f"subagent-context should include greenfield clarification_focus: {ctx_raw}")

    # Legacy generation commands should be unavailable from CLI.
    legacy = run(["write-analysis", "--name", REQ], check=False)
    if legacy.returncode == 0:
        raise RuntimeError("expected write-analysis command to be removed from CLI")

    analysis = """# 分析报告 - 回归冒烟

## 原始需求
- R-01 需求A
- R-02 需求B

## 需求上下文采集
- 代码模块：scripts
- 数据库：sqlite 测试库
- 业务角色：产品、运营
- 约束：保持现有行为稳定

## 项目现状与相关模块
- 当前代码具备基础命令执行能力。
- 数据库用于结果核对与追踪。

## 候选模块扫描
<!-- SCAN:START -->
- scripts
<!-- SCAN:END -->

## 数据库现状
- 已识别连接串并可读取 schema。
<!-- DB-SCHEMA:START -->
- sqlite:///tmp_demo.sqlite
<!-- DB-SCHEMA:END -->

## 需求覆盖矩阵
| 需求点 | 现有模块/表 | 是否满足 | 差距/说明 |
|---|---|---|---|
| R-01 需求A | scripts / orders | 可满足 | 需验收确认 |
| R-02 需求B | scripts / order_logs | 可满足 | 需验收确认 |

## 需求满足性分析
- 现有代码路径可支撑本次需求落地。
- 数据一致性可通过库表核对完成闭环。

## 风险与影响
- 风险1：需求边界变化导致返工。
- 风险2：数据口径不统一导致验收偏差。

## 结论
- 可进入方案落地与验收阶段。

## 全局记忆约束
- 已结合全局记忆文档（spec/00-global-memory.md）中的项目通用规则。

## 澄清补充
<!-- CLARIFICATIONS:START -->
- [C-002] 需求已提供数据库连接信息，可用于分析阶段拉取库表结构。
<!-- CLARIFICATIONS:END -->

## 修订记录
| 修订日期 | 修订人 | 修订内容摘要 |
|---|:---:|---|
| 2025-02-25 | 回归测试 | 冒烟用例构造 |
"""
    (req_dir / "01-analysis.md").write_text(analysis, encoding="utf-8")

    analysis_hash = content_hash(analysis)
    prd = f"""# PRD - 回归冒烟

## 需求范围与边界
- R-01 覆盖需求A主流程。
- R-02 覆盖需求B异常路径。
- 本期不包含跨团队流程重构。

## 简要说明
- 目标：统一业务动作结果判定口径。
- 背景：当前不同角色对结果认定存在分歧。
- 价值：降低交付返工概率。

## 产品功能描述与业务流程
- 流程1：用户发起动作 -> 系统校验 -> 返回结果。
- 流程2：记录过程信息用于复核。

## 需求项映射
| 需求ID | 需求描述 | PRD 功能定义 |
|---|---|---|
| R-01 | 需求A | 明确主流程动作与结果 |
| R-02 | 需求B | 明确异常处理与提示 |

## 分支流程与异常处理
- 分支1：输入缺失时阻断并给出提示。
- 分支2：状态冲突时拒绝并保留上下文。
- 分支3：重复提交时保持结果稳定。

## 非功能性需求
- 可用性：关键流程可持续执行。
- 一致性：同类输入得到同类结果。
- 可观测性：过程可追踪可复核。

## 待确认需求点
- 已通过澄清文档闭环关键不确定项。

## 冲突与影响
- 影响：业务协作口径需要同步。
- 处理：按文档口径统一执行。

## 全局记忆约束
- 已结合全局记忆文档（spec/00-global-memory.md）中的术语与交付规范。

## 澄清补充
<!-- CLARIFICATIONS:START -->
- [C-002] 需求已提供数据库连接信息，可用于分析阶段拉取库表结构。
<!-- CLARIFICATIONS:END -->

## 修订记录
| 修订日期 | 修订人 | 修订内容摘要 |
|---|:---:|---|
| 2025-02-25 | 回归测试 | 冒烟用例构造 |

{dependency_signature_block({"analysis": analysis_hash})}
"""
    prd_hash = content_hash(prd)
    tech = f"""# 技术方案 - 回归冒烟

## 当前项目/功能情况
- 现有命令框架可承载本次改造。
- 数据持久化以 sqlite 为验证基准。

## 实现目标
- R-01 完成主流程处理能力。
- R-02 完成异常场景处理能力。
- 保证结果可核对、可追踪。

## 整体架构设计思路
- 入口层：参数校验与路由分发。
- 规则层：业务规则判断与状态计算。
- 持久层：动作结果落库与审计。

## 架构图
- A -> B -> C

## 数据库设计
- 主表：orders
- 日志表：order_logs
- 索引：业务键与时间字段

## 可执行 SQL
```sql
SELECT id, status FROM orders;
SELECT id, order_id, action FROM order_logs;
```

## 核心功能代码片段
```text
validate -> execute -> persist -> audit
```

## 单元测试
- 覆盖主流程成功路径。
- 覆盖异常输入阻断路径。
- 覆盖重复提交处理路径。

## 数据迁移与回滚策略
- 迁移：先灰度启用，再全量启用。
- 回滚：故障时关闭新路径并保留审计记录。

## 注意事项
- 变更前后需核对数据口径一致。

## 全局记忆约束
- 已结合全局记忆文档（spec/00-global-memory.md）中的工程与上线约束。

## 澄清补充
<!-- CLARIFICATIONS:START -->
- [C-002] 需求已提供数据库连接信息，可用于分析阶段拉取库表结构。
<!-- CLARIFICATIONS:END -->

## 修订记录
| 修订日期 | 修订人 | 修订内容摘要 |
|---|:---:|---|
| 2025-02-25 | 回归测试 | 冒烟用例构造 |

{dependency_signature_block({"analysis": analysis_hash, "prd": prd_hash})}
"""
    tech_hash = content_hash(tech)
    acceptance = f"""# 验收清单 - 回归冒烟

## 验收项清单
| 编号 | 验收项 | 预期结果 |
|---|---|---|
| A-001 | 需求A主流程（R-01） | 结果正确且数据一致 |
| A-002 | 需求B异常流程（R-02） | 异常可解释且不产生脏数据 |

## 验收计划与步骤
### A-001 验收计划与步骤（R-01）
- 前置条件：
  1. 准备有效业务输入。
  2. 验收账号具备操作权限。
- 验收步骤：
  1. 触发主流程动作并记录响应。
  2. 核对响应结果是否符合规则。
  3. 查询 `{REQ}_record` 或业务表核对状态一致。
- 通过标准：
  1. 结果字段与业务预期一致。
  2. 数据状态与响应一致。
- 失败处理：
  1. 记录失败输入与日志。
  2. 回填澄清并修订后复验。

### A-002 验收计划与步骤（R-02）
- 前置条件：
  1. 准备异常输入样例。
  2. 准备重复提交样例。
- 验收步骤：
  1. 触发异常场景并记录提示信息。
  2. 触发重复提交并观察处理结果。
  3. 查询数据库确认无脏数据与越权结果。
- 通过标准：
  1. 异常提示包含错误码且可恢复。
  2. 重复提交返回固定状态码且数据库条数不增加。
- 失败处理：
  1. 记录失败步骤与数据库快照。
  2. 反馈并修订后重新验收。

## 受影响功能验证
- 验证原流程在未命中新规则时保持稳定。
- 验证日志与状态变更一致。
- 验证权限边界未扩大。

## 数据库核对指引
- 查询 orders 与 order_logs 对齐业务动作。
- 比对响应状态与库内状态一致性。

## 全局记忆约束
- 已结合全局记忆文档（spec/00-global-memory.md）中的验收口径与风险控制要求。

## 澄清补充
<!-- CLARIFICATIONS:START -->
- [C-002] 需求已提供数据库连接信息，可用于分析阶段拉取库表结构。
<!-- CLARIFICATIONS:END -->

## 修订记录
| 修订日期 | 修订人 | 修订内容摘要 |
|---|:---:|---|
| 2025-02-25 | 回归测试 | 冒烟用例构造 |

{dependency_signature_block({"analysis": analysis_hash, "prd": prd_hash, "tech": tech_hash})}
"""
    (req_dir / "02-prd.md").write_text(prd, encoding="utf-8")
    (req_dir / "03-tech.md").write_text(tech, encoding="utf-8")
    (req_dir / "04-acceptance.md").write_text(acceptance, encoding="utf-8")

    run(["inspect-db", "--name", REQ])
    # Keep dependency freshness order after analysis is updated by inspect-db.
    analysis_after_inspect = (req_dir / "01-analysis.md").read_text(encoding="utf-8")
    analysis_hash = content_hash(analysis_after_inspect)
    prd = prd.rsplit("<!-- DEPENDENCY-SIGNATURE:START -->", 1)[0].rstrip() + "\n\n" + dependency_signature_block({"analysis": analysis_hash}) + "\n"
    prd_hash = content_hash(prd)
    tech = tech.rsplit("<!-- DEPENDENCY-SIGNATURE:START -->", 1)[0].rstrip() + "\n\n" + dependency_signature_block({"analysis": analysis_hash, "prd": prd_hash}) + "\n"
    tech_hash = content_hash(tech)
    acceptance = acceptance.rsplit("<!-- DEPENDENCY-SIGNATURE:START -->", 1)[0].rstrip() + "\n\n" + dependency_signature_block({"analysis": analysis_hash, "prd": prd_hash, "tech": tech_hash}) + "\n"
    (req_dir / "02-prd.md").write_text(prd, encoding="utf-8")
    (req_dir / "03-tech.md").write_text(tech, encoding="utf-8")
    (req_dir / "04-acceptance.md").write_text(acceptance, encoding="utf-8")

    # Negative check 1: missing clarification block should fail final-check.
    prd_no_clar = re.sub(
        re.escape("<!-- CLARIFICATIONS:START -->") + r"[\s\S]*?" + re.escape("<!-- CLARIFICATIONS:END -->"),
        "",
        prd,
        flags=re.MULTILINE,
    )
    (req_dir / "02-prd.md").write_text(prd_no_clar, encoding="utf-8")
    clar_count_before = clarification_row_count(req_dir / "00-clarifications.md")
    bad_out = run(["final-check", "--name", REQ, "--dry-run"], check=True).stdout
    if issue_count(bad_out) <= 0:
        raise RuntimeError("expected final-check to fail when clarification block is missing")
    bad_out_write = run(["final-check", "--name", REQ], check=True).stdout
    if issue_count(bad_out_write) <= 0:
        raise RuntimeError("expected final-check to report issues when missing clarification block")
    clar_count_after = clarification_row_count(req_dir / "00-clarifications.md")
    if clar_count_after != clar_count_before:
        raise RuntimeError("doc-quality issues should not auto-append clarification rows")
    (req_dir / "02-prd.md").write_text(prd, encoding="utf-8")

    # Negative check 2: stale dependency signature should fail final-check.
    acceptance_stale_sig = re.sub(r"(tech:\s*)[0-9a-f]{32}", r"\1deadbeefdeadbeefdeadbeefdeadbeef", acceptance)
    (req_dir / "04-acceptance.md").write_text(acceptance_stale_sig, encoding="utf-8")
    bad_out = run(["final-check", "--name", REQ, "--dry-run"], check=True).stdout
    if issue_count(bad_out) <= 0:
        raise RuntimeError("expected final-check to fail when dependency signature is stale")
    (req_dir / "04-acceptance.md").write_text(acceptance, encoding="utf-8")

    # Negative check 3: vague/non-assertable acceptance criteria should fail final-check.
    acceptance_vague = (
        acceptance
        .replace("1. 结果字段与业务预期一致。", "1. 功能正常。")
        .replace("2. 数据状态与响应一致。", "2. 体验良好。")
        .replace("1. 异常提示包含错误码且可恢复。", "1. 体验良好。")
        .replace("2. 重复提交返回固定状态码且数据库条数不增加。", "2. 功能正常。")
    )
    (req_dir / "04-acceptance.md").write_text(acceptance_vague, encoding="utf-8")
    bad_out = run(["final-check", "--name", REQ, "--dry-run"], check=True).stdout
    if issue_count(bad_out) <= 0:
        raise RuntimeError("expected final-check to fail when acceptance pass criteria are not assertable")
    (req_dir / "04-acceptance.md").write_text(acceptance, encoding="utf-8")

    out = run(["final-check", "--name", REQ]).stdout
    if "final-check issues: 0" not in out:
        raise RuntimeError(f"unexpected final-check result: {out}")

    run(["subagent-stage", "--name", REQ, "--stage", "analysis", "--status", "completed", "--agent", "analysis-agent"])
    run(["subagent-stage", "--name", REQ, "--stage", "prd", "--status", "completed", "--agent", "prd-agent"])
    run(["subagent-stage", "--name", REQ, "--stage", "tech", "--status", "completed", "--agent", "tech-agent"])
    run(["subagent-stage", "--name", REQ, "--stage", "acceptance", "--status", "completed", "--agent", "acceptance-agent"])
    bad_fc = run(
        ["subagent-stage", "--name", REQ, "--stage", "final_check", "--status", "completed", "--agent", "analysis-agent"],
        check=False,
    )
    if bad_fc.returncode == 0:
        raise RuntimeError("expected final_check stage to reject non-independent agent")
    run(["subagent-stage", "--name", REQ, "--stage", "final_check", "--status", "completed", "--agent", "final-check-agent"])
    status_payload = json.loads(run(["--json-output", "subagent-status", "--name", REQ]).stdout.strip())
    if status_payload.get("current_stage") != "final_check":
        raise RuntimeError(f"unexpected subagent current_stage: {status_payload}")
    if status_payload.get("stale_stages"):
        raise RuntimeError(f"unexpected stale stages after ordered completion: {status_payload}")

    # Non-semantic revision updates should not trigger stale stage normalization.
    analysis_path = req_dir / "01-analysis.md"
    analysis_text = analysis_path.read_text(encoding="utf-8")
    analysis_text += "\n| 2025-02-26 | 回归测试 | 仅更新修订记录 |\n"
    analysis_path.write_text(analysis_text, encoding="utf-8")
    status_after_revision = json.loads(run(["--json-output", "subagent-status", "--name", REQ]).stdout.strip())
    if status_after_revision.get("stale_stages"):
        raise RuntimeError(f"revision-only changes should not mark stale stages: {status_after_revision}")

    # Clarify-flow: 更新澄清内容后 → 门禁通过 → final-check 通过（验证 spec-agent-clarify 的关联触发路径）
    clar_md_path = req_dir / "00-clarifications.md"
    clar_md = clar_md_path.read_text(encoding="utf-8-sig")
    if "待确认" in clar_md:
        clar_md = clar_md.replace("| 待确认 |", "| 已确认 |")
        clar_md_path.write_text(clar_md, encoding="utf-8")
    strict_out = run(["check-clarifications", "--name", REQ, "--strict", "--json-output"]).stdout.strip()
    payload = json.loads(strict_out)
    if int(payload.get("pending", -1)) != 0:
        raise RuntimeError(f"expected pending=0 after confirming all clarifications: {payload}")
    out2 = run(["final-check", "--name", REQ]).stdout
    if "final-check issues: 0" not in out2:
        raise RuntimeError(f"expected final-check ok after clarify gate pass: {out2}")

    # spec-agent-chat 校验：澄清内容（已确认）写入后，四份文档必须更新（澄清补充区块引用 C-xxx），否则 final-check 不通过
    for doc_key, filename in [("analysis", "01-analysis.md"), ("prd", "02-prd.md"), ("tech", "03-tech.md"), ("acceptance", "04-acceptance.md")]:
        doc_path = req_dir / filename
        content = doc_path.read_text(encoding="utf-8")
        if re.search(r"\bC-\d+\b", content):
            content_no_c = re.sub(r"\bC-\d+\b", "C-X-REMOVED", content)
            doc_path.write_text(content_no_c, encoding="utf-8")
    out_no_ref = run(["final-check", "--name", REQ, "--dry-run"], check=True).stdout
    if issue_count(out_no_ref) <= 0:
        raise RuntimeError("expected final-check to fail when docs lack C-xxx reference (spec-agent-chat: other files must be updated)")
    for doc_key, filename in [("analysis", "01-analysis.md"), ("prd", "02-prd.md"), ("tech", "03-tech.md"), ("acceptance", "04-acceptance.md")]:
        doc_path = req_dir / filename
        content = doc_path.read_text(encoding="utf-8")
        content = content.replace("C-X-REMOVED", "C-002")
        doc_path.write_text(content, encoding="utf-8")
    out_restored = run(["final-check", "--name", REQ]).stdout
    if "final-check issues: 0" not in out_restored:
        raise RuntimeError(f"expected final-check ok after restoring C-xxx in docs: {out_restored}")

    # Targeted clarification coverage: PRD-targeted confirmed clarification must be referenced in PRD.
    clar_md = clar_md_path.read_text(encoding="utf-8-sig")
    targeted_row = "| C-099 | 已确认 | 高 | 范围 | prd | 需求范围与边界 | 新增PRD定向澄清 | 范围已确认 | 已按确认更新PRD |"
    if targeted_row not in clar_md:
        clar_md = clar_md.replace(
            "|---|---|---|---|---|---|---|---|---|\n",
            "|---|---|---|---|---|---|---|---|---|\n" + targeted_row + "\n",
            1,
        )
        clar_md_path.write_text(clar_md, encoding="utf-8")
    prd_path = req_dir / "02-prd.md"
    prd_text = prd_path.read_text(encoding="utf-8")
    if "C-099" not in prd_text:
        prd_text = prd_text.replace(
            "- [C-002] 需求已提供数据库连接信息，可用于分析阶段拉取库表结构。",
            "- [C-002] 需求已提供数据库连接信息，可用于分析阶段拉取库表结构。\n- [C-099] 新增PRD定向澄清已确认并落地。",
        )
    prd_without_c099 = re.sub(r"\bC-099\b", "C099REMOVED", prd_text)
    prd_path.write_text(prd_without_c099, encoding="utf-8")
    targeted_fail = run(["final-check", "--name", REQ, "--dry-run"], check=True).stdout
    if issue_count(targeted_fail) <= 0:
        raise RuntimeError("expected final-check to fail when PRD-targeted clarification ID is missing in PRD doc")
    prd_path.write_text(prd_without_c099.replace("C099REMOVED", "C-099"), encoding="utf-8")
    targeted_ok = run(["final-check", "--name", REQ], check=True).stdout
    if "final-check issues: 0" not in targeted_ok:
        raise RuntimeError(f"expected final-check ok after restoring PRD-targeted clarification id: {targeted_ok}")

    # Trigger final-check failure and verify auto reopen mapping to earliest impacted stage.
    prd_broken = prd.replace("| R-02 | 需求B | 明确异常处理与提示 |\n", "")
    (req_dir / "02-prd.md").write_text(prd_broken, encoding="utf-8")
    stale_preview = json.loads(run(["--json-output", "subagent-status", "--name", REQ]).stdout.strip())
    if "prd" not in stale_preview.get("stale_stages", []):
        raise RuntimeError(f"expected stale preview to include prd without normalization: {stale_preview}")
    if stale_preview.get("stages", {}).get("prd", {}).get("status") != "completed":
        raise RuntimeError(f"subagent-status without --normalize should be read-only: {stale_preview}")
    normalized_preview = json.loads(run(["--json-output", "subagent-status", "--name", REQ, "--normalize"]).stdout.strip())
    if normalized_preview.get("stages", {}).get("prd", {}).get("status") != "pending":
        raise RuntimeError(f"subagent-status --normalize should persist pending for stale stages: {normalized_preview}")
    run([
        "subagent-stage",
        "--name",
        REQ,
        "--stage",
        "final_check",
        "--status",
        "failed",
        "--agent",
        "final-check-agent",
        "--notes",
        "simulate final-check fail",
    ])
    reopened_status = json.loads(run(["--json-output", "subagent-status", "--name", REQ]).stdout.strip())
    if reopened_status.get("current_stage") not in {"analysis", "prd", "tech", "acceptance"}:
        raise RuntimeError(f"expected current_stage to reopen into doc stages: {reopened_status}")
    last_reopen = reopened_status.get("last_reopen", {}) if isinstance(reopened_status.get("last_reopen", {}), dict) else {}
    reopen_stage = str(last_reopen.get("stage", "")).strip()
    if reopen_stage not in {"analysis", "prd", "tech", "acceptance"}:
        raise RuntimeError(f"expected auto-mapped reopen stage from final_check: {reopened_status}")
    if str(last_reopen.get("source", "")) != "final_check":
        raise RuntimeError(f"expected reopen source=final_check: {reopened_status}")
    mapped_issues = last_reopen.get("issues", []) if isinstance(last_reopen.get("issues", []), list) else []
    if mapped_issues and not all(str(item.get("code", "")).strip() for item in mapped_issues if isinstance(item, dict)):
        raise RuntimeError(f"expected structured issue codes in last_reopen mapping: {reopened_status}")
    reopen_ctx = json.loads(run(["--json-output", "subagent-context", "--name", REQ, "--stage", reopen_stage]).stdout.strip())
    if not reopen_ctx.get("reopen_reason", ""):
        raise RuntimeError(f"expected reopen_reason for mapped stage context: {reopen_ctx}")

    # check-clarifications strict should be executable in AI-first contract.
    strict_out = run(["check-clarifications", "--name", REQ, "--strict", "--json-output"]).stdout.strip()
    payload = json.loads(strict_out)
    if int(payload.get("pending", -1)) < 0:
        raise RuntimeError(f"unexpected check-clarifications output: {strict_out}")

    # cleanup smoke artifacts
    remove_dir(req_dir)
    if db.exists():
        db.unlink()

    print("regression smoke: ok")


if __name__ == "__main__":
    main()

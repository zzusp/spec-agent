---
name: spec-agent-chat
description: Route user chat into clarification or memory updates, then drive document refresh in AI-first mode. Use when users send conversational (one or few) updates in AI IDE and expect automatic classification, recording, and document updates per AGENTS.md § Document update (apply clarifications).
---

# Spec agent chat

## Trigger

Use when users send **conversational** updates in AI IDE (one or a few messages) and expect automatic classification (clarification vs memory), recording, and selective document updates. For batch-confirmed clarification rows with round report, use `spec-agent-clarify`. Invoke as `/spec-agent-chat ...`

## Workflow

1. Resolve active requirement from `spec/.active`; if none, stop and prompt user to init or switch.
2. Classify message as `clarification` (→ `00-clarifications.md/.json`) or `memory` (→ `spec/00-global-memory.md`).
3. After write: ensure subagent state; **update impacted docs in stage order** (analysis → prd → tech → acceptance) by **applying clarification decisions to redesign and adjust full document content** (not only adding C-xxx); run sync-memory and final-check, commit final_check when issues=0. **YAGNI**：更新文档时范围限定于当前需求与已确认澄清，不引入“将来可能”的设计或功能描述。
4. Return status card (当前需求, 本次识别, 写入结果, 文档更新, 阶段状态, 变更摘要, 检查结果, 下一步建议).

## Memory preload (must)

- Read `spec/00-global-memory.md` before any classification or update.

## Active requirement precheck (must)

- Resolve active requirement from `spec/.active` before handling the message.
- Pin active requirement name as `<name>` and use explicit `--name <name>` on all requirement-targeted commands in this turn.
- If no active requirement exists, stop and prompt user first:
  - ask user to run `/spec-agent-task ...` to initialize one, or
  - ask user to run `/spec-agent-switch ...` to select an existing one.
- In this case, do not write memory/clarification files and do not run checks.

### No-active response template (must)

When no active requirement exists, reply with:

- `状态`: 未检测到激活需求
- `下一步`:
  - `/spec-agent-task 这是一个新需求，请初始化并设为当前需求，然后开始文档流程。`
  - `/spec-agent-switch 切换到已有需求 <name>`
- `说明`: 未执行任何写入或检查

## Intent routing (must)

Classify each user message into exactly one bucket:

1. `clarification`
- Requirement-specific decision, constraint, scope, acceptance rule, edge case, or answer to open item.
- **若用户意图是「按刚才确认的澄清更新文档」**：视为 clarification，写入澄清后走 Post-save update loop 更新受影响文档（不要用 `spec-agent-update`）。
- Record to `00-clarifications.md/.json`.

2. `memory`
- **Only** when the user is stating a **cross-requirement** convention, project constraint, or user/team habit (e.g. “以后所有需求默认都要记录操作人和来源IP”). Record to `spec/00-global-memory.md`.
- **Do NOT** classify as `memory` when the user is describing the **current requirement’s scope or conclusion** (e.g. “本需求只改 proto”“本需求不修改业务代码”). That is requirement-specific and must go to **clarification** (`00-clarifications.md`), not global memory. Global memory is for **project context and user habits**, not for single-requirement content.

If ambiguous:
- Ask one short disambiguation question.
- If user does not clarify, default to `clarification`.

## Write targets

- `clarification` -> active requirement `00-clarifications.md/.json`
- `memory` -> `spec/00-global-memory.md` (then sync snapshot to active requirement metadata)

## Post-save update loop (must)

After either `clarification` or `memory` write:

1. Ensure subagent orchestration state exists:
```bash
python scripts/spec_agent.py subagent-init --name <name>
```

2. Read current stage matrix and stale stages:
```bash
python scripts/spec_agent.py subagent-status --name <name> --json-output
```

3. If `stale_stages` is non-empty, treat those stages as pending and rerun from earliest stale stage.
```bash
python scripts/spec_agent.py subagent-status --name <name> --normalize
```

4. Determine impacted docs/stages:
- `analysis`
- `prd`
- `tech`
- `acceptance`

5. **修订记录 (must)**：每次更新任一文档（`01-analysis.md`、`02-prd.md`、`03-tech.md`、`04-acceptance.md`、`00-clarifications.md`）时，必须在该文档的 **修订记录** 表中追加一行：**修订日期**（yyyy-MM-dd）、**修订人**（如「chat」或「用户」）、**修订内容摘要**（当次更新要点）。

6. Update docs only if needed, but enforce dependency order:
- `analysis` -> `prd` -> `tech` -> `acceptance`
  - before each stage update:
```bash
python scripts/spec_agent.py subagent-context --name <name> --stage <stage> --json-output
```
  - consume handoff contract fields from context JSON:
    - `target_sections`
    - `must_keep_sections`
    - `reopen_reason`
    - `project_mode`
    - `clarification_focus`
  - after stage doc update:
```bash
python scripts/spec_agent.py subagent-stage --name <name> --stage <stage> --status completed --agent <stage-agent>
```

7. **Document update scope (must)**：遵循 **AGENTS.md § Clarification policy → Document update (apply clarifications)**（与 spec-agent-clarify 同一套规则）。结合澄清重写时：Substantive update、Whole-document review、Targeted then holistic、修订记录、Acceptance 可测试性、Traceability minimum、Convergence 均按该节执行。clarification focus 按 `project_mode`：`greenfield` 覆盖基线决策，`existing` 优先需求/方案影响，跨领域仅在变更时涉及。

8. For `prd/tech/acceptance`, include dependency signatures:
- `<!-- DEPENDENCY-SIGNATURE:START -->`
- `<!-- DEPENDENCY-SIGNATURE:END -->`
- signature values must match current upstream content hashes
- **若更新 04-acceptance.md**：验收项须满足可测试性——验收步骤可执行、通过标准可断言（同 `spec-agent-write` 中「04-acceptance.md 可测试性要求」），便于实现阶段 TDD。

9. Run checks:
- `sync-memory` (when memory changed)
- `final-check`
```bash
python scripts/spec_agent.py sync-memory --name <name>
python scripts/spec_agent.py final-check --name <name>
```

10. Commit `final_check` stage only when `final-check` reports `issues=0`:
```bash
python scripts/spec_agent.py subagent-stage --name <name> --stage final_check --status completed --agent final-check-agent
```

11. If checks return issues:
- revise impacted docs and rerun `final-check` until stable
  - mark final_check failed:
```bash
python scripts/spec_agent.py subagent-stage --name <name> --stage final_check --status failed --agent final-check-agent --notes "<issue summary>"
```
  - runtime will auto-map issues to earliest impacted stage and reopen downstream stages (based on structured issue codes)

12. Return final stage state:
```bash
python scripts/spec_agent.py subagent-status --name <name> --json-output
```

## User-facing response (must)

Return a concise structured summary:

- `intent`: `clarification` or `memory`
- `written_files`
- `updated_docs` (ordered)
- `section_changes` (doc -> changed sections)
- `check_result` (`issues=0` or issue summary)

### Standard status card (must)

Always output a user-friendly status card in this order:

1. `当前需求`: `<date>/<name>` or `未激活`
2. `本次识别`: `clarification` / `memory`
3. `写入结果`: files updated this turn
4. `文档更新`: which docs were updated in dependency order
5. `阶段状态`: subagent stage matrix highlights (`current_stage`, reopened stages if any)
6. `变更摘要`: doc-level diff summary (see below)
7. `检查结果`: final-check conclusion
8. `下一步建议`: one short actionable sentence

### Change summary format (must)

For each updated doc, provide compact diff-style bullets:

- `<doc_path>`
  - `+` added points/sections
  - `~` modified points/sections
  - `-` removed points/sections (if any)

Example style:
- `01-analysis.md`
  - `+` 新增「风险与影响」2 条约束
  - `~` 更新「需求覆盖矩阵」R-03 映射
- `04-acceptance.md`
  - `~` 调整 `A-002` 验收步骤第 3 步

## Output

- Status card: 当前需求, 本次识别 (clarification/memory), 写入结果, 文档更新, 阶段状态, 变更摘要, 检查结果, 下一步建议.

## Guardrails

- Do not use removed legacy generation commands.
- Keep AI-first behavior: caller AI writes document content directly.
- Use `subagent-*` commands for stage state; do not manually infer stage completion.
- **Scope**: Only write/update under `spec/` (clarifications, global memory, requirement docs). Do not modify project source code (temporary scripts excepted per AGENTS.md).

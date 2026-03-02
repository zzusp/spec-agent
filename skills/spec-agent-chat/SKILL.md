---
name: spec-agent-chat
description: Unified conversational entry for spec-agent. Use when users chat in AI IDE and expect scope detection, intent analysis, and routing to one or multiple spec-agent skills (including local clarification/memory updates).
disable-model-invocation: true
---

# Spec agent chat

## Trigger

Use when users send `/spec-agent-chat ...` and expect a **single conversational entry** that:
- first determines whether the message is a spec-agent usage scenario,
- then analyzes user intent and expected outcome,
- and routes to one skill or multiple skills in sequence.

## Workflow

1. Run **scope relevance gate**: in-scope vs out-of-scope for spec-agent.
2. If out-of-scope: return guidance message and stop (no write, no checks).
3. If in-scope: extract intent(s), expected result, and target requirement context.
4. Build route plan: execute one skill or multiple skills in order.
5. For conversational requirement supplements, use local `clarification`/`memory` path in this skill and run post-save update loop.
6. Return status card (当前需求, 路由结果, 本次识别, 写入结果, 文档更新, 阶段状态, 变更摘要, 检查结果, 下一步建议).

## Scope relevance gate (must)

Treat as **spec-agent in-scope** when user message is about any of:
- creating or refining requirement docs (`analysis/prd/tech/acceptance/clarifications`)
- requirement initialization/switching/listing/checking
- clarification closure or clarification-driven rewrite
- global memory updates (project-level constraints/conventions)
- asking spec-agent workflow/command usage

Treat as **out-of-scope** when message is not related to spec-agent workflow (e.g., coding implementation request, unrelated Q&A, casual chat).

### Out-of-scope response template (must)

When out-of-scope, reply with:
- `状态`: 非 spec-agent 场景
- `说明`: 当前消息不属于需求文档工作流（spec-agent）范围
- `可处理范围`: 需求初始化、文档生成/更新、澄清闭环、全局记忆、质量检查、需求切换
- `示例`: `/spec-agent-chat 现在有一个新需求：...` 或 `/spec-agent-chat 已确认澄清，请更新文档并复检。`
- `执行结果`: 未执行任何写入或检查

## Intent analysis (must)

For in-scope messages, extract:
- `primary_intent`: main intent category
- `secondary_intents`: optional follow-up intents in same message
- `expected_outcome`: what user expects to happen this turn
- `target_requirement`: explicit name/path if provided; otherwise active requirement
- `constraints`: strict/dry-run/preferences explicitly mentioned by user

If multiple intents exist, execute in dependency order and keep each step idempotent.
If intent is ambiguous, ask one short disambiguation question. If user does not clarify, default to `clarification` for requirement-specific supplements.

## Routing map (must)

Route by intent to one skill or multiple skills:

1. `new_requirement` -> `spec-agent-task`
- User provides new requirement and expects full doc set generation.

2. `project_spec_init` -> `spec-agent-init`
- User explicitly asks to initialize fixed project spec path.

3. `switch_requirement` -> `spec-agent-switch`
- User asks to switch active requirement by name/path.

4. `batch_clarification_rewrite` -> `spec-agent-clarify`
- User indicates clarification rows are confirmed and asks systematic rewrite.

5. `doc_refine_without_clarify` -> `spec-agent-update`
- User asks to revise specific docs/sections directly (non-clarification workflow).

6. `draft_or_redraft_docs` -> `spec-agent-write`
- User asks to generate or regenerate requirement docs from current initialized workspace.

7. `run_quality_check` -> `spec-agent-check`
- User asks for final-check/quality gate.

8. `global_memory_explicit` -> `spec-agent-memory`
- User explicitly asks to add/change cross-requirement memory.

9. `chat_clarification_or_memory` -> handle in **this skill** (local flow below)
- Conversational one/few-message updates requiring automatic classification and immediate document linkage.

### Multi-skill chaining examples (must)

- Switch + clarify rewrite + check:
  - `spec-agent-switch` -> `spec-agent-clarify` -> `spec-agent-check`
- Memory update + sync + requirement check:
  - `spec-agent-memory` -> `sync-memory` (active requirement) -> `spec-agent-check`
- Init then draft docs:
  - `spec-agent-init` -> `spec-agent-write`
- New requirement then immediate supplement:
  - `spec-agent-task` -> local `clarification` flow (this skill)

## Memory preload (must)

- Read `spec/00-global-memory.md` before any classification or update.

## Active requirement precheck (must)

- For intents requiring an existing requirement context, resolve active requirement from `spec/.active`.
- Pin active requirement name as `<name>` and use explicit `--name <name>` on all requirement-targeted commands in this turn.
- If no active requirement exists:
  - for `new_requirement` and `project_spec_init`, continue by routing to `spec-agent-task` or `spec-agent-init`;
  - for other intents, stop and prompt user to initialize or switch first.
- When stop is required, do not write memory/clarification files and do not run checks.

### No-active response template (must)

When no active requirement exists, reply with:

- `状态`: 未检测到激活需求
- `下一步`:
  - `/spec-agent-task 这是一个新需求，请初始化并设为当前需求，然后开始文档流程。`
  - `/spec-agent-switch 切换到已有需求 <name>`
- `说明`: 未执行任何写入或检查

## Chat-local intent routing (must)

Only for route `chat_clarification_or_memory` in this skill:

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

## Chat-local write targets

- `clarification` -> active requirement `00-clarifications.md/.json`
- `memory` -> `spec/00-global-memory.md` (then sync snapshot to active requirement metadata)

## Chat-local post-save update loop (must)

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

- `route_plan` (skills executed in order; `spec-agent-chat(local)` when local flow is used)
- `intent`: `clarification` or `memory`
- `written_files`
- `updated_docs` (ordered)
- `section_changes` (doc -> changed sections)
- `check_result` (`issues=0` or issue summary)

### Standard status card (must)

Always output a user-friendly status card in this order:

1. `当前需求`: `<date>/<name>` or `未激活`
2. `路由结果`: executed skill(s) and order
3. `本次识别`: `clarification` / `memory` / other routed intent
4. `写入结果`: files updated this turn
5. `文档更新`: which docs were updated in dependency order
6. `阶段状态`: subagent stage matrix highlights (`current_stage`, reopened stages if any)
7. `变更摘要`: doc-level diff summary (see below)
8. `检查结果`: final-check conclusion or routed-skill check result
9. `下一步建议`: one short actionable sentence

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
- For routed intents, execute the target skill workflow as defined in that skill's `SKILL.md`; do not partially emulate and skip required gates.
- Use `subagent-*` commands for stage state; do not manually infer stage completion.
- **Scope**: Only write/update under `spec/` (clarifications, global memory, requirement docs). Do not modify project source code (temporary scripts excepted per AGENTS.md).

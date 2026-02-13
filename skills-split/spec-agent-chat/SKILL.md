---
name: spec-agent-chat
description: Route user chat into clarification or memory updates, then drive document refresh in AI-first mode. Use when users send conversational updates in AI IDE and expect automatic recording plus selective document updates.
---

# spec-agent-chat

Use this skill for direct AI IDE chat updates:
- `/spec-agent-chat ...`

## Memory preload (must)

- Read `spec/00-global-memory.md` before any classification or update.

## Active requirement precheck (must)

- Resolve active requirement from `spec/.active` before handling the message.
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
- Record to `00-clarifications.md/.json`.

2. `memory`
- Cross-requirement convention/preference/policy/terminology/compliance rule.
- Record to `spec/00-global-memory.md`.

If ambiguous:
- Ask one short disambiguation question.
- If user does not clarify, default to `clarification`.

## Write targets

- `clarification` -> active requirement `00-clarifications.md/.json`
- `memory` -> `spec/00-global-memory.md` (then sync snapshot to active requirement metadata)

## Post-save update loop (must)

After either `clarification` or `memory` write:

1. Determine impacted docs:
- `analysis`
- `prd`
- `tech`
- `acceptance`

2. Update docs only if needed, but enforce dependency order:
- `analysis` -> `prd` -> `tech` -> `acceptance`

3. Each updated doc must include:
- `## 全局记忆约束` with concrete bullets
- `## 澄清补充` block:
  - `<!-- CLARIFICATIONS:START -->`
  - `<!-- CLARIFICATIONS:END -->`
- confirmed clarification references using `C-xxx` when applicable

4. For `prd/tech/acceptance`, include dependency signatures:
- `<!-- DEPENDENCY-SIGNATURE:START -->`
- `<!-- DEPENDENCY-SIGNATURE:END -->`
- signature values must match current upstream content hashes

5. Run checks:
- `sync-memory` (when memory changed)
- `final-check`

6. If checks return issues:
- revise impacted docs and rerun `final-check` until stable

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
5. `变更摘要`: doc-level diff summary (see below)
6. `检查结果`: final-check conclusion
7. `下一步建议`: one short actionable sentence

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

## Hard constraints

- Do not use removed legacy generation commands.
- Keep AI-first behavior: caller AI writes document content directly.

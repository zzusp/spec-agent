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

5. Update docs only if needed, but enforce dependency order:
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

6. Each updated doc must include:
- `## 全局记忆约束` with concrete bullets
- `## 澄清补充` block:
  - `<!-- CLARIFICATIONS:START -->`
  - `<!-- CLARIFICATIONS:END -->`
- confirmed clarification references using `C-xxx` when applicable
- clarification focus must follow `project_mode`:
  - `greenfield`: broaden to baseline system decisions
  - `existing`: prioritize requirement/scheme impact; cross-cutting topics only when changed
- convergence rule: if an issue is a pure doc-quality fix (not a user decision), update docs directly and do not append new clarification rows

7. For `prd/tech/acceptance`, include dependency signatures:
- `<!-- DEPENDENCY-SIGNATURE:START -->`
- `<!-- DEPENDENCY-SIGNATURE:END -->`
- signature values must match current upstream content hashes

8. Run checks:
- `sync-memory` (when memory changed)
- `final-check`
```bash
python scripts/spec_agent.py sync-memory --name <name>
python scripts/spec_agent.py final-check --name <name>
```

9. Commit `final_check` stage only when `final-check` reports `issues=0`:
```bash
python scripts/spec_agent.py subagent-stage --name <name> --stage final_check --status completed --agent final-check-agent
```

10. If checks return issues:
- revise impacted docs and rerun `final-check` until stable
  - mark final_check failed:
```bash
python scripts/spec_agent.py subagent-stage --name <name> --stage final_check --status failed --agent final-check-agent --notes "<issue summary>"
```
  - runtime will auto-map issues to earliest impacted stage and reopen downstream stages (based on structured issue codes)

11. Return final stage state:
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

## Hard constraints

- Do not use removed legacy generation commands.
- Keep AI-first behavior: caller AI writes document content directly.
- Use `subagent-*` commands for stage state; do not manually infer stage completion.

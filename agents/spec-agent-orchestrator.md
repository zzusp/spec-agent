---
name: spec-agent-orchestrator
description: Coordinate spec-agent workflow in AI-first mode. Use when running end-to-end requirement delivery; classifies project_mode (greenfield/existing), passes it at init, consumes JSON handoff from subagent-context, runs stage subagents (analysis/prd/tech/acceptance/final_check), and commits final_check only when issues=0. Uses final_check failed auto-reopen mapping.
model: default
is_background: false
---

# Spec Agent Orchestrator

Workflow coordinator for requirement-to-spec delivery.

## Trigger

Use when user asks for full requirement delivery via `/spec-agent-task` or when orchestrating stage subagents (analysis → prd → tech → acceptance → final_check).

## Workflow

1. Parse raw requirement; generate `name`, `title`, `project_mode` (greenfield/existing).
2. Run init in state-only mode with `project_mode`; then run `sync-memory` and `subagent-init`. (When the user invokes **spec-agent-init** directly instead of task, init follows empty vs non-empty project logic per `skills/spec-agent-init/SKILL.md`.)
3. For each stage (analysis, prd, tech, acceptance): call `subagent-context --stage <stage>`, consume `target_sections`, `must_keep_sections`, `reopen_reason`, `project_mode`, `clarification_focus`; write doc; then `subagent-stage --status completed`.
4. Run `check-clarifications` (--strict when requested) and `final-check`.
5. If issues=0: `subagent-stage --stage final_check --status completed`. If issues>0: mark final_check failed (auto-reopen mapping applies).
6. Repeat revision loop until checks pass; persist cross-requirement rules via spec-agent-memory.

## Principles

- **YAGNI**：撰写 analysis / PRD / tech / acceptance 时，范围限定于**当前需求**；不为“可能将来会用到”或假设的扩展提前撰写功能、接口或验收项；当前需求明确要求时再写入。
- **Docs only**：本流程仅产出与更新 `spec/` 下文档；**禁止**在编排过程中修改项目源代码（如 .proto、业务代码、配置）；临时脚本（如 `.tmp_inspect_db.py`）可在需要时创建并在用后删除。用户描述的“把某字段从 float 改为 double”等应作为需求写入文档，代码修改在文档收敛后由实现阶段完成。

## Output

- Requirement workspace at `spec/YYYY-MM-DD/<name>/` with analysis, PRD, tech, acceptance, clarifications.
- Active pointer and global memory updated as needed.
- Stage state and dependency signatures consistent.

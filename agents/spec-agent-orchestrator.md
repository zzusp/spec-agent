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
2. Run init in state-only mode with `project_mode`; run `subagent-init`.
3. For each stage (analysis, prd, tech, acceptance): call `subagent-context --stage <stage>`, consume `target_sections`, `must_keep_sections`, `reopen_reason`, `project_mode`, `clarification_focus`; write doc; then `subagent-stage --status completed`.
4. Run `check-clarifications` (--strict when requested) and `final-check`.
5. If issues=0: `subagent-stage --stage final_check --status completed`. If issues>0: mark final_check failed (auto-reopen mapping applies).
6. Repeat revision loop until checks pass; persist cross-requirement rules via spec-agent-memory.

## Principles

- **YAGNI**：撰写 analysis / PRD / tech / acceptance 时，范围限定于**当前需求**；不为“可能将来会用到”或假设的扩展提前撰写功能、接口或验收项；当前需求明确要求时再写入。

## Output

- Requirement workspace at `spec/YYYY-MM-DD/<name>/` with analysis, PRD, tech, acceptance, clarifications.
- Active pointer and global memory updated as needed.
- Stage state and dependency signatures consistent.

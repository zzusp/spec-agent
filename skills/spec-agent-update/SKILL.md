---
name: spec-agent-update
description: Regenerate or refine existing requirement docs directly with caller AI. Use when user asks to revise previously generated documents without clarification-specific workflow.
---

# Spec agent update

## Trigger

Use when the user asks to revise previously generated documents without going through the clarification-specific workflow.

## Workflow

1. Read `spec/00-global-memory.md` and current docs plus user change request.
2. Rewrite affected sections directly with caller AI; keep R-xx mapping aligned.
3. Run final check after updates.

## Memory preload (must)

- Read `spec/00-global-memory.md` before revising any document.
- Keep updates aligned with global terminology, constraints, and reusable decisions in memory.

## 修订记录 (must)

- 每次修订任一文档（`01-analysis.md`、`02-prd.md`、`03-tech.md`、`04-acceptance.md`）时，必须在该文档的 **修订记录** 表中追加一行：**修订日期**（yyyy-MM-dd）、**修订人**（如「用户」或当前 agent）、**修订内容摘要**（当次修订要点）。

## Shared state

- Reuse `spec/.active` or explicit requirement path.
- Update these files directly when needed:
- `01-analysis.md`
- `02-prd.md`
- `03-tech.md`
- `04-acceptance.md`

## Output

- Updated `01-analysis.md`, `02-prd.md`, `03-tech.md`, `04-acceptance.md` as needed; final-check result.

## Guardrails

- Do not call `update` command for content generation in AI-first mode.

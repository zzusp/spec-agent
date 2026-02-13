---
name: spec-agent-update
description: Regenerate or refine existing requirement docs directly with caller AI. Use when user asks to revise previously generated documents without clarification-specific workflow.
---

# spec-agent-update

Use this skill for non-clarification-focused document revisions.

## Memory preload (must)

- Read `spec/00-global-memory.md` before revising any document.
- Keep updates aligned with global terminology, constraints, and reusable decisions in memory.

## Shared state

- Reuse `spec/.active` or explicit requirement path.
- Update these files directly when needed:
- `01-analysis.md`
- `02-prd.md`
- `03-tech.md`
- `04-acceptance.md`

## Process

1. Read current docs and user change request.
2. Rewrite affected sections directly with caller AI.
3. Keep R-xx requirement mapping aligned across docs.
4. Run final check after updates.

## Hard constraints

- Do not call `update` command for content generation in AI-first mode.

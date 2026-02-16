---
name: spec-agent-write
description: Write requirement documents directly with caller AI in AI-first mode. Use when workspace is initialized and docs must be drafted to satisfy section requirements and mandatory fields.
---

# spec-agent-write

Use this skill to draft and write document content directly.

## Memory preload (must)

- Read `spec/00-global-memory.md` before drafting.
- Treat memory content as global constraints for all sections and mandatory fields.

## Shared state

- Target directory comes from `spec/.active` or explicit requirement path.
- Required output files:
- `01-analysis.md`
- `02-prd.md`
- `03-tech.md`
- `04-acceptance.md`
- `00-clarifications.md`

## Writing rules

- Use caller AI reasoning, not template generation commands.
- Fill each doc according to repository-required sections and mandatory content.
- Ensure R-xx mapping consistency across analysis/PRD/tech/acceptance.
- For `00-clarifications.md`, generate candidate questions using `spec-agent-clarify` candidate question policy.
- In subagent mode, always read `subagent-context` before drafting current stage and commit completion with `subagent-stage`.
- Treat `subagent-context.project_mode` as mandatory routing signal for clarification focus:
  - `greenfield`: full-spectrum clarification (requirement + architecture + performance + deploy + security + stack/language/db choices + operations readiness).
  - `existing`: focus on requirement/technical impact and changed surface; cross-cutting topics are conditional (only when changed by requirement/solution).

## Hard constraints

- Do not use `write-all` / `write-analysis` / `write-prd` / `write-tech` / `write-acceptance`.

---
name: spec-agent-task
description: Coordinate the split spec-agent skills in AI-first mode. Use when user asks for end-to-end requirement delivery and expects the caller AI to generate name, title, and all document content directly.
---

# spec-agent-task

Use this skill as the single entry in AI IDE:
- `/spec-agent-task 现在产品提了一个新需求，需求如下：...`

## Child skills

- `spec-agent-memory`
- `spec-agent-switch`
- `spec-agent-init`
- `spec-agent-write`
- `spec-agent-clarify`
- `spec-agent-update`
- `spec-agent-check`

## AI-first contract (must)

1. Parse user text as `raw_requirement`.
2. Use caller AI reasoning to generate:
- `name` (kebab-case, <= 64 chars)
- `title` (clear business title)
3. Initialize workspace state only.
4. Generate document content directly with caller AI and write files.
5. Run clarification gate and final check.
6. If check returns issues, revise documents and repeat until acceptable.

## Shared state contract

- Requirement workspace: `spec/YYYY-MM-DD/<requirement_name>/`
- Active pointer: `spec/.active`
- Global memory: `spec/00-global-memory.md`

## Execution sequence

1. Read `spec/00-global-memory.md` and inject global constraints into drafting context.
2. If current target requirement is not the desired one, switch context via `spec-agent-switch`.
3. Sync memory snapshot to requirement metadata.
4. Run init in state-only mode (no template content generation).
5. Draft and write:
- `01-analysis.md`
- `02-prd.md`
- `03-tech.md`
- `04-acceptance.md`
- `00-clarifications.md`
  - generate clarification candidates by following `spec-agent-clarify` candidate question policy
6. Run clarification gate (`check-clarifications --strict` when strict requested).
7. Run `final-check`.
8. Resolve reported issues with two-phase loop:
- update only impacted sections first
- then re-review full affected docs and append newly found unclear items to clarifications
  - enforce per-round candidate cap from `spec-agent-clarify` (max 10 new candidates)
  - emit round report fields (`round_id`, `docs_rechecked`, `new_issues_found`, `new_candidates_added`, `high_impact_unresolved_count`, `reopen_count`)
9. Persist new cross-requirement constraints via `spec-agent-memory`.

## Hard constraints

- Do not use `write-all` / `write-analysis` / `write-prd` / `write-tech` / `write-acceptance` for content generation.
- Do not use `update` / `clarify` for content generation.
- Keep script usage for state and quality gates only (`sync-memory`, `init --state-only`, `check-clarifications`, `final-check`).

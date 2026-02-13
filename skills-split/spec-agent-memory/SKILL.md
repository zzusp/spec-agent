---
name: spec-agent-memory
description: Maintain project-level and user-level persistent memory shared by all requirements. Use when users provide global constraints, conventions, terminology, compliance rules, or preferences that should apply to every requirement.
---

# spec-agent-memory

Use this skill to keep cross-requirement memory up to date.

## Memory preload (must)

- Always read current `spec/00-global-memory.md` before adding or modifying entries.
- Merge changes in-place by section; do not duplicate existing rules.

## Shared memory file

- `spec/00-global-memory.md`

## Update rules

- Keep entries concise and factual.
- Store only reusable, cross-requirement constraints.
- Do not store one-off requirement details.
- When a rule changes, update existing entry instead of appending duplicates.

## Structure

Maintain sections:
- `## User Preferences`
- `## Project Constraints`
- `## Terminology`
- `## Compliance and Policy`
- `## Reusable Decisions`

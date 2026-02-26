---
name: spec-agent-memory
description: Maintain project-level and user-level persistent memory shared by all requirements. Use when users explicitly ask to add or change global memory; for in-conversation updates, spec-agent-chat can also record to global memory.
---

# Spec agent memory

## Trigger

Use when users **explicitly** ask to add or change global memory entries (constraints, conventions, terminology, compliance rules, or preferences that apply to every requirement). If the user provides such content in passing during conversation, `spec-agent-chat` can also record it (chat classifies as `memory` and writes to `spec/00-global-memory.md`).

## Workflow

1. Read current `spec/00-global-memory.md`.
2. Merge new or changed entries in-place by section; do not duplicate.
3. Keep entries concise and reusable; update existing entry when a rule changes.

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

## Output

- Updated `spec/00-global-memory.md` with merged, in-place changes.

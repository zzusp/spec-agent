---
name: spec-agent-memory
description: Maintain project-level and user-level persistent memory shared by all requirements. Use when users explicitly ask to add or change global memory; for in-conversation updates, spec-agent-chat can also record to global memory.
---

# Spec agent memory

## What global memory is for (must)

- **Purpose**: Global memory records **project-level context** (e.g. tech stack, deployment environment, compliance) and **user/team habits and conventions** (e.g. naming rules, delivery standards, “always record operator and source IP”) that apply across requirements. It is referenced when writing any requirement doc.
- **Do NOT store in global memory**: Single-requirement content—e.g. “本需求（xxx）：仅变更某 proto”“本需求不修改业务代码”、当前需求的范围/结论/描述. Those belong in requirement docs or `00-clarifications.md`, not in global memory.

## Trigger

Use when users **explicitly** ask to add or change global memory entries (constraints, conventions, terminology, compliance rules, or preferences that apply to **every** requirement). If the user provides such content in passing during conversation, `spec-agent-chat` can also record it (chat classifies as `memory` and writes to `spec/00-global-memory.md`).

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
- Store only **project context** or **cross-requirement** conventions/preferences (reusable for many requirements).
- **Do not** store: current-requirement scope, description, or conclusion (e.g. “本需求仅变更 proto”“本需求不修改业务代码”); those go in requirement docs or clarifications.
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

## Guardrails

- **Scope**: Only read/update `spec/00-global-memory.md` (and run `sync-memory` when needed). Do not modify project source code (temporary scripts excepted per AGENTS.md).
- **Content**: Do not add current-requirement scope, description, or conclusion to global memory; only project context and user/team conventions.

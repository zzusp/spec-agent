---
name: spec-agent-update
description: Regenerate or refine existing requirement docs directly with caller AI. Use when user explicitly asks to revise specific doc(s)/section(s) without clarification-table workflow; if intent is to apply confirmed clarifications, use spec-agent-clarify or spec-agent-chat.
disable-model-invocation: true
---

# Spec agent update

## Trigger

Use when the user **explicitly** asks to revise specific document(s) or section(s), **without** going through the clarification-table confirmation workflow. If the user intent is to apply already-confirmed clarifications to docs, use `spec-agent-clarify` or `spec-agent-chat` instead.

## Workflow

1. Read `spec/00-global-memory.md` and current docs plus user change request.
2. Rewrite affected sections directly with caller AI; keep R-xx mapping aligned. **YAGNI**：仅按用户当次修订意图修改，不引入当前需求与修订范围之外的“将来可能”设计或功能。
3. **若修订 04-acceptance.md**：验收项须满足可测试性（验收步骤可执行、通过标准可断言），见 `spec-agent-write`「04-acceptance.md 可测试性要求」。
4. Run final check after updates.

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
- **Scope**: Only update files under `spec/` (requirement docs). Do not modify project source code (temporary scripts excepted per AGENTS.md).

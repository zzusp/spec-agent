---
name: spec-agent-clarify
description: Close clarification items and drive clarification-based document rewrites in AI-first mode. Use when user has batch-confirmed clarification rows and wants systematic doc rewrites with round report; apply clarification decisions per AGENTS.md § Document update (apply clarifications).
disable-model-invocation: true
---

# Spec agent clarify

## Trigger

Use when the user has **batch-confirmed** clarification rows and wants **systematic** doc rewrites from confirmed decisions, with **round report** (clarification-driven rewrite loop). For single or few conversational updates, prefer `spec-agent-chat`.

## Workflow

1. Ensure clarification rows are updated (status 已确认, 用户确认/补充, 解决方案 filled).
2. Run `check-clarifications --strict`; if it passes, **apply confirmed clarifications to redesign and adjust full document content** (not only add C-xxx): two-phase update (targeted section rewrite, then holistic doc review). **YAGNI**：重写时勿引入当前澄清决策之外的“将来可能”范围或设计。
3. Add newly found unclear items to `00-clarifications.md/.json` per candidate question policy; run final check and iterate.

## Memory preload (must)

- Read `spec/00-global-memory.md` before clarification-driven rewrites.
- When clarified decisions conflict with memory, update memory first (via `spec-agent-memory`) and then rewrite docs.

## Clarification source

- `00-clarifications.md`
- `00-clarifications.json`

## Candidate question generation policy (must)

When generating candidate clarification questions, produce a prioritized list and apply all constraints below.

### Answerability constraints

Each question must be answerable by exactly one of:
- A short multiple-choice question with 2-5 mutually exclusive options.
- A one-word/short-phrase answer with explicit limit: `回答不超过 5 个词`.

### Impact filter

Include only questions whose answer materially affects at least one of:
- architecture decisions
- data modeling
- task decomposition
- test design
- UX behavior
- operations readiness
- compliance validation

Exclude:
- already answered items
- trivial style preferences
- plan-level execution details unless correctness is blocked
- pure document-quality/editorial fixes that can be resolved directly by updating docs (do not turn these into user clarifications)

### Scenario-aware focus (must)

Use requirement `project_mode` from metadata/context:
- `greenfield`:
  - default to full coverage across requirement, architecture, data, performance, deployment, security, compliance, operations readiness.
  - selected questions should proactively close baseline design decisions, not only immediate feature behavior.
- `existing`:
  - prioritize requirement behavior, impacted modules/interfaces/data paths, migration/rollback and acceptance consistency.
  - for performance/deployment/security/framework/language/database selection, ask only when requirement or proposed solution introduces explicit change/risk.

### Prioritization and coverage

- Prioritize questions that reduce rework risk or prevent acceptance-test inconsistency.
- Balance category coverage: cover highest-impact unresolved categories first.
- Do not ask two low-impact questions while any high-impact category remains unresolved.
- If more than 5 categories remain unresolved, choose top 5 by `(impact * uncertainty)` heuristic.

### Output format

For each candidate item, include:
- `priority` (P0/P1/P2)
- `category` (one of the impact categories above)
- `question`
- `answer_type` (`mcq` or `short_phrase`)
- `options` (required for `mcq`, 2-5 options)
- `constraint` (required for `short_phrase`: `回答不超过 5 个词`)

## Process

1. Ensure user has updated clarification rows:
- status set to `已确认`
- `用户确认/补充` filled
- `解决方案` filled
2. Run clarification gate:
```bash
python scripts/spec_agent.py check-clarifications --strict
```
3. If gate passes, apply confirmed clarifications to docs per **Document update (must)** below and AGENTS.md § Document update (apply clarifications).
4. Add newly found unclear items back into `00-clarifications.md/.json` as candidate questions (follow candidate question generation policy).
5. Run final check and iterate if needed.

## Document update (must)

- **遵循 AGENTS.md § Clarification policy → Document update (apply clarifications)**：结合澄清重写文档时，按该节的 Substantive update、Whole-document review、Targeted then holistic、修订记录、Acceptance 可测试性、Traceability minimum、Convergence 执行。
- **修订记录**：每次根据澄清更新任一文档时，在该文档的「## 修订记录」表中追加一行：修订日期（yyyy-MM-dd）、修订人（如「clarify-agent」或「用户」）、修订内容摘要（如「应用已确认澄清 C-xxx 重写相关章节」）。
- **Two-phase**：先按澄清影响修订相关段落，再通读整份文档做一致性检查；发现需用户决策的内容须追加到澄清文档并标为待确认。

## Minimal viable enhancement (enforced)

### Round-based closure loop

Run clarification in rounds. In each round:
1. Apply confirmed clarifications to impacted sections.
2. Re-check full affected docs for newly exposed issues.
3. Add new candidate clarification items.
4. Return a round report.

### Per-round candidate cap

- At most `10` new clarification candidates can be added in one round.
- If detected candidates exceed 10, keep top 10 by `(impact * uncertainty)` and defer the rest to next round.
- Convergence-first budget:
  - `existing` mode: prefer `<= 5` new candidates in one round.
  - `greenfield` mode: prefer `<= 8` new candidates in one round.

### Candidate selection strategy

- Prioritize unresolved high-impact categories first.
- Avoid adding low-impact candidates while high-impact unresolved categories still exist.
- Exclude already answered questions and non-material style preferences.

### Candidate metadata tags (required in question text or side notes)

For each new candidate, include:
- priority: `P0/P1/P2`
- category: `architecture/data_modeling/task_decomposition/test_design/ux_behavior/operations_readiness/compliance_validation`
- uncertainty: `U1/U2/U3` (low/medium/high)
- source: `<doc>#<section>`

### Round report (must)

After each round, output:
- `round_id`
- `docs_rechecked`
- `new_issues_found`
- `new_candidates_added` (must be `<= 10`)
- `high_impact_unresolved_count`
- `reopen_count`

## Output

- Updated analysis/PRD/tech/acceptance with clarification decisions applied; round report (round_id, docs_rechecked, new_issues_found, new_candidates_added, etc.).

## Guardrails

- Do not call `clarify` or `update` commands for content generation in AI-first mode.
- **Scope**: Only update files under `spec/` (requirement docs, clarifications). Do not modify project source code (temporary scripts excepted per AGENTS.md).

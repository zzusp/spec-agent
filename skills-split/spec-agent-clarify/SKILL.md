---
name: spec-agent-clarify
description: Close clarification items and drive clarification-based document rewrites in AI-first mode. Use when user confirms clarification rows and wants all docs regenerated from confirmed decisions.
---

# spec-agent-clarify

Use this skill for clarification lifecycle only.

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
3. If gate passes, apply confirmed clarifications to docs using two-phase update:
- Phase A (targeted rewrite): update only impacted sections of affected docs.
- Phase B (holistic review): re-check each affected doc as a whole (not only changed sections), identify newly exposed ambiguities/conflicts/test gaps.
4. Add newly found unclear items back into `00-clarifications.md/.json` as candidate questions (follow candidate question generation policy).
5. Run final check and iterate if needed.

## Two-phase update quality rule (must)

When applying a clarification to any of the 4 docs (`analysis/prd/tech/acceptance`), enforce:
- Section-level precision first (avoid unnecessary global rewrite).
- Whole-document consistency review immediately after section updates.
- If whole-document review finds new unresolved issues, do not silently continue; append them to clarifications and mark as pending.
- Prefer preventing acceptance-test mismatch and downstream rework over keeping question count low.

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

## Hard constraints

- Do not call `clarify` or `update` commands for content generation in AI-first mode.

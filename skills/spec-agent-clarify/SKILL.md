---
name: spec-agent-clarify
description: Close clarification items and drive clarification-based document rewrites in AI-first mode. Use when user confirms clarification rows and wants all docs regenerated from confirmed decisions; updates must apply clarification decisions to redesign and adjust full doc content (not only adding C-xxx references).
---

# Spec agent clarify

## Trigger

Use when the user has confirmed clarification rows and wants all docs regenerated from confirmed decisions (clarification-driven rewrite loop).

## Workflow

1. Ensure clarification rows are updated (status 已确认, 用户确认/补充, 解决方案 filled).
2. Run `check-clarifications --strict`; if it passes, **apply confirmed clarifications to redesign and adjust full document content** (not only add C-xxx): two-phase update (targeted section rewrite, then holistic doc review).
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
3. If gate passes, apply confirmed clarifications to docs using two-phase update (see **Document update scope** and **Two-phase update quality rule** below).
4. Add newly found unclear items back into `00-clarifications.md/.json` as candidate questions (follow candidate question generation policy).
5. Run final check and iterate if needed.

## 修订记录 (must)

- 每次根据澄清更新任一文档（`01-analysis.md`、`02-prd.md`、`03-tech.md`、`04-acceptance.md`、`00-clarifications.md`）时，必须在该文档的 **修订记录** 表中追加一行：**修订日期**（yyyy-MM-dd）、**修订人**（如「clarify-agent」或「用户」）、**修订内容摘要**（如「应用已确认澄清 C-xxx 重写相关章节」）。

## Document update scope (must): 结合澄清内容重新设计调整整份文档，而非仅添加澄清引用

- **Substantive update**: 根据已确认澄清的「用户确认/补充」与「解决方案」，修订文档中**所有受影响的章节与整体设计**，使正文结论、范围、方案、验收标准等与澄清决策一致。不得仅在各文档中增加 C-xxx 引用即视为完成。
- **Whole-document review (must)**: 每份文档更新时须**整体回顾整篇文档**，不仅修改与澄清直接对应的段落。思考：内容前后是否有矛盾、是否有更合适的表述或实现；若有矛盾或更优方案且可自行收敛则直接修正，若需用户决策则**追加到澄清文档**（`00-clarifications.md/.json`）为新澄清项、状态为待确认。
- **Targeted then holistic**: 先按澄清影响修订相关段落（需求范围、架构、数据、验收项等），再通读整份文档做一致性检查；若发现新的冲突、遗漏或需用户确认的点，补充到澄清或当轮修正。
- **Traceability minimum**: 每份文档须包含 `## 澄清补充` 区块并引用已确认澄清（C-xxx）、体现决策要点；仍须满足依赖签名与全局记忆约束等既有要求。

## Two-phase update quality rule (must)

When applying a clarification to any of the 4 docs (`analysis/prd/tech/acceptance`), enforce:
- Section-level precision first (avoid unnecessary global rewrite).
- **Whole-document review**: 通读整份文档，检查前后是否矛盾、是否有更合适的实现；需用户确认的内容必须追加到澄清文档并标为待确认。
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

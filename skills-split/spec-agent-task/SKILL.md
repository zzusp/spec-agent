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

## Subagent roles (must)

- `orchestrator-agent`
  - Owns routing, stage ordering, retries, and state transitions only.
  - Must not bypass stage state checks.
- `analysis-agent`
- `prd-agent`
- `tech-agent`
- `acceptance-agent`
- `final-check-agent`

## AI-first contract (must)

1. Parse user text as `raw_requirement`.
2. Use caller AI reasoning to generate:
- `name` (kebab-case, <= 64 chars)
- `title` (clear business title)
- `project_mode` (`greenfield` / `existing`)
   - `greenfield`: first-time project from scratch, no stable baseline to inherit
   - `existing`: new requirement on an existing project baseline
3. Initialize workspace state only.
4. Generate document content directly with caller AI and write files.
   - Prefer stage subagents (`analysis/prd/tech/acceptance/final_check`) coordinated by orchestrator.
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
4. Run init in state-only mode (no template content generation) and pass `project_mode`.
```bash
python scripts/spec_agent.py init --name <name> --title "<title>" --desc "<raw_requirement>" --state-only --project-mode <greenfield|existing>
```
5. Initialize stage orchestration state:
```bash
python scripts/spec_agent.py subagent-init --name <name>
```
6. Query current stage status before writing:
```bash
python scripts/spec_agent.py subagent-status --name <name> --json-output
```
7. Run stage subagents in order (`analysis -> prd -> tech -> acceptance`):
   - before each stage, read context:
```bash
python scripts/spec_agent.py subagent-context --name <name> --stage <stage> --json-output
```
   - consume handoff contract fields from context JSON:
     - `target_sections`
     - `must_keep_sections`
     - `reopen_reason`
     - `project_mode`
     - `clarification_focus`
   - stage subagent writes target doc (and clarifications when needed)
   - stage completes with:
```bash
python scripts/spec_agent.py subagent-stage --name <name> --stage <stage> --status completed --agent <stage-agent>
```
8. Ensure `00-clarifications.md` follows `spec-agent-clarify` candidate question policy and uses `project_mode` strategy:
   - `greenfield`: cover requirement + architecture + performance + deploy + security + stack/language/db selection + operations readiness.
   - `existing`: prioritize requirement/scheme/impact; only include performance/deploy/security/stack/language/db when requirement or solution explicitly affects them.
   - convergence rule: do not add clarification items for pure doc-quality fixes that can be resolved directly.
9. Run clarification gate (`check-clarifications --strict` when strict requested).
10. Run `final-check`; only when `issues=0` commit `final_check` stage:
```bash
python scripts/spec_agent.py final-check --name <name>
```
```bash
python scripts/spec_agent.py subagent-stage --name <name> --stage final_check --status completed --agent final-check-agent
```
11. If `final-check` has issues (`issues>0`), mark stage failed:
```bash
python scripts/spec_agent.py subagent-stage --name <name> --stage final_check --status failed --agent final-check-agent --notes "<issue summary>"
```
   - runtime will auto-map issues to earliest impacted stage and reopen downstream stages (based on structured issue codes)
   - check `last_reopen` in:
```bash
python scripts/spec_agent.py subagent-status --name <name> --json-output
```
12. Resolve reported issues with two-phase loop:
- update only impacted sections first
- then re-review full affected docs and append newly found unclear items to clarifications
  - enforce per-round candidate cap from `spec-agent-clarify` (max 10 new candidates)
  - emit round report fields (`round_id`, `docs_rechecked`, `new_issues_found`, `new_candidates_added`, `high_impact_unresolved_count`, `reopen_count`)
13. Persist new cross-requirement constraints via `spec-agent-memory`.

## Hard constraints

- Do not use `write-all` / `write-analysis` / `write-prd` / `write-tech` / `write-acceptance` for content generation.
- Do not use `update` / `clarify` for content generation.
- Keep script usage for state and quality gates only (`sync-memory`, `init --state-only`, `check-clarifications`, `final-check`, `subagent-init`, `subagent-context`, `subagent-stage`, `subagent-status`).

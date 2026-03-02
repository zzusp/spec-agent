---
name: spec-agent-task
description: Full-spec delivery skill. Use when user runs /spec-agent-task with requirement text and expects end-to-end analysis, PRD, tech, acceptance generation.
disable-model-invocation: true
---

# Spec agent task

## Trigger

**When**: User invokes `/spec-agent-task` with requirement text (the part after the command is `raw_requirement`).

**Examples**: `/spec-agent-task Fix login timeout` · `/spec-agent-task New requirement: add export to CSV`

**Boundary**: For “init vs task vs chat” and path strategy (date vs fixed), see **docs/INIT-VS-TASK-DECISION-TREE.md** and AGENTS.md § Entry decision.

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

1. Parse user text (or the text after `/spec-agent-task`) as `raw_requirement`.
2. Use caller AI reasoning to generate:
   - `name` (kebab-case, ≤64 chars)
   - `title` (clear business title)
   - `project_mode` (`greenfield` | `existing`): greenfield = first-time project; existing = new requirement on existing baseline
3. Initialize workspace state only.
4. Generate document content directly with caller AI and write files.
   - Prefer stage subagents (`analysis/prd/tech/acceptance/final_check`) coordinated by orchestrator.
   - **YAGNI**：撰写时范围限定于当前需求；不为假设的将来需求提前撰写功能或设计（见 `rules/coding.mdc`、`docs/开发规范与流程总结.md`）。
5. Run clarification gate and final check.
6. If check returns issues, revise documents and repeat until acceptable.

## Shared state contract

- **Project root**: The `spec` directory is under the **user’s project (workspace) root** (the CWD when running spec-agent commands), not the plugin repo root. Ensure commands run with the user’s project as current working directory.
- Requirement workspace: `spec/YYYY-MM-DD/<requirement_name>/`
- Active pointer: `spec/.active`
- Global memory: `spec/00-global-memory.md`

## Execution sequence

1. Read `spec/00-global-memory.md` and inject global constraints into drafting context.
2. If current target requirement is not the desired one, switch context via `spec-agent-switch`.
3. Run init in state-only mode (no template content generation) and pass `project_mode`. (This is the **task-orchestrated** flow; when the user invokes **spec-agent-init** directly, that skill uses empty vs non-empty project logic and may run full init—see `spec-agent-init` SKILL.)
```bash
python scripts/spec_agent.py init --name <name> --title "<title>" --desc "<raw_requirement>" --state-only --project-mode <greenfield|existing>
```
4. Sync memory snapshot to requirement metadata:
```bash
python scripts/spec_agent.py sync-memory --name <name>
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
   - **acceptance 阶段**：撰写验收项时须满足可测试性（验收步骤可执行、通过标准可断言），见 `spec-agent-write`「04-acceptance.md 可测试性要求」。
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
13. Persist **only project-level or user-preference** cross-requirement constraints via `spec-agent-memory`. Do **not** write the current requirement’s scope, description, or conclusion (e.g. “本需求仅变更某 proto”) to global memory; that belongs in requirement docs and clarifications.

## Output

- Requirement workspace at `spec/YYYY-MM-DD/<name>/` with analysis, PRD, tech, acceptance, clarifications.
- Active pointer and global memory updated as needed. Stage state and dependency signatures consistent.

## Scope and forbidden actions (must)

- **Output scope**: This skill **only** produces and updates files under the requirement workspace `spec/` (e.g. `01-analysis.md`, `02-prd.md`, `03-tech.md`, `04-acceptance.md`, `00-clarifications.md`, metadata). It does **not** implement or change project source code.
- **Forbidden**: Do **not** modify project source code (e.g. `.proto` files, application code, config files, dependencies). User requirements like "change field X from float to double" must be captured in the spec documents; code changes happen only **after** docs are closed and the user enters an implementation phase (e.g. TDD / development). **Exception**: temporary scripts (e.g. `.tmp_inspect_db.py` for DB inspection) may be created at project root and **must be deleted after use** per AGENTS.md.
- If the user text describes a concrete change (e.g. "把 lcia_result 从 float 改为 double") treat it as the **requirement description** for this run: init a requirement, write analysis → prd → tech → acceptance that specify this change; do **not** edit proto or code in this flow.

## Guardrails

- Do not use `write-all` / `write-analysis` / `write-prd` / `write-tech` / `write-acceptance` for content generation.
- Do not use `update` / `clarify` for content generation.
- Keep script usage for state and quality gates only (`sync-memory`, `init --state-only`, `check-clarifications`, `final-check`, `subagent-init`, `subagent-context`, `subagent-stage`, `subagent-status`).

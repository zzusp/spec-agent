# AGENTS Guide

## Scope

This repository uses split skills under `skills-split/` as the default workflow.
Legacy root skill entry files (`SKILL.md`, `agents/openai.yaml`) are intentionally removed.

Use `spec-agent-task` as the primary entry skill in AI IDE.

## When to trigger `spec-agent`

Trigger split skills when user intent includes any of:
- 提出开发需求或功能需求，需要产出完整需求文档集
- 编写/更新 `analysis` / `PRD` / `tech` / `acceptance` / `clarifications`
- 基于澄清文档多轮完善文档
- 执行最终检查并定位冲突、遗漏、不一致
- 指定并更新某个需求目录

## Canonical workflow

1. Use `/spec-agent-task <raw_requirement>` in AI IDE.
2. Caller AI generates `name/title` and writes docs directly in strict order:
   - `analysis` -> `prd` -> `tech` -> `acceptance`
3. Downstream docs must be based on upstream docs:
   - `prd` must incorporate `analysis`
   - `tech` must incorporate `analysis` + `prd`
   - `acceptance` must incorporate `analysis` + `prd` + `tech`
4. All four docs (`analysis/prd/tech/acceptance`) must always incorporate:
   - global memory (`spec/00-global-memory.md`)
   - confirmed clarifications (`00-clarifications.md/.json`)
   - for `prd/tech/acceptance`, include dependency signatures:
     - `<!-- DEPENDENCY-SIGNATURE:START --> ... <!-- DEPENDENCY-SIGNATURE:END -->`
     - signature values must match current upstream content hashes
5. Scripts are used for state/check gates (`sync-memory`, `init --state-only`, `check-clarifications`, `final-check`).
6. Repeat clarification loop until checks pass.

## Command contract (single source of truth)

| Command | Input | Output | Side effects |
|---|---|---|---|
| `init` | one of `--desc/--desc-json/--desc-file` (must carry user requirement content), optional `--name`, optional `--state-only` | requirement skeleton/state + metadata | create docs/state, set active |
| `scan` | target requirement | module candidates | update analysis scan block |
| `inspect-db` | target requirement | db schema summary | update analysis db-schema block |
| `sync-memory` | target requirement (or active) | memory hash synced to metadata | update metadata memory snapshot |
| `check-clarifications` | target requirement, optional `--strict` | unresolved clarification count | no write (strict mode returns non-zero when pending exists) |
| `final-check` | target requirement | issue count | append issues to clarifications |
| `set-active` | `--name` or `--path` | active pointer | update `spec/.active` |
| `list` | none | requirement list | no write |
| `copy-rules` | optional `--dest` | copy result | write `.cursor/rules` |

## Multi-requirement rules

- Prefer explicit `--name` (or `--path`) on all mutating commands.
- If omitted, command resolves by `spec/.active`.
- Use `set-active` before operations if context may be ambiguous.

## Dry-run policy

For mutating commands, support preview mode:
```bash
... --dry-run
```

Optional default:
- Set `dry_run_default: true` in `spec-agent.config.json`.

## Clarification policy

- Unclear points must be captured in `00-clarifications.md`.
- Only configured statuses are valid.
- Confirmed status is defined by config key: `clarify_confirmed_status`.

## DB context policy

- If requirement or clarification includes DB connection string or connection-file path:
  - analysis phase must inspect schema context,
  - connection evidence should be recorded in clarifications.
- `inspect-db` auto-inspects:
  - `sqlite://` directly,
  - `mysql://` with local `mysql` client,
  - `postgres://` / `postgresql://` with local `psql` client,
  - otherwise output guided fallback message.

## Regression policy

Run regression scripts sequentially:
```bash
python scripts/regression_smoke.py
python scripts/regression_edge_cases.py
python scripts/regression_split_skill_contract.py
```

Do not run them in parallel.  
`regression_edge_cases.py` temporarily overrides config for negative tests.

## References

- Split skills: `skills-split/`
- Runtime script: `scripts/spec_agent.py`
- Config: `spec-agent.config.json`

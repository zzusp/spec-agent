# AGENTS Guide

## Scope

This repository uses a single main skill: `spec-agent`.

Do not split into multiple skills for the core workflow.  
Use one lifecycle pipeline and execute by step-level commands.

## When to trigger `spec-agent`

Trigger `spec-agent` when user intent includes any of:
- 提出开发需求或功能需求，需要产出完整需求文档集
- 编写/更新 `analysis` / `PRD` / `tech` / `acceptance` / `clarifications`
- 基于澄清文档多轮完善文档
- 执行最终检查并定位冲突、遗漏、不一致
- 指定并更新某个需求目录

## Canonical workflow

1. Initialize requirement docs
```bash
python scripts/spec_agent.py init --name <name> --title "<title>" --desc "<raw_requirement>"
```
- `raw_requirement` is mandatory input from the user request.
- `name` is optional. If omitted, `init` auto-generates a kebab-case/fallback requirement name.
- `title` is optional. If omitted, `init` auto-generates title from requirement content.
- After auto-name init, subsequent commands can omit `--name` and use `spec/.active`.
- If missing, stop generation and ask user for requirement content first.

2. Optional scan and DB inspect
```bash
python scripts/spec_agent.py scan --name <name>
python scripts/spec_agent.py inspect-db --name <name>
```

3. Generate docs by stage
```bash
python scripts/spec_agent.py write-analysis --name <name>
python scripts/spec_agent.py write-prd --name <name>
python scripts/spec_agent.py write-tech --name <name>
python scripts/spec_agent.py write-acceptance --name <name>
```

Or one-shot generation:
```bash
python scripts/spec_agent.py write-all --name <name>
```

4. Clarification loop
- User updates `00-clarifications.md` (set confirmed status and fill solution).
- Rebuild docs:
```bash
python scripts/spec_agent.py update --name <name>
```
- Strict mode (block unresolved clarifications):
```bash
python scripts/spec_agent.py update --name <name> --strict
```

5. Final check
```bash
python scripts/spec_agent.py final-check --name <name>
```

## Command contract (single source of truth)

| Command | Input | Output | Side effects |
|---|---|---|---|
| `init` | one of `--desc/--desc-json/--desc-file` (must carry user requirement content), optional `--name` | requirement skeleton + metadata | create docs, set active |
| `scan` | target requirement | module candidates | update analysis scan block |
| `inspect-db` | target requirement | db schema summary | update analysis db-schema block |
| `write-all` | target requirement | full doc set + check result | update 4 docs + append clarifications + final-check |
| `write-analysis` | target requirement | analysis draft | update analysis + append clarifications |
| `write-prd` | target requirement | prd draft | update prd + append clarifications |
| `write-tech` | target requirement | tech draft | update tech + append clarifications |
| `write-acceptance` | target requirement | acceptance draft | update acceptance + append clarifications |
| `update` | target requirement | regenerated docs + check result | update 4 docs + append clarifications |
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
python scripts/regression_skill_contract.py
```

Do not run them in parallel.  
`regression_edge_cases.py` temporarily overrides config for negative tests.

## References

- Skill definition: `SKILL.md`
- Runtime script: `scripts/spec_agent.py`
- Config: `spec-agent.config.json`

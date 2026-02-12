---
name: spec-agent
description: Generate and maintain analysis/PRD/tech/acceptance/clarifications docs from user requirements with a clarification loop. Use when users propose new development or feature requirements, ask to write or update analysis/PRD/tech/acceptance/clarifications, iterate documents through clarification rounds, run final checks for conflicts or missing items, or update a specific requirement directory.
---

# spec-agent

Use this skill to build and maintain:
- `analysis`（分析报告）
- `PRD`
- `tech`（技术方案）
- `acceptance`（验收清单）
- `clarifications`（澄清文档）

All docs are Markdown and stored at:
- `spec/YYYY-MM-DD/<requirement_name_en>/`

## Trigger conditions

Trigger this skill when user intent matches any of the following:
- 提出开发需求或新功能需求，需要拆解并形成完整文档
- 明确要求编写或更新 `analysis/PRD/tech/acceptance/clarifications`
- 需要通过澄清文档驱动多轮完善文档
- 需要执行最终检查、定位文档冲突或遗漏
- 需要在多需求目录下切换并更新指定需求文档

## Workflow

0. 调用入参（必须先收集）
- Required:
- `raw_requirement`: 用户本轮需求原文（可多段）
- Optional:
- `name`: 需求英文名（目录名）；若不提供，`init` 自动生成
- `title`: 标题；若不提供，`init` 基于需求正文首行自动生成（再 fallback 到 `name`）
- `clarify`: 用户已知补充澄清（如 DB 连接信息）
- Rule:
- 未提供 `raw_requirement` 时，不允许直接执行 `write-*` / `update` 来“猜测需求”；必须先向用户索取需求正文，随后执行 `init`。
- Canonical init:
```bash
python scripts/spec_agent.py init --name <name> --title "<title>" --desc "<raw_requirement>"
```
- 若未提供 `name`，`init` 会自动生成目录名并设置为 active；后续可直接使用不带 `--name` 的命令。

1. 初始化文档骨架
- Collect: `需求英文名`、`标题(可选)`、`原始需求`
- Run:
```bash
python scripts/spec_agent.py init --name <name> --title "<title>" --desc "<raw_requirement>"
```
- Structured input is also supported:
```bash
python scripts/spec_agent.py init --name <name> --desc-json '{"goal":"...","scope":["...","..."]}'
python scripts/spec_agent.py init --name <name> --desc-file requirements.json
```
- If user already provides clarifications (e.g. DB connection info), include them at init:
```bash
python scripts/spec_agent.py init --name <name> --title "<title>" --desc "<raw_requirement>" --clarify "<extra_clarifications>"
```

2. 编写分析报告
- Optional scan:
```bash
python scripts/spec_agent.py scan --name <name>
```
- Optional DB inspect (auto-inspect sqlite; other protocols will output guided fallback):
```bash
python scripts/spec_agent.py inspect-db --name <name>
```
- Note:
- `sqlite://` will be inspected directly.
- `mysql://` requires local `mysql` client.
- `postgres://` / `postgresql://` requires local `psql` client.
- Generate:
```bash
python scripts/spec_agent.py write-analysis --name <name>
```
- Behavior:
- 自动将分析阶段不明确问题写入 `00-clarifications.md`（`归属文档=analysis`）
- 如果需求或补充澄清中包含数据库连接信息或存放数据库连接信息的文件路径，分析阶段应连接数据库读取库表结构并更新分析结论；连接信息会自动记录到 `00-clarifications.md`

3. 编写 PRD
- Run:
```bash
python scripts/spec_agent.py write-prd --name <name>
```
- Behavior:
- 自动将 PRD 阶段不明确问题写入 `00-clarifications.md`（`归属文档=prd`）

4. 编写技术方案
- Run:
```bash
python scripts/spec_agent.py write-tech --name <name>
```
- Behavior:
- 自动将技术阶段不明确问题写入 `00-clarifications.md`（`归属文档=tech`）

5. 编写验收清单
- Run:
```bash
python scripts/spec_agent.py write-acceptance --name <name>
```
- Behavior:
- 自动将验收阶段不明确问题写入 `00-clarifications.md`（`归属文档=acceptance`）

6. 用户补充澄清后更新文档
- User edits `00-clarifications.md`:
- 将可确认项标记为 `已确认`
- 填写 `用户确认/补充` 和 `解决方案`
- Run:
```bash
python scripts/spec_agent.py update --name <name>
```
- Strict mode (未闭环则阻止更新):
```bash
python scripts/spec_agent.py update --name <name> --strict
```
- Behavior:
- 基于已确认澄清重生成 `analysis/PRD/tech/acceptance`
- 采用章节级更新，尽量保留文档中的人工补充章节
- 自动执行 `final-check`

7. 单独执行最终检查
```bash
python scripts/spec_agent.py final-check --name <name>
```

7.5 一键生成全部文档
```bash
python scripts/spec_agent.py write-all --name <name>
```

8. Dry run (no file writes)
- For mutating commands, append `--dry-run` to preview actions without writing files.
- You can also set `dry_run_default: true` in config to make dry-run default.

## Multi-requirement operations

Switch active requirement:
```bash
python scripts/spec_agent.py set-active --name <name>
```

List requirements:
```bash
python scripts/spec_agent.py list
```

All write/update/check commands also support:
- `--path <spec/YYYY-MM-DD/name>`
- If `--name` and `--path` are omitted, script uses `spec/.active`

## Rules copy

Copy allowed rules to `.cursor/rules/`:
```bash
python scripts/spec_agent.py copy-rules
```

## Regression smoke test

Run local smoke regression:
```bash
python scripts/regression_smoke.py
```

Run edge-case regression:
```bash
python scripts/regression_edge_cases.py
```

Run skill contract regression:
```bash
python scripts/regression_skill_contract.py
```
- Run these scripts sequentially (do not run in parallel), because edge-case test temporarily overrides config.

Run all regressions in one step:
```bash
python scripts/regression_all.py
```

## Caller-agent contract

### Command contract
| Command | Required input | Output | Side effects |
|---|---|---|---|
| `init` | (`--desc` / `--desc-json` / `--desc-file` at least one) + optional `--name` | requirement directory + metadata | create docs, set active |
| `scan` | `--name` or `--path` or active | module list in analysis scan block | update `01-analysis.md` |
| `inspect-db` | `--name` or `--path` or active | DB schema summary block | update `01-analysis.md` |
| `write-all` | target requirement | full doc set + check result | update 4 docs, append clarifications, run final-check |
| `write-analysis` | target requirement | analysis draft | update `01-analysis.md`, append clarifications |
| `write-prd` | target requirement | PRD draft | update `02-prd.md`, append clarifications |
| `write-tech` | target requirement | tech draft | update `03-tech.md`, append clarifications |
| `write-acceptance` | target requirement | acceptance draft | update `04-acceptance.md`, append clarifications |
| `update` | target requirement | regenerated docs + check result | update 4 docs, append clarifications |
| `final-check` | target requirement | issue count | append issues into clarifications |
| `copy-rules` | optional `--dest` | copy result | write `.cursor/rules` |
| `set-active` | `--name` or `--path` | active target | update `spec/.active` |
| `list` | none | requirement list | no write |

Notes:
- `init` accepts one or more: `--desc` / `--desc-json` / `--desc-file`; `--name` omitted will auto-generate requirement name.
- `00-clarifications.md` and `00-clarifications.json` are auto-synced; newer side wins when mismatch is detected.
- All commands support top-level `--json-output` and `--verbose`.

Caller responsibilities:
- Follow `rules/*.mdc` before writing/refining content
- Always pass user requirement content into init (`--desc` / `--desc-json` / `--desc-file`) before generation
- Ground content in user requirement + codebase context + clarifications
- Keep PRD free from implementation details
- Ensure unresolved items are captured in `00-clarifications.md`

## Quality gates

- PRD must not contain technical implementation details
- Tech doc must include architecture, DB design, executable SQL, test points, and rollback strategy
- Acceptance doc must include full scenario coverage and impacted-function verification
- Cross-doc consistency: `R-xx` requirement IDs in PRD/tech/acceptance must align with analysis
- Final-check output must be resolved via clarification loop

## Optional config

`spec-agent.config.json` supports:
- `spec_dir`
- `date_format`
- `placeholders`
- `prd_tech_words`
- `prd_tech_whitelist`
- `clarify_columns`
- `clarify_statuses`
- `clarify_confirmed_status`
- `enable_auto_seed_clarifications`
- `max_seed_questions_per_doc`
- `doc_clarify_seeds`
- `max_context_file_kb`
- `min_doc_bullets`
- `dry_run_default`
- `rules_copy_allowlist`

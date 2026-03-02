# AGENTS Guide

## Scope

This repository follows the Cursor Plugin layout (see `.cursor-plugin/plugin.json`): skills live under `skills/`, plugin-level agents under `agents/`, rules under `rules/`.

Use `spec-agent-chat` as the unified conversational entry in AI IDE; `spec-agent-task` remains the direct full-spec generation command when user explicitly calls it.

## Documentation source hierarchy (single source of truth)

**Canonical source**: **AGENTS.md (this file)** is the single source of truth for workflow, command contract, and guardrails. Other docs must not redefine or duplicate these; they reference AGENTS.md or supply only supplementary content.

Precedence when content overlaps:

1. **AGENTS.md (this file)**: normative workflow, command contract, and hard guardrails.
2. **skills/*/SKILL.md**: skill-specific execution details; must not contradict AGENTS.md.
3. **commands/*.md**: slash-command entry wrappers; point to SKILL.md and AGENTS.md, not redefine contracts.
4. **README.md / QUICKSTART.md**: onboarding and examples; informational only. Contract details → AGENTS.md.
5. **docs/PLUGIN-AND-SKILL-COMPLIANCE.md**: compliance explanation and rationale; informational only. Contract → AGENTS.md.

**Conflict rule**: If any wording conflicts, **AGENTS.md wins**.

**Update rule**: For contract/process changes, update **AGENTS.md first**, then align other docs by reference (avoid duplicating long normative blocks).

**Consistency**: QUICKSTART.md and PLUGIN-AND-SKILL-COMPLIANCE.md do not duplicate command tables, path rules, or init/task boundaries from AGENTS.md; they link or summarize. When editing those docs, verify alignment with AGENTS.md to reduce drift.

## When to trigger `spec-agent`

Trigger split skills when user intent includes any of:

- **Unified chat entry**: user message via `/spec-agent-chat ...` should first be checked for spec-agent relevance; if in-scope, route to one or multiple skills by intent.
- **Slash-command with requirement** (e.g. `/spec-agent-task Fix login timeout` or `/spec-agent-task New requirement: ...`) → trigger `spec-agent-task`. Each skill is also exposed as a **command** with the same name (e.g. `spec-agent-task`) so that typing `/spec-agent-xxx` in Cursor reliably invokes that skill; see `commands/spec-agent-*.md` and `docs/PLUGIN-AND-SKILL-COMPLIANCE.md`.
- User proposes a dev or feature requirement and needs a full requirement doc set
- Write/update `analysis` / `PRD` / `tech` / `acceptance` / `clarifications`
- Refine docs over multiple rounds based on clarifications
- Run final check and surface conflicts, gaps, inconsistencies
- Designate and update a requirement directory

## Canonical workflow

1. Prefer `/spec-agent-chat <message>` as unified dialogue entry in AI IDE; when user explicitly wants direct full generation, use `/spec-agent-task <raw_requirement>`.
2. **Scope (all spec-agent skills)**: Every spec-agent skill **only** writes/updates files under `spec/` (requirement docs, global memory, metadata, `spec/.active`, and under `spec/db/` when applicable). No skill may modify **project source code** (e.g. `.proto`, application code, config, dependencies); code changes belong to the implementation phase after docs are closed. **Exception**: temporary scripts (e.g. `.tmp_inspect_db.py` at project root for DB inspection per “DB context policy” below) may be created for script execution and **must be deleted after use**.
  - **Where `spec/` lives**: The `spec` directory is always under the **user’s project (workspace) root**—the directory from which the spec-agent commands are run (current working directory), **not** the plugin/skill repository root. When using the plugin in an IDE, ensure the process runs with the user’s project as CWD so that `spec/` is created at `<user_project_root>/spec`. Override with env `SPEC_AGENT_PROJECT_ROOT` if needed.
3. Caller AI generates `name/title` and writes docs directly in strict order:
  - `analysis` -> `prd` -> `tech` -> `acceptance`
4. Downstream docs must be based on upstream docs:
  - `prd` must incorporate `analysis`
  - `tech` must incorporate `analysis` + `prd`
  - `acceptance` must incorporate `analysis` + `prd` + `tech`
5. All four docs (`analysis/prd/tech/acceptance`) must always incorporate:
  - global memory (`spec/00-global-memory.md`)
  - confirmed clarifications (`00-clarifications.md` as source of truth, `.json` as mirror)
  - for `prd/tech/acceptance`, include dependency signatures:
    - `<!-- DEPENDENCY-SIGNATURE:START --> ... <!-- DEPENDENCY-SIGNATURE:END -->`
    - signature values must match current upstream content hashes
  - **修订记录**：五份文档（`analysis` / `PRD` / `tech` / `acceptance` / `clarifications`）均包含「## 修订记录」表（修订日期 yyyy-MM-dd、修订人、修订内容摘要）。凡会修改上述文档的 skill 在每次更新文档时，必须在该文档的修订记录表中追加一行。
6. Scripts are used for state/check gates (`sync-memory`, `init`, `check-clarifications`, `final-check`).
  - **spec-agent-init** (when invoked standalone): Uses **fixed date** `--date 0000-00-00` so the requirement path is `spec/0000-00-00/project-spec/`. First judge if the user's project is **empty** (no source dirs/code files). **Empty** → `init --state-only` (skeleton only). **Non-empty** → `init` without `--state-only` (creates all doc templates), then caller AI fills 01/02/03; 04 and clarifications remain default. See `skills/spec-agent-init/SKILL.md`.
  - When using stage subagents, also use:
    - `subagent-init`
    - `subagent-context`
    - `subagent-stage`
    - `subagent-status`
7. Repeat clarification loop until checks pass.

## Entry decision (init vs task)

Use this decision order to avoid mixing `spec-agent-init` and `spec-agent-task`:

1. Default conversational entry:
   - `/spec-agent-chat <message>`
2. Requirement-specific full spec generation (date-based requirement workspace):
   - `/spec-agent-task <raw_requirement>`
3. Project baseline initialization at fixed path `spec/0000-00-00/project-spec/`:
   - `/spec-agent-init <message>`

Practical boundary:
- `spec-agent-task`: for **new requirement delivery** and iterative requirement docs.
- `spec-agent-init`: for **project-level bootstrap/refresh** at fixed path (empty-vs-non-empty logic).
- Do not use `spec-agent-init` as the default command for every new requirement.
- See `docs/INIT-VS-TASK-DECISION-TREE.md` for examples and anti-patterns.

## Command contract (single source of truth)


| Command                | Input                                                                                                                                                                             | Output                                                                                                              | Side effects                                                                                                                |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `init`                 | one of `--desc/--desc-json/--desc-file` (must carry user requirement content), optional `--name`, optional `--state-only`, optional `--project-mode` (`auto/greenfield/existing`) | **With `--state-only`**: skeleton + metadata. **Without**: skeleton + metadata + 01–04 and clarifications (default template content). | **With `--state-only`**: create state, set active. **Without**: create docs + state, set active. |
| `scan`                 | target requirement                                                                                                                                                                | module candidates                                                                                                   | update analysis scan block                                                                                                  |
| `inspect-db`           | target requirement                                                                                                                                                                | db schema summary                                                                                                   | update analysis db-schema block                                                                                             |
| `sync-memory`          | target requirement (or active)                                                                                                                                                    | memory hash synced to metadata                                                                                      | update metadata memory snapshot                                                                                             |
| `check-clarifications` | target requirement, optional `--strict`                                                                                                                                           | unresolved clarification count                                                                                      | no write (strict mode returns non-zero when pending exists)                                                                 |
| `final-check`          | target requirement                                                                                                                                                                | issue count                                                                                                         | append clarification-relevant issues to clarifications (non-clarification quality issues only reported)                     |
| `set-active`           | `--name` or `--path`                                                                                                                                                              | active pointer                                                                                                      | update `spec/.active`                                                                                                       |
| `list`                 | none                                                                                                                                                                              | requirement list                                                                                                    | no write                                                                                                                    |
| `copy-rules`           | optional `--dest`                                                                                                                                                                 | copy result                                                                                                         | write `.cursor/rules`                                                                                                       |
| `subagent-init`        | target requirement, optional `--reset`                                                                                                                                            | stage-state initialized                                                                                             | update metadata `subagents` section                                                                                         |
| `subagent-context`     | target requirement + `--stage`                                                                                                                                                    | stage input context (`target_sections`/`must_keep_sections`/`reopen_reason` + `project_mode`/`clarification_focus`) | no write (except one-time state normalization)                                                                              |
| `subagent-stage`       | target requirement + `--stage` + `--status`                                                                                                                                       | stage update result                                                                                                 | update stage status / hashes; may downgrade downstream to pending; for `final_check failed` auto-map issues to reopen stage |
| `subagent-status`      | target requirement, optional `--normalize`                                                                                                                                        | stage matrix + stale stages                                                                                         | default no write; with `--normalize` writes stale stages back to `pending`                                                  |


> AI 判定说明：当 `init` 未显式传入 `--project-mode`（即 `auto`）或未传 `--name` 需要自动命名时，运行时会调用 AI 判定命令。需配置环境变量 `SPEC_AGENT_AI_JUDGE_COMMAND` 或配置项 `ai_judge_command`；判定失败时会直接报错，不做关键字兜底。

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

- Set `dry_run_default: true` in `scripts/spec-agent.config.json`.

## Global memory content policy

- **Purpose**: `spec/00-global-memory.md` records **project-level context** (e.g. tech stack, deployment, compliance) and **user/team habits and conventions** (e.g. naming rules, “all requirements must record operator and source IP”) that apply across requirements.
- **Do NOT write to global memory**: Single-requirement scope, description, or conclusion (e.g. “本需求（xxx）：仅变更某 proto”“本需求不修改业务代码”). Those belong in requirement docs or `00-clarifications.md`. Global memory is for **project situation and user habits**, not for the content of one requirement.

## Clarification policy

- Unclear points must be captured in `00-clarifications.md`.
- `00-clarifications.md` is the single source of truth; `00-clarifications.json` is a machine-readable mirror.
- Only configured statuses are valid.
- Confirmed status is defined by config key: `clarify_confirmed_status`.
- When applying confirmed clarifications to docs (e.g. via spec-agent-clarify or spec-agent-chat): combine clarification content to redesign and adjust full document; review whole document for contradictions or better implementations; append items that need user confirmation to the clarification doc as new pending rows.

### Document update (apply clarifications)

When applying confirmed clarifications to any of the four docs (analysis / PRD / tech / acceptance), the following rules are the single source of truth. Skills spec-agent-clarify and spec-agent-chat must follow them; they may add only skill-specific output (e.g. round report, status card).

- **Substantive update**: 根据已确认澄清的「用户确认/补充」与「解决方案」，修订文档中**所有受影响的章节与整体设计**，使正文结论、范围、方案、验收标准等与澄清决策一致。不得仅在各文档中增加 C-xxx 引用即视为完成。
- **Whole-document review (must)**: 每份文档更新时须**整体回顾整篇文档**，不仅修改与澄清直接对应的段落。若有矛盾或更优方案且可自行收敛则直接修正，若需用户决策则追加到澄清文档（`00-clarifications.md/.json`）为新澄清项、状态为待确认。
- **Targeted then holistic**: 先按澄清影响修订相关段落，再通读整份文档做一致性检查；若发现新的冲突、遗漏或需用户确认的点，补充到澄清或当轮修正。
- **修订记录**: 每次更新任一文档（`01-analysis.md`、`02-prd.md`、`03-tech.md`、`04-acceptance.md`、`00-clarifications.md`）时，在该文档的「## 修订记录」表中追加一行：修订日期（yyyy-MM-dd）、修订人、修订内容摘要。
- **Acceptance 可测试性**: 凡修改或新增验收项（A-xxx），须保持验收步骤可执行、通过标准可断言；若澄清导致验收条件变化，须把验收步骤与通过标准改写为可测试形式，便于实现阶段 TDD。
- **Traceability minimum**: 每份文档须包含 `## 澄清补充` 区块并引用已确认澄清（C-xxx）、体现决策要点；仍须满足依赖签名与全局记忆约束等既有要求。
- **Convergence**: 纯文档质量/表述问题可直接在文档中修正，不要扩充澄清列表；需用户决策的内容才追加为待确认澄清项。

## DB context policy

- If requirement or clarification includes DB connection string or connection-file path:
  - analysis phase must inspect schema context,
  - connection evidence should be recorded in clarifications.
- **方式 B（DB 探查脚本）**：获取数据库表结构时，由 AI 在**项目根目录**生成固定文件名的**临时**脚本（见下），用于连接并取表信息；调用 `inspect-db` 执行该脚本，获取到结果后**自动删除临时脚本**。
- **inspect-db**：仅通过临时脚本获取 schema。临时脚本路径固定为项目根目录下 `./.tmp_inspect_db.py`；存在则执行，**执行完毕后删除该文件**。全量 schema 写入**公共存储** `spec/db/{scheme}-{dbname}-schema.md`（如 `spec/db/postgres-hiq_admin-schema.md`）；若脚本输出含可选 `ddl_sql`，则同时写入 `spec/db/{scheme}-{dbname}-ddl.sql` 作为全量 DDL。各需求 `01-analysis.md` 的「数据库现状」块仅写入引用行：`本需求涉及表详见 [dbname schema 文档](spec/db/xxx-schema.md)。`。无脚本或执行失败时在 db-schema 块中写入提示。
- **DB 探查脚本契约**（项目根目录 `./.tmp_inspect_db.py`）：
  - **输入**：stdin 接收单个 JSON 对象 `{"connections": ["uri1", "uri2", ...]}`。
  - **输出**：stdout 输出单个 JSON 对象 `{"results": [{"connection": "…", "ok": true|false, "message": "…", "tables": {"表名": ["列1","列2",…]}, "table_comments": {"表名":"表注释"}}], "ddl_sql": "可选"}`。
    - `tables` 可省略或为空；列列表可为空；列建议使用 `列名:类型（注释：字段注释）` 的字符串形式。
    - `table_comments` 可省略或为空。
    - **ddl_sql**（可选）：全量 DDL SQL 字符串（如 `CREATE TABLE …;`、索引等）。若提供，引擎会写入 `spec/db/{slug}-ddl.sql`；PostgreSQL 可在脚本内用 `pg_dump --schema-only` 子进程获取，MySQL 可用 `SHOW CREATE TABLE` 拼接。
  - 脚本需自行选择并安装所需驱动（如缺驱动可在 message 中说明安装建议）；运行目录为项目根目录。

## Regression policy

Run regression scripts sequentially:

```bash
python scripts/regression_smoke.py
python scripts/regression_edge_cases.py
python scripts/regression_split_skill_contract.py
```

Do not run them in parallel.  
`regression_edge_cases.py` temporarily overrides config for negative tests. On Windows, two lock/concurrent tests are skipped to avoid runner-induced KeyboardInterrupt; lock semantics are exercised on Unix.

## Principles (see also)

- **YAGNI (You Aren't Gonna Need It)**：不实现、不撰写当前需求不需要的内容；不为“可能将来会用到”提前做功能/抽象/扩展或文档中的设计。详见 `rules/coding.mdc`、`rules/delivery.mdc` 与 `docs/开发规范与流程总结.md`。

## References

- Split skills: `skills/` (plugin manifest: `.cursor-plugin/plugin.json`)
- Plugin agents: `agents/`
- Runtime script: `scripts/spec_agent.py`
- Config: `scripts/spec-agent.config.json`
- Plugin & skill compliance: `docs/PLUGIN-AND-SKILL-COMPLIANCE.md` (trigger model, script usage, skill-to-skill)


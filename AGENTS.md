# AGENTS Guide

## Scope

This repository follows the Cursor Plugin layout (see `.cursor-plugin/plugin.json`): skills live under `skills/`, plugin-level agents under `agents/`, rules under `rules/`.

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
   - confirmed clarifications (`00-clarifications.md` as source of truth, `.json` as mirror)
   - for `prd/tech/acceptance`, include dependency signatures:
   - **修订记录**：五份文档（`analysis` / `PRD` / `tech` / `acceptance` / `clarifications`）均包含「## 修订记录」表（修订日期 yyyy-MM-dd、修订人、修订内容摘要）。凡会修改上述文档的 skill 在每次更新文档时，必须在该文档的修订记录表中追加一行。
   - for `prd/tech/acceptance`, include dependency signatures:
     - `<!-- DEPENDENCY-SIGNATURE:START --> ... <!-- DEPENDENCY-SIGNATURE:END -->`
     - signature values must match current upstream content hashes
5. Scripts are used for state/check gates (`sync-memory`, `init --state-only`, `check-clarifications`, `final-check`).
   - When using stage subagents, also use:
     - `subagent-init`
     - `subagent-context`
     - `subagent-stage`
     - `subagent-status`
6. Repeat clarification loop until checks pass.

## Command contract (single source of truth)

| Command | Input | Output | Side effects |
|---|---|---|---|
| `init` | one of `--desc/--desc-json/--desc-file` (must carry user requirement content), optional `--name`, optional `--state-only`, optional `--project-mode` (`auto/greenfield/existing`) | requirement skeleton/state + metadata | create docs/state, set active |
| `scan` | target requirement | module candidates | update analysis scan block |
| `inspect-db` | target requirement | db schema summary | update analysis db-schema block |
| `sync-memory` | target requirement (or active) | memory hash synced to metadata | update metadata memory snapshot |
| `check-clarifications` | target requirement, optional `--strict` | unresolved clarification count | no write (strict mode returns non-zero when pending exists) |
| `final-check` | target requirement | issue count | append clarification-relevant issues to clarifications (non-clarification quality issues only reported) |
| `set-active` | `--name` or `--path` | active pointer | update `spec/.active` |
| `list` | none | requirement list | no write |
| `copy-rules` | optional `--dest` | copy result | write `.cursor/rules` |
| `subagent-init` | target requirement, optional `--reset` | stage-state initialized | update metadata `subagents` section |
| `subagent-context` | target requirement + `--stage` | stage input context (`target_sections`/`must_keep_sections`/`reopen_reason` + `project_mode`/`clarification_focus`) | no write (except one-time state normalization) |
| `subagent-stage` | target requirement + `--stage` + `--status` | stage update result | update stage status / hashes; may downgrade downstream to pending; for `final_check failed` auto-map issues to reopen stage |
| `subagent-status` | target requirement, optional `--normalize` | stage matrix + stale stages | default no write; with `--normalize` writes stale stages back to `pending` |

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
`regression_edge_cases.py` temporarily overrides config for negative tests. On Windows, two lock/concurrent tests are skipped to avoid runner-induced KeyboardInterrupt; lock semantics are exercised on Unix.

## Principles (see also)

- **YAGNI (You Aren't Gonna Need It)**：不实现、不撰写当前需求不需要的内容；不为“可能将来会用到”提前做功能/抽象/扩展或文档中的设计。详见 `rules/coding.mdc`、`rules/delivery.mdc` 与 `docs/开发规范与流程总结.md`。

## References

- Split skills: `skills/` (plugin manifest: `.cursor-plugin/plugin.json`)
- Plugin agents: `agents/`
- Runtime script: `scripts/spec_agent.py`
- Config: `scripts/spec-agent.config.json`
- Plugin & skill compliance: `docs/PLUGIN-AND-SKILL-COMPLIANCE.md` (trigger model, script usage, skill-to-skill)

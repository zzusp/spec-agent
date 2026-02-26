---
name: spec-agent-write
description: Write requirement documents directly with caller AI in AI-first mode. Use when workspace is initialized and docs must be drafted to satisfy section requirements and mandatory fields.
---

# Spec agent write

## Trigger

Use when the workspace is initialized and docs must be drafted (analysis, PRD, tech, acceptance, clarifications) with caller AI writing content directly.

## Workflow

1. Read `spec/00-global-memory.md` and treat as global constraints.
2. For each stage (analysis → prd → tech → acceptance), read `subagent-context` when in subagent mode, then write the target doc and run `subagent-stage` on completion.
3. Ensure R-xx mapping and dependency signatures; generate clarification candidates per `spec-agent-clarify` policy.

## Memory preload (must)

- Read `spec/00-global-memory.md` before drafting.
- Treat memory content as global constraints for all sections and mandatory fields.

## Shared state

- Target directory comes from `spec/.active` or explicit requirement path.
- Required output files:
- `01-analysis.md`
- `02-prd.md`
- `03-tech.md`
- `04-acceptance.md`
- `00-clarifications.md`

## 修订记录 (must)

- 每次创建或更新任一文档（`01-analysis.md`、`02-prd.md`、`03-tech.md`、`04-acceptance.md`、`00-clarifications.md`）时，必须在该文档的 **修订记录** 表中追加一行：**修订日期**（yyyy-MM-dd）、**修订人**（如阶段 agent 名或「初始化」）、**修订内容摘要**（简要说明当次修改）。文档模板已包含「## 修订记录」表头与分隔符，只需在表体追加新行。

## Writing rules

- Use caller AI reasoning, not template generation commands.
- Fill each doc according to repository-required sections and mandatory content.
- Ensure R-xx mapping consistency across analysis/PRD/tech/acceptance.
- For `00-clarifications.md`, generate candidate questions using `spec-agent-clarify` candidate question policy.

### 04-acceptance.md（验收项）可测试性要求（must）

撰写或更新验收清单时，每条验收项（A-xxx）须便于实现阶段按 TDD（RED-GREEN-REFACTOR）先写失败测试再实现：

- **验收步骤**：须**可执行**——明确「在何种前置条件下、执行何种操作、输入/输出或系统状态可观测」；避免仅描述意图而无可操作步骤。
- **通过标准**：须**可断言**——每条标准能对应成测试中的明确判定（真/假或等价于断言），例如返回值、状态码、数据变更、日志条目等；禁止仅用「功能正常」「体验良好」等不可验证表述作为唯一通过标准，须拆成可验证条款。
- **建议测试层级**（可选）：对每条 A-xxx 标注建议验证层级（单元 / 集成 / 端到端），便于实现时先写对应层级的失败测试。
- 与 R-xx、技术方案一致：验收项须能追溯到 PRD/tech 中的需求与设计，且表述与 03-tech 中的接口、数据、流程一致，避免实现时歧义。
- In subagent mode, always read `subagent-context` before drafting current stage and commit completion with `subagent-stage`.
- Treat `subagent-context.project_mode` as mandatory routing signal for clarification focus:
  - `greenfield`: full-spectrum clarification (requirement + architecture + performance + deploy + security + stack/language/db choices + operations readiness).
  - `existing`: focus on requirement/technical impact and changed surface; cross-cutting topics are conditional (only when changed by requirement/solution).

## Commands (when in subagent mode)

Before drafting each stage, get context; after writing the doc, commit the stage. Use explicit `--name <name>` (from `spec/.active` or user).

```bash
python scripts/spec_agent.py subagent-context --name <name> --stage <stage> --json-output
# ... then write target doc ...
python scripts/spec_agent.py subagent-stage --name <name> --stage <stage> --status completed --agent <stage-agent>
```

Full subcommand contract: see AGENTS.md “Command contract”.
## Output

- `01-analysis.md`, `02-prd.md`, `03-tech.md`, `04-acceptance.md`, `00-clarifications.md` under the active requirement path.


## Guardrails

- Do not use `write-all` / `write-analysis` / `write-prd` / `write-tech` / `write-acceptance`.

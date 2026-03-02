# 快速开始（Cursor / Claude Code）

在 AI IDE 中直接使用 spec-agent 的步骤与常见场景。

> **规范与契约的唯一来源**：工作流、命令契约、路径与 init/task 边界等以 **AGENTS.md** 为准。本文档仅做入门与示例，不重复定义契约；详见 AGENTS.md § Documentation source hierarchy、§ Command contract、§ Entry decision (init vs task)。

## 在 AI IDE 中使用

### spec-agent-init 使用示例

`spec-agent-init` 用于**初始化项目**的 spec 目录，路径固定为 `spec/0000-00-00/project-spec/`。

- **首次初始化**：`/spec-agent-init 请初始化项目 spec，并生成第一版文档。若名称和标题没给，请自动生成。`
- **再次执行**：`/spec-agent-init 请根据当前项目更新分析报告、PRD 和系统设计文档。`
空项目仅创建 spec 骨架；非空项目会生成分析报告、PRD、系统设计（01/02/03），验收与澄清为默认内容。

- `/spec-agent-chat 现在产品提了一个新需求，需求如下：……`
- 或直接：`/spec-agent-task 现在产品提了一个新需求，需求如下：……`
- 若有数据库信息，可同一句里追加（连接地址、库名、只读账号等）。
- 若要明确澄清策略场景，可说明：`这是从零新建项目` 或 `这是在现有项目上的新增需求`。
- **范围与 spec 目录**：见 AGENTS.md § Canonical workflow（仅写 spec/，不修改项目代码；spec 位于用户项目根，可设 `SPEC_AGENT_PROJECT_ROOT`）。

## 三个最常见场景（可直接复制）

### 1. 新需求（统一入口）

`/spec-agent-chat 现在有一个新需求，需求如下：……（补充目标、范围、限制、上下游、数据库信息）`

### 2. 用户补充澄清

`/spec-agent-chat 补充一下：退款失败时最多重试 3 次，超过就告警。`

### 3. 沉淀全局记忆

`/spec-agent-chat 以后所有需求默认都要记录操作人和来源IP。`

全局记忆用于**项目约定与用户/团队习惯**（如上述「默认记录操作人和来源 IP」），勿将**当前需求的范围或结论**（如「本需求只改 proto」）写入全局记忆；后者应写入澄清或需求文档。

AI 会按流程自动完成：

1. 创建本次需求对应的文档目录，并设为当前激活需求。
2. 按固定顺序生成文档：分析 → PRD → 技术方案 → 验收清单。
3. 生成/更新时使用上游文档作为输入：PRD 结合分析报告，技术方案结合分析报告和 PRD，验收清单结合分析报告、PRD、技术方案。
4. 做一致性检查，标出冲突、遗漏和不明确点。

### 文档依赖顺序（强约束）

- 顺序与规则以 **AGENTS.md § Canonical workflow** 为准（analysis → prd → tech → acceptance；上游约束、依赖签名、全局记忆与澄清、final-check 校验）。

### 实现阶段：TDD 与 RED-GREEN-REFACTOR（推荐）

文档收敛后进入开发实现时，建议采用**测试驱动开发**：以 `04-acceptance.md` 的验收项（A-xxx）为先，**先写失败测试（RED）→ 最小实现通过（GREEN）→ 在测试保持通过下重构（REFACTOR）**。插件规则 `rules/delivery.mdc` 中已约定该流程，AI 在实现阶段会按此执行。

### 用户补充澄清后如何触发更新

1. 编辑需求目录下的 `00-clarifications.md`（init 固定路径为 `spec/0000-00-00/project-spec/`，task 为 `spec/YYYY-MM-DD/<name>/`），将状态改为 `已确认`并填写「用户确认/补充」「解决方案」。
2. 发送：`/spec-agent-clarify 已确认，请更新`；严格模式：`/spec-agent-clarify 按严格模式执行，有未确认项就先报出来`。
3. 更新与闭环规则见 **AGENTS.md § Clarification policy**（实质性更新、整篇回顾、修订记录、可测试性）。

## 快速开始四步

1. 把原始需求完整告诉 AI（目标、范围、限制、上下游、数据库信息）。
2. 让 AI 按标准流程先生成首版完整文档。
3. 你根据澄清文档逐条补充确认信息。
4. 再让 AI 基于已确认澄清重生成并复检，直到问题收敛。

## 常用使用方式（AI IDE）

### 新需求启动

- **新需求、要一套完整文档**（按需求建目录、可多需求并存）→ 用 **`/spec-agent-task 需求描述…`**（日期路径 `spec/YYYY-MM-DD/<name>/`）。  
- **项目级初始化/只维护一份项目 spec**（整个项目对应一个目录）→ 用 **`/spec-agent-init …`**（固定路径 `spec/0000-00-00/project-spec/`）。  

详见 **docs/INIT-VS-TASK-DECISION-TREE.md**。init 调用时使用固定日期 `0000-00-00`；空项目仅骨架，非空项目 full init 后 AI 填写 01/02/03。

### 文档重生成

`/spec-agent-update 基于当前激活需求，重生成完整文档并做最终检查。`

### 澄清闭环

`/spec-agent-clarify 我已经补充了澄清文档，请基于已确认项更新全部文档并复检。`  
若要卡口更严格：`/spec-agent-clarify 未确认项不要跳过，先拦截并列出来。`  
澄清驱动更新时，会结合澄清重新设计整份文档、整体回顾矛盾与更优实现，需用户确认的会追加到澄清文档。

### 分析辅助

`/spec-agent-write 先扫描相关模块并补充到分析文档，再结合数据库结构做分析结论。`

### 对话式更新

`/spec-agent-chat 这个需求补充：失败重试最多 3 次，超过要告警。`  
`/spec-agent-chat 以后所有需求默认都要输出审计字段 created_by/updated_by。`

`spec-agent-chat` 会先判断是否属于 spec-agent 场景；若无关会直接返回可处理范围与示例，不执行写入或检查。若有关，会分析意图并路由到一个或多个技能（例如切换需求 + 应用澄清 + 复检）。

若当前没有激活需求（`spec/.active` 不存在或无效），`spec-agent-chat` 会先提示初始化或切换需求。

`spec-agent-chat` 会默认返回一张「状态卡片」，包括：当前需求、路由结果、本次识别（澄清/记忆或其他意图）、写入结果、文档更新（按 analysis → prd → tech → acceptance）、阶段状态（subagent current_stage / 回退阶段）、变更摘要（按文档 diff）、检查结果与下一步建议。

### 预览与机器可读输出

`/spec-agent-task 先做预览，不要落盘；确认后再正式写入。`  
若需对接外部流程，可在同一句里要求 AI 返回结构化结果（如 JSON）。脚本命令使用 `--json-output` 时，成功与失败都会输出 JSON（失败时含 `error` 且 `ok=false`）。

## 澄清文档如何填写

编辑 `00-clarifications.md` 的 `## 澄清项` 表格：

1. 把目标行 `状态` 改为 `已确认`
2. 填写 `用户确认/补充`
3. 填写 `解决方案`

建议同时补充：`优先级`、`影响范围`、`关联章节`。

注意：归属文档、状态枚举、澄清真源与镜像见 **AGENTS.md § Clarification policy** 与配置 `clarify_statuses` / `clarify_confirmed_status`。

## 目录结构示例

以下 `spec/` 位于用户项目根目录。**何时用 init 固定路径、何时用 task 日期路径**见 **AGENTS.md § Entry decision** 与 **docs/INIT-VS-TASK-DECISION-TREE.md**。

```text
<用户项目根目录>/
  spec/
    0000-00-00/          # spec-agent-init 固定日期与名称
      project-spec/
        00-clarifications.md
        00-clarifications.json
        01-analysis.md
        02-prd.md
        03-tech.md
        04-acceptance.md
        metadata.json
    YYYY-MM-DD/          # 或按日期（如 task 编排 / 脚本未指定 --date）
      <name>/
        ...
```

## 回归测试

执行顺序与说明见 **AGENTS.md § Regression policy**。示例：

```bash
python scripts/regression_smoke.py
python scripts/regression_edge_cases.py
python scripts/regression_split_skill_contract.py
```

或一键：`python scripts/regression_all.py`。

## 配置

配置文件：`scripts/spec-agent.config.json`（由插件脚本所在目录加载）。常用项：`spec_dir`（相对**用户项目根**，默认 `spec`）、`date_format`、`dry_run_default`、`default_project_mode`（`greenfield`/`existing`）、`ai_judge_command` / `ai_judge_timeout_sec`（用于语义判定）、`clarify_statuses`、`clarify_confirmed_status`、`rules_copy_allowlist`、各类 lock 超时与轮询参数。用户项目根默认为运行脚本时的当前工作目录（CWD），可通过环境变量 `SPEC_AGENT_PROJECT_ROOT` 覆盖。若要覆盖 AI 判定命令，可设置环境变量 `SPEC_AGENT_AI_JUDGE_COMMAND`。

## 故障排查

- 报错 `multiple requirements found ...`：同名需求存在多个日期目录，请改用 `--path`。
- 报错 `clarifications not closed ...`：`--strict` 模式下存在未确认澄清项，先在 `00-clarifications.md` 完成闭环。
- `inspect-db` 未探查成功：
  - 确认项目根目录是否存在临时脚本 `./.tmp_inspect_db.py`，且实现了 AGENTS.md 中约定的输入/输出契约。
  - 对 Postgres/MySQL 等库，临时脚本需自行选择并导入合适驱动（例如 `psycopg2`、`pymysql`）；缺少驱动时应在脚本返回的 `message` 中给出安装建议。
  - 无临时脚本或脚本执行失败时，analysis 的「数据库现状」块会提示“未提供 DB 探查临时脚本或脚本执行失败”，可据此排查。

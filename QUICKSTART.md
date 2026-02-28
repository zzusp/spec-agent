# 快速开始（Cursor / Claude Code）

在 AI IDE 中直接使用 spec-agent 的步骤与常见场景。

## 在 AI IDE 中使用

### spec-agent-init 使用示例

`spec-agent-init` 用于**初始化项目**的 spec 目录，路径固定为 `spec/0000-00-00/project-spec/`。

- **首次初始化**：`/spec-agent-init 请初始化项目 spec，并生成第一版文档。若名称和标题没给，请自动生成。`
- **再次执行**：`/spec-agent-init 请根据当前项目更新分析报告、PRD 和系统设计文档。`
空项目仅创建 spec 骨架；非空项目会生成分析报告、PRD、系统设计（01/02/03），验收与澄清为默认内容。

- `/spec-agent-task 现在产品提了一个新需求，需求如下：……`
- 若有数据库信息，可同一句里追加（连接地址、库名、只读账号等）。
- 若要明确澄清策略场景，可说明：`这是从零新建项目` 或 `这是在现有项目上的新增需求`。
- **注意**：所有 spec-agent 技能（如 `/spec-agent-task`、`/spec-agent-write`、`/spec-agent-clarify` 等）只生成与更新 spec 目录下的文档与状态，**不会**直接修改项目代码（如 .proto、业务代码）；仅允许为执行约定流程而使用的临时脚本（如 DB 探查用脚本），且用后删除。具体实现与代码修改应在文档收敛后、在实现阶段进行。
- **spec 目录位置**：`spec/` 创建在**用户项目工程根目录**（即运行 spec-agent 命令时的当前工作目录，即 AI IDE 中打开的工作区根目录），而不是插件/技能所在仓库的根目录。请在用户项目根目录下执行脚本（或保证 CWD 为用户项目根）；如需覆盖可使用环境变量 `SPEC_AGENT_PROJECT_ROOT`。

## 三个最常见场景（可直接复制）

### 1. 新需求

`/spec-agent-task 现在有一个新需求，需求如下：……（补充目标、范围、限制、上下游、数据库信息）`

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

- 顺序：`01-analysis.md` → `02-prd.md` → `03-tech.md` → `04-acceptance.md`
- 规则：
  - 上游文档变更后，下游文档必须同步更新
  - 不允许跳过上游直接改下游
  - 验收文档必须基于前三份文档的最新版本
  - 四份文档在新建和更新时都必须结合：全局记忆 `spec/00-global-memory.md`、已确认澄清项（以 `00-clarifications.md` 为准，`00-clarifications.json` 为镜像）
  - `prd/tech/acceptance` 必须包含依赖签名区块：`<!-- DEPENDENCY-SIGNATURE:START --> ... <!-- DEPENDENCY-SIGNATURE:END -->`，签名中记录上游文档哈希
  - `final-check` 会基于文档内容哈希检查下游是否使用上游最新内容，并校验 R→PRD→TECH→A 的链路追踪完整性

### 实现阶段：TDD 与 RED-GREEN-REFACTOR（推荐）

文档收敛后进入开发实现时，建议采用**测试驱动开发**：以 `04-acceptance.md` 的验收项（A-xxx）为先，**先写失败测试（RED）→ 最小实现通过（GREEN）→ 在测试保持通过下重构（REFACTOR）**。插件规则 `rules/delivery.mdc` 中已约定该流程，AI 在实现阶段会按此执行。

### 用户补充澄清后如何触发更新

1. 打开需求目录下的 `00-clarifications.md`（如使用 spec-agent-init 则为 `spec/0000-00-00/project-spec/00-clarifications.md`，否则为 `spec/YYYY-MM-DD/<name>/00-clarifications.md`），把确认过的问题状态改为 `已确认`，并补全「用户确认/补充」和「解决方案」。
2. 在 AI IDE 中发送：`/spec-agent-clarify 我已经补充并确认了澄清文档，请基于已确认项重新更新全部文档。` 或 `/spec-agent-clarify 已确认，请更新`。
3. 若要「有未确认项就先报出来」：`/spec-agent-clarify 按严格模式执行，有未确认项就先报出来。`

更新时 AI 会**结合澄清内容重新设计调整整份文档**（不限于改对应段落），**整体回顾**各文档前后是否矛盾、是否有更合适的实现；若发现需用户确认的内容会**追加到澄清文档**（新澄清项、状态待确认）。

## 快速开始四步

1. 把原始需求完整告诉 AI（目标、范围、限制、上下游、数据库信息）。
2. 让 AI 按标准流程先生成首版完整文档。
3. 你根据澄清文档逐条补充确认信息。
4. 再让 AI 基于已确认澄清重生成并复检，直到问题收敛。

## 常用使用方式（AI IDE）

### 新需求启动

`/spec-agent-init 这是一个新需求，请初始化并生成第一版完整文档。若名称和标题没给你，请你自动生成。`

调用时使用**固定日期** `0000-00-00`，需求目录为 `spec/0000-00-00/project-spec/`。先判断当前项目是否为空（无源码目录/代码文件）：**空项目**仅初始化 spec 目录骨架（metadata、澄清基线、激活指针）；**非空项目**会初始化完整 spec 并生成分析报告、PRD、系统设计文档（01/02/03 由 AI 根据项目内容填写），验收与澄清文档使用默认模板内容。

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

若当前没有激活需求（`spec/.active` 不存在或无效），`spec-agent-chat` 会先提示初始化或切换需求。

`spec-agent-chat` 会默认返回一张「状态卡片」，包括：当前需求、本次识别（澄清/记忆）、写入结果、文档更新（按 analysis → prd → tech → acceptance）、阶段状态（subagent current_stage / 回退阶段）、变更摘要（按文档 diff）、检查结果与下一步建议。

### 预览与机器可读输出

`/spec-agent-task 先做预览，不要落盘；确认后再正式写入。`  
若需对接外部流程，可在同一句里要求 AI 返回结构化结果（如 JSON）。脚本命令使用 `--json-output` 时，成功与失败都会输出 JSON（失败时含 `error` 且 `ok=false`）。

## 澄清文档如何填写

编辑 `00-clarifications.md` 的 `## 澄清项` 表格：

1. 把目标行 `状态` 改为 `已确认`
2. 填写 `用户确认/补充`
3. 填写 `解决方案`

建议同时补充：`优先级`、`影响范围`、`关联章节`。

注意：

- `归属文档` 仅允许：`analysis/prd/tech/acceptance/global`
- `状态` 仅允许配置中的状态（默认 `待确认/已确认`）
- `00-clarifications.md` 是唯一真源；`00-clarifications.json` 由脚本自动同步为镜像

## 目录结构示例

以下 `spec/` 位于**用户项目工程根目录**下（即工作区根目录，非插件仓库根目录）。使用 **spec-agent-init** 时采用固定日期 `0000-00-00` 与名称 `project-spec`；使用 **spec-agent-task** 或脚本直接 init 时可为当天日期 `YYYY-MM-DD`。

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

按顺序执行：

```bash
python scripts/regression_smoke.py
python scripts/regression_edge_cases.py
python scripts/regression_split_skill_contract.py
```

或一键：`python scripts/regression_all.py`。

说明：`regression_edge_cases.py` 会临时覆盖配置用于负向测试，需顺序执行。`regression_split_skill_contract.py` 校验 `skills/` 下所有 skill 的契约完整性。

## 配置

配置文件：`scripts/spec-agent.config.json`（由插件脚本所在目录加载）。常用项：`spec_dir`（相对**用户项目根**，默认 `spec`）、`date_format`、`dry_run_default`、`default_project_mode`（`greenfield`/`existing`）、`clarify_statuses`、`clarify_confirmed_status`、`rules_copy_allowlist`、各类 lock 超时与轮询参数。用户项目根默认为运行脚本时的当前工作目录（CWD），可通过环境变量 `SPEC_AGENT_PROJECT_ROOT` 覆盖。

## 故障排查

- 报错 `multiple requirements found ...`：同名需求存在多个日期目录，请改用 `--path`。
- 报错 `clarifications not closed ...`：`--strict` 模式下存在未确认澄清项，先在 `00-clarifications.md` 完成闭环。
- `inspect-db` 未探查成功：
  - 确认项目根目录是否存在临时脚本 `./.tmp_inspect_db.py`，且实现了 AGENTS.md 中约定的输入/输出契约。
  - 对 Postgres/MySQL 等库，临时脚本需自行选择并导入合适驱动（例如 `psycopg2`、`pymysql`）；缺少驱动时应在脚本返回的 `message` 中给出安装建议。
  - 无临时脚本或脚本执行失败时，analysis 的「数据库现状」块会提示“未提供 DB 探查临时脚本或脚本执行失败”，可据此排查。

# spec-agent

`spec-agent` 用于把原始需求转成一套可持续迭代的需求文档，并通过澄清闭环持续更新：

- `01-analysis.md`（分析报告）
- `02-prd.md`（PRD）
- `03-tech.md`（技术方案）
- `04-acceptance.md`（验收清单）
- `00-clarifications.md/.json`（澄清文档）

文档默认生成在：

- `spec/YYYY-MM-DD/<requirement_name>/`

## 默认工作模式（split-only）

当前仅使用 `skills-split/` 技能体系。
根目录旧主技能入口（`SKILL.md`、`agents/openai.yaml`）已移除，这是有意的架构收敛。

核心入口：
- `spec-agent-task`：统一编排入口（AI IDE 推荐直接调用）

子技能：
- `spec-agent-init`：初始化需求状态
- `spec-agent-write`：调用端 AI 直接撰写 4 份文档
- `spec-agent-update`：调用端 AI 做通用文档重写
- `spec-agent-clarify`：基于已确认澄清重写文档
- `spec-agent-check`：执行质量门禁检查
- `spec-agent-memory`：记录跨需求通用规则
- `spec-agent-switch`：切换当前激活需求
- `spec-agent-chat`：在 AI IDE 对话中自动识别“澄清/记忆”，记录并联动更新文档

共享状态：

- `spec/YYYY-MM-DD/<requirement_name>/`
- `spec/.active`
- `spec/00-global-memory.md`

执行原则（AI-first）：
- 文档正文由调用端 AI 直接写入文件。
- 脚本主要负责状态与校验（记忆快照同步、初始化、澄清检查、最终检查）。

## 在 AI IDE 中使用（Cursor / Claude Code）

直接这样用：

- `/spec-agent-task 现在产品提了一个新需求，需求如下：……`
- 如果有数据库信息，也直接追加在同一句里（例如连接地址、库名、只读账号等）。

## 3 个最常见场景（可直接复制）

### 1. 新需求

`/spec-agent-task 现在有一个新需求，需求如下：……（补充目标、范围、限制、上下游、数据库信息）`

### 2. 用户补充澄清

`/spec-agent-chat 补充一下：退款失败时最多重试 3 次，超过就告警。`

### 3. 沉淀全局记忆

`/spec-agent-chat 以后所有需求默认都要记录操作人和来源IP。`

AI 会按流程自动做这几件事：

1. 先创建这次需求对应的文档目录，并设置为当前激活需求。
2. 再按固定顺序生成文档：分析 -> PRD -> 技术方案 -> 验收清单。
3. 生成/更新时必须使用上游文档作为输入：
   - PRD 必须结合分析报告
   - 技术方案必须结合分析报告和 PRD
   - 验收清单必须结合分析报告、PRD、技术方案
4. 最后做一致性检查，标出冲突、遗漏和不明确点。

### 文档依赖顺序（强约束）

- 顺序：`01-analysis.md` -> `02-prd.md` -> `03-tech.md` -> `04-acceptance.md`
- 规则：
  - 上游文档变更后，下游文档必须同步更新
  - 不允许跳过上游直接改下游
  - 验收文档必须基于前三份文档的最新版本
  - 四份文档在新建和更新时，都必须结合：
    - 全局记忆文档 `spec/00-global-memory.md`
    - 已确认澄清项 `00-clarifications.md/.json`
  - `prd/tech/acceptance` 必须包含依赖签名区块：
    - `<!-- DEPENDENCY-SIGNATURE:START --> ... <!-- DEPENDENCY-SIGNATURE:END -->`
    - 签名中记录其上游文档哈希（例如 `analysis/prd/tech`）
  - `final-check` 会基于文档内容哈希（记录在 `metadata.json` 的 `doc_dependency_state`）检查下游是否使用了上游最新内容

### 用户补充澄清后如何触发更新

1. 打开 `spec/YYYY-MM-DD/<name>/00-clarifications.md`，把确认过的问题状态改成 `已确认`，并补全“用户确认/补充”和“解决方案”。
2. 回到 AI IDE，直接发送：`/spec-agent-clarify 我已经补充并确认了澄清文档，请基于已确认项重新更新全部文档。`或`/spec-agent-clarify 已确认，请更新`
3. 如果你希望“只要还有未确认项就不要更新”，直接发送：`/spec-agent-clarify 按严格模式执行，有未确认项就先报出来。`

## 快速开始

1. 把原始需求完整告诉 AI（目标、范围、限制、上下游、数据库信息）。
2. 让 AI 按标准流程先生成首版完整文档。
3. 你根据澄清文档逐条补充确认信息。
4. 再让 AI 基于已确认澄清重生成并复检，直到问题收敛。

## 常用使用方式（AI IDE）

### 新需求启动

`/spec-agent-init 这是一个新需求，请初始化并生成第一版完整文档。若名称和标题没给你，请你自动生成。`

### 文档重生成

`/spec-agent-update 基于当前激活需求，重生成完整文档并做最终检查。`

### 澄清闭环

`/spec-agent-clarify 我已经补充了澄清文档，请基于已确认项更新全部文档并复检。`  
如果你要卡口更严格：`/spec-agent-clarify 未确认项不要跳过，先拦截并列出来。`

### 分析辅助

`/spec-agent-write 先扫描相关模块并补充到分析文档，再结合数据库结构做分析结论。`

### 对话式更新

`/spec-agent-chat 这个需求补充：失败重试最多 3 次，超过要告警。`  
`/spec-agent-chat 以后所有需求默认都要输出审计字段 created_by/updated_by。`

注意：如果当前没有激活需求（`spec/.active` 不存在或无效），`spec-agent-chat` 会先提示你初始化或切换需求，再继续处理。

`spec-agent-chat` 会默认返回一张“状态卡片”，包括：
- 当前需求
- 本次识别（澄清/记忆）
- 写入结果
- 文档更新（按 analysis -> prd -> tech -> acceptance）
- 变更摘要（按文档 diff）
- 检查结果与下一步建议

### 预览与机器可读输出

`/spec-agent-task 先做预览，不要落盘；确认后再正式写入。`  
如果你需要对接外部流程，也可以直接在同一句里要求 AI 返回结构化结果（如 JSON）。

## 澄清文档如何填写

编辑 `00-clarifications.md` 的 `## 澄清项` 表格：

1. 把目标行 `状态` 改为 `已确认`
2. 填写 `用户确认/补充`
3. 填写 `解决方案`

建议同时补充：

- `优先级`
- `影响范围`
- `关联章节`

注意：

- `归属文档` 仅允许：`analysis/prd/tech/acceptance/global`
- `状态` 仅允许配置中的状态（默认 `待确认/已确认`）
- `00-clarifications.md` 与 `00-clarifications.json` 会自动同步

## 目录结构示例

```text
spec/
  2026-02-11/
    order-refund/
      00-clarifications.md
      00-clarifications.json
      01-analysis.md
      02-prd.md
      03-tech.md
      04-acceptance.md
      metadata.json
```

## 回归测试

按顺序执行：

```bash
python scripts/regression_smoke.py
python scripts/regression_edge_cases.py
python scripts/regression_split_skill_contract.py
```

或一键：

```bash
python scripts/regression_all.py
```

说明：
- `regression_edge_cases.py` 会临时覆盖配置用于负向测试，需顺序执行。
- `regression_split_skill_contract.py` 校验 `skills-split/` 下所有拆分 skill 的契约完整性。

## 配置

配置文件：`spec-agent.config.json`

常用项：

- `spec_dir`
- `date_format`
- `dry_run_default`
- `clarify_statuses`
- `clarify_confirmed_status`
- `rules_copy_allowlist`

## 故障排查

- 报错 `multiple requirements found ...`：
  - 说明同名需求存在多个日期目录，请改用 `--path`。
- 报错 `clarifications not closed ...`：
  - `--strict` 模式下存在未确认澄清项，先在 `00-clarifications.md` 完成闭环。
- `inspect-db` 未探查成功：
  - `sqlite://` 可直接探查；
  - `mysql://` 需要本地 `mysql` 客户端；
  - `postgres://`/`postgresql://` 需要本地 `psql` 客户端。

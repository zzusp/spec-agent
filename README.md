# spec-agent

`spec-agent` 用于把原始需求转成一套可持续迭代的需求文档，并通过澄清闭环持续更新：

- `01-analysis.md`（分析报告）
- `02-prd.md`（PRD）
- `03-tech.md`（技术方案）
- `04-acceptance.md`（验收清单）
- `00-clarifications.md/.json`（澄清文档）

文档默认生成在：

- `spec/YYYY-MM-DD/<requirement_name>/`

## 快速开始

1. 初始化需求

```bash
python scripts/spec_agent.py init --name order-refund --title "退款流程优化" --desc "用户可发起退款申请，支持审核与回退"
```

2. 一键生成全部文档

```bash
python scripts/spec_agent.py write-all --name order-refund
```

3. 用户补充澄清后更新文档

```bash
python scripts/spec_agent.py update --name order-refund
```

4. 最终检查

```bash
python scripts/spec_agent.py final-check --name order-refund
```

## 在 AI IDE 中使用（Cursor / Claude Code）

建议把下面整段直接粘贴给 AI：

```text
现在产品提了一个新需求，请你使用 spec-agent 的标准流程处理这个需求。
需求如下：xxxxxxx
数据库连接信息：xxxxxx
```

对应命令通常是：

```bash
# 未提供 --name/--title 时会自动生成需求英文名和标题
python scripts/spec_agent.py init --title "退款流程优化" --desc "<raw_requirement>"
# init 会自动 set-active，后续可直接执行
python scripts/spec_agent.py write-all
python scripts/spec_agent.py final-check
```

### 用户补充澄清后如何触发更新

1. 在 `spec/YYYY-MM-DD/<name>/00-clarifications.md` 中把目标项改为 `已确认`，并填写 `用户确认/补充` 与 `解决方案`。
2. 让 AI 执行更新：

```text
我已经补充并确认了 00-clarifications.md，请基于已确认澄清执行 update。
```

3. 对应命令：

```bash
python scripts/spec_agent.py update --name <name>
```

4. 若你希望“有未确认项就阻断更新”，使用严格模式：

```bash
python scripts/spec_agent.py update --name <name> --strict
```

## 常用命令

### 初始化与切换

```bash
# 文本初始化（--name/--title 可选；缺省自动生成）
python scripts/spec_agent.py init --name <name> --desc "<raw_requirement>"
python scripts/spec_agent.py init --desc "<raw_requirement>"

# JSON 字符串初始化
python scripts/spec_agent.py init --name <name> --desc-json '{"goal":"...","scope":["..."]}'

# 文件初始化（.json/.md/.txt）
python scripts/spec_agent.py init --name <name> --desc-file requirements.md

# 查看需求列表
python scripts/spec_agent.py list

# 切换 active 需求
python scripts/spec_agent.py set-active --name <name>
python scripts/spec_agent.py set-active --path spec/2026-02-11/<name>
```

### 文档生成

```bash
# 一键生成 4 份文档 + final-check
python scripts/spec_agent.py write-all --name <name>

# 分阶段生成
python scripts/spec_agent.py write-analysis --name <name>
python scripts/spec_agent.py write-prd --name <name>
python scripts/spec_agent.py write-tech --name <name>
python scripts/spec_agent.py write-acceptance --name <name>
```

### 澄清闭环

```bash
# 基于澄清更新 4 份文档（并自动 final-check）
python scripts/spec_agent.py update --name <name>

# 严格模式：存在未闭环澄清项时阻断更新
python scripts/spec_agent.py update --name <name> --strict
```

### 分析辅助

```bash
# 扫描候选模块（写入 analysis 的 scan 区块）
python scripts/spec_agent.py scan --name <name>

# 数据库 schema 探查（写入 analysis 的 db-schema 区块）
python scripts/spec_agent.py inspect-db --name <name>
```

### 预览与机器可读输出

```bash
# 预览，不落盘
python scripts/spec_agent.py write-all --name <name> --dry-run

# JSON 输出（支持放在子命令前/后）
python scripts/spec_agent.py --json-output list
python scripts/spec_agent.py list --json-output
```

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
python scripts/regression_skill_contract.py
```

或一键：

```bash
python scripts/regression_all.py
```

说明：
- `regression_edge_cases.py` 会临时覆盖配置用于负向测试，需顺序执行。
- `regression_skill_contract.py` 校验 skill 契约（`SKILL.md` frontmatter 与 `agents/openai.yaml` 关键字段）。

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

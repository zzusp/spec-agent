# spec-agent

spec-agent 是一套面向 AI IDE 的需求文档工作流：把原始需求转成可持续迭代的文档集，并通过澄清闭环持续更新。产出包括分析报告、PRD、技术方案、验收清单以及澄清文档（`00-clarifications.md` / `.json`），默认输出到 `spec/YYYY-MM-DD/<requirement_name>/`。

## 工作方式

从你在对话里提出需求开始：AI 不会只写单份文档，而是按固定顺序生成 **分析 → PRD → 技术方案 → 验收清单**，每份下游文档都基于上游内容与全局记忆、已确认澄清项编写。不明确之处会进入澄清文档，你确认后由 AI 结合澄清**重新设计整份文档**并整体回顾一致性。最终通过 `final-check` 做依赖签名与链路校验，保证 R→PRD→TECH→A 可追溯。技能由插件声明，调用端 AI 直接写文件，脚本负责状态与校验（初始化、澄清检查、最终检查、子阶段状态）。详见 [AGENTS.md](AGENTS.md)。

## Installation

**说明：** 不同平台安装方式不同。Cursor / Claude Code 等可通过插件市场或命令安装；其他环境可从本仓库路径添加插件。

### Cursor

在 Cursor Agent 对话中安装：

```text
/add-plugin spec-agent
```

或从本仓库路径添加插件。插件清单：`.cursor-plugin/plugin.json`；技能在 `skills/`，代理在 `agents/`，规则在 `rules/`。Commands 与 Hooks 见 [Plugin & Skill 开发规范符合性说明](docs/PLUGIN-AND-SKILL-COMPLIANCE.md#6-commands-与-hooks)。

### 验证安装

在新会话中发起一次应触发技能的操作（例如「有一个新需求，需求如下：……」），AI 应能调用 `spec-agent-task` 并开始生成文档。完整用法见 [QUICKSTART.md](QUICKSTART.md)。

## 基本工作流

1. **提需求** — 用 `/spec-agent-task` 把原始需求（目标、范围、限制、上下游、数据库信息等）一次性交给 AI，可附带「从零新建项目」或「现有项目上新需求」等澄清策略。
2. **首版文档** — AI 按顺序生成分析、PRD、技术方案、验收清单，并做一致性检查；不明确点写入澄清文档。
3. **补充澄清** — 你在 `00-clarifications.md` 中把项标为「已确认」并填写确认内容与方案，再用 `/spec-agent-clarify` 让 AI 基于已确认项重写全部文档并复检。
4. **收敛** — 重复「补充澄清 → clarify」直到检查通过，需求文档集即可作为交付与开发依据。
5. **实现阶段**（推荐）— 开发时按 `04-acceptance.md` 的验收项采用 TDD（RED-GREEN-REFACTOR），见 [QUICKSTART.md](QUICKSTART.md) 与 `rules/delivery.mdc`。

更细的步骤、常用命令与故障排查见 [QUICKSTART.md](QUICKSTART.md)。

## What's Inside

### Skills

| Skill | Description |
|:------|:------------|
| `spec-agent-task` | 统一编排入口：从原始需求到完整文档集，含阶段子代理与澄清闭环 |
| `spec-agent-init` | 初始化需求工作区状态（目录、metadata、激活指针） |
| `spec-agent-write` | 由调用端 AI 直接撰写 analysis / PRD / tech / acceptance 四份文档 |
| `spec-agent-update` | 通用文档重写（非澄清专项） |
| `spec-agent-clarify` | 基于已确认澄清项重写文档：结合澄清重新设计整份文档、整体回顾矛盾与更优实现，需用户确认的追加到澄清；多轮收敛 |
| `spec-agent-check` | 执行 final-check 质量门禁与一致性检查 |
| `spec-agent-memory` | 维护跨需求全局记忆 `spec/00-global-memory.md` |
| `spec-agent-switch` | 切换当前激活需求（多需求场景） |
| `spec-agent-chat` | 对话中识别澄清/记忆，写入并联动更新文档（结合澄清重设计整份文档、整体回顾，需用户确认的追加到澄清）与阶段状态 |

### Agents

| Agent | Description |
|:------|:------------|
| `spec-agent-orchestrator` | 编排端到端流程：project_mode、阶段顺序、subagent-context 交接、final_check 与自动回退映射 |

### Rules

| Rule | Description |
|:-----|:------------|
| `delivery.mdc` | 项目/功能完整交付闭环与验收强制流程 |
| `coding.mdc` | 代码复用、文件约束、注释与问题修复原则 |
| `spec-agent.mdc` | 使用 spec-agent 时的文档顺序、修订记录、澄清真源与多需求约定 |

## 理念 / Philosophy

- **Test-Driven Development** — Write tests first, always.（测试先行，始终如此。）
- **Systematic over ad-hoc** — Process over guessing.（流程优先于猜测。）
- **Complexity reduction** — Simplicity as primary goal.（以简单为首要目标。）
- **Evidence over claims** — Verify before declaring success.（先验证再宣布成功。）

## 设计原则

- **文档顺序强约束** — 分析 → PRD → 技术方案 → 验收清单；下游必须基于上游与澄清、全局记忆更新。
- **澄清即真源** — 以 `00-clarifications.md` 为准，确认后驱动整份文档重设计而非局部修补。
- **证据优先** — 交付与验收以可验证结果为准；final-check 做依赖签名与链路追踪，避免遗漏与不一致。

## 更多

- **快速开始（Cursor / Claude Code）**：[QUICKSTART.md](QUICKSTART.md)
- **工作流与命令约定**：[AGENTS.md](AGENTS.md)
- **目录结构、回归测试、配置与故障排查**：[QUICKSTART.md](QUICKSTART.md) 及仓库内 `scripts/spec-agent.config.json`、`scripts/spec_agent.py`

## License

MIT

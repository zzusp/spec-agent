# Plugin & Skill 开发规范符合性说明

本文档说明当前项目与 Cursor Plugin / Skill 规范的对应关系，以及脚本使用、Skill 触发方式的约定。

> **规范与契约的唯一来源**：命令契约、路径策略、init vs task 边界等以 **AGENTS.md** 为准。本文档为符合性说明与 rationale，不重新定义契约；具体子命令、参数、init/task 决策见 AGENTS.md 与 `docs/INIT-VS-TASK-DECISION-TREE.md`。

## 1. Plugin 清单 (plugin.json)

- **规范**：符合 [plugin.schema.json](https://github.com/cursor/plugins/blob/main/schemas/plugin.schema.json)。`name` 为 kebab-case；`skills`、`agents`、`rules` 为相对路径。
- **当前**：`.cursor-plugin/plugin.json` 提供 `name`、`displayName`、`version`、`description`、`skills`（`./skills/`）、`agents`（`./agents/`）、`rules`（`./rules/`）、`commands`（`./commands/`）、`hooks`（`./hooks/hooks.json`）。未使用 `mcpServers`。
- **结论**：符合规范。技能、规则、命令与钩子通过清单声明，由 Cursor 从插件根目录解析。

## 2. Skill 触发方式

- **规范**：Skill 由用户在 AI IDE 中通过 **斜杠命令** 触发，格式为 `/skill-name [参数或自然语言]`。Skill 名称与 `skills/<name>/SKILL.md` 的 frontmatter `name` 一致时，会注册为对应斜杠命令。
- **当前**：
  - 用户触发：`/spec-agent-task ...`、`/spec-agent-init ...`、`/spec-agent-clarify ...`、`/spec-agent-chat ...` 等，与 9 个 skill 的 `name`（如 `spec-agent-task`）一一对应。
  - **统一对话入口**：`spec-agent-chat` 作为会话入口时，先做“是否属于 spec-agent 场景”判定；若属于则按意图路由到一个或多个技能（也可在 chat 内走本地 clarification/memory 流程）。
  - **双注册（斜杠可靠触发）**：为避免“指定调用但不触发”，每个 spec-agent 技能除在 `skills/` 下定义外，在 `commands/` 下均有**同名** command 文件（如 `commands/spec-agent-task.md`）。Cursor 会从 `commands/` 发现并注册斜杠命令，用户输入 `/spec-agent-xxx` 时优先命中该 command，command 正文要求 AI 按对应 `skills/spec-agent-xxx/SKILL.md` 执行，从而保证斜杠一定触发预期技能。
  - 各 skill 的 frontmatter 已设置 `disable-model-invocation: true`，技能**仅**在用户显式输入 `/spec-agent-xxx`（或执行同名 command）时加入上下文，不参与“Agent Decides”自动匹配，避免误触发或与 command 双入口歧义。
  - 子技能/编排：`spec-agent-task` 中列出的 “Child skills” 为**逻辑分组**，不表示 Cursor 自动链式调用。编排由**调用端 AI** 在单次 `/spec-agent-task` 会话中按 SKILL.md 的 Execution sequence 执行脚本与写文档完成，而非多次发起 `/spec-agent-init`、`/spec-agent-write` 等斜杠命令。
- **结论**：符合规范。每个 skill 对应一个用户可用的斜杠命令；通过 command 同名双注册与 `disable-model-invocation` 保证斜杠调用稳定触发；编排在 task 内通过文档与脚本约定完成。

## 3. 脚本使用方式

- **规范**：Plugin 可依赖“由 AI 在遵循 Skill 说明时执行的命令”。官方示例（如 cursor-team-kit）多使用系统 CLI（如 `gh`、`git`）；也可使用插件自带的脚本，由 Skill 文档约定调用方式。
- **当前**：
  - 唯一入口脚本：`scripts/spec_agent.py`，从**用户项目根目录**执行（当前工作目录 CWD，即 AI IDE 工作区根目录；可用 `SPEC_AGENT_PROJECT_ROOT` 覆盖）。
  - 调用形式：`python scripts/spec_agent.py <subcommand> [--name <name>] [其他参数]`。所有子命令与入参以 `AGENTS.md` 的 “Command contract” 为**单一事实来源**。
  - 各 Skill 仅描述**何时**、**何种顺序**调用哪些子命令；具体子命令名、参数以 AGENTS.md 及技能内 “Run”/“Commands” 为准。
- **结论**：符合规范。脚本作为“状态与质量门禁”工具，由 AI 按技能说明在正确时机执行；同时通过 plugin 的 **Commands** 暴露常用子命令，便于 Agent/用户发现与执行。

## 4. 脚本运行时配置（scripts/spec-agent.config.json）

- **作用**：`scripts/spec-agent.config.json` 是**脚本运行时配置**，仅被 `scripts/spec_agent.py`（及引擎 `spec_agent_engine_core.py`）在启动时加载，与 Cursor 的 `.cursor-plugin/plugin.json` **无隶属关系**。Plugin 清单描述“插件有哪些 skills/agents/rules/commands/hooks”；该文件描述“脚本执行时的行为参数”（目录、澄清表结构、锁超时、默认 project_mode 等）。配置与脚本同目录，便于维护。
- **规范符合性**：Cursor Plugin / Skill 规范**未定义**也**未禁止**“插件自有的配置文件”。官方只约定 manifest、rules、skills、agents、commands、hooks、mcpServers；脚本如何读配置是实现细节。当前做法（`scripts/` 下独立 JSON、脚本单源加载）符合规范，且职责清晰：Plugin 资源由 Cursor 解析，运行时参数由脚本解析。
- **主要配置项**：`spec_dir`、`date_format`、`clarify_columns` / `clarify_statuses` / `clarify_confirmed_status`、`dry_run_default`、`default_project_mode`、`ai_judge_command` / `ai_judge_timeout_sec`、`metadata_lock_*` / `requirement_lock_*` 等；详见 `scripts/spec_agent_engine_core.py` 内 `DEFAULT_CONFIG` 与 `validate_config`。如需定制行为，直接编辑该 JSON；Skills 仅描述“何时调用哪些子命令”，不覆盖这些键。
- **结论**：保持现有实现即可；无需把配置迁入 plugin.json（schema 无对应字段，且会混淆“给 Cursor 用的清单”与“给脚本用的参数”）。若需在文档中集中说明可配置项，可在 README 或本文档中增加配置说明表或链接到引擎默认值。

## 5. Skill 间关系与引用

- **规范**：Skill 之间可通过“在文档中指名另一个 skill”建立引用，由 AI 理解并协调行为；不需要也不依赖 Cursor 提供“程序化链式调用”能力。
- **当前**：
  - **spec-agent-chat** 可引用并路由到其他技能（如 task/init/switch/write/clarify/update/check/memory），属于文档级编排约定；由同一会话内 AI 按路由顺序执行，不依赖 Cursor 程序化链式调用。
  - **spec-agent-task** 列出 Child skills（spec-agent-memory、spec-agent-switch、spec-agent-init 等），表示编排时会用到这些能力，由同一会话内的 AI 按 task 的 Execution sequence 执行（脚本 + 写文件），而非再触发其他斜杠命令。
  - **spec-agent-write**、**spec-agent-clarify** 等引用“按 spec-agent-clarify 的 candidate question policy”等，为**策略/契约引用**，不涉及运行时触发其他 skill。
  - 建议下一步（如 spec-agent-switch 的 Output）：用“建议用户使用 `/spec-agent-write` 或 `/spec-agent-check`”等表述，明确**用户**可主动发起的下一跳斜杠命令。
- **结论**：符合规范。Skill 间为文档级引用与编排约定，触发始终为用户发起的斜杠命令或用户按建议发起另一条斜杠命令。

## 6. Commands 与 Hooks

### Commands（Agent 可执行命令）

- **规范**：Plugin 可将“可由 Agent 执行的命令”放在 `commands/` 目录，每文件为 `.md`/`.mdc`/`.txt`，含 frontmatter `name`、`description` 及正文步骤；Cursor 会做组件发现并供 Agent/用户发现与执行。
- **当前**：`commands/` 下提供两类命令：
  - **脚本子命令（6 个）**：对应 `spec_agent.py` 常用子命令，供直接执行或由技能内引用。子命令契约与 init/task 边界以 **AGENTS.md § Command contract**、§ Entry decision 及 **docs/INIT-VS-TASK-DECISION-TREE.md** 为准；init 固定路径与空/非空分支见 `skills/spec-agent-init/SKILL.md`。
    - `spec-final-check`：对当前/指定需求做终检
    - `spec-check-clarifications`：检查待确认澄清数量（可 `--strict` 作门禁）
    - `spec-set-active`：设置当前活跃需求
    - `spec-sync-memory`：将全局记忆同步到需求元数据
    - `spec-list`：列出需求目录
  - **技能同名命令（9 个）**：与 `skills/` 下各技能同名（如 `spec-agent-task`、`spec-agent-chat` 等），用于保证用户输入 `/spec-agent-xxx` 时稳定触发对应技能；命令正文要求 AI 按 `skills/spec-agent-xxx/SKILL.md` 执行。
- **使用**：在 IDE/CLI/Cloud 中，Agent 或用户可通过插件暴露的 Command 名称执行上述操作；脚本类命令应在用户项目根目录执行 `python scripts/spec_agent.py <subcommand> ...`（或设置 `SPEC_AGENT_PROJECT_ROOT`），完整契约以 AGENTS.md 为准。

### Hooks（事件触发自动化）

- **规范**：在 `hooks/hooks.json` 中配置事件名与要执行的 `command`（脚本或命令行）；支持事件包括 `afterFileEdit`、`beforeShellExecution`、`sessionEnd` 等。
- **当前**：`hooks/hooks.json` 中配置了可选 `sessionEnd` 钩子，在会话结束时执行 `python scripts/spec_agent.py list`（只读，用于提醒或日志）。项目可按需增删或改为 `afterFileEdit`（如编辑 `spec/**` 后执行 `sync-memory`）、`sessionEnd` 执行 `final-check` 等；脚本路径相对于插件根目录。

## 7. 建议与可选改进

| 项目 | 说明 |
|------|------|
| **脚本路径** | 当前统一写 `python scripts/spec_agent.py`。若需兼容仅提供 `python3` 的环境，可在 README 或 AGENTS 中说明“可用 `python3` 替代 `python`”。 |
| **Skill 内脚本可见性** | 凡依赖 `spec_agent.py` 子命令的 skill，应在该 skill 内或通过引用 AGENTS 明确写出完整调用示例（如 “Run”/“Commands” 小节），以便单独触发该 skill 时 AI 也能正确执行。已对 spec-agent-write 补充 “Commands” 示例。 |
| **Hooks 定制** | 若需在编辑 `spec/` 下文件后自动同步记忆，可在 `hooks/hooks.json` 的 `afterFileEdit` 中加入 `command: python scripts/spec_agent.py sync-memory`（注意可能频繁执行）；或仅在 `sessionEnd` 运行轻量只读命令。 |

## 8. 总结

- **Plugin 清单**：符合 Cursor Plugin 规范；skills/agents/rules/commands/hooks 路径与官方约定一致。
- **Skill 触发**：以用户斜杠命令 `/spec-agent-<name>` 触发；`spec-agent-chat` 可作为统一对话入口先做场景判定与多技能路由，`spec-agent-task` 继续负责全量文档生成编排，不依赖多 skill 程序化链式调用。
- **脚本与 Commands**：以 `scripts/spec_agent.py` 为唯一入口；子命令契约以 AGENTS.md 为准；常用子命令已通过 `commands/` 暴露为 Plugin Commands，便于发现与执行。
- **Hooks**：通过 `hooks/hooks.json` 提供可选事件钩子（如 sessionEnd 列出需求），可按项目需要调整或扩展。
- **脚本运行时配置**：`scripts/spec-agent.config.json` 仅供脚本使用，与 plugin.json 分离，符合规范。
- **Skill 间关系**：通过文档引用与“建议下一步”的斜杠命令表述即可，当前实现符合规范。

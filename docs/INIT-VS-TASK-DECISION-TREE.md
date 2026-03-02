# Init vs Task 决策树

本文档说明何时使用 `/spec-agent-chat`、`/spec-agent-task`、`/spec-agent-init`，以及对应的路径策略，减少误用。规范摘要以 **AGENTS.md § Entry decision (init vs task)** 为准。

## 一句话对照

| 入口 | 用途 | 路径策略 |
|------|------|----------|
| `/spec-agent-chat <message>` | 统一对话入口：新需求、澄清、记忆、复检等，先判定再路由 | 由路由到的技能决定（多为 task 的日期路径或 init 的固定路径） |
| `/spec-agent-task <raw_requirement>` | **新需求交付**：单次从零生成 analysis→PRD→tech→acceptance，迭代文档 | **日期路径** `spec/YYYY-MM-DD/<name>/` |
| `/spec-agent-init <message>` | **项目级初始化/刷新**：为整个项目建立或更新 spec 基线 | **固定路径** `spec/0000-00-00/project-spec/` |

## 决策顺序（优先用上一条）

1. **先看是否只是对话/澄清/记忆**
   - 用户说“补充澄清”“记一下团队习惯”“做一次复检”等 → 用 **`/spec-agent-chat`**，由 chat 路由到 clarify/memory/check 等，无需选 init 或 task。

2. **再看是否“新需求、要一套完整文档”**
   - 用户给出一段新需求描述并期望得到一整套分析/PRD/技术方案/验收 → 用 **`/spec-agent-task <raw_requirement>`**。
   - 路径为 **日期**：`spec/YYYY-MM-DD/<name>/`（每次新需求通常新日期或新 name）。

3. **最后看是否“项目级初始化/只维护一个项目 spec”**
   - 用户要“初始化项目 spec”“把当前项目当整体建一份 spec”“更新项目级分析/PRD/系统设计” → 用 **`/spec-agent-init <message>`**。
   - 路径为 **固定**：`spec/0000-00-00/project-spec/`（空项目仅骨架，非空项目 full init 后 AI 填写 01/02/03）。

## 路径策略对比

- **init（固定）**  
  - 始终 `--date 0000-00-00`、`--name project-spec` → `spec/0000-00-00/project-spec/`。  
  - 重复执行 init 不会新建目录，只更新同一目录；适合“整个项目对应一份 spec”的场景。

- **task（日期）**  
  - 使用 `YYYY-MM-DD` 与 `name` → `spec/YYYY-MM-DD/<name>/`。  
  - 每个新需求一条目录，适合多需求、多迭代、按需求追溯。

## 正确用法示例

- “有一个新需求：登录超时改为 30 秒” → **`/spec-agent-task`**（新需求交付，走日期路径）。
- “请初始化这个项目的 spec，并生成第一版分析/PRD/系统设计” → **`/spec-agent-init`**（项目级，固定路径）。
- “补充一下：退款失败最多重试 3 次” → **`/spec-agent-chat`**（澄清/补充，由 chat 路由）。
- “以后所有需求默认记录操作人和来源 IP” → **`/spec-agent-chat`**（全局记忆，由 chat 路由）。

## 反例（避免误用）

- **不要**对每个新需求都用 `/spec-agent-init`：init 是项目级、固定路径，用于“整个项目一份 spec”，不是“每个需求一条目录”。
- **不要**用 `/spec-agent-task` 去做“只刷新当前项目一份 spec”：若目标是项目级基线，应用 `/spec-agent-init` 在 `spec/0000-00-00/project-spec/` 更新。
- **不要**在未确定“项目级 vs 新需求”时混用：先按上面决策顺序选 chat → task 或 init，再执行；路径一旦选错会导致需求进错目录。

## 参考

- **AGENTS.md** § Entry decision (init vs task)、§ Canonical workflow、§ Command contract
- **skills/spec-agent-init/SKILL.md**：init 的固定日期/路径与空/非空分支
- **skills/spec-agent-task/SKILL.md**：task 的编排与日期路径

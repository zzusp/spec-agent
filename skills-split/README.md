# skills-split

Split-skill prototype for the same `spec-agent` workspace.

Default mode in this folder is AI-first:
- caller AI writes document content directly
- scripts are used for state operations and quality gates
- stage-based subagent orchestration is supported via `subagent-init/context/stage/status`
  - `subagent-context` includes fixed handoff fields: `target_sections` / `must_keep_sections` / `reopen_reason`
  - `subagent-context` also includes clarification routing fields: `project_mode` / `clarification_focus`
  - `subagent-status` is read-only by default; use `--normalize` to persist stale->pending updates
  - `subagent-stage --stage final_check --status failed` auto-maps reopen stage from check issues
- every split skill must read `spec/00-global-memory.md` before execution
- clarification candidates must follow prioritized, answer-constrained policy in `spec-agent-clarify`
- clarification loop uses round-based closure with per-round cap: at most 10 new candidates

## Skills

- `spec-agent-init`
- `spec-agent-write`
- `spec-agent-update`
- `spec-agent-clarify`
- `spec-agent-check`
- `spec-agent-task`
- `spec-agent-memory`
- `spec-agent-switch`
- `spec-agent-chat`

## AI IDE invocation examples

- `/spec-agent-task 现在产品提了一个新需求，需求如下：……`
- `/spec-agent-init 初始化一个新需求并自动生成名称和标题`
- `/spec-agent-write 为当前激活需求生成完整文档`
- `/spec-agent-clarify 我已经确认了澄清项，请基于已确认项更新文档`
- `/spec-agent-update 基于当前激活需求重新生成文档`
- `/spec-agent-check 对当前激活需求做最终一致性检查`
- `/spec-agent-memory 记录一条跨需求通用规则：……`
- `/spec-agent-switch 切换到需求 order-refund`
- `/spec-agent-chat 用户补充：导出接口必须记录操作人和来源IP`

`spec-agent-chat` 默认会返回状态卡片：
- 当前需求
- 本次识别（澄清/记忆）
- 写入结果
- 文档更新
- 阶段状态（subagent current_stage / reopen）
- 变更摘要（按文档 diff）
- 检查结果

## Shared workspace contract

- Requirement docs: `spec/YYYY-MM-DD/<requirement_name>/`
- Active pointer: `spec/.active`
- Global memory: `spec/00-global-memory.md`

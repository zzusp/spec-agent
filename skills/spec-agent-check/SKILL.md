---
name: spec-agent-check
description: Run quality gates and consistency checks for AI-written spec documents. Use when docs are drafted/updated and must be validated before acceptance.
---

# Spec agent check

## Trigger

Use when docs are drafted or updated and must be validated before acceptance (quality gates and consistency checks).

## Workflow

1. Read `spec/00-global-memory.md` and validate docs against structural gates and memory constraints.
2. Run `final-check` for the active (or named) requirement.
3. Append only clarification-relevant issues to clarifications; fix doc-quality issues in docs directly. In subagent mode, commit final_check stage when issues=0.

## Memory preload (must)

- Read `spec/00-global-memory.md` before running checks.
- Validate documents not only for structural quality gates but also for consistency with global memory constraints.

## Run

```bash
python scripts/spec_agent.py final-check --name <name>
```

or rely on active requirement:
```bash
python scripts/spec_agent.py final-check
```

## Behavior

- Detect missing required docs.
- Validate placeholders, structure, and R-xx consistency.
- 对验收文档（04-acceptance.md）：final-check 通过后，建议确认每条验收项满足可测试性（验收步骤可执行、通过标准可断言），便于实现阶段 TDD；详见 `spec-agent-write`「04-acceptance.md 可测试性要求」。
- Convergence-first writeback:
  - append only clarification-relevant issues (need user decision) into clarifications.
  - for pure doc-quality issues, report and fix in docs directly; do not expand clarification list.
- In subagent mode, after `issues=0`, commit stage state:
```bash
python scripts/spec_agent.py subagent-stage --name <name> --stage final_check --status completed --agent final-check-agent
```

## Output

- Final-check result (issues count, clarification-relevant writeback if any); optional stage commit when issues=0.

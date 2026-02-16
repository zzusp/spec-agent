---
name: spec-agent-check
description: Run quality gates and consistency checks for AI-written spec documents. Use when docs are drafted/updated and must be validated before acceptance.
---

# spec-agent-check

Use this skill for validation only.

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
- Convergence-first writeback:
  - append only clarification-relevant issues (need user decision) into clarifications.
  - for pure doc-quality issues, report and fix in docs directly; do not expand clarification list.
- In subagent mode, after `issues=0`, commit stage state:
```bash
python scripts/spec_agent.py subagent-stage --name <name> --stage final_check --status completed --agent final-check-agent
```

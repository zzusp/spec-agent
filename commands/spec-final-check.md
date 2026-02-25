---
name: spec-final-check
description: Run quality and consistency check on the active (or named) requirement docs. Use before considering docs done or after updates.
---

# Spec final-check

Run final-check on requirement docs. Run from repository root.

## Steps

1. Run for active requirement:
```bash
python scripts/spec_agent.py final-check
```
2. Or for a named requirement:
```bash
python scripts/spec_agent.py final-check --name <name>
```
3. Add `--dry-run` to report issues without writing clarification-relevant items to `00-clarifications.*`. Use `--json-output` for machine-readable result.

## Output

- Issue count and report; clarification-relevant issues may be appended to `00-clarifications.md/.json`. See AGENTS.md Command contract.

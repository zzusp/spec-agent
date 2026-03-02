---
name: spec-check-clarifications
description: Check unresolved clarification count. Use with --strict to fail when any pending items exist (gate before clarify-driven update).
---

# Spec check-clarifications

Check clarification status. Run from user project root (CWD or `SPEC_AGENT_PROJECT_ROOT`).

## Steps

1. Run for active requirement:
```bash
python scripts/spec_agent.py check-clarifications [--strict] [--json-output]
```
2. Or for a named requirement:
```bash
python scripts/spec_agent.py check-clarifications --name <name> [--strict] [--json-output]
```
3. With `--strict`, exit non-zero when there are pending (unconfirmed) items. Use before running clarify-driven doc updates.

## Output

- Pending count and optional list; JSON when `--json-output`. See AGENTS.md Command contract.

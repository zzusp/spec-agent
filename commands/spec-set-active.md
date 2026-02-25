---
name: spec-set-active
description: Set the active requirement by name or path. Use when switching context in multi-requirement workflows.
---

# Spec set-active

Set active requirement. Run from repository root.

## Steps

1. By name:
```bash
python scripts/spec_agent.py set-active --name <name>
```
2. By path:
```bash
python scripts/spec_agent.py set-active --path spec/YYYY-MM-DD/<name>
```
3. Confirm active path (e.g. via `list` or next command). See AGENTS.md Command contract.

## Output

- Updates `spec/.active`; subsequent commands without `--name`/`--path` use this requirement.

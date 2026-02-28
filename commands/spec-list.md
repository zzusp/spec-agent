---
name: spec-list
description: List requirements (by date directory). Use to discover requirement names or paths.
---

# Spec list

List requirements. Run from repository root.

## Steps

1. Run:
```bash
python scripts/spec_agent.py list
```
2. Use output to choose `--name` or `--path` for other commands. See AGENTS.md Command contract.

## Output

- List of requirement paths (e.g. `spec/YYYY-MM-DD/<name>`). No side effects.

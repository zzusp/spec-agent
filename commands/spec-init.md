---
name: spec-init
description: Initialize a requirement workspace (directory, metadata, active pointer). Use when starting a new requirement or need state-only skeleton.
---

# Spec init

Initialize requirement workspace. Run from repository root.

## Steps

1. Resolve requirement name/title and optional project_mode (greenfield/existing) from user or context.
2. Run:
```bash
python scripts/spec_agent.py init --name <name> --title "<title>" --desc "<raw_requirement>" --state-only [--project-mode <greenfield|existing>]
```
3. If `--date` is needed, add `--date YYYY-MM-DD`. For full options see AGENTS.md Command contract.

## Output

- Requirement directory at `spec/YYYY-MM-DD/<name>/` with metadata and clarification baseline; `spec/.active` set.

---
name: spec-agent-init
description: Initialize the project's spec directory (fixed date 0000-00-00, name project-spec). Empty project → state-only; non-empty → full init then fill 01/02/03.
---

# Spec agent init (slash command)

This command invokes the **spec-agent-init** skill. Follow the full instructions in the skill: `skills/spec-agent-init/SKILL.md`.

- Use fixed date `--date 0000-00-00` and `--name project-spec`. If `spec/0000-00-00/project-spec/` already exists, skip init and proceed to update docs as needed.
- Run from user project root; see AGENTS.md for command contract.

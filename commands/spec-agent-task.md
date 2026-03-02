---
name: spec-agent-task
description: Full-spec delivery skill. Run when user invokes /spec-agent-task with requirement text; produces analysis, PRD, tech, acceptance.
---

# Spec agent task (slash command)

This command invokes the **spec-agent-task** skill. Follow the full instructions in the skill: `skills/spec-agent-task/SKILL.md`.

- Treat the user message (or the text after `/spec-agent-task`) as `raw_requirement`.
- Execute the skill workflow: init → analysis → prd → tech → acceptance; use scripts and child-skill logic as defined in the skill.
- When to use task vs init vs chat: see **docs/INIT-VS-TASK-DECISION-TREE.md** and AGENTS.md § Entry decision. Run from user project root; command contract in AGENTS.md.

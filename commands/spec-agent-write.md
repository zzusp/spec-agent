---
name: spec-agent-write
description: Write requirement documents (analysis, PRD, tech, acceptance) in AI-first mode. Use when workspace is initialized and docs must be drafted.
---

# Spec agent write (slash command)

This command invokes the **spec-agent-write** skill. Follow the full instructions in the skill: `skills/spec-agent-write/SKILL.md`.

- Read global memory; for each stage (analysis → prd → tech → acceptance) write target doc and run subagent-stage when in subagent mode.
- Run from user project root; see AGENTS.md for command contract.

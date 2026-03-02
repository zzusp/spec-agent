---
name: spec-agent-chat
description: Unified conversational entry for spec-agent. Detect in-scope vs out-of-scope messages, analyze intent, then route to one or multiple skills (or run local clarification/memory flow).
---

# Spec agent chat (slash command)

This command invokes the **spec-agent-chat** skill. Follow the full instructions in the skill: `skills/spec-agent-chat/SKILL.md`.

- First run scope relevance gate: if message is not spec-agent related, return out-of-scope guidance and stop.
- For in-scope messages, analyze user intent and expected outcome, then route to one or multiple skills in order.
- For conversational supplements, classify as clarification or memory, write, then run chat-local post-save update loop per skill.
- Run from user project root; see AGENTS.md for command contract.

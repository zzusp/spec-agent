---
name: spec-sync-memory
description: Sync global memory snapshot to the active (or named) requirement metadata. Use after editing spec/00-global-memory.md.
---

# Spec sync-memory

Sync global memory to requirement metadata. Run from user project root (CWD or `SPEC_AGENT_PROJECT_ROOT`).

## Steps

1. Run for active requirement:
```bash
python scripts/spec_agent.py sync-memory
```
2. Or for a named requirement:
```bash
python scripts/spec_agent.py sync-memory --name <name>
```
3. Add `--dry-run` to preview; `--json-output` for machine-readable result.

## Output

- Metadata `global_memory_hash` updated for the requirement. See AGENTS.md Command contract.

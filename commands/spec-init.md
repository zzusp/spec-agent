---
name: spec-init
description: Initialize a requirement workspace (directory, metadata, active pointer). When used by spec-agent-init skill: fixed date 0000-00-00 and name project-spec; empty → state-only; non-empty → full init then caller fills 01/02/03.
---

# Spec init

Initialize requirement workspace. Run from user project root (CWD or `SPEC_AGENT_PROJECT_ROOT`).

## spec-agent-init skill behavior

- **Fixed date and name**: Use `--date 0000-00-00` and `--name project-spec`; requirement path is `spec/0000-00-00/project-spec/`.
- **Empty project** (no source dirs like `src/`/`lib/`/`app/` or no code files): run init with `--state-only --date 0000-00-00 --name project-spec`. Output: requirement directory, metadata, clarification baseline, `spec/.active`; no 01–04 doc files.
- **Non-empty project**: run init **without** `--state-only` and with `--date 0000-00-00 --name project-spec`; then caller AI overwrites `01-analysis.md`, `02-prd.md`, `03-tech.md`; `04-acceptance.md` and clarifications stay default. If `spec/0000-00-00/project-spec/` already exists, do not run init; first run `set-active --path spec/0000-00-00/project-spec`, then work directly in that path and update 01/02/03.

## Steps

1. Resolve requirement name/title and optional project_mode (greenfield/existing) from user or context.
2. **State-only** (empty or when orchestrated by spec-agent-task). For spec-agent-init use fixed date:
```bash
python scripts/spec_agent.py init --name project-spec --title "<title>" --desc "<raw_requirement>" --state-only [--project-mode <greenfield|existing>] --date 0000-00-00
```
3. **Full init** (non-empty, standalone spec-agent-init): omit `--state-only`, use `--date 0000-00-00`, then caller fills 01/02/03:
```bash
python scripts/spec_agent.py init --name project-spec --title "<title>" --desc "<raw_requirement>" [--project-mode <greenfield|existing>] --date 0000-00-00
```
4. For other dates (e.g. script-only init by date), use `--date YYYY-MM-DD`. For full options see AGENTS.md Command contract.

## Output

- **spec-agent-init** (with `--date 0000-00-00` and `--name project-spec`): Requirement directory at `spec/0000-00-00/project-spec/`.
- **State-only**: Requirement directory with metadata and clarification baseline; `spec/.active` set.
- **Full init**: As above plus `01-analysis.md`, `02-prd.md`, `03-tech.md`, `04-acceptance.md` with default template content; caller then overwrites 01/02/03 with real content.

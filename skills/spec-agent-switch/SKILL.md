---
name: spec-agent-switch
description: Switch active requirement context in multi-requirement workflows. Use when user asks to operate on another requirement and active context may be ambiguous.
---

# Spec agent switch

## Trigger

Use when the user asks to operate on another requirement and active context may be ambiguous (multi-requirement workflows).

## Workflow

1. Resolve target by name or path; if ambiguous, ask user to disambiguate.
2. Run `set-active --name <name>` or `set-active --path ...`.
3. Reply with active name, path, and one next-step suggestion for a downstream skill.

## Memory preload (must)

- Read `spec/00-global-memory.md` before switching.
- If memory defines preferred requirement naming or environment conventions, follow them when selecting target.

## Inputs

- Preferred: explicit requirement name or full requirement path.
- Optional: reason for switching (for audit context in conversation).

## Process

1. If target is ambiguous, ask user to disambiguate name/path.
2. Switch active requirement to target.
3. Confirm active path in response and continue downstream skills on new context.

## Response template (must)

After successful switch, always reply with:

1. Active target name.
2. Absolute or workspace-relative active path.
3. One explicit next-step suggestion for downstream skill.

Template:
```text
已切换需求上下文。
当前需求：<name>
当前路径：<path>
建议下一步：<e.g. /spec-agent-write 继续生成文档 或 /spec-agent-check 执行复检>
```

## Run

By name:
```bash
python scripts/spec_agent.py set-active --name <name>
```

By path (e.g. spec-agent-init uses `spec/0000-00-00/project-spec`):
```bash
python scripts/spec_agent.py set-active --path spec/0000-00-00/project-spec
# or spec/YYYY-MM-DD/<name>
```

## Output

- Confirmation of active requirement name and path; one suggested next step (e.g. `/spec-agent-write` or `/spec-agent-check`).

## Guardrails

- Do not mutate requirement docs in this skill.
- Only change `spec/.active` context.
- **Scope**: Only update `spec/.active`. Do not modify project source code or any other files (temporary scripts excepted per AGENTS.md).

#!/usr/bin/env python
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Cursor Plugin layout: skills live under skills/ (see .cursor-plugin/plugin.json)
SKILLS_ROOT = ROOT / "skills"
COMMANDS_ROOT = ROOT / "commands"


def parse_frontmatter(text: str) -> dict[str, str]:
    normalized = text.lstrip("\ufeff\r\n\t ")
    match = re.match(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)", normalized, re.DOTALL)
    if not match:
        raise RuntimeError("SKILL.md missing YAML frontmatter block")
    out = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise RuntimeError(f"invalid frontmatter line: {raw_line}")
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip()
    return out


def iter_split_skills() -> list[Path]:
    if not SKILLS_ROOT.exists():
        return []
    return sorted([p for p in SKILLS_ROOT.iterdir() if p.is_dir()])


def validate_split_skill(skill_dir: Path):
    """Validate a plugin skill under skills/<name>/: only SKILL.md with frontmatter and content patterns."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise RuntimeError(f"{skill_dir} missing SKILL.md")

    skill_text = skill_md.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(skill_text)
    required = {"name", "description"}
    optional = {"disable-model-invocation"}
    keys = set(frontmatter.keys())
    missing = required - keys
    unknown = keys - required - optional
    if missing or unknown:
        raise RuntimeError(
            f"{skill_dir} frontmatter invalid; missing={sorted(missing)}, unknown={sorted(unknown)}, got={sorted(keys)}"
        )
    if "disable-model-invocation" in frontmatter:
        raw_flag = str(frontmatter.get("disable-model-invocation", "")).strip().lower()
        if raw_flag not in {"true", "false"}:
            raise RuntimeError(
                f"{skill_dir} disable-model-invocation must be true/false, got: {frontmatter.get('disable-model-invocation')}"
            )

    skill_name = frontmatter.get("name", "")
    if not skill_name:
        raise RuntimeError(f"{skill_dir} frontmatter name is empty")
    if skill_dir.name != skill_name:
        raise RuntimeError(f"{skill_dir} folder name must match frontmatter name: {skill_name}")
    description = frontmatter.get("description", "")
    if "Use when" not in description:
        raise RuntimeError(f"{skill_dir} description must include trigger guidance using 'Use when ...'")

    if skill_name == "spec-agent-task":
        required_patterns = [
            r"subagent-context\s+--name\s+<name>\s+--stage\s+<stage>\s+--json-output",
            r"issues=0[\s\S]*?final_check",
            r"issues>0",
        ]
        for pattern in required_patterns:
            if not re.search(pattern, skill_text, flags=re.IGNORECASE):
                raise RuntimeError(f"{skill_dir} missing required task flow pattern: {pattern}")

    if skill_name == "spec-agent-chat":
        required_patterns = [
            r"explicit\s+`--name\s+<name>`",
            r"subagent-init\s+--name\s+<name>",
            r"subagent-status\s+--name\s+<name>\s+--json-output",
            r"subagent-context\s+--name\s+<name>\s+--stage\s+<stage>\s+--json-output",
            r"subagent-stage\s+--name\s+<name>\s+--stage\s+<stage>\s+--status\s+completed",
            r"subagent-stage\s+--name\s+<name>\s+--stage\s+final_check\s+--status\s+completed",
            r"subagent-stage\s+--name\s+<name>\s+--stage\s+final_check\s+--status\s+failed",
            r"subagent-status\s+--name\s+<name>\s+--normalize",
        ]
        for pattern in required_patterns:
            if not re.search(pattern, skill_text, flags=re.IGNORECASE):
                raise RuntimeError(f"{skill_dir} missing required chat flow pattern: {pattern}")


# Pattern: spec-agent-<word> (skill name), e.g. spec-agent-task, spec-agent-clarify
SKILL_REF_PATTERN = re.compile(r"spec-agent-[a-z0-9-]+", re.IGNORECASE)


def collect_skill_references(skill_text: str) -> set[str]:
    """Extract all spec-agent-* skill names referenced in SKILL.md body (Child skills, policy refs, etc.)."""
    refs = set()
    for m in SKILL_REF_PATTERN.finditer(skill_text):
        refs.add(m.group(0).lower())
    return refs


def validate_skill_associations(skill_dirs: list[Path], known_names: set[str]) -> None:
    """Ensure every skill referenced in any SKILL.md exists under skills/ (association/trigger consistency)."""
    for skill_dir in skill_dirs:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        text = skill_md.read_text(encoding="utf-8")
        refs = collect_skill_references(text)
        missing = refs - known_names
        if missing:
            raise RuntimeError(
                f"{skill_dir.name} references non-existent skill(s): {sorted(missing)}. "
                f"Known: {sorted(known_names)}."
            )


def _must_contain(path: Path, needle: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        raise RuntimeError(f"{path} missing required text: {needle}")


def _must_not_contain(path: Path, needle: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle in text:
        raise RuntimeError(f"{path} contains forbidden text: {needle}")


def validate_doc_runtime_contracts() -> None:
    command_files = [
        COMMANDS_ROOT / "spec-final-check.md",
        COMMANDS_ROOT / "spec-check-clarifications.md",
        COMMANDS_ROOT / "spec-list.md",
        COMMANDS_ROOT / "spec-set-active.md",
        COMMANDS_ROOT / "spec-sync-memory.md",
    ]
    for command_file in command_files:
        _must_contain(command_file, "Run from user project root")
        _must_not_contain(command_file, "Run from repository root")

    task_skill = (SKILLS_ROOT / "spec-agent-task" / "SKILL.md").read_text(encoding="utf-8")
    init_idx = task_skill.find("python scripts/spec_agent.py init --name <name>")
    sync_idx = task_skill.find("python scripts/spec_agent.py sync-memory --name <name>")
    if init_idx == -1 or sync_idx == -1:
        raise RuntimeError("skills/spec-agent-task/SKILL.md missing init or sync-memory command example")
    if init_idx > sync_idx:
        raise RuntimeError("skills/spec-agent-task/SKILL.md must run init before sync-memory")

    init_skill = SKILLS_ROOT / "spec-agent-init" / "SKILL.md"
    _must_not_contain(init_skill, "no .active switching")
    _must_not_contain(init_skill, "不需要切换 `spec/.active`")
    _must_not_contain(init_skill, "禁止读取")
    _must_contain(init_skill, "set-active --path spec/0000-00-00/project-spec")

    compliance_doc = ROOT / "docs" / "PLUGIN-AND-SKILL-COMPLIANCE.md"
    _must_contain(compliance_doc, "用户项目根目录")
    _must_not_contain(compliance_doc, "从仓库根目录执行")

    summary_doc = ROOT / "docs" / "开发规范与流程总结.md"
    _must_contain(summary_doc, "/spec-agent-chat")
    _must_not_contain(summary_doc, "入口技能为 `spec-agent-task`")


def main():
    skills = iter_split_skills()
    if not skills:
        print("regression split skill contract: skipped (skills/ not found)")
        return
    known_names = {d.name for d in skills}
    for skill_dir in skills:
        validate_split_skill(skill_dir)
    validate_skill_associations(skills, known_names)
    validate_doc_runtime_contracts()
    print(f"regression split skill contract: ok ({len(skills)} skills, associations valid)")


if __name__ == "__main__":
    main()

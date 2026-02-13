#!/usr/bin/env python
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLIT_ROOT = ROOT / "skills-split"


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


def parse_openai_yaml_interface(text: str) -> dict[str, str]:
    interface_match = re.search(r"(?ms)^interface:\r?\n(.*?)(?:^\S|\Z)", text)
    if not interface_match:
        raise RuntimeError("agents/openai.yaml missing interface block")
    block = interface_match.group(1)
    out = {}
    for raw_line in block.splitlines():
        if not raw_line.strip():
            continue
        if not raw_line.startswith("  "):
            continue
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip('"')
    return out


def iter_split_skills() -> list[Path]:
    if not SPLIT_ROOT.exists():
        return []
    return sorted([p for p in SPLIT_ROOT.iterdir() if p.is_dir()])


def validate_split_skill(skill_dir: Path):
    skill_md = skill_dir / "SKILL.md"
    openai_yaml = skill_dir / "agents" / "openai.yaml"
    if not skill_md.exists():
        raise RuntimeError(f"{skill_dir} missing SKILL.md")
    if not openai_yaml.exists():
        raise RuntimeError(f"{skill_dir} missing agents/openai.yaml")

    frontmatter = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    allowed = {"name", "description"}
    keys = set(frontmatter.keys())
    if keys != allowed:
        raise RuntimeError(f"{skill_dir} frontmatter keys must be exactly {sorted(allowed)}, got {sorted(keys)}")

    skill_name = frontmatter.get("name", "")
    if not skill_name:
        raise RuntimeError(f"{skill_dir} frontmatter name is empty")
    if skill_dir.name != skill_name:
        raise RuntimeError(f"{skill_dir} folder name must match frontmatter name: {skill_name}")
    description = frontmatter.get("description", "")
    if "Use when" not in description:
        raise RuntimeError(f"{skill_dir} description must include trigger guidance using 'Use when ...'")

    interface = parse_openai_yaml_interface(openai_yaml.read_text(encoding="utf-8"))
    required = {"display_name", "short_description", "default_prompt"}
    missing = [k for k in required if not interface.get(k)]
    if missing:
        raise RuntimeError(f"{skill_dir} openai.yaml missing required interface fields: {missing}")
    if f"${skill_name}" not in interface["default_prompt"]:
        raise RuntimeError(f"{skill_dir} default_prompt must mention ${skill_name}")


def main():
    skills = iter_split_skills()
    if not skills:
        print("regression split skill contract: skipped (skills-split not found)")
        return
    for skill_dir in skills:
        validate_split_skill(skill_dir)
    print(f"regression split skill contract: ok ({len(skills)} skills)")


if __name__ == "__main__":
    main()


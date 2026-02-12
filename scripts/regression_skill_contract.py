#!/usr/bin/env python
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_frontmatter(text: str) -> dict[str, str]:
    normalized = text.lstrip("\ufeff\r\n\t ")
    match = re.match(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)", normalized, re.DOTALL)
    if not match:
        raise RuntimeError("SKILL.md missing YAML frontmatter block")
    fm = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise RuntimeError(f"invalid frontmatter line: {raw_line}")
        key, value = line.split(":", 1)
        fm[key.strip()] = value.strip()
    return fm


def test_skill_frontmatter_contract():
    skill_md = ROOT / "SKILL.md"
    if not skill_md.exists():
        raise RuntimeError("SKILL.md not found")
    content = skill_md.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(content)

    allowed = {"name", "description"}
    keys = set(frontmatter.keys())
    if keys != allowed:
        raise RuntimeError(f"SKILL.md frontmatter keys must be exactly {sorted(allowed)}, got {sorted(keys)}")
    if frontmatter.get("name") != "spec-agent":
        raise RuntimeError("SKILL.md frontmatter name must be spec-agent")
    description = frontmatter.get("description", "")
    if "Use when" not in description:
        raise RuntimeError("SKILL.md description must include trigger guidance using 'Use when ...'")


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


def test_openai_yaml_contract():
    openai_yaml = ROOT / "agents" / "openai.yaml"
    if not openai_yaml.exists():
        raise RuntimeError("agents/openai.yaml not found")
    text = openai_yaml.read_text(encoding="utf-8")
    interface = parse_openai_yaml_interface(text)
    required = {"display_name", "short_description", "default_prompt"}
    missing = [k for k in required if not interface.get(k)]
    if missing:
        raise RuntimeError(f"agents/openai.yaml missing required interface fields: {missing}")
    if "$spec-agent" not in interface["default_prompt"]:
        raise RuntimeError("agents/openai.yaml default_prompt must mention $spec-agent")


def main():
    test_skill_frontmatter_contract()
    test_openai_yaml_contract()
    print("regression skill contract: ok")


if __name__ == "__main__":
    main()

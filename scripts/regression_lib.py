#!/usr/bin/env python
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ai_judge_mock_path(root: Path | None = None) -> Path:
    base = root or repo_root()
    return base / "scripts" / "regression_ai_judge_mock.py"


def ai_judge_command(root: Path | None = None) -> str:
    mock = ai_judge_mock_path(root)
    return f'"{sys.executable}" "{mock}"'


def spec_agent_py(root: Path | None = None) -> list[str]:
    base = root or repo_root()
    return [sys.executable, str(base / "scripts" / "spec_agent.py")]


def run_spec_agent(
    args: list[str],
    *,
    root: Path | None = None,
    check: bool = True,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    base = root or repo_root()
    cmd = spec_agent_py(base) + args
    merged_env = os.environ.copy()
    merged_env["SPEC_AGENT_AI_JUDGE_COMMAND"] = ai_judge_command(base)
    if env:
        merged_env.update(env)
    proc = subprocess.run(
        cmd,
        cwd=str(base),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=merged_env,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{proc.stdout}\n{proc.stderr}")
    return proc


def remove_dir(path: Path):
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)

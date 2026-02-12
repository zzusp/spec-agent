#!/usr/bin/env python
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(script: str):
    p = subprocess.run(["python", str(ROOT / "scripts" / script)], cwd=str(ROOT), capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{script} failed\nstdout:\n{p.stdout}\nstderr:\n{p.stderr}")
    print(p.stdout.strip())


def main():
    run("regression_smoke.py")
    run("regression_edge_cases.py")
    run("regression_skill_contract.py")
    print("regression all: ok")


if __name__ == "__main__":
    main()

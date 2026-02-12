#!/usr/bin/env python
import datetime as dt
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ["python", str(ROOT / "scripts" / "spec_agent.py")]
REQ = "regression-smoke"


def run(args, check=True):
    cmd = PY + args
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{p.stdout}\n{p.stderr}")
    return p


def main():
    date = dt.date.today().strftime("%Y-%m-%d")

    # Prepare sqlite test db + connection file
    db = ROOT / "tmp_demo.sqlite"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    cur.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, status TEXT, amount REAL)")
    cur.execute("CREATE TABLE order_logs (id INTEGER PRIMARY KEY, order_id INTEGER, action TEXT)")
    con.commit()
    con.close()

    env_file = ROOT / "tmp_db_conn.env"
    env_file.write_text("DB_URL=sqlite:///tmp_demo.sqlite\n", encoding="utf-8")

    req_dir = ROOT / "spec" / date / REQ
    if req_dir.exists():
        subprocess.run(["cmd", "/c", "rd", "/s", "/q", str(req_dir)], cwd=str(ROOT), check=False)

    run([
        "init",
        "--name",
        REQ,
        "--title",
        "回归冒烟",
        "--desc",
        "需求A；需求B",
        "--clarify",
        "数据库连接文件：tmp_db_conn.env",
        "--date",
        date,
    ])
    run(["write-analysis", "--name", REQ])
    run(["inspect-db", "--name", REQ])
    run(["write-prd", "--name", REQ])
    run(["write-tech", "--name", REQ])
    run(["write-acceptance", "--name", REQ])
    out = run(["final-check", "--name", REQ]).stdout
    if "final-check issues: 0" not in out:
        raise RuntimeError(f"unexpected final-check result: {out}")

    # strict should block when unresolved clarifications exist
    p = run(["update", "--name", REQ, "--strict"], check=False)
    if p.returncode == 0:
        raise RuntimeError("expected strict update to fail when clarifications unresolved")

    # cleanup smoke artifacts
    subprocess.run(["cmd", "/c", "rd", "/s", "/q", str(req_dir)], cwd=str(ROOT), check=False)
    if env_file.exists():
        env_file.unlink()
    if db.exists():
        db.unlink()

    print("regression smoke: ok")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
import datetime as dt
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ["python", str(ROOT / "scripts" / "spec_agent.py")]
CFG = ROOT / "spec-agent.config.json"
BACKUP = ROOT / "spec-agent.config.backup.test.json"


def run(args, check=True):
    p = subprocess.run(PY + args, cwd=str(ROOT), capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(PY + args)}\n{p.stdout}\n{p.stderr}")
    return p


def test_bad_config_rejected():
    if CFG.exists():
        shutil.copyfile(CFG, BACKUP)
    bad = {
        "spec_dir": "spec",
        "date_format": "%Y-%m-%d",
        "placeholders": [],
        "prd_tech_words": [],
        "clarify_columns": ["ID", "状态"],
        "clarify_statuses": [],
        "clarify_confirmed_status": "已确认",
    }
    CFG.write_text(json.dumps(bad, ensure_ascii=False, indent=2), encoding="utf-8")
    p = run(["list"], check=False)
    if p.returncode == 0:
        raise RuntimeError("expected invalid config to fail")


def test_large_context_file_warning():
    if BACKUP.exists():
        shutil.copyfile(BACKUP, CFG)

    big = ROOT / "tmp_big_conn.txt"
    big.write_text("x" * (256 * 1024), encoding="utf-8")

    req = "edge-smoke"
    date = dt.date.today().strftime("%Y-%m-%d")
    req_dir = ROOT / "spec" / date / req
    if req_dir.exists():
        subprocess.run(["cmd", "/c", "rd", "/s", "/q", str(req_dir)], cwd=str(ROOT), check=False)

    run([
        "init",
        "--name",
        req,
        "--title",
        "边界回归",
        "--desc",
        "需求A",
        "--clarify",
        "sqlite:///tmp_demo.sqlite；数据库连接文件：tmp_big_conn.txt",
        "--date",
        date,
    ])

    # create sqlite db for direct connection path
    db = ROOT / "tmp_demo.sqlite"
    if not db.exists():
        import sqlite3
        con = sqlite3.connect(str(db))
        con.execute("create table if not exists t1(id integer)")
        con.commit()
        con.close()

    clar = req_dir / "00-clarifications.md"
    text = clar.read_text(encoding="utf-8")
    if "skipped too large" not in text:
        raise RuntimeError("expected skipped too large warning in clarifications")

    # cleanup
    subprocess.run(["cmd", "/c", "rd", "/s", "/q", str(req_dir)], cwd=str(ROOT), check=False)
    if big.exists():
        big.unlink()
    if db.exists():
        db.unlink()


def test_init_without_name_auto_generated():
    date = dt.date.today().strftime("%Y-%m-%d")
    p = run([
        "--json-output",
        "init",
        "--desc",
        "用户发起退款，支持部分退款。",
        "--date",
        date,
    ])
    try:
        payload = json.loads(p.stdout.strip())
    except Exception as ex:
        raise RuntimeError(f"expected json output for auto-name init: {ex}; raw={p.stdout}")

    name = payload.get("name", "")
    path = payload.get("path", "")
    if not name or not path:
        raise RuntimeError(f"auto-name init missing name/path: {payload}")
    if not payload.get("auto_named", False):
        raise RuntimeError(f"auto-name init should mark auto_named=true: {payload}")
    if not payload.get("auto_titled", False):
        raise RuntimeError(f"auto-title init should mark auto_titled=true: {payload}")
    auto_title = payload.get("title", "")
    if not auto_title:
        raise RuntimeError(f"auto-title should not be empty: {payload}")
    lowered = str(name).lower()
    if "sqlite" in lowered or "tmp" in lowered:
        raise RuntimeError(f"auto-generated name should avoid connection/path hints: {name}")
    created = Path(path)
    if not created.exists():
        raise RuntimeError(f"auto-generated requirement path not created: {path}")
    meta_path = created / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("title") != auto_title:
        raise RuntimeError("metadata title mismatch with init output title")

    subprocess.run(["cmd", "/c", "rd", "/s", "/q", str(created)], cwd=str(ROOT), check=False)


def main():
    try:
        test_bad_config_rejected()
        test_large_context_file_warning()
        test_init_without_name_auto_generated()
        print("regression edge cases: ok")
    finally:
        if BACKUP.exists():
            shutil.copyfile(BACKUP, CFG)
            BACKUP.unlink()


if __name__ == "__main__":
    main()

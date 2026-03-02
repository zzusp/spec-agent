#!/usr/bin/env python
import datetime as dt
import json
import os
import sqlite3
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = [sys.executable, str(ROOT / "scripts" / "spec_agent.py")]
CFG = ROOT / "scripts" / "spec-agent.config.json"
BACKUP = ROOT / "scripts" / "spec-agent.config.backup.test.json"


def run(args, check=True, timeout=None):
    """Run spec_agent.py with optional timeout (seconds). Used by lock test to avoid indefinite block."""
    p = subprocess.run(
        PY + args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(PY + args)}\n{p.stdout}\n{p.stderr}")
    return p


def remove_dir(path: Path):
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


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


def test_invalid_lock_config_rejected():
    if BACKUP.exists():
        shutil.copyfile(BACKUP, CFG)
    base = json.loads(CFG.read_text(encoding="utf-8-sig"))
    base["metadata_lock_timeout_sec"] = 0
    CFG.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
    p = run(["list"], check=False)
    if p.returncode == 0:
        raise RuntimeError("expected invalid metadata_lock_timeout_sec to fail")

    base["metadata_lock_timeout_sec"] = 8
    base["requirement_lock_poll_sec"] = False
    CFG.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
    p = run(["list"], check=False)
    if p.returncode == 0:
        raise RuntimeError("expected invalid requirement_lock_poll_sec to fail")

    base["requirement_lock_poll_sec"] = 0.05
    base["enforce_final_check_agent_independence"] = "true"
    CFG.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
    p = run(["list"], check=False)
    if p.returncode == 0:
        raise RuntimeError("expected invalid enforce_final_check_agent_independence to fail")


def test_invalid_project_mode_config_rejected():
    if BACKUP.exists():
        shutil.copyfile(BACKUP, CFG)
    base = json.loads(CFG.read_text(encoding="utf-8-sig"))
    base["default_project_mode"] = "invalid-mode"
    CFG.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
    p = run(["list"], check=False)
    if p.returncode == 0:
        raise RuntimeError("expected invalid default_project_mode to fail")


def test_live_lock_owner_not_stolen_by_stale_policy():
    # On Windows the subprocess that waits for the lock often receives KeyboardInterrupt from the
    # runner before the wait completes; skip here to avoid flaky failures. Lock semantics are
    # exercised on Unix (CI or local).
    if sys.platform == "win32":
        return
    if BACKUP.exists():
        shutil.copyfile(BACKUP, CFG)
    req = "edge-lock-live-owner"
    date = dt.date.today().strftime("%Y-%m-%d")
    req_dir = ROOT / "spec" / date / req
    remove_dir(req_dir)
    holder = None
    try:
        cfg = json.loads(CFG.read_text(encoding="utf-8-sig"))
        cfg["requirement_lock_stale_sec"] = 0.2
        cfg["requirement_lock_timeout_sec"] = 5.0
        cfg["requirement_lock_poll_sec"] = 0.05
        CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

        run([
            "init",
            "--name",
            req,
            "--title",
            "并发锁回归",
            "--desc",
            "需求A",
            "--state-only",
            "--date",
            date,
        ])

        holder_code = (
            "import datetime as dt, time\n"
            "from pathlib import Path\n"
            "import spec_agent_engine as eng\n"
            f"path = Path('spec') / dt.date.today().strftime('%Y-%m-%d') / '{req}'\n"
            "with eng.requirement_write_lock(path, dry_run=False):\n"
            "    print('holder_acquired', flush=True)\n"
            "    time.sleep(0.8)\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "scripts")
        holder = subprocess.Popen(
            [sys.executable, "-c", holder_code],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        line = holder.stdout.readline().strip() if holder.stdout else ""
        if "holder_acquired" not in line:
            if holder.poll() is None:
                holder.kill()
                holder.wait(timeout=2)
            raise RuntimeError(f"lock holder did not acquire lock; got: {line!r}")

        # sync-memory must wait for holder to release (not steal live lock); cap wait so test never hangs
        start = time.time()
        run(
            ["sync-memory", "--name", req, "--json-output"],
            timeout=8,
        )
        elapsed = time.time() - start
        if elapsed < 0.5:
            if holder.poll() is None:
                holder.kill()
                holder.wait(timeout=2)
            raise RuntimeError(f"live lock owner should not be stolen; elapsed={elapsed:.2f}s")

        holder.wait(timeout=5)
        if holder.returncode != 0:
            err = holder.stderr.read() if holder.stderr else ""
            raise RuntimeError(f"lock holder exited with error: {err}")
    except subprocess.TimeoutExpired as e:
        if holder is not None and holder.poll() is None:
            holder.kill()
            holder.wait(timeout=2)
        raise RuntimeError(
            f"sync-memory did not complete within timeout (lock may be stuck or config not applied): {e}"
        ) from e
    finally:
        if holder is not None and holder.poll() is None:
            holder.kill()
            holder.wait(timeout=2)
        if BACKUP.exists():
            shutil.copyfile(BACKUP, CFG)
        remove_dir(req_dir)


def test_concurrent_init_same_name_not_overwritten():
    # Skip on Windows: concurrent subprocess communicate() often gets KeyboardInterrupt from runner.
    if sys.platform == "win32":
        return
    if BACKUP.exists():
        shutil.copyfile(BACKUP, CFG)
    req = "edge-init-race"
    date = dt.date.today().strftime("%Y-%m-%d")
    req_dir = ROOT / "spec" / date / req
    remove_dir(req_dir)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "scripts")
    holder = None
    try:
        holder_code = (
            "import datetime as dt, time\n"
            "from pathlib import Path\n"
            "import spec_agent_engine as eng\n"
            f"path = Path('spec') / dt.date.today().strftime('%Y-%m-%d') / '{req}'\n"
            "with eng.requirement_write_lock(path, dry_run=False):\n"
            "    print('holder_acquired', flush=True)\n"
            "    time.sleep(1.5)\n"
        )
        holder = subprocess.Popen(
            [sys.executable, "-c", holder_code],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        line = holder.stdout.readline().strip() if holder.stdout else ""
        if "holder_acquired" not in line:
            holder.kill()
            raise RuntimeError(f"lock holder did not acquire lock; got: {line}")

        cmd_a = PY + [
            "--json-output",
            "init",
            "--name",
            req,
            "--title",
            "TITLE_A",
            "--desc",
            "DESC_A",
            "--state-only",
            "--date",
            date,
        ]
        cmd_b = PY + [
            "--json-output",
            "init",
            "--name",
            req,
            "--title",
            "TITLE_B",
            "--desc",
            "DESC_B",
            "--state-only",
            "--date",
            date,
        ]
        p_a = subprocess.Popen(cmd_a, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(0.05)
        p_b = subprocess.Popen(cmd_b, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out_a, err_a = p_a.communicate(timeout=10)
        out_b, err_b = p_b.communicate(timeout=10)

        outcomes = [
            {"code": p_a.returncode, "out": out_a.strip(), "err": err_a.strip()},
            {"code": p_b.returncode, "out": out_b.strip(), "err": err_b.strip()},
        ]
        success = [x for x in outcomes if x["code"] == 0]
        failed = [x for x in outcomes if x["code"] != 0]
        if len(success) != 1 or len(failed) != 1:
            raise RuntimeError(f"expected exactly one success and one failure for concurrent same-name init: {outcomes}")
        fail_text = (failed[0].get("err", "") or "") + "\n" + (failed[0].get("out", "") or "")
        if "requirement already exists" not in fail_text:
            raise RuntimeError(f"expected failure reason 'requirement already exists': {failed[0]}")

        payload = json.loads(success[0]["out"])
        meta = json.loads((req_dir / "metadata.json").read_text(encoding="utf-8-sig"))
        if meta.get("title") != payload.get("title"):
            raise RuntimeError(f"metadata title was overwritten unexpectedly: meta={meta}, payload={payload}")
        expected_desc = {"TITLE_A": "DESC_A", "TITLE_B": "DESC_B"}.get(str(payload.get("title", "")), "")
        if not expected_desc or meta.get("original_requirement") != expected_desc:
            raise RuntimeError(f"metadata original requirement was overwritten unexpectedly: meta={meta}, payload={payload}")
    finally:
        if holder is not None:
            try:
                holder.wait(timeout=5)
            except Exception:
                holder.kill()
        remove_dir(req_dir)


def test_structured_db_connections_saved():
    if BACKUP.exists():
        shutil.copyfile(BACKUP, CFG)

    req = "edge-smoke"
    date = dt.date.today().strftime("%Y-%m-%d")
    req_dir = ROOT / "spec" / date / req
    remove_dir(req_dir)

    db = ROOT / "tmp_demo.sqlite"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(str(db))
    con.execute("create table if not exists t1(id integer)")
    con.commit()
    con.close()
    db_connections_json = json.dumps([
        {
            "db_type": "sqlite",
            "connection": "sqlite:///tmp_demo.sqlite",
            "source": "caller-ai",
        },
        {
            "db_type": "mysql",
            "host": "127.0.0.1",
            "port": 3306,
            "username": "user",
            "password": "secret",
            "database": "demo",
            "source": "caller-ai",
        },
    ], ensure_ascii=False)

    run([
        "init",
        "--name",
        req,
        "--title",
        "边界回归",
        "--desc",
        "需求A",
        "--db-connections-json",
        db_connections_json,
        "--date",
        date,
    ])

    clar = req_dir / "00-clarifications.md"
    text = clar.read_text(encoding="utf-8")
    if "type=sqlite" not in text:
        raise RuntimeError("expected structured sqlite connection evidence in clarifications")
    if "type=mysql" not in text:
        raise RuntimeError("expected structured mysql connection evidence in clarifications")
    if "secret" in text:
        raise RuntimeError("expected mysql password to be masked in clarifications")

    meta = json.loads((req_dir / "metadata.json").read_text(encoding="utf-8-sig"))
    ai_connections = meta.get("ai_db_connections", [])
    if not isinstance(ai_connections, list) or len(ai_connections) < 2:
        raise RuntimeError(f"expected ai_db_connections persisted in metadata: {meta}")

    # cleanup
    remove_dir(req_dir)
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

    remove_dir(created)


def test_init_rejects_multiple_desc_sources():
    date = dt.date.today().strftime("%Y-%m-%d")
    p = run([
        "init",
        "--desc",
        "需求A",
        "--desc-json",
        '{"x":"需求B"}',
        "--date",
        date,
    ], check=False)
    if p.returncode == 0:
        raise RuntimeError("expected init to reject multiple desc input sources")
    msg = (p.stderr or "") + "\n" + (p.stdout or "")
    if "exactly one input source" not in msg:
        raise RuntimeError(f"unexpected error message for multi-source init: {msg}")


def test_scan_includes_scripts_module():
    req = "edge-scan-scripts"
    date = dt.date.today().strftime("%Y-%m-%d")
    req_dir = ROOT / "spec" / date / req
    remove_dir(req_dir)
    try:
        run([
            "init",
            "--name",
            req,
            "--title",
            "扫描模块回归",
            "--desc",
            "需求A",
            "--date",
            date,
        ])
        run(["scan", "--name", req])
        analysis = (req_dir / "01-analysis.md").read_text(encoding="utf-8")
        if "- scripts" not in analysis:
            raise RuntimeError(f"expected scan output to include scripts module: {analysis}")
    finally:
        remove_dir(req_dir)


def test_inspect_db_inserts_marker_and_masks_secret():
    req = "edge-inspect-db"
    date = dt.date.today().strftime("%Y-%m-%d")
    req_dir = ROOT / "spec" / date / req
    db = ROOT / "tmp_abs_demo.sqlite"
    remove_dir(req_dir)
    if db.exists():
        db.unlink()
    try:
        con = sqlite3.connect(str(db))
        con.execute("create table if not exists t_demo(id integer primary key, name text)")
        con.commit()
        con.close()

        sqlite_conn = "sqlite:////" + str(db.resolve()).lstrip("/")
        mysql_conn = "mysql://user:secret123@127.0.0.1:3306/demo"
        db_connections_json = json.dumps([
            {
                "db_type": "sqlite",
                "connection": sqlite_conn,
                "source": "caller-ai",
            },
            {
                "db_type": "mysql",
                "connection": mysql_conn,
                "source": "caller-ai",
            },
        ], ensure_ascii=False)
        run([
            "init",
            "--name",
            req,
            "--title",
            "inspect-db 回归",
            "--desc",
            "请核查数据库连接信息",
            "--db-connections-json",
            db_connections_json,
            "--date",
            date,
        ])

        analysis_path = req_dir / "01-analysis.md"
        legacy_like = analysis_path.read_text(encoding="utf-8")
        legacy_like = legacy_like.replace("<!-- DB-SCHEMA:START -->\n", "").replace("\n<!-- DB-SCHEMA:END -->", "")
        analysis_path.write_text(legacy_like, encoding="utf-8")

        run(["inspect-db", "--name", req])
        updated = analysis_path.read_text(encoding="utf-8")
        if "<!-- DB-SCHEMA:START -->" not in updated or "<!-- DB-SCHEMA:END -->" not in updated:
            raise RuntimeError("inspect-db should insert DB-SCHEMA marker block for legacy analysis docs")
        # 方式 B：无脚本时写入提示，不执行内置探查
        if "未提供 DB 探查临时脚本" not in updated and ".tmp_inspect_db.py" not in updated:
            raise RuntimeError(f"inspect-db without script should write script-required message: {updated[:600]}")
        if "secret123" in updated:
            raise RuntimeError("inspect-db output should not expose plaintext credentials")
    finally:
        remove_dir(req_dir)
        if db.exists():
            db.unlink()


def test_inspect_db_script_preferred():
    """方式 B：全量 schema 写入 spec/db/{slug}-schema.md，analysis 仅写引用行。"""
    req = "edge-inspect-db-script"
    date = dt.date.today().strftime("%Y-%m-%d")
    req_dir = ROOT / "spec" / date / req
    script_path = ROOT / ".tmp_inspect_db.py"
    global_schema = ROOT / "spec" / "db" / "sqlite-any.db-schema.md"
    remove_dir(req_dir)
    try:
        run([
            "init",
            "--name",
            req,
            "--title",
            "inspect-db 脚本优先",
            "--desc",
            "需求含 DB 连接",
            "--db-connections-json",
            json.dumps([{"db_type": "sqlite", "connection": "sqlite:///any.db", "source": "test"}]),
            "--date",
            date,
        ])
        script_path.write_text(
            "import json,sys\n"
            "d=json.load(sys.stdin)\n"
            "print(json.dumps({\"results\":[{\"connection\":\"custom-script-demo\",\"ok\":True,\"message\":\"script tables: 1\",\"tables\":{\"t_demo\":[\"id\",\"name\"]}}]},ensure_ascii=False))",
            encoding="utf-8",
        )
        analysis_path = req_dir / "01-analysis.md"
        legacy = analysis_path.read_text(encoding="utf-8")
        legacy = legacy.replace("<!-- DB-SCHEMA:START -->\n", "").replace("\n<!-- DB-SCHEMA:END -->", "")
        analysis_path.write_text(legacy, encoding="utf-8")
        run(["inspect-db", "--name", req])
        updated = analysis_path.read_text(encoding="utf-8")
        if "本需求涉及表详见" not in updated or "schema 文档" not in updated or "spec/db/" not in updated:
            raise RuntimeError(f"inspect-db should write reference line in analysis: {updated[:500]}")
        if not global_schema.exists():
            raise RuntimeError(f"inspect-db should write full schema to {global_schema}")
        global_content = global_schema.read_text(encoding="utf-8")
        if "script tables: 1" not in global_content or "表 `t_demo`" not in global_content:
            raise RuntimeError(f"global schema file should contain script output: {global_content[:500]}")
    finally:
        if script_path.exists():
            script_path.unlink()
        if global_schema.exists():
            global_schema.unlink()
        remove_dir(req_dir)
        if (ROOT / "spec" / "db").exists() and not any((ROOT / "spec" / "db").iterdir()):
            (ROOT / "spec" / "db").rmdir()


def test_inspect_db_script_file_deleted_after_run():
    """临时脚本执行后被删除；全量写入 spec/db，analysis 仅引用。"""
    req = "edge-inspect-db-temp-script"
    date = dt.date.today().strftime("%Y-%m-%d")
    req_dir = ROOT / "spec" / date / req
    temp_script = ROOT / ".tmp_inspect_db.py"
    global_schema = ROOT / "spec" / "db" / "sqlite-any.db-schema.md"
    remove_dir(req_dir)
    try:
        run([
            "init",
            "--name",
            req,
            "--title",
            "inspect-db 临时脚本",
            "--desc",
            "需求含 DB 连接",
            "--db-connections-json",
            json.dumps([{"db_type": "sqlite", "connection": "sqlite:///any.db", "source": "test"}]),
            "--date",
            date,
        ])
        try:
            temp_script.write_text(
                "import json,sys\n"
                "d=json.load(sys.stdin)\n"
                "print(json.dumps({\"results\":[{\"connection\":\"temp-script\",\"ok\":True,\"message\":\"temp script ran\",\"tables\":{\"t1\":[\"a\"]}}]},ensure_ascii=False))",
                encoding="utf-8",
            )
            analysis_path = req_dir / "01-analysis.md"
            legacy = analysis_path.read_text(encoding="utf-8")
            legacy = legacy.replace("<!-- DB-SCHEMA:START -->\n", "").replace("\n<!-- DB-SCHEMA:END -->", "")
            analysis_path.write_text(legacy, encoding="utf-8")
            run(["inspect-db", "--name", req])
            if temp_script.exists():
                raise RuntimeError(f"temp script should be deleted after inspect-db: {temp_script}")
            updated = analysis_path.read_text(encoding="utf-8")
            if "本需求涉及表详见" not in updated or "spec/db/" not in updated:
                raise RuntimeError(f"inspect-db should write reference in analysis: {updated[:500]}")
            if global_schema.exists() and "temp script ran" not in global_schema.read_text(encoding="utf-8"):
                raise RuntimeError("global schema file should contain script output")
        finally:
            if temp_script.exists():
                temp_script.unlink()
            if global_schema.exists():
                global_schema.unlink()
    finally:
        remove_dir(req_dir)
        if (ROOT / "spec" / "db").exists() and not any((ROOT / "spec" / "db").iterdir()):
            (ROOT / "spec" / "db").rmdir()


def test_add_clarifications_rebuild_without_crash():
    sys.path.insert(0, str(ROOT / "scripts"))
    import spec_agent_engine as eng

    content = "## 澄清项\n(空)\n"
    updated = eng.add_clarifications(content, [{"id": "C-001", "doc": "analysis", "question": "请确认范围"}])
    if "| C-001 |" not in updated:
        raise RuntimeError(f"expected rebuilt clarification table with inserted row: {updated}")


def test_copy_rules_json_output_single_payload():
    p = run(["--json-output", "copy-rules", "--dry-run"], check=False)
    if p.returncode != 0:
        raise RuntimeError(f"copy-rules --json-output should succeed: {p.stderr}")
    non_empty_lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
    if len(non_empty_lines) != 1:
        raise RuntimeError(f"copy-rules --json-output should emit one json payload: {p.stdout!r}")
    payload = json.loads(non_empty_lines[0])
    if payload.get("ok") is not True:
        raise RuntimeError(f"unexpected copy-rules payload: {payload}")


def test_check_clarifications_md_source_and_json_error_output():
    req = "edge-clarifications-union"
    date = dt.date.today().strftime("%Y-%m-%d")
    req_dir = ROOT / "spec" / date / req
    remove_dir(req_dir)
    try:
        run([
            "init",
            "--name",
            req,
            "--title",
            "澄清并集回归",
            "--desc",
            "需求A",
            "--state-only",
            "--date",
            date,
        ])
        clar_md = req_dir / "00-clarifications.md"
        clar_json = req_dir / "00-clarifications.json"

        # Add a non-example pending row in markdown only.
        md_text = clar_md.read_text(encoding="utf-8")
        md_insert = "| C-002 | 待确认 | 高 | 范围 | prd | 范围 | 请确认范围边界 |  |  |\n"
        md_text = md_text.replace("|---|---|---|---|---|---|---|---|---|\n", "|---|---|---|---|---|---|---|---|---|\n" + md_insert, 1)
        clar_md.write_text(md_text, encoding="utf-8")

        # strict should fail when markdown contains pending rows.
        p = run(["check-clarifications", "--name", req, "--strict"], check=False)
        if p.returncode == 0:
            raise RuntimeError("expected strict clarification check to fail when markdown has pending row")

        # strict + json-output should emit machine-readable json error.
        p_json = run(["check-clarifications", "--name", req, "--strict", "--json-output"], check=False)
        if p_json.returncode == 0:
            raise RuntimeError("expected strict clarification check to fail in json-output mode")
        if not p_json.stdout.strip():
            raise RuntimeError("expected json error payload on stdout for --json-output failures")
        try:
            payload = json.loads(p_json.stdout.strip())
        except Exception as ex:
            raise RuntimeError(f"invalid json error payload: {ex}; raw={p_json.stdout!r}")
        if not payload.get("error"):
            raise RuntimeError(f"expected json error field for failure payload: {payload}")
        if "clarifications not closed" not in str(payload.get("error", "")):
            raise RuntimeError(f"unexpected json error message: {payload}")

        # markdown is source-of-truth: once markdown row is confirmed, strict should pass
        # even when json mirror is stale/pending.
        md_text = clar_md.read_text(encoding="utf-8")
        md_text = md_text.replace("| C-002 | 待确认 |", "| C-002 | 已确认 |", 1)
        md_text = md_text.replace("| 请确认范围边界 |  |  |", "| 请确认范围边界 | 范围已确认 | 已按确认范围更新 |", 1)
        clar_md.write_text(md_text, encoding="utf-8")

        stale_json = {
            "rows": [
                {
                    "id": "C-002",
                    "status": "待确认",
                    "priority": "高",
                    "impact": "范围",
                    "doc": "prd",
                    "section": "范围",
                    "question": "请确认范围边界",
                    "answer": "",
                    "solution": "",
                }
            ]
        }
        clar_json.write_text(json.dumps(stale_json, ensure_ascii=False, indent=2), encoding="utf-8")

        p_ok = run(["check-clarifications", "--name", req, "--strict", "--json-output"], check=False)
        if p_ok.returncode != 0:
            raise RuntimeError(f"expected strict clarification check to pass based on markdown source-of-truth: {p_ok.stderr}")
        ok_payload = json.loads(p_ok.stdout.strip())
        if ok_payload.get("pending") != 0:
            raise RuntimeError(f"expected pending=0 when markdown rows are all confirmed: {ok_payload}")
        if ok_payload.get("source_of_truth") != "markdown":
            raise RuntimeError(f"expected source_of_truth=markdown: {ok_payload}")
        if ok_payload.get("mirror_in_sync") is not False:
            raise RuntimeError(f"expected mirror_in_sync=false when json mirror is stale: {ok_payload}")
    finally:
        remove_dir(req_dir)


def test_json_output_parser_failure_returns_json():
    p = run(["--json-output", "unknown-command"], check=False)
    if p.returncode == 0:
        raise RuntimeError("expected parser failure for unknown command")
    if not p.stdout.strip():
        raise RuntimeError("expected json error payload on stdout for parser failure with --json-output")
    try:
        payload = json.loads(p.stdout.strip())
    except Exception as ex:
        raise RuntimeError(f"invalid parser failure json payload: {ex}; raw={p.stdout!r}")
    if payload.get("ok") is not False:
        raise RuntimeError(f"expected ok=false in parser failure payload: {payload}")
    if not payload.get("error"):
        raise RuntimeError(f"expected error field in parser failure payload: {payload}")


def main():
    try:
        test_bad_config_rejected()
        test_invalid_lock_config_rejected()
        test_invalid_project_mode_config_rejected()
        test_live_lock_owner_not_stolen_by_stale_policy()
        test_concurrent_init_same_name_not_overwritten()
        test_structured_db_connections_saved()
        test_init_without_name_auto_generated()
        test_init_rejects_multiple_desc_sources()
        test_scan_includes_scripts_module()
        test_inspect_db_inserts_marker_and_masks_secret()
        test_inspect_db_script_preferred()
        test_inspect_db_script_file_deleted_after_run()
        test_add_clarifications_rebuild_without_crash()
        test_copy_rules_json_output_single_payload()
        test_check_clarifications_md_source_and_json_error_output()
        test_json_output_parser_failure_returns_json()
        print("regression edge cases: ok")
    finally:
        if BACKUP.exists():
            shutil.copyfile(BACKUP, CFG)
            BACKUP.unlink()


if __name__ == "__main__":
    main()

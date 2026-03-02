#!/usr/bin/env python
from __future__ import annotations

import errno
import json
import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import spec_agent_engine_core as core


def _read_lock_owner(lock_path: Path) -> tuple[int | None, str]:
    try:
        raw = lock_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None, ""
    if not raw:
        return None, ""
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            pid_raw = data.get("pid")
            start = str(data.get("start", "")).strip()
            pid = int(pid_raw) if pid_raw is not None else None
            return pid, start
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    if "|" in raw:
        pid_part, start_part = raw.split("|", 1)
        try:
            return int(pid_part.strip()), start_part.strip()
        except ValueError:
            return None, ""
    try:
        return int(raw), ""
    except ValueError:
        return None, ""


def _acquire_file_lock(lock_path: Path, timeout_sec: float, poll_sec: float, stale_sec: float, lock_name: str):
    def pid_running(pid: int | None) -> bool:
        if not pid or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError as ex:
            if ex.errno == errno.ESRCH:
                return False
            if ex.errno == errno.EPERM:
                return True
            return True

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            payload = {
                "pid": os.getpid(),
                "start": core._process_start_signature(os.getpid()),
            }
            os.write(fd, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            os.close(fd)
            return
        except FileExistsError:
            owner_pid, owner_start_sig = _read_lock_owner(lock_path)
            owner_running = pid_running(owner_pid)
            owner_current_start_sig = core._process_start_signature(owner_pid) if owner_running else ""
            try:
                mtime = lock_path.stat().st_mtime
                if (time.time() - mtime) > stale_sec:
                    # Reclaim stale lock only when owner process is not alive.
                    if not owner_running:
                        try:
                            lock_path.unlink()
                        except FileNotFoundError:
                            pass
                        continue
                    # Reclaim stale lock when PID was reused by a different process instance.
                    if owner_start_sig and owner_current_start_sig and owner_start_sig != owner_current_start_sig:
                        try:
                            lock_path.unlink()
                        except FileNotFoundError:
                            pass
                        continue
            except OSError:
                pass
            if (time.time() - start) > timeout_sec:
                raise SystemExit(f"{lock_name} lock timeout")
            time.sleep(poll_sec)


def _release_file_lock(lock_path: Path):
    try:
        if not lock_path.exists():
            return
        owner_pid, owner_start_sig = _read_lock_owner(lock_path)
        if owner_pid and owner_pid != os.getpid():
            return
        if owner_start_sig:
            current_sig = core._process_start_signature(os.getpid())
            if current_sig and current_sig != owner_start_sig:
                return
        if owner_pid is None and owner_start_sig:
            return
        lock_path.unlink()
    except FileNotFoundError:
        return
    except OSError as ex:
        core.runtime_log(f"[warn] failed to release lock: {lock_path} ({ex})", stderr=True)
        return


def _acquire_metadata_lock(lock_path: Path):
    _acquire_file_lock(
        lock_path,
        timeout_sec=core.METADATA_LOCK_TIMEOUT_SEC,
        poll_sec=core.METADATA_LOCK_POLL_SEC,
        stale_sec=core.METADATA_LOCK_STALE_SEC,
        lock_name="metadata",
    )


def _release_metadata_lock(lock_path: Path):
    _release_file_lock(lock_path)


def _acquire_requirement_lock(lock_path: Path):
    _acquire_file_lock(
        lock_path,
        timeout_sec=core.REQUIREMENT_LOCK_TIMEOUT_SEC,
        poll_sec=core.REQUIREMENT_LOCK_POLL_SEC,
        stale_sec=core.REQUIREMENT_LOCK_STALE_SEC,
        lock_name="requirement",
    )


def _release_requirement_lock(lock_path: Path):
    _release_file_lock(lock_path)


@contextmanager
def requirement_write_lock(path: Path, dry_run: bool = False):
    lock_path = core._requirement_lock_path(path)
    if dry_run:
        core.runtime_log(f"[dry-run] would acquire requirement lock: {lock_path}")
        yield
        return
    _acquire_requirement_lock(lock_path)
    try:
        yield
    finally:
        _release_requirement_lock(lock_path)

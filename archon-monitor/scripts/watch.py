#!/usr/bin/env python3
"""Wait until no coding-loop run of a project is running, then print the project's runs and exit.

Exit 0 when the runs stopped (paused, failed, completed or none left); a transient status failure
is retried, never taken as a change. Exit 1 on --timeout.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path


def runs(status_cmd: list[str], project: Path) -> list[dict] | None:
    """The project's coding-loop runs, or None when the status could not be read."""
    try:
        out = subprocess.run(status_cmd, capture_output=True, text=True, timeout=120)
        data = json.loads(out.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    listed = data if isinstance(data, list) else data.get("runs") if isinstance(data, dict) else None
    if not isinstance(listed, list):
        return None
    mine = []
    for r in (r for r in listed if isinstance(r, dict)):
        path = r.get("working_path") or ""
        if path and Path(path).resolve() == project and r.get("workflow_name") == "coding-loop":
            mine.append(r)
    return mine


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--interval", type=float, default=30, help="seconds between checks")
    ap.add_argument("--settle", type=float, default=60, help="seconds to wait first, so a just-sent answer is picked up")
    ap.add_argument("--timeout", type=float, default=0, help="give up after this many seconds (0: never)")
    a = ap.parse_args()
    project = Path(a.project).resolve()
    status_cmd = shlex.split(os.environ.get("ARCHON_STATUS_CMD", "archon workflow status --all --json"))
    start = time.monotonic()
    time.sleep(a.settle)
    while True:
        found = runs(status_cmd, project)
        if found is not None and not any(r.get("status") == "running" for r in found):
            stamp = time.strftime("%H:%M")
            print(f"{stamp} " + ("; ".join(f"{r.get('id')} {r.get('status')}" for r in found) or "no runs"))
            return 0
        if a.timeout and time.monotonic() - start > a.timeout:
            print("timeout: still running", file=sys.stderr)
            return 1
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Append one decision to the monitoring log, so the owner can review every answer later.

Writes "## HH:MM — task <task> — <title>" and the note to --log (created when missing).
Exit 0.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--title", required=True, help="one line: what was asked")
    ap.add_argument("--note", required=True, help="what was answered and why; name any choice the owner should review")
    ap.add_argument("--review", action="store_true", help="mark the entry for the owner's review")
    a = ap.parse_args()
    path = Path(a.log)
    path.parent.mkdir(parents=True, exist_ok=True)
    flag = " — REVIEW" if a.review else ""
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {time.strftime('%H:%M')} — task {a.task} — {a.title}{flag}\n{a.note}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

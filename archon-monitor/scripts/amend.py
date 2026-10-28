#!/usr/bin/env python3
"""Give a sub-phase task more files it may change (a plan amendment), keeping the plan file's format.

Adds each --file to the task's "files" in docs/subtask/phase-<phase>/<subphase>.json (already
listed files are left alone) and prints the new list. Send the answer afterwards with --amended.
Exit 0 when saved, 1 when the plan or task is not found.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def plan_path(project: Path, phase: str, task: str) -> Path:
    major, _, minor = task.partition(".")
    return project / "docs" / "subtask" / f"phase-{phase}" / f"{major}.{int(minor):02d}.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--phase", required=True)
    ap.add_argument("--task", required=True, help="task id, e.g. 11.18")
    ap.add_argument("--file", action="append", required=True, dest="files", help="repo-relative path; repeat")
    a = ap.parse_args()
    path = plan_path(Path(a.project).resolve(), a.phase, a.task)
    if not path.is_file():
        print(f"no sub-phase plan at {path}", file=sys.stderr)
        return 1
    raw = path.read_text(encoding="utf-8")
    doc = json.loads(raw)
    task = next((t for t in doc.get("tasks", []) if t.get("task_id") == a.task), None)
    if task is None:
        print(f"task {a.task} not in {path}", file=sys.stderr)
        return 1
    for f in a.files:
        if f not in task["files"]:
            task["files"].append(f)
    indent = 2 if raw.startswith("{\n  ") else None
    path.write_text(json.dumps(doc, indent=indent, ensure_ascii=False) + ("\n" if raw.endswith("\n") else ""),
                    encoding="utf-8")
    print("\n".join(task["files"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

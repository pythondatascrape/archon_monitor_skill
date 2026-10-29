#!/usr/bin/env python3
"""Amend a sub-phase task's plan (more files it may change, or what its tests are expected to fail with), keeping the plan file's format.

Adds each --file to the task's "files" in docs/subtask/phase-<phase>/<subphase>.json (already
listed files are left alone) and/or sets --expect-failure on the task's tests (all, or those named
with --test), e.g. when the plan expects a build error ("undefined: X") where the loop needs an
assertion failure. Prints the task's files. Send the answer afterwards with --amended.
Exit 0 when saved, 1 when the plan, task or test is not found, 2 when nothing is asked.
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
    ap.add_argument("--file", action="append", default=[], dest="files", help="repo-relative path; repeat")
    ap.add_argument("--expect-failure", help="the text the task's tests now fail with (an assertion's message)")
    ap.add_argument("--test", action="append", default=[], dest="tests", help="only this test's name; repeat")
    a = ap.parse_args()
    if not a.files and a.expect_failure is None:
        ap.error("give --file and/or --expect-failure")
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
    if a.expect_failure is not None:
        chosen = [t for t in task.get("tests", []) if not a.tests or t.get("name") in a.tests]
        missing = set(a.tests) - {t.get("name") for t in chosen}
        if missing or not chosen:
            print(f"task {a.task} has no test {sorted(missing) or 'at all'}", file=sys.stderr)
            return 1
        for t in chosen:
            t["expect_failure"] = a.expect_failure
    indent = 2 if raw.startswith("{\n  ") else None
    path.write_text(json.dumps(doc, indent=indent, ensure_ascii=False) + ("\n" if raw.endswith("\n") else ""),
                    encoding="utf-8")
    print("\n".join(task["files"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

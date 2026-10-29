#!/usr/bin/env python3
"""Amend a sub-phase task's plan (more files it may change, what its tests are expected to fail with, or its commands), keeping the plan file's format.

Adds each --file to the task's "files" in docs/subtask/phase-<phase>/<subphase>.json (already
listed files are left alone) and/or sets --expect-failure on the task's tests (all, or those named
with --test), e.g. when the plan expects a build error ("undefined: X") where the loop needs an
assertion failure. --command OLD NEW rewrites a command the task's gate runs; --drop-command OLD
removes one (e.g. a check that already failed at phase start and whose fix is outside the phase). Prints the task's files. Send the answer afterwards with --amended.
Exit 0 when saved, 1 when the plan, task or test is not found, 2 when nothing is asked.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path


def plan_path(project: Path, phase: str, task: str) -> Path:
    """The sub-phase plan that holds the task (13.5 can be in 13.04.json, not 13.05.json)."""
    folder = project / "docs" / "subtask" / f"phase-{phase}"
    for path in sorted(folder.glob("*.json")):
        try:
            if any(t.get("task_id") == task for t in json.loads(path.read_text(encoding="utf-8")).get("tasks", [])):
                return path
        except (ValueError, AttributeError):
            continue
    return folder / f"{task}.json"


def unfreeze(project: Path, frozen: list, granted: str) -> list:
    """Frozen wins over files in the loop: a glob that covers a granted file becomes the files it
    covers today, less the granted one, so everything else stays frozen."""
    out = []
    tracked = subprocess.run(["git", "ls-files"], cwd=project, capture_output=True, text=True).stdout.split()
    on_disk = {str(p.relative_to(project)) for p in project.rglob("*") if p.is_file() and ".git" not in p.parts}
    for pattern in frozen:
        if pattern == granted:
            continue
        if any(c in pattern for c in "*?[") and fnmatch.fnmatch(granted, pattern):
            out += sorted(f for f in set(tracked) | on_disk if fnmatch.fnmatch(f, pattern) and f != granted)
        else:
            out.append(pattern)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--phase", required=True)
    ap.add_argument("--task", required=True, help="task id, e.g. 11.18")
    ap.add_argument("--file", action="append", default=[], dest="files", help="repo-relative path; repeat")
    ap.add_argument("--expect-failure", help="the text the task's tests now fail with (an assertion's message)")
    ap.add_argument("--test", action="append", default=[], dest="tests", help="only this test's name; repeat")
    ap.add_argument("--command", nargs=2, action="append", default=[], dest="commands", metavar=("OLD", "NEW"),
                    help="rewrite this gate command exactly; repeat")
    ap.add_argument("--drop-command", action="append", default=[], dest="drops", metavar="OLD",
                    help="remove this gate command exactly; repeat")
    a = ap.parse_args()
    if not a.files and a.expect_failure is None and not a.commands and not a.drops:
        ap.error("give --file, --expect-failure, --command and/or --drop-command")
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
        task["frozen"] = unfreeze(Path(a.project).resolve(), task.get("frozen", []), f)
    if a.expect_failure is not None:
        chosen = [t for t in task.get("tests", []) if not a.tests or t.get("name") in a.tests]
        missing = set(a.tests) - {t.get("name") for t in chosen}
        if missing or not chosen:
            print(f"task {a.task} has no test {sorted(missing) or 'at all'}", file=sys.stderr)
            return 1
        for t in chosen:
            t["expect_failure"] = a.expect_failure
    commands = task.get("commands", [])
    text = [c.get("command") if isinstance(c, dict) else c for c in commands]
    missing = [old for old, _ in a.commands if old not in text] + [old for old in a.drops if old not in text]
    if missing:
        print(f"task {a.task} has no command {missing}; it has {text}", file=sys.stderr)
        return 1
    for old, new in a.commands:
        i = text.index(old)
        text[i] = new
        commands[i] = {**commands[i], "command": new} if isinstance(commands[i], dict) else new
    task["commands"] = [c for c, t in zip(commands, text) if t not in a.drops]
    if not commands:
        del task["commands"]
    indent = 2 if raw.startswith("{\n  ") else None
    path.write_text(json.dumps(doc, indent=indent, ensure_ascii=False) + ("\n" if raw.endswith("\n") else ""),
                    encoding="utf-8")
    print("\n".join(task["files"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

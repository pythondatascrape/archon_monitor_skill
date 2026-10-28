#!/usr/bin/env python3
"""Run the loop's own answer handling on a scratch copy of the phase state, to see if a reply would be accepted.

The real run is never touched: the state folder is copied, the controller is loaded from the
installed workflow, and only its absorb_answer step runs. Plan files are read from the project, so
an amendment saved there is checked too.
Exit 0: ACCEPTED (with a note when questions asked ahead are left for their turn). Exit 1: REFUSED, with the loop's "Not accepted" reason. Exit 2: could not check.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _loop  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--phase")
    ap.add_argument("--state-dir", help="the coding-loop state folder (default: under ARCHON_HOME)")
    ap.add_argument("--reply", required=True, help="file holding the reply text")
    ap.add_argument("--decision", default="answer")
    a = ap.parse_args()
    project = Path(a.project).resolve()
    pdir = _loop.phase_dir(project, a.phase, a.state_dir)
    shared = _loop.loop_dir().parent / ".shared"
    sys.path.insert(0, str(shared))
    sys.dont_write_bytecode = True  # never leave __pycache__ in the installed workflow
    try:
        import loop_core  # type: ignore
        from loop_controller import Controller  # type: ignore
    except ImportError as exc:
        print(f"cannot load the coding-loop controller from {shared}: {exc}", file=sys.stderr)
        return 2
    text = Path(a.reply).read_text(encoding="utf-8")
    problem, note = _loop.numbering_problem(_loop.read_state(pdir).get("clarification") or {}, text)
    if problem:
        print(f"REFUSED: {problem}")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp) / "state"
        copy = state / "coding-loop" / pdir.name
        shutil.copytree(pdir, copy, ignore=shutil.ignore_patterns("evidence", "passes"))
        (Path(tmp) / "art").mkdir()
        ctl = Controller(project, _loop.phase_of(pdir), state, Path(tmp) / "art", "precheck")
        paused = ctl.absorb_answer(loop_core.parse_gate(json.dumps({"decision": a.decision, "text": text})))
    if not paused:
        print(f"ACCEPTED ({note})" if note else "ACCEPTED")
        return 0
    lines = paused.get("message", "").splitlines()
    print("REFUSED: " + next((ln for ln in lines if ln.startswith("Not accepted")), " ".join(lines[:3])))
    return 1


if __name__ == "__main__":
    sys.exit(main())

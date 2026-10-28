#!/usr/bin/env python3
"""Print what the paused coding loop is waiting for: the open question with each proposed rule's label.

Exit 0 with the question (or approval request) printed; exit 1 when nothing is waiting.
--json prints {"phase", "state", "task", "kind", "origin", "reason", "questions", "proposals": [{"label", ...}], "ahead"}.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _loop  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--phase")
    ap.add_argument("--state-dir", help="the coding-loop state folder (default: under ARCHON_HOME)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    pdir = _loop.phase_dir(Path(a.project), a.phase, a.state_dir)
    s = _loop.read_state(pdir)
    c = s.get("clarification")
    if s.get("state") == "AWAITING_HUMAN_APPROVAL":
        out = {"phase": _loop.phase_of(pdir), "state": s["state"], "task": None, "kind": "approval",
               "questions": [], "proposals": [], "ahead": {}}
    elif s.get("state") == "AWAITING_CLARIFICATION" and c:
        out = {"phase": _loop.phase_of(pdir), "state": s["state"], "task": c.get("task"), "kind": c.get("kind"),
               "origin": c.get("origin"), "reason": c.get("reason"), "questions": c.get("questions", []),
               "proposals": [{"label": label, **rule} for label, rule in _loop.proposal_labels(c)],
               "ahead": {t: len(q) for t, q in (c.get("ahead") or {}).items()}}
    else:
        print(f"phase {_loop.phase_of(pdir)}: nothing waiting (state {s.get('state')})")
        return 1
    if a.json:
        print(json.dumps(out, indent=1))
        return 0
    print(f"phase {out['phase']} {out['state']} task {out['task']} ({out['kind']}, {out.get('origin')}): {out.get('reason')}")
    for q in out["questions"]:
        print(f"Q: {q}")
    for p in out["proposals"]:
        print(f"  {p['label']}  {p.get('file')} :: {p.get('function')} | {p.get('rule')}")
    if out["ahead"]:
        print("asked ahead (answer optional): " + ", ".join(f"{t} ({n})" for t, n in out["ahead"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

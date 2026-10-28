"""Shared helpers: where an Archon project's coding-loop state lives, and how to read it."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path


def archon_home() -> Path:
    return Path(os.environ.get("ARCHON_HOME", Path.home() / ".archon"))


def loop_dir() -> Path:
    """The coding-loop workflow: its tools/ and the controller code in ../.shared/."""
    return archon_home() / "workflows" / "tasks" / "coding-loop"


def state_root(project: Path, override: str | None = None) -> Path:
    """<archon home>/workspaces/_folder/<project folder name>/state/coding-loop, unless overridden."""
    if override:
        return Path(override)
    return archon_home() / "workspaces" / "_folder" / project.resolve().name / "state" / "coding-loop"


def phase_dir(project: Path, phase: str | None, override: str | None = None) -> Path:
    """The phase's state folder; without a phase, the one whose state.json changed last."""
    root = state_root(project, override)
    if phase:
        return root / f"phase-{phase}"
    found = sorted(root.glob("phase-*/state.json"), key=lambda p: p.stat().st_mtime)
    if not found:
        raise SystemExit(f"no coding-loop state under {root}")
    return found[-1].parent


def phase_of(pdir: Path) -> str:
    match = re.fullmatch(r"phase-(.+)", pdir.name)
    return match.group(1) if match else ""


def read_state(pdir: Path) -> dict:
    return json.loads((pdir / "state.json").read_text(encoding="utf-8"))


def proposal_labels(clarification: dict) -> list[tuple[str, dict]]:
    """Each proposed rule with the label the loop accepts for it: 1a, 1b, 2a, ... in question order."""
    out = []
    for i, (_, rules) in enumerate((clarification.get("proposals") or {}).items(), 1):
        for j, rule in enumerate(rules):
            out.append((f"{i}{chr(97 + j)}", rule))
    return out


def asked_ahead(clarification: dict) -> list[dict]:
    """Questions coders working ahead asked for later tasks, numbered on after this task's own, as
    the loop shows them. A reply numbered through them gives each later task its answer, so the
    loop can code it ahead again."""
    n = len(clarification.get("questions") or [])
    joined = [(t, q) for t, qs in (clarification.get("ahead") or {}).items() for q in qs]
    return [{"number": i, "task": t, "question": q} for i, (t, q) in enumerate(joined, n + 1)]


NUMBERED = re.compile(r"(?m)^[ \t]*(\d+)[.)][ \t]")  # how the loop finds a reply's numbered answers


def numbering_problem(clarification: dict, text: str) -> tuple[str, str]:
    """('', note) when the reply is numbered as the loop splits it, else (problem, ''). With
    questions asked ahead the loop takes 1..own (they wait for their turn, named in note) or
    1..own+ahead (each later task gets its part), or an unnumbered reply (all of it is this task's);
    numbering that stops between the two is refused."""
    ahead = asked_ahead(clarification)
    if not ahead:
        return "", ""
    own = len(clarification.get("questions") or [])
    total = own + len(ahead)
    got = [int(m.group(1)) for m in NUMBERED.finditer(text)]
    if got == list(range(1, total + 1)):
        return "", ""
    if got in ([], list(range(1, own + 1))):  # unnumbered: the loop gives it all to this task
        return "", "asked ahead, left for their turn: " + ", ".join(dict.fromkeys(a["task"] for a in ahead))
    shown = f"1-{max(got)}" if got else "no numbers"
    return (f"number the reply 1-{own} (this task) or 1-{total} (with the questions asked ahead), "
            f"got {shown}"), ""

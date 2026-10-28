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

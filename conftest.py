"""Fixtures for this skill's tests: a throwaway project, a fake Archon home with a paused phase, and a fake controller."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent / "archon-monitor"

# A stand-in for the coding loop's controller: refuses an unknown rule label, accepts anything else.
FAKE_CORE = "import json\n\ndef parse_gate(raw):\n    d = json.loads(raw)\n    return {'decision': d['decision'], 'text': d['text']}\n"
FAKE_CONTROLLER = textwrap.dedent('''
    import json, re
    from pathlib import Path

    class Controller:
        def __init__(self, root, phase, state_dir, artifacts_dir, run_id):
            self.dir = Path(state_dir) / "coding-loop" / f"phase-{phase}"
            self.s = json.loads((self.dir / "state.json").read_text())

        def absorb_answer(self, gate):
            labels = {f"{i}{chr(97 + j)}" for i, rules in enumerate(self.s["clarification"]["proposals"].values(), 1)
                      for j in range(len(rules))}
            for used in re.findall(r"^(\\d+[a-z])\\b", gate["text"], re.M):
                if used not in labels:
                    return {"kind": "pause", "message": f"Reply ...\\nNot accepted: {used} is not a proposed rule.\\nQ..."}
            self.s["state"] = "TEST_AUTHORING"
            return None
''')


def run(script: str, *args, cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SKILL / "scripts" / script), *args], cwd=cwd,
                          capture_output=True, text=True, env={**os.environ, **(env or {})})


@pytest.fixture
def world(tmp_path):
    """A project "proj", an Archon home whose phase 07 is paused on a two-question clarification, and a fake controller."""
    project = tmp_path / "proj"
    plan = project / "docs" / "subtask" / "phase-07"
    plan.mkdir(parents=True)
    (plan / "07.03.json").write_text(json.dumps({"tasks": [{"task_id": "07.3", "files": ["src/a.py"]}]}, indent=2) + "\n")
    home = tmp_path / "archon"
    shared = home / "workflows" / "tasks" / ".shared"
    shared.mkdir(parents=True)
    (shared / "loop_core.py").write_text(FAKE_CORE)
    (shared / "loop_controller.py").write_text(FAKE_CONTROLLER)
    pdir = home / "workspaces" / "_folder" / "proj" / "state" / "coding-loop" / "phase-07"
    pdir.mkdir(parents=True)
    (pdir / "evidence").mkdir()
    (pdir / "state.json").write_text(json.dumps({"state": "AWAITING_CLARIFICATION", "clarification": {
        "task": "07.3", "kind": "coder", "origin": "TEST_AUTHORING", "reason": "needs information",
        "questions": ["1. Which column?", "2. Which default?"],
        "proposals": {"1. Which column?": [{"file": "m.sql", "function": "t", "rule": "add c"},
                                           {"file": "m.sql", "function": "t", "rule": "index c"}],
                      "2. Which default?": [{"file": "m.sql", "function": "t", "rule": "default 0"}]},
        "ahead": {"07.4": ["a question"]}}}))
    return {"project": project, "home": home, "phase": pdir, "env": {"ARCHON_HOME": str(home)}}

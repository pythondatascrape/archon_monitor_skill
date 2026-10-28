import json
import stat

from conftest import run


def test_pending_lists_questions_and_rule_labels(world):
    r = run("pending.py", str(world["project"]), "--json", cwd=world["project"], env=world["env"])
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert (out["phase"], out["task"], out["kind"]) == ("07", "07.3", "coder")
    assert [p["label"] for p in out["proposals"]] == ["1a", "1b", "2a"]
    assert out["ahead"] == {"07.4": 1}


def test_pending_says_nothing_waiting(world):
    s = json.loads((world["phase"] / "state.json").read_text())
    s.update(state="IMPLEMENTATION", clarification=None)
    (world["phase"] / "state.json").write_text(json.dumps(s))
    r = run("pending.py", str(world["project"]), cwd=world["project"], env=world["env"])
    assert r.returncode == 1 and "nothing waiting" in r.stdout


def test_precheck_accepts_known_labels_and_leaves_real_state_alone(world, tmp_path):
    reply = tmp_path / "reply.txt"
    reply.write_text("1. Column c.\n1a OK\n1b OK\n2. Zero.\n2a OK\n")
    before = (world["phase"] / "state.json").read_text()
    r = run("precheck.py", str(world["project"]), "--reply", str(reply), cwd=world["project"], env=world["env"])
    assert r.returncode == 0 and r.stdout.strip() == "ACCEPTED", r.stdout + r.stderr
    assert (world["phase"] / "state.json").read_text() == before
    assert not list((world["home"] / "workflows").rglob("__pycache__"))


def test_precheck_reports_the_loops_refusal(world, tmp_path):
    reply = tmp_path / "reply.txt"
    reply.write_text("1a OK\n2a OK\n2b: an extra rule\n")
    r = run("precheck.py", str(world["project"]), "--reply", str(reply), cwd=world["project"], env=world["env"])
    assert r.returncode == 1 and "REFUSED: Not accepted: 2b is not a proposed rule." in r.stdout


def test_amend_adds_files_once_and_keeps_format(world):
    args = ("amend.py", str(world["project"]), "--phase", "07", "--task", "07.3")
    r = run(*args, "--file", "src/b.py", "--file", "src/a.py", cwd=world["project"])
    assert r.returncode == 0, r.stderr
    plan = world["project"] / "docs" / "subtask" / "phase-07" / "07.03.json"
    text = plan.read_text()
    assert json.loads(text)["tasks"][0]["files"] == ["src/a.py", "src/b.py"]
    assert text.startswith("{\n  ") and text.endswith("\n")


def test_amend_unknown_task_fails(world):
    r = run("amend.py", str(world["project"]), "--phase", "07", "--task", "07.9", "--file", "x", cwd=world["project"])
    assert r.returncode == 1


def test_log_appends_entries_marked_for_review(tmp_path):
    log = tmp_path / "logs" / "night.md"
    run("log.py", "--log", str(log), "--task", "07.3", "--title", "migration", "--note", "kept 1a", cwd=tmp_path)
    run("log.py", "--log", str(log), "--task", "07.4", "--title", "rule change", "--note", "dropped X", "--review",
        cwd=tmp_path)
    text = log.read_text()
    assert "task 07.3 — migration\nkept 1a" in text and "task 07.4 — rule change — REVIEW\ndropped X" in text


def fake_status(tmp_path, statuses):
    """A status command that prints the next listed status on each call."""
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps(statuses))
    script = tmp_path / "status.py"
    script.write_text(
        "import json, sys\n"
        f"q = json.load(open({str(queue)!r}))\n"
        "s = q.pop(0) if len(q) > 1 else q[0]\n"
        f"json.dump(q, open({str(queue)!r}, 'w'))\n"
        "print(json.dumps(s))\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return f"python3 {script}"


def test_watch_returns_when_the_run_stops(world, tmp_path):
    proj = str(world["project"].resolve())
    running = [{"id": "r1", "workflow_name": "coding-loop", "status": "running", "working_path": proj}]
    paused = [{"id": "r1", "workflow_name": "coding-loop", "status": "paused", "working_path": proj}]
    other = [{"id": "x", "workflow_name": "coding-loop", "status": "running", "working_path": "/elsewhere"}]
    cmd = fake_status(tmp_path, [running + other, "not json", paused + other])
    r = run("watch.py", proj, "--settle", "0", "--interval", "0.01", cwd=world["project"],
            env={"ARCHON_STATUS_CMD": cmd})
    assert r.returncode == 0, r.stderr
    assert "r1 paused" in r.stdout and "x" not in r.stdout.split(" ", 1)[1]


def test_watch_times_out_while_running(world, tmp_path):
    proj = str(world["project"].resolve())
    cmd = fake_status(tmp_path, [[{"id": "r1", "workflow_name": "coding-loop", "status": "running", "working_path": proj}]])
    r = run("watch.py", proj, "--settle", "0", "--interval", "0.01", "--timeout", "0.2", cwd=world["project"],
            env={"ARCHON_STATUS_CMD": cmd})
    assert r.returncode == 1

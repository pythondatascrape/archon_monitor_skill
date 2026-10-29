import json
import stat

from conftest import run


def test_pending_lists_questions_and_rule_labels(world):
    r = run("pending.py", str(world["project"]), "--json", cwd=world["project"], env=world["env"])
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert (out["phase"], out["task"], out["kind"]) == ("07", "07.3", "coder")
    assert [p["label"] for p in out["proposals"]] == ["1a", "1b", "2a"]
    assert out["ahead"] == [{"number": 3, "task": "07.4", "question": "a question"}]


def test_pending_numbers_questions_asked_ahead_after_the_tasks_own(world):
    r = run("pending.py", str(world["project"]), cwd=world["project"], env=world["env"])
    assert r.returncode == 0 and "  3. [07.4] a question" in r.stdout


def precheck(world, tmp_path, text):
    reply = tmp_path / "reply.txt"
    reply.write_text(text)
    return run("precheck.py", str(world["project"]), "--reply", str(reply), cwd=world["project"], env=world["env"])


def test_precheck_accepts_a_reply_numbered_through_the_questions_asked_ahead(world, tmp_path):
    r = precheck(world, tmp_path, "1. Column c.\n1a OK\n1b OK\n2. Zero.\n2a OK\n3. Round half up.\n")
    assert r.returncode == 0 and r.stdout.strip() == "ACCEPTED", r.stdout + r.stderr


def test_precheck_marks_questions_asked_ahead_left_for_their_turn(world, tmp_path):
    r = precheck(world, tmp_path, "1. Column c.\n1a OK\n1b OK\n2. Zero.\n2a OK\n")
    assert r.returncode == 0 and r.stdout.strip() == "ACCEPTED (asked ahead, left for their turn: 07.4)"


def test_precheck_refuses_a_reply_numbered_partway_through(world, tmp_path):
    s = json.loads((world["phase"] / "state.json").read_text())
    s["clarification"]["ahead"]["07.5"] = ["another"]
    (world["phase"] / "state.json").write_text(json.dumps(s))
    r = precheck(world, tmp_path, "1. Column c.\n1a OK\n1b OK\n2. Zero.\n2a OK\n3. Round half up.\n")
    assert r.returncode == 1
    assert "REFUSED: number the reply 1-2 (this task) or 1-4 (with the questions asked ahead), got 1-3" in r.stdout


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
    assert r.returncode == 0 and r.stdout.startswith("ACCEPTED"), r.stdout + r.stderr
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


def test_amend_sets_a_tests_expected_failure(world):
    """Phase 13 (2026-10-29): a plan expected a build error ("undefined: X") where the loop needs an
    assertion failure; swarzy could only add files, so it left a fixable plan to the owner."""
    plan = world["project"] / "docs" / "subtask" / "phase-07" / "07.03.json"
    doc = json.loads(plan.read_text())
    doc["tasks"][0]["tests"] = [{"name": "test_a", "file": "tests/test_a.py", "expect_failure": "undefined: X"},
                                {"name": "test_b", "file": "tests/test_a.py", "expect_failure": "undefined: X"}]
    plan.write_text(json.dumps(doc, indent=2) + "\n")
    r = run("amend.py", str(world["project"]), "--phase", "07", "--task", "07.3", "--file", "src/x.py",
            "--expect-failure", "want", cwd=world["project"])
    assert r.returncode == 0, r.stderr
    t = json.loads(plan.read_text())["tasks"][0]
    assert [x["expect_failure"] for x in t["tests"]] == ["want", "want"] and "src/x.py" in t["files"]
    r = run("amend.py", str(world["project"]), "--phase", "07", "--task", "07.3", "--test", "test_b",
            "--expect-failure", "assert", cwd=world["project"])
    assert r.returncode == 0, r.stderr
    assert [x["expect_failure"] for x in json.loads(plan.read_text())["tasks"][0]["tests"]] == ["want", "assert"]


def test_amend_finds_a_task_in_any_sub_phase_and_unfreezes_only_the_granted_file(world):
    """Phase 13 (2026-10-29): task 13.5 lives in 13.04.json, not 13.05.json, so amend.py found no
    plan; and the granted file matched the task's frozen 'internal/retrieval/*_test.go', which wins."""
    root = world["project"]
    for f in ("pkg/a_test.py", "pkg/b_test.py", "pkg/c_test.py"):
        (root / f).parent.mkdir(parents=True, exist_ok=True)
        (root / f).write_text("x\n")
    sub = root / "docs" / "subtask" / "phase-07" / "07.02.json"
    sub.write_text(json.dumps({"tasks": [{"task_id": "07.5", "files": ["pkg/a.py"],
                                          "frozen": ["docs/*", "pkg/*_test.py"]}]}, indent=2) + "\n")
    r = run("amend.py", str(root), "--phase", "07", "--task", "07.5", "--file", "pkg/b_test.py", cwd=root)
    assert r.returncode == 0, r.stderr
    t = json.loads(sub.read_text())["tasks"][0]
    assert t["files"] == ["pkg/a.py", "pkg/b_test.py"]
    assert t["frozen"] == ["docs/*", "pkg/a_test.py", "pkg/c_test.py"]


def test_amend_needs_a_change(world):
    r = run("amend.py", str(world["project"]), "--phase", "07", "--task", "07.3", cwd=world["project"])
    assert r.returncode == 2


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


def test_watch_until_running_returns_when_a_run_starts_again(world, tmp_path):
    proj = str(world["project"].resolve())
    failed = [{"id": "r1", "workflow_name": "coding-loop", "status": "failed", "working_path": proj}]
    other = [{"id": "x", "workflow_name": "coding-loop", "status": "running", "working_path": "/elsewhere"}]
    started = failed + [{"id": "r2", "workflow_name": "coding-loop", "status": "running", "working_path": proj}]
    cmd = fake_status(tmp_path, [failed + other, "not json", started])
    r = run("watch.py", proj, "--until", "running", "--settle", "0", "--interval", "0.01", cwd=world["project"],
            env={"ARCHON_STATUS_CMD": cmd})
    assert r.returncode == 0, r.stderr
    assert "r2 running" in r.stdout and "r1" not in r.stdout and "x" not in r.stdout.split(" ", 1)[1]


def test_watch_until_running_times_out_while_stopped(world, tmp_path):
    proj = str(world["project"].resolve())
    cmd = fake_status(tmp_path, [[{"id": "r1", "workflow_name": "coding-loop", "status": "failed", "working_path": proj}]])
    r = run("watch.py", proj, "--until", "running", "--settle", "0", "--interval", "0.01", "--timeout", "0.2",
            cwd=world["project"], env={"ARCHON_STATUS_CMD": cmd})
    assert r.returncode == 1

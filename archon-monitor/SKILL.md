---
name: archon-monitor
description: Watch an Archon coding-loop run and answer its pauses for the owner: clarification questions, out-of-attempts stops and plan gaps, each answer grounded in the phase plan and the code, pre-checked against the loop's own controller, sent with the loop's answer tool, and logged for the owner's review. Use when the owner asks you to monitor, babysit or answer a coding-loop run (for example "watch the loop while I sleep", "answer its questions").
---

Scripts take the project folder (default `.`); state is read from `$ARCHON_HOME` (default `~/.archon`).

- `python3 ${CLAUDE_SKILL_DIR}/scripts/watch.py <project>`: waits until the project's coding-loop run stops running, then prints it. Run it in the background; it returns when there is a pause to handle.
- `python3 ${CLAUDE_SKILL_DIR}/scripts/watch.py <project> --until running`: after a run failed or was stopped with nothing waiting, waits until a run of the project starts again, then prints it. Then carry on watching that run.
- `python3 ${CLAUDE_SKILL_DIR}/scripts/pending.py <project>`: the open question, each proposed rule with the label the loop accepts (`1a`, `1b`, `2a` ...), and the questions asked ahead for later tasks, numbered on. Exit 1 when nothing is waiting.
- `python3 ${CLAUDE_SKILL_DIR}/scripts/precheck.py <project> --reply <file>`: runs the loop's own answer handling on a scratch copy of the state. Exit 0 `ACCEPTED` (with a note naming tasks whose questions asked ahead were left for their turn), exit 1 `REFUSED: <the reason>`.
- `python3 ${CLAUDE_SKILL_DIR}/scripts/amend.py <project> --phase <xx> --task <id> [--file <path> ...] [--expect-failure <text> [--test <name> ...]] [--command <old> <new> ...] [--drop-command <old> ...]`: adds files a task may change to its sub-phase plan, sets what its tests are expected to fail with, and/or rewrites or removes a command its gate runs.
- `python3 ${CLAUDE_SKILL_DIR}/scripts/log.py --log <file> --task <id> --title <line> --note <text> [--review]`: appends one decision to the log.
- Send with the loop's own tool: `python3 $ARCHON_HOME/workflows/tasks/coding-loop/tools/answer.py <project> --phase <xx> --file <reply> [--amended]`. It waits for the controller and prints `ACCEPTED`.

## Each pause

1. `pending.py`. Read every question and proposal.
2. Gather the facts before deciding, never from memory:
   - the phase document and the task's sub-phase plan (`docs/subtask/phase-<xx>/<task>.json`: its files, rules, tests);
   - the earlier answers already given this run (the state's `answer_items`), so a new answer never contradicts one (a percentage stays a percentage, a default stays the same);
   - the code the question names: functions, tables, columns, callers and the existing tests that pin them.
3. Write the reply to a file, one line per numbered question, then the proposal marks:
   - `1a OK` keeps a rule; `1a: <rule>` replaces it; `1a REJECT` drops it.
   - Mark only labels `pending.py` printed. A new label (for example `3b` when only `3a` exists) is refused.
   - Answer the questions asked ahead for later tasks too: `pending.py` lists them numbered on after this task's own. One line each, numbered through to the last, grounded in that later task's sub-phase plan. Each later task gets its answer and is coded ahead again instead of waiting.
   - Only when one of them cannot be grounded, number just this task's questions: all of them then wait for their own turn. `precheck.py` refuses numbering that stops partway.
4. `precheck.py`; fix the reply until it prints `ACCEPTED`.
5. Send with `answer.py` (with `--amended` after `amend.py`), then `log.py`, then `watch.py` again.

## How to decide

- The phase document, the approved design and earlier answers win over a coder's proposal. Correct a proposal that drifts from them, and say which earlier answer you follow.
- Prefer the smallest change that keeps existing behaviour and tests valid. When an existing test pins a function's arguments or output, add optional arguments, or put new work beside the pinned function instead of inside it.
- A task needs a file outside its list (a caller to wire, a test that pins old behaviour): amend the plan with `amend.py` and name the exact parts it may change. Search the suite for every test that depends on the old behaviour, so the question does not come back.
- A plan the loop's own gate can never accept is yours to fix, never the owner's: amend it and answer. Example (phase 13, 2026-10-29): a Go test task expected "undefined: ClaimJaccard", a build error, but RED must fail at an assertion. Fix: give the test task the source file too (`--file`) for a stub that returns zero values, set `--expect-failure` to the assertion's text (e.g. `want`), and tell the coder to write the stub; the implementing task fills it in. Log it with `--review`.
- A gate command the plan states in a way that can never pass (it runs every package at once and a timing check fails under that load): rewrite it with `amend.py --command`, the way earlier phases ran it. Telling the coder to run it differently does nothing: the loop reruns the plan's own command. Example (phase 13, 2026-10-29): `go test -json ./... > testdata/results/phase-13.jsonl` became `go test -p 1 -json ./... > ...`, as phases 09 and 10 did.
- A gate command that fails for a reason the phase did not cause and cannot fix: `pending.py` lists it under `phase_start_failures` (it already failed before the phase changed anything). Drop it from the task with `amend.py --drop-command`, answer, and log it with `--review` naming the fix the owner should queue as its own change. Never leave it to the owner. Example (phase 13): `make vuln` failed on a flaw in Go 1.27.2 itself; the fix (Go 1.27.3) changes frozen files, so the check was dropped for the run and the upgrade queued.
- Something the plan promises but no task builds (a feature that is defined but never called or scheduled): treat it as a gap. Give it to the current task with an amendment, and log it for review.
- A changed rule from an earlier phase (security, visibility, retention): check every code path it touches first, then log the change with `--review`.
- Never invent facts the code or plan does not hold (a version, a date, a host list). Say it is unrecorded, choose the safe default, and log it for review.

## A rule check (Jev) flag

Since 2026-10-29 the loop limits Jev itself: a standards flag (S-xx) never fails the gate, it goes
to the adversarial review; a plan or answer rule fails a task once, and every later flag in that
task goes to the review. The loop's message says this. So Jev alone cannot run a task out of
attempts; an out-of-attempts pause is a test or check failure, answered as such.
- Never answer a Jev flag by asking for another attempt, a rule change or an exemption: the review decides.
- If the coder asks whether a flag is real, read the flagged function. It already satisfies the rule: say so and to make the check visible in that function. A real gap (an uncaught error on malformed input, an unchecked path segment): fix just that function, add no new or renamed function, and add one test for the case.

## Logging

Log every answer: what was asked, what was decided, and any choice the owner may want to change (`--review`): design changes, earlier-phase rules changed, defaults chosen without a stated value, features dropped from an approved design. Never print tokens or secrets in replies or logs.

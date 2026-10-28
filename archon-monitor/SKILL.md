---
name: archon-monitor
description: Watch an Archon coding-loop run and answer its pauses for the owner: clarification questions, out-of-attempts stops and plan gaps, each answer grounded in the phase plan and the code, pre-checked against the loop's own controller, sent with the loop's answer tool, and logged for the owner's review. Use when the owner asks you to monitor, babysit or answer a coding-loop run (for example "watch the loop while I sleep", "answer its questions").
---

Scripts take the project folder (default `.`); state is read from `$ARCHON_HOME` (default `~/.archon`).

- `python3 ${CLAUDE_SKILL_DIR}/scripts/watch.py <project>`: waits until the project's coding-loop run stops running, then prints it. Run it in the background; it returns when there is a pause to handle.
- `python3 ${CLAUDE_SKILL_DIR}/scripts/pending.py <project>`: the open question, each proposed rule with the label the loop accepts (`1a`, `1b`, `2a` ...), and the questions asked ahead for later tasks, numbered on. Exit 1 when nothing is waiting.
- `python3 ${CLAUDE_SKILL_DIR}/scripts/precheck.py <project> --reply <file>`: runs the loop's own answer handling on a scratch copy of the state. Exit 0 `ACCEPTED` (with a note naming tasks whose questions asked ahead were left for their turn), exit 1 `REFUSED: <the reason>`.
- `python3 ${CLAUDE_SKILL_DIR}/scripts/amend.py <project> --phase <xx> --task <id> --file <path> [--file ...]`: adds files a task may change to its sub-phase plan.
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
- Something the plan promises but no task builds (a feature that is defined but never called or scheduled): treat it as a gap. Give it to the current task with an amendment, and log it for review.
- A changed rule from an earlier phase (security, visibility, retention): check every code path it touches first, then log the change with `--review`.
- Never invent facts the code or plan does not hold (a version, a date, a host list). Say it is unrecorded, choose the safe default, and log it for review.

## Out of attempts on a rule check (Jev)

The rule check fails a task once per function and rule; a new or renamed function gets a fresh failure, which is how a task runs out of attempts without a real bug.
- Read the flagged function. If it already satisfies the rule, the flag is a false alarm: make the check visible inside that function.
- If there is a real gap (an uncaught error on malformed input, an unchecked path segment), fix just that.
- Either way: change only the flagged function's body and docstring, add no new, renamed or split function, and add one test for the case. A repeat flag on the same function then goes to the adversarial review instead of failing the gate.

## Logging

Log every answer: what was asked, what was decided, and any choice the owner may want to change (`--review`): design changes, earlier-phase rules changed, defaults chosen without a stated value, features dropped from an approved design. Never print tokens or secrets in replies or logs.

# Build notes — issue 14 / input-mode-prefix-dispatch (iteration 3)

Target: eduralph/nl-shell @ main (`e7bb63c`). Worktree: `$PDCA_WORKTREE`
(`/home/eddie/nl-shell/nl-shell.pdca-wt-l1`). Line numbers below are on the patched tree
unless they say `main`.

## What this round changes

This round starts from the iteration-2 patch (`iteration-v2/patch.diff`) and fixes the
one finding carried forward: `: quit` / `: exit` were called "unknown meta-command :quit"
while that same reply listed `:quit` as known.

Cause: the exit check matched the raw stripped line against the set
`{":quit", ":exit"}` (`src/nl_shell/repl.py:60` on `main`, kept by v2). Iteration 2 made
the `:` payload stripped (`parse`, `src/nl_shell/input_modes.py:55-64`), so `: status`
works, but the exit commands did not follow that rule.

Fix: the exit check now goes through the same parse as every other meta-command.

- `src/nl_shell/input_modes.py:25-27`: `EXIT_COMMANDS` (raw strings) is replaced with
  `EXIT_NAMES = ("quit", "exit")`, the bare names. It's a tuple, not a frozenset, so the
  "Known:" list keeps a fixed order.
- `src/nl_shell/input_modes.py:67-74`: new `is_exit(text)`. It's true when the parsed line
  is in `Mode.META` and its payload is in `EXIT_NAMES`.
- `src/nl_shell/input_modes.py:112`: `known_meta_commands()` builds the list from
  `META_COMMANDS` plus `EXIT_NAMES`, so the list of known commands and the exit check
  come from the same tuple and can't drift apart.
- `src/nl_shell/input_modes.py:101-103`: the comment now points at `is_exit`.
- `src/nl_shell/repl.py:17,62`: the loop calls `input_modes.is_exit(text)` instead of
  `text in EXIT_COMMANDS`. The check order is the same as in the brief's Design: strip →
  blank → exit → prefix dispatch → router.
- `tests/test_input_modes.py:182-188`: `test_exit_commands_still_stop_the_loop` gains the
  rows `": quit"` and `":  exit"`, as the finding asked.

The reviewer suggested two fixes. I took the first one (check the parsed META payload). The
second one ("at least leave them out of the unknown reply") was rejected because it only
hides the symptom: `: quit` would still not exit, and it would get a reply that no longer
lists the command the user meant. The first fix removes the cause and is about 10 lines.

Exit matching stays exact and case-sensitive, like the other meta-commands: `:Quit` and
`:quitx` are unknown. `\:quit` is a `\` command, not an exit.

## Carried from iterations 1–2 (unchanged this round)

- New module `src/nl_shell/input_modes.py`: prefix parse (`@@` before `@`,
  `input_modes.py:45-51`), the `STATUS_LINES` extension point (`input_modes.py:80-82`),
  the fixed replies, `META_COMMANDS` (`input_modes.py:104-108`), and `reply()`
  (`input_modes.py:131`).
- `src/nl_shell/repl.py:66-77` `_reply`: `\cmd` with a payload returns the existing
  `COMMAND_NOT_YET` (`repl.py` on `main` lines 19-22), with the ADR-0013 §7 / #64 comment.
  Plain input still goes to `route()` and gets byte-identical replies, so
  `tests/test_repl.py` passes unchanged.
- From iteration 1: the payload is stripped for every prefix, and the `:status` table row
  checks only the first line, so appending to `STATUS_LINES` doesn't break it.

## Verification (through the project's runners)

- C4 `engine/scripts/run-verify.sh` (with `PDCA_BUNDLE` and `PDCA_WORKTREE` set): green
  leg 29/29 passed. Red leg (production hunks reverted): 23 of 29 failed, 0 import errors.
  Result: `PDCA-EVIDENCE: C4 PASS`.
- T3 `engine/scripts/run-suite.sh`: 177 passed.
- After the runs, the worktree diff is byte-identical to `patch.diff`.

## Self-refutation

- **(a) Genuine red? Yes.** With the production hunks reverted, 23 of 29 tests fail
  (`\frobnicate`, `?why`, `@…`, `@@…`, every `:` row, all five bare-prefix usage rows, both
  `:status` tests, the extension test, and the new `: quit` / `:  exit` rows). The 6 that pass on `main`
  are expected to: `\ls -la` (the brief says it proves nothing alone), the two plain-input
  rows `ls -la` and `show disk usage`, `test_replies_are_distinct`, and `:quit` /
  `:exit`. Bare `:` fails on `main` here, even though the brief expected it to pass: on
  `main` it gets the command reply, and the test pins the usage reply instead. Against the
  iteration-2 code, the new `: quit` rows also fail: `": quit" not in {":quit", ":exit"}`,
  so the line reaches dispatch, which prints the unknown reply, and `out == ""` fails.
  The reviewer reproduced that on the v2 tree. I did not re-run it myself, because the
  runner only reverts to `main`, not to v2.
- **(b) Production path? Yes.** Every test drives the real `Repl(...).run()` loop with a
  scripted read function. The only module-level import is `nl_shell.repl.Repl`.
  `input_modes` is imported inside the extension test, and that test uses the real
  `STATUS_LINES` list.
- **(c) Fixture includes the fault? Yes.** The fault is "an exit command written with a
  space after `:`". The fixture feeds exactly `": quit"` and `":  exit"`, followed by
  `":status"`. If the loop did not exit, `:status` (or the unknown reply) would show up in
  the output, and `out == ""` catches that.

## Commit-readiness

The target has no formatter or commit hooks: there is no `.pre-commit-config.yaml`, and
`pyproject.toml` has no ruff or black section. Ruff isn't installed in the instance venv
either. I matched the surrounding style by hand: lines are 92 characters or fewer, the
imports follow the file's existing order, and type hints match the rest of the file.

## Deferred

The six findings in `deferred-findings.json` need a human decision. They were not handled
here, as the carry-forward said.

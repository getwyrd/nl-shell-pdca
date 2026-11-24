# Build notes — issue 14 / input-mode-prefix-dispatch

Target: eduralph/nl-shell @ main (worktree base `e7bb63c`). Line numbers below are
`main` for old code and the patched worktree for new code.

## What changed

- **New `src/nl_shell/input_modes.py`** — the prefix dispatch as its own unit, apart from
  `nl_shell.router` (brief Scope / Alternatives: the router stays the plain-input
  heuristic #40 replaces).
  - `PREFIXES` (`input_modes.py:44-50`) lists `@@` before `@`; `parse()` (`:53-63`)
    returns `Prefixed(mode, payload)` or `None`. Payload is stripped, except for `:`,
    where it is the name as typed so matching is exact and case-sensitive
    (`:statusx`, `:Status`, `: status` are all unknown).
  - `STATUS_LINES` (`:69-71`) — the extension point: a module-level list of zero-argument
    callables, one line each; `status()` (`:74-75`) joins them in list order. Starts with
    `nl-shell {nl_shell.__version__}`. #92 / #16 / #77 just append.
  - `META_COMMANDS` (`:92-96`) maps `context` / `history` / `status`; `:quit` / `:exit`
    stay in the loop and are only listed as known (`known_meta_commands()`, `:99-100`).
  - Fixed replies (`:78-88`) each name their milestone/issue; one usage reply per bare
    prefix (`USAGE`, `:103-110`; `:` usage built in `reply()`).
  - `EXIT_COMMANDS` moved here (`:25`) from `repl.py:18` on main, so the unknown-meta
    reply and the loop share one source; `repl.py:17` re-imports it, so
    `nl_shell.repl.EXIT_COMMANDS` still exists.
- **`src/nl_shell/repl.py`** — the wiring point the brief names (`repl.py:57-62` on main).
  The loop body keeps strip → blank → exit (`repl.py:59-63`) and now calls
  `Repl._reply` (`repl.py:64`, `:66-77`): prefix dispatch first, router only when there is
  no prefix. A `\cmd` with a payload returns the existing `COMMAND_NOT_YET` via
  `REPLIES[Route.COMMAND]`, with the comment citing ADR-0013 §7 (Proposed) and #64 / #78
  (`repl.py:73-75`). `COMMAND_NOT_YET` / `NATURAL_LANGUAGE_NOT_YET` are untouched, so
  plain-input replies are byte-identical and `tests/test_repl.py` passes unchanged.
- No change to `cli.py`, `router.py`, docs, or the architecture table (all out of scope).

## Why the command route stays in `repl.py`

`COMMAND_NOT_YET` lives in `repl.py`, and `repl.py` imports `input_modes`. Having
`input_modes` return that reply would need either a circular import or moving the
constant (touching the plain-input reply table the brief wants left alone). Instead
`input_modes.reply()` covers every mode except a non-empty `\` command, and the REPL hands
that case to its own command route. That is also where #78 will hand the payload to the
gate, so the split matches the next step. Cost of the alternative (move both reply
constants into `input_modes`): about 12 moved lines plus a re-export in `repl.py` — not
much bigger, but it changes where the plain-input replies live for no gain in this issue.

## Choices the brief left open

- Unknown meta reply includes the typed name: `Unknown meta-command :frobnicate. Known:
  :context, :history, :status, :quit, :exit.` Still a fixed literal for a given input,
  pinned in the test.
- `\` usage reply uses `\<command>`; all usage replies start with `Usage:`.

## Test — `tests/test_input_modes.py`

Imports only `Repl` at module level; helpers copied from `tests/test_repl.py:20-57`;
every reply is a literal. `nl_shell.input_modes` is imported only inside
`test_status_lines_can_be_extended`, and `nl_shell` (exists on main) inside the version
test. `test_replies_are_distinct` checks the 14 literals are all different (dict size).

## Red → green (project runner)

`engine/scripts/run-verify.sh` with `PDCA_BUNDLE` / `PDCA_WORKTREE` set:

```
15 failed, 6 passed in 0.11s
   (pytest exit 1; ran 21, failed 15, setup errors 0, import/collection errors 0)
PDCA-EVIDENCE: C4 PASS — red without the fix (15 of 21 failed), green with it
```

`engine/scripts/run-suite.sh`: `169 passed in 4.31s`, `T3 PASS`.

The 6 that pass on main, as the brief predicted: `\ls -la`, `ls -la`, `show disk usage`,
`:quit`, `:exit`, and the distinct-literals check. Bare `:` fails on main only because the
usage reply is new (the `:` builtin routes it as a command there).

## Self-refutation

- **(a) Genuine red?** Yes. The C4 red leg reverted `src/` and re-ran: 15 of 21 failed
  with no import error, including the brief's red rows — `\frobnicate the widgets` (got
  the natural-language reply), `?why did that fail`, `:status`, `:frobnicate`, and the
  extension test (`ImportError: cannot import name 'input_modes'`).
- **(b) Production path?** Yes. Every case goes through the real `Repl(...).run()` loop
  in `src/nl_shell/repl.py`, which calls the real `input_modes.parse` / `reply` and
  `router.route`. The extension test appends to the real `input_modes.STATUS_LINES` and
  removes it in `finally`.
- **(c) Fixture includes the fault?** Yes. The fault is "the router decides a prefixed
  line". The fake `$PATH` has only `ls`, `git`, `find`, so `frobnicate` is not on it and
  the router alone calls `frobnicate the widgets` natural language — the `\` row only
  passes because the prefix overrides that. `@@clean up…` is asserted to get the `@@`
  reply, which is distinct from the `@` reply.

## Commit-readiness

The target has no formatter or pre-commit config (`pyproject.toml` has none; no
`.pre-commit-config.yaml`; CI workflows are tests, docs-checks, linked-issue, triage).
All new lines are ≤ 92 columns, matching the existing code. Nothing pushed, no PR opened.

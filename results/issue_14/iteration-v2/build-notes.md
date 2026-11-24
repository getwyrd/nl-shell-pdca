# Build notes — issue 14 / input-mode-prefix-dispatch (iteration 2)

Target: eduralph/nl-shell @ main (worktree base `e7bb63c`). Line numbers below are in the
patched worktree unless marked `main`.

## What iteration 2 changes

I started from the iteration-1 patch (`iteration-v1/patch.diff`) and fixed the two
findings in the carry-forward. Nothing else changed.

### Finding 1 — `: status` returned "unknown" (payload not stripped for `:`)

The brief says the payload is "the text after the prefix (stripped)" for every prefix
(brief.md:24). Iteration 1 left the `:` payload unstripped, so `: status` looked up
`" status"` and got the unknown reply.

- `src/nl_shell/input_modes.py:53-62` — `parse()` now strips the payload for every mode:
  `return Prefixed(mode, text[len(prefix):].strip())` (line 61). The docstring now says so.
- `src/nl_shell/input_modes.py:125` — the bare-`:` check is now `if not payload:`. The
  old `payload.strip()` only existed because the payload was unstripped.
- Lookup stays exact and case-sensitive (`META_COMMANDS.get(payload)`), so `:statusx` is
  still unknown. A new table row pins that (brief Design: "`:statusx` is unknown").

Regression rows added to the table in `tests/test_input_modes.py`: `": status"`,
`":  context"`, `"? why did that fail"`, `"@ show disk usage"`, `"\\ frobnicate the widgets"`.
I checked these rows against the iteration-1 parser: with the old line 61 put back,
`: status` and `:  context` fail (`2 failed, 173 passed` on the suite runner) and pass
again with the fix (`175 passed`). So they cover this exact defect.

### Finding 2 — the `:status` table row pinned the whole output as `"nl-shell 0.0.0\n"`

That broke the extension point. As soon as #92/#16/#77 append a line, or the version is
bumped (`src/nl_shell/__init__.py:3`), the row would go red. Fix in the test only:

- `STATUS = "nl-shell "` is now the literal prefix of the version line, with a comment
  explaining why only the first line is checked.
- In `test_prefix_dispatch`, a `:status` row checks
  `out.splitlines()[0] == STATUS + nl_shell.__version__`, so the version line must come
  first. Every other row still compares the whole output exactly.
- `test_status_lines_can_be_extended` uses the same version-line string instead of the
  `0.0.0` literal.
- `nl_shell` is imported inside the test functions only. It exists on `main`, so the red
  leg can still import the module.

Rejected: dropping the `:status` row from the table. The reviewer offered this as an
option, but the criterion asks for `:status` in the table, and the row is part of the red
evidence on `main` (the router sends `:status` to natural language there).

## Changes on main (unchanged from iteration 1 except as above)

- `src/nl_shell/input_modes.py` (new, 133 lines): prefix table with `@@` before `@`
  (lines 44-50), `parse()` (53-62), `STATUS_LINES` list of zero-argument callables plus
  `status()` (65-74), fixed replies, `META_COMMANDS` by exact name, usage replies, `reply()`.
- `src/nl_shell/repl.py:57-62` on `main` (the loop body). After the strip, blank and exit
  checks, the routed reply is now `self._reply(text)` (patched `repl.py:64`). `_reply`
  (patched `repl.py:66-77`) tries prefix dispatch first and falls back to
  `REPLIES[route(text)]`, so plain input is byte-identical. `\cmd` returns the existing
  command reply, with the ADR-0013 §7 (Proposed) / #64 comment.
- `EXIT_COMMANDS` moved from `repl.py:18` on `main` to `input_modes.py:25`. `repl.py:17`
  imports it back, so `nl_shell.repl.EXIT_COMMANDS` still resolves.

## Red → green (project runner)

`engine/scripts/run-verify.sh` (the C4 gate), run with `PDCA_BUNDLE` / `PDCA_WORKTREE` set:

- green leg: `27 passed` (pytest exit 0, ran 27).
- red leg: `21 failed, 6 passed` (exit 1, ran 27, 0 collection errors).
- `PDCA-EVIDENCE: C4 PASS — red without the fix (21 of 27 failed), green with it`.

The six rows that pass on `main` are the ones the brief says prove nothing on their own:
`\ls -la`, plain `ls -la`, `show disk usage`, the distinctness check, and the two
`:quit`/`:exit` tests. `engine/scripts/run-suite.sh` (T3): `175 passed`.

## Self-refutation

- **(a) Genuine red?** Yes. The C4 red leg reverts the production hunks and gets 21 of 27
  failing, including `\frobnicate…`, `?why…`, `:status`, `:frobnicate`, and the extension
  test (ImportError for `nl_shell.input_modes`). For this iteration's fix I also put back
  only the iteration-1 `parse()` line: `: status` and `:  context` went red, then green
  once the fix was restored.
- **(b) Production path?** Yes. Every row runs through the real `Repl(...).run()` from
  `nl_shell.repl` with a scripted read function. The extension test appends to the real
  `nl_shell.input_modes.STATUS_LINES`. Nothing is mocked except the `read` function and
  `$PATH`.
- **(c) Fixture includes the fault?** Yes. The fake `$PATH` holds only `ls`, `git` and
  `find`, so `frobnicate` and `?why` are not on it, and on `main` the router sends them to
  natural language. That is the behaviour the prefix override must beat. The whitespace
  rows feed in the exact input from the finding (`: status`).

## Commit-readiness

nl-shell configures no formatter, linter or pre-commit hook (`pyproject.toml` has only
pytest config, and `.github/workflows/tests.yml:21-23` runs only pip install and pytest).
`git diff --check` is clean, no line is over 99 characters, and
`git apply --check -R patch.diff` succeeds on the worktree.

Housekeeping: while comparing patch files I wrote one scratch file, `/tmp/p.diff`, outside
the given roots. Cleanup is left to the harness, as the rules say.

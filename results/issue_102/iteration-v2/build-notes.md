# Build notes — #102 session terminal ownership (pty-protocol v1 §6), iteration 2

Target: eduralph/nl-shell, integration branch at `cefb359` (#140 + #141 + #143 folded onto
`main`). Line numbers below are on that tree with this `patch.diff` applied (worktree
`nl-shell.pdca-wt-l0`).

## What this iteration changes (carry-forward)

I started from `iteration-v1/patch.diff` (applied cleanly to `cefb359`) and fixed the two
findings in the carry-forward. Everything else is the v1 design, re-cited below.

### Finding 1: the mirror spun forever on a full output destination (fixed)

Cause: v1's `mirror()` looped `os.write` → `BlockingIOError` → `select(…, 0.02)` →
`continue` until every byte was written. A real terminal that stops reading (a full
non-blocking fd) kept the session's main loop inside `mirror()` for good. `D`, `E` and the
caller's timeout were never checked. With a *blocking* full fd, `os.write` blocked in the
kernel instead, with the same result.

Fix, all in `src/nl_shell/session_terminal.py` (§6.2):
- `begin()` saves the output fd's blocking flag and sets it non-blocking (`:160-161`);
  `end()` puts it back (`:191-196`), in the same nested `finally` as the master's flag.
- `mirror()` (`:263`) queues the bytes in `_mirror` and makes one non-blocking write
  (`_write_mirror`, `:276`). It never waits. Past `MIRROR_LIMIT = 1 MiB` (`:51`) queued
  bytes, the rest of the copy is dropped and `mirror_dropped` is set. The capture is not
  affected: `_Output._append` (`session.py:458-461`) still keeps what `capture()`
  returns.
- `write_fds()` (`:212`) adds the output fd while the queue is non-empty, and `pump()`
  (`:223`) writes to it when `select` says it is writable. So the session loop
  (`session.py:781-789`, unchanged) waits on the PTY, fd 3, the terminal's input and its
  output together, with its usual 20 ms poll and deadline.
- `end()` calls `_settle_mirror()` (`:178`, `:291`): it writes the rest of the queue while
  the terminal keeps taking bytes, stopping after 0.25 s with no room or 1 s in total
  (`MIRROR_SETTLE`, `:52`). Then it drops what is left. In the normal case the queue is
  already empty and this costs nothing. This is the only added wait, and it is bounded.
- Dropped queue bytes are zeroed first (`_drop_mirror`, `:313`), like `_drop_pending`. The
  queue can hold the echo of forwarded input, and §6.1 says such bytes are not kept.

`session.py` is not touched in this iteration. `_await_output_end` (`session.py:831`)
feeds output into the same `mirror()`, so it cannot block either.

Spec §6.2 gets one bullet for this (`v1.md:449-452`): the copy MUST NOT block reading
the PTY or fd 3; it is queued up to 1 MiB and dropped past that; at the end it is written
for at most 1 s. The brief puts §6.2 wording in scope. The spec is `draft`.

Test: `test_a_terminal_that_stops_reading_does_not_stall_the_run` (`tests/test_session_terminal.py:460`),
for both a blocking and a non-blocking output fd. The output side of the `Terminal` is a
pipe that nobody reads, filled up first. The run (100 KB of output, then `echo end`) goes
on a worker thread, so a stall fails the test instead of hanging the suite. After the run,
the test drains the pipe to free a stuck worker. It checks that the run returned within
`RUN_TIMEOUT + 2` s, that the status is 0, that the capture holds all 100 KB plus `end`,
that the pipe's blocking flag was put back, and that the session is healthy.

### Finding 2: the new mirror path is unfiltered and the threat model did not say so (doc fix)

- New Known-gaps bullet, `.oss-scanner/threat_model.md:220-225`: the §6 mirror copies
  output byte for byte, so OSC 52, title changes and terminal queries (`ESC [6n`,
  `ESC [21t`) reach the real terminal until the rendering filter lands. A query's answer
  is forwarded to the command inside the window, or waits for the next reader after `D`.
  It says this breaks "Output rendering is filtered everywhere" (`:132`).
- The #78 gate line (`:228`) now also requires the rendering filter on the §6 mirror.
- **No issue number**: no rendering-filter issue exists on the tracker. I searched
  `gh issue list -R eduralph/nl-shell --search "rendering filter"` and `"OSC 52"`: only
  #63, #71 (closed, the threat-model revision), #101, #102, #116, #143 and #151 match.
  `policy-gate/v1.md:164` says "rendering filter (#71)", but #71 is the closed
  threat-model revision. The parent brief (`results/issue_10/brief.md:19`) says the human
  files that issue. So the doc names the filter, not a number. **For the human:** file the
  issue and put its number in both lines.
- I did not add a test that shows OSC 52 passing through. It would pin the gap as
  wanted behaviour and go red when the filter lands. The filter itself is out of scope
  (brief Scope).

The 10 deferred findings in `deferred-findings.json` are for the human; I did not act on
them.

## The v1 design (unchanged, re-cited)

- `Terminal(input_fd, output_fd=None)` (`session_terminal.py:111`); `own()` (`:119`)
  returns the per-run `_Ownership` (`:124`).
- §6.1 window start, `begin()` (`:150`): save termios, raw mode, `tcflush(TCIFLUSH)`
  (`:157`) so bytes typed before the run are not forwarded, master non-blocking (`:159`),
  SIGWINCH handler on the main thread only (`:163`), copy the size once.
- §6.1 forwarding, `pump()` (`:218`): reads the terminal only while nothing is queued
  (`read_fds`, `:205`), writes at most `CHUNK = 1024` (`:46`) per call, and calls the
  session's `forwarding_over()` before every write (`:242`). `stop()` (`:168`) at `D`
  zeroes and drops the queue.
- §6.2 alternate screen, `_AltScreen` (`:73`), regex `:56`, split-sequence tail
  `_held_tail` (`:63`). Capture stops at a set and resumes only on the reset of the same
  mode.
- Decision 7, `capture()` (`:319`): nothing captured once a byte has been forwarded.
- §6.3, `_on_winch` → `_copy_size` (`:332`, `:335`). §6.4 needs no code (raw mode clears
  ISIG on the real terminal). §6.5, `end()` (`:173`), nested `finally`s, TCSANOW.
- `session.py`: `run(…, terminal=None)` (`:686`, body `:717-726`); `_wait_for_result(…,
  owner)` (`:735`) with the record handling moved into `control()` (`:746`) plus
  `owner.stop()` at `D` (`:752`); `forwarding_over()` (`:764`); select with read and write
  sets (`:781`) and `owner.pump` (`:789`); `_Output(…, sink)` (`:401`, `:448`,
  `:458-461`); `_marker_start` (`:1178`, used at `:453`) so a prompt with no newline reaches
  the screen at once; `CommandResult.input_forwarded` (`:387`, set at `:863`); the decision-6
  drain in `RCFILE` (`:258-262`), last before `E`, with a `[[ -t 0 ]]` guard; `"read"`
  added to `HOOK_BUILTINS` (`:96`).
- Brief inaccuracies noted in v1, still true: `read` was not in `HOOK_BUILTINS` on the
  branch (added, so `enable -n read` degrades with `h-changed`); Scope says the drain goes
  "between `D` and the snapshot" but the Goal says last before `E`, and I followed the Goal.
- Docs from v1: §1.3 reference rcfile, §6.1 (discard, fd-3 check per ≤1 KB write, drain,
  residual race, `input_forwarded`), §6.2 `?1047` and same-mode pairing, ADR-0014 Decision 4
  "From sending the command to the done record", threat model drain-race bullet (`:212`)
  and "How to exercise it" (`:232`).

Criterion map: (a) `:174`; (b) `:199`; (c) `:264` and window start `:342`; (d) `:359`
(emacs, vi), `:375` (200 KB burst), `:512` (`true` < 0.5 s); (e) `:526`; (f) `:548`;
(g) `:576`, `:586`, `:602`. Beyond the criterion: window end `:314`, full input buffer
`:412`, and the new stalled-output test `:460`.

## Results

- `python3 -m pytest tests/test_session.py tests/test_session_terminal.py` (venv python,
  wrapped in `timeout 300`) → `181 passed` in 167 s.
- Whole suite through `engine/scripts/run-suite.sh` → `498 passed`,
  `PDCA-EVIDENCE: T3 PASS`. The one warning (`forkpty()` in a multi-threaded process) was
  already in `iteration-v1/gate-logs/T3-suite.log`.
- `python -I scripts/docs_links.py` → `0 broken`. The docs immutability check freezes only
  non-draft specs and non-Proposed ADRs; the spec is `draft`, ADR-0014 is `Proposed`, and
  the threat model is not a design record.

## Refutation (forced)

**(a) Genuine red? Yes.** For the whole patch, the v1 result holds: with `src/` reverted,
the test file fails (`ModuleNotFoundError: nl_shell.session_terminal` in each test). For
this iteration's fix: I ran the new test against v1's `session_terminal.py` (v1 patch
applied, before my change) → `2 failed` (both `blocking=True` and `blocking=False`),
`AssertionError: run() stalled behind a real terminal that stopped reading`, 24 s. After
the fix → both pass. A narrower mutation: with only the `os.set_blocking(output_fd,
False)` line in `begin()` replaced by `pass`, the `blocking=True` case goes red (the
first write blocks in the kernel) and `blocking=False` stays green. So each part is bound
by one case. I restored the file from a copy (`src/nl_shell/session_terminal.py.keep`,
left untracked in the worktree and not in `patch.diff`).

**(b) Production path? Yes.** The test calls the real `Session.run(…, terminal=Terminal(fd,
out_w))` against real bash on a ptyprocess PTY. The output goes through the production
`_Output` → `mirror()` path. The only stand-ins are the user's terminal (an `os.openpty()`
pair, as the brief prescribes) and the output pipe that plays a stuck terminal. Nothing
is mocked.

**(c) Fixture includes the fault? Yes.** The pipe is really full before the run (filled
until `BlockingIOError`) and nobody reads it while the run is checked. It is run once
with the fd left blocking and once non-blocking, which are the two ways a stuck terminal
shows up. The other faults from v1 are still injected for real: `\x03`, the sentinel, the
typed-ahead text, the 200 KB burst from a thread, a real `SIGWINCH`, a real degrade and an
exception raised mid-command.

## Things I ruled out

- **Backpressure (stop reading the PTY while the terminal is full)** instead of dropping
  the copy. It is closer to how a slow terminal slows a program down. But the command
  then blocks on its output, `D` never comes, and a `run()` with no timeout hangs. That is
  the same failure the finding is about, just moved. Dropping the copy past 1 MiB keeps
  the capture whole and the run finite.
- **Writing the copy from a thread.** It would need a lock around the queue and a join in
  `end()`, and it does not fix the case where the write blocks in the kernel. Making the
  fd non-blocking and gating writes on `select` fixes both, with no second thread.
- **Leaving the output fd blocking and writing only after `select` says writable.** On a
  tty, `select` reports writable when *some* room is free. A blocking write larger than
  that room still blocks. The non-blocking flag is what makes the write safe, as the
  mutation above shows.
- **Adding the rendering filter.** Out of scope (brief Scope; it blocks #78).

## Open for sign-off

- **Accept the residual drain race for v1, or ask for Option A** (from the brief).
- **Confirm decisions 6/7 and the strict `?1047` pairing** (from the brief).
- **File the rendering-filter issue** and put its number in `threat_model.md:220` and
  `:228` (see Finding 2).
- The new §6.2 bullet sets two numbers (1 MiB queue, 1 s settle). They are starting
  values, like §6.6's 64 KiB.
- Re-run a red (d) once before reading it as a regression (from the brief).

## Housekeeping

- No formatter or commit hook is configured in the target (no `.pre-commit-config.yaml`,
  no ruff/black/flake8 in `pyproject.toml`; CI runs pytest and the docs checks). No line
  over 100 characters in the touched Python files.
- Untracked in the worktree, not in the patch: `src/nl_shell/session_terminal.py.keep`
  (the copy used to undo the mutation). I did not delete it; the harness reclaims the
  worktree.
- Nothing pushed, no PR opened.

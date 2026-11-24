# Build notes — #102 session terminal ownership (pty-protocol v1 §6), iteration 3

Target: eduralph/nl-shell, integration branch at `cefb359` (#140 + #141 + #143 folded onto
`main`). Line numbers below are on that tree with this `patch.diff` applied (worktree
`nl-shell.pdca-wt-l0`).

## What this iteration changes (carry-forward of round 2)

I started from `iteration-v2/patch.diff` (applied cleanly to `cefb359`) and fixed the three
findings in the round-2 carry-forward. The rest is the v1/v2 design, re-cited at the end.

### Finding 1: `O_NONBLOCK` was set on the terminal's shared file description (fixed)

Cause: v2's `begin()` called `os.set_blocking(output_fd, False)`. The flag lives in the
open file description, which every copy of the fd shares (the login shell, its background
jobs), so all of them got non-blocking writes for the length of each command.

Fix (§6.2), `src/nl_shell/session_terminal.py`:
- `_open_private(fd)` (`:132`) opens the same terminal or pipe again with
  `O_WRONLY | O_NOCTTY | O_NONBLOCK | O_CLOEXEC`: first by `os.ttyname(fd)`, then by
  `/proc/self/fd/<fd>` (for a pipe, or a tty with no name). That gives nl-shell its own
  description; the shared fds keep their flags.
- A regular file is not reopened: writes to it never block, and a reopen would write at
  offset 0 instead of the shared offset.
- If nothing can be opened (no `/proc`, a socket), it falls back to the shared fd with its
  flags untouched. `_write_mirror` (`:331`) then writes only after `select` says the fd is
  writable, and at most `_SHARED_CHUNK = 256` bytes (`:60`, `:344`). On a tty, `select`
  reports writable only when that much room is free, so this does not block in practice.
  This path is a last resort and no test reaches it on Linux.
- `begin()` sets `self._out` (`:215`); `end()` closes it (`:247`) inside the existing
  nested `finally`, before termios is restored. `write_fds`, `pump`, `settle` use `_out`.
- Input fd: never made non-blocking (it is only read after `select` says readable), so
  nothing changes there. The session master (`_master`) is nl-shell's own ptyprocess fd;
  it still gets `set_blocking(False)` and that is not shared with other processes.
- A SIGKILL mid-run no longer leaves any flag behind on the terminal.

Test: `test_the_terminal_fds_keep_their_flags_while_a_command_runs`
(`tests/test_session_terminal.py:522`). It runs `echo x; sleep 1` with
`Terminal(screen.fd)`, keeps a `dup` of the slave (another process's copy), and 0.4 s in a
helper thread checks `os.get_blocking` on both. Both must be True during and after the run,
and the copy must still reach the screen. In the stalled-output test (`:469`), the existing
`os.get_blocking(out_w) is blocking` check now passes because the pipe is reopened through
`/proc/self/fd`, not because the flag was put back.

### Finding 2: alternate-screen parsing missed combined parameters and 8-bit CSI (fixed)

Fix (§6.2), `session_terminal.py`:
- `_PRIVATE_MODE` (`:68`) matches any DEC private mode set/reset: `(ESC [ | 0x9b) ? <digits
  and ;> (h|l)`. `_alt_modes` (`:82`) splits the list and keeps 47/1047/1049 in order. It
  strips leading zeros (xterm reads `01049` as 1049) and skips anything over 4 digits, so
  `int()` never sees a huge string.
- `_AltScreen.filter` (`:101`) applies the alt modes in order with the same strict pairing
  as before. A sequence with no screen switch while on the main screen (`ESC [?25l`) is kept
  as plain output, same as v2 kept a reset on the main screen.
- Split sequences: `_PRIVATE_MODE_START` (`:70`) holds back a tail that may start such a
  sequence, looking at the last `_HOLD_LIMIT = 4096` bytes. A parameter list longer than
  that split across reads is not caught; I judged that edge acceptable (the effect is that
  some alternate-screen text gets captured, and captured output is untrusted anyway).
- I checked byte-by-byte feeding against one-shot feeding for the combined, 8-bit, leading
  zero and mismatched cases: same output (`b'AB'`, `b'AB'`, `b'AB\x1b[?25h'`, `b'A'`).
- 8-bit CSI false positives: in UTF-8 output `0x9b` is a continuation byte. It would have
  to be followed by a literal `?47h`-style string to match. When that happens capture
  pauses, which is the safe direction.

Test: `test_alternate_screen_is_mirrored_but_not_captured` (`:174`) now also prints
`ESC [?25;1049h … ESC [?1049;25l`, `ESC [?01047h … ESC [?1047l`, `\233?47h … \233?47l`
(octal 233 = `0x9b`) and a non-screen `ESC [?25l … ESC [?25h`. It checks they are
captured as expected and all mirrored.

Spec §6.2 (`docs/design/specs/pty-protocol/v1.md:447-450`) now says the whole parameter
list counts, leading zeros too, and the 8-bit CSI.

### Finding 3: `mirror_dropped` was never reported (fixed)

- `CommandResult.mirror_dropped: bool = False` (`src/nl_shell/session.py:390`), set at
  `:869`.
- The settle step (writing the rest of the queue for at most 1 s) used to run only in
  `end()`, which runs after the result is built. `_result` now calls `owner.settle()`
  first (`session.py:858`), so a drop during settle is in the result too. `end()` still
  calls `settle()` (`session_terminal.py:356`) for the exception paths; a second call finds
  an empty queue and returns at once.
- The degraded path also goes through `_result` (`session.py`, inside `_wait_for_result`),
  so `SessionDegraded.result` carries the flag too.
- Spec §6.2 (`v1.md:456`) names `CommandResult.mirror_dropped`.

Test: the stalled-output test (`:514`) asserts `result.mirror_dropped`; the alternate-screen
test (`:192`) asserts it is False on a normal run.

The deferred findings in `deferred-findings.json` are for the human; I did not act on them.

## Results

- `tests/test_session_terminal.py` alone (venv python, `timeout 300`): `18 passed` in 22 s.
- Whole suite through `engine/scripts/run-suite.sh` (with `PDCA_WORKTREE` set to the
  worktree, wrapped in `timeout 590`): `499 passed, 1 warning`, `PDCA-EVIDENCE: T3 PASS`.
  This includes `tests/test_session.py` unchanged. The warning (`forkpty()` in a
  multi-threaded process) was already there in earlier iterations.
- `python -I scripts/docs_links.py` → `63 relative links in 55 Markdown files, 0 broken`.

## Refutation (forced)

**(a) Genuine red? Yes.**
- Whole patch: with `src/` at the base, every test fails (no `terminal=` argument / no
  `nl_shell.session_terminal`), same as v1/v2.
- This iteration: I put back v2's `session.py` and `session_terminal.py` and kept the new
  tests. Result: `4 failed, 14 passed`. Failing: the alternate-screen test
  (`AttributeError: … no attribute 'mirror_dropped'`), both stalled-output cases (same
  attribute), and the flags test (`assert [(False, False)] == [(True, True)]` — v2 set
  `O_NONBLOCK` on the shared description and the `dup` saw it).
- The alternate-screen test fails on the attribute first, so I also ran a narrower
  mutation: v3 code with only `_PRIVATE_MODE` changed back to v2's single-parameter regex.
  It goes red on the content: the captured text holds `[?25;1049hHIDDEN6…` and
  `[?01047hHIDDEN7…`. So the parsing fix is bound by the test on its own.
- I restored v3 from copies kept in the worktree (`session_terminal.py.v3`, `session.py.v3`,
  untracked, not in `patch.diff`) and re-ran: green.

**(b) Production path? Yes.** Every test calls the real `Session.run(…, terminal=Terminal(…))`
against real bash on a ptyprocess PTY. The output goes through the production `_Output` →
`mirror()` / `capture()` path, the sequences are printed by bash's `printf`, and the flag
check reads the real fds' flags. The only stand-ins are the user's terminal (an
`os.openpty()` pair, as the brief prescribes) and, in the stall test, a pipe that nobody
reads.

**(c) Fixture includes the fault? Yes.** The flags test keeps a `dup` of the terminal fd,
which is exactly the "other process shares the description" case. The alt-screen test
prints the combined, leading-zero and 8-bit forms that slipped past v2. The stall test's
pipe is filled until `BlockingIOError` before the run, so the copy really is dropped.

## The v1/v2 design (unchanged, re-cited)

- `Terminal(input_fd, output_fd=None)` (`session_terminal.py:163`); `own()` (`:171`)
  returns the per-run `_Ownership` (`:176`).
- §6.1 window start, `begin()` (`:203`): save termios, raw mode, `tcflush(TCIFLUSH)`
  (`:212`) so bytes typed before the run are not forwarded, master non-blocking, SIGWINCH
  handler on the main thread only (`:217`), size copied once.
- §6.1 forwarding, `pump()` (`:273`): reads the terminal only while nothing is queued
  (`read_fds`, `:260`), writes at most `CHUNK = 1024` (`:50`) per call, and calls the
  session's `forwarding_over()` before every write (`:297`). `stop()` (`:222`) at `D`
  zeroes and drops the queue (`_drop_pending`, `:311`).
- §6.2 output: `mirror()` (`:318`) queues up to `MIRROR_LIMIT = 1 MiB` (`:55`), never
  waits; `settle()` (`:356`) at most `MIRROR_SETTLE = 1 s` (`:56`); dropped bytes zeroed
  (`_drop_mirror`, `:379`).
- Decision 7, `capture()` (`:385`): nothing captured once a byte has been forwarded.
- §6.3 `_on_winch` → `_copy_size` (`:398`, `:401`). §6.4 needs no code (raw mode clears
  ISIG on the real terminal). §6.5 `end()` (`:227`), nested `finally`s, TCSANOW.
- `session.py`: `run(…, terminal=None)` (`:689`); `_wait_for_result(…, owner)` (`:738`) with
  record handling in `control()` (`:749`) and `owner.stop()` at `D` (`:755`);
  `forwarding_over()` (`:767`); `owner.pump` (`:792`); `_Output(…, sink)`; `_marker_start`
  (`:1184`); `input_forwarded` (`:868`); decision-6 drain in `RCFILE` (`:261`), last before
  `E`, guarded by `[[ -t 0 ]]`; `"read"` in `HOOK_BUILTINS` (`:96`).
- Brief inaccuracies noted in v1, still true: `read` was not in `HOOK_BUILTINS` on the
  branch (added); Scope says the drain goes "between `D` and the snapshot" but the Goal
  says last before `E`, and I followed the Goal.
- Docs from v1/v2: §1.3 reference rcfile, §6.1 (discard, fd-3 check per ≤1 KB write, drain,
  residual race, `input_forwarded`), §6.2 `?1047` and same-mode pairing plus the
  non-blocking copy, ADR-0014 Decision 4 "From sending the command to the done record",
  threat model drain-race bullet, unfiltered-mirror bullet and #78 gate line, "How to
  exercise it".

Criterion map: (a) `:174`; (b) `:208`; (c) `:273`, window start `:351`, window end `:323`;
(d) `:368` (emacs, vi), `:384` (200 KB burst), `:544` (`true` < 0.5 s); (e) `:558`;
(f) `:580`; (g) `:608`, `:618`, `:634`. Beyond the criterion: full input buffer `:421`,
stalled output `:469`, shared fd flags `:522`.

## Things I ruled out

- **Keep `set_blocking` on the shared fd but restore it sooner.** It does not help: the
  flag is shared for however long it is set, and a SIGKILL still leaves it.
- **Write the copy from a thread with a blocking fd.** A write blocked in the kernel
  cannot be cancelled, so `end()` would have to leave the thread behind or wait on it.
  That is the stall from round 1 in another place.
- **`/proc/self/fd` only, no `ttyname`.** That would tie the tty path to Linux. `ttyname`
  works on any POSIX system; `/proc` is the second try for pipes.
- **Reopening regular files.** Loses the shared offset; writes there never block, so the
  shared fd is used as is.
- **A cap on the parameter list in the main regex.** xterm accepts leading zeros of any
  length, so a cap would be a bypass. Only the held-back tail is capped (4096 bytes), to
  keep re-scanning linear.

## Open for sign-off

- **Accept the residual drain race for v1, or ask for Option A** (from the brief).
- **Confirm decisions 6/7 and the strict `?1047` pairing** (from the brief).
- **File the rendering-filter issue** and put its number in `threat_model.md` Known gaps
  ("The §6 mirror is not filtered yet") and the #78 gate line (carried from v2).
- §6.2 now has two more normative sentences (parameter list / 8-bit CSI; no `O_NONBLOCK`
  on the shared fds). The spec is `draft`.
- Re-run a red (d) once before reading it as a regression (from the brief).

## Housekeeping

- No formatter or commit hook is configured in the target (no `.pre-commit-config.yaml`,
  no ruff/black/flake8 in `pyproject.toml`; CI runs pytest and the docs checks). No line
  over 100 characters in the touched Python files (checked with `awk 'length > 100'`).
- Untracked in the worktree, not in the patch: `session_terminal.py.v3`, `session.py.v3`
  (copies used to undo the mutation runs). The new files are marked intent-to-add
  (`git add -N`) so `git diff` includes them. I did not delete anything; the harness
  reclaims the worktree.
- Nothing pushed, no PR opened.

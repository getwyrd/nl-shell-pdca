# Build notes — #102 session terminal ownership (pty-protocol v1 §6)

Target: eduralph/nl-shell, integration branch `pdca-integration/main-r2546dbf9639f` at
`cefb359` (#140 + #141 + #143 folded onto `main`). Line numbers below are on that tree with
the patch applied (worktree `nl-shell.pdca-wt-l0`).

## What changed and why

### New module `src/nl_shell/session_terminal.py` (standard library only)

- `Terminal(input_fd, output_fd=None)` (`session_terminal.py:101`) is the injectable real
  terminal. `Terminal.own(master_fd)` (`:109`) returns one run's `_Ownership` (`:114`),
  which the session loop drives.
- §6.1 window start, `_Ownership.begin` (`:137`): save termios, `tty.setraw(…, TCSANOW)`,
  `tcflush(TCIFLUSH)` (`:144`) so bytes typed before the run are never forwarded, set the
  session master non-blocking (`:146`), install the SIGWINCH handler (main thread only,
  `:148`), copy the size once.
- §6.1 forwarding, `pump` (`:193`): reads the real terminal only while nothing is queued
  (`read_fds`, `:183`), so input never piles up in nl-shell. Writes at most `CHUNK = 1024`
  bytes (`:43`) per call, only when `select` reports the master writable. It calls the
  session's `forwarding_over()` before **every** write, which reads fd 3 and returns True
  from `D` on. `stop()` (`:153`) zeroes and drops the queue. `forwarded` is set on the first
  byte actually written.
- §6.2, `_AltScreen` (`:63`): regex `ESC [?(1049|1047|47)(h|l)` (`:46`). Capture stops at a
  set and resumes only on the reset of the **same** mode. A reset of another mode, or a
  second set, changes nothing. A reset seen on the main screen is kept as plain output.
  A tail that could be the start of a sequence split across reads is held back
  (`_held_tail`, `:53`) and released by `flush()` at the end marker.
- Decision 7, `capture()` (`:250`): returns `b""` once `forwarded` is set. Mirroring
  (`mirror`, `:235`) is not affected.
- §6.3, `_on_winch` → `_copy_size` (`:263`, `:266`): TIOCGWINSZ on the real terminal,
  TIOCSWINSZ on the master (the kernel then signals bash's foreground job). Errors are
  swallowed: this runs inside a signal handler.
- §6.4 needs no code: raw mode turns the real terminal's ISIG off, so `\x03` arrives as a
  byte and the session PTY's line discipline signals the job.
- §6.5, `end()` (`:158`): drop the queue, restore the SIGWINCH handler, restore the
  master's blocking flag, then `tcsetattr(TCSANOW, saved)`. Nested `finally`s, so one
  failure does not skip the rest. TCSANOW, not TCSADRAIN: a real terminal that is not
  being read must not hang the restore.

### `src/nl_shell/session.py` (child-1): the smallest hooks, the run loop wrapped, not forked

- `run(…, terminal=None)` (`session.py:686`, body `:717-726`): `owner.begin()` before
  `command_sent()` and the paste, `owner.end()` in `finally`. Without `terminal`, behaviour
  is unchanged.
- `_wait_for_result(timeout, owner=None)` (`:735`). The existing record handling moved into
  a nested `control()` (`:746`) with the same body, plus `owner.stop()` at `D` (`:752`), so
  both the main loop and the forwarder's pre-write check use the same code.
  `forwarding_over()` (`:764`) is the fd-3 check run before every write. When there is an
  owner, the loop uses `select` with read **and** write sets (`:781`) and then calls
  `owner.pump` (`:789`). The loop keeps reading PTY output and fd 3 while input is queued.
- `_Output(…, sink=None)` (`:401`): the command's output goes to `sink.mirror` and only
  `sink.capture(...)` is kept (`:458-460`); `sink.flush()` runs at the end marker
  (`:448`).
- **Child-1 sequencing change, and why:** `_Output.feed` used to hold back the last
  `len(marker)-1` bytes (~40) every time. It now holds back only a tail that really is a
  start of the marker (`_marker_start`, `:1178`, used at `:453`). Without this, §6.2
  ("copy PTY output to the real terminal") fails for interactive programs: a prompt with
  no newline ("Name: ") would not reach the screen until more output arrived. The captured
  bytes are the same. `tests/test_session.py` passes unchanged.
- `CommandResult.input_forwarded: bool = False` (`:387`, set at `:863`): the decision-7
  flag. It defaults to False, so existing callers are unaffected.
- Decision 6 drain in `RCFILE` (`:258-262`), last before the reset line and `E`, as the
  Goal requires:
  ```
  __nls_v=x
  while [[ -t 0 && -n $__nls_v ]]; do
    __nls_v=
    \builtin read -r -s -N 4096 -t 0.05 __nls_v || \builtin :
  done
  ```
  The loop ends at the first read that returns nothing within 50 ms. A timed-out read with
  partial input keeps the loop going, as does a full 4096. If `read` is disabled the
  variable stays empty and the loop ends. **Addition not in the brief:** the `[[ -t 0 ]]`
  guard. Without it, a confirmed `exec </dev/urandom` would make the drain loop forever:
  `E` would never come, and a `run()` with no timeout would hang, because the prompt rule
  ignores a redirected fd 0. With the guard, the fd check at `E` degrades that session
  instead. Rationale comment at `:147`.
- **Brief inaccuracy:** the brief says `read` is already in #141's `HOOK_BUILTINS`. On the
  integration branch it was not. I added it (`:96`) because
  `test_hook_builtins_are_exactly_the_ones_the_hooks_call` requires the list to match the
  `\builtin` names exactly. As a result, `enable -n read` now degrades with `h-changed`
  (`test_disabling_any_hook_builtin_degrades` covers it, green).
- **Brief inconsistency:** Scope says "between `D` and the snapshot", but the Goal (round-2
  plan review) says last step before `E`, with the reason that a drain after `E` could eat
  the next paste. I followed the Goal.

### Docs

- Spec `pty-protocol/v1` (draft): the §1.3 reference rcfile has the drain and `'read'` in
  the H builtins list (`v1.md:177`, and the `compgen` list).
  `test_spec_reference_rcfile_is_the_one_in_use` keeps the two identical. §6.1 now covers
  discard before/after the window, the fd-3 check per ≤1 KB write, the drain, the named
  residual race, and the `input_forwarded` flag (`v1.md:425-441`). §6.2 now names `?1047`
  and the same-mode pairing (`v1.md:445-447`). The Conformance note names the new test
  file.
- ADR-0014 Decision 4 (Proposed): "From sending the command to the done record"
  (`0014:63`), rewrapped.
- Threat model: a Known-gaps bullet for the residual drain race, naming Option A
  (`threat_model.md:212`), and the terminal tests under "How to exercise it" (`:232`).

## Tests — `tests/test_session_terminal.py` (module-level imports: stdlib + pytest)

The success-criterion items map to tests as follows: (a) `:174`, (b) `:199`, (c) `:264`
plus window start `:342`, (d) `:359` (emacs and vi) and `:375` (200 KB burst) and `:459`
(`true` < 0.5 s with no terminal), (e) `:473`, (f) `:495`, (g) `:523`, `:533`, `:549`.
Two tests go beyond the criterion: `:314` (window **end**: a byte typed between `D` and `E`
is not forwarded) and `:412` (a full PTY input buffer does not stall the run). Why I added
them is under the refutation below.

Results on this host (bash 5.3, Linux 7.0):
`python3 -m pytest tests/test_session.py tests/test_session_terminal.py` → green. The whole
suite through `engine/scripts/run-suite.sh` → `496 passed`, `T3 PASS`. The new tests ran
three times in a row with no flakes (~27 s for 20 tests).

## Refutation (forced)

**(a) Genuine red? Yes.** I ran `git apply -R --include='src/*' patch.diff` (the test file
stays) and then the test: `15 failed`. 14 failed with
`ModuleNotFoundError: nl_shell.session_terminal`. `test_the_drain_keeps_a_command_fast…`
failed on its `"read" in HOOK_BUILTINS` assertion. After re-applying, the tree's diff is
byte-identical to `patch.diff`. A per-part check broke each production part on its own
(the helper was a throwaway `.mutate.py` in the worktree, not in the patch). Each one goes
red in the test meant for it:
- drain removed → both (d) modes and the burst test red;
- `tcflush` removed → window-start test red (`head` got the `Z`);
- alt-screen filter removed, strict pairing loosened (`mode is not None`), or `1047`
  removed from the regex → (a) red;
- decision-7 check removed → (e) red;
- SIGWINCH handler not installed → (f) red;
- `tcsetattr` restore removed → all three (g) tests red;
- forwarded bytes kept on the object (`self._seen = data`) or logged at DEBUG → (c) red;
- stop-at-`D` removed (both `owner.stop()` and the `done` term in `forwarding_over`) →
  window-end test `:314` red. Removing only one of the two is not caught, because each
  covers the other.

Two results the human should know about:
- Removing **only** `os.set_blocking(master, False)` is **not** caught. On this kernel a
  PTY master takes ~18 KB of input before EAGAIN (measured). `pump` writes only when
  `select` reports room, and a write into partial room returned a partial count rather than
  blocking (instrumented: 15×1024, 512, 1024, no EAGAIN). So the non-blocking flag is a
  second safety layer here, not the thing the test checks. With **both** layers removed
  (blocking master and no `select` gate), the full-buffer test `:412` goes red: "run()
  stalled behind a full PTY input buffer", after the 12 s bound. The burst test the brief
  names (`:375`, `sleep 2`, canonical mode) does not stall even then: in canonical mode the
  line discipline drops what a full line buffer cannot hold, so the input never fills.
  That is why I added `:412`, which uses `stty -icanon` and 300 KB of output.
- Without the extra window-end test, removing stop-at-`D` would also pass every brief-named
  test: the drain catches bytes forwarded after `D`. `:314` uses a `~/.bashrc`
  `PROMPT_COMMAND='sleep 0.8'` (it runs after `D`, before the snapshot) to type inside the
  `D`→`E` gap.

**(b) Production path? Yes.** Every test calls the real `Session.run(…, terminal=Terminal(fd))`
against a real `bash --rcfile <RCFILE> -i` on a ptyprocess PTY. The drain under test is
the production `RCFILE` string. The only stand-in is the user's terminal (an
`os.openpty()` pair), which the brief prescribes. Nothing is mocked. Test (c) wraps
`Terminal.own` only to keep a reference to the ownership object it returns, so it can be
scanned.

**(c) Fixture includes the fault? Yes.** The faults are injected for real: `\x03` written
to the stand-in master (b); a sentinel written while `cat` runs (c); typed-ahead
`echo INJECTED; ` with no Enter (d); a 200 KB burst from a separate non-blocking writer
thread (d); a real `SIGWINCH` sent with `os.kill` to the test process after a real
TIOCSWINSZ on the stand-in (f); a real degrade (`PROMPT_COMMAND=:`) and an exception raised
from `on_record` on the `S` record, mid-command (g). The (c) scan covers `vars()` of the
session, the result, the `Terminal`, every live `nl_shell.session_terminal` object
(`gc.get_objects()`) and the recorded `_Ownership`s, recursing into dicts, sequences,
bound methods and closure cells. It also covers both modules' globals and every caplog
record at DEBUG on the root logger.

## Things I ruled out

- **Mirroring raw PTY chunks in `_wait_for_result` instead of through `_Output`.** That
  would mirror the prompt and user `PROMPT_COMMAND` output after the end marker, and §6.6
  says those bytes must not reach the screen directly. Going through `_Output` mirrors
  exactly the command's output (between `ESC [?2004l` and the end marker). The cost is the
  `_marker_start` change above (+7 lines). Readline's echo of the paste itself is not
  mirrored; the REPL (#78) already shows the command.
- **Forwarding in a thread.** SIGWINCH has to be handled on the main thread anyway, and a
  second reader of the master would race `_read_pty`.
- **Writing every queued chunk in one `pump` call.** One chunk per loop turn keeps PTY
  output and fd 3 read between writes. At 1 KB per turn with `select` returning at once,
  throughput is not the limit; the session's ~18 KB input buffer is.
- The rejected approaches the brief names (readline kill keys before the paste;
  `tcflush` from the master side; the iteration-v3 typed-ahead behaviour). I did not
  re-open them.

## Open for sign-off (from the brief)

- **Accept the residual drain race for v1, or ask for Option A** (a back-channel on fd 4)
  as a follow-up. It is named in spec §6.1 and threat model Known gaps.
- **Confirm decisions 6/7 and the strict `?1047` pairing** match what was decided.
- (d) depends on that race not firing. In my runs it never did (3/3 green), but re-run a
  red (d) once before reading it as a regression.

## Housekeeping

- No formatter or commit hook is configured in the target (no `.pre-commit-config.yaml`;
  no ruff/black/flake8 in `pyproject.toml`; CI runs only pytest and docs checks). I checked
  by hand: no line over 100 characters in the touched Python files, and no new unused
  imports (an AST check; the one hit, `CommandRefused` in `session.py`, is an existing
  re-export).
- The docs immutability check only freezes non-draft specs and non-Proposed ADRs. Both
  edited docs are `draft` / `Proposed`.
- I left `.mutate.py` (the throwaway mutation helper) untracked in the worktree. It is not
  in `patch.diff`. By mistake I also wrote one scratch file outside the roots,
  `/tmp/x` (a copy of the `src/` diff, from a stray redirect). It holds nothing secret;
  the harness or the human can ignore it.
- Nothing was pushed and no PR was opened.

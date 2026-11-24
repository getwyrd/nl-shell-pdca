# Build notes — issue 120 / buffer-background-pty-output

Target: eduralph/nl-shell @ main (worktree base a6efb0a). Line numbers below are in the
patched worktree unless marked "base".

## What changed

`src/nl_shell/session.py`

- `BACKGROUND_LIMIT = 64 * 1024` (:314), the one named constant for the buffer, and
  `BACKGROUND_HEADER = b"[background output]\r\n"`. Both added to `__all__`.
- `_PROMPT_QUIET` / `_PROMPT_SETTLE_MAX` / `_PROMPT_POLL` (:322-327): the short settle after
  bash is first seen waiting for a line (see "The boundary" below).
- `class _Background` (:530): bytearray of the newest 64 KiB, a dropped-byte counter and a
  lock (the reader thread adds while the caller may take). `take()` returns
  `header + bytes`, plus `\r\n` (only if the bytes don't already end a line) and
  `[N bytes dropped]\r\n` when N > 0; `b""` when nothing is waiting; it clears the buffer.
- `Session.__init__` (:617-622): buffer, thread, wake pipe, `_bg_armed` flag.
- `close()` (:649-652): stops the reader **before** the PTY fd is closed, so the thread can
  never read a reused fd number. The buffer stays takeable after close.
- `_spawn()` (:721): starts the reader once the baseline and the start checks are done.
- `background_waiting` (:802) and `take_background_output()` (:807): the hand-over. The
  docstring says the bytes are untrusted (ADR-0016), never in a `CommandResult` or the
  state block, only to be shown through the mirror/filter path (#78), never in a confirm
  (#74), and states the boundary and its known limit. No taint type (#11, out of scope).
- `_start_background` / `_stop_background` / `_background_loop` (:828-900): one daemon
  thread per idle period, named `nl-shell-background-output`. It selects on the PTY master
  and a wake pipe. Phase 1 (not armed): polls `_reading_terminal()` every 5 ms and drops what
  it reads. Once bash is seen blocked, it keeps dropping until 10 ms pass with nothing to
  read (capped at 50 ms after the sighting), then arms. Phase 2 (armed): `select` with no
  timeout, every chunk goes to `_Background.add`. It never writes to the PTY (§5.3), never
  touches the tracker or the control channel; on EOF/EIO it just returns and the next
  `run()`'s own `_drain_pty` reads the EOF and degrades as today ("the shell exited").
  Stop = write a byte to the wake pipe and `join()` — immediate, no polling delay.
- `run()` (:927-963): base :756 `self._drain_pty()` (the drop the brief names as the cause)
  becomes `self._stop_background()` + the same `_drain_pty()`, which now **keeps** bytes
  when armed instead of dropping them. Same position, so the order with `_drain_control`
  (base :758-760) and EOF detection is unchanged: a control record that arrived while idle
  is still checked before the paste. A second `_drain_pty()` (:943) right before the last
  `_raise_if_degraded()` and the paste narrows the window in which a background byte could
  sit in the master in front of readline's echo of the paste. The reader is restarted in a
  `finally` when the command finished, or when the session is degraded (nothing is written
  to the PTY then, §4.3, and reading keeps a background writer from stalling). It is not
  restarted after a non-degrading exception mid-command (e.g. the `_Boom` test): bash may
  still be running that command, and its output must not be read as background.
- `_drain_pty()` (:1386): keeps chunks when `_bg_armed`, else drops them (today's
  behaviour). No second reader next to it — it runs only after the thread is joined.

No change to `session_terminal.py`: per the brief, the block is bytes to the caller; #78
wires it through `_Ownership.mirror` / `_write_mirror` (base `session_terminal.py:357-395`).

`docs/design/specs/pty-protocol/v1.md` (draft, editable): §6.6 first bullet gets the
boundary sentence (:492-497); the Conformance paragraph (:547-552) now claims vector 15 at
session level and only the buffering part of 13 and 14; the notice (#74) and the display
(#78) stay untested.

`.oss-scanner/threat_model.md`: the "Background output can't reach the screen during a
confirm" property (:150-158) now says what #120 builds and what waits for #74/#78; a new
Known-gaps bullet (:273-278) for the dropped window.

`tests/test_session_terminal.py` (:702-801): four tests, new API reached only inside test
bodies.

## The boundary — one deliberate refinement of the Invariant wording

The Invariant says "from the first moment after E that bash is seen blocked reading fd 0
... every byte read from the PTY master is background output". I add a settle of at most
50 ms after that sighting (10 ms quiet). Reason: Linux PTYs hand slave writes to the master
through a deferred flush (`tty_flip_buffer_push` queues work), so the prompt bash wrote
just before it blocked can become readable on the master a moment *after* we see it
blocked. Without the settle, a prompt byte could be counted as background output and (d)
would flake under load. The brief already allows "a background byte that lands in that
short window is a stated known limit"; the settle is part of that window and is written
into §6.6, the docstring and the threat model's Known gaps. If the human prefers the
strict reading, drop the `elif seen is not None: quiet_until = ...` branch and arm on
`seen` (3-line change); I'd expect occasional (d) flakes from that.

## Tests and how they map to the Success criterion

- `test_background_output_is_held_back_while_idle` — (a), (b), (d). The job prints
  `Run this? [y/N] `; the command writes the `?` as `\077`, because bash's job notices
  (`[1]+ Running ( sleep 0.3; printf '...' ) &`, and the later `Done` notice) repeat the
  command text and would otherwise put `Run this?` on the screen / in the output
  legitimately (§4.1). The test only sleeps 1 s, then checks waiting, runs `echo after`
  through `run(terminal=stand_in)`, checks neither the stand-in screen nor the result holds
  `Run this?`, then takes the block (exactly `header + b"Run this? [y/N] "`), checks waiting
  is false and a second take is `b""`.
- `test_a_chatty_background_job_is_not_stalled_and_its_tail_is_kept` — (c), (d). Differs
  from the brief's command by a leading `sleep 0.3`: without it `head` starts writing during
  the command, those bytes are the command's own output (§4.1) and the exact count 983040
  would not hold. With it, all 1 MiB arrives while idle. `~/bg.done` appears within 10 s
  with the test only polling the file; block is exactly
  `header + b"x"*65536 + b"\r\n[983040 bytes dropped]\r\n"`; the next command's output has
  no `x` run.
- `test_the_prompt_and_the_prompt_hook_are_not_background_output` — (d). PROMPT_COMMAND
  hook printing at every prompt (as `tests/test_session.py:1004-1013`); after start and
  after each of 3 commands plus 0.5 s idle, waiting is false; output stays `hello\r\n`.
- `test_commands_after_background_output_stay_clean_and_close_ends_the_reader` — (e).
  Takes a block, then 20 × `echo hello` each exactly `b"hello\r\n"`, not degraded; then
  leaves output waiting, calls `close()` in a bounded thread, checks it returned and no
  thread from after the test's start is still alive. A `run("wait")` before the take
  absorbs the job's `Done` notice, which §4.1 assigns to the next command — otherwise the
  first `echo hello` would legitimately contain it.

`test_job_notice_is_part_of_the_next_commands_output` (`tests/test_session.py:1016-1023`)
and the whole suite still pass.

## Evidence

- C4 (`engine/scripts/run-verify.sh`, the project's gate): green leg ran 24, failed 0; red
  leg (production hunks reverted) ran 24, failed 4 → `C4 PASS`. On the red leg the 1 MiB
  test fails on the real cause ("the background job stalled: nobody read the PTY while the
  session was idle"); the other three fail with `AttributeError` on the new API inside the
  test body (no import error).
- T3 (`engine/scripts/run-suite.sh`): 1105 passed, 1 skipped → `T3 PASS`.
- Flake check: the 4 new tests 8 runs in a row with 4 busy-loop processes loading the CPU:
  8/8 green, ~6.6 s each.
- `scripts/docs_links.py`: 0 broken. `scripts/docs_checks.py immutability`: OK (the spec
  is `status: draft`). `tests/test_docs_*.py`: 113 passed.
- Formatter / hooks: the target has no formatter config and no pre-commit hooks
  (`pyproject.toml`, no `.pre-commit-config.yaml`); CI runs pytest + the docs checks, both
  run above. Added lines are ≤ 93 chars (the files already have lines up to 100-103).

## Refuting my own test

- **(a) Genuine red?** Yes. With the production hunks reverted (the C4 red leg, run twice,
  on the last two patch versions) 4 of 4 new tests fail. The binding one is
  (c): on base nobody reads the PTY while idle, the 1 MiB job blocks on a full PTY, and
  `~/bg.done` never appears in 10 s. "waiting" and the block have no API on base.
- **(b) Production path?** Yes. Every test drives the real `nl_shell.session.Session` on a
  real bash 5.3 PTY; the reader thread, `_drain_pty`, `_Background` and the public
  `background_waiting` / `take_background_output` are production code. The stand-in is
  only the *real terminal* side (the existing `_StandIn` fixture), as in every other test
  in the file. No mock of the session.
- **(c) Fixture includes the fault?** Yes. The fault is "a background job writes while the
  session is idle and nobody calls it"; the tests start real `&` jobs that write after the
  command ended, and the test thread only sleeps or polls a file. (c) writes 16× the
  buffer size, so the drop/stall path is exercised, not avoided.

## Things for the human

- **New `forkpty` DeprecationWarnings.** The suite shows 5 `This process is multi-threaded,
  use of forkpty() may lead to deadlocks in the child` warnings with the patch; base shows
  1 (`test_busy_python_thread_stays_healthy`). The 4 new ones come from
  `test_aliases_cannot_reach_inside_the_hooks`, which starts a second `Session` while the
  first one's reader thread is alive. One session never forks while its own reader runs
  (`restart()` → `close()` stops it first; `_spawn` starts it only after the fork). The
  risk is a lock held by another thread being needed in the child between fork and exec;
  the reader holds no lock while in `select`, and only the buffer lock (which the child
  never touches) for a moment. Removing the warning would need a module-level registry
  that pauses every session's reader around any `_spawn` — about 15-20 lines (a
  `WeakSet` of sessions, a lock, stop/restart loops in `_spawn`). I did not add it: it
  guards a warning, not an observed failure, and it couples sessions to each other.
  Decide whether that is acceptable for the REPL (#78), which may host more than one
  session.
- **Exact block format** (`\r\n` line ends, dropped line after the bytes, a line break added
  only when the bytes don't end one) is my choice; the brief fixes only header / bytes /
  dropped-line order. #78 may want to adjust it when it renders the block.
- **The brief's (c) command** gained a `sleep 0.3` (reason above).
- Commit/PR wording: "Refs #120", not "Closes" (the brief: done-when needs #74 and #78).

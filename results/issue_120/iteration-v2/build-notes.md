# Build notes — issue 120 / buffer-background-pty-output (iteration 2)

Target: eduralph/nl-shell @ main (worktree base a6efb0a). Line numbers are in the patched
worktree (`/home/eddie/nl-shell/nl-shell.pdca-wt-l1`) unless marked "base".

This iteration starts from the iteration-1 patch (`iteration-v1/patch.diff`; its notes
describe the overall design and still hold) and changes three things: the two the
carry-forward asks for, plus a third bug that the new test exposed.

## Carry-forward: what changed and why

The finding: after a run() that raised without degrading (an `on_record` callback raising
at `S`, or a `KeyboardInterrupt` in `_wait_for_result`), (1) no reader thread ran, so a
background job stalled again, and (2) `_bg_armed` stayed `True` from the idle period
before, so the next run()'s first `_drain_pty` filed the interrupted command's leftover
output and the prompt under `[background output]`.

1. **`_bg_armed` is cleared at the paste** — `src/nl_shell/session.py:946-948`, just before
   `command_sent()` and the write. That is the point where, per the Invariant, background
   output ends ("up to the next paste"). Clearing it there, not in `_stop_background`,
   matters: `_stop_background` runs at the top of run() (:929), and the first `_drain_pty`
   (:932) still needs `_bg_armed` to keep what a background job wrote right before the
   paste. With the flag cleared at the paste, every way out of run() after it (return,
   exception, degrade) leaves it `False`.
2. **The reader restarts on every way out of run()** — `:962-968`. The `finished` flag and
   the `if finished or self._tracker.degraded` condition are gone; the `finally` always
   calls `_start_background()`, which returns at once if the session is closed (:833) and
   starts the thread unarmed (:835). Iteration 1 skipped the restart after an exception on
   the grounds that the interrupted command's output must not be read as background. The
   unarmed start already covers that: the reader drops everything until bash waits for its
   next key, which is after the interrupted command, its end marker and the prompt hook.
   Dropping that output is what base `_drain_pty` (base `session.py:756`, :1203-1208) did
   at the next run().
3. **The reader arms only on readline's untimed wait** — new `_waiting_for_key()`
   (`:1177-1193`), used by the reader at `:871` instead of `_reading_terminal()`. I found
   this while making test 1 below pass. With fixes 1 and 2 alone, it still failed: the
   block held `\x1b[?2004h$ `, the prompt. I traced bash's `/proc/<pid>/syscall` every
   0.5 ms (the scripts are in the worktree's `.scratch/`, which is not part of the patch).
   After a command, bash 5.3 first blocks in `pselect6(1, …)` **with a timeout** (5th
   argument set) for about 50 ms, writes the prompt, and only then enters the untimed
   `pselect6(1, …, NULL, …)`:

   ```
   # one traced run: syscall nr 270 = pselect6, nfds 0x1; 5th arg is the timeout
   (0.5142, 'sys', ['270', '0x1', ..., '0x7ffefeb79820', ...])   # timed wait
   (0.5644, 'sys', ['270', '0x1', ..., '0x0', ...])              # untimed wait
   # another run, reader-thread reads: bash first seen waiting at 0.519
   (0.5649, 'bgread', b'\x1b[?2004h$ ')                          # prompt arrives
   ```

   `_reading_terminal()` counts both waits. The reader saw the timed one, its 50 ms settle
   cap ran out, and it armed just before the prompt arrived. In the normal (no exception)
   path, iteration 1 got away with this only because run() returns about 50 ms after `E`
   (the trace shows run() returning at 0.5705), so the reader starts after the prompt is
   already out. That is a timing accident, not a guarantee. `_waiting_for_key()` keeps
   `_reading_terminal()` (fd 0 is this PTY) and adds one more read of the syscall line: a
   `read(0)`, or a `pselect6`/`select` on nfds 1 whose timeout argument is 0. On
   bash 5.1/5.2, readline's wait has no timeout, so this changes nothing there.
   `_reading_terminal()` itself, and so the prompt rule (`_wait_for_prompt`, the §4.2 third
   trigger), are unchanged.

   This narrows the Invariant's "first moment after E that bash is seen blocked reading
   fd 0 (`_reading_terminal()`)" to "...in a wait with no timeout". The aim is the one the
   Invariant states: the prompt and the prompt hook's output are not background output. I
   wrote the narrowing into §6.6 (`docs/design/specs/pty-protocol/v1.md:492-500`) and into
   the `take_background_output` docstring (`session.py:818-824`). The human should know
   about it: the brief named `_reading_terminal()` itself.

Unchanged from iteration 1: `BACKGROUND_LIMIT` (:314), `_Background` (:530), the
hand-over API (:802, :807), `close()` stopping the reader before the fd closes (:652),
`_drain_pty` keeping bytes when armed (:1408), the threat-model text, the conformance
paragraph. No change to `session_terminal.py`. As the brief says, #78 wires the block
through `_Ownership.mirror` / `_write_mirror` (base `session_terminal.py:357-395`).

## Tests (tests/test_session_terminal.py)

Iteration 1's four tests (:718, :744, :769, :782) cover criteria (a) to (e), as described
in `iteration-v1/build-notes.md`. Two tests are new, from the carry-forward:

- `test_after_an_exception_mid_command_the_leftover_is_not_background_output` (:805).
  The session idles 0.5 s, so the old code arms. Then run() raises `_Boom` from
  `on_record` at `S` while `sleep 0.5; printf 'LEFTOVER\n'` runs. That is the same trigger
  as `test_terminal_settings_restored_after_an_exception_mid_command` (:682-700). The
  `O` is written `\117`, so only the command's output spells LEFTOVER, not readline's echo.
  The test sleeps 1.5 s. It asserts "waiting" is false, runs `echo after`, asserts
  "waiting" is still false, and asserts the session is not degraded.
- `test_after_an_exception_mid_command_a_background_job_is_not_stalled` (:834). It starts
  `(sleep 1; head -c 1048576 /dev/zero | tr '\0' x; touch ~/bg.done) &` normally. Then
  `sleep 0.2` raises `_Boom` at `S`. The test only polls for the file: `~/bg.done` must
  appear within 10 s. The block must be exactly `header + x*65536 + "\r\n[983040 bytes
  dropped]\r\n"`, which also proves that no prompt bytes were filed. The next command's
  output must hold no `x` run, and the session must not be degraded.

The carry-forward also names `KeyboardInterrupt` during `_wait_for_result`. It takes the
same `finally` (:962-968) and the same cleared flag, so I did not add a separate test.
Sending a real SIGINT to the test process at a precise moment would be flaky.

## Evidence

- **C4** (`engine/scripts/run-verify.sh`, the project's gate): green leg ran 26, failed 0.
  Red leg (production hunks reverted to base) ran 26, failed 6, giving `PDCA-EVIDENCE: C4
  PASS`.
- **Red against iteration 1's code.** This is the check that matters for the carry-forward.
  I put iteration 1's `session.py` in place and ran the two new tests. Both fail, each for
  the reported reason: the leftover test with `AssertionError: b'[background output]\r\n…`
  (the prompt filed as background output, from the stale `_bg_armed`), and the stall test
  with `the background job stalled: nobody read the PTY after the exception`. Then I put
  the new `session.py` back.
- **Red with fixes 1 and 2 only** (before fix 3): the leftover test failed at :827 with the
  prompt `\x1b[?2004h$ ` in the block, and the stall test reported 983050 dropped bytes
  instead of 983040. The extra 10 bytes are that prompt. Fix 3 turns both green.
- **T3** (`engine/scripts/run-suite.sh`): 1107 passed, 1 skipped, giving `T3 PASS`.
  `test_job_notice_is_part_of_the_next_commands_output` passes.
- **Flake check:** the 7 background-related tests passed 6 runs in a row with 4 busy-loop
  processes loading the CPU, about 10.7 s per run.
- **Docs:** `scripts/docs_links.py` reports 0 broken links. `scripts/docs_checks.py
  immutability` reports OK (the spec is `status: draft`).
- **Formatter / hooks:** the target has no formatter config and no `.pre-commit-config.yaml`.
  CI runs pytest and the docs checks, and both pass above. No added line is over 100
  characters.

## Refuting my own test

- **(a) Genuine red?** Yes. With the production hunks reverted to base, 6 of 26 tests fail
  (C4 red leg). With iteration 1's `session.py`, both new tests fail on the reported
  defects. With fixes 1 and 2 but not fix 3, both still fail on the prompt bytes.
- **(b) Production path?** Yes. The tests drive the real `Session` on a real bash 5.3 PTY:
  the real reader thread, `_drain_pty`, `_Background`, `_waiting_for_key` and the public
  API. The exception comes from the real `on_record` hook, raised inside run()'s own
  `_wait_for_result`. Nothing is mocked.
- **(c) Fixture includes the fault?** Yes. The fixture raises a non-degrading exception
  mid-command after an idle period long enough to arm the old code. That is exactly the
  sequence in the finding. The stall test's job writes 16 times the buffer size after the
  exception, so a reader that never restarts blocks it for certain.

## For the human

- **The boundary narrowing (fix 3)** is my call. The brief names `_reading_terminal()`.
  Taken literally, bash 5.3's prompt is counted as background output whenever the reader
  starts watching before the prompt is out. Keeping the brief's literal wording would mean
  dropping fix 3, and the leftover test would then fail every time.
- **Forkpty DeprecationWarnings:** 5 with the patch, 1 on base. The same as iteration 1;
  see its notes.
- **A `read x` builtin interrupted by an exception:** bash then sits in an untimed
  `read(0)` while that command is still running, so the reader arms during it. The prompt
  rule has the same blind spot (`_wait_for_prompt` treats that state as a prompt), and the
  next run() pastes into `read`, as it does on base. I left it alone.
- Commit and PR wording: "Refs #120", not "Closes".

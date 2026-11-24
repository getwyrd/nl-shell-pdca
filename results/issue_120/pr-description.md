## Summary
**User impact:** When you start a job in the background (`some-command &`) and it prints
something while you are back at the prompt, you never see it. The text is quietly thrown
away when you run your next command. A job that prints a lot freezes partway through
until you happen to run another command.

This PR makes the session keep reading between commands and hold what background jobs
print in a bounded buffer, labelled `[background output]`, for the REPL to show later. It
never goes straight to the screen (where it could pose as a confirm prompt) and never
mixes into the next command's output.

Reported in [#120](https://github.com/eduralph/nl-shell/issues/120).

Showing the "background output waiting" notice during a confirm (#74) and printing the
block above the prompt (#78) build on this and are tracked in their own issues.

## What to look at
- `Session.background_waiting` and `Session.take_background_output()` in
  `src/nl_shell/session.py`: the new API the REPL will use.
- The reader thread (`_background_loop`) and where `run()` stops and restarts it. This is
  the part where a race or a leak would hide.
- The new tests at the end of `tests/test_session_terminal.py`.

To try it:

```python
from nl_shell.session import Session
s = Session.start()
s.run("(sleep 0.3; printf 'Run this? [y/N] ') &")
import time; time.sleep(1)   # call nothing on the session
s.background_waiting          # True
s.take_background_output()    # b'[background output]\r\nRun this? [y/N] '
```

On `main`, `background_waiting` does not exist, and the text is lost at the next `run()`.

## Root cause
Nothing read the PTY between commands. The bytes stayed in the kernel buffer until the
next `run()` called `_drain_pty()`, which read them and dropped them together with the
prompt (`src/nl_shell/session.py:756`, `:1203-1208` on `main`). A writer that filled
the PTY buffer blocked until then.

## Fix
- **Bounded buffer.** `_Background` keeps the newest `BACKGROUND_LIMIT` (64 KiB) bytes and
  counts the dropped ones. A lock guards it because the reader thread adds while the caller
  takes. `take()` returns the header line, the bytes, and `[N bytes dropped]` when N > 0,
  then empties the buffer.
- **What counts as background output.** Bytes count only from the moment after a command
  ends that bash is seen blocked in readline's untimed wait for a key (`_waiting_for_key`,
  built on the existing prompt check), plus a short settle time of at most 50 ms for the
  prompt still in transit. Before that point the bytes are the prompt and `PROMPT_COMMAND`
  output, and they are dropped as before. This avoids parsing the stream for prompts.
- **Reader thread.** It starts when the session starts and after every `run()`, on every
  exit path, including exceptions and degraded mode. It stops (woken through a pipe and
  joined) before `run()` touches the PTY and before `close()`. It never writes to the PTY.
- **No leaked shells.** The thread holds the session only through a `weakref`, and a
  `weakref.finalize` stops it. A `Session` dropped without `close()` is still collected,
  the thread is joined before the PTY fd closes, and bash exits as it did before.
- **Docs.** pty-protocol v1 §6.6 gets one paragraph giving the exact boundary and its known
  limit. The conformance paragraph says which vectors are now covered. The threat model's
  "Background output can't reach the screen during a confirm" control says what is built
  and what waits for #74/#78, and lists the dropped-byte window as a known limit.

## Verification
- **Claim:** background output written while the session is idle is buffered, does not
  reach the screen, and can be taken as a labelled block.
  - **Checked:** on `main`, the only reader between commands is `_drain_pty`, which drops
    everything (`src/nl_shell/session.py:1203-1208`, called at `:756`).
  - **Test:** `test_background_output_is_held_back_while_idle`
    (`tests/test_session_terminal.py:719`). It fails on `main` and passes with the fix.
- **Claim:** a job that writes far more than the PTY holds finishes while the session is
  idle. Only the last 64 KiB is kept, with an exact dropped count.
  - **Test:** `test_a_chatty_background_job_is_not_stalled_and_its_tail_is_kept`
    (`:745`). It writes 1 MiB with no newline, so the counts are exact: the block holds
    65536 bytes and reports 983040 dropped. On `main` the job never finishes, so the test
    fails. It passes with the fix.
- **Claim:** the prompt and prompt-hook output are not background output, and none of it
  leaks into a later `CommandResult`.
  - **Test:** `test_the_prompt_and_the_prompt_hook_are_not_background_output` (`:770`),
    plus the output checks in the two tests above. The existing
    `test_job_notice_is_part_of_the_next_commands_output` (`tests/test_session.py:1016`)
    still passes.
- **Claim:** no race between the idle reader and `run()`, and `close()` leaves no thread
  behind.
  - **Test:** `test_commands_after_background_output_stay_clean_and_close_ends_the_reader`
    (`:783`): 20 runs of `echo hello` after background output, then `close()` with output
    still waiting.
- **Claim:** after an exception inside `run()`, the reader runs again and the interrupted
  command's leftover output is not filed as background output.
  - **Test:** `test_after_an_exception_mid_command_the_leftover_is_not_background_output`
    (`:806`) and `test_after_an_exception_mid_command_a_background_job_is_not_stalled`
    (`:835`).
- **Claim:** a `Session` dropped without `close()` is collected and its bash exits.
  - **Test:** `test_a_session_dropped_without_close_is_collected_and_bash_ends` (`:866`).
    This guards against a regression only the new thread could cause, so it also passes
    on `main`. It fails against an earlier version of this patch that held the session
    strongly.
- **Doc claims:** the spec text this implements is `docs/design/specs/pty-protocol/v1.md:489-494`.
  The conformance paragraph it updates is `:536-540`. The threat-model control it makes
  true is `.oss-scanner/threat_model.md:150-153`, and the risk is the High row at
  `:305-306`.
- **Whole suite:** 1108 passed, 1 skipped, on real bash 5.3. With the production change
  reverted, 7 of the 27 tests in `tests/test_session_terminal.py` fail. With it, all 27
  pass.

## Known limits and follow-ups
- A background byte written during the short window between a command's end and bash
  waiting for its next key (at most about 50 ms after the prompt), or while bash's stdin
  is not the terminal, is dropped with the prompt. This is documented in §6.6, the
  docstring and the threat model.
- `run()` calls `_stop_background()` just before the `try` whose `finally` restarts the
  reader. A Ctrl-C during that join would leave no reader and leak the wake pipe's two fds.
  Moving the call inside the `try` is a small follow-up.
- `forkpty()` now runs while another session's reader thread may be alive, so Python warns
  about it (DeprecationWarning, seen when a second `Session` starts in the suite). It should
  be resolved before #78, either by dropping the Python `preexec_fn` in `_spawn` or by
  pausing readers during spawn.
- If the reader thread drops the last reference to a session, the session's cleanup
  (`PtyProcess.__del__`) runs on that thread. Nothing waits on it, and a 30-session stress
  run showed no errors.

Fixes #120

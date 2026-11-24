# Adversarial review — issue 120 / buffer-background-pty-output

**Result:** I could not break the main fix. I found one real regression (a Session that is
never closed now leaks its bash) and one new fork-safety risk. Both come from adding the
reader thread.

## The red→green evidence: holds

- `gate-logs/C4-verify.log`: 6 of 26 tests fail before the fix. Four fail only on a missing
  attribute (`AttributeError: ... 'background_waiting'`, e.g. `tests/test_session_terminal.py:728`),
  which proves the API is absent, not that the behaviour is wrong. Two fail on real
  behaviour: the 1 MiB job stalls because nobody reads the PTY
  (`tests/test_session_terminal.py:755` and `:854`, "the background job stalled"). Those two
  go through the production `Session.run` and the production reader thread, not a copy, so
  the red is real. The brief says the red rests on these, and that claim holds.
- Tried to make the prompt boundary fail (`src/nl_shell/session.py:858-895`,
  `_waiting_for_key` at `:1177-1192`): I ran 64 busy-loop processes on 32 cores, used a
  `PROMPT_COMMAND` hook, and ran 40 commands. The prompt was misfiled as background output
  0 times out of 40. `TMOUT=600` does not break the "wait with no timeout" check either:
  bash 5.3 still waits in `pselect6` with a NULL timeout. `read -t 2` inside an interrupted
  command waits with a timeout, so it does not arm the reader early. With `set -b`, the job
  notice shows up as background output, which is reasonable. I could not refute these parts.

## Findings

- NEEDS-HUMAN [impl] — **A Session that is never closed now leaks its bash process.**
  `src/nl_shell/session.py:838-844` starts the thread with `target=self._background_loop`,
  a bound method. The daemon thread holds a strong reference to the Session, so the
  Session, its `PtyProcess` and bash are never garbage-collected. Before this patch,
  `PtyProcess.__del__` (`ptyprocess/ptyprocess.py:370-385`) closed them. Test:
  `s = Session.start(); pid = s.pid; del s; gc.collect(); os.kill(pid, 0)`. With the patch,
  bash is **still alive**, and the thread `nl-shell-background-output` stays alive until the
  process exits. On the pre-fix base, bash is gone. A REPL or test that drops a session
  without `close()` (for example, after an exception that skips the close) now keeps a
  shell and its jobs running. Fix: have the thread hold only what it needs (the fd, the
  `_Background`, the pid and proc paths for the syscall check) or a `weakref` to the
  Session. Add a test that drops an unclosed Session and checks that bash exits.
- NEEDS-HUMAN [human] — **New warning: `forkpty()` now runs while another thread is
  alive.** `gate-logs/T3-suite.log:28-34` shows `DeprecationWarning: This process ... is
  multi-threaded, use of forkpty() may lead to deadlocks in the child`. It fires in
  `test_aliases_cannot_reach_inside_the_hooks`, which starts a second Session while the
  first one's reader thread runs. `_spawn` (`src/nl_shell/session.py:681-694`) runs a Python
  `preexec_fn` (`wire_fd3`) in the forked child. Python's docs say this is unsafe when other
  threads exist. Today the REPL holds one session, and `restart()` stops the thread first
  (`close()` at `:652`), so it is rare. But any second session, or any later
  `subprocess(preexec_fn=...)` in the same process, now forks with a live thread. A human
  should decide whether to accept this, or whether to drop the Python `preexec_fn` (or
  pause readers during spawn) as part of keeping a thread.
- **Minor, no tag needed:** a session that never arms (for example, an interrupted
  long-running foreground command, or bash never waiting on fd 0) keeps polling `/proc`
  every 5 ms (`_PROMPT_POLL`, `src/nl_shell/session.py:326`; loop at `:866-878`), with two
  file reads per poll, for as long as it stays idle. That costs some CPU but breaks
  nothing.
- **Minor, no tag needed:** if `os.pipe()` fails in the `finally` of `run()`
  (`src/nl_shell/session.py:962-968` → `:836`, e.g. EMFILE, meaning out of file
  descriptors), the `OSError` replaces a command result that had already succeeded or
  the real exception. This is an unlikely edge case.

## Reviewer claims checked

- "Never silently discarded" (brief, Invariant) holds only with the stated limits: bytes
  in the ≤50 ms prompt window, bytes when `run()` comes before the reader arms, and bytes
  when fd 0 is redirected. The docstring (`src/nl_shell/session.py:826-829`), §6.6 and the
  threat model say this openly, so I don't count it as a hidden overclaim.

## Process note

To get the pre-fix result for the leak test, I ran `git stash` / `git stash pop` once on
`$PDCA_TARGET`. That was a write to a read-only input. I then checked that `git diff` in
the target is identical to `patch.diff` (ignoring `index` lines) and that no stash is left
behind. My other scratch files (`probe*.py`, `leak.py`, `load.py`, `home/`, `cur.diff`)
are in this sandbox.

<!-- pdca:leaf-complete -->

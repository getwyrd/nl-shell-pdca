# Build notes — issue 120 / buffer-background-pty-output (iteration 3)

Target: eduralph/nl-shell @ main (worktree base a6efb0a). Line numbers are in the patched
worktree (`/home/eddie/nl-shell/nl-shell.pdca-wt-l1`) unless marked "base".

This iteration starts from the iteration-2 patch (`iteration-v2/patch.diff`). Its notes and
iteration 1's still describe the design: the buffer, the hand-over API, the arming rule
(`_waiting_for_key`), the reader restart on every way out of `run()`, and the spec and
threat-model text. The only change is how the reader thread is tied to the session, which
is what the round-2 carry-forward asks for.

## Carry-forward: the reader thread kept an unclosed session alive

The finding: the thread ran `target=self._background_loop`, a bound method, so it held a
strong reference to the Session. A Session dropped without `close()` was never collected,
so `PtyProcess.__del__` never ran and bash (and its jobs) stayed alive until the process
exited. Base collects it and bash ends.

Fix (`src/nl_shell/session.py`):

1. **The loop is a module-level function that holds the session only weakly** —
   `_background_loop` (:1472). It gets `weakref.ref(session)`, the PTY fd, the wake pipe's
   read end, a stop `threading.Event`, and the `_Background` buffer (:843-849). It turns
   the weak reference into a real one only inside `_bash_waiting_for_key` (:1521), for the
   one `/proc` reading it needs (`Session._waiting_for_key`, :1139), and drops it on return.
   The rest of the time, including the untimed `select` once armed, it holds no reference
   to the session.
2. **The armed flag moved onto `_Background`** (`armed`, :531-541) so the thread can set
   it without the session. `run()` (:910) and `_drain_pty` (:1379) read and clear it
   there. The behaviour is the same as `_bg_armed` in iteration 2.
3. **One stop routine, run by `weakref.finalize`** — `_stop_reader` (:1534). It sets the
   stop event, writes to the wake pipe, joins the thread (unless it runs on that thread
   itself), and closes the pipe. `_start_background` registers it as
   `weakref.finalize(self, _stop_reader, …)` (:850). `_stop_background` (:853) just calls
   that finalizer, so `close()` and the next `run()` stop the thread the same way as
   before. When a session is dropped, CPython runs the finalizer before it releases the
   session's attributes, so the thread is stopped and joined before `PtyProcess.__del__`
   closes the PTY fd and the number can be reused.
4. **The reader may drop the last reference itself.** If the caller drops the session while
   the reader is inside `_bash_waiting_for_key`, the session is freed on the reader thread,
   and `_stop_reader` runs there. It does not join itself (:1542). The loop checks `stop`
   before every `select` (:1500), so it never touches the fd or the closed wake pipe after
   that.

I considered a second option: a small object with the pid, `proc_root` and tty device
number that the thread uses instead of the session. That means moving `_syscall`,
`_reading_terminal`, `_stdin_is_terminal` and `_waiting_for_key` (base `session.py:1140-
1212`, about 70 lines, which the prompt rule and the §4.2 checks also use) onto it, or
copying them. It would still need the same finalizer, because the thread holds the fd
number either way and must stop before the fd closes. The weak reference keeps one copy of
the prompt-rule code, so I chose it.

## Test (tests/test_session_terminal.py)

New: `test_a_session_dropped_without_close_is_collected_and_bash_ends` (:866). It starts a
Session directly (not through the `start_session` fixture, which keeps a reference for
teardown), runs `(sleep 0.2; printf 'BG-TEXT') &`, and waits until background output is
waiting. That proves the reader ran and armed. Then it does `del session; gc.collect()` and
asserts: the weak reference is dead, bash's pid is gone within 5 s (`os.kill(pid, 0)`
raises `ProcessLookupError`), and no thread started by the test is still alive. If the
session leaks (the red case), the `finally` closes it so the run does not leave a bash
behind.

The other 6 background tests from iterations 1-2 are unchanged.

## Evidence

- **C4** (`engine/scripts/run-verify.sh`, run with `PDCA_BRIEF_BASE=origin/main`): green
  leg 27 of 27 pass. Red leg (production hunks reverted) 7 of 27 fail, giving
  `PDCA-EVIDENCE: C4 PASS`.
- **Red against iteration 2's code**, which is the check for this carry-forward. I put base
  `session.py` + iteration 2's `session.py` hunks in place and ran the new test. It fails
  with `AssertionError: the dropped session is still referenced`, the reported defect.
  Then I restored the iteration-3 file (`git diff --stat` confirms it).
- On base the new test passes: base has no thread, so it is a guard against this
  regression, not red evidence on base. The red evidence on base comes from the other 6.
- **T3** (`engine/scripts/run-suite.sh`): 1108 passed, 1 skipped, giving `T3 PASS`.
  `test_job_notice_is_part_of_the_next_commands_output` passes.
- **Repeat runs:** the 9 background, exception and prompt-hook tests passed 4 runs in a
  row (about 11.3 s each).
- **Stress script** (`.scratch/stress_drop.py` in the worktree, not part of the patch): 30
  sessions dropped without `close()` at three moments: right after start (reader still
  polling `/proc`, so the reader often drops the last reference), after 0.3 s idle
  (armed, in an untimed `select`), and after a background job wrote. Half had
  `gc.collect()`, half used refcount only. In all 30 the session was freed within about
  1 ms, bash exited, the thread ended, and `threading.excepthook` caught nothing.
- **fd count:** the stress run leaks 1 fd per dropped session, and base leaks exactly the
  same (5 → 34 on both). It is the control pipe `_ctl`, which only `close()` releases on
  base. The wake pipe is closed by `_stop_reader`, so the patch adds no leak. I left `_ctl`
  alone: it is base behaviour and out of scope.
- **Docs / hooks:** `scripts/docs_links.py` reports 0 broken links. The spec and
  threat-model text are unchanged from iteration 2. The target has no formatter config and
  no `.pre-commit-config.yaml`. No added line is over 100 characters.

## Refuting my own test

- **(a) Genuine red?** Yes. With iteration 2's `session.py` the new test fails on the
  reported defect (session still referenced, so bash stays alive). With the production
  hunks reverted to base, 7 of 27 tests fail (C4 red leg). The new test is green on base,
  as expected: it guards against a regression that only this patch's thread could cause.
- **(b) Production path?** Yes. A real `Session` on a real bash 5.3 PTY, the real reader
  thread, the real `weakref.finalize` and `PtyProcess.__del__`. Nothing is mocked.
- **(c) Fixture includes the fault?** Yes. The session is dropped after the reader has run
  and armed (background output is waiting), so the thread is alive at the drop. That is
  the state in which iteration 2's bound method kept the session alive.

## For the human

- Everything in iteration 2's "For the human" list still holds: the narrowing of the
  boundary to readline's untimed wait, the forkpty DeprecationWarnings (5 with the patch,
  1 on base), and the `read x` case.
- The session is freed on whichever thread drops the last reference. If that is the reader
  thread, `PtyProcess.__del__` (its 0.1 s `delayafterclose` and the terminate) runs there,
  not on the caller's thread. Nothing waits on it, and the stress run showed no errors.
- Commit and PR wording: "Refs #120", not "Closes".

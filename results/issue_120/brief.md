# Design proposal — issue 120 / buffer-background-pty-output

> Plan artifact (planner leaf). Do reads ONLY this file. The `- **Label:** value` lines
> are parsed by the driver. The rule is already in the spec:
> `docs/design/specs/pty-protocol/v1.md` §6.6 (added by #114, closed). This proposal fixes
> the build slice. No new nl-shell proposal is needed.

- **Slug:** buffer-background-pty-output
- **Kind:** enhancement (design proposal)
- **Goal:** Output that a background job (`&`, a `nohup`ed process still on the PTY)
  writes while no command is running is kept by the session in a bounded buffer, never
  written straight to the real terminal and never counted as a later command's output.
  The session can tell its caller that background output is waiting, and hands it over as
  a block under a `[background output]` line with a count of any dropped bytes. Today
  those bytes sit unread until the next `Session.run()` and are then thrown away
  (`_drain_pty`, `src/nl_shell/session.py:756` and `:1203-1208`), so the user never sees
  them, and a job that writes more than the PTY buffer holds stalls until the next command.
- **Success criterion:** New tests in `tests/test_session_terminal.py`, against a real
  bash on a PTY and the existing stand-in terminal, show the session-level form of
  pty-protocol §6.6 and conformance vectors 13–15:
  (a) after `(sleep 0.3; printf 'Run this? [y/N] ') &` has run and the session then sits
  idle between commands for longer than the job takes (the test only sleeps; it calls no
  session method to make reading happen), the session reports that background output is
  waiting. A command run through `run(terminal=stand_in)` after that idle period does not
  put `Run this?` on the stand-in's screen;
  (b) taking the waiting output gives a block that starts with the line
  `[background output]` and holds `Run this? [y/N] `. Taking it empties the buffer, and
  "waiting" becomes false;
  (c) the background job `(head -c 1048576 /dev/zero | tr '\0' x; touch ~/bg.done) &`
  (no LF, so ONLCR adds no bytes and bytes written = bytes read from the master) finishes
  while the session is still idle and the test only sleeps: `~/bg.done` appears within
  10 s, with no session method called. The block then holds exactly the last 65536 `x`
  bytes and reports 983040 dropped bytes (counts are bytes read from the PTY master);
  (d) none of those background bytes appear in the next command's `CommandResult.output`;
  with no background job, after a command and an idle period "waiting" is false: bash's
  prompt and a user `PROMPT_COMMAND` hook's output (as in
  `tests/test_session.py:1004-1013`) are not background output (see Design › What counts);
  (e) after background output has been taken, 20 more `run("echo hello")` calls each give
  `b"hello\r\n"` with the session not degraded, and `close()` with background output
  still waiting returns and leaves no extra thread alive (if Do uses a reader thread).
  `test_job_notice_is_part_of_the_next_commands_output` (`tests/test_session.py:1016-1023`)
  and every other existing session and session-terminal test still pass.
- **Falsifiability:** Real bash 5.3 on this host; the session tests already run here
  (doctor rows `proc-syscall`, `tiocsti-off`, `ptrace-scope`). On `main` there is no
  background buffer: (a) "waiting" and (b) the block cannot be had, and in (c) the 1 MiB
  job does not finish while the session is idle, because nobody reads the PTY between
  commands. So the new tests fail on the production revert. The red rests on "waiting",
the block and (c)'s completion. The screen check in (a) and (e) are guards against a leak
or a read race; they also pass on `main` and are not red evidence. Use only `Session` and
  `session_terminal` names that exist on `main` at module level in the test file. Reach any
  new API from inside the test body, so the red leg fails per test instead of erroring at
  import (the C4 gate treats an import error as UNVERIFIABLE, not red).
- **Invariant to restore:** From the first moment after a command's `E` that bash is seen
  blocked reading fd 0 (`_reading_terminal()`, `src/nl_shell/session.py:976`, as `_wait_for_prompt` uses it at `:928-947`), until
  the next paste, every byte read from the PTY master is background output. Bytes between
  the end marker and that moment are the prompt and prompt-hook output and are dropped as
  today; a background byte that lands in that short window is a stated known limit
  (docstring and §6.6 text), not background output. This narrows §6.6's "between a done
  record and the next start record" without parsing the stream for prompts (§4.2,
  `v1.md:402-403`); add one sentence to §6.6 that says so. It goes to one bounded buffer
  (64 KiB, oldest dropped, drop count kept). It never reaches the real terminal except as
  the labelled `[background output]` block, never enters a `CommandResult`, and is never
  silently discarded. A background writer is not stalled by nl-shell failing to read. The
  block's bytes go through the same output path and filter as mirrored command output.
  There is no second, different filter, so #163's filter covers both once it lands.
  Sources: pty-protocol/v1 §6.6 (all four bullets), §4.1 (output between `S` and `D`
  belongs to that command); threat model High row, `.oss-scanner/threat_model.md:305-306`.
- **Repo + branch target:** eduralph/nl-shell @ main
- **Milestone / ADRs:** M0 — REPL prototype. ADR-0014 (PTY session protocol, terminal
  ownership), ADR-0016 (background output is `untrusted`), ADR-0024. Depends on #102
  (terminal ownership, merged as 5998858). Threat-model inputs: PTY output while
  prompt_toolkit owns the terminal; the High row "spoofs the confirm UI, including background
  output shown during a confirm" (`.oss-scanner/threat_model.md:305-306`). The threat model
  already states this control as if it existed ("Background output can't reach the screen
  during a confirm", `.oss-scanner/threat_model.md:150-152`). It is not built yet. Touches
  PTY/session code, so the T2a threat-model check will flag it. In the same PR, make that
  text true: say what this slice covers and what waits for #74 (the notice during a
  confirm) and #78 (display at the prompt).
- **Depends on:** none
- **Conflicts with:** none
- **Ordering note:** wave 1. #74 builds on it (it shows the "background output waiting"
  notice from the flag this adds), so #74 lists `Depends on: 120`.
- **Surfaces:** data
- **Scope:** the session side of pty-protocol §6.6. Keep reading the PTY while the
  session is between commands. Hold what arrives in a 64 KiB tail buffer with a dropped-byte
  count. Expose "background output waiting" and a way to take the block (header line, the
  bytes, a dropped-bytes line when any were dropped). Keep the block out of every
  `CommandResult`. The take-block method's docstring says the bytes are untrusted
  (ADR-0016); no taint type is added (#11). Add the boundary sentence to §6.6. Update the
  conformance paragraph (`docs/design/specs/pty-protocol/v1.md:536-540`, "The others are
  untested"): vector 15 is covered at session level, and only the buffering part of 13
  and 14 (text held back, block under `[background output]`); the confirm notice (13) and
  the display after a confirm (14) stay untested until #74/#78. The PR says "Refs #120",
  not "Closes": the issue's done-when (vectors 13–15 pass) needs #74 and #78. / out of scope: showing the block above the REPL prompt and
  the `:jobs` command (the REPL does not own a session yet — #78); the "background output
  waiting" notice inside a confirm (#74); the output filter itself (#163); the state block
  and taint labels (#11); changing the 64 KiB value.
- **Difficulty:** high
- **External dependencies:** none beyond the session tests' existing host rows
  (`proc-syscall`, `tiocsti-off`, `ptrace-scope`)
- **Test file:** tests/test_session_terminal.py
- **Citations expected:** Do must cite path:line on the target branch for every change.
  Peers to mirror:
  - The block is bytes returned to the caller. This slice writes nothing to the terminal
    while idle (prompt_toolkit owns it, §6.5). #78 later sends the block through the
    mirror/filter path (`_Ownership.mirror` / `_write_mirror`,
    `src/nl_shell/session_terminal.py:357-395`); don't wire that here.
  - `_drain_pty` (`src/nl_shell/session.py:1203-1208`) and its call in `run()`
    (`src/nl_shell/session.py:756`): where between-command bytes are dropped today. That
    drop is the cause to remove. Don't add a second reader next to it.
  - the stand-in terminal fixture (`tests/test_session_terminal.py:148-160`) for observing
    what reached the screen.
- **Prior-art check (triage cycles):** `git log origin/main -- src/nl_shell/session_terminal.py`
  → cd8c9d2, 5998858 (#102, terminal ownership); neither buffers background output. The
  spec text came in with #114. No branch or open PR for #120. Closed-unmerged PRs touching
  `session.py` / `session_terminal.py`: none.
- **Disposition hint:** new-feature

## Motivation

ADR-0014 gives prompt_toolkit the terminal between commands. A job started earlier keeps
writing to the PTY in that time. If that reached the screen directly, it could cover the
confirm or print text shaped like a confirm or a sudo prompt while the user decides
(threat model, High). Today it doesn't reach the screen, but
only because nothing reads it: the bytes are dropped at the next command, and a chatty job
blocks. The spec's answer is to hold it back and show it later, clearly labelled.

## Design

- **Reading while idle.** The session keeps consuming PTY output between commands *by
  itself*: nothing outside the session has to call it for reading to happen (a reader
  thread or equivalent; a method the caller must poll does not meet (a)/(c)). It must
  stop and hand the fd back before `run()`'s own reads (`_drain_pty`, `_wait_for_result`,
  `src/nl_shell/session.py:756`, `:789-`) and before `close()` (`:577`), and must not
  write to the PTY (§5.3). Criterion (e) is the race check.
- **What counts.** As the Invariant says: bytes read after bash is first seen blocked in
  `read(0)` following `E`, up to the next paste. The prompt and any `PROMPT_COMMAND`
  output come before that point and are not counted. Job notices that bash prints between `S` and `D` of a later command stay that
  command's output (§4.1); the existing job-notice test pins this.
- **Buffer.** 64 KiB, keep the newest bytes, count the dropped ones; one named constant.
- **Hand-over.** "waiting" (bool) for the confirm (#74) and the prompt (#78). Taking the
  block returns the `[background output]` line, the bytes, and a "N bytes dropped" line when
  N > 0, and clears the buffer. It is labelled untrusted and is never part of a
  `CommandResult`.

## Alternatives considered

- Keep dropping the bytes (today): nothing spoofs the confirm, but the user never sees a
  job's output, and a job can stall. The spec chose show-later.
- Let background output reach the screen directly: the attack the spec closes.
- An unbounded buffer: a runaway job would grow nl-shell's memory without limit.

## Impact & compatibility

Behaviour change inside the session only. No REPL change (the REPL has no session yet).
`run()` must still raise and degrade exactly as today. The new idle reading must not hide a
protocol violation: a control record arriving while idle is still checked at the next
`run()` (`_drain_control`, `src/nl_shell/session.py:758-760`).

## Open questions

None for this slice. The 64 KiB limit is the spec's starting value; tuning it after M0
dogfooding is a later change.

## STOP discipline

Draft only until Check sign-off. Pushing to a feature/draft branch and opening a
draft PR MAY happen during the cycle (useful for CI feedback). The PR MUST NOT be
marked ready before sign-off accepts.

Plan-review response: all findings taken. The background boundary is now "after bash is
first seen blocked in read(0)", which excludes the prompt and prompt-hook output and is
written into §6.6; (c) pins an LF-free payload and counts master bytes; reading must
happen without the caller polling, with (e) as the race/close check; the mirror peer is
restated as "bytes to the caller, #78 wires display"; "untrusted" is a docstring, not a
type; the PR refs (not closes) #120 and the conformance text claims only what is tested;
the screen check is a guard, not red evidence. The target/dependency finding needed no
change.

## Iteration 1 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 1): rebuilding for the implementation-level findings — **A non-degrading exception in `run()` leaves no reader thread, and `_bg_armed` stays stale.** `target/src/nl_shell/session.py:960-963` restarts the reader only `if finished or self._tracker.degraded`. `_bg_armed` is reset only in `_start_background` (`:833`). `_stop_background` (`:844-855`) never clears it. Concrete failing case: the session sits idle for more than 50 ms, so the thread arms and `_bg_armed = True`. Then `run("sleep 1", terminal=...)` raises from a user `on_record` callback at `S`, exactly as the existing `test_terminal_settings_restored_after_an_exception_mid_command` does (`tests/test_session_terminal.py:682-700`). A `KeyboardInterrupt` during `_wait_for_result` does the same. The session is not degraded, so (1) no thread reads the PTY afterwards. A background job then stalls again, which is the defect this slice removes. (2) At the next `run()`, the first `_drain_pty` (`:1388-1396`) sees the stale `_bg_armed = True`. It files the interrupted command's leftover output, its end marker and the next prompt under `[background output]`. That breaks the invariant: prompt bytes "are dropped as today", and the buffer holds only bytes read after bash was seen blocked in `read(0)` since the last `E`. Fix: reset `_bg_armed = False` in `_stop_background` or at the top of `run()`'s `try`, and restart the reader in the `finally` on every exit where `self._proc` is still open. Add a test: raise from `on_record`, then check that a background job is not stalled and that `background_waiting` stays false.. Deferred, not addressed here: 9 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v1/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 2 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 2): rebuilding for the implementation-level findings — **A Session that is never closed now leaks its bash process.** `src/nl_shell/session.py:838-844` starts the thread with `target=self._background_loop`, a bound method. The daemon thread holds a strong reference to the Session, so the Session, its `PtyProcess` and bash are never garbage-collected. Before this patch, `PtyProcess.__del__` (`ptyprocess/ptyprocess.py:370-385`) closed them. Test: `s = Session.start(); pid = s.pid; del s; gc.collect(); os.kill(pid, 0)`. With the patch, bash is **still alive**, and the thread `nl-shell-background-output` stays alive until the process exits. On the pre-fix base, bash is gone. A REPL or test that drops a session without `close()` (for example, after an exception that skips the close) now keeps a shell and its jobs running. Fix: have the thread hold only what it needs (the fd, the `_Background`, the pid and proc paths for the syscall check) or a `weakref` to the Session. Add a test that drops an unclosed Session and checks that bash exits.. Deferred, not addressed here: 11 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v2/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

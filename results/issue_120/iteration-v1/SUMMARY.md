# Result — issue 120 / buffer-background-pty-output

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: Output that a background job (`&`, a `nohup`ed process still on the PTY)
  writes while no command is running is kept by the session in a bounded buffer, never
  written straight to the real terminal and never counted as a later command's output.
  The session can tell its caller that background output is waiting, and hands it over as
  a block under a `[background output]` line with a count of any dropped bytes. Today
  those bytes sit unread until the next `Session.run()` and are then thrown away
  (`_drain_pty`, `src/nl_shell/session.py:756` and `:1203-1208`), so the user never sees
  them, and a job that writes more than the PTY buffer holds stalls until the next command.
- Success criterion: New tests in `tests/test_session_terminal.py`, against a real
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
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: the session side of pty-protocol §6.6. Keep reading the PTY while the
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

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (4 of 24 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — security-relevant paths touched and the threat model updated: docs/design/specs/pty-protocol/v1.md src/nl_shell/session.
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review #120: continuously drain idle PTY output into a bounded, labelled background buffer without leaking it to the terminal or later command results.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The brief gives observable idle-reading, overflow, isolation and lifecycle criteria, with REPL display deferred; target docs/design/specs/pty-protocol/v1.md:489 and tests/test_session_terminal.py:717 ground the session slice. |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing only session.py reproduced the missing background_waiting API on real bash; the frozen test run also shows the chatty job stalling and four ordinary failures, not collection errors (gate-logs/C4-verify.log:116). |
| C3 Change | PASS | Changes stay within session buffering, regression coverage and the corresponding spec/threat model; independent syntax parsing and git diff --check passed (src/nl_shell/session.py:530; tests/test_session_terminal.py:717). |
| C4 Verification (red→green) | PASS | Restoring the stash independently passed real-PTY idle buffering, exact take/reset, next-command isolation and thread cleanup; frozen pytest evidence shows 24 green versus four red (gate-logs/C4-verify.log:118). |
| C5 Causal adequacy | PASS | Autonomous draining removes the unread-PTY cause of writer stalls, with exclusive reader handover before command execution; no optional-capability probe papers over a load-time cause (src/nl_shell/session.py:856; src/nl_shell/session.py:927). |
| T1 Structure | PASS | One locked tail buffer and explicit wake/join ownership keep idle reading separate from command protocol tracking and terminal rendering (src/nl_shell/session.py:530; src/nl_shell/session.py:844). |
| T2 Shape | PASS | Threat-model changes disclose buffering, deferred UI controls and discarded-output limits; the frozen scanner confirms the required threat-model touch (gate-logs/T2-threat-model.log:11; .oss-scanner/threat_model.md:150). |
| T3 Runtime | PASS | Frozen full-suite evidence reports 1105 passed, one skipped and five forkpty warnings; local pytest is unavailable, so this is log-supported rather than an independent suite rerun (gate-logs/T3-suite.log:27; gate-logs/T3-suite.log:37). |
| T4 Contribution | N/A | Contribution artifacts are absent by design; the substantive audit must rerun at publish (gate-logs/T4-contribution.log:11). |
| T5 Judgment | NEEDS-HUMAN | Decide whether the additional post-read(0) discard interval of up to 50 ms is acceptable scope, since it can lose genuine background bytes beyond the brief's boundary; also confirm affected-path merged and closed/rejected prior art, since this snapshot has only one base commit and no remotes, while the brief records a narrower history search (docs/design/specs/pty-protocol/v1.md:495; brief.md:113). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the session-only delivery and documented loss window for the intended workflow; real-PTY smoke and frozen tests establish buffering, but confirm notices and filtered prompt display remain future work (docs/design/specs/pty-protocol/v1.md:544; src/nl_shell/session.py:806). |

Verification limits: Python 3.14 and ptyprocess were available; pytest was not installed. Instance-root gate wrappers were unavailable here, so their complete frozen logs were inspected. Host-dependent PTY functionality was exercised directly, without a shim or curated topology. The independent buffer check also confirmed the exact 65,536-byte tail, 983,040 dropped-byte count and reset after a 1 MiB input. The disposable target's production stash was restored. No stale-target caveat was needed. No INTEGRATION.md was present in the provided target.

The first local smoke assertion mistakenly treated the repeated command text in bash's Done notice as leaked payload. Repeating the check with an escaped payload distinguished the two and passed; job notices remain legitimate command output as required by the brief.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 120 / buffer-background-pty-output

I tried to break the evidence, the fix and the verdict. The red→green holds, and the happy paths do what the brief asks. I found one real gap on the exception path in `run()`, plus some weaker points.

- NEEDS-HUMAN [impl] — **A non-degrading exception in `run()` leaves no reader thread, and `_bg_armed` stays stale.** `target/src/nl_shell/session.py:960-963` restarts the reader only `if finished or self._tracker.degraded`. `_bg_armed` is reset only in `_start_background` (`:833`). `_stop_background` (`:844-855`) never clears it. Concrete failing case: the session sits idle for more than 50 ms, so the thread arms and `_bg_armed = True`. Then `run("sleep 1", terminal=...)` raises from a user `on_record` callback at `S`, exactly as the existing `test_terminal_settings_restored_after_an_exception_mid_command` does (`tests/test_session_terminal.py:682-700`). A `KeyboardInterrupt` during `_wait_for_result` does the same. The session is not degraded, so (1) no thread reads the PTY afterwards. A background job then stalls again, which is the defect this slice removes. (2) At the next `run()`, the first `_drain_pty` (`:1388-1396`) sees the stale `_bg_armed = True`. It files the interrupted command's leftover output, its end marker and the next prompt under `[background output]`. That breaks the invariant: prompt bytes "are dropped as today", and the buffer holds only bytes read after bash was seen blocked in `read(0)` since the last `E`. Fix: reset `_bg_armed = False` in `_stop_background` or at the top of `run()`'s `try`, and restart the reader in the `finally` on every exit where `self._proc` is still open. Add a test: raise from `on_record`, then check that a background job is not stalled and that `background_waiting` stays false.

- **Red evidence is thin for three of the four tests.** `gate-logs/C4-verify.log:34,83,108`: on the pre-fix code, (a)/(b), (d) and (e) fail only with `AttributeError: 'Session' object has no attribute 'background_waiting'`. Any stub property would turn them green. Only `test_a_chatty_background_job_is_not_stalled_and_its_tail_is_kept` (`log:66`, the stall) goes red for a behavioural reason. The brief allows this ("the red rests on 'waiting', the block and (c)'s completion"), so this is not a refutation. The C4 summary "4 of 24 failed" still overstates how much behaviour was shown red: one test proves the idle reader exists. (a), (b) and (d) are proven only on the green side.

- **The prompt boundary is a timing guess, and it is tested only on an idle host.** `target/src/nl_shell/session.py:865-875` arms after at most `_PROMPT_SETTLE_MAX` (50 ms) once bash is seen in `read(0)`. If the PTY flush is delayed under load, so the prompt or the readline bracketed-paste enable `\e[?2004h` reaches the master more than 50 ms after bash blocks, those bytes become "background output". `background_waiting` then goes true with no job at all, which would raise a false notice in #74's confirm. The spec and threat-model text state the opposite known limit (background bytes dropped), not this one (prompt bytes kept). `test_the_prompt_and_the_prompt_hook_are_not_background_output` runs only on a quiet host. Advisory only; I have no failing run to show.

- **The unarmed loop can poll /proc forever.** `target/src/nl_shell/session.py:865-876`: if bash is never seen in `read(0)`, the thread polls `/proc/<pid>/syscall` every 5 ms until the next `run()`. That happens when fd 0 is redirected, or when `_ProcUnreadable` keeps firing (it is swallowed at `:871-872`). That is about 200 wakeups a second for the whole idle period, including when degraded (the thread is also started on degrade, `:962-963`). This is low cost, not a correctness bug. I'm noting it as a resource issue that the patch adds.

- **Other attacks that did not land:**
  - Thread-safety of `_reading_terminal` from the reader thread. It reads only `_proc.pid`, `proc_root` and `_tty_rdev`, and `close()` and `run()` stop and join the thread first (`:652`, `:927`).
  - Losing bytes between the two `_drain_pty` calls. `_wait_for_prompt` (`:1111-1129`) does not read the PTY.
  - Exact block bytes for (c). The `\r\n` is added before the dropped line only when the data does not end in LF (`_Background.take`).
  - `close()` leaving a thread behind. It is covered by (e) and the join in `_stop_background`.
  - The SessionTimeout path. It degrades before raising, so the reader is restarted.
  - T3 is green: 1105 passed, 1 skipped (`gate-logs/T3-suite.log`).

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory) — issue 120, buffer background PTY output

**Attacker-reachable input this diff touches:** command output (threat model "Where untrusted input enters" item 1). Here that means bytes a background job writes to the PTY while no command runs. Whoever controls that job's output controls them: a cloned repo's script, a fetched page piped through a job, and so on. Nothing else on the untrusted list is touched. There are no gate, classifier, sudo, history, log or model-context changes.

**Verdict: no finding at any severity on the threat model's scale.** The patch narrows an attack surface. It does not widen one.

What I checked, with paths in the target source:

- **Background bytes never reach the real terminal.** The reader thread `_background_loop` (`src/nl_shell/session.py:858-894`) only calls `os.read` on the PTY and `_Background.add`. It never writes to the PTY (§5.3) or the terminal. `take_background_output` (`src/nl_shell/session.py:807-826`) returns bytes to the caller, and no caller exists yet. So the High row "spoofs the confirm UI, including background output shown during a confirm" (`.oss-scanner/threat_model.md:305-306`) cannot be reached through this diff.
- **Background bytes never enter a `CommandResult`.** `run()` stops the thread first (`src/nl_shell/session.py:927`). It drains twice: at the start, and again right before the paste (`:930`, `:944`). Each drain sends bytes to the buffer when armed, or drops them (`:1387-1396`). Only bytes read inside `_wait_for_result` feed `_Output`, which is unchanged. A background byte that lands between the second drain and the paste write is counted as the command's output. That matches the old behaviour and §4.1, and the window is a few syscalls wide. Test (d) (`test_a_chatty_background_job_is_not_stalled_and_its_tail_is_kept`, `test_background_output_is_held_back_while_idle`) checks the attacker case: `Run this?` and the 1 MiB `x` payload are absent from the next command's `output` and from the stand-in screen.
- **Control channel and forging completion.** The thread never reads fd 3 and never touches the tracker. A record that arrives while idle is still checked by `_drain_control` at the next `run()` (`src/nl_shell/session.py:933`). Printed text still cannot forge `D`/`E`.
- **Resource use.** The buffer is capped: 64 KiB kept, plus at most one 64 KiB chunk briefly before the trim (`_Background.add`, `src/nl_shell/session.py:541-547`). A 1 MiB flood is tested and ends with exactly 65536 bytes kept and 983040 counted as dropped. Memory does not grow with the attacker's input.
- **Thread lifetime and fd reuse.** `close()` stops and joins the thread before the PTY fd is closed (`src/nl_shell/session.py:652`), so the thread cannot read from a reused fd number. `restart()` goes through `close()`. On a timeout the session degrades (`:1066-1068`), so the `finally` in `run()` restarts the reader (`:961-963`). Test (e) checks that `close()` returns with output still waiting and leaves no thread behind.
- **Taint.** The docstring marks the block as untrusted (ADR-0016), as the brief asks. No taint type is added (deferred to #11), and the block goes nowhere near the state block or the model.
- **Threat-model and spec text.** The patch updates `.oss-scanner/threat_model.md` ("Built so far (#120)…" under "What must hold", plus a new "Some background output is dropped, not shown" known gap). Both match the code: the 50 ms settle cap is `_PROMPT_SETTLE_MAX`, and the fd-0-redirected case falls to the dropped path. The T2 gate log confirms the threat model was updated.

Low notes, not tagged (no action needed in this slice):

- `src/nl_shell/session.py:865-876`: if bash is never seen waiting on the terminal between commands (after a confirmed `exec 0</dev/null`, or a degraded session), the thread polls `/proc/<pid>/syscall` every 5 ms until the next `run()`, and all PTY bytes in that time are dropped. That costs some CPU but is not exploitable. The threat model already lists the dropped bytes as a known gap. Getting there needs a confirmed session-altering command, which is out of scope.
- `src/nl_shell/session.py:554-569`: the block is raw PTY bytes. It has a header line but no closing delimiter, and the tail cut can start in the middle of an escape sequence. Neither matters until something displays the block. When #78 wires the display, the block must pass through the same output filter as the §6 mirror (#163). The docstring and the new threat-model text both say so. The existing "#78 MUST NOT wire the session…" sentence (`.oss-scanner/threat_model.md:281`) names only "the §6 mirror". Naming the background block there too would make the dependency explicit. That is a wording suggestion, not a defect in this diff.

No NEEDS-HUMAN items.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T5 Judgment — Decide whether the additional post-read(0) discard interval of up to 50 ms is acceptable scope, since it can lose genuine background bytes beyond the brief's boundary; also confirm affected-path merged and closed/rejected prior art, since this snapshot has only one base commit and no remotes, while the brief records a narrower history search (docs/design/specs/pty-protocol/v1.md:495; brief.md:113).
- [ ] Validation — fitness-to-purpose — Accept the session-only delivery and documented loss window for the intended workflow; real-PTY smoke and frozen tests establish buffering, but confirm notices and filtered prompt display remain future work (docs/design/specs/pty-protocol/v1.md:544; src/nl_shell/session.py:806).
- [ ] **A non-degrading exception in `run()` leaves no reader thread, and `_bg_armed` stays stale.** `target/src/nl_shell/session.py:960-963` restarts the reader only `if finished or self._tracker.degraded`. `_bg_armed` is reset only in `_start_background` (`:833`). `_stop_background` (`:844-855`) never clears it. Concrete failing case: the session sits idle for more than 50 ms, so the thread arms and `_bg_armed = True`. Then `run("sleep 1", terminal=...)` raises from a user `on_record` callback at `S`, exactly as the existing `test_terminal_settings_restored_after_an_exception_mid_command` does (`tests/test_session_terminal.py:682-700`). A `KeyboardInterrupt` during `_wait_for_result` does the same. The session is not degraded, so (1) no thread reads the PTY afterwards. A background job then stalls again, which is the defect this slice removes. (2) At the next `run()`, the first `_drain_pty` (`:1388-1396`) sees the stale `_bg_armed = True`. It files the interrupted command's leftover output, its end marker and the next prompt under `[background output]`. That breaks the invariant: prompt bytes "are dropped as today", and the buffer holds only bytes read after bash was seen blocked in `read(0)` since the last `E`. Fix: reset `_bg_armed = False` in `_stop_background` or at the top of `run()`'s `try`, and restart the reader in the `finally` on every exit where `self._proc` is still open. Add a test: raise from `on_record`, then check that a background job is not stalled and that `background_waiting` stays false.
- [ ] **The brief contradicts itself on which bytes count as background output, and the spec forbids the obvious fix.** The Invariant says "Between a command's `D` record and the next `S` record, every byte read from the PTY master is background output". That matches spec §6.6 (`docs/design/specs/pty-protocol/v1.md:489-491`, "Between a done record and the next start record"). But criterion (d) says "bash's own prompt (`$ `, printed after `E`) is not counted as background output", and Design › What counts starts only "after bash's own prompt redraw". The prompt and the end marker are both written between D and S. Under the Invariant they are background output; under (d) they are not. The brief does not say how the session finds where the prompt ends, and spec §4.2 says "nl-shell does not parse the PTY stream for prompts" (`v1.md:402-403`). The brief also says nothing about a user's `PROMPT_COMMAND` output, which `tests/test_session.py:1004-1013` pins as "not the command's". Under the new rule it lands at every prompt, between D and S, so it would show up as background output after every command. That breaks (b)'s "waiting becomes false" right after an idle period. The planner should name the boundary: for example, bytes read after `_wait_for_prompt()` sees bash blocked in `read(0)` count, and prompt-hook output does or does not count. Without that, (d) is a design decision handed to Do rather than a criterion.
- [ ] **Criterion (c)'s exact byte counts depend on the payload the brief doesn't fix.** "the block then holds exactly the last 65536 bytes of what it wrote and reports 983040 dropped bytes" only holds if the PTY passes the job's bytes through unchanged. The PTY has ONLCR on: existing tests expect `b"hello\r\n"` for `echo hello` (`tests/test_session.py:1009`), so every LF the job writes reaches the master as two bytes. A payload that contains newlines turns the 1 MiB that was written into more than 1 MiB that was read, and both numbers come out wrong. The criterion should pin a payload with no LF (e.g. `head -c 1048576 /dev/zero | tr '\0' x`). It should also say whether the counts refer to bytes the job wrote or bytes read from the master.
- [ ] **Criteria (a) and (c) assume reading happens on its own, but the Design leaves that open.** (c) needs the job to finish "while the session is still idle (it is not stalled on a full PTY)". Design › Reading while idle lets Do pick "a method the REPL's event loop polls, a reader thread, a select hook". If Do picks polling, nothing reads unless the test calls the method, so the test either drives it (and passes no matter what) or the job stalls (red for good). The brief should say whether the session reads by itself while idle or the test polls, and how often. Otherwise the no-stall property can't be falsified. A reader thread has its own unaddressed cost: it has to hand the fd back cleanly to `run()`'s `_drain_pty` / `_wait_for_result` reads (`src/nl_shell/session.py:756`, `:831-841`) and to `close()`. The brief names that race but says nothing about how a test would show it is absent.
- [ ] **The "Peers to mirror" note puts the out-of-scope display back into scope.** The brief says "The background block is written through it [`_Ownership.mirror` / `_write_mirror`, `src/nl_shell/session_terminal.py:357-395`], not through a new writer". But an `_Ownership` only exists inside `run()` (`terminal.own(self._proc.fd)`, `src/nl_shell/session.py:771-780`), and it writes straight to the real terminal. Between commands, prompt_toolkit owns the terminal (§6.5, `v1.md:485`), and showing the block is explicitly out of scope ("showing the block above the REPL prompt … — #78"). In this slice the block can only be handed to the caller as bytes, which is how (b) frames it. As written, Do may wire a terminal write while idle (forbidden by §6.6) or spend time trying to fit the mirror path in. Restate it as "the block is bytes returned to the caller; #78 sends it through the mirror/filter path."
- [ ] **"Mark the block as untrusted" is in scope, the taint labels are out of scope, and no criterion checks the mark.** The Scope line says "Mark the block as untrusted", but the out-of-scope list holds "the state block and taint labels (#11)". `src/nl_shell` has no taint or untrusted type to attach (grep finds only comments in `cli.py:110` and `failure_classes.py:6`). None of (a)-(d) checks the label. So this is either a hidden second change (inventing a taint type before #11) or an untestable promise. Drop it, or name the concrete form (a typed return value, a docstring?) and add a check for it.
- [ ] **The issue's "Done when" can't be met by this slice, and the docs update could overclaim.** The issue says "**Done when:** the three background-output vectors in the PTY spec's conformance table pass". Vectors 13 and 14 need a confirm and its notice (`v1.md:532-533`), which the brief defers to #74/#78. The brief still frames its tests as "the session-level form of … conformance vectors 13–15" and asks Do to update `v1.md:536-540` to "say which vectors the new tests cover". The brief should state that the PR must not close #120, or that #120 is being re-scoped. It should also say that the conformance paragraph must describe the session-level parts only and not list 13/14 as covered. Otherwise Check signs off on a closure the thread's own criterion rejects.
- [ ] **The screen half of criterion (a) passes vacuously.** "the text has not reached the stand-in terminal's screen" is true on `main` too: nothing reads the PTY between commands, and the stand-in (`tests/test_session_terminal.py:148-160`) is only attached through `run(terminal=…)` during a command. The red leg of (a) rests entirely on the "waiting" flag. That's acceptable, but the brief's Falsifiability should not present the screen check as evidence. If the intent is to catch the block leaking to the terminal, the test needs a command run after the idle period. It should then check that the stand-in's screen for that run does not contain `Run this?`.
- [ ] **Target and dependencies check out.** `Depends on: none` while the metadata block says "Depends on #102 (terminal ownership, merged as 5998858)". This is consistent, because #102 is merged rather than a pending bundle, and no `dependency-state.json` is present. The threat-model edit (`.oss-scanner/threat_model.md:150-152`) is extra scope, but it is justified because the T2a gate requires it. I attempted to fault the repo/branch target and the dependency declarations and could not.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: iterated-to-Do
- Iteration delta (if iterating): Auto-iterate (round 1): rebuilding for the implementation-level findings — **A non-degrading exception in `run()` leaves no reader thread, and `_bg_armed` stays stale.** `target/src/nl_shell/session.py:960-963` restarts the reader only `if finished or self._tracker.degraded`. `_bg_armed` is reset only in `_start_background` (`:833`). `_stop_background` (`:844-855`) never clears it. Concrete failing case: the session sits idle for more than 50 ms, so the thread arms and `_bg_armed = True`. Then `run("sleep 1", terminal=...)` raises from a user `on_record` callback at `S`, exactly as the existing `test_terminal_settings_restored_after_an_exception_mid_command` does (`tests/test_session_terminal.py:682-700`). A `KeyboardInterrupt` during `_wait_for_result` does the same. The session is not degraded, so (1) no thread reads the PTY afterwards. A background job then stalls again, which is the defect this slice removes. (2) At the next `run()`, the first `_drain_pty` (`:1388-1396`) sees the stale `_bg_armed = True`. It files the interrupted command's leftover output, its end marker and the next prompt under `[background output]`. That breaks the invariant: prompt bytes "are dropped as today", and the buffer holds only bytes read after bash was seen blocked in `read(0)` since the last `E`. Fix: reset `_bg_armed = False` in `_stop_background` or at the top of `run()`'s `try`, and restart the reader in the `finally` on every exit where `self._proc` is still open. Add a test: raise from `on_record`, then check that a background job is not stalled and that `background_waiting` stays false.. Deferred, not addressed here: 9 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- By / date: auto-iterate / 2026-10-23

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 8 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

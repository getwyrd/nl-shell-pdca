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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (6 of 26 failed), green with it
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

Review #120: keep idle PTY background output in a bounded session buffer without leaking it to the terminal or later command results, including after interrupted runs.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | NEEDS-HUMAN | Accept the widened discard boundary — the added timeout-free wait and up-to-50-ms settling interval lose more background bytes than the brief's first-read boundary; target/docs/design/specs/pty-protocol/v1.md:494 and brief.md:136. |
| C2 Reproduction (red pre-fix) | PASS | Frozen real-PTY evidence shows six failures with production reverted, including two actual background-job completion timeouts rather than collection errors; gate-logs/C4-verify.log:14. |
| C3 Change | PASS | The change stays within session buffering, tests and its security/specification contract; terminal display remains a later integration, target/src/nl_shell/session.py:811 and target/.oss-scanner/threat_model.md:153. |
| C4 Verification (red→green) | PASS | Captured gate output establishes 26 green tests versus six red production-revert failures; local repetition is unavailable because python3 lacks pytest, so this verdict relies on gate-logs/C4-verify.log:10. |
| C5 Causal adequacy | PASS | Continuous idle consumption removes the unread-PTY cause; unconditional restart and pre-paste disarming address the carried-forward exception defect, with explicit regression coverage; target/src/nl_shell/session.py:948, target/src/nl_shell/session.py:962 and target/tests/test_session_terminal.py:806. |
| T1 Structure | PASS | Exclusive reader handover and locked bounded storage give clear ownership without a second simultaneous PTY consumer; target/src/nl_shell/session.py:530 and target/src/nl_shell/session.py:846. |
| T2 Shape | PASS | The threat model records both buffering protection and residual output loss, matching the affected security surface; target/.oss-scanner/threat_model.md:153 and target/.oss-scanner/threat_model.md:273; captured scanner agrees at gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | Frozen full-suite evidence is 1107 passed, one skipped with forkpty warnings; independent local syntax, buffer overflow/count/take assertions and documentation links passed, but local pytest execution was unavailable; gate-logs/T3-suite.log:37. |
| T4 Contribution | N/A | Contribution artifacts are absent by design; their substantive audit must run at publish, as recorded in gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm prior art for all affected paths in merged history and closed/rejected work — the brief records only a session-terminal history query, while the supplied repository has one synthetic base commit and no remotes, preventing independent completion; brief.md:113 and target/src/nl_shell/session.py:830. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept session-only delivery and the documented output-loss window — confirm notices and filtered prompt display remain #74/#78, so end-user conformance is incomplete; target/docs/design/specs/pty-protocol/v1.md:548 and target/.oss-scanner/threat_model.md:156. |

Evidence limits: the supplied target is readable and contains the patch. No target-state defect was found. Python 3.14.4 is available, but `python3 -m pytest tests/test_session_terminal.py -q --basetemp=/tmp/pdca-review-lh1ncz7o/pytest-green` exits with `No module named pytest`; `python` is absent. Consequently no stash/revert test was performed, and C2/C4/T3 are adjudicated from the complete frozen logs, not claimed as independently reproduced. The logs exercise real bash/PTys rather than a replacement tool or curated buffer fixture; no undischarged external dependency is established by the supplied evidence.

Independent checks: extracted and executed the actual `_Background` class using Python's AST and threading module; a 1-MiB payload retained exactly 65536 bytes, reported 983040 dropped bytes, and cleared on take. Both changed Python files parsed. `python3 scripts/docs_links.py` reported 64 links across 57 Markdown files with zero broken. `scripts/docs_checks.py` without arguments only printed its required `immutability BASE HEAD` usage and supplied no substantive verdict. Gate wrappers are instance-scoped and unavailable here; their complete captured outputs were read. No INTEGRATION.md was supplied, so no project-specific human-only list could be inspected.

The capability-probe smell test did not fire: the added syscall observation determines the output attribution boundary; it does not mask an eager optional-capability side effect. The boundary expansion is nevertheless a human scope decision under C1. No builder-fixable defect was established in this review.

For later integration acceptance, run `python3 -m pytest tests/test_session_terminal.py -q` in an environment with the declared development dependencies; the current tests exercise screen exclusion, idle writer completion, overflow accounting, exception recovery and reader shutdown. They do not establish the deferred confirm notice or filtered prompt rendering.

<!-- pdca:leaf-complete -->

### Advisory — adversary

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

### Advisory — security-review

# Security review — issue 120 / buffer-background-pty-output

**Attacker-reachable input touched:** command output (threat model "Where untrusted input enters" item 1), specifically PTY bytes a background job writes between commands. It is now read by a new reader thread, kept in a 64 KiB buffer and handed to the caller through `take_background_output()`. No other untrusted input is touched: there is no gate, confirm, sudo, model-context or logging change.

Rated against `.oss-scanner/threat_model.md`. `AGENTS.md` has no reviewer protocol that changes this review.

## Findings

No finding at any severity on the threat model's scale. Here is what I checked:

- **Background bytes cannot reach the real terminal in this slice.** The reader thread only calls `os.read` and `_Background.add` (`src/nl_shell/session.py:858-894`). It never writes to the PTY or to the terminal. `run()` stops and joins the thread before its first read (`session.py:929`). The thread starts again only in the outer `finally` (`session.py:968`), after the inner `finally` has already called `owner.end()`. So the §6 mirror (`session_terminal.py:357-395`) never runs while the thread reads, and idle bytes never go through it. The "High: background output shown during a confirm" row cannot be reached, because nothing shows the block yet.
- **Untrusted bytes are not relabelled, and nothing new goes into a `CommandResult`.** Once armed, idle bytes go only to `_Background` (`session.py:1417-1418`, `:891-892`). `_bg_armed` is cleared before the paste (`session.py:948`), so the command's own output still goes to the result as it did before. Bytes that land between the last `_drain_pty` and the paste become the command's output. That is the existing §4.1 rule, and that output is untrusted anyway. No path takes the buffer into the state block, the reader, `on_record` or a log.
- **Moving the arming point does not give an attacker anything.** A background writer can only change *when* its bytes are counted. The worst it can do is get its bytes dropped (prompt window, or fd 0 redirected). This patch adds that case to "Known gaps" (`threat_model.md:273-278`). It cannot push bytes into a command's result or onto the screen.
- **Resource use is in proportion to the input.** The buffer has a fixed size (`BACKGROUND_LIMIT`, `session.py:314`). A job that floods the PTY costs one 64 KiB read plus at most a 64 KiB `bytearray` trim per chunk. The dropped count is a plain int.
- **Hangs.** `_stop_background` calls `join()` with no timeout (`session.py:853-854`). The thread is woken by a pipe it also selects on. Its only blocking calls are `select`, an `os.read` made only after `select` reported the fd readable (no other reader is active then), and short `/proc` reads. I found no input that keeps it from waking. Test (e) runs `close()` with output still waiting, and it returns.
- **Sudo password.** `session.py` has no sudo passthrough yet. Keys are forwarded only while `owner` is active, and the thread never runs then. So no typed key passes through the new buffer.
- **Tests cover the attacker case.** `test_background_output_is_held_back_while_idle` uses confirm-shaped text (`Run this? [y/N] `) and checks that it stays off the stand-in screen and out of the next result. The 1 MiB flood test checks the size cap and the dropped count. Both exception-path tests check that the reader comes back after a failed `run()`. C4 is red before the fix (6 of 26) and green after. T3 passes with 1107 tests (`gate-logs/C4-verify.log`, `gate-logs/T3-suite.log`).

## Notes (not findings, nothing to adjudicate)

- `take_background_output()` returns raw bytes, including any OSC 52 or terminal-query escapes. The docstring says to show them only through the mirror filter (`session.py:814-816`). This is safe until #78 wires display. #78 must apply the #163 filter to this block, and the threat model's "#78 MUST NOT wire…" paragraph already requires that. A job run in the background that reads a sensitive file (`cat ~/.ssh/id_ed25519 &`) also ends up in this buffer without a secret label. That is fine today because the buffer only reaches the caller. #78/#11 need to keep it screen-only and out of logs and history.
- If the reader thread hits an exception it does not expect, it ends silently and a chatty job stalls again. That is a reliability problem, not one of the threat model's properties, so I did not rate it.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C1 Spec — Accept the widened discard boundary — the added timeout-free wait and up-to-50-ms settling interval lose more background bytes than the brief's first-read boundary; target/docs/design/specs/pty-protocol/v1.md:494 and brief.md:136.
- [ ] T5 Judgment — Confirm prior art for all affected paths in merged history and closed/rejected work — the brief records only a session-terminal history query, while the supplied repository has one synthetic base commit and no remotes, preventing independent completion; brief.md:113 and target/src/nl_shell/session.py:830.
- [ ] Validation — fitness-to-purpose — Accept session-only delivery and the documented output-loss window — confirm notices and filtered prompt display remain #74/#78, so end-user conformance is incomplete; target/docs/design/specs/pty-protocol/v1.md:548 and target/.oss-scanner/threat_model.md:156.
- [ ] **A Session that is never closed now leaks its bash process.** `src/nl_shell/session.py:838-844` starts the thread with `target=self._background_loop`, a bound method. The daemon thread holds a strong reference to the Session, so the Session, its `PtyProcess` and bash are never garbage-collected. Before this patch, `PtyProcess.__del__` (`ptyprocess/ptyprocess.py:370-385`) closed them. Test: `s = Session.start(); pid = s.pid; del s; gc.collect(); os.kill(pid, 0)`. With the patch, bash is **still alive**, and the thread `nl-shell-background-output` stays alive until the process exits. On the pre-fix base, bash is gone. A REPL or test that drops a session without `close()` (for example, after an exception that skips the close) now keeps a shell and its jobs running. Fix: have the thread hold only what it needs (the fd, the `_Background`, the pid and proc paths for the syscall check) or a `weakref` to the Session. Add a test that drops an unclosed Session and checks that bash exits.
- [ ] **New warning: `forkpty()` now runs while another thread is alive.** `gate-logs/T3-suite.log:28-34` shows `DeprecationWarning: This process ... is multi-threaded, use of forkpty() may lead to deadlocks in the child`. It fires in `test_aliases_cannot_reach_inside_the_hooks`, which starts a second Session while the first one's reader thread runs. `_spawn` (`src/nl_shell/session.py:681-694`) runs a Python `preexec_fn` (`wire_fd3`) in the forked child. Python's docs say this is unsafe when other threads exist. Today the REPL holds one session, and `restart()` stops the thread first (`close()` at `:652`), so it is rare. But any second session, or any later `subprocess(preexec_fn=...)` in the same process, now forks with a live thread. A human should decide whether to accept this, or whether to drop the Python `preexec_fn` (or pause readers during spawn) as part of keeping a thread.
- [ ] **The brief contradicts itself on which bytes count as background output, and the spec forbids the obvious fix.** The Invariant says "Between a command's `D` record and the next `S` record, every byte read from the PTY master is background output". That matches spec §6.6 (`docs/design/specs/pty-protocol/v1.md:489-491`, "Between a done record and the next start record"). But criterion (d) says "bash's own prompt (`$ `, printed after `E`) is not counted as background output", and Design › What counts starts only "after bash's own prompt redraw". The prompt and the end marker are both written between D and S. Under the Invariant they are background output; under (d) they are not. The brief does not say how the session finds where the prompt ends, and spec §4.2 says "nl-shell does not parse the PTY stream for prompts" (`v1.md:402-403`). The brief also says nothing about a user's `PROMPT_COMMAND` output, which `tests/test_session.py:1004-1013` pins as "not the command's". Under the new rule it lands at every prompt, between D and S, so it would show up as background output after every command. That breaks (b)'s "waiting becomes false" right after an idle period. The planner should name the boundary: for example, bytes read after `_wait_for_prompt()` sees bash blocked in `read(0)` count, and prompt-hook output does or does not count. Without that, (d) is a design decision handed to Do rather than a criterion.
- [ ] **Criterion (c)'s exact byte counts depend on the payload the brief doesn't fix.** "the block then holds exactly the last 65536 bytes of what it wrote and reports 983040 dropped bytes" only holds if the PTY passes the job's bytes through unchanged. The PTY has ONLCR on: existing tests expect `b"hello\r\n"` for `echo hello` (`tests/test_session.py:1009`), so every LF the job writes reaches the master as two bytes. A payload that contains newlines turns the 1 MiB that was written into more than 1 MiB that was read, and both numbers come out wrong. The criterion should pin a payload with no LF (e.g. `head -c 1048576 /dev/zero | tr '\0' x`). It should also say whether the counts refer to bytes the job wrote or bytes read from the master.
- [ ] **Criteria (a) and (c) assume reading happens on its own, but the Design leaves that open.** (c) needs the job to finish "while the session is still idle (it is not stalled on a full PTY)". Design › Reading while idle lets Do pick "a method the REPL's event loop polls, a reader thread, a select hook". If Do picks polling, nothing reads unless the test calls the method, so the test either drives it (and passes no matter what) or the job stalls (red for good). The brief should say whether the session reads by itself while idle or the test polls, and how often. Otherwise the no-stall property can't be falsified. A reader thread has its own unaddressed cost: it has to hand the fd back cleanly to `run()`'s `_drain_pty` / `_wait_for_result` reads (`src/nl_shell/session.py:756`, `:831-841`) and to `close()`. The brief names that race but says nothing about how a test would show it is absent.
- [ ] **The "Peers to mirror" note puts the out-of-scope display back into scope.** The brief says "The background block is written through it [`_Ownership.mirror` / `_write_mirror`, `src/nl_shell/session_terminal.py:357-395`], not through a new writer". But an `_Ownership` only exists inside `run()` (`terminal.own(self._proc.fd)`, `src/nl_shell/session.py:771-780`), and it writes straight to the real terminal. Between commands, prompt_toolkit owns the terminal (§6.5, `v1.md:485`), and showing the block is explicitly out of scope ("showing the block above the REPL prompt … — #78"). In this slice the block can only be handed to the caller as bytes, which is how (b) frames it. As written, Do may wire a terminal write while idle (forbidden by §6.6) or spend time trying to fit the mirror path in. Restate it as "the block is bytes returned to the caller; #78 sends it through the mirror/filter path."
- [ ] **"Mark the block as untrusted" is in scope, the taint labels are out of scope, and no criterion checks the mark.** The Scope line says "Mark the block as untrusted", but the out-of-scope list holds "the state block and taint labels (#11)". `src/nl_shell` has no taint or untrusted type to attach (grep finds only comments in `cli.py:110` and `failure_classes.py:6`). None of (a)-(d) checks the label. So this is either a hidden second change (inventing a taint type before #11) or an untestable promise. Drop it, or name the concrete form (a typed return value, a docstring?) and add a check for it.
- [ ] **The issue's "Done when" can't be met by this slice, and the docs update could overclaim.** The issue says "**Done when:** the three background-output vectors in the PTY spec's conformance table pass". Vectors 13 and 14 need a confirm and its notice (`v1.md:532-533`), which the brief defers to #74/#78. The brief still frames its tests as "the session-level form of … conformance vectors 13–15" and asks Do to update `v1.md:536-540` to "say which vectors the new tests cover". The brief should state that the PR must not close #120, or that #120 is being re-scoped. It should also say that the conformance paragraph must describe the session-level parts only and not list 13/14 as covered. Otherwise Check signs off on a closure the thread's own criterion rejects.
- [ ] **The screen half of criterion (a) passes vacuously.** "the text has not reached the stand-in terminal's screen" is true on `main` too: nothing reads the PTY between commands, and the stand-in (`tests/test_session_terminal.py:148-160`) is only attached through `run(terminal=…)` during a command. The red leg of (a) rests entirely on the "waiting" flag. That's acceptable, but the brief's Falsifiability should not present the screen check as evidence. If the intent is to catch the block leaking to the terminal, the test needs a command run after the idle period. It should then check that the stand-in's screen for that run does not contain `Run this?`.
- [ ] **Target and dependencies check out.** `Depends on: none` while the metadata block says "Depends on #102 (terminal ownership, merged as 5998858)". This is consistent, because #102 is merged rather than a pending bundle, and no `dependency-state.json` is present. The threat-model edit (`.oss-scanner/threat_model.md:150-152`) is extra scope, but it is justified because the T2a gate requires it. I attempted to fault the repo/branch target and the dependency declarations and could not.
- [ ] T5 Judgment — Decide whether the additional post-read(0) discard interval of up to 50 ms is acceptable scope, since it can lose genuine background bytes beyond the brief's boundary; also confirm affected-path merged and closed/rejected prior art, since this snapshot has only one base commit and no remotes, while the brief records a narrower history search (docs/design/specs/pty-protocol/v1.md:495; brief.md:113).

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
- Iteration delta (if iterating): Auto-iterate (round 2): rebuilding for the implementation-level findings — **A Session that is never closed now leaks its bash process.** `src/nl_shell/session.py:838-844` starts the thread with `target=self._background_loop`, a bound method. The daemon thread holds a strong reference to the Session, so the Session, its `PtyProcess` and bash are never garbage-collected. Before this patch, `PtyProcess.__del__` (`ptyprocess/ptyprocess.py:370-385`) closed them. Test: `s = Session.start(); pid = s.pid; del s; gc.collect(); os.kill(pid, 0)`. With the patch, bash is **still alive**, and the thread `nl-shell-background-output` stays alive until the process exits. On the pre-fix base, bash is gone. A REPL or test that drops a session without `close()` (for example, after an exception that skips the close) now keeps a shell and its jobs running. Fix: have the thread hold only what it needs (the fd, the `_Background`, the pid and proc paths for the syscall check) or a `weakref` to the Session. Add a test that drops an unclosed Session and checks that bash exits.. Deferred, not addressed here: 11 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- By / date: auto-iterate / 2026-10-23

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 8 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

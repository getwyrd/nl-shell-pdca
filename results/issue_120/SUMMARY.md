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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (7 of 27 failed), green with it
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

Review #120: consume idle PTY output into a bounded, labelled session buffer without leaking it to the terminal or later command results.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The session-only contract has observable bounds, handover, isolation and lifecycle criteria; prompt display and confirm notices remain separate work (target/docs/design/specs/pty-protocol/v1.md:486, target/docs/design/specs/pty-protocol/v1.md:548). |
| C2 Reproduction (red pre-fix) | PASS | Independently stashed the patch: the real-PTY 1 MiB writer failed to finish during a three-second idle interval and the background API was absent; frozen pytest evidence additionally shows 7 failures without collection errors (gate-logs/C4-verify.log:223; target/tests/test_session_terminal.py:743). |
| C3 Change | NEEDS-HUMAN | Accept the expanded discard boundary or require Plan re-entry — unlike the brief's first observed read(0) boundary, the patch requires an untimed wait and adds up to 50 ms settling, during which genuine background bytes can be lost; redirected stdin is also expressly excluded (target/docs/design/specs/pty-protocol/v1.md:494). |
| C4 Verification (red→green) | PASS | Independent stash/pop probe changed the stalled writer into successful idle completion with the exact 65536-byte tail and 983040 dropped count; frozen pytest log reports 27 green tests and 7 pre-fix failures, not an import-error red (gate-logs/C4-verify.log:12, gate-logs/C4-verify.log:223; target/tests/test_session_terminal.py:760). |
| C5 Causal adequacy | PASS | Continuous idle consumption removes the unread-PTY cause of writer backpressure; reader handoff avoids competing readers and the finally path restores consumption after exceptions; no optional-capability symptom guard was introduced (target/src/nl_shell/session.py:891, target/src/nl_shell/session.py:924, target/src/nl_shell/session.py:1502). |
| T1 Structure | PASS | A locked bounded buffer and one stoppable reader preserve ownership separation; weak references avoid retaining an abandoned session, independently confirmed by collection and bash exit (target/src/nl_shell/session.py:531, target/src/nl_shell/session.py:843, target/src/nl_shell/session.py:1534). |
| T2 Shape | PASS | Threat-model changes disclose both delivered isolation and deferred UI/filter integration, including the output-loss limit; independently confirmed affected security paths and threat-model edits, matching the scanner log (target/.oss-scanner/threat_model.md:150, target/.oss-scanner/threat_model.md:273; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Independent real-PTY probe passed exact buffering, clear-on-take, 20 clean commands after consuming the expected job notice, and abandoned-session cleanup; frozen full-suite evidence records 1108 passed, 1 skipped, with forkpty warnings (target/tests/test_session_terminal.py:784, target/tests/test_session_terminal.py:866; gate-logs/T3-suite.log:28). |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive contribution audit reruns at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm merged and closed/rejected prior art by affected path before accepting novelty — the supplied git snapshot has one synthetic base commit and no remotes, so the brief's triage claim cannot be independently established here (brief.md:113; target/src/nl_shell/session.py:831; target/src/nl_shell/session_terminal.py:357). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether this session-only delivery and its documented output-loss window satisfy the intended milestone — the confirm notice, prompt display and rendering-filter integration remain future work, so this evidence does not establish end-to-end confirm safety (target/.oss-scanner/threat_model.md:156; target/docs/design/specs/pty-protocol/v1.md:548). |

Independent verification details: `python3 -m pytest tests/test_session_terminal.py -q -p no:cacheprovider --basetemp=/tmp/pdca-review-3xyxeskw/pytest-tmp` could not start because pytest is absent. The instance-scoped gate wrappers are unavailable here; all four supplied gate logs were read. These are reviewer-host limitations, not patch failures or unmet dependencies in the captured gate environment. The real Session/Bash/PTY probe did run successfully on this host without a shim. No source was edited; the tracked patch was stashed and restored for the red leg. Syntax parsing and `git diff --check` also passed. An isolated buffer exercise independently passed exact tail accounting and clearing, and is not treated as PTY integration evidence.

To reproduce the independent integration exercise, run `python3 reviewer-probe.py green` from this report's directory. It uses a fresh HOME inside this sandbox, starts a real Session, launches the delayed 1 MiB job, checks completion and the exact labelled block, consumes the expected bash job-completion notice with `wait`, checks 20 subsequent commands, closes the session, and separately checks collection of an unclosed session. The first probe version omitted `wait` and hit the existing permitted job-notice behavior; the corrected probe passed. The frozen tests explicitly preserve that behavior. The pre-fix leg was run with the tracked patch stashed and restored in a finally block.

The target is readable and contains the applied patch; no target-state caveat was needed. No INTEGRATION.md was supplied or found in the target; project-specific human-only requirements beyond the available artifacts cannot be inferred.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 120 / buffer-background-pty-output (round 3)

I tried to refute the evidence, the fix, and the gate verdicts. I could not refute the core fix. Nothing below should block; one small `[impl]` item and some notes.

## The evidence (C4 red→green)

- **Red is real where it counts, and only there.** `gate-logs/C4-verify.log:66` and `:181` are the two true behaviour reds. In both, the 1 MiB job stalls because nothing reads the PTY while the session is idle. The tests poll only `os.path.exists`, so no session method is called (`tests/test_session_terminal.py:532`, `:631`). The other 5 reds are `AttributeError: … 'background_waiting'` (`C4-verify.log:34,83,108,140,212`). They show the API is missing, not that the behaviour is wrong. The brief says the screen check and (e) are guards, so this matches it. The "7 of 27 red" headline overstates the independent red evidence: it is really 2 behaviour reds plus 5 missing-API reds.
- **The prompt-hook guard does catch a wrong boundary.** If the reader armed at once, without the `_waiting_for_key` wait at `src/nl_shell/session.py:1139-1154`, the `HOOK-OUTPUT` and prompt bytes would be buffered. `test_the_prompt_and_the_prompt_hook_are_not_background_output` (`tests/test_session_terminal.py:546-556`) would then go red. So it is not a tautology. Its red on `main` is just the AttributeError.
- **I checked the "timed wait before the prompt" claim instead of trusting it.** The `wait == 0` check (`src/nl_shell/session.py:1154`) and the §6.6 text say bash 5.3 first waits on fd 0 with a timeout of about 50 ms. On this host's bash 5.3.9, the real `Session` rcfile shows `pselect6(1, …, timeout=0x7fff…)` for about 50 ms, then `pselect6(1, …, NULL)`. The claim holds, and arming on the NULL-timeout wait is the right signal. (With plain `bash --norc` there is no timed wait, so the timed wait comes from the session's own setup.)
- **T3 passes** (`gate-logs/T3-suite.log`: 1108 passed, 1 skipped), including `test_job_notice_is_part_of_the_next_commands_output`.

## Attacks on the fix that did not land

- **A dropped Session leaking bash (the iteration-2 finding).** The fix holds. The thread gets `weakref.ref(self)` (`src/nl_shell/session.py:845`) and takes a strong reference only inside `_bash_waiting_for_key` (`:1521-1531`), which is never called once armed. Cleanup runs through `weakref.finalize`. CPython clears weakrefs before it clears the instance dict, so `_stop_reader` stops and joins the reader before `PtyProcess.__del__` closes the fd. If the last reference drops on the reader thread itself, `_stop_reader` skips the join and the loop returns at `stop.is_set()` before it touches either fd again.
- **A stale `armed` flag or no reader after a non-degrading exception (the iteration-1 finding).** The fix holds. `armed=False` is set before the paste (`:910`), the reader restarts in `finally` (`:930`), and `_start_background` resets `armed` again.
- **Read races between the thread and `run()`.** I found none. `_stop_background` joins before any `run()` read, and `close()` stops the reader before `proc.close` (`:653`).
- **An uncaught exception in the reader thread** (the thread would die quietly and the stall would come back). Every exception path in `_waiting_for_key`, `_syscall` and `_stdin_is_terminal` either turns into `_ProcUnreadable`, which is caught at `:1530`, or is caught locally. I found no way in.
- **TMOUT and readline timeouts making the reader never arm** (if so, all background output would be dropped silently). It does not happen. With `TMOUT=100`, bash 5.3.9 still waits in `pselect6(1, …, NULL)`, because TMOUT uses `alarm()`.

## Findings

- NEEDS-HUMAN [impl] — `src/nl_shell/session.py:891`: `self._stop_background()` is called *before* the `try` whose `finally` restarts the reader (`:930`). `_stop_background` sets `self._bg_stop = None` first and then calls the finalizer, which calls `thread.join()`. A `KeyboardInterrupt` that lands during that join leaves `run()` without passing through `finally`. The result: no reader thread, and `_bg_stop` is None, so nothing restarts the reader until the next `run()`. A chatty background job stalls again, which is the defect this slice fixes. The wake pipe's two fds also leak, because `_stop_reader` never reaches its `os.close` calls. The window is small: the join usually returns at once because the wake byte is already written. The fix is cheap, though: move the call to be the first statement inside the `try`. Same class of bug as the iteration-1 finding, on a narrower path.
- `src/nl_shell/session.py:1502` (note, not tagged): until it has seen bash waiting for a key, the reader polls `/proc/<pid>/syscall` every 5 ms. After a non-degrading exception on a long command (say `run("sleep 600")` stopped by `on_record`), or in a session degraded because bash is stopped, it keeps polling at about 200 Hz until the command ends or `restart()`. That costs CPU but is still correct.
- `src/nl_shell/session.py:1472-1518` (note, behaviour to know about): with `set -b` (immediate job notification), bash prints `[1]+  Done …` while idle. I confirmed this on bash 5.3.9. The notice then goes into the `[background output]` block, not the next command's output. That seems right under §6.6 (bash wrote it while no command ran), and the existing job-notice test covers only the default `set +b`. Worth one line in the known-limits text so #78 is not surprised.
- `docs/design/specs/pty-protocol/v1.md` §6.6 (note): the spec now sets "50 ms" as the settle time in normative text. That repeats the private constant `_PROMPT_SETTLE_MAX` (`src/nl_shell/session.py:324`). If the constant is tuned later, the spec drifts. This is wording only.

Bottom line: I attacked the evidence (5 of the 7 reds are missing-API only, but the 2 behaviour reds are real and come through the production path), the boundary heuristic (checked live on bash 5.3.9), GC/finalizer ordering, read races, reader-thread death and TMOUT. I could not refute the fix. The only buildable item is the interrupted-join edge at `:891`.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review — issue 120 / buffer-background-pty-output

Attacker-reachable inputs this diff touches: **command output** (threat model "Where untrusted input enters" item 1), here the PTY bytes a background job writes between commands. The bash process state that the new reader thread reads through `/proc` is touched too, but only read, never trusted as data.

**No finding at any severity.** What I checked:

- **Background bytes kept off the screen and out of a `CommandResult`.** The reader thread (`src/nl_shell/session.py:1472-1518`, `_background_loop`) only `os.read`s the PTY master. It never writes to the PTY or to the real terminal. `run()` stops it and joins it before any of its own reads (`session.py:891`). The second `_drain_pty` just before the paste (`session.py:906`) files bytes that arrived during the pre-paste checks as background output. Before this patch those bytes were dropped. `armed` is cleared before the paste (`session.py:910`), so nothing from the paste on lands in the buffer. Bytes between that last drain and the paste reaching bash still count as the command's output. That race existed before this patch, and this patch narrows it. The test `test_background_output_is_held_back_while_idle` uses confirm-shaped text (`Run this? [y/N] `) and checks that it is in neither the stand-in screen nor the next result. So the attacker case is tested, not just the friendly path.
- **Concurrent reads and fd reuse.** `close()`, `restart()` (through `close()`) and `run()` stop the thread before the fd is closed or read (`session.py:653`, `:891`). The `weakref.finalize` path wakes the thread through the pipe, and it never joins itself (`_stop_reader`, `session.py:1534`). The thread holds the session only weakly, and `_waiting_for_key` / `_reading_terminal` / `_stdin_is_terminal` (`session.py:1125-1175`) only read `/proc`. They never call `_tracker.degrade`, so the thread cannot change protocol state behind `run()`'s back. A `_ProcUnreadable` from the thread is caught (`_bash_waiting_for_key`).
- **Memory and CPU use.** The buffer is capped at 64 KiB and drops the oldest bytes (`_Background.add`, `session.py:544`). Before arming, bytes are dropped rather than stored. A flooding job cannot keep the reader from arming: the quiet window ends at `seen + _PROMPT_SETTLE_MAX` (50 ms) however busy the PTY is. The 1 MiB test (`test_a_chatty_background_job_is_not_stalled_and_its_tail_is_kept`) shows the job does not stall.
- **Session state an attacker could set to keep the reader unarmed** (item 4, e.g. `TMOUT` from a sourced script). If readline waited with a timeout, `_waiting_for_key` would never become true, and all background output would be dropped silently. I checked this on this host's bash 5.3.9 with an interactive bash on a PTY, with and without `TMOUT=3600`. In both cases `/proc/<pid>/syscall` shows `pselect6` with nfds 1 and timeout pointer 0x0, because bash enforces `TMOUT` with an alarm, not a select timeout. So `TMOUT` does not defeat arming. The remaining known limit (fd 0 redirected, the 50 ms window) is written down in the threat model's Known gaps (`.oss-scanner/threat_model.md:273-278`). It is a visibility loss, not a spoof.
- **Threat-model text.** The new "Built so far / Not built yet" wording (`.oss-scanner/threat_model.md:150-157`) matches the code: the block is handed over only on request, and nothing displays it yet.

Forward note for #78/#74, not a finding for this diff (nothing displays the block yet): the block returned by `take_background_output` (`session.py:808`, built by `_Background.take` at `session.py:557`) has a header but no end line, and its contents are raw attacker bytes. Once #78 shows it, a job can print `\r\n` followed by text shaped like nl-shell's own prompt or confirm, or a fake `[0 bytes dropped]` line, or escape sequences that erase the `[background output]` header. That is the High row "spoofs the confirm UI" (`threat_model.md:315-316`). The filter (#163) and the display design in #78 need to cover it, for example with an end marker and escaping before display. This patch's docstring already says to show the bytes only through the mirror filter.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] C3 Change — Accept the expanded discard boundary or require Plan re-entry — unlike the brief's first observed read(0) boundary, the patch requires an untimed wait and adds up to 50 ms settling, during which genuine background bytes can be lost; redirected stdin is also expressly excluded (target/docs/design/specs/pty-protocol/v1.md:494).
- [x] T5 Judgment — Confirm merged and closed/rejected prior art by affected path before accepting novelty — the supplied git snapshot has one synthetic base commit and no remotes, so the brief's triage claim cannot be independently established here (brief.md:113; target/src/nl_shell/session.py:831; target/src/nl_shell/session_terminal.py:357).
- [x] Validation — fitness-to-purpose — Decide whether this session-only delivery and its documented output-loss window satisfy the intended milestone — the confirm notice, prompt display and rendering-filter integration remain future work, so this evidence does not establish end-to-end confirm safety (target/.oss-scanner/threat_model.md:156; target/docs/design/specs/pty-protocol/v1.md:548).
- [x] `src/nl_shell/session.py:891`: `self._stop_background()` is called *before* the `try` whose `finally` restarts the reader (`:930`). `_stop_background` sets `self._bg_stop = None` first and then calls the finalizer, which calls `thread.join()`. A `KeyboardInterrupt` that lands during that join leaves `run()` without passing through `finally`. The result: no reader thread, and `_bg_stop` is None, so nothing restarts the reader until the next `run()`. A chatty background job stalls again, which is the defect this slice fixes. The wake pipe's two fds also leak, because `_stop_reader` never reaches its `os.close` calls. The window is small: the join usually returns at once because the wake byte is already written. The fix is cheap, though: move the call to be the first statement inside the `try`. Same class of bug as the iteration-1 finding, on a narrower path.
- [x] **The brief contradicts itself on which bytes count as background output, and the spec forbids the obvious fix.** The Invariant says "Between a command's `D` record and the next `S` record, every byte read from the PTY master is background output". That matches spec §6.6 (`docs/design/specs/pty-protocol/v1.md:489-491`, "Between a done record and the next start record"). But criterion (d) says "bash's own prompt (`$ `, printed after `E`) is not counted as background output", and Design › What counts starts only "after bash's own prompt redraw". The prompt and the end marker are both written between D and S. Under the Invariant they are background output; under (d) they are not. The brief does not say how the session finds where the prompt ends, and spec §4.2 says "nl-shell does not parse the PTY stream for prompts" (`v1.md:402-403`). The brief also says nothing about a user's `PROMPT_COMMAND` output, which `tests/test_session.py:1004-1013` pins as "not the command's". Under the new rule it lands at every prompt, between D and S, so it would show up as background output after every command. That breaks (b)'s "waiting becomes false" right after an idle period. The planner should name the boundary: for example, bytes read after `_wait_for_prompt()` sees bash blocked in `read(0)` count, and prompt-hook output does or does not count. Without that, (d) is a design decision handed to Do rather than a criterion.
- [x] **Criterion (c)'s exact byte counts depend on the payload the brief doesn't fix.** "the block then holds exactly the last 65536 bytes of what it wrote and reports 983040 dropped bytes" only holds if the PTY passes the job's bytes through unchanged. The PTY has ONLCR on: existing tests expect `b"hello\r\n"` for `echo hello` (`tests/test_session.py:1009`), so every LF the job writes reaches the master as two bytes. A payload that contains newlines turns the 1 MiB that was written into more than 1 MiB that was read, and both numbers come out wrong. The criterion should pin a payload with no LF (e.g. `head -c 1048576 /dev/zero | tr '\0' x`). It should also say whether the counts refer to bytes the job wrote or bytes read from the master.
- [x] **Criteria (a) and (c) assume reading happens on its own, but the Design leaves that open.** (c) needs the job to finish "while the session is still idle (it is not stalled on a full PTY)". Design › Reading while idle lets Do pick "a method the REPL's event loop polls, a reader thread, a select hook". If Do picks polling, nothing reads unless the test calls the method, so the test either drives it (and passes no matter what) or the job stalls (red for good). The brief should say whether the session reads by itself while idle or the test polls, and how often. Otherwise the no-stall property can't be falsified. A reader thread has its own unaddressed cost: it has to hand the fd back cleanly to `run()`'s `_drain_pty` / `_wait_for_result` reads (`src/nl_shell/session.py:756`, `:831-841`) and to `close()`. The brief names that race but says nothing about how a test would show it is absent.
- [x] **The "Peers to mirror" note puts the out-of-scope display back into scope.** The brief says "The background block is written through it [`_Ownership.mirror` / `_write_mirror`, `src/nl_shell/session_terminal.py:357-395`], not through a new writer". But an `_Ownership` only exists inside `run()` (`terminal.own(self._proc.fd)`, `src/nl_shell/session.py:771-780`), and it writes straight to the real terminal. Between commands, prompt_toolkit owns the terminal (§6.5, `v1.md:485`), and showing the block is explicitly out of scope ("showing the block above the REPL prompt … — #78"). In this slice the block can only be handed to the caller as bytes, which is how (b) frames it. As written, Do may wire a terminal write while idle (forbidden by §6.6) or spend time trying to fit the mirror path in. Restate it as "the block is bytes returned to the caller; #78 sends it through the mirror/filter path."
- [x] **"Mark the block as untrusted" is in scope, the taint labels are out of scope, and no criterion checks the mark.** The Scope line says "Mark the block as untrusted", but the out-of-scope list holds "the state block and taint labels (#11)". `src/nl_shell` has no taint or untrusted type to attach (grep finds only comments in `cli.py:110` and `failure_classes.py:6`). None of (a)-(d) checks the label. So this is either a hidden second change (inventing a taint type before #11) or an untestable promise. Drop it, or name the concrete form (a typed return value, a docstring?) and add a check for it.
- [x] **The issue's "Done when" can't be met by this slice, and the docs update could overclaim.** The issue says "**Done when:** the three background-output vectors in the PTY spec's conformance table pass". Vectors 13 and 14 need a confirm and its notice (`v1.md:532-533`), which the brief defers to #74/#78. The brief still frames its tests as "the session-level form of … conformance vectors 13–15" and asks Do to update `v1.md:536-540` to "say which vectors the new tests cover". The brief should state that the PR must not close #120, or that #120 is being re-scoped. It should also say that the conformance paragraph must describe the session-level parts only and not list 13/14 as covered. Otherwise Check signs off on a closure the thread's own criterion rejects.
- [x] **The screen half of criterion (a) passes vacuously.** "the text has not reached the stand-in terminal's screen" is true on `main` too: nothing reads the PTY between commands, and the stand-in (`tests/test_session_terminal.py:148-160`) is only attached through `run(terminal=…)` during a command. The red leg of (a) rests entirely on the "waiting" flag. That's acceptable, but the brief's Falsifiability should not present the screen check as evidence. If the intent is to catch the block leaking to the terminal, the test needs a command run after the idle period. It should then check that the stand-in's screen for that run does not contain `Run this?`.
- [x] **Target and dependencies check out.** `Depends on: none` while the metadata block says "Depends on #102 (terminal ownership, merged as 5998858)". This is consistent, because #102 is merged rather than a pending bundle, and no `dependency-state.json` is present. The threat-model edit (`.oss-scanner/threat_model.md:150-152`) is extra scope, but it is justified because the T2a gate requires it. I attempted to fault the repo/branch target and the dependency declarations and could not.
- [x] size backstop — this slice is behaving oversized: 2 round(s) already spent (threshold 2). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.
- [x] T5 Judgment — Decide whether the additional post-read(0) discard interval of up to 50 ms is acceptable scope, since it can lose genuine background bytes beyond the brief's boundary; also confirm affected-path merged and closed/rejected prior art, since this snapshot has only one base commit and no remotes, while the brief records a narrower history search (docs/design/specs/pty-protocol/v1.md:495; brief.md:113).
- [x] C1 Spec — Accept the widened discard boundary — the added timeout-free wait and up-to-50-ms settling interval lose more background bytes than the brief's first-read boundary; target/docs/design/specs/pty-protocol/v1.md:494 and brief.md:136.
- [x] T5 Judgment — Confirm prior art for all affected paths in merged history and closed/rejected work — the brief records only a session-terminal history query, while the supplied repository has one synthetic base commit and no remotes, preventing independent completion; brief.md:113 and target/src/nl_shell/session.py:830.
- [x] **New warning: `forkpty()` now runs while another thread is alive.** `gate-logs/T3-suite.log:28-34` shows `DeprecationWarning: This process ... is multi-threaded, use of forkpty() may lead to deadlocks in the child`. It fires in `test_aliases_cannot_reach_inside_the_hooks`, which starts a second Session while the first one's reader thread runs. `_spawn` (`src/nl_shell/session.py:681-694`) runs a Python `preexec_fn` (`wire_fd3`) in the forked child. Python's docs say this is unsafe when other threads exist. Today the REPL holds one session, and `restart()` stops the thread first (`close()` at `:652`), so it is rare. But any second session, or any later `subprocess(preexec_fn=...)` in the same process, now forks with a live thread. A human should decide whether to accept this, or whether to drop the Python `preexec_fn` (or pause readers during spawn) as part of keeping a thread.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: merged-wider
- Iteration delta (if iterating):
- By / date: Eduard Ralph / 2026-10-23

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 8 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)
- Follow-up: `session.py:891` `_stop_background()` runs before the `try` whose `finally` restarts the reader — a Ctrl-C during the join leaves no reader and leaks the wake-pipe fds; move it inside the `try`.
- Follow-up (before #78): `forkpty()` now runs while a reader thread is alive (DeprecationWarning in T3, second Session) — drop the Python `preexec_fn` in `_spawn` or pause readers during spawn.

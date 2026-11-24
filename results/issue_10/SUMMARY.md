# Result — issue 10 / persistent-bash-pty-session

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: A session object that starts one long-lived interactive bash on a PTY with nl-shell's control channel on fd 3, sends a confirmed command byte-for-byte, and reports when it started and finished, its exit status and `PIPESTATUS`, its captured output and the session snapshot — all from control-channel records, never from printed text — and that owns the real terminal while a command runs. `cd` and `export` persist between commands; Ctrl-C interrupts; protocol violations put the session into degraded mode.
- Success criterion: both children's success criteria hold: child A (session core, spec §1–§5) — `python3 -m pytest tests/test_session.py` passes; child B (terminal ownership, spec §6) — `python3 -m pytest tests/test_session_terminal.py` passes. Each child brief states its own vectors.
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: pty-protocol v1 §1–§6 with the decisions below, as two children. / out of scope: wiring into the REPL or `cli.py` (#78); the policy gate and its fd-3 rejection (#12); sudo passthrough (#13); history write-back (#17); taint and the state block (#11); the output rendering filter (OSC 52 etc. — the human files a separate issue that blocks #78); the architecture doc 05 code-layout table.

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — N/A — close disposition (no patch to verify)
- C3 Change: none — patch.diff
- C4 Verification (red→green): none — N/A — close disposition (no patch to verify)
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — N/A — close disposition (no patch to verify)
- T2 Shape: none — N/A — close disposition (no patch to verify)
- T3 Runtime: none — N/A — close disposition (no patch to verify)
- T4 Contribution: none — N/A — close disposition (no patch to verify)
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

# Advisory review — SKIPPED (close disposition)

The reviewer leaf was skipped: this bundle's Plan concluded a close / no-fix disposition (split), so there is no patch to review.

- NEEDS-HUMAN — Confirm the close disposition 'split' (no patch was built). Override to a fix path (iterate-to-Do) if the close is wrong.


## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] Confirm the close disposition 'split' (no patch was built). Override to a fix path (iterate-to-Do) if the close is wrong.
- [x] T5 Judgment — Confirm affected-path prior art against merged and closed/rejected work, and the applicable human-only checklist — this copy has only one synthetic base commit, the brief supplies an uncorroborated path-based search summary, and INTEGRATION.md is absent; brief.md:26.
- [x] **Typed-ahead input becomes part of the next confirmed command.** `src/nl_shell/session.py:517-524` forwards terminal bytes to the PTY while a command runs. If the command doesn't read them, readline picks them up at the next prompt. Then `run()` pastes the next confirmed command after them (`session.py:454`), and `_drain_pty()` at `session.py:434` can't stop this because it only drains output. Concrete case: during `run("sleep 2", terminal=t)`, write `echo INJECTED; ` (no Enter) to the terminal. The next `run("true")` returns output `'INJECTED\n'`, so bash ran `echo INJECTED; true`. A 200 KB paste gave status 127 on the next `true`. This breaks the Goal's "sends a confirmed command byte-for-byte" and spec §5.1 ("exactly the confirmed bytes"). #78's gate will confirm one string while bash runs another. Fixing it needs a decision §5.3 doesn't currently allow: clear readline's line before the paste (e.g. a kill-line byte), or stop forwarding when no process is reading. That's why I tagged this [human] rather than [impl]. No test covers typeahead.
- [x] **A typed-ahead Enter, or any syntax error or comment-only command, degrades the session.** For a line that doesn't parse, PS0 never runs, but `__nls_done` still bumps `__nls_seq` (`session.py:80`, `session.py:85`). So a `D n+1` arrives with no `S`, and `pty_protocol.py:221-222` degrades the session. Reproduced: `run("fi")` and `run("# just a comment")` both raise `SessionDegraded: control record 'D' arrived out of order (without a start record)`. So does pressing Enter during a forwarded `sleep 2` (the *next* `run("true")` raises). An unclosed quote (`echo 'abc`) degrades after the 1 s back-at-a-prompt rule. All of these fail closed, and the behaviour comes from the spec's reference rcfile (v1.md:62). But in practice an ordinary typo forces a restart, and that loses `cd`/`export` state. The brief and the tests don't mention it. A human should decide whether that's acceptable for M0, or whether to treat "D n+1 without S" as "didn't parse, not run" (a spec change).
- [x] **Capture stops for good at the first forwarded byte**, including the Ctrl-C in vector 10 (`session.py:520-522`, `_Capture.stop` at `session.py:207-211`). The brief's Scope says capture pauses only on the alternate screen. Spec §6.2 makes capture a MAY, so this is allowed. Still, an interrupted or interactive command reaches #62 (failure classes) and #11 (state block) with only partial output, flagged by `input_forwarded`. That's a product trade-off the human should confirm, not a bug.
- [x] **Medium, possibly High** (same ratings as above). `target/src/nl_shell/session.py:82-106` (and the comment at `target/src/nl_shell/session.py:67-68`, which says `builtin`/`command` keep the hooks safe from user functions). **Input:** session state from a confirmed `source` (item 4). **What goes wrong:** bash lets a function be named `builtin` or `command`. Probed: after `builtin(){ echo "shadowed builtin: $*"; }`, `builtin printf "hi\n"` runs the function. Once such a function exists, every snapshot record is produced by attacker code: `F` (via `builtin compgen`), `L`, `T`, `B`, `H` and `V`. So the snapshot can hide the function itself and report the baseline `H`. `readonly -f` can't stop this, because there is nothing to mark readonly before the function is defined. This is a limit of reporting state from inside bash, which spec `pty-protocol/v1` §3 and ADR-0014 don't address. A human should decide whether to accept it as a known gap in the threat model (the in-shell snapshot trusts that `source`'d code didn't shadow `builtin`/`command`) or to require a different design, for example having the gate class `source`/`.` of untrusted files as session-altering and always confirmed, which ADR-0013 may already do.
- [x] **High once wired in** (threat model: "output writes the clipboard"; "What must hold: output rendering is filtered everywhere"). `target/src/nl_shell/session.py:494` and `:503`. **Input:** command output (item 1), for example `cat` of a repository file containing `\e]52;c;<base64>\a` (an OSC 52 clipboard write) or `\e[8m` (concealed text, so the user's screen hides what the capture and later the model's state block contain). **What goes wrong:** `_write_all(mirror_out, chunk)` copies PTY bytes to the real terminal with no filter. The brief puts the rendering filter out of scope, and nothing calls `run(terminal=...)` outside tests yet, so this can't be reached today. The open question in the brief says no issue owns the filter. A human should make sure one is filed and that it blocks #78, which makes the mirror user-facing.
- [x] T5 Judgment — Confirm affected-path merged and closed/rejected prior art before accepting novelty — the supplied history is one synthetic base commit, and the brief's broader src/ search does not independently establish history for every affected path — brief.md:26.
- [x] **Medium** (same rating as the round-1 finding this iteration was meant to fix: "the session doesn't enter degraded mode when its hooks were changed"; High once #12 relies on `F`/`L`). The `readonly -f __nls_done __nls_ret` fix (`session.py:114-115`) blocks redefining the hook, but the hook trusts code it doesn't protect. Every record is written through `builtin …` and `command tr` / `command cksum` (`session.py:96-107`). Bash calls a *function* named `builtin` or `command` before the real builtin, and `command tr` / `command cksum` are looked up on `PATH`. **Input:** a sourced repository script (item 4). Both routes below hide a new alias from `L` with `H` unchanged and no degraded mode (probed):

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
- By / date: Eduard Ralph / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- (empty is the common case)
- File the output rendering filter issue (OSC 52, concealed text, etc.) and make it block #78 — no tracker issue owns it yet (issue_10 §6 item 8).

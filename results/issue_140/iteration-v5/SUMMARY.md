# Result — issue 140 / persistent-bash-session-core

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: 
- Success criterion: `python3 -m pytest tests/test_session.py` passes on the host (real bash 5.3.9, no VM, no sudo). Every test that waits on bash passes an explicit timeout of a few seconds and closes its session in teardown. Covers:
  (a) `cd /tmp` then `pwd` → `/tmp`; `export FOO=bar` then `printf %s "$FOO"` → `bar`.
  (b) Spec Conformance vectors 1–8, 10, 12: `true` → `S 1`, `D 1 0 0`, snapshot, `E`; `false | true` → status 0, pipestatus `1 0`; `(exit 3)` → 3; `printf 'D 99 0 0\n'` and `printf '\x1b]133;D;0\x07'` → only real records, status 0; `echo 'done!!'` → `done!!`; `alias ll2='ls -la'; g(){ :; }` → next `F` gains `g`, `L` contains `ll2`; `PROMPT_COMMAND=:` → degraded at that command's snapshot with a reason; `sleep 5` then interrupt → `D` status 130 < 3 s after `\x03`, not degraded; a command with `ESC [201~`, `ESC` or another C0 control except TAB/LF is refused and nothing reaches the PTY.
  (c) `exec 3>&-` typed raw → degraded.
  (d) no-output, multi-line, here-doc and `sleep 1 &` each give exactly one S/D pair; after `sleep 3 &` the next `J` is `0` and the session stays usable; a finished background job's notice (`[1]+ Done …`) appears in the next command's output (pinned, and documented).
  (e) empty line, `# x` and `fi` each report not-run with the `D` status and leave the session healthy; `echo 'abc` (unclosed quote), `read x` and `read x </dev/tty` with no input each degrade within 5 s by the prompt rule. With the session's `/proc` root pointed (constructor keyword `proc_root`, default `"/proc"`) at a temp dir where bash's `syscall` file is missing, a run that needs the prompt rule degrades with a reason naming the file, never hangs and never reports healthy-not-run.
  (f) `T`, `B`, `X`, `P`, `J`, `H`, `V` present; `export LD_PRELOAD=/x.so` changes `V` and is reported; `PS0=` then `true` → DEGRADED, and `true` is not reported not-run with a healthy session. I2-b: each of `PROMPT_COMMAND+=(':')`, `PS0='x'`, redefining one of nl-shell's hook functions, and `export TERM=dumb`, as a confirmed command, degrades at THAT command's snapshot, and a following `run("echo hello")` raises without writing to the PTY. Negative (no over-degrading): `readonly FOO=1`, `trap 'echo hi' EXIT`, and `PS1='x$ '` each leave the session HEALTHY, and a following `echo ok` returns `ok` (`T` still reports the trap).
  (g) I2-c reproducers: each of `PS1='${__nls_x[__nls_state=1]-}\$ '`, `readonly`, and `trap '<assign>' DEBUG`, run once per variable in a module-level tuple `HOOK_STATE_VARS`, followed by `true` then `touch MARK; echo printed; (exit 7)`, ends DEGRADED or with the third command reported as ran (output and status 7) — never "ran False" with a healthy session. The test checks that every shell variable the rcfile hooks use has prefix `__nls_` and every `__nls_` name in the rcfile text is in `HOOK_STATE_VARS`. I2-d: `alias builtin=" " printf=__p` then `touch MARK; echo printed; (exit 7)` ends DEGRADED or reported as ran with that output and status; after `alias ls='touch PWNED' builtin=' ' alias=':'` the next `L` still lists `ls`.
  (k) `x=$(sleep 2); echo hi`, `cd "$(sleep 1.5; echo /tmp)"`, ``y=`sleep 1.5` `` finish normally with a HEALTHY session.
  (l) a literal separator byte and a newline in `PATH`, an alias and a trap round-trip exactly; `hash -p <script> tr|cksum|wc`, `BASH_CMDS[tr]=<script>` and a `PATH` with fake `tr`/`cksum`/`wc` first leave the snapshot honest (no marker).
  (m, first half) a test-HOME `~/.bashrc` setting an alias and its own `PROMPT_COMMAND` (as a two-element array) → alias in baseline `L`; the user hook still runs, before nl-shell's snapshot. I3: in the baseline `H` text, nl-shell's hook is the last `PROMPT_COMMAND` element and `PS1`/`PS2` equal nl-shell's fixed values, and the same holds in the `H` of the snapshot after each of 3 further runs.
  (n) `HISTFILE` unset; `[ -p /dev/fd/3 ]` true; every record ends in `\n` with no `\r`; a record with `\r` fed to the parser is malformed (→ degraded).
  (o) restart after degraded mode gives a healthy session with a fresh baseline.
  (q) with a test-HOME `PROMPT_COMMAND` printing `HOOK-OUTPUT`, 20 runs each of `echo hello` and `printf abc` return exactly the command's own output.
  No test for any functrace / `declare -ft` / `extdebug` / builtin-shadowing / `read -u N` case (R1–R3).
  **Docs** (same patch; every claim in them must match the closed list — R1): spec `pty-protocol/v1` §1.2 (user `PROMPT_COMMAND` before the snapshot; nl-shell sets `PS1`/`PS2`), §1.3 reference rcfile (`:50-76`) replaced (no external programs, `\\n` inside `PS0`) with a short "what this protects" paragraph that states the closed list and "nothing else is claimed yet (#141, #145)" — no per-evasion list, no functrace sentence; §3 (`H`/`V` carry encoded `declare -p` text compared exactly; what `H` covers, incl. `TERM`; output between `S` and `D` includes bash's own job notices), §4.1 (`D n+1` without `S n+1` = nothing ran), §4.2 (`:102-107`: first trigger excepts that case; third trigger states the decision-7 rule and that terminal reads on other fds, timed reads `read -t`/`read -n1 -t` and `select` are known limits, #136), §4.3 (`:108-109`, degraded gets no further commands until restart), §4.4–§4.5 (`:110-116`: one line each that restore-cwd and the `session_restart` record land with #121), Conformance vector 8 (`:180`) → "degraded at that command's snapshot (`H` changed)", the vectors note (`:190-191`) names what `tests/test_session.py` now checks, §Versioning (`:164-165`) one sentence: while `status: draft`, v1 changes in place; the v2 rule applies from `stable`. Policy-gate `v1` §7.5 item 5 (`:197-201`, `V` is encoded `declare -p` text, not `cksum`) and item 6 (`:202`, decision 10); item 6 gains one clause saying this session degraded mode (refuse) is not the gate-level target-mismatch state of item 7. Leave item 7 (`:203-204`) and ADR-0023 `:74-77` unchanged: they use "degraded" for that different, gate-level state. Glossary `docs/design/architecture/10-quality-risks-glossary.md:71` ("Degraded mode" row) → decision 10 wording (the session state; no further commands until restart). ADR-0014 Decision 1 (`:45-46`, decision 6) and Decision 2 (`:52-54`, decision 10); ADR-0013 `:72-74` (same degraded wording). Keep each ADR edit to those sentences. Threat model `.oss-scanner/threat_model.md`: §How to exercise it says the session tests need only bash; Known gaps list (heading `:165`, list `:167-180`) gains ONE interim bullet: the session core claims only the closed list (one line), nothing else is claimed until #141 (tamper checks) and #145 (gap review) land, `run()` without a timeout can wait forever on a terminal read on an fd other than 0 (#136), and #78 must not wire the session to confirmed commands before #141 lands. The bullet names #141 so #141 removes or rewrites it. The rcfile comment in `session.py` says the same as spec §1.3, no more.
- Repo + branch target: eduralph/nl-shell @ main — build on `origin/main` = `c47c5c2`. The stale stack (`pdca-integration/main-r2546dbf9639f` = `2ddc3e8` = `8c95e05` "pdca-integrate: issue_14" + `4c755f2` + "pdca-integrate: issue_92"; the #140 body's `8c95e05` and this `2ddc3e8` are the same stack, missing 25 commits of `main`) was removed from this bundle on 2026-10-16; #140 does not depend on #14 or #92. Every `path:line` here is on `c47c5c2`.
- Scope (one logical fix) / out of scope: 

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: likely-fix
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (90 of 90 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — security-relevant paths touched and the threat model updated: docs/design/specs/policy-gate/v1.md docs/design/specs/pty-
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review issue #140: add an unwired persistent bash PTY session with fd-3 protocol snapshots, exact command pasting, and sticky degradation under the brief's closed guarantees.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The closed guarantees and explicit exclusions give a bounded acceptance contract; no general tamper resistance is required (brief.md:7; target/docs/design/specs/pty-protocol/v1.md:144). |
| C2 Reproduction (red pre-fix) | N/A | New functionality has no existing symptom to reproduce; removal sensitivity is assessed under C4 (brief.md:31). |
| C3 Change | PASS | Changes stay within the session, parser, dependency, tests, and specified design documents; the core remains unwired (target/src/nl_shell/session.py:9; target/pyproject.toml:15). |
| C4 Verification (red→green) | PASS | Independent stash/restore smoke check went from missing session module to passing real bash checks; frozen evidence additionally shows 90/90 red and 90 green, although pytest is unavailable for a full local rerun (reviewer-red.log:1; reviewer-green.log:1; gate-logs/C4-verify.log:13; gate-logs/C4-verify.log:3323). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Close the I2-b value-change detection gap: confirmed scratch-state assignments remain healthy because their values are overwritten before H, contradicting the promised own-command degradation (target/src/nl_shell/session.py:128; target/docs/design/specs/pty-protocol/v1.md:148; target/tests/test_session.py:522). |
| T1 Structure | PASS | Pure protocol sequencing is separated from PTY lifecycle and I/O, making failure transitions independently inspectable (target/src/nl_shell/pty_protocol.py:157; target/src/nl_shell/session.py:322). |
| T2 Shape | PASS | Threat-model coverage explicitly limits the claim and prohibits wiring confirmed commands before #141; the frozen touch-check passes and the independent docs-link scan found zero broken links (target/.oss-scanner/threat_model.md:181; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen full-suite evidence reports 267 passing tests; independent real-bash smoke checks exercised persistence, output, pipeline status, refusal, degradation, and restart, but did not replace the unavailable pytest rerun (gate-logs/T3-suite.log:15; reviewer-green.log:1). |
| T4 Contribution | N/A | Contribution artifacts are absent by design; the substantive contribution audit is deferred to the mandatory publish rerun (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm the path-based prior-art disposition against merged and closed/rejected work: the brief records that check, but this one-commit target has no remote or PR evidence with which to independently settle it (brief.md:38). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the completed closed guarantees meet the intended standalone-core milestone after the C5 discrepancy is resolved; retain the already accepted unwired scope and #141 integration prerequisite (target/.oss-scanner/threat_model.md:181; target/docs/design/specs/pty-protocol/v1.md:144). |

Independent finding: ordinary value assignments evade the promised I2-b degradation

Using real bash 5.3.9 and the installed ptyprocess, I started a fresh session for each of these confirmed commands with `Session.start(env=env, cwd=home, timeout=5)` and `session.run(command, timeout=5)`:

```text
'__nls_n=42'       ran=True healthy=True status=0
'__nls_st=42'      ran=True healthy=True status=0
'__nls_v=changed'  ran=True healthy=True status=0
'__nls_c=changed'  ran=True healthy=True status=0
'__nls_ps=(42)'    ran=True healthy=True status=0
```

These are ordinary assignments within the explicit I2-b claim, not excluded DEBUG/functrace or builtin-shadowing evasions. The hooks overwrite the values before recording H (target/src/nl_shell/session.py:111, target/src/nl_shell/session.py:128, target/src/nl_shell/session.py:139). The test matrix checks an integer attribute change, but not these plain value changes (target/tests/test_session.py:530). Add regression coverage for the promised own-command degradation and resolve the implementation/contract discrepancy. This finding does not demonstrate a hidden executed command; it demonstrates failure of the expressly claimed degradation behavior. Narrowing that guarantee instead would require a human scope decision.

Verification limits and grounding

- The disposable target identifies its base as c47c5c2 and its applied changes match the supplied patch scope. Citations above were checked against this target; no stale-target caveat was needed. The patch was restored after the independent red leg.
- `reviewer-smoke.py` is the independent runnable check. Run from this review directory with `TMPDIR="$PWD/reviewer-tmp" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/target/src" python3 reviewer-smoke.py`. Red failed importing the absent implementation; green exercised real PTY and proc-syscall behavior. Neither external dependency was replaced with a shim or fixture.
- Python cannot import pytest in this reviewer environment. Therefore the complete 90-test and 267-test results above are attributed to the frozen gate logs, not represented as independent full-suite reproductions. All four supplied gate logs were read; the wrappers are harness-scoped. No missing-log escalation applies.
- Independent `git diff --check` passed. `python3 scripts/docs_links.py` reported 63 links in 55 Markdown files, zero broken; it also emitted three host messages, `Failed to create stream fd: Operation not permitted`, while exiting successfully.
- The target has one synthetic base commit, no configured remote, and no history entries for the three new affected paths. The brief names the prior path-based search and merged design PRs, but closed/rejected upstream work cannot be independently established from this bundle. No INTEGRATION.md was supplied or found in the target.
- The C5 symptom-guard smell test found no eager/load-time capability workaround: the `os.ptsname` feature check selects a platform/Python compatibility implementation, and `/proc` failures fail closed rather than conceal a load-time cause (target/src/nl_shell/session.py:740).

This report is advisory; deterministic gates retain their separate role.
<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 140 / persistent-bash-session-core

I drove the real `nl_shell.session.Session` (target `src/`, system `ptyprocess`, bash 5.3.9)
from scratch scripts in this sandbox. pytest is not installed here, so I could not re-run
`tests/test_session.py` itself. I judged C4/T3 from the frozen logs instead.

## Evidence (C4 / T3)

- `gate-logs/C4-verify.log`: green 90/90; red 90/90, every failure is
  `ModuleNotFoundError: No module named 'nl_shell.session'` from the in-test import
  (`tests/test_session.py:28`, `:67`). For two new modules that is the only red the gate
  can show, and no test passed with the fix reverted, so no test is a tautology that
  ignores the module. The tests drive the production `Session`/`ProtocolTracker`, not a
  copy (`tests/test_session.py:904-912` also pins the spec's reference rcfile to `RCFILE`).
  T3: 267 passed. I found no problem with the evidence.

## Refutation attempts that failed (the fix held)

- I2-a, multi-line input where the first line runs nothing (`'# x\ntouch MARK'`,
  `'\ntouch MARK'`, `')\ntouch MARK'`, `'fi\ntouch MARK'`) and the reverse (`'true\n# x'`):
  every case gave `ran=True`, the right status, a healthy session, and MARK existed only
  when it should (`src/nl_shell/pty_protocol.py:227-241`).
- Hooks under user shell options: `set -u` (+ an empty line), `set -e`, `IFS=x`,
  `shopt -s failglob nullglob extglob`, `set -f`, `set -o pipefail`, `shopt -s lastpipe`,
  `LC_ALL=C`, `set -o posix`. Each one, followed by `true` and then
  `touch MARK; echo printed; (exit 7)`, reported the third command as ran with status 7.
  The only exception was `set -e`, where bash itself exits on `(exit 7)` and the session
  degrades with "the shell exited". That is correct, not a lie.
- I2-b attributes: `declare -n V=PS1`, `declare -i V`, `declare -u V` and `export V` on
  every non-function name in `HOOK_STATE_VARS` (`src/nl_shell/session.py:59-72`). Every
  change bash accepted degraded at that command's own snapshot. The two that did not
  degrade (`declare -n __nls_ps`, `declare -n __nls_user_pc`) were refused by bash
  ("reference variable cannot be an array"), so nothing changed.
- A PTY write deadlock in `run()`. `_write_all` (`src/nl_shell/session.py:509`, `:739-747`)
  is a blocking write that runs before the timeout loop, so a deadlock would ignore
  `timeout=`. I tried single lines up to 100 KB and pastes of up to 5000 lines (315 KB).
  All finished in at most 2.2 s with correct output. No hang.

## Findings

- NEEDS-HUMAN [impl] — The docs claim more than the code gives for I3 (R1 makes this a
  defect). `docs/design/specs/pty-protocol/v1.md:153-157` says "nothing confirmed code sets
  runs after the snapshot" and "one to `PS1`/`PS2` is overwritten".
  `docs/design/specs/pty-protocol/v1.md:51-52` says "no prompt string the user or a command
  set is ever expanded". `.oss-scanner/threat_model.md:184` repeats the first claim.
  Concrete failing case: the confirmed command `readonly PS1='$(touch PS1_RAN)\$ '`.
  `__nls_snap` skips the reset because the attributes are `-r`
  (`src/nl_shell/session.py:135`). The final `PS1='\$ '` then fails on the readonly
  variable (`src/nl_shell/session.py:167`), so bash expands the user's `PS1` after `E`, and
  `PS1_RAN` is created after the snapshot. The session does degrade ("H differs", result
  seq 1), so I2 holds, but the code did run after the snapshot and `PS1` was not
  overwritten. The same happens with `PROMPT_COMMAND+=('touch PC_RAN')`: the appended
  element runs after nl-shell's hook in that same prompt cycle, and `PC_RAN` exists after
  the snapshot. Here the doc's own next clause ("degrades (`H`)") describes it honestly,
  but the lead sentence does not. (`readonly PS2=…` did not run, since PS2 is never
  shown.) Fix: reword those three places to say what really happens. A confirmed change to
  `PROMPT_COMMAND`, `PS0`, or a readonly/attributed `PS1`/`PS2` degrades the session at
  that command's snapshot, but may run once after it. Only a plain or exported `PS1`/`PS2`
  is overwritten. The brief's own I3 wording has the same gap, so the human may want to
  confirm the new wording at sign-off.
- Note, not a defect of this child: after the confirmed command `set -v`, every result's
  `output` includes bash's echo of the hook text
  (`\__nls_done; \__nls_snap "$(\builtin trap -p)"`), because verbose mode prints the
  `PROMPT_COMMAND` text before the end marker (`src/nl_shell/session.py:117`, `:171`). Exact
  output is claimed only for the (q) `HOOK-OUTPUT` case, and `set -v` is next to the
  xtrace/`PS4` family that the brief leaves to #141/#145. No doc claims otherwise, so I am
  only recording it for #145.

Apart from the I3 doc overclaim above, I could not refute the fix. I tried multi-line
not-run handling, shell-option safety of the hooks, attribute tampering on hook state, and
a large-paste deadlock.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory): issue 140, persistent-bash-session-core

**Attacker-reachable inputs this diff touches:** command output on the PTY (threat model "Where untrusted input enters" item 1), which goes into `_Output` and `CommandResult.output`; and session state from `~/.bashrc` (item 4), which ends up in the baseline snapshot. The confirmed command bytes (item 5, model output) reach `check_command` and the paste. Nothing calls the session yet (#78), so none of these paths can be reached in the shipped product today.

## Findings

- NEEDS-HUMAN [impl] — **Low (docs claim more than the code gives; R1 says this counts as a defect)**: `docs/design/specs/pty-protocol/v1.md:51-52` says nl-shell resets `PS1`/`PS2` "so no prompt string the user or a command set is ever expanded". `v1.md:153-157` and `.oss-scanner/threat_model.md:184` say "nothing confirmed code sets [in] `PS1` … runs after the snapshot" and that a change to `PS1`/`PS2` "is overwritten". The code only overwrites plain or exported `PS1`/`PS2` (`src/nl_shell/session.py:135`, which matches `declare -[-x]` only). The input is a confirmed command, which comes from the model, a text-only attacker can steer it, and the user confirms it. Example: `declare -r PS1='$(touch /tmp/X)\$ '`. It can't be overwritten: the reset at `session.py:167` fails with "PS1: readonly variable", which I checked in bash 5.3.9. So `$(touch /tmp/X)` runs when the next prompt is drawn, which is after `E`. The same holds for `PROMPT_COMMAND+=('touch /tmp/X')`: that element runs after nl-shell's hook, so after the snapshot. There is no real bypass: `H` changes in both cases, the session degrades at that command's own snapshot, and nothing more is written (`ps1-readonly` and `prompt-command-array` rows, `tests/test_session.py:525-533`). What's wrong is the wording, which the brief's R1 counts as a defect. Fix: say that a `PS1`/`PS2` with attributes, or any change to `PS0`/`PROMPT_COMMAND`, degrades the session, and that its code may still run once after that snapshot before nl-shell refuses further commands. Change the threat-model bullet to match. Test: add a `test_table_a_row_1` row, `declare -r PS1='$(touch MARK)\$ '`, and assert that it degrades with `result.seq == 1`. Whether `MARK` exists afterwards only pins the documented behaviour; it is not a security check. I didn't run this through `Session`: `ptyprocess` isn't installed in any Python I can reach here. The bash behaviour it relies on is confirmed.

## What I checked and found no problem with

- **Printed text forging status or completion.** Status and completion come only from fd-3 records (`pty_protocol.py:187-303`). `printf 'D 99 0 0\n'` and the OSC 133 look-alike are covered by vector (b). Out-of-order, duplicate and malformed records degrade the session. Records containing `\r` and records over `MAX_RECORD` degrade it too. Number fields are capped at 18 digits (`pty_protocol.py:26`), so `int()` can't raise on huge numbers.
- **Output delimiting** (`session.py:256-317`). Output only counts after readline's `ESC [?2004l`, which readline prints before the command runs, so command output can't come before it. The end marker uses a 128-bit token that changes at every start (`session.py:404`). A text-only attacker can't learn it. Only code running as the user can read it, via `declare -f __nls_done`, and that is out of scope. The output kept is capped at `MAX_OUTPUT` (1 MiB) and the truncated flag is set. The look-behind buffer is capped at the marker length.
- **What is confirmed is what runs** (`pty_protocol.py:139-148`, `session.py:505-509`). ESC, `ESC [201~` and every C0 control except TAB and LF are refused before anything is written. ISIG/IXON/VLNEXT keys (the terminal's signal, flow-control and literal-next keys) are all C0, so they are refused too. The paste is only written once bash is blocked in readline's `pselect6` (`_wait_for_prompt`). At that point the terminal is in non-canonical mode, so the kernel's line-editing keys (erase, kill) and its 4096-byte line limit don't touch the pasted bytes. DEL (0x7f) and C1 characters are allowed. Inside a bracketed paste, readline inserts them literally, so they don't change what runs. Hiding them from the user is the confirm UI's job (#74). The brief's refuse list matches the code.
- **Sticky degraded mode.** `run()` raises before writing once degraded (`session.py:498-507`), and the tests check that nothing was written, using a spy on PTY writes.
- **`/proc` prompt rule.** If `/proc` can't be read, the session degrades (fails closed) at start and during a run (`session.py:446`, `553-557`, `612-617`).
- **Unbounded wait.** `run()` without a timeout can wait forever on a terminal read on another fd. That is a known gap the threat model already lists (#136). I'm not raising it again.
- **Scope.** Function shadowing, DEBUG traps, readline bindings and `bind -x` are out of scope for this child (brief R1, #141/#145). I didn't file them.

Gates: C4 and T3 pass, and T2 passes with the threat model updated (`check-gates.json`).

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C5 Causal adequacy — Close the I2-b value-change detection gap: confirmed scratch-state assignments remain healthy because their values are overwritten before H, contradicting the promised own-command degradation (target/src/nl_shell/session.py:128; target/docs/design/specs/pty-protocol/v1.md:148; target/tests/test_session.py:522).
- [ ] T5 Judgment — Confirm the path-based prior-art disposition against merged and closed/rejected work: the brief records that check, but this one-commit target has no remote or PR evidence with which to independently settle it (brief.md:38).
- [ ] Validation — fitness-to-purpose — Decide whether the completed closed guarantees meet the intended standalone-core milestone after the C5 discrepancy is resolved; retain the already accepted unwired scope and #141 integration prerequisite (target/.oss-scanner/threat_model.md:181; target/docs/design/specs/pty-protocol/v1.md:144).
- [ ] The docs claim more than the code gives for I3 (R1 makes this a defect). `docs/design/specs/pty-protocol/v1.md:153-157` says "nothing confirmed code sets runs after the snapshot" and "one to `PS1`/`PS2` is overwritten". `docs/design/specs/pty-protocol/v1.md:51-52` says "no prompt string the user or a command set is ever expanded". `.oss-scanner/threat_model.md:184` repeats the first claim. Concrete failing case: the confirmed command `readonly PS1='$(touch PS1_RAN)\$ '`. `__nls_snap` skips the reset because the attributes are `-r` (`src/nl_shell/session.py:135`). The final `PS1='\$ '` then fails on the readonly variable (`src/nl_shell/session.py:167`), so bash expands the user's `PS1` after `E`, and `PS1_RAN` is created after the snapshot. The session does degrade ("H differs", result seq 1), so I2 holds, but the code did run after the snapshot and `PS1` was not overwritten. The same happens with `PROMPT_COMMAND+=('touch PC_RAN')`: the appended element runs after nl-shell's hook in that same prompt cycle, and `PC_RAN` exists after the snapshot. Here the doc's own next clause ("degrades (`H`)") describes it honestly, but the lead sentence does not. (`readonly PS2=…` did not run, since PS2 is never shown.) Fix: reword those three places to say what really happens. A confirmed change to `PROMPT_COMMAND`, `PS0`, or a readonly/attributed `PS1`/`PS2` degrades the session at that command's snapshot, but may run once after it. Only a plain or exported `PS1`/`PS2` is overwritten. The brief's own I3 wording has the same gap, so the human may want to confirm the new wording at sign-off.
- [ ] **Low (docs claim more than the code gives; R1 says this counts as a defect)**: `docs/design/specs/pty-protocol/v1.md:51-52` says nl-shell resets `PS1`/`PS2` "so no prompt string the user or a command set is ever expanded". `v1.md:153-157` and `.oss-scanner/threat_model.md:184` say "nothing confirmed code sets [in] `PS1` … runs after the snapshot" and that a change to `PS1`/`PS2` "is overwritten". The code only overwrites plain or exported `PS1`/`PS2` (`src/nl_shell/session.py:135`, which matches `declare -[-x]` only). The input is a confirmed command, which comes from the model, a text-only attacker can steer it, and the user confirms it. Example: `declare -r PS1='$(touch /tmp/X)\$ '`. It can't be overwritten: the reset at `session.py:167` fails with "PS1: readonly variable", which I checked in bash 5.3.9. So `$(touch /tmp/X)` runs when the next prompt is drawn, which is after `E`. The same holds for `PROMPT_COMMAND+=('touch /tmp/X')`: that element runs after nl-shell's hook, so after the snapshot. There is no real bypass: `H` changes in both cases, the session degrades at that command's own snapshot, and nothing more is written (`ps1-readonly` and `prompt-command-array` rows, `tests/test_session.py:525-533`). What's wrong is the wording, which the brief's R1 counts as a defect. Fix: say that a `PS1`/`PS2` with attributes, or any change to `PS0`/`PROMPT_COMMAND`, degrades the session, and that its code may still run once after that snapshot before nl-shell refuses further commands. Change the threat-model bullet to match. Test: add a `test_table_a_row_1` row, `declare -r PS1='$(touch MARK)\$ '`, and assert that it degrades with `result.seq == 1`. Whether `MARK` exists afterwards only pins the documented behaviour; it is not a security check. I didn't run this through `Session`: `ptyprocess` isn't installed in any Python I can reach here. The bash behaviour it relies on is confirmed.
- [ ] **I3 claims more than the scope covers, and nothing tests it.** The brief says "(I3) Nothing confirmed code can install runs between the snapshot and the next paste except nl-shell's own hook". The out-of-scope list then excludes "readline state and bindings (`bind`…)" and "DEBUG/RETURN traps inside the hooks". Two problems:
- [ ] **Decision 10 ("degraded = refuse") is edited into some docs and left out of others, so they will contradict each other.** The brief rewrites spec §4.3, policy-gate item 6 (`:202`), ADR-0014 Decision 2 and ADR-0013 `:72-74`, and says "edit no other ADR". These still say degraded means "everything needs a confirm" or "everything `mutating`":
- [ ] **The brief adds claims and tests that neither the tracker body nor the human's R1–R5 decisions cover.** Compared with `notes.json`:
- [ ] **The "keep the patch under 100 KB" goal pulls against the scope.** The brief says "Keep the patch under 100 KB (v4 was 100,456 B; the removals should bring it under)". This round removes the functrace handling (R2). But it also adds new tests (TERM, I2-d, `/dev/tty`, `proc_root`, job notice) and new doc text (threat-model bullet, §Versioning, §4.4–§4.5 one-liners, the job-notice docs). Nobody has shown the net size will be negative. If 100 KB is a hard limit, say what gets cut when it is exceeded. If it isn't, don't state it as a success condition.
- [ ] **The base history doesn't match, and the starting artifact isn't in the record.** The brief calls the stale base `pdca-integration/main-r2546dbf9639f = 2ddc3e8` and says v4 "was built on `2ddc3e8`". The issue says "NOT the stale `stack-base` `8c95e05` (C4 failed on it in v4 and v5)". Two different stale bases are named for v4. The brief's main instruction, "Start from `iteration-v4/patch.diff` in this bundle", depends on knowing what v4 was built on. Neither that file nor the brief's "does not apply at `v1.md:43`" claim can be checked from the inputs. Reconcile the two SHAs, so Do knows which hunks were already rebased.
- [ ] **Some citations can't be checked against the target, and some are off by one.**
- [ ] T5 Judgment — Confirm that draft v1 may change in place and that the coupled protocol/Proposed ADR edits belong in this child; that decision determines compatibility expectations and the accepted scope (patch.diff:31; patch.diff:44; patch.diff:292).
- [ ] **The gating C4 red is a base mismatch, not a defect in the fix.** `check-gates.json` C4 says "patch.diff did not apply onto 'origin/pdca-integration/main-r2546dbf9639f'". That branch (`2ddc3e8`) sits on the stale `8c95e05` stack-base, which the brief says not to use. It does not contain `c47c5c2`: `git log 2ddc3e8..c47c5c2` lists #124–#133. The hunk that fails is `docs/design/specs/pty-protocol/v1.md:45`, because that file differs by 26 lines between the two bases. `git apply --check` passes cleanly on `c47c5c2`, and on that base the proof is 82 red → 82 green (above). A human needs to choose the base the integration branch is rebuilt on, or rebase the patch onto it. The builder cannot fix this by iterating on the code.
- [ ] **One confirmed command can turn off bracketed paste without degrading, and the next command then runs as raw keystrokes.** At `src/nl_shell/session.py:545`, `run()` always writes `PASTE_START + data + PASTE_END + "\r"`, but nothing checks that readline still has bracketed paste on. Reproduced case: `export TERM=dumb` (or `bind 'set enable-bracketed-paste off'`) is reported as ran and HEALTHY. Then `run("echo /etc/hostnam\tX; touch $HOME/MARK")` is written to the PTY and **runs** (MARK is created). Only after that does the session degrade with "output could not be delimited". With paste off, a TAB in the confirmed bytes triggers completion, so the line bash runs is not the confirmed line. That breaks §5, and brief decision 10 says "refuse, not confirm then run". The threat model's Known gaps (`.oss-scanner/threat_model.md:184`) already lists "readline state" for #141, which explains the `bind` case. `TERM` is an environment variable, though, not a readline binding. A human should confirm that #141's scope (or V) covers `TERM`, or decide this child should add `TERM` to H.
- [ ] **High** (scale: "a session change (alias, function, hook) goes undetected by the gate"; it also breaks the brief's invariant I2). Locations: `src/nl_shell/session.py:106` (the rcfile comment says the hooks are safe because every call goes through `builtin`), `:126` (`PS0` uses `builtin printf` to write `S`), `:140`, `:175-176`, and the same claim in the spec §1.3 text (`patch.diff:194`). **Input:** a shell function named `builtin` (or `command`). Bash lets a function shadow both names. Anyone who controls a script the user confirms with `source`, or the user's `~/.bashrc`, can define one. Once it exists, every `builtin …` call in `PS0`, `__nls_done` and `__nls_snap` runs the attacker's function instead. The function can then fake any record: H, F, L, T, P, V, even `S`. No external program is needed, so the `hash -p` / `BASH_CMDS` / `PATH` tests in (l) never see it. **What goes wrong**, reproduced against the patch's own `Session`:
- [ ] **The tracker record is missing, so the problem statement can't be checked.** The bundle has only `brief.md`. There is no `notes.json` and no `sources/`. The brief's authority rests on `results/issue_101/brief.md` ("Settled decisions (from the parent brief…)", "this brief supersedes the #101 issue text"), `iteration-v5/patch.diff`, `iteration-v3/patch.diff` and `iteration-v3/SUMMARY.md` §6 (the "prior reproducers for (g) and (k)"). None of these is in the bundle or in the target (`**/issue_101/**` finds nothing in `$PDCA_TARGET`). So no reviewer can confirm that decisions 1–13 match the maintainer's thread. Do also cannot "reuse … `_Output`" (decision 13) or the v3 reproducers unless the driver supplies those files. Either attach them to the bundle, or restate in the brief the parts Do relies on (the `_Output` boundary cut and the §6 reproducers).
- [ ] **The brief changes the v1 wire format, which the spec says needs v2.** `pty-protocol/v1.md:164-165` says: "Changing a record's fields, the paste framing or the start-up command requires v2." The brief changes `H` from "a `cksum` of `$PROMPT_COMMAND` and `$PS0`" (`:94`) to encoded `declare -p` text over a wider set. It changes `V` from a `cksum` (`:94-95`, `policy-gate/v1.md:199`) to encoded text. It redefines `P` as a reversible encoding, `L` to use "ONE reversible encoding" in place of the `\x1e` join (`:84`), and the hook order (`:48`, ADR-0014 `:45-46`). All of this happens inside `v1`. The spec is `draft`/`unstable`, so this may be acceptable, but the brief never mentions the versioning clause. A docs reviewer will flag the contradiction. The brief should either edit `:164-165` in the same patch or justify keeping `v1`.
- [ ] **Scope is one feature plus a docs revision of five documents.** The Docs list rewrites normative text in spec §1.2, §1.3, §3, §4.1, §4.2 and §4.3, Conformance vector 8 and the vectors note. It also edits policy-gate §7.5 items 5–6, ADR-0014 Decisions 1–2, ADR-0013 `:72-74` and the threat model. Several of these reverse earlier decisions (hook order, "degraded = every command needs a confirm" → "refuse"), so they go beyond describing the new code. That is a second logical change (re-deciding the protocol) bundled with the implementation. With 13 test letters this makes a large review surface for a `high` difficulty run. Consider landing the spec/ADR revision as its own docs bundle, or say why it has to ship with the code.
- [ ] **§4.3 and §4.4 conflict after the edit, and restart scope is unclear.** The brief has §4.3 say "degraded gets no further commands until restart", and (o) only requires "restart … gives a healthy session with a fresh baseline". But §4.4 (`pty-protocol/v1.md:110-113`) still requires that a restart "restores the last cwd with a visible, logged `cd -- <path>`", and §4.5 requires a `session_restart` log record. The brief puts session recovery out of scope (#121) but doesn't mark §4.4–4.5 as deferred. A reviewer can't tell whether a restart that loses cwd is conformant. Add one line to the Docs list (or to Out of scope) saying `restart()` here does not implement §4.4–4.5.
- [ ] **The prompt rule rests on an unchecked host assumption.** Decision 7 (and criteria (e), (k), and implicitly (b) vector 8) needs to read `/proc/<bash pid>/syscall`. That file needs ptrace-attach permission, which depends on `kernel.yama.ptrace_scope` and on any sandbox the gate runs pytest in. This very run's sandbox could not even start a nested user namespace. The brief lists `proc-syscall` as an external dependency but doesn't say what the session should do if the read fails (degrade? raise?), and doesn't say the gate host was checked. If the read is denied, (e) and (k) go red for an environmental reason, not because of the code, and "re-run a timeout red once" won't help. Specify the failure behaviour, and confirm that the C4 gate host (`engine/scripts/run-verify.sh`) can read the file.
- [ ] **The threat-model bullet goes into a "do not report" list.** The Docs item adds "ONE interim bullet" to Known gaps saying the remaining Table A rows and all of Table B land later. That section is titled `## Known gaps: do not report these on their own` (`.oss-scanner/threat_model.md:165`), while `:205` and `:220` rate "a session change (alias, function, hook) goes undetected" as High and "the session doesn't enter degraded mode when its hooks were changed" as Medium. An interim note in that list tells scanners to suppress exactly the class of finding the follow-up child exists to close, and it has no removal trigger. The brief also never names the file's path (`.oss-scanner/threat_model.md`). Name the path, and have the bullet name the child-2 tracking id so it can be removed when that child lands.
- [ ] **Criterion (g) has an escape hatch.** "ends DEGRADED or with the third command reported as ran" passes for an implementation that degrades on any `readonly` or `trap … DEBUG` at all, including legitimate user commands. That is consistent with I2, but nothing in (a)–(q) checks that an ordinary unrelated `readonly FOO=1` or `trap 'echo hi' EXIT` keeps the session HEALTHY. Without such a negative, over-degrading passes every gate. Add one health-preserving case to (g) or (f) if over-degradation counts as a regression.

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
- Iteration delta (if iterating): Auto-iterate (round 2): rebuilding for the implementation-level findings — C5 Causal adequacy — Close the I2-b value-change detection gap: confirmed scratch-state assignments remain healthy because their values are overwritten before H, contradicting the promised own-command degradation (target/src/nl_shell/session.py:128; target/docs/design/specs/pty-protocol/v1.md:148; target/tests/test_session.py:522).; The docs claim more than the code gives for I3 (R1 makes this a defect). `docs/design/specs/pty-protocol/v1.md:153-157` says "nothing confirmed code sets runs after the snapshot" and "one to `PS1`/`PS2` is overwritten". `docs/design/specs/pty-protocol/v1.md:51-52` says "no prompt string the user or a command set is ever expanded". `.oss-scanner/threat_model.md:184` repeats the first claim. Concrete failing case: the confirmed command `readonly PS1='$(touch PS1_RAN)\$ '`. `__nls_snap` skips the reset because the attributes are `-r` (`src/nl_shell/session.py:135`). The final `PS1='\$ '` then fails on the readonly variable (`src/nl_shell/session.py:167`), so bash expands the user's `PS1` after `E`, and `PS1_RAN` is created after the snapshot. The session does degrade ("H differs", result seq 1), so I2 holds, but the code did run after the snapshot and `PS1` was not overwritten. The same happens with `PROMPT_COMMAND+=('touch PC_RAN')`: the appended element runs after nl-shell's hook in that same prompt cycle, and `PC_RAN` exists after the snapshot. Here the doc's own next clause ("degrades (`H`)") describes it honestly, but the lead sentence does not. (`readonly PS2=…` did not run, since PS2 is never shown.) Fix: reword those three places to say what really happens. A confirmed change to `PROMPT_COMMAND`, `PS0`, or a readonly/attributed `PS1`/`PS2` degrades the session at that command's snapshot, but may run once after it. Only a plain or exported `PS1`/`PS2` is overwritten. The brief's own I3 wording has the same gap, so the human may want to confirm the new wording at sign-off.; **Low (docs claim more than the code gives; R1 says this counts as a defect)**: `docs/design/specs/pty-protocol/v1.md:51-52` says nl-shell resets `PS1`/`PS2` "so no prompt string the user or a command set is ever expanded". `v1.md:153-157` and `.oss-scanner/threat_model.md:184` say "nothing confirmed code sets [in] `PS1` … runs after the snapshot" and that a change to `PS1`/`PS2` "is overwritten". The code only overwrites plain or exported `PS1`/`PS2` (`src/nl_shell/session.py:135`, which matches `declare -[-x]` only). The input is a confirmed command, which comes from the model, a text-only attacker can steer it, and the user confirms it. Example: `declare -r PS1='$(touch /tmp/X)\$ '`. It can't be overwritten: the reset at `session.py:167` fails with "PS1: readonly variable", which I checked in bash 5.3.9. So `$(touch /tmp/X)` runs when the next prompt is drawn, which is after `E`. The same holds for `PROMPT_COMMAND+=('touch /tmp/X')`: that element runs after nl-shell's hook, so after the snapshot. There is no real bypass: `H` changes in both cases, the session degrades at that command's own snapshot, and nothing more is written (`ps1-readonly` and `prompt-command-array` rows, `tests/test_session.py:525-533`). What's wrong is the wording, which the brief's R1 counts as a defect. Fix: say that a `PS1`/`PS2` with attributes, or any change to `PS0`/`PROMPT_COMMAND`, degrades the session, and that its code may still run once after that snapshot before nl-shell refuses further commands. Change the threat-model bullet to match. Test: add a `test_table_a_row_1` row, `declare -r PS1='$(touch MARK)\$ '`, and assert that it degrades with `result.seq == 1`. Whether `MARK` exists afterwards only pins the documented behaviour; it is not a security check. I didn't run this through `Session`: `ptyprocess` isn't installed in any Python I can reach here. The bash behaviour it relies on is confirmed.. Deferred, not addressed here: 7 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- By / date: auto-iterate / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 6 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

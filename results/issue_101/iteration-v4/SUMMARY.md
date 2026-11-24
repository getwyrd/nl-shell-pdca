# Result — issue 101 / persistent-bash-session-core

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: see Goal (new functionality). Re-plan reason: the v3 sign-off (`iteration-v3/SUMMARY.md` §9) found that confirmed code could (a) make a command that ran report "nothing ran", with its output hidden and no degrade (`PS1` or `readonly` setting the hook's guard variable); (b) change hook state after the snapshot so the NEXT confirmed command ran altered (a DEBUG trap rebinding CR or turning on `set -H`); (c) break the paste (`set +o emacs`, `stty intr '|'`). Separately, (d) the 1 s "back at a prompt" rule degraded ordinary `out=$(make)` commands.
- Success criterion: `python3 -m pytest tests/test_session.py` passes on the host (real bash 5.3.9, no VM, no sudo). Every test that waits on bash has a timeout of a few seconds (a hang fails the test) and closes its session in teardown. "Marker" below means a file the injected code would create; the test asserts it does NOT exist. The file covers:
  (a) `cd /tmp` then `pwd` → output `/tmp`; `export FOO=bar` then `printf %s "$FOO"` → `bar`.
  (b) Spec §Conformance vectors 1–8, 10 and 12 as tabled. `true` → `S 1`, `D 1 0 0`, snapshot, `E`. `false | true` → status 0, pipestatus `1 0`. `(exit 3)` → 3. `printf 'D 99 0 0\n'` and `printf '\x1b]133;D;0\x07'` → the control channel carries only the real records, status 0. `echo 'done!!'` → `done!!`. `alias ll2='ls -la'; g(){ :; }` → the next snapshot's `F` gains `g` and `L` contains `ll2`. `PROMPT_COMMAND=:` → degraded within 5 s with a reason. `sleep 5` then the interrupt method → `D` with status 130 arrives < 3 s after `\x03` is written, and the session is NOT degraded. A command containing `ESC [201~`, `ESC` or another C0 control except TAB/LF is refused and nothing reaches the PTY.
  (c) Vector 9 typed raw: `exec 3>&-` → degraded (control channel closed; tested with no background job).
  (d) A command with no output, a multi-line command, a here-doc and `sleep 1 &` each give exactly one S/D pair. After `sleep 3 &` the next snapshot's `J` is `0` (stopped jobs only) and the session stays usable.
  (e) Decision 5: an empty line, a comment-only line (`# x`) and a syntax error (`fi`) each report not-run, carry the `D` status, and leave the session healthy (the next `true` succeeds). An unclosed quote (`echo 'abc`) degrades within 5 s by the prompt rule (decision 7).
  (f) Snapshot fields `T`, `B`, `X`, `P`, `J`, `H`, `V` are present. `export LD_PRELOAD=/x.so` makes `V` differ from the baseline and is reported as changed. `PS0=` followed by `true` → the session is DEGRADED and the `true` result is NOT reported as not-run with a healthy session.
  (g) **I2 reproducers** (each from v1–v3 reviews). Each of these, followed by `true` and then `touch MARK; echo printed; (exit 7)`, ends with the session DEGRADED, or with the third command reported as ran, with its output and status 7. It never ends with "ran False" and a healthy session: `PS1='${__nls_x[__nls_state=1]-}\$ '` for EVERY hook state variable, `readonly` on EVERY hook state variable, and `trap '<assign each hook state variable>' DEBUG`. So the test does not depend on Do's naming choices, the session module MUST expose the full list of shell variables its hooks read or write as a module-level tuple `HOOK_STATE_VARS`, and the test MUST also check that list against the rcfile text: every shell variable the generated rcfile's hooks use is named with the prefix `__nls_`, and every `__nls_` name found in the rcfile text appears in `HOOK_STATE_VARS`. Then each attack is run once per listed variable.
  (h) **Table A "detect" rows.** Each of these, run as a confirmed command, makes the session degrade at THAT command's snapshot, and a following `run("echo hello")` raises without writing to the PTY, so no marker is created: assigning `PROMPT_COMMAND`; `PROMPT_COMMAND+=(':')`; `PS0='x'`; `trap ':' DEBUG`; `trap ':' RETURN`; `set -o functrace`; `shopt -s extdebug`; `set -H`; `set -o vi` (when the baseline is emacs); `set +o emacs`; `bind '"\r": " ; touch MARK\n"'`; `bind -x '"\C-m": "touch MARK"'`; `bind '"\e[2": "touch MARK\n"'` (a prefix of the paste-start sequence); `bind 'set enable-bracketed-paste off'`; `bind 'set convert-meta on'`; redefining one of nl-shell's hook functions; `exec >/dev/null`; `exec 2>/dev/null`; `exec </dev/null` (the last three by the outside fd check, Table B).
  (i) **I3 reproducers.** A user `PROMPT_COMMAND` (installed from the test HOME's `~/.bashrc`) that runs `bind '"\r": " ; touch MARK\n"'` on its second run, and a `PS1` whose expansion would run the same `bind`. In both cases the session degrades before any later paste is written, and no marker exists.
  (j) **Table B (outside checks).** `stty intr '|'` → degraded, and a following `run("true || touch MARK")` raises without writing; no marker. `stty -isig` → degraded before the next paste. (`stty icanon`/`-echo` are not tested: readline resets both each time it reads a line, so they cannot persist to the next paste.) The session constructor takes a keyword `tiocsti_path: str = "/proc/sys/dev/tty/legacy_tiocsti"` (read-only use: the file is only read at startup; a missing or unreadable file, or any content other than `0`, degrades). With `tiocsti_path` pointed (by the test) at a temp file containing `1`, and separately at a path that doesn't exist, the session starts degraded with a reason naming it. `kill -STOP $$` (sent from a background subshell) → degraded within 5 s, not a hang.
  (k) **Prompt rule (decision 7).** `x=$(sleep 2); echo hi`, `cd "$(sleep 1.5; echo /tmp)"` and ``y=`sleep 1.5` `` each finish with a normal result and a HEALTHY session. `read x` with no input degrades within 5 s (the accepted limit, #136).
  (l) Decision 4: a literal separator byte and a newline in `PATH`, an alias and a trap each round-trip exactly (decoded snapshot value == `printf %s` of the live value). `hash -p <script> tr`, `hash -p <script> cksum`, `hash -p <script> wc`, `BASH_CMDS[tr]=<script>` and a `PATH` with fake `tr`/`cksum`/`wc` first all leave the snapshot honest (the fake script is never run: no marker).
  (m) A `~/.bashrc` in the test HOME that sets an alias and its own `PROMPT_COMMAND` → the alias is in the baseline `L`, and the user's `PROMPT_COMMAND` still runs, BEFORE nl-shell's snapshot (decision 6). A `~/.bashrc` with `bind 'set enable-bracketed-paste off'` and `set -o vi` → the session either works (a two-line command arrives byte-for-byte with one S/D pair) or starts degraded with a reason. It never runs mangled bytes.
  (n) `HISTFILE` is unset in the session. `[ -p /dev/fd/3 ]` is true. Every record read ends in `\n` with no `\r`. A record containing `\r` fed to the parser is malformed (→ degraded).
  (o) Restart after degraded mode gives a healthy session with a fresh baseline.
  (p) **Output capture.** After each of `bind 'set enable-bracketed-paste off'`, `set +o emacs` and `set -o vi` run as a confirmed command (each in a fresh session), a following `echo hello` never returns `output == b""` with a healthy session. Either the change already degraded the session ((h)), or capture does not depend on the marker.
  **Docs** (same patch). Spec `pty-protocol/v1`: §1.2 (user `PROMPT_COMMAND` runs before nl-shell's snapshot; nl-shell sets `PS1`/`PS2` itself; reference rcfile in §1.3 updated to match, with no external programs and `\\n` inside `PS0`); §3 (`H`/`V` carry the encoded `declare -p` text, compared exactly; `H` covers the Table A "detect" rows; the outside checks of Table B and when they run); §4.1 (`D n+1` without `S n+1` = nothing ran); §4.2 (first trigger excepts that case; third trigger states the decision-7 rule; new triggers: outside-check mismatch, bash stopped, TIOCSTI allowed); §4.3 (a degraded session gets no further commands until restart, decision 10); §Conformance: vector 8 (`:180`) becomes "degraded at that command's snapshot (`H` changed)", the vectors 1–7 note (`:190`) says which vectors `tests/test_session.py` now checks automatically, and the "Open questions" bullet on forcing `enable-bracketed-paste on` (`:195-196`) is closed by naming decision 6 and Table A's readline row. Policy-gate `v1` §7.5: item 5 (`:199`) one-line wording fix, `V` is the encoded `declare -p` text, not a `cksum` (the rule and the variable list don't change); item 6 (`:202`) changes to match decision 10. ADR-0014 (`status: Proposed`): Decision 1 (`:45-46`) says the user `PROMPT_COMMAND` runs before nl-shell's snapshot (decision 6); Decision 2 (`:52-54`) says a degraded session takes no further commands and nl-shell offers the restart (decision 10). ADR-0013 (`status: Proposed`) `:72-74`: the same degraded-mode wording. Keep each ADR edit to those sentences. `.oss-scanner/threat_model.md`: Known gaps gains the bullets under Decision 2 and the "Known gap" rows of both tables, each naming its follow-up issue; §How to exercise it says the session tests need only bash.
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: New `src/nl_shell/session.py` (and `src/nl_shell/pty_protocol.py` for record parsing, if separated); `ptyprocess` in `pyproject.toml` `dependencies`; the spec, policy-gate, ADR and threat-model edits listed under Docs above (both specs are `status: draft` and ADR-0013/ADR-0014 are `status: Proposed`, so the frozen-records CI check, fb71bd1, allows the edits; edit no other ADR); `tests/test_session.py`.
  **Settled decisions** (1–5 from the parent re-plan, `results/issue_10/brief.md:27-57`; 6–9 human, 2026-10-15, this re-plan):
  (1) A command writing to fd 3 is out of scope (ADR-0014 Decision 1, Known gap; follow-up #135). No defence.
  (2) Known gaps, to be written as bullets, and code comments must not claim more than these: deliberate subversion from inside bash by a loadable builtin (`enable -f`) or a function named `builtin`/`command`/`local`/`return` (gate class `session-altering`; ADR-0024 rejects shipping our own); a `~/.bashrc`/`~/.inputrc` edited by a program and picked up at restart (#134); `ptrace_scope = 0` (#137); builtin-only commands over 1 s degrade (#136); the outside checks are Linux-only (#138).
  (3) `H`/`V` carry raw `declare -p` (or builtin-output) text, encoded and compared exactly. No checksums.
  (4) The hooks call no external program, only bash builtins and parameter expansion. Every free-text field uses ONE reversible encoding (escape the escape character first).
  (5) `D n+1` without `S n+1` = nothing ran; the session stays healthy. I2 must still hold.
  (6) The user's `PROMPT_COMMAND` runs BEFORE nl-shell's snapshot, not after. nl-shell sets `PS1` and `PS2` to its own fixed values after the snapshot, so no user prompt string expands at prompt time. bash's prompt is never shown to the user, because nl-shell's REPL draws its own.
  (7) **Prompt rule (replaces the v3 `tcgetpgrp` rule):** from the moment the paste is sent, if no `D` for this command has arrived and bash itself has been blocked waiting on the terminal (fd 0, read from `/proc/<bash pid>/syscall`) continuously for 1 s, degrade with the reason "no done record after the shell returned to a prompt". This covers both a lost `D` and input bash is still reading (an unclosed quote, PS2). It ignores `$(...)`, pipelines and child programs. Measured on this host: at a prompt or PS2, bash is in `pselect6` on fd 0; during `x=$(sleep 2)` it is in `read` on the substitution pipe; during `read y` it is in `read` on fd 0 (the accepted limit, #136). Do not parse the PTY stream for prompts.
  (8) **Outside checks:** immediately before every paste, and when each snapshot's `E` arrives, nl-shell reads, from outside bash, the PTY's terminal settings (`termios` via the master) and bash's fds 0/1/2 (via `/proc`). Any difference from the values recorded with the baseline degrades the session, and the paste is not written. At startup, nl-shell reads `dev.tty.legacy_tiocsti`; if it is not `0`, or cannot be read, the session starts degraded. A stopped bash process (`/proc` state `T`) degrades too.
  (10) **Degraded means "no more pastes", not "confirm then run".** Once the session is degraded, nl-shell can no longer promise that the bytes bash runs are the confirmed bytes (I1), so a confirm would promise something false. The session object therefore refuses (raises) instead of writing; the REPL (#78) tells the user why and offers the restart. This replaces "every command needs a confirm" in ADR-0014 Decision 2 (`adr/0014:52-54`), ADR-0013 (`adr/0013:72-74`), `pty-protocol/v1.md` §4.3 (`:108`) and `policy-gate/v1.md` §7.5 item 6 (`:202`); all four are edited in this patch (Docs). This follows from I1 and the threat model's Critical row; sign-off confirms it.
  (11) **This brief supersedes issue #101's text** where they differ: the user `PROMPT_COMMAND` runs before the snapshot (decision 6, not "after"), the prompt rule is decision 7 (not `os.tcgetpgrp`), the limits are 5 s / < 3 s (not 3 s / < 2 s), and degraded mode is decision 10. Check and sign-off grade against this brief, not the issue body. The publish step should say so in the PR description.
  (9) **The closed list.** Table A covers what bash keeps; Table B covers what a program the session runs can reach. "Detect" rows MUST be implemented and tested; "Known gap" rows MUST appear in the threat model. Table A:

  | Bash state | Handling |
  |---|---|
  | `PS0`, `PROMPT_COMMAND` (every array element), nl-shell's hook functions and hook state variables (value AND attributes), saved user hook | detect, in `H` |
  | `PS1`, `PS2`, `promptvars` | made harmless by decision 6 |
  | Traps `DEBUG`/`RETURN`, `extdebug`, `functrace` | detect, in `H` (`T`/`X` are still reported for the gate) |
  | Readline: on/off, emacs/vi mode, ALL readline variables (`bind -v`), ALL key bindings (functions, macros, `bind -X` shell commands) | detect, in `H`, compared to the baseline |
  | History expansion (`set -H`) | detect, in `H` |
  | Aliases, `expand_aliases`, functions, disabled builtins, `hash`/`BASH_CMDS`, `PATH` | reported in `L`/`F`/`B`/`P` for the gate (#12); not a session degrade |
  | Pager/loader variables (policy-gate §7.5) | reported in `V`, compared to the baseline |
  | Options that end or stall bash (`set -e`, `set -u`, `exit`) | caught by channel close / missing record / prompt rule; the hooks must themselves be safe under `set -u` and `set -e` |
  | Loadable builtins, functions shadowing `builtin`/`command`/`local`/`return` | Known gap (decision 2) |

  Table B (a program the session runs):

  | Path back into the session | Handling |
  |---|---|
  | Terminal settings (`stty`, any `tcsetattr`) | detect, outside check (decision 8) |
  | Injected keystrokes (`TIOCSTI`) | detect at startup (decision 8) |
  | bash's fds 0/1/2 redirected (`exec >/dev/null`) | detect, outside check (decision 8) |
  | Signals to bash (`kill -9 $$`, `kill -STOP $$`) | detect: channel close / stopped state |
  | Fake records on fd 3 | Known gap, #135 |
  | `ptrace` / `/proc/<pid>/mem` on bash | blocked by `ptrace_scope ≥ 1`; Known gap for `0`, #137 |
  | `~/.bashrc` / `~/.inputrc` edited, picked up at restart | Known gap, #134 |
  | Bytes written to the PTY that look like prompts or records | not a session input; status comes only from fd 3; screen spoofing is #120 / the output filter |
  | Changing files later commands run | the gate's job (policy-gate §7.4) |

  / **out of scope:** everything in spec §6, meaning raw mode, keystroke forwarding, mirroring to a real terminal, alternate-screen capture pause, SIGWINCH, terminal restore, typed-ahead discard and background-output buffering (#102, #120); session recovery and cwd restore (#121); REPL / `cli.py` wiring (#78), including what degraded mode looks like to the user (`src/nl_shell/repl.py` and `src/nl_shell/input_modes.py` exist on `main`; do not touch them or `cli.py`); the policy gate and its fd-3 rejection (#12); sudo passthrough (#13); history write-back (#17); taint and the state block (#11); the output rendering filter; the architecture doc 05 code-layout table; follow-ups #134–#138.

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 Verification (worktree mismatch): fail — issue_101: patch.diff did not apply onto 'origin/pdca-integration/main-r2546dbf9639f' in /home/eddie/nl-shell/nl-shell.pdca-wt-l0. Failing closed — a green over
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 Shape: none — (no gate configured)
- T3 Runtime: none — (no gate configured)
- T4 Contribution: none — (no gate configured)
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review the persistent bash session core for issue #101: exact confirmed pastes, fd-3 status and snapshots, persistent state, and sticky degradation on the brief's enumerated changes.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The closed detection tables and explicit exclusions provide falsifiable boundaries for byte integrity, truthful execution reporting, and prompt ordering; brief.md:14–35 and brief.md:41–82. |
| C2 Reproduction (red pre-fix) | NEEDS-HUMAN | Obtain the independent pre-fix test run — the absent session is consistent with a new feature, but no current red evidence was supplied and pytest is unavailable; brief.md:36, check-gates.json (C2 row). |
| C3 Change | PASS | The changed paths fit the session, tests, dependency, and normative documentation scope; stale target prevents grounding new source there, so reviewed patch.diff:1, patch.diff:390, patch.diff:402, patch.diff:721, patch.diff:1556. |
| C4 Verification (red→green) | NEEDS-HUMAN | Resolve the stale reconstruction base and supply/re-run the actual validator and scanners — the only gate row is worktree-mismatch with no log key, gate-logs/ is absent, and pytest is unavailable; no full red→green is established; check-gates.json (C4 row), brief.md:38. |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Correct the output boundary and add a stdout-emitting prompt-hook regression — five real-bash runs included post-D HOOK_OUTPUT in a healthy command result, so downstream consumers receive text the command did not print; patch.diff:866, patch.diff:868, patch.diff:1302–1312. |
| T1 Structure | PASS | Separating pure protocol sequencing from PTY lifecycle makes the trust boundary reviewable without coupling to the deferred REPL/terminal work; patch.diff:402, patch.diff:721. |
| T2 Shape | PASS | Both added production modules parse successfully; bounded records/output, explicit phases, and structured results support the intended API; patch.diff:432, patch.diff:495, patch.diff:985, patch.diff:1003. |
| T3 Runtime | NEEDS-HUMAN | Establish the complete host test outcome — real bash 5.3.9, ptyprocess 0.7.0, child /proc checks, TIOCSTI=0 and ptrace_scope=1 were exercised/observed, but smoke checks do not establish the full adversarial and timing matrix; brief.md:16–36, brief.md:82. |
| T4 Contribution | NEEDS-HUMAN | Confirm affected-path prior art against current merged history and closed/rejected work — the brief reports triage, but the stale target's path-filtered history only exposes older spec history and no independent closed-work evidence is supplied; brief.md:85. |
| T5 Judgment | PASS | The implementation addresses the specified causes through unconditional start records and snapshot/outside checks; no capability probe masking an eager-load side effect was identified, and documented exclusions bound the review; patch.diff:818–847, brief.md:41–78. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the corrected session's closed threat model and accepted limits are adequate for downstream REPL integration — full verification and the output-boundary correction remain outstanding; brief.md:14–35, brief.md:78. |

Target-state caveat: `$PDCA_TARGET` is `/home/eddie/nl-shell/nl-shell.pdca-wt-l0`, clean at `8c95e05` (`pdca-integrate: issue_14`). The brief requires `c47c5c2` and explicitly identifies `8c95e05` as stale. Read-only `git apply --check` reproduces a context failure in `docs/design/specs/pty-protocol/v1.md:40`. This is not a C4 patch-defect FAIL. No stash/pop was attempted because the target does not contain the applied patch. All affected-source citations above therefore refer to numbered lines of `patch.diff`, not presumed target lines.

Independent checks: extracted the two newly added production modules verbatim into `review-runtime/` inside this scratch root and parsed both with Python's AST parser. With a scratch HOME and TMPDIR, started real bash through the actual ptyprocess implementation. Startup was healthy; `true` returned status 0; `false | true` returned status 0 and PIPESTATUS `(1, 0)`; an exported variable persisted; `x=$(sleep 2); echo hi` returned `hi` without degradation; disabling bracketed paste degraded with an H mismatch. These are supplemental checks, not the missing gate run. `python3` cannot import pytest and the target has no `.venv/bin/python`. No validator/scanner evidence or INTEGRATION.md was supplied/found in the target file search, so project-specific human-only checks cannot be certified.

C5 reproduction: set the isolated HOME's `.bashrc` to `PROMPT_COMMAND='echo HOOK_OUTPUT'`, start `Session.start(env=env, timeout=5)`, then call `session.run('echo COMMAND_OUTPUT', timeout=5)` five times. Every result was `b'COMMAND_OUTPUT\r\nHOOK_OUTPUT\r\n'`, with `session.degraded == False`. The hook writes D before running the user's prompt command (patch.diff:866–870), but `_wait_for_result` consumes ready PTY bytes and drains the PTY when D is observed (patch.diff:1302–1312). Thus post-D output is attributed to the confirmed command. Require a regression asserting only `COMMAND_OUTPUT\r\n`, including a prompt hook that emits enough output to expose scheduling differences. This is an output-boundary defect, not a forged-status claim.

Prior-art investigation: read target AGENTS.md and CONTRIBUTING.md, and queried target git history by `src/nl_shell/session.py`, `tests/test_session.py`, and `docs/design/specs/pty-protocol/v1.md`; the visible result was `31e8314` (original safety/spec decisions). The brief's claims about current main and closed-unmerged work cannot be independently confirmed from this stale checkout and artifact bundle. No other checkout was consulted.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 101 / persistent-bash-session-core

All line numbers point at `c47c5c2` (current `main`) with `patch.diff` applied. I rebuilt
that tree in the sandbox from `git archive c47c5c2`. The patch applies cleanly there.

## Evidence (red→green)

- C4's red is a driver fault, not a broken fix. `check-gates.json` C4 reports
  `worktree-mismatch`: the patch "did not apply onto
  'origin/pdca-integration/main-r2546dbf9639f'". The target worktree is still on `8c95e05`,
  the stale `stack-base` that brief.md:37 says must be cleared before Do. On `c47c5c2` I
  re-ran the gate myself. With the patch, `tests/test_session.py` gives 99 passed in 52 s
  (bash 5.3.9, ptyprocess 0.7.0). With every production hunk reverted (main's `src/`, the
  patch's tests), it gives 99 failed in 1.2 s, each test failing on its own (the imports
  sit inside the tests). The tests import the real `nl_shell.session`, not a copy.
- NEEDS-HUMAN [human] — The gating C4 row stays red until someone clears or re-resolves the
  bundle's `stack-base` to `main` (`c47c5c2`) and re-runs Check. My run above is
  provisional evidence, not the gate.

## The fix: inputs that break it

- NEEDS-HUMAN [human] — **A confirmed command can make bash run extra code during every
  later command, with the session left healthy and nothing reported** (I1, I3). Concrete
  case: `exec 9>/dev/null; BASH_XTRACEFD=9; PS4='$(echo x >> MARK)'; set -x`, then
  `echo hi`. Measured: `echo hi` returns `hi\n`, `ran True`, `degraded False`, and the
  PS4 payload ran 9 more times during that one command. H (`src/nl_shell/session.py:164-190`)
  leaves out `xtrace`, `PS4` and `BASH_XTRACEFD`. The hooks save xtrace in `__nls_x`
  (`session.py:143`) and turn it back on after the snapshot (`session.py:196`), but H only
  records the variable's attributes, not its value (`session.py:169-170`). V
  (`session.py:85-88`) and T/X don't cover these either, so the gate (#12) can't see it.
  This acts like a DEBUG trap, which Table A marks "detect". Table A has no row for
  xtrace/PS4, so this is a missing *category*, which brief.md:8 counts as a real finding.
  The test `tests/test_session.py:675-688` passes only because its PS4 payload also
  rebinds CR, which H does catch. A payload that changes nothing H covers gets through.
  The fix is small (add `xtrace`, `declare -p PS4 BASH_XTRACEFD` to H, plus a test whose
  PS4 payload only touches a marker), but it adds a row to the closed list, so a human
  should approve the scope.
- NEEDS-HUMAN [impl] — **Output from the user's `PROMPT_COMMAND` gets counted as the
  command's output.** Concrete case: `~/.bashrc` with `PROMPT_COMMAND='printf USERHOOK'`,
  then `run("true")` 40 times: 25 of 40 results had `USERHOOK` in `output`. The same
  thing happens with no setup at all on this host: `/etc/bash.bashrc` loads the vte hook,
  and `\x1b]666;vte.shell.postexec=0\x1b\\` showed up in 5 of 30 `echo HELLO` results.
  Cause: `__nls_done` writes `D` and then runs the user hook (`session.py:147-150`). The
  wait loop reads the PTY before it handles the control record from the same select round
  (`session.py:575-585`), so text printed after `D` gets added to the command's output
  whenever both are ready together. That breaks the brief's "PTY output between `S` and
  `D`" (brief.md:14). Decision 6 is what made the user hook print between `D` and `E`, so
  the output should be cut at a point bash marks (for example, an fd-3 record or ack
  written before the user hook runs), not by read order. No test checks command output
  when a user hook prints; (m) only checks that the hook runs.

## Tried and could not refute

- I2 attacks: `readonly` / `declare -n` / `declare -i` on hook variables show up in H
  through the attribute lines (`session.py:169-173`). Changing `__nls_seq`'s value is
  overwritten in `__nls_done` before PS0 reads it (`session.py:145`). A bad value causes
  a sequence error, which fails closed.
- `enable -n printf` / `read` / `declare`: the hooks break, then the prompt rule, the
  check-point wait (`session.py:679-683`) or a changed H degrades the session. It fails
  closed.
- A background loop flipping `stty iuclc` on and off (with SIGTTOU ignored) to race the
  check that runs just before the paste: 30 runs of `echo HELLO` all returned `HELLO`.
  No changed bytes ran.
- `trap … ERR` / `CHLD` also run code during later commands, but Table A lists only
  DEBUG/RETURN traps for H, and T reports these traps to the gate. They are inside the
  brief's design, so I don't count them as findings against this diff.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Advisory review — security-review — NOT COMPLETED

<!-- pdca:leaf-status human-empty -->

Failure class: **substantive — needs a human.** The leaf ran but did not yield a usable verdict; do not assume an infra blip.

- NEEDS-HUMAN — advisory leaf 'security-review' did not produce findings (produced no artifact); re-run it or adjudicate by hand.

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C2 Reproduction (red pre-fix) — Obtain the independent pre-fix test run — the absent session is consistent with a new feature, but no current red evidence was supplied and pytest is unavailable; brief.md:36, check-gates.json (C2 row).
- [ ] C4 Verification (red→green) — Resolve the stale reconstruction base and supply/re-run the actual validator and scanners — the only gate row is worktree-mismatch with no log key, gate-logs/ is absent, and pytest is unavailable; no full red→green is established; check-gates.json (C4 row), brief.md:38.
- [ ] C5 Causal adequacy — Correct the output boundary and add a stdout-emitting prompt-hook regression — five real-bash runs included post-D HOOK_OUTPUT in a healthy command result, so downstream consumers receive text the command did not print; patch.diff:866, patch.diff:868, patch.diff:1302–1312.
- [ ] T3 Runtime — Establish the complete host test outcome — real bash 5.3.9, ptyprocess 0.7.0, child /proc checks, TIOCSTI=0 and ptrace_scope=1 were exercised/observed, but smoke checks do not establish the full adversarial and timing matrix; brief.md:16–36, brief.md:82.
- [ ] T4 Contribution — Confirm affected-path prior art against current merged history and closed/rejected work — the brief reports triage, but the stale target's path-filtered history only exposes older spec history and no independent closed-work evidence is supplied; brief.md:85.
- [ ] Validation — fitness-to-purpose — Decide whether the corrected session's closed threat model and accepted limits are adequate for downstream REPL integration — full verification and the output-boundary correction remain outstanding; brief.md:14–35, brief.md:78.
- [ ] The gating C4 row stays red until someone clears or re-resolves the bundle's `stack-base` to `main` (`c47c5c2`) and re-runs Check. My run above is provisional evidence, not the gate.
- [ ] **A confirmed command can make bash run extra code during every later command, with the session left healthy and nothing reported** (I1, I3). Concrete case: `exec 9>/dev/null; BASH_XTRACEFD=9; PS4='$(echo x >> MARK)'; set -x`, then `echo hi`. Measured: `echo hi` returns `hi\n`, `ran True`, `degraded False`, and the PS4 payload ran 9 more times during that one command. H (`src/nl_shell/session.py:164-190`) leaves out `xtrace`, `PS4` and `BASH_XTRACEFD`. The hooks save xtrace in `__nls_x` (`session.py:143`) and turn it back on after the snapshot (`session.py:196`), but H only records the variable's attributes, not its value (`session.py:169-170`). V (`session.py:85-88`) and T/X don't cover these either, so the gate (#12) can't see it. This acts like a DEBUG trap, which Table A marks "detect". Table A has no row for xtrace/PS4, so this is a missing *category*, which brief.md:8 counts as a real finding. The test `tests/test_session.py:675-688` passes only because its PS4 payload also rebinds CR, which H does catch. A payload that changes nothing H covers gets through. The fix is small (add `xtrace`, `declare -p PS4 BASH_XTRACEFD` to H, plus a test whose PS4 payload only touches a marker), but it adds a row to the closed list, so a human should approve the scope.
- [ ] **Output from the user's `PROMPT_COMMAND` gets counted as the command's output.** Concrete case: `~/.bashrc` with `PROMPT_COMMAND='printf USERHOOK'`, then `run("true")` 40 times: 25 of 40 results had `USERHOOK` in `output`. The same thing happens with no setup at all on this host: `/etc/bash.bashrc` loads the vte hook, and `\x1b]666;vte.shell.postexec=0\x1b\\` showed up in 5 of 30 `echo HELLO` results. Cause: `__nls_done` writes `D` and then runs the user hook (`session.py:147-150`). The wait loop reads the PTY before it handles the control record from the same select round (`session.py:575-585`), so text printed after `D` gets added to the command's output whenever both are ready together. That breaks the brief's "PTY output between `S` and `D`" (brief.md:14). Decision 6 is what made the user hook print between `D` and `E`, so the output should be cut at a point bash marks (for example, an fd-3 record or ack written before the user hook runs), not by read order. No test checks command output when a user hook prints; (m) only checks that the hook runs.
- [ ] leaf produced no usable verdict (needs a human) — advisory leaf 'security-review' did not produce findings (produced no artifact); re-run it or adjudicate by hand.
- [ ] C4 Verification (worktree mismatch) FAILED (gating) — issue_101: patch.diff did not apply onto 'origin/pdca-integration/main-r2546dbf9639f' in /home/eddie/nl-shell/nl-shell.pdca-wt-l0. Failing closed — a green over
- [ ] **The target base does not match the brief.** The Ordering note says "`main` moved since v3 (now `c47c5c2`: #131/#132/#133 edited `pty-protocol/v1.md` §4.4–§4.5, §6.6 and Conformance 13–16, and the threat model). Build on current `main`". The resolved target is HEAD `8c95e05`, and its spec has none of those edits. `docs/design/specs/pty-protocol/v1.md` §4 stops at item 3 (`:98-109`), §6 stops at item 5 (`:120-133`), and the Conformance table stops at vector 12 (`:152-163`). The policy-gate citations also point to the wrong lines on this tree. The brief puts §3 session-altering at `:98-107`, but it is at `policy-gate/v1.md:92-101`. It puts the §7.5 `V` list at `:197-201`, but it is at `:191-195`; `:196-198` are items 6–7. Either the target was resolved to a stale commit, or the brief describes a `main` that doesn't exist. In both cases the docs edits and the "cite path:line on `main`" rule will drift during Do. Re-resolve the target to `c47c5c2`, or correct the brief, before Do starts.
- [ ] **Decision 6 contradicts an ADR, and the brief forbids editing ADRs.** Scope says "do NOT edit any ADR". `docs/design/adr/0014-pty-session-protocol.md:45-46` says a user `PROMPT_COMMAND` "is kept and run after nl-shell's hook". Decision 6 and test (m) require it to run BEFORE the snapshot. ADR-0014 is the normative source the brief tells Do to cite ("Decisions 1–3"). After this patch the spec and its decision record would disagree, and a Check reviewer could fairly fault either side. The brief should either allow a one-line ADR-0014 amendment or a superseding note, or name the follow-up that will make one.
- [ ] **What degraded mode means also conflicts with ADR-0014 and the issue.** The brief says "while degraded the session object sends NOTHING more to the PTY (it raises)", and the planned §4.3 edit says "a degraded session gets no further commands until restart". `adr/0014:53-54` says: "every command needs a confirm, and nl-shell offers to restart the session". `adr/0013-policy-gate-v2.md:73` says the same ("everything needs a confirm until the session is ..."), and so does `policy-gate/v1.md:196`. The issue body (notes.json) asks only for "degraded mode ... (sticky until restart)". This is a behavior change to two decision records and the gate spec, made without editing any of them. The brief's §4.3 edit leaves `policy-gate/v1.md:196` and both ADRs saying "confirm and run".
- [ ] **The issue thread now contradicts the brief, and the brief doesn't say which one wins.** `notes.json` still asks for the user's `PROMPT_COMMAND` to run "after nl-shell's hook" (its (h)) and specifies the `os.tcgetpgrp` back-at-a-prompt rule with "degraded within 3 s" and Ctrl-C "< 2 s". The brief reverses the first (decision 6), replaces the second (decision 7, `/proc/<pid>/syscall`), and loosens the timings to 5 s and < 3 s. The decisions are recorded as human, 2026-10-15, but the tracker record was never updated. A Check or sign-off reviewer who grades against issue #101 will find "regressions" that are actually agreed decisions. Update the issue body, or have the brief say explicitly that it supersedes the issue's criterion.
- [ ] **Scope is several mechanisms, not one change.** Besides the session object and record parser, the brief adds:
- [ ] **Some sub-criteria are defined by the implementation, so Do can make them pass by construction.**
- [ ] **A Conformance vector would be left stale.** `pty-protocol/v1.md:159` says vector 8 (`PROMPT_COMMAND=:`) is "degraded mode at the next prompt (missing `D`)". Under the new design it degrades through `H` at that command's own snapshot (test (h)). The Docs list edits §1.2, §3 and §4.1–§4.3 but not the Conformance table. The vectors 1–7 note at `:165-166` and the "Open questions" bullet at `:170-171` (forcing `enable-bracketed-paste on`) also need resolving, because (h) and (m) now answer that question.
- [ ] **The brief's evidence can't be checked from here.** The brief relies on `iteration-v3/SUMMARY.md` §6/§9, `deferred-findings.json`, `results/issue_10/brief.md:27-57` and follow-ups #134–#138 as "filed". None of these are in the inputs. Every reproducer in (g)–(k) is justified as "reproduced live against the v3 patch". The human should confirm at sign-off that the follow-up issues exist, because the threat-model Known-gap bullets must name them.
- [ ] size backstop — this slice is behaving oversized: patch is 110 KB (threshold 100 KB). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.
- [ ] T5 Judgment — Confirm affected-path prior art across merged history and closed/rejected work: the brief reports a broad src/dependency search, but this one-commit target has no remote/history evidence to verify all affected documentation/test paths or rejected attempts (`brief.md:14`).
- [ ] `src/nl_shell/session.py:381`: after `set +o emacs` (readline off), bash no longer treats the bracketed-paste markers as markers, so they become part of the command text. Live: `set +o emacs` then `echo hello` → `status 127, output ''`, session not degraded. Bash ran `\e[200~echo hello\e[201~`, not the confirmed bytes, and that breaks the brief's "sends exactly the confirmed bytes" (§5). For a multi-line paste, the second and later lines run as typed while the first line is mangled. Nothing in `H`/`X` watches the line-editing state. Deciding whether this is a §4.2 trigger (add `set -o` / `bind -v` state to `H`) or a Known gap is a spec/scope call.
- [ ] **Critical (the command that runs differs from the one the user confirmed), but only after an earlier confirmed termios change** — `src/nl_shell/pty_protocol.py:148-153`, `src/nl_shell/session.py:381`. The §5 guard only refuses ESC, C0 controls and `ESC [201~`. It assumes the PTY's termios special characters (termios: the terminal's line settings; e.g. the interrupt key) are still their C0 defaults. Readline leaves ISIG (the terminal turning keys into signals) on. So once the session has run `stty intr '|'` (typed, from a cloned repo's `~/.bashrc` or env script that the user confirmed `source`-ing, or a confirmed proposal), every `|` in a later confirmed command reaches the line discipline as SIGINT, not as text. Readline drops the line typed so far, and whatever follows the last `|` runs. Reproducer: `run("stty intr '|'")`, then `run("true || touch never_confirmed_to_run")`. The confirmed command can never create a file. In the probe it created `never_confirmed_to_run~` (the trailing `~` is the leftover from `ESC [201~` once the paste was cut). It was reported `ran=True, status=0`, and the session stayed healthy. Nothing in the snapshot (§3) records termios, so neither H nor V changes. The same flaw makes `interrupt()` (`session.py:359`) silently do nothing after `stty intr` moves away from `^C`. Fix options: before each write, read the line settings with `os.tcgetattr` on the master and refuse (or degrade) if any active VINTR/VQUIT/VSUSP character (or VLNEXT/VDISCARD under IEXTEN, the extended-input flag) appears in the command; or record those settings in the baseline and degrade when they change. Either one widens spec §5.2 or §3 beyond what the brief settled, so a human should pick which. Add the reproducer above as a test.
- [ ] **The tracker record was not provided, so the problem statement can't be checked against the thread.** The cwd has only `brief.md`. There is no `notes.json`, no `sources/` and no `dependency-state.json`. Three things in the brief therefore can't be verified here: the human decisions dated 2026-10-15 in Scope ("Settled decisions (parent brief, human 2026-10-15)"), the ordering claim "#65 is closed", and the rejected approaches it attributes to `results/issue_10/iteration-v3`. The citation offered for #65 being closed is `v1.md:7`, but that line (`docs/design/specs/pty-protocol/v1.md:7`) only reads `tracking-issue: "#65"`. It says nothing about the issue's state. Before sign-off, check that the bundle really carries the thread.
- [ ] **Changing `H`/`V` to raw `declare -p` text leaves the policy-gate spec contradicting it.** The brief rewrites pty-protocol §3 so that `H`/`V` "carry the encoded `declare -p` text" and are compared exactly, with no checksums (decision 3). But `docs/design/specs/policy-gate/v1.md:192-194` still defines §7.5 as "`V`, a `cksum` of `PAGER`, `MANPAGER`, …". The brief also names policy-gate §7.5 as a normative source for the `V` list. The Scope doesn't list policy-gate/v1 as an edit, and that spec's Versioning (`policy-gate/v1.md:207`) says "changing §7 requires v2". So the plan as written either leaves two draft specs that disagree about the `V` format, or it needs a policy-gate edit that is out of scope and possibly needs v2. One of these has to happen: add a one-line §7.5 wording fix to the scope, after confirming it is wording only and not a v2 change, or record the inconsistency as accepted.
- [ ] **Decision 5 edits spec §4.1, but §4.2 keeps a rule that contradicts it.** The brief changes §4.1 so that "`D n+1` without `S n+1` means nothing ran" and the session stays healthy. `pty-protocol/v1.md:104` (§4.2, first trigger) still says nl-shell MUST degrade when "a record is missing". `S` is a record, so after the edit the spec would require both outcomes. Criterion (e) tests the healthy behaviour, which makes the conflict concrete. The Scope only says "§3 and §4.1 wording". Add §4.2's first trigger to the doc edits, carving out the not-run case explicitly.
- [ ] **Decision 5 weakens tamper detection for `PS0`, and nothing tests it.** With "D without S = healthy", a session where `PS0` has been blanked no longer fails through sequencing. Every later command looks like "nothing ran" while it actually runs. Only the `H` comparison catches this. Criterion (f) covers "changing `PS0` → `H` differs → degraded" for a single command, but no criterion says the result is a degraded session rather than a not-run result. Add a test: `PS0=` followed by `true` must degrade, not report not-run. Without it, a regression in the `H` check would let every command be reported as not-run without anyone noticing.
- [ ] **Scope is more than the implementation.** "Session core" brings three normative-doc changes with it: pty-protocol §3, §4.1 and the §1.3 reference rcfile rewrite, plus two threat-model sections. It also brings the back-at-a-prompt rule, which is a new behavioural rule (the §4.2 third trigger) that the brief defines itself, not the spec. That includes its accepted fail-closed limit that `read x` and `wait` degrade. These are settled decisions, not hidden changes, but the brief does not have the spec record the new rule. §4.2 still just says "no `D` arrives after the shell is back at a prompt". Either the 1 s `tcgetpgrp` rule goes into the spec, or the spec and the code will disagree about when degraded mode triggers.
- [ ] **Wall-clock thresholds in the success criterion may be flaky on the gate host.** The criterion asserts "degraded within 3 s" (vector 8) and "`D` with status 130 arrives < 2 s after `\x03`". The back-at-a-prompt rule itself needs 1 s of continuous foreground ownership. On a loaded CI or gate host, a 1 s rule inside a 3 s limit leaves little margin. A spurious red would look like a real regression. Consider widening the limits or stating the host assumption.
- [ ] **Minor: the prior-art line undercounts what's on `main`.** It lists "scaffold, router, isolation only", but `src/nl_shell/repl.py` exists (`repl.py:4` says "the PTY session … Nothing runs yet"). The claim that there is no session code still holds, so this doesn't change the plan. It does mean Do will see a REPL module that the brief's Scope excludes from wiring (#78), and Do needs to know not to touch it.
- [ ] C5 Causal adequacy — Decide whether failing closed on absent Readline framing is the acceptable causal remedy, or whether capture should remove its dependency on that capability; the new runtime guard protects a path that expects bracketed paste, triggering the required symptom-guard review; no eager/load-time cause was established (target/src/nl_shell/session.py:139; target/src/nl_shell/session.py:436).
- [ ] T5 Judgment — Confirm that the policy-gate V wording remains a v1 clarification, and substantiate merged plus closed/rejected prior art for all affected paths; the brief reports a src/ and pyproject search, but this flattened target has only one base commit and no closed-work evidence (brief.md:14; brief.md:17; target/docs/design/specs/policy-gate/v1.md:203).
- [ ] `src/nl_shell/session.py:464-473` (the back-at-a-prompt rule) degrades healthy, common commands that use **command substitution** (`$(...)` or backticks). A `$(...)` child does not get its own process group, so `os.tcgetpgrp` keeps returning bash's pid while the external program runs. Each of these degraded after 1.01 s, live: `echo $(sleep 2)` · ``x=`sleep 1.5`; echo hi`` · `x=$(sleep 1.5 | cat)` · `cd "$(sleep 1.2; echo /tmp)"` · `for i in 1 2 3; do x=$(sleep 0.6); done` (no single substitution passes 1 s, but bash holds the foreground the whole time). The same commands without substitution pass: `( sleep 1.5 )`, `f(){ sleep 1.5; }; f`, `sleep 1.5 | cat` and `cat <(sleep 1.5)` all returned healthy at 1.51 s. So `out=$(make)`, `v=$(curl …)` or `cd "$(slow-tool)"` will knock the session into degraded mode, and the only way out is `restart()`, whose `close(force=True)` (`session.py:287`) sends SIGHUP and kills the command that is still running. The brief, the spec (`docs/design/specs/pty-protocol/v1.md:168-171`) and the threat model's Known-gaps bullet (`.oss-scanner/threat_model.md:174-177`) accept this limit only for commands that "run inside bash itself" (`read x`, `wait`, builtin-only loops). Command substitution of an external program is a much bigger class, and none of the three documents name it. No test covers it. A human has to decide whether this limit is acceptable for v1. If it is, the docs must name command substitution. If not, the rule needs another signal, for example "bash has no live child processes", which is not simple: background jobs are also children, so a lost `D` with a job running would then hang. That is a design choice, not a builder's tweak.

## 7. Proven / not proven
- Proven by which oracle: gates overall = fail (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: iterated-to-Do
- Iteration delta (if iterating): Rejected at sign-off (v3 of this slice). Keep it as one slice; fix these on current main (c47c5c2), not the stale stack-base 8c95e05: 1. xtrace/PS4 hole: a confirmed `exec 9>/dev/null; BASH_XTRACEFD=9; PS4='$(echo x >> MARK)'; set -x` makes the PS4 payload run during every later command while the session stays healthy. Add `xtrace`, `PS4` and `BASH_XTRACEFD` (value, not just attributes) to H as a new Table A "detect" row (approved at sign-off), with a test whose PS4 payload ONLY touches a marker (no CR rebind). 2. Output boundary: output printed by the user's PROMPT_COMMAND (or /etc/bash.bashrc's vte hook) after D leaks into the command's output (25 of 40 runs). Cut output at a point bash marks (e.g. an fd-3 record written before the user hook runs), not by PTY read order. Add a regression test where a user hook prints, asserting output is exactly the command's own. 3. C4 must run on main; the security-review advisory produced nothing last round and must produce a verdict.
- By / date: Eduard Ralph / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 8 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

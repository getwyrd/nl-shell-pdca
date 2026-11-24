<!-- pdca:split-proposal v1 -->
# Split proposal — issue 101

<!-- Each child is a COMPLETE brief, not a sketch. A filled Slug alone makes `state.state`
     classify the materialised file as PLANNED, so `pdca flow` skips Plan and sends it
     straight to Do — a child missing `Repo + branch target` then builds successfully and
     has nowhere to publish. Fill every field. -->

<!-- Delimiters are HTML comments, not headings, DELIBERATELY: each child body is a full
     draft brief and may contain arbitrary headings and fenced code blocks, so anything
     that could also appear inside a child cannot be its boundary. `pdca split --accept`
     parses these markers; keep them exactly as written. -->

## Why this slice is oversized

This is not inherited size. #101 is already a split child of #10, but the oversize here
comes from this brief's own scope: the v5 build of exactly this brief produced a 118 KB
patch (over the 100 KB backstop) and was rejected at sign-off for that reason. The human
then wrote a two-child split plan into the brief itself ("Split plan (human,
2026-10-15)"). This proposal follows that plan, with one small change (below).

The brief holds two outcomes that can each ship and be judged on their own:

1. **A working session** — bash on a PTY (pseudo-terminal) with the fd-3 record channel,
   the record parser, sequencing, the paste filter, interrupt, restart, the 1 s prompt
   rule, the output boundary, "degraded means refuse", the user hook running before the
   snapshot, the I2 guarantee ("a command that ran is never reported as not-run"), the
   reversible encoding, and the first Table A row (nl-shell's own hooks) in `H`. This is
   usable and testable without any of the tamper checks.
2. **Tamper checks** — every other Table A "detect" row in `H` (traps, readline state,
   `set -H`, xtrace, disabled builtins) and all of Table B (outside checks on terminal
   settings and fds 0/1/2, the TIOCSTI startup check, a stopped bash). This is the I1
   hardening that three review rounds kept finding holes in. It has its own success
   letters, (h) (i) (j) (p) (r) (s), and adds no new session behaviour beyond "degrade on
   this new trigger".

The seam is "the session runs commands correctly" vs. "the session notices when a
command changed it so a later paste would run differently". Splitting further (e.g.
readline checks apart from outside checks) would cost a third full cycle on the same
two files for no gain in reviewability, so two it is.

**One change from the human's plan:** the second half of criterion (m) — a `~/.bashrc`
with `bind 'set enable-bracketed-paste off'` and `set -o vi` must either work or start
degraded — moves from child A to child B. It is a check on readline state, which is
child B's Table A row. Left in A, it would force A to build a piece of the readline
check early, which is the scope this split is meant to separate. The first half of (m)
(alias in baseline `L`, user `PROMPT_COMMAND` runs before the snapshot) stays in A.

## Wave sketch

- **Wave 1: child-1 (session core) alone.**
- **Wave 2: child-2 (tamper checks)**, `Depends on: child-1`.

child-2 cannot run in parallel with child-1. It adds rows to the `H` snapshot that
child-1's rcfile generates, adds checks into child-1's paste path in
`src/nl_shell/session.py`, adds tests to child-1's `tests/test_session.py`, and edits the
same spec §3/§4.2 and threat-model Known-gaps bullet that child-1 writes. It needs
child-1's accepted result as its base, so `Depends on` is the right field (it already
keeps them out of one wave; a `Conflicts with` would add nothing).

Outside this proposal: sibling #102 (terminal ownership) edits the same prompt hook in
`session.py` and should depend on child-2 once it has a tracker id (human agreed
2026-10-15; #102's own `Depends on:` is updated separately). #120/#121 depend on this
work as a whole, so they should depend on child-2 as well.

<!-- pdca:child child-1 -->
- **Slug:** persistent-bash-session-core
- **Kind:** enhancement
- **Defect / goal:** nl-shell has no shell session. Add a session object (`src/nl_shell/session.py`, record parsing optionally in `src/nl_shell/pty_protocol.py`) that starts one long-lived interactive bash (≥ 5.1) on a PTY via `ptyprocess` (ADR-0021 §2), with nl-shell's control channel on fd 3 and a generated rcfile (spec `pty-protocol/v1` §1). It parses the `S`, `D`, `F`, `L`, `T`, `B`, `X`, `P`, `J`, `H`, `V`, `E` records (§2–§3) and ignores unknown types. It records the first snapshot as the baseline, checks sequencing, and on every degrade trigger enters degraded mode with a human-readable reason. Degraded mode is sticky until restart; while degraded the session sends NOTHING more to the PTY (it raises; the REPL, #78, offers the restart). It sends exactly the confirmed bytes as one bracketed paste plus `CR`, and refuses, without writing, a command containing `ESC`, any other C0 control except TAB/LF, or `ESC [201~` (§5). Interrupt writes `\x03`; restart starts a fresh session with a fresh baseline. A result carries the sequence number, `$?`, `PIPESTATUS`, the PTY output between `S` and `D` (bounded, with a truncated flag) and the snapshot. Status and completion come only from fd-3 records, never from printed text. `cd` and `export` persist. No terminal ownership (#102).
  **Invariants this child holds:** (I2) a command that ran is never reported as "nothing ran" while the session stays healthy — whether `S` is emitted must not depend on any state confirmed code can assign (variable, readonly flag, trap) unless `H` covers it and the session degrades at that command's own snapshot. (I3) nothing confirmed code can install runs between the snapshot and the next paste except nl-shell's own hook: the user's `PROMPT_COMMAND` runs BEFORE the snapshot and nl-shell sets fixed `PS1`/`PS2` after it. I1 against tampering is NOT yet complete in this child (child-2); the threat model says so (Docs).
  **Settled decisions (from the parent brief, `results/issue_101/brief.md`):** (1) writes to fd 3 by a command are out of scope (#135). (3) `H`/`V` carry raw `declare -p` / builtin-output text, encoded and compared exactly, no checksums. (4) hooks call no external program, only builtins and parameter expansion; every free-text field uses ONE reversible encoding (escape the escape character first). (5) `D n+1` without `S n+1` = nothing ran, session stays healthy. (6) user `PROMPT_COMMAND` before the snapshot; fixed `PS1`/`PS2` after. (7) prompt rule: from the paste, if no `D` has arrived and bash has been blocked reading fd 0 (from `/proc/<bash pid>/syscall`) for 1 s continuously, degrade with "no done record after the shell returned to a prompt"; do not parse the PTY stream for prompts. (10) degraded = refuse, not "confirm then run". (11) this brief supersedes the #101 issue text where they differ (hook order, prompt rule, 5 s / < 3 s limits, decision 10); the PR description should say so. (13, part) the output boundary is cut at a point bash marks before the user hook runs (reuse `iteration-v5/patch.diff` `_Output`). `H` in this child covers Table A row 1 only: `PS0`, every `PROMPT_COMMAND` element, nl-shell's hook functions, hook state variables (value AND attributes), the saved user hook. `V` covers the policy-gate §7.5 pager/loader variables. The hooks must be safe under `set -u` and `set -e`.
- **Success criterion:** `python3 -m pytest tests/test_session.py` passes on the host (real bash 5.3.9, no VM, no sudo). Every test that waits on bash has a timeout of a few seconds and closes its session in teardown. Covers the parent brief's letters (a) (b) (c) (d) (e) (f) (g) (k) (l) (n) (o) (q) and the first half of (m):
  (a) `cd /tmp` then `pwd` → `/tmp`; `export FOO=bar` then `printf %s "$FOO"` → `bar`.
  (b) Spec Conformance vectors 1–8, 10, 12: `true` → `S 1`, `D 1 0 0`, snapshot, `E`; `false | true` → status 0, pipestatus `1 0`; `(exit 3)` → 3; `printf 'D 99 0 0\n'` and `printf '\x1b]133;D;0\x07'` → only real records, status 0; `echo 'done!!'` → `done!!`; `alias ll2='ls -la'; g(){ :; }` → next `F` gains `g`, `L` contains `ll2`; `PROMPT_COMMAND=:` → degraded within 5 s with a reason; `sleep 5` then interrupt → `D` status 130 < 3 s after `\x03`, not degraded; a command with `ESC [201~`, `ESC` or another C0 control except TAB/LF is refused and nothing reaches the PTY.
  (c) `exec 3>&-` typed raw → degraded.
  (d) no-output, multi-line, here-doc and `sleep 1 &` each give exactly one S/D pair; after `sleep 3 &` the next `J` is `0` and the session stays usable.
  (e) empty line, `# x` and `fi` each report not-run with the `D` status and leave the session healthy; `echo 'abc` (unclosed quote) degrades within 5 s by the prompt rule.
  (f) `T`, `B`, `X`, `P`, `J`, `H`, `V` present; `export LD_PRELOAD=/x.so` changes `V` and is reported; `PS0=` then `true` → DEGRADED, and `true` is not reported not-run with a healthy session. Table A row 1 (in `H`, this child): each of `PROMPT_COMMAND+=(':')`, `PS0='x'` and redefining one of nl-shell's hook functions, as a confirmed command, degrades at THAT command's snapshot, and a following `run("echo hello")` raises without writing to the PTY.
  (g) I2 reproducers: each of `PS1='${__nls_x[__nls_state=1]-}\$ '`, `readonly`, and `trap '<assign>' DEBUG`, run once per variable in a module-level tuple `HOOK_STATE_VARS`, followed by `true` then `touch MARK; echo printed; (exit 7)`, ends DEGRADED or with the third command reported as ran (output and status 7) — never "ran False" with a healthy session. The test checks that every shell variable the rcfile hooks use has prefix `__nls_` and every `__nls_` name in the rcfile text is in `HOOK_STATE_VARS`.
  (k) `x=$(sleep 2); echo hi`, `cd "$(sleep 1.5; echo /tmp)"`, ``y=`sleep 1.5` `` finish normally with a HEALTHY session; `read x` with no input degrades within 5 s (accepted limit, #136).
  (l) a literal separator byte and a newline in `PATH`, an alias and a trap round-trip exactly; `hash -p <script> tr|cksum|wc`, `BASH_CMDS[tr]=<script>` and a `PATH` with fake `tr`/`cksum`/`wc` first leave the snapshot honest (no marker).
  (m, first half) a test-HOME `~/.bashrc` setting an alias and its own `PROMPT_COMMAND` → alias in baseline `L`; the user hook still runs, before nl-shell's snapshot.
  (n) `HISTFILE` unset; `[ -p /dev/fd/3 ]` true; every record ends in `\n` with no `\r`; a record with `\r` fed to the parser is malformed (→ degraded).
  (o) restart after degraded mode gives a healthy session with a fresh baseline.
  (q) with a test-HOME `PROMPT_COMMAND` printing `HOOK-OUTPUT`, 20 runs each of `echo hello` and `printf abc` return exactly the command's own output.
  **Docs** (same patch): spec `pty-protocol/v1` §1.2 (user `PROMPT_COMMAND` before the snapshot; nl-shell sets `PS1`/`PS2`), §1.3 reference rcfile updated (no external programs, `\\n` inside `PS0`), §3 (`H`/`V` carry encoded `declare -p` text compared exactly; `H` covers the hook row), §4.1 (`D n+1` without `S n+1` = nothing ran), §4.2 (first trigger excepts that case; third trigger states the decision-7 rule), §4.3 (degraded gets no further commands until restart), Conformance vector 8 (`:180`) → "degraded at that command's snapshot (`H` changed)", and the vectors 1–7 note (`:189-190`) names what `tests/test_session.py` now checks. Policy-gate `v1` §7.5 item 5 (`:199`, `V` is encoded `declare -p` text, not `cksum`) and item 6 (`:202`, decision 10). ADR-0014 Decision 1 (`:45-46`, decision 6) and Decision 2 (`:52-54`, decision 10); ADR-0013 `:72-74` (same degraded wording). Keep each ADR edit to those sentences. Threat model: §How to exercise it says the session tests need only bash; Known gaps gains ONE interim bullet saying the remaining Table A rows and all of Table B land with the follow-up child, and nothing calls the session until #78.
- **Falsifiability:** RED on the C4 gate (`engine/scripts/run-verify.sh`): it reverts every non-`tests/` hunk and re-runs `tests/test_session.py`. The test imports `nl_shell.session` (and the protocol module) INSIDE each test or fixture, never at module level, so each test fails on its own when the change is reverted (proven shape: iteration-v3 C4, 46/46 red then green). Timing limits: 1 s prompt rule inside a 5 s limit, Ctrl-C < 3 s; re-run a timeout red once before reading it as a regression.
- **Repo + branch target:** eduralph/nl-shell @ main — build on `origin/main` = `c47c5c2`, NOT the stale `stack-base` `8c95e05` (C4 failed on it in v4 and v5). Every `path:line` here is on `c47c5c2`.
- **Reproduction:** n/a (new functionality). Prior reproducers for (g) and (k) are in `results/issue_101/iteration-v3/SUMMARY.md` §6.
- **Scope (one logical fix) / out of scope:** New `src/nl_shell/session.py` (+ optional `src/nl_shell/pty_protocol.py`); `ptyprocess` in `pyproject.toml` `dependencies`; `tests/test_session.py` (new; only stdlib + pytest at module level; runs under `tests/conftest.py:52` `isolated_environment`; never marked `vm`/`sudo`); the Docs edits above (specs are `status: draft`, ADR-0013/0014 `status: Proposed`, so the frozen-records check fb71bd1 allows them; edit no other ADR). Reuse `results/issue_101/iteration-v5/patch.diff` and `iteration-v3/patch.diff` freely, but NOT the rejected parts: a guard variable deciding whether `S` is sent, the user hook after the snapshot, the `tcgetpgrp` prompt rule, `tr`/`cksum` hooks, CRC-32 `H`/`V`, non-reversible `P`, "D without S → degraded".
  **Out of scope:** Table A rows 2–7 in `H` (traps/`extdebug`/`functrace`, xtrace/`PS4`/`BASH_XTRACEFD`, disabled hook builtins, readline state and bindings, `set -H`) and all of Table B (termios/fd outside checks, TIOCSTI, stopped bash) — child-2. Also: everything in spec §6 (#102, #120); session recovery (#121); REPL / `cli.py` wiring, `repl.py`, `input_modes.py` (#78); the policy gate (#12); sudo (#13); history (#17); taint (#11); the output filter; architecture doc 05; #134–#138.
- **External dependencies:** `ptyprocess` · `proc-syscall`
- **Test file:** `tests/test_session.py`
- **Difficulty:** high
<!-- pdca:end child-1 -->

<!-- pdca:child child-2 -->
- **Slug:** persistent-bash-session-tamper-checks
- **Kind:** enhancement
- **Defect / goal:** After child-1, a confirmed command can still change bash or its terminal so that the NEXT confirmed paste runs bytes other than the confirmed ones, or so that a paste is mangled, without the session degrading. Close that for the closed list below, so that **I1 holds: the bytes bash executes for a paste are exactly the confirmed bytes, or nothing is sent.** For every "detect" row, a change made by an earlier command shows in that command's own snapshot (session degrades), or an outside check catches it immediately before the paste is written. Source: threat model "What must hold" and its Critical row; spec §5.1.
  **Table A rows added to `H`** (compared to the baseline; a difference degrades at that command's snapshot): traps `DEBUG`/`RETURN`, `extdebug`, `functrace` (`T`/`X` still reported for the gate); `xtrace`, `PS4`, `BASH_XTRACEFD` values (decision 13; reuse the v5 detection); the enabled/disabled state of every builtin the hooks call, at least `trap`, `printf`, `read`, `declare`, `bind`, `shopt`, `compgen`, `alias`, `jobs`, `enable`, `eval`, `set`, `builtin`, exposed as a module-level tuple `HOOK_BUILTINS` (decision 12; tests read it inside each test, never at module level, so its absence on the red leg is a per-test failure, not a collection error); readline on/off, emacs/vi mode, ALL readline variables (`bind -v`), ALL key bindings (functions, macros, `bind -X` shell commands); history expansion (`set -H`). Every command substitution in the hooks captures stderr (`2>&1`), so a failing or disabled builtin never yields an empty, baseline-matching value (fixes the v5 hole at `session.py:211`, `trap -p` dropping stderr).
  **Table B outside checks** (decision 8): immediately before every paste and when each snapshot's `E` arrives, read from outside bash the PTY's termios (via the master) and bash's fds 0/1/2 (via `/proc`); any difference from the baseline degrades and the paste is not written. At startup read `tiocsti_path` (constructor keyword, default `"/proc/sys/dev/tty/legacy_tiocsti"`, read-only); missing, unreadable or not `0` → start degraded with a reason naming it. A stopped bash (`/proc` state `T`) degrades. New degrade reasons: outside-check mismatch, bash stopped, TIOCSTI allowed.
- **Success criterion:** `python3 -m pytest tests/test_session.py` passes on the host (real bash 5.3.9, no VM, no sudo), keeping all of child-1's tests green and adding the parent brief's letters (h) (i) (j) (p) (r) (s) and the second half of (m). "Marker" = a file the injected code would create; the test asserts it does NOT exist.
  (h) Each of these as a confirmed command degrades at THAT command's snapshot, and a following `run("echo hello")` raises without writing (no marker): `trap ':' DEBUG`; `trap ':' RETURN`; `set -o functrace`; `shopt -s extdebug`; `set -H`; `set -o vi` (baseline emacs); `set +o emacs`; `bind '"\r": " ; touch MARK\n"'`; `bind -x '"\C-m": "touch MARK"'`; `bind '"\e[2": "touch MARK\n"'`; `bind 'set enable-bracketed-paste off'`; `bind 'set convert-meta on'`; `exec >/dev/null`, `exec 2>/dev/null`, `exec </dev/null` (the last three by the outside fd check). The Table A row-1 cases (`PROMPT_COMMAND`, `PS0`, hook functions) are child-1's tests, not repeated here.
  (i) I3 reproducers: a test-HOME `~/.bashrc` `PROMPT_COMMAND` that runs `bind '"\r": " ; touch MARK\n"'` on its second run, and a `PS1` whose expansion would run the same `bind` → degraded before any later paste; no marker.
  (j) `stty intr '|'` → degraded, then `run("true || touch MARK")` raises without writing; no marker. `stty -isig` → degraded before the next paste. `tiocsti_path` pointed at a temp file containing `1`, and at a missing path → starts degraded with a reason naming it. `kill -STOP $$` from a background subshell → degraded within 5 s, not a hang. (`stty icanon`/`-echo` not tested: readline resets both per line.)
  (m, second half) a test-HOME `~/.bashrc` with `bind 'set enable-bracketed-paste off'` and `set -o vi` → the session either works (a two-line command arrives byte-for-byte with one S/D pair) or starts degraded with a reason; never runs mangled bytes.
  (p) after each of `bind 'set enable-bracketed-paste off'`, `set +o emacs`, `set -o vi` (fresh session each), a following `echo hello` never returns `output == b""` with a healthy session.
  (r) `exec 9>/dev/null; BASH_XTRACEFD=9; PS4='$(echo x >> MARK)'; set -x` → degraded at that snapshot; a following `run("true")` raises without writing; no marker.
  (s) for EVERY name in `HOOK_BUILTINS` (the test checks each appears in the rcfile text), `enable -n <name>` → degraded within 5 s and a following `run(...)` raises without writing. Plus the v5 reproducers: `trap '[[ $BASH_COMMAND == "echo later" ]] && : > MARK' DEBUG; enable -n trap` then `run("echo later")`, and `alias ls='touch MARK #'; enable -n alias` then `run("ls")` → raises or degraded before the paste; no marker.
  **Docs** (same patch): spec `pty-protocol/v1` §3 (`H` covers all Table A "detect" rows; the Table B outside checks and when they run), §4.2 new triggers (outside-check mismatch, bash stopped, TIOCSTI allowed), and the Conformance "Open questions" bullet on forcing `enable-bracketed-paste on` (`:195-196`) closed by naming decision 6 and Table A's readline row. Threat model Known gaps: replace child-1's interim bullet with: the decision-2 bullets (loadable builtins via `enable -f` and functions named `builtin`/`command`/`local`/`return`, gate class `session-altering`, ADR-0024; `~/.bashrc`/`~/.inputrc` edited and picked up at restart, #134; `ptrace_scope = 0`, #137; builtin-only commands over 1 s degrade, #136; outside checks are Linux-only, #138) and the Known-gap rows of both tables (fake fd-3 records, #135), each naming its follow-up. NO catch-all sentence ("not every deliberate way around them") that would also cover `enable -n` (decision 12). Code comments must not claim more than these bullets.
- **Falsifiability:** RED on the C4 gate (`engine/scripts/run-verify.sh`, which counts the red leg as PASS when >0 tests ran and failed, and resets to `$PDCA_VERIFY_BASE`, the wave-2 folded branch holding child-1). Reverting this child's production hunks leaves child-1's session in place, so child-1's tests stay green while (h) (i) (j) (r) (s) and (m)/(p) fail on their attack (marker created, or session stays healthy), not on import. Every attack here was reproduced live against the v3/v5 patches (`iteration-v3/SUMMARY.md` §6, `iteration-v5/SUMMARY.md`), so they go red against a wrong implementation, not only an absent one. Needs `/proc/<pid>/syscall` and `/proc/<pid>/fd` readable for the session's own child (`ptrace_scope = 1` allows it), and `dev.tty.legacy_tiocsti = 0` on the host (test (j) simulates `1` through `tiocsti_path`, no root).
- **Repo + branch target:** eduralph/nl-shell @ main — build on child-1's accepted result (the wave-2 integration branch), not on bare `main` and not on the stale `stack-base` `8c95e05`. Cite `path:line` on that base for `session.py`/`test_session.py`, and on `c47c5c2` for the docs lines above.
- **Reproduction:** n/a as a fresh feature; on child-1 alone, each (h)/(j)/(s) command above leaves the session healthy and the next paste runs altered (the v3/v5 reproducers in `iteration-v3/SUMMARY.md` §6 and `deferred-findings.json`).
- **Scope (one logical fix) / out of scope:** `src/nl_shell/session.py` (rcfile `H` additions, `HOOK_BUILTINS`, `2>&1` on every hook substitution, outside checks in the paste path and at `E`, `tiocsti_path` startup check, stopped-state check); `tests/test_session.py` (new tests only; keep child-1's tests); the Docs edits above.
  **Out of scope:** anything child-1 owns (parser, sequencing, paste filter, prompt rule, output boundary, I2/`HOOK_STATE_VARS`, encoding); Table A rows "reported for the gate" or "made harmless by decision 6"; defending fd-3 writes (#135); loadable builtins / shadowing functions (decision 2, Known gap); spec §6 and terminal ownership (#102, #120); #78, #121, #12, #13, #17, #11; `repl.py`, `input_modes.py`, `cli.py`; #134–#138.
- **External dependencies:** `ptyprocess` · `proc-syscall` · `tiocsti-off` · `ptrace-scope`
- **Test file:** `tests/test_session.py`
- **Difficulty:** high
- **Depends on:** child-1
<!-- pdca:end child-2 -->

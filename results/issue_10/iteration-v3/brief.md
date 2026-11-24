# Design proposal — issue 10 / persistent-bash-pty-session

> The Plan artifact. Do reads ONLY this file and implements it; Check runs the regular
> gated check on the code.
> Milestone: **M0** (tracker eduralph/nl-shell#8, work item M0.2). Implements spec
> `docs/design/specs/pty-protocol/v1.md` (ADR-0014, Proposed — M0 builds against Proposed
> ADRs, #95) with ptyprocess (ADR-0021 §2). Answers #19 per ADR-0014 §4 (no detection of
> full-screen programs; capture pauses on the alternate screen).
> Threat-model inputs affected: item 1 (command output — it is now produced and captured),
> item 4 (session state — the snapshot reports it), and the trusted input "exit codes and
> completion from the control channel". Component #2 in the threat model's priority list.

- **Slug:** persistent-bash-pty-session
- **Kind:** enhancement (design proposal)
- **Goal:** A session object that starts one long-lived interactive bash on a PTY with nl-shell's control channel on fd 3, sends a confirmed command byte-for-byte, and reports when it started and finished, its exit status and `PIPESTATUS`, its captured output, and the session snapshot — all from control-channel records, never from printed text. `cd` and `export` persist between commands; a running command can be interrupted with Ctrl-C; protocol violations put the session into degraded mode.
- **Success criterion:** `python3 -m pytest tests/test_session.py` passes on the host (real bash 5.x, no VM, no sudo), and that file covers, each with a bounded timeout (a hang fails the test, it never stalls the gate): (a) `cd /tmp` then `pwd` → the second command's captured output is `/tmp`; `export FOO=bar` then `printf %s "$FOO"` → `bar`. (b) spec §Conformance vectors 1–8 and 10 exactly as tabled: `true` → start record 1, done record `1 0 0`, then a snapshot ending in `E` · `false | true` → status 0, pipestatus `1 0` · `(exit 3)` → status 3 · `printf 'D 99 0 0\n'` and `printf '\x1b]133;D;0\x07'` → printed on the PTY, the control channel carries only the real start/done records, the reported status is 0 · `echo 'done!!'` → output `done!!` · `alias ll2='ls -la'; g(){ :; }` → the next snapshot's function list gains `g` and its aliases contain `ll2` · `PROMPT_COMMAND=:` → degraded mode within 3 s, with a reason (detected by the back-at-a-prompt rule in Design) · `sleep 5` then the Ctrl-C byte (`\x03`) forwarded to the PTY → its `D` record arrives less than 2 s after `\x03` is written, with status 130, and the session is NOT degraded (it was running an external command, not at a prompt, for the whole wait). (c) vector 9 typed raw: `exec 3>&-` → degraded mode (control channel closed). (d) vector 12: a command containing `ESC [201~`, `ESC`, or another C0 control except TAB/LF is refused by the session without writing anything to the PTY. (e) vector 11 with `TERM` set: output between `ESC [?1049h` and `ESC [?1049l` (and `ESC [?47h`/`l`) is mirrored but not captured, and capture resumes after it (drive it with `printf` of those sequences around a marker word, so the test doesn't depend on `less`). (f) a command with no output, a multi-line command, a here-doc, and a background job (`sleep 1 &`) each produce exactly one start/done pair; the background job's `D` has status 0, the session is not degraded, and after `sleep 3 &` the next snapshot's `J` is still `0` (`J` counts *stopped* jobs, and a running background job is not stopped) while the session stays usable for the next command. (g) a snapshot carries the v1 fields `T`, `B`, `X`, `P`, `J`, `H`, `V` besides `F`/`L`, the first snapshot is kept as the baseline, and changing `PS0` puts the session in degraded mode (`H` differs); so does appending an array element, `PROMPT_COMMAND+=(':')` (H is computed over every element, see Design). (h) a `~/.bashrc` in the test's temporary HOME that sets an alias and its own `PROMPT_COMMAND` → the alias is in the first snapshot and the user's `PROMPT_COMMAND` still runs, after nl-shell's hook; a `~/.bashrc` containing `bind 'set enable-bracketed-paste off'` and `set -o vi` → a two-line command still arrives byte-for-byte and gives exactly one start/done pair. (i) bash writes no history: `HISTFILE` is unset in the session. (j) control-channel wiring: inside the session `[ -p /dev/fd/3 ]` is true (fd 3 is a FIFO, not the PTY), every record read in tests (a)–(i) ends in `\n` with no `\r`, and a record containing `\r` fed to the record parser is malformed (→ degraded). (k) terminal ownership with an `os.openpty()` pair as the "real" terminal: its termios attributes are equal before and after a forwarded run; after resizing it to 40×100 and delivering `SIGWINCH`, `stty size` in the session prints `40 100`; a sentinel byte string forwarded while `cat > /dev/null` runs does not appear in the captured output, in the result object, or in any attribute of the session object (checked by scanning `vars()` recursively for the sentinel).
- **Falsifiability:** RED is reachable on the shipped C4 gate (`engine/scripts/run-verify.sh`, plain pytest on the host). With the production change reverted the session module does not exist, so each test's import of it — done inside the test function, see Test file — raises and the test fails (tests ran, failures > 0). GREEN needs real `bash` (host: GNU bash 5.3.9 on Ubuntu 26.04 — the same version the spec's vectors 1–7 were checked against) and `ptyprocess` importable from the gate's venv (`.venv`), which is NOT installed today: that is the `ptyprocess` doctor row below, and the driver holds this bundle before Do until it passes. No vector needs real sudo, a VM or a GPU.
- **Repo + branch target:** eduralph/nl-shell @ main
- **Ordering note:** No `Depends on`: the thread names #65 and #19 as prerequisites and both are met on `main` — #65 (the protocol ADR + spec) is closed with `docs/design/specs/pty-protocol/v1.md` merged (`v1.md:7` tracking-issue #65); #19 is still open but its question is answered by ADR-0014 §4 (`0014-pty-session-protocol.md:69-70`). Both are `Proposed`/draft, which M0 builds against (#95). First wave, beside #14 (no shared files: this bundle adds new modules, a test file, the dependency in `pyproject.toml` and the threat-model paragraph; #14 edits `repl.py`). #62 depends on this bundle's done-record type. Wiring the session into the REPL is NOT here — #78 owns input → gate → PTY, so commands never reach bash before the gate exists.
- **Surfaces:** data
- **Scope:** One session unit (new module(s) under `src/nl_shell/`) implementing pty-protocol v1 §1–§6: start `bash --noprofile --rcfile <rcfile> -i` on a PTY via ptyprocess with a pipe's write end as fd 3 in the child (§1.1); the rcfile as the spec's reference (§1.3), with two fixes stated in Design (`\\n` inside `PS0`, and `H` over every `PROMPT_COMMAND` element) plus the v1 snapshot records `T`, `B`, `X`, `P`, `J`, `H`, `V` (§3) and `bind 'set enable-bracketed-paste on'` (the spec's first open question — force it so `~/.bashrc` can't turn bracketed paste off); parse records (§2), enforce the S → D → snapshot → E order and enter degraded mode on every §4.2 trigger, with a reason, and offer a restart (a method that starts a fresh session; the REPL message is #78's); send a command as one bracketed paste + CR and refuse forbidden bytes (§5); terminal ownership (§6): a forwarding loop that, between send and done record, puts a given real terminal in raw mode, forwards its input bytes to the PTY master unchanged and keeps none of them, copies PTY output to the terminal, captures output for the caller except on the alternate screen (§6.2), copies the window size on `SIGWINCH` (§6.3), and restores the terminal afterwards. Unknown record types are ignored (spec §Versioning). Add `ptyprocess` to `pyproject.toml` `dependencies`. Update `.oss-scanner/threat_model.md` §How to exercise it (the issue asks for this): how the session tests run and that they need only bash. / out of scope: wiring into the REPL or `cli.py` (#78); the policy gate and its fd-3 / control-character rejection (#12 — the session's own refusal in (d) is defence in depth, not the gate); sudo passthrough and the per-session `SUDO_PROMPT` (#13, ADR-0015); history write-back to `~/.bash_history` (§7 — #17); taint labels and the state block (#11); a rendering filter for mirrored output (OSC 52 etc. — not owned by this issue, see Open questions); the architecture doc 05 code-layout table (one docs pass after the batch).
- **Difficulty:** high
- **External dependencies:** `ptyprocess` (gate venv; install with the row's hint before Do). Real bash ≥ 5.1 on the host (base toolchain: Ubuntu 26.04 ships 5.3.9).
- **Test file:** `tests/test_session.py` (new). The C4 red leg reverts every non-`tests/` file and re-runs this file; a module-level import of the new session module would fail to IMPORT and make the run UNVERIFIABLE instead of red. So import the session module inside each test (or inside a fixture), and keep module-level imports to the standard library and pytest. Every test that waits on bash must have a timeout (a few seconds) and close the session in teardown, so the gate never hangs and no bash outlives the test. Tests run under the suite's isolation (`tests/conftest.py`: temporary HOME, guarded `sudo`) — never mark them `vm` or `sudo`.
- **Citations expected:** Do must cite path:line on `main` for every change, and the spec section (`pty-protocol/v1` §n) each part implements. Normative sources to cite for the protocol: `docs/design/specs/pty-protocol/v1.md` §1–§6 and §Conformance; `docs/design/adr/0014-pty-session-protocol.md` Decision 1–4. Test isolation peer: `tests/conftest.py:51-70` (`isolated_environment`).
- **Prior-art check (triage cycles):** `git -C ../nl-shell log origin/main -- src/nl_shell` → only the scaffold (305d8a4), router (dc784f0) and isolation (c45c53e); no session code exists. `git grep -i ptyprocess origin/main -- src pyproject.toml` → nothing. Closed-unmerged PRs touching `src/` or `pyproject.toml`: none. Open PRs: only #100 (docs). Issue search "pty" / "ptyprocess": #10 itself, #19 (answered by ADR-0014), #24 (sudo-rs facts, M1), #13/#75 (sudo, later). No prior work.
- **Disposition hint:** new-feature

## Motivation

Everything in M0 that decides what runs — the gate's live-session check (ADR-0013 §5),
sudo passthrough (ADR-0015), failure classes (#62), state capture (#11) — needs to know
exactly when a command starts and ends, its exit status, and the session's state, in a
way printed text can't forge. This is the base they all stand on.

## Design

Follow `pty-protocol/v1` as written; it is the contract. Points Do must not get wrong:

- The control channel is the only source of start, done, exit status and snapshot.
  Never parse the PTY stream for them (vectors 4 and 5 test this).
- A command is sent as `ESC [200~` + bytes + `ESC [201~` + `CR`, and nothing else is
  written to the PTY while it runs except forwarded input.
- Output between the start and done records belongs to that command. Capture pauses on
  `ESC [?1049h` / `ESC [?47h` and resumes on the matching reset; mirroring to the terminal
  continues.
- Forwarded input bytes are never stored, logged or included in captured output (the
  sudo password will travel this way once #13 lands).
- Degraded mode is sticky until restart and always carries a human-readable reason.
- The session runs in the caller's environment, with `TERM` set; the rcfile sources the
  user's `~/.bashrc` first and installs nl-shell's hooks last, keeping the user's
  `PROMPT_COMMAND` and running it after nl-shell's hook.

Probe result at Plan (host bash 5.3.9, ptyprocess 0.7.0, the reference rcfile, fd 3 set
up with `preexec_fn` `os.dup2` + `pass_fds`): `(exit 3)` → `D 1 3 3`, `false | true` →
`D 2 0 1 0`, `printf 'D 99 0 0\n'` → control channel showed only `S 3` / `D 3 0 0`, and
`sleep 5` + `\x03` → `D 4 130 130`. The start record arrived as `S 1\r\n`, not `S 1\n`.
Re-probed at plan review: fd 3 *is* a FIFO (`[ -p /dev/fd/3 ]` true in the child, `D`
records arrive with plain `\n`). The `\r` comes from bash's prompt decoding: `PS0` is a
prompt string, and with line editing on bash turns the prompt escape `\n` into `\r\n`
before `printf` sees it. Writing `printf "S %s\\n"` inside `PS0` gives `S 1\n` (probed,
bash 5.3.9). So: fix it in the rcfile (`\\n` in `PS0`), and the parser does NOT accept
`\r` — a record containing `\r` is malformed (§Conventions, §4.2). Report the reference
rcfile bug in build-notes rather than editing the spec.

**Back at a prompt (§4.2 third trigger).** The spec does not say how to detect it, and the
records can't (after `PROMPT_COMMAND=:` there are none). Use the kernel: the PTY's
foreground process group (`os.tcgetpgrp(master_fd)`). While an external command runs it is
the command's group; at the readline prompt it is bash's own pid (probed). Rule: after an
`S n`, if no `D n` has arrived and the foreground group has been bash's pid continuously for
1 s, enter degraded mode ("no done record after the shell returned to a prompt"). Known
limit, accepted as fail-closed: a builtin that waits on the terminal (`read x`, `wait`)
looks the same and degrades the session after 1 s; say so in build-notes. Do not parse the
PTY stream for a prompt.

**`H` and array `PROMPT_COMMAND`.** bash ≥ 5.1 allows `PROMPT_COMMAND` to be an array and
`$PROMPT_COMMAND` expands only element 0, so `PROMPT_COMMAND+=('evil')` would not change a
`cksum` of `$PROMPT_COMMAND`. Compute `H` over `declare -p PROMPT_COMMAND PS0` (covers every
element), and note the spec wording in build-notes. The rcfile's assignment
`PROMPT_COMMAND='__nls_done; …'` replaces element 0 only; any further elements a user's
`~/.bashrc` set keep running after it, which matches §1.2's ordering.

**Background jobs and fd 3.** A background job inherits fd 3, so after `exec 3>&-` the pipe
may stay open while that job lives. Vector 9 is tested with no background job running; the
"control channel closed" trigger is EOF on the read end.

The API shape (class names, sync vs. callback) is Do's choice; keep it usable by #78 (send
one confirmed command, wait for its result) and by the forwarding loop with a real
terminal, and make the terminal and its file descriptors injectable so tests can use
`os.openpty()` in place of a real tty.

## Alternatives considered

- pexpect with output sentinels: rejected by ADR-0014 (forgeable, changes the command).
- OSC 133 marks on the PTY stream: rejected by ADR-0014 (printed text can fake them;
  vector 5 checks this).

## Impact & compatibility

New runtime dependency `ptyprocess` (ADR-0021). Nothing user-visible yet: the REPL still
prints its "can't run anything yet" reply until #78 wires the session in.

## Open questions

- **Rendering filter.** The threat model requires mirrored PTY output to be filtered
  (no OSC 52 clipboard writes, no spoofed nl-shell UI) while full-screen programs keep
  their escapes. No open issue owns that filter; this brief leaves it out. Suggest filing
  one before #78 makes the mirror user-facing.
- Whether this slice should be split in two (session + protocol, then terminal ownership
  + forwarding). Kept as one: the forwarding loop is what makes vectors 10 and 11 real.

## STOP discipline

Draft only until Check sign-off. Pushing to a feature/draft branch and opening a
draft PR MAY happen during the cycle (useful for CI feedback). The PR MUST NOT be
marked ready before sign-off accepts.

Plan-review response: findings 1, 2, 3, 5, 6, 7, 8 addressed in the brief — (1) re-probed: fd 3 is a FIFO; the `\r` is bash's prompt decoding of `\n` in `PS0`, so the rcfile is fixed and `\r` is malformed, with test (j); (2) the back-at-a-prompt rule is named (foreground process group, 1 s) with a no-degrade check on vector 10, and its `read`-builtin false positive is stated as an accepted fail-closed limit — the human should confirm that trade-off at sign-off; (3) background-job row added to (f); (5) `H` covers every `PROMPT_COMMAND` element, with a test in (g); (6) SIGWINCH, termios restore and the never-store-input property are tested in (k); (7) forced bracketed paste is tested in (h); (8) vector 10 bound is 2 s. Finding 4: the Ordering note now records why #65 and #19 are treated as met (#65 closed, spec merged; #19 answered by ADR-0014 §4).

## Iteration 1 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 1): rebuilding for the implementation-level findings — C5 Causal adequacy — Reject oversized numeric fields through sticky degradation — a live malformed D record raises uncaught ValueError and leaves degraded=False, violating the protocol-failure contract; target/src/nl_shell/pty_protocol.py:248 and target/docs/design/specs/pty-protocol/v1.md:104.; **Medium** (threat model: "the session doesn't enter degraded mode when its hooks were changed"; it becomes **High** once #12's gate relies on `F`/`L`, because a session change then goes undetected by the gate). `target/src/nl_shell/session.py:100` and `target/src/nl_shell/pty_protocol.py:277`. **Input:** session state set by a confirmed `source` of a repository script (item 4). **What goes wrong:** `H` is a checksum of `declare -p PROMPT_COMMAND PS0` only. The code that actually runs at every prompt is outside it: the function `__nls_done` (`session.py:82`), `__nls_ret`, and the variable `__nls_user_pc`, which is `eval`'d at every prompt (`session.py:105`). A sourced script can redefine `__nls_done` to print well-formed but false `D`/`F`/`L` records (for example, an `L` that hides a newly added `alias ls='rm -rf ~'`), or put any code in `__nls_user_pc`. `PROMPT_COMMAND` and `PS0` keep the same text, so `H` matches the baseline and the session never degrades. `F` lists only function names, so a redefined `__nls_done` doesn't change it either. **Reproducer** (probed on host bash 5.3.9): with `PS0` set, `h1=$(declare -p PROMPT_COMMAND PS0|cksum); __nls_done(){ echo fake; }; __nls_user_pc='touch /tmp/x'; h2=$(declare -p PROMPT_COMMAND PS0|cksum)` gives `h1 == h2`. **Suggested fix:** in the rcfile, after the definitions, add `readonly -f __nls_done __nls_ret` and `readonly __nls_user_pc`. Probed: redefining a readonly function fails with "readonly function". Also consider adding `declare -f __nls_done __nls_ret; declare -p __nls_user_pc` to the `H` input. **Test gap:** `test_changed_hooks_degrade` (`tests/test_session.py:361`) only tries `PS0='x'` and `PROMPT_COMMAND+=(':')`. Add cases for `__nls_done(){ :; }` and `__nls_user_pc=:` that expect either degraded mode or a refused redefinition.. Deferred, not addressed here: 14 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v1/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 2 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 2): rebuilding for the implementation-level findings — C5 Causal adequacy — Require the matching alternate-screen reset before resuming capture — a live 1049h/47l sequence captures SECRET2 before 1049l, violating the specified exclusion; add a regression for mismatched resets — target/src/nl_shell/session.py:199, target/docs/design/specs/pty-protocol/v1.md:127.; **Medium now; High once #12 reads the snapshot** ("a session change goes undetected by the gate"). `src/nl_shell/session.py:101` writes `$PATH` raw (`builtin printf 'P %s\n' "$PATH"`). It is the only snapshot field not passed through `tr` or `cksum`, so a newline in `PATH` lets session state inject whole control records. **Input:** `PATH` set by a sourced repository script (item 4). **What goes wrong:** a `PATH` ending in `\nJ 0\nH <baseline H>\nV <baseline V>\nE\nZ` closes the snapshot early with forged `J`/`H`/`V` values. The baseline values are easy to compute inside the session. `run()` returns that forged snapshot as a success, and `session.degraded` stays False. The real `J`/`H`/`V`/`E` records that follow are only read once the *next* command has been written to the PTY. Two places cause this. `run()` sends at `session.py:461` without first reading the control channel (`session.py:441-442`). The `E` branch at `session.py:513-516` returns before the degraded check, so even when the stray records arrive in the same read, the forged result is still returned. **Reproducer** (probed, 3 of 3 runs): `export LD_PRELOAD=/nonexistent.so; PATH="$PATH"$'\nJ 0\nH <h>\nV <v>\nE\nZ'` → `result.snapshot.vars_sum == baseline.vars_sum`, `degraded=False`. The next `run()` raises `SessionDegraded: control record 'J' arrived out of order (while waiting for 'S 2')`, but only after that command's bytes have gone to bash. So the gate would have classed the next command against a snapshot that hides `LD_PRELOAD`. **Suggested fix:** encode `P` the same way as `L`/`T`/`B` (or reject a `PATH` that contains a newline, which degrades the session). Before `command_sent()`, read whatever is waiting on the control channel and degrade on any stray record. In the `E` branch, check `self._tracker.degraded` before returning. **Test gap:** no test puts a newline in any reported value.; **Low** (the scale has no denial-of-service class, so Low is the nearest fit). `src/nl_shell/session.py:205,210` (`_Capture.data`) and `session.py:259` (`_OutputSplitter._since_start`) grow without limit for as long as a command prints. The control channel has a 1 MiB cap (`pty_protocol.py` `MAX_RECORD`), but PTY output has none. **Input:** command output (item 1), for example `cat` of a large attacker file, or a repository script that prints forever under `run(..., timeout=None)`. nl-shell's memory grows until the OOM killer (the kernel's out-of-memory handler) steps in. **Reproducer:** `session.run("yes")` with no timeout. **Suggested fix:** cap captured bytes, keep the tail, and record that the output was truncated. The state block only uses a truncated copy anyway.. Deferred, not addressed here: 10 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v2/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 3 — carry-forward (from the previous attempt)
- Sign-off rationale: Re-plan to settle the security decisions before another build; more Do rounds keep patching one hole at a time in the same class (in-shell code reporting on its own state). Decide in the brief, and record in the threat model / spec as needed: - Trust model of the snapshot: is it meant to resist a hostile `source`d script? A function named `builtin`/`command` currently hides aliases/functions from F/L with H unchanged (session.py:78-79 comment overstates the guarantee). Either add a structural defence or document it as a known gap and have the gate (#12) treat `source`/`.` as session-altering. - fd 3 forgery: a command can write its own D + snapshot + E to fd 3 and run() returns it as success. Decide protocol-level: keep fd 3 away from the command, authenticate records, or accept + document. - H/V integrity: cksum (CRC-32) is forgeable; decide whether to send raw text for nl-shell to compare or use a real hash (spec change). - Implementation fixes to carry into the brief: no external tr/cksum lookup via PATH/hash table in the hook (bash string ops or absolute paths) + a `hash -p` regression; reversible PATH encoding (literal \x1e collides with encoded newline) + regression. - Product trade-offs to decide with them: typed-ahead input prepended to the next confirmed command; syntax error/comment-only line degrades the session; capture stops at first forwarded byte; an owner issue for the output rendering filter (OSC 52 etc.) that blocks #78. Consider splitting the slice (session core / snapshot integrity / terminal forwarding) — 2 rounds spent, 71 KB patch.
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Re-plan to settle the security decisions before another build; more Do rounds keep patching one hole at a time in the same class (in-shell code reporting on its own state).
  Decide in the brief, and record in the threat model / spec as needed:
  - Trust model of the snapshot: is it meant to resist a hostile `source`d script? A function named `builtin`/`command` currently hides aliases/functions from F/L with H unchanged (session.py:78-79 comment overstates the guarantee). Either add a structural defence or document it as a known gap and have the gate (#12) treat `source`/`.` as session-altering.
  - fd 3 forgery: a command can write its own D + snapshot + E to fd 3 and run() returns it as success. Decide protocol-level: keep fd 3 away from the command, authenticate records, or accept + document.
  - H/V integrity: cksum (CRC-32) is forgeable; decide whether to send raw text for nl-shell to compare or use a real hash (spec change).
  - Implementation fixes to carry into the brief: no external tr/cksum lookup via PATH/hash table in the hook (bash string ops or absolute paths) + a `hash -p` regression; reversible PATH encoding (literal \x1e collides with encoded newline) + regression.
  - Product trade-offs to decide with them: typed-ahead input prepended to the next confirmed command; syntax error/comment-only line degrades the session; capture stops at first forwarded byte; an owner issue for the output rendering filter (OSC 52 etc.) that blocks #78.
  Consider splitting the slice (session core / snapshot integrity / terminal forwarding) — 2 rounds spent, 71 KB patch.
- Full previous attempt preserved in `iteration-v3/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

# Design proposal — issue 10 / persistent-bash-pty-session (re-plan after 3 rounds)

> The Plan artifact. This brief is the PARENT of a two-way split (see "Split" below); each
> child gets its own brief. Do builds the children, not this one.
> Milestone: **M0** (tracker eduralph/nl-shell#8, work item M0.2). Implements spec
> `docs/design/specs/pty-protocol/v1.md` (ADR-0014, Proposed — M0 builds against Proposed
> ADRs, #95) with ptyprocess (ADR-0021 §2). Answers #19 per ADR-0014 §4.
> Threat-model inputs affected: item 1 (command output), item 4 (session state), and the
> trusted input "exit codes and completion from the control channel".

- **Slug:** persistent-bash-pty-session
- **Kind:** enhancement (design proposal)
- **Goal:** A session object that starts one long-lived interactive bash on a PTY with nl-shell's control channel on fd 3, sends a confirmed command byte-for-byte, and reports when it started and finished, its exit status and `PIPESTATUS`, its captured output and the session snapshot — all from control-channel records, never from printed text — and that owns the real terminal while a command runs. `cd` and `export` persist between commands; Ctrl-C interrupts; protocol violations put the session into degraded mode.
- **Success criterion:** both children's success criteria hold: child A (session core, spec §1–§5) — `python3 -m pytest tests/test_session.py` passes; child B (terminal ownership, spec §6) — `python3 -m pytest tests/test_session_terminal.py` passes. Each child brief states its own vectors.
- **Falsifiability:** per child (each child's test imports its own new module inside the test functions, so the C4 red leg — production change reverted, test kept — fails with real test failures, not a collection error; proven shape: iteration-v3 C4 "46 of 46 failed" red, green after). Real bash 5.3.9 on the host; `ptyprocess` 0.7.0 in `.venv` (doctor row passes).
- **Repo + branch target:** eduralph/nl-shell @ main
- **Ordering note:** No `Depends on` for the parent: #65 is closed with the spec merged (`v1.md:7`); #19 is answered by ADR-0014 §4. Child B depends on child A (it extends A's session module).
- **Surfaces:** data
- **Scope:** pty-protocol v1 §1–§6 with the decisions below, as two children. / out of scope: wiring into the REPL or `cli.py` (#78); the policy gate and its fd-3 rejection (#12); sudo passthrough (#13); history write-back (#17); taint and the state block (#11); the output rendering filter (OSC 52 etc. — the human files a separate issue that blocks #78); the architecture doc 05 code-layout table.
- **Difficulty:** high
- **External dependencies:** `ptyprocess` (gate venv). Real bash ≥ 5.1 on the host (base toolchain: Ubuntu 26.04 ships 5.3.9).
- **Test file:** per child: `tests/test_session.py` (A), `tests/test_session_terminal.py` (B).
- **Citations expected:** Do must cite path:line on `main` for every change, and the spec section (`pty-protocol/v1` §n) each part implements.
- **Prior-art check (triage cycles):** `git -C ../nl-shell log origin/main -- src/nl_shell pyproject.toml` → only the scaffold (305d8a4), router (dc784f0) and isolation (c45c53e); `git grep -i ptyprocess origin/main` → only docs. Merged PRs (gh, all states): none touch a session/PTY module; closed-unmerged PRs touching `src/`: none. Issues "pty"/"session"/"filter": #10, #19, #24, #74 (confirm UI only), #78 (turn pipeline). No prior work. The three earlier attempts of THIS bundle are in `iteration-v1..v3/` (not upstream).
- **Disposition hint:** new-feature

## Decisions settled at re-plan (human, 2026-10-15)

These answer the iteration-v3 sign-off. They hold for both children.

1. **fd 3 forgery by a command is out of scope** — already decided: ADR-0014 Decision 1
   ("A program that writes to its inherited fd 3 on purpose is code running as the user,
   outside the threat model"), threat model Known gaps ("Child processes inherit the control
   channel (fd 3)"), and the gate rejects fd-3 redirects (policy-gate v1 §4, vector 25). No
   protocol change; no defence in the session.
2. **Deliberate subversion of the in-shell hooks by confirmed code is a Known gap.** A
   function named `builtin`/`command`, `enable -f`, etc. defined by a confirmed `source` is
   code running as the user; `source`/`.` is already `session-altering` (ADR-0013 §4,
   policy-gate v1 §3), so it is always confirmed. Add a bullet to the threat model's Known
   gaps saying so. No partial in-band defence (it would restart the one-hole-at-a-time loop).
   Code comments must not claim more than this.
3. **No checksums for `H`/`V`.** The snapshot sends the raw text (`declare -p` of the hook
   variables / of the pager-and-loader variables, encoded reversibly like the other text
   fields) and nl-shell compares it exactly against the baseline. Update spec §3 wording
   (the spec is `draft`, so the docs CI allows it).
4. **The hook runs no external programs** (no `tr`, `cksum`, `wc`): bash parameter expansion
   only, so `PATH`, `hash -p` and `BASH_CMDS` can't swap them. Every free-text field uses one
   **reversible** encoding (a literal separator byte in a value must round-trip exactly).
5. **"D n+1 without S n+1" means nothing ran** (empty line, comment-only line, syntax
   error): report it as not-run with the `D` status, session stays healthy. Spec §4.1 is
   updated to say so. A tampered `PS0` is still caught by `H`.
6. **Typed-ahead input must never join the next confirmed command** (threat model:
   "What the user confirms is exactly what runs", Critical). Forwarding stops at the `D`
   record; before each paste, input bash has not consumed is discarded.
7. **Capture stops at the first forwarded byte** for the rest of that command (spec §6.2
   capture is MAY); the result carries a flag saying so.
8. **Rendering filter:** out of scope; the human files an owner issue that blocks #78.

## Split

- **A — session core (spec §1–§5):** process start, rcfile, records, snapshot, sequencing
  and degraded mode, sending a command, restart; decisions 1–5. Ctrl-C (vector 10) via a
  session method that writes `\x03` to the PTY.
- **B — terminal ownership (spec §6):** raw mode, forwarding, mirroring, alternate-screen
  capture pause (vector 11), SIGWINCH, terminal restore, never keeping input; decisions 6–7.
  Depends on A.

## Alternatives considered

- pexpect with output sentinels / OSC 133 marks on the PTY stream: rejected by ADR-0014.
- Three children (snapshot integrity on its own): rejected — it shares the rcfile with the
  core, so it would cost a cycle for no independence.
- Authenticating fd-3 records / a structural defence against shadowed builtins: rejected,
  decisions 1–2 (code running as the user is out of scope).

## STOP discipline

Draft only until Check sign-off. The PR MUST NOT be marked ready before sign-off accepts.

# Build notes — issue 101 (persistent-bash-session-core)

Target: eduralph/nl-shell @ main, base `8c95e05`. Line numbers below are on the patched
worktree (new files) or the base (edited docs).

## What changed and why

| File | Change | Spec |
|---|---|---|
| `src/nl_shell/pty_protocol.py` (new) | record parser `parse_record` (:115), field decoder `decode_field` (:95), command check `check_command` (:139), the §4 state machine `ProtocolTracker` (:156) | §2, §3, §4, §5.2, §Versioning |
| `src/nl_shell/session.py` (new) | `Session`: spawn on a PTY with fd 3 (`_spawn` :283), `RCFILE` (:72), `run` (:361), `interrupt` (:355), `restart` (:253), back-at-a-prompt rule (`_bash_in_foreground` :453, check at :428), bounded output (`_Output` :178) | §1, §4.2, §5 |
| `pyproject.toml:15` | `ptyprocess>=0.7` in `dependencies` | ADR-0021 §2 |
| `docs/design/specs/pty-protocol/v1.md` | §1.3 reference rcfile replaced by the one in use (+ notes), §2 F/L rows + encoding paragraph, §3 H/V wording, §4.1 "D without S = nothing ran", §4.2 first-trigger exception and third-trigger back-at-a-prompt rule, Conformance note, removed the now-answered bracketed-paste open question | — |
| `docs/design/specs/policy-gate/v1.md:192-196` | §7.5 wording: `V` is the encoded `declare -p` text, not a `cksum`; rule and variable list unchanged | — |
| `.oss-scanner/threat_model.md:168` | Known-gaps bullet (decision 2 + the 1 s fail-closed limit); `:187` How-to-exercise paragraph | — |
| `tests/test_session.py` (new) | 55 tests, criteria (a)–(k) | §Conformance 1–10, 12 |

### Settled decisions, as built

1. fd-3 writes by a command: no defence, no claim (comment at `session.py` top of RCFILE).
2. Deliberate subversion (function named `builtin`, `enable -f`, a confirmed `source`):
   threat-model Known-gaps bullet added. The code comment on `readonly -f` says it only
   makes an accidental redefinition fail, "not a defence".
3. `H`/`V` carry raw `declare -p` / `declare -f` text, encoded, compared exactly
   (`pty_protocol.py`, `_end_snapshot`, `snapshot.hooks != self.baseline.hooks`). No
   checksum anywhere.
4. The hooks call no external program (`session.py:85-119`): builtins via `builtin`, one
   reversible encoding in `__nls_enc` (backslash first, then LF, then CR, all with quoted
   pattern/replacement so bash 5.2's `patsub_replacement` can't treat `&` specially). The
   `J` count uses parameter expansion (`${v//[!$'\n']/}`), not `wc`.
5. `D n+1` without `S n+1` → `ran=False`, status from `D`, session healthy
   (`pty_protocol.py:240-244`).

### Things I added beyond the letter of the brief, with reasons

- **`shopt -s promptvars` forced, and `shopt -p promptvars` included in `H`.** Without
  `promptvars`, bash prints `PS0` literally and never runs its `$(...)`, so no `S` record
  is written. Under decision 5 every command would then look like "nothing ran" on a
  healthy session — exactly what (f)'s `PS0=` case guards against, through a different
  door. Test `test_changed_hooks_degrade[promptvars-off]`. The spec §3 `H` wording names it.
  The human may want to confirm this is within "H covers … PS0".
- **`F` is sent in every snapshot.** The old reference sent it only when a `cksum` kept in a
  shell variable changed; a command could set that variable and hide a new function, and
  the cksum also breaks decision 4. Spec §2 row updated ("function names, one per line").
  The remaining open question ("hash plus diff") is left as is.
- **The user's `PROMPT_COMMAND` is saved as an array** (`__nls_user_pc=("${PROMPT_COMMAND[@]}")`)
  and each element is run, with `$?` restored before each. bash ≥ 5.1 allows an array
  `PROMPT_COMMAND`; saving `$PROMPT_COMMAND` would keep element 0 only.
- **Spec §2 F/L rows changed** (not only §3/§4): leaving them saying "space-separated" /
  "joined with `\x1e`" would contradict decision 4's single encoding.
- **A test that the spec's §1.3 reference block equals `RCFILE`** (minus its header line),
  so the two cannot drift.
- `run()` raises `SessionDegraded` in degraded mode instead of running anything. Spec §4.3
  says commands in degraded mode need a confirm; this child has no REPL, and with the hooks
  broken it cannot report completion, so refusing is the conservative choice. The REPL
  (#78) can call `restart()`. When degradation is found only in the snapshot after a
  complete `D` (H changed), the exception carries the command's `result`.

### API summary (for #78 / child-2)

`Session.start(timeout=, env=, cwd=, dimensions=, on_record=, max_output=)`,
`run(cmd, timeout=) -> CommandResult(seq, ran, status, pipestatus, output,
output_truncated, snapshot, variables_changed)`, `interrupt()`, `restart()`, `close()`,
properties `degraded`, `degraded_reason`, `baseline`, `snapshot`, `pid`.
Exceptions: `CommandRefused` (nothing written), `SessionDegraded(reason, result)`,
`SessionTimeout` (also degrades).

## Accepted fail-closed limit (brief: "say so in build-notes")

The back-at-a-prompt rule (spec §4.2 third trigger) is purely: no `D` yet, and
`os.tcgetpgrp(master) == bash pid` continuously for 1 s. A command that runs inside bash
itself for longer than 1 s — `read x`, `wait`, `while :; do :; done` with only builtins,
`sleep` as a loadable builtin — keeps bash in the foreground and **degrades the session**.
That is by design and is stated in the spec §4.2 and the threat model's Known gaps. The
earlier attempt (iteration-v3) read `/proc` to exclude a busy bash; I did not carry that
over, because the brief defines the rule without it and it adds a Linux-only heuristic.

Also: the window between writing the paste and readline accepting it is bash-in-foreground
time too. On a loaded host that could approach 1 s for a very large paste; not seen here.

## What I tried / ruled out

- `builtin local st=$? ps=(...)` — bash refuses array assignment through `builtin local`
  (syntax error at rcfile load). Plain `local` it is; a function named `local` is part of
  the decision-2 Known gap.
- Output boundaries: I use readline's "bracketed paste off" (`ESC[?2004l`), which readline
  writes when it hands the line to bash, as the start of the command's output, and the
  arrival of `D` (plus a drain of what the PTY holds) as the end. This is not prompt
  parsing — it never decides completion, which comes only from fd 3. The prompt printed
  after `E` could, in theory, be drained with the output on a very fast bash; the hook's
  several `$(...)` forks happen between `D` and the prompt, and 4 full runs showed no leak.
- Dropped from iteration-v3 as out of scope (child-2): raw mode, keystroke forwarding,
  mirroring, alternate-screen capture, SIGWINCH, terminal restore. Also dropped its
  `tr`/`cksum` hook, CRC `H`/`V`, `\x1e` encoding and "D without S → degraded" (the
  rejected approaches the brief names).

## Verification

Runner: the project's C4 gate, `engine/scripts/run-verify.sh` with `PDCA_BUNDLE` and
`PDCA_WORKTREE` set (instance `.venv`, ptyprocess 0.7.0, host bash 5.3.9):

```
55 passed in 11.69s      (pytest exit 0; ran 55, failed 0)
55 failed in 0.54s       (pytest exit 1; ran 55, failed 55, setup errors 0)
PDCA-EVIDENCE: C4 PASS — red without the fix (55 of 55 failed), green with it
```

T3 (`engine/scripts/run-suite.sh`): `232 passed`, T3 PASS. T2 threat-model touch: satisfied.
Docs CI scripts on a temporary local commit: `docs_checks.py immutability` OK,
`docs_links.py` 0 broken. The session tests ran 4 times in a row with no flake (~11.7 s).

The first C4 run had the session import in the fixture, so 51 tests *errored* in setup
instead of failing; I moved the import into the factory the test body calls, giving 55/55
real failures.

### Refuting my own test

- **(a) Genuine red?** Yes. With every non-`tests/` file reverted, all 55 tests ran and
  failed (`ModuleNotFoundError` inside each test). Beyond that, targeted mutations of the
  production code each turned the matching tests red, then restored:
  no LF escape in `__nls_enc` → 3 round-trip tests red; no forced bracketed paste → the
  bashrc vi-mode test red; `promptvars` removed from `H` → its test red; the 1 s prompt
  rule disabled → vector 8 and unclosed-quote red; "D without S" made to degrade → 3
  not-run tests red; user `PROMPT_COMMAND` dropped → bashrc test red; `P` computed through
  `command tr` → the `tr` fake tests red (marker file created).
- **(b) Production path?** Yes. Every session test starts the real `nl_shell.session.Session`
  (real bash 5.3.9 on a real PTY via ptyprocess, the real `RCFILE`, the real fd-3 pipe).
  The only spy is in vector 12, which wraps the module's own `_write_all` and still calls
  it. Parser tests call `nl_shell.pty_protocol` directly.
- **(c) Fixture includes the fault?** Yes. The faults are injected for real inside the live
  bash: `PROMPT_COMMAND=:`, `exec 3>&-`, `PS0=`, `shopt -u promptvars`, an array
  `PROMPT_COMMAND`, fake `tr`/`cksum`/`wc` executables via `hash -p`, `BASH_CMDS` and a
  `PATH` prefix (with a marker file that must stay absent), a real `~/.bashrc` turning
  bracketed paste off with `set -o vi`, a real SIGINT through the PTY line discipline, a
  real stopped job (`kill -STOP`). Nothing is curated out.

## Housekeeping

No formatter or lint hook is configured in the target (no `.pre-commit-config.yaml`; CI
runs only tests and docs checks), and neither `ruff` nor `pyflakes` is installed here. I
kept lines ≤ 100 chars, except `session.py:83`: the `PS0=` line inside the rcfile string
is shell text and wrapping it would change what bash runs. Scratch backup files `.session.bak`
and `.proto.bak` are untracked in the worktree and are not in `patch.diff`.

Not pushed, no PR opened.

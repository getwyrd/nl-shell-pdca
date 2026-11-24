# Build notes — issue 101 / persistent-bash-session-core (re-plan, Do round 1)

All `path:line` references are on the patched tree built on `c47c5c2` (current `main`).

## Read this first: the base

The worktree the harness gave me was checked out at `8c95e05` (the stale
`pdca-integration/main-r2546dbf9639f` named in this bundle's `stack-base`). The brief's
Ordering note says to build on `c47c5c2` and that `stack-base` "must be cleared or
re-resolved to `main` before Do". It was not cleared: `stack-base` still names the old
integration branch and `stack-base-tip` is still `8c95e05`.

I moved the worktree to `c47c5c2` (`git checkout --detach c47c5c2`) and built there.
`patch.diff` applies cleanly to `c47c5c2` and does **not** apply to `8c95e05`
(`docs/design/specs/pty-protocol/v1.md` differs: #131/#132/#133 are missing there). Checked
with `git apply --cached --check` against a temporary index of each tree.

**Action for the human:** clear or re-resolve `stack-base` to `main` before Check's gates
run. If the driver exports `PDCA_VERIFY_BASE` from it, the C4 gate will report "patch does
not apply — stale" for a reason that has nothing to do with the patch. When I ran the gate
myself with `PDCA_BRIEF_BASE=origin/main` (= `c47c5c2`) it passed (below).

## What the change does

New `src/nl_shell/session.py` and `src/nl_shell/pty_protocol.py`, `ptyprocess>=0.7` in
`pyproject.toml:15`, `tests/test_session.py` (99 tests), and the doc edits the brief lists.
The parser and much of the Python I/O loop are reused from `iteration-v3/patch.diff`. The
rcfile, the outside checks, the prompt rule and the check point are new.

### Invariant I2 — no guard variable decides whether `S` is sent

- `PS0` (`session.py:133`) writes `S n+1` for **every** line bash reads, with no guard. The
  tracker accepts a repeated `S n+1` while it waits for `D n+1`
  (`pty_protocol.py:251-252`); any other number degrades. This is the fix the v3 adversary
  proposed ("emit `S n` on every PS0 expansion and have the tracker accept repeated
  `S n`").
- Consequence for criterion (d), "exactly one S/D pair": a multi-line command now produces
  several identical `S 1` records and one `D 1`. The test counts *distinct* start numbers
  (`_pairs`, and `test_one_start_done_pair_per_command` also asserts every `S` is `S 1`).
  The spec says so (§2 table, §4.1). I read "one pair" as one start number and one done
  record. If the human reads it as "one `S` record on the wire", the only way back is a
  shell-side guard, which is exactly what I2 rejects.
- Every hook variable is a global named `__nls_*` (no `local`: a readonly global of the same
  name would make `local` fail). `HOOK_STATE_VARS` (`session.py:67`) lists all 14 names,
  functions included, and `H` reports for each whether it is a variable and with which
  attributes. The test checks the list against the rcfile text both ways and parses the
  rcfile for any non-`__nls_` variable it reads or writes, against a fixed list of bash's
  own (`PIPESTATUS`, `PATH`, `PROMPT_COMMAND`, `PS0`, `PS1`, `PS2`, `HISTFILE`).

### Invariant I3 — everything that runs at prompt time runs before the snapshot

- Order (`session.py:142-198`): `__nls_done` saves `$?`/`PIPESTATUS`, writes `D`, runs
  the user's saved `PROMPT_COMMAND`, sets `PS1`/`PS2` to fixed values (`:152`). Then
  `PROMPT_COMMAND` (`:198`) lists the traps **at its top level** and passes them as
  arguments to `__nls_snap`, which writes F L T B X P J H V and `E`.
- Why traps are listed at the top level: I found that bash **hides `DEBUG`, `RETURN` and
  `ERR` traps inside a function**. Both `trap -p DEBUG` and `$(trap -p)` print nothing for
  them when run inside a function without `functrace`/`errtrace` (live, bash 5.3.9). So
  v3's `T` and `H` never contained them, and policy-gate §7.5 item 5 ("`T` MUST show no
  `DEBUG`, `RETURN` or `ERR` trap…") could not have worked on v3's `T`. Also checked live: a
  `DEBUG` trap runs *before* the arguments of the command are expanded, so it cannot remove
  itself from the capture and then act. (If it removes itself, there is nothing left to act
  after the snapshot.)
- `PS1`/`PS2` are set **before** `H` and are part of `H`. Decision 6 says "after the
  snapshot"; I put them just before it, because nothing runs in between and this way a
  `readonly PS1='${ … }'` (assignment fails) changes `H` and degrades. That is stricter than
  the literal wording, not weaker.
- `xtrace` is turned off at the start of `__nls_done`, again after the user hook (it may turn
  it on), and back on as the last command of `__nls_snap` (`:144`, `:151`, `:196`). With
  bash 5.3's `${ cmd; }`, a `PS4` can run `bind` in the shell itself. PS4 now last runs
  for the traced call of the hook, before the snapshot, so `H` sees it
  (`test_xtrace_ps4_acts_only_before_the_snapshot`).
- `PROMPT_COMMAND` calls the hooks as `\__nls_done`, `\__nls_snap` and `\builtin`, so an
  alias with those names does not apply.

### Table A — `H` (`session.py:164-190`)

`declare -p PROMPT_COMMAND PS0 PS1 PS2 __nls_user_pc`; for each `HOOK_STATE_VARS` name, its
`declare -p` text up to `=` (attributes only, since several change value every prompt), or
"`NAME unset`"; the `DEBUG`/`RETURN` trap text from the top-level argument; `shopt -p
extdebug promptvars`; `functrace`, `histexpand`, `emacs`, `vi` on/off; **all** of
`bind -v`; for `emacs`, `vi-insert`, `vi-command`: `bind -p`, `-s`, `-X`; `declare -f` of
the four hook functions. It is about 32 KB per snapshot. Every "detect" row in (h) is a
parametrized case of `test_table_a_changes_degrade_at_their_own_snapshot`. That test asserts
`SessionDegraded.result is not None` with `seq == 1`, i.e. the problem was found in *that*
command's snapshot and not by a later rule, and that the following `run("echo hello")`
writes nothing to the PTY.

- I dropped v3's `readonly -f` on the hook functions. With it, "redefining one of nl-shell's
  hook functions" (h) fails silently and never degrades. Without it the redefinition
  succeeds and `H` catches it.
- Side effect of "ALL readline variables": `HISTSIZE=…` changes `bind -v`'s
  `history-size`, so it degrades. A change to `LC_ALL` could also change readline variables
  or `declare -p` quoting. Both fail closed. I did not exclude anything from `bind -v`,
  because the brief says all of it.

### Table B and decision 8 — the outside checks and the check point on fd 4

This is the one mechanism the brief did not spell out, so here is why it is needed.

- I measured (live PTY) that readline, while it waits for a line, forces `ISIG` on (and
  `ICANON`/`ECHO` off). So after `stty -isig`, `tcgetattr` taken at the prompt is
  **identical** to the baseline's: criterion (j)'s `stty -isig` cannot be detected
  "immediately before the paste". It is only visible while bash is *not* in readline.
- "When each snapshot's `E` arrives" is racy if done passively. Bash may already be in
  readline when nl-shell reads `E`, which gives the prompt settings again. Also, while the
  hook runs `builtin printf … >&3`, bash has temporarily `dup2`ed fd 3 onto fd 1, so a
  `/proc/<pid>/fd/1` read at that moment shows the pipe.
- So after `E` the hook blocks in `builtin read -r -t 10 -u 4 __nls_ack` (`session.py:195`)
  on a second pipe (read end = bash's fd 4, write end kept by nl-shell; wired in
  `wire_fds`, `:422`). `Session._check_point` (`:648`) waits until `/proc/<pid>/syscall`
  shows bash blocked on fd 4. That is `pselect6` with nfds 5 (measured; `read -t` does not
  block in `read`). Then it compares the hook-time ("cooked") termios and fds 0–4 with the
  baseline's, checks the process state, and writes one line to fd 4. If bash shows up
  waiting on fd 0 instead, or doesn't stop within 3 s, the check can't be trusted and the
  session degrades.
- Before every paste, `_check_before_paste` (`:690`) waits for bash to be in readline's
  wait (`pselect6`, nfds 1). It then compares the prompt-time termios with the prompt-time
  baseline (recorded at start-up once bash first waits for a line) and checks fds 0–4. This
  also closes a latent v3 race: v3 could write the paste while bash was still in its hook,
  and then the line discipline would handle the bytes in canonical mode, where `DEL`
  (0x7f, which §5 lets through) erases a character.
- TIOCSTI (`_check_tiocsti`, `:476`): reads `tiocsti_path` (keyword, default
  `/proc/sys/dev/tty/legacy_tiocsti`, `:335`). Anything but `0`, or a read error, means
  `start()` returns a **degraded** session whose reason names the path. It does not raise.
- Stopped bash: `/proc/<pid>/stat` state `T`/`t` is checked on every loop pass, at the
  check point and before a paste (`_stopped`, `:738`).

Alternatives I rejected, with their cost:
- *Sample termios when `D` or `E` arrives and hope bash is still in the hook.* No new fd,
  but it is a race. It would also need logic to tell cooked from prompt-time samples, and
  the `printf >&3` fd swap makes the fd check give false alarms. It can't meet (j)
  reliably.
- *Sample when `S` arrives* (readline has restored the cooked settings before `PS0` runs).
  That is after the paste has been written, so it can't stop the command, and the command
  itself (vim, less, ssh, `read -s`) may already have changed termios: false degrades on
  ordinary use.
- *Pipe back-pressure* (shrink fd 3 to 4 KiB with `F_SETPIPE_SZ` and rely on the ~32 KB `H`
  to make bash block before `E`). Deterministic only through an argument about record
  sizes, and fragile.
- The fd-4 check point costs one extra pipe (`session.py:419-447`), one rcfile line
  (`:195`), about 40 lines of `_check_point` and the helpers, and one spec paragraph (§3
  "Outside checks", `v1.md:197`). The spec now says fd 4 exists (§1.1). This is a
  protocol addition to a `draft` spec. **Sign-off should confirm it**, since the brief did
  not name it.

### Prompt rule (decision 7)

`_is_fd_wait` (`:762`) reads `/proc/<pid>/syscall`: `read(0,…)`, or
`pselect6`/`select` with nfds 1. The syscall numbers are tabled for x86_64 and aarch64
(`_SYSCALLS`, `:228`). On another architecture the check point never matches and
`Session.start()` raises `SessionDegraded`. That is fail-closed, and the threat model's
Linux-only bullet (#138) covers it. Live: `x=$(sleep 2)`, `cd "$(sleep 1.5; …)"` and
backticks stay healthy; `read x` and an unclosed quote degrade after 1 s; `PROMPT_COMMAND=:`
degrades by this rule.

### Degraded = no more pastes (decision 10)

`run()` raises before any write when degraded (`:533`). `interrupt()` writes only in the
`RUNNING` phase, never when degraded. The tests check "nothing written" by spying on
`session._write_all`, the module's only PTY writer.

## Docs

- Spec `pty-protocol/v1`: §1.1 (fd 4), §1.2 (user `PROMPT_COMMAND` before the snapshot,
  `PS1`/`PS2`, line editing and bracketed paste forced), §1.3. The reference rcfile is
  generated from `RCFILE`, and `test_spec_reference_rcfile_is_the_one_in_use` keeps them
  equal. Also §2 (repeated `S`, encoding), §3 (`H`/`V` exact text, what `H` covers, the
  outside checks), §4.1, §4.2 (all triggers), §4.3 (decision 10), Conformance vector 8
  (`:318`), the vectors note, and the open question closed (`:334`).
- **Vector 8 wording differs from the brief's literal text.** The brief says vector 8
  becomes "degraded at that command's snapshot (`H` changed)". But `PROMPT_COMMAND=:`
  removes the hook, so no snapshot is ever written; the session degrades by the prompt
  rule. The row now says that, and adds that a `PROMPT_COMMAND` that still calls the hook
  but differs degrades at that command's snapshot (that is the "assigning
  `PROMPT_COMMAND`" case in (h)). I wrote what the code does rather than the brief's
  sentence.
- Policy-gate §7.5 items 5 and 6, ADR-0014 Decisions 1 and 2, ADR-0013 item 5: only the
  named sentences. Threat model: Known gaps for decision 2, #134, #135, #136, #137, #138,
  and a "How to exercise it" paragraph.
- `scripts/docs_checks.py immutability c47c5c2 <tmp commit>` → `docs-immutability: OK`;
  `scripts/docs_links.py` → 0 broken. (I made a temporary commit in the worktree to run the
  first, then `git reset --mixed c47c5c2`.)

## Things the human should know (not defects I could fix within the brief)

1. **(i) PS1 case: the session stays healthy.** The brief says "in both cases the session
   degrades". For the `PS1` case nothing can degrade: nl-shell replaces `PS1` before every
   prompt, so the user's `PS1` (from `~/.bashrc` or confirmed) is never expanded. The test
   accepts either degrade-and-refuse, or healthy with exact output **and** `\C-m` still
   bound to `accept-line` (if `PS1` had run, `H` would have changed). No marker in either
   case. The PS4 variant of the same attack does run, and degrades at its own snapshot.
2. **A crafted `DEBUG` trap can still forge `H`** if it also turns on `extdebug` and
   `functrace`: it can then skip the hook's own commands inside the `H` subshell. I listed
   this under the deliberate-subversion Known gap. A plain `trap … DEBUG` is detected (h).
3. **Signal traps.** Measured: a `USR1`/`CHLD` trap does *not* run while readline waits.
   It runs once the next line has been read, just before that command runs. So it can't
   change the paste bytes (I1 holds), but it can define a function just before the
   confirmed command runs. Traps are in `T` for the gate (#12). Not a session-degrade row in
   Table A, and not added.
4. **User `PROMPT_COMMAND` output can leak into captured output.** The hook writes `D` and
   then runs the user hook. nl-shell drains the PTY right after reading `D` (to catch the
   command's last bytes still in the tty buffer), and that drain can include what the
   user hook printed. Example: Ubuntu's `/etc/bash.bashrc` (read by Ubuntu's bash even with
   `--rcfile`) installs VTE's hook when `VTE_VERSION` is set, and that hook prints an OSC
   sequence. Over-inclusive only. The test fixture unsets `VTE_VERSION` so exact-output
   asserts don't depend on the developer's terminal.
5. With `set -x` on, the trace lines of the hook's first command show up in captured
   output. Cosmetic.
6. Interactive `set -e` followed by a failing command ends bash (normal bash behaviour); the
   channel closes and the session degrades. The hooks themselves are safe under `set -e`
   (`test_errexit_does_not_break_the_hooks`).

## Refutation — answered

**(a) Genuine red? Yes.** With `session.py` and `pty_protocol.py` moved out of the tree:
`99 failed in 1.24s`, 0 errors. I moved the spy fixture's import into the test bodies after
a first run showed 37 setup errors. Then the project's own C4 gate, run as
`PDCA_BUNDLE=… PDCA_WORKTREE=… PDCA_BRIEF_BASE=origin/main engine/scripts/run-verify.sh`:
`PDCA-EVIDENCE: C4 PASS — red without the fix (99 of 99 failed), green with it`, rc 0.

Module presence alone proves little, so I also broke one defence at a time (each restored
afterwards; `cmp` against a backup confirmed it):

| Mutation | Result |
|---|---|
| tracker rejects a repeated `S n+1` | multi-line / here-doc / function cases red |
| no hook-time termios comparison | `stty -isig` and `stty intr` cases red |
| traps listed inside the function (v3 style) | `trap ':' DEBUG`, `trap ':' RETURN`, `set -o functrace` cases red |
| user `PS1` not replaced | `test_user_ps1_never_runs` red (marker created) |
| no pre-paste outside check | background-job `stty` case red |
| `bind -v` removed from `H` | `convert-meta on` and bracketed-paste-off cases red |
| no stopped-state check | both `kill -STOP` cases red |
| v3-style `PS0` guard variable put back (attribute check off) | `test_hook_state_attacks_never_hide_a_command[readonly]` red: the probe showed exactly v3's symptom, `ran False, status 7, output ''`, healthy |
| attribute lines removed from `H` (no guard) | stays green: with no guard variable, nothing about `S` depends on them. They are a second layer, not the I2 fix |

The I2 attacks first used bare `readonly NAME` and `NAME=1`, which did **not** catch the
guard mutant. I changed them to the v3 reproducers' form (assign the sequence number the
guard would need), and then they did.

**(b) Production path? Yes.** Every session test starts the real `Session` from
`nl_shell.session` on a real bash 5.3.9 via ptyprocess, and the rcfile under test is the
production `RCFILE`. The only test double is a spy wrapped around `session._write_all`
that records the bytes and then calls the real function. The protocol-only tests drive the
production `ProtocolTracker`/`parse_record`.

**(c) Fixture includes the fault? Yes.** Each attack is actually executed in the live
session: real `stty`, real `bind` macros that `touch` a marker, real `exec >/dev/null`, a
real `kill -STOP $$` from a background subshell, a real `~/.bashrc` in the suite's
temporary HOME with a hostile `PROMPT_COMMAND`/`PS1`, real `hash -p`/`PATH` fakes. The
TIOCSTI case is simulated through the `tiocsti_path` keyword, which is the same file read
the production default uses (the host really has `0`, which `test_tiocsti_off_is_healthy`
also exercises).

## Runs

- `tests/test_session.py`: 99 passed (about 50 s), three times; once more with every CPU
  busy (`nproc` busy loops): 99 passed in 77 s.
- Whole suite: 276 passed.
- `git diff --check` clean. No formatter or pre-commit hook is configured in the target
  (no `.pre-commit-config.yaml`, nothing in `pyproject.toml`; CI runs pytest and the two
  docs scripts). New lines are ≤ 100 columns. No linter is installed, so I checked imports
  by reading them.
- Scratch files (`.scratch/` in the worktree: probes, mutation scripts, backups) are
  untracked and not in the patch.

No external dependency beyond the brief's list (`ptyprocess`, `proc-syscall`,
`tiocsti-off`, `ptrace-scope`) was needed.

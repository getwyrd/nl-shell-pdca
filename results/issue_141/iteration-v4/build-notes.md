# Build notes — issue 141 (persistent-bash-session tamper checks), round 4

Target: `pdca-integration/main-r2546dbf9639f` @ `0771812` (worktree `$PDCA_WORKTREE`).
"base:" line numbers are on `0771812`; "patched:" line numbers are in the patched tree.

## What changed and why

### The reading point (the v3 defect, the invariant)

v3 read the terminal at `D`. On the base, code that is not nl-shell's runs after `D`: the
user's `PROMPT_COMMAND` elements (base `session.py:126-131`, after the `D` write at `:125`)
and a top-level DEBUG trap, which fires before each simple command of the hook element
(base `session.py:177`), i.e. before `\__nls_done` and before `\__nls_snap …` (bash runs
the DEBUG trap before word expansion, so after its last firing only the expansion of
`\__nls_snap`'s arguments and the function body run).

So the hook-time reading is now the hook's very last step: after `E`, `__nls_snap` blocks
in `\builtin read -r -u 4 __nls_v` (patched `session.py:243`). nl-shell waits until
`/proc/<pid>/syscall` shows bash itself blocked in `read(4, …)` and `/proc/<pid>/fd/4` is
its own pipe (patched `_wait_for_hook`, `session.py:886`), reads termios through the
master and fds 0/1/2 through `/proc/<pid>/fd` + `fdinfo` (`_read_termios`, `_read_fds`,
`session.py:961`), compares them with the readings taken at the same point at the first
prompt, and writes the one line bash waits for only if they match (`_hook_check`,
`session.py:850`; called on every `E` at `session.py:679`, and at start in `_spawn`).
If they don't match, or `H` differs, nl-shell never writes the line: bash stays blocked
in its hook and readline never takes the terminal again. This also means code a
confirmed command appends after nl-shell's `PROMPT_COMMAND` element, or puts in a
readonly `PS1`, no longer runs once after the degrading snapshot (spec §1.3 text
updated accordingly).

No new record type was needed: `E` is the trigger (allowed edit (1) "any new record or
handshake"; the handshake is fd 4). `pty_protocol.py` gets only the reason codes.

Why `H` itself is not fooled by code that runs after it:
- **DEBUG/RETURN traps are invisible inside an untraced function.** Experiment
  (`t5.sh` in the scratch dir): inside a function, `$(trap -p DEBUG RETURN)` prints
  nothing even with both traps set (bash saves/clears them around untraced function
  calls); at top level it shows them. So `trap -p DEBUG RETURN CHLD` is read at the top
  level of nl-shell's element and passed in as `$3` (patched `session.py:247-248`), after
  the last DEBUG firing for that element, then written into `H` (`session.py:198`).
- **functrace makes the substitution that reads the traps inherit the DEBUG trap**, which
  can then remove itself only in the subshell and print nothing (experiment `t1.sh`:
  `T-on sub: []`). `$-` is expanded in the same simple command (`"${-//[!T]/}"`, passed as
  `$4`), in the parent, after that subshell; so any functrace that is still on at that
  point shows in `H`. With functrace off, a command substitution does not inherit the
  trap even from a function with the trace attribute (experiment `t2.sh`).
- **functrace on at the baseline** (`set -T` or `extdebug` in `~/.bashrc`) would let a
  later DEBUG trap hide itself while `$-` matches the baseline. Rather than a `set +T`
  dance (needs a new hook state variable carried from `__nls_done` to `__nls_snap`, ~4
  rcfile lines plus a `HOOK_STATE_VARS` entry, and still needs the `$-` check for the
  trace-attribute case), the session starts degraded (patched `session.py:563`, code
  `other`). Not in the brief; it closes a hole the invariant forbids. Test:
  `test_bashrc_functrace_starts_degraded` (`tests/test_session.py:1420`).
- **CHLD trap** (beyond the brief's list): a confirmed `trap X CHLD` runs X each time one
  of the hooks' `$( … )` children is reaped — measured 13+ times per hook (`t7.py`:
  `ccccccccccccccccccccccccccc` for two commands), including after `H` is read. That is
  non-nl-shell code inside the hooks after the snapshot with no outside sender needed, so
  CHLD joins DEBUG/RETURN in `H`. Test `test_chld_trap_cannot_bind_enter_after_the_snapshot`
  (`tests/test_session.py:1123`) binds Enter only from the 4th firing on: red on the base
  (marker path), green now. Traps on other signals need an outside sender (a background
  job's `kill`) and stay reported in `T` (brief: `T` reported only); documented as a gap.
- `declare -pF` of the hook functions (attributes such as `-t`) — small extra `H` row.

### H rows (Table A) — patched `session.py:183-245`

`PS4` in the `declare -p` line; `shopt -p extdebug`; `shopt -po emacs vi functrace xtrace
histexpand`; traps + `$-` line; `BASH_XTRACEFD` in the `declare -p` loop; `declare -pF`;
the disabled hook builtins via `compgen -A disabled -X "!name" -- name` per name (no
inner substitution, so a disabled `compgen` shows its error in `H`); `bind -v` minus the
`history-size` line (parameter expansion only); `bind -p/-s/-X` for five keymaps.
Every `$( … )` in the hooks now ends in `2>&1` (base `:139`, `:151`, `:159`, `:177`, plus
F/L/B/X/J). Side effect: for unset names `H`/`V` now carry `bash: declare: X: not found`
before `X unset`; stable, and #140's `"LD_PRELOAD unset" in …split("\n")` still holds.

`readonly PS4` right after `unset HISTFILE` (patched `session.py:147`). Experiment `t4.py`:
an assignment to a readonly variable aborts the rest of the interactive line, so in (r)'s
first case `set -x` never runs and the degrade comes from `BASH_XTRACEFD` (`h-changed`),
as the brief predicted.

`HOOK_BUILTINS` (patched `session.py:84`) is a literal tuple; the rcfile loop lists the
names quoted (`'read' 'return' …`). Unquoted, #140's `test_hook_state_vars_cover_the_rcfile`
regex `\bread\s+…([A-Za-z_]\w*)` read `read return` as a `read` into a variable `return`
(it failed on the first run); quoting also stops `builtin <name>` from appearing in the
list text for (s)'s regex.

### Disabled hook builtins — what really happens (probe `en.py`)

| name | outcome | time |
|---|---|---|
| `:` alias bind compgen declare enable eval jobs read return shift shopt trap | `h-changed` | 0.04 s |
| `printf` | `missing-record` (no records; prompt rule) | 1.06 s |
| `builtin` | `missing-record` | 1.88 s (was ~12 s, see below) |
| `set` | **`other`: "malformed control record: malformed D record: 'D 1  '"** | 0.00 s |

- `builtin`: Ubuntu's `/etc/bash.bashrc` (sourced even with `--rcfile`) defines
  `command_not_found_handle`, which runs `/usr/lib/command-not-found` (~85 ms). With
  `builtin` disabled every `\builtin X` in the hooks runs it: ~12 s per hook, beyond (s)'s
  5 s. Fix: `__nls_snap`'s body is wrapped in `if \builtin set -- …; then … fi` (patched
  `session.py:184`), so when its first builtin call fails the hook skips everything and
  bash goes to readline; the prompt rule fires in ~1 s. Also: E is written as
  `\builtin printf 'E\n' >&3 || __nls_v=x` and the fd-4 wait only runs if E was written
  (`session.py:240-243`), so with `printf` disabled the hook does not block forever.
- `set` — **divergence from the brief.** The brief expects `h-changed` or `missing-record`
  for every hook builtin. Disabling `set` breaks `__nls_done`'s first line
  (`\builtin set -- "$?" "${PIPESTATUS[@]}"`, base `session.py:116`), so `$1` is empty
  and the `D` record is `D 1  ` — malformed, degraded by #140's parser site
  (`pty_protocol.py:211`, untagged → `other`). That line is before `D`, outside the
  allowed edits, and the brief says untagged #140 sites keep `other`. The test keeps a
  separate module-level tuple `_MALFORMED_DONE_BUILTINS = ("set",)`
  (`tests/test_session.py:1364`) expecting `other` and the "malformed control record"
  reason; `_NO_RECORD_BUILTINS = ("builtin", "printf")` (`:1361`) expect `missing-record`.
  Sign-off should decide whether that is acceptable or whether a later slice may touch the
  pre-D line.

### Prompt rule extended to the fd-4 wait

With the hook blocking on fd 4, `exec 3>/dev/null` (records written into /dev/null, E
"succeeds") would leave bash blocked in `read(4)` forever and `run()` without timeout
would hang — a regression of #140's prompt rule. `_wait_for_result` now treats "blocked
reading fd 4 with no E yet" like "blocked reading the terminal" (patched `session.py:704`),
with the same reason text and `missing-record` code.

### Pre-paste reading (b), stopped, TIOCSTI

- `run()` (patched `session.py:641-646`): after `_wait_for_prompt`, `_check_stopped()`
  then `_prompt_check()` (`session.py:925`) compares the full `tcgetattr` list with the
  first prompt's reading in the same (readline) state, and fds 0-2 with the baseline.
- `_check_stopped` (`session.py:1007`) parses `/proc/<pid>/stat` after the last `)`;
  called before every paste, on every poll tick of `_wait_for_result` (after the prompt
  rule, so #140's tests that fake `/proc` keep their reason text naming `syscall` /
  `fd/0`), in `_wait_for_prompt`'s loop and in `_wait_for_hook`. While stopped in
  `pselect6`, `/proc/<pid>/syscall` still reads as "reading the terminal", so the
  pre-paste stopped check is what refuses that case.
- `_check_tiocsti` (`session.py:1029`) at the end of `_spawn`; `tiocsti_path` keyword,
  default `/proc/sys/dev/tty/legacy_tiocsti`.
- Reason codes: `ProtocolTracker.degrade(reason, code="other")` + `degraded_code`
  (`pty_protocol.py:165`, `:172-178`); tagged #140 sites `pty_protocol.py:276`
  (`missing-record`), `:302` (`h-changed`), `session.py:716` (`missing-record`),
  `session.py:1061` (`exited`); reason text byte-identical. `Session.degraded_code`
  (`session.py:597`), `SessionDegraded.code` (`session.py:317`), passed at every raise.
  The `ack` write uses `os.write`, not `_write_all`, so the tests' PTY write spy never
  counts it.

## Other divergences / things the human should know

1. **#140 test constant edited.** `tests/test_session.py:811` `_NLS_HOOK` mirrors the
   `PROMPT_COMMAND` element byte for byte. The brief requires stderr capture at base
   `session.py:177` (that element), and the DEBUG/RETURN/CHLD read had to move into the
   element (see above), so the constant had to change. Nothing else in #140's tests was
   touched; all of them are green. The brief says "new tests only; keep #140's" — this is
   a forced exception.
2. **Spec §1.1** (fd 4 in the start-up requirement) edited besides the brief's listed
   sections; needed for the handshake.
3. **Threat model:** the brief's named bullets, plus "a trap on a signal other than CHLD"
   folded into the first (gate) bullet, because that is a real route the patch leaves
   open (`T` reported only) and the brief forbids a catch-all; the #136 bullet uses the
   spec's own wording (`read -t 2`, `select`). ADR-0024 is cited as the brief asked, with
   ADR-0013 §2 where the class `session-altering` is defined.
4. **Tracker divergence** (from the brief): publish MUST say in the PR description that the
   issue body is out of date on `PS4` (now `readonly`, decision 3) and on `stty icanon/-echo`
   (now tested, (j)).
5. `(i)` PS1 case uses `${ __ps1_bind; }` (bash 5.3 no-fork substitution) so that, if it
   were ever expanded, the `bind` would land in the shell itself; on older bash it would be
   a bad-substitution error, still never expanded.
6. `convert-meta` row: the test flips whatever the baseline has; on this host (en_US.UTF-8)
   the baseline is `off`, so the brief's literal `bind 'set convert-meta on'` is what ran.
7. Not checked/claimed (for #145): `MAILPATH` messages are expanded by bash before the
   prompt; I did not establish whether that is before or after `PROMPT_COMMAND`.

## Rejected alternatives

- Reading at `D` or at `E` without a handshake: bash continues into readline right after
  `E`, so a reading races readline's prep (and at `D` it is v3's defect).
- A new control record for the handshake: `E` already marks "snapshot written"; a new
  type would need parser/sequencing changes for no gain.
- Bash 5.3 `${ cmd; }` to read traps without a subshell: the suite and threat model say
  bash ≥ 5.1.
- `set +T` around the `H` read instead of the start-degrade: cost given above.

## Refuting my own test

- **(a) Genuine red?** Yes. `PDCA_BUNDLE=… ./engine/scripts/run-verify.sh` (the C4 gate,
  which reverts the production hunks and keeps the tests): "PDCA-EVIDENCE: C4 PASS — red
  without the fix (48 of 148 failed), green with it", 0 collection errors. Inspected red
  messages: (h)/(h2)/(i)/(j) rows fail because `run()` returned a healthy
  `CommandResult` (e.g. `('stty -isig', CommandResult(seq=1, ran=True, status=0, …`), the
  stopped test fails with "still blocked after 5.0 s", `exec >/dev/null` degrades on the
  base but with no `degraded_code` (wrong-code class), the tiocsti tests fail with
  `TypeError … 'tiocsti_path'` and (s) with `AttributeError` on `HOOK_BUILTINS` (API
  absent; the brief accepts per-test failure for these). Regression guards stay green on
  the red leg: (m), (p), (fa), `exec </dev/null`, the `é` guard, PS1-in-bashrc.
- **(b) Production path?** Yes. Every new test starts the real `Session` from
  `src/nl_shell/session.py` on a real bash 5.3.9 PTY (ptyprocess), and reads the real
  `RCFILE`/`HOOK_BUILTINS`. The only stand-in is the existing spy that wraps
  `_write_all` to count PTY writes; it still calls the real write.
- **(c) Fixture includes the fault?** Yes. The faults are real: real `stty` from inside
  real traps, a real `PROMPT_COMMAND` in a temp `~/.bashrc`, a real background job
  changing termios while readline holds the terminal, a real `kill -STOP $$`, real
  `enable -n`. The one simulated input is TIOCSTI (`tiocsti_path` pointing at a temp file
  holding `1`, or missing), as the brief prescribes; the host has `legacy_tiocsti = 0`.

## Runs

- T3 `./engine/scripts/run-suite.sh`: 385 passed (three runs, ~89 s each; base was 93
  session tests in 43.5 s, now 148). `H` is ~46 KB per snapshot; a simple `run()` takes
  ~40 ms.
- No external dependency was missing: `ptyprocess`, `/proc/<pid>/syscall` and `fd`
  readable (`ptrace_scope = 1`), `legacy_tiocsti = 0`, bash 5.3.9 on the host.
- Commit-readiness: the target has no formatter or linter configured (no ruff/black in
  `pyproject.toml`, no pre-commit config); I kept every added line ≤ 100 columns like the
  surrounding code, `git diff --check` is clean, `python3 scripts/docs_links.py` reports
  0 broken links, and the spec is `status: draft` (not frozen for `docs_checks.py
  immutability`).

## Housekeeping (my mistakes, for the human)

- An early `mktemp -d -p $PDCA_WORKTREE/..` created an empty directory
  `/home/eddie/nl-shell/tmp.9Avu9sZr34` outside my roots. I did not delete it.
- Probe scripts live in `$PDCA_WORKTREE/.scratch/` (untracked, not in `patch.diff`). One
  `rm -f out6.txt` ran inside it before I caught myself.

# Build notes — issue 141 (persistent-bash-session tamper checks), round 5

Target: `pdca-integration/main-r2546dbf9639f` @ `0771812` (worktree `$PDCA_WORKTREE`).
"base:" line numbers are on `0771812`; "patched:" line numbers are in the patched tree.

This round starts from the round-4 patch (`iteration-v4/patch.diff`, applied unchanged) and
fixes the two findings in the carry-forward. Everything round 4 did is kept; its notes are
repeated below, with line numbers updated, after the round-5 section.

## Round 5: what the carry-forward asked, and what changed

### 1. Bash's mail check ran code after the hook-time reading (Medium finding)

The finding is right. After `PROMPT_COMMAND` returns, bash checks mail (when `MAILCHECK`
is a number ≥ 0) and expands the text after `?` in each `MAILPATH` entry, so a `$( … )`
there runs after nl-shell's fd-4 reading and before readline takes the terminal. The
pre-paste reading cannot see `-isig` (readline turns ISIG on while it holds the
terminal). I reproduced it on the round-4 code with the new test (see "Red" below): the
paste `stty -a` was written and its output showed `-isig`.

Fix (the one the reviewer suggested first, smallest that removes the cause):

- patched `session.py:150` (and spec reference rcfile `v1.md:82`): right after
  `readonly PS4`, `unset MAILCHECK; readonly MAILCHECK`. Bash's own rule: if `MAILCHECK`
  is unset (or not a number ≥ 0) it never checks mail, so neither `MAILPATH` nor `MAIL`
  matters. A readonly variable cannot be unset or set again, so a confirmed
  `MAILCHECK=0` fails with "readonly variable" (checked: `bash -c 'MAILCHECK=5; unset
  MAILCHECK; readonly MAILCHECK; declare -p MAILCHECK; MAILCHECK=0'` prints `declare -r
  MAILCHECK` then `MAILCHECK: readonly variable`). `MAIL`/`MAILPATH` stay as they are
  for programs that read them.
- patched `session.py:197`: `MAILCHECK` added to H's `declare -p` line, as PS4 is, so if
  some path ever left it set the snapshot degrades `h-changed`.
- patched `session.py:304` `_MAILCHECK_OFF` and `:575-581`: if `~/.bashrc` made
  `MAILCHECK` readonly itself, the rcfile's `unset` fails and mail checks continue with
  the user's `MAILPATH`, whose message can call a function a confirmed command may
  redefine. The session then starts degraded (code `other`), the same pattern as the
  round-4 functrace check (`session.py:569`).

Why not move the reading after the mail check instead: there is no hook in bash between
the mail check and readline that nl-shell could block in (the mail check is the last step
of bash's prompt preparation; PS1 is expanded next, and PS1 is set to the fixed `\$ `).
Blocking in PS1's expansion would put a `$( … )` in PS1, which the hooks' design keeps
out. Carrying `MAILPATH` in H alone would not be enough either: a `MAILPATH` from
`~/.bashrc` that calls a function `f` is in the baseline, and a confirmed `f() { stty
-isig; }` changes only `F` (reported only). The `bashrc` row of the new test is exactly
that case.

User-visible change (documented in spec §1.2, `v1.md:61-66`): the session never prints
"You have mail", and `MAILCHECK=…` fails as readonly. Same kind of change as decision 3
(`readonly PS4`); the human should confirm it at sign-off.

Other pre-prompt steps I checked for code that runs after the reading (no bash source on
the host, so from bash's documented order plus experiment):
- PS1 expansion: `__nls_snap` sets PS1 to `\$ ` after E (`session.py:244`). If PS1 is
  readonly (from `~/.bashrc`), that assignment fails, which aborts the hook before the
  fd-4 wait, so the session starts degraded ("the shell did not wait on fd 4…",
  `outside-check`) — probe output: `True outside-check the shell did not wait on fd 4 for
  nl-shell's outside check at the end of its hooks`. A confirmed `readonly PS1=…` shows
  in H. New regression test `test_bashrc_ps1_the_hook_cannot_replace_cannot_change_the_terminal`
  (`tests/test_session.py:1198`) pins this; it is red on `0771812` but was already green
  on round 4, so it is a guard, not evidence for this round's fix.
- Job notices and `checkwinsize`: no user code. A CHLD trap: in H (round 4). Traps on
  other signals: known gap (threat model, round 4).

### 2. Disabled `set` degraded with code `other` (C5 finding)

Round 4 let `enable -n set` degrade through #140's malformed-record site (`D 1  `,
code `other`) and the test accepted `other`. The brief's (s) wants `h-changed`, or
`missing-record` for names whose disabling stops the records.

Fix: patched `session.py:167` (spec `v1.md:99`): `__nls_done`'s first line is now
`\builtin set -- "$?" "${PIPESTATUS[@]}" || \builtin return`. If `set` is disabled the
function returns before it writes anything; `__nls_snap` already does nothing when its
first `\builtin set` fails (`session.py:187`), so no `D`/`E` is written, bash reaches
readline, and the prompt rule degrades with `missing-record` (measured in the suite run:
well under the 5 s limit). `$?` and `PIPESTATUS` are expanded before `set` runs, so the
normal path is unchanged; `return` is already in `HOOK_BUILTINS`, so the (s) regex test
still matches.

This touches a line before `D`, which the brief's allowed edit (1) ("the hook order after
`D`") does not literally list. I judged it the smallest way to meet criterion (s) and the
carry-forward, which both require `missing-record`/`h-changed` for every hook builtin; the
alternative (computing `$?`/`PIPESTATUS` without `set`) rewrites more of #140's
`__nls_done` (the `__nls_pre` save sits between, and `$( … )` resets `$?`): ~5 changed
lines instead of 1. Flag for sign-off.

Test: `_NO_RECORD_BUILTINS = ("builtin", "printf", "set")` (`tests/test_session.py:1424`);
the `other` branch and `_MALFORMED_DONE_BUILTINS` are gone, so `set` must give
`missing-record`. Justification per name: `printf` writes every record; `builtin`
disabled makes every `\builtin …` a "command not found"; `set` disabled stops both hook
functions at their first line.

Spec: §1.2 bullet (`v1.md:69-72`) and the closing paragraph of §1.3's "What this
protects" (`v1.md:220-230`) now say `set`, `printf` or `builtin` stop the records and the
prompt rule degrades; the old "Disabling `set` makes the `D` record malformed" sentence
is gone. Spec §3 (`v1.md:275`, `:288-289`) names `MAILCHECK` in H and the mail check as off.

### New tests this round (`tests/test_session.py`)

- `_assert_next_paste_is_refused_or_has_signals_on` (`:1151`): the next paste `stty -a`
  is refused with zero PTY writes, or, if written, its output does not show `-isig`
  (readline gives the command bash's own settings, so this is what the paste ran with).
- `test_mail_check_cannot_change_the_terminal_after_the_hooks[confirmed|bashrc]`
  (`:1166`): the reviewer's reproducer (confirmed `MAILCHECK=0; MAILPATH='m?$(stty
  -isig)'`, then new mail), and the `~/.bashrc` variant (bashrc sets `MAILCHECK=0` and a
  `MAILPATH` message calling `__mail_msg`; the confirmed command redefines it to `stty
  -isig`).
- `test_bashrc_readonly_mailcheck_starts_degraded` (`:1188`).
- `test_bashrc_ps1_the_hook_cannot_replace_cannot_change_the_terminal` (`:1198`), guard.

## Refuting my own test (round 5)

- **(a) Genuine red?** Yes, both ways.
  - Against round 4's code (this round's fix not applied), via the project runner
    (`engine/scripts/run-suite.sh`): `3 failed, 385 passed` — both mail rows failed with
    "a paste was written with signals off" (`stty -a` output contained `-isig`, seq 3,
    written), and `test_disabling_any_hook_builtin_degrades` failed with `('set',
    'other', "malformed control record: malformed D record: 'D 1  '")`.
  - The C4 gate (`PDCA_BUNDLE=… ./engine/scripts/run-verify.sh`, reverts all production
    hunks to `0771812`, keeps the tests): `PDCA-EVIDENCE: C4 PASS — red without the fix
    (52 of 152 failed), green with it`, 0 setup and 0 collection errors. The new tests
    are among the 52 (both mail rows, readonly-MAILCHECK, the PS1 guard).
- **(b) Production path?** Yes. Every test starts the real `Session` from
  `src/nl_shell/session.py` with the real `RCFILE` on a real bash 5.3.9 PTY. The only
  stand-in is the existing spy around `_write_all`, which still calls the real write.
- **(c) Fixture includes the fault?** Yes. A real `MAILPATH` with a real `$( stty -isig )`
  message, a real mailbox whose mtime changes (`sleep 1.1; echo x >> mbox`), a real
  `~/.bashrc` in the suite's temp HOME; a real `enable -n set`.

## Runs (round 5)

- `engine/scripts/run-suite.sh` (T3): `389 passed in 96.67s`.
- C4 as above.
- Commit-readiness: the target has no formatter, linter or pre-commit config (none in
  `pyproject.toml`, no `.pre-commit-config.yaml`). `git diff --check` clean; no added
  line in `session.py`/`test_session.py` over 100 columns; `python3 scripts/docs_links.py`:
  0 broken links; the spec stays `status: draft`.
- No external dependency was missing.

## Housekeeping

- Probe files live in `$PDCA_WORKTREE/.scratch/` (untracked, not in `patch.diff`); this
  round added `.scratch/home/.bashrc`.
- While checking docs I ran `git add -N . && git reset -q` in the worktree; it only
  touched the index (intent-to-add of `.scratch/`, then removed). The working tree and
  `patch.diff` are unaffected (`git diff | cmp - patch.diff` matched after the C4 run).
- Round 4's stray empty directory `/home/eddie/nl-shell/tmp.9Avu9sZr34` is still there; I
  did not delete it.

---

## Round 4 notes (kept; line numbers updated to the round-5 patched tree)

### The reading point (the v3 defect, the invariant)

v3 read the terminal at `D`. On the base, code that is not nl-shell's runs after `D`: the
user's `PROMPT_COMMAND` elements (base `session.py:126-131`, after the `D` write at `:125`)
and a top-level DEBUG trap, which fires before each simple command of the hook element
(base `session.py:177`).

So the hook-time reading is now the hook's very last step: after `E`, `__nls_snap` blocks
in `\builtin read -r -u 4 __nls_v` (patched `session.py:246`). nl-shell waits until
`/proc/<pid>/syscall` shows bash itself blocked in `read(4, …)` and `/proc/<pid>/fd/4` is
its own pipe (`_wait_for_hook`, `session.py:899`), reads termios through the master and
fds 0/1/2 through `/proc/<pid>/fd` + `fdinfo` (`_read_fds`, `session.py:974`), compares
them with the readings taken at the same point at the first prompt, and writes the line
bash waits for only if they match (`_hook_check`, `session.py:863`; called on every `E`
at `session.py:692`, and at start in `_spawn`). If they don't match, or `H` differs,
nl-shell never writes the line: bash stays blocked in its hook and readline never takes
the terminal again.

No new record type: `E` is the trigger and fd 4 the handshake (allowed edit (1)).
`pty_protocol.py` gets only the reason codes.

Why `H` itself is not fooled by code that runs after it:
- DEBUG/RETURN traps are invisible inside an untraced function (experiment: inside a
  function `$(trap -p DEBUG RETURN)` prints nothing with both set). So `trap -p DEBUG
  RETURN CHLD` is read at the top level of nl-shell's element and passed in as `$3`
  (patched `session.py:201`, element at the end of `RCFILE`).
- functrace makes the substitution that reads the traps inherit the DEBUG trap, which
  could remove itself only in the subshell. `$-` is expanded in the same simple command
  (`"${-//[!T]/}"`, `$4`), in the parent, after that subshell.
- functrace on at the baseline (`set -T` or `extdebug` in `~/.bashrc`): the session
  starts degraded (`session.py:569`). Test `test_bashrc_functrace_starts_degraded`
  (`tests/test_session.py:1477`).
- CHLD trap (beyond the brief's list): runs each time one of the hooks' `$( … )` children
  is reaped, including after `H` is read, so it joins DEBUG/RETURN in `H`. Test
  `test_chld_trap_cannot_bind_enter_after_the_snapshot` (`tests/test_session.py:1123`).
  Traps on other signals need an outside sender and stay reported in `T`; documented gap.
- `declare -pF` of the hook functions (`session.py:208`).

### H rows (Table A)

`PS4` (and now `MAILCHECK`) in the `declare -p` line; `shopt -p extdebug`; `shopt -po emacs
vi functrace xtrace histexpand`; traps + `$-` line; `BASH_XTRACEFD`; `declare -pF`; the
disabled hook builtins via `compgen -A disabled -X "!name" -- name`; `bind -v` minus the
`history-size` line; `bind -p/-s/-X` for five keymaps. Every `$( … )` in the hooks ends in
`2>&1` (base `:139`, `:151`, `:159`, `:177`, plus F/L/B/X/J). Side effect: for unset names
`H`/`V` carry `bash: declare: X: not found` before `X unset`; stable, and #140's
`"LD_PRELOAD unset" in …split("\n")` still holds.

`readonly PS4` right after `unset HISTFILE` (patched `session.py:149`). An assignment to a
readonly variable aborts the rest of the interactive line, so in (r)'s first case `set
-x` never runs and the degrade comes from `BASH_XTRACEFD` (`h-changed`).

`HOOK_BUILTINS` (patched `session.py:84`) is a literal tuple; the rcfile loop lists the
names quoted so #140's `test_hook_state_vars_cover_the_rcfile` regex does not read `read
return` as a `read` into `return`, and so `builtin <name>` does not appear in the list
text for (s)'s regex.

### Disabled hook builtins (round 5 outcome)

| name | outcome |
|---|---|
| `:` alias bind compgen declare enable eval jobs read return shift shopt trap | `h-changed` |
| `printf`, `builtin`, `set` | `missing-record` (no records; prompt rule) |

`builtin`: Ubuntu's `/etc/bash.bashrc` (sourced even with `--rcfile`) defines
`command_not_found_handle` (~85 ms per call). `__nls_snap`'s body is wrapped in `if
\builtin set -- …; then … fi` (`session.py:187`) so it skips everything when `builtin` is
disabled; E is written as `\builtin printf 'E\n' >&3 || __nls_v=x` and the fd-4 wait only
runs if E was written, so with `printf` disabled the hook does not block forever.

### Prompt rule extended to the fd-4 wait

`exec 3>/dev/null` would leave bash blocked in `read(4)` forever and `run()` without
timeout would hang. `_wait_for_result` treats "blocked reading fd 4 with no E yet" like
"blocked reading the terminal" (`session.py:717`), same reason text, `missing-record`.

### Pre-paste reading (b), stopped, TIOCSTI, reason codes

- `run()`: after `_wait_for_prompt`, `_check_stopped()` then `_prompt_check()`
  (`session.py:938`) compares the full `tcgetattr` list with the first prompt's reading
  in the same (readline) state, and fds 0-2 with the baseline.
- `_check_stopped` (`session.py:1020`): before every paste, on every poll tick of
  `_wait_for_result`, in `_wait_for_prompt`'s loop and in `_wait_for_hook`.
- `_check_tiocsti` (`session.py:1042`) at the end of `_spawn`; `tiocsti_path` keyword.
- Reason codes: `ProtocolTracker.degrade(reason, code="other")` + `degraded_code`
  (`pty_protocol.py:165`, `:178`); tagged #140 sites keep their reason text
  (`missing-record`, `h-changed`, `session.py:729` `missing-record`, `session.py:1074`
  `exited`). `Session.degraded_code` (`session.py:610`), `SessionDegraded.code`
  (`session.py:323`). The fd-4 ack uses `os.write`, not `_write_all`, so the tests' PTY
  write spy never counts it.

### Other divergences / things the human should know

1. #140 test constant edited: `tests/test_session.py:811` `_NLS_HOOK` mirrors the
   `PROMPT_COMMAND` element byte for byte; the brief's stderr capture at base
   `session.py:177` and the trap read forced the change. Nothing else in #140's tests
   changed; all green.
2. Spec §1.1 (fd 4 in the start-up requirement) edited besides the listed sections.
3. Threat model: the brief's named bullets, plus "a trap on a signal other than CHLD"
   folded into the first (gate) bullet. ADR-0024 cited as asked, with ADR-0013 §2.
4. Tracker divergence (from the brief): publish MUST say in the PR description that the
   issue body is out of date on `PS4` (now `readonly`, decision 3) and on `stty
   icanon/-echo` (now tested, (j)). Round 5 adds a second user-visible change of the same
   kind: `MAILCHECK` is unset and readonly (no mail notices in the session).
5. Round 5 edits one line of #140's `__nls_done` before `D` (`|| \builtin return`), see
   section 2 above.
6. `convert-meta` row flips whatever the baseline has; on this host the baseline is `off`.

### Rejected alternatives (round 4)

- Reading at `D` or at `E` without a handshake: a reading races readline's prep (and at
  `D` it is v3's defect).
- A new control record for the handshake: `E` already marks "snapshot written".
- Bash 5.3 `${ cmd; }` to read traps without a subshell: the suite and threat model say
  bash ≥ 5.1.
- `set +T` around the `H` read instead of the start-degrade: ~4 rcfile lines plus a
  `HOOK_STATE_VARS` entry, and still needs the `$-` check.

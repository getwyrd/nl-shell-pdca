# Build notes — issue 141, round 6 (option B)

Target: `pdca-integration/main-r2546dbf9639f` @ `0771812` (worktree `$PDCA_WORKTREE`).
Line numbers marked "base" are on `0771812`; "patched" are in the tree after `patch.diff`.

## What was read

`brief.md`. The brief keeps everything from `iteration-v5/brief.md` unless it says
otherwise and names v5's code as reusable, so I read that brief and v5's `patch.diff` and
started from that patch. I did not read v5's build-notes or check files. The brief's
carry-forward asks for no fd-4 handshake (option B). I kept none of v5's handshake code.

## Result

- `python3 -m pytest tests/test_session.py`, via the project runner
  (`engine/scripts/run-suite.sh`, the whole suite): **400 passed**, four serial runs.
- C4 (`engine/scripts/run-verify.sh`, run with `PDCA_BUNDLE` set to this bundle):
  **PASS**. Green leg: 163 ran, 0 failed. Red leg (production hunks reverted): 163 ran,
  60 failed, 0 collection errors. Every #140 test in the file passed on the red leg.
- `scripts/docs_links.py`: 0 broken links. `git diff --check`: clean. The repo has no
  formatter or pre-commit hook (`pyproject.toml` configures only pytest). The
  immutability check does not apply: `pty-protocol/v1.md` is `status: draft`.

## The design (option B), with citations

### Part 1: bash state in `H`

- **All traps except EXIT.** The base passes `$(\builtin trap -p)` from the top level of
  nl-shell's `PROMPT_COMMAND` element (base `session.py:177`) but puts it only in `T`
  (base `:164`). Now `__nls_snap` also writes it into `H`
  (patched `session.py:200-205`). The top level is the only place that sees
  DEBUG/RETURN/ERR: I checked that inside a function `$(trap -p)` shows only EXIT and
  signal traps. The EXIT trap (`trap -p EXIT`, which is always first in that list) is
  cut off the front; see "Brief conflicts" below.
- `shopt -po emacs vi functrace errtrace xtrace histexpand`, `shopt -p extdebug`,
  `declare -p PS4 MAILCHECK BASH_XTRACEFD`, `declare -pF` of the hook functions, the
  disabled state of each `HOOK_BUILTINS` name, `bind -v` minus `history-size`, and
  `bind -p/-s/-X` for five keymaps (patched `session.py:206-232`). These come from v5,
  plus `errtrace`.
- Every `$( … )` in the hooks keeps stderr (`2>&1`): patched `:195`, `:211`, `:225`,
  `:237-245`, `:256`. The base dropped it at `:139`, `:151`, `:159`, `:177`.
- `HOOK_BUILTINS` (patched `:85-101`) is exactly what the hook part of `RCFILE` calls:
  `:`, alias, bind, compgen, declare, enable, eval, jobs, printf, return, set, shift,
  shopt, trap, plus `builtin`. `read` is no longer in it, because without the handshake
  no hook calls `read`. `test_hook_builtins_are_exactly_the_ones_the_hooks_call`
  (patched test `:1498`) checks the tuple against the rcfile.
- Pins after `~/.bashrc` (patched `:150-155`): `readonly PS4`, and `unset MAILCHECK;
  readonly MAILCHECK`. If `~/.bashrc` already made either one readonly, the rcfile
  defines a function `nl_shell_unpinned_<name>`. `_start_checks` finds it in the
  baseline `F` and starts the session degraded with a reason naming the variable
  (patched `:590-622`). I first tried
  `if { PS4=${PS4-}; } 2>/dev/null; then …` to detect the readonly case. bash aborts the
  whole compound command on a readonly assignment, so neither branch ran. Reading the
  attribute with `declare -p` is what works. The prefix is not `__nls_`, because
  #140's `test_hook_state_vars_cover_the_rcfile` would then require the marker in
  `HOOK_STATE_VARS`.
- Start checks (patched `:590-622`): functrace on after `~/.bashrc` (from v5; the
  `set -o functrace` line in H); an unpinned PS4/MAILCHECK; and PS1/PS2 with an attribute
  that `__nls_snap` cannot reset (`declare -p` attribute not `--` or `-x`). The last one
  is what (i) asks for: `readonly PS1='$(bind …)'` makes the session start degraded.
- Both hook functions now start `\builtin set -- … || return` (patched `:172`, `:192`;
  base `:116`, `:136`). This is allowed edit (1). It uses a plain `return`, not
  `\builtin return`. With `builtin` disabled, every `\builtin x` runs bash's
  `command_not_found_handle` (on this host, `/usr/lib/command-not-found`, a Python
  script). I traced about 70 calls, which kept bash busy for well over the 5 s limit.
  The `enable -n builtin` row of (s) hung until I made this change. A function named
  `return` could take over that plain `return`, but that branch only runs when
  `set`/`builtin` is already disabled. That state degrades the session anyway (no
  records), and shadowing functions are a named Known gap.

### Part 2: the whole terminal state before every paste

`Session.run` (patched `:689-694`; base `:511-515`): after `_wait_for_prompt`, it calls
`_check_stopped`, then `_prompt_check` (patched `:917-938`). `_prompt_check` compares the
full `tcgetattr` of the master with the first-prompt reading and checks fds 0-2. At start,
`_prompt_baseline` (patched `:896-915`) takes that reading and requires R to have
readline's values; `VDISCARD` is exempt (see R below).

### Part 3: the shell's own R, after the fact, with no handshake

`_read_shell_r` (patched `:940-950`) is called in `_wait_for_result` after `D` is read
and before `E` (patched `:735-737`; checked at `E` on `:733`). It is called the same way in `_spawn` between `D 0`
and `E` for the startup value (patched `:581-582`). Why a reading there is of the
shell's own settings and not readline's: bash writes `E` (rcfile `printf 'E\n'`) before
`__nls_snap` returns, and readline takes the terminal only after `PROMPT_COMMAND` ends.
So I take `tcgetattr`, then `select` fd 3 with a zero timeout. If nothing new is
readable, `E` had not been written at the time of the reading, so readline did not hold
the terminal. If bytes are pending, the loop reads them and tries again. If `E` comes
first, there is no reading, and `_check_shell_r` degrades (fail closed, patched
`:952-969`). At `E`, R must equal the startup value, or the session degrades with
`outside-check`. The check runs after `_await_output_end`, so the degraded error carries
the command's real result (criterion (k): "output is exactly hello").

The window from `D` to `E` is the hook runtime, which includes several forks
(`$(trap -p)`, the PS1/PS2 loop, the H subshell, then V/F/L/B/X/J). That is a few
milliseconds. Python reacts to `D` well inside it. Evidence it holds:
`test_many_quick_commands_stay_healthy` (50 × `true`) passed in every run, including
four runs with two suites in parallel. No part-3 false alarm appeared in any run.

### R itself

- Measured live (scratch script driving `bash --norc -i` through ptyprocess and reading
  `tcgetattr` at the prompt, after a foreground `stty`, and while a command ran):
  readline forces ISIG on; ICANON and ECHO off; ICRNL, INLCR, ISTRIP and INPCK off;
  VMIN=1, VTIME=0; VLNEXT and VDISCARD set to 0. Not forced: IXON, IXOFF, VINTR, VEOF,
  OPOST, IEXTEN, ECHONL, NOFLSH, TOSTOP, ECHOCTL, ECHOE, ECHOK, ONLCR, IMAXBEL, BRKINT,
  IGNBRK. `stty cs7` does not stick on a PTY.
- Read the source: readline `rltty.c` on the bash-5.3 branch (savannah cgit),
  `prepare_terminal_settings`. It confirms the list above and adds:
  - **FLUSHO** (added to R): cleared if set. Linux did not keep a `stty flusho`, so it
    always reads 0.
  - **VDISCARD** is disabled only when its key is bound to a readline function in the
    current keymap (`\C-o` is, by default). So the first-prompt check does not require
    it to be 0 (`_R_CONDITIONAL`, patched `:332`). It stays in R for part 3 and in the
    full part-2 compare.
  - ISTRIP/INPCK are cleared only for CS8 or meta. A PTY stays CS8, as measured.
  - IXON/IXANY are cleared only when `_rl_use_tty_xon_xoff == 0`. On 5.3.9 IXON stayed
    on, so it is not in R.
  - VDSUSP does not exist on Linux.
- The table is `_R_FIELDS` (patched `:317-330`).

### Other outside checks (from v5, kept)

- fds 0-2: checked before the paste and at each `E`. At `E` this runs before the output
  wait, because with fd 1 on `/dev/null` the end marker never arrives.
- Stopped state: checked before the paste, on every poll of `_wait_for_result` and
  `_wait_for_prompt` (allowed edit (2)).
- `tiocsti_path`: checked at start.

### Reason codes (`pty_protocol.py`)

`degrade(reason, code="other")` and `degraded_code` (patched `:165`, `:174-178`).
`missing-record` at patched `:276`, `h-changed` at `:302`. In `session.py`: the prompt
rule is `missing-record` (patched `:768`) and "the shell exited" is `exited` (patched
`:1090`). The reason text at every #140 site is unchanged.

## Brief conflicts (for sign-off)

NEEDS-HUMAN brief conflict: the brief lists EXIT among "every trap" in `H`, but its
Success criterion also says all #140 tests stay green, and #140's
`test_ordinary_changes_stay_healthy[exit-trap]` (test `:576-590`) requires
`trap 'echo hi' EXIT` to stay healthy. I left EXIT out of `H`: an EXIT trap runs only
when bash exits, and subshells reset it, so it cannot run before a paste. `T` still
reports it. Brief decision 8 also treats EXIT as harmless ("A trap (other than `EXIT`)").
Cost of the other choice: put EXIT in `H` (drop rcfile lines 200-205's trim, about −3
lines) and edit that #140 test's parameter list (one line).

NEEDS-HUMAN brief conflict: (h) requires `trap ':' USR1` to degrade, but #140's
`test_text_fields_round_trip_exactly[trap]` (test `:759`) set a USR1 trap and required a
healthy session. Both cannot hold. I changed that one vector from `USR1` to `EXIT`
(still a multi-line trap text with `\x1e` and a backslash, still read back through
`$(trap -p)`), so it keeps testing what it was written for: the `T` field's encoding.
This is the one #140 test line whose meaning changed.

Also changed in #140's test file, but not in meaning: `_NLS_HOOK` (base test `:811`) was
a literal copy of the hook element. The element changed (`2>&1`), so it is now
`_nls_hook()`, read from `RCFILE`'s `PROMPT_COMMAND=(` line (patched test `:811-816`).
It stays green on both trees, so the C4 red leg sees no #140 failure from it.

## Red-leg notes

Of the 60 red-leg failures, nearly all fail on the attack: "DID NOT RAISE
SessionDegraded", "the first command run under the change ended healthy", "the next
paste would be written with Enter bound…", "the USR1 trap would bind Enter…", a
`_try_run` that returned a healthy `CommandResult`, a stopped bash that blocks `run()`
for over 5 s, or PS4 assignments that succeed (`assert 0 != 0`). These fail only because
the API is new, and the brief already counts them that way: `tiocsti_path` (2 ×
TypeError), `HOOK_BUILTINS` (2 × AttributeError). Two fail only on `degraded_code`,
because #140 already degrades them for another reason: `set -x` (xtrace output breaks
the end-marker framing) and `exec >/dev/null` (end marker never arrives). By the brief's
rule these two are not red-leg evidence for I1. Without them there are still about 54
attack failures.

## Refute my own test (a) (b) (c)

- **(a) Genuine red? Yes.** `run-verify.sh` reverts the production hunks
  (`src/nl_shell/*.py`) in place and reruns `tests/test_session.py`: 60 of 163 fail with
  0 collection errors. Examples: the (h2) `*__nls_snap*` DEBUG-trap `bind` row fails
  with "the next paste would be written with Enter bound to a macro"; (t) fails with "the
  USR1 trap would bind Enter while readline waits"; all five (k) rows fail with "the first
  command run under the change ended healthy"; the v5 fd-4 bypass shape fails with "DID
  NOT RAISE SessionDegraded". The worktree was checked against `patch.diff` (`cmp`)
  after each verify run.
- **(b) Production path? Yes.** Every test starts the real `nl_shell.session.Session`
  (a real bash 5.3.9 on a real PTY, `RCFILE` as shipped) and calls `Session.run`. The
  only stand-in is a spy around `_write_all` that records and then calls the real write.
  `tiocsti_path` is the constructor keyword the brief defines; pointing it at a temp file
  is the brief's way to simulate `1` without root. Nothing re-implements a check.
- **(c) Fixture includes the fault? Yes.** Each attack is the real one, pasted as a
  confirmed command into that session: the self-removing DEBUG trap with `bind`; a USR1
  trap fired by a real `kill -USR1 $$` 0.5 s later while readline waits; real foreground
  `stty -isig` etc.; a real background job (`trap '' TTOU; sleep 0.5; stty -isig`) that
  changes the PTY while readline holds it; a real `kill -STOP $$`; a real `MAILPATH` with
  new mail written after `sleep 1.1`. Markers are real files the injected code would
  create, and tests assert they are absent.

## Environment notes

- No external dependency was missing. ptyprocess, `/proc/<pid>/{syscall,stat,fd,fdinfo}`
  (`ptrace_scope` = 1), `legacy_tiocsti` = 0 and bash 5.3.9 were all present.
- Pre-existing flake, not from this patch: #140's `test_vector10_interrupt_ends_the_command`
  failed (status 0, not 130) in 1 of 2 suites in each of two parallel runs on the patched
  tree. I then reverted only `src/` to base and ran the same parallel pair twice: it
  failed there too (2 of 4 runs). It sends Ctrl-C 0.3 s after `S`, so under load the
  byte can arrive before `sleep` is the foreground job. Nothing in this patch runs
  between `S` and the command. Serial runs are always green.

## Ruled out

- Any reading that needs bash to wait for nl-shell (v3-v5's fd 4): forbidden by option
  B, and bypassed via `/proc/<pid>/fd/4` in v5.
- Requiring a reading from inside the command (between `S` and `D`) for part 3: a
  confirmed `vim`/`less`/`read -s` changes the terminal while it runs, so that would
  raise false alarms. The `D`..`E` window is after the command and before readline.
- Comparing every field in part 3, not just R: fields outside R already reach part 2
  at the next paste, with the shell's own values. Adding them would give two checks for
  one fault and more ways to raise a false alarm.
- A wrapping `if \builtin set …; then … fi` around `__nls_snap` (v5's shape): it
  re-indents about 60 rcfile lines (and the spec copy) where the `|| return` first line
  does the same in one changed line per function.

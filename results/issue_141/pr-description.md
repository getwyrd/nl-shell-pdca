## Summary
**User impact:** a command you confirmed could quietly set up bash or the terminal so
that the *next* command you confirm runs something other than what you approved — for
example, pressing Enter adds `; touch MARK` to the line, or a later stray character
interrupts it halfway — and nl-shell would not notice or warn you. This matters once
the persistent shell session runs confirmed commands (#78); today the session is built
but not wired up yet.

This PR makes the session notice those changes and refuse to send the next command
(the session is marked degraded and offers a restart) instead of sending it into a
shell that might run it differently.

Reported in [#141](https://github.com/eduralph/nl-shell/issues/141).

Builds on #140 (PR #146, commit `7d657847d4a701d5f676429807ca2b3e40640024`) and should
merge after it.

## What to look at
- **The idea:** before each command is sent, nl-shell already compares a snapshot of its
  own hook state with the one from startup. This PR widens that snapshot to the bash
  settings that change how a pasted line is read (traps, key bindings, editing mode,
  tracing, disabled builtins), and adds a second check that reads the terminal settings
  and bash's stdin/stdout/stderr from outside bash right before each paste.
- **Try it:** start a `Session`, `run("bind '\"\\r\": \" ; touch MARK\\n\"'")`, then
  `run("echo hello")`. Before this PR the second command runs and creates `MARK`. Now the
  first command degrades the session and the second is refused, with nothing written to
  the shell. Same for `trap ':' USR1`, `set -o vi`, `stty intr '|'`, or a background job
  that runs `stty -isig`.
- **Behaviour you will see change:** `PS4` and `MAILCHECK` become read-only after
  `~/.bashrc` runs, so `PS4='+ '` now fails with "readonly variable" and bash no longer
  checks mail. `LC_ALL=C` degrades the session (it changes readline's meta settings; this
  fails safe). `HISTSIZE=…` does not.
- **What it deliberately does not check:** the shell's own values of the terminal fields
  readline overrides while it reads a line (signals, echo, line mode, …). Those cannot
  change what a pasted line contains, and every way to read them without making bash wait
  raced the scheduler and raised false alarms. After `stty -isig`, for example, the
  session stays healthy and `Session.interrupt()` no longer interrupts a command. This is
  listed as a known gap (#149).

## Root cause
The snapshot from #140 covered only nl-shell's own hook state, so any other bash or
terminal state a command changed — key bindings, traps (signal traps can run while
readline waits), editing mode, tracing, terminal control characters — carried into the
next paste unseen. Terminal settings are not bash state at all, so no in-shell snapshot
could have caught a background job changing them.

## Fix
- `src/nl_shell/session.py` rcfile: `H` gains every trap except `EXIT`, `extdebug`,
  `functrace`, `errtrace`, `xtrace`, `BASH_XTRACEFD`, `declare -p PS4`/`MAILCHECK`, `set -H`,
  readline on/off and mode, `bind -v` (minus `history-size`), all key bindings in every
  keymap, and the enabled state of `HOOK_BUILTINS` (`session.py:85`). Every command
  substitution in the hooks captures stderr. `readonly PS4` and `unset MAILCHECK; readonly
  MAILCHECK` after `~/.bashrc` (`session.py:154-155`).
- Pre-paste outside check in `Session.run` between the prompt wait and the write
  (`session.py:676-683`): stopped-state check, then `_prompt_check` (`:900`), which compares
  the whole termios and bash's fds 0-2 with the first-prompt baseline (`_prompt_baseline`,
  `:879`). fds are also compared at each `E`, re-read once before a mismatch counts
  (`_check_fds_after_e`, `:931`).
- Stopped bash (`_check_stopped`, `:1014`) degrades before every paste and on every poll
  tick; a kernel that allows TIOCSTI starts the session degraded (`_check_tiocsti`,
  `:1036`; path is the `tiocsti_path` keyword, `:455`).
- Reason codes: `ProtocolTracker.degrade(reason, code="other")`
  (`src/nl_shell/pty_protocol.py:174`), exposed as `Session.degraded_code` (`:632`) and
  `SessionDegraded.code`. Codes: `h-changed`, `missing-record`, `exited`, `outside-check`,
  `stopped`, `tiocsti`, `other`. #140's reason texts are unchanged.
- Docs: spec `docs/design/specs/pty-protocol/v1.md` §1.2 MUST list and §1.3 reference
  rcfile, "What this protects" (`:191-232`), §3 outside checks (`:312-355`), §4.2 triggers
  and codes (`:368-396`). Threat model Known gaps rewritten as named items
  (`.oss-scanner/threat_model.md:181-213`), ending with: "#78 MUST NOT wire the session to
  confirmed commands until each of #145, #147, #148, #149 and #150 is fixed or a human has
  accepted it in writing as a known risk for #78."

## Verification
- **Claim:** the bytes bash runs for a paste are exactly the confirmed bytes, or nothing
  is sent, for the closed list in spec §1 "What this protects".
- **Checked:** `src/nl_shell/session.py:676-683` — the outside check sits after the prompt
  wait and before the only paste write; a degrade there raises before `_write_all`.
- **Checked:** `src/nl_shell/session.py:85` vs the hook functions — `HOOK_BUILTINS` equals
  the builtins named in the hooks (`test_hook_builtins_are_exactly_the_ones_the_hooks_call`,
  `tests/test_session.py:1588`).
- **Test (red without the fix, green with it):** `tests/test_session.py` — with the
  production changes reverted, 56 of 164 tests fail, 54 of them on the attack itself
  (marker file created, paste written, or session left healthy); none of #140's tests
  fails and there are no setup or collection errors. With the fix, all 164 pass, and the
  whole suite passes (401 tests). Key tests: table rows at their own snapshot (`:1078`),
  DEBUG/CHLD/signal traps and redefined prompt functions binding Enter (`:1128-1188`),
  background `stty -isig` refused (`:1189`), `stty intr '|'` (`:1212`), stopped shell
  (`:1259`), PS4/xtrace (`:1524-1587`), disabling each hook builtin (`:1604`), mail check
  off (`:1464`).
- **Regression guards (pass before and after):** no false alarms on 50 quick commands,
  `é` round trip, `HISTSIZE`, `stty -ixon` in `~/.bashrc` (`:1273`, `:1392-1418`); vi mode
  and bracketed paste off in `~/.bashrc` still work (`:1494`). Python stalls must not
  degrade a healthy session — a 50 ms sleep after each write, before each control read,
  and a busy thread in the same process (`:1338-1383`); these failed 3/3 against an
  earlier design that read the shell's own terminal fields, which is why that reading is
  gone (`:1384` checks it stays gone).

**Where this differs from the issue text** (the issue body predates these decisions):
- `PS4` is made read-only, not just compared in the snapshot.
- The issue's "masked bits" became the readline-forced fields (R); only R while readline
  holds the terminal is checked, not the shell's own values (#149).
- A `PS1` in `~/.bashrc` that would run code: healthy with exact output is also accepted
  (the rcfile resets `PS1`).
- `exec </dev/null` only has to be refused with nothing run.
- vi mode plus bracketed paste off in `~/.bashrc` must work, not "or start degraded".
- `HOOK_BUILTINS` is derived from the rcfile; `read` is not in it.
- Reason codes and `degrade(reason, code)` are added.
- Every trap except `EXIT` is in the snapshot, not only DEBUG/RETURN.
- New stall tests guard against timing false alarms.
- The planned "`stty cs7 istrip` is refused" test cannot hold on Linux: the kernel's PTY
  driver forces `CS8` on every settings change, so `cs7` never takes. It was replaced by
  `test_character_size_change_cannot_strip_paste_bytes` (`:1231`), which checks that the
  terminal is still `CS8` and an `é` paste arrives intact (or the session degrades).

**Known limits of the evidence:** `test_disabling_any_hook_builtin_degrades` (`:1604`)
reads `HOOK_BUILTINS` to choose what to disable, so without the fix it fails on the
missing name rather than on the attack. The separate
`test_disabling_the_builtin_that_would_show_a_change_is_refused` (`:1631`) does fail on
the attack for its two cases. Follow-ups: loop over the names parsed from the rcfile
instead, and quote the file name in the fd-mismatch reason (`_fds_match`, `:996`) with
`!r` before #78 shows reasons to users.

Fixes #141

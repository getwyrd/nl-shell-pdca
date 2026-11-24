# Adversarial review — issue 141 (round 8, option N)

Short version: I could not break the production fix. I found two problems with the
evidence. One test cannot go red the way it was asked to, and one brief row was replaced by
a different test. I also found a brief requirement that no test can ever meet on Linux.

## Attempts to refute the fix (none succeeded)

- `src/nl_shell/session.py:900` (`_prompt_check`). I tried to find a terminal change that
  gets past the pre-paste reading:
  - A background job could set an R field (R = the terminal fields readline forces while
    it reads a line) to the value readline already forces, e.g. `stty -echo`. That
    reading shows no change, but nothing changed in practice either, so the paste is safe.
  - A background job could make readline re-prepare the terminal so the change becomes
    part of the "shell's own" settings. Readline only does that after SIGINT, SIGQUIT or
    SIGTSTP. Interactive bash ignores SIGQUIT and SIGTSTP. SIGINT at the prompt makes bash
    send an unrequested `D`, which already degrades the session.

  No bypass found, apart from the already-accepted race between the check and the write
  (#147).
- I checked R against a real bash 5.3.9 prompt with a probe in my sandbox (`probe.py`):
  `bash -i` on a PTY, `tcgetattr` on the master after each foreground command. After each
  of `stty -isig`, `stty istrip`, `stty -icrnl` and `stty -ixon`, the prompt still read
  `isig 1, icanon 0, echo 0, istrip 0, icrnl 0, lnext 0`. So the brief's claim that the
  shell's own R values cannot change paste bytes holds on this host. Dropping part 3 does
  not open a hole in I1 (the rule that bash runs exactly the confirmed bytes, or nothing
  is sent).
- I looked for timing dependence like round 7's. `_prompt_baseline` and `_prompt_check`
  (`session.py:879`, `:900`) only read the terminal after `_wait_for_prompt` has seen bash
  blocked in `pselect6` on fd 0, which is a state bash stays in. `_check_fds_after_e`
  (`session.py:931`) reads the fds again once bash is back at the prompt, so a Python
  stall can only delay it, never cause a false alarm. I found no reading that depends on
  a window bash does not wait in. That matches the green (st) tests in the T3 log.
- I tried to hide traps from `H` with the EXIT-trap cut (the `${1#"$__nls_v"}` line in
  `__nls_snap`, from the `RCFILE` hunk). `trap -p` prints EXIT (signal 0) first, and the
  cut removes exactly the `trap -p EXIT` text. So EXIT trap text can never hide a real
  trap printed after it. With `trap` disabled, both readings return error text and the
  disabled-builtin list changes, so the session degrades.
- `bind -v` `history-size` removal: the pattern needs a newline before
  `set history-size`. `history-size` is never the first line of `bind -v` (boolean
  variables come first), so that edge case does not happen.

## Evidence findings

- NEEDS-HUMAN [impl] — `tests/test_session.py:1604-1608`
  (`test_disabling_any_hook_builtin_degrades`) loops over the new
  `session_mod.HOOK_BUILTINS` before any attack runs. On the C4 red leg it failed with
  `AttributeError: module 'nl_shell.session' has no attribute 'HOOK_BUILTINS'` (logged at
  test line 1607). So the (s) claim "for EVERY name, `enable -n <name>` degrades" has no
  red-leg evidence on the attack. Only the two `hidden-*` variants show one. That breaks
  the brief's Falsifiability rule that new API is read only after the attack assertion.
  Fix: loop over the names taken from `RCFILE` with the regex that
  `test_hook_builtins_are_exactly_the_ones_the_hooks_call` already uses (`_hook_part`,
  `\\?builtin ([A-Za-z_]+|:)`, plus `builtin`). Keep the separate equality test for
  `HOOK_BUILTINS`. Then the loop goes red on the base because the session stays healthy.
- NEEDS-HUMAN [human] — `tests/test_session.py:1231`
  (`test_character_size_change_cannot_strip_paste_bytes`) does not test brief row (j)'s
  CSIZE guard. The brief asks that a confirmed `stty cs7 istrip` degrade with
  `outside-check` and that the next run be refused with zero writes. The test instead
  accepts "degraded, OR `é` round-trips as `c3 a9`", plus CSIZE reading CS8. It is not in
  the red-leg failure list, so it passes on the base: it is a regression guard, not
  evidence. The builder's reason holds: a Linux PTY forces CS8. I checked on this host
  (kernel 7.0.0-38): after `tcsetattr` with CS7|ISTRIP on a slave, the master reads back
  CS8 with ISTRIP still on. So the brief's required outcome cannot happen. The spec text
  (`docs/design/specs/pty-protocol/v1.md:322-323`) states this. A human should accept the
  change to the brief row, because "pins the CS8 condition" is now only "CS8 is observed".
- `gate-logs/C4-verify.log` (the "56 of 164 failed" in `check-gates.json`) overstates the
  I1 evidence a little. About 7 of the 56 do not fail on an attack:
  - `[xtrace]` and `test_redirected_shell_fds_are_refused[stdout]` already degrade on
    the base. They fail only at `session.degraded_code` (`tests/test_session.py:1031`),
    which the brief says is not I1 evidence.
  - Two `tiocsti` tests fail with a `TypeError` on `tiocsti_path` (allowed by the brief).
  - Two tests fail with an `AttributeError` on `HOOK_BUILTINS` (see the first finding).
  - `test_fd_check_at_e_waits_out_the_e_redirect` is a regression guard that fails with
    an `AttributeError` on `_read_fds`.

  About 49 attack failures remain. The red→green proof still stands, but the count is not
  "56 attack failures". No setup errors and no failures of #140's tests: all 108 others
  passed.
- No other refutation. In short, I tried to:
  - bypass the termios check with a background job, and with a signal that makes readline
    re-prepare the terminal;
  - find timing false alarms at start, before a paste, and at `E`;
  - hide traps with the EXIT-trap text;
  - break the `history-size` pattern;
  - find a disabled-builtin gap. `HOOK_BUILTINS` matches the regex over the hook text, so
    none.

  I could not break any of them.

<!-- pdca:leaf-complete -->

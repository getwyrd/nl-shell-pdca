# Security review (advisory) — issue 141, round 7

**Attacker-reachable inputs this diff touches:** session state (threat model "Where untrusted input enters" item 4: traps, `bind`, `stty`, `exec` redirects, `PS4`/`MAILCHECK`, `enable -n`, set by a confirmed command or `~/.bashrc`) and the terminal settings a background job can change. No new input path is added. This round's only behaviour change is the fd 0/1/2 check at E (the end-of-command record) in `_check_fds_after_e`.

## What I checked

- **The new retry at E** (`src/nl_shell/session.py:956-978`, called at `:819-820`). If the first reading of bash's fds 0-2 after E differs from the baseline, it waits until bash is blocked reading the terminal again (`_reading_terminal`, `:861`), or until `_SETTLE` (3 s, `:283`) runs out. Then it reads again, and a difference still degrades the session.
  - Can an attacker use the retry? The only change it lets through is one that bash undoes by itself before readline takes the terminal, which is what bash's own `>&3` redirect for `printf 'E\n'` does. A confirmed `exec >/dev/null`, `exec 2>/dev/null` or `exec </dev/null` lasts past that point, so the second reading still differs. Other processes can't change bash's fds without ptrace (Known gap #137, out of scope).
  - Even if the E check missed something, I1 (the pasted bytes are exactly the confirmed bytes, or nothing is sent) does not depend on it. `_prompt_check` (`:896-917`) compares the fds again right before every paste, while readline holds the terminal (`:788-790`). So the retry can only delay detection by one step. It cannot let a paste through.
  - When the wait times out, the code falls through to a second `_check_fds()` and degrades if the fds still differ (fail closed). When `/proc` can't be read it degrades with the error, and a stopped bash also degrades. I found no path that skips the second reading. `_fds_match` asserts `self._fds is not None` (`:1023`). That assert can only fail on a session that is already degraded, and degraded sessions skip this call (`:819`).
  - Can an attacker cause a hang or use too many resources? The loop is capped at `_SETTLE` and polls every 2 ms. That is the same cap as `_wait_for_prompt`, and it runs at most once per command.
- **Tests for the attacker case.** `tests/test_session.py:1090-1105` (`test_redirected_shell_fds_are_refused`) still requires `exec >/dev/null` and `exec 2>/dev/null` to degrade at their own snapshot with code `outside-check`, and the next paste to be refused with no marker file created. So the retry did not weaken the hostile case. The new `test_fd_check_at_e_waits_out_the_e_redirect` (`:1302-1345`) replays the brief race, with fd 1 pointing at the control pipe at E, and requires the session to stay healthy. That covers the false alarm from round 6. T3 (the full test suite): 401 passed. C4 (the red-before-fix, green-after-fix check): 61 of 164 tests fail without the fix and all pass with it.
- **Everything else in the patch.** The EXIT-trap wording, `H` rows, `HOOK_BUILTINS`, the `PS4`/`MAILCHECK` pins, the R checks (R = the terminal fields readline sets itself while it reads a line), TIOCSTI (the kernel call that pushes bytes into a terminal's input) and the stopped check are carried over from round 6. The sign-off said to keep these as built, and round 6's security review found no I1 bypass in them. I did not re-raise the known gaps #147, #148, #149 or #150 (all settled in the brief).

## Findings

No findings. The retry delays detection of a lasting fd redirect by at most one bounded wait. It does not hide the redirect, and the pre-paste fd check still guards I1. The patch's tests cover the hostile redirect as well as the friendly race.

<!-- pdca:leaf-complete -->

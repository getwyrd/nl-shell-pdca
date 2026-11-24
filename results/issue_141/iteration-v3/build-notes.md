# Build notes — #141 persistent-bash-session tamper checks (iteration 3)

Base: worktree HEAD `0771812` ("pdca-integrate: issue_140"), the wave-2 folded branch with
child-1 (#140). Every `path:line` below is on that base plus this patch (post-fix line
numbers). The docs lines the brief cites on `c47c5c2` (`:195-196`, the Open-questions
bullet) were at `docs/design/specs/pty-protocol/v1.md:323-324` on this base; iteration 1
closed that bullet.

Files: `src/nl_shell/session.py`, `src/nl_shell/pty_protocol.py`, `tests/test_session.py`,
`docs/design/specs/pty-protocol/v1.md`, `.oss-scanner/threat_model.md`.

This iteration starts from iteration 2's patch (`iteration-v2/patch.diff`, applied cleanly
on `0771812`) and changes only what the round-2 carry-forward asked for. Everything else
from iterations 1 and 2 is kept; see "Kept from iterations 1 and 2".

## What the round-2 carry-forward asked, and what I changed

### 1. A background job could change masked terminal bits at the prompt (I1 broken)

Reproduced first, on iteration 2's code (`.scratch/repro_istrip.py` in the worktree,
untracked): `run("(trap '' TTOU; sleep 0.5; stty istrip) &")`, wait 1.5 s, then
`run("printf '%s' 'é' | od -An -tx1")` → session healthy, output ` 43 29` (`C)`), not
`c3 a9`. Bash ran bytes other than the confirmed ones.

Cause: `_termios_view` (`session.py:1119`) drops the bits readline changes
(`_RL_IFLAG`/`_RL_LFLAG`/`_RL_CC`, `session.py:329-337`) from every compare, including the
one right before the paste.

Fix (`session.py`):

- `_check_outside` passes `at_prompt` through to `_check_termios` (`session.py:944`).
- `_check_termios(at_prompt=True)` compares **every** setting, unmasked
  (`_termios_full`, `session.py:1113`), with the baseline (`session.py:967-972`).
- The baseline was already read at the first prompt, after `_wait_for_prompt()`
  (`session.py:608-619`), while readline holds the terminal. Before a paste, `run()` also
  waits for the prompt first (`session.py:722`) and then calls
  `_check_outside(at_prompt=True)` (`:725`). So both reads are taken in the same state.
- Readline sets the bits it changes to fixed values each time it takes the terminal. So
  the only way they can differ at the prompt is if something changed them after readline
  did, which is the attack.
- The checks at `E` and `D` are unchanged (masked compare plus the ISIG rules), because
  bash is in its hooks then, not in readline.
- Comment at `session.py:325-328` updated to say which check masks and which does not.

After the fix, the repro gives `DEGRADED outside-check … the session terminal's settings
at the prompt differ from the first prompt's`, and nothing is written.

Tests:

- `test_j_background_job_changing_the_terminal_at_the_prompt_degrades`
  (`tests/test_session.py:1171-1187`, parametrise at `:1171`) is the reviewer's repro as a test. It is
  parametrised over `istrip`, `icrnl`, `inlcr` and `-isig`. Each run must:
  - stay healthy for the job's own command;
  - then refuse the `é` paste with `outside-check`;
  - with zero PTY writes.
- `test_j_terminal_checked_at_the_prompt_stays_healthy` (`:1190`) guards against false
  degrades. A normal `é` round trip gives `c3 a9`, three `echo hello` runs follow, and
  the session stays healthy.
- I first had `lnext ^-` as a row. It passed on iteration 2's code too, because readline
  already disables VLNEXT at the prompt, so turning it off changes nothing. I replaced it
  with `inlcr`. It was not evidence for anything.

Spec: §3 "Outside checks" (`docs/design/specs/pty-protocol/v1.md:273-281`) now says the
baseline is read while readline holds the terminal, that every setting must match before a
paste (with the `istrip` example), and that the mask applies only to the checks at `E` and
`D`. The threat model is unchanged: this was not listed as a gap, and it is now closed.

### 2. Test (r) did not test the xtrace and PS4 rows

The reviewer was right. With `PS4` readonly (`session.py:179`), the assignment in the
brief's line fails, bash drops the rest of the line, and `set -x` never runs. Only
`BASH_XTRACEFD` changed `H`. Measured: the new `H` lines for that command are exactly
`declare -- BASH_XTRACEFD="9"`. The baseline instead has `BASH_XTRACEFD unset` and
bash's stderr `declare: BASH_XTRACEFD: not found`, captured by the `2>&1` rule.

Changes in `tests/test_session.py`:

- `_TAMPER` gets an `"xtrace": ("set -x", "h-changed")` row (`:1037`), as asked.
- `_changed_hook_lines` (`:1304`): the `H` lines in a result's snapshot that the baseline
  (with its seq line updated, `pty_protocol.expected_hooks`) does not have. With it, a
  test can assert *which* row fired.
- `test_r_brief_line_degrades_and_its_payload_never_runs` (`:1310`) runs the brief's exact
  line and states honestly what happens:
  - `h-changed`;
  - output contains `PS4: readonly variable`;
  - the only new `H` line is the `BASH_XTRACEFD` one;
  - the next paste is refused unsent;
  - no marker.
- `test_r_ps4_payload_is_refused_and_never_runs` (`:1333`) runs `PS4=…`, `declare PS4=…`
  and `printf -v PS4 …`. Each must fail with "readonly variable" and leave `H`
  unchanged, the session healthy and no marker.
- `test_r_each_xtrace_row_degrades_at_its_own_snapshot` (`:1357`) is parametrised over
  `set -x`, `set -o xtrace` and `BASH_XTRACEFD=9` (after `exec 9>/dev/null`). It runs the
  brief's attack split into separate pastes, so each step really runs:
  - first the refused `PS4` payload (healthy);
  - then the row's command, which must degrade `h-changed` with the expected new `H`
    line (`__nls_x="1"` or `BASH_XTRACEFD="9"`) and no `PS4` line;
  - then the next paste is refused unsent, and no marker exists.

No production change for (r).

## Kept from iterations 1 and 2 (unchanged)

- `H` additions (Table A rows): DEBUG/RETURN traps, `extdebug`, `functrace`, `histexpand`,
  `emacs`/`vi`, `__nls_x`, `PS4`, `BASH_XTRACEFD`, the enable state of each
  `HOOK_BUILTINS` name, `bind -v`, and `bind -p/-s/-X` for `emacs vi-insert vi-command`.
  `RCFILE` is at `session.py:169-281`.
- `HOOK_BUILTINS` (`session.py:98-114`) and `HOOK_BUILTINS_WITHOUT_RECORDS = ("builtin",
  "printf")` (`:119`). `printf` writes every record and `builtin` prefixes every hook call.
  With either disabled no `D` is written, so the prompt rule fires (`missing-record`). Every
  other hook builtin, measured live, gives `h-changed` within about 0.05 s.
- `PS4` readonly after `~/.bashrc` (`session.py:179`). Bash traces `PROMPT_COMMAND`, so a
  `PS4` set by a command would run before any snapshot could see it. Any confirmed
  `PS4=…` now fails with "readonly variable".
- The fd 4 wait after `D` (`session.py:204`, pipe setup `:563-592`, `_read_control`
  `:1064`, `_answer_done` `:1082`). Bash waits in `__nls_done` until nl-shell has read the
  terminal settings, so the `D`-time read always sees the command's own settings. It
  also fails closed if those look like readline's (`session.py:978`). `__nls_k` is in
  `HOOK_STATE_VARS`.
- `2>&1` on every command substitution in the hooks. Degrade codes; outside checks (fds
  0-2 at `E` and before the paste, stopped check on every poll); `tiocsti_path`; the
  `prompt-not-fixed` start check.
- Threat model Known gaps: child-1's interim bullet replaced with the decision-2 list
  (ADR-0024, #134, #137, #136, #138, #135). No catch-all sentence.

## Deviations from the brief (for the human)

1. **(m) and (p) are not all red on #140.** The base rcfile already forces bracketed paste
   on after `~/.bashrc`. So (m) passes on #140 and is a regression guard. (p)
   `bracketed-paste-off` and `readline-off` also pass on #140, which degrades them as
   `undelimited`. (p) `vi-mode` is red on #140. I did not fake a red.
2. **(i) PS1.** A plain `PS1` from `~/.bashrc` is replaced before it is ever expanded, so
   the session stays healthy with no marker. A readonly `PS1` using `${ …; }` is expanded,
   so it starts degraded (`prompt-not-fixed`) with no marker.
3. **(r) as one line never reaches `set -x`**, because `PS4` is readonly (see change 2).
   The xtrace and `PS4` rows are proven by the split tests instead.
4. **fd 4 is new protocol surface** that the brief did not name (iteration 2).
5. **The pre-paste check now compares every terminal bit** (this iteration). That is
   stricter than the spec text Plan pointed at.

## Limits (not fixed; flag at sign-off)

- **Race after the pre-paste check.** A job could change a setting between the check and
  readline reading the paste, a window of about one `write()`. Closing it would need the
  terminal locked against other process groups. That is out of scope (terminal ownership,
  #102/#120).
- **A change made while a command runs that readline later overrides** (for example
  `stty istrip` from a job while bash runs `sleep`) is not caught at `E`, because of the
  mask. Readline clears it for the paste, so I1 holds. The next command then runs with
  that setting, as with any `stty` the user runs.
- **The fd 4 wait can be fed early** through `/proc/$$/fd/4`. That only brings back the
  old race, and the fail-closed rule at `D` covers it (iteration 2).
- **Hangs with `enable -n return` + Ubuntu's `command_not_found_handle`** (iteration 1).
  Nothing is pasted, so I1 holds. Belongs with #136.
- **False degrades (fail closed):**
  - `HISTSIZE=…` (readline's `history-size` is in `bind -v`);
  - `stty sane`, or a program that leaves the terminal changed;
  - a program that leaves ICANON and ECHO off when it exits;
  - new this iteration: a command that changes a masked bit readline does *not* override
    at the prompt (for example `stty -ixon`, if readline leaves IXON alone). That now
    degrades before the next paste instead of passing. This is correct for I1, since IXON
    on would eat `^S`/`^Q` from a paste. No test in the suite hit it: 377 passed.

## Rejected alternatives (with cost)

- **Take a second baseline at every prompt and compare against the previous prompt.**
  This needs one more `_termios()` read and a field in `_OutsideBaseline`, about +6
  lines. But it would accept a change a command made deliberately, as long as it stayed.
  The first-prompt baseline is already in the right state, so the change I made is about
  +15 lines of code (`_termios_full` 5, the `at_prompt` branch 6, the signature/call 2).
- **Shrink the mask** (drop `ISTRIP`/`INPCK`/`ICRNL`/`INLCR`/`IXON`/`IXANY` from
  `_RL_IFLAG`). That would degrade every ordinary command at `E`, because readline
  restores the shell's own settings there. Child-1's tests would fail. A full compare is
  correct only while readline holds the terminal, which is the state before a paste.
- **Make (r)'s one-line test pass by dropping `readonly PS4`.** Iteration 1 did that, and
  the payload ran before the snapshot (rejected in round 1).

## Refuting my own test

- **(a) Genuine red? Yes, on two reverts.**
  - *Against iteration 2's production code* (base + `iteration-v2/patch.diff` for
    `session.py` only, new tests kept): **4 failed, 136 passed**. All four
    `test_j_background_job_…[istrip|icrnl|inlcr|-isig]` fail with "DID NOT RAISE
    SessionDegraded": the paste was written while the terminal had been changed. The
    standalone repro on that code printed `HEALTHY … ' 43 29'`.
  - *Against base* (`session.py` and `pty_protocol.py` from `0771812`, new tests kept):
    **42 failed, 98 passed**.
    - Every (h) row (now including `xtrace`), both (i) attacks, every (j) row
      (`stty intr`, both `-isig` rows, the four background-job rows, the late-check rows,
      tiocsti ×3, stopped), `p[vi-mode]`, all five (r) tests, the (s) loop and both v5
      reproducers.
    - One child-1 test, `test_spec_reference_rcfile_is_the_one_in_use`, also failed. That
      is only because I left the patched spec in place while reverting the rcfile; with
      the spec reverted too, it passes (iteration 2 measured that).
  - With the fix: `run-suite.sh` gave **377 passed, "T3 PASS"** twice (86 s each).
- **(b) Production path? Yes.** Every test starts the real `Session`, which runs the real
  `RCFILE` in a real bash 5.3.9 on a real PTY. The attack is a real background `stty` on
  that PTY. The only patching is `_spy_on_pty_writes`, which wraps `_write_all` and still
  calls it, and, in the older late-check tests, `_slow_termios_check`, which only adds a
  delay.
- **(c) Does the fixture include the fault? Yes.** The background job really changes the
  terminal while readline holds it; the `istrip` repro showed real byte corruption on the
  old code. The (r) tests run the real `PS4` payload, `set -x` and `BASH_XTRACEFD`, and
  assert which `H` line changed. Markers are absolute paths under `tmp_path`.

## Environment / runner / commit-readiness

- Tests: `engine/scripts/run-suite.sh` (full suite) and the bundle venv's
  `python3 -m pytest` for targeted runs and the revert legs, each wrapped in `timeout`. I
  did not run `run-verify.sh` (`$PDCA_VERIFY_BASE` is unset here); the driver's C4 run
  covers it.
- External dependencies, all present: `ptyprocess`; `/proc/<pid>/syscall`, `stat`, `fd`
  readable; `legacy_tiocsti = 0`; `ptrace_scope = 1`.
- Formatter / hooks: the target has none (no ruff/black/pre-commit in `pyproject.toml`,
  no `.pre-commit-config.yaml`). `git diff --check` is clean.
- CI docs checks pass:
  - `scripts/docs_links.py`: 0 broken.
  - `docs_checks.py immutability`: OK. I ran the base copy, as CI does, on a temporary
    commit built with a separate index (`commit-tree`), so HEAD and the index were not
    touched.
- New lines are at most 100 characters. The only exception is the existing one-line
  `PROMPT_COMMAND` in `RCFILE` (`session.py:279`), which must match the spec block.
- Working files are in `$PDCA_WORKTREE/.scratch/` (untracked, not in `patch.diff`).

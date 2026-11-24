# Build notes — #141 persistent-bash-session tamper checks (iteration 2)

Base: worktree HEAD `0771812` ("pdca-integrate: issue_140"), the wave-2 folded branch with
child-1 (#140). Every `path:line` below is on that base plus this patch (post-fix line
numbers unless marked "base"). The docs lines the brief cites on `c47c5c2` (`:195-196`, the
Open-questions bullet) were at `docs/design/specs/pty-protocol/v1.md:323-324` on this base;
that is the bullet I closed.

Files: `src/nl_shell/session.py`, `src/nl_shell/pty_protocol.py`, `tests/test_session.py`,
`docs/design/specs/pty-protocol/v1.md`, `.oss-scanner/threat_model.md`.

This iteration starts from iteration 1's patch (`iteration-v1/patch.diff`) and changes only
what the carry-forward asked for. Everything iteration 1 did that was not rejected is kept
and summarised under "Kept from iteration 1".

## What the carry-forward asked, and what I changed

### 1. (r): the PS4 payload must never run (no marker)

Iteration 1 let the payload run once, before the snapshot, and the test only checked that
the marker stopped growing. That was rejected: the brief's (r) says "no marker".

Cause: with `xtrace` on, bash expands `PS4` for every traced command, and it traces
`PROMPT_COMMAND`. The first traced command is the hook's own call, so `PS4` runs before
`__nls_done` can turn `xtrace` off. Nothing inside the hooks can run earlier.

Fix: the rcfile makes `PS4` readonly right after `~/.bashrc` (`session.py:179`). A confirmed
`PS4='$(…)'` then fails with "readonly variable", so `PS4` keeps its baseline value and
nothing is run. The rest of the (r) line still runs: `BASH_XTRACEFD=9` and `set -x` change
`H` (`BASH_XTRACEFD`, `__nls_x`), so the session degrades at that snapshot with
`h-changed`. Checked live on bash 5.3.9: `readonly PS4; PS4='$(echo x >> M)'; set -x; true`
creates no `M`.

`readonly` also blocks every other way to set it (`declare`, `printf -v`, `read`, `local`),
and it cannot be undone from inside bash.

Test: `test_r_ps4_payload_degrades_and_never_runs_for_a_later_command`
(`tests/test_session.py:1275`) asserts no marker again, both after the refused paste and
0.3 s later. `test_h_snapshot_carries_the_table_a_rows` now expects `declare -r PS4=`
(`tests/test_session.py:1074`).

Behaviour change for the human: any confirmed `PS4=…` now fails with "readonly variable"
(the session stays healthy, as nothing in `H` changed). A `PS4` from `~/.bashrc` is kept and
becomes the baseline.

### 2. `stty -icanon -echo -isig` looked like readline's own settings

Iteration 1 skipped the ISIG rule whenever ICANON and ECHO were both off ("readline has the
terminal"), so a command that turned off all three was never caught.

### 3. The `D`-time termios read was a race

Iteration 1 read the settings when Python handled `D`, hoping bash was still in the hooks.
If Python was late, it saw readline's settings (ISIG forced on) and missed `-isig`.

Fix for both (one mechanism plus one rule):

- **bash waits for nl-shell after `D`.** A second pipe is bash's fd 4 (read end in bash,
  write end kept by nl-shell; `session.py:564-591`). After writing `D`, `__nls_done` runs
  `\builtin read -r -t 5 -u 4 __nls_v` (`session.py:204`). nl-shell, for every `D` line it
  reads, first checks the terminal settings and then writes one `\n` to fd 4
  (`_read_control`, `session.py:1050-1066`; `_answer_done`, `:1068-1075`). So the read always
  happens while bash is blocked in its hook, never in readline. The reviewer's reproducer
  (delay the check by 0.15 s) now waits instead of missing it.
- **Fail closed at `D`.** If the settings read for a `D` have ICANON and ECHO both off, the
  session degrades (`outside-check`), because ISIG cannot be judged from readline-like
  settings (`_check_termios(in_hooks=True)`, `session.py:944-977`, rule at `:964`). With
  the wait in place, bash cannot be in readline at that moment, so these are the command's
  own settings: `stty -icanon -echo -isig` degrades. If the wait were ever bypassed (see
  "Limits"), a late read sees readline's settings and fails closed instead of skipping.
- `__nls_k` holds the `read`'s exit status (`session.py:205`). It is a hook state variable
  (`HOOK_STATE_VARS`, `session.py:82`) and is saved in `__nls_pre` before the hook
  overwrites it (`session.py:194`), so a wait that failed or timed out, or a confirmed
  `__nls_k=42`, shows in `H` and degrades `h-changed`. Child-1's
  `test_hook_state_value_changes_degrade_at_their_own_snapshot` caught that I had first
  left it out of `__nls_pre`.
- nl-shell answers from the raw control lines, not from the tracker's events
  (`session.py:1057-1060`). The tracker returns no event for the baseline `D` or for a `D`
  it rejects, and bash must be answered in every case or it waits 5 s. My first try used
  the events and every start timed out; that is how I found it.
- The answer is written even when the session is degraded, and the write end is
  non-blocking, with errors ignored (`session.py:588`, `:1068-1075`).

Tests:

- `test_j_signals_off_degrades_before_the_next_paste` is now parametrised over
  `stty -isig` and `stty -icanon -echo -isig` (`tests/test_session.py:1151-1167`).
- `test_j_signals_off_degrades_even_when_the_check_at_d_is_late` (`:1183`) is the
  reviewer's reproducer as a test: the real `_check_termios` runs 0.15 s late
  (`_slow_termios_check`, `:1170`, which wraps and calls the real method); `stty -isig` must
  still degrade with `outside-check`, and the next paste is refused unsent.
- `test_j_late_check_at_d_still_reads_the_command_s_settings` (`:1194`): with the same
  delay, three `echo hello` runs stay healthy. This is the test that needs the wait, not
  just the fail-closed rule: I swapped `_answer_done()` before `_check_termios()` (answer
  first, no wait) and this test failed with a false degrade, while the others passed.

Spec: §1.1 (fd 4), §1.2 (readonly `PS4`, wait after `D`), the explanation after the
reference rcfile (the `read`, `__nls_k`), the "What this protects" `PS4` sentence (it no
longer says `PS4` runs before the snapshot), and §3 "Outside checks" (when the `D`-time read
happens and the fail-closed rule). The reference rcfile block is regenerated from `RCFILE`
(child-1's `test_spec_reference_rcfile_is_the_one_in_use` checks it).

## Kept from iteration 1 (unchanged)

- `H` additions (Table A rows): DEBUG/RETURN traps (read at the top level of
  `PROMPT_COMMAND` and passed as `$2`, as a function does not see them), `extdebug`,
  `functrace`, `histexpand`, `emacs`/`vi`, `__nls_x` (xtrace was on), `PS4`,
  `BASH_XTRACEFD`, the enable state of each `HOOK_BUILTINS` name, `bind -v`, and
  `bind -p/-s/-X` for `emacs vi-insert vi-command`. `RCFILE` is at `session.py:169-281`.
- `HOOK_BUILTINS` (`session.py:98-114`) and `HOOK_BUILTINS_WITHOUT_RECORDS =
  ("builtin", "printf")` (`:119`). Why each of those two: `printf` writes every record;
  `builtin` prefixes every hook call. With either disabled no `D` is written, so the prompt
  rule fires (`missing-record`). Every other hook builtin, measured live, gives `h-changed`
  within about 0.05 s. `read` is now also needed for the fd 4 wait; `enable -n read` still
  gives `h-changed` (the (s) loop passes), because `\builtin read` fails at once and `H`
  shows it disabled.
- `2>&1` on every command substitution in the hooks; `$?`/`PIPESTATUS`/`BASHOPTS` passed as
  arguments; the `\builtin printf '' && { … }` guard.
- Degrade codes (`pty_protocol.py` and `session.py:134-142`), outside checks (fds 0-2 at `E`
  and before the paste, stopped check on every poll), `tiocsti_path`, and the
  `prompt-not-fixed` start check for a readonly `PS1`/`PS2` from `~/.bashrc`.
- Threat model Known gaps: child-1's interim bullet replaced with the decision-2 list
  (ADR-0024, #134, #137, #136, #138, #135). No catch-all sentence.
- `_NLS_HOOK` in child-1's tests became `_nls_hook()`, which reads the element from the
  `RCFILE` in use. Nothing else in child-1's tests changed.

## Deviations from the brief (for the human)

1. **(m) and (p) are not all red on #140.** The base rcfile already forces bracketed paste
   on after `~/.bashrc` (base `session.py:100`), so (m) passes on #140 and is a regression
   guard. (p) `bracketed-paste-off` and `readline-off` also pass on #140 (#140 degrades
   them as `undelimited`). (p) `vi-mode` is red on #140. I did not fake a red.
2. **(i) PS1.** A plain `PS1` from `~/.bashrc` is replaced before it is ever expanded, so
   the session stays healthy with no marker. The case where it is expanded, a readonly
   `PS1` using `${ …; }`, starts degraded (`prompt-not-fixed`) with no marker.
3. **fd 4 is new protocol surface** the brief did not name. It is the smallest change I
   found that makes the `D`-time read reliable; see "Rejected alternatives".

## Limits (not fixed; flag at sign-off)

- **The fd 4 wait can be fed early.** On Linux, a command can open `/proc/$$/fd/4` for
  writing and put a line in the pipe, so the next hook's `read` returns at once. That only
  puts back the old race, and the fail-closed rule covers the race: a late read sees
  readline's settings and degrades. A child process can also read fd 4 and take
  nl-shell's answer; then bash waits the full 5 s, `__nls_k` is non-zero, and the session
  degrades `h-changed`. Neither path lets `-isig` through healthy.
- **Hangs with `enable -n return` + Ubuntu's `command_not_found_handle`** (iteration 1
  finding, unchanged): with VTE's prompt command, bash never reaches the prompt and `run()`
  ends only by the caller's timeout. Nothing is pasted, so I1 holds. Belongs with #136.
- **False degrades (fail closed):** `HISTSIZE=…` (readline's `history-size` is in
  `bind -v`); `stty sane` or a program that leaves the terminal changed; a program that
  leaves ICANON and ECHO off when it exits.
- **Each prompt now waits for nl-shell.** If nl-shell is not reading when bash writes a
  `D` (for example Ctrl-C at an idle prompt), bash waits until the next `run()` drains it,
  or 5 s, then degrades on that snapshot. Measured cost on a normal prompt: none visible
  (the session test file took 75 s before and after).

## Rejected alternatives (with cost)

- **Fail closed at `D` without the wait.** This is the reviewer's first suggestion, about
  12 lines (only the `in_hooks` rule). It closes both bypasses, but any late read becomes
  a false degrade on an ordinary command. I measured that directly: with the answer sent
  before the check (no wait), `test_j_late_check_at_d_still_reads_the_command_s_settings`
  fails. Under load that would flake child-1's tests in the gate. The wait adds about 30
  lines (`session.py` pipe setup 12, `_read_control`/`_answer_done` 16, rcfile 3) plus the
  spec text.
- **Detect a bad `PS4` instead of blocking it.** Any check in the hooks runs after the
  first traced command, which already ran `PS4`. There is no earlier place to check.
- **Read the answer from the PTY instead of a new fd.** `read -n1` on a terminal changes
  its settings (cbreak), which is what the check reads, and the PTY carries the pastes.
- **A per-`D` random token on fd 4**, so an early line could be told apart. bash cannot
  check a token it does not know, and adding a record to report it back changes the
  tracker. The fail-closed rule already covers that case.
- **Compare the full termios at `D` against a `D`-time baseline**, so `stty -echo` alone
  also degrades. This would need a second baseline read in `_spawn` and would degrade
  every `stty -echo`. The brief marks `icanon`/`echo` as not tested, so I left the masked
  compare as it was.

## Refuting my own test

- **(a) Genuine red? Yes, on two reverts.**
  - *Against iteration 1's production code* (rejected approach), with the new tests: **4
    failed, 126 passed**:
    - `test_r_ps4_…`: the marker exists.
    - `test_j_signals_off_…[isig-as-readline]`: did not raise.
    - `test_j_signals_off_degrades_even_when_the_check_at_d_is_late`: did not raise.
    - `test_h_snapshot_carries_the_table_a_rows`: no `__nls_k`, `PS4` not readonly.
  - *Against base* (`git checkout HEAD -- session.py pty_protocol.py v1.md`, new tests
    kept): **31 failed, 99 passed**. All of child-1's tests pass. On the attack itself:
    - 14 (h) rows and both (i) attacks did not raise.
    - `stty intr`, both `-isig` rows and the late-check row did not raise.
    - `p[vi-mode]` stayed healthy.
    - In (r), the marker exists.
    - Both v5 `enable -n` reproducers stayed healthy.
    - The `kill -STOP` case blocked longer than 5 s.
  - On missing API: the `tiocsti_path` tests (3), the (s) loop (`HOOK_BUILTINS`), the
    `H`-content test, and `test_j_late_check_…` (no `_check_termios` on base).
  - Passed on base, as expected: `h[stdin-null]`, (m), `p[bracketed-paste-off]`,
    `p[readline-off]`, the plain-PS1 test, `enable -n echo`.
  - *Answer-before-check variant* (no wait): `test_j_late_check_…` fails. So that test
    checks the wait.
  - With the fix: **130 passed** in `tests/test_session.py` (75 s). Also **130 passed** with
    every CPU busy (`nproc` busy loops, 116 s). The whole suite through
    `engine/scripts/run-suite.sh` gave **367 passed, "T3 PASS"**.
- **(b) Production path? Yes.** Every test starts the real `Session`, which runs the real
  `RCFILE` in a real bash 5.3.9 on a real PTY. The only patching is:
  - `_spy_on_pty_writes`, which wraps `_write_all` and still calls it;
  - `_slow_termios_check`, which sleeps and then calls the real `_check_termios`. It adds
    delay only; the real check still decides.
- **(c) Does the fixture include the fault? Yes.** Each test runs the real attack in bash:
  - `stty -icanon -echo -isig`, `stty -isig`, the real `PS4` payload with `set -x`, and
    real `enable -n`;
  - the late read is a real 0.15 s delay in nl-shell, the reviewer's own reproducer.

  Markers are absolute paths under `tmp_path`, so they show up if the payload runs. It
  does run on iteration 1's code: the (r) marker exists there.

## Environment / runner / commit-readiness

- Tests: the bundle venv's `python3 -m pytest` from the worktree root (what
  `engine/scripts/run-suite.sh` runs), each run wrapped in `timeout`. Full suite through
  `run-suite.sh` with `PDCA_WORKTREE` set. I did not run `run-verify.sh`
  (`$PDCA_VERIFY_BASE` is unset here); the driver's C4 run covers it.
- External dependencies, all present: `ptyprocess`; `/proc/<pid>/syscall`, `stat`, `fd`
  readable; `legacy_tiocsti = 0`; `ptrace_scope = 1`.
- Formatter / hooks: the target has none (no ruff/black/pre-commit in `pyproject.toml`, no
  `.pre-commit-config.yaml`). `git diff --check` is clean. CI's docs checks pass:
  `scripts/docs_links.py` (0 broken) and `scripts/docs_checks.py immutability` (OK, run
  on a temporary commit that I then undid with `git reset`). New Python lines are within
  the file's width, except the existing one-line `PROMPT_COMMAND` in `RCFILE`, which must
  match the spec block.
- Working files are in `$PDCA_WORKTREE/.scratch/` (untracked, not in `patch.diff`).

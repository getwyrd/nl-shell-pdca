# Adversarial review: persistent-bash-session-core (issue_140, round 3)

Method: pytest is not installed in this sandbox, so I could not re-run the C4 gate. I used the frozen log instead (`gate-logs/C4-verify.log`: red 88/88, all `ModuleNotFoundError`; green 88/88; T3 325 passed). Bash 5.3.9 and `ptyprocess` are present, so I drove the production `Session` from `$PDCA_TARGET/src` directly with small probe scripts in my cwd. The red leg proves only that the module is new, which is the expected shape for new code. The real question is whether the green tests prove the invariants. One of them does not (first bullet).

- NEEDS-HUMAN [human] — **I2 is broken by a DEBUG trap combined with `set -T` (functrace). Every later command is reported "ran False" while the session stays healthy.** Repro on a fresh session, run as confirmed commands:
  1. `__k=0; trap 'if [[ $BASH_COMMAND == "PS1="* ]]; then __k=$__nls_seq; __nls_seq="x["; elif [[ $BASH_COMMAND == *__nls_done* && $__nls_seq == "x[" ]]; then __nls_seq=$__k; fi' DEBUG; set -T`
  2. `true`
  3. `touch MARK_T; echo printed; (exit 7)`

  Observed: the third command returns `ran=False, status=7, output=''` with `degraded=False`, and `MARK_T` exists on disk. `echo after` behaves the same way. How it works: with functrace on, the trap fires inside `__nls_snap` just before its last line, `PS1='\$ ' PS2='> '` (`src/nl_shell/session.py:179`). That is after `H` was sampled (`session.py:145-161`). The trap corrupts `__nls_seq`, so PS0's `$((__nls_seq + 1))` (`session.py:120`) errors and no `S` is sent. The trap then restores the counter before `__nls_done` runs, so `D n+1` arrives without `S`, and `src/nl_shell/pty_protocol.py:232-234` reports that as healthy "nothing ran". The brief says this child **holds** I2 ("whether `S` is emitted must not depend on any state confirmed code can assign (variable, readonly flag, trap) unless `H` covers it"). Here `H` does cover `__nls_seq`, but only at a point the attacker can step around. The (g) test `tests/test_session.py:627-631` passes for the wrong reason: its `debug-trap` case has no `set -T`, so the trap never fires inside the hooks. The threat model (`.oss-scanner/threat_model.md:172-173`) and spec §3 list `extdebug`/`functrace` as "not yet detected (#141)", but they do not say this breaks I2. A human has to decide: either I2 is not held in this child and the brief and docs should say so, or add functrace to `H` (`shopt -po functrace`, or `$-` containing `T`) and add a `set -T` variant to `_I2_ATTACKS`.

- NEEDS-HUMAN [impl] — **`read x </dev/tty` slips past the prompt rule, and `run()` with the default `timeout=None` hangs forever.** `_stdin_is_terminal` (`src/nl_shell/session.py:691`) accepts fd 0 only when its `st_rdev` equals the PTY slave's. `/dev/tty` is the same terminal but has device 5:0, so bash blocked in `read(0)` on it never counts as "reading the terminal". Observed: `run("read x </dev/tty", timeout=4)` → `SessionTimeout` after 4.0 s, with no degrade before that. Without a timeout it never returns. The redirect check added this round fixed `read < <(…)` but over-narrowed the rule. Suggested fix: also treat fd 0 as the terminal when it is `/dev/tty` (major 5, minor 0, the controlling terminal). Add `read x </dev/tty` to `test_read_with_no_input_degrades`. A related case: after `exec </dev/tty` the session reports healthy, then every next `run()` degrades before writing anything, with the misleading reason "the shell did not return to its prompt" (`session.py:627`). That fails closed, but the same fix would cover it.

- NEEDS-HUMAN [impl] — **Readline turned off (`set +o emacs`, no `bind` involved) is not named in the known gaps.** After `set +o emacs` the session stays healthy. The next `run("touch MARK_E; echo hi")` writes the paste bytes into a non-readline reader, and only afterwards degrades with "output could not be delimited" (`session.py:594-598`). The command did not run as confirmed (`MARK_E` was not created). The docs mention only "readline state (`bind`, …)" (`.oss-scanner/threat_model.md:174`, spec §3). Name `set +o emacs`/`set +o vi` next to `bind` as #141 scope. This is a one-line doc fix and keeps within the patch-size limit.

- Minor, no action needed: `exec </dev/null` makes bash exit, and the next `run()` degrades with "cannot read /proc/<pid>/syscall (PermissionError)" (`session.py:646-649`) instead of "the shell exited". It fails closed, but the reason is misleading.

Tried and could not refute, all on the production code:
- `export TERM=dumb` degrades at its own snapshot.
- `bind 'set enable-bracketed-paste off'` degrades at the next command, as documented.
- `IFS=x`, `set -u`, `set -o posix` and `shopt -s failglob nullglob` all keep the hooks working, with correct output and status.
- A command that prints `ESC [?2004l` or a partial `ESC ]7700;` keeps its own output intact.
- A trailing newline, multi-line input and blank-only input give the right ran/not-run results.
- The forbidden-byte check (`pty_protocol.py:139-148`) matches §5.2.
- The red-to-green evidence itself is sound for new code. The tests import `nl_shell.session` inside each test and exercise the real `Session`, not a copy.

<!-- pdca:leaf-complete -->

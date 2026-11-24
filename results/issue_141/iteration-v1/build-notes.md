# Build notes — #141 persistent-bash-session tamper checks

Base: the worktree HEAD `0771812` ("pdca-integrate: issue_140"), the wave-2 folded branch
holding child-1 (#140). Every `path:line` below is on that base plus this patch (post-fix
line numbers unless marked "base"). The brief said to cite the docs on `c47c5c2`; on this
base the Conformance "Open questions" bullet the brief cites as `:195-196` was at
`docs/design/specs/pty-protocol/v1.md:323-324` (base), and that is the one I closed.

Files: `src/nl_shell/session.py`, `src/nl_shell/pty_protocol.py`, `tests/test_session.py`,
`docs/design/specs/pty-protocol/v1.md`, `.oss-scanner/threat_model.md`.

## What changed and why

### Inside bash: `H` (Table A rows) — `src/nl_shell/session.py` RCFILE (`:160-269`)

- `HOOK_BUILTINS` (`session.py:95-113`): every builtin the hooks call. Brief's list plus
  `:` and `return` (the hooks call both: `|| \builtin :`, `__nls_ret`). `shift` was
  dropped from the hooks (now `"${@:2}"`), so it is not listed. `read` is last on
  purpose: child-1's `test_hook_state_vars_cover_the_rcfile` variable scan reads
  `read <word>` as a variable, and `read return` in the loop list tripped it. I reordered
  the tuple rather than edit child-1's test.
- `H` now also prints (`__nls_snap`, the `$( { … } 2>&1 )` block):
  `shopt -p promptvars extdebug`; `shopt -po functrace histexpand emacs vi`;
  `DEBUG/RETURN traps: $2`; `declare -p PS4 BASH_XTRACEFD` (in the same loop as the hook
  state vars); `declare -p __nls_x` (whether xtrace was on); a `builtin <name>
  enabled|not enabled` line per `HOOK_BUILTINS` (filtered from `enable -a` with `case`,
  so `enable -n` of any other builtin stays only in `B`); `bind -v`; and `bind -p/-s/-X`
  for keymaps `emacs vi-insert vi-command` (`_KEYMAPS`, `session.py:120`).
- DEBUG/RETURN traps must be read at the top level: I checked live that `trap -p DEBUG`
  inside a function (no functrace) prints nothing. So the `PROMPT_COMMAND` element now
  passes `"$(\builtin trap -p DEBUG RETURN 2>&1)"` as `$2` to `__nls_snap`
  (`session.py:267`).
- `$?`/`PIPESTATUS` are now passed as arguments by `PROMPT_COMMAND`
  (`\__nls_done "$?" "${PIPESTATUS[@]}"`) instead of `\builtin set -- …` inside the hook.
  Reason: with `set` disabled, `set --` failed, `$1` was empty and `D` was malformed, so
  `enable -n set` fired `malformed`, not `h-changed`. Passing them as arguments needs no
  builtin. `BASHOPTS` is passed as `$3` for the same reason.
- xtrace (decision 13, v5's approach): `__nls_done` records `[[ -o xtrace ]]` in
  `__nls_x` and turns xtrace off; `__nls_snap`'s last command turns it back on
  (`session.py:264`). `__nls_x` is added to `HOOK_STATE_VARS` (`:89`) and to `__nls_pre`.
- Every command substitution in the hooks now has `2>&1`, including PS0
  (`2>&1 >&3`, so stderr goes to the expansion, not into fd 3), `F`, `L`, `B`, `X`,
  `jobs`, the `declare -p` loops of `H` and `V`, and the PS1/PS2 check (whose
  `|| __nls_v=` keeps the old behaviour on failure).
- Guard (`session.py:180-204`): `__nls_done` starts with `\builtin printf '' && { … }`
  and `PROMPT_COMMAND` runs `__nls_snap` only on `&&`. Without it, `enable -n builtin`
  made every `\builtin` call fall into Ubuntu's `command_not_found_handle`, which runs
  `/usr/lib/command-not-found` (about 0.6 s each, measured). The hooks then took well over
  5 s before bash reached the prompt, so the run hit the caller's timeout instead of
  degrading. With the guard it costs one lookup, then the prompt rule fires (about 1.6 s
  measured). The block ends in `(( 1 ))` so a failed scratch assignment inside it does not
  skip the snapshot, which would change child-1's behaviour.
- The rcfile already had `bind 'set enable-bracketed-paste on'` after `~/.bashrc` (base
  `session.py:100`). I kept it and documented it in the spec (§1.2). I did not add
  another copy.

### Codes — `src/nl_shell/pty_protocol.py:32-38, 182-186`; `session.py:130-139`

`ProtocolTracker.degrade(reason, code)` with `degraded_code`; `SessionDegraded.code`;
`Session.degraded_code` (`session.py:653`). The tracker's codes: `malformed`,
`out-of-order`, `missing-record`, `control-closed`, `baseline-invalid`, `h-changed`. The
session's: `exited`, `proc-unreadable`, `not-at-prompt`, `timeout`, `undelimited`,
`outside-check`, `stopped`, `tiocsti`, `prompt-not-fixed`; the prompt rule reuses
`missing-record`. Reason texts are unchanged except the `H` one, which still contains
"H differs", which child-1's tests assert on.

Scope note: the brief lists only `session.py` for production code, but the `H`
comparison and the other protocol degrades live in `pty_protocol.py`. Giving `h-changed`
a code there is 41 diff lines. The other option was to subclass `ProtocolTracker` in
`session.py` and map reason text to codes, which is fragile string matching. I took the
direct edit.

### Outside checks (Table B) — `session.py:899-990, 1043-1060`

- Termios via `tcgetattr` on the master. Linux returns the slave's settings (I checked
  live: the master shows readline's `-icanon -echo` at the prompt). Readline changes
  some settings while it waits for a line. I measured them live: `ICRNL` in iflag,
  `ICANON|ECHO` in lflag, and cc `VTIME`, `VMIN`, `VDISCARD`, `VLNEXT`. It also forces
  `ISIG` on (checked live: after `stty -isig`, the prompt state still shows isig=1, and
  the running state shows isig=0). `_termios_view` (`:1048`) masks those plus readline's
  documented `INLCR|IXON|IXANY|ISTRIP|INPCK`. On top of that, `ISIG` must be on whenever
  the state is not readline's prepped state (`_readline_prepped`, `:1057`).
- When the checks run:
  - Before every paste (`run`, `:699`): stopped, fds exactly as at baseline, termios.
  - When `D` arrives (`:734`): termios only. This is the moment `stty -isig` is visible,
    because bash is in the hooks, not in readline. Fds are not checked at D, because the
    user's `PROMPT_COMMAND` (run after D) can briefly redirect fd 1, e.g. child-1's test
    `>> ~/pc.log`.
  - When `E` arrives (`:737`): stopped, fds, termios. fd 1 may be the control pipe for an
    instant, because `__nls_enc … >&3` redirects bash's own fd 1 while it writes a record.
    That one case is allowed, and only at E.
  - On every poll tick (`:759`): stopped. It runs after the prompt rule's syscall read, so
    child-1's "unreadable syscall" test still sees the syscall path in the reason.
- TIOCSTI: `tiocsti_path` constructor keyword (`:461`), read once at start
  (`_check_tiocsti`, `:613`). The session starts degraded with code `tiocsti` if the file
  is missing, unreadable or not `0`.
- `_check_fixed_prompts` (`:597`), for (i): a `PS1`/`PS2` that `~/.bashrc` made readonly
  (or gave another attribute) is expanded at every prompt, after the snapshot. The
  session starts degraded with code `prompt-not-fixed`. A plain `PS1` is replaced by
  #140's hook before it is ever shown, so it needs nothing more.

### Docs

- Spec: §1.2 (forced bracketed paste, the guard, `2>&1`, the extended "What this
  protects" list), §3 (`H`'s new rows; `T`/`X`/`B` reported-only, with `H` holding only
  the hook builtins' enable state; the outside checks and when they run), §4.2 (new
  triggers and the code list), and the Open-questions bullet closed. The reference rcfile
  block is regenerated from `RCFILE`; child-1's `test_spec_reference_rcfile_is_the_one_in_use`
  enforces this.
- Threat model: replaced child-1's interim bullet with the decision-2 list, each with its
  follow-up (ADR-0024, #134, #137, #136, #138, #135). No catch-all sentence.

## Changes to child-1's tests (both needed, neither weakens a check)

- `_NLS_HOOK` (a hard-coded copy of the old `PROMPT_COMMAND` element) is replaced by
  `_nls_hook()` (`tests/test_session.py:811`), which reads the element from the `RCFILE`
  in use. A literal copy would have been red on the red leg for a reason that has nothing
  to do with the attack. With the function, child-1's tests stay green with the fix
  reverted (shown below). The I3 assertion is unchanged: nl-shell's element is last.
- Nothing else in child-1's tests changed.

## Deviations from the brief's wording (for the human)

1. **(r) "no marker"** cannot hold literally. bash traces `PROMPT_COMMAND`, so with `set -x`
   the `PS4` payload runs for the first traced hook commands. That is before D, which
   makes it code that runs before the snapshot. I checked this live: the marker exists
   right after `set -x`, even with no nl-shell code involved. The test asserts what can be
   true (v5's form): the session degrades at that snapshot with `h-changed`, and the
   marker does not grow after that. So the payload never runs after the snapshot or for
   a later paste.
2. **(i) PS1**: a plain `PS1` from `~/.bashrc` is never expanded (#140 replaces it before
   the first prompt), so the session stays healthy and there is no marker
   (`test_i_bashrc_plain_ps1_is_replaced_before_it_is_ever_expanded`). The case where the
   expansion does happen is a readonly `PS1` using `${ …; }` (a bash 5.3 command
   substitution that runs in the current shell; `$( … )` runs in a subshell and cannot
   change bash's bindings). That case now starts degraded (`prompt-not-fixed`) with no
   marker.
3. **(m) and (p): red on #140 is not true for all of them.** The base rcfile already
   forces bracketed paste on after `~/.bashrc` (base `session.py:100`), so (m) passes on
   #140. It is a regression guard, not red-leg evidence. (p) `bracketed-paste-off` and
   `readline-off` also pass on #140, because #140 degrades them through `undelimited`.
   (p) `vi-mode` is red on #140, since the session stays healthy. I did not fake a red.
4. **(s) exception set** = `HOOK_BUILTINS_WITHOUT_RECORDS = ("builtin", "printf")`
   (`session.py:116`). Why each one:
   - `printf` writes every record.
   - `builtin` is the prefix of every hook call.

   With either disabled, no `D` is written, so the prompt rule fires (`missing-record`).
   I measured every other hook builtin live: each gives `h-changed` within about 0.05 s.

## Known limits I found (not fixed; flag at sign-off)

- **`stty -isig` relies on reading at D.** Readline forces ISIG on while it waits, so only
  a read while bash is outside readline can see it. That window runs from D to the end of
  the snapshot: the user's `PROMPT_COMMAND` plus about 10 command substitutions plus a
  3 ms bind dump. If Python read D only after bash had reached readline, `-isig` would be
  missed for that command. It would also never be caught later, because readline always
  shows ISIG on. Measured: 20/20 passes with every CPU busy (`nproc` busy loops), plus 6
  normal repeats. A deterministic fix needs a back-channel from nl-shell to bash (the hook
  waits for an ack before returning to readline). That means a new fd, a `read -u` in the
  hook, and a write in `_wait_for_result`: about 15 lines plus a spec change to §1. It
  also adds a blocking wait to every prompt. I did not do it here.
- **`enable -n return` with a `PROMPT_COMMAND` that calls `return`, plus Ubuntu's
  `command_not_found_handle`.** Example: VTE's `__vte_prompt_command` when `VTE_VERSION`
  is set. The handler itself calls `return`, so it recurses through subshells without
  end. bash never reaches the prompt, and `run()` ends only by the caller's timeout
  (`timeout`), or never if there is none. The same happens for `enable -n [` followed by
  any `[`. Nothing is pasted, so I1 holds, but it is a hang. The test fixture removes
  `VTE_VERSION`, so `test_s_every_hook_builtin_disabled_degrades` does not hit it. This
  belongs with #136 (unbounded waits). Not claimed in the docs.
- **False degrades (fail closed):**
  - `bind -v` includes `history-size`, which follows `HISTSIZE`, so a confirmed
    `HISTSIZE=…` degrades.
  - `stty sane` or a program that leaves the terminal changed degrades by the outside
    check.
  - The brief asks for ALL readline variables, so I did not exclude any.
- `stty -icanon -echo … -isig` together, set up to look exactly like readline's prepped
  state, would pass the ISIG rule. The brief marks `icanon`/`echo` as not tested.

## Rejected alternatives (with cost)

- **Keep `\builtin set -- "$?" …` in `__nls_done`.** Then `enable -n set` gives
  `malformed`, not `h-changed`, and `set` would have to join the exception set, which the
  brief limits to "stops writing records". Passing the values as arguments changes 1
  `PROMPT_COMMAND` line and removes 3 hook lines.
- **Guard as a separate wrapper function** (`__nls_done() { \builtin printf '' &&
  __nls_done_body "$@"; }`). This avoids re-indenting about 22 lines, but adds a hook
  function name that `HOOK_STATE_VARS`, the `declare -f` list and child-1's coverage test
  would all need. I re-indented instead.
- **Read DEBUG/RETURN traps out of `$1` (the full `trap -p` text) in the hook.** That
  needs parsing quoted trap strings that can contain newlines and `' DEBUG`-looking text.
  Passing a second, narrower `trap -p DEBUG RETURN` is one argument.
- **Check fds when `D` arrives too.** This gave false degrades from the user's
  `PROMPT_COMMAND` redirections (`>> ~/pc.log` in child-1's test). Fds are checked at `E`
  and before the paste instead.

## Refuting my own test

- **(a) Genuine red? Yes.** I reverted `session.py`, `pty_protocol.py` and the spec to
  base (`git checkout HEAD -- …`) and kept the new `tests/test_session.py`. Result:
  **29 failed, 97 passed**, and all 93 of child-1's tests passed.
  - Failures on the attack itself:
    - `DID NOT RAISE SessionDegraded`: 14 (h) cases, both (i) attack tests, `stty intr`,
      `stty -isig`, and the (r) PS4 case.
    - Session stayed healthy: `p[vi-mode]` and both v5 `enable -n` reproducers.
    - Run blocked longer than 5 s: the `kill -STOP` case.
  - Failures on missing new API: `tiocsti_path` (3 tests), `HOOK_BUILTINS` (the (s) loop),
    and the new `H`-content test.
  - Passed on base, as expected: `h[stdin-null]` (the brief calls it a regression guard),
    (m), `p[bracketed-paste-off]`, `p[readline-off]`, the plain-PS1 test and
    `enable -n echo`.

  After restoring the fix: **127 passed** in `tests/test_session.py`, and the whole suite
  through `engine/scripts/run-suite.sh` gave **364 passed, "T3 PASS"**. Both were run
  before the last two small cleanups (reuse `CODE_MISSING_RECORD`; fail closed if
  `tcgetattr` fails at start). After those I re-ran `tests/test_session.py`: 127 passed.
- **(b) Production path? Yes.** Every test starts the real `Session` from
  `nl_shell.session`, which runs the real `RCFILE` in a real bash 5.3.9 on a real PTY.
  Nothing is mocked. The only patching is the existing `_spy_on_pty_writes`, which wraps
  `_write_all` and still calls the real one. The TIOCSTI test points the real constructor
  keyword at a temp file, which is the brief's method; the real file is read when the
  keyword is not given (`/proc/sys/dev/tty/legacy_tiocsti` is `0` here).
- **(c) Does the fixture include the fault? Yes.** Each test runs the real attack command
  in bash:
  - `bind -x`, `stty intr`, `exec >/dev/null`, a real `kill -STOP $$`, real
    `enable -n <name>`;
  - a `~/.bashrc` written to the suite's temp HOME.

  The marker paths are absolute in `tmp_path`, so a marker shows up if the payload runs.
  On base it does run for the bind cases (the paste fires the rebound `\r`); with the fix
  nothing is written to the PTY (`pty_writes == []`).

## Environment / runner

- I ran tests with the bundle venv: `.venv/bin/python3 -m pytest` from the worktree root,
  which is what `engine/scripts/run-suite.sh` runs. The full-suite run went through
  `run-suite.sh`. I did not run `run-verify.sh` myself: `$PDCA_VERIFY_BASE` is unset in
  this shell, so the driver's C4 run is the check for that.
- External dependencies were all present: `ptyprocess`; `/proc/<pid>/syscall`, `stat` and
  `fd` readable; `legacy_tiocsti = 0`; `ptrace_scope = 1`.
- Formatter / commit hooks: the target has none configured (no ruff, black or pre-commit
  in `pyproject.toml`; no `.pre-commit-config.yaml`). `git diff --check` is clean, and the
  Python files compile. New Python lines stay within the file's existing width, except
  the bash `PROMPT_COMMAND` line inside `RCFILE` (152 characters), which has to stay one
  line to match the spec's reference block.
- I left working files in `$PDCA_WORKTREE/.scratch/` (untracked, not in `patch.diff`).
  The harness reclaims the worktree.

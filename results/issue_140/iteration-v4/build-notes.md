# Build notes — issue_140 (persistent-bash-session-core), iteration 4

## Base

Built in `$PDCA_WORKTREE` = `/home/eddie/nl-shell/nl-shell.pdca-wt-l0`, HEAD `2ddc3e8`
(`origin/pdca-integration/main-r2546dbf9639f`, the branch C4 applies the patch to; the
brief names `c47c5c2`, but iteration 1 failed C4 because its patch did not apply here).
I applied the iteration-3 patch (it applied cleanly) and made only the four fixes the
round-3 sign-off asked for. Line numbers below are on this tree with the patch applied.

## The four sign-off items

### 1. Aliases inside the hooks (High)

The sign-off's suggested fix was "`\builtin` everywhere". I did that, but it is not
enough on its own. I checked bash 5.3.9 and found that aliases on **reserved words** also
apply inside a `$( … )` that is parsed again at run time: with `alias for='echo X'
if='echo Y' '{'='echo Z'`, a function whose body has `$( for …; do …; done )`,
`$( if …; fi )` or `$( { …; } )` gets syntax errors or runs the alias. `__nls_snap`'s
H and V bodies use `for`, `if` and `{`. You cannot backslash-quote a reserved word
(`\for` is no longer a keyword), so `\builtin` alone would leave that hole open.

What I did:
- `__nls_snap` turns `expand_aliases` off as its second command and turns it back on
  after `E` only if it was on (`src/nl_shell/session.py:134-135`, `:171`). The old state
  is read from `$BASHOPTS` (read-only, so confirmed code cannot fake it) into a
  positional parameter in the same simple command that turns off functrace (`:134`). No
  new state variable is needed, so `H` does not change when the user switches
  `expand_aliases`.
- `\builtin` everywhere in PS0 (`:106`, written `\\builtin` because bash decodes prompt
  escapes first), `__nls_done`, `__nls_ret`, `__nls_enc` and every `$( … )` in
  `__nls_snap` (`:111-172`). This is the fix the sign-off asked for. It is defence in
  depth now that aliases are off.
- The false claim ("an alias that changes one changes H") is gone from the comment
  (`session.py:81-94`) and the spec (`docs/design/specs/pty-protocol/v1.md:134-138`).

Tests (`tests/test_session.py:671-690`): `test_aliases_cannot_reach_inside_the_hooks`
with `[builtin-printf]` (the reviewer's exact repro: `alias builtin=" " printf=__p`) and
`[reserved-words]` (`for`/`if`/`{`). Each must end degraded or report the next command
as ran with output `printed` and status 7. Both then check that, after `alias
ls='touch PWNED' builtin=' ' alias=':'` and `ls`, `L` still lists `ls`. A third part
checks that the user's own aliases still work after a snapshot, and that `shopt -u
expand_aliases` is kept (both are needed because the hook now toggles the option).

### 2. DEBUG trap + `set -T` (functrace)

Adding functrace to `H` alone does not hold. I showed that a DEBUG trap running inside a
function can rewrite that function's positional parameters (`set -- HACKED` in the trap
changes `$1` for the next command), and with `-T` the trap is also inherited into every
`$( … )`. So anything the hooks sample while functrace is on can be forged, `H` included,
before it is sent.

What I did: the **first** command of each hook turns functrace off, in one simple command
that also captures what it needs:
- `__nls_done`: `\builtin set +T -- "$?" "$-" "${PIPESTATUS[@]}"` (`session.py:116`).
  `$?`, `$-` and `PIPESTATUS` are expanded before `set` runs, so status capture and
  turning off `-T` happen together. The trap can still fire once before this command
  (as it can at top level before any hook). After it, the trap never fires inside the
  hook again. `__nls_f` keeps `T` if functrace was on (`:117`). It is in
  `HOOK_STATE_VARS` (`:64`), so `H` carries it.
- `__nls_snap`: `\builtin set +T -- "$1" "${BASHOPTS-}"` (`:134`). The top-level DEBUG
  trap could turn `-T` back on between the two hooks; this turns it off again before `H`
  is taken.
- The rcfile runs `set +H +T` after `~/.bashrc` (`:98`), so a `~/.bashrc` with `set -T`
  does not make the first command degrade (the baseline would otherwise have `T`).
  The spec's §1.2 rule says so (`v1.md:46`).

Result: `set -T` degrades at that command's own snapshot (the `H` reason now names
functrace, `src/nl_shell/pty_protocol.py:296`), and so does `shopt -s extdebug` (it sets
`T` in `$-`). The reviewer's exact repro degrades at its first command. A "hidden"
variant (the trap turns `-T` on only before `__nls_done` and clears `__nls_f` and `-T`
before `__nls_snap`) stays healthy and reports every command honestly: once `-T` is off
inside the hooks the trap cannot touch the counter after `H`.

**Not held: `extdebug`.** With `extdebug`, `set +T` does not stop the DEBUG trap from
running inside functions (I checked this: the trap still fired in the function after
`set +T`), and a trap that returns non-zero **skips** the next command, so it can skip
`set +T` itself. No in-band hook can defend against that. My two crafted `extdebug`
attacks did not break I2 (one degraded via `__nls_f`, one stayed honest), but I cannot
show that it holds in general. The docs therefore say "I2 is not claimed against it
(#141)": comment `session.py:91-94`, spec `v1.md:139-141`, threat model
`.oss-scanner/threat_model.md:173-174`. That is Table A row 2, child-2 scope, as the
brief says.

Tests: `_TABLE_A_ROW_1["functrace"] = "set -T"` (`tests/test_session.py:546`), so it
must degrade at its own snapshot and the next `run("echo hello")` must raise without
writing. `_I2_ATTACKS["debug-trap-functrace"]` (`:640`) runs once per name in
`HOOK_STATE_VARS`. `test_functrace_debug_trap_never_hides_a_command` (`:653-668`) has the
reviewer's exact repro (`corrupt-after-h`) and the `hidden` variant.

`test_snapshot_cut_short_after_done_degrades` (`:359`) used `shopt -s extdebug; set -T;`
plus a trap that skipped from `__nls_enc H` on. With this change that setup degrades
earlier, by `H` at its own snapshot, so `E` does arrive and the test's "no E" assertion
failed. That is a stronger outcome. The test exists to cover the "D arrives, E never
does" path, so I changed only its setup to an `extdebug` trap that skips `__nls_snap`
itself (`[[ $BASH_COMMAND != *__nls_snap* ]]`). It still asserts the same reason, "the
snapshot did not finish after the shell returned to a prompt".

### 3. `read x </dev/tty`

`_stdin_is_terminal` now also accepts fd 0 when it is `/dev/tty` (char device 5:0,
`_DEV_TTY` at `session.py:214`, check at `:687`). bash's controlling terminal is the PTY
(`ptyprocess` makes the session leader's controlling terminal the PTY slave), so
`/dev/tty` opened by bash is this PTY. `test_read_with_no_input_degrades` is
parametrized over `read x` and `read x </dev/tty` (`tests/test_session.py:746`). Before
the fix the `/dev/tty` case raised `SessionTimeout` at 5 s; now it degrades with the
prompt-rule reason in about 1 s. This also covers the reviewer's `exec </dev/tty` side
case, which now gets the prompt-rule reason instead of "did not return to its prompt".

### 4. Docs: readline turned off

`set +o emacs` / `set +o vi` are named next to `bind` as #141 scope in the threat model
Known-gaps bullet (`.oss-scanner/threat_model.md:175-176`), spec §3 (`v1.md:185-187`)
and the rcfile comment (`session.py:93-94`).

## Size

The size signal uses 1 KiB = 1024 bytes (`pdca.toml:346` `patch_kb = 100`; the harness
divides by 1024), so the limit is 102,400 bytes. The patch is **100,456 bytes**
(iteration 3: 98,157). To pay for the new code and tests I:
- cut the rcfile comment in `session.py` from 35 lines to 14 (`:81-94`). It repeated
  spec §1.3, so it now points there;
- merged `test_vector2_pipestatus`/`test_vector3_exit_status` into one parametrized
  test with the same two cases;
- moved the I2 "third command" check into one helper (`_ends_degraded_or_ran`,
  `tests/test_session.py:622`) shared by the old and new I2 tests;
- put the `set -T` case into the existing Table A table instead of adding a new test.
No test case was removed: there are 95 tests, up from 88.

## Verification (the project's runners)

- `engine/scripts/run-verify.sh` on the bundle: `C4 PASS — red without the fix (95 of 95
  failed), green with it` (95 passed).
- That red is mostly `ModuleNotFoundError`. To show that the new tests catch the real
  bugs, I ran the same runner on a delta bundle (inside the worktree,
  `.scratch/delta-bundle/`). Its patch is only this round's code changes (the
  iteration-3 `session.py`/`pty_protocol.py` → now) plus the test file. Result:
  `C4 PASS — red without the fix (6 of 95 failed)`. The six that fail on the
  iteration-3 code are exactly the targets:
  - `table_a_row_1…[functrace]`: DID NOT RAISE (`set -T` stayed healthy);
  - `functrace_debug_trap…[corrupt-after-h]`: `(False, 7, '')`, i.e. "ran False" while
    healthy, the reviewer's finding;
  - `aliases_cannot_reach…[builtin-printf]`: `(False, 7, '')`, the reviewer's finding;
  - `aliases_cannot_reach…[reserved-words]`: `ls` missing from `L`;
  - `read_with_no_input_degrades[read x </dev/tty]`: `SessionTimeout`;
  - `spec_reference_rcfile_is_the_one_in_use` (the spec copy was updated).
  Afterwards the worktree matched `patch.diff` byte for byte.
- Whole suite (`engine/scripts/run-suite.sh`): `332 passed`, T3 PASS.
- `python3 -I scripts/docs_links.py`: 0 broken links.
- Formatter / hooks: the target configures none (no pre-commit config, no
  ruff/black/flake8 in `pyproject.toml`; CI runs pytest plus `scripts/docs_checks.py`
  and `scripts/docs_links.py`). The Python files compile, no new line is over 100
  columns, and I reflowed the two spec lines my edits made long. I did not run
  `docs_checks.py immutability BASE HEAD`, because it needs two commits and I made no
  commit. I did not touch either ADR this round.

## Refuting my own test

- **(a) Genuine red?** Yes. With the whole fix reverted, 95/95 fail. With only this
  round's code reverted (iteration-3 code, new tests), the 6 tests above fail, each
  for the reason the reviewers reported (`ran False` healthy, `SessionTimeout`, `ls`
  hidden from `L`, `set -T` not detected). Two of the new cases (`[hidden]`,
  `debug-trap-functrace`) and the `[reserved-words]` first half also pass on the old
  code. They are extra coverage, not the binding red.
- **(b) Production path?** Yes. Every session test starts a real bash 5.3.9 on a PTY
  through `nl_shell.session.Session`, with the production `RCFILE`, and reads the real
  fd-3 records. The no-write checks spy on `session._write_all` and still call the real
  function.
- **(c) Fixture includes the fault?** Yes. Each attack (the alias definitions, the DEBUG
  trap with `set -T`, `read x </dev/tty`) is run as a confirmed command in the real
  session, and the following `touch MARK; echo printed; (exit 7)` really runs. The
  marker file is checked on disk.

## Open for the human

- `extdebug` + DEBUG trap: I2 is not claimed (docs say so, #141). Builtin-shadowing
  functions are still documented, not detected (#141), as the round-2 sign-off chose.
- Side effect of item 2: functrace no longer survives across prompts. The hooks turn it
  off at every prompt, and a command that turns it on degrades. A user who wants `set -T`
  in nl-shell's session cannot have it. I judged that acceptable for an interactive shell.
- The patch is 1.9 KiB under the size signal, not far under.

No external dependency beyond the brief's `ptyprocess` and `proc-syscall` was needed.

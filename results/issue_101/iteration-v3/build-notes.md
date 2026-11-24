# Build notes — issue 101 (persistent-bash-session-core), iteration 3

Target: eduralph/nl-shell @ main, base `8c95e05` (worktree `$PDCA_WORKTREE`, which is also
`origin/pdca-integration/main-r2546dbf9639f`, the bundle's `stack-base`). New files are
cited at their line in the patched tree; edited docs at their patched line.

This iteration starts from the iteration-v2 patch (applied unchanged) and fixes the three
carry-forward findings. The iteration-v1 and iteration-v2 notes
(`iteration-v2/build-notes.md`) still hold for the rest of the design; nothing they
describe was undone.

## Carry-forward findings and what I did

### 1. Key bindings of `\r` and `\e[200~` were not covered by `H`

`H` now has, for each input keymap (`emacs`, `vi-insert`, `vi-command`), every line of
`bind -p`, `bind -s` and `bind -X` whose key sequence starts with `"\C-m` or `"\e[200~`
(`src/nl_shell/session.py:130-135`). Those are the only keys §5 sends outside the paste
(readline reads the paste body raw until `ESC [201~`, it does not look the body bytes up
in the keymap). "Starts with" also catches a binding to a longer sequence such as
`"\e[200~e"`, which turns `\e[200~` into a prefix and lets the paste's first byte pick a
macro. `bind` prints a CR as `\C-m`, so `"\r"` and `"\C-m"` bindings look the same.
Pure parameter expansion and builtins (`read`, `case`, `printf`), no external program
(decision 4). It runs inside the same `$( … )` as the rest of `H`, so no extra fork.

What I ruled out: putting the whole `bind -p/-s/-X` output (27 648 bytes for the three
keymaps) into `H`. I measured it: `set -o vi` changes 6 lines of the emacs keymap
(readline rebinds some terminal keys on a mode switch: `"\e[2~"`, `"\e[5C"`, …), so a
user typing `set -o vi` would degrade the session. The filtered lines don't change on
`set -o vi`/`set -o emacs` or a `TERM` change (checked in a scratch bash, and the test
below).

Reviewer's reproducer: `bind '"\r": " ; touch MARK_CR\n"'` now degrades at its own
snapshot ("H differs"), so `echo hello` is refused and `MARK_CR` is never created.

Tests: `test_changed_key_bindings_degrade` (`tests/test_session.py:534`), seven cases —
macro on `\r`, on `\C-m`, on `\r` in `vi-insert` only, on `\e[200~`, on `\e[200~e`, a
`bind -x` shell command on `\C-m`, and `\C-m` rebound to `abort`. Each asserts "H
differs", that the next command is refused, and that the marker file does not exist.
`test_vi_mode_switch_keeps_the_bindings_unchanged` (`:548`) guards against the false
positive above.

### 2. History expansion turned back on was not detected

`H` gets a `history expansion on` line when `[[ -o histexpand ]]` (`session.py:126`). The
rcfile turns it off (`set +H`, `session.py:90`), so the baseline never has the line and
a `set -H` degrades at its own snapshot. Reviewer's reproducer
(`history -s 'touch MARK_H'; set -H`, then `echo "x!t"`): the first command degrades,
the second is refused, the marker is never created. Test:
`test_history_expansion_turned_on_degrades` (`:557`).

I did not put all of `$-` into `H`: it also holds `u`, `x`, `e` and so on, and
`test_nounset_without_path_keeps_the_snapshot_whole` expects `set -u` to keep the session
healthy.

### 3. Code after `E` could set `__nls_ps0` and hide a command that ran

Cause: `__nls_done` cleared the "S already sent" guard (`__nls_ps0`) near its start,
before the snapshot. Anything that ran later at the same prompt — the DEBUG trap before
`__nls_started=1`, the user's `PROMPT_COMMAND`, a function it calls — could set it to the
current number, so the next command's `PS0` sent no `S` and the command was reported as
"nothing ran" with its output dropped, on a healthy session.

Fix (option (b)-style, the cause rather than one vector): the guard is now cleared by
the **last** command of `PROMPT_COMMAND`, `__nls_started=1 __nls_ps0=`
(`session.py:143`), after the snapshot and after the user's hooks. The DEBUG trap fires
*before* that command, so the assignment wins; after it, bash only expands `PS1` and
reads the line with readline before `PS0`. The rcfile starts it as `__nls_ps0=` rather
than unset (`session.py:97`), so it always exists, and `H` now records its attributes
only (cut at `=`, like `__nls_seq`, `session.py:122-124`) because its value at snapshot
time is the number of the command that just ran. A `readonly __nls_ps0=…` still shows up
as `declare -r` and degrades (`test_changed_hook_state_degrades[ps0-guard-readonly]`
stays green). Comment `session.py:58-61`, spec note `v1.md:122-124`.

I chose this over option (a) (`trap -p DEBUG` in `H`): (a) closes only the DEBUG-trap
path, not the user-hook path the reviewer also named, and it would degrade every user who
sets a DEBUG trap in a command. The diff for (b) is 3 changed rcfile lines; (a) would be
1 line in `H` plus a second fix for the user-hook path.

What (b) does not close, written into the threat model's Known-gaps bullet
(`.oss-scanner/threat_model.md:172-178`): a `PS1` written to run code (its expansion
comes after the reset), and changes to history expansion or key bindings made after the
snapshot by the user's own hook (seen only at the next command's snapshot, after that
command ran). Both need code that targets nl-shell's hooks or a user hook a confirmed
command redefined — decision 2's deliberate-subversion gap. I didn't add `PS1` to `H`:
prompt tools (starship, powerline) rewrite `PS1` from the user's `PROMPT_COMMAND` at every
prompt, which would degrade those users on every command.

Tests: `test_debug_trap_setting_the_start_guard_cannot_hide_a_command` (`:500`, the
reviewer's reproducer) and `test_user_hook_setting_the_start_guard_cannot_hide_a_command`
(`:510`, a `~/.bashrc` hook function redefined to set the guard). Both assert the marker
command comes back `ran=True`, status 7, output `printed\n`, session healthy
(`_assert_ran_and_reported`, `:493`).

## Doc changes this iteration

- Spec `docs/design/specs/pty-protocol/v1.md`: §1.3 reference block regenerated from
  `RCFILE` (`test_spec_reference_rcfile_is_the_one_in_use` keeps them equal); new note on
  where the guard is cleared (`:122-124`); §3 `H` wording lists history expansion and the
  key bindings (`:156-161`); §4.2 `H` trigger says "settings and key bindings".
- Threat model Known-gaps bullet (`threat_model.md:172-178`): adds history expansion and
  key bindings to what `H` detects, and the after-the-snapshot limit above.

## Accepted fail-closed limit (brief: "say so in build-notes")

Unchanged: a command that runs inside bash itself for over 1 s (`read x`, `wait`, a
builtin-only loop) keeps bash in the foreground and degrades the session (spec §4.2,
threat model Known gaps).

## Verification

All runs through the project's runners, instance `.venv` (ptyprocess 0.7.0), host bash
5.3.9.

C4 (`engine/scripts/run-verify.sh`, with `PDCA_BUNDLE`, `PDCA_WORKTREE`,
`PDCA_VERIFY_BASE=origin/pdca-integration/main-r2546dbf9639f`):

```
76 failed in 0.80s  (pytest exit 1; ran 76, failed 76, setup errors 0, import/collection errors 0)
PDCA-EVIDENCE: C4 PASS — red without the fix (76 of 76 failed), green with it
```

T3 (`engine/scripts/run-suite.sh`): `253 passed`, T3 PASS.
Docs CI: `docs_links.py` 0 broken; `docs_checks.py immutability` OK, run from the base's
copy against a throwaway commit object built with a separate index file (HEAD and the
real index not moved).

### Refuting my own test

- **(a) Genuine red?** Yes. Reverting all production files: 76 of 76 fail (C4 red leg).
  That only proves the module is missing, so I also undid each fix on its own in
  `session.py` (script `.scratch/mutate.py`) and re-ran C4; each time exactly the matching
  tests went red, then the file was restored (`cmp` against the saved copy):

  | Fix undone | Red |
  |---|---|
  | binding lines out of `H` | `test_changed_key_bindings_degrade` ×7 (+ spec-sync) |
  | history-expansion line out of `H` | `test_history_expansion_turned_on_degrades` (+ spec-sync) |
  | guard back to "unset inside `__nls_done`" | `test_debug_trap_…` and `test_user_hook_…` (+ spec-sync) |

- **(b) Production path?** Yes. Every session test runs the real
  `nl_shell.session.Session` with the real `RCFILE` on a real bash 5.3.9 PTY and fd-3
  pipe; no mocks. The new tests use `run()` and the real `~/.bashrc` path under the
  suite's temporary HOME.
- **(c) Fixture includes the fault?** Yes. Each fault is set up for real in the live bash:
  the reviewers' exact `bind` macros (plus `bind -x` and a rebind to `abort`), the real
  `history -s …; set -H`, a real DEBUG trap writing `__nls_ps0`, and a real `~/.bashrc`
  hook function redefined by a confirmed command. Each test checks a marker file the
  injected code would create.

## Housekeeping

No formatter or lint hook is configured in the target (no `.pre-commit-config.yaml`,
nothing in `pyproject.toml`; CI runs tests and the docs checks), and neither `ruff`,
`black` nor `pyflakes` is installed. All three Python files compile; lines are ≤ 100
characters except `session.py:98`, the `PS0=` line inside the rcfile string, which is
shell text that can't be wrapped (same as before). Scratch files are under
`$PDCA_WORKTREE/.scratch/` (untracked, not in `patch.diff`).

Not pushed, no PR opened.

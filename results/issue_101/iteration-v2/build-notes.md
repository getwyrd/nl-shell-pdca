# Build notes — issue 101 (persistent-bash-session-core), iteration 2

Target: eduralph/nl-shell @ main, base `8c95e05` (worktree `$PDCA_WORKTREE`). New files are
cited at their line in the patched tree; edited docs at their patched line.

This iteration starts from the iteration-v1 patch (applied unchanged) and fixes the five
carry-forward findings. Everything in the iteration-v1 notes about the rest of the design
still holds; the parts that matter are repeated at the end.

## Carry-forward findings and what I did

### 1. Snapshot cut short after `D` → `run()` hung forever (`set -u; unset PATH`)

Two fixes, as the reviewer suggested:

- **The foreground-group timer now runs until `E`, not until `D`**
  (`src/nl_shell/session.py:464-473`). Before, the check was `done is None and
  bash_in_foreground`; now it is just `bash_in_foreground`, and the reason names what is
  missing: "no done record …" before `D`, "the snapshot did not finish after the shell
  returned to a prompt" after it. This is spec §4.2 trigger 1 ("a record is missing")
  enforced for snapshot records. The hook itself runs in bash's process group (its
  `$(...)` forks are not job-controlled), so the timer already counted it; a normal
  snapshot takes well under 1 s.
- **The rcfile is safe under `set -u`**: `__nls_enc P "${PATH-}"` (`session.py:111`). I
  went through every other expansion in the hooks: `$1`/`$2` are always passed, the
  locals are assigned before use, `${__nls_ps0-}` and `${__nls_once[...]-}` already had
  defaults, `"${__nls_user_pc[@]}"` of an empty array is fine under `set -u` on bash ≥ 4.4.
  The new `H` items avoid `${x@a}` because that errors under `set -u` for an unset
  variable or an empty array (checked: `bash -c 'set -u; unset x; echo "${x@a}"'` →
  "unbound variable"); they use `declare -p … 2>&1` instead.

Tests:
- `test_nounset_without_path_keeps_the_snapshot_whole` (`tests/test_session.py:313`):
  `set -u; unset PATH` then `echo still here`, both through `run()` with its **default**
  (no) timeout, each bounded by the test in a thread (`_run_default_timeout`, `:86`).
  Asserts the snapshot's `P` is `""` and the session is healthy.
- `test_snapshot_cut_short_after_done_degrades` (`:325`): needs a real snapshot cut short
  after `D` now that `set -u` no longer does it. I use a DEBUG trap with `set -T` and
  `extdebug` that skips every hook command from `__nls_enc H` on, so `D 1`, `F`…`J` arrive
  and `E` never does, with bash back at its prompt. Through `run()` with no timeout, it
  must degrade with the new reason within 5 s. (I first tried a SIGINT from the trap: bash
  then re-runs the hook, sends a stray `D 2 130`, and degrades by "out of order" — not the
  hang path, so not useful as a test.)

### 2. Output silently empty when a confirmed command turns bracketed paste off

`bind 'set enable-bracketed-paste off'`, `TERM=dumb` and (found while testing)
`set +o emacs` all stop readline from writing `ESC[?2004l`, and every later result had
`output == b""` on a healthy session. Two layers:

- **`H` now covers the readline state the capture depends on** (`session.py:120-122`):
  the `enable-bracketed-paste` value from `bind -v` (extracted with parameter expansion,
  no `grep`), and a `line editing on` line when `-o emacs` or `-o vi` is set. I checked
  `bind -v` works inside the hook's `$(...)` and that it reports `off` after `TERM=dumb`
  (readline re-inits on a `TERM` change). So the command that makes the change degrades
  at its own snapshot, and the next command is never sent. Switching between emacs and
  vi mode is not a change (`vi` users keep working: test (h) `set -o vi` stays green).
- **A Python backstop** (`session.py:438-446`, `_Output.delimited` at `:204`): if a
  command's `S` arrived and its `D` arrives with no end-of-paste marker seen, the session
  degrades: "the command's output could not be delimited (readline did not end a
  bracketed paste)". This catches a change `H` cannot see because it happens after the
  snapshot — the user's own `PROMPT_COMMAND` runs after `E`.

I chose "degrade" over "capture from `S` onward". `S` arrives on fd 3 while the echo and
the output arrive on the PTY; when Python reads `S`, the PTY buffer may already hold both
the echo (written before `S`) and the first output bytes (written after), and the two
channels give no way to split them. Any split would be a guess at the PTY text, which the
brief rules out. Degrading is honest and fail-closed.

Tests: `test_command_turning_bracketed_paste_off_degrades[paste-off|term-dumb|no-line-editing]`
(`:604`) and `test_bracketed_paste_off_between_snapshots_degrades` (`:616`, a `~/.bashrc`
`PROMPT_COMMAND` that turns paste off after each snapshot; asserts the backstop's reason,
so `H` alone can't make it pass).

### 3. `interrupt()` at an idle prompt degraded the session

`interrupt()` now writes `\x03` only while the tracker is in `Phase.RUNNING` (`S` seen,
`D` not yet) and returns `True`; otherwise it writes nothing and returns `False`
(`session.py:374-388`). `Phase.SENT` (paste written, no `S` yet) is excluded too: Ctrl-C
there could flush part of the paste in readline and leave a stray `CR` to submit.

Residual race, documented rather than fixed: if bash finishes the command and starts the
hook in the ≤ 50 ms before the run loop reads `D`, a Ctrl-C written in that window lands
in the hook or at the prompt, and the session degrades (bash re-runs the hook and sends a
`D` out of order, as seen in the SIGINT experiment above). That fails closed and never
misreports. I did not close it by draining the control channel inside `interrupt()`:
`interrupt()` is called from another thread while `run()` reads that same fd, and two
readers on one pipe would split records. Stated in the docstring, spec §4.2 (`v1.md:179`)
and the threat-model bullet (`threat_model.md:168-176`).

Tests: `test_interrupt_at_a_prompt_writes_nothing` (`:239`): before any command and after
one, `interrupt()` returns `False`, `_write_all` (spied, still calls through) is never
called, no record arrives in 1 s, and the next command is `seq 2` and healthy. Vector 10
now also asserts the mid-command `interrupt()` returned `True`.

### 4. The hooks' state variables were not covered by `H`

`H` now includes `declare -p __nls_once __nls_ps0` in full and, for `__nls_seq` and
`__nls_started`, the `declare -p` text cut at `=` — attributes and name, without the
value that changes every command (`session.py:115-118`). Normally `__nls_ps0` is unset
when `H` is computed (the hook unset it just before), so it reads "not found"; a
`readonly __nls_ps0=2` survives the unset and shows up as `declare -r __nls_ps0="…"`.

The reviewer's reproducer (`readonly __nls_ps0=2`, then `touch m3; echo printed; (exit 7)`)
now degrades at the first command; the second is refused and `m3` is never created. Test:
`test_changed_hook_state_degrades[ps0-guard-readonly|started-readonly|once-readonly]`
(`:479`). I first included `declare -i __nls_ps0` as a case; it does not degrade, and
that is correct — the hook's `unset` removes the attribute with the variable, so it has no
effect on the next command. I dropped the case rather than make it pass.

`readonly __nls_seq` was already caught (the `D` repeats the old number → out of order);
its attributes are in `H` now as well.

### 5. Comment claimed more than the code does

Reworded (`session.py:67-73`): builtins the hooks use are called through `builtin`,
**except `local` and `return`**, which are bare (bash refuses `builtin local` with an
array assignment), so a function named `local` or `return` changes the hooks. Same
exception in the spec's notes on the reference rcfile and in the threat-model Known-gaps
bullet. I kept `return` bare as well: it would work as `builtin return`, but `local`
cannot, so the gap stays either way and one stated exception is simpler than two
different rules.

## Other changes this iteration

- `pty_protocol.py:301-303`: the `H` degrade reason now says "the hook functions, their
  state variables or the settings they need". Tests match on "H differs", unchanged.
- Spec `docs/design/specs/pty-protocol/v1.md`: §1.3 reference block regenerated from
  `RCFILE` (test `test_spec_reference_rcfile_is_the_one_in_use` keeps them equal); notes
  gain the `local`/`return` exception and the `set -u` note; §3 `H` wording lists the new
  items (`:147`); §4.2 trigger 3 now covers "after `D` until `E`" (`:172`), a new bullet
  for "readline did not end the bracketed paste" (`:176`), and a paragraph on Ctrl-C at a
  prompt (`:179`).
- Threat model Known-gaps bullet (`threat_model.md:168`): lists the hook state and paste
  setting in what `H` detects, the `local`/`return` exception, the Ctrl-C race and `set -e`.

## Found while testing, not fixed (out of this brief's scope)

`set -e` followed by a failing command ends the interactive bash (bash's own behaviour),
and the session degrades with "the shell exited". That fails closed; making the hooks
`errexit`-proof would mean changing a shell option the user set, which is not this
child's job. Named in the threat-model bullet.

## Accepted fail-closed limit (brief: "say so in build-notes")

Unchanged from iteration 1: a command that runs inside bash itself for over 1 s
(`read x`, `wait`, a builtin-only loop) keeps bash in the foreground and degrades the
session, by the back-at-a-prompt rule (spec §4.2, threat model Known gaps). Extending the
timer to `E` does not widen this: during the snapshot bash is always in the foreground,
and the hook runs in tens of milliseconds.

## Verification

All runs through the project's runners, instance `.venv` (ptyprocess 0.7.0), host bash 5.3.9.

C4 (`engine/scripts/run-verify.sh`, `PDCA_BUNDLE`, `PDCA_WORKTREE`, `PDCA_BRIEF_BASE` set):

```
65 passed in ~15 s
65 failed in 0.65s  (pytest exit 1; ran 65, failed 65, setup errors 0, import/collection errors 0)
PDCA-EVIDENCE: C4 PASS — red without the fix (65 of 65 failed), green with it
```

T3 (`engine/scripts/run-suite.sh`): `242 passed`, T3 PASS.
Docs CI: `docs_links.py` 0 broken; `docs_checks.py immutability` OK, run from the base's
copy against a throwaway commit object (`git commit-tree`, HEAD not moved).

### Refuting my own test

- **(a) Genuine red?** Yes, on two levels. Reverting all production files: 65 of 65 tests
  fail (C4 red leg). That only proves the module is missing, so I also undid each fix on
  its own in `session.py` and re-ran the C4 green leg; each time exactly the matching new
  test(s) went red, then the file was restored (checked with `cmp`):
  | Fix undone | Red |
  |---|---|
  | `${PATH-}` → `$PATH` | `test_nounset_without_path_keeps_the_snapshot_whole` (+ spec-sync test) |
  | timer back to `done is None and …` | `test_snapshot_cut_short_after_done_degrades` (the `run()` thread was still blocked at 5 s) |
  | backstop disabled | `test_bracketed_paste_off_between_snapshots_degrades` |
  | paste/line-editing lines out of `H` | `test_command_turning_bracketed_paste_off_degrades` ×3 (+ spec-sync) |
  | state variables out of `H` | `test_changed_hook_state_degrades` ×3 (+ spec-sync) |
  | `interrupt()` guard removed | `test_interrupt_at_a_prompt_writes_nothing` |
- **(b) Production path?** Yes. Every session test runs the real `nl_shell.session.Session`
  with the real `RCFILE` on a real bash 5.3.9 PTY and fd-3 pipe. The two spies (vector 12
  and the idle-interrupt test) wrap the module's own `_write_all` and still call it.
  `_run_default_timeout` calls the real `run()` with its real default (no timeout) — the
  thread is only the test's own guard against a hang.
- **(c) Fixture includes the fault?** Yes. Each fault is injected for real in the live
  bash: `set -u; unset PATH`; a DEBUG trap that truly stops the hook after `D`; `bind …
  off`, `TERM=dumb`, `set +o emacs`; a `~/.bashrc` `PROMPT_COMMAND` that turns paste off;
  `readonly` on the hook's state variables; a real `\x03` path (spied, not mocked) at an
  idle prompt.

## Housekeeping

No formatter or lint hook is configured in the target (no `.pre-commit-config.yaml`,
nothing in `pyproject.toml`; CI runs tests and the docs checks), and neither `ruff` nor
`pyflakes` is installed. All three Python files compile; lines are ≤ 100 characters except
`session.py:91`, the `PS0=` line inside the rcfile string, which is shell text that can't
be wrapped. Scratch files are under `$PDCA_WORKTREE/.scratch/` (untracked, not in
`patch.diff`).

Not pushed, no PR opened.

# Build notes — issue 140 / persistent-bash-session-core (round 6)

## Base

Built on `origin/main` = `c47c5c2` in `$PDCA_WORKTREE`
(`/home/eddie/nl-shell/nl-shell.pdca-wt-l0`). I started from `iteration-v5/patch.diff`,
which applies cleanly to `c47c5c2` (`git apply --check` passed). Code citations are on the
patched tree.

## What this round changes (carry-forward)

### 1. C5: value changes to the hooks' scratch variables now degrade (I2-b)

**The bug.** The reviewer showed that `__nls_n=42`, `__nls_st=42`, `__nls_v=changed`,
`__nls_c=changed` and `__nls_ps=(42)` each left the session healthy. The hooks write to
those variables before `H` is taken (v5 `session.py:113-139`), so the confirmed command's
value was gone by the time `H` was built. Attribute changes (`declare -i`, `readonly`)
survived, which is why v5's `state-variable-integer` row passed and hid the gap. The brief
claims "value AND attributes" for every `__nls_*` hook state variable, so this was a real
gap in a claimed case.

**The fix (removes the cause, not a guard).** Before the hooks change anything, keep a copy
of what the command left behind, and put that copy in `H`:

- `__nls_done` now runs, right after it saves `$?`/`PIPESTATUS`:
  `__nls_pre=$(\builtin declare -p __nls_pre __nls_c __nls_n __nls_ps __nls_st __nls_v 2>&1) || \builtin :`
  (`src/nl_shell/session.py:117-118`). `__nls_pre` lists itself, so the command's own value
  of `__nls_pre` is in the copy too: `$( … )` runs before the assignment.
- `__nls_pre` is added to `HOOK_STATE_VARS` (`session.py:66`), so the existing `H` loop
  prints `declare -p __nls_pre`, which is the copy.
- `__nls_snap` resets all scratch variables to the rcfile's starting values just before `E`
  (`session.py:171`), and the rcfile sets the same values at start (`session.py:105`). So
  with no tampering, every copy is the same text, matching the baseline byte for byte.
- `\builtin`-quoted and `|| \builtin :`, so it is safe with user aliases and under `set -e`
  (an `unset __nls_v` makes `declare -p` fail; the error text lands in the copy and degrades).
- Comment at `session.py:54-59` and `:85-89` updated; spec §3 `H` bullet
  (`docs/design/specs/pty-protocol/v1.md:199-203`) now says the same thing instead of "the
  hooks reset their scratch variables before `H` is taken". The spec's reference rcfile
  (`v1.md:57-135`) was regenerated from `RCFILE` (the spec test checks they match).

**Why not just list the scratch values in `H` as they are at snapshot time?** That is what
v5 did, and it cannot work: by then the hooks have overwritten them. **Why not drop the
scratch variables (use positional parameters only)?** `__nls_snap` needs a loop variable
and `$( … )` results across 12 statements, and `__nls_done` needs `__nls_st`/`__nls_ps`
across the user hook loop. Rewriting both functions to use only `"$@"` would touch about 30
of the ~70 rcfile lines and both spec copies, for the same result. The copy is 3 rcfile
lines plus one name.

**The test** (`tests/test_session.py:553-573`,
`test_hook_state_value_changes_degrade_at_their_own_snapshot`) loops over every name in
`HOOK_STATE_VARS` (not just the scratch ones), assigns `42` and then `(42)`, and asserts
the session degrades with a result for `seq == 1` and "H differs", then that `echo hello`
is refused without writing to the PTY. `__nls_seq` is the one exception: `__nls_seq=42`
makes `D` arrive as 43, so it degrades one record earlier, at that command's own `D`
("out of order"); the test checks that reason instead.

### 2. Docs no longer claim more than the code gives for I3 (R1)

The reviewer's case: `declare -r PS1='$(touch X)\$ '` can't be overwritten, so it runs at
the next prompt, after `E`. `PROMPT_COMMAND+=('touch X')` runs after nl-shell's hook in the
same prompt cycle. Both degrade at their own snapshot, so I2 holds, but the docs said
"nothing confirmed code sets runs after the snapshot" and "no prompt string … is ever
expanded". I reworded, as the reviewer suggested:

- spec §1.2 bullet (`v1.md:51-53`): nl-shell sets `PS1`/`PS2` "unless a command gave them
  attributes (such as `readonly`), which `H` shows (§3)".
- spec §1.3 "What this protects", second bullet (`v1.md:157-165`): user elements run before
  the snapshot; a change to the value of a plain or exported `PS1`/`PS2` is overwritten;
  a change to `PS0`, `PROMPT_COMMAND`, or `PS1`/`PS2` attributes degrades at that
  command's own snapshot "but the code it set may still run once after that snapshot,
  before nl-shell refuses further commands".
- threat model interim bullet (`.oss-scanner/threat_model.md:182-186`): same wording.
- `session.py:87-88` comment: "plain or exported ones only; others show in H".

ADR-0014 Decision 1 says "nl-shell sets `PS1` and `PS2` after the snapshot". I left it: it
describes what the rcfile does, makes no "nothing runs" claim, and the brief limits the ADR
edit to those sentences.

**For the human at sign-off:** this rewording is narrower than the brief's own I3 text
("nothing confirmed code sets runs after the snapshot"). The brief's I3 has the same gap
the reviewer found in the docs. The code is unchanged here; only the claim is corrected.

New test row: `ps1-readonly-command` = `declare -r PS1='$(touch PS1_RAN)\$ '` in
`_TABLE_A_ROW_1` (`tests/test_session.py:532-533`). It asserts degraded at `seq == 1` with
"H differs" and that the next command is refused. It does not check whether `PS1_RAN`
exists; that would only pin the documented "may run once" behaviour. This row passes on
v5 too (the code already degraded); it guards the documented behaviour, it is not a red
test for the fix.

## Red → green (project runner)

`PDCA_BUNDLE=… PDCA_WORKTREE=… ./engine/scripts/run-verify.sh` (the C4 gate):

```
== C4 green leg: … 93 passed in 44.31s
== C4 red leg:   … 93 failed in 1.25s
PDCA-EVIDENCE: C4 PASS — red without the fix (93 of 93 failed), green with it
```

Whole target suite (`python3 -m pytest tests/`, wrapped in `timeout 500`, instance venv):
270 passed.

## Self-refutation (forced)

- **(a) Genuine red?** Yes, and not only the coarse revert. The C4 red leg reverts every
  production hunk (93/93 fail, since each test imports the modules inside the test). For
  this round's fix I also put back only v5's `session.py` (extracted from
  `iteration-v5/patch.diff`), kept everything else, and ran
  `-k "value_changes or table_a"`: `test_hook_state_value_changes_…[scalar]` and `[array]`
  both failed with `DID NOT RAISE SessionDegraded`; 11 others passed. Then I restored the
  file; `git diff` is byte-identical to `patch.diff` (checked with `cmp`).
- **(b) Production path?** Yes. The test starts the real `Session` (`ptyprocess` →
  `bash --rcfile <RCFILE>`, bash 5.3.9) and reads the real fd-3 records. The only double is
  the spy that wraps `_write_all` and still calls it.
- **(c) Fixture includes the fault?** Yes. The fault is the real confirmed command
  `__nls_v=42` etc. sent through `Session.run`, for every name in `HOOK_STATE_VARS`, against
  real bash; nothing is curated out.

## Commit-readiness

The target has no formatter, pre-commit config or linter config. Its CI runs pytest, the
docs immutability check and the link check. `python3 -I scripts/docs_links.py` → 63 links,
0 broken. `git diff --check` is clean. No line in the new Python files is over 100
characters. The changed docs (both specs, ADR-0013/0014, glossary, threat model) are the
same set as v5, which passed the immutability check.

## Size

`patch.diff` is 104,682 B, over the ~100 KB target (v5: 102,072 B). Per file:
`tests/test_session.py` 39.8 KB, `session.py` 29.7 KB, pty-protocol spec 15.3 KB,
`pty_protocol.py` 12.1 KB, everything else under 2.1 KB. This round added about 2.6 KB:
the new test (~1.5 KB), the rcfile lines in both copies, and the reworded doc text. I cut
no claimed test or listed doc edit.

## For the PR description (publish)

As in v5: per decision 11, say that this brief supersedes the #101 issue text and the #140
body where they differ (hook order, prompt rule, 5 s / < 3 s limits, decision 10, `TERM`
in `H`, I2-d, `/dev/tty`, `proc_root`, the pinned job notice, the threat-model bullet).
Add: `H` now carries `__nls_pre`, a copy of the scratch variables taken before the hooks
change them; and the I3 wording says what really happens with readonly `PS1`/`PS2` and
appended `PROMPT_COMMAND` elements.

## Housekeeping

I wrote nothing outside the worktree and the bundle. The red check swapped `session.py`
in place inside one Python process and restored it in a `finally` block.
`tests/test_session.py` was copied to the bundle as `test_session.py`.

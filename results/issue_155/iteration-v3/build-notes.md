# Build notes — #155 failure-classifier-by-exit-code (iteration 3)

## Base

Built in `$PDCA_WORKTREE` (`/home/eddie/nl-shell/nl-shell.pdca-wt-l0`) on the folded wave
base `pdca-integration/main-r2546dbf9639f` @ `5d3d291` (from `stack-base` /
`stack-base-tip`). That base has #140's `session.CommandResult`
(`src/nl_shell/session.py:375-389`) and `pty_protocol.Snapshot` / `Done`
(`src/nl_shell/pty_protocol.py:51-72`), so the brief's "report blocked" branch does not
apply. Both files stay new; `router.py` is untouched, as the brief asks.

Citation drift (same as iterations 1 and 2): the §4.1 sentence the brief cites at
`docs/design/specs/pty-protocol/v1.md:370-372` on `cefb359` is at `:375-376` on this base.

## Starting point

I applied iteration 2's `patch.diff` (it applies cleanly) and changed only the privilege
word matching plus its test rows. Precedence, `Failure` fields, rule 4, display safety and
signals are unchanged; see `iteration-v1/build-notes.md` and `iteration-v2/build-notes.md`
for that rationale. All line numbers below are in the patched worktree.

## What changed, and why

Iterations 1 and 2 were both sent back for the same kind of bug: a spelling bash turns into
`sudo` that the matcher had not been shown yet. Iteration 2 fixed the spellings it was given
(`$'sudo'`, `${X:-sudo}`) and the reviewers then found the next ones (NUL in `$'...'`,
brace expansion, empty expansions). Adding a third set of spellings to the regex would
repeat the rejected approach. So this iteration adds one general pass that does what bash
does to a word before it runs it, and matches every result.

1. **NUL in `$'...'`** (C5 finding). `_decode_ansi_c` now ends the decoded string at the
   first NUL (`src/nl_shell/failure_classes.py:241`). I checked bash 5.3.9 first:
   `printf '[%s]\n' $'su\0x'do` prints `[sudo]`, and `$'sudo\0ignored'` prints `[sudo]`.
   So bash cuts the quoted segment at the NUL, and the rest of the word still follows.
   This one change covers `\0`, `\x00`, `\u0000` and `\c@`, because they all decode to NUL
   first.

2. **The expanded pass** (`:244-411`), used by `is_privileged` through `_candidates`
   (`:453-455`). For each confirmed text (and each alias value it follows):
   - line continuations are removed and `$'...'` is decoded, as in the coarse pass;
   - `_as_braces` (`:294-331`) walks the text once and rewrites each expansion as the
     values it may take. `$NAME`, `$@`/`$1`/..., `$(...)`, backticks and `${NAME...}`
     are dropped, because their value is not in the text and may be empty
     (`sud${X}o`, `sud$(:)o`, `` sud`:`o ``, `pkexec$X`, `doas$IFS`). `${NAME-word}` and
     the other operators that can give their word (`:-`, `=`, `:=`, `+`, `:+`) become
     `{,word}`, with the word rewritten the same way, so nested defaults work
     (`${X:-su}do`, `sud${X:-${Y:-}}o`). `$((...))` and `$[...]` become "empty or one
     digit", so `run$((0))` gives `run0`. Nesting is followed by `_matching`
     (`:275-291`);
   - quotes, backslashes and `$` are removed, the text is cut at whitespace and shell
     operators (`_EXPANDED_SPLIT`, `:263`), and each word is brace-expanded the way bash
     does it (`_brace_expand`, `:377-395`, with `_brace_close` `:334-359` and
     `_sequence` `:362-374`): comma lists, nested braces, and `{a..b}` / `{1..9..2}`
     sequences. A brace with no comma and no sequence stays literal, as in bash
     (`awk '{print $1}'` is unchanged). Checked against bash: `s{u,}do` gives
     `sudo sdo`, `r{u,}n{0..1}` gives `run0 run1 rn0 rn1`, `{r..s}udo` gives
     `rudo sudo`.
   - Each result is also split at `=` and `:` (`_PIECE_SPLIT`, `:264`), like the coarse
     pass, so `FOO=s{u,}do` still yields `sudo`.

   **Cap.** One word with more than `MAX_EXPANSIONS = 4096` results (`:262`) raises
   `_TooMany`, and `is_privileged` then returns True (`:437`, `:448`). Without the cap a
   word like `{1..100000}` would cost time; without the "True", padding a word with
   braces would be a new way past the rule. Over-matching is the direction decision 1
   accepts. The pinned row is `echo {1..100000}` (PRIVILEGE). A normal command will not
   hit this (`{1..100}` and `{a,b}{c,d}` stay OTHER, tested).

   The old shlex pass and coarse pass (`words`, `_coarse`, `:196-220`) are kept, so the
   words inside `$(...)` and backticks are still matched (`echo $(sudo x)`), and every
   iteration-1/2 row still passes. `_unresolved_word` (rule 4) still uses `words` only;
   the new pass is privilege-only.

### Rejected alternatives

- **More regex special cases in `_coarse`** (iteration 2's approach, and what the
  reviewers' "cheap fix" lines describe). Each is 1-2 lines, but each new spelling needs
  another one; the previous two rounds show the list does not end. The general pass is
  about 165 lines (`:244-411`), and it covers every spelling the round-2 reviewers reported plus the ones
  next to them (`s{x,u}do`, `{r..s}udo`, `run$((0))`) without a rule per spelling.
- **Delete every `{`, `}` and `,` instead of expanding braces.** About 1 line. It finds
  `s{u,}do` (`sudo`) but not `s{x,u}do` (it gives `sxudo`, bash gives `sudo`). Real brace
  expansion is exact.
- **Try every combination of "empty" and "operand" per `${...}`.** That is what
  `{,word}` already does, by letting the brace expander do the combinations, so no extra
  code was needed.
- **Subsequence or substring matching** ("does `sudo` appear anywhere in the word"): it
  would make `pseudo`, `sudoers-check` and `visudo` privileged, and the brief requires
  `pseudo x` to be OTHER.

## Still out of reach (not in the carry-forward's build list)

No word matcher can see a name whose value is not in the text. These need the policy
gate's real parse (#12) or running the shell, and I did not add rows that would pretend
otherwise:

- a name built in variables (`c=sud; c+=o; $c x`) or by a substitution's output
  (`$(printf '\163udo') x`, `${X/foo/sudo}` with `X` set);
- a session function that wraps sudo (`s() { sudo "$@"; }`): the snapshot carries only
  function names, and decision 1 names aliases only;
- `ran=False` with privileged text (`sudo foo (`) is OTHER, as decision 2 orders.

More over-matching now, accepted by decision 1: a word with more than 4096 expansions,
and any word whose brace expansion contains a privilege name (`ls {a..z}{a..z}` contains
`su`, which is what bash would produce too).

## Red → green (project runner)

With `PDCA_BUNDLE=results/issue_155` and `PDCA_WORKTREE` set:

- `engine/scripts/run-verify.sh` (C4): `PDCA-EVIDENCE: C4 PASS — red without the fix
  (184 of 185 failed), green with it`. Red leg: pytest exit 1, 0 import/collection
  errors. The one test that passes on the red leg is the ASCII check on the test file
  itself, which does not depend on the production module.
- `engine/scripts/run-suite.sh` (T3): `837 passed`, `PDCA-EVIDENCE: T3 PASS`.

Extra check for this iteration: C4 can only revert to "no module", so I put iteration 2's
`failure_classes.py` (taken from `iteration-v2/patch.diff`) in place and ran the new test
file against it (venv pytest, run from Python with a 180 s timeout, because the `timeout`
binary is not runnable in this sandbox). Result: `29 failed, 156 passed`. The failures are
exactly the new privilege rows (3 NUL, 6 brace, 17 empty-expansion / operand rows, the
cap row, the brace alias row) and `test_only_other_goes_to_the_reader`, which walks the
privilege table. `${X:-su}do x` and `${A:-su}${B:+x}do x` already passed on iteration 2,
but only by luck: the leftover piece `su` is itself a privilege program. They stay as rows
because the new pass catches them for the right reason. Afterwards I restored the module
and checked that `git diff` matches `patch.diff` byte for byte.

## Refuting my own test

- **(a) Genuine red?** Yes. C4 reverts the production file: 184 of 185 fail, 0
  collection errors. Against iteration 2's module (the rejected approach), the 29 new
  checks fail, so the new rows bind this iteration's fix, not just the module's existence.
- **(b) Production path?** Yes. Every test calls the real
  `nl_shell.failure_classes.classify` on a real `session.CommandResult` holding a real
  `pty_protocol.Snapshot`. `$PATH` checks run the production `router.is_executable_file`
  on real files in `tmp_path`. Only the package lookup is a fake, because the brief makes
  it an injected callable and the real one is #156's.
- **(c) Fixture includes the fault?** Yes. The new privilege rows are the exact strings
  the reviewers reported (`$'sudo\0ignored' x`, `s{u,}do x`, `{s,}udo x`, `pk{e,}xec x`,
  `pkexec$X x`, `pke${X}xec x`, `doas$IFS x`, `sud${X}o apt update`, `sud$(:)o x`,
  `` sud`:`o x ``, and the rest), each checked as a classify() call with status 1 (and
  `sud${X}o x` with 127, which iteration 2 made NOT_FOUND). Before writing the rows I ran
  the forms in bash 5.3.9 with `printf` in place of the program to confirm bash really
  builds `sudo` from each. No real sudo or other privilege tool runs, as the brief
  requires.

## Commit-readiness

The target has no formatter, linter or pre-commit config (no `.pre-commit-config.yaml`,
no ruff/black section in `pyproject.toml`), and CI (`.github/workflows/tests.yml`) only
runs `python -m pytest`. `git diff --check` is clean, no line is over 95 characters, and
the test file is pure ASCII (its own test checks that). `failure_classes.py` has the two
`§` in comments that iterations 1 and 2 also had.

No push, no PR.

# Build notes — #155 failure-classifier-by-exit-code (iteration 2)

## Base

Built in `$PDCA_WORKTREE` (`/home/eddie/nl-shell/nl-shell.pdca-wt-l1`) on the folded wave
base `pdca-integration/main-r2546dbf9639f` @ `5d3d291`. That base has #140's
`session.CommandResult` (`src/nl_shell/session.py:375-389`) and `pty_protocol.Snapshot` /
`Done` (`src/nl_shell/pty_protocol.py:51-72`) with the fields the brief lists. It is not
plain `main`, so the "report blocked" branch of the brief does not apply.

Citation drift (same as iteration 1): the §4.1 sentence the brief cites at
`docs/design/specs/pty-protocol/v1.md:370-372` on `cefb359` is at `:375-376` on this base.

## Starting point

I re-applied iteration 1's `patch.diff` (`iteration-v1/patch.diff`, it applies cleanly)
and changed only what the carry-forward asks for. The rest of the design (precedence,
`Failure` fields, rule 4, display safety, signals) is unchanged; see
`iteration-v1/build-notes.md` for that rationale. Both files are still new; nothing else
in the tree is touched (`router.py` unchanged, as the brief asks).

## What changed in this iteration, and why

All line numbers are in the patched worktree.

1. **Privileged words bash builds before running them** (carry-forward C5 + adversary +
   security review). The coarse pass `_coarse` (`src/nl_shell/failure_classes.py:216-220`)
   now normalises the text before splitting:
   - backslash-newline pairs are removed (`_LINE_CONTINUATION`, `:80`), so `sud\<nl>o`
     reads as `sudo`;
   - every `$'...'` segment is replaced by its decoded value (`_ANSI_C`, `:81`, and
     `_decode_ansi_c`, `:223-240`). The decoder follows `bash(1)` QUOTING: the simple
     escapes, `\nnn` octal, `\xHH`, `\uHHHH`, `\UHHHHHHHH`, `\cX`. So `$'sudo'`,
     `$'\x73udo'`, `$'\163udo'`, `$'sudo'` and `pk$'exec'` all give a `sudo` /
     `pkexec` fragment;
   - the operator of a `${NAME-word}` family expansion (`-`, `:-`, `=`, `:=`, `+`, `:+`,
     `?`, `:?`) is cut off with a regex (`_EXPANSION_OPERATOR`, `:93`), so the word after
     it stands alone: `${X:-sudo}`, `${X-sudo}`, `${X:+pkexec}`;
   - `$` is now dropped with the quotes and backslashes (`_COARSE_DROP`, `:94`), which
     covers `$"sudo"`, and `:` is a split character (`_COARSE_SPLIT`, `:95`).
   - Words with a glob character are matched as patterns with `fnmatch.fnmatchcase`
     against `PRIVILEGE_PROGRAMS` (`_names_privilege_program`, `:247-253`, used at
     `:268`), so `/usr/bin/sud[o]`, `/usr/bin/sud?` and `pke*c` count. A pattern with no
     letter or digit of its own (`*`, `?`) is skipped, so `ls *` stays OTHER.

   **Rejected: the adversary's "split on `-` too".** That would turn `echo sudo-ish`
   into a `sudo` fragment and break the lookalike row the brief requires
   (`echo sudo-ish` is not privilege). The regex cuts `-` only right after `${NAME` /
   `${NAME:`, which is where bash reads it as an operator. Cost of the regex instead:
   1 line (`:93`) and 1 call (`:219`).

   New test rows: `tests/test_failure_classes.py:198-213` (15 privilege rows) and
   lookalike rows `:259-265` (`${X:-pseudo} x`, `$'visudo' x`, `ls *`, `ls *.txt` stay
   OTHER).

2. **Lookup returns a bare `str` or `None`** (adversary finding). `_suggestion`
   (`src/nl_shell/failure_classes.py:306-312`) now treats a `str` as one package name and
   `None` as no packages. A lookup that raises still propagates: #156 owns the provider,
   and hiding its errors here would hide its bugs. If the human wants the classifier to
   survive a broken provider, it is a 3-line `try/except Exception` around `:306`.
   Tests: `tests/test_failure_classes.py:464-476`.

3. **Literal U+202E in the test source** (finding on the old `:394`, `:416`). Both are now
   `‮` escapes (`tests/test_failure_classes.py:420`, `:442`). A new test
   (`:479-482`) reads the file's bytes and asserts all are ASCII, so a literal bidi
   override cannot come back unnoticed.

## Left as is (not in the carry-forward's build list; deferred to the human)

These stay open because no word splitter can see them without a real parse (#12), or
because the brief scopes them out. I list them so sign-off sees the edge:

- `su${EMPTY}do x` and `su$()do x`: these now happen to match, because dropping `$`
  and splitting on `{}`/`()` leaves a `su` fragment. That is luck, not a rule; I did not
  add rows that would pin it.
- A word built from variables (`c=sud; c+=o; $c x`) or from a parameter substitution
  (`${X/foo/sudo}`): the value is not in the text.
- Session functions that wrap sudo (`s() { sudo "$@"; }`): the snapshot carries only
  function names, and the brief's decision 1 names aliases only.
- `ran=False` with privileged text (`sudo foo (`) is OTHER, as decision 2 orders.
- Glob matching over-matches more now: `ls s*` and `echo su?` with a failing status are
  PRIVILEGE (no correction offered). Decision 1 accepts over-matching.

## Red → green (project runner)

Both through the project's gate scripts with `PDCA_BUNDLE=results/issue_155` and
`PDCA_WORKTREE` set:

- `engine/scripts/run-verify.sh` (C4): `PDCA-EVIDENCE: C4 PASS — red without the fix
  (148 of 149 failed), green with it`. Red leg: pytest exit 1, 0 collection errors. The
  one test that passes on the red leg is the ASCII check on the test file itself, which
  does not depend on the production module.
- `engine/scripts/run-suite.sh` (T3): `801 passed`, `PDCA-EVIDENCE: T3 PASS`.

Extra check, specific to this iteration: I put iteration 1's `failure_classes.py` back in
place (taken from `iteration-v1/patch.diff`) and ran the new test file against it
(`timeout 120 .venv/bin/python3 -m pytest -q tests/test_failure_classes.py`, with a
timeout, outside the gate scripts, because C4 can only revert to "no module"). Result:
`16 failed, 133 passed`. The failures are exactly the new rows: 13 privilege spellings,
the two lookup-return tests, and `test_only_other_goes_to_the_reader` (it walks the
privilege table). `${X:=doas} x` and `${X:-/usr/bin/sudo} x` already passed on the old
code (`=` and `/` were already split points); they stay as regression rows. The current
module was restored after; `git diff` matches `patch.diff` byte for byte.

## Refuting my own test

- **(a) Genuine red?** Yes. C4 reverts the production file: 148 of 149 fail, 0
  collection errors. Against iteration 1's module (the rejected approach), the 16 new
  checks fail, so the new rows bind this iteration's fix, not just the module's
  existence.
- **(b) Production path?** Yes. Every test calls the real
  `nl_shell.failure_classes.classify` on a real `session.CommandResult` holding a real
  `pty_protocol.Snapshot`. `$PATH` checks run the production `router.is_executable_file`
  on real files in `tmp_path`. Only the package lookup is a fake, because the brief makes
  it an injected callable and the real one is #156's.
- **(c) Fixture includes the fault?** Yes. The privilege rows are the exact strings the
  reviewers reported as bypasses (`$'sudo' apt update`, `${X:-sudo} apt update`,
  `pk$'exec' x`, `$'\x73udo' x`, `sud\<newline>o apt update`, `/usr/bin/sud[o] apt
  update`, `/usr/bin/sud? x`). The lookup tests return the bad shapes (`"htop"`, `None`)
  the adversary named. `output` always holds hostile text and never changes the class. No
  real sudo or other privilege tool runs, as the brief requires; the class depends only
  on the confirmed text.

## Commit-readiness

The target has no formatter, linter or pre-commit config (no `.pre-commit-config.yaml`,
no ruff/black section in `pyproject.toml`; neither tool is installed here), and CI
(`.github/workflows/tests.yml`) only runs `python -m pytest`. `git diff --check` is clean,
no line is over 95 characters, and both new files are pure ASCII apart from two `§` in
`failure_classes.py` comments (`:12`, `:45`), which iteration 1 also had and the suite's
own checks accept.

No push, no PR.

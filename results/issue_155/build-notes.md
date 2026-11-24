# Build notes — issue 155, iteration 8

Base: integration commit `5d3d291` (worktree `$PDCA_WORKTREE`, clean before the build).
Starting point: `iteration-v7/patch.diff`, applied unchanged, as the carry-forward asks
("keep the rest of the patch as it is"). This round changes only what the Iteration 7
carry-forward names.

## What changed against v7

1. **The fix (`src/nl_shell/failure_classes.py:113-115`).** `_ALIAS_START` and
   `_ALIAS_LINE` now accept an optional `-- ` after `alias `:
   `alias (?:-- )?([^=\s]+)=`. Bash's `alias -p` prints a name that starts with `-` as
   `alias -- -s='sudo'`. The old pattern `alias ([^=\s]+)=` matched `--`, then failed
   on the space, so the line was skipped. Two things went wrong because of that:
   - `-s x` with `alias -- -s='sudo'` was not seen as an alias. `-s` is a plain first word
     under P3, so the result was other. It must be privilege (P5).
   - For a multi-line value under `alias -- `, the parser skipped the real start line and
     then read the next line (`alias ls=sudo`) as a new alias. That is the same line-start
     bug that round 6 fixed for ordinary names.
   With the optional `-- `, `_parse_aliases` (`failure_classes.py:301-331`) finds the real
   start, reads the value by its quoting through `_word_end`, and the inner line stays
   part of the value. Both regexes needed the change: `_ALIAS_LINE` is used on the
   unclosed-quote path (`failure_classes.py:327`) to mark every later line-start name as
   None (unknown, so privileged).
   A name that is literally `--` still works: `alias -- --='x'` takes the optional `-- `,
   then reads `--` as the name.

2. **Test rows (`tests/test_failure_classes.py`).**
   - `PRIVILEGED_P5` gets `alias-dash-name` (`-s x`, `alias -- -s='sudo'\n`) and
     `alias-dash-multi-line-value` (`-z x`, `alias -- -z='ls\nalias ls=sudo'\n`). Both
     must be privilege.
   - `test_plain_alias_forms_are_not_privilege` gets `dash-value-inner-line` (`ls x`
     with the same alias text). It must be other. This row checks the "read as one quoted
     value" part directly: `-z x` would be privilege even if the parse were wrong in some
     other way (P1 sees `sudo` in the value). But `ls` only turns privileged if the inner
     `alias ls=sudo` line is wrongly read as a new alias.
   - These rows also feed `test_no_message_in_any_table_says_none`, because that test
     collects every row of `PRIVILEGED_P5`.

3. **Optional nit (`.oss-scanner/threat_model.md:202-203`).** I rewrapped the end of the
   classifier's Known-gaps bullet so no line runs past the file's usual width (about 90
   columns). The words are the same.

## Red → green evidence

- **C4 gate** (`engine/scripts/run-verify.sh`, with `PDCA_BUNDLE` and `PDCA_WORKTREE`
  set): `PDCA-EVIDENCE: C4 PASS — red without the fix (272 of 273 failed), green with it`.
  The one test that passes in both legs is the ASCII self-check, as the brief expects.
- **Targeted red for this round:** I put back only the v7 regexes and kept the rest of the
  module. Then I ran
  `pytest -k "dash or chain-10-a8 or multi-line-value or repeated"`:
  - v7 regexes: **3 failed** (`alias-dash-name`, `alias-dash-multi-line-value`,
    `dash-value-inner-line`), 6 passed. The 6 are the round-6 rows, which v7 already
    fixed.
  - fix restored: 9 passed.
- Full test file with the fix: 273 passed. Full target suite (`python -m pytest`, what CI
  runs): 925 passed.

## Refute-your-own-test

- **(a) Genuine red?** Yes. With only the two regexes put back to v7, the three new rows
  fail (shown above). With the whole module reverted, the C4 red leg fails 272 of 273.
- **(b) Production path?** Yes. The rows call the real `failure_classes.classify` with a
  real `session.CommandResult`. Its `pty_protocol.Snapshot.aliases` is set to the raw
  `alias -p` text. Nothing is mocked. The parse runs through the real `_parse_aliases`.
- **(c) Fixture includes the fault?** Yes. The alias text is exactly what bash's
  `alias -p` prints for a dash-leading name (`alias -- NAME='VALUE'`). The multi-line
  fixture holds the line (`alias ls=sudo`) that a line-start parse would wrongly read as
  a new alias.

## Commit-readiness

The target has no formatter, pre-commit config or git hooks. There is no ruff, black or
pre-commit entry in `pyproject.toml`, `.github/` or `CONTRIBUTING.md`, and nothing in
`.git/hooks` except samples. CI (`.github/workflows/tests.yml`, `docs-checks.yml`) runs
pytest, `scripts/docs_links.py` and `scripts/docs_checks.py immutability BASE HEAD`.
- pytest: 925 passed.
- `docs_links.py`: 0 broken.
- `docs_checks.py` needs two commits, so it can't run on an uncommitted tree. The only doc
  change this round is a two-line rewrap inside the bullet that v7 already added.
- No line in the two Python files is over 100 characters.

## Housekeeping

During the targeted red run I left a copy of the fixed module at
`src/nl_shell/failure_classes.py.fixed.tmp` in the worktree. It is untracked, not in
`patch.diff`, and not imported by anything. Per the harness rules I did not delete it; the
harness reclaims the worktree.

## Not changed (on purpose)

- P3 still cuts at `&` and `|` before it looks for redirections. That gap is recorded in
  the Known-gaps bullet as kind (5) and goes to #12, as round 6 decided.
- No other part of the v7 patch was touched.

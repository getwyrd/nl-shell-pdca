# Build notes — issue 155, iteration 5

Target: eduralph/nl-shell, folded wave base `5d3d291` (includes #140's `session.CommandResult`),
worktree `$PDCA_WORKTREE`. Line numbers below are on the patched tree.

## Starting point

The iteration-v4 patch was applied unchanged as the base (it already met every row of the
brief's Success criterion), and only the six implementation findings in the Iteration 4
carry-forward were fixed on top. The rejected approach (a bash expander, iteration v1–v3) is
not brought back: nothing is expanded; the fixes are all in the word splitter and the
rule 1b walker.

## The six carry-forward findings and the fix for each

1. **`#` after a closing substitution started a comment.** `src/nl_shell/failure_classes.py:200`
   now starts a comment only when `#` is not glued to a closing `)` or backtick
   (`_glues_to_word`, `:284-287`). A `#` after `;`, `|`, `(` or whitespace still starts a
   comment, as in bash. Rows: `echo $(true)#; sudo apt update`, `` echo `true`#; sudo apt update ``
   (`tests/test_failure_classes.py:224-225`), `echo $(true)#; ${X}sudo y` (1b table).
   Guard rows that stay OTHER: `echo $(ls)#x`, `ls # $X`, `ls;# $X`.
   Side effect: a `#` glued to a plain subshell close, `(true)#x`, is also read as a word
   (bash reads it as a comment). That only over-matches, which is the safe direction.

2. **A quoted `[[` swallowed the rest of the line.** New `_keyword` (`:343-349`): a word is a
   keyword only when its raw text equals its text after quote removal, so `'[['`, `\[[`,
   `'function'`, `'{'`, `'if'` are ordinary commands. On top of that, `in_test` now ends at
   `;`, `;;`, `&`, `|`, `|&` and newline (`_TEST_ENDERS`, `:353`), which cannot appear inside a
   real `[[ ]]`. `&&`, `||`, `(`, `)` are left alone because they are valid inside `[[ ]]`
   (`[[ $a && $b ]]` is a guard row that stays OTHER). Rows: `'[[' a; ${X}sudo y`,
   `\[[ a; $(printf sud)o y`, `'[[' a; f` with `f` a function.

3. **Broken quoting threw away the first scan.** `_split` (`:290-298`) now returns both
   scans when quoting is broken, and `_text_is_privileged` (`:465-489`) checks rules 1a and 1b
   on each. Rows: `echo "a #"; sudo x '` at `ran=True` (`tests/...:227`) and at `ran=False`
   (`tests/...:467`, decision 3).

4. **No 1b inside a double-quoted substitution.** `_unclear_command_word` takes a `pieces`
   flag (`:356-358`). For pieces of a re-split quoted word, the words themselves are not
   command words (so `git commit -m "fix: x (y)"` stays OTHER: `(` in pieces mode does not
   start a command), but after a `$(` or backtick inside them the normal command-word rules
   apply. `_text_is_privileged` now runs 1b on every re-split level with `pieces=depth > 0`
   (`:470`). Rows: `echo "$(sud${X}o x)"`, `` echo "`sud${X}o x`" ``, `v="$(run$# x)"; ls`.
   Guard row: `echo "$(ls $X)"` stays OTHER.
   Accepted cost: this also fires for single-quoted text that bash would not expand at that
   level, e.g. `echo '$(ls$x)'` → PRIVILEGE. I kept it because the pieces of a single-quoted
   `bash -c '...'` argument do run, and the scanner does not know which command consumes the
   word. Over-match only.

5. **`[[ ... ]]` skipped substitutions.** Substitution openers are now handled before the
   `in_test` branch, for every state; the restore stack holds `(expect, in_test, quiet)` so
   closing the substitution goes back into the test. A `)` seen while `in_test` is still on is
   a grouping paren and is ignored, so it never pops the stack by mistake. Rows:
   `[[ -n $(sud${X}o x) ]]`, `[[ -n $(pk$#exec x) ]] && ls`. Guard row `[[ -n $(ls) ]]`.

6. **`eval f` with `f` a function.** The 1a loop treats any word (including re-split pieces
   and alias values) that names a snapshot function as privileged (`:478-480`). Rows:
   `eval f`, `eval "f"` (`tests/test_failure_classes.py:313-322`). `ls` with an unrelated function `t` is still
   OTHER (existing row). The module docstring and the threat-model Known-gaps bullet say
   "any word that names a shell function" now (`.oss-scanner/threat_model.md:190-196`).

7. **`coproc N { … }`** (the Low finding). After the command word `coproc`, if the next word is
   followed by an unquoted `{`, that word is taken as the coprocess name (it must be plain)
   and the `{` starts a command, so the body's first word is checked. Row:
   `coproc N { sud${X}o x; }`. Guard row: `coproc N { ls; }`. `coproc $X` → PRIVILEGE,
   `coproc ls` → OTHER (probed, not in the table).

## Cost bound

The union of two scans could in theory double work per re-split level. In practice the
fallback scan only yields words with whitespace through backslash escapes, which cost source
length to nest. Probes (not in the test file), each one `classify` call:
`"x " + "\"a '"*5000` 0.028 s; `"x " + "'a \"b "*3000 + "#"` 0.019 s;
`"x " + "\\\\ "*10000 + "'"` 0.015 s; `"echo " + "\"$("*3000` 0.001 s;
`"[[ " + "$("*5000` 0.001 s; `"echo " + "\"a $(b '\"c "*2000` 0.018 s. The brief's five
BOUNDED rows still pass.

## Verification (project runner: the venv's `python -m pytest`, as `engine/scripts/run-suite.sh` runs it)

- Fixed tree: `tests/test_failure_classes.py` 289 passed; whole suite 941 passed (3 min).
- New rows against the iteration-v4 module: 19 failed, 270 passed. Every failure is one of
  the carry-forward reproducers.
- Production change reverted (module removed, threat model back to `HEAD`): 288 failed,
  1 passed. The one pass is `test_this_file_writes_every_non_ascii_character_as_an_escape`,
  which only reads the test file, as the brief says.

## Refute-my-own-test answers

- **(a) Genuine red?** Yes. With the module removed and the threat-model bullet reverted,
  288 of 289 fail as assertion/import failures inside test bodies (imports are inside the
  functions, so collection succeeds). The new carry-forward rows also go red against the
  previous attempt's module (19 failures), so they bind these specific fixes.
- **(b) Production path?** Yes. Every row calls `nl_shell.failure_classes.classify` with a
  real `nl_shell.session.CommandResult` and `nl_shell.pty_protocol.Snapshot`. Nothing is
  mocked except the package lookup, which the brief says is injected.
- **(c) Fixture includes the fault?** Yes. Each row is the exact reproducer text from the
  carry-forward (the `#` after `$(true)`, the quoted `[[`, the broken-quote `#`, the quoted
  substitution, the substitution inside `[[`, `eval f` with `f` in `snapshot.functions`, the
  coproc body), not a cleaned-up variant.

## Formatter / hooks

The target has no formatter or linter config (`pyproject.toml` has only setuptools and
pytest sections; no pre-commit config in the repo). Neither ruff nor pyflakes is installed in
the venv. I kept lines under 100 characters (router.py's longest is 99) and `git diff --check`
is clean.

## Housekeeping

`$PDCA_WORKTREE/.build-tmp/` holds scratch copies (the v4 module and the fixed module) used
for the red check. It is untracked and not in `patch.diff`; the harness reclaims the worktree.

## Not done here

The 9 deferred findings in `deferred-findings.json` are for the human; none were acted on.
Publishing still depends on #146 merging, or a draft PR against #146's branch (brief
Ordering note).

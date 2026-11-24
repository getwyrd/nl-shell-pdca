# Build notes — issue 108 / router-english-sentence-rule (iteration 3)

Target: eduralph/nl-shell @ main (worktree base a6efb0a). Line numbers below are in the
patched worktree `/home/eddie/nl-shell/nl-shell.pdca-wt-l0`.

## What changed in this iteration

The iteration-2 carry-forward said nothing pinned the order "quote signal before rule 3".
Moving the `-` word and metacharacter checks above `_has_unbalanced_single_quote` left
every vector green. I kept the iteration-2 production code unchanged (it already checks
the signal first, `src/nl_shell/router.py:91-104`) and added two vectors to the router
table, `tests/test_repl.py:123-125`:

- `find . -name it's` → natural language. It has an odd `'`, no `"`, no `\`, so the signal
  fires. It also has a `-` word, so rule 3 would make it a command if rule 3 ran first.
- `find what's in ~/src` → natural language. Same, but rule 3 would fire on the `~` and
  `/` metacharacters.

Two vectors, not one, so both halves of rule 3 (`router.py:100-101` for `-` words,
`router.py:102-103` for metacharacters) are pinned against the signal on their own.

The signal's order against rule 1 is pinned by `echo it's fine`, against rule 2 by the same
vector (3 words), and against rule 4 by `find what's using port 80` (no function word:
`what's` is not `what`). All those were already in place from iterations 1-2.

## Carried over from iteration 2 (unchanged)

- `src/nl_shell/router.py:1-26` — docstring: describes the signal, rules 1-4, what a
  "word" is (`text.split()`), and the known limitations that remain.
- `src/nl_shell/router.py:72-83` — `FREE_TEXT_COMMANDS`, `SHELL_METACHARACTERS`,
  `FUNCTION_WORDS` (the brief's lists, verbatim).
- `src/nl_shell/router.py:86-88` — `_has_unbalanced_single_quote`: odd `'`, no `"`, no `\`.
  No lexer, as the brief asks; `first_token` (`router.py:53`) is not reused and is
  unchanged, so `failure_classes.py`'s use of it is untouched.
- `src/nl_shell/router.py:91-104` — `_reads_like_english`: signal, then rules 1-4.
- `src/nl_shell/router.py:107-112` — `_is_command_name`: the old builtin / path / `$PATH`
  logic moved out of `route()` with no behaviour change; `$PATH` is still read per call.
- `src/nl_shell/router.py:115-122` — `route()`: unresolved → NL; resolved and English → NL;
  otherwise COMMAND.
- `tests/test_repl.py:50-59` — `fake_path` now holds `watch who free sort grep` too, so
  vectors on those words resolve and do not pass on `main` for the wrong reason.
- `tests/test_repl.py:89-125` — pinned vector flipped, "Known heuristic limitation" comment
  dropped, the brief's twelve vectors plus the iteration-1 vectors for rule 3, rule 4's
  negative side and the signal's `\`/`"` exclusions, plus this iteration's two.
- `docs/design/architecture/05-building-block-view.md:75` — router row describes the rule.

## Evidence

- C4 gate (`engine/scripts/run-verify.sh`, the project's verify runner): red without the
  fix, 8 of 43 failed (all the NL vectors whose first word resolves, including the two new
  ones); green with it. `PDCA-EVIDENCE: C4 PASS`.
- Mutant from the carry-forward (rule 3 moved before the signal), run through
  `engine/scripts/run-suite.sh`: exactly the two new vectors fail, 1120 passed, 1 skipped.
  So the new vectors bind the order. With the real patch restored, `git diff` matches
  `patch.diff` byte for byte (`cmp`).
- `tests/test_failure_classes.py` is part of that full-suite run and passed.

## Refuting my own test

- **(a) Genuine red?** Yes. The C4 gate reverts only the production hunks and 8 of 43 router
  cases fail, among them `find large files in my home`, `find . -name it's` and
  `find what's in ~/src`.
- **(b) Production path?** Yes. Every vector runs through `Repl(...).run()` (`run()` helper
  in `tests/test_repl.py`), which calls the real `nl_shell.router.route`. No mock.
- **(c) Fixture includes the fault?** Yes. `fake_path` puts every command word the vectors
  use on `$PATH` (`find`, `watch`, `who`, `free`, `sort`, `grep`, `ls`, `git`); `kill`,
  `echo`, `printf`, `cd`, `export` are bash builtins. So the NL vectors only pass because
  of the new rule, not because the word is missing.

## Formatter / hooks

The target has no `.pre-commit-config.yaml` and no ruff/black config in `pyproject.toml`;
the venv has no ruff. The new lines follow the file's existing style (black-like, under
88 columns). Nothing to run.

## Housekeeping

The mutant run left an untracked copy of the patched router at
`/home/eddie/nl-shell/nl-shell.pdca-wt-l0/.router.orig` (identical to the patched
`src/nl_shell/router.py`). It is not in `patch.diff`. I did not delete it, per the
harness's no-cleanup rule; the harness reclaims the worktree.

## Ruled out

- Changing production code: the carry-forward is a coverage gap, not a defect. The order
  the brief fixes ("checked before rules 1-4; when it holds it overrides them") is already
  what `router.py:93-94` does.

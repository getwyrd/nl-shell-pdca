# Build notes — issue 108 / router-english-sentence-rule (iteration 2)

Target: eduralph/nl-shell @ main (worktree base a6efb0a). Line numbers are in the patched
tree unless marked "base".

## What this iteration changes

The production code (`src/nl_shell/router.py`) and the docs row are the same as iteration
1 (`iteration-v1/patch.diff`). The review found no defect in them; it found that the test
table did not pin three parts of the rule. This iteration only adds test vectors and fixes
two misleading comments in `tests/test_repl.py`.

Carry-forward findings and how each is addressed:

1. **Rule 3 untested** (no `-` word, no metacharacter, `router.py:100-103`). Added lines
   that pass rules 1, 2 and 4 and fail only rule 3:
   - `find the big files -size +1G` → command (`tests/test_repl.py:116`, a `-` word only;
     `+` is not a metacharacter).
   - `find big files in ~/src` → command (`:117`, `~` and `/`; the docstring names it as a
     known limitation).
   - `grep the in file|less` → command (`:118`, `|`).
   - `grep "the files in here` → command (`:119`, `"` as a rule-3 metacharacter; the old
     `git commit -m "wip` line also has `-m`, so it never pinned `"` on its own).
2. **Rule 4's negative side untested** (`router.py:104`). Added `git push origin main` →
   command (`:120`): 4 words, no `-`, no metacharacter, no function word.
3. **`\` and `"` exclusions in the quote signal untested** (`router.py:88`). Added
   `grep it\'s x y` → command (`:121`) and `git commit -m "it's"` → command (`:122`).
4. Not asked for, but the same gap: `printf` in rule 1 (`router.py:72`) had no vector, only
   `echo`. Added `printf the answer is 42` → command (`:115`).
5. The comments the reviewer called out as claiming coverage they did not give are fixed:
   `find . -name '*.py'` now says "option, quotes, no function word" (`:106`); the
   `git commit -m "wip` comment already only claimed "not the quote signal", which is true.
6. `grep` added to the `fake_path` fixture (`tests/test_repl.py:56`, docstring `:51-53`) so
   the `grep` lines resolve on the fake `$PATH` and are not natural language just because
   `grep` is missing.

## Full change list (unchanged from iteration 1 except the test table)

- `src/nl_shell/router.py:1-26` — module docstring: the base "Known limitation" paragraph
  (base `router.py:8-10`) replaced by the new rule, "word" = `text.split()`, and what it
  still misses.
- `src/nl_shell/router.py:71-83` — `FREE_TEXT_COMMANDS`, `SHELL_METACHARACTERS`,
  `FUNCTION_WORDS` (brief's list verbatim).
- `src/nl_shell/router.py:86-88` — `_has_unbalanced_single_quote` (odd `'`, no `"`, no `\`;
  no lexer).
- `src/nl_shell/router.py:91-104` — `_reads_like_english`: quote signal first, then rules
  1–4.
- `src/nl_shell/router.py:107-112` — `_is_command_name`: base `router.py:61-66` logic,
  same behaviour.
- `src/nl_shell/router.py:115-122` — `route()`; `$PATH` still read on every call.
- `first_token` unchanged (`router.py:53-63`, base `38-48`); second caller
  `failure_classes.py:46,388` unaffected.
- `tests/test_repl.py:49-59` — fixture; `:89-129` — router table (flipped vector, the 12
  brief vectors, the 8 isolating vectors above).
- `docs/design/architecture/05-building-block-view.md:75` — router row.

## Red → green (project runner)

`./engine/scripts/run-verify.sh` with `PDCA_BUNDLE` and `PDCA_WORKTREE` set:
green leg 41 passed; red leg (router hunks reverted) 6 of 41 failed — the six
natural-language vectors whose first word resolves. `PDCA-EVIDENCE: C4 PASS`. The tree was
restored afterwards (`git diff --stat` identical).

## Mutation check (what the reviewer did, now done before hand-off)

The C4 runner can only revert the whole patch, so for per-clause checks I edited
`router.py` one clause at a time and ran `tests/test_repl.py -k routed_as` under the venv
pytest with a 120 s `timeout`. Each mutation turns at least one vector red:

| Mutation | Red vectors |
| --- | --- |
| drop rule 3 (`router.py:100-103`) | `-size +1G`, `~/src`, `file\|less`, `"the files in here` |
| drop only the `-` check (`:100-101`) | `find the big files -size +1G` |
| drop only the metachar check (`:102-103`) | `~/src`, `file\|less`, `"the files in here` |
| rule 4 always true (`:104`) | `git push origin main`, `grep it\'s x y` |
| drop `"\\" not in text` (`:88`) | `grep it\'s x y` |
| drop `'"' not in text` (`:88`) | `git commit -m "it's"` |
| `printf` removed from `FREE_TEXT_COMMANDS` (`:72`) | `printf the answer is 42` |
| `"` removed from `SHELL_METACHARACTERS` (`:75`) | `grep "the files in here` |

Rules 1 (`echo`) and 2 (word count) were already pinned in iteration 1 by
`echo all is well in the world` and `ls my files`.

## Refuting my own test

- **(a) Genuine red?** Yes. With the router hunks reverted, 6 of 41 vectors fail (C4 red
  leg above). With each clause broken on its own, the matching vector fails (table above).
- **(b) Production path?** Yes. Every vector goes through `Repl(...).run()` →
  `nl_shell.router.route()`, the real module; nothing is mocked except `$PATH`.
- **(c) Fixture includes the fault?** Yes. `fake_path` holds every external command word
  the vectors use (`ls git find watch who free sort grep`); `kill`, `echo`, `printf`,
  `cd`, `export` are builtins. So each "natural language" vector's first word does
  resolve, and red on `main` comes from the router, not a missing binary.

## Commit-ready

The target has no formatter config or pre-commit hook (`pyproject.toml` has only
setuptools and pytest sections; no `.pre-commit-config.yaml`). CI runs pytest,
`scripts/docs_checks.py` and `scripts/docs_links.py`; results below. No new line is over
88 columns; the two existing ones (`router.py:60`, `test_repl.py:143`) are on base too.

## Suite and docs checks

- `./engine/scripts/run-suite.sh`: 1120 passed, 1 skipped — `PDCA-EVIDENCE: T3 PASS`
  (includes `tests/test_failure_classes.py`, the other `first_token` caller).
- `scripts/docs_links.py`: 64 relative links, 0 broken.
- `scripts/docs_checks.py immutability BASE HEAD` (as CI runs it, against a temporary
  local commit that was then undone): `docs-immutability: OK`.

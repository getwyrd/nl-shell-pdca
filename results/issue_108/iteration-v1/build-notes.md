# Build notes — issue 108 / router-english-sentence-rule

Target: eduralph/nl-shell @ main (worktree base a6efb0a). Line numbers below are in the
patched tree unless marked "base".

## What changed

- `src/nl_shell/router.py:1-34` — module docstring rewritten. The old "Known limitation"
  paragraph (base `router.py:8-10`) is replaced by a description of the new rule (quote
  signal, the four conditions, "word" = `text.split()`), why a misroute is only a
  usability cost (gate + `\cmd`), and what it still misses: short English, English with
  no function word, English with a metacharacter, and bash keywords / assignments /
  aliases / functions.
- `src/nl_shell/router.py:71-83` — three module constants: `FREE_TEXT_COMMANDS`
  (`echo`, `printf`, rule 1), `SHELL_METACHARACTERS` (the exact set from the brief plus
  backtick and `"`, rule 3), `FUNCTION_WORDS` (the brief's list verbatim, rule 4).
- `src/nl_shell/router.py:86-88` — `_has_unbalanced_single_quote`: odd count of `'`, no
  `"`, no `\`. No lexer, as the brief requires.
- `src/nl_shell/router.py:91-104` — `_reads_like_english`: the quote signal first (so it
  overrides rule 1, pinned by `echo it's fine`), then rules 1–4 in order.
- `src/nl_shell/router.py:107-112` — `_is_command_name`: the old builtin / path / `$PATH`
  checks from base `router.py:61-66`, unchanged in behaviour, pulled out so the rule runs
  for all three kinds of resolved token (the brief: "builtin, `$PATH` hit, or executable
  path").
- `src/nl_shell/router.py:115-122` — `route()`: unresolved first token → natural language
  (as before); resolved and reads like English → natural language; otherwise command.
  `shutil.which` is still called on every line, so `$PATH` is not cached.
- `first_token` (`router.py:53-63`, base `38-48`) is untouched, as the brief requires; its
  other caller `failure_classes.py:46,388` is unaffected.
- `tests/test_repl.py:49-59` (fixture at `:50`) — `fake_path` now also holds `watch`, `who`, `free`, `sort`,
  so the new vectors resolve on the fake `$PATH` and cannot pass on `main` just because the
  word is missing (the brief's Falsifiability point). `kill` and `echo` are builtins.
- `tests/test_repl.py:89-119` — router table: removed the "Known heuristic limitation"
  comment and the pinned `find large files in my home` → COMMAND vector (base
  `test_repl.py:93-95`), added all twelve vectors from the brief's Design table with the
  routes given there.
- `docs/design/architecture/05-building-block-view.md:75` — router row now names the
  English-sentence rule.

## Why this shape

The brief fixes the rule, the word list and the order, so there was little to decide. I
put the rule in private helpers inside `router.py` (the brief allows "in `route()` or a new
private helper"), which keeps `route()` readable and leaves `first_token` alone. I did not
reuse `first_token`'s `ValueError` path for the quote signal: as the brief says, it only
lexes the first word, so `find what's using port 80` never hits it.

Small points I checked against the brief:

- Rule 3 checks metacharacters on the whole line, but "starts with `-`" per word. A
  hyphen inside a word (`up-to-date`) is fine.
- Rule 4 lowercases each split word but does not strip punctuation, so `home?` does not
  match `home`. The brief says "word, lowercased", nothing about punctuation; I kept to it.
  (`?` is not in the metacharacter set, so `who is logged in?` still has `is` and goes NL.)
- An executable path as first token (`/usr/bin/find ...`) can never pass rule 3, since `/`
  is a metacharacter, but the quote signal can still fire for it. That follows from the
  brief's rules as written.

Ruled out: a dictionary or part-of-speech heuristic (the brief's Alternatives already
reject it), and changing `first_token` (has a second caller).

## Red → green (project runner)

Ran `./engine/scripts/run-verify.sh` with `PDCA_BUNDLE` and `PDCA_WORKTREE` set:

- green leg: `tests/test_repl.py` 33 passed.
- red leg (production hunks of `router.py` reverted by the script): 6 of 33 failed —
  exactly the six natural-language vectors whose first word resolves:
  `find large files in my home`, `find what's using port 80`,
  `watch the logs for errors`, `who is logged in`, `kill the process on port 8080`,
  `echo it's fine`.
- `PDCA-EVIDENCE: C4 PASS`.

Full suite via `./engine/scripts/run-suite.sh`: 1112 passed, 1 skipped
(`PDCA-EVIDENCE: T3 PASS`). `tests/test_failure_classes.py` + `tests/test_input_modes.py`
re-run after the final edit: 312 passed. `scripts/docs_links.py`: 0 broken links.

## Refuting my own test

- **(a) Genuine red?** Yes. The verify script reverts the `router.py` hunks and re-runs
  the file: 6 failures, each `AssertionError` showing the COMMAND reply where the
  natural-language reply was expected. The six COMMAND vectors stay green on `main`, which
  is right — they pin that the new rule does not over-fire.
- **(b) Production path?** Yes. The test drives `Repl(...).run()` with a scripted reader,
  which calls the real `nl_shell.router.route` (`repl.py:23`). Nothing is mocked except
  `$PATH`, which points at a temp dir of real executable files.
- **(c) Fixture includes the fault?** Yes. The fault is "a command word starting an
  English sentence". The fixture puts `find`, `watch`, `who` on `$PATH` (and `kill`, `echo`
  are builtins), so every NL vector's first word really resolves — on `main` they route as
  COMMAND, which is the bug. Without the fixture change, `watch` / `who` would have gone NL
  on `main` for the wrong reason.

## Commit-readiness

nl-shell has no formatter or pre-commit config (no `.pre-commit-config.yaml`, no ruff /
black section in `pyproject.toml`; `ruff` is not installed here). CI runs pytest and the
docs checks. I matched the file's existing style and kept new lines within 88 chars (the
file already had one 89-char line before this change, `router.py:60` base `45`).

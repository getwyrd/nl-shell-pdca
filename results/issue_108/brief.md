# Design proposal — issue 108 / router-english-sentence-rule

> Plan artifact (planner leaf). Do reads ONLY this file. The `- **Label:** value` lines
> are parsed by the driver. The design itself is already settled in the issue (design
> update 2026-10-15, checked against `main` at e7bb63c); this proposal fixes its scope
> for one cycle. No new nl-shell proposal under `docs/design/proposals/` is needed.

- **Slug:** router-english-sentence-rule
- **Kind:** enhancement (design proposal)
- **Goal:** Plain English that starts with a command name (`find large files in my home`,
  `who is logged in`) routes as natural language instead of as a shell command, using one
  deterministic rule in `nl_shell.router`. An unbalanced single quote (`find what's using
  port 80`) also counts as natural language.
- **Success criterion:** In `tests/test_repl.py`'s router table
  (`test_input_is_routed_as_command_or_natural_language`, `tests/test_repl.py:88-108`), the
  pinned vector `find large files in my home` is flipped to natural language, and the twelve
  vectors in the table under Design all pass with the route given there. Run through
  `Repl(...).run()` with a fake `$PATH` that holds every command word the vectors use.
  Every existing router and REPL test in the file still passes, and so does
  `tests/test_failure_classes.py` (the other user of `first_token`).
- **Falsifiability:** Plain pytest on the host, no external service. On `main` the router
  returns `Route.COMMAND` whenever the first token resolves (`src/nl_shell/router.py:56-67`),
  so the flipped vector and every new "natural language" vector whose first word is on the
  fake `$PATH` or a builtin (`find …`, `watch …`, `who …`, `kill …`) fail. That red comes
  from the production revert alone. The fake `$PATH` must hold those words: the existing
  `fake_path` fixture (`tests/test_repl.py:49-58`) has only `ls`, `git` and `find`. Without
  `watch`, `who`, `free` and `sort` on it, those vectors would pass on `main` for the wrong
  reason (the word is simply not found). Extend the fixture, or add one, so they resolve.
- **Repo + branch target:** eduralph/nl-shell @ main
- **Milestone / ADRs:** M0 — REPL prototype. Builds on ADR-0013 (a misroute still ends at
  the gate) and ADR-0024; architecture 05 building-block view. Does not touch the policy
  gate, PTY/sudo, taint, logging or the installer, so no threat-model input changes.
- **Depends on:** none
- **Conflicts with:** none
- **Ordering note:** #14 (prefix dispatch) is merged; it landed in `input_modes.py` and
  `repl.py`, not `router.py`, so no dependency is left. Nothing else in this batch edits `router.py` or `tests/test_repl.py`; #74's confirm UI
  is a new module and leaves the REPL to #78.
- **Surfaces:** data
- **Scope:** add the English-sentence rule and the unbalanced-quote signal to
  `nl_shell.router`; rewrite the module docstring's "Known limitation" paragraph
  (`src/nl_shell/router.py:8-10`) to describe the new rule and what it still misses; update
  the router table in `tests/test_repl.py` (flip the pinned vector, drop its "Known
  heuristic limitation" comment at `tests/test_repl.py:93-95`, add the vectors below); update
  the `nl_shell.router` row in `docs/design/architecture/05-building-block-view.md:75`. All in
  one PR. / out of scope: the M3 intent classifier (#40); prefix modes; any change to how a
  COMMAND or NATURAL_LANGUAGE route is handled in `repl.py`; bash keywords, aliases,
  functions and leading assignments (still unrecognised, still named in the docstring).
- **Difficulty:** low
- **External dependencies:** none
- **Test file:** tests/test_repl.py
- **Citations expected:** Do must cite path:line on the target branch for every change.
  `first_token` (`src/nl_shell/router.py:38-48`) only lexes the first word, so its
  `ValueError` branch never fires for `find what's using port 80`; do not reuse it. The
  quote signal and the four rules live in `route()` or a new private helper in
  `router.py`. `first_token`'s signature and behaviour stay unchanged: it has a second
  caller, `src/nl_shell/failure_classes.py:46,388`, and `tests/test_failure_classes.py`
  must stay green.
- **Prior-art check (triage cycles):** `git log origin/main -- src/nl_shell/router.py` →
  only dc784f0 (M0.7, the original router). `tests/test_repl.py` → 821e6e4, eaa2c8b, dc784f0,
  305d8a4; none touch this rule. Closed-unmerged PRs touching either path: none. Open PRs:
  none.
- **Disposition hint:** new-feature

## Motivation

On this machine `find`, `which`, `who`, `w`, `last`, `watch`, `free`, `top`, `kill`,
`sort`, `test`, `time` and `install` all resolve as commands, so a lot of ordinary English
gets routed to bash. A false command route is a usability problem, not a safety one: the
line still has to pass the gate (ADR-0013, architecture 05). A false natural-language route
costs one model call, and `\cmd` always forces bash. So the rule leans towards natural
language for sentence-shaped input.

## Design

After the first token resolves as a command (builtin, `$PATH` hit, or executable path),
route as **natural language** when all of these hold:

1. The first token is not `echo` or `printf` (their operands are free text).
2. The line has at least 4 words.
3. No word starts with `-`, and the line contains no shell metacharacter: none of
   `|&;<>$*=(){}[]~/`, no backtick and no double quote.
4. At least one word, lowercased, is in this function-word list:
   `a an the my me all any some this that these those which what who how in on of for
   from to with by is are was were than`.

Separately, an **unbalanced single quote** is a natural-language signal on its own: an
apostrophe as in `what's` is English, and bash would wait for the closing quote anyway.
It is defined without a lexer: the line holds an odd number of `'`, no `"` and no `\`.
An unclosed double quote or a trailing backslash is *not* the signal (those lines go
through rules 1–4 as usual, and rule 3 rejects `"`). Order: the signal is checked only
after the first token resolves (an unresolved token is natural language already), and
before rules 1–4; when it holds it overrides them (so `echo it's fine` is natural
language).

"Word" in rules 2–4 means an item of `text.split()` (plain whitespace split, not shlex),
so it is defined even on lines shlex cannot lex. The new docstring says so.

Everything else keeps today's behaviour: an unresolved first token is natural language, a
resolved one that fails the rule is a command, and `$PATH` is still read on every call.

Test vectors to add to the router table:

| Line | Route | Why |
| --- | --- | --- |
| `find large files in my home` | natural language | flips the pinned vector |
| `find what's using port 80` | natural language | unbalanced quote |
| `watch the logs for errors` | natural language | function words |
| `who is logged in` | natural language | 4 words, `is`, `in` |
| `kill the process on port 8080` | natural language | function words |
| `find . -name '*.py'` | command | option and quotes |
| `ls my files` | command | 3 words |
| `free -h` | command | option |
| `echo all is well in the world` | command | `echo` excluded |
| `sort users.txt` | command | 2 words |
| `echo it's fine` | natural language | quote signal overrides rule 1 |
| `git commit -m "wip` | command | unclosed `"` is not the signal; rule 3 |

## Alternatives considered

- Leave it to the M3 classifier (#40): that is months out and needs training data; this
  rule is the classifier's fallback anyway, so improving it now is not wasted.
- A bigger English heuristic (part-of-speech, dictionaries): more code to review for a
  usability-only gain; the four conditions are easy to read and test.

## Impact & compatibility

Only routing changes. The one existing vector that pinned the old limitation flips on
purpose. No settings, no i18n, no spec change. The docstring and the 05 row are the
documented behaviour and change in the same PR.

## Open questions

None. The rule, list and vectors are fixed by the issue.

## STOP discipline

Draft only until Check sign-off. Pushing to a feature/draft branch and opening a
draft PR MAY happen during the cycle (useful for CI feedback). The PR MUST NOT be
marked ready before sign-off accepts.

Plan-review response: all six findings taken. The quote signal no longer reuses
`first_token` and is defined by quote counts; its order against rules 1–4 is fixed and
pinned by `echo it's fine`; an unclosed `"` is pinned as not the signal; "word" means
`str.split()`; `first_token` stays unchanged; the #14 wording is corrected.

## Iteration 1 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 1): rebuilding for the implementation-level findings — Rule 3 (no `-` word and no shell metacharacter, `target/src/nl_shell/router.py:100-103`) is not covered by any test. I replaced `_reads_like_english` in-process with a version that drops rule 3 entirely and re-ran all 20 router vectors: none failed. The reason is that every command vector with 4+ words also fails rule 4. `find . -name '*.py'` and `git commit -m "wip` contain no function word, so rule 4 alone keeps them routed as commands. The comments "option and quotes" and "rule 3" at `tests/test_repl.py:106,112` claim coverage the vectors do not give. Concrete fix: add vectors that pass rules 2 and 4 and fail only rule 3, for example `find big files in ~/src` → command (the docstring already names it as a known limitation, `router.py:22-23`), `find the big files -size +1G` → command (`-` word), and `grep the in file|less` → command.; The negative side of rule 4 (`router.py:104`) is also uncovered. When I made `FUNCTION_WORDS` match every word, all command vectors still passed, because each 4+ word command vector is already rejected by rule 3. Add a plain 4+ word line with no function word that must stay a command, for example `git push origin main` → command.; The `\` and `"` exclusions in the quote signal (`router.py:88`) are uncovered. Removing the `"\\" not in text` clause leaves every vector green. The only vector with `"` (`git commit -m "wip`) has no `'` at all, so it never reaches the `"` check either. Concrete cases to pin: `grep it\'s x y` → command (the `\` turns the signal off, and the line has no function word, so it stays a command; with the `\` clause removed it flips to natural language) and `git commit -m "it's"` → command.. Deferred, not addressed here: 8 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v1/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 2 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 2): rebuilding for the implementation-level findings — The brief says the quote signal "overrides" rules 1–4, but nothing pins it against rule 3 (`target/src/nl_shell/router.py:93-94` versus `:100-103`). I swapped in a version of `_reads_like_english` that checks rule 3 (`-` words and metacharacters) *before* the quote signal and ran all 20 new vectors: none failed. Only the spec'd output of `find . -name it's` changed, from NATURAL_LANGUAGE to COMMAND. `echo it's fine` pins the order against rule 1, and `find what's using port 80` pins it against rule 4, but no vector has an odd `'` together with a `-` word or a metacharacter. Fix: add a vector like `find . -name it's` → natural language, or `find what's in ~/src` → natural language, to `target/tests/test_repl.py:91-123`.. Deferred, not addressed here: 10 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v2/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

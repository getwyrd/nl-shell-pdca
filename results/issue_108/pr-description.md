## Summary
**User impact:** If you type an ordinary English request that happens to start with
a command name, such as "find large files in my home", "who is logged in" or "kill the
process on port 8080", nl-shell hands it to bash as a command instead of answering it.
You get a shell error or a command you did not mean, rather than help. Many everyday
words are commands on a normal Linux box (`find`, `who`, `watch`, `kill`, `free`,
`sort`, `time`, `test`…), so this hits a lot of plain requests.

This PR adds one simple, predictable rule to the router: a line that reads like an
English sentence goes to the model even when its first word is a command.

Reported in [#108](https://github.com/eduralph/nl-shell/issues/108).

## What to look at
The rule, in plain terms. Once the first word is known to be a command, the line is
treated as English if either:

- it has an apostrophe that bash would see as an unclosed quote ("find what's using
  port 80", "echo it's fine"), or
- it is at least four words long, is not an `echo`/`printf` line, has no option word
  (starting with `-`) and no shell symbol like `|`, `/`, `~` or `$`, and contains a
  common small English word such as "the", "in", "my" or "is".

Everything else routes as before. `ls -la`, `find . -name '*.py'` and
`git push origin main` stay commands. Typing `\cmd` still forces bash, and a wrong
route never skips the safety check on commands.

To try it: `pytest tests/test_repl.py -k routed`, or start nl-shell and type
`who is logged in`.

Known limits, also written in the module docstring: short sentences ("ls my files"),
sentences with no small function word, and sentences that hold a shell symbol ("find
big files in ~/src") still route as commands. The planned intent classifier (#40) is
meant to cover those.

## Root cause
`route()` returned COMMAND as soon as the first token was a bash builtin or resolved on
`$PATH`, without looking at the rest of the line. The module docstring named this as a
known limitation, and a test pinned it on purpose.

## Fix
- `src/nl_shell/router.py`: new `_reads_like_english()` applies the rule above after the
  first token resolves. The apostrophe check (`_has_unbalanced_single_quote()`: odd
  count of `'`, no `"`, no `\`) runs first and wins over the other checks. The old
  builtin / path / `$PATH` lookup moves into `_is_command_name()` with no change in
  behaviour, and `$PATH` is still read on every call. "Word" means `text.split()`, so
  the rule works on lines shlex cannot parse. `first_token()` is untouched, so its
  other caller in `failure_classes.py` is unaffected.
- Module docstring rewritten to describe the rule and its remaining limits.
- `docs/design/architecture/05-building-block-view.md`: router row updated.
- `tests/test_repl.py`: the fake `$PATH` fixture now also holds `watch`, `who`, `free`,
  `sort` and `grep`, so the new cases resolve as commands and cannot pass just because
  the word is missing. The pinned "known limitation" vector is flipped and new vectors
  are added.

## Verification
- **Claim:** English that starts with a command name routes as natural language. Old
  behaviour is kept for real commands.
  - **Checked:** `src/nl_shell/router.py:56-67` on `main` (a6efb0a): `route()` returns
    COMMAND on any resolved first token, and `:8-10` documents this as a limitation.
    After the patch, `route()` is at `src/nl_shell/router.py:115-122` and calls
    `_reads_like_english()` at `:91-104`.
  - **Test:** `tests/test_repl.py::test_input_is_routed_as_command_or_natural_language`
    (`tests/test_repl.py:89-125` after the patch). With only the production changes
    reverted, 8 of the 43 cases fail, among them `find large files in my home`,
    `find . -name it's` and `find what's in ~/src`. With the patch, all pass.
- **Claim:** each part of the rule is pinned by its own test case.
  - **Checked:** `tests/test_repl.py:113-125`: each case reads as English on every
    count but one (`printf …`, a `-` word, `~`/`/`, `|`, `"`, no function word, `\`
    or `"` next to an apostrophe). Two more cases show the apostrophe check runs
    before the option/symbol check. Moving that check after the option/symbol check
    makes exactly those two cases fail.
- **Claim:** nothing else changes.
  - **Checked:** `first_token()` (`src/nl_shell/router.py:53` after the patch) is
    unchanged. The full suite, including `tests/test_failure_classes.py` (its other
    user), passes.

Fixes #108

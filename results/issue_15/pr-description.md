## Summary
**User impact:** whatever you type at the `nl>` prompt, nl-shell answers with the same
"can't run anything yet" line. A shell command like `ls -la` and a plain request like
`show disk usage` look identical to it, so there is no sign the shell can tell them apart.

This PR adds the first, simple version of that decision: if the first word of the line is
a known command (a bash builtin, a program on your `$PATH`, or a path to an executable
file), the line is treated as a shell command; otherwise it is treated as a natural-language
request. Each kind now gets its own reply, saying which upcoming milestone makes it work.

Reported in [#15](https://github.com/eduralph/nl-shell/issues/15).

## What to look at
- The new router is a small standalone module, kept apart from the read loop so the later
  trained classifier (#40) can reuse it as its fallback without touching the REPL.
- The read loop change is one line: it asks the router which kind of input it got and
  prints the matching reply.
- Try it: `python3 -m nl_shell`, then type `ls -la` (command reply), `show disk usage`
  (natural-language reply), `what's using port 80` (natural-language reply, no crash on
  the lone quote), and `:quit`.
- Known, accepted limitation: English that starts with a command name, such as
  `find large files in my home`, is routed as a command. The test pins this on purpose so
  the trade-off is visible; the classifier in #40 is what fixes it. The full builtin list
  is used, so words like `help`, `type` or `test` at the start of a sentence also route as
  commands — trimming that list is a one-line change if reviewers prefer it.

## Root cause
There was no input router yet: the read loop printed a single fixed reply for every
non-empty, non-exit line (`src/nl_shell/repl.py:15` and `:47` on `main`). This is a gap
from the M0.1 scaffold, not a regression.

## Fix
- New `src/nl_shell/router.py`: a `Route` enum (command / natural language), the bash
  builtin list (`compgen -b`, keywords such as `if`/`for` left out), `first_token`, which
  reads only the first shell word and falls back to a whitespace split on bad quoting,
  and `route`, which checks builtin → path-to-executable → `shutil.which`.
- `src/nl_shell/repl.py`: the single `NOT_YET` constant becomes two fixed replies plus a
  route → reply map; the old print at `main:47` becomes `print(REPLIES[route(text)], ...)`,
  still after the blank-line and exit-command checks, so prefix modes (#14) can slot in
  before it.
- `docs/design/architecture/05-building-block-view.md`: a `nl_shell.router` row in the
  §5.3 code-layout table; the "planned" row now lists prefix modes instead of the router.
- `cli.py` is unchanged.

## Verification
Line numbers below are on this PR's branch (`main` at f9e01b7fa255978801957c88f724eae541f310c4
plus this change) unless marked `main:`.

- **Claim:** each line is routed as a command or natural language by its first word, and
  the reply says which.
  - **Checked:** `src/nl_shell/router.py:56-67` — builtin → command; token with `/` →
    command only if it names an executable file (`:51-53`); else `shutil.which`.
    `src/nl_shell/repl.py:19-30` — two distinct fixed replies naming M0.2 and M0.8;
    `:62` — the wiring point that replaced `main:47`.
  - **Test:** `tests/test_repl.py:87-107`, `test_input_is_routed_as_command_or_natural_language`
    — nine rows (`ls -la`, `git status`, `find large files in my home`, `cd /tmp`,
    `export FOO=1`, `  ls`, `show disk usage`, `what's using port 80`,
    `frobnicate the widgets`), run through the real `Repl` with `$PATH` pointed at a temp
    dir holding only fake `ls`, `git`, `find` (`:48-57`), so the host's tools don't matter.
    `cd` and `export` are not on that fake `$PATH`, so they pass only via the builtin check.
- **Claim:** input with invalid shell quoting never raises.
  - **Checked:** `src/nl_shell/router.py:38-48` — `ValueError` from the lexer falls back to
    a whitespace split.
  - **Test:** the `what's using port 80` row above.
- **Claim:** a path to an executable file counts as a command.
  - **Test:** `tests/test_repl.py:110-114`, `test_path_to_an_executable_routes_as_a_command`.
- **Claim:** `$PATH` is read on every line, not cached at import.
  - **Test:** `tests/test_repl.py:117-134`, `test_path_is_read_on_every_line` — same line
    twice, `$PATH` widened in between; first reply is natural language, second is command.
- **Claim:** `:quit` / `:exit` still end the loop before any routing; blank lines still
  print nothing.
  - **Test:** `tests/test_repl.py:137-140` (new) and the existing exit, blank-line and EOF
    tests (`:60-72`), unchanged. The two existing tests that asserted the old reply
    (`:75-84`) now assert the route-specific replies.
- **Red → green:** with only the production files reverted to `main`, 14 of 19 tests in
  `tests/test_repl.py` fail (each prints the old single reply where a route reply was
  expected; the 5 that pass are the pre-existing exit/blank/EOF tests). With the change,
  19 of 19 pass, and the full suite (`tests/`) passes 21 of 21.

Fixes #15

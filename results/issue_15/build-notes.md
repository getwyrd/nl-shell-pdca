# Build notes — issue 15 / heuristic-nl-vs-command-router

Target: eduralph/nl-shell @ main (f9e01b7). Worktree: `$PDCA_WORKTREE`
(`/home/eddie/nl-shell/nl-shell.pdca-wt`). Post-patch line numbers below refer to that tree;
"main:" refers to the base.

## What changed

1. **New module `src/nl_shell/router.py`** (67 lines). It has no REPL dependency, so #40 can
   keep it as the classifier's fallback.
   - `Route` enum, `router.py:21`.
   - `BASH_BUILTINS`, `router.py:27`: the output of `compgen -b` in bash 5 on this host,
     pasted in as-is. Keywords (`if`, `for`, `while`) are left out, as the brief says.
   - `first_token`, `router.py:38`: a `shlex.shlex(posix=True, whitespace_split=True)` lexer
     reads ONLY the first word, so `'ls' -la` still gives `ls`. On a quoting error
     (`ValueError`, `router.py:44`, e.g. `what's using port 80`) it falls back to
     `text.split()[0]`. It never raises.
   - `route`, `router.py:56`: builtin → command; a token containing `/` → command if
     `is_executable_file` (an executable regular file, `~` expanded, `router.py:51`);
     otherwise `shutil.which(token)` (`router.py:65`). `shutil.which` with no `path`
     argument reads `os.environ["PATH"]` on every call, so nothing is cached at import.
     An empty token (e.g. the input `''`) → natural language.
2. **`src/nl_shell/repl.py`**: replaces the single `NOT_YET` constant (main:15) with two fixed
   replies, `COMMAND_NOT_YET` (`repl.py:19`, names M0.2 / bash session) and
   `NATURAL_LANGUAGE_NOT_YET` (`repl.py:23`, names M0.8 / model backend), plus a
   `REPLIES` map (`repl.py:27`). The wiring point main:47 becomes
   `print(REPLIES[route(text)], ...)` at `repl.py:62`, still after the blank-line and
   exit-command checks (main:43-46), so #14's prefixes can slot in before it. Docstring
   updated (`repl.py:1-7`). `cli.py` untouched.
3. **`docs/design/architecture/05-building-block-view.md:75`**: new `nl_shell.router` row in
   the §5.3 table. In the "planned" row I swapped "input router" for "prefix modes", because
   the heuristic router part is now built and prefix modes (#14) are the part of the
   §5.1 input router still missing.
4. **`tests/test_repl.py`**: see below.

## Test

All in `tests/test_repl.py`, appended to the existing suite. Top-level import is
`from nl_shell.repl import Repl` only (the `NOT_YET` import is gone because the patch
removes that constant). The two expected replies are pinned as literals (`:9`, `:13`) rather
than imported, so the module still imports on the red leg where they don't exist.

- `fake_path` fixture (`:48`): `tmp_path/bin` holding executable `ls`, `git`, `find` stubs;
  `monkeypatch.setenv("PATH", …)` points only at it, so the host's installed tools don't matter.
- `test_input_is_routed_as_command_or_natural_language` (`:104`): the brief's table, all nine
  string rows, through `Repl` via the existing `run`/`scripted` helpers (`:20`, `:36`).
- `test_path_to_an_executable_routes_as_a_command` (`:110`): `<tmp>/build.sh --release` → command.
- `test_path_is_read_on_every_line` (`:117`): same line twice, `$PATH` widened between them;
  first reply is NL, second is command. This proves `$PATH` is read per call.
- `test_exit_commands_are_checked_before_routing` (`:137`).
- Updated: `test_ctrl_c_clears_the_line_and_keeps_going` (`:75`) and
  `test_input_is_not_run_yet` (`:81`) now assert the route-specific replies and use
  `fake_path` (the `ls` line would otherwise depend on the host's PATH).
- Unchanged and still passing: exit commands (`:65`), blank lines (`:71`), EOF (`:60`).

## Red → green (project's C4 gate, `engine/scripts/run-verify.sh`)

Run with `PDCA_BUNDLE=results/issue_15 PDCA_WORKTREE=<worktree>`:

```
green leg: (pytest exit 0; ran 19, failed 0, setup errors 0, import/collection errors 0)
red leg:   (pytest exit 1; ran 19, failed 14, setup errors 0, import/collection errors 0)
PDCA-EVIDENCE: C4 PASS — red without the fix (14 of 19 failed), green with it
```

The 5 tests that stay green on the red leg are the pre-existing exit/blank/EOF tests, which
is expected. Whole suite (`tests/`, incl. `test_cli.py`) with the patch: 21 passed.

## Self-refutation

- **(a) Genuine red?** Yes. The gate's red leg reverts every non-`tests/` hunk (router.py
  removed, repl.py back to main) and re-runs the file: 14 of 19 fail, 0 collection errors.
  Every failure is the old single `nl-shell can't run anything yet…` line where a route
  reply was expected.
- **(b) Production path?** Yes. Every new test drives the real `Repl.run` →
  `nl_shell.router.route` → `shutil.which` / `os.access`. Nothing is mocked except `$PATH`,
  which is the input the heuristic is defined on.
- **(c) Fixture includes the fault?** Yes. The fixture holds both sides: real executables on
  `$PATH` (`ls`, `git`, `find`), names not on it (`show`, `what's`, `frobnicate`), builtins
  that are NOT on the fake PATH (`cd`, `export`, so the builtin branch is what makes them
  pass), an unbalanced quote, and an executable reached by path.

## Choices and what I ruled out

- **Full builtin list vs. a trimmed one.** Some builtins are English words (`help`, `type`,
  `read`, `set`, `test`, `wait`, `source`), so "help me find big files" routes as a command.
  I kept the full list because the issue and brief say "bash builtin" with no carve-out,
  and the brief already accepts this class of miss (`find large files…` is pinned). Worth a
  human look; trimming is a one-line change in `router.py:27`.
- **`shlex.split(text)[0]` vs. the single-token lexer.** `shlex.split` parses the whole line,
  so a quoting error anywhere (even after a valid first word, e.g. `echo "hi`) would hit the
  fallback. The lexer only reads the first word. Both fall back the same way, so this mostly
  affects which path runs, not the result.
- **Importing reply constants in the test** was ruled out: per the brief, a module-level
  import would turn the red leg into a collection error (UNVERIFIABLE). A lazy import inside
  the test would also work, but literals pin the user-facing text directly.
- **Out of scope, not done:** prefixes/meta-commands (#14), env-assignment prefixes
  (`FOO=1 make` → NL today), aliases/functions, bash keywords, `cli.py`.

## Commit-readiness

The target has no formatter or pre-commit config (no `.pre-commit-config.yaml`, no
ruff/black section in `pyproject.toml`; CI `.github/workflows/tests.yml` runs only pytest).
I checked `git diff --check` (clean, no whitespace errors) and kept lines ≤ 95 chars to
match the existing files. Nothing pushed, no PR opened.

# Build notes — #155 failure-classifier-by-exit-code

## Base

Built in `$PDCA_WORKTREE` (`/home/eddie/nl-shell/nl-shell.pdca-wt-l1`) on the folded wave
base `pdca-integration/main-r2546dbf9639f` @ `5d3d291`. That base has #140's
`session.CommandResult` (`src/nl_shell/session.py:375-389`) with the fields the brief
lists (plus two defaulted ones, `input_forwarded` and a dropped-copy flag, which the
classifier does not read). It is not plain `main`, so the "report blocked" branch of the
brief does not apply.

Citation drift: the brief cites the pty-protocol §4.1 text at
`docs/design/specs/pty-protocol/v1.md:370-372` on `cefb359`. On this base the same sentence
("`D n+1` without `S n+1` means bash read the input but ran nothing ...") is at
`docs/design/specs/pty-protocol/v1.md:375-376`. Same text, later lines.

## The change (2 new files, nothing else touched)

- `src/nl_shell/failure_classes.py` (new, 335 lines)
  - `classify(result, command, lookup=None)` — `failure_classes.py:114`. Checks
    `isinstance(result, session.CommandResult)` first, so a bare `pty_protocol.Done` or an
    `int` raises `TypeError` (decision 3). The precedence order follows the brief: `ran=False`
    → status 0 → 130 → privilege → 127 → 126 → 129–192 → other.
  - `Failure` dataclass: `kind`, `status`, `pipestatus`, `message`, `offer_correction`,
    `to_reader`, `command_word`, `packages`, `signal_number`, `signal_name`, plus an
    `is_error` property. `offer_correction` is False only for NONE, INTERRUPTED and
    PRIVILEGE. `to_reader` is True only for OTHER. Both are worked out in one place (the
    inner `failure()` helper), so no branch can get them wrong.
  - Rule 1 (privilege): `words()` at `failure_classes.py:176` is the second, whole-text
    splitter the brief asks for. It is built like `router.first_token`
    (`src/nl_shell/router.py:38-48`): `shlex` in posix mode with `whitespace_split`, and a
    whitespace fallback on `ValueError`. It also sets `punctuation_chars=";&|()<>`"` so
    operators are split off words, and `commenters=""`. On top of that there is a coarse
    pass (`_coarse`): it removes quotes and backslashes, then splits on whitespace,
    operators and `{},=`. `is_privileged` (`:204`) checks the basename of every word
    against `PRIVILEGE_PROGRAMS` (`:46`; policy-gate spec §4 plus sudo-rs, sudo.ws,
    sudoedit, sudoedit-rs). It also follows alias values from the snapshot, aliases of
    aliases included, with a visited set so it ends.
  - Rule 2: `_blank_or_comment` checks that every line is blank or starts with `#`. If so,
    the result is NONE; anything else is OTHER with a "may be a syntax error" message.
  - Rule 4: `_unresolved_word` (`:263`) returns a word only when all of these hold:
    the text is one line; no operator token, backtick or `$(` (this catches the
    double-quoted `"$(htop)"`, which shlex keeps as one word); the first word (from
    `router.first_token` itself) is not an assignment and is a plain name (no `/`, `$`,
    glob, `~` or quotes); it is not a snapshot function, alias or keyword; it is not a
    builtin unless `enable -n` turned that builtin off; every `$PATH` entry is absolute
    (an empty, `.` or relative entry means "unknown", so no suggestion); and it is not an
    executable file in any `$PATH` directory (`router.is_executable_file`). The lookup
    is called only when a word passes these checks and `_safe_to_show`.
  - Display safety: `_safe_to_show` (`:301`) requires 1–64 characters,
    `str.isprintable()`, and no hits from the project's own character policy
    (`render.has_hidden`, `render.too_many_marks`, `src/nl_shell/render.py:136,154`).
    Package names get the same check, are de-duplicated, and are capped at 5.
  - Signals: `signal.Signals(n).name`. If the number has no name (e.g. a realtime signal
    number), the message says "signal 40" with no name, so the text `None` never appears.
    137 adds the OOM-killer hint (the kernel's out-of-memory killer, which sends SIGKILL).
  - The module source has none of `/var/`, `/usr/`, `commands.db`, `ubuntu`, `sqlite3`,
    `targets`. The docstrings were worded to avoid them, because the test checks this.
- `tests/test_failure_classes.py` (new, 474 lines). It imports only the standard library
  and pytest at module level, and has no skips. It builds real `CommandResult` /
  `Snapshot` / `Done` objects inside each test function.

## Choices and what I ruled out

- **The coarse pass on top of shlex for rule 1.** shlex alone misses
  `echo "$(sudo x)"` (one word, `$(sudo x)`), `bash -c "sudo x"`, and brace expansion
  `{sudo,} x`. Bash runs sudo in all three. The brief says over-matching is the safe
  direction, so the coarse pass adds every fragment. Cost: about 6 lines
  (`_COARSE_DROP`, `_COARSE_SPLIT`, `_coarse`). It does not change any lookalike row:
  `echo sudo-ish`, `pseudo x`, `visudo x` and `sudoers-check x` stay OTHER, because `-`
  and letters are not split points. I did not recurse shlex into quoted words, because
  the coarse pass already covers that with no depth limit to reason about.
- **`commenters=""`.** shlex's default treats `#` in the middle of a word as the start
  of a comment. So `echo a#; sudo x` would hide the `sudo`, even though bash runs it.
  Turning comments off makes `ls # sudo` count as privileged; that is over-matching,
  which the brief accepts.
- **No catch around `lookup(word)`.** The brief says the provider (#156) owns checking
  its own data. Swallowing provider errors here would hide #156 bugs. If the human wants
  the classifier to survive a broken provider, it is a 3-line `try/except Exception`
  in `_suggestion`.
- **Words containing `/` get no suggestion.** A 127 for `./x` or `/opt/x` means that path
  does not exist. Naming the package for that basename would often be wrong. The brief
  does not cover this case; I picked the safe side, and the `path-word` row pins it.
- **Not-found message names the word even without a package** ("Command not found:
  frobnicate."), but only when rule 4 shows it is the word that failed. When the word is
  unknown (a pipe, a list, a found wrapper) the message is just "Command not found.", so
  it never blames the wrong word (`cat` in `cat f | htop`).
- **Privilege message** is one constant, `PRIVILEGE_MESSAGE` (`:61`). It has no tool
  name, no "password", no "authoriz", no "permission" and no retry wording; a test checks
  this list. The test also checks that every privilege row gets exactly this text.
- I did not change `router.py`, as the brief asks. The keyword set lives in
  `failure_classes.py:52`.

## Red → green (project runner)

Both checks were run through the project's own gate scripts with
`PDCA_BUNDLE=results/issue_155` and `PDCA_WORKTREE` set:

- `engine/scripts/run-verify.sh` (C4): `PDCA-EVIDENCE: C4 PASS — red without the fix
  (127 of 127 failed), green with it`. Red leg: pytest exit 1, ran 127, 0 collection
  errors. Each test fails on its in-function `import nl_shell.failure_classes` with
  `ModuleNotFoundError`, which counts as a test failure, not a collection error.
- `engine/scripts/run-suite.sh` (T3): `779 passed`, `PDCA-EVIDENCE: T3 PASS`.

## Refuting my own test

- **(a) Genuine red?** Yes. `run-verify.sh` removes the production file
  (`src/nl_shell/failure_classes.py`) and re-runs the test. All 127 tests failed, with 0
  collection errors. With the file put back, all 127 pass. While writing the test I also
  caught a test bug: `"" not in message` is always False. I replaced it with an
  exact-message check.
- **(b) Production path?** Yes. Every test calls the real
  `nl_shell.failure_classes.classify` on a real `nl_shell.session.CommandResult` holding a
  real `pty_protocol.Snapshot`. The `$PATH` checks run the production
  `router.is_executable_file` against real executable files the test writes into
  `tmp_path`. Only the package lookup is a fake. The brief makes it an injected callable,
  and the real one belongs to #156.
- **(c) Fixture includes the fault?** Yes. The `output` field always holds hostile text
  (`command not found`, `wrong password`), and `test_output_does_not_change_the_class`
  swaps in different output, including an ESC sequence, and shows the class does not
  change. The NO_SUGGESTION rows install the wrapper (`timeout`, `env`, `bash`, `htop`
  itself) on the session `$PATH`, so a word that was actually found is there in the test.
  The unsafe-word rows put a real ESC, a real U+202E and a BEL into the command. As the
  brief requires, no real sudo or other privilege tool runs; the privilege class depends
  only on the confirmed text, so building results directly loses nothing.

## Commit-readiness

The target has no formatter, linter or pre-commit config: `pyproject.toml` has no
ruff/black section, there is no `.pre-commit-config.yaml`, and CI
(`.github/workflows/tests.yml:23`) only runs `python -m pytest`.
`.github/workflows/docs-checks.yml` checks docs, and this patch touches none.
`git diff --check` is clean. The longest line is 95 characters; the existing `src/` has
209 lines over 88, so this matches the house style. Non-ASCII test inputs are written as
Python escapes, the same convention as `tests/test_charsafety.py`.

No push, no PR.

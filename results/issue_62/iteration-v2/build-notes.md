# Build notes — issue 62 / failure-classes-by-exit-code (iteration 2)

Wave base: `pdca-integration/main-r2546dbf9639f` @ `cefb359` (worktree
`nl-shell.pdca-wt-l0`). Line numbers are post-patch unless marked "base".

This iteration starts from the iteration-1 patch (`iteration-v1/patch.diff`) and fixes the
six carry-forward findings. The target loader (`targets.py`) and `target.toml` parts are
unchanged from iteration 1.

## Carry-forward findings and what I did

1. **Confident wrong package when the first word was found** (`timeout 5 frobnicate`,
   `stdbuf`, `setsid`, `bash -c`, `ssh host …`). I did not just grow the wrapper list. A
   list can never be complete: any found program can exit 127 (`npm run x` when the script
   is missing, any shell script on `$PATH`). I took the reviewer's "sounder fix" instead,
   which removes the cause: a package is suggested only when the session could **not**
   resolve the first word. `_resolves` (`failure_classes.py:285-306`) checks, in order:
   bash keywords (`_BASH_KEYWORDS`, `:85`), the snapshot's functions, aliases parsed from
   `alias -p` text (`:93`), bash builtins not disabled by `enable -n` (reusing
   `router.BASH_BUILTINS`, base `router.py:26-34`, not a second list), and an executable
   file in any `$PATH` entry from the snapshot (`Snapshot.path`, base
   `pty_protocol.py:69`). If `$PATH` has an empty or relative entry, the answer depends on
   the session's working directory, which the snapshot doesn't carry, so the word counts
   as found (no suggestion, the safe side).
   - Where the session state comes from: `CommandResult.snapshot` (base `session.py:373`),
     the snapshot reported right after the command. A bare `pty_protocol.Done` has no
     session state, so with a bare `Done` the classifier gives **no** suggestion
     (`:207-212`; the `snapshot is not None` term). This changes iteration 1: the binding
     table now builds `session.CommandResult` records (the "session's completion result
     (#10)" in Scope (1)) with a snapshot whose `$PATH` is an empty temp folder the test
     controls. `Done` is still accepted and still classified; only the suggestion needs the
     snapshot. Test: `test_bare_done_record_gives_no_suggestion`.
   - I kept the brief's seven-word wrapper list plus sudo/su/pkexec/doas (`:81-83`). The
     brief requires it, and it still matters for words like `env` that are always found.
   - Real-host replay (host `$PATH`, real `commands.db`): `timeout 5 frobnicate`,
     `stdbuf -oL frobnicate`, `setsid frobnicate`, `bash -c frobnicate`,
     `ssh host frobnicate` → all "Command not found." with no package. `htop` and
     `cowsay hi` (neither installed here) → "provided by the package htop" / "cowsay".
2. **`ran=False` ignored.** New class `NOT_RUN` (`:105`), checked first (`:191-192`), for
   every status: `is_error`, `offer_correction` and `to_reader` are all False, message
   "No command ran." I picked one rule for all statuses rather than trying to tell a
   syntax error (status 2, real) from a comment (stale `$?`): telling them apart needs a
   parse, which is #12's job. Test: `test_nothing_ran_is_not_classed` (5 statuses × 3
   texts, including a stale 127).
3. **"None" in the message.** The display check (`_is_shown_safely`, `:280-282`) is now
   part of the "certain" test (`:207-212`). An unsafe word gives the plain
   "Command not found.", no packages, and `command_word=None`. So `command_word` is now
   always display-safe when set, which also closes the "raw word unfiltered" note in
   finding 6; the `Failure` docstring says so (`:134-136`).
4. **`$`-anchor case missing.** Added `"htop\n"` to `test_bad_provider_names_are_dropped`.
   Mutating `fullmatch` to `re.match(r"…$")` now fails exactly that case.
5. **`not-found-under-sudo` didn't test the exclusion.** Added `"sudo": ["sudo"]` to
   `FAKE_PROVIDERS`. Removing `| set(WRAPPER_FAILURE_STATUS)` now fails that row.
6. **Display guard untested.** `test_unsafe_word_reaches_no_message` has ESC, a U+202E
   bidi override, a 65-char word and a BEL byte. `test_64_char_word_is_shown` pins the
   boundary.

## Decisions worth a look at sign-off

- **Bare `Done` → no package suggestion.** Safe direction, but a caller that only has the
  `D` record loses suggestions. `Session.run` returns `CommandResult` (base
  `session.py:782-790`), so #17 will have the snapshot.
- **The `$PATH` check runs after the command**, on the snapshot taken after it. If the
  command itself installed the word, there is no suggestion: safe direction.
- **`NOT_RUN` for `ran=False` with status 0 too.** It is not `NONE`; both are non-errors
  with no offer and no reader, so consumers treating "not NONE" as a failure should check
  `is_error`.
- Still open from iteration 1: the sudo + status 1 product decision (brief Open questions);
  `sudo x` with status 2 is `OTHER` (row `other-sudo-2`); `/usr/bin/sudo` matches by
  basename.

## Ruled out

- **Only extending `_COMMAND_WRAPPERS`** with `timeout stdbuf chroot setsid ionice taskset
  nsenter unshare flock runuser eval bash sh ssh`: a 1-line change, but it guards a symptom.
  `npm run x`, `make`-like tools, `python3 -m x` and any user script on `$PATH` still give a
  wrong package. The `_resolves` fix is ~25 lines (`:285-306`) and covers every found word.
- **Probing the nl-shell process's own `$PATH` with `shutil.which`** (what the router does,
  base `router.py:65`): the session's `$PATH` can differ (the user may change it), and the
  snapshot reports the real one. It would also make the table depend on what the test host
  has installed.

## Verification

- C4 (`engine/scripts/run-verify.sh` with `PDCA_BUNDLE`/`PDCA_WORKTREE`): green, then red
  with production hunks reverted: 92 of 92 failed, 0 collection errors →
  `PDCA-EVIDENCE: C4 PASS`.
- T3 (`engine/scripts/run-suite.sh`): 573 passed → `PDCA-EVIDENCE: T3 PASS`. The real-lookup
  test ran (this host has the command-not-found data); it was not skipped.
- Targeted mutations (each fix broken alone, test file re-run, file restored):
  no `_resolves` → 10 fail; no `ran` check → 15 fail; `$`-anchored `re.match` → 1 fail
  (`htop\n`); sudo removed from wrappers → 1 fail; no display guard → 4 fail; empty/relative
  `$PATH` entry allowed → 4 fail; disabled builtins ignored → 1 fail.
- Target repo has no formatter, linter or pre-commit config (no `.pre-commit-config.yaml`,
  no ruff/black/flake8 in `pyproject.toml`, no git hooks). All lines ≤ 100 chars.
  `scripts/docs_links.py`: 0 broken.
- Housekeeping: the mutation run left a scratch copy `.mut-orig.py` in the worktree root
  (untracked, not in `patch.diff`), and one stray `git diff` copy went to `/tmp/x`. I did
  not delete either, per the harness rule; both are safe to drop.

## Refuting my own test

- **(a) Genuine red?** Yes. The C4 red leg reverts `failure_classes.py`, `targets.py` and
  `target.toml` and re-runs the file: 92/92 fail, no collection error (all imports of new
  code are inside test functions). Each carry-forward fix also goes red on its own (the
  mutation list above).
- **(b) Production path?** Yes. Every test calls the real `failure_classes.classify` /
  `provider_lookup` and `targets.load`, with real `session.CommandResult`,
  `pty_protocol.Snapshot` and `pty_protocol.Done` objects. Only the package lookup is faked
  in the table, as the brief requires. `test_real_lookup_with_session_path_skips_found_wrapper`
  runs the reviewer's `timeout` case through the shipped `target.toml` and the host's real
  database.
- **(c) Fixture includes the fault?** Yes. The fixtures contain the failing elements: a
  real executable `timeout`/`npm` on the session `$PATH` with a lookup that knows them; an
  alias, a function and a builtin that the lookup also knows; `ran=False` with a stale 127;
  ESC/bidi/65-char words with a lookup that returns a package; `htop\n`; and `sudo` known
  to the lookup. The `CommandResult` output holds attacker-shaped "command not found" text
  to show it is never read.

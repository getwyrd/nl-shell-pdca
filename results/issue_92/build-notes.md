# Build notes — issue 92 / os-target-folder-and-selection (iteration 4, narrowed slice)

## Base

The Do worktree (`$PDCA_WORKTREE`, HEAD `8c95e05`, the old `pdca-integration` tip) is not
`origin/main` (`c47c5c2`), the brief's target. It differs from `main` only in docs and in
`targets/ubuntu-26.04/sensitive.toml` (which is missing here). `src/`, `tests/` and
`pyproject.toml` are byte-identical (`git diff HEAD origin/main -- src tests pyproject.toml`
is empty). So every `path:line` cited below for the *pre-change* code is the same on `main`.
The patch only touches those paths plus the new `targets/ubuntu-26.04/target.toml`, and
`git apply --check patch.diff` succeeds on the `main` checkout (`c47c5c2`).

## What changed, and why

1. **`targets/ubuntu-26.04/target.toml`** (new). ADR-0023 fields (`0023-os-targets.md:43`).
   Keys: `id`, `display_name`, `shell`, `package_owner_query` (an argv array,
   `["dpkg", "-S"]`, so a later caller can exec it without shell-splitting), `[os_release]
   ID / VERSION_ID`, `[sudo] implementation / version` (`sudo-rs` `0.2.13`, ADR-0015
   `0015-sudo-handling-v2.md:29`). The key names are documented in the comment at the top of
   the file. No `allowlist.toml` (moved to #139, as the re-plan requires).

2. **`src/nl_shell/os_release.py`** (new). `read()` (`:85`) tries `/etc/os-release` then
   `/usr/lib/os-release`, and moves on **only** on `FileNotFoundError`. Any other `OSError`
   (directory, permission denied) or a UTF-8 decode error raises `OsReleaseError` at once.
   `parse()` (`:31`) with `_unquote()` (`:47`) handles single quotes (literal), double quotes
   (backslash escapes only `" \ $ ``), and unquoted words. It skips comments, blanks and
   malformed lines (unbalanced quote, unquoted whitespace), as systemd does. I first used
   `shlex.split`, then dropped it: inside double quotes shlex keeps the backslash in `\$`
   and `` \` ``, which os-release(5) says to drop.

3. **`src/nl_shell/config.py`** (new, kept separate from the target loader as the Ordering
   note asks, so #77 can extend it). `config_path()` (`:33`) ignores an empty or
   non-absolute `XDG_CONFIG_HOME` and falls back to `$HOME/.config`. `load()` (`:45`):
   missing file → defaults; bad TOML or bad UTF-8 → `ConfigError` naming the file; a
   `target` that is not a string → `ConfigError`; unknown keys are ignored.

4. **`src/nl_shell/targets.py`** (new). `TARGETS_ROOT` (`:28`) = the repo's `targets/` next
   to `src/`. `load()` (`:127`) checks the id with `is_plain_id` (`:114`, regex `:35`, and
   rejects `.` and `..`) **before** any `root / id` join. It then requires the folder to be a
   directory that resolves inside the root (this also stops a symlink escape), and passes the
   parsed TOML to `_validate()` (`:154`). That checks the required fields and types, that
   `id` equals the folder name, and that `shell` is `bash`. It reads only `target.toml`.
   `select()` (`:210`):
   - named target → load it; `matches` is True only if os-release was read and `ID` and
     `VERSION_ID` are exactly equal; otherwise `reason = MISMATCH_REASON` (`:32`, the spec
     §7.7 text). If os-release could not be read, detected is `unknown unknown`.
   - nothing named → refuse (`NoMatchingTarget`, `:42`) if os-release can't be read.
     Otherwise the only candidate is the folder `<ID>-<VERSION_ID>`, and its
     `[os_release]` must agree too. No scan, no `ID_LIKE`, no near version. A broken
     `target.toml` in the matching folder is refused with its file and problem. I chose
     "derive the folder name, then check" over "scan every target for a match" so that an
     unrelated broken target can't block start-up. The ADR also defines the id as
     `ID-VERSION_ID` (`0023-os-targets.md:37-39`).
   - `Selection` (`:88`) carries `target`, `matches`, `detected_id`,
     `detected_version_id` and `reason` for #12, plus `status_lines()` (`:102`).

5. **`src/nl_shell/cli.py`** (was `:11-18`; now `main` at `:19`). Adds `--target ID`. The
   keyword-only `targets_root` / `os_release_paths` arguments are the test injection points
   (Scope 7). The flag takes priority over `config.target`. A refusal prints a short
   `nl-shell: ...` message to stderr and returns 1 before the REPL is built. The no-match
   message names the detected OS, the available ids (read at run time) and both ways to name
   one, including the real config path. A mismatch prints a start-up warning. The
   selection's status lines go to `Repl.interactive(status_lines=...)`. The tagline is now
   OS-free (`DESCRIPTION`, was `cli.py:14`). The config file is always loaded, even with
   `--target`: a broken config is refused, not silently skipped. A config `target` that
   doesn't exist is never loaded when the flag is given (tested).

6. **`:status` per-session mechanism** (Scope 5). The module-level `STATUS_LINES` list
   (`input_modes.py:77-82` on main) is removed. `StatusLine` (`input_modes.py:78`) is a
   zero-argument callable. `status(session_lines)` (`:92`) prints the version line, then the
   session's lines. `META_COMMANDS` (`:111`) values now take the session's status lines.
   `reply(prefixed, status_lines)` (`:138`) passes them through (`:151`). `Repl` keeps its own
   tuple (`repl.py:42-48`). `interactive` accepts it (`repl.py:51-55`), and `_reply` is no
   longer a `@staticmethod` (was `repl.py:66-67`, now `:74`, passing `self._status_lines` at
   `:84`). The comment at `input_modes.py:77-79` is rewritten to describe this and how #16 /
   #77 add a line: add a callable to the tuple `cli.main` builds. **The PR description must
   record this change for #16 and #77** (publish's job; noted here so it isn't missed).

7. **Tagline.** `__init__.py:1`, `cli.py:14`, `pyproject.toml:8` reworded to "Natural-language
   shell: a small local model proposes commands, bash runs them". `pyproject.toml:34` still
   says `sudo-rs` in a pytest marker description. That is not `ubuntu`/`26.04` and not the
   `[project] description`, so criterion (j) doesn't cover it. I left it alone.

8. **Tests.** `tests/test_targets.py` (new) covers (a)–(k). `tests/test_cli.py` now injects a
   fake matching target and os-release, and asserts the status lines handed to `interactive`.
   `tests/test_input_modes.py::test_status_lines_can_be_extended` had to change: it appended
   to the removed `STATUS_LINES`. It now passes lines to `Repl(...)` and checks that a fresh
   `Repl` doesn't show them. Its header comment (`:28-29`) is updated too. New modules are
   imported only inside test functions, so on the red leg the file still loads and fails.

## Things for the PR description (publish)

- `Refs #92` (never Fixes/Closes). The slice is narrowed: allowlist → #139, "(degraded)" → #12.
- The `:status` extension point changed (item 6), for #16 and #77.
- Known limit: after a non-editable `pip install .`, `TARGETS_ROOT` points outside the
  installed package, so nl-shell refuses to start ("no target ... matches"). CI and
  CONTRIBUTING use `pip install -e`. Not fixed here (#48, #50).

## Red→green evidence (project runner)

`PDCA_BUNDLE=results/issue_92 ./engine/scripts/run-verify.sh` (the C4 gate, run from the
instance root, worktree = `$PDCA_WORKTREE`):

```
== C4 green leg: ... tests/test_cli.py tests/test_input_modes.py tests/test_targets.py
91 passed
== C4 red leg: bundle test(s) with the production change reverted
61 failed, 30 passed   (ran 91, import/collection errors 0)
PDCA-EVIDENCE: C4 PASS — red without the fix (61 of 91 failed), green with it
```

Full suite with the fix: `237 passed` (`.venv/bin/python3 -m pytest -q`).

## Refuting my own test

- **(a) Genuine red? Yes.** The C4 red leg reverted every non-`tests/` hunk and re-ran the
  tests: 61 failed, with 0 import errors. In `test_targets.py`, every test fails except
  `test_repl_without_target_has_no_target_lines`, which guards behaviour `main` already has
  (I checked by comparing the collected ids with the FAILED list). (j) is a real red: it
  reports `src/nl_shell/__init__.py:1 ... for Ubuntu 26.04` and the `cli.py:14` line, and
  `test_no_os_name_in_project_description` fails on `pyproject.toml:8`.
  `test_cli.py::test_main_runs_the_interactive_repl` fails with `TypeError: main() got an
  unexpected keyword argument 'targets_root'`.
- **(b) Production path? Yes.** The tests call the real `cli.main`, real `targets.select` and
  `load`, the real `os_release.read` on real files, the real `config.load` through the real
  XDG env, and a real `Repl`. The only substitutes are `Repl.interactive` (it would need a
  TTY and prompt_toolkit; replaced by a scripted `Repl`, as the brief asks) and a
  pass-through spy on `targets.select`. The spy calls the real function and records the
  `Selection` it returns, so the test can check the result directly. (i) loads the real
  `targets/ubuntu-26.04/target.toml` and checks `TARGETS_ROOT` is the repo's `targets/`.
- **(c) Fixture includes the fault? Yes.** The fakes contain the failing inputs, not curated
  ones. Non-matching os-release: a near version `26.10`, and `ID=debian` with
  `ID_LIKE=ubuntu`. An `/etc/os-release` that is a directory, mode 000 (skipped as root) or
  not UTF-8, *with a matching `/usr/lib/os-release` beside it*, so a wrong fallback would
  show. A valid target placed at `../x` outside the root, so a wrong path join would load it.
  A folder named `ubuntu-26.04` whose match fields disagree. Each broken `target.toml` case.
  A relative `XDG_CONFIG_HOME` that points at a real config with a different target.

## Commit-readiness

nl-shell has no formatter, linter or pre-commit config (no `.pre-commit-config.yaml`, no
ruff/black/flake8 settings in `pyproject.toml`, no non-sample git hooks). CI runs only
pytest, docs checks and the linked-issue check. I kept new lines within 92 columns (the
longest line in the existing `src/` and test files I compared against), and
`git diff --check` is clean. The publish commit needs DCO sign-off (`git commit -s`,
CONTRIBUTING.md).

## Housekeeping slip

While comparing test ids I wrote two scratch files, `/tmp/all_ids.txt` and
`/tmp/failed.txt`, outside the allowed roots. They are not part of the patch. I did not
delete them (cleanup belongs to the harness).

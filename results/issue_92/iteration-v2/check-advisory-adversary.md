# Adversarial review — issue 92 / os-target-folder-and-selection

I tried to break the fix and mostly could not. One edge case is a judgment call for the human. The rest are notes.

## Evidence (red→green)

- `gate-logs/C4-verify.log`: I could not re-run it here, because this sandbox has no `pytest`. That is a missing tool, not a sign the fix is broken. The frozen log is enough to judge it. Green: 49 passed. Red (production files reverted): the new tests fail on `ImportError: cannot import name 'targets'` (`tests/test_targets.py:440`), and the `cli.main(["--target", …])` cases fail. The only tests that stay green are `test_version_flag`, `test_no_os_name_in_code` (green-only by design, criterion (h)) and `test_repl_without_a_target_has_no_target_lines`. So the red is real and comes from the intended cause.
- I checked whether the tests use the real code or a copy of it. They use the real code. `tests/test_targets.py:95-117` calls the real `cli.main`, real `os_release.read` and real `targets.select`. Only `Repl.interactive` (prompt_toolkit) and the os-release path and targets root are swapped out. Case (g) reads the real `targets/ubuntu-26.04/` through the real loader (`tests/test_targets.py:436-442`). The one wiring step no test covers is `Repl.interactive(selection)` → `cls(session.prompt, sys.stdout, selection)` at `src/nl_shell/repl.py:56-60`. It is a one-line pass-through, so I'm not filing it.

## Inputs I tried against the production code (run directly with plain Python against `$PDCA_TARGET/src`)

- **os-release parsing** (`src/nl_shell/os_release.py:20-57`). I tried single quotes, double quotes, unquoted values, a trailing space, CRLF line endings, an escaped quote, an unescaped inner quote (rejected), `export ID=…` (ignored) and a duplicate key (the last one wins, as in a shell). All behave correctly. A UTF-8 BOM drops the `ID` key, which leads to a refusal. That is the safe outcome.
- **Target ids** (`src/nl_shell/targets.py:35,130`). `Ubuntu-26.04`, `ubuntu-26.04/`, `ubuntu-26.04/../ubuntu-26.04` and `.` are all refused before any path is built, so path traversal through `--target` or `target =` doesn't work. The automatic candidate `<ID>-<VERSION_ID>` goes through the same regex (`targets.py:242`).
- **Unreadable or non-UTF-8 os-release** (last round's finding). Fixed at `os_release.py:80-91`: only `FileNotFoundError` falls back to the next file. A directory or a permission error becomes a refusal, and both have tests (`tests/test_targets.py:193-226`).
- **Allowlist** (`targets/ubuntu-26.04/allowlist.toml`). Last round's items are fixed and pinned by tests: `hostname` is cut down to `-s`/`-I` (`:304-306`, test `:542`), the GPU tools have `max_operands = 0` (`:400-409`, test `:547`), and the `less`/`more` `+` words have a comment for #12 (`:341-347`, test `:554`). I found no listed option that writes a file, runs a program or changes system state. The question of whether each entry is safe to run without a confirm is still the human's (already deferred).

## Findings

- NEEDS-HUMAN [human] — `src/nl_shell/cli.py:28-38` with `src/nl_shell/os_release.py:82-91`: `--target` can't get past an os-release file that exists but can't be read, though it does get past a missing one. Reproduced with fakes. If `/etc/os-release` is a directory (or unreadable) and the user passes `--target ubuntu-26.04`, nl-shell exits 1 with "can't be read". If neither os-release file exists, the same command starts the REPL in the mismatch state ("detected: unknown unknown"). Either way the session would be in mismatch (degraded) mode, where every command needs a confirm. So starting would be safe, and refusing takes away the user's only way out. Brief case (c) only says "on a non-matching OS → starts" and doesn't cover this. Low severity. The human should decide whether a named target should also start, in mismatch mode, when os-release can't be read.
- `src/nl_shell/config.py:30-31` (note, not gating): a relative `XDG_CONFIG_HOME` is used as given, so `config.toml` is looked up relative to the current directory. The XDG Base Directory spec says to ignore relative values. The impact is small: a stray `config.toml` can only name a target that already exists under `targets/`, and a mismatch is still recorded. Not routing this back on its own.
- `src/nl_shell/cli.py:13-14` (note): the patch joins `prog=` and `description=` onto one line. That change isn't needed, but it keeps the tagline on line 14, so the exception for criterion (h) (`tests/test_targets.py:569`) still lines up. That exception is keyed by (file, line), not by text, so any OS name added later on `cli.py:14` would slip past (h). This is weak, but the brief defines it that way.

## Reviewer verdict

- `check-gates.json` T2 "no security-relevant path touched" is still not a security review of the allowlist. This patch adds a new `allowlist.toml` that decides what runs without a confirm. The human review that the brief asks for (Impact: "Every allowlist entry lands in SUMMARY §6") is already among the deferred findings, so I'm not filing it again. Sign-off must not count T2 = pass as that review.

Attempted to refute: the red→green evidence (parallel copy, tautology, wrong-reason red), os-release parsing and the fallback between the two files, target-id path traversal, the order of flag vs config, a broken `target.toml`, and the last round's allowlist fixes. I could not refute any of them. The only open item is the `--target`/unreadable os-release case above.

<!-- pdca:leaf-complete -->

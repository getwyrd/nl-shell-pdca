# Adversarial review — issue 92 / os-target-folder-and-selection

**Result: I tried to refute the fix and could not.** No NEEDS-HUMAN findings. The notes below
are what I attacked and why it held, plus two small observations that need no action.

## Evidence (red→green)

- `gate-logs/C4-verify.log:10-16,1714` — I could not re-run pytest here (`python3 -m pytest`:
  "No module named pytest"). That is a sandbox gap, not a refutation, so I judged the frozen log.
  Red leg: 61 of 91 fail; every failure is a missing name/kwarg in production code
  (`TypeError: main() got an unexpected keyword argument 'targets_root'`, `ImportError`, and the
  real tagline hits for (j)), not a test-setup fault. The 30 red passes are the existing
  `tests/test_input_modes.py` table plus `tests/test_targets.py::test_repl_without_target_has_no_target_lines`,
  which is a regression guard for (k) and is meant to pass on `main`. Every new `test_targets.py`
  case except that one goes red. The red is real.
- `tests/test_targets.py:122-160` — the `start` fixture drives the real `cli.main` and the real
  `targets.select` (the spy wraps it and returns its result unchanged). Only
  `Repl.interactive` is swapped for a scripted `Repl`, as the brief requires. No parallel copy of
  production logic. Assertions pin full stdout/stderr text as literals and also check the
  `Selection` fields directly (`:183-188`, `:240-245`, `:549-551`), so they can't pass for the
  wrong reason.
- `tests/conftest.py:57-61` sets `XDG_CONFIG_HOME` to a temp dir for every test, so the config
  tests can't read the developer's real `config.toml`.

## Fix — inputs I tried

- Path escape: `targets.py:129-137` checks the id against `[A-Za-z0-9][A-Za-z0-9._-]*` before
  building `root / id`, and rejects `.`/`..`. It also rejects a folder whose resolved path leaves
  the root. I probed a symlinked folder pointing outside the root: `load` refuses it. Empty,
  `../x`, `a/b`, `/x` and `x/../x` are all refused (tests `:379-420`).
- Exact match only by folder `<ID>-<VERSION_ID>` (`targets.py:244-260`): I first suspected this
  skipped targets whose folder had a different name. ADR-0023 (`docs/design/adr/0023-os-targets.md:37-38`)
  defines `<id>` as exactly `ID`-`VERSION_ID`, and the code also requires `target.toml`'s match
  fields to agree. No ID_LIKE or near-version path exists. Holds.
- os-release fallback (`os_release.py:91-104`): only `FileNotFoundError` moves on to
  `/usr/lib/os-release`. A directory, mode 000 or bad UTF-8 raises at once. A named target then
  starts not matching with `unknown unknown` (`targets.py:226-238`). Matches the brief's (g).
- Quoting: CRLF line endings, mixed `'ubu'"ntu"` concatenation and backslash escapes parse
  correctly (probe output `{'ID': 'ubuntu', 'VERSION_ID': '26.04'}`).
- `:status` leakage: `STATUS_LINES` is gone; lines live on the `Repl` instance (`repl.py:38-48`)
  and pass through `input_modes.reply` → `status` (`input_modes.py:93-94,138-151`). No module
  state is left to leak, and `test_status_lines_do_not_leak_between_runs` covers two runs in one
  process.
- OS names in code: `grep -rniE 'ubuntu|26\.04|dpkg|sudo-rs' src/ pyproject.toml` finds only the
  existing `sudo` pytest-marker text at `pyproject.toml:34`, which this diff didn't touch and which
  is not the `description` (j) checks.

## Small observations (no action needed)

- `cli.py:299-303` — `config.toml` is loaded even when `--target` is given, so an invalid
  `config.toml` refuses the start even if the flag names a valid target. The brief's (d) says
  invalid config is refused and doesn't exempt the flag case, and the error names the file, so
  the user can fix it. I'm noting it, not calling it a defect.
- `os_release.py:39` — an os-release line with an unquoted inline comment (`VERSION_ID=26.04 # x`)
  or a leading UTF-8 BOM drops that key, and the OS shows as `unknown`. Real os-release files
  don't contain either, and the outcome is fail-closed (refuse or mismatch), never a wrong match.

## Reviewer's verdict

I found no claim in `check-gates.json` that the evidence doesn't support. C4's "red without the
fix (61 of 91 failed), green with it" matches the log. T2 "no security-relevant path touched"
is plausible for a loader that only reads files, and the brief moves the allowlist and
target-folder integrity work to #139. T4 is deferred to publish and isn't a judgment here.

<!-- pdca:leaf-complete -->

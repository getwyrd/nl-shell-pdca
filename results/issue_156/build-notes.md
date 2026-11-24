# Build notes — issue_156 (ubuntu-command-not-found-provider, child-2 of #62)

Target: eduralph/nl-shell @ main. The worktree base is `5d3d291` (stack base
`pdca-integration/main-r2546dbf9639f`). Line numbers below are post-patch in that worktree,
unless marked "base".

## What changed

- `src/nl_shell/targets.py`
  - `:33` adds `COMMAND_PROVIDER_FORMATS = ("sqlite",)`.
  - `:65-77` adds the frozen `CommandProvider(format, path, query)` dataclass.
  - `:94-95` adds `Target.command_provider: CommandProvider | None = None`. It goes last
    and has a default, so existing `Target(...)` callers don't break.
  - `:214-233` validates `[command_provider]` in `_validate`, right after the
    `package_owner_query` check (base `:185-195`). It reuses `table()` (base `:163-169`)
    and `string()` (base `:155-161`), as the brief says, so not-a-table, missing key,
    non-string and empty string all raise the existing `TargetError` messages. It is
    optional: `table()` is only called when the key is present (`if "command_provider" in
    doc`), so a target without it gets `None` instead of the "missing required table"
    error. The extra checks are: format in `COMMAND_PROVIDER_FORMATS`, `Path(path).is_absolute()`,
    and `query.count("?") == 1`.
  - `:245` passes `command_provider=provider` into `Target`.
- `targets/ubuntu-26.04/target.toml`: `:13-20` header comment in the style of the `[sudo]`
  line; `:35-40` the table (`format = "sqlite"`, the path, and a JOIN query over
  `commands`/`packages`).
- `src/nl_shell/command_provider.py` (new): `provider_lookup` at `:43`. `None` or an unknown
  format returns a function that always gives `()`. Otherwise it checks `is_file()`, so a
  missing file is never created. It builds the URI with `Path.as_uri() + "?mode=ro"`
  (`:56`), connects with `uri=True, timeout=1.0`, runs the target's query with the word as
  a bound parameter (`:59`), and catches `sqlite3.Error`/`OSError`/`ValueError` and returns
  `()`. Names are filtered with `re.fullmatch` against `_PACKAGE_NAME` (`:29`; non-strings
  are dropped), then put in a set and sorted (`:62-63`). The module names no OS and no path
  (ADR-0023). `test_no_os_name_in_package_code` stays green.
- `.oss-scanner/threat_model.md:102-106`: a "Trusted" entry for the data file. It says why
  names are still filtered (they end up in text shown to the user).

## Prior art and how this differs

Started from `results/issue_62/iteration-v3/patch.diff`, which the brief cites. The
`targets.py` and `target.toml` hunks are nearly the same as that patch. Its `provider_lookup`
did not filter names, collapse duplicates or sort them; this one does all three, as the
brief requires. Results are sorted in Python rather than relying on the query's `ORDER BY`,
so the "sorted" contract holds whatever query a target ships. The test runs the query
both ascending and descending to check this.

## Ruled out

- Building `f"file:{path}?mode=ro"` by hand. The brief forbids it, and the mutation run
  below shows the test with `?`/`#`/`%` in the path catches it.
- Running `/usr/lib/command-not-found` or fetching anything. Out of scope (localised prose,
  ADR-0003).
- A public `Lookup` type of `Iterable[str]`. The contract here is the narrower
  `tuple[str, ...]` (brief "Ordering note").

## Tests and gates (project runner)

- C4 `engine/scripts/run-verify.sh`: `PDCA-EVIDENCE: C4 PASS — red without the fix (47 of 47
  failed), green with it`.
- T3 `engine/scripts/run-suite.sh`: `699 passed` (`PDCA-EVIDENCE: T3 PASS`), which includes
  `tests/test_targets.py::test_no_os_name_in_package_code`.
- The supplementary host test `test_real_lookup_finds_htop` **ran and passed** here, because
  `/var/lib/command-not-found/commands.db` exists on this host. Nothing was skipped.

## Self-refutation

- **(a) Genuine red?** Yes. C4's red leg reverts the production hunks: 47 of 47 failed
  (`ModuleNotFoundError` / missing `command_provider`), with no collection errors, because
  imports are inside the test functions. A second mutation run kept the module but swapped in
  the prior-art behaviour (no name filter, no dedup/sort, hand-built `file:` URI). The green
  leg then failed 10 tests: sorted, duplicates, URI characters, read-only URI, every bad-name
  case, and bad-next-to-good. After the mutation was restored it went back to green.
- **(b) Production path?** Yes. Every test calls the real `targets.load` and
  `command_provider.provider_lookup`, using the real `sqlite3`. The only monkeypatch
  (`test_read_only_mode_is_used`) wraps `sqlite3.connect` to record its arguments, and it
  still calls the real function.
- **(c) Fixture includes the fault?** Yes. The fixtures contain the bad inputs themselves: a
  missing file, a non-SQLite file, a wrong schema, a path containing `?#%`, bad names in the
  DB (`htop\n`, `HTOP`, `-htop`, int, bytes, NULL), duplicate `pkgID`s, and SQL-like words.
  The shipped target file is loaded from `targets/` directly, not copied.

## Commit-readiness

The target repo configures no formatter, linter or pre-commit hook: nothing in
`pyproject.toml`, no `.pre-commit-config.yaml`, and CI (`.github/workflows/tests.yml`) runs
only pytest. Neither `ruff` nor `black` is installed. I matched the repo's style by hand
(longest repo line is 99 characters; mine are at most 96).

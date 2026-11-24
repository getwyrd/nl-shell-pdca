## Summary
**User impact:** When you type a command that isn't installed, nl-shell can't yet tell
you which package would provide it, so the "command not found" help has nothing useful to
suggest. This PR adds the piece that answers "which package has this command?" from the
data already on your machine. Nothing shows up in the shell yet: hooking it into the
"command not found" message is a separate change.

The change: each OS target can now name a local database for this lookup, the Ubuntu
26.04 target names its command-not-found database, and a small read-only function looks
up a command word in it.

Reported in [#156](https://github.com/eduralph/nl-shell/issues/156).

## What to look at
- **The lookup** (new `src/nl_shell/command_provider.py`): give it a command word, get
  back a sorted tuple of package names, or `()` if there is no data. It never writes,
  never fetches anything and never creates the file.
- **The target config** (`targets/ubuntu-26.04/target.toml`): the new optional
  `[command_provider]` table holds the file path and query, so the package code names no
  OS and no path.
- **Try it** on an Ubuntu host that has `command-not-found` installed:

  ```python
  from pathlib import Path
  from nl_shell import targets
  from nl_shell.command_provider import provider_lookup

  t = targets.load("ubuntu-26.04", Path("targets"))
  provider_lookup(t.command_provider)("htop")   # -> ('htop',)
  ```

## Root cause
nl-shell had no way to ask the active target which package provides a command, and by
ADR-0023 the code itself may not hard-code an OS's file or table names. So the data source
has to be described in `target.toml` and read by OS-neutral code.

## Fix
- `src/nl_shell/targets.py`: adds a frozen `CommandProvider(format, path, query)`
  dataclass and an optional `Target.command_provider` (default `None`, placed last so
  existing `Target(...)` callers don't change). `_validate` checks the table right after
  `package_owner_query`, using the existing `table()` and `string()` helpers. On top of
  those it requires `format` to be `sqlite`, `path` to be absolute, and `query` to have
  exactly one `?`. A target without the table gets `None` instead of a
  "missing required table" error.
- `targets/ubuntu-26.04/target.toml`: adds the `[command_provider]` table
  (`/var/lib/command-not-found/commands.db`, a JOIN over `commands` and `packages`) and a
  header comment in the style of the `[sudo]` one.
- `src/nl_shell/command_provider.py` (new): `provider_lookup(provider)` returns a function
  `str -> tuple[str, ...]`. It builds the URI with `Path(path).as_uri() + "?mode=ro"` so
  `?`, `#` and `%` in the path are percent-encoded, connects with `uri=True` and a 1-second
  timeout, and passes the word as a bound parameter. `sqlite3.Error`, `OSError` and
  `ValueError` give `()`. It keeps only names that fully match the Debian package-name rule
  (`re.fullmatch(r"[a-z0-9][a-z0-9+.-]+", ...)`, Debian Policy §5.6.1), then removes
  duplicates and sorts in Python, so the result is sorted whatever order the query uses.
- `.oss-scanner/threat_model.md`: lists the database as trusted input (root-owned,
  package-managed, read-only). It also says why names are still filtered: they end up in
  text shown to the user.

**Known gap for the caller:** an empty word is not refused here. On a real Ubuntu database
`""` returns `('mailutils-mh', 'nmh')`. The first caller (or a later change to this lookup)
should skip the lookup for an empty word.

## Verification
- **Claim:** a target with a valid `[command_provider]` exposes it, a target without one
  gets `None`, and bad tables are refused with `TargetError`.
  - **Checked:** `src/nl_shell/targets.py:155-169` on `main` (`string()` already rejects
    empty and non-string values, `table()` rejects non-tables). The new check goes right
    after `:185-195` (`package_owner_query`), and `:196` is where `Target(...)` gets the new
    field.
  - **Test:** `tests/test_command_provider.py`: `test_valid_provider_loads`,
    `test_target_without_provider_has_none`, `test_invalid_provider_is_refused` (12 cases:
    unknown format, relative path, zero or two `?`, each missing key, non-string values,
    empty strings), `test_provider_that_is_not_a_table_is_refused`.
- **Claim:** the shipped Ubuntu 26.04 target names the command-not-found database.
  - **Checked:** `targets/ubuntu-26.04/target.toml:11-12` and `:23-25` on `main` (the
    `[sudo]` comment and table this follows).
  - **Test:** `test_shipped_target_has_sqlite_provider`.
- **Claim:** the lookup is read-only, local, and safe with odd input.
  - **Test:** `test_read_only_mode_is_used` (the URI ends `?mode=ro`, with `uri=True`),
    `test_lookups_leave_the_file_unchanged` (same bytes, no extra files),
    `test_missing_file_gives_nothing_and_is_not_created`,
    `test_path_with_uri_characters` (a directory named `a?b#c%41d`),
    `test_word_is_a_bound_parameter` (`'`, `;`, `%` in the word),
    `test_not_sqlite_gives_nothing`, `test_schema_without_tables_gives_nothing`,
    `test_no_provider_finds_nothing`.
- **Claim:** results are sorted, without duplicates, and only valid package names.
  - **Test:** `test_two_packages_come_back_sorted` (runs the query ascending and
    descending), `test_duplicate_names_collapse`, `test_bad_names_are_dropped` (`HTOP`,
    `htop; rm -rf ~`, `htop\nevil`, `htop\n`, `-htop`, int, bytes, NULL),
    `test_good_names_are_kept` (`libc6`, `g++`, `python3.12`),
    `test_bad_name_does_not_hide_good_one`.
- **Claim:** the package code names no OS and no path (ADR-0023).
  - **Test:** `test_module_names_no_os_or_path`, plus the existing
    `tests/test_targets.py::test_no_os_name_in_package_code`, which stays green.
- **Red / green:** with the production changes reverted, all 47 tests in
  `tests/test_command_provider.py` fail (the imports are inside the tests, so the file still
  loads). With them, all pass. A second run put back the older version's behaviour (no
  name filter, no dedup or sort, a hand-built `file:` URI) and 10 tests caught it. The
  full suite passes (699 tests).
- **Real data:** `test_real_lookup_finds_htop` runs the shipped target against the host's
  `/var/lib/command-not-found/commands.db`. It ran and passed here. It is skipped on hosts
  without that file, and it is the only test that can skip.

Fixes #156

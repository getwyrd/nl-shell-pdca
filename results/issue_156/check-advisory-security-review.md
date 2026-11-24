# Advisory security review — ubuntu-command-not-found-provider (issue_156)

**Attacker-reachable inputs this diff touches:** one, later — the command word passed to the lookup (`word` in `provider_lookup`'s returned function). Nothing calls it yet (wiring is out of scope), but its eventual callers will pass a word taken from a model proposal or a command that failed, which the threat model treats as untrusted (entries 1, 2, 5). The other inputs are trusted: `target.toml` ships with the repo, and the patch adds the SQLite file to the threat model's Trusted list.

Rubric: `.oss-scanner/threat_model.md` (read). `AGENTS.md` read; it lists no settled deferrals that apply here.

## Findings

No finding. Here is what I checked:

- **SQL injection through the word.** `src/nl_shell/command_provider.py:59` passes `word` only as a bound `?` parameter, and the SQL text comes only from `target.toml`. The loader requires exactly one `?` (`src/nl_shell/targets.py:228`). Tests at `tests/test_command_provider.py` (`test_word_is_a_bound_parameter`, `test_lookups_leave_the_file_unchanged`) use `'`, `;`, `%` and `'; DROP TABLE commands; --`. Covered.
- **Odd words crashing the lookup (a panic reachable from untrusted input).** I tested this here with Python's `sqlite3`. A lone surrogate (`"\udcff"`, which is how a non-UTF-8 file name decodes) raises `UnicodeEncodeError`. That is a `ValueError` subclass, so `command_provider.py:60` catches it and returns `()`. An embedded NUL (`"ht\x00op"`) and a 10 MB word both return `[]`, with no error and no hang. The patch's tests don't include these two inputs, but the code handles them. This is too small to report as a test gap.
- **Writes or file creation.** `is_file()` is checked first (`command_provider.py:52`), and the file is opened through `Path.as_uri() + "?mode=ro"` (`:56`), which percent-encodes `?`, `#` and `%`, so a path can't add URI parameters. Tests check that the bytes don't change, that no extra file appears, that a missing file is not created, and that a path with `?#%` still works. Covered.
- **Hostile package names reaching user-facing text.** `command_provider.py:36` uses `re.fullmatch` with `[a-z0-9][a-z0-9+.-]+`, so newlines (including a trailing `\n`), spaces, `;`, uppercase, a leading `-`, non-strings and control or bidi characters are all dropped (`:62`). Tests cover `htop\n`, `htop\nevil`, `htop; rm -rf ~`, `-htop`, int, bytes and NULL. The data is trusted anyway, so this is extra protection.
- **Resource use.** The lookup waits at most 1 s on a locked database (`_TIMEOUT`, `command_provider.py:31`). The result is bounded by what the root-owned file holds, and the count cap is #155's job. No finding.
- **Trust boundary.** The patch adds the command-not-found database to the Trusted list (`.oss-scanner/threat_model.md:102`). The brief explicitly asked for this, so it was decided at Plan. The claim holds: the file is root-owned, rebuilt by apt from signed index files, opened read-only, and a text-only attacker can't write to it. The name filter is kept anyway. I'm not raising this as a new finding; the human confirms it at sign-off along with the rest.
- **No network (ADR-0003, "Locally complete").** The module only opens a local file and never runs `/usr/lib/command-not-found`. No finding.

Gate evidence: C4-verify passes (47 of 47 tests fail without the fix, all pass with it), and T3-suite passes (699 passed, `gate-logs/T3-suite.log`).

No NEEDS-HUMAN items from this review.

<!-- pdca:leaf-complete -->

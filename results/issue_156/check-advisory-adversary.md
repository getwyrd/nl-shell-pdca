# Adversarial review — ubuntu-command-not-found-provider (issue_156)

I tried to break the evidence, the fix and the verdict. I could not refute the fix. Two small edge cases are below. Neither breaks the brief's criterion.

## Evidence

- **Red→green holds, and it runs real code.** `gate-logs/C4-verify.log` shows 47 run, 47 failed on the reverted tree, and every failure is the expected `ModuleNotFoundError`/`ImportError` from the in-function imports (not a collection error). That includes `test_real_lookup_finds_htop`, so it ran on the gate host rather than being skipped. The tests call the real `provider_lookup` and `targets.load`; none of them mirror production code. `test_read_only_mode_is_used` checks the exact URI (`db.as_uri() + "?mode=ro"`, `uri=True`), so the `mode=ro` claim is pinned down, not just inferred from unchanged bytes. T3 shows 699 passed on Python 3.14 (`gate-logs/T3-suite.log`). I could not re-run pytest myself because pytest is not installed in this sandbox. Instead I drove the module directly with `python3 -I`, and every result matched the tests.
- **Production path against the host's real data.** I loaded the shipped `targets/ubuntu-26.04/target.toml` and queried the real `/var/lib/command-not-found/commands.db`. `htop` → `('htop',)`. `vi` → 12 names, sorted. `ls` → the four `coreutils-from-*` names. `HTOP` and `%` → `()`. The real schema (`commands(cmdID, pkgID, command)`, `packages(pkgID, name, …)`) fits the shipped query. Its journal mode is `delete`, so the read-only open needs no `-wal`/`-shm` side files.

## Attempts on the fix

- **NEEDS-HUMAN [impl] — An empty word returns packages.** `src/nl_shell/command_provider.py:48` sends `word` straight to the query. The real host database has rows whose `command` is `''`, so `lookup("")` returns `('mailutils-mh', 'nmh')` (I reproduced this against the shipped target). A caller that passes an empty or whitespace-trimmed-to-empty word, for example a blank line reaching the "command not found" path, would get a made-up suggestion. The brief does not list this case, so it is not a criterion failure. The fix is one line (`if not word: return ()`) plus one test row.
- **The `?` count check is a heuristic, not a parameter count.** `src/nl_shell/targets.py:228` counts `?` characters in the text. A query like `SELECT name FROM packages WHERE name = :w -- ?` passes the loader, then every lookup silently returns `()`. I confirmed that `sqlite3.ProgrammingError` is caught at `command_provider.py:60`. A valid query with a `?` inside a string literal would be wrongly refused. `target.toml` is repo-owned, trusted data, and the brief asked for exactly this check ("zero or two `?`"), so I am not escalating it. A misconfigured target fails silently rather than loudly, though.
- **Attempts that did not break it:**
  - Write or multi-statement queries: `mode=ro` blocks writes, and Python 3.12+ (`requires-python >= 3.12`) raises `ProgrammingError`, which is caught. Note: `sqlite3.Warning` is not caught, but it only applies before 3.12.
  - A file that disappears between the `is_file()` check and the connect: `mode=ro` never creates a file.
  - A relative path built directly in `CommandProvider`: `as_uri()` raises `ValueError`, which is caught.
  - A WAL-mode database in a read-only directory: returns `()`, no crash.
  - Non-str words (`None`, `b"htop"`, `1`): all return `()`.
  - Non-ASCII names: Python's `[a-z]` range is ASCII-only.
  - A directory or FIFO at the path: `is_file()` is false.

## Verdict and gates

- **The T2 row text is wrong, but the conclusion is still fine.** `check-gates.json` T2 says "no security-relevant path touched", yet the patch does update `.oss-scanner/threat_model.md` with the new trusted input. The row is non-gating and the threat-model entry is present, so this is a gate-heuristic gap, not a patch defect. No action needed for this diff.
- I found no claim in the brief or the gate rows that this evidence fails to support.

## Process note

While trying the revert, I ran `git stash` / `git stash pop` inside `$PDCA_TARGET`. This only touched tracked files, and the pop restored them: `git status` and `git diff --stat` match the patch afterwards. I mention it because the target is supposed to be read-only for this leaf.

<!-- pdca:leaf-complete -->

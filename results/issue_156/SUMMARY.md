# Result — issue 156 / ubuntu-command-not-found-provider

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: 
- Success criterion: `python3 -m pytest tests/test_command_provider.py` passes on main AND the full suite `python3 -m pytest` stays green (in particular `tests/test_targets.py::test_no_os_name_in_package_code`, which fails on `ubuntu` or `26.04` in any case anywhere under `src/nl_shell/`, so no docstring or comment in `targets.py` / `command_provider.py` may name the OS). The new file covers, each as its own assertion:
  - loader: a `target.toml` with a valid `[command_provider]` loads and exposes it on `Target.command_provider`; a target without the table loads with `command_provider is None`; each of these raises `TargetError`: unknown `format`, relative `path`, `query` with zero or two `?`, a missing key, a non-string value, an empty string, `[command_provider]` that is not a table.
  - the shipped `targets/ubuntu-26.04/target.toml` loads and its provider is `format = "sqlite"`, `path = "/var/lib/command-not-found/commands.db"`.
  - reader, against a SQLite file the test builds in `tmp_path` with the same two tables: `htop` → `("htop",)`; a word with two packages → both, sorted; the same package `name` under two `pkgID`s → that name once (duplicates collapsed); a database in a `tmp_path` subdirectory whose name contains `?`, `#` and `%` → still finds `htop` (the path is percent-encoded into the URI); an unknown word → `()`; a missing file → `()` and the file is NOT created; a file that is not SQLite, or a schema without the tables → `()`; the database file's bytes are unchanged after lookups (opened with `mode=ro`); a word containing `'`, `;` or `%` is passed as a bound parameter and returns `()` (no SQL built by string formatting); `provider_lookup(None)` returns a function that always gives `()`.
  - name rule, whole-string (`re.fullmatch(r"[a-z0-9][a-z0-9+.-]+", name)`): `HTOP`, `htop; rm -rf ~`, `htop\nevil`, `htop\n` (the case a `$` anchor would wrongly accept), `-htop`, and a non-string value from the database are each dropped; `libc6`, `g++`, `python3.12` are kept.
  - `src/nl_shell/command_provider.py`'s source text contains none of `ubuntu`, `/var/`, `commands.db` (the path and query come from `target.toml`).
  - supplementary: the real `targets/ubuntu-26.04` lookup returns a tuple containing `htop` for `htop` when `/var/lib/command-not-found/commands.db` exists on the host; skipped otherwise. This is the only test that may skip.
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: 

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (47 of 47 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — no security-relevant path touched
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review the optional target-configured, local SQLite command-to-package provider for the command-not-found feature.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The contract is falsifiable and scoped to a data provider, with caller wiring explicitly excluded; loader compatibility and failure behavior are specified (brief.md:8, brief.md:21). |
| C2 Reproduction (red pre-fix) | N/A | This is new functionality rather than an existing symptom; pre-fix falsification belongs to C4 (brief.md:19). |
| C3 Change | PASS | All five affected paths serve the specified provider contract; optional configuration preserves existing targets and introduces no caller integration (src/nl_shell/targets.py:214, src/nl_shell/command_provider.py:43). |
| C4 Verification (red→green) | PASS | Frozen evidence records 47 executed failures without production changes and 47 passes with them; independent stash/restore attempts could not execute pytest because it is absent locally, so this verdict rests on the captured gate output (gate-logs/C4-verify.log:11, gate-logs/C4-verify.log:1144). |
| C5 Causal adequacy | PASS | Lazy lookup supplies the missing capability directly; absence handling is part of the optional-data contract, with no eager capability side effect being masked; independent real-host lookup returned ('htop',) (src/nl_shell/command_provider.py:48, targets/ubuntu-26.04/target.toml:35). |
| T1 Structure | PASS | Immutable provider configuration stays with target loading, while database access is isolated behind the requested callable contract (src/nl_shell/targets.py:65, src/nl_shell/command_provider.py:25). |
| T2 Shape | PASS | Read-only URI access, bound input, full-string name filtering and explicit connection closure protect the stated trust boundary; the threat model documents it, although the frozen scanner only reports no matching security-sensitive path (src/nl_shell/command_provider.py:34, src/nl_shell/command_provider.py:56, .oss-scanner/threat_model.md:102; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen full-suite output shows 699 passes and one forkpty warning; local pytest is unavailable, but independent stdlib smoke checks passed for shipped loading/query, URI escaping, deduplication, rejected newline names, bound input, unchanged bytes and the real host database (gate-logs/T3-suite.log:27; src/nl_shell/command_provider.py:56). |
| T4 Contribution | N/A | Contribution artifacts are absent by design; the substantive contribution audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm merged-history and closed/rejected-work prior art by all five affected file paths before sign-off — this self-contained target has only one synthetic base commit, no supplied prior-art audit, and the brief explicitly leaves the #62 split/prior-art records for human reconfirmation (brief.md:21, brief.md:32). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether this provider-only increment satisfies the intended #62 split and may proceed to later caller wiring — automated checks and a successful real-host lookup establish lookup behavior, while user-facing command-not-found usefulness remains outside this patch (brief.md:18, brief.md:21). |

Evidence notes: Source citations above were checked against the patched target at `$PDCA_TARGET`; it is readable and matches the reviewed changes. The patch was restored after the independent red attempt. Both local pytest attempts stopped at `No module named pytest`, which is a reviewer-host limitation, not a patch defect. The frozen wrappers are instance-scoped; their full logs were read rather than treating their absence here as a defect. No undischarged binding external dependency was found: the real host database was present and independently returned `htop`. No INTEGRATION.md or closed/rejected-work record was supplied in the target. `git diff --check` passed. The C5 capability-guard smell does not apply to handling explicitly optional provider data.

<!-- pdca:leaf-complete -->

### Advisory — adversary

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

### Advisory — security-review

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

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] T5 Judgment — Confirm merged-history and closed/rejected-work prior art by all five affected file paths before sign-off — this self-contained target has only one synthetic base commit, no supplied prior-art audit, and the brief explicitly leaves the #62 split/prior-art records for human reconfirmation (brief.md:21, brief.md:32).
- [x] Validation — fitness-to-purpose — Decide whether this provider-only increment satisfies the intended #62 split and may proceed to later caller wiring — automated checks and a successful real-host lookup establish lookup behavior, while user-facing command-not-found usefulness remains outside this patch (brief.md:18, brief.md:21).
- [x] **The tracker record is missing, so the root cause and the context can't be checked.** The sandbox holds only `brief.md` (and `.claude/`). There is no `notes.json`, no `sources/` and no `dependency-state.json`. I could not check the brief against the #62 thread, the split decision, the "#92 merged (PR #142)" claim or the "#155 independent" claim. I also could not look for a maintainer constraint or a failed earlier attempt. The prior art the brief cites (`results/issue_62/iteration-v3/patch.diff`) is not in the bundle or the target either. A human should confirm that the split and the prior-art pointer match the thread.
- [x] **The binding gate runs only the new test file, but the change can break an existing test that is stricter than the brief's own check.** `tests/test_targets.py:650-662` (`test_no_os_name_in_package_code`) fails on any line in `src/nl_shell/**/*.py` that matches `ubuntu|26\.04` with `re.IGNORECASE`. The brief's check (line 14) only bans lowercase `ubuntu`, `/var/` and `commands.db`, and only in `command_provider.py`. So a docstring saying "Ubuntu's command-not-found", or a comment in `targets.py` naming the 26.04 file, passes `pytest tests/test_command_provider.py` but turns the existing suite red. Fix: make the criterion "the full suite passes, plus the new file", and point to the existing test instead of writing a weaker copy of it.
- [x] **Building the URI from `path` is under-specified, and the "relative path" check doesn't cover it.** The brief says to open `file:…?mode=ro` with `uri=True` (line 21), and the loader only rejects a relative `path` (line 10). If `path` (or a pytest `tmp_path`) contains `?`, `#` or `%`, a plain `f"file:{path}?mode=ro"` breaks or opens a different file. Fix: require percent-encoding (for example `Path(path).as_uri() + "?mode=ro"`, or `urllib.parse.quote`) and add one reader assertion with a database path that contains such a character. As written, the `mode=ro` / "file not created" rows can pass while the URI handling is still wrong.
- [x] **The duplicates contract is missing.** Line 12 asks for "a word with two packages → both, sorted", but says nothing about the same package name coming back more than once. In the real command-not-found database one name can appear in several rows (several `pkgID`s for one name, for example per component), so a plain JOIN can return `("htop", "htop")`. The supplementary test (line 15) only checks "contains `htop`", so it won't catch this. Fix: add "duplicate names are collapsed" as its own assertion (two `pkgID`s with the same `name` → one entry).
- [x] **The interface is stated two different ways.** Line 8 promises `provider_lookup(provider) -> Callable[[str], tuple[str, ...]]`. The Ordering note (line 18) says the interface shared with #155 is `Callable[[str], Iterable[str]]`. If #155 is written against `Iterable` and this child returns a tuple, that works. But the brief should pick one contract so the sign-off reviewer knows which signature to check against.
- [x] **"Mirror `package_owner_query`" doesn't fit an optional table.** In `src/nl_shell/targets.py:185-195`, `package_owner_query` is a required top-level list. The `table()` helper at `targets.py:163-169` raises "missing required table" when the table is absent. An optional `[command_provider]` table needs its own absent → `None` path, and `string()` (`targets.py:155-161`) also rejects empty strings, which the brief doesn't list among the `TargetError` cases (line 10). This is minor, but the citation the brief asks for will mislead Do. It should say "validate like `[sudo]` / `string()`, but optional".

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: merged-wider
- Iteration delta (if iterating):
- By / date: Eduard Ralph / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 6 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)
- command_provider: guard empty word (real DB returns mailutils-mh, nmh for '') — in the lookup or at its first caller.

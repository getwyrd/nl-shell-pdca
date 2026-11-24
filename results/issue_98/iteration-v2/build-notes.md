# Build notes — issue 98, docs-checks-internal-links (iteration 2)

Target: eduralph/nl-shell, built on the wave's integration branch
`pdca-integration/main-r31e6545f56bb` @ `a972610` (main + #97's folded patch). Line refs
are in the patched worktree.

## What this iteration changes

I started from the iteration-1 patch (`iteration-v1/patch.diff`), applied unchanged, and
fixed the two gaps the sign-off carry-forward named. Everything else (the rule, the
workflow step, the other tests) is as iteration 1 left it; see `iteration-v1/build-notes.md`
for those choices.

### 1. Tests that a fenced block closes

Four new must-fail entries in `MUST_FAIL` (`tests/test_docs_links.py:84-99`). Each has a
fence that holds a valid link, closes it, and then has a broken link after it. Each must
exit 1 and name `docs/page.md:` and the broken dest:

- plain backtick fence: ```` ```\n[a](guide.md)\n```\n[y](after-fence.md) ```` (the exact
  example from the carry-forward);
- tilde fence;
- fence opened and closed on a list-marker line (`- ```` … `  ````);
- fence opened and closed inside a `>` block quote.

The last two prove the closing line is stripped the same way as the opening line
(`fence_view`, `scripts/docs_links.py:83`, used at `:104`).

### 2. `parse_dest` requires `)` or a title opener

`scripts/docs_links.py:205-236`. After the destination ends, the parser skips whitespace
and then requires the next character to be `)` or a title opener (`"`, `'`, `(`). If not,
it returns `""`, so the text is not a link (`:234`). The old check (`if i >= n`) only
rejected a destination that ran to the end of the paragraph. That is why
`See [x](missing.md for more.` was reported as broken.

- New must-pass `no closing paren (prose)` (`tests/test_docs_links.py:133`).
- New must-pass `valid file with a title` (`:134`) for `[g](guide.md "The guide")` and
  `[s](guide.md (Setup))`, so titles still work as the carry-forward asked.
- New must-fail `with a title` (`:82`): `[g](title-missing.md "The guide")` is still
  checked. Without it, a fix that dropped titled links entirely would pass.
- I updated the docstring (`:21-24`, `:34-35`) to say what the parser now does with titles.
  Titles are recognized by their opening character only, never parsed. That stays a known
  gap, in line with decision 5.

Ruled out: matching the title to its closing quote and then requiring `)`. The
carry-forward asks only for "`)` (or the start of a title)". Full title parsing is
CommonMark work that the brief puts out of scope. It would add about 15 lines for quote and
paren matching, and no live doc uses titles.

## Evidence

- C4 through the project runner (`engine/scripts/run-verify.sh` with `PDCA_BUNDLE`,
  `PDCA_WORKTREE`, `PDCA_VERIFY_BASE=pdca-integration/main-r31e6545f56bb`) on the final
  `patch.diff`: `PDCA-EVIDENCE: C4 PASS — red without the fix (32 of 32 failed), green with
  it`.
- Whole suite (`engine/scripts/run-suite.sh`): `138 passed`, `T3 PASS`.
- Live tree: `python3 -I scripts/docs_links.py` →
  `60 relative links in 53 Markdown files, 0 broken`, exit 0. That matches the brief's count.
- The workflow step was checked only by reading it (`.github/workflows/docs-checks.yml:45-48`).
  Per the brief, the draft PR's CI run is what exercises it.

## Refuting my own test

- **(a) Genuine red? Yes.** C4 reverted `scripts/docs_links.py` and all 32 tests failed on
  assertions, not on collection. Because a missing script would also turn every test red,
  I ran three targeted mutations through `run-suite.sh`, each restored from a saved copy
  (`cmp` confirmed the restore):
  1. The fence close branch turned into a no-op (`:105` → `if False:`), which is the
     carry-forward's exact complaint. Result: the 4 new "after a closed … fence" tests failed
     (`4 failed, 134 passed`).
  2. The closing line matched raw instead of through `fence_view` (`:104` `view` → `line`).
     Result: the list-marker and block-quote close tests failed (`2 failed, 136 passed`).
  3. `parse_dest` put back to the old end check (`:234` → `if end >= n:`). Result:
     `no closing paren (prose)` failed (`1 failed, 137 passed`).
- **(b) Production path? Yes.** Every test runs the real `scripts/docs_links.py` as a
  subprocess (`sys.executable` + a path built from `__file__`), the same entry point CI
  uses. Nothing is copied or mocked.
- **(c) Fixture includes the fault? Yes.** Each must-fail fixture is a real git repo with a
  committed `.md` file whose link target is untracked. The live test runs on the real
  nl-shell checkout, a git worktree where `.git` is a file.

## Commit-readiness

nl-shell has no `.pre-commit-config.yaml`, and `pyproject.toml` has no ruff, black or flake8
config. No ruff, pyflakes or black is installed. So there was nothing to run. Every line is
at most 92 columns (checked with `awk`). No new imports were added.

## Housekeeping (my mistakes)

- I left `scripts/docs_links.py.orig` in the worktree. It is untracked, it is not in
  `patch.diff`, and it is the backup copy from the mutation runs. I did not delete it,
  per the no-cleanup rule. The harness reclaims the worktree.
- One command wrote a stray `git diff` output to `/tmp/x`, which is outside the harness
  roots. It holds only a copy of this diff. I did not delete it.

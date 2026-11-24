# Build notes — issue 98, docs-checks-internal-links (iteration 4)

Target: eduralph/nl-shell, built on the wave's integration branch
`pdca-integration/main-r31e6545f56bb` (tip `a972610`, which holds #97's folded patch, so
`.github/workflows/docs-checks.yml` and its freeze step exist). Line numbers are in the
patched worktree (`$PDCA_WORKTREE` = `/home/eddie/nl-shell/nl-shell.pdca-wt`).

## What this iteration changes

Iteration 3's sign-off said: keep `scripts/docs_links.py`, the workflow step and decision 5's
rule exactly as they are, and only add the three missing tests. So I applied
`iteration-v3/patch.diff` unchanged and added three parametrize entries to
`tests/test_docs_links.py`. `diff iteration-v3/patch.diff patch.diff` shows only those
test lines (plus the test file's blob hash and hunk length); the workflow and script hunks
are byte-identical.

| Carry-forward item | Test (`tests/test_docs_links.py`) | Rule clause it binds (`scripts/docs_links.py`) |
|---|---|---|
| 1. fence in a `>` quote, closed by a longer run | must-pass `fence in a block quote closed by a longer run` (:159): `"> ```\n> [x](missing.md)\n> ````\n"` | `:87` `QUOTE_MARKERS_RE.sub` in `fence_view` |
| 2. a longer run closes a fence | must-fail `after a longer closing run` (:114-117; comment :113), names `after-longer.md` | `:107` `len(run.group(0)) >= len(fence)` |
| 3. badge / nested link | must-fail `image inside a link (badge)` (:119), names `missing.png` | `:185` `i += 1` rescan in `inline_links` |

Item 1 uses a closing run of 4 backticks against an opener of 3, so step 3 (inline code,
exact-length pairing) cannot pair the two runs and hide the link by accident; only the fence
rule hides it.

## Each new test goes red when its clause is removed

Ran with the venv Python the C4 runner uses (`engine/scripts/run-verify.sh:125`), restoring
the script after each mutation:

| Mutation | Result |
|---|---|
| `:87` → `rest = line.lstrip()` (no `>` stripping) | 1 failed, 41 passed: only `fence in a block quote closed by a longer run` |
| `:107` `>=` → `==` | 1 failed, 41 passed: only `after a longer closing run` |
| after `:184` add `i = close + 1; continue` (skip past the outer link) | 1 failed, 41 passed: only `image inside a link (badge)` |
| none | 42 passed |

In each case exactly the new test caught the mutation, so these clauses were not covered
before this iteration.

## C4 run (project runner)

`PDCA_BUNDLE=… PDCA_WORKTREE=… ./engine/scripts/run-verify.sh` →
`PDCA-EVIDENCE: C4 PASS — red without the fix (42 of 42 failed), green with it`, exit 0.

## Refute-the-test answers

- **(a) Genuine red?** Yes. run-verify.sh reverts `scripts/docs_links.py` (outside the
  non-behavioral paths) and all 42 tests fail; with it applied all 42 pass. The three
  mutations above each turn the matching new test red.
- **(b) Production path?** Yes. Every test runs the real `scripts/docs_links.py` as a
  subprocess (`tests/test_docs_links.py:49-57`), against a real git repo; nothing is mocked
  or copied.
- **(c) Fixture includes the fault?** Yes. Each must-fail fixture commits a doc with the
  broken link and asserts the file and the link are named; the must-pass fixtures contain a
  real broken target (`missing.md`) that only the rule under test hides.

## Commit-readiness

nl-shell has no `.pre-commit-config.yaml` and no formatter config, and `ruff` is not
installed here. The new lines follow the file's existing style and stay under 100 columns.

## Not changed

The script, the workflow step, the rule, and the known-gaps docstring, as the sign-off asked.

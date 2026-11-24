# Build notes — issue 98, docs-checks-internal-links (iteration 3)

Target: eduralph/nl-shell, built on the wave's integration branch
`pdca-integration/main-r31e6545f56bb` (tip `a972610`, which holds #97's folded patch, so
`.github/workflows/docs-checks.yml` and its freeze step exist). Line numbers below are in
the patched worktree.

## What this iteration changes

Iteration 2's sign-off said: keep the patch and decision 5's rule as is, and only add the
tests that were missing, each of which must go red if its rule clause is removed. So I
started from `iteration-v2/patch.diff` unchanged and added:

| Carry-forward item | Test (`tests/test_docs_links.py`) | Rule clause it binds (`scripts/docs_links.py`) |
|---|---|---|
| 1. close needs a run at least as long | must-pass `shorter inner run does not close a fence` (:148) and must-fail companion `after a longer fence closes past a shorter inner run` (:101) | `:107` `len(run.group(0)) >= len(fence)` |
| 2. close needs the same character | must-pass `other fence character does not close a fence` (:149) | `:106` `re.escape(fence[0]) + "+"` |
| 3. escaped backtick does not open a span | must-fail `after an escaped backtick` (:106), names `esc-missing.md` | `:126` the backslash branch in `strip_inline_code` |
| 4. inline code stays in one paragraph | must-fail `backtick run does not span paragraphs` (:108), names `para-missing.md` | `:261` paragraph split in `find_links` |
| 5. escapes in dest are undone | `test_backslash_escapes_in_dest_are_undone` (:161): `[g](gu\_ide.md)` with tracked `docs/gu_ide.md` passes, and exactly 1 link was checked | `:275` `ESCAPE_RE.sub` in `target_of` |
| 6. ref definition after `>` markers | must-fail `reference definition after quote marker` (:112), names `missing.md` | `:58` `(?:>\s*)*` in `REFDEF_RE` |

Root-absolute links: no change to resolution, per the sign-off. Added to the known-gaps list
in the docstring (`scripts/docs_links.py:37-38`).

Item 5's test also asserts `1 relative links`, so it cannot pass by checking no links at
all (for example if the link were silently dropped).

No production logic changed. The only change to `scripts/docs_links.py` is the two docstring
lines.

## Evidence

- C4 through the project runner (`engine/scripts/run-verify.sh` with `PDCA_BUNDLE`,
  `PDCA_WORKTREE`, `PDCA_VERIFY_BASE=pdca-integration/main-r31e6545f56bb`) on the final
  `patch.diff`: `PDCA-EVIDENCE: C4 PASS — red without the fix (39 of 39 failed), green with
  it`. 0 collection errors.
- Whole suite (`engine/scripts/run-suite.sh`): `145 passed`, `T3 PASS`.
- Live tree: `python3 -I scripts/docs_links.py` →
  `60 relative links in 53 Markdown files, 0 broken`, exit 0. Matches the brief's count.
- Workflow step (`.github/workflows/docs-checks.yml:45-48`, unchanged from iteration 2) was
  checked by reading it only. Per the brief, the draft PR's CI run exercises it.

## Refuting my own test

- **(a) Genuine red? Yes.** C4 reverted `scripts/docs_links.py`: 39 of 39 failed on
  assertions. A missing script turns everything red, so I also ran one mutation per
  carry-forward item through `run-suite.sh`, restoring from a backup copy each time
  (`cmp` confirmed the final restore):
  1. `:107` `>= len(fence)` → `>= 0`: both item-1 tests failed (`2 failed, 143 passed`).
  2. `:106` close on any of `` ` `` or `~`: item-2 test failed (`1 failed, 144 passed`).
  3. `:126` backslash branch → `if False:`: item-3 test failed (`1 failed, 144 passed`).
  4. `:261` `if line.strip():` → `if True:` (whole file is one paragraph): item-4 test
     failed (`1 failed, 144 passed`).
  5. `:275` drop `ESCAPE_RE.sub`: item-5 test failed (`1 failed, 144 passed`).
  6. `:58` drop `(?:>\s*)*` from `REFDEF_RE`: item-6 test failed (`1 failed, 144 passed`).
  In each run only the targeted test failed, so each test binds its own clause.
- **(b) Production path? Yes.** Every test runs the real `scripts/docs_links.py` as a
  subprocess (`sys.executable` + a path built from `__file__`), the same entry point CI
  uses. Nothing is copied or mocked.
- **(c) Fixture includes the fault? Yes.** Each must-fail fixture is a real git repo with a
  committed `.md` file whose link target is untracked. Item 5's fixture really tracks
  `docs/gu_ide.md`. The live test runs on the real nl-shell checkout, a git worktree where
  `.git` is a file.

## Commit-readiness

nl-shell has no `.pre-commit-config.yaml`, and `pyproject.toml` configures no ruff, black or
flake8, so there is no formatter to run. Every line is at most 92 columns (checked with
`awk`; one new assert was split to meet that). No new imports.

## Housekeeping

`scripts/docs_links.py.bak` is left in the worktree: it is the backup used to restore after
each mutation, identical to the patched file, untracked and not in `patch.diff`. I did not
delete it, per the no-cleanup rule.

# Adversarial review — docs-checks-adr-immutability (iteration 3)

Result: I tried to refute the fix and could not. Nothing below needs a rebuild or a human decision.

## What I tried

- **The red→green evidence is real, but C4's red does not prove what this iteration changed.** C4 (`gate-logs/C4-verify.log`) went red 71/71 only because `scripts/docs_checks.py` was removed. C4 never reverts `.github/`, so it never tested a workflow without `-I`. I tested that by hand. In a copy of the target I took `-I` out of `.github/workflows/docs-checks.yml:39` and `:42` and re-ran the CI-step tests. `test_ci_step_ignores_a_stdlib_module_planted_by_the_pr` (`tests/test_docs_checks.py:621`) and `test_ci_step_fallback_ignores_a_module_planted_next_to_the_script` (`tests/test_docs_checks.py:640`) both went red: exit 0 with `docs-immutability: OK`, so the planted `re.py` took over. With `-I` back, all 71 tests pass on `$PDCA_TARGET`. The new tests run the real `run:` block taken from the workflow file (`tests/test_docs_checks.py:566-597`), not a copy of it. So they would catch someone dropping `-I` later.
- **Other ways a PR could change what the base script runs, under `-I`.** I put `sitecustomize.py` and `usercustomize.py` in the cwd and piped a script to `python -I -`. Neither ran, and `sys.path` had no `''` entry. With plain `python -`, `''` was first on the path. The script's `git` calls (`scripts/docs_checks.py:150-166`) use `cat-file blob` and `diff --name-status`. Neither applies `.gitattributes` filters or textconv (text conversion for diffs), and git config comes from `.git/config`, which a PR cannot change. So a PR-added `.gitattributes` cannot hide a change. I found no bypass.
- **Ways to change a frozen file without being caught.** I traced these through `compare`/`check_record` (`scripts/docs_checks.py:205-291`):
  - Swapping the file for a symlink shows up as a type change, and the blob differs, so it fails.
  - Swapping it for a directory shows up as `D`, so it fails.
  - Hiding a body edit behind a bare `\r` inside the status line fails. `bytes.splitlines` splits on `\r`, so more than one line differs.
  - Renaming past git's rename limit falls back to D+A. `D` fails.
  - Undecodable filenames raise an exception that is not caught, so the script exits non-zero.

  Every case fails, which is the safe direction.
- **End to end on the real repo.** I committed the patched target as the base, then made a head that edits the body of ADR-0001 (Accepted), appends a line to ADR-0005 (`Superseded by ADR-0013`) and appends a line to ADR-0008 (`Proposed (… superseded by ADR-0019)`). I ran the base copy the way CI does (`git show B:scripts/docs_checks.py | python -I - immutability B H`). It exited 1 and named 0001 and 0005, and it let 0008 through. That matches the brief.
- **The reviewer's verdict.** I found no claim in `check-gates.json` that the evidence doesn't support. C4 doesn't cover the `-I` change, but the mutation run above does.

Out of scope, so not filed: a PR editing `.github/workflows/docs-checks.yml` itself. The iteration-2 sign-off explicitly left that to repo settings.

No NEEDS-HUMAN findings.

<!-- pdca:leaf-complete -->

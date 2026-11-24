# Build notes — issue 97 (docs-checks-adr-immutability), iteration 3

Target: eduralph/nl-shell @ main (`bc25e56`). Worktree: `$PDCA_WORKTREE`.

## What changed this iteration

Started from `iteration-v2/patch.diff` unchanged (applied with `git apply --index`), then
closed the one gap the iteration-2 sign-off named. Freeze logic, BOM handling, merge-base
diffing and the `pull_request`-only trigger are untouched.

1. `.github/workflows/docs-checks.yml:39` — the base-copy line is now
   `git show "$BASE:scripts/docs_checks.py" | python -I - immutability "$BASE" "$HEAD"`.
   `.github/workflows/docs-checks.yml:42` — the fallback line is now
   `python -I scripts/docs_checks.py immutability "$BASE" "$HEAD"`.
   `.github/workflows/docs-checks.yml:28-30` — a comment saying why.
   (These were lines 36 and 39 in v2; the 3-line comment moved them down.)

   Why `-I`: with `python -`, `sys.path[0]` is `''` (the current directory = the PR
   checkout), so a PR-added `re.py` is imported instead of the stdlib `re` that
   `scripts/docs_checks.py:26` imports. With `python scripts/docs_checks.py`,
   `sys.path[0]` is `scripts/`, so `scripts/re.py` does the same on the fallback leg.
   `-I` drops both from `sys.path` and also ignores `PYTHONPATH` / other `PYTHON*` env vars
   and the user site dir. The script's imports (`scripts/docs_checks.py:22-29`) are all
   stdlib, so isolated mode loses nothing.

2. `tests/test_docs_checks.py:621` `test_ci_step_ignores_a_stdlib_module_planted_by_the_pr`
   — the test the sign-off asked for, next to
   `test_ci_step_runs_the_base_copy_so_a_pr_cannot_disable_the_check` (`:600`). Base has
   the script and an Accepted ADR; head edits the ADR body and adds a root `re.py` that
   prints `docs-immutability: OK` and exits 0. Runs the real `run: |` block extracted from
   the workflow file. Asserts exit 1, ADR path in stdout, and that the base-copy branch ran.

3. `tests/test_docs_checks.py:640` `test_ci_step_fallback_ignores_a_module_planted_next_to_the_script`
   — same attack on the fallback leg (PR that first adds the script), with `scripts/re.py`.
   The sign-off asked for `-I` on both lines; this test proves the second one binds too.
   Shared payload is `SHADOW_RE` at `:618`.

Not done (out of scope per carry-forward): a PR that edits the workflow file itself.
That needs CODEOWNERS / branch protection on the repo.

## Red→green evidence

- C4 via the project runner (`PDCA_BUNDLE=… ./engine/scripts/run-verify.sh`):
  `PDCA-EVIDENCE: C4 PASS — red without the fix (71 of 71 failed), green with it`.
- C4 reverts the script and `.github/` together, so it cannot show the `-I` change alone is
  what the new tests catch. Separate check: removed only the two `-I` flags
  (`sed 's/python -I /python /'`), ran `python3 -m pytest tests/test_docs_checks.py`
  (the reproduction runner from `docs/INTEGRATION.md:52-53`, under `timeout 300`):
  `2 failed, 69 passed` — exactly the two new tests. Restored the flags: `71 passed`.

## Refute-your-own-test

- **(a) Genuine red?** Yes. With only `-I` reverted, both new tests fail (the planted
  `re.py` prints OK and exits 0, so the assertion `returncode == 1` fails at
  `tests/test_docs_checks.py:651` and the matching line in the other test). Full revert: 71/71 red.
- **(b) Production path?** Yes. `workflow_step_script()` (`tests/test_docs_checks.py:566`)
  reads the `run: |` body from the shipped `.github/workflows/docs-checks.yml` and runs it
  under `bash` with `python` on PATH pointing at the real interpreter, in a checkout of the
  PR head — the same shape GitHub runs. The base copy of the script is the real
  `scripts/docs_checks.py` bytes committed into the temp repo.
- **(c) Fixture includes the fault?** Yes. The head commit contains both the frozen-ADR
  edit and the attacker's `re.py` in the working directory the step runs in (`repo.git(
  "checkout", head)` in `run_workflow_step`, `:588`).

Limit: the test runs the step locally with bash, not on a GitHub runner. The draft PR's own
CI run is the on-GitHub confirmation (per the brief).

## Commit-readiness

nl-shell has no formatter or pre-commit config (no ruff/black/pre-commit entries in
`pyproject.toml`, `CONTRIBUTING.md`, `AGENTS.md`; no `.pre-commit-config.yaml`). `ruff` is
not installed. `git diff --cached --check` is clean; no line over 100 chars in the two
Python files.

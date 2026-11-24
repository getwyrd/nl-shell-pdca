# Build notes — issue 97 (docs-checks-adr-immutability), iteration 2

Target: eduralph/nl-shell @ main (`bc25e56`). Worktree: `$PDCA_WORKTREE`. All line numbers
below are in the patched tree.

## Starting point

Applied `iteration-v1/patch.diff` unchanged (sign-off accepted the core check), then made
only the two changes the iteration-1 carry-forward asked for. Everything else, including
the "any text after `Superseded by ADR-NNNN`" rule and an empty `status:` counting as
frozen, is untouched.

## Change 1 — CI runs the base commit's copy of the script

`.github/workflows/docs-checks.yml:25-40`. The step "Frozen design records are unchanged"
(`:28`) now:

- takes the SHAs through `env:` (`:29-31`), not by pasting `${{ }}` into the shell text;
- if `scripts/docs_checks.py` exists at `$BASE` (`:34`), runs
  `git show "$BASE:scripts/docs_checks.py" | python - immutability "$BASE" "$HEAD"` (`:36`);
- otherwise (the PR that first adds the script) runs the PR's copy (`:39`).

Trigger is still `pull_request` only, `permissions: contents: read`, no path filter,
`fetch-depth: 0`. The script works when fed on stdin: it uses no `__file__`, and its
`git` subprocesses use `capture_output`, so they do not read the piped script.

**A limit to know about at sign-off.** Under `pull_request`, GitHub reads the workflow
file itself from the PR's merge ref. So a PR can still disable the check by editing
`.github/workflows/docs-checks.yml`. This change closes the quieter route (editing the
Python file, which a reviewer may skim). The workflow route shows up as a `.github/`
diff. Fully closing it needs a repo setting (a ruleset with a required workflow, or
CODEOWNERS on `.github/` plus required review), or `pull_request_target`. The brief bans
`pull_request_target`, and repo settings are out of scope. I did not work around this.

**Test for it.** `tests/test_docs_checks.py:566-580` (`workflow_step_script`) reads the
step's `run: |` block out of the real workflow file. `run_workflow_step` (`:582-597`)
runs that block with `bash` in a throwaway repo checked out at the PR head, with
`BASE`/`HEAD` set and a `python` on PATH pointing at `sys.executable`. Three tests:

- `:600` — the base has the real script and an Accepted ADR. The head replaces the script
  with a no-op that prints "OK" and exits 0, and edits the ADR body. Must exit 1, name the
  ADR path, and say it ran the base copy.
- `:618` — the base has no script; the head adds it and edits an Accepted ADR. Must exit 1
  via the fallback.
- `:632` — a clean status-only move passes through the step (exit 0).

No YAML library: the block is found by step name and indentation, so the test adds no
dependency.

## Change 2 — leading UTF-8 BOM

`scripts/docs_checks.py:117` adds `UTF8_BOM`. At `:127`, `status_line_index` strips it
from line 0 before checking for `---`. Only the frontmatter lookup ignores the BOM.
`compare` still compares raw bytes, so adding or removing a BOM on a frozen file is an
edit, the same as LF→CRLF. Every status read goes through `status_line_index` (base side
in `frozen_status`, head side in `compare`), so this one line covers both.

Tests: `tests/test_docs_checks.py:536` (the must-fail the sign-off asked for: an Accepted
ADR saved with a BOM, body edited → exit 1 and the path named), `:545` (BOM'd Accepted
ADR, status-only move to Superseded → exit 0), `:552` (dropping the BOM from an Accepted
ADR → exit 1).

Ruled out: stripping the BOM from the whole blob before comparing. That would let a PR add
or remove a BOM on a frozen file without failing, which breaks the byte-exact rule the
brief keeps from iterations 1–3.

## Refuting my own test

- **(a) Genuine red?** Yes, at three levels:
  - The C4 gate (`engine/scripts/run-verify.sh`, run with `PDCA_BUNDLE` set to this bundle)
    gave `PDCA-EVIDENCE: C4 PASS — red without the fix (69 of 69 failed), green with it`.
  - With only the BOM line reverted (`:127` back to `line_text(lines[0])`), the BOM tests
    failed: `test_accepted_adr_saved_with_a_bom_is_still_frozen` and
    `test_removing_the_bom_from_an_accepted_adr_fails` (2 failed, 1 passed).
  - With only the workflow step reverted to a plain
    `python scripts/docs_checks.py immutability "$BASE" "$HEAD"`,
    `test_ci_step_runs_the_base_copy_so_a_pr_cannot_disable_the_check` failed: the PR's
    no-op script let the edit pass. The fallback test also failed, on its log message.
    After restoring both files, 69/69 passed and the tree matched `patch.diff` exactly.
- **(b) Production path?** Yes. Every test runs the real `scripts/docs_checks.py` as a
  subprocess. The CI tests run the real `run:` text from the shipped workflow file, not
  a copy of it.
- **(c) Fixture includes the fault?** Yes. The BOM fixture starts with the real bytes
  `EF BB BF`. The CI fixture commits a hostile no-op script at the PR head next to a real
  edit to an Accepted ADR.

One caveat for C4: it treats `.github/` as non-behavioural and does not revert it, so the
gate's own red leg does not isolate the workflow change. The manual workflow revert above
covers that. The draft PR's own CI run is still the only proof on GitHub itself.

## Commit-readiness

The target has no formatter, linter config or commit hooks: no `.pre-commit-config.yaml`,
no `core.hooksPath`, and nothing in `pyproject.toml`. `git diff --check` is clean. No
line in the two Python files is over 100 chars. `CONTRIBUTING.md:9-17` requires a DCO
`Signed-off-by` trailer on the commit, which publish has to add.

## Housekeeping

Two slips while testing, both fixed:

- A throwaway helper I ran crashed between reverting the BOM line and restoring it. I
  restored the line with `sed` and confirmed the tree matched `patch.diff` before going on.
- A stray `cp scripts/docs_checks.py /tmp/x` in one command left a copy of the script at
  `/tmp/x`, outside the roots I'm allowed to write to. I did not delete it, because cleanup
  belongs to the harness.

No external dependencies were needed beyond git, bash and the instance venv's pytest.

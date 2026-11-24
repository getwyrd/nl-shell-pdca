# Build notes — issue 97 (docs-checks-adr-immutability)

Target: eduralph/nl-shell @ main (`bc25e56`). Worktree: `/home/eddie/nl-shell/nl-shell.pdca-wt`.
All `path:line` refs below are in the patched tree unless marked "base".

## What I did

Started from the parent bundle's converged patch
(`results/issue_7/iteration-v3/patch.diff`), as the brief says, and removed everything for
link checking:

- `scripts/docs_checks.py`: cut `cmd_links` and every helper under the `# --- links ---`
  marker (261 lines), the `links` branch in `main`, the `links` usage text and docstring
  paragraph, and the now-unused `bisect` / `urllib.parse.unquote` imports. Replaced the
  docstring's links paragraph with one stating the merge-base → head rule.
- `.github/workflows/docs-checks.yml`: dropped the "Relative Markdown links resolve" step
  and the "and relative Markdown links resolve" comment.
- `tests/test_docs_checks.py`: dropped section (b) links and (c) live-tree links test.

Then checked the remaining code against the brief point by point (the brief wins where they
differ; I found no conflict in the immutability half):

| Brief rule | Where |
|---|---|
| (i) ADR frozen unless base status starts `Proposed`; Accepted → only `Superseded by ADR-NNNN…`; no `implemented` | `scripts/docs_checks.py:52-60` (`AdrClass`), regex `:37` |
| (ii) proposal frozen unless `draft`; accepted → implemented/withdrawn only | `scripts/docs_checks.py:63-71` |
| (iii) spec frozen unless `draft`; stable → superseded/withdrawn only | `scripts/docs_checks.py:74-83` |
| (r1) status from frontmatter, case-insensitive, `# …` comment and quotes stripped | `scripts/docs_checks.py:117-136` (`status_line_index`, `status_value`) |
| (r2) no frontmatter/status → not frozen | `scripts/docs_checks.py` `frozen_status` (`return None  # … (r2)`) |
| (r3) only `NNNN-*.md` for ADRs/proposals, specs minus README | `scripts/docs_checks.py:33-35`, `:94-101` |
| (r4) rename checked at its old path | `changed_paths` (`-M`), `check_record` `:255` |
| (r5) only the status line may differ, byte-exact incl. line terminator | `compare` `:197` |
| merge-base → head diff; frozen at merge-base OR base tip; renames followed merge-base → tip | `cmd_immutability` `:291-316` |
| Error output tells author to supersede | `compare` advice + summary line in `cmd_immutability` |
| Workflow: `pull_request` only, no path filter, `contents: read`, `fetch-depth: 0`, named step | `.github/workflows/docs-checks.yml:8-29` |
| Index sentence, ADR README | `docs/design/adr/README.md:11-15` (inserted after "records the supersession", base `:9-11`) |
| Index sentence, proposals README | `docs/design/proposals/README.md:12-13` (after base `:11`) |

Sources the code cites (all verified on the base tree): ADR-0001 Decision
`docs/design/adr/0001-record-architecture-decisions.md:18-23` and `:30-31`;
`docs/design/README.md:18-21`; `docs/design/proposals/README.md:10-11`;
`docs/design/templates/{adr,proposal,spec}.md:4`.

### Tests I added (cases the brief names that the carry-forward did not cover)

- Must-pass: `draft-spec-with-template-comment-body`, `draft-proposal-with-template-comment-body`,
  `proposed-adr-with-template-comment-body`, `quoted-draft-spec-body`,
  `single-quoted-draft-proposal-body`, `accepted-proposal-with-template-comment-to-implemented`,
  `quoted-stable-spec-to-superseded`.
- Must-fail: `superseded-spec-status`, `stable-spec-with-template-comment-body`,
  `quoted-accepted-proposal-body`.
- `test_pr_branched_before_main_superseded_an_adr_passes`: main moves ADR X Accepted →
  Superseded by ADR-0050 after the PR branched; the PR does not touch X → exit 0. (The
  Proposed → Accepted variant was already in the carry-forward as
  `test_diverged_pr_not_touching_the_accepted_adr_passes`.)

Template-comment constants are copied verbatim from base `docs/design/templates/*.md:4`.

Every must-fail assertion checks the expected path is in stdout (parametrized
`test_frozen_record_change_fails` asserts `path in result.stdout` and `"supersede"`).

## Style / commit-readiness

nl-shell has no formatter, linter config, `.pre-commit-config.yaml`, or git hooks (checked:
no ruff/black/flake8 config in `pyproject.toml`, no hooks dir entries, `core.hooksPath`
unset). I wrapped every new line to ≤ 92 columns to match the existing code (only 2 of the
tracked `.py` lines exceed 92). `scripts/docs_checks.py` is mode 100755 (it has a shebang);
the workflow calls it via `python`, so the mode doesn't matter for CI.

## Verification

- C4 (`engine/scripts/run-verify.sh`, run with `PDCA_BUNDLE`/`PDCA_WORKTREE` set):
  `PDCA-EVIDENCE: C4 PASS — red without the fix (63 of 63 failed), green with it`.
  Production path reverted by the gate: `scripts/docs_checks.py`. No collection error on the
  red leg (the test never imports the script).
- T3 (`engine/scripts/run-suite.sh`): `98 passed`, `T3 PASS`.
- Real tree, the brief's reproduction, using throwaway commit objects (`git commit-tree`, no
  ref moved) on top of `bc25e56`:
  - edit `## Context` in ADR-0001 (Accepted) → exit 1, names
    `docs/design/adr/0001-record-architecture-decisions.md`;
  - same edit on ADR-0005 (`Superseded by ADR-0013`) → exit 1, names the path;
  - same edit on ADR-0008 (`Proposed (… superseded by ADR-0019)`) → exit 0.
  This left a scratch index file at `<worktree git dir>/pdca-demo-index` and some loose
  objects; I did not delete them (cleanup is the harness's).

## Refuting my own test

- **(a) Genuine red?** Yes. The C4 gate reverted `scripts/docs_checks.py` and re-ran the file:
  63 of 63 failed (must-fail tests fail because stdout lacks the path; must-pass tests fail
  on returncode 2 from a missing script). Not a collection error.
- **(b) Production path?** Yes. Each test runs the real `scripts/docs_checks.py` as a
  subprocess (`sys.executable`, path from `Path(__file__).resolve().parent.parent`), the same
  file and command line the workflow runs. Nothing is mocked; git is real.
- **(c) Fixture includes the fault?** Yes. Each must-fail fixture makes an actual git commit
  that edits/deletes/renames a frozen record; the diverged tests build real branches with a
  real merge-base. The real-tree run above also exercised the brief's exact reproduction on
  ADR-0001.

## Not verified here

- That the workflow runs and fails on GitHub on every PR. That half is only provable on the
  draft PR's own CI run (brief: "checked by reading the patch and by the draft PR's own CI
  run, not by C4"). I did not push or open a PR. The optional "throwaway commit touching
  ADR-0001 to show the job fail" is left for the draft-PR step.
- Making the job a required check is a repo setting for the human (out of scope).

## Ruled out

- Keeping the link-check code but unused: the brief puts all link checking in child-2.
- Diffing base tip → head: brief forbids it; `test_pr_branched_before_main_superseded_an_adr_passes`
  and `test_diverged_pr_not_touching_the_accepted_adr_passes` would go red under it.

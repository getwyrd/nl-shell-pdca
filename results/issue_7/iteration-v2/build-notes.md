# Build notes — issue 7 / docs-checks-adr-immutability-links (iteration 2)

Target: eduralph/nl-shell @ main (`bc25e56`), worktree `$PDCA_WORKTREE`
(`/home/eddie/nl-shell/nl-shell.pdca-wt`). Line numbers are in the patched tree unless
marked "base".

## What this iteration changes

I started from the v1 patch (`iteration-v1/patch.diff`) and fixed the three defects the
sign-off carry-forward lists. Scope, rules r1–r6, the workflow and the two README sentences
are unchanged from v1. Only `scripts/docs_checks.py` and `tests/test_docs_checks.py` differ.

### 1. Frozen at the merge-base OR the base tip

- `cmd_immutability` (`scripts/docs_checks.py:263-286`) still diffs `merge-base..head`
  (what the PR itself changed). It now also resolves the base tip and passes both as
  `bases` (`:265-271`); the tip is only added when it differs from the merge-base.
- `check_record` (`:238-260`) loops over both. If the path is frozen at either one
  (`frozen_status`, `:183-194`), the head must equal that frozen copy except for an allowed
  status-line change (`compare`, `:197-235`). The message names which one froze it
  (`"at the merge-base"` / `"at the base tip"`).
- Why compare against the tip copy (not the merge-base copy) when the tip froze it: if main
  accepted the ADR and the PR made the same `Proposed → Accepted` flip, tip == head and it
  passes. If the PR edited the body, tip vs head differs outside the status line and fails.
  A PR that does not touch the file is not in the diff at all, so main's own changes are
  never blamed on it (`test_diverged_pr_not_touching_the_accepted_adr_passes`).
- Regression: `test_adr_accepted_on_main_after_the_pr_branched_is_frozen` builds a real
  branch: ADR Proposed at the branch point, main commits `Accepted`, the PR branch edits the
  body. Must fail and name the path and "base tip". Two must-pass companions:
  `test_diverged_pr_editing_a_still_proposed_adr_passes`,
  `test_diverged_pr_not_touching_the_accepted_adr_passes`.

### 2. Byte-exact comparison

- Blobs are read with `git cat-file blob` and no `text=True` (`git_blob`, `:151-161`), so
  there is no newline translation. Lines are split with `bytes.splitlines(keepends=True)`
  (`split_lines`, `:106-108`), so `\r\n` and `\n` lines compare unequal. Only the status
  value is decoded, for parsing (`line_text`, `status_value`, `:115-137`).
- Even on an allowed status-line change, the status line must keep its exact line ending
  (`terminator`, `:111-112`, used at `compare` `:222-226`), so CRLF can't sneak in there.
- Regressions: `test_crlf_rewrite_of_an_accepted_adr_fails` (whole file LF → CRLF, text
  identical) and `test_crlf_on_an_allowed_status_line_change_fails`. Must-pass:
  `test_crlf_accepted_adr_status_only_change_passes` (a CRLF file can still take its allowed
  transition). The test helper pins `core.autocrlf=false` and writes raw bytes, so git
  stores the CRLF exactly.

### 3. Link parser false failures

`link_targets` (`:392-408`) now masks the whole file first, keeping offsets and newlines so
line numbers stay right, then scans:

- **Fenced and indented code blocks** — `mask_code_blocks` (`:313-353`). An indented block
  (4 spaces or a tab, `INDENTED_RE`) counts as code only after a blank line or another code
  line (it can't interrupt a paragraph) and not inside a list (indented list content is
  item text, not code). Lists end at a non-indented, non-item line after a blank.
- **HTML comments and code spans, including ones that cross lines** — `INLINE_MASK_RE`
  (`:300-305`), one left-to-right alternation so whichever starts first wins. A code span
  needs a closing backtick run of the same length and cannot cross a blank line.
- **Footnote definitions** — `REFDEF_RE` (`:296`) rejects a label starting with `^`.
- **Balanced parentheses** — `inline_destination` (`:356-391`) walks the destination,
  counting `(`/`)` depth, handling `\` escapes and `<…>` destinations. So
  `file(v1).md` resolves to `file(v1).md`, not `file(v1`.

Regressions: `test_markdown_that_is_not_a_broken_link_passes` (11 cases: two footnote forms,
balanced and escaped parens, two cross-line code spans, space- and tab-indented code, three
HTML comment forms). To check the masking doesn't hide real links:
`test_broken_link_next_to_ignored_markdown_fails` (8 cases: missing `file(v2).md`, and
broken links right after a footnote, a closed code span, a comment, an indented block, as an
indented paragraph continuation, as indented list-item content, and after an unclosed
backtick). Each asserts the file and the quoted link appear in stdout.

Live tree: `docs-links: OK (60 relative links checked)` — same 60/0 as v1 and the brief.

## Rules and sources (unchanged from v1)

- r3 file classes: `ADR_RE`/`PROPOSAL_RE`/`SPEC_RE` `:36-38`, `record_class` `:96-103`.
- ADR: frozen unless base status starts with `proposed`; `accepted` → `superseded by
  adr-NNNN…` only (`AdrClass` `:55-63`). ADR-0001
  `docs/design/adr/0001-record-architecture-decisions.md:18-23` (base),
  `docs/design/README.md:20` (base), `docs/design/templates/adr.md:4` (base).
- Proposal: frozen unless `draft`; `accepted` → `implemented`|`withdrawn` (`:66-74`).
  `docs/design/README.md:21`, `docs/design/proposals/README.md:10-11`,
  `docs/design/templates/proposal.md:4` (base).
- Spec: frozen unless `draft`; `stable` → `superseded`|`withdrawn` (`:77-85`).
  `docs/design/README.md:18`, `docs/design/templates/spec.md:4` (base).
- r2 no frontmatter / no status → not frozen (`frozen_status` `:189-190`). r4 rename checked
  at the old path, r5 delete/rename/other-line change fails (`compare` `:203-206`).
- Workflow `.github/workflows/docs-checks.yml`: shape mirrors `.github/workflows/tests.yml`
  (base): `pull_request` only, `permissions: contents: read`, `fetch-depth: 0`.
- README sentences: `docs/design/adr/README.md:11-15`, `docs/design/proposals/README.md:12-13`.

## Red → green (project runner)

`engine/scripts/run-verify.sh` (C4):

```
== C4 green leg: ... 79 passed in 3.55s
== C4 red leg:   ... 79 failed (ran 79, failed 79, import/collection errors 0)
PDCA-EVIDENCE: C4 PASS — red without the fix (79 of 79 failed), green with it
```

`engine/scripts/run-suite.sh` (T3, whole suite): `114 passed`, T3 PASS.

## Refuting my own test

- **(a) Genuine red? Yes.** C4's red leg removes the script and all 79 fail (no collection
  errors). That only shows "script absent", so I also ran the new test file against the
  **v1 script** (the rejected attempt) via the venv pytest under `timeout`: 15 failed,
  64 passed. The 15 failures are exactly the new regressions — the diverged-history test,
  both CRLF must-fails, all 11 link must-pass cases, and `balanced-parens-missing`. So each
  carry-forward defect turns at least one test red on the old code. One mutation on v2:
  dropping the `not in_list` guard in `mask_code_blocks` → 1 fail
  (`indented-list-item-content`). The v2 script was restored after each run and the patch
  re-diffed byte-identical to the one C4 ran.
- **(b) Production path? Yes.** Every test runs the real `scripts/docs_checks.py` as a
  subprocess (`sys.executable`) against real git repos; the diverged-history test uses a
  real branch and a real `git merge-base`. No mocks or copies. The live-tree test runs it on
  the nl-shell worktree itself (`.git` is a file).
- **(c) Fixture includes the fault? Yes.** The diverged test has the ADR Accepted only on
  main's tip, not at the merge-base — the exact case v1 missed. The CRLF tests store real
  CRLF bytes in git. The link cases contain the actual Markdown that v1 misreported.

## Ruled out

- **Comparing against the merge-base copy only, but taking frozen-ness from the tip.** A PR
  that made the same `Proposed → Accepted` flip as main would then be judged "frozen, status
  changed from proposed" and false-fail. Comparing against the tip's own copy avoids that.
- **Diffing `base_tip..head`** instead of merge-base: blames the PR for main's own commits.
  The carry-forward says to keep merge-base..head.
- **A full CommonMark parser** (e.g. `markdown-it-py`): the brief requires stdlib only.
- **Masking every 4-space-indented line:** would hide links in list-item content and lazy
  paragraph continuations (false passes). Covered by the two must-fail cases above.
- Out of scope, untouched: fragment anchors, conformance vectors, `docs/plan.md`, running
  the base copy of the script / CODEOWNERS, and the stale-result branch setting (the
  carry-forward lists those last two as maintainer calls).

## Commit-readiness

nl-shell has no formatter config, `.pre-commit-config.yaml` or `core.hooksPath`.
`git diff --check` is clean and both Python files compile. CONTRIBUTING wants a DCO
`Signed-off-by` on the commit; that is publish's job.

## Housekeeping

During a self-check I redirected a `git diff` to `/tmp/x`, which is outside the roots I'm
allowed to write. It holds only a copy of this patch and can be ignored or removed by the
harness.

## Not verifiable here

The "runs on every PR" half can only be seen on the draft PR's own CI run. I did not push
or open a PR.

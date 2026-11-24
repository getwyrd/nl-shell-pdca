# Build notes — issue 7 / docs-checks-adr-immutability-links (iteration 3)

Target: eduralph/nl-shell @ main (`bc25e56`), worktree `$PDCA_WORKTREE`
(`/home/eddie/nl-shell/nl-shell.pdca-wt`). Line numbers are in the patched tree unless
marked "base". Test copy in the bundle: `tests/test_docs_checks.py`.

## What this iteration changes

I applied the v2 patch (`iteration-v2/patch.diff`) and fixed the four defects in the
Iteration 2 carry-forward. Scope, rules r1–r6, the workflow and the two README sentences
are unchanged from v2. Only `scripts/docs_checks.py` and `tests/test_docs_checks.py`
differ.

### 1. Frozen status follows renames on the base branch

- `cmd_immutability` (`scripts/docs_checks.py:291-319`) still diffs `merge-base..head`.
  For the base-tip leg it now also computes `renames_between(merge_base, base_tip)`
  (`:286-288`, which is `git diff --name-status -z -M` filtered to `R`). Each leg is a
  `Base(label, rev, renames)` (`:242-253`); the merge-base leg has no renames.
- `check_record` (`:255-283`): for each leg, the frozen copy is looked up at
  `renames.get(path, path)`, the file's path *at that base*. The record class comes from
  that path too, so `draft/0001` moved to `accepted/0001` is judged as a frozen proposal.
- `compare` (`:197-239`) now takes the frozen path and the PR's head path. The head path is
  the new path for an `R`, none for a `D`, otherwise the same path. If the PR keeps the
  file somewhere other than where the base froze it, that fails (`:211-212`). If it is at
  the same path, the old byte-exact, status-line-only rule applies. On the merge-base leg
  this gives exactly v2's behaviour (rename or delete of a frozen file fails).
- The message names both paths: `<path> (frozen at the base tip, where the base branch
  moved it to <new path>) ...`.
- Regression (the carry-forward's case): `test_pr_editing_a_draft_proposal_that_main_ratified_and_moved_fails`
  (`tests/test_docs_checks.py:356`). Main does `git mv draft/ → accepted/` plus
  `status: accepted` after the PR branched; the PR edits the body at `draft/`. Must fail and
  name both paths. v2 printed `docs-immutability: OK`.
- Companions: `test_pr_making_the_same_ratification_as_main_passes` (`:372`, PR and main
  both do the identical ratification → pass), `test_pr_ratifying_with_a_different_body_than_main_fails`
  (`:384`), `test_pr_not_touching_a_proposal_main_moved_passes` (`:397`).
- `diverged()` (`:335`) now also seeds a draft proposal and takes `main_moves`/`pr_moves`.

### 2. Code blocks nested in list items

`mask_code_blocks` (`:364-423`) was rewritten around a stack of list-item content columns:

- `list_content_column` (`:349-361`) gives an item's content column: marker width plus 1–4
  spaces (1 if the item is empty or followed by 5+ spaces). `indent_of` (`:343-346`)
  expands tabs to 4-column stops.
- On a non-blank line, items whose content column is past the line's indent are closed
  after a blank line, or when the line starts a fence or a new item. Without a blank line a
  less-indented plain line is a lazy continuation and keeps the item open (`:396-402`).
- Indentation is then measured from the enclosing item's content column: `>= 4` after a
  blank (or continuing a code block) is indented code (`:404-410`); `<= 3` may open a
  fence, which remembers its container column (`:413-418`).
- A fence closes on a matching run within 3 columns of its container, or when a non-blank
  line drops below the container column (the item ended; that line is reread,
  `:379-392`).
- Text indented to the item's content stays text, so `1. Item\n\n    [x](gone.md)`
  (content column 3, relative indent 1) is still link-checked. The existing
  `indented-list-item-content` must-fail case stays and passes.

Regressions in `NOT_A_BROKEN_LINK` (`:542-565`): `tilde-fence-in-list-item` (the exact
carry-forward input, `:554`), `backtick-fence-in-list-item`, `fence-in-nested-list-item`,
`fence-in-list-item-without-blank-line`, `indented-code-in-list-item` (`:560`). In
`STILL_A_BROKEN_LINK` (`:577-600`): `after-a-fence-in-a-list-item-closes`,
`after-the-list-ends-a-fence-left-open`, `nested-list-item-content`.

### 3. Reference-definition destinations are unescaped

- `unescape` (`:338-340`, `ESCAPE_RE` `:330`) drops the backslash from escaped ASCII
  punctuation (CommonMark §2.4). `link_targets` (`:502-521`) strips `<…>` from a reference
  destination and unescapes it. The `<…>` inline form is now unescaped too
  (`inline_destination`, `:480`); the bare inline form already was.
- Regressions: `escaped-parens-in-reference-definition` (`[ref]: file\(v1\).md` to a tracked
  `file(v1).md`, `:561`) and its `<…>` form (`:562`) must pass;
  `escaped-parens-in-reference-definition-missing` (`file\(v2\).md`, `:587`) must fail and
  print `'file(v2).md'`.

### 4. Escaped backticks don't open a code span

- The one-regex inline mask (`INLINE_MASK_RE`) is replaced by a left-to-right scanner,
  `mask_inline` (`:426-463`). It skips `\` + escapable punctuation as a pair, so `` \` `` is
  a literal and `\\` followed by a backtick still opens a span. It blanks `<!-- … -->` and
  code spans (a run closed by the next run of the same length, not across a blank line).
  An unmatched run stays literal text.
- `link_targets` also skips `](` after an odd number of backslashes (`\]` is a literal
  bracket), `:511`.
- Regressions: `escaped-backticks` (the carry-forward input, `:586`) must fail naming
  `gone.md`; `escaped-backslash-then-code-span` (`:563`) and `escaped-closing-bracket`
  (`:564`) must pass.

Live tree: `docs-links: OK (60 relative links checked)`, the same 60/0 as the brief.

## Rules and sources (unchanged from v1/v2)

- r3 file classes: `ADR_RE`/`PROPOSAL_RE`/`SPEC_RE` `:36-38`, `record_class` `:96-103`.
- ADR: frozen unless base status starts with `proposed`; `accepted` → `superseded by
  adr-NNNN…` only (`AdrClass` `:55-63`). Sources:
  `docs/design/adr/0001-record-architecture-decisions.md:18-23` (base),
  `docs/design/README.md:20` (base), `docs/design/templates/adr.md:4` (base).
- Proposal: frozen unless `draft`; `accepted` → `implemented`|`withdrawn` (`:66-74`).
  `docs/design/README.md:21`, `docs/design/proposals/README.md:10-11`,
  `docs/design/templates/proposal.md:4` (base).
- Spec: frozen unless `draft`; `stable` → `superseded`|`withdrawn` (`:77-85`).
  `docs/design/README.md:18`, `docs/design/templates/spec.md:4` (base).
- r2 no frontmatter / no status → not frozen (`frozen_status` `:183-194`). r4 rename checked
  at the old path, r5 delete/rename/other-line change fails (`compare` `:197-239`).
  Byte-exact comparison (the iteration-1 fix) is kept: `git_blob` `:151-160`,
  `split_lines`/`terminator` `:106-112`.
- Workflow `.github/workflows/docs-checks.yml`: shape mirrors `.github/workflows/tests.yml`
  (base): `pull_request` only, `permissions: contents: read`, `fetch-depth: 0`.
- README sentences: `docs/design/adr/README.md:11-15`, `docs/design/proposals/README.md:12-13`.

## Red → green (project runners)

`engine/scripts/run-verify.sh` (C4), with `PDCA_BUNDLE` and `PDCA_WORKTREE` set:

```
97 failed in 2.46s
   (pytest exit 1; ran 97, failed 97, setup errors 0, import/collection errors 0)
PDCA-EVIDENCE: C4 PASS — red without the fix (97 of 97 failed), green with it
```

`engine/scripts/run-suite.sh` (T3, whole nl-shell suite): `132 passed`, T3 PASS.

## Refuting my own test

- **(a) Genuine red? Yes.** C4's red leg removes the script and all 97 tests fail with no
  collection errors. That only proves "script absent", so I also ran the new test file
  against the **v2 script** (the rejected attempt), via the project venv's pytest under
  `timeout 300`: **10 failed, 87 passed**. The 10 failures cover every carry-forward item:
  - renames: `test_pr_editing_a_draft_proposal_that_main_ratified_and_moved_fails`,
    `test_pr_ratifying_with_a_different_body_than_main_fails`;
  - list code: `tilde-fence-in-list-item`, `indented-code-in-list-item`,
    `after-the-list-ends-a-fence-left-open`;
  - ref-def escapes: `escaped-parens-in-reference-definition`, its `<…>` form, and
    `escaped-parens-in-reference-definition-missing`;
  - escaped backtick: `escaped-backticks` (plus `escaped-closing-bracket`).
  After that run I put the v3 script back and confirmed `git diff` is byte-identical to
  `patch.diff` (`cmp` clean).
  Three new list cases (`backtick-fence-in-list-item`, `fence-in-nested-list-item`,
  `fence-in-list-item-without-blank-line`) passed on v2 too. In v2 the 2-space fence
  matched `^ {0,3}`, and in the deeper cases the ```` ``` ```` lines were read as a
  multi-line code span, which happened to hide the link. They stay as must-pass guards.
- **(b) Production path? Yes.** Every test runs the real `scripts/docs_checks.py` as a
  subprocess (`sys.executable`) against real git repos. The rename tests use a real branch,
  real `git mv` on main, and a real `git merge-base`. No mocks or copies. The live-tree test
  runs it on the nl-shell worktree itself, where `.git` is a file.
- **(c) Fixture includes the fault? Yes.** In the rename regression the proposal is a
  draft at the merge-base and exists **only** under `accepted/` at the base tip. That is the
  exact case v2 missed. The link cases contain the literal Markdown from the carry-forward.

## Ruled out

- **Comparing the PR's head file at the *old* path against the tip's copy at the new path,
  ignoring the path difference.** A PR that edits `draft/0001` without changing the bytes
  that matter would then pass while main has moved the file. Git would merge that edit into
  `accepted/0001` through rename detection, which edits a frozen file. Requiring the head
  path to equal the frozen path (`compare` `:211-212`) fails it. A PR that doesn't touch the
  file is not in the merge-base..head diff, so main's own move is never blamed on it
  (`test_pr_not_touching_a_proposal_main_moved_passes`).
- **Diffing `base_tip..head`** to pick up the rename: that blames the PR for main's
  commits. The carry-forward says to keep merge-base..head.
- **Patching the old `INLINE_MASK_RE` with a `(?<!\\)` lookbehind** for escaped backticks.
  It gets `\\` + backtick wrong (an escaped backslash, then a real span): the lookbehind
  sees a backslash and refuses to open the span. A scanner that consumes escapes as pairs
  handles both. `escaped-backslash-then-code-span` covers this.
- **A full CommonMark parser** (e.g. `markdown-it-py`): the brief requires stdlib only.
  Blockquote containers (`>`) are still not modelled. A fence inside a blockquote is not
  masked, so a link inside one can false-fail. The live tree has none, and the carry-forward
  didn't ask for it.
- Out of scope, untouched: fragment anchors, conformance vectors, `docs/plan.md`, running
  the base copy of the script / CODEOWNERS (a maintainer call per the carry-forward).

## Commit-readiness

nl-shell has no formatter config, `.pre-commit-config.yaml`, `core.hooksPath`, or
ruff/black/flake8 settings in `pyproject.toml`. `git diff --check` is clean and both Python
files compile. CONTRIBUTING wants a DCO `Signed-off-by` on the commit; that is publish's
job.

## Not verifiable here

The "runs on every PR" half can only be seen on the draft PR's own CI run. I did not push
or open a PR.

# Result — issue 7 / docs-checks-adr-immutability-links

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: nl-shell's design docs declare Accepted ADRs and accepted proposals append-only (ADR-0001 `:22-23`; `docs/design/README.md` class table `:18-21`; `docs/design/proposals/README.md:10-11`), and stable spec versions are never edited (`docs/design/README.md:18`). ADR-0001 `:30-31` says a docs CI check enforces this, but no such check exists. `.github/workflows/` holds only `tests.yml`, `require-linked-issue.yml` and `triage-new-issue.yml`, so a PR can edit an Accepted ADR or a stable spec, or break a relative Markdown link, and still merge green. The issue asks to port wyrd's docs CI (`getwyrd/wyrd` `.github/workflows/docs-immutability.yml` and `docs-check.yml`), adapted to nl-shell's rules below.
- Success criterion: A new pytest file `tests/test_docs_checks.py` runs nl-shell's docs checks against throwaway git repos it builds in `tmp_path`. It passes with the fix and fails without it. It shows the following.
  (a) **Immutability.** Between a base and a head commit, the check exits non-zero and names the offending path when a PR modifies, deletes or renames away a frozen file (frozen = see Invariant), except for the allowed status-line transitions below. Must-fail cases include: editing the body of an `Accepted` ADR; editing any part of an ADR whose base status starts with `Superseded`; changing an `Accepted` ADR's status to anything other than `Superseded by ADR-NNNN…` (in particular `Accepted` → `Implemented` fails: ADRs have no implemented state); changing an `Accepted` ADR's status line *and* its body in the same PR; editing the body of an `accepted` proposal; changing an `accepted` proposal's status to `superseded`; editing an `implemented` or `withdrawn` proposal; editing the body of a `stable` spec; editing a `superseded` or `withdrawn` spec.
  It exits 0 when the PR: edits a `Proposed` ADR (including a status like `Proposed (… superseded by ADR-0019)`, i.e. ADR-0008); flips an ADR's status `Proposed` → `Accepted`; changes only the status line of an `Accepted` ADR to `Superseded by ADR-NNNN` (any text after that prefix allowed); moves proposal 0001 from `draft/` to `accepted/` while setting its status to `accepted` (the #6 ratification step); changes only the status line of an `accepted` proposal to `implemented` or `withdrawn`; edits a `draft` spec; flips a spec's status `draft` → `stable`; changes only the status line of a `stable` spec to `superseded` or `withdrawn`; adds a new spec file (e.g. `policy-gate/v2.md`); adds a new numbered ADR or proposal; or edits `adr/README.md`, `proposals/README.md` or `specs/README.md`.
  (b) **Links.** The check exits non-zero and names the file and the link when a tracked `.md` file has a relative link (inline `[t](path)`, image `![t](path)`, or reference definition `[t]: path`, with or without `#fragment`) whose target is not a tracked file or directory. It exits 0 when the only such links are external (`https:`, `mailto:` and other `scheme:` URLs), pure `#fragment` links, or links inside fenced code blocks or inline code.
  (c) The link check exits 0 on the nl-shell tree itself. Today there are 60 relative links and 0 broken. This test runs against the live checkout (the repo root found from the test file's location). That means `tests.yml` also fails when a broken link reaches the tree. This is intended: a code PR can only go red from it if main already has a broken link, which the docs job exists to stop. The test must work when `.git` is a file, i.e. in a git worktree, which is how the C4 gate runs it (`engine/scripts/run-verify.sh:118`). Use `git ls-files` run from the repo root; don't open `.git` directly.
  Every must-fail assertion also checks that the expected path or link appears in the output, so a missing or crashing script cannot satisfy it. The new workflow runs both checks on every PR. That part is checked by reading the patch and by the draft PR's own CI run (see Falsifiability), not by C4.
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: Add:
  (1) The docs-check logic as a stdlib-only Python script outside `.github/`/`docs/`/`tests/`, runnable from any git checkout's root. It has an immutability mode that takes a base and a head ref, and a link mode that scans `git ls-files '*.md'`.
  (2) One sentence in `docs/design/adr/README.md`'s opening paragraph (lines 9-11, after "a later ADR supersedes it, and this index records the supersession"). The sentence says: the only change ever allowed to an Accepted ADR is setting its status line to `Superseded by ADR-NNNN`; a Superseded ADR is never edited at all, including the ones superseded while still Proposed (0005-0007, 0011); and an ADR that is only partly superseded and still Proposed (0008) stays editable like any Proposed ADR.
  (3) One sentence in `docs/design/proposals/README.md` after line 11: the only change allowed to an accepted proposal is setting its status line to `implemented` or `withdrawn`.
  (4) A workflow `.github/workflows/docs-checks.yml` on `pull_request` with **no path filter** (so it always reports and can later be a required check), `permissions: contents: read`, and `actions/checkout` with `fetch-depth: 0`. It runs both modes with `${{ github.event.pull_request.base.sha }}` / `head.sha`.
  (5) `tests/test_docs_checks.py`.
  Rules that differ from wyrd and must be kept:
  (r1) Status is read from the YAML frontmatter `status:` line (case-insensitive). Whether a file is frozen comes from the **base** commit.
  (r2) A file with no frontmatter or no `status:` in the base is not frozen.
  (r3) README/index pages are excluded. For ADRs and proposals only `NNNN-*.md` files count; for specs every `.md` except `README.md`.
  (r4) A rename is checked at its old path.
  (r5) A frozen file passes only if the base and head differ in exactly the `status:` line, and the head value is an allowed next state for the base value (see Invariant). Removing a frozen file, renaming it, or changing any other line fails. The one exception is the proposal move `draft/` → `accepted/`, which applies only to a base status of `draft` (not frozen).
  (r6) wyrd also allows a status-only change to Superseded. nl-shell keeps that and also allows the other next states its templates list. `proposals/README.md:10-11` still holds: proposals have no `superseded` state, so a proposal's supersession is recorded only in the index.
  The tests set their own git identity for the throwaway repos (git -c options or the GIT_AUTHOR/GIT_COMMITTER env vars) and never rely on the host git config (`tests/conftest.py:52-56` sets a temp HOME). Error output tells the author to supersede the file (a new ADR/proposal/spec version plus an index entry) instead of editing it.
  / out of scope: wyrd's conformance-vector rule (non-Markdown files under a spec's `vN/` directory belong to that spec; nl-shell has no vectors yet, so non-Markdown files under `specs/` are not checked); checking `#fragment` anchors against headings; wyrd's Obsidian lint and site render (`lint_docs.py`, `render_site.py`); `docs/plan.md`, which is frozen by a banner, not by a `status:` field (`docs/plan.md:3`, `docs/design/README.md:75-76`), and is left unchecked; making the job a required status check in branch protection (a repo setting for the human); editing the template status comments, ADR-0001 (it is Accepted and frozen), or any existing doc other than the two index sentences above; the harness's own `docs/INTEGRATION.md` T2 row.

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: likely-fix
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — N/A — close disposition (no patch to verify)
- C3 Change: none — patch.diff
- C4 Verification (red→green): none — N/A — close disposition (no patch to verify)
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — N/A — close disposition (no patch to verify)
- T2 Shape: none — N/A — close disposition (no patch to verify)
- T3 Runtime: none — N/A — close disposition (no patch to verify)
- T4 Contribution: none — N/A — close disposition (no patch to verify)
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

# Advisory review — SKIPPED (close disposition)

The reviewer leaf was skipped: this bundle's Plan concluded a close / no-fix disposition (split), so there is no patch to review.

- NEEDS-HUMAN — Confirm the close disposition 'split' (no patch was built). Override to a fix path (iterate-to-Do) if the close is wrong.


## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] Confirm the close disposition 'split' (no patch was built). Override to a fix path (iterate-to-Do) if the close is wrong.

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
- (empty is the common case)

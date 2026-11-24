# Brief — issue 7 / docs-checks-adr-immutability-links

> Plan artifact. Do reads ONLY this file. Template: `brief.md.tpl` (not the design-proposal
> form): this ports an existing CI check, with no architecture, API or data-model impact.
> Milestone: **Foundations**. Builds on **ADR-0001** (record architecture decisions —
> "Once Accepted it MUST NOT be edited", `docs/design/adr/0001-record-architecture-decisions.md:22-23`,
> and "A docs CI check enforces immutability (Foundations milestone)", same file `:30-31`).
> Threat-model inputs affected: none (a read-only CI job; no runtime code).

- **Slug:** docs-checks-adr-immutability-links
- **Defect:** nl-shell's design docs declare Accepted ADRs and accepted proposals append-only (ADR-0001 `:22-23`; `docs/design/README.md` class table `:18-21`; `docs/design/proposals/README.md:10-11`), and stable spec versions are never edited (`docs/design/README.md:18`). ADR-0001 `:30-31` says a docs CI check enforces this, but no such check exists. `.github/workflows/` holds only `tests.yml`, `require-linked-issue.yml` and `triage-new-issue.yml`, so a PR can edit an Accepted ADR or a stable spec, or break a relative Markdown link, and still merge green. The issue asks to port wyrd's docs CI (`getwyrd/wyrd` `.github/workflows/docs-immutability.yml` and `docs-check.yml`), adapted to nl-shell's rules below.
- **Success criterion:** A new pytest file `tests/test_docs_checks.py` runs nl-shell's docs checks against throwaway git repos it builds in `tmp_path`. It passes with the fix and fails without it. It shows the following.
  (a) **Immutability.** Between a base and a head commit, the check exits non-zero and names the offending path when a PR modifies, deletes or renames away a frozen file (frozen = see Invariant), except for the allowed status-line transitions below. Must-fail cases include: editing the body of an `Accepted` ADR; editing any part of an ADR whose base status starts with `Superseded`; changing an `Accepted` ADR's status to anything other than `Superseded by ADR-NNNN…` (in particular `Accepted` → `Implemented` fails: ADRs have no implemented state); changing an `Accepted` ADR's status line *and* its body in the same PR; editing the body of an `accepted` proposal; changing an `accepted` proposal's status to `superseded`; editing an `implemented` or `withdrawn` proposal; editing the body of a `stable` spec; editing a `superseded` or `withdrawn` spec.
  It exits 0 when the PR: edits a `Proposed` ADR (including a status like `Proposed (… superseded by ADR-0019)`, i.e. ADR-0008); flips an ADR's status `Proposed` → `Accepted`; changes only the status line of an `Accepted` ADR to `Superseded by ADR-NNNN` (any text after that prefix allowed); moves proposal 0001 from `draft/` to `accepted/` while setting its status to `accepted` (the #6 ratification step); changes only the status line of an `accepted` proposal to `implemented` or `withdrawn`; edits a `draft` spec; flips a spec's status `draft` → `stable`; changes only the status line of a `stable` spec to `superseded` or `withdrawn`; adds a new spec file (e.g. `policy-gate/v2.md`); adds a new numbered ADR or proposal; or edits `adr/README.md`, `proposals/README.md` or `specs/README.md`.
  (b) **Links.** The check exits non-zero and names the file and the link when a tracked `.md` file has a relative link (inline `[t](path)`, image `![t](path)`, or reference definition `[t]: path`, with or without `#fragment`) whose target is not a tracked file or directory. It exits 0 when the only such links are external (`https:`, `mailto:` and other `scheme:` URLs), pure `#fragment` links, or links inside fenced code blocks or inline code.
  (c) The link check exits 0 on the nl-shell tree itself. Today there are 60 relative links and 0 broken. This test runs against the live checkout (the repo root found from the test file's location). That means `tests.yml` also fails when a broken link reaches the tree. This is intended: a code PR can only go red from it if main already has a broken link, which the docs job exists to stop. The test must work when `.git` is a file, i.e. in a git worktree, which is how the C4 gate runs it (`engine/scripts/run-verify.sh:118`). Use `git ls-files` run from the repo root; don't open `.git` directly.
  Every must-fail assertion also checks that the expected path or link appears in the output, so a missing or crashing script cannot satisfy it. The new workflow runs both checks on every PR. That part is checked by reading the patch and by the draft PR's own CI run (see Falsifiability), not by C4.
- **Falsifiability:** RED is available locally under the shipped C4 gate (`engine/scripts/run-verify.sh`). The gate reverts every changed path outside `tests/`, `docs/`, `.github/`, `.oss-scanner/` and `*.md`, then re-runs the named test file. So the check logic must live in a tracked, non-Markdown file **outside** those paths (e.g. `scripts/docs_checks.py`). If it lived only inside `.github/workflows/*.yml`, C4 would classify the patch as "no behavioral production change" and report PDCA-UNVERIFIABLE (exit 77). The tests must call the check as a subprocess (`sys.executable` plus the script path resolved from the test file's location), not import it at module level. On the red leg the reverted script is gone. An import would become a collection error (UNVERIFIABLE) instead of a real red, while a subprocess call fails cleanly. The "runs on every PR" half can only go red or green on GitHub: the draft PR this bundle opens runs the new workflow, and the human sees the result at sign-off. Optional: push a throwaway commit that touches ADR-0001 to show the job fail, then drop it.
- **Invariant to restore:** A design record that is frozen in a PR's **base** stays byte-identical at the PR's head, except for one allowed change: its frontmatter `status:` line moves to a listed next state. Every relative Markdown link in the tracked tree resolves to a tracked path. Frozen files and their allowed next states (matched case-insensitively on the base and head `status:` values):
  (i) `adr/NNNN-*.md`: frozen when the base status does not start with `Proposed`. From `Accepted`, the only allowed change is to `Superseded by ADR-NNNN…`. A status starting with `Superseded` has no next state. There is no `implemented` state for ADRs.
  (ii) `proposals/{draft,accepted}/NNNN-*.md`: frozen when the base status is not `draft`. From `accepted`, the allowed changes are `implemented` or `withdrawn`. `implemented` and `withdrawn` have no next state.
  (iii) `specs/**/*.md` (not `README.md`): frozen when the base status is not `draft`. From `stable`, the allowed changes are `superseded` or `withdrawn`. Those two have no next state.
  
  Sources: ADR-0001 Decision (`docs/design/adr/0001-record-architecture-decisions.md:18-23`); `docs/design/README.md` class table (specs "a stable version is never edited, only replaced by a new version" `:18`; ADRs "Append-only; superseded, never edited" `:20`; proposals "Draft → accepted → implemented; accepted records are immutable" `:21`); `docs/design/proposals/README.md:10-11`; the status vocabularies in `docs/design/templates/adr.md:4`, `proposal.md:4`, `spec.md:4`, which the allowed next states are taken from (maintainer decision 3 below).
- **Repo + branch target:** eduralph/nl-shell @ main
- **Ordering note:** Single-issue batch. PR #96 (`docs/ratification-rule`), which this brief used to note as open, is now merged into main (`bc25e56`). It added the "Building against Proposed ADRs" paragraph at `adr/README.md:17-20`. The opening paragraph this brief edits is still `:9-11`. No other open work touches these files.
- **Surfaces:** data
- **Difficulty:** medium — three new files plus one sentence in each of two indexes. But the workflow runs on every future nl-shell PR, so a wrong rule blocks unrelated work: a false fail on the #6 ratification move, on a Proposed ADR edit, or on an allowed status-line transition (e.g. a proposal going to `implemented`).
- **Scope:** Add:
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
- **Repro instruction:** On `eduralph/nl-shell` `main` (`bc25e56`), run `git switch -c demo && sed -i 's/^## Context/## Context (edited)/' docs/design/adr/0001-record-architecture-decisions.md && git commit -am demo`. No workflow or test fails, and `ls .github/workflows` shows no docs check. Likewise, changing `adr/README.md`'s link to `0001-record-architecture-decisions.md` into a missing filename goes unnoticed.
- **External dependencies:** none — git, Python 3.12+ and pytest are the base toolchain the gate already uses.
- **Test file:** tests/test_docs_checks.py
- **Citations expected:** Do must cite path:line on the target branch for every rule it encodes: ADR-0001 `:18-23`, the `docs/design/README.md` class table `:18-21`, `docs/design/proposals/README.md:10-11`, and the template status lines `docs/design/templates/{adr,proposal,spec}.md:4`. Peer callsite to mirror for the workflow's shape: `.github/workflows/tests.yml` (trigger, `permissions: contents: read`, checkout/setup-python steps). Use `pull_request`, **never** `pull_request_target`: that would run PR-supplied code with a write token. Reference port source: wyrd's `docs-immutability.yml`. This port follows its base-status, rename, diff-filter and status-only-supersession logic, extends the status-only rule to the transitions above, and drops the conformance-vector handling (`governing_spec_for`). Its spec rule is kept for spec Markdown files only.
- **Prior-art check (triage cycles):** merged history (`git -C ../nl-shell log origin/main -- .github/workflows docs/design/README.md docs/design/adr/README.md`): only the scaffold (`305d8a4`) and docs commits (latest `6a3c48a`, #96), no docs check. Open PRs: none touching these paths. Closed-unmerged PRs touching `.github/workflows/` or `scripts/`: none. `gh search issues` for `immutability` and `links`: only #7 itself. Result: nothing ahead.
- **Disposition hint:** likely-fix

## Decisions recorded at Plan

1. **Superseded ADRs are frozen** (maintainer, 2026-10-15). Never edited, the same as
   Accepted, including ADRs superseded while still Proposed. Scope item (2) writes this into
   the ADR index so the rule is stated in nl-shell's own docs.
2. **Specs are in scope** (maintainer, 2026-10-15, option a). Freeze any spec Markdown file whose base status isn't `draft`, using the same base-status rule. wyrd's conformance-vector rule is left out until nl-shell has vectors. All five specs are `draft` today, so the tests build stable specs in their throwaway repos.
3. **Status-line transitions on frozen files are allowed** (maintainer, 2026-10-15, plan-review revision, option A). A frozen file may change only its `status:` line, and only to a next state its template lists: ADR `Accepted` → `Superseded by ADR-NNNN`; proposal `accepted` → `implemented` / `withdrawn`; spec `stable` → `superseded` / `withdrawn`. **ADRs can never be implemented.** `implemented` is a proposal-only state, and an ADR status change to it fails.
4. **A partly superseded, still Proposed ADR stays editable** (Plan, 2026-10-15). ADR-0008 (`Proposed (backend order and VRAM budget superseded by ADR-0019)`) follows the starts-with-`Proposed` rule and can be edited in full, including its superseded section. Supersession of the decision is tracked in the index (`adr/README.md:33`).

## STOP discipline

Draft only until Check sign-off. Pushing to a feature/draft branch and opening a
draft PR MAY happen during the cycle (useful for CI feedback). The PR MUST NOT be
marked ready before sign-off accepts.

Plan-review response: all five findings are addressed in place. Lifecycle and template statuses are fixed by decision 3 (status-only transitions, none for ADRs to `implemented`). ADR-0008 is covered by decision 4 and the reworded README sentence. Criterion (c) running in `tests.yml` is stated as intended, with worktree-safe `git ls-files`. `docs/plan.md` is listed as out of scope.

## Split decision (sign-off of iteration 3, confirmed at Plan 2026-10-15)

Three build rounds showed this is two outcomes, not one. The freeze check converged (round-3
adversary and security review found nothing). The link checker did not converge: every round
turned up new CommonMark edge cases. This brief is therefore split into two children:

- **Child A — freeze check.** Scope items (1) as an immutability-only script
  `scripts/docs_checks.py`, (2), (3), (4) with only the immutability step, and (5) with only the
  immutability tests. Success criteria (a). Carry forward iteration-v3's immutability logic
  (`iteration-v3/patch.diff`, `scripts/docs_checks.py` up to `cmd_immutability`) and its tests,
  including the regressions from the iteration-1/2 carry-forwards (merge-base OR base-tip frozen
  status, rename-following between merge-base and base tip, byte-exact LF/CRLF comparison).
- **Child B — link check**, built after A (`Depends on` A). A separate script
  `scripts/docs_links.py` and test file `tests/test_docs_links.py`. It adds one step to A's
  `.github/workflows/docs-checks.yml` and does not touch `scripts/docs_checks.py`. Success
  criteria (b) and (c), with (b) judged against the deliberately simple rule below, not against
  CommonMark.

**Link rule for child B (maintainer decision 5, 2026-10-15).** The rule is applied in this order:
1. Remove `<!-- … -->` comments, even across lines. An unclosed `<!--` hides everything after
   it.
2. Remove fenced code. On each line, first strip leading whitespace, any `>` quote markers and
   one list marker (`-`, `*`, `+`, `1.`, `1)`). If the line then starts with 3+ backticks or
   tildes, a fence opens. It closes at the next line, stripped the same way, that starts with a
   run of the same character at least as long. An unclosed fence runs to the end of the file.
3. Remove inline code: a backtick run up to the next run of the same length within the same
   paragraph (no blank line in between). A backslash-escaped backtick does not open a span.
   An unmatched run is literal text.
4. Check what is left:
   - Inline and image links `[t](dest)` / `![t](dest)`. A backslash-escaped `[` does not start a
     link. Balanced parentheses in `dest` are allowed.
   - Reference definitions `[t]: dest` at any indentation, after any `>` markers, but not
     `[^…]:` footnotes.
   - Skip anything with a scheme (`https:`, `mailto:`, any `scheme:`) and pure `#…` links.
   - Strip the `#fragment`, undo backslash escapes, resolve relative to the file's directory, and
     require that the result is a tracked file or directory (`git ls-files`).

Known gaps, documented in the script's docstring and **not bugs**: indented (4-space) code blocks
are not recognized, so a link in one is checked; `<…>` destinations, link titles, and
percent-encoding are not handled; an unclosed `<!--` or fence masks the rest of the file; and
anything else CommonMark does that this rule doesn't. The live tree uses none of these today: 53
tracked `.md` files, all fences at column 0, no reference definitions, no `<…>`/`%`-encoded
links, and HTML comments only in `docs/design/templates/`. Round-3's open cases are resolved by
this rule as follows: a fence inside a comment is removed with the comment (step 1 runs first);
an unclosed `<!--` masks the rest (documented gap); a nested-list reference definition is
checked (any indentation); a fence on a list-marker line or inside a block quote is recognized
(step 2 strip); `\[x](missing.md)` is not a link (step 4).

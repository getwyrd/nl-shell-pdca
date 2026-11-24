<!-- pdca:split-proposal v1 -->
# Split proposal — issue 7

<!-- Each child is a COMPLETE brief, not a sketch. A filled Slug alone makes `state.state`
     classify the materialised file as PLANNED, so `pdca flow` skips Plan and sends it
     straight to Do — a child missing `Repo + branch target` then builds successfully and
     has nowhere to publish. Fill every field. -->

<!-- Delimiters are HTML comments, not headings, DELIBERATELY: each child body is a full
     draft brief and may contain arbitrary headings and fenced code blocks, so anything
     that could also appear inside a child cannot be its boundary. `pdca split --accept`
     parses these markers; keep them exactly as written. -->

## Why this slice is oversized

Issue #7 asks for two separate docs checks that share a workflow file and nothing else:

1. **A freeze check.** It compares a PR's base and head and fails when a frozen design
   record (Accepted/Superseded ADR, non-draft proposal, non-draft spec) changes in any way
   other than an allowed `status:` line move. Its inputs are two git refs and the
   frontmatter `status:` value. Its rules come from nl-shell's lifecycle docs.
2. **A link check.** It scans every tracked `.md` file and fails on a relative link whose
   target is not tracked. Its inputs are the Markdown text and `git ls-files`. Its rules
   are a Markdown parsing question, with no tie to lifecycles at all.

Each one fixes its own defect (a frozen doc can be edited and merge green; a broken link
can merge green), has its own success criterion ((a) vs (b)+(c) in the parent brief), its
own test and its own PR. They share no code.

Three build rounds already proved the seam in practice. The freeze check converged by
round 3 (adversary and security review found nothing). The link checker did not: each
round turned up new CommonMark edge cases, and every round re-built and re-reviewed the
finished freeze logic along with it. The maintainer confirmed this split at sign-off of
iteration 3 and set a fixed, deliberately simple link rule (decision 5) so the link child
has a finish line.

Two children is the right count. The freeze check's sub-parts (ADR rules, proposal rules,
spec rules, two index sentences, the workflow) all share one script, one base-vs-head diff
walk, and one test file; splitting them further would add cycles without making any piece
shippable on its own. The two index sentences belong with the freeze check because they
state in nl-shell's own docs the rule that check enforces.

## Wave sketch

- **Wave 1: child-1 (freeze check)** alone. It creates `scripts/docs_checks.py`,
  `tests/test_docs_checks.py`, the two index sentences, and
  `.github/workflows/docs-checks.yml` with one step.
- **Wave 2: child-2 (link check)**, `Depends on: child-1`. It adds a second step to the
  workflow file child-1 creates, so it must build on child-1's accepted result; built in
  parallel, both would create the same new file and collide. The dependency also puts
  them in different waves, so no separate `Conflicts with:` is needed.

The order also follows the risk. Child-1 is carry-forward work that already converged and
should ship fast. Child-2 is where the past rounds stalled; stacking it second means a
slow link check no longer holds back the freeze check.

An alternative the human may prefer: give child-2 its own workflow file
(`docs-links.yml`). Then the two children share no file, would be independent, and could
run in one wave. I did not propose that because the maintainer's split decision says child
B "adds one step to A's `.github/workflows/docs-checks.yml`", and one docs job is simpler
to make a required check later. If you switch, drop child-2's `Depends on:` line and
change its scope item (3).

<!-- pdca:child child-1 -->
# Brief — docs-checks-adr-immutability (split from issue 7, child-1)

> Plan artifact. Do reads ONLY this file. Milestone: **Foundations**. Builds on **ADR-0001**
> ("Once Accepted it MUST NOT be edited", `docs/design/adr/0001-record-architecture-decisions.md:22-23`;
> "A docs CI check enforces immutability (Foundations milestone)", same file `:30-31`).
> Threat-model inputs affected: none (a read-only CI job; no runtime code).
> Carry-forward: the parent bundle's `/home/eddie/nl-shell/nl-shell-pdca/results/issue_7/iteration-v3/patch.diff` holds a
> converged implementation of this check (`scripts/docs_checks.py` up to and including
> `cmd_immutability`, and the immutability tests in `tests/test_docs_checks.py`). Start from
> it; drop everything for link checking.

- **Slug:** docs-checks-adr-immutability
- **Defect / goal:** nl-shell's design docs declare Accepted ADRs and accepted proposals append-only (ADR-0001 `:22-23`; `docs/design/README.md` class table `:18-21`; `docs/design/proposals/README.md:10-11`), and stable spec versions are never edited (`docs/design/README.md:18`). ADR-0001 `:30-31` says a docs CI check enforces this, but none exists. `.github/workflows/` holds only `tests.yml`, `require-linked-issue.yml` and `triage-new-issue.yml`, so a PR can edit an Accepted ADR or a stable spec and still merge green. Port the freeze half of wyrd's docs CI (`getwyrd/wyrd` `.github/workflows/docs-immutability.yml`), adapted to nl-shell's rules below.
- **Success criterion:** A new pytest file `tests/test_docs_checks.py` runs the freeze check against throwaway git repos it builds in `tmp_path`. It passes with the fix and fails without it. Between a base and a head commit, the check exits non-zero **and names the offending path** when a PR modifies, deletes or renames away a frozen file (see Invariant), except for the allowed status-line moves.
  Must-fail cases include: editing the body of an `Accepted` ADR; editing any part of an ADR whose base status starts with `Superseded`; changing an `Accepted` ADR's status to anything other than `Superseded by ADR-NNNN…` (in particular `Accepted` → `Implemented` fails: ADRs have no implemented state); changing an `Accepted` ADR's status line *and* its body in the same PR; editing the body of an `accepted` proposal; changing an `accepted` proposal's status to `superseded`; editing an `implemented` or `withdrawn` proposal; editing the body of a `stable` spec; editing a `superseded` or `withdrawn` spec.
  Must-pass (exit 0) cases: editing a `Proposed` ADR (including a status like `Proposed (… superseded by ADR-0019)`, i.e. ADR-0008); flipping an ADR `Proposed` → `Accepted`; changing only the status line of an `Accepted` ADR to `Superseded by ADR-NNNN` (any text after that prefix); moving proposal 0001 from `draft/` to `accepted/` while setting its status to `accepted` (the #6 ratification step); changing only the status line of an `accepted` proposal to `implemented` or `withdrawn`; editing a `draft` spec; flipping a spec `draft` → `stable`; changing only the status line of a `stable` spec to `superseded` or `withdrawn`; adding a new spec file (e.g. `policy-gate/v2.md`); adding a new numbered ADR or proposal; editing `adr/README.md`, `proposals/README.md` or `specs/README.md`.
  Also keep the regressions carried forward from iterations 1–3: frozen status is taken from the merge-base OR the base tip (frozen in either counts); renames are followed between merge-base and base tip; comparison is byte-exact, so an LF→CRLF change on a frozen file fails.
  Every must-fail assertion also checks that the expected path appears in the output, so a missing or crashing script cannot satisfy it. The new workflow runs the check on every PR; that part is checked by reading the patch and by the draft PR's own CI run, not by C4.
  **Falsifiability:** the shipped C4 gate (`engine/scripts/run-verify.sh`) reverts every changed path outside `tests/`, `docs/`, `.github/`, `.oss-scanner/` and `*.md`, then re-runs the test file. So the logic must live in a tracked non-Markdown file outside those paths (`scripts/docs_checks.py`); logic only in the workflow YAML would give PDCA-UNVERIFIABLE (exit 77). Tests call the script as a subprocess (`sys.executable` plus a path resolved from the test file's location), never import it at module level — on the red leg the script is gone, and an import would become a collection error instead of a clean red. The "runs on every PR" half goes red/green only on GitHub, via the draft PR this bundle opens. Optional: push a throwaway commit touching ADR-0001 to show the job fail, then drop it.
  **Invariant to restore:** a design record frozen in a PR's **base** stays byte-identical at the head, except that its frontmatter `status:` line may move to a listed next state (matched case-insensitively):
  (i) `adr/NNNN-*.md`: frozen when the base status does not start with `Proposed`. From `Accepted`, only `Superseded by ADR-NNNN…` is allowed. A status starting with `Superseded` has no next state. ADRs have no `implemented` state.
  (ii) `proposals/{draft,accepted}/NNNN-*.md`: frozen when the base status is not `draft`. From `accepted`: `implemented` or `withdrawn`. Those two have no next state.
  (iii) `specs/**/*.md` (not `README.md`): frozen when the base status is not `draft`. From `stable`: `superseded` or `withdrawn`. Those two have no next state.
  Sources: ADR-0001 Decision `:18-23`; `docs/design/README.md` class table `:18-21`; `docs/design/proposals/README.md:10-11`; template status vocabularies `docs/design/templates/{adr,proposal,spec}.md:4`.
- **Repo + branch target:** eduralph/nl-shell @ main
- **Reproduction:** On `eduralph/nl-shell` `main` (`bc25e56`), run `git switch -c demo && sed -i 's/^## Context/## Context (edited)/' docs/design/adr/0001-record-architecture-decisions.md && git commit -am demo`. No workflow or test fails, and `ls .github/workflows` shows no docs check.
- **Scope (one logical fix) / out of scope:** Add:
  (1) `scripts/docs_checks.py`: stdlib-only Python, runnable from any git checkout's root, with one mode that takes a base and a head ref. No link-check mode.
  (2) One sentence in `docs/design/adr/README.md`'s opening paragraph (lines 9-11, after "a later ADR supersedes it, and this index records the supersession"): the only change ever allowed to an Accepted ADR is setting its status line to `Superseded by ADR-NNNN`; a Superseded ADR is never edited at all, including those superseded while still Proposed (0005-0007, 0011); an ADR only partly superseded and still Proposed (0008) stays editable like any Proposed ADR.
  (3) One sentence in `docs/design/proposals/README.md` after line 11: the only change allowed to an accepted proposal is setting its status line to `implemented` or `withdrawn`.
  (4) `.github/workflows/docs-checks.yml` on `pull_request` with **no path filter**, `permissions: contents: read`, `actions/checkout` with `fetch-depth: 0`, and one step running the freeze check with `${{ github.event.pull_request.base.sha }}` / `head.sha`. Mirror `.github/workflows/tests.yml` for trigger, permissions and checkout/setup-python. Use `pull_request`, **never** `pull_request_target`. Name the step so a second (link) step can be added after it later without restructuring.
  (5) `tests/test_docs_checks.py` (freeze tests only).
  Rules that differ from wyrd and must be kept:
  (r1) Status is read from the YAML frontmatter `status:` line, case-insensitive. Frozen-ness comes from the **base** side (merge-base or base tip, per the carry-forward).
  (r2) No frontmatter or no `status:` in the base → not frozen.
  (r3) README/index pages excluded. ADRs and proposals: only `NNNN-*.md`. Specs: every `.md` except `README.md`.
  (r4) A rename is checked at its old path.
  (r5) A frozen file passes only if base and head differ in exactly the `status:` line and the head value is an allowed next state. Removing, renaming, or changing any other line fails. The one exception is the proposal move `draft/` → `accepted/`, which applies only to a base status of `draft` (not frozen).
  (r6) wyrd allows a status-only change to Superseded; nl-shell keeps that and adds the other next states its templates list. Proposals have no `superseded` state (`proposals/README.md:10-11`); a proposal's supersession is recorded only in the index.
  Tests set their own git identity (git `-c` options or GIT_AUTHOR/GIT_COMMITTER env vars) and never rely on host git config (`tests/conftest.py:52-56` sets a temp HOME). Error output tells the author to supersede (new ADR/proposal/spec version plus an index entry) instead of editing.
  Cite `path:line` on the target branch for every rule encoded (ADR-0001 `:18-23`, `docs/design/README.md:18-21`, `docs/design/proposals/README.md:10-11`, `docs/design/templates/{adr,proposal,spec}.md:4`).
  / out of scope: **all link checking** (that is child-2); wyrd's conformance-vector rule (`governing_spec_for`; nl-shell has no vectors, so non-Markdown files under `specs/` are not checked); wyrd's `lint_docs.py` / `render_site.py`; `docs/plan.md` (frozen by a banner, not a `status:` field, `docs/plan.md:3`); making the job a required check (a repo setting for the human); editing template status comments, ADR-0001, or any doc other than the two index sentences; the harness's own `docs/INTEGRATION.md` T2 row.
  Decisions recorded at Plan (maintainer, 2026-10-15): Superseded ADRs are frozen, including ones superseded while Proposed; specs are in scope with the same base-status rule; status-line moves on frozen files are allowed only to template-listed next states, and ADRs can never be `implemented`; a partly superseded, still Proposed ADR (0008) stays fully editable.
- **External dependencies:** none
- **Test file:** tests/test_docs_checks.py
- **Difficulty:** medium
<!-- pdca:end child-1 -->

<!-- pdca:child child-2 -->
# Brief — docs-checks-internal-links (split from issue 7, child-2)

> Plan artifact. Do reads ONLY this file. Milestone: **Foundations**. Threat-model inputs
> affected: none (a read-only CI job; no runtime code).
> Builds on child-1 (`docs-checks-adr-immutability`): this child adds one step to the
> `.github/workflows/docs-checks.yml` that child-1 creates. It must not touch
> `scripts/docs_checks.py` or `tests/test_docs_checks.py`.
> Judge the parser against the **fixed link rule below**, not against CommonMark. The
> parent cycle ran three rounds chasing CommonMark edge cases; the maintainer ended that
> with decision 5. A case the rule handles "wrong" by CommonMark standards but exactly as
> the rule says is correct; a documented known gap is not a bug.

- **Slug:** docs-checks-internal-links
- **Defect / goal:** Nothing checks relative Markdown links in nl-shell. A PR can rename or delete a doc, or mistype a link target, and every workflow still passes. Repro: change `docs/design/adr/README.md`'s link to `0001-record-architecture-decisions.md` into a missing filename; nothing fails. Port the link half of wyrd's docs CI (`getwyrd/wyrd` `docs-check.yml`) as a separate script with the simple rule below.
- **Success criterion:** A new pytest file `tests/test_docs_links.py` passes with the fix and fails without it, and shows:
  (b) Against throwaway git repos built in `tmp_path`: the check exits non-zero **and names both the file and the link** when a tracked `.md` file has a relative link (inline `[t](path)`, image `![t](path)`, or reference definition `[t]: path`, with or without `#fragment`) whose target is not a tracked file or directory. It exits 0 when the only such links are external (`https:`, `mailto:`, any `scheme:`), pure `#fragment` links, or inside HTML comments, fenced code or inline code as the rule defines them. Include cases for each rule step, and for the round-3 cases with the outcomes listed under the rule.
  (c) The check exits 0 on the live nl-shell checkout (repo root found from the test file's location). At planning time there were 53 tracked `.md` files, 60 relative links, 0 broken. Because this test runs in `tests.yml` too, a broken link on main will turn code PRs red; that is intended. The test must work when `.git` is a file (a git worktree, which is how C4 runs it, `engine/scripts/run-verify.sh:118`): use `git ls-files` from the repo root; never open `.git` directly.
  Every must-fail assertion checks that the expected file and link appear in the output, so a missing or crashing script cannot satisfy it. The workflow step is checked by reading the patch and by the draft PR's CI run, not by C4.
  **Falsifiability:** C4 (`engine/scripts/run-verify.sh`) reverts changed paths outside `tests/`, `docs/`, `.github/`, `.oss-scanner/` and `*.md`, then re-runs the test file. The logic lives in `scripts/docs_links.py` (outside those paths) so the red leg is real. Tests call it as a subprocess (`sys.executable` plus a path resolved from the test file), never import it at module level, so the red leg fails cleanly rather than as a collection error.
  **Link rule (maintainer decision 5, 2026-10-15), applied in this order:**
  1. Remove `<!-- … -->` comments, even across lines. An unclosed `<!--` hides everything after it.
  2. Remove fenced code. On each line, first strip leading whitespace, any `>` quote markers and one list marker (`-`, `*`, `+`, `1.`, `1)`). If the line then starts with 3+ backticks or tildes, a fence opens. It closes at the next line, stripped the same way, that starts with a run of the same character at least as long. An unclosed fence runs to end of file.
  3. Remove inline code: a backtick run up to the next run of the same length within the same paragraph (no blank line between). A backslash-escaped backtick does not open a span. An unmatched run is literal text.
  4. Check what is left:
     - Inline and image links `[t](dest)` / `![t](dest)`. A backslash-escaped `[` does not start a link. Balanced parentheses in `dest` are allowed.
     - Reference definitions `[t]: dest` at any indentation, after any `>` markers, but not `[^…]:` footnotes.
     - Skip anything with a scheme and pure `#…` links.
     - Strip the `#fragment`, undo backslash escapes, resolve relative to the file's directory, and require a tracked file or directory (`git ls-files`).
  Round-3 cases and their required outcomes: a fence inside a comment is removed with the comment (step 1 runs first); an unclosed `<!--` masks the rest (documented gap); a nested-list reference definition is checked (any indentation); a fence on a list-marker line or inside a block quote is recognized (step 2 strip); `\[x](missing.md)` is not a link (step 4).
  **Known gaps, documented in the script's docstring, not bugs:** indented (4-space) code blocks are not recognized, so a link inside one is checked; `<…>` destinations, link titles and percent-encoding are not handled; an unclosed `<!--` or fence masks the rest of the file; anything else CommonMark does that this rule doesn't. The live tree uses none of these today (all fences at column 0, no reference definitions, no `<…>`/`%`-encoded links, HTML comments only in `docs/design/templates/`).
- **Repo + branch target:** eduralph/nl-shell @ main
- **Reproduction:** On `eduralph/nl-shell` `main`, edit `docs/design/adr/README.md` so its link to `0001-record-architecture-decisions.md` points at `0001-missing.md`, commit, and run the test suite and workflows: nothing fails, and no link check exists in `.github/workflows/`.
- **Scope (one logical fix) / out of scope:** Add:
  (1) `scripts/docs_links.py`: stdlib-only Python, runnable from any git checkout's root, scanning `git ls-files '*.md'` with the rule above; known gaps listed in its docstring.
  (2) `tests/test_docs_links.py`, setting its own git identity for throwaway repos (git `-c` or GIT_AUTHOR/GIT_COMMITTER env vars), never relying on host git config (`tests/conftest.py:52-56` sets a temp HOME).
  (3) One step in `.github/workflows/docs-checks.yml` (created by child-1) after the freeze step, running `scripts/docs_links.py`. Keep child-1's trigger (`pull_request`, no path filter), `permissions: contents: read` and checkout unchanged; never `pull_request_target`.
  The parent's `/home/eddie/nl-shell/nl-shell-pdca/results/issue_7/iteration-v3/patch.diff` has a link checker (`cmd_links` in `scripts/docs_checks.py`) and tests; reuse what fits the rule above, but move it to the new script and drop anything the rule does not call for.
  / out of scope: the freeze check, `scripts/docs_checks.py` and `tests/test_docs_checks.py` (child-1); checking `#fragment` anchors against headings; closing any listed known gap; full CommonMark conformance; wyrd's `lint_docs.py` / `render_site.py`; making the job a required check; editing any existing doc to fix links (there are none broken).
- **External dependencies:** none
- **Test file:** tests/test_docs_links.py
- **Difficulty:** medium
- **Depends on:** child-1
<!-- pdca:end child-2 -->

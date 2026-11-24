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
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (97 of 97 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — no security-relevant path touched
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review issue #7: enforce frozen design-record immutability and tracked Markdown link validity on every pull request, including the carried-forward rename and Markdown parsing fixes.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The freeze policy and permitted lifecycle transitions are defined, with the two iterations specifying concrete regressions; target/docs/design/adr/0001-record-architecture-decisions.md:22 and target/docs/design/README.md:18 ground the invariant. |
| C2 Reproduction (red pre-fix) | PASS | Captured execution shows all 97 assertions failing when the new checker is absent, rather than a collection failure; this establishes missing enforcement, not correctness of every parser case (gate-logs/C4-verify.log:15, gate-logs/C4-verify.log:1875). |
| C3 Change | PASS | The five changed paths stay within the approved checker, tests, workflow and index scope; the workflow runs on pull_request without a path filter and uses explicit base/head SHAs (target/.github/workflows/docs-checks.yml:8, target/.github/workflows/docs-checks.yml:27). |
| C4 Verification (red→green) | PASS | Frozen evidence records 97 failed without the checker and 97 passed with it; local pytest is unavailable, so this is log-adjudicated rather than independently reproduced; direct stdlib subprocess probes confirm body rejection and allowed supersession (gate-logs/C4-verify.log:13, gate-logs/C4-verify.log:1875; target/scripts/docs_checks.py:231). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Fix Markdown masking before relying on universal link enforcement: a fence inside an HTML comment hides a subsequent real broken link, while a fence opened after a list marker falsely rejects code examples; both reproduced with the actual CLI (target/scripts/docs_checks.py:413, target/scripts/docs_checks.py:504). |
| T1 Structure | PASS | The checker remains stdlib-only and separate from the shipped runtime, with subprocess tests exercising real Git repositories; target/scripts/docs_checks.py:24 and target/tests/test_docs_checks.py:62. |
| T2 Shape | PASS | The frozen threat-model scan reports no security-relevant path touched, consistent with the diff; workflow permissions are read-only and the event is pull_request (gate-logs/T2-threat-model.log:10; target/.github/workflows/docs-checks.yml:9). |
| T3 Runtime | PASS | The full-suite log records 132 passed; local execution stops because python3 has no pytest, not because of a patch failure (gate-logs/T3-suite.log:13). |
| T4 Contribution | N/A | Contribution artifacts are intentionally absent at Check; the substantive contribution audit must re-run at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm the recorded path-based prior-art search covers all affected paths and closed/rejected work: the brief reports merged and closed-unmerged searches, but this target has only one synthetic base commit and no captured remote search results, so independent confirmation is unavailable (brief.md:48; target/tests/test_docs_checks.py:1). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Confirm the real draft-PR docs job runs and its enforcement is acceptable before sign-off: GitHub execution was not exercised in this bundle, and local tests cannot establish event integration; also decide the explicitly reserved checker-ownership and up-to-date-branch policy (target/.github/workflows/docs-checks.yml:8, target/.github/workflows/docs-checks.yml:25; brief.md:63). |

Independent findings (target source grounded; no production files edited):

1. **Broken link hidden after an HTML comment.** A tracked `page.md` containing `<!--\n```\n-->\n[x](missing.md)\n` returns exit 0, `docs-links: OK (0 relative links checked)`. The code-block pass runs before comment masking, interprets the comment's fence marker as an unclosed fence, and removes the real link after the closing comment. Fix ordering/context handling and add a regression requiring exit 1 naming `missing.md`. Grounding: target/scripts/docs_checks.py:414 and target/scripts/docs_checks.py:504.
2. **Fenced code beginning on a list-marker line is checked as prose.** A tracked `page.md` containing `- ~~~\n  [x](missing.md)\n  ~~~\n` returns exit 1 and reports `page.md:2`. The opening fence is valid list-item content, but the parser only records the content column without parsing the remainder of that same line. Add a must-pass regression and handle that opening fence. Grounding: target/scripts/docs_checks.py:419.
3. **Additional reproduced false failures.** `> ~~~\n> [x](missing.md)\n> ~~~\n` returns exit 1 for code inside a block quote. Literal escaped-opening-bracket text `\[x](missing.md)` also returns exit 1 despite having no link. The former lacks block-quote container handling; the latter scans `](` without validating an opening bracket. Grounding: target/scripts/docs_checks.py:378 and target/scripts/docs_checks.py:511.

Verification limits and remaining decisions:

- Attempted `python3 -m pytest -q -p no:cacheprovider` against the disposable target; `/usr/bin/python3: No module named pytest`. Therefore no independent stash/red/unstash/green suite run was possible. Read the frozen C4, T2, T3 and deferred T4 logs instead. No missing-tool failure is attributed to the patch, and the gate logs demonstrate that pytest was present on the gate host.
- Direct CLI probes in scratch repositories inside this review directory independently rejected an Accepted ADR body edit (exit 1, offending path named) and accepted its status-only supersession (exit 0). Markdown probes likewise used tracked files and the actual checker subprocess, not substitute parsers.
- The brief records path-based prior-art checks over merged history and closed-unmerged PRs. `git -C target log --all -- .github/workflows scripts docs/design/adr/README.md docs/design/proposals/README.md` yields only the synthetic `cfebc9c` base. No INTEGRATION.md is supplied in the permitted evidence or target; any additional project human-only checklist cannot be independently enumerated here.
- For GitHub validation, inspect the draft PR's **Docs checks / docs** job and verify both named steps execute. If testing rejection on the draft branch, temporarily commit an edit to ADR-0001's body and verify the immutability step fails naming that path, then restore the intended patch before sign-off. Checker ownership/CODEOWNERS and stale-result policy remain maintainer calls, as the brief explicitly reserves them.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review: issue 7, docs-checks-adr-immutability-links (iteration 3)

I could not refute the immutability check. The link checker still has two concrete false passes: real broken links that it does not report. Both are small parser gaps, not design problems.

**Evidence.** pytest is not installed in this sandbox, so I could not re-run the suite. I used the frozen logs instead. `gate-logs/C4-verify.log` shows the red leg as 97 of 97 failed, with 0 collection or import errors. That is a real red: `tests/test_docs_checks.py:20-21` resolves `scripts/docs_checks.py` from the test file and runs it as a subprocess, so reverting the script turns every test red instead of breaking collection. The tests drive the shipped script, not a copy of it. The live link check also passes on the patched tree: `python3 scripts/docs_checks.py links` printed `OK (60 relative links checked)`, which matches brief (c).

## Findings

- NEEDS-HUMAN [impl] — `scripts/docs_checks.py:455-460`: an unclosed `<!--` in prose blanks out the rest of the file, so later broken links are never seen. When `find("-->")` fails, `end = n`. Concrete case: `case.md` = `Write <!-- to open.\n\n[x](missing3.md)\n` gives `docs-links: OK (0 relative links checked)` with exit 0. CommonMark treats an inline `<!--` with no closing `-->` as plain text, so `missing3.md` is a real broken link, and brief (b) says it must fail. Fix: if there is no closing `-->`, treat the `<!--` as plain text instead of masking to the end of the file. Only an HTML block that starts at the beginning of a line runs to the end of the document. Add a must-fail regression test.
- NEEDS-HUMAN [impl] — `scripts/docs_checks.py:363` (`REFDEF_RE = ^ {0,3}\[…`), used at `:529-534`: reference definitions are matched against raw line indentation, not indentation relative to the list item that contains them. A reference definition nested in a list item at column 4 or more is skipped. Concrete case: `1. a\n   - b\n\n     [r]: missing2.md\n` gives `OK (0 relative links checked)`, but `[r]: missing2.md` is a valid reference definition inside the nested item. This is the same container-column problem that iteration 2's carry-forward fixed for fences and indented code. It was not applied to reference definitions. Fix: measure the allowed 0-3 space indent from the content column that `mask_code_blocks` already tracks, and add a must-fail regression test.
- `scripts/docs_checks.py:293-295` (`renames_between`), non-blocking note: following renames on the base branch depends on git's default 50% similarity threshold for `-M`. I reproduced main ratifying a short 6-line proposal (git mv draft/ to accepted/ plus the status change). Git paired the files at only **R052**, just above the cutoff, so the PR's stale body edit was caught (exit 1). A slightly shorter file, or a ratification commit that also touches the body, would fall below 50%. The rename would then be missed, and the iteration-2 regression would come back silently. The real proposal 0001 is long, so this is not reachable today. Matching proposals by `NNNN` across `draft/` and `accepted/` would remove the dependence on similarity. I'm not raising this for routing.

## Immutability attacks I tried that did not break the check

- A frozen file replaced by a symlink (type change `T`): fails, because the blob bytes differ.
- Whitespace or comment-only edits to the status line (`Accepted` to `Accepted `): fails, because `allowed_next` rejects accepted to accepted.
- Status line moved, or an extra frontmatter key added: fails, because more than one line differs.
- A frozen record renamed or moved (accepted/ back to draft/): fails at the old path.
- Delete plus re-add with low similarity: fails as a deletion.
- Diverged history, with an ADR accepted on main after the PR branched: covered by tests at `tests/test_docs_checks.py:408-459`, which I read but could not run.
- Live statuses (`docs/design/{adr,proposals,specs}`): none is frozen by mistake. ADR-0008's `Proposed (…superseded by ADR-0019)` stays editable, all specs and proposal 0001 are `draft`, and 0005-0007 and 0011 are frozen as decision 1 requires.

## Link-parser cases I tried that are handled correctly

A link title (`"t"`), a link after a fence with an info string, a lazy fence that ends a list, a tab after a list marker followed by indented code (correctly treated as code, per CommonMark example 5), a fence inside a blockquote, an indented link in a blockquote, and a link inside an HTML block.

## Reviewer verdict

I found no unwarranted claim in `check-gates.json`. C4 "red without the fix (97 of 97 failed)" is backed by the log, and the failures are real assertion failures, not collection errors. T4 is deferred to publish, and the gate says so. Running the base copy of the script (a PR can edit `scripts/docs_checks.py` to weaken its own check) remains the maintainer's call, as recorded in the carry-forward. I did not re-file it.
<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory) — issue 7 / docs-checks-adr-immutability-links

**Attacker-reachable inputs touched: none.** The diff adds a CI (continuous integration) workflow, a stdlib-only docs-check script, its tests and two README edits. None of these touch the 11 untrusted inputs listed in `.oss-scanner/threat_model.md` ("Where untrusted input enters"). Nothing ships in the REPL, the policy gate, the PTY session, the model or the installer, and none of the "What must hold" properties depend on this code. The T2 gate agrees ("no security-relevant path touched", `gate-logs/T2-threat-model.log`).

The threat model does not cover CI, so I also checked the workflow against the usual GitHub Actions risks from a fork PR author. These checks are unrated because the threat model has no severity scale for CI:

- `.github/workflows/docs-checks.yml:9`: the trigger is `pull_request`, not `pull_request_target`, so fork PRs run without repo secrets. `:11-12` sets `permissions: contents: read`. This matches the existing `tests.yml:3-9` and `require-linked-issue.yml:11-16`.
- `.github/workflows/docs-checks.yml:27-29`: the only `${{ }}` values put into a shell `run:` line are `pull_request.base.sha` and `head.sha`. GitHub sets these to 40-character hex strings and the PR author can't control their text, so there is no script injection. No PR title, body or branch name is put into the script.
- `scripts/docs_checks.py:144-158`: every git call uses an argument list (`subprocess.run([...])`) with no shell. Paths from `git diff -z` only appear after a `rev:` prefix in `cat-file` arguments, so a crafted file name (spaces, `;`, a leading `-`, a newline) can't become a shell command or a git option.
- `scripts/docs_checks.py:555`: the links check opens tracked `.md` files and only prints link targets it parses out of them. A tracked symlink pointing outside the repo would let a PR print link-shaped strings from a runner file. That gives the attacker nothing, because a PR can already run any code it likes in this read-only job.
- The actions are pinned by tag (`actions/checkout@v4`, `actions/setup-python@v5`), not by commit SHA. The existing workflows do the same, so the patch adds no new risk here.

One integrity note, not a security finding: the workflow runs the PR's own copy of `scripts/docs_checks.py` (`docs-checks.yml:27,31`). A PR that edits a frozen ADR could also weaken the script in the same PR and still pass. That PR would show a visible change to `scripts/docs_checks.py`, and the comment at `docs-checks.yml:7` shows the choice was deliberate (running PR code without privileges is the safe trade-off). If maintainers want the check to resist this, they could run the script from the base commit, e.g. `git show BASE:scripts/docs_checks.py | python -`. That is a process choice, and I'm not raising it as a NEEDS-HUMAN item.

**No findings.** There are no NEEDS-HUMAN items from this review.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C5 Causal adequacy — Fix Markdown masking before relying on universal link enforcement: a fence inside an HTML comment hides a subsequent real broken link, while a fence opened after a list marker falsely rejects code examples; both reproduced with the actual CLI (target/scripts/docs_checks.py:413, target/scripts/docs_checks.py:504).
- [ ] T5 Judgment — Confirm the recorded path-based prior-art search covers all affected paths and closed/rejected work: the brief reports merged and closed-unmerged searches, but this target has only one synthetic base commit and no captured remote search results, so independent confirmation is unavailable (brief.md:48; target/tests/test_docs_checks.py:1).
- [ ] Validation — fitness-to-purpose — Confirm the real draft-PR docs job runs and its enforcement is acceptable before sign-off: GitHub execution was not exercised in this bundle, and local tests cannot establish event integration; also decide the explicitly reserved checker-ownership and up-to-date-branch policy (target/.github/workflows/docs-checks.yml:8, target/.github/workflows/docs-checks.yml:25; brief.md:63).
- [ ] `scripts/docs_checks.py:455-460`: an unclosed `<!--` in prose blanks out the rest of the file, so later broken links are never seen. When `find("-->")` fails, `end = n`. Concrete case: `case.md` = `Write <!-- to open.\n\n[x](missing3.md)\n` gives `docs-links: OK (0 relative links checked)` with exit 0. CommonMark treats an inline `<!--` with no closing `-->` as plain text, so `missing3.md` is a real broken link, and brief (b) says it must fail. Fix: if there is no closing `-->`, treat the `<!--` as plain text instead of masking to the end of the file. Only an HTML block that starts at the beginning of a line runs to the end of the document. Add a must-fail regression test.
- [ ] `scripts/docs_checks.py:363` (`REFDEF_RE = ^ {0,3}\[…`), used at `:529-534`: reference definitions are matched against raw line indentation, not indentation relative to the list item that contains them. A reference definition nested in a list item at column 4 or more is skipped. Concrete case: `1. a\n   - b\n\n     [r]: missing2.md\n` gives `OK (0 relative links checked)`, but `[r]: missing2.md` is a valid reference definition inside the nested item. This is the same container-column problem that iteration 2's carry-forward fixed for fences and indented code. It was not applied to reference definitions. Fix: measure the allowed 0-3 space indent from the content column that `mask_code_blocks` already tracks, and add a must-fail regression test.
- [ ] **The freeze rule blocks the documented proposal lifecycle (accepted → implemented).** The brief says a proposal "is editable only if its base status is exactly `draft`" (Scope) and adds "no supersession-stamp carve-out". The target defines the lifecycle as "Draft → accepted → implemented" (`docs/design/README.md:21`), and the template's status vocabulary is `draft | accepted | implemented | withdrawn` (`docs/design/templates/proposal.md:4`). With the brief's rule, setting an accepted proposal (0001 after #6) to `implemented` fails CI on every attempt, because the `implemented` state can only be reached by editing a frozen file. The Difficulty line names "a false fail on the #6 ratification move" as the main risk but misses this next step. The criterion's must-pass list needs a decision: either allow accepted→implemented as a status-only change, or record that the status stays `accepted` and the index tracks graduation.
- [ ] **The "no carve-out" rule is credited to sources that only partly support it, and it leaves template statuses unreachable.** The brief says nl-shell records supersession "in the index instead, per ADR-0001 and `proposals/README.md`". `proposals/README.md:10-11` does say that. ADR-0001 `:22-23` only says "the index records the supersession". It does not forbid stamping the file. The repo already stamps superseded files: `adr/0005…md:4` `status: Superseded by ADR-0013`, and likewise 0006, 0007 and 0011. The ADR template offers `Proposed | Accepted | Superseded by ADR-NNNN` (`templates/adr.md:4`), and the spec template offers `draft | stable | superseded | withdrawn` (`templates/spec.md:4`). Under the brief's rule, an Accepted ADR can never reach `Superseded by…`, and a stable spec can never reach `superseded` or `withdrawn`. Unlike the two decisions listed under "Decisions recorded at Plan", this one is not recorded as a maintainer decision. It needs one, and probably a matching template or README note, or the frozen files' frontmatter will contradict the index from then on.
- [ ] **Criterion (c) quietly adds a second enforcement point.** "The link check exits 0 on the nl-shell tree itself" as a pytest test means `tests.yml` (run on every PR and push to main, `.github/workflows/tests.yml:3-6`) also fails whenever any doc gains a broken link. The docs-check job is then no longer the only gate, and code PRs can go red because of docs-only drift. That may be intended, but the brief doesn't say so. The test also depends on the live tree and on `.git` being present. Here the checkout is a worktree (`target/.git` → `gitdir: …/worktrees/target`), so check that `git ls-files` works inside the C4 gate's reverted copy, or the green leg becomes environment-dependent.
- [ ] **Partially superseded ADRs: Decision 1 and the criterion are close to conflicting.** Decision 1 freezes ADRs "superseded while still Proposed". The criterion requires exit 0 when editing `Proposed (… superseded by ADR-0019)`, which is ADR-0008 (`adr/0008…md:4`). The index lists 0008 as "Proposed; backend order superseded by 0019" (`adr/README.md:33`), and the new sentence in scope (2) lists only 0005-0007 and 0011. This is probably intended (the starts-with-`Proposed` rule), but the maintainer should confirm that a partially superseded ADR stays fully editable, including its superseded section. Otherwise the new README sentence ("including one superseded while it was still Proposed") reads as covering 0008 too.
- [ ] **A frozen document outside the invariant is ignored.** `docs/design/README.md:75` calls `docs/plan.md` "kept for history and frozen" (`specs/README.md:22` says the same: "the frozen `docs/plan.md`"). The brief's invariant ("Any design record that is frozen…") covers only ADRs, proposals and specs, and does not list `plan.md` as out of scope. Either add it (a fixed-path freeze) or list it under out of scope, so Check doesn't flag it as a gap.
- [ ] size backstop — this slice is behaving oversized: 2 round(s) already spent (threshold 2). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: iterated-to-Plan
- Iteration delta (if iterating): Split this slice in two; the work is wanted, the slicing was wrong. After 3 rounds the freeze check holds up (adversary + security found nothing), but every round surfaces new Markdown-parser edge cases in the link checker. - Slice A: immutability (freeze) check + the two index README sentences + the docs-checks workflow. Essentially ready; carry the current docs_checks.py immutability logic and its tests forward. - Slice B: link check. Re-plan with an explicit decision on how much Markdown it must understand (e.g. a deliberately simple rule — strip fenced/inline code and HTML comments, check the rest — with documented known gaps) instead of chasing full CommonMark. Open reproduced cases from round 3: fence inside <!-- --> hides a later broken link; unclosed inline <!-- masks the rest of the file; nested-list reference definition skipped; false fails for a fence opened on a list-marker line, a fence inside a block quote, and escaped \[x](missing.md).
- By / date: Eduard Ralph / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 5 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

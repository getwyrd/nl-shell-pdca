# Result — issue 97 / docs-checks-adr-immutability

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: 
- Success criterion: A new pytest file `tests/test_docs_checks.py` runs the freeze check against throwaway git repos it builds in `tmp_path`. It passes with the fix and fails without it. Between a base and a head commit, the check exits non-zero **and names the offending path** when a PR modifies, deletes or renames away a frozen file (see Invariant), except for the allowed status-line moves.
  Must-fail cases include: editing the body of an `Accepted` ADR; editing any part of an ADR whose base status starts with `Superseded`; changing an `Accepted` ADR's status to anything other than `Superseded by ADR-NNNN…` (in particular `Accepted` → `Implemented` fails: ADRs have no implemented state); changing an `Accepted` ADR's status line *and* its body in the same PR; editing the body of an `accepted` proposal; changing an `accepted` proposal's status to `superseded`; editing an `implemented` or `withdrawn` proposal; editing the body of a `stable` spec; editing a `superseded` or `withdrawn` spec.
  Must-pass (exit 0) cases: editing a `Proposed` ADR (including a status like `Proposed (… superseded by ADR-0019)`, i.e. ADR-0008); flipping an ADR `Proposed` → `Accepted`; changing only the status line of an `Accepted` ADR to `Superseded by ADR-NNNN` (any text after that prefix); moving proposal 0001 from `draft/` to `accepted/` while setting its status to `accepted` (the #6 ratification step); changing only the status line of an `accepted` proposal to `implemented` or `withdrawn`; editing a `draft` spec; flipping a spec `draft` → `stable`; changing only the status line of a `stable` spec to `superseded` or `withdrawn`; adding a new spec file (e.g. `policy-gate/v2.md`); adding a new numbered ADR or proposal; editing `adr/README.md`, `proposals/README.md` or `specs/README.md`.
  Also must-pass: a new spec or proposal whose status line still carries the template comment (`status: draft   # draft | stable | superseded | withdrawn`) can be edited, and so can one with a quoted value (`status: "draft"`); a PR branched before main changed ADR X's status (Proposed → Accepted, or Accepted → Superseded by …), which does not touch X, exits 0.
  **Which commits are compared:** what the PR changed is the diff **merge-base → head** (`git merge-base <base> <head>`), never base tip → head. The base tip is used only to decide frozen status (a record frozen on the base after the PR branched off is frozen too) and to follow renames the base made after the merge-base.
  Also keep the regressions carried forward from iterations 1–3: frozen status is taken from the merge-base OR the base tip (frozen in either counts); renames are followed between merge-base and base tip; comparison is byte-exact, so an LF→CRLF change on a frozen file fails.
  Every must-fail assertion also checks that the expected path appears in the output, so a missing or crashing script cannot satisfy it. The new workflow runs the check on every PR; that part is checked by reading the patch and by the draft PR's own CI run, not by C4.
  **Falsifiability:** the shipped C4 gate (`engine/scripts/run-verify.sh`) reverts every changed path outside `tests/`, `docs/`, `.github/`, `.oss-scanner/` and `*.md`, then re-runs the test file. So the logic must live in a tracked non-Markdown file outside those paths (`scripts/docs_checks.py`); logic only in the workflow YAML would give PDCA-UNVERIFIABLE (exit 77). Tests call the script as a subprocess (`sys.executable` plus a path resolved from the test file's location), never import it at module level — on the red leg the script is gone, and an import would become a collection error instead of a clean red. The "runs on every PR" half goes red/green only on GitHub, via the draft PR this bundle opens. Optional: push a throwaway commit touching ADR-0001 to show the job fail, then drop it.
  **Invariant to restore:** a design record frozen in a PR's **base** stays byte-identical at the head, except that its frontmatter `status:` line may move to a listed next state (matched case-insensitively):
  (i) `adr/NNNN-*.md`: frozen when the base status does not start with `Proposed`. From `Accepted`, only `Superseded by ADR-NNNN…` is allowed. A status starting with `Superseded` has no next state. ADRs have no `implemented` state.
  (ii) `proposals/{draft,accepted}/NNNN-*.md`: frozen when the base status is not `draft`. From `accepted`: `implemented` or `withdrawn`. Those two have no next state.
  (iii) `specs/**/*.md` (not `README.md`): frozen when the base status is not `draft`. From `stable`: `superseded` or `withdrawn`. Those two have no next state.
  Sources: ADR-0001 Decision `:18-23`; `docs/design/README.md` class table `:18-21`; `docs/design/proposals/README.md:10-11`; template status vocabularies `docs/design/templates/{adr,proposal,spec}.md:4`.
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: 

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: Fixed
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (63 of 63 failed), green with it
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

Review adding a PR docs check that preserves frozen ADRs, proposals and specs while permitting explicitly allowed status transitions.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The missing enforcement and permitted transitions are falsifiable and bounded by the brief; the underlying immutability obligation is grounded at target/docs/design/adr/0001-record-architecture-decisions.md:22 and target/docs/design/README.md:18. |
| C2 Reproduction (red pre-fix) | PASS | Removing the checker reproduces the missing enforcement mechanism: independent stash run exits 2 for the absent script; the frozen regression run records 63 assertion failures, not collection errors (review-evidence/direct-checks.json:18; gate-logs/C4-verify.log:1144). |
| C3 Change | PASS | The five affected files stay within the specified enforcement, tests and index-clarification scope; PR-only execution with full history matches the intended comparison context (target/.github/workflows/docs-checks.yml:8; target/scripts/docs_checks.py:291). |
| C4 Verification (red→green) | PASS | Frozen evidence demonstrates 63 failures without production logic and 63 passes with it; independent stash/restore checks reject a body edit with its path and accept a status-only supersession; full pytest rerun unavailable locally because pytest is absent (gate-logs/C4-verify.log:12; gate-logs/C4-verify.log:1144; review-evidence/direct-checks.json:25). |
| C5 Causal adequacy | PASS | Enforcement addresses the missing check directly, without a capability guard; merge-base change selection, both-base frozen status and exact-byte comparison cover the stated cause and divergence regressions (target/scripts/docs_checks.py:226; target/scripts/docs_checks.py:269; target/scripts/docs_checks.py:297). |
| T1 Structure | PASS | Git inspection and record policy remain in a standalone stdlib script outside the shipped runtime, with subprocess regressions independent of importing the implementation (target/scripts/docs_checks.py:21; target/tests/test_docs_checks.py:20). |
| T2 Shape | PASS | Read-only PR permissions and the narrow affected paths support the recorded no-security-relevant-path verdict; no runtime threat-model surface changes were found (target/.github/workflows/docs-checks.yml:11; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | The captured full-suite run reports 98 passing tests; this is log-supported evidence, not an independently repeated suite run, because local python3 lacks pytest (gate-logs/T3-suite.log:10). |
| T4 Contribution | N/A | Contribution artifacts are intentionally not drafted at Check; the substantive contribution audit must run at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art against merged history and closed/rejected work, and any INTEGRATION.md §4 human-only obligations — the provided target has one synthetic base commit, no remote and no INTEGRATION.md, so those checks cannot be settled from this bundle (target/AGENTS.md:22; brief.md:49). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Confirm the recorded policy choices and successful real GitHub PR execution before sign-off — local Git tests establish checker behavior but no supplied evidence exercises the hosted workflow, and the Plan decisions lack a tracker confirmation (brief.md:55; target/.github/workflows/docs-checks.yml:25). |

Independent review evidence: `review-evidence/direct-checks.json` records an Accepted ADR body edit rejected with exit 1 and its offending path, an allowed supersession accepted with exit 0, the absent-checker red leg with exit 2, and the same successful behavior after restoring the stash. The supplied target patch was restored; `git diff --check` passed. No implementation defect was established.

The full C4 and T3 results above rely on the supplied gate logs. The instance-scoped gate wrappers are not part of this target; their absence is expected. The local pytest absence is a reviewer-host limitation, not evidence of a patch defect or of a failed original gate. These fixtures use real Git and Python, with no tool aliases or shims.

Prior-art investigation: `git log --all -- <each of the five affected paths>` returned only `da251c7 pre-fix base bc25e566af42c8d63071e9f1866a065063bb04e6`; `git remote -v` returned nothing. No closed/rejected-work evidence or INTEGRATION.md was supplied. This is an evidence limitation, not stale-target failure.

For hosted validation, open the draft PR and inspect the **Docs checks / docs** job on a `pull_request` run. Confirm it passes the normal patch. On a disposable PR branch, change the body of Accepted ADR-0001 and confirm that job fails naming `docs/design/adr/0001-record-architecture-decisions.md`. The maintainer must also confirm the Plan's frozen-state and allowed-transition policy; making the job required remains a separate repository-setting decision outside this patch.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — docs-checks-adr-immutability

**Overall: I could not refute the core fix.** The red→green proof is real, and the brief's must-fail and must-pass cases all hold. What I found are gaps at the edges plus one design-level bypass. None of them blocks this bundle.

## Things I tried to refute and could not

- **The evidence (`gate-logs/C4-verify.log`).** The red leg is a clean red: 63 of 63 tests fail with 0 collection errors. The tests run the real `scripts/docs_checks.py` as a subprocess (`target/tests/test_docs_checks.py`, `run_check`), not a copy of its logic. Every must-fail case checks for exit 1, the offending path in stdout, and the word "supersede". A missing or crashing script exits 2 with no path, so it cannot pass these by accident.
- **Brief coverage.** Each listed must-fail and must-pass case has its own scenario, including Accepted→Implemented, status plus body changed together, ADR-0008-style `Proposed (… superseded …)`, template comments, quoted values, diverged branches, and CRLF.
- **Inputs I checked against `target/scripts/docs_checks.py` (the first I ran; the rest are from reading the code):**
  - Accepted→Implemented fails, as it should.
  - Rename, move and delete of a frozen file fail. `check_record` keeps the old path (`scripts/docs_checks.py:267`), and `compare` fails when the head path differs (`:209-212`).
  - A type change (file to symlink) shows up as letter `T`, so it should reach the byte comparison and fail. I did not run this one.
  - A PR that merges main into itself is handled, because the diff starts at the merge-base (`:297`, `:302`).

## Findings

- NEEDS-HUMAN [human] — `.github/workflows/docs-checks.yml:26-29` runs `python scripts/docs_checks.py` from the PR's own checkout. **Failing case:** one PR edits the body of ADR-0001 and also changes `scripts/docs_checks.py` so `main()` returns 0. The job goes green and the frozen ADR is edited. The brief requires `pull_request` (not `pull_request_target`), which is the right call for safety, but it means the PR controls the checker. One option: run the base commit's copy (`git show "$BASE:scripts/docs_checks.py" | python - immutability …`), with a fallback for the PR that first adds the script. Another option: make `scripts/docs_checks.py` and the workflow CODEOWNERS-protected. Either way this is a design decision, and the brief did not ask for it.
- NEEDS-HUMAN [human] — `scripts/docs_checks.py:37` / `:59-60` lets any text follow `Superseded by ADR-NNNN` on the status line, as the brief asks ("any text after that prefix"). **Case I ran:** an Accepted ADR changed to `status: Superseded by ADR-0002; actually we now decide Y instead of X` exits 0. So a status-only PR can still rewrite the decision in one frontmatter line. If the human wants that closed, a tighter pattern like `^superseded by adr-\d{4}(?:\s*(?:,|and)\s*adr-\d{4})*\s*$` would still allow ADR-0007's real `Superseded by ADR-0016 and ADR-0017`.
- NEEDS-HUMAN [impl] — `scripts/docs_checks.py:117` (`status_line_index`) only sees frontmatter when the first line is exactly `---`. A file saved with a UTF-8 BOM (byte-order mark, the invisible `EF BB BF` prefix some Windows editors add) has first line `﻿---`, so it is read as having no frontmatter and is never frozen. **Case I ran:** an Accepted ADR with a BOM, body edited, exits 0. No current record has a BOM (ADR-0001 starts with `2d2d2d`), so this matters only for future files. The fix is small: strip a leading `﻿` in `line_text`, or decode with `utf-8-sig` for line 0, and add a test.
- NEEDS-HUMAN [impl] — `scripts/docs_checks.py:56-57` (`AdrClass.frozen`) treats an empty value (`status:` with nothing after it) as frozen, because `""` does not start with `proposed`. **Case I ran:** an ADR with a blank `status:` and an edited body exits 1. Rule r2 says a missing status means not frozen, and a blank value is closer to "missing" than to "Accepted". This only produces a false failure, and the ADR template ships `status: Proposed` (`docs/design/templates/adr.md:4`). Low priority: either treat an empty value as not frozen or add a test that pins the current behaviour.
- Minor, no action needed: `status_line_index` (`:121-126`) uses the first `status:` key. YAML uses the last one. A frontmatter with `status: Proposed` followed by `status: Accepted` is treated as Proposed and stays editable (I ran it: exit 0). This is contrived, and no current record has a duplicate key.
- Unverifiable here: the brief says the "runs on every PR" half is checked only by the draft PR's own CI run. Nothing in `check-gates.json` shows that run yet (T4 is `deferred`). The human should confirm the `Docs checks / docs` job shows up on the draft PR and that a throwaway edit to ADR-0001 turns it red.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory) — docs-checks-adr-immutability

**Attacker-reachable inputs touched: none.** The patch adds a CI-only docs check (`scripts/docs_checks.py`, `.github/workflows/docs-checks.yml`), two index sentences and a test file. None of the 11 entry points in `.oss-scanner/threat_model.md` ("Where untrusted input enters": command output, file names, env, session state, model output, history, reader output, model socket, install artifacts, training data, dev teacher) reach this code, and it breaks none of the "What must hold" properties: nothing here runs in the REPL, gate, PTY, sudo path or installer. The T2 gate agrees (`gate-logs/T2-threat-model.log`: "no security-relevant path touched"). No findings are rated on the threat model's scale.

What I checked anyway, on the CI side:

- `.github/workflows/docs-checks.yml:9` uses `pull_request`, not `pull_request_target`, with `permissions: contents: read`. Fork PRs get no secrets and only a read-only token. No finding.
- `.github/workflows/docs-checks.yml:28-29` puts `${{ github.event.pull_request.base.sha }}` / `head.sha` straight into a `run:` line. These are 40-character hex SHAs that GitHub sets, not PR-author text like titles or branch names, so there's no script injection. No finding.
- `scripts/docs_checks.py:142-155` calls git with an argument list (no shell). Refs come from `rev-parse --verify` output, and blob specs are `"<rev>:<path>"`, so a file name that starts with `-` can't be read as an option. `scripts/docs_checks.py:166` uses `--name-status -z`, so names with newlines, quotes or tabs split correctly. No finding.
- Renames are checked at the old path, deletes fail, and the comparison is byte-exact (LF→CRLF fails). So a PR can't slip an edit past the check by moving or re-encoding a frozen file. The tests cover these cases, and C4 shows 63/63 red without the fix and green with it. No finding.

One note on how far the check's integrity goes (not a threat-model finding):

- NEEDS-HUMAN [human] — `.github/workflows/docs-checks.yml:27` runs `scripts/docs_checks.py` **from the PR head**, so a PR can turn off its own check. A PR that changes `scripts/docs_checks.py` so `main()` returns 0, and in the same PR edits the body of `docs/design/adr/0001-record-architecture-decisions.md`, will pass the job. This is the usual limit of a `pull_request` job, and the brief chose it on purpose (the workflow comment at `:7` says so). Fixing it means running the script as it exists at the base SHA (e.g. `git show "$BASE:scripts/docs_checks.py" | python - immutability …`, with a fallback for the first PR that adds it), or requiring CODEOWNERS review on `scripts/docs_checks.py` and the workflow. Either way, a human has to decide where this trust boundary sits, along with the already out-of-scope choice of making the job a required check. Until then, the check catches honest mistakes, not a determined PR author, and reviewers need to read changes to the script itself.

No other findings.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T5 Judgment — Confirm affected-path prior art against merged history and closed/rejected work, and any INTEGRATION.md §4 human-only obligations — the provided target has one synthetic base commit, no remote and no INTEGRATION.md, so those checks cannot be settled from this bundle (target/AGENTS.md:22; brief.md:49).
- [ ] Validation — fitness-to-purpose — Confirm the recorded policy choices and successful real GitHub PR execution before sign-off — local Git tests establish checker behavior but no supplied evidence exercises the hosted workflow, and the Plan decisions lack a tracker confirmation (brief.md:55; target/.github/workflows/docs-checks.yml:25).
- [ ] `.github/workflows/docs-checks.yml:26-29` runs `python scripts/docs_checks.py` from the PR's own checkout. **Failing case:** one PR edits the body of ADR-0001 and also changes `scripts/docs_checks.py` so `main()` returns 0. The job goes green and the frozen ADR is edited. The brief requires `pull_request` (not `pull_request_target`), which is the right call for safety, but it means the PR controls the checker. One option: run the base commit's copy (`git show "$BASE:scripts/docs_checks.py" | python - immutability …`), with a fallback for the PR that first adds the script. Another option: make `scripts/docs_checks.py` and the workflow CODEOWNERS-protected. Either way this is a design decision, and the brief did not ask for it.
- [ ] `scripts/docs_checks.py:37` / `:59-60` lets any text follow `Superseded by ADR-NNNN` on the status line, as the brief asks ("any text after that prefix"). **Case I ran:** an Accepted ADR changed to `status: Superseded by ADR-0002; actually we now decide Y instead of X` exits 0. So a status-only PR can still rewrite the decision in one frontmatter line. If the human wants that closed, a tighter pattern like `^superseded by adr-\d{4}(?:\s*(?:,|and)\s*adr-\d{4})*\s*$` would still allow ADR-0007's real `Superseded by ADR-0016 and ADR-0017`.
- [ ] `scripts/docs_checks.py:117` (`status_line_index`) only sees frontmatter when the first line is exactly `---`. A file saved with a UTF-8 BOM (byte-order mark, the invisible `EF BB BF` prefix some Windows editors add) has first line `﻿---`, so it is read as having no frontmatter and is never frozen. **Case I ran:** an Accepted ADR with a BOM, body edited, exits 0. No current record has a BOM (ADR-0001 starts with `2d2d2d`), so this matters only for future files. The fix is small: strip a leading `﻿` in `line_text`, or decode with `utf-8-sig` for line 0, and add a test.
- [ ] `scripts/docs_checks.py:56-57` (`AdrClass.frozen`) treats an empty value (`status:` with nothing after it) as frozen, because `""` does not start with `proposed`. **Case I ran:** an ADR with a blank `status:` and an edited body exits 1. Rule r2 says a missing status means not frozen, and a blank value is closer to "missing" than to "Accepted". This only produces a false failure, and the ADR template ships `status: Proposed` (`docs/design/templates/adr.md:4`). Low priority: either treat an empty value as not frozen or add a test that pins the current behaviour.
- [ ] `.github/workflows/docs-checks.yml:27` runs `scripts/docs_checks.py` **from the PR head**, so a PR can turn off its own check. A PR that changes `scripts/docs_checks.py` so `main()` returns 0, and in the same PR edits the body of `docs/design/adr/0001-record-architecture-decisions.md`, will pass the job. This is the usual limit of a `pull_request` job, and the brief chose it on purpose (the workflow comment at `:7` says so). Fixing it means running the script as it exists at the base SHA (e.g. `git show "$BASE:scripts/docs_checks.py" | python - immutability …`, with a fallback for the first PR that adds it), or requiring CODEOWNERS review on `scripts/docs_checks.py` and the workflow. Either way, a human has to decide where this trust boundary sits, along with the already out-of-scope choice of making the job a required check. Until then, the check catches honest mistakes, not a determined PR author, and reviewers need to read changes to the script itself.
- [ ] **No tracker record to check the brief against.** The cwd holds only `brief.md` (plus `.claude/`). There is no `notes.json`, no `sources/` and no `dependency-state.json`. So it cannot be shown that the "Decisions recorded at Plan (maintainer, 2026-10-15)" line (brief:43) or the split from issue 7 / child-1 match the thread. Those decisions are what make Superseded-while-Proposed ADRs (0005–0007, 0011) frozen and add the spec/proposal next states, which go beyond ADR-0001 `:22-23` ("Once Accepted it MUST NOT be edited"). The human should confirm them against the issue before sign-off.
- [x] **Which side the byte-for-byte comparison uses is not specified. A stale branch would then fail on a file it never touched.** brief:17 and brief:34 say frozen status comes from "merge-base OR the base tip". brief:20 and (r5) say "base and head differ in exactly the `status:` line", but never say which base the head is diffed against. Take a PR branched before main flips ADR X from Proposed to Accepted (or Accepted to Superseded), with the PR not touching X. Diffed against the base tip, X differs (head still has the old status), so the check fails an unrelated PR. The workflow passes `github.event.pull_request.base.sha`, which is the base *tip*, not the merge-base (brief:31). Do reads only this brief (brief:3), so it must say explicitly: diff merge-base→head to decide what the PR changed, and use the base tip only for frozen status and rename-following. It should also add a must-pass case: "branch predates a status change on main and does not touch the file → exit 0". The carry-forward may already handle this, but the brief does not make it verifiable.
- [x] **Status parsing ignores the YAML comments the templates actually ship.** `docs/design/templates/spec.md:4` is `status: draft   # draft | stable | superseded | withdrawn`, and `templates/proposal.md:4` is `status: draft   # draft | accepted | implemented | withdrawn`. A new spec or proposal copied verbatim keeps the comment. Rules (ii) and (iii) say "frozen when the base status is not `draft`" (exact match, unlike the ADR "starts with" rule). A literal implementation would therefore freeze a fresh draft and fail the next edit to it. Neither (r1) nor the must-pass list covers trailing `# …` comments or quoted values (`status: "draft"`). Add a must-pass case: "edit a draft spec/proposal whose status line still carries the template comment".
- [x] **Contradictory trigger instruction.** brief:31 says the workflow runs "on `pull_request`" and also "Mirror `.github/workflows/tests.yml` for trigger". But `tests.yml:3-6` triggers on `pull_request` **and** `push: branches: [main]`. On a push event, `github.event.pull_request.base.sha` / `head.sha` are empty, so a faithful mirror makes the job fail (or silently pass) on every push to main. Pick one: pull_request only, or mirror plus a guard.
- [x] **The carry-forward is an unverifiable out-of-bundle input that may encode superseded rules.** brief:3 says "Do reads ONLY this file", yet brief:7-10 tells Do to start from `/home/eddie/nl-shell/nl-shell-pdca/results/issue_7/iteration-v3/patch.diff`. That path is outside both the bundle and `$PDCA_TARGET` and cannot be checked from here. The brief also changes the rules compared with iterations 1–3: it adds the specs class, the explicit next-state tables, and "in particular `Accepted` → `Implemented` fails" (brief:15), which reads like a correction of earlier behaviour. If Do "starts from it", the stale rules may survive wherever the brief's test list does not pin them. Either list which carry-forward behaviours are known to change, or drop the instruction to start from that file.
- [x] **Reproduction base is unverifiable from the target.** brief:26 pins `main` at `bc25e56`, but the target checkout has no `.git`, so the SHA could not be resolved here. The rest of the defect is confirmed on the target. `.github/workflows/` holds only `tests.yml`, `require-linked-issue.yml` and `triage-new-issue.yml`. There is no `scripts/` directory. ADR-0001 `:30-31` promises the check. ADR-0001 `:4` is `status: Accepted`. All 5 specs are `draft` and proposal 0001 is `draft` (`proposals/draft/0001-implementation-arc.md:4`). The problem statement and root cause hold.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: iterated-to-Do
- Iteration delta (if iterating): Core freeze check is accepted as correct; rebuild to close two gaps found at Check, keeping everything else as is. 1. The workflow must not run the PR head's copy of scripts/docs_checks.py, because a PR can then disable its own check. Run the base commit's copy instead (e.g. `git show "$BASE:scripts/docs_checks.py" | python - immutability "$BASE" "$HEAD"`), with a fallback to the head copy only when the script does not exist at the base (the PR that first adds it). Keep `pull_request` (never `pull_request_target`) and read-only permissions. 2. A file starting with a UTF-8 BOM (EF BB BF) is read as having no frontmatter and is never frozen. Strip a leading BOM before frontmatter/status parsing, and add a must-fail test: an Accepted ADR saved with a BOM whose body is edited exits 1 and names the path. Leave unchanged: the "any text after `Superseded by ADR-NNNN`" rule (it matches the brief) and empty `status:` counting as frozen.
- By / date: Eduard Ralph / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 6 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

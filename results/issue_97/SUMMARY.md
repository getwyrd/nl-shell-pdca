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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (71 of 71 failed), green with it
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

Review the documentation immutability check and its isolated Python execution, preventing frozen-record edits and PR-supplied modules from bypassing CI.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The freeze policy and permitted transitions are explicit and testable; the authoritative immutability commitment is grounded at target/docs/design/adr/0001-record-architecture-decisions.md:22 and target/docs/design/README.md:18. |
| C2 Reproduction (red pre-fix) | PASS | Independently reproduced the current iteration's bypass: a real Git repository with an edited Accepted ADR and planted re.py returns success without isolation (review-replay.log:1); the full pre-feature test failure is also captured at gate-logs/C4-verify.log:1384. |
| C3 Change | PASS | The five affected files fit the authorized freeze-check scope; both CI execution branches isolate imports, and the regression tests cover the base-copy and bootstrap paths (target/.github/workflows/docs-checks.yml:39; target/tests/test_docs_checks.py:621). |
| C4 Verification (red→green) | PASS | Independent Python/Git replay changes the shadowing attack from exit 0 to exit 1 with the offending path, including isolated script execution (review-replay.log:1); frozen gate evidence records 71 green and 71 red tests without collection errors (gate-logs/C4-verify.log:12, :1384). |
| C5 Causal adequacy | PASS | Removing the checkout from Python's import search addresses the demonstrated execution takeover directly; no capability guard masks a load-time cause (target/.github/workflows/docs-checks.yml:28; review-replay.log:4). |
| T1 Structure | PASS | The stdlib checker remains outside the shipped runtime package, with Git access, status parsing and comparisons separated; tests exercise subprocess behavior (target/scripts/docs_checks.py:150, :205; target/tests/test_docs_checks.py:19). |
| T2 Shape | PASS | The workflow has an unfiltered pull_request trigger and read-only permissions, with isolated base-script execution; the frozen scanner reports no security-relevant path under its configured classification (target/.github/workflows/docs-checks.yml:8; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | The captured full-suite execution reports 106 passing tests; this is logged evidence, not a local suite rerun, because local Python lacks pytest (gate-logs/T3-suite.log:13). |
| T4 Contribution | N/A | Contribution artifacts are intentionally absent at Check; the substantive audit is deferred to the mandatory publish rerun (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art in merged history and closed/rejected work before accepting this approach — the supplied target has one synthetic base commit, no remote, and no tracker evidence, so that investigation cannot establish prior decisions (target/scripts/docs_checks.py:1; target/tests/test_docs_checks.py:1). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Confirm the recorded policy choices and observe the docs job on the actual draft PR — local shell execution does not establish GitHub event/ref wiring or repository enforcement; inspect the docs job for a clean PR and test an Accepted ADR body edit on a disposable PR, expecting failure naming its path (target/.github/workflows/docs-checks.yml:9, :33; target/docs/design/adr/README.md:11). |

Evidence and limits:

- Source citations above were checked against the supplied patched target. No stale-target condition was found. The target was not modified.
- Local `python3 -m pytest --version` reports `No module named pytest`; consequently no full-suite stash/red/unstash/green rerun was performed. The complete frozen gate logs were read instead. Their red leg removes the new checker and produces ordinary test failures, not collection failures. The independent iteration-specific replay uses the real installed Python and Git, with no substitute implementation or tool shim; its output is in `review-replay.log` and its repository is `review-replay/`.
- The replay demonstrated root-level module shadowing without `-I`, rejection with stdin execution under `-I`, and rejection with script execution under `-I`. It does not claim to reproduce GitHub Actions hosting. The brief lists no external dependencies, but its required draft-PR CI outcome is not present in the frozen evidence and remains part of validation.
- Affected-path history was queried for scripts/docs_checks.py, tests/test_docs_checks.py, .github/workflows/docs-checks.yml and both changed indexes. Only synthetic commit `3800ad7` was available; `git remote -v` returned no entries. No INTEGRATION.md is supplied, so additional project-specific human-only items cannot be enumerated from this bundle.
- The bootstrap fallback is explicitly authorized when the base lacks the checker; it is not a symptom guard. Editing the workflow itself remains the explicitly excluded repository-settings concern. No builder-fixable defect was established in this review.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — docs-checks-adr-immutability (iteration 3)

Result: I tried to refute the fix and could not. Nothing below needs a rebuild or a human decision.

## What I tried

- **The red→green evidence is real, but C4's red does not prove what this iteration changed.** C4 (`gate-logs/C4-verify.log`) went red 71/71 only because `scripts/docs_checks.py` was removed. C4 never reverts `.github/`, so it never tested a workflow without `-I`. I tested that by hand. In a copy of the target I took `-I` out of `.github/workflows/docs-checks.yml:39` and `:42` and re-ran the CI-step tests. `test_ci_step_ignores_a_stdlib_module_planted_by_the_pr` (`tests/test_docs_checks.py:621`) and `test_ci_step_fallback_ignores_a_module_planted_next_to_the_script` (`tests/test_docs_checks.py:640`) both went red: exit 0 with `docs-immutability: OK`, so the planted `re.py` took over. With `-I` back, all 71 tests pass on `$PDCA_TARGET`. The new tests run the real `run:` block taken from the workflow file (`tests/test_docs_checks.py:566-597`), not a copy of it. So they would catch someone dropping `-I` later.
- **Other ways a PR could change what the base script runs, under `-I`.** I put `sitecustomize.py` and `usercustomize.py` in the cwd and piped a script to `python -I -`. Neither ran, and `sys.path` had no `''` entry. With plain `python -`, `''` was first on the path. The script's `git` calls (`scripts/docs_checks.py:150-166`) use `cat-file blob` and `diff --name-status`. Neither applies `.gitattributes` filters or textconv (text conversion for diffs), and git config comes from `.git/config`, which a PR cannot change. So a PR-added `.gitattributes` cannot hide a change. I found no bypass.
- **Ways to change a frozen file without being caught.** I traced these through `compare`/`check_record` (`scripts/docs_checks.py:205-291`):
  - Swapping the file for a symlink shows up as a type change, and the blob differs, so it fails.
  - Swapping it for a directory shows up as `D`, so it fails.
  - Hiding a body edit behind a bare `\r` inside the status line fails. `bytes.splitlines` splits on `\r`, so more than one line differs.
  - Renaming past git's rename limit falls back to D+A. `D` fails.
  - Undecodable filenames raise an exception that is not caught, so the script exits non-zero.

  Every case fails, which is the safe direction.
- **End to end on the real repo.** I committed the patched target as the base, then made a head that edits the body of ADR-0001 (Accepted), appends a line to ADR-0005 (`Superseded by ADR-0013`) and appends a line to ADR-0008 (`Proposed (… superseded by ADR-0019)`). I ran the base copy the way CI does (`git show B:scripts/docs_checks.py | python -I - immutability B H`). It exited 1 and named 0001 and 0005, and it let 0008 through. That matches the brief.
- **The reviewer's verdict.** I found no claim in `check-gates.json` that the evidence doesn't support. C4 doesn't cover the `-I` change, but the mutation run above does.

Out of scope, so not filed: a PR editing `.github/workflows/docs-checks.yml` itself. The iteration-2 sign-off explicitly left that to repo settings.

No NEEDS-HUMAN findings.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Advisory security review — docs-checks-adr-immutability

Attacker-reachable inputs this diff touches: **none** (from the threat model's list). The patch adds a CI job (`.github/workflows/docs-checks.yml`), a standalone script (`scripts/docs_checks.py`), its tests, and two README edits. None of it is nl-shell runtime code. It never touches command output, the state block, the gate, the PTY, sudo passthrough, the model socket, history or the installer (`.oss-scanner/threat_model.md`, "Where untrusted input enters", items 1–11). The T2 gate agrees: `gate-logs/T2-threat-model.log` says "no security-relevant path touched".

**No finding.** To be sure the CI job itself can't be abused by the one party who controls its input (whoever opens the PR: file names, file contents, the PR branch), I checked:

- **Trigger and token:** `.github/workflows/docs-checks.yml:8-12` uses `pull_request` (never `pull_request_target`) with `permissions: contents: read`. A fork PR gets no secrets and only a read-only token, so PR code running there can't write to the repo.
- **Expression injection** (a `${{ }}` value pasted into a shell script, where crafted text becomes shell code): `docs-checks.yml:32-34` passes only `base.sha` and `head.sha` through `env:` and quotes them as `"$BASE"`/`"$HEAD"`. These are commit hashes, not text the PR author writes, such as a title or branch name. Nothing is pasted into `run:` directly.
- **Shell or argument injection via file names:** `scripts/docs_checks.py:149-163` runs `git` from an argument list (no shell). PR-controlled paths only ever show up inside a `rev:path` spec (`git_blob`, `:154`), so a file named `--output=x` or `$(…)` stays a single argument and is never read as an option. `changed_paths` (`:166-183`) reads `-z` output, so names with newlines or quotes split correctly.
- **The PR switching off its own check:** `docs-checks.yml:37-39` runs the base commit's copy of the script, and `python -I` keeps planted modules (a `re.py` in the checkout) off `sys.path`. The fallback to the PR's copy (`:41-42`) only runs when the base doesn't have the script yet. That's a one-time bootstrap, it's documented in the comments, and it's an integrity question for the docs process, not a threat-model property.
- **git running PR-supplied helpers:** the script runs `git diff --name-status`, `cat-file`, `merge-base` and `rev-parse` only. None of these run textconv or external diff drivers, so a PR's `.gitattributes` can't make git execute anything.
- **Resource use:** the work grows linearly with the number of changed paths and the blob sizes. A crafted PR can't make it hang beyond what GitHub's own job timeout allows.

Actions are pinned by tag (`actions/checkout@v4`, `actions/setup-python@v5`), not by commit SHA. The existing `tests.yml:16-17` does the same, and this job has a read-only token with no secrets. It's the repo's existing convention, not something this patch introduces, so I'm not filing it.

The patch's tests (`tests/test_docs_checks.py`) cover the check's logic. No security-relevant test is needed, because no runtime trust boundary changes.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] T5 Judgment — Confirm affected-path prior art in merged history and closed/rejected work before accepting this approach — the supplied target has one synthetic base commit, no remote, and no tracker evidence, so that investigation cannot establish prior decisions (target/scripts/docs_checks.py:1; target/tests/test_docs_checks.py:1).
- [x] Validation — fitness-to-purpose — Confirm the recorded policy choices and observe the docs job on the actual draft PR — local shell execution does not establish GitHub event/ref wiring or repository enforcement; inspect the docs job for a clean PR and test an Accepted ADR body edit on a disposable PR, expecting failure naming its path (target/.github/workflows/docs-checks.yml:9, :33; target/docs/design/adr/README.md:11).
- [x] **No tracker record to check the brief against.** The cwd holds only `brief.md` (plus `.claude/`). There is no `notes.json`, no `sources/` and no `dependency-state.json`. So it cannot be shown that the "Decisions recorded at Plan (maintainer, 2026-10-15)" line (brief:43) or the split from issue 7 / child-1 match the thread. Those decisions are what make Superseded-while-Proposed ADRs (0005–0007, 0011) frozen and add the spec/proposal next states, which go beyond ADR-0001 `:22-23` ("Once Accepted it MUST NOT be edited"). The human should confirm them against the issue before sign-off.
- [x] **Which side the byte-for-byte comparison uses is not specified. A stale branch would then fail on a file it never touched.** brief:17 and brief:34 say frozen status comes from "merge-base OR the base tip". brief:20 and (r5) say "base and head differ in exactly the `status:` line", but never say which base the head is diffed against. Take a PR branched before main flips ADR X from Proposed to Accepted (or Accepted to Superseded), with the PR not touching X. Diffed against the base tip, X differs (head still has the old status), so the check fails an unrelated PR. The workflow passes `github.event.pull_request.base.sha`, which is the base *tip*, not the merge-base (brief:31). Do reads only this brief (brief:3), so it must say explicitly: diff merge-base→head to decide what the PR changed, and use the base tip only for frozen status and rename-following. It should also add a must-pass case: "branch predates a status change on main and does not touch the file → exit 0". The carry-forward may already handle this, but the brief does not make it verifiable.
- [x] **Status parsing ignores the YAML comments the templates actually ship.** `docs/design/templates/spec.md:4` is `status: draft   # draft | stable | superseded | withdrawn`, and `templates/proposal.md:4` is `status: draft   # draft | accepted | implemented | withdrawn`. A new spec or proposal copied verbatim keeps the comment. Rules (ii) and (iii) say "frozen when the base status is not `draft`" (exact match, unlike the ADR "starts with" rule). A literal implementation would therefore freeze a fresh draft and fail the next edit to it. Neither (r1) nor the must-pass list covers trailing `# …` comments or quoted values (`status: "draft"`). Add a must-pass case: "edit a draft spec/proposal whose status line still carries the template comment".
- [x] **Contradictory trigger instruction.** brief:31 says the workflow runs "on `pull_request`" and also "Mirror `.github/workflows/tests.yml` for trigger". But `tests.yml:3-6` triggers on `pull_request` **and** `push: branches: [main]`. On a push event, `github.event.pull_request.base.sha` / `head.sha` are empty, so a faithful mirror makes the job fail (or silently pass) on every push to main. Pick one: pull_request only, or mirror plus a guard.
- [x] **The carry-forward is an unverifiable out-of-bundle input that may encode superseded rules.** brief:3 says "Do reads ONLY this file", yet brief:7-10 tells Do to start from `/home/eddie/nl-shell/nl-shell-pdca/results/issue_7/iteration-v3/patch.diff`. That path is outside both the bundle and `$PDCA_TARGET` and cannot be checked from here. The brief also changes the rules compared with iterations 1–3: it adds the specs class, the explicit next-state tables, and "in particular `Accepted` → `Implemented` fails" (brief:15), which reads like a correction of earlier behaviour. If Do "starts from it", the stale rules may survive wherever the brief's test list does not pin them. Either list which carry-forward behaviours are known to change, or drop the instruction to start from that file.
- [x] **Reproduction base is unverifiable from the target.** brief:26 pins `main` at `bc25e56`, but the target checkout has no `.git`, so the SHA could not be resolved here. The rest of the defect is confirmed on the target. `.github/workflows/` holds only `tests.yml`, `require-linked-issue.yml` and `triage-new-issue.yml`. There is no `scripts/` directory. ADR-0001 `:30-31` promises the check. ADR-0001 `:4` is `status: Accepted`. All 5 specs are `draft` and proposal 0001 is `draft` (`proposals/draft/0001-implementation-arc.md:4`). The problem statement and root cause hold.
- [x] size backstop — this slice is behaving oversized: 2 round(s) already spent (threshold 2). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.

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
- Plan advisory: 6 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

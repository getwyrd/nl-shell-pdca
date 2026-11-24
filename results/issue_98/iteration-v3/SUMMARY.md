# Result — issue 98 / docs-checks-internal-links

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: 
- Success criterion: A new pytest file `tests/test_docs_links.py` passes with the fix and fails without it, and shows:
  (b) Against throwaway git repos built in `tmp_path`: the check exits non-zero **and names both the file and the link** when a tracked `.md` file has a relative link (inline `[t](path)`, image `![t](path)`, or reference definition `[t]: path`, with or without `#fragment`) whose target is not a tracked file or directory. It exits 0 when the only such links are external (`https:`, `mailto:`, any `scheme:`), pure `#fragment` links, or inside HTML comments, fenced code or inline code as the rule defines them. At minimum, these cases (each a separate test or parametrize entry):
  must-fail (names file and link): a broken inline link; a broken image link; a broken reference definition `[t]: missing.md`; a broken link with a `#fragment` (`missing.md#x`); a broken reference definition in a nested list item; a broken link after an inline-code span that closes on the same line; a broken link whose `dest` has balanced parentheses (`missing(1).md`).
  must-pass: an external `https:` link and a `mailto:` link; a pure `#fragment` link; a valid link to a tracked file, to a tracked directory, and with a `#fragment` on a tracked file; a broken link inside `<!-- … -->` spanning lines; a broken link inside an unclosed `<!--` (rest of file masked); a broken link inside a fenced block (backticks, and tildes); a broken link inside a fence opened on a list-marker line and one inside a `>` block quote; a fence inside a comment (step 1 removes it, no stray fence opens); a broken link inside inline code (single and double backtick runs); `[^1]: missing.md` (footnote, skipped); `\[x](missing.md)` (escaped, not a link).
  The round-3 cases listed under the rule are in these lists.
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
- Repo + branch target: eduralph/nl-shell @ main (built in a later wave than #97: per `Depends on: 97` the driver folds #97's accepted patch into the wave's integration branch and verifies against it via `$PDCA_VERIFY_BASE`, `engine/scripts/run-verify.sh:51,64`, so `.github/workflows/docs-checks.yml` and its freeze step exist when this bundle builds)
- Scope (one logical fix) / out of scope: 

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: Fixed
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (39 of 39 failed), green with it
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

Review the relative Markdown link checker and CI step, including the fence, escape, paragraph, and reference-definition regression coverage requested in iteration 2.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The fixed parsing rule and explicit exclusions give a falsifiable scope; iteration 2 identifies concrete regression cases rather than requiring CommonMark conformance (brief.md:23; brief.md:59). |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing the production script made all 38 fixture invocations fail with missing-script exit 2; the frozen pytest red leg separately records 39 assertion failures and no collection errors (gate-logs/C4-verify.log:699; target/tests/test_docs_links.py:118). |
| C3 Change | PASS | Changes stay within the checker, its tests, and the existing workflow; the prerequisite freeze step remains intact and the link step follows it (target/.github/workflows/docs-checks.yml:32; target/.github/workflows/docs-checks.yml:47). |
| C4 Verification (red→green) | PASS | Independent direct execution passed 38 fixtures and the live scan; stash/restoration confirmed script absence causes red and restoration returns the live scan to green; frozen pytest evidence shows 39 green and 39 red (gate-logs/C4-verify.log:10; gate-logs/C4-verify.log:699). |
| C5 Causal adequacy | PASS | Checking tracked destinations addresses the missing validation directly; ordered masking and explicit destination checks implement the agreed rule without a capability probe masking a load-time cause (target/scripts/docs_links.py:243; target/scripts/docs_links.py:318). |
| T1 Structure | PASS | The checker is stdlib-only tooling outside the shipped package; subprocess fixtures isolate Git repositories and provide their own identity (target/scripts/docs_links.py:48; target/tests/test_docs_links.py:21; target/tests/test_docs_links.py:36). |
| T2 Shape | PASS | Read-only pull-request permissions and isolated Python execution are retained; the frozen threat-model scanner reports no security-relevant path touched (target/.github/workflows/docs-checks.yml:10; target/.github/workflows/docs-checks.yml:48; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen full-suite output reports 145 passing tests; independent execution confirms 60 relative links across 53 Markdown files with zero broken links; local pytest is unavailable, so full-suite confidence rests on the captured run (gate-logs/T3-suite.log:11; target/tests/test_docs_links.py:181). |
| T4 Contribution | N/A | Contribution artifacts are intentionally drafted after Check; their substantive audit is deferred to the mandatory publish rerun (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm prior-art review by affected path against merged history and closed/rejected work — this bundle exposes only a synthetic base commit and no closed-work evidence, so duplication or a previously rejected approach cannot be ruled out (target/scripts/docs_links.py:1; target/tests/test_docs_links.py:1; target/.github/workflows/docs-checks.yml:47). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Confirm that decision 5's deliberately limited syntax and making existing broken links fail code PRs are acceptable, and inspect the draft PR's docs job — local checks validate behavior but do not establish hosted workflow execution or maintainer acceptance (brief.md:19; brief.md:47; target/scripts/docs_links.py:32). |

Verification details:

- All source citations were grounded in the supplied `$PDCA_TARGET`, which contains the prerequisite workflow and the applied patch. No stale-target caveat was needed.
- Python 3 is available, but `python3 -m pytest --version` reports `No module named pytest`. The instance-scoped wrappers are not part of this bundle. C4, T2, T3, and T4 were adjudicated from their captured logs; this local host limitation is not a patch defect or an unmet dependency in the original gate run.
- Independently evaluated the test file's literal fixture data using the standard library, created Git-indexed fixture repositories inside this review sandbox, and invoked the actual checker with `python3 -I`. All 36 parametrized fixtures plus the escaped-destination and comment-ordering cases passed. The separate live checkout scan also passed. These direct checks supplement, rather than claim to reproduce, the pytest runner and its isolation fixtures.
- Stashed only `scripts/docs_links.py` with untracked files included, observed missing-script failures for all 38 fixture invocations, then restored the stash and reran the live scan successfully. The original patch remains restored. The red leg establishes the absence of the checker, not a pre-existing parser regression.
- `git diff --check` passed. A path-scoped `git log --all` for all three affected files returned only `6c27276 pre-fix base a972610a6ed1f9dc2c7571258120402d398a9f56`. No `INTEGRATION.md` was supplied, so additional project-specific human-only items could not be enumerated.
- For hosted validation, open the draft PR's Actions run, inspect the `Docs checks` workflow's `Relative links resolve` step, and confirm successful execution and zero broken links. No GUI behavior is changed.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — docs-checks-internal-links (iteration 3)

**What I re-ran:** the C4 red→green log is real. The red leg in `gate-logs/C4-verify.log` shows 39/39 failing with the script reverted, and the tests call the production `scripts/docs_links.py` as a subprocess, not a copy. pytest is not installed in my sandbox, so I ran every MUST_FAIL/MUST_PASS case from `tests/test_docs_links.py` straight against the script with the same pass/fail checks. The baseline is all green. Then I made 12 small deliberate breaks ("mutants") in the script to see whether any test notices. 9 were caught. 3 survive, listed below. All three are test gaps, not wrong behavior. The script gets each of those inputs right today.

- NEEDS-HUMAN [impl] — The "fence in a block quote" tests pass for the wrong reason. `scripts/docs_links.py:87` strips `>` markers before looking for a fence. If you replace that with `line.lstrip()`, every test still passes. Why: in `tests/test_docs_links.py:140` (`"> ```\n> [x](missing.md)\n> ```\n"`) and `:96`, the two `` ``` `` runs are on lines of the same paragraph, so step 3 (inline code) pairs them up and hides the link anyway. The fence code is never exercised. A case that does exercise it: `"> ```\n> [x](missing.md)\n> ````\n"` (closing run longer than the opener, so inline code can't pair the runs). It must pass. The real script gives rc=0, the mutant gives rc=1 and reports `missing.md`. This is the same kind of gap the iteration-1 sign-off asked to close ("so the stripped closing lines are tested"), and it is still open for the `>` case.
- NEEDS-HUMAN [impl] — The "at least as long" fence-close clause is only half tested. Changing `>=` to `==` at `scripts/docs_links.py:107` passes every test. The cases at `tests/test_docs_links.py:101` and `:148` only show that a *shorter* run does not close the fence. Nothing shows that a *longer* run does. A case that catches it, as must-fail: `"```\n[a](guide.md)\n````\n[y](after-longer.md)\n"`. The real script gives rc=1 and names `after-longer.md`. The `==` mutant never closes the fence, hides the rest of the file, and gives rc=0. The iteration-2 sign-off said each case "must go red if its rule clause is removed", and this half of the clause isn't covered.
- NEEDS-HUMAN [impl] — The rescan at `scripts/docs_links.py:185` (`i += 1  # rescan the link text too: [![img](a.png)](b) holds two links`) has no test. If you change it to skip past the outer link (`i = close + 1`), all tests still pass. The README badge pattern then goes unchecked: `"[![b](missing.png)](guide.md)\n"` gives rc=1 naming `missing.png` today and rc=0 under the mutant. Badges are common, so this case is worth adding as must-fail.
- `.github/workflows/docs-checks.yml:47` — the new step has no `if: ${{ !cancelled() }}`. If the freeze step fails, the link check is skipped, so a PR that both edits a frozen ADR and breaks a link only shows the first error. This is minor and the brief doesn't ask for it, so I'm not raising it as NEEDS-HUMAN.
- Not refutations (the rule allows them, or they are documented gaps): `"Some text\n[Note]: see below\n"` is reported as the broken link `see`, because `REFDEF_RE` (`scripts/docs_links.py:58`) matches any line in a paragraph, and decision 5 says "at any indentation" with no start-of-paragraph rule. `` Use `<!--` here. `` hides the rest of the file (step 1 runs first, and this is a documented gap). `[x](<guide.md>)` is reported (documented gap). `[x](missing.md 'tis fine` is reported (titles are recognized by their opening quote only, also documented). The iteration-1 prose fix holds: `See [x](missing.md for more.` is skipped.
- Things I tried that held up: the git-worktree case (only `git rev-parse` and `ls-files -z` are used), `../` escaping the repo root (reported), directory targets `./` and `../`, an empty `#` fragment, a fence closing line with an info string, link text that spans two lines, `\\[x](…)` (an escaped backslash before the bracket, so it is still a link), and footnote, fragment, title and paren handling (each mutant was caught by a test).

**Verdict:** I could not refute the fix itself. Every input I tried behaves as decision 5 says. The reviewer's pass verdict is fair on behavior. What doesn't hold is the claim from the iteration-1 and iteration-2 sign-offs that each rule clause is now pinned by a test that goes red without it: the three test gaps above remain, and each is a one-line test the builder can add.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory) — docs-checks-internal-links

Attacker-reachable inputs this diff touches: **none** under the threat model. The patch adds a CI-only link checker (`scripts/docs_links.py`), its tests, and one workflow step. None of it is nl-shell runtime code, so none of the threat model's "Where untrusted input enters" items (command output, file names in the shell, env, session state, model output, history, reader output, model socket, downloads, training data, dev teacher) reach it. The T2 gate agrees: `gate-logs/T2-threat-model.log` reports "no security-relevant path touched".

**Verdict: no attacker-reachable input touched; no finding.**

What I checked anyway, in case the CI job itself is the concern (none of these is rated, because the threat model doesn't cover CI):

- `.github/workflows/docs-checks.yml:46-48`: the new step runs on `pull_request` (not `pull_request_target`), with `permissions: contents: read`, no secrets, and `python -I` (isolated mode: the checkout is kept off `sys.path`, so a PR can't plant a fake `re.py`). The step runs the **PR's** copy of the script, unlike the freeze step, which runs the base copy. So a PR can turn off its own link check by editing the script. This is a hygiene check, not a protection boundary, the job is not a required check (out of scope per the brief), and the edit would show up in the diff. Not a finding.
- `scripts/docs_links.py:283`: `git` runs with a fixed argument list and no shell, so file names can't inject commands. `scripts/docs_links.py:308`: files are opened only from `git ls-files` output under the repo root. Link targets are only normalized and compared against a set (`posixpath.normpath`). They are never opened, so `../../etc/passwd`-style links can't read anything. A tracked symlink `.md` would be followed when opened, but in CI the PR author already runs their own code, so that adds nothing.
- Resource use: `matching_bracket` (`scripts/docs_links.py:189`, called at `:180` for every `[`) scans to the end of the paragraph when there is no `]`, so time grows with the square of the input. I measured it on the target copy: one paragraph of 5,000 `[` took 0.36 s, and 20,000 took 5.25 s. Inline-code matching (`find_run`, `:148`) stayed fast in the same test. Only a PR author can trigger this, and only against their own CI run (or a test run on a checkout that holds such a file). It falls outside the threat model's attackers and severity scale. I'm noting it for information only; it is not a NEEDS-HUMAN item.
- Tests: the patch is not security-relevant, so I don't require attacker-path tests. The tests set their own git identity and `GIT_CONFIG_NOSYSTEM`, and they don't depend on host config.

No findings.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] T5 Judgment — Confirm prior-art review by affected path against merged history and closed/rejected work — this bundle exposes only a synthetic base commit and no closed-work evidence, so duplication or a previously rejected approach cannot be ruled out (target/scripts/docs_links.py:1; target/tests/test_docs_links.py:1; target/.github/workflows/docs-checks.yml:47).
- [x] Validation — fitness-to-purpose — Confirm that decision 5's deliberately limited syntax and making existing broken links fail code PRs are acceptable, and inspect the draft PR's docs job — local checks validate behavior but do not establish hosted workflow execution or maintainer acceptance (brief.md:19; brief.md:47; target/scripts/docs_links.py:32).
- [ ] The "fence in a block quote" tests pass for the wrong reason. `scripts/docs_links.py:87` strips `>` markers before looking for a fence. If you replace that with `line.lstrip()`, every test still passes. Why: in `tests/test_docs_links.py:140` (`"> ```\n> [x](missing.md)\n> ```\n"`) and `:96`, the two `` ``` `` runs are on lines of the same paragraph, so step 3 (inline code) pairs them up and hides the link anyway. The fence code is never exercised. A case that does exercise it: `"> ```\n> [x](missing.md)\n> ````\n"` (closing run longer than the opener, so inline code can't pair the runs). It must pass. The real script gives rc=0, the mutant gives rc=1 and reports `missing.md`. This is the same kind of gap the iteration-1 sign-off asked to close ("so the stripped closing lines are tested"), and it is still open for the `>` case.
- [ ] The "at least as long" fence-close clause is only half tested. Changing `>=` to `==` at `scripts/docs_links.py:107` passes every test. The cases at `tests/test_docs_links.py:101` and `:148` only show that a *shorter* run does not close the fence. Nothing shows that a *longer* run does. A case that catches it, as must-fail: `"```\n[a](guide.md)\n````\n[y](after-longer.md)\n"`. The real script gives rc=1 and names `after-longer.md`. The `==` mutant never closes the fence, hides the rest of the file, and gives rc=0. The iteration-2 sign-off said each case "must go red if its rule clause is removed", and this half of the clause isn't covered.
- [ ] The rescan at `scripts/docs_links.py:185` (`i += 1  # rescan the link text too: [![img](a.png)](b) holds two links`) has no test. If you change it to skip past the outer link (`i = close + 1`), all tests still pass. The README badge pattern then goes unchecked: `"[![b](missing.png)](guide.md)\n"` gives rc=1 naming `missing.png` today and rc=0 under the mutant. Badges are common, so this case is worth adding as must-fail.
- [x] **The base is wrong for scope item (3): the prerequisite has not landed.** `dependency-state.json` lists `"97": {"declared": "Depends on", "state": "PLANNED"}`, so child-1 has not been built, let alone merged. The brief still targets `eduralph/nl-shell @ main` (brief l.31). Scope (3) adds "One step in `.github/workflows/docs-checks.yml` (created by child-1) after the freeze step" (l.36). That file does not exist on the target: `.github/workflows/` contains only `require-linked-issue.yml`, `triage-new-issue.yml` and `tests.yml`. If Do starts from `main` it has nothing to add a step to, and no "freeze step" to put it after. It would either have to invent child-1's workflow, which is a hidden second change that collides with #97, or drop (3). The brief needs one of two fixes: declare `Stacks on: 97` and target child-1's branch, or hold this bundle until #97 merges. "Depends on" against a PLANNED prereq with a `main` base will strand the run.
- [x] **The tracker record is missing from the bundle, so the problem framing and "maintainer decision 5" cannot be checked.** The sandbox has only `brief.md` and `dependency-state.json`. There is no `notes.json` and no `sources/`. The whole link rule (l.20–29) and the instruction to "judge the parser against the fixed link rule below, not against CommonMark" (l.8–11) rest on "maintainer decision 5, 2026-10-15" and "the parent cycle ran three rounds". I could not check either against a thread quote. A human should confirm that decision 5 says what l.20–30 encode, especially the deliberate gaps: unclosed `<!--` masks the rest of the file, 4-space indented code is not recognized. Those gaps define what counts as correct for every downstream Check.
- [x] **Do is pointed at an input outside the bundle.** l.37 says to reuse `cmd_links` from `/home/eddie/nl-shell/nl-shell-pdca/results/issue_7/iteration-v3/patch.diff`, but l.3 says "Do reads ONLY this file". That is an absolute host path to another run's artifact. It is not in the bundle or in `$PDCA_TARGET`, and Do may not be able to read it in its sandbox. The parent's code was also written during the three CommonMark rounds that decision 5 ended, so "reuse what fits" invites drift back toward CommonMark behaviour. Either copy the relevant excerpt into the bundle or drop the pointer. As written it is an unverifiable dependency.
- [x] **Live-tree claims could only be partly checked.** Without Bash I could not run `git ls-files` to confirm "53 tracked `.md` files, 60 relative links, 0 broken" (l.17). What I could check holds:
- [x] **Criterion (b)'s "cases for each rule step" is open-ended.** l.16 asks for "cases for each rule step, and for the round-3 cases". The round-3 cases (l.29) are listed concretely, but "each rule step" has no list. That leaves the Check reviewer to argue over coverage, and it reopens the edge-case chase l.8–11 is meant to close. A fix would be to list the minimum must-fail and must-pass cases per step, e.g. step 3 escaped backtick, step 3 unmatched run, step 4 balanced parens, step 4 `[^1]:` footnote skipped, the image link and the `#fragment`-stripped link. Then the success criterion becomes a checklist instead of a judgment call.
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
- Outcome: iterated-to-Do
- Iteration delta (if iterating): Keep scripts/docs_links.py, the workflow step and decision 5's rule exactly as they are; the behavior is correct. Only add the three tests the iteration-3 adversary review found missing (SUMMARY §6 items 3-5). Each must go red if its rule clause is removed from the script: 1. Fence inside a ">" block quote, closed by a longer run so inline code cannot pair the runs: "> ```\n> [x](missing.md)\n> ````\n" must PASS. It must fail if scripts/docs_links.py:87 strips only whitespace and not ">" markers. 2. A longer run closes a fence: "```\n[a](guide.md)\n````\n[y](after-longer.md)\n" must FAIL and name after-longer.md. It must fail if ">=" at scripts/docs_links.py:107 becomes "==". 3. Badge / nested link: "[![b](missing.png)](guide.md)\n" must FAIL and name missing.png. It must fail if the rescan at scripts/docs_links.py:185 skips past the outer link. Do not change anything else.
- By / date: Eduard Ralph / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 5 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

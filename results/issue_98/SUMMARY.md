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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (42 of 42 failed), green with it
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

Review adding the fixed-rule relative Markdown link check to nl-shell CI, including the three regression tests required by iteration 3.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The fixed parsing rule and explicit exclusions make success decidable, with three concrete regression obligations in the final carry-forward (brief.md:73; target/tests/test_docs_links.py:113). |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing the new production script makes all 39 parameterized cases fail; frozen pytest evidence separately records 42 assertion failures without collection errors (review-rerun.json:7; gate-logs/C4-verify.log:14). |
| C3 Change | PASS | The patch is limited to the separate link checker, its tests, and the CI step after the existing freeze check; the sibling freeze implementation is untouched (patch.diff:1; target/.github/workflows/docs-checks.yml:45). |
| C4 Verification (red→green) | PASS | Independent direct subprocess checks reproduced 39 failures without the script and 39 passes after restoration; the frozen gate records all 42 pytest cases green then red (review-rerun.json:1; gate-logs/C4-verify.log:10). |
| C5 Causal adequacy | PASS | Missing tracked destinations now produce actionable failures, and each requested quote-strip, longer-close, and nested-image mutation changes the expected result; no capability probe masks an eager cause (target/scripts/docs_links.py:313; target/tests/test_docs_links.py:113; review-mutations.json:1). |
| T1 Structure | PASS | The stdlib checker remains outside the shipped package, and subprocess tests exercise real temporary git repositories with explicit identity (target/scripts/docs_links.py:43; target/tests/test_docs_links.py:21; target/tests/test_docs_links.py:35). |
| T2 Shape | PASS | CI retains pull_request, read-only contents permission, and the existing checkout/freeze step; the frozen scanner reports no security-relevant path touched (target/.github/workflows/docs-checks.yml:9; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | The frozen suite log shows 148 passing tests; independent execution on this target reports 60 relative links in 53 Markdown files with zero broken (gate-logs/T3-suite.log:14; review-rerun.json:56; target/scripts/docs_links.py:287). |
| T4 Contribution | N/A | Contribution artifacts are intentionally absent at Check; the substantive contribution audit is deferred to its mandatory publish rerun (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art across merged history and closed/rejected work, and supply any applicable INTEGRATION.md §4 obligations — this target contains only one synthetic base commit, no remote, and no integration-policy file, so those checks cannot be established from the supplied evidence (target/AGENTS.md:24; patch.diff:1). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Confirm decision 5's deliberately limited parser remains suitable for documentation CI and confirm the draft PR workflow succeeds — executable parser checks pass, but the bundle contains no hosted workflow result and does not establish product acceptance (brief.md:12; target/scripts/docs_links.py:27; target/.github/workflows/docs-checks.yml:47). |

Independent evidence and limits:

- The supplied target is readable and contains the prerequisite freeze workflow. There is no stale-target caveat. Source citations above are grounded in that target; bundle and log citations identify supplied evidence.
- `/usr/bin/python3` is Python 3.14.4, but pytest is unavailable locally (`No module named pytest`). Accordingly, the full pytest verdicts rely on the actual captured C4 and T3 execution logs, not an asserted local suite rerun. The instance-scoped wrappers were not sought in other checkouts. The frozen evidence shows a real pytest run, not a substituted tool or an unmet external dependency.
- Independently extracted the 39 parameterized fixtures from the test source using the stdlib AST parser, created committed git fixtures inside this review root, and ran the real script via `python3 -I`. All 39 passed, all 39 failed while only the production script was stashed, and all 39 passed after stash restoration. This reproduces the new-check absence, not a claim that the old implementation misparsed links. The live scan also passed. Full results: `review-rerun.json`.
- Evaluated three temporary in-memory mutations of the production parser without editing the submitted code: removing quote stripping exposes `missing.md`; replacing `>=` with `==` hides `after-longer.md`; skipping nested-link rescanning hides `missing.png`. The original parser produces the expected results in all three cases. Full results: `review-mutations.json`.
- Ran `git diff --check` successfully. The target's submitted files were restored after the red leg. No implementation changes were made.
- Ran affected-path history inspection for `scripts/docs_links.py`, `tests/test_docs_links.py`, and `.github/workflows/docs-checks.yml`: only `ca7c4d3 pre-fix base a972610a6ed1f9dc2c7571258120402d398a9f56` is available; `git remote -v` is empty. No closed/rejected-work evidence or INTEGRATION.md is supplied. Prior-art confirmation therefore remains owed rather than being reported as completed.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — docs-checks-internal-links (iteration 4)

Short answer: I tried to refute this round and could not. The three tests the sign-off asked for exist, and each one goes red when its rule clause is broken. No NEEDS-HUMAN findings.

How I checked: the sandbox has no `pytest`, so I copied `$PDCA_TARGET` into my scratch folder and drove the test file's own case tables and test functions with a small stand-in runner (`tools/runner.py`, fake `pytest.mark.parametrize`). Baseline: all cases pass, including the live-checkout test. Then I mutated the script copy one clause at a time and re-ran:

- `scripts/docs_links.py:87`, stop stripping `>` markers (`rest = line.lstrip()`): only the new must-pass case `fence in a block quote closed by a longer run` (`tests/test_docs_links.py:159`) goes red. Sign-off item 1 is met, and the case is not passing by accident through inline-code pairing.
- `scripts/docs_links.py:107`, change `>=` to `==`: only the new must-fail case `after a longer closing run` (`tests/test_docs_links.py:114-117`) goes red. Item 2 is met.
- `scripts/docs_links.py:185`, jump past the outer link (`i = close + 1` after a match): only `image inside a link (badge)` (`tests/test_docs_links.py:119`) goes red. Item 3 is met.
- Earlier-round clauses still hold: making the close branch a no-op (`:108`) turns 6 cases red; not stripping the list marker (`:88`) turns 2 red; ignoring the fence character (`:106`) turns 1 red; dropping the footnote exclusion (`:256`) turns 1 red; dropping paren depth (`:227`) turns 17 red.
- C4 red leg (`gate-logs/C4-verify.log`): 42 of 42 tests fail with the script reverted, and they fail as assertion failures, not collection errors. That matches the subprocess design (`tests/test_docs_links.py:49-57`).

Other ways I tried to break it, all handled as decision 5 says, or listed as known gaps (`scripts/docs_links.py:32-40`):
- CRLF line endings: `\r` doesn't stop a fence from opening or closing, `REFDEF_RE`'s `\S+` excludes `\r`, and blank lines that are just `\r` still split paragraphs.
- Escaped backslash before a real link (`\\[x](missing.md)`) is still checked. `\![x](missing.md)` is still checked as a link, which matches CommonMark.
- An unbalanced outer bracket (`[a [b](missing.md)`) still finds the inner link.
- Inline code holding `]` inside link text (``[`]`](missing.md)``) is blanked first, so the link is still found.
- Non-ASCII file names: `git ls-files -z` avoids git's path quoting.

Scope: the patch touches only `scripts/docs_links.py`, `tests/test_docs_links.py` and one step in `.github/workflows/docs-checks.yml`. The workflow step adds no trigger, permission or checkout change. The line numbers the sign-off cites (87, 107, 185) still point at the same clauses, which suggests the script was left alone as asked. I could not diff it against `iteration-v3/` because that folder isn't among my inputs.

I don't see a claim in `check-gates.json` that goes beyond the evidence. My one caveat: my mutation runs used a stand-in runner, not pytest itself. The real pytest red→green result comes from the C4 log.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory) — docs-checks-internal-links

Attacker-reachable inputs this diff touches: **none** in the threat model's sense. The patch adds a CI/dev-only docs linter (`scripts/docs_links.py`), its tests, and one workflow step. None of it runs inside nl-shell, so it touches none of the eleven "Where untrusted input enters" items (`.oss-scanner/threat_model.md`) and none of the "What must hold" properties (gate, confirm, sudo password, control channel, output rendering). The T2 gate agrees: `gate-logs/T2-threat-model.log` says "no security-relevant path touched".

The only party who controls this code's input is a PR author, who writes the Markdown files the script reads. I checked what that author could do through this patch:

- **Workflow trust boundary** (`.github/workflows/docs-checks.yml:9-14,47-48`): the trigger is still `pull_request` (not `pull_request_target`), `permissions: contents: read` is unchanged, and checkout is unchanged. The new step runs `python -I` (isolated mode, so the PR checkout is not on `sys.path`), uses no `${{ }}` expressions in `run:`, and has no secrets in its env. A PR author can already run arbitrary code in this job and in `tests.yml`, so the new step gives them nothing new. No finding.
- **PR can switch off its own link check**: the step runs the PR's copy of `scripts/docs_links.py`, unlike the freeze step, which runs the base copy (`docs-checks.yml:26-43`). A PR could edit the script so it always passes. This is about docs quality, not a security property, and the brief scoped it this way. Not a finding; noting it so the difference from the freeze step is a known choice.
- **Path traversal** (`scripts/docs_links.py:318-320`): the link target is joined and `normpath`'d, then only looked up in in-memory sets built from `git ls-files`. Nothing is opened or stat'd based on a link destination, so `../../etc/passwd` just gets reported as broken. Files that do get opened (`:308`) come only from `git ls-files`. No finding.
- **Command injection** (`scripts/docs_links.py:281-284`): `git` is called with a fixed argv list, without `shell=True` and without any value taken from file contents. No finding.
- **Resource use** (`scripts/docs_links.py:54,75`): `COMMENT_RE` (`<!--.*?-->` with DOTALL) can go quadratic on a file full of unclosed `<!--`. Only a PR author can trigger it, it only slows a CI job they already control, and it has no runtime reach. No finding.
- **Escape bytes in output** (`scripts/docs_links.py:320-323`): a broken link's destination is printed as-is, so a crafted `[x](<ESC>]52;…)` would reach the terminal of a developer who runs the script locally on an untrusted checkout. The threat model's "Output rendering is filtered" property covers nl-shell's own PTY mirror, `:context` and `:history`, not developer tooling. Also, a developer running a repo's scripts already trusts that repo's code. Out of scope; no finding.
- **Tests**: they use throwaway repos in `tmp_path` with their own git identity and `GIT_CONFIG_NOSYSTEM=1`, and they never touch host git config (`tests/test_docs_links.py:22-28`). No security-relevant behavior is in play, so a friendly-path-only test gap does not apply here.

No findings. No NEEDS-HUMAN items.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] T5 Judgment — Confirm affected-path prior art across merged history and closed/rejected work, and supply any applicable INTEGRATION.md §4 obligations — this target contains only one synthetic base commit, no remote, and no integration-policy file, so those checks cannot be established from the supplied evidence (target/AGENTS.md:24; patch.diff:1).
- [x] Validation — fitness-to-purpose — Confirm decision 5's deliberately limited parser remains suitable for documentation CI and confirm the draft PR workflow succeeds — executable parser checks pass, but the bundle contains no hosted workflow result and does not establish product acceptance (brief.md:12; target/scripts/docs_links.py:27; target/.github/workflows/docs-checks.yml:47).
- [x] **The base is wrong for scope item (3): the prerequisite has not landed.** `dependency-state.json` lists `"97": {"declared": "Depends on", "state": "PLANNED"}`, so child-1 has not been built, let alone merged. The brief still targets `eduralph/nl-shell @ main` (brief l.31). Scope (3) adds "One step in `.github/workflows/docs-checks.yml` (created by child-1) after the freeze step" (l.36). That file does not exist on the target: `.github/workflows/` contains only `require-linked-issue.yml`, `triage-new-issue.yml` and `tests.yml`. If Do starts from `main` it has nothing to add a step to, and no "freeze step" to put it after. It would either have to invent child-1's workflow, which is a hidden second change that collides with #97, or drop (3). The brief needs one of two fixes: declare `Stacks on: 97` and target child-1's branch, or hold this bundle until #97 merges. "Depends on" against a PLANNED prereq with a `main` base will strand the run.
- [x] **The tracker record is missing from the bundle, so the problem framing and "maintainer decision 5" cannot be checked.** The sandbox has only `brief.md` and `dependency-state.json`. There is no `notes.json` and no `sources/`. The whole link rule (l.20–29) and the instruction to "judge the parser against the fixed link rule below, not against CommonMark" (l.8–11) rest on "maintainer decision 5, 2026-10-15" and "the parent cycle ran three rounds". I could not check either against a thread quote. A human should confirm that decision 5 says what l.20–30 encode, especially the deliberate gaps: unclosed `<!--` masks the rest of the file, 4-space indented code is not recognized. Those gaps define what counts as correct for every downstream Check.
- [x] **Do is pointed at an input outside the bundle.** l.37 says to reuse `cmd_links` from `/home/eddie/nl-shell/nl-shell-pdca/results/issue_7/iteration-v3/patch.diff`, but l.3 says "Do reads ONLY this file". That is an absolute host path to another run's artifact. It is not in the bundle or in `$PDCA_TARGET`, and Do may not be able to read it in its sandbox. The parent's code was also written during the three CommonMark rounds that decision 5 ended, so "reuse what fits" invites drift back toward CommonMark behaviour. Either copy the relevant excerpt into the bundle or drop the pointer. As written it is an unverifiable dependency.
- [x] **Live-tree claims could only be partly checked.** Without Bash I could not run `git ls-files` to confirm "53 tracked `.md` files, 60 relative links, 0 broken" (l.17). What I could check holds:
- [x] **Criterion (b)'s "cases for each rule step" is open-ended.** l.16 asks for "cases for each rule step, and for the round-3 cases". The round-3 cases (l.29) are listed concretely, but "each rule step" has no list. That leaves the Check reviewer to argue over coverage, and it reopens the edge-case chase l.8–11 is meant to close. A fix would be to list the minimum must-fail and must-pass cases per step, e.g. step 3 escaped backtick, step 3 unmatched run, step 4 balanced parens, step 4 `[^1]:` footnote skipped, the image link and the `#fragment`-stripped link. Then the success criterion becomes a checklist instead of a judgment call.
- [x] size backstop — this slice is behaving oversized: 3 round(s) already spent (threshold 2). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.

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
- Plan advisory: 5 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

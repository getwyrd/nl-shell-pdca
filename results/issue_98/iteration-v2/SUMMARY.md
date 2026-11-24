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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (32 of 32 failed), green with it
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

Add a tracked-Markdown relative-link CI check using the maintainer’s fixed parsing rule, including fence-closing and incomplete-link regressions.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The fixed rule and explicit known gaps make the acceptance boundary testable; required failure diagnostics distinguish broken links from scanner crashes (target/tests/test_docs_links.py:103; target/scripts/docs_links.py:8). |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing only the new scanner made all 32 case assertions fail with exit 2; the absent checker cannot enforce the required link policy (target/tests/test_docs_links.py:19; gate-logs/C4-verify.log:575). |
| C3 Change | PASS | The three affected paths stay within the authorized link-check scope; the freeze step, PR trigger and read-only permissions remain intact (target/.github/workflows/docs-checks.yml:10; target/.github/workflows/docs-checks.yml:32; target/.github/workflows/docs-checks.yml:47). |
| C4 Verification (red→green) | PASS | Independent stdlib subprocess replay reproduced 0/32 passing without the scanner and 32/32 after restoration; frozen pytest evidence separately records 32 green and 32 red, without collection errors (gate-logs/C4-verify.log:12; gate-logs/C4-verify.log:575; target/tests/test_docs_links.py:108). |
| C5 Causal adequacy | PASS | Missing link enforcement is addressed directly without capability probes; exercised cases detect links after all four fence closures and accept incomplete prose, satisfying the carried-forward concerns (target/tests/test_docs_links.py:83; target/tests/test_docs_links.py:133; target/scripts/docs_links.py:234). |
| T1 Structure | PASS | The checker remains a standalone stdlib build tool outside the shipped runtime, and subprocess tests resolve it from their own checkout (target/scripts/docs_links.py:46; target/tests/test_docs_links.py:18; target/CONTRIBUTING.md:43). |
| T2 Shape | PASS | The workflow retains the existing low-privilege execution boundary and isolated Python invocation; frozen threat-model evidence reports no security-relevant path touched (target/.github/workflows/docs-checks.yml:12; target/.github/workflows/docs-checks.yml:48; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | The frozen full-suite log establishes 138 passing tests; local scanner execution independently reports 60 relative links across 53 Markdown files with zero broken links, though local pytest is unavailable (gate-logs/T3-suite.log:13; target/scripts/docs_links.py:322). |
| T4 Contribution | N/A | Contribution artifacts are absent by design; the substantive contribution audit is deferred to the mandatory publish rerun (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art against merged history and closed/rejected work before sign-off — this copy exposes only one synthetic base commit and no remote, so the path-scoped history query cannot establish either history (target/.github/workflows/docs-checks.yml:47; target/scripts/docs_links.py:1; target/tests/test_docs_links.py:1). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Confirm decision 5’s parser limits and inspect the draft PR’s Docs checks and test-suite CI results — local behavior passes, but acceptance of deliberately incomplete Markdown coverage and hosted workflow execution remains owed (target/scripts/docs_links.py:32; target/.github/workflows/docs-checks.yml:47; brief.md:21; brief.md:47). |

Independent verification used real Git repositories created only inside this review sandbox. A standard-library runner extracted the supplied literal case data and exercised 31 fixture cases plus the live checkout, checking exit status and expected diagnostics. It stashed only `scripts/docs_links.py`, ran the red leg, restored the stash, and ran the green leg. This was an independent behavioral replay, not a pytest rerun; `/usr/bin/python3 -m pytest --version` reports that pytest is unavailable. The original patch state was restored. `git diff --check` passed.

The frozen C4 log shows failures caused by the intentionally absent scanner, followed by its aggregate red verdict; its earlier green leg records 32 passing tests. The frozen T3 log records an actual 138-test passing run. The instance-scoped wrappers are not available here; their captured logs supply the gate evidence. No unmet external dependency is declared in the brief, and the real Git/Python link-check dependencies were exercised locally. The existing freeze workflow is present in the supplied base, so no stale-target caveat applies.

The affected-path history investigation (`git log --all --oneline -- .github/workflows/docs-checks.yml scripts/docs_links.py tests/test_docs_links.py`) returned only `bfb6045 pre-fix base a972610a6ed1f9dc2c7571258120402d398a9f56`; `git remote -v` returned nothing. No closed/rejected-work evidence or INTEGRATION.md was supplied. This limits prior-art and project-specific human-only review, rather than demonstrating a patch defect.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — docs-checks-internal-links (iteration 2)

**Bottom line:** I could not break the fix against decision 5's rule. Both carry-forward items are fixed. But the tests still leave six rule clauses unguarded: each can be deleted or weakened and the whole test file stays green. That is the same kind of gap the sign-off sent back last round (the untested fence-close branch).

## What I checked

- **The red→green proof holds.** `gate-logs/C4-verify.log` shows all 32 tests failing with the script reverted and passing with it. Every test runs the real `scripts/docs_links.py` as a subprocess, and every must-fail case checks for `file:line: broken link: dest`. So a missing or crashing script can't pass. There is no copy of the logic inside the test file.
- **Both carry-forward items are fixed.**
  - Fence close: the four "after a closed fence" cases go red if the close branch at `scripts/docs_links.py:105` becomes a no-op.
  - Prose with no closing `)`: `parse_dest` (`scripts/docs_links.py:233-264`) now returns nothing when no `)` or title follows, and the prose must-pass case covers it.
- **Edge cases that behave as the rule says.** I ran each of these against the patched script in throwaway repos. None is a refutation.
  - A double backslash before a link (`\\[x](m.md)`) is still checked.
  - A ```` ```python ```` line inside a ```` ``` ```` fence closes the fence (the rule says "starts with a run of the same character").
  - `[1]: see the docs` is read as a reference definition pointing at `see` (the rule allows any indentation).
  - `[x](m.md (as noted` is read as a link with a title. The sign-off explicitly allowed `(` as a title opener.
  - `<guide.md>` destinations are a documented known gap.

## Findings

- NEEDS-HUMAN [impl] — Six rule clauses have no test. I applied each change below to a copy of the script and ran every case in `tests/test_docs_links.py` (MUST_FAIL, MUST_PASS and the comment-fence test). All still passed. For the first four I also ran a probe file that does change the script's output:
  1. Fence close "at least as long": drop the length check at `scripts/docs_links.py:105` (`if run:`). Then ```` ````\n```\n[x](missing.md)\n```` ```` lets the broken link through, because the shorter inner run wrongly closes the fence.
  2. Fence close "same character": allow any run of `` ` `` or `~` at `scripts/docs_links.py:104`. Then ```` ```\n~~~\n[x](missing.md)\n``` ```` wrongly reports the fenced link (exit 1).
  3. "A backslash-escaped backtick does not open a span": replace `scripts/docs_links.py:124` with `if False:`. Then ``\`see [x](esc-missing.md) `y` `` hides the broken link (exit 0 instead of 1).
  4. "Within the same paragraph": treat every line as one paragraph at `scripts/docs_links.py:259`. Then `` `a\n\n[x](para-missing.md) ` `` hides the broken link (exit 0 instead of 1).
  5. "Undo backslash escapes": drop the unescape at `scripts/docs_links.py:273`. No test has an escape in a destination.
  6. Reference definitions "after any `>` markers": drop `(?:>\s*)*` from `REFDEF_RE` at `scripts/docs_links.py:56`. No test has `> [t]: missing.md`.

  The fix is to add one must-fail case for each (the probe inputs above work, plus `> [t]: missing.md` and a valid `[g](gu\_ide.md)`-style escaped destination as a must-pass). The brief's minimum list doesn't name these cases. But the brief requires the rule, and the last sign-off rejected a patch for exactly this kind of unguarded branch.

- NEEDS-HUMAN [human] — Root-absolute links (`[g](/docs/guide.md)`) are always reported broken, even when the target is tracked. `posixpath.join(base, "/docs/guide.md")` at `scripts/docs_links.py:316` keeps the leading `/`, so the result is never in the tracked set. I confirmed this with a probe: exit 1, `docs/page.md:1: broken link: /docs/guide.md`. GitHub resolves such links from the repo root. The live tree has none today, so this is latent. Decision 5 says "relative to the file's directory" and doesn't mention `/`-prefixed paths, and the docstring's known-gaps list (`scripts/docs_links.py:32-38`) doesn't mention them either. The maintainer should decide whether to list this as a known gap or resolve such links from the repo root. Either way, a future contributor using that style will get a CI failure that looks like a real broken link.

- About the reviewer's likely verdict: the "C4 PASS" in `check-gates.json` is earned. Be careful with any claim that the tests "cover the rule", though. They cover the brief's minimum list plus the carry-forward cases, not every clause of the rule (see the first finding).

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review — docs-checks-internal-links (issue 98)

Attacker-reachable inputs this diff touches: **none** in the threat model's sense. The patch adds a CI-only link checker (`scripts/docs_links.py`), its tests, and one workflow step. No nl-shell runtime code changes: not the gate, the PTY, sudo passthrough, taint, the reader, logging, or the installer. None of the 11 "Where untrusted input enters" items in `.oss-scanner/threat_model.md` covers PR-supplied Markdown read by CI, and T2 agrees (`gate-logs/T2-threat-model.log`: "no security-relevant path touched").

**No findings.** Below is what I checked, so the verdict can be audited. A PR author is the only person who controls the input here: tracked `.md` contents and file names.

- **Workflow trust boundary** (`.github/workflows/docs-checks.yml:47-48`). The new step runs the PR's own copy of `scripts/docs_links.py`. The freeze step above it runs the base copy instead. That is acceptable. The trigger stays `pull_request` (not `pull_request_target`), `permissions: contents: read` is unchanged, and the job holds no secrets. So a PR author who rewrites the script gains nothing they couldn't already get by editing the workflow file. At worst they switch off their own advisory link check, which is not a security property. `python -I` keeps the checkout off `sys.path`, the same as child-1's step.
- **Path traversal** (`scripts/docs_links.py:316-318`). Link targets go through `posixpath.normpath`, and the result is only checked against the set of `git ls-files` paths. They are never opened or read. A link like `[x](../../../etc/passwd)` just gets reported as broken. The only file reads are tracked `.md` paths under the repo root (`:306`). A tracked symlink `.md` would be followed, but the PR author already runs their own code on that runner, so this gives them no new access.
- **Output injection.** `parse_dest` stops at whitespace and newlines (`:222`), and `REFDEF_RE` captures `\S+`, so a link destination can't add a line to the CI log. Every printed line starts with the tracked path. Again, the PR author controls the script anyway.
- **Subprocess use** (`:279-282`). `git` is called with a fixed argument list. Nothing goes through a shell, and no file content becomes an argument.
- **Resource use (not a finding, for information only).** `inline_links` calls `matching_bracket` from every `[` (`:178`, `:183`), and each call scans to the end of the paragraph. On a run of unmatched `[` that is quadratic: I measured `find_links('['*5000)` at 0.38 s and `'['*20000` at 5.34 s with python 3.14, so a ~200 KB single-paragraph file would take several minutes. The only party affected is the PR author's own CI job, which the runner's job timeout bounds. On main it would also slow `tests.yml` (`test_live_checkout_has_no_broken_links`), but that needs the file to pass review and merge first. Nothing on the threat model's scale covers this, so I am not filing it as NEEDS-HUMAN. If the builder wants it gone, the simple fix is to stop `matching_bracket` at the first unmatched-depth failure, or to cap the scan.
- **Test coverage.** The fix is not security-relevant, so there is no attacker case its tests need to cover. The tests set their own git identity and `GIT_CONFIG_NOSYSTEM` (`tests/test_docs_links.py` `GIT_ENV`) and don't read host git config, as the brief asks.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T5 Judgment — Confirm affected-path prior art against merged history and closed/rejected work before sign-off — this copy exposes only one synthetic base commit and no remote, so the path-scoped history query cannot establish either history (target/.github/workflows/docs-checks.yml:47; target/scripts/docs_links.py:1; target/tests/test_docs_links.py:1).
- [ ] Validation — fitness-to-purpose — Confirm decision 5’s parser limits and inspect the draft PR’s Docs checks and test-suite CI results — local behavior passes, but acceptance of deliberately incomplete Markdown coverage and hosted workflow execution remains owed (target/scripts/docs_links.py:32; target/.github/workflows/docs-checks.yml:47; brief.md:21; brief.md:47).
- [ ] Six rule clauses have no test. I applied each change below to a copy of the script and ran every case in `tests/test_docs_links.py` (MUST_FAIL, MUST_PASS and the comment-fence test). All still passed. For the first four I also ran a probe file that does change the script's output:
- [ ] Root-absolute links (`[g](/docs/guide.md)`) are always reported broken, even when the target is tracked. `posixpath.join(base, "/docs/guide.md")` at `scripts/docs_links.py:316` keeps the leading `/`, so the result is never in the tracked set. I confirmed this with a probe: exit 1, `docs/page.md:1: broken link: /docs/guide.md`. GitHub resolves such links from the repo root. The live tree has none today, so this is latent. Decision 5 says "relative to the file's directory" and doesn't mention `/`-prefixed paths, and the docstring's known-gaps list (`scripts/docs_links.py:32-38`) doesn't mention them either. The maintainer should decide whether to list this as a known gap or resolve such links from the repo root. Either way, a future contributor using that style will get a CI failure that looks like a real broken link.
- [ ] **The base is wrong for scope item (3): the prerequisite has not landed.** `dependency-state.json` lists `"97": {"declared": "Depends on", "state": "PLANNED"}`, so child-1 has not been built, let alone merged. The brief still targets `eduralph/nl-shell @ main` (brief l.31). Scope (3) adds "One step in `.github/workflows/docs-checks.yml` (created by child-1) after the freeze step" (l.36). That file does not exist on the target: `.github/workflows/` contains only `require-linked-issue.yml`, `triage-new-issue.yml` and `tests.yml`. If Do starts from `main` it has nothing to add a step to, and no "freeze step" to put it after. It would either have to invent child-1's workflow, which is a hidden second change that collides with #97, or drop (3). The brief needs one of two fixes: declare `Stacks on: 97` and target child-1's branch, or hold this bundle until #97 merges. "Depends on" against a PLANNED prereq with a `main` base will strand the run.
- [ ] **The tracker record is missing from the bundle, so the problem framing and "maintainer decision 5" cannot be checked.** The sandbox has only `brief.md` and `dependency-state.json`. There is no `notes.json` and no `sources/`. The whole link rule (l.20–29) and the instruction to "judge the parser against the fixed link rule below, not against CommonMark" (l.8–11) rest on "maintainer decision 5, 2026-10-15" and "the parent cycle ran three rounds". I could not check either against a thread quote. A human should confirm that decision 5 says what l.20–30 encode, especially the deliberate gaps: unclosed `<!--` masks the rest of the file, 4-space indented code is not recognized. Those gaps define what counts as correct for every downstream Check.
- [ ] **Do is pointed at an input outside the bundle.** l.37 says to reuse `cmd_links` from `/home/eddie/nl-shell/nl-shell-pdca/results/issue_7/iteration-v3/patch.diff`, but l.3 says "Do reads ONLY this file". That is an absolute host path to another run's artifact. It is not in the bundle or in `$PDCA_TARGET`, and Do may not be able to read it in its sandbox. The parent's code was also written during the three CommonMark rounds that decision 5 ended, so "reuse what fits" invites drift back toward CommonMark behaviour. Either copy the relevant excerpt into the bundle or drop the pointer. As written it is an unverifiable dependency.
- [ ] **Live-tree claims could only be partly checked.** Without Bash I could not run `git ls-files` to confirm "53 tracked `.md` files, 60 relative links, 0 broken" (l.17). What I could check holds:
- [ ] **Criterion (b)'s "cases for each rule step" is open-ended.** l.16 asks for "cases for each rule step, and for the round-3 cases". The round-3 cases (l.29) are listed concretely, but "each rule step" has no list. That leaves the Check reviewer to argue over coverage, and it reopens the edge-case chase l.8–11 is meant to close. A fix would be to list the minimum must-fail and must-pass cases per step, e.g. step 3 escaped backtick, step 3 unmatched run, step 4 balanced parens, step 4 `[^1]:` footnote skipped, the image link and the `#fragment`-stripped link. Then the success criterion becomes a checklist instead of a judgment call.

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
- Iteration delta (if iterating): Keep the patch and decision 5's rule as is; only add the tests the adversary review (SUMMARY §6 item 3) showed are missing. Each must go red if its rule clause is removed from scripts/docs_links.py: 1. Fence close "at least as long": "````\n```\n[x](missing.md)\n````\n" must PASS (inner shorter run does not close the fence). Add a companion case where a link after the real close is reported. 2. Fence close "same character": "```\n~~~\n[x](missing.md)\n```\n" must PASS (~~~ does not close a backtick fence). 3. Escaped backtick does not open a span: "\`see [x](esc-missing.md) `y`" must FAIL and name esc-missing.md. 4. Inline code stays within a paragraph: "`a\n\n[x](para-missing.md) `" must FAIL and name para-missing.md. 5. Backslash escapes in dest are undone: a valid "[g](gu\_ide.md)" pointing at tracked gu_ide.md must PASS. 6. Reference definition after ">" markers: "> [t]: missing.md" must FAIL and name missing.md. Root-absolute links ("/docs/x.md", §6 item 4): do not change resolution; add them to the known-gaps list in the script's docstring (they are resolved relative to the file's directory, so they are reported broken).
- By / date: Eduard Ralph / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 5 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

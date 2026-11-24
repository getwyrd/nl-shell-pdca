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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (25 of 25 failed), green with it
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

Review the new relative Markdown link checker and its CI step, using the maintainer’s fixed parsing rule to catch broken tracked-file links.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The fixed rule and explicit known gaps give a falsifiable scope; required failing and passing cases are represented in target/tests/test_docs_links.py:68 and target/tests/test_docs_links.py:96. |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing only the new production script caused all 25 case expectations to fail, consistent with the missing pre-fix checker; rerun-red.log:26 and gate-logs/C4-verify.log:14. |
| C3 Change | PASS | The three changed paths match the requested scope, preserve the prerequisite freeze check, and introduce the link step immediately afterward; target/.github/workflows/docs-checks.yml:32 and target/.github/workflows/docs-checks.yml:47. |
| C4 Verification (red→green) | PASS | Independent subprocess checks went from 0/25 expectations satisfied without the script to 25/25 after restoration; frozen pytest evidence separately records 25 passing tests; rerun-red.log:26, rerun-restored.log:26, gate-logs/C4-verify.log:12. |
| C5 Causal adequacy | PASS | Tracked-target membership directly addresses missing link validation, with ordered masking and explicit broken-link diagnostics; no optional-capability probe papers over a load-time cause; target/scripts/docs_links.py:228 and target/scripts/docs_links.py:305. |
| T1 Structure | PASS | The stdlib checker is separate from shipped runtime code and the prerequisite checker, and tests call its executable boundary; target/scripts/docs_links.py:39 and target/tests/test_docs_links.py:49. |
| T2 Shape | PASS | The workflow retains pull_request, contents: read, and isolated Python execution; the frozen threat-model gate reports no security-relevant path touched; target/.github/workflows/docs-checks.yml:9, target/.github/workflows/docs-checks.yml:48, gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | The frozen full-suite log explicitly reports 131 passing tests; independent live-tree execution also finds 60 links across 53 Markdown files with zero broken; gate-logs/T3-suite.log:13 and rerun-restored.log:25. |
| T4 Contribution | N/A | Contribution artifacts are intentionally drafted after Check; their substantive audit must rerun at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art against merged history and closed/rejected work — the supplied repository contains only one snapshot commit, so duplicate or previously rejected approaches cannot be ruled out; target/.github/workflows/docs-checks.yml:47 and target/tests/test_docs_links.py:1. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Confirm maintainer decision 5’s deliberately limited parsing rule and inspect the draft PR’s Docs checks run — local success does not establish the hosted workflow result or acceptance of the documented gaps; target/scripts/docs_links.py:28 and target/.github/workflows/docs-checks.yml:47. |

Verification details: this sandbox has no `python` command and its `python3` lacks pytest. I therefore read the frozen C4 and T3 logs and independently exercised the supplied test-case data with a stdlib subprocess runner (`rerun.py`), without substituting a pytest shim. The runner creates real Git indexes, checks exit codes and file/link diagnostics, and runs the checker against the supplied live target. Its fixtures use staging rather than commits; the checker consumes `git ls-files`. The regression expectations failed 25/25 when the production script was stashed and passed 25/25 after `git stash pop`. These checks supplement, rather than claim to reproduce, the full pytest suite. The target’s patch was restored; `git diff --check` passed.

Prior-art investigation: `git log --all -- .github/workflows/docs-checks.yml scripts/docs_links.py tests/test_docs_links.py` returns only snapshot commit `c24304e`; `git rev-list --count --all` returned 1 before the temporary stash. No closed/rejected-work evidence or INTEGRATION.md was supplied or found in the target. The target contains the prerequisite workflow and checker, so no stale-target caveat is needed. No implementation defect was established against the specified rule.

For the remaining hosted validation, open the draft PR’s Actions run, select Docs checks → docs, and confirm “Frozen design records are unchanged” succeeds followed by “Relative links resolve” reporting zero broken links. Confirm the documented parser gaps are acceptable before sign-off.
<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — docs-checks-internal-links (#98)

I re-ran the check on the target tree and probed the parser with ~25 edge-case inputs. I also ran one mutation test: a copy of the script, edited so a fence never closes, run against the bundle's tests.

- **Evidence holds up.** `gate-logs/C4-verify.log` shows the red leg as 25/25 failing with "can't open file .../scripts/docs_links.py". That is the expected red: the brief tells the tests to call the script as a subprocess. Every must-fail case also asserts that `docs/page.md:` and `broken link: <dest>` appear in stdout (`tests/test_docs_links.py:92-93`), so a crashing script can't pass. On the target, `python3 -I scripts/docs_links.py` prints `60 relative links in 53 Markdown files, 0 broken` with exit 0, which matches the brief's planning-time count.

- NEEDS-HUMAN [impl] — The tests never check that a fenced block *closes*. `scripts/docs_links.py:101-102` is the close branch. When I replaced `fence = None` with `pass`, so every fence runs to end of file, all 24 fixture tests still passed (`24 passed`). The live-tree test (`tests/test_docs_links.py:136-141`) would pass too, because masking more text only means fewer links get checked, and the count stays at 0 broken. Every fence case in MUST_PASS (`tests/test_docs_links.py:106-109`) ends at end of file, and the only "link after a construct" test (`:125-132`) covers a comment, not a fence. Failing case the suite should have: `` "```\n[a](guide.md)\n```\n[y](missing.md)\n" `` must exit 1 and name `missing.md`. The fence-on-a-list-marker and block-quote fences need the same kind of case, so that their *closing* lines get tested after stripping. The current code handles all of these correctly (I probed them). Only the test is missing, so a future regression that silently stops checking most of a doc would go unnoticed.

- NEEDS-HUMAN [impl] — `parse_dest` (`scripts/docs_links.py:205-227`) returns a destination even when no `)` follows. Only hitting the end of the paragraph returns `""` (`:224-225`). If it stops at whitespace (`:215-216`), it returns the text so far. Failing case: the prose line `See [x](missing.md for more.` is reported as `broken link: missing.md`, even though there is no `[t](dest)` per rule step 4. The behavior is also inconsistent: `See [x](missing.md` at the end of a paragraph is ignored. This is a false positive (an extra error, not a missed broken link) and it's rare. A fix would be to require that, after any whitespace, the next character is `)` or the start of a title. The brief lists titles as a known gap, so a human may decide this is out of scope. Without the fix, `[a](b "title")` keeps working.

- Not a refutation, but worth seeing at sign-off: because step 1 runs before step 3, a `<!--` inside inline code hides the rest of the file. The input `` "`<!--` [y](out.md)\n\n[z](z.md)\n" `` yields no links at all. This follows decision 5 and the documented "unclosed `<!--` masks the rest" gap, and no live doc has this today (the only `<!--` hits are the four closed comments in `docs/design/templates/`). Likewise, a ```` ```python ```` line inside an open ``` fence closes it, as the rule literally says. Neither is a bug by the brief's terms.

- Things I tried to break and couldn't: escaped `[` and `\\[` (double backslash, so the link counts); an escaped backtick before a link; a backslash inside a code span; nested brackets in link text; an image inside a link; an escaped `]`; link text spanning lines; a dest on the next line; CRLF line endings; a 4-backtick fence with a 3-backtick line inside; a fence inside a comment; a fence inside a list item followed by a link; a comment on the same line as a link; a nested-list reference definition; footnotes; `../` up to the repo root; directory targets. All behaved as the rule says, and line numbers were right.

- The reviewer's verdict: I found no claim in `check-gates.json` that the evidence doesn't support. C4 and T3 are real passes. The weak spot is the C4 headline "red without the fix (25 of 25 failed)": that red only proves the script exists, not that each parser rule is enforced. The fence-close mutation above shows one rule the suite doesn't pin down.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review — docs-checks-internal-links

Attacker-reachable inputs this diff touches: **none.** The threat model's untrusted inputs
(`.oss-scanner/threat_model.md`, "Where untrusted input enters", items 1–11) are all about
the running nl-shell REPL: command output, file names, env vars, session state, model
output, history, the reader, the model socket, install-time downloads, training data and
the dev teacher. This patch adds a CI-only link checker (`scripts/docs_links.py`), its test
(`tests/test_docs_links.py`) and one workflow step (`.github/workflows/docs-checks.yml:47-48`).
None of it is imported by `src/`, and none of it runs inside the REPL, the gate, the PTY
session, sudo passthrough, the installer or the training data path. The T2 gate agrees
("no security-relevant path touched"). Nothing here can break a "What must hold" property,
so no finding is rated.

What I checked anyway, all with no finding:

- **Workflow trust boundary.** The new step runs under child-1's `pull_request` trigger
  with `permissions: contents: read`. There is no `pull_request_target`, no secrets, and no
  `${{ }}` expression goes into the `run:` line (`.github/workflows/docs-checks.yml:9-13,47-48`).
  It runs the PR's own copy of `docs_links.py`, so a PR can turn off its own link check by
  editing the script. That differs from the freeze step, which runs the base copy. This is
  a check-integrity point, not a security one: the script guards doc hygiene, not a
  security property, and `tests/test_docs_links.py` repeats the check in `tests.yml`.
  `python -I` keeps the PR checkout off `sys.path`, the same way the freeze step does.
- **Path traversal / file reads.** The script opens only paths from `git ls-files` under
  the repo root (`scripts/docs_links.py:295`). Link targets are only normalized and looked
  up in in-memory sets (`scripts/docs_links.py:305`); they are never opened. So
  `[x](../../../etc/passwd)` is just reported as broken. A tracked `.md` symlink pointing
  outside the repo would be read, but only link destinations are printed, never file
  contents, and this runs on a throwaway CI runner with a read-only token.
- **Subprocess / injection.** `git` is called with a fixed argv list and no shell
  (`scripts/docs_links.py` `git()`). File names go through `-z`, so names with newlines or
  quotes can't break parsing.
- **Resource use.** `inline_links` calls `matching_bracket` (`scripts/docs_links.py:162,184`)
  from every `[`, so a file with many unclosed `[` takes quadratic time (for example, 100k
  `[` characters means about 5·10⁹ steps). Only a PR author controls tracked `.md` content.
  In this workflow they can already run any code they want, and the cost is CI minutes on
  their own PR. This is outside the threat model and needs no fix.
- **Test isolation.** The tests set their own git identity and `GIT_CONFIG_NOSYSTEM`, build
  repos only under `tmp_path`, and run the script as a subprocess with a 60s timeout
  (`tests/test_docs_links.py`). They don't touch HOME or host git config.

No findings. Nothing for a human to decide on security grounds.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T5 Judgment — Confirm affected-path prior art against merged history and closed/rejected work — the supplied repository contains only one snapshot commit, so duplicate or previously rejected approaches cannot be ruled out; target/.github/workflows/docs-checks.yml:47 and target/tests/test_docs_links.py:1.
- [ ] Validation — fitness-to-purpose — Confirm maintainer decision 5’s deliberately limited parsing rule and inspect the draft PR’s Docs checks run — local success does not establish the hosted workflow result or acceptance of the documented gaps; target/scripts/docs_links.py:28 and target/.github/workflows/docs-checks.yml:47.
- [ ] The tests never check that a fenced block *closes*. `scripts/docs_links.py:101-102` is the close branch. When I replaced `fence = None` with `pass`, so every fence runs to end of file, all 24 fixture tests still passed (`24 passed`). The live-tree test (`tests/test_docs_links.py:136-141`) would pass too, because masking more text only means fewer links get checked, and the count stays at 0 broken. Every fence case in MUST_PASS (`tests/test_docs_links.py:106-109`) ends at end of file, and the only "link after a construct" test (`:125-132`) covers a comment, not a fence. Failing case the suite should have: `` "```\n[a](guide.md)\n```\n[y](missing.md)\n" `` must exit 1 and name `missing.md`. The fence-on-a-list-marker and block-quote fences need the same kind of case, so that their *closing* lines get tested after stripping. The current code handles all of these correctly (I probed them). Only the test is missing, so a future regression that silently stops checking most of a doc would go unnoticed.
- [ ] `parse_dest` (`scripts/docs_links.py:205-227`) returns a destination even when no `)` follows. Only hitting the end of the paragraph returns `""` (`:224-225`). If it stops at whitespace (`:215-216`), it returns the text so far. Failing case: the prose line `See [x](missing.md for more.` is reported as `broken link: missing.md`, even though there is no `[t](dest)` per rule step 4. The behavior is also inconsistent: `See [x](missing.md` at the end of a paragraph is ignored. This is a false positive (an extra error, not a missed broken link) and it's rare. A fix would be to require that, after any whitespace, the next character is `)` or the start of a title. The brief lists titles as a known gap, so a human may decide this is out of scope. Without the fix, `[a](b "title")` keeps working.
- [x] **The base is wrong for scope item (3): the prerequisite has not landed.** `dependency-state.json` lists `"97": {"declared": "Depends on", "state": "PLANNED"}`, so child-1 has not been built, let alone merged. The brief still targets `eduralph/nl-shell @ main` (brief l.31). Scope (3) adds "One step in `.github/workflows/docs-checks.yml` (created by child-1) after the freeze step" (l.36). That file does not exist on the target: `.github/workflows/` contains only `require-linked-issue.yml`, `triage-new-issue.yml` and `tests.yml`. If Do starts from `main` it has nothing to add a step to, and no "freeze step" to put it after. It would either have to invent child-1's workflow, which is a hidden second change that collides with #97, or drop (3). The brief needs one of two fixes: declare `Stacks on: 97` and target child-1's branch, or hold this bundle until #97 merges. "Depends on" against a PLANNED prereq with a `main` base will strand the run.
- [x] **The tracker record is missing from the bundle, so the problem framing and "maintainer decision 5" cannot be checked.** The sandbox has only `brief.md` and `dependency-state.json`. There is no `notes.json` and no `sources/`. The whole link rule (l.20–29) and the instruction to "judge the parser against the fixed link rule below, not against CommonMark" (l.8–11) rest on "maintainer decision 5, 2026-10-15" and "the parent cycle ran three rounds". I could not check either against a thread quote. A human should confirm that decision 5 says what l.20–30 encode, especially the deliberate gaps: unclosed `<!--` masks the rest of the file, 4-space indented code is not recognized. Those gaps define what counts as correct for every downstream Check.
- [x] **Do is pointed at an input outside the bundle.** l.37 says to reuse `cmd_links` from `/home/eddie/nl-shell/nl-shell-pdca/results/issue_7/iteration-v3/patch.diff`, but l.3 says "Do reads ONLY this file". That is an absolute host path to another run's artifact. It is not in the bundle or in `$PDCA_TARGET`, and Do may not be able to read it in its sandbox. The parent's code was also written during the three CommonMark rounds that decision 5 ended, so "reuse what fits" invites drift back toward CommonMark behaviour. Either copy the relevant excerpt into the bundle or drop the pointer. As written it is an unverifiable dependency.
- [x] **Live-tree claims could only be partly checked.** Without Bash I could not run `git ls-files` to confirm "53 tracked `.md` files, 60 relative links, 0 broken" (l.17). What I could check holds:
- [x] **Criterion (b)'s "cases for each rule step" is open-ended.** l.16 asks for "cases for each rule step, and for the round-3 cases". The round-3 cases (l.29) are listed concretely, but "each rule step" has no list. That leaves the Check reviewer to argue over coverage, and it reopens the edge-case chase l.8–11 is meant to close. A fix would be to list the minimum must-fail and must-pass cases per step, e.g. step 3 escaped backtick, step 3 unmatched run, step 4 balanced parens, step 4 `[^1]:` footnote skipped, the image link and the `#fragment`-stripped link. Then the success criterion becomes a checklist instead of a judgment call.

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
- Iteration delta (if iterating): Fix two gaps the adversary review found (SUMMARY §6 items 3 and 4); keep the rest of the patch and decision 5's rule as is. 1. Add tests that a fenced code block CLOSES: e.g. "```\n[a](guide.md)\n```\n[y](missing.md)\n" must exit 1 and name missing.md. Add the same "link after the closing fence" case for a fence opened on a list-marker line and for one inside a > block quote, so the stripped closing lines are tested. Today replacing the close branch (scripts/docs_links.py:101-102) with a no-op still passes every test. 2. parse_dest (scripts/docs_links.py:205-227) must not return a destination when no ")" follows. "See [x](missing.md for more." is currently reported as a broken link. After the destination and any whitespace, require ")" (or the start of a title, so [a](b "title") keeps working); otherwise it is not a link. Add a must-pass test for that prose case.
- By / date: Eduard Ralph / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 5 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

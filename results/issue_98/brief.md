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
- **Repo + branch target:** eduralph/nl-shell @ main (built in a later wave than #97: per `Depends on: 97` the driver folds #97's accepted patch into the wave's integration branch and verifies against it via `$PDCA_VERIFY_BASE`, `engine/scripts/run-verify.sh:51,64`, so `.github/workflows/docs-checks.yml` and its freeze step exist when this bundle builds)
- **Reproduction:** On `eduralph/nl-shell` `main`, edit `docs/design/adr/README.md` so its link to `0001-record-architecture-decisions.md` points at `0001-missing.md`, commit, and run the test suite and workflows: nothing fails, and no link check exists in `.github/workflows/`.
- **Scope (one logical fix) / out of scope:** Add:
  (1) `scripts/docs_links.py`: stdlib-only Python, runnable from any git checkout's root, scanning `git ls-files '*.md'` with the rule above; known gaps listed in its docstring.
  (2) `tests/test_docs_links.py`, setting its own git identity for throwaway repos (git `-c` or GIT_AUTHOR/GIT_COMMITTER env vars), never relying on host git config (`tests/conftest.py:52-56` sets a temp HOME).
  (3) One step in `.github/workflows/docs-checks.yml` (created by child-1) after the freeze step, running `scripts/docs_links.py`. Keep child-1's trigger (`pull_request`, no path filter), `permissions: contents: read` and checkout unchanged; never `pull_request_target`.
  Write the parser fresh from the rule above. Do not start from the parent issue-7 patch's `cmd_links`: it was written while chasing CommonMark and does more than the rule asks.
  / out of scope: the freeze check, `scripts/docs_checks.py` and `tests/test_docs_checks.py` (child-1); checking `#fragment` anchors against headings; closing any listed known gap; full CommonMark conformance; wyrd's `lint_docs.py` / `render_site.py`; making the job a required check; editing any existing doc to fix links (there are none broken).
- **External dependencies:** none
- **Test file:** tests/test_docs_links.py
- **Difficulty:** medium
- **Depends on:** 97

Plan-review response: finding 1 stands. `Depends on:` is the wave dependency, not a wait for merge: #98 runs in a later wave on #97's folded result (`$PDCA_VERIFY_BASE`, `engine/scripts/run-verify.sh:51,64`), so the workflow file exists; the branch-target line now says so. If #97 is not accepted, #98 is not scheduled. Finding 2 stands: decision 5 was made with the maintainer in the parent issue-7 planning session; the human confirms it at sign-off. Finding 3 addressed: the pointer to the parent patch is removed and Do writes the parser from the rule. Finding 4 addressed: re-checked at Plan, 53 tracked `.md` files, 60 relative links, 0 broken. Finding 5 addressed: criterion (b) now lists the minimum must-fail and must-pass cases.

## Iteration 1 — carry-forward (from the previous attempt)
- Sign-off rationale: Fix two gaps the adversary review found (SUMMARY §6 items 3 and 4); keep the rest of the patch and decision 5's rule as is. 1. Add tests that a fenced code block CLOSES: e.g. "```\n[a](guide.md)\n```\n[y](missing.md)\n" must exit 1 and name missing.md. Add the same "link after the closing fence" case for a fence opened on a list-marker line and for one inside a > block quote, so the stripped closing lines are tested. Today replacing the close branch (scripts/docs_links.py:101-102) with a no-op still passes every test. 2. parse_dest (scripts/docs_links.py:205-227) must not return a destination when no ")" follows. "See [x](missing.md for more." is currently reported as a broken link. After the destination and any whitespace, require ")" (or the start of a title, so [a](b "title") keeps working); otherwise it is not a link. Add a must-pass test for that prose case.
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Fix two gaps the adversary review found (SUMMARY §6 items 3 and 4); keep the rest of the patch and decision 5's rule as is.
  1. Add tests that a fenced code block CLOSES: e.g. "```\n[a](guide.md)\n```\n[y](missing.md)\n" must exit 1 and name missing.md. Add the same "link after the closing fence" case for a fence opened on a list-marker line and for one inside a > block quote, so the stripped closing lines are tested. Today replacing the close branch (scripts/docs_links.py:101-102) with a no-op still passes every test.
  2. parse_dest (scripts/docs_links.py:205-227) must not return a destination when no ")" follows. "See [x](missing.md for more." is currently reported as a broken link. After the destination and any whitespace, require ")" (or the start of a title, so [a](b "title") keeps working); otherwise it is not a link. Add a must-pass test for that prose case.
- Full previous attempt preserved in `iteration-v1/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 2 — carry-forward (from the previous attempt)
- Sign-off rationale: Keep the patch and decision 5's rule as is; only add the tests the adversary review (SUMMARY §6 item 3) showed are missing. Each must go red if its rule clause is removed from scripts/docs_links.py: 1. Fence close "at least as long": "````\n```\n[x](missing.md)\n````\n" must PASS (inner shorter run does not close the fence). Add a companion case where a link after the real close is reported. 2. Fence close "same character": "```\n~~~\n[x](missing.md)\n```\n" must PASS (~~~ does not close a backtick fence). 3. Escaped backtick does not open a span: "\`see [x](esc-missing.md) `y`" must FAIL and name esc-missing.md. 4. Inline code stays within a paragraph: "`a\n\n[x](para-missing.md) `" must FAIL and name para-missing.md. 5. Backslash escapes in dest are undone: a valid "[g](gu\_ide.md)" pointing at tracked gu_ide.md must PASS. 6. Reference definition after ">" markers: "> [t]: missing.md" must FAIL and name missing.md. Root-absolute links ("/docs/x.md", §6 item 4): do not change resolution; add them to the known-gaps list in the script's docstring (they are resolved relative to the file's directory, so they are reported broken).
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Keep the patch and decision 5's rule as is; only add the tests the adversary review (SUMMARY §6 item 3) showed are missing. Each must go red if its rule clause is removed from scripts/docs_links.py:
  1. Fence close "at least as long": "````\n```\n[x](missing.md)\n````\n" must PASS (inner shorter run does not close the fence). Add a companion case where a link after the real close is reported.
  2. Fence close "same character": "```\n~~~\n[x](missing.md)\n```\n" must PASS (~~~ does not close a backtick fence).
  3. Escaped backtick does not open a span: "\`see [x](esc-missing.md) `y`" must FAIL and name esc-missing.md.
  4. Inline code stays within a paragraph: "`a\n\n[x](para-missing.md) `" must FAIL and name para-missing.md.
  5. Backslash escapes in dest are undone: a valid "[g](gu\_ide.md)" pointing at tracked gu_ide.md must PASS.
  6. Reference definition after ">" markers: "> [t]: missing.md" must FAIL and name missing.md.
  Root-absolute links ("/docs/x.md", §6 item 4): do not change resolution; add them to the known-gaps list in the script's docstring (they are resolved relative to the file's directory, so they are reported broken).
- Full previous attempt preserved in `iteration-v2/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 3 — carry-forward (from the previous attempt)
- Sign-off rationale: Keep scripts/docs_links.py, the workflow step and decision 5's rule exactly as they are; the behavior is correct. Only add the three tests the iteration-3 adversary review found missing (SUMMARY §6 items 3-5). Each must go red if its rule clause is removed from the script: 1. Fence inside a ">" block quote, closed by a longer run so inline code cannot pair the runs: "> ```\n> [x](missing.md)\n> ````\n" must PASS. It must fail if scripts/docs_links.py:87 strips only whitespace and not ">" markers. 2. A longer run closes a fence: "```\n[a](guide.md)\n````\n[y](after-longer.md)\n" must FAIL and name after-longer.md. It must fail if ">=" at scripts/docs_links.py:107 becomes "==". 3. Badge / nested link: "[![b](missing.png)](guide.md)\n" must FAIL and name missing.png. It must fail if the rescan at scripts/docs_links.py:185 skips past the outer link. Do not change anything else.
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Keep scripts/docs_links.py, the workflow step and decision 5's rule exactly as they are; the behavior is correct. Only add the three tests the iteration-3 adversary review found missing (SUMMARY §6 items 3-5). Each must go red if its rule clause is removed from the script:
  1. Fence inside a ">" block quote, closed by a longer run so inline code cannot pair the runs: "> ```\n> [x](missing.md)\n> ````\n" must PASS. It must fail if scripts/docs_links.py:87 strips only whitespace and not ">" markers.
  2. A longer run closes a fence: "```\n[a](guide.md)\n````\n[y](after-longer.md)\n" must FAIL and name after-longer.md. It must fail if ">=" at scripts/docs_links.py:107 becomes "==".
  3. Badge / nested link: "[![b](missing.png)](guide.md)\n" must FAIL and name missing.png. It must fail if the rescan at scripts/docs_links.py:185 skips past the outer link.
  Do not change anything else.
- Full previous attempt preserved in `iteration-v3/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

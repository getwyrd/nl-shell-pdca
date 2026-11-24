## Summary
**User impact:** a link from one nl-shell doc to another can break without anyone
noticing. Renaming or deleting a doc, or mistyping a link, passes every CI check today, so
readers land on dead links until someone happens to click one.

This PR adds a CI check that fails when a relative link in a Markdown file points at a
file or folder that isn't in the repo, and says which file, line and link are broken.

Reported in [#98](https://github.com/eduralph/nl-shell/issues/98).

This builds on #97, which adds the Docs checks workflow this step is added to; review and
merge #97 first.

## What to look at
- A new script that reads every tracked Markdown file and checks its relative links, using
  a short, fixed rule (below) rather than a full Markdown parser.
- One new step in the Docs checks workflow that runs it.
- A test file that walks through the rule case by case.

To try it: in `docs/design/adr/README.md`, change the link to
`0001-record-architecture-decisions.md` into `0001-missing.md`, commit, and run
`python scripts/docs_links.py`. It exits 1 and prints
`docs/design/adr/README.md:26: broken link: 0001-missing.md`. On a clean tree it exits 0.

## Root cause
The repo had no link check at all: neither `tests.yml` nor the Docs checks workflow looked
at Markdown links. Link checking was the half of the docs CI from `getwyrd/wyrd` that had
not been ported yet.

## Fix
`scripts/docs_links.py` (stdlib only) lists files with `git ls-files`, so it also works in
a git worktree, and applies this rule in order:

1. Remove `<!-- … -->` comments, even across lines. An unclosed `<!--` hides the rest of
   the file.
2. Remove fenced code. Leading whitespace, `>` quote markers and one list marker are
   stripped before looking for a fence of 3+ backticks or tildes. It closes on a run of the
   same character at least as long. An unclosed fence runs to the end of the file.
3. Remove inline code: a backtick run up to the next run of the same length in the same
   paragraph. An escaped backtick does not open a span.
4. Check inline links, image links and reference definitions (not footnotes). Skip
   anything with a scheme (`https:`, `mailto:`, …) and pure `#…` links. Strip the
   fragment, undo backslash escapes, resolve relative to the file's folder, and require a
   tracked file or folder.

The rule is deliberately simpler than CommonMark. Its known gaps are listed in the
script's docstring: indented (4-space) code blocks are not recognized, `<…>` destinations
and percent-encoding are not handled, root-absolute links (`/docs/x.md`) are reported as
broken, and `#fragment` anchors are not checked against headings. The current docs use
none of these.

The workflow gets one step, after the frozen-record step, running
`python -I scripts/docs_links.py`. The trigger (`pull_request`, no path filter),
`permissions: contents: read` and checkout are unchanged.

## Verification
- **Claim:** a broken relative link fails the check and names the file and the link.
  - **Checked:** `scripts/docs_links.py:287-328` (`main`): each unresolved link is printed
    as `file:line: broken link: dest`, and the exit code is 1.
  - **Test:** `tests/test_docs_links.py:68-131`. 18 must-fail cases (inline, image,
    reference definition, `#fragment`, nested-list reference definition, link after inline
    code, balanced parentheses, link after a closed fence of each kind, a badge
    `[![b](missing.png)](guide.md)`, and others). Each asserts the file and the link appear
    in the output.
- **Claim:** links that should not be checked, or that resolve, pass.
  - **Checked:** comments `scripts/docs_links.py:73-79`, fences `:85-110`, inline code
    `:120-145`, link and destination parsing `:167-238` (prose like
    `[x](missing.md for more.` is not a link, `:236-237`), external and fragment links
    `:271-275`.
  - **Test:** `tests/test_docs_links.py:134-188`. 21 must-pass cases plus two focused
    tests: links in comments, fences (including in lists, in `>` quotes and with
    shorter/other-character inner runs), inline code, footnotes, escaped brackets,
    external and fragment links, valid files and folders, and escaped characters in a
    link target.
- **Claim:** the repo itself has no broken links, and the check works in a git worktree.
  - **Test:** `tests/test_docs_links.py:191-196` runs the script on the checkout. At
    planning time: 53 tracked `.md` files, 60 relative links, 0 broken. Because this test
    also runs in `tests.yml`, a broken link on main will turn code PRs red too, which is
    intended.
- **Claim:** the tests really test the script.
  - With `scripts/docs_links.py` removed, all 42 tests fail; with it, all 42 pass. The
    tests call the script as a subprocess, so a missing script fails each test instead of
    breaking collection.
  - Single-line changes to the fence rule (`:87` not stripping `>`, `:107` `>=` to `==`)
    and to the link rescan in `inline_links` each turn exactly one test red.
- **Claim:** the workflow step runs the check.
  - **Checked:** `.github/workflows/docs-checks.yml:45-48`. Confirmed by this PR's own CI
    run.

Fixes #98

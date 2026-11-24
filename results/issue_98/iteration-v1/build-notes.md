# Build notes — issue 98, docs-checks-internal-links

Target: eduralph/nl-shell, built on the wave's integration branch
`pdca-integration/main-r31e6545f56bb` @ `a972610` (main + #97's folded patch), so
`.github/workflows/docs-checks.yml` and its freeze step exist. Line refs below are in the
patched worktree.

## What changed

1. **`scripts/docs_links.py`** (new, stdlib only). Written fresh from the brief's link rule
   (decision 5); I did not look at the parent issue-7 patch.
   - Step 1, comments: `strip_comments` (`scripts/docs_links.py:68`). Closed comments are
     replaced by their newlines only, and an unclosed `<!--` blanks the rest of the file.
     Line numbers stay correct either way.
   - Step 2, fences: `fence_view` + `strip_fences` (`:80`, `:87`). Each line is stripped of
     leading whitespace, `>` markers and one list marker (which must be followed by
     whitespace or end of line, so `---` frontmatter is not taken as a `-` marker). Then a
     3+ backtick or tilde run opens a fence. The fence closes at a line, stripped the same
     way, that starts with a run of the same character at least as long. Fenced lines,
     the fence lines included, are blanked.
   - Step 3, inline code: `strip_inline_code` (`:115`), run per paragraph (consecutive
     non-blank lines). A backslash before ASCII punctuation is skipped as an escape pair,
     so `` \` `` does not open a span. A backtick run is matched to the next run of exactly
     the same length. An unmatched run is literal text.
   - Step 4: inline and image links via `inline_links` (`:162`): an unescaped `[`, its
     matching `]` (nesting counted), then `(`, then a dest with balanced parens up to
     whitespace or the closing `)`. After each `[` the scan carries on from the next
     character, so `[![badge](img.svg)](https://…)` yields both links. Reference
     definitions use `REFDEF_RE` (`:53`): any indentation, any `>` markers, `[^…]`
     footnotes skipped. `target_of` skips scheme links and pure `#` links, strips the
     fragment and undoes escapes. `main` (`:274`) resolves the path against the file's
     directory and requires a tracked file or a directory that holds a tracked file
     (`.` counts).
   - Repo root comes from `git rev-parse --show-toplevel`, and files from `git ls-files -z`.
     It never opens `.git`, so it works in a worktree where `.git` is a file.
   - Output is one line per broken link, `file:line: broken link: dest`, plus a summary
     line. Exit codes: 0 clean, 1 broken links, 2 git error.
   - The docstring lists the known gaps the brief names, plus "fragments not checked
     against headings" (out of scope in the brief).
2. **`tests/test_docs_links.py`** (new). There are 7 must-fail cases and 16 must-pass
   cases (parametrized), one extra ordering test, and the live-checkout test. That is 25
   tests in total. Each must-fail case asserts exit 1 and that both `docs/page.md:` and
   `broken link: <dest>` appear on stdout. The git identity comes from env vars
   (`GIT_AUTHOR_*`, `GIT_COMMITTER_*`, `GIT_CONFIG_NOSYSTEM`), never host config. The
   script is run as `sys.executable <path from __file__>` and is never imported.
3. **`.github/workflows/docs-checks.yml:47-48`**: one new step, "Relative links resolve",
   which runs `python -I scripts/docs_links.py`. It sits after the freeze step. Trigger,
   permissions and checkout are unchanged. I also extended the header comment by one line
   (`:4-5`).

## Choices and things I ruled out

- **List markers before reference definitions.** The rule says "at any indentation, after
  any `>` markers". It does not say after a list marker, so `- [t]: x.md` on the marker
  line itself is **not** checked. The nested-list must-fail case therefore puts the
  definition on an indented continuation line of a nested item, which is how I read
  "(any indentation)" in the round-3 note. If the maintainer meant the marker line too,
  it is a one-line change: strip `LIST_MARKER_RE` in front of `REFDEF_RE`.
- **Absolute paths (`/docs/x.md`).** The rule says "resolve relative to the file's
  directory". The script does exactly that, so a leading-`/` path resolves outside the
  repo and is reported as broken. The live tree has none. I did not add repo-root
  resolution because the rule does not ask for it.
- **The closing fence may carry trailing text.** The rule says the closing line "starts
  with a run … at least as long". I followed that literally. CommonMark would also
  require nothing after the run. That difference falls under "anything else CommonMark
  does".
- **Base-commit copy of the script in CI** (the pattern the freeze step uses). Ruled out:
  the brief says "running `scripts/docs_links.py`". A PR that edits this script is also
  caught by `tests/test_docs_links.py` in `tests.yml`. `-I` is kept to match the
  neighbouring step.
- **Rescanning from `[`+1 instead of skipping past a whole link.** Skipping is simpler,
  but it would miss the image inside a badge link (`[![…](img)](url)`). Rescanning costs
  nothing extra in code.

## Evidence

- Live tree: `python3 -I scripts/docs_links.py` prints
  `60 relative links in 53 Markdown files, 0 broken`, exit 0. That matches the brief's
  planning-time count exactly.
- Brief's repro: I pointed `docs/design/adr/README.md`'s link at `0001-missing.md`. The
  script printed `docs/design/adr/README.md:30: broken link: 0001-missing.md` and exited 1.
  Then I reverted the file with `git checkout`.
- C4 through the project runner (`engine/scripts/run-verify.sh`, with `PDCA_BUNDLE` and
  `PDCA_WORKTREE` set), on the final patch.diff: green leg `ran 25, failed 0`, red leg
  `ran 25, failed 25`, `PDCA-EVIDENCE: C4 PASS`.
- Whole suite (`engine/scripts/run-suite.sh`): `131 passed`, T3 PASS.
- The workflow step was checked only by reading it. Per the brief, the draft PR's CI run
  is what exercises it.

## Refuting my own test

- **(a) Genuine red? Yes.** C4 removed `scripts/docs_links.py` (it is outside the
  non-behavioural paths) and re-ran the tests: 25 of 25 failed. They failed on
  assertions (exit 2, "can't open file"), not with a collection error. That red would
  also come from a missing script, so I added two parser mutations to show the tests bind
  the logic. (1) With reference definitions switched off, the `reference definition` and
  `nested-list reference definition` cases went red (2 failed, 23 passed). (2) With the
  list-marker strip in `fence_view` removed, `fence on a list-marker line` went red
  (1 failed, 24 passed). Both mutations were reverted with `sed`. The final file has no
  trace of them (`grep -c 'MUT\|if False'` → 0), and the final C4 run is on the restored
  file.
- **(b) Production path? Yes.** Each test runs the real `scripts/docs_links.py` as a
  subprocess, through the same entry point CI uses. Nothing is copied or mocked.
- **(c) Fixture includes the fault? Yes.** Each must-fail fixture is a real git repo with
  a committed `.md` file whose link target is untracked. The live test runs against the
  real nl-shell checkout, which is a git worktree where `.git` is a file. That is the case
  the brief calls out.

## Commit-readiness

nl-shell has no formatter config, no `.pre-commit-config.yaml` and no installed git hooks
(only sample hooks), so there was nothing to run. I kept every line at 92 columns or less
(the peer `tests/test_docs_checks.py` goes up to 94). Imports were checked by eye:
neither file has an unused import. Neither pyflakes nor ruff is installed.

## Housekeeping

One command wrote a stray `git diff` output to `/tmp/_unused`, outside the harness roots.
That was a mistake on my part. It holds only a copy of this diff and has no effect on the
bundle. I did not delete it, per the no-cleanup rule.

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

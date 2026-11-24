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

# Adversarial review: issue 7, docs-checks-adr-immutability-links (iteration 3)

I could not refute the immutability check. The link checker still has two concrete false passes: real broken links that it does not report. Both are small parser gaps, not design problems.

**Evidence.** pytest is not installed in this sandbox, so I could not re-run the suite. I used the frozen logs instead. `gate-logs/C4-verify.log` shows the red leg as 97 of 97 failed, with 0 collection or import errors. That is a real red: `tests/test_docs_checks.py:20-21` resolves `scripts/docs_checks.py` from the test file and runs it as a subprocess, so reverting the script turns every test red instead of breaking collection. The tests drive the shipped script, not a copy of it. The live link check also passes on the patched tree: `python3 scripts/docs_checks.py links` printed `OK (60 relative links checked)`, which matches brief (c).

## Findings

- NEEDS-HUMAN [impl] — `scripts/docs_checks.py:455-460`: an unclosed `<!--` in prose blanks out the rest of the file, so later broken links are never seen. When `find("-->")` fails, `end = n`. Concrete case: `case.md` = `Write <!-- to open.\n\n[x](missing3.md)\n` gives `docs-links: OK (0 relative links checked)` with exit 0. CommonMark treats an inline `<!--` with no closing `-->` as plain text, so `missing3.md` is a real broken link, and brief (b) says it must fail. Fix: if there is no closing `-->`, treat the `<!--` as plain text instead of masking to the end of the file. Only an HTML block that starts at the beginning of a line runs to the end of the document. Add a must-fail regression test.
- NEEDS-HUMAN [impl] — `scripts/docs_checks.py:363` (`REFDEF_RE = ^ {0,3}\[…`), used at `:529-534`: reference definitions are matched against raw line indentation, not indentation relative to the list item that contains them. A reference definition nested in a list item at column 4 or more is skipped. Concrete case: `1. a\n   - b\n\n     [r]: missing2.md\n` gives `OK (0 relative links checked)`, but `[r]: missing2.md` is a valid reference definition inside the nested item. This is the same container-column problem that iteration 2's carry-forward fixed for fences and indented code. It was not applied to reference definitions. Fix: measure the allowed 0-3 space indent from the content column that `mask_code_blocks` already tracks, and add a must-fail regression test.
- `scripts/docs_checks.py:293-295` (`renames_between`), non-blocking note: following renames on the base branch depends on git's default 50% similarity threshold for `-M`. I reproduced main ratifying a short 6-line proposal (git mv draft/ to accepted/ plus the status change). Git paired the files at only **R052**, just above the cutoff, so the PR's stale body edit was caught (exit 1). A slightly shorter file, or a ratification commit that also touches the body, would fall below 50%. The rename would then be missed, and the iteration-2 regression would come back silently. The real proposal 0001 is long, so this is not reachable today. Matching proposals by `NNNN` across `draft/` and `accepted/` would remove the dependence on similarity. I'm not raising this for routing.

## Immutability attacks I tried that did not break the check

- A frozen file replaced by a symlink (type change `T`): fails, because the blob bytes differ.
- Whitespace or comment-only edits to the status line (`Accepted` to `Accepted `): fails, because `allowed_next` rejects accepted to accepted.
- Status line moved, or an extra frontmatter key added: fails, because more than one line differs.
- A frozen record renamed or moved (accepted/ back to draft/): fails at the old path.
- Delete plus re-add with low similarity: fails as a deletion.
- Diverged history, with an ADR accepted on main after the PR branched: covered by tests at `tests/test_docs_checks.py:408-459`, which I read but could not run.
- Live statuses (`docs/design/{adr,proposals,specs}`): none is frozen by mistake. ADR-0008's `Proposed (…superseded by ADR-0019)` stays editable, all specs and proposal 0001 are `draft`, and 0005-0007 and 0011 are frozen as decision 1 requires.

## Link-parser cases I tried that are handled correctly

A link title (`"t"`), a link after a fence with an info string, a lazy fence that ends a list, a tab after a list marker followed by indented code (correctly treated as code, per CommonMark example 5), a fence inside a blockquote, an indented link in a blockquote, and a link inside an HTML block.

## Reviewer verdict

I found no unwarranted claim in `check-gates.json`. C4 "red without the fix (97 of 97 failed)" is backed by the log, and the failures are real assertion failures, not collection errors. T4 is deferred to publish, and the gate says so. Running the base copy of the script (a PR can edit `scripts/docs_checks.py` to weaken its own check) remains the maintainer's call, as recorded in the carry-forward. I did not re-file it.
<!-- pdca:leaf-complete -->

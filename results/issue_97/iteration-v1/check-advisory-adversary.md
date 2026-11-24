# Adversarial review — docs-checks-adr-immutability

**Overall: I could not refute the core fix.** The red→green proof is real, and the brief's must-fail and must-pass cases all hold. What I found are gaps at the edges plus one design-level bypass. None of them blocks this bundle.

## Things I tried to refute and could not

- **The evidence (`gate-logs/C4-verify.log`).** The red leg is a clean red: 63 of 63 tests fail with 0 collection errors. The tests run the real `scripts/docs_checks.py` as a subprocess (`target/tests/test_docs_checks.py`, `run_check`), not a copy of its logic. Every must-fail case checks for exit 1, the offending path in stdout, and the word "supersede". A missing or crashing script exits 2 with no path, so it cannot pass these by accident.
- **Brief coverage.** Each listed must-fail and must-pass case has its own scenario, including Accepted→Implemented, status plus body changed together, ADR-0008-style `Proposed (… superseded …)`, template comments, quoted values, diverged branches, and CRLF.
- **Inputs I checked against `target/scripts/docs_checks.py` (the first I ran; the rest are from reading the code):**
  - Accepted→Implemented fails, as it should.
  - Rename, move and delete of a frozen file fail. `check_record` keeps the old path (`scripts/docs_checks.py:267`), and `compare` fails when the head path differs (`:209-212`).
  - A type change (file to symlink) shows up as letter `T`, so it should reach the byte comparison and fail. I did not run this one.
  - A PR that merges main into itself is handled, because the diff starts at the merge-base (`:297`, `:302`).

## Findings

- NEEDS-HUMAN [human] — `.github/workflows/docs-checks.yml:26-29` runs `python scripts/docs_checks.py` from the PR's own checkout. **Failing case:** one PR edits the body of ADR-0001 and also changes `scripts/docs_checks.py` so `main()` returns 0. The job goes green and the frozen ADR is edited. The brief requires `pull_request` (not `pull_request_target`), which is the right call for safety, but it means the PR controls the checker. One option: run the base commit's copy (`git show "$BASE:scripts/docs_checks.py" | python - immutability …`), with a fallback for the PR that first adds the script. Another option: make `scripts/docs_checks.py` and the workflow CODEOWNERS-protected. Either way this is a design decision, and the brief did not ask for it.
- NEEDS-HUMAN [human] — `scripts/docs_checks.py:37` / `:59-60` lets any text follow `Superseded by ADR-NNNN` on the status line, as the brief asks ("any text after that prefix"). **Case I ran:** an Accepted ADR changed to `status: Superseded by ADR-0002; actually we now decide Y instead of X` exits 0. So a status-only PR can still rewrite the decision in one frontmatter line. If the human wants that closed, a tighter pattern like `^superseded by adr-\d{4}(?:\s*(?:,|and)\s*adr-\d{4})*\s*$` would still allow ADR-0007's real `Superseded by ADR-0016 and ADR-0017`.
- NEEDS-HUMAN [impl] — `scripts/docs_checks.py:117` (`status_line_index`) only sees frontmatter when the first line is exactly `---`. A file saved with a UTF-8 BOM (byte-order mark, the invisible `EF BB BF` prefix some Windows editors add) has first line `﻿---`, so it is read as having no frontmatter and is never frozen. **Case I ran:** an Accepted ADR with a BOM, body edited, exits 0. No current record has a BOM (ADR-0001 starts with `2d2d2d`), so this matters only for future files. The fix is small: strip a leading `﻿` in `line_text`, or decode with `utf-8-sig` for line 0, and add a test.
- NEEDS-HUMAN [impl] — `scripts/docs_checks.py:56-57` (`AdrClass.frozen`) treats an empty value (`status:` with nothing after it) as frozen, because `""` does not start with `proposed`. **Case I ran:** an ADR with a blank `status:` and an edited body exits 1. Rule r2 says a missing status means not frozen, and a blank value is closer to "missing" than to "Accepted". This only produces a false failure, and the ADR template ships `status: Proposed` (`docs/design/templates/adr.md:4`). Low priority: either treat an empty value as not frozen or add a test that pins the current behaviour.
- Minor, no action needed: `status_line_index` (`:121-126`) uses the first `status:` key. YAML uses the last one. A frontmatter with `status: Proposed` followed by `status: Accepted` is treated as Proposed and stays editable (I ran it: exit 0). This is contrived, and no current record has a duplicate key.
- Unverifiable here: the brief says the "runs on every PR" half is checked only by the draft PR's own CI run. Nothing in `check-gates.json` shows that run yet (T4 is `deferred`). The human should confirm the `Docs checks / docs` job shows up on the draft PR and that a throwaway edit to ADR-0001 turns it red.

<!-- pdca:leaf-complete -->

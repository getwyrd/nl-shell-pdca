# Adversarial review — issue 80 / pinned-tldr-snapshot (round 3)

**Result: I tried to refute the fix and could not.** No NEEDS-HUMAN findings. The notes below are low-severity and none of them blocks.

## What I attacked, and what held

- **Red→green evidence.** `gate-logs/C4-verify.log` shows a real red leg: 10 of 12 tests fail on assertions, not collection errors. Examples: `tests/test_tldr_snapshot.py:114` "real pinned corpus must be shipped", and the `:58` shipped-file assertion. The 2 tests that pass on the red leg are the audit positive controls (`:104-109`). They don't touch production, so they are expected to pass. I re-ran the green leg on `$PDCA_TARGET` with the harness venv's pytest 9.1.1 and got `12 passed in 1.37s`. T3 shows `1343 passed, 1 skipped`.
- **Is the anchor real, or just self-consistent?** I recomputed it with my own script from the shipped `data/tldr/pages.jsonl` bytes, without using the reader or the manifest. Results: 6,837 records (4,754 common + 2,083 linux), 4,050,595 bytes, inventory SHA-256 `4ce7ecdf…d960`. All three match the Plan values in brief.md:42-44. The `tar.md` / `apt.md` blob IDs and the `LICENSE.md` blob `9b4ebcb9…` also match brief.md:46. My first recompute gave a different digest, but that was my own bug: in Python, `"\0100644"` parses as the octal escape `\010` followed by `0644`. Production writes `\000100644` at `scripts/tldr_snapshot.py:49`, which is correct. A fabricated corpus would need SHA-1 blob collisions to pass, so the anchor is a real external check.
- **Is the test a parallel copy of production?** No. Each corruption case runs the real `scripts/tldr_snapshot.py export --root <copy>` in an audited child (`tests/test_tldr_snapshot.py:143`) and asserts the specific error message (`:148-159`). I checked which production checks each case pins:
  - `fabricated` (`:119`, `:139-141`) swaps one ASCII byte. It recomputes the page's manifest entry and `corpus_sha256`, and the count and byte total stay the same. Only the `digest != INVENTORY` clause at `scripts/tldr_snapshot.py:54` can reject it, so deleting that clause turns the test red.
  - `path` (`pages/common/../escape.md`) would hit the ordering check at `:41` if the parts check at `:43` were removed. The test would then fail on the wrong message, so `:43` is pinned too.
  - `extra` (a `"trusted": true` key) pins the strict schema check at `:38`, which closes the iteration-1 trust-label pass-through.
- **Earlier findings.**
  - The U+2028/U+2029/U+0085 split bug is fixed: the reader uses `split("\n")` at `scripts/tldr_snapshot.py:32`, and the `digest`/`manifest` cases inject those characters (`tests/…:122`). The shipped corpus contains none of them, and no CR or BOM either.
  - All reads specify the encoding.
  - The README rebuild now checks Git tree modes, not tar permission bits (`data/tldr/README.md:70`, `:97-98`).
  - No path in the corpus needs `git ls-tree` C-quoting, so the recipe's unquoted `split("\t")` parsing (`README.md:68`) works for this revision.
  - Re-serialising the parsed records canonically reproduces `pages.jsonl` byte for byte, which matches the recipe at `README.md:83`.
- **Audit vacuity.** The positive controls (`tests/…:104-109`) prove the hook is installed and blocks both `socket.connect` and `subprocess.Popen` before they run. The event names at `:20-22` match CPython's audit table, and `os.fork`/`os.forkpty` were added since round 2. The reader imports only `argparse, hashlib, json, pathlib, sys` (`scripts/tldr_snapshot.py:3-7`), so there is no native or non-stdlib escape.
- **Threat model.** `.oss-scanner/threat_model.md:101-102` keeps the `(local-reference, ADR-0016)` label on the man/`--help` bullet. Round 1 had dropped it; that is now fixed. The new paragraph at `:111-114` matches ADR-0016:43 and brief.md:36, and it makes no REPL-wiring claim.

## Low-severity notes (not refutations, no action required)

- `scripts/tldr_snapshot.py:43`: `len(Path(path).parts) != 3` accepts `pages/common/./x.md`, because `pathlib` drops the `.` part. It cannot ship, though: the raw path is part of the inventory anchor at `:49`/`:54`, so any such path fails there. Treat it as hardening only.
- `scripts/tldr_snapshot.py:66`: a deeply nested JSON line in a tampered `--root` copy (with `corpus_sha256` recomputed) raises `RecursionError`, which the `except` list doesn't catch. The run still exits non-zero with empty stdout, because validation finishes before any output. The only cost is a traceback instead of the "invalid tldr snapshot" message.
- `tests/test_tldr_snapshot.py:53`: if the wrapper child crashes before its `finally` block writes the report, the test errors with `FileNotFoundError` instead of failing an assertion. This is cosmetic.
- I did not re-run the network acquisition recipe (`data/tldr/README.md:45-94`); this check is offline by design. The binding check is the anchor, and it matches the Plan value independently, so this does not weaken the verdict.

## Verdict on the reviewer's likely claims

The C4 PASS and T3 PASS rows in `check-gates.json` are backed by the frozen logs and by my own re-run. The T2 row ("no security-relevant path touched") is advisory, and it undersells the patch, which does edit the threat model as the brief asked. That is a gate-classification detail, not a defect in the fix. I found no unwarranted claim to flag.

<!-- pdca:leaf-complete -->

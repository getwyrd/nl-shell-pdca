## Summary
**User impact:** nl-shell promises that its command reference works with the
network unplugged, and the design lists a bundled copy of the tldr pages as part
of that reference. That copy was never added. Nothing in the repository supplies
tldr examples, so the planned reference harvest has nothing to build from and
the license review has nothing to check.

This PR adds a pinned copy of the English tldr pages for common and Linux
commands, with the upstream license and credit. It also adds a small offline
tool that checks the copy and exports it for the harvest.

Reported in [#80](https://github.com/getwyrd/nl-shell/issues/80).

## What to look at
- **Size:** the diff is about 6 MB. Almost all of it is two generated data files
  (`data/tldr/pages.jsonl`, `data/tldr/source.json`) that you don't need to read
  line by line. The test recomputes a fixed fingerprint of the whole page set, so
  you can check the data by running it.
- **The parts to review by eye:** the reader script, the test, the license and
  credit files, the README rebuild steps and a five-line threat-model change.
- **Try it** from a checkout of this branch, with the network off if you like:
  ```sh
  python3 scripts/tldr_snapshot.py export | head -n 2
  python3 -m pytest -q tests/test_tldr_snapshot.py
  ```
  Each exported line is one tldr page with its upstream path, its text, the
  pinned revision, `language: "en"` and `provenance: "local-reference"`.
- **Licensing:** the page text stays under CC BY 4.0, separate from nl-shell's
  Apache-2.0 code license. Whether generated datasets or model weights may be
  released is still open in #34. This PR does not decide that.

## Root cause
ADR-0003 and ADR-0016 both name a vendored tldr snapshot as local reference
data, but no change ever added one. There was no pinned source, no license
record and no reader for the future harvest (#23) to call.

## Fix
- `data/tldr/pages.jsonl`: all 6,837 English pages under `pages/common/` and
  `pages/linux/` of tldr-pages/tldr at
  `eacda7020c4102729187c38c35ce28fac00365c9` (4,050,595 bytes). They are stored
  as sorted path/content JSON lines, with the original text and placeholders
  unchanged.
- `data/tldr/source.json`: the upstream repository, revision, selected folders,
  a note on how the pages were repackaged, per-page byte counts and hashes, a
  checksum of the whole file and a fingerprint of the page set.
- `data/tldr/LICENSE.md` (the upstream file, byte for byte) and
  `data/tldr/NOTICE.md` (credit to the tldr-pages team and contributors, a link
  to the pinned revision and to CC BY 4.0, and a description of the selection).
- `data/tldr/README.md`: offline usage, plus a step-by-step rebuild from a `git
  clone` that never runs upstream code. It also notes that a future refresh must
  update the pinned values in the script and the test.
- `scripts/tldr_snapshot.py export`: standard library only, and it imports
  nothing from the REPL. It checks everything before it prints a single page. It
  never opens a network connection or starts a process.
- `.oss-scanner/threat_model.md`: moves tldr out of the Trusted list into its
  own local-reference paragraph, matching ADR-0016. The man-page and `--help`
  entry keeps its local-reference label.

## Verification
- **Claim:** the shipped pages are exactly the pinned upstream selection, not
  just consistent with their own manifest.
  **Checked:** `tests/test_tldr_snapshot.py:56-74` recomputes each page's Git
  blob ID from the shipped text and hashes the sorted inventory. It compares the
  result with a fixed SHA-256
  (`4ce7ecdff5a4da72bfef4378f027ad141b7daa28dc6b0a68f57905a6e080d960`) taken
  from the upstream Git tree when the change was planned, along with the page
  count and byte total. `pages/common/tar.md`, `pages/linux/apt.md` and
  `LICENSE.md` are also checked against their upstream blob IDs.
- **Claim:** the reader refuses a bad copy before it exports anything.
  **Checked:** `scripts/tldr_snapshot.py:20-56` checks, in order: source
  identity (:22), the license (:26), the file checksum (:29), the record shape,
  rejecting extra keys such as a planted `"trusted": true` (:37-38), path order,
  duplicates and path form, the per-page manifest (:51), and finally the pinned
  count, byte total and fingerprint (:54).
  `tests/test_tldr_snapshot.py:112-159` damages temporary copies in nine ways.
  One of them edits a page and then recomputes every local hash to match, so
  only the fixed fingerprint can catch it. Each case must fail with its own error
  message and print nothing.
- **Claim:** the data is split only on real line breaks.
  **Checked:** `scripts/tldr_snapshot.py:32` splits on LF only, so U+2028,
  U+2029 and U+0085 inside page text don't break records apart. Two of the
  damage cases above put those characters into a page.
- **Claim:** export is repeatable and fully offline.
  **Checked:** `tests/test_tldr_snapshot.py:17-40,91-101` runs the real export
  twice, in a child process with a Python audit hook (a callback that sees every
  socket and process call). The hook blocks and records network and process
  events. The test requires no recorded events, byte-identical output on both
  runs, and the expected fields on every page. It also checks that command text
  from `tar.md` comes through as plain data.
  `tests/test_tldr_snapshot.py:104-109` proves the hook works: one child tries a
  loopback connection and another tries to start a process, and both must be
  caught and blocked.
- **Claim:** the threat-model change is narrow.
  **Checked:** `.oss-scanner/threat_model.md:101-102` (man pages and `--help`
  keep "local-reference, ADR-0016") and `:111-114` (the new tldr paragraph). On
  `main` the old wording is at `.oss-scanner/threat_model.md:101-102`, and
  `docs/design/adr/0016-taint-model-v2.md:43` lists tldr as local-reference.
- **Test:** `tests/test_tldr_snapshot.py`. With the data and script removed,
  10 of 12 tests fail on assertions. The two hook self-checks pass either way
  because they don't use the snapshot. With the change, all 12 pass, and the
  full suite passes (1343 passed, 1 skipped).

Fixes #80

# Result — issue 80 / pinned-tldr-snapshot

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: Make a real, pinned tldr reference snapshot available offline, with upstream license and attribution, for the future #23 harvest to consume.
- Success criterion: On a clean patched checkout, ordinary pytest in tests/test_tldr_snapshot.py verifies that the shipped English common/Linux snapshot matches the Plan-pinned upstream inventory digest below (computed from actual page bytes, not manifest claims), retains its upstream license and attribution, and exports all shipped pages deterministically with revision, language and local-reference provenance; corruption is rejected, and audited offline export completes with zero network or process-execution attempts, with positive controls proving those audits detect attempts.
- Repo + branch target: getwyrd/nl-shell @ main
- Scope (one logical fix) / out of scope: The missing pinned, attributed local tldr source and its offline consumption contract for #23, including reproducible acquisition instructions and integrity evidence. Keep these one source-vendoring deliverable. Out of scope: a design proposal/index entry, executable network acquisition/refresh tooling, #23's VM/man-page harvest, executing examples, training/dataset generation, runtime reference search, packaging/install integration, additional languages/platforms, broad security-policy changes and #34's release license decision.

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (10 of 12 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — no security-relevant path touched
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T4 host docs checks: immutability, checker tests, links, and ADR index: pass — adr_index: 28 ADRs, 0 problems
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Task under review: issue #80 — vendor a pinned, attributed English common/Linux tldr snapshot (upstream eacda70) under `data/tldr/`, with a stdlib offline reader/export at `scripts/tldr_snapshot.py`, a regression in `tests/test_tldr_snapshot.py`, and a narrow threat-model clarification, for the future #23 harvest.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | Brief is concrete and falsifiable: fixed inventory anchor, count/bytes, LICENSE blob, audit + positive controls, corruption cases (brief.md:6-7, 42-52); scope keeps #23/#34 out. |
| C2 Reproduction (red pre-fix) | PASS | No C2 gate; I re-ran it myself: with `data/`, `scripts/tldr_snapshot.py` and the threat-model edit stashed, tests/test_tldr_snapshot.py gives 10 failed / 2 passed, all executed assertion failures (:58, :114), no collection errors; the 2 passes are the positive controls, which by design touch no production code. Matches gate-logs/C4-verify.log red leg. |
| C3 Change | PASS | Patch is one logical change: 6 new files under data/tldr/ plus scripts/tldr_snapshot.py, the test, and a 2-hunk edit to .oss-scanner/threat_model.md:101-102,111-114; no ADR, proposal or index changed (host-docs immutability OK). Previous rounds' gap (missing corpus/metadata/license) is closed. |
| C4 Verification (red→green) | PASS | Re-ran in $PDCA_TARGET with the instance .venv: green 12 passed; red 10 failed / 2 passed. Agrees with gate-logs/C4-verify.log ("red without the fix (10 of 12 failed), green with it"). |
| C5 Causal adequacy | PASS | I confirmed the corpus is the real upstream: the GitHub tree API for eacda70 (truncated=false) gives 6,837 blobs, all 100644, 4,050,595 bytes, anchor 4ce7ecdf…d960, the same as my recompute from the shipped pages.jsonl; the README recipe run against a shallow fetch of that commit reproduces pages.jsonl, source.json and LICENSE.md byte for byte. The reader verifies everything before it writes anything (scripts/tldr_snapshot.py:20-55 then :68-71). It enforces exact `{path,content}` str keys (:38) and the fixed anchor (:54), and splits on LF only (:32). No capability probe or guard. |
| T1 Structure | PASS | Stdlib-only script in scripts/ (imports argparse/hashlib/json/pathlib/sys only, scripts/tldr_snapshot.py:3-7); no REPL/model import, no network or subprocess code; data stays tracked text with no .gitattributes change and no binary hunks in patch.diff. |
| T2 Shape | PASS | Gate passed as "no security-relevant path touched" (gate-logs/T2-threat-model.log). I reviewed the clarification the brief asks for: the tldr clause is gone from the Trusted bullet, man/`--help` keep "(local-reference, ADR-0016)" (threat_model.md:101-102, which fixes the round-1 finding), and the new Local-reference paragraph (:111-114) matches ADR-0016:43 without changing what taint does. |
| T3 Runtime | PASS | gate-logs/T3-suite.log: 1343 passed, 1 skipped, exit 0 on the patched worktree; the 5 warnings are pre-existing forkpty DeprecationWarnings in tests/test_session.py, unrelated to this patch. |
| T4 Contribution | N/A | T4-contribution is `deferred`: pr-description.md is not drafted yet, and the gate re-runs at publish (gate-logs/T4-contribution.log). The host-docs half passed: immutability OK, 0 broken links, ADR index has 0 problems (gate-logs/host-docs.log). |
| T5 Judgment | PASS | Earlier findings are fixed: positive controls (test:104-109), nine corruption cases including a fabricated page with a recomputed manifest that must fail the anchor (:119-150), and a forged `trusted` key (:124). Also fixed: UTF-8/LF reads, tar/apt blob IDs, os.fork/forkpty audited, and neutral README paths. Nits only, none blocking: the README recipe builds `inventory` in its loop and then overwrites it (README.md:52,61 vs :65); `"\000100644"` (scripts/tldr_snapshot.py:49, test:71) is correct but hard to read, and `"\0" + "100644"` would be clearer. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether shipping about 6 MB of CC BY 4.0 data (pages.jsonl 4.57 MB plus source.json 1.52 MB) in the Apache-2.0 repo is acceptable. Then confirm that NOTICE.md/LICENSE.md give enough attribution for in-repo redistribution, which is separate from the #34 dataset/weights decision. The code cannot settle this: it is a license and repo-size call, and refreshing the snapshot later means editing pinned constants in both script and test (README.md:90-93). Prior art: `gh pr list --search tldr` finds no PRs, which matches the brief's path-based check. |

<!-- pdca:leaf-complete -->

### Advisory — adversary

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

### Advisory — security-review

# Security review — issue 80 / pinned-tldr-snapshot

Attacker-reachable inputs touched: one, the vendored tldr page text (`data/tldr/pages.jsonl`). Under threat model item 10 (training data as a supply-chain input, `.oss-scanner/threat_model.md:90-92`) it is upstream community text that will later feed the #23 harvest and the shipped dataset. Nothing in the runtime path (REPL, gate, PTY, model, reader) is touched.

**No finding.** What I checked:

- **Tampering after pinning.** `scripts/tldr_snapshot.py:20-56` rebuilds every page's Git blob ID from the actual page bytes. It hashes those into an inventory and compares the result with a constant in the code (`INVENTORY`, line 10, and again at line 54), along with the page count, the byte total, the corpus SHA-256 and the license blob. The anchor `4ce7ecdf…d960` is the one Plan computed on its own (brief.md:44), not a value the builder supplied, so swapping the corpus would also require editing the code constants and the test's `ANCHOR` (`tests/test_tldr_snapshot.py:16`), and review would see that. The `fabricated` case (test lines 119-141: content changed, manifest and corpus digest recomputed to match) is rejected by the inventory anchor. This is the attacker case, and it is tested.
- **Provenance and trust label.** Every exported record carries `provenance: "local-reference"` (`scripts/tldr_snapshot.py:69-70`), and the test asserts it on every record (test line 99). The threat model edit (`.oss-scanner/threat_model.md:101-114`) moves tldr *out* of the "Trusted" list into its own local-reference paragraph that says it is "not executable commands or trusted instructions". This lowers trust rather than raising it, which matches ADR-0016 and the "untrusted text is labelled trusted" High row. No trust boundary moves the wrong way.
- **Path handling.** A path must start with one of the two prefixes, end in `.md`, sort strictly after the previous path (so no duplicates), and have exactly three parts (lines 41-44). `pages/common/../escape.md` has four parts and is rejected, and the `path` corruption test covers it. The exporter writes only to stdout and never builds file paths from record data, so path traversal is not reachable here at all.
- **Hidden characters in page text.** I scanned all 6,837 pinned pages for C0/C1 controls (escape sequences such as ESC included), DEL, Cf/Co/Cn characters and bidi overrides/isolates. There were none. The reader doesn't filter these, but the pinned inventory means any change to the content fails the check, and filtering before training belongs to the #23 harvest, not to this source-vendoring step.
- **Network/process use.** The reader imports only `argparse`, `hashlib`, `json`, `pathlib` and `sys`. The test wrapper (test lines 17-40) installs a `sys.addaudithook` (a Python hook that sees socket and process-start events) and records zero network or process attempts during export. The positive controls (test lines 104-109) show the hook does catch `socket.connect` and `subprocess.Popen`. This meets "Locally complete" (`threat_model.md:203`).
- **Validation before output.** `verified_pages` finishes before any page is written (lines 65-71). Every corruption case asserts empty stdout (test line 145), so a half-valid corpus never sends some pages downstream.
- **Resource use.** `--root` is set by whoever runs the build, not by an attacker, and the input is bounded by the pinned 6,837 pages and 4 MB.
- **Rebuild recipe** (`data/tldr/README.md`). It runs only `git ls-tree`, `cat-file` and `show` on a `--no-checkout` clone, which runs no upstream hooks or code. A path with unusual characters (which `ls-tree` would quote, since the recipe doesn't use `-z`) would break the anchor assertion rather than slip through.

Gate evidence agrees: C4 is red without the fix (10 of 12 failed) and green with it, and T3 passes the full suite (1343 passed).

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] Validation — fitness-to-purpose — Decide whether shipping about 6 MB of CC BY 4.0 data (pages.jsonl 4.57 MB plus source.json 1.52 MB) in the Apache-2.0 repo is acceptable. Then confirm that NOTICE.md/LICENSE.md give enough attribution for in-repo redistribution, which is separate from the #34 dataset/weights decision. The code cannot settle this: it is a license and repo-size call, and refreshing the snapshot later means editing pinned constants in both script and test (README.md:90-93). Prior art: `gh pr list --search tldr` finds no PRs, which matches the brief's path-based check.
- [x] external dependency: loopback-socket — the execution sandbox denies AF_INET socket creation with PermissionError (errno 1), before socket.connect; the required network audit positive control and hence the complete success criterion cannot be proved here.
- [x] **The main success clause can't be checked offline, so a fake corpus would pass it.** The brief says the test "verifies a nonempty vendored … snapshot against its recorded immutable upstream revision and content hashes". The patch writes both the revision and the hashes. An offline test can therefore only check that the corpus agrees with its own manifest. It can't check that the content really is tldr-pages@`eacda70…`. A made-up or locally edited corpus with hashes recomputed to match would turn green. The only real check against upstream is moved to "record a real upstream acquisition/integrity comparison in Do's evidence" (Design ¶3), and no gate runs that. Fix: say plainly that the gated check is self-consistency only. Then either pin an external anchor the test can check offline and that Do cannot choose, such as the upstream git tree/blob SHA-1s for `pages/common/tar.md` and `pages/linux/apt.md` (and ideally the `pages/` tree hash) written into the brief now from the Plan-time API check, or name the reviewer step that re-runs the refresh/verify command against GitHub.
- [x] **No mechanism is given to prove the code "neither accesses the network nor executes page examples".** The brief requires this in the success criterion and the repro, but never says how a test would show it. Nothing in `pyproject.toml:34-44` blocks network access (no plugin, no marker). If no mechanism is named, Do can write an assertion that passes no matter what the code does. Name one, for example: run the subprocess with a `sitecustomize`/`sys.addaudithook` that fails on `socket.connect`, `subprocess.Popen` and `os.system`/`exec*`, and add a positive control showing the hook trips.
- [x] **The brief says "never trusted", but the threat model lists the snapshot under "Trusted:".** Brief line 8 says "vendored tldr is local-reference, never trusted". The target's `.oss-scanner/threat_model.md:97-102` puts "the vendored tldr snapshot (local-reference, ADR-0016)" under the **Trusted:** heading. ADR-0016:43 labels it `local-reference`, which is a separate class from `trusted` (:41). Design ¶4 says the brief will "Update the threat model to describe … reference text is data, not executable code or trusted instructions". That edit either reclassifies the snapshot in a security document or contradicts its current wording. That is a security-model decision hidden inside a data-vendoring slice. The brief should either quote the current lines and say exactly what changes (for example, moving it out of "Trusted:" or adding a "local-reference" heading), or leave that edit out.
- [x] **The scope covers four deliverables, not one.** The thread asks only for a pinned snapshot plus license/attribution that #23 "can include". The brief also commits Do to (1) the corpus and metadata, (2) a reader/export CLI with an acquisition/refresh command (`scripts/tldr_snapshot.py`, Design ¶3), (3) a new design proposal `docs/design/proposals/draft/0002-pinned-tldr-snapshot.md` with an index row, and (4) the threat-model edit above. `docs/design/proposals/README.md:9` reserves proposals for "larger changes and milestone plans". A proposal shipped together with its own implementation is a second deliverable, and it adds `docs_checks.py` immutability/status surface. The refresh/acquisition code path is network code, and no gated test can run it offline. Consider dropping the proposal, or making it the only deliverable, and splitting refresh tooling from the read/export path.
- [x] **The brief cites a frozen document as its invariant.** "Invariant to restore" and "Citations expected" rely on `docs/plan.md:21–27,94–99,268`. But `docs/plan.md:3-8` says: "**Historical — frozen on 2026-10-14.** … no longer maintained and already differs from the decisions … The live design is in design/". The live statement of the same invariant is ADR-0003 (`docs/design/adr/0003-locally-complete.md:22-23`), and the brief never cites it. That ADR also says local reference is "harvested at install time", and `docs/plan.md:99` says harvested reference docs "need not be redistributed". So the brief should say why redistributing tldr in-repo (rather than fetching it reproducibly, which the thread also allows) is consistent with ADR-0003, instead of resting on the frozen plan.
- [x] **The patch would be too large to review, and that clashes with the contribution gate.** All English `pages/common` + `pages/linux` pages is several thousand pages, roughly megabytes of text, in one JSONL file plus per-page hashes. The brief notes T4 contribution is gating ("Verification contract") but never sizes the diff or says how a reviewer or the reverted C4 leg handles a multi-MB hunk. State the expected page count and byte size, and say whether `.gitattributes` (absent in the target) should mark the file `-diff`/`linguist-vendored`, so the review surface is a known quantity and not a surprise at Check.
- [x] **The milestone citation doesn't resolve in the target.** The brief says "issue slice M1.4; proposal 0001 §M1". `docs/design/proposals/draft/0001-implementation-arc.md:62-72` (§M1) never mentions tldr or an M1.4 slice. M1's "Done when" covers the VM, harvest and sudo-rs. Training-data license checks belong to M2 (:78-79). "M1.4" exists only in the issue title. This is minor, but don't cite it as proposal authority. Also, `pdca.toml` and `engine/scripts/run-verify.sh` (cited under "Verification contract") don't exist in the target, so those claims can't be checked from here.
- [x] size backstop — this slice is behaving oversized: patch is 6006 KB (threshold 100 KB); 2 round(s) already spent (threshold 2). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.
- [x] external dependency: github-https — DNS/HTTPS acquisition unavailable; blocks the real 6,837-page corpus, original license, and actual inventory comparison
- [x] external dependency: audit-socket-runtime — sandbox rejects socket creation with PermissionError before connect_ex reaches socket.connect; blocks the required network audit positive control
- [x] external dependency: pre-commit — configured commit-hook runner is not installed; complete target hooks could not be exercised
- [x] external dependency: github-https — DNS/network access to GitHub blocks acquisition of the pinned source and therefore production implementation and green verification.
- [x] external dependency: pre-commit — missing executable blocks running the target's configured commit hooks; committability is unverified.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: merged-wider
- Iteration delta (if iterating):
- By / date: Eduard Ralph / 2026-11-14

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 7 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

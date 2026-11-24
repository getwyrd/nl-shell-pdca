# Build notes — issue 94, iteration 3

Target: main at 4d040301a2341590ca9c574b2df1cefe34585000. Only the brief, its cited documents/code slices and required runner/hook configuration were consulted; prior iteration bundles and Check rules were not read.

The architecture is the production artifact for this documentation defect. ADR-0023:37–55 defines target contents/consumers, :57–71 defines manifest integrity and adapter identity, and :73–87 defines exact selection and the first target. Paths here are relative to docs/design/ unless otherwise stated. specs/policy-gate/v1.md:33–49 supplies the shared-procedure/package-owned distinction. Neither normative document is changed.

Changes and rationale:

- architecture/05-building-block-view.md:30 adds the target diagram node, with command prompts pointing at backend and an explicitly planned gate edge. :62 explains consumer status; :74 includes both planned REPL inputs omitted previously; :76 marks all gate integration and mismatch confirmation planned; :80 distinguishes the built reader library from REPL wiring. :94 makes harvest per target. :108 lists only target-related built modules, replacing the stale catch-all instead of asserting that unrelated existing modules are still planned. Built evidence is src/nl_shell/targets.py:27–28,145–169,249–276, src/nl_shell/prompts.py:80–91, src/nl_shell/reader.py:198–204 and src/nl_shell/gate/vectors.py:49–53; the carry-forward provides the warning/integration limitations. No runtime implementation is claimed.
- architecture/07-deployment-view.md:15–33 separates planned packaging, integrity and adapters; :38 generalizes package ownership; :67 makes reference systems per target; :69–72 retains BOTH open distribution questions. ADR-0023:41–71 is the authority; no host/channel is selected.
- architecture/08-crosscutting-concepts.md:35,54,114,143,145,166 scopes provenance, gate examples, reader lookup, execution filtering, specifics and local lookup. Taint classes, confirmation levels and offline rules are preserved.
- architecture/01-introduction-and-goals.md:16,37,44 identifies first-target goals/users; 02-constraints.md:18 scopes the constraint; 03-context-and-scope.md:20 scopes the sudo node; 04-solution-strategy.md:23,33 scopes training; 06-runtime-view.md:38 scopes the sudo flow; 10-quality-risks-glossary.md:28,44,55,58–59,70,72,82,105 scopes goals/probes, update mitigation, risks, glossary and sandbox examples. Chapter 09's historical milestone labels remain unchanged. Existing uncertainty about ROCm support and OS defaults is retained, without certifying new OS facts. The unrelated chapter 03 trust row is untouched.
- tests/test_architecture_targets.py:1–65 reads actual architecture files relative to the repository, uses bounded consumer bullets and checks planned status alongside each manifest/adapter requirement. Missing sections raise explanatory assertions rather than next() failures. The diagram assertions bind the corrected destination and planned gate label. These are document relationships, not runtime tests or a semantic proof.

Rejected approaches: no runtime changes were considered appropriate because this is a documentation invariant. Keeping the old catch-all would retain a false status; replacing its one row with four target-specific rows avoids a general inventory refresh. No cost-based rejection of a causal fix was made. A stand-in test runner or copied documentation fixture was ruled out because neither proves the real document changes.

Verification:

The brief explicitly authorizes direct instance-.venv pytest for this docs-only slice. Ran /home/eddie/nl-shell/nl-shell-pdca/.venv/bin/python3 -m pytest -q tests/test_architecture_targets.py against original Markdown: 3 failed (exit 1). Applied documents: 3 passed (exit 0). Then actually reverse-applied the entire document diff while retaining the SAME test, reran: 3 failed (exit 1; red.log). Reapplied the diff and reran: 3 passed (exit 0; green.log). No stand-in pytest was used.

Forced refutation:
(a) Genuine red: YES. The actual reverse-apply and repeat run failed all three collected tests; the test stayed present throughout.
(b) Production path: YES for the documented objective. Path reads go to docs/design/architecture in this worktree, the Markdown changed by patch.diff; no copied fixture or runtime mock is involved.
(c) Fault included: YES. The reverted real chapter 05 lacks the target node/consumer description, chapter 07 lacks the planned runtime/manifest relationships, and chapter 08 retains universal dpkg provenance. All remain included in the test's reads; nothing is curated out.

Ran the actual engine/scripts/run-verify.sh with PDCA_BUNDLE and PDCA_WORKTREE: exit 77, PDCA-UNVERIFIABLE: no behavioral production change to revert (test-only or docs-only patch). This confirms the accepted exception still applies; it is NOT C4 PASS. Full architecture semantic review remains NEEDS-HUMAN, including every chapter and especially chapter 10's goal/probe, sudo mitigation, ROCm uncertainty, point-release, glossary and testing statements. Check must run T3 and host-docs; this document test alone does not discharge those gates or semantic review.

Commit readiness: pyproject.toml defines no formatter/linter. git diff --check passed. The configured .pre-commit-config.yaml:15–38 contains machine-local filename rejection and gitleaks (including staged-blob scanning). Changed paths include no machine-local files. Real gitleaks stdin --no-banner --redact --ignore-gitleaks-allow scanned the complete patch and found no leaks. pre-commit itself is absent from PATH and the instance .venv, so the configured hook orchestration and staged-blob hook could not be run; no fake hook success is claimed.

NEEDS-HUMAN external dependency: pre-commit — missing executable blocks running the target's configured commit hooks; direct gitleaks and whitespace checks do not prove full hook execution

```toml
[[doctor.checks]]
id    = "pre-commit"
cmd   = "pre-commit --version"
hint  = "Install pre-commit==4.7.0 as documented in the target .pre-commit-config.yaml, then run the reviewed hooks over the changed files."
level = "MISSING"
```

No push, PR, ready-mark, commit or merge was performed. Artifacts include the test both at its target path and bundle tests/test_architecture_targets.py. patch.diff contains the Markdown and new test, with no rationale mixed into either.

Changed-line citation ledger (old main line → edited worktree line; every hunk):
- `docs/design/architecture/01-introduction-and-goals.md:16` → `docs/design/architecture/01-introduction-and-goals.md:16`.
- `docs/design/architecture/01-introduction-and-goals.md:37` → `docs/design/architecture/01-introduction-and-goals.md:37`.
- `docs/design/architecture/01-introduction-and-goals.md:44` → `docs/design/architecture/01-introduction-and-goals.md:44`.
- `docs/design/architecture/02-constraints.md:18` → `docs/design/architecture/02-constraints.md:18`.
- `docs/design/architecture/03-context-and-scope.md:20` → `docs/design/architecture/03-context-and-scope.md:20`.
- `docs/design/architecture/04-solution-strategy.md:23` → `docs/design/architecture/04-solution-strategy.md:23`.
- `docs/design/architecture/04-solution-strategy.md:33` → `docs/design/architecture/04-solution-strategy.md:33`.
- `docs/design/architecture/05-building-block-view.md:11` → `docs/design/architecture/05-building-block-view.md:11`.
- `docs/design/architecture/05-building-block-view.md:30` → `docs/design/architecture/05-building-block-view.md:31`.
- `docs/design/architecture/05-building-block-view.md:55` → `docs/design/architecture/05-building-block-view.md:59`.
- `docs/design/architecture/05-building-block-view.md:57` → `docs/design/architecture/05-building-block-view.md:62`.
- `docs/design/architecture/05-building-block-view.md:62` → `docs/design/architecture/05-building-block-view.md:94`.
- `docs/design/architecture/05-building-block-view.md:76` → `docs/design/architecture/05-building-block-view.md:108`.
- `docs/design/architecture/06-runtime-view.md:37` → `docs/design/architecture/06-runtime-view.md:38`.
- `docs/design/architecture/07-deployment-view.md:15` → `docs/design/architecture/07-deployment-view.md:15`.
- `docs/design/architecture/07-deployment-view.md:20` → `docs/design/architecture/07-deployment-view.md:38`.
- `docs/design/architecture/07-deployment-view.md:49` → `docs/design/architecture/07-deployment-view.md:67`.
- `docs/design/architecture/07-deployment-view.md:51` → `docs/design/architecture/07-deployment-view.md:71`.
- `docs/design/architecture/08-crosscutting-concepts.md:35` → `docs/design/architecture/08-crosscutting-concepts.md:35`.
- `docs/design/architecture/08-crosscutting-concepts.md:55` → `docs/design/architecture/08-crosscutting-concepts.md:55`.
- `docs/design/architecture/08-crosscutting-concepts.md:113` → `docs/design/architecture/08-crosscutting-concepts.md:114`.
- `docs/design/architecture/08-crosscutting-concepts.md:142` → `docs/design/architecture/08-crosscutting-concepts.md:143`.
- `docs/design/architecture/08-crosscutting-concepts.md:144` → `docs/design/architecture/08-crosscutting-concepts.md:145`.
- `docs/design/architecture/08-crosscutting-concepts.md:146` → `docs/design/architecture/08-crosscutting-concepts.md:147`.
- `docs/design/architecture/08-crosscutting-concepts.md:165` → `docs/design/architecture/08-crosscutting-concepts.md:166`.
- `docs/design/architecture/10-quality-risks-glossary.md:28` → `docs/design/architecture/10-quality-risks-glossary.md:28`.
- `docs/design/architecture/10-quality-risks-glossary.md:44` → `docs/design/architecture/10-quality-risks-glossary.md:44`.
- `docs/design/architecture/10-quality-risks-glossary.md:55` → `docs/design/architecture/10-quality-risks-glossary.md:55`.
- `docs/design/architecture/10-quality-risks-glossary.md:58` → `docs/design/architecture/10-quality-risks-glossary.md:58`.
- `docs/design/architecture/10-quality-risks-glossary.md:70` → `docs/design/architecture/10-quality-risks-glossary.md:70`.
- `docs/design/architecture/10-quality-risks-glossary.md:72` → `docs/design/architecture/10-quality-risks-glossary.md:72`.
- `docs/design/architecture/10-quality-risks-glossary.md:82` → `docs/design/architecture/10-quality-risks-glossary.md:82`.
- `docs/design/architecture/10-quality-risks-glossary.md:105` → `docs/design/architecture/10-quality-risks-glossary.md:105`.
- New regression: `tests/test_architecture_targets.py:1` (no pre-existing main counterpart).

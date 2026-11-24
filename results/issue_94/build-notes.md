# Build notes — issue 94, iteration 5

Target: getwyrd/nl-shell main, 4d040301a2341590ca9c574b2df1cefe34585000.
All source edits are in /home/eddie/nl-shell/nl-shell.pdca-wt-l0.
Citations below are relative to that target worktree; corrected-document line numbers
refer to the shipped patch. No previous cycle documents or conformance ruleset were read.
The current bundle's docs-working.diff supplied the working document changes; the
brief's carry-forward supplied the corrections. No push, PR, commit, or cleanup occurred.

## Rationale and scope

ADR-0023:37–55 defines target contents/consumers, :57–71 defines manifest integrity
and adapter identity, and :73–87 defines selection and the first target
(docs/design/adr/0023-os-targets.md). The shared procedure and target-owned inputs
are in docs/design/specs/policy-gate/v1.md:33–49. These remain unchanged.

Preserved the working document patch and applied the explicit carry-forward corrections:
- docs/design/architecture/05-building-block-view.md:11–13 retains the planned-status
  legend; :32–34 connects targets to backend prompts and planned gate integration;
  :60–90 describes built and planned target consumers separately. The REPL warning
  (:71–74) is not the planned per-command confirmation (:78–81); the reader library
  (:82–83, :113) is explicitly not wired into the REPL. Planned REPL manifest/sensitive
  inputs (:75–77), installer integrity (:84–86), absent pipeline files (:87–90), and
  unshipped targets (:69) have local status wording.
- docs/design/architecture/05-building-block-view.md:114 restores state capture in
  “PTY session, state capture, policy gate integration, confirm UI, session log”
  as planned. Evidence: src/nl_shell/prompts.py:47 says the state slot is empty until
  #11; src/nl_shell/repl.py:8–9 and :45 describe pending execution integration.
  The target consumers stay listed at :110–113; this is not a general module inventory.
- docs/design/architecture/07-deployment-view.md:15–33 distinguishes intended packaging,
  downloads, SHA-256 refusal, and adapter compatibility from built behavior. :28–30
  fixes “Downloads happen never” to the install/explicit-update-only rule.
  :67 makes reference systems per target; :69–72 leaves both distribution questions
  open and states the manifest resolves neither. No channel is selected.
- docs/design/architecture/08-crosscutting-concepts.md:35 scopes package provenance
  to the target VM; :54–56 scopes gate examples; :114 uses target package data/query;
  :143–149 scopes training and specifics; :165–166 removes duplicated “local” and
  keeps target-local offline lookup. Existing taint/confirmation requirements remain.
- Preserved the narrowly scoped first-target qualifications in
  docs/design/architecture/01-introduction-and-goals.md:16,37,44;
  docs/design/architecture/02-constraints.md:18;
  docs/design/architecture/03-context-and-scope.md:20;
  docs/design/architecture/04-solution-strategy.md:23,33;
  docs/design/architecture/06-runtime-view.md:39–40;
  docs/design/architecture/10-quality-risks-glossary.md:28,44,55,58–59,70,72,82,105.
  Historical milestones, bash-only scope, and factual uncertainty are retained.

The retained working diff did not include every round-3/4 correction, so those specific
carry-forward fixes were reapplied. No runtime alternative was attempted or rejected on
cost: runtime implementation is expressly out of scope. No decision is based on a claim
that removing a cause is “larger.” This restores the descriptive shared/target invariant,
rather than adding a runtime guard.

## Test and forced refutation

tests/test_architecture_targets.py:1–33 reads the actual architecture files relative to
the target checkout and extracts consumer bullets with explicit missing-section assertions.
:36–59 pins the diagram and layout status, including state capture.
:62–98 pins status within each consumer bullet rather than accepting a nearby link or word.
:101–132 pins deployment status, integrity, adapters, and both unresolved channels.
:135–148 checks scoped provenance/training/offline descriptions.

(a) Genuine red: YES. Kept the identical test in place, wrote the architecture-only diff
to docs-working.diff, applied it in reverse, ran the instance Python's documented
runner command, then reapplied the diff. docs-red.log: 9 failed, exit 1; docs-green.log:
9 passed, exit 0. Command from the target root:
`/home/eddie/nl-shell/nl-shell-pdca/.venv/bin/python3 -m pytest -q tests/test_architecture_targets.py`.
This direct runner invocation is the brief's expressly accepted docs-only exception
and docs/INTEGRATION.md §3's reproduction command, not a substitute C4 runner.

(b) Production path: YES for this documentation contribution. The tests read the real
Markdown changed by the patch, not copied text or a stand-in reader. They do not prove
runtime target integration, manifest enforcement, or semantic correctness of every sentence.

(c) Fixture includes fault: YES. The unmodified main documents were the red fixture,
with the global OS assumptions and absent target relationships intact. No chapter,
target, or failing statement was curated out. Tests are ordinary unmarked pytest.

Additional mutation refutation: mutation-check.py temporarily changes the real documents,
runs the same pytest with a 30-second subprocess bound, and restores each file in finally.
All 15 mutations caused real assertion failures (mutation-*.log):
mismatch-confirm, reader-row-built, reader-bullet-built, repl-input-status,
installer-status, gate-status, pipeline-status, ch05-integrity-status, packaging-status,
state-capture, deployment-lead-in, integrity-status, adapter-status,
distribution-resolution, distribution-choice. The final restored run was 9 passed.
In particular the two expressly requested mutations each produce 1 failed, 8 passed.

## Other validation and limits

- Actual engine/scripts/run-verify.sh with PDCA_BUNDLE set returned 77:
  “PDCA-UNVERIFIABLE: no behavioral production change to revert (test-only or docs-only patch)”.
  The Plan-accepted exception still holds. This is NOT C4 PASS.
- T3 used the actual engine/scripts/run-suite.sh with a 60-second outer bound.
  The full run did not finish within the bound. A diagnostic rerun through the same runner,
  with PYTEST_ADDOPTS=--maxfail=1 and the same bound, reported 835 passed, 1 skipped,
  1 failed in 6.97s. suite-first-failure.log records the existing reader test's localhost
  socket creation failing with PermissionError. T3 is NOT green.
- Host-docs: six checker unit tests pass (docs-check.log), 82 relative links in 63
  Markdown files have zero broken links, ADR index checks 28 ADRs with zero problems.
  The configured immutability checker reports docs-immutability: OK against a synthetic
  patched commit. Its temporary index/object store lives inside this bundle, with the
  target object database read only as an alternate; no primary-checkout writes.
- Target pyproject.toml:24–39 configures pytest, no formatter/linter.
  .pre-commit-config.yaml:15–43 configures machine-local filename rejection and gitleaks,
  not a formatter. Ran those filename checks and the actual gitleaks stdin entry with
  --no-banner --redact --ignore-gitleaks-allow on every touched file: all exit 0.
  The pre-commit wrapper is unavailable, so this is direct hook-tool execution on full
  working-file contents, not a claim that a staged commit hook was executed.
  git diff --check passes. No hook configuration was changed.

NEEDS-HUMAN external dependency: localhost-sockets — sandbox denies AF_INET socket creation; full T3 reader/teacher-client integration cannot be validated here.
```toml
[[doctor.checks]]
id = "localhost-sockets"
cmd = "python3 -c 'import socket; s=socket.socket(); s.bind((\"127.0.0.1\", 0)); s.close()'"
hint = "Run T3 in an environment allowing localhost TCP socket creation and binding."
level = "MISSING"
```

Human Check remains required for the architecture-wide semantic sweep, including chapter
10's uncertainty, risk mitigation, goals/probes, glossary and testing examples. The
carry-forward specifically reserves gate-vectors.toml shipment versus gate-tests,
§8.5 dpkg/apt wording versus command-not-found data, and the PTY/reader status convention
for human judgment. These were not decided here. Inspect every architecture chapter
against ADR-0023 and policy-gate/v1, decide those reserved items, and run T3 where local
sockets are permitted. Green document assertions and host-docs checks do not discharge
that review or prove runtime implementation.

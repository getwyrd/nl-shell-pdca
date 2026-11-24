# Build notes — issue 94

Base: main 4d040301a2341590ca9c574b2df1cefe34585000. All edits are in PDCA_WORKTREE.
No runtime changes, immutable-document edits, commits, pushes or PR operations.

## Rationale

ADR-0023 (docs/design/adr/0023-os-targets.md:37, :57, :65, :73, :83) defines the layout,
consumer relationships, manifest integrity, adapter identity and exact selection.
The shared gate/package-owned abstraction follows docs/design/specs/policy-gate/v1.md:33, :48.
Chapter 05 adds target data and consumers, separates runtime from build-time material,
and splits only the target-related built statuses from the stale catch-all.
Built evidence: src/nl_shell/targets.py:1, :27, :145, :249;
src/nl_shell/os_release.py:1; src/nl_shell/gate/vectors.py:49;
src/nl_shell/prompts.py:80; src/nl_shell/reader.py:198.
Chapter 07 describes planned packaging, downloads, integrity and adapter requirements,
retaining both unresolved distribution choices. Chapter 08 scopes reference provenance,
reader queries, execution filtering and specifics to the target, preserving taint and confirms.
Other edits qualify OS assumptions in goals, constraints, context diagram, strategy,
sudo sequence, risks, glossary and test examples. Exact changed-line citations follow below.
Chapter 09 historical milestones (:24, :26) and chapter 03 history trust (:45) remain unchanged.

Rejected alternatives: runtime implementation is outside the brief's Scope; selecting a
host/channel would exceed ADR-0023:59, which specifies URLs without choosing a host.
No alternative was rejected on cost. No new OS or shell support is promised.

## Forced test refutation and evidence

Test: tests/test_architecture_targets.py:1; actual document reader :11; consumer checks :15;
status/harvest :23; deployment :36; provenance/specifics :46.

(a) Genuine red? YES. The same retained test first failed on original documents (7 failed).
After edits it passed (7 passed). Then ALL documentation edits were actually reverted
using git apply -R, retaining the test: 7 failed, exit 1 (red.log, 0.08 s).
Restoring those hunks yielded 7 passed, exit 0 (green.log, 0.01 s).
Command explicitly permitted by brief Falsifiability and companion docs/INTEGRATION.md:52:
/home/eddie/nl-shell/nl-shell-pdca/.venv/bin/python -m pytest -q tests/test_architecture_targets.py

(b) Production path? YES for this documentation objective: the test reads real architecture
Markdown relative to its own checkout, not a copy/mock/parallel implementation. It proves
no runtime installation, gate, integrity or adapter enforcement.

(c) Fixture includes the fault? YES: no curated fixture; original chapters 05/07/08 are read.
Failures identified missing target component, built-consumer statuses, manifest deployment
relationships and target-owned provenance. This is limited document evidence, not semantic proof.

Configured C4 runner returned PDCA-UNVERIFIABLE, exit 77, for docs-only changes.
This is NOT C4 PASS. The human-approved docs-only exception remains applicable.
No runtime change was added to evade classification.

Host-docs components passed: six checker unit tests (docs-check.log), 81 relative links
across 63 Markdown files with zero broken, 28 ADR index entries with zero problems,
and scripts/docs_checks.py immutability reported OK. Synthetic commit objects and index
were confined to the worktree; the real index/branches were unchanged.
Reverse git apply --check of patch.diff and git diff --check passed.

Commit checks (.pre-commit-config.yaml:14, :22): directly executed the configured filename
guard, gitleaks staged-diff check (~9861 bytes) and actual staged-blob check for all ten
changed files; all passed. The pre-commit wrapper is absent; installed gitleaks executed
the checks. No formatter/linter is configured in pyproject.toml:1 or the hook config.
Initial private-index population hit the read-only shared object database; discarded the
resulting empty diff scan as evidence. Successful rerun used .pdca-hooks-index and
.pdca-hook-objects inside the worktree, with shared objects as an alternate.

## Human handoff

NEEDS-HUMAN: Check must review every architecture chapter semantically against ADR-0023
and policy-gate/v1. Assertions and host-docs do not discharge this item. Explicitly review
chapter 10's sudo update mitigation :55, ROCm uncertainty :58, point-release drift :59,
goal/probe wording :28, :44, glossary :70, :72, :80, :82 and test example :105.
Existing OS factual uncertainties remain; these edits do not certify new OS facts.
Verify both open distribution choices and built/planned distinctions. T3 full-suite and
T4 contribution verdicts are left to Check; no full-suite result is asserted here.

## Change citations

Below: target base path:line -> patched path:line, one entry per changed hunk.
- docs/design/architecture/01-introduction-and-goals.md:16 -> docs/design/architecture/01-introduction-and-goals.md:16
- docs/design/architecture/01-introduction-and-goals.md:37 -> docs/design/architecture/01-introduction-and-goals.md:37
- docs/design/architecture/01-introduction-and-goals.md:44 -> docs/design/architecture/01-introduction-and-goals.md:44
- docs/design/architecture/02-constraints.md:18 -> docs/design/architecture/02-constraints.md:18
- docs/design/architecture/03-context-and-scope.md:20 -> docs/design/architecture/03-context-and-scope.md:20
- docs/design/architecture/04-solution-strategy.md:23 -> docs/design/architecture/04-solution-strategy.md:23
- docs/design/architecture/04-solution-strategy.md:33 -> docs/design/architecture/04-solution-strategy.md:33
- docs/design/architecture/05-building-block-view.md:30 -> docs/design/architecture/05-building-block-view.md:31
- docs/design/architecture/05-building-block-view.md:55 -> docs/design/architecture/05-building-block-view.md:61
- docs/design/architecture/05-building-block-view.md:57 -> docs/design/architecture/05-building-block-view.md:64
- docs/design/architecture/05-building-block-view.md:62 -> docs/design/architecture/05-building-block-view.md:91
- docs/design/architecture/05-building-block-view.md:76 -> docs/design/architecture/05-building-block-view.md:105
- docs/design/architecture/06-runtime-view.md:37 -> docs/design/architecture/06-runtime-view.md:38
- docs/design/architecture/07-deployment-view.md:15 -> docs/design/architecture/07-deployment-view.md:15
- docs/design/architecture/07-deployment-view.md:20 -> docs/design/architecture/07-deployment-view.md:26
- docs/design/architecture/07-deployment-view.md:25 -> docs/design/architecture/07-deployment-view.md:33
- docs/design/architecture/07-deployment-view.md:49 -> docs/design/architecture/07-deployment-view.md:69
- docs/design/architecture/07-deployment-view.md:51 -> docs/design/architecture/07-deployment-view.md:73
- docs/design/architecture/08-crosscutting-concepts.md:35 -> docs/design/architecture/08-crosscutting-concepts.md:35
- docs/design/architecture/08-crosscutting-concepts.md:56 -> docs/design/architecture/08-crosscutting-concepts.md:57
- docs/design/architecture/08-crosscutting-concepts.md:97 -> docs/design/architecture/08-crosscutting-concepts.md:100
- docs/design/architecture/08-crosscutting-concepts.md:113 -> docs/design/architecture/08-crosscutting-concepts.md:116
- docs/design/architecture/08-crosscutting-concepts.md:122 -> docs/design/architecture/08-crosscutting-concepts.md:125
- docs/design/architecture/08-crosscutting-concepts.md:142 -> docs/design/architecture/08-crosscutting-concepts.md:146
- docs/design/architecture/08-crosscutting-concepts.md:144 -> docs/design/architecture/08-crosscutting-concepts.md:148
- docs/design/architecture/08-crosscutting-concepts.md:146 -> docs/design/architecture/08-crosscutting-concepts.md:150
- docs/design/architecture/08-crosscutting-concepts.md:165 -> docs/design/architecture/08-crosscutting-concepts.md:170
- docs/design/architecture/10-quality-risks-glossary.md:28 -> docs/design/architecture/10-quality-risks-glossary.md:28
- docs/design/architecture/10-quality-risks-glossary.md:44 -> docs/design/architecture/10-quality-risks-glossary.md:44
- docs/design/architecture/10-quality-risks-glossary.md:55 -> docs/design/architecture/10-quality-risks-glossary.md:55
- docs/design/architecture/10-quality-risks-glossary.md:58 -> docs/design/architecture/10-quality-risks-glossary.md:58
- docs/design/architecture/10-quality-risks-glossary.md:70 -> docs/design/architecture/10-quality-risks-glossary.md:70
- docs/design/architecture/10-quality-risks-glossary.md:72 -> docs/design/architecture/10-quality-risks-glossary.md:72
- docs/design/architecture/10-quality-risks-glossary.md:82 -> docs/design/architecture/10-quality-risks-glossary.md:82
- docs/design/architecture/10-quality-risks-glossary.md:105 -> docs/design/architecture/10-quality-risks-glossary.md:105
- New file: tests/test_architecture_targets.py:1 (no base counterpart).

# Build notes — #94, iteration 3 carry-forward

Base: getwyrd/nl-shell main, 4d040301a2341590ca9c574b2df1cefe34585000.
All source changes are in PDCA_WORKTREE. No runtime implementation, ADR/spec change,
commit, push or PR was made. Prior-cycle artifacts were not read.

## Rationale and citations

The invariant is descriptive consistency with docs/design/adr/0023-os-targets.md:37
(layout/consumers), :57 (manifest), :66 (verification, downloads, adapter identity),
:73 (selection) and docs/design/specs/policy-gate/v1.md:33 (shared procedure), :48
(package ownership). The architecture used to omit the folder in
05-building-block-view.md:16, describe a single reference VM at :65, omit integrity
in 07-deployment-view.md:15, and name dpkg globally in 08-crosscutting-concepts.md:35
and :112. All architecture paths below are under docs/design/architecture/.

Changed-line citations in the patched target worktree:

- 05-building-block-view.md:32 adds the folder with command-prompt/backend and planned
  gate edges, not an input-router edge; :60 adds its responsibility; :63–92 explains
  its consumers and existing/planned files; :98 makes harvest per target; :112–116
  lists built target consumers and retains a narrowed planned row. The header at :11
  retains the note about planned components. REPL start-up :70–73 says warning;
  planned REPL inputs :74–75 include both manifest and sensitive data. Gate :76–80
  and pipeline :85–86 explicitly disclaim built integration/files. Reader :81 and
  :115 both disclaim REPL wiring. This addresses all three carry-forward rounds.
- Status evidence cited by the brief: src/nl_shell/targets.py:1–12, :27–28,
  :145–169, :249–276; src/nl_shell/prompts.py:80–91;
  src/nl_shell/reader.py:198–204; src/nl_shell/gate/vectors.py:49–53.
  src/nl_shell/repl.py:8 and :45 support retaining PTY and policy gate integration
  as planned. The carry-forward identifies the sensitive stub (#190) and warning-only
  CLI behavior, so these are not claimed built. No general status inventory was attempted.
- 07-deployment-view.md:15–21 identifies intended deployment and files without claiming
  packaging exists; :26 scopes package ownership; :33–43 gives the planned integrity,
  install/update-only download, refusal and adapter requirements; :68 makes reference
  systems per target; :70–72 retains BOTH open distribution questions. The download
  sentence is now grammatical. Gate vectors are described as test input at :20;
  their eventual packaging remains a human review question, not a new requirement.
- 08-crosscutting-concepts.md:35 scopes local-reference provenance; :59 qualifies the
  apt example; :112–114 uses target package data/query; :143 scopes execution filtering;
  :145–147 identifies the first target's specifics; :165–166 uses target package lookup
  without duplicate 'local'. Taint, offline and confirmation requirements remain.
- 01-introduction-and-goals.md:16, :37, :44 scopes initial users/goals;
  02-constraints.md:18 scopes OS constraints; 03-context-and-scope.md:20 scopes the
  sudo diagram (the unrelated history row is untouched); 04-solution-strategy.md:23,
  :33 scopes training; 06-runtime-view.md:38 scopes the sudo example.
- 10-quality-risks-glossary.md:28, :44 scopes goal/probe wording; :55 scopes sudo update
  mitigation; :58–59 scopes ROCm uncertainty and drift without resolving either;
  :70, :72, :82, :105 scopes glossary/training/test examples. Chapter 09's historical
  milestone names remain unchanged. The full semantic sweep remains for human Check.
- tests/test_architecture_targets.py:1–71 reads actual tracked Markdown, checks
  section-local relationships/status and asserts the two requested mutation failures.

I ruled out runtime changes because this is an architecture consistency slice, not a
request to implement the gate/installer/pipeline. This is a scope decision, not a
cost-based rejection. No alternative was rejected on unquantified cost.

## Evidence and forced refutation

Used the brief's explicit host-docs exception and exact named pytest entry point:
/home/eddie/nl-shell/nl-shell-pdca/.venv/bin/python -m pytest -q tests/test_architecture_targets.py
Each subprocess in the refutation run had a 60-second timeout.

(a) Genuine red: YES. After saving patched Markdown in memory, restored every chapter
from git HEAD while retaining the exact same test, actually ran pytest, and restored
the patched bytes in finally. docs-red.log records 3 executed failures; docs-green.log
records 3 passes. This is document evidence, not runtime evidence.

(b) Production path: YES for this docs-only objective. Tests read the real worktree
architecture documents with Path, without mocked documents or copied prose fixtures.
They do not establish runtime implementation or semantic equivalence with the ADR.

(c) Fault included: YES. The red fixture is original main Markdown, including missing
target/manifest relationships and global package provenance. No chapter is curated out
of the restoration. Additionally mutation-mismatch.log records 1 failure after replacing
'currently prints a warning' with 'makes every command need confirmation';
mutation-reader.log records 1 failure after replacing the reader row's qualified status
with plain 'built'. Both mutations were restored; the final 3-test run passed.

C4 runner actually executed with this patch and exited 77:
PDCA-UNVERIFIABLE: no behavioral production change to revert (test-only or docs-only patch).
This is NOT C4 PASS. The Plan-approved docs-only exception remains necessary; human Check
must confirm it and perform semantic review of every chapter, including chapter 10's
risk uncertainty, examples and glossary. No runtime changes were added to bypass C4.

Other checks: git diff --check passed; six .github/docs-check unittest cases passed;
docs_links checked 82 relative links / 63 Markdown files, zero broken; adr_index checked
28 ADRs, zero problems. Immutable ADRs/specs and frozen docs/plan.md have no diff.
Gitleaks scanned the changed architecture directory and the test contents, zero leaks.
No formatter is configured in pyproject.toml; .pre-commit-config.yaml configures secret
checks, not a formatter. The configured pre-commit launcher is missing, so these direct
scans are additional evidence, not a claim that the configured hooks ran.

NEEDS-HUMAN external dependency: pre-commit — configured commit-hook execution could not be produced because the launcher is absent; commit-readiness remains unverified
```toml
[[doctor.checks]]
id    = "pre-commit"
cmd   = "pre-commit --version"
hint  = "Install pre-commit 4.7.0 and activate the reviewed secret guard following .pre-commit-config.yaml; rerun configured hooks before publication"
level = "MISSING"
```

Human semantic checklist: compare all architecture chapters against ADR-0023 and
policy-gate/v1; specifically review intended runtime file membership (gate vectors),
first-target sudo/ROCm claims with their retained uncertainty, and the built/planned
consumer distinctions. Automated phrase assertions do not discharge this requirement.

The actual T3 runner completed: 52 failed, 1281 passed, 2 skipped, 5 warnings in
190.20 seconds; exit 1. It is NOT green. Socket-using reader/teacher tests fail in this
sandbox with PermissionError [Errno 1] Operation not permitted, including
 tests/test_reader.py:291 when constructing HTTPServer. No runtime files were changed
to bypass those failures. Full-suite success needs a socket-enabled environment.

NEEDS-HUMAN external dependency: local-sockets — sandbox socket creation is denied; full T3-suite success could not be produced
```toml
[[doctor.checks]]
id    = "local-sockets"
cmd   = "python3 -c 'import socket; s=socket.socket(); s.bind((\"127.0.0.1\", 0)); s.close(); u=socket.socket(socket.AF_UNIX); u.close()'"
hint  = "Run the suite in an environment permitting loopback TCP and Unix sockets"
level = "MISSING"
```

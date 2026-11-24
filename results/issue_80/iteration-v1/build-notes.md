# Incomplete builder handoff — success criterion NOT met

Target: getwyrd/nl-shell main. All source edits are in the harness worktree
/home/eddie/nl-shell/nl-shell.pdca-wt-l0. No commit, push or PR was made.
The patch is a partial implementation, not a completed vendored snapshot.
Do not publish it as satisfying #80. The corpus, source.json and upstream
LICENSE.md are absent. No invented corpus or substituted license was supplied.

## Rationale and target citations

The brief is the authoritative plan. Offline reference input follows
`docs/design/adr/0003-locally-complete.md:18`, the local-reference label follows
`docs/design/adr/0016-taint-model-v2.md:43`, and generic/personal separation follows
`docs/design/adr/0010-generic-training-data-local-personalization.md:18`.
Future per-target harvest remains separate (`docs/design/adr/0023-os-targets.md:48`).

New target lines: `scripts/tldr_snapshot.py:19` verifies the complete local input
before returning records; `scripts/tldr_snapshot.py:63` checks the fixed inventory
anchor; `scripts/tldr_snapshot.py:66` supplies provenance; and
`scripts/tldr_snapshot.py:72` provides the standalone stdlib export entry point.
`data/tldr/README.md:17` documents offline consumption, and
`data/tldr/README.md:33` documents explicit acquisition and deterministic conversion.
`data/tldr/NOTICE.md:3` attributes upstream and `data/tldr/NOTICE.md:6` distinguishes
CC BY 4.0 from the code license. These are preparation, not acquisition evidence.
`.oss-scanner/threat_model.md:101` retains dpkg/man/help and
`.oss-scanner/threat_model.md:110` gives tldr the required separate classification.
The other trusted items remain in the list. No immutable ADR changed.

`tests/test_tldr_snapshot.py:59` invokes the production entry point from a child
inside the test body, independently hashes actual exported bytes, checks the
fixed count/byte total/inventory/license anchors, and compares shipped content.
`tests/test_tldr_snapshot.py:95` supplies separate audit controls;
`tests/test_tldr_snapshot.py:103` corrupts copies rather than tracked input.
No new production import occurs during collection. No runtime integration or
#23 implementation is claimed, consistent with `CONTRIBUTING.md:45`.

A tracked JSONL source was chosen as the brief specifies. No cause-removing
alternative was rejected on cost. Fabricated pages, a mutable client cache, and
network fetches during consumption cannot satisfy the pinned offline anchor and
were not substituted. The conversion instructions are not executed evidence.

## Actual acquisition and missing environment

Attempted in the worktree:
`curl -fL --max-time 120 https://codeload.github.com/tldr-pages/tldr/tar.gz/eacda7020c4102729187c38c35ce28fac00365c9 -o .pdca-source/upstream.tar.gz`

Actual result: exit 6, `Could not resolve host: codeload.github.com`.
No actual source bytes were obtained. Generated corpus/metadata/license sizes:
not available; comparison with the Plan anchor has NOT been performed.
The brief anticipated GitHub HTTPS availability, but it is unavailable here.

NEEDS-HUMAN external dependency: github-https — DNS/HTTPS acquisition unavailable; blocks the real 6,837-page corpus, original license, and actual inventory comparison

```toml
[[doctor.checks]]
id = "github-https"
cmd = "curl -fIL --max-time 20 https://codeload.github.com/tldr-pages/tldr/tar.gz/eacda7020c4102729187c38c35ce28fac00365c9"
hint = "Provide GitHub DNS/HTTPS access for explicit pinned acquisition before Do; offline consumption does not need it."
level = "MISSING"
```

NEEDS-HUMAN external dependency: audit-socket-runtime — sandbox rejects socket creation with PermissionError before connect_ex reaches socket.connect; blocks the required network audit positive control

```toml
[[doctor.checks]]
id = "audit-socket-runtime"
cmd = ".venv/bin/python3 -c 'import socket; s = socket.socket(); s.close()'"
hint = "Run host pytest where creating an ordinary loopback socket is allowed; the test hook must still block connect before it executes."
level = "MISSING"
```

NEEDS-HUMAN external dependency: pre-commit — configured commit-hook runner is not installed; complete target hooks could not be exercised

```toml
[[doctor.checks]]
id = "pre-commit"
cmd = "pre-commit --version"
hint = "Install pre-commit==4.7.0 as directed by the target .pre-commit-config.yaml:4 and provision its pinned hook environment."
level = "MISSING"
```

## Verification actually run

Used the configured project runner, not an assembled pytest/container command:
`PDCA_BUNDLE=/home/eddie/nl-shell/nl-shell-pdca/results/issue_80 bash /home/eddie/nl-shell/nl-shell-pdca/engine/scripts/run-verify.sh`.
It selected the instance .venv Python. Applied leg: 3 executed, 3 failed,
0 collection errors, exit 1. Failures: missing source.json, denied socket creation,
and missing real corpus. Accordingly C4 did not advance to its automatic revert
leg. This is a failed verification, not a green mechanical proxy.

Separately moved only scripts/tldr_snapshot.py into .pdca-source inside the
worktree, reran the same configured runner with a 60-second orchestration bound,
and restored the script in a finally block. The regression again executed three
failed assertions (0 collection errors); the export assertion now reported
FileNotFoundError for the missing production script. See reverted-run.txt for
actual output. No red→green is claimed.

`git diff --check` passed. The target's .pre-commit-config.yaml:15 configures
machine-local-file rejection and gitleaks, not a Python formatter. Attempting
`pre-commit run --files ...` failed: command not found. Ran the real installed
`gitleaks stdin --no-banner --redact --ignore-gitleaks-allow` against each of the
five changed files: all exit 0, no leaks. This is supplemental evidence only,
not a substitute for the configured hooks or staged-blob scanning. Commit-ready
status remains unverified. No suite-wide success is claimed.

## Forced refutation

(a) Genuine red? YES for the executed missing-production assertion: physically
removed the production entry point, ran the project runner and observed
`tests/test_tldr_snapshot.py:61` fail with FileNotFoundError inside its child,
not a collection failure. BUT it is also red with the partial fix; this does
not establish the required red→green result.

(b) Production path? The test invokes the actual scripts/tldr_snapshot.py via
runpy under the preinstalled audit hook; it does not copy the reader logic.
However, a successful production export has NOT run because the real snapshot
is absent. Therefore a binding successful production-path proof is NO so far.

(c) Fixture includes the fault? NO complete fixture is available. The test
requires the real full corpus and rejects its absence; it does not curate out
pages or use synthetic references. Corruption and full-corpus checks cannot
complete until the actual pinned upstream bytes are acquired. Audit controls
also remain unproven in this sandbox. This item is NOT DONE.

## Human continuation

Provide GitHub HTTPS access and a host runtime that permits the audit control's
socket creation. Follow data/tldr/README.md:33 to acquire and convert the exact
pinned source, retaining original LICENSE.md. Record actual byte sizes and the
computed fixed inventory anchor. Run the configured C4 runner again (both legs
must pass its oracle), then the required suite and configured commit hooks.
Extend corruption coverage if those runs uncover defects. This partial patch
must not be accepted as a completed source-data deliverable.

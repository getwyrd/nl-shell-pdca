# Build notes — issue 80

Status: production contribution and real upstream data supplied; NOT fully verified.
C4 remains red on the required loopback audit positive control because this sandbox
forbids socket creation before the audited connect event. No skip, synthetic audit
event, mock socket, fabricated source or replacement positive control was used.

NEEDS-HUMAN external dependency: loopback-socket — the execution sandbox denies AF_INET socket creation with PermissionError (errno 1), before socket.connect; the required network audit positive control and hence the complete success criterion cannot be proved here.
```toml
[[doctor.checks]]
id = "loopback-socket"
cmd = "python3 -c 'import socket; socket.socket(socket.AF_INET, socket.SOCK_STREAM).close()'"
hint = "Run verification on the host or in an environment allowing AF_INET socket creation; the test audit hook blocks connect before any network operation executes."
level = "MISSING"
```

## Authority and changed paths

Base is main 4d040301a2341590ca9c574b2df1cefe34585000. Citations below
name target-worktree paths and their patched line numbers; immutable authority
citations refer to the unchanged target base. No previous-cycle files or review
ruleset were read; carry-forward findings were read in the supplied brief.

- Offline source implements docs/design/adr/0003-locally-complete.md:18 and :22.
  Generic/personal separation follows docs/design/adr/0010-generic-training-data-local-personalization.md:18.
  Future target selection stays with the harvest described by
  docs/design/adr/0023-os-targets.md:49. No pipeline, installation or runtime change.
- data/tldr/pages.jsonl:1 contains the actual English common/Linux source, sorted
  by full upstream path through line 6837. data/tldr/source.json:2 records the
  corpus digest; :3 the external inventory anchor; :6 begins per-page byte/hash
  metadata; :41029 begins selected prefixes; :41033 names the upstream repository,
  :41034 its exact commit and :41035 describes the transformation.
- data/tldr/LICENSE.md:1 preserves all 1,572 upstream license bytes, including
  the original notice and separate scripts-license explanation. No scripts from
  upstream ship. data/tldr/NOTICE.md:3 names the team/contributors and pinned URL,
  :6 links CC BY 4.0, :11 describes selection/repackaging and :14 reserves #34.
- scripts/tldr_snapshot.py:20 validates identity, license, corpus, schema, paths,
  manifest and actual-byte pinned inventory before returning any pages. :31 uses
  LF splitting, preserving raw U+0085/U+2028/U+2029 inside JSON strings. :38 rejects
  extra keys and non-string values; :54 checks the fixed anchor/count/byte total.
  :59 provides the stdlib build entry point, :68 emits only explicit fields with
  revision, English language and local-reference provenance.
- data/tldr/README.md:11 documents offline export; :28 starts neutral acquisition
  instructions and a deterministic Git-object conversion recipe. :83 explains
  Git tree mode versus archive permissions. :90 explicitly requires future
  refreshes to update production/test anchors. No harness terminology in product docs.
- .oss-scanner/threat_model.md:101 retains man/help's local-reference annotation;
  :111 gives tldr its separate local-reference paragraph, consistent with
  docs/design/adr/0016-taint-model-v2.md:43. Other Trusted items remain intact.
- tests/test_tldr_snapshot.py:20 installs the test-owned audit wrapper before
  runpy invokes production, :56 independently anchors the shipped corpus/license,
  :104 defines network/process positive controls in separate children and :112
  begins temporary-copy rejection cases. :119 changes one content byte without
  changing length, then :139 recomputes that page's manifest and corpus checksum;
  :150 requires rejection at the production pinned-inventory check. This binds
  the actual upstream anchor independently of local self-consistency.

## Acquisition and actual sizes

The initial curl to codeload.github.com failed DNS resolution (exit 6). The
connected GitHub API worked, so no initial acquisition dependency remains missing.
Fetched real upstream Git trees 747e792cad30b57acf76d659c9e09d0031491dc2 (4,754
common entries) and ad34d72cdeeaf830fbd4c21e3ff7e4317b517109 (2,083 Linux
entries), then fetched each of their 6,837 Git blobs by SHA through the GitHub
connector. One transient server disconnect on pages/linux/oomctl.md succeeded on
retry. Fetched LICENSE.md blob 9b4ebcb9a886af3506c5d42f1dcf1253a520efbe separately.
These were real upstream responses, not generated example pages or a curated fixture.

Decoded only UTF-8, sorted by upstream path, serialized path/content JSONL, and
recomputed Git blob SHA-1 from each actual content byte string. The resulting
inventory SHA-256 is exactly
4ce7ecdff5a4da72bfef4378f027ad141b7daa28dc6b0a68f57905a6e080d960;
6,837 pages total 4,050,595 original bytes. Conversion assertions executed before
metadata was written. The passing real-corpus test independently repeats this
calculation, verifies tar.md/apt.md blob IDs and verifies original LICENSE bytes
(tests/test_tldr_snapshot.py:56).

Generated sizes: pages.jsonl 4,565,959 bytes; source.json 1,515,470;
LICENSE.md 1,572; NOTICE.md 688; README.md 4,684. patch.diff is 6,150,016 bytes
and contains normal text additions for all three formerly missing generated files.
The JSONL layout uses one corpus file rather than 6,837 separate page files; no
binary attribute or diff suppression was added. No alternative cause-removing fix
was rejected on cost: this directly supplies the missing reference source.

## Verification and forced refutation

Ran the actual companion engine/scripts/run-verify.sh with PDCA_WORKTREE and
PDCA_BUNDLE set, under a 180-second outer timeout. It uses the instance .venv
Python and ordinary pytest. do-verify.log records 12 executed tests, 11 passed,
1 failed. The failing test's traceback proves socket.socket() itself receives
PermissionError before connect; an empty attempted-event list is correctly
rejected. The production full export ran twice successfully, deterministically,
with no audited network/process attempts. The process-launch positive control
passed with subprocess.Popen recorded and blocked. All nine corruption cases
passed with empty stdout and specific expected production validation errors.

The C4 wrapper stops at a failed green leg, so it could not run its own red leg.
To perform the explicitly required revert experiment anyway, reversed every
non-test hunk with git apply -R --exclude='tests/*', ran the project's actual
engine/scripts/run-suite.sh with PYTEST_ADDOPTS=tests/test_tldr_snapshot.py and
an outer 180-second timeout, then restored production using a shell EXIT trap
and git apply. do-red.log records 12 executed tests: 11 failed, 1 passed. Ten
failures are executed assertions for absent source, including the real-corpus
assertion; the eleventh is the unchanged environment-blocked socket control.
Production was restored. The ordinary complete test file has no skip markers.

(a) Genuine red? YES for the production objective: reverting the patch changes
all ten corpus-dependent cases from passing to executed failed assertions. See
do-red.log and do-verify.log, tests/test_tldr_snapshot.py:58 and :114. A complete
red-to-green verdict is NOT claimed: the socket control fails on both legs.

(b) Production path? YES: the test-owned child installs the hook and uses runpy
on scripts/tldr_snapshot.py with its documented export argv, against real local
data (tests/test_tldr_snapshot.py:20, :48). No copied reader/backend or mock export.

(c) Fixture includes the fault? YES for corpus and integrity: the full pinned
inventory is shipped and all corruptions are made to full temporary copies
(tests/test_tldr_snapshot.py:115). The fabricated-content case retains the original
byte total and recomputes local hashes, forcing external-anchor rejection. The
process control reaches the real subprocess audit event. NO for the socket
positive control's required connect attempt: the sandbox blocks creation first.
Therefore the item is not fully done. Do not infer complete offline-audit assurance
until the human rerun below passes.

## Commit readiness and remaining validation

CONTRIBUTING.md:26 and :29 require one logical change and green tests; :45 separates
build tooling from runtime. This patch adds no runtime imports/dependencies.
The target .pre-commit-config.yaml defines only the forbidden-machine-local-path
check and gitleaks hooks, with no formatter/linter. pre-commit's launcher is absent
in this environment; executed its underlying checks directly: verified no changed
filename matches forbidden names and ran installed gitleaks v8.30.1 stdin with
--no-banner --redact --ignore-gitleaks-allow on all eight changed files, scanning
entire file bytes as the staged-blob hook does. All passed; do-hooks.log contains
per-file results. git diff --check passed. No code formatter is configured in
that hook configuration. No commit, push or PR operation performed.

Human validation: on a host allowing IPv4 socket creation, apply patch.diff and
run the normal engine/scripts/run-verify.sh with this bundle/worktree. The existing
network control must produce exactly ["socket.connect"] and fail before connect
executes; both complete exports must record []. Require C4 green-plus-red, then
run engine/scripts/run-suite.sh for the whole suite. Until then leave the success
criterion unverified. The required socket control has deliberately not been
weakened to make sandbox checks green.

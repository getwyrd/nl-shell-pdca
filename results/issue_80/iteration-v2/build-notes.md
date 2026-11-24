# Build status: incomplete, blocked on acquisition

Target: main at 4d040301a2341590ca9c574b2df1cefe34585000. This is not a completed implementation and must not be published as the requested contribution.

The brief's carry-forward requires the actual upstream corpus, metadata and license, rather than another reader without its input. Acquisition was attempted with curl -fL --max-time 120 against codeload.github.com/tldr-pages/tldr/tar.gz/eacda7020c4102729187c38c35ce28fac00365c9, and with --max-time 30 against github.com/tldr-pages/tldr/archive/eacda7020c4102729187c38c35ce28fac00365c9.tar.gz. Both exited 6 (Could not resolve host). No upstream bytes were acquired; no generated sizes or anchor comparison can honestly be reported. No replacement fixture, fabricated license, shim or code-read verification was used.

NEEDS-HUMAN external dependency: github-https — DNS/network access to GitHub blocks acquisition of the pinned source and therefore production implementation and green verification.

```toml
[[doctor.checks]]
id = "github-https"
cmd = "curl -fIL --connect-timeout 10 --max-time 30 https://codeload.github.com/tldr-pages/tldr/tar.gz/eacda7020c4102729187c38c35ce28fac00365c9"
hint = "Provide working GitHub HTTPS/DNS access or the authentic pinned upstream archive."
level = "MISSING"
```

This is the network condition explicitly anticipated by brief.md:17 and its carry-forward, rather than a newly discovered installable source dependency. The suggested row is useful as an acquisition preflight only; offline consumption must never need it.

The sole target change is tests/test_tldr_snapshot.py:1–102. Lines 20–59 assert real files, full independently recomputed Git inventory anchor, byte count and original license identity. Lines 62–102 exercise the future production entry point through a test-body child with an audit hook and deterministic complete export comparison. UTF-8 reads are explicit and records split only on LF, addressing the carry-forward's locale/Unicode findings. There is no production script or data addition. This partial regression still lacks corruption cases and audit positive controls; it is not presented as complete success-criterion coverage. The bundle test is an exact copy of this file. patch.diff contains only this addition, explicitly avoiding resubmission of the rejected reader-without-corpus approach.

No cost-based alternative was rejected. The requirement for authentic bytes decides the blocker; a synthetic substitute would violate the inventory anchor requirement regardless of its size. No threat-model changes were made without a source implementation to describe. The intended reference semantics remain those cited by the brief: docs/design/adr/0003-locally-complete.md:18–26, docs/design/adr/0016-taint-model-v2.md:37–49, docs/design/adr/0010-generic-training-data-local-personalization.md:18–25 and docs/design/adr/0023-os-targets.md:41–55. Existing threat wording is .oss-scanner/threat_model.md:97–109. Test placement follows CONTRIBUTING.md:26–31; no runtime imports were introduced (CONTRIBUTING.md:45–49).

Verification used the configured engine/scripts/run-verify.sh with PDCA_BUNDLE set to this bundle and PDCA_WORKTREE supplied by the driver. Exit 77: no behavioral production change to revert. The configured engine/scripts/run-suite.sh was also run; its output is build-suite.log. No ad-hoc pytest runner was assembled.

Forced test refutation:

(a) Genuine red? Not proven red→green. The source is absent and the regression asserts its absence as failure; C4 cannot perform a production revert because there is no fix. This remains incomplete.

(b) Production path? Not yet. The export regression targets scripts/tldr_snapshot.py via runpy, but that file cannot be delivered/validated with its authentic input in this environment. There is no stand-in implementation.

(c) Fixture includes the fault? The test requires all 6,837 real pages with the Plan anchor; none were acquired. Missing source is not curated out or skipped. Corruption coverage cannot honestly be claimed.

Commit readiness: pyproject.toml has no formatter/linter configuration. The configured .pre-commit-config.yaml supplies the machine-local file guard and gitleaks hooks. Attempted `pre-commit run --files tests/test_tldr_snapshot.py`; exit 127, pre-commit not found. No hook activation or bypass was performed.

NEEDS-HUMAN external dependency: pre-commit — missing executable blocks running the target's configured commit hooks; committability is unverified.

```toml
[[doctor.checks]]
id = "pre-commit"
cmd = "pre-commit --version"
hint = "Install pre-commit==4.7.0 as documented in .pre-commit-config.yaml and provide its configured hook dependencies."
level = "MISSING"
```

To resume: provide authentic pinned upstream bytes and working commit-hook tooling, then implement conversion, metadata, reader, attribution, rebuild documentation and the narrow threat clarification; finish the corruption and positive-control regressions; run C4 and hooks. Do not accept this incomplete bundle based on the partial test.

Final runner result: T3 exited 1, with 54 failed, 1278 passed, 2 skipped in 184.30 seconds. Both new snapshot tests failed on missing production additions. Other failures are recorded in build-suite.log and were not investigated outside the brief's narrow scope; no claim is made that all failures come from this partial regression. C4 exited 77 as recorded above. No green or completed red→green result exists.

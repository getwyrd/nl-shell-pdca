Review issue #92: add OS target data, exact startup selection, explicit mismatch reporting, and the initial Ubuntu 26.04 allowlist.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | Exact matching, explicit overrides, refusal cases and deferred gate enforcement give this slice testable boundaries; brief.md:15 and brief.md:21. |
| C2 Reproduction (red pre-fix) | PASS | Frozen execution demonstrates missing functionality: 37 failures, 3 passes and 3 setup errors with production changes reverted, not collection failure; gate-logs/C4-verify.log:14 and its final summary. |
| C3 Change | PASS | Selection runs before interactive startup and passes session-specific mismatch state to status reporting, satisfying the scoped behavior; target/src/nl_shell/cli.py:28 and target/src/nl_shell/repl.py:89. |
| C4 Verification (red→green) | PASS | Frozen C4 output shows 43 green tests and a substantive red leg; local pytest rerun is unavailable (`No module named pytest`), so this verdict relies on that captured execution; gate-logs/C4-verify.log:10. |
| C5 Causal adequacy | PASS | Exact matching and explicit named selection address the unsupported-OS ambiguity directly; no capability probe conceals a load-time cause, and target-less REPL construction is an intentional supported case; target/src/nl_shell/targets.py:233 and target/tests/test_targets.py:507. |
| T1 Structure | PASS | Separate config, OS parsing and target-loading units keep future settings and target extensions independent; target/src/nl_shell/config.py:40, target/src/nl_shell/os_release.py:21 and target/src/nl_shell/targets.py:131. |
| T2 Shape | NEEDS-HUMAN | Approve each allowlist entry as suitable for future unconfirmed execution — the threat-model scanner reports no relevant path touched and does not discharge the mandated human security review; target/targets/ubuntu-26.04/allowlist.toml:1, target/docs/design/specs/policy-gate/v1.md:204 and gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | Frozen full-suite output reports 218 passes; direct local smoke checks also confirmed exact selection, near-version refusal, allowlist parsing and mismatch status; gate-logs/T3-suite.log:15 and target/src/nl_shell/repl.py:89. |
| T4 Contribution | N/A | Contribution artifacts are intentionally absent at Check; substantive contribution audit must run at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm prior-art coverage for every affected path, including merged and closed/rejected work — the brief reports a CLI history query and broad src/targets search, but this single-commit target has no remotes or review history to independently establish complete coverage; brief.md:26 and patch.diff:111. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept this slice's recorded mismatch as sufficient pending #12 enforcement, the product-tagline exception, omission of command/ip, and combined loader/allowlist scope — these are explicit sign-off decisions affecting the feature's promise and policy coverage; brief.md:21 and target/targets/ubuntu-26.04/allowlist.toml:19. |

Evidence and limits:

- Source citations above resolve in the supplied `target/` copy. Its prerequisite status machinery is present; no stale-target caveat was needed. No implementation files were modified.
- Attempted `python3 -m pytest -q -p no:cacheprovider --basetemp=/tmp/pdca-review-0dq1oo7o/pytest-green` from the target. The interpreter lacks pytest, so no independent pytest red/green or full-suite rerun was possible. Read the frozen gate logs instead; their wrapper paths refer to the original instance, not this target. This local tool limitation does not invalidate the recorded gate executions or imply an unmet production dependency.
- Independently exercised the actual target modules using standard-library Python: matching Ubuntu 26.04 selected successfully; Ubuntu 26.10 without an override raised the expected refusal; an explicit target on `other 1` recorded the mismatch; the actual allowlist parsed; a scripted REPL printed `target: ubuntu-26.04 (Ubuntu 26.04 LTS)` and `target os: does not match this OS (detected: other 1)`.
- The frozen red leg demonstrates absence of the feature, largely through missing-module imports; it does not establish that every individual allowlist restriction would detect a mutation. The green restriction assertions are grounded at target/tests/test_targets.py:455. The real command-policy engine and degraded enforcement belong to #12, so neither these tests nor the smoke checks prove safe unconfirmed execution.
- Prior-art investigation in the provided target returned only the synthetic pre-fix base commit and no remotes. The claimed closed-work search cannot be independently confirmed from this artifact bundle. No other checkout was consulted.

<!-- pdca:leaf-complete -->

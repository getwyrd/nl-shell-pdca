Review #155: add a deterministic failure classifier using trusted command results, conservative privilege matching, and optional injected package suggestions.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | Precedence, accepted matching costs, suggestion eligibility and scope are explicit and falsifiable; brief.md:20 and brief.md:40. |
| C2 Reproduction (red pre-fix) | PASS | Independent production-only stash made the direct probe fail on the absent classifier; frozen pytest evidence records 259 failures and one intentionally unchanged pass; gate-logs/C4-verify.log:6557. |
| C3 Change | PASS | The three affected paths match the authorized scope; trusted result fields determine classification and raw output is excluded; src/nl_shell/failure_classes.py:578 and tests/test_failure_classes.py:44. |
| C4 Verification (red→green) | PASS | Independently restored the patch and passed 175 direct table cases, including bounded-work cases; full pytest rerun unavailable because this host lacks pytest, while the frozen log records 260 green and 259 red failures; gate-logs/C4-verify.log:15 and gate-logs/C4-verify.log:6557. |
| C5 Causal adequacy | PASS | Conservative unclear-command classification removes the need to emulate expansions, with remaining argument/case/function-body misses explicitly documented; no optional-capability symptom guard was added; src/nl_shell/failure_classes.py:396 and .oss-scanner/threat_model.md:190. |
| T1 Structure | PASS | Classification, tokenization, alias analysis and provider display filtering remain isolated in the new module without modifying router/session behavior; src/nl_shell/failure_classes.py:146 and src/nl_shell/failure_classes.py:459. |
| T2 Shape | PASS | Independently checked syntax, forbidden package-data references, ASCII test bytes and the Known-gaps entry; the frozen scanner only reports no security-relevant path touched, so its pass alone is not substantive coverage; .oss-scanner/threat_model.md:190 and gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | Frozen suite output shows 912 passing tests and one forkpty deprecation warning; this host lacks pytest, so full runtime coverage rests on that captured run rather than an independent suite rerun; gate-logs/T3-suite.log:30. |
| T4 Contribution | N/A | Contribution artifacts are drafted after Check; the substantive audit must rerun at publish, as the deferred gate explicitly states; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm path-based prior-art clearance against merged and closed/rejected remote work — local git history has no entries for either new path but contains only the harness base, and the attempted GitHub query failed to connect; brief.md:61. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the deliberate false positives and documented privilege misses, including quoted-word re-splitting, and choose publication after #140 merges or against its branch — these affect correction availability, reader eligibility and usable CI; .oss-scanner/threat_model.md:190, brief.md:37 and brief.md:77. |

Independent execution used review-probe.py, which imports test tables with inert pytest decorators and directly invokes assertions; it is not a pytest runner. Its pre-fix failure was an import failure, not the assertion-only pytest red recorded by the frozen gate. The production patch was restored; target git status matches the initial three changed paths. No real privilege program or shell command from a test table was executed.

The brief lists no external runtime dependency. Its folded prerequisite is present here: the probe imported and constructed the real session.CommandResult and Snapshot. Remote merge/publish ordering remains a human decision, not a compilation defect. No INTEGRATION.md was found in the supplied target. Instance-scoped gate wrappers were adjudicated through all four readable frozen logs; their absence from this target is expected.

<!-- pdca:leaf-complete -->

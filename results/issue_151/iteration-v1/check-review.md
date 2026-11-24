Review the new OpenAI-compatible teacher transport and REPL error handling, including bounded requests and escaped server failures.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The transport contract, failure behavior, deadline coverage and child-2 exclusions are explicit and testable; brief.md:3 and brief.md:12. |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence shows all 72 tests executed and failed without production changes, including missing client imports rather than collection failure; gate-logs/C4-verify.log:15 and gate-logs/C4-verify.log:1722. |
| C3 Change | PASS | The four affected files stay within the specified transport, backend error, REPL and test scope; patch.diff:1, patch.diff:32, patch.diff:89 and patch.diff:572. |
| C4 Verification (red→green) | PASS | Frozen gate evidence records 72 green and 72 red, with no collection errors; local pytest rerun is unavailable because pytest is absent, and loopback smoke cannot bind sockets (EPERM); gate-logs/C4-verify.log:12 and gate-logs/C4-verify.log:1724. |
| C5 Causal adequacy | PASS | The deadline covers the whole worker exchange rather than individual reads; an independent stalled-DNS check returned DeadlineExceeded in 0.05 s, and no optional-capability probe masks a load-time cause; target/src/nl_shell/teacher_client.py:341 and target/src/nl_shell/teacher_client.py:360. |
| T1 Structure | PASS | The transport reuses the backend contract, schema and rendering boundary, while the existing parser remains the only proposal parser; independently checked schema object identity; target/src/nl_shell/teacher_client.py:333 and target/src/nl_shell/repl.py:170. |
| T2 Shape | NEEDS-HUMAN | Decide whether the new network/error surface requires a threat-model update despite the brief excluding documentation changes — the scanner explicitly leaves this security-boundary decision to sign-off; gate-logs/T2-threat-model.log:10, brief.md:12 and target/src/nl_shell/teacher_client.py:421. |
| T3 Runtime | PASS | The frozen full-suite log reports 553 passed with one forkpty deprecation warning; this is logged host execution, not an independent suite rerun in this pytest-less sandbox; gate-logs/T3-suite.log:20 and gate-logs/T3-suite.log:25. |
| T4 Contribution | N/A | Contribution artifacts are intentionally absent at Check; the substantive contribution audit must rerun at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm prior-art coverage for all four affected paths across merged and closed/rejected work — local path-filtered history returns only the synthetic base commit, has no remotes, and cannot independently establish the brief's earlier-attempt disposition; brief.md:20 and patch.diff:1. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the specified fake-server transport contract and interim synchronous failure replies meet this child's intended use before endpoint selection is wired in child-2; real model integration is outside this brief, while PyYAML is present and exercised by the frozen suite; brief.md:12, brief.md:13 and target/src/nl_shell/repl.py:39. |

Evidence limits: the target is readable and contains the prerequisite backend, prompts, schema and rendering modules; no stale-target caveat was observed. No production files were changed. The supplied instance-scoped gate wrappers are not available here, so their captured logs were read instead. PyYAML and client imports succeeded locally. Independent checks also confirmed default HTTP port selection, trailing `/v1` normalization and refusal of whitespace/control-character and userinfo URLs. The blocked loopback smoke and missing pytest prevented an independent stash/red/restore/green run; the red→green conclusion above is explicitly limited to the frozen gate evidence.

No INTEGRATION.md was supplied or found in the target; project-specific human-only requirements beyond the available instructions could not be enumerated. Prior-art inspection was restricted to this target and the supplied brief; no other checkout was searched.

<!-- pdca:leaf-complete -->

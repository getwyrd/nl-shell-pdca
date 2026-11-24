Review issue #108: route command-prefixed English sentences and unbalanced apostrophes as natural language while preserving the specified shell-command exceptions.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The deterministic rule, override order, exclusions and compatibility boundary are explicit and testable; target/src/nl_shell/router.py:7, target/tests/test_repl.py:101. |
| C2 Reproduction (red pre-fix) | PASS | Independently executing all 30 table vectors against the base router reproduces exactly 8 misroutes; the frozen pytest red leg likewise reports 8 failures (gate-logs/C4-verify.log:15); target/tests/test_repl.py:101. |
| C3 Change | PASS | The three affected files stay within the routing, regression-test and architecture-documentation scope; first_token is AST-identical to the base, preserving its other caller; target/src/nl_shell/router.py:53. |
| C4 Verification (red→green) | PASS | Independent standard-library execution gives 8/30 failures on the base and 0/30 patched; frozen evidence gives 8/43 red and 43/43 green through Repl; local pytest is unavailable, so pytest confirmation rests on gate-logs/C4-verify.log:10; target/tests/test_repl.py:129. |
| C5 Causal adequacy | PASS | The change addresses the specified command-name-only classification cause; quote precedence and each independent exclusion now have distinguishing vectors, with no capability-probe workaround; target/src/nl_shell/router.py:93, target/tests/test_repl.py:115. |
| T1 Structure | PASS | Pure routing helpers preserve separation from REPL execution and retain per-call executable resolution; target/src/nl_shell/router.py:107. |
| T2 Shape | PASS | No execution, policy, PTY, sudo or taint surface changes; the frozen threat-model scanner confirms no security-relevant path touched (gate-logs/T2-threat-model.log:11); target/src/nl_shell/router.py:115. |
| T3 Runtime | PASS | Frozen full-suite output shows 1122 passed, 1 skipped and a forkpty warning; local pytest is absent, so this is log-backed rather than a reproduced suite run; gate-logs/T3-suite.log:33; target/tests/test_repl.py:129. |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive audit must rerun at publish, as recorded in gate-logs/T4-contribution.log:11. |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art across merged history and closed/rejected work before sign-off — the supplied target contains only one synthetic base commit and no remotes, so the brief's prior-art claim cannot be independently established; target/src/nl_shell/router.py:115, target/tests/test_repl.py:129. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the specified heuristic's usability tradeoff — short English and metacharacter-bearing sentences still route as commands, while apostrophes can override shell-looking syntax; target/src/nl_shell/router.py:22, target/tests/test_repl.py:124. |

Independent checks: production-only stash succeeded and was restored after pytest reported `No module named pytest`; a standard-library harness extracted the actual 30 test vectors, used executable command files on an isolated PATH, and compared the committed base router with the patched router. This fixture exercises real executable lookup and can reproduce the forbidden misroutes; no external dependency is required by the brief. `git diff --check` passed. The supplied target is current with the patch, and no INTEGRATION.md is present in it. Instance-scoped gate wrappers are not supplied; their captured logs were read instead. No implementation defect was identified.

The local full-suite and failure-class reruns could not execute without pytest; the frozen full-suite result covers the failure-class tests, and the unchanged first_token was independently checked structurally. This host limitation does not contradict the captured successful gate execution.

<!-- pdca:leaf-complete -->

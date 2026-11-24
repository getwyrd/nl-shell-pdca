Review #196: add the fail-closed AST policy gate’s shell layer, conservative command/live stubs, and conformance tests.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The shell-layer contract and explicit sibling exclusions give this increment a bounded acceptance target; src/nl_shell/gate/parse.py:15 and src/nl_shell/gate/rules.py:3 agree with brief.md. |
| C2 Reproduction (red pre-fix) | PASS | Frozen execution shows all 189 feature tests fail with production changes reverted, including missing gate imports; gate-logs/C4-verify.log:16 and gate-logs/C4-verify.log:6912. |
| C3 Change | PASS | The patch supplies the declared package, dependency pins and vectors without REPL wiring; independent AST checks passed for all nine new Python files and both TOML files parsed; pyproject.toml:17 and src/nl_shell/gate/__init__.py:26. |
| C4 Verification (red→green) | PASS | Log-supported rather than independently reproduced: 189 tests pass patched and 189 fail reverted; this sandbox has neither pytest nor either tree-sitter module, so stash/retest cannot yield meaningful evidence here; gate-logs/C4-verify.log:14 and gate-logs/C4-verify.log:6912. |
| C5 Causal adequacy | NEEDS-HUMAN | Approve decision C and the stricter descriptor and quote-blind character rejection policies as acceptable v1 raises — they intentionally refuse additional user commands; docs/design/specs/policy-gate/v1.md:238, src/nl_shell/gate/__init__.py:8 and src/nl_shell/gate/parse.py:676. |
| T1 Structure | PASS | Invocation/context records and separate command/live hooks provide the declared extension points for the sibling work; src/nl_shell/gate/parse.py:241 and src/nl_shell/gate/__init__.py:138. |
| T2 Shape | PASS | The security-path scanner reports a threat-model update, and source inspection confirms explicit parser, descriptor and residual-risk coverage; gate-logs/T2-threat-model.log:10 and .oss-scanner/threat_model.md:114. |
| T3 Runtime | PASS | Frozen full-suite execution reports 1290 passed, one skipped and one forkpty warning; actual runtime dependencies were exercised there, but are absent in this reviewer sandbox; gate-logs/T3-suite.log:35. |
| T4 Contribution | N/A | Contribution artifacts are absent by design; the substantive contribution audit must rerun at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm dependency licensing and path-based prior art across merged and closed/rejected work — the disposable target contains only one synthetic base commit, so its path-history search cannot establish that history; pyproject.toml:19 and brief.md:139. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether this unwired shell-layer increment is fit for its staged purpose, accepting documented parser latency and unresolved dynamic redirect/arithmetic cases pending sibling work — passing unit tests do not establish complete shell enforcement; .oss-scanner/threat_model.md:120, .oss-scanner/threat_model.md:126 and src/nl_shell/gate/__init__.py:26. |

Evidence limits: all four supplied gate logs were read. Independent source syntax/TOML checks passed; runtime and red→green verdicts rely on the captured executions, not fresh runs. The target is readable and matches the patched layout. No implementation defect was established in this review. No capability-probe/load-time symptom guard was identified; parser-mismatch refusals enforce the declared fail-closed syntax policy.

Prior art: `git log --all -- src/nl_shell/gate pyproject.toml tests/test_policy_gate.py` returns only the synthetic pre-fix base. The brief describes a rejected predecessor and carries forward its defects, but provides no path-based merged/closed-work search evidence; human confirmation remains owed above. INTEGRATION.md is not present among the supplied target files; the brief’s explicit human-only licensing and rule-change requirements are retained.
<!-- pdca:leaf-complete -->

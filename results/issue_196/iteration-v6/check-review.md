Review the new fail-closed policy-gate shell layer, including grammar coverage, invocation records, stdin tracking, and bounded parsing.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The shell-layer scope and deliberately mutating command/live stubs are explicit; class-raising compatibility decisions still require human approval under docs/design/specs/policy-gate/v1.md:238. |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence shows all 217 cases fail with production changes reverted because the gate package is absent; gate-logs/C4-verify.log:17. This establishes the missing feature, not independent coverage of every shell semantic. |
| C3 Change | PASS | Changes stay within the planned parser, pipeline stubs, vectors, dependency pins, tests and threat-model update; src/nl_shell/gate/__init__.py:126 and pyproject.toml:19. |
| C4 Verification (red→green) | PASS | Captured real-parser run reports 217 green cases and 217 red failures, with no collection errors; gate-logs/C4-verify.log:15. Independent rerun unavailable: python is absent and python3 lacks tree_sitter; no local red→green is claimed. |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Correct fd-0 output-duplication/closure tracking before downstream rules trust stdin: _stdin_after leaves both >& and >&- unchanged, so 0>&1 and 0>&- retain terminal/pipe provenance incorrectly; src/nl_shell/gate/parse.py:1026. Add invocation-level regressions for these forms and redirect ordering. |
| T1 Structure | PASS | Parsing/context and command/live policy remain separate with one shared classification budget and explicit extension points; src/nl_shell/gate/__init__.py:126 and src/nl_shell/gate/parse.py:331. |
| T2 Shape | PASS | Threat-model touch is confirmed by the scanner log and source inspection; it documents parser limits, descriptor protections and unresolved dynamic-path limits; .oss-scanner/threat_model.md:114 and gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | Captured full-suite run reports 1318 passed, one skipped and a forkpty warning; gate-logs/T3-suite.log:36. Local runtime reproduction is unavailable without tree_sitter; the dependency was exercised by the captured gate. |
| T4 Contribution | N/A | Contribution artifacts are drafted after Check; the substantive audit reruns at publish, as recorded in gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Approve decision C, stricter descriptor rejection and quote-blind hidden-character rejection under docs/design/specs/policy-gate/v1.md:238; confirm licenses for the new pins at pyproject.toml:19. Confirm affected-path prior art across merged and closed/rejected work: this disposable target has only one synthetic base commit and no remotes, so its history cannot settle that check (brief.md:139). INTEGRATION.md §4 is not supplied, so additional enumerated human-only obligations cannot be checked here. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether this deliberately conservative, unwired shell layer is fit for the staged rollout, including rejected parser-mismatch syntax and deferred command/live semantics; src/nl_shell/gate/__init__.py:25 and .oss-scanner/threat_model.md:133. Green tests alone do not establish completeness against Bash. |

Independent investigation: extracted the actual `_stdin_after` and `_is_zero` function ASTs from target source and executed them with simple redirect records, without replacing their logic. For fd 0 starting at terminal, operators `>&`, `>&-`, `<&`, `<&-` returned respectively `terminal`, `terminal`, `descriptor`, `closed`. A real Bash `exec 0>&-` followed by checking `/proc/self/fd/0` reported `closed`. This isolates the missing output-operator branches; full classify/invocation regression remains for the builder because the parser dependency is unavailable locally.

All source citations refer to the supplied target tree. No capability-probe/load-time-side-effect symptom guard was found; parser-mismatch rejection protects unsupported syntax directly. Frozen wrappers are instance-scoped and were adjudicated from their complete logs. The target was not modified.

<!-- pdca:leaf-complete -->

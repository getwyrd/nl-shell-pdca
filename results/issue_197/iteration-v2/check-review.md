Review the data-driven AST policy command engine, including wrapper recursion, privilege rejection, destructive effects, variable assignments, and fail-closed decisions A–C.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The command grammar, fixed effects, conservative defaults, and root-shell rejection have explicit acceptance contracts; target docs/design/specs/policy-gate/v1.md:131 and :194. |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence demonstrates the stub misclassifies sudo as mutating and reports 248 failures out of 418 with production changes reverted; gate-logs/C4-verify.log:19 and :65. |
| C3 Change | PASS | Reviewed changes address the specified command engine and exposed walker integration cases; command semantics remain target data interpreted by generic handlers; target src/nl_shell/gate/rules.py:455 and targets/ubuntu-26.04/commands.toml:77. |
| C4 Verification (red→green) | PASS | Captured actual pytest execution shows 418 passing post-fix tests and 248 failing pre-fix tests, without setup/collection errors; gate-logs/C4-verify.log:10. Local reproduction is unavailable because pytest and tree_sitter are absent. |
| C5 Causal adequacy | PASS | Command meaning replaces the stub at the classification boundary, and nested work shares a bounded budget; no added capability probe papers over a load-time cause; target src/nl_shell/gate/rules.py:214 and :251. |
| T1 Structure | PASS | Target-data loading, argv interpretation, effect dispatch, and shell walking have separate responsibilities; target src/nl_shell/gate/commands.py:1 and src/nl_shell/gate/rules.py:455. |
| T2 Shape | PASS | Independent AST syntax checks and TOML parsing passed for the gate modules and 49 command rows; the threat-model change is present, matching the captured touch scanner; target targets/ubuntu-26.04/commands.toml:77; gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | Frozen full-suite output records 1519 passed, 1 skipped, and one forkpty deprecation warning, with exit zero; gate-logs/T3-suite.log:10. This is captured gate evidence, not an independent local suite run. |
| T4 Contribution | N/A | Contribution artifacts are drafted after Check; the substantive contribution audit is required again at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm prior art by every affected file path across merged history and closed/rejected work before accepting duplication risk — the provided target has only one synthetic base commit and no closed-work evidence; target .git/HEAD:1; affected paths are listed in patch.diff. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the conservative false-positive cost of decision A and the class-raising command policy for intended use — passing classifier tests cannot decide whether these rejection defaults fit users; target docs/design/specs/policy-gate/v1.md:174 and :310. |

Evidence limits: attempted `python -m pytest -q tests/test_gate_commands.py tests/test_policy_gate.py` in the target failed because `python` is unavailable; `python3 -m pytest` failed because pytest is absent, and importing tree_sitter failed. Consequently no stash/red/pop/green sequence was performed. The frozen C4 and T3 logs contain actual successful test execution, rather than code-read or shim evidence, so the review host's missing tools do not establish an unmet dependency in those recorded runs. Instance-scoped gate wrappers were assessed through their supplied logs. The target is readable and contains the patch; no stale-target caveat was needed.

No grounded implementation defect was identified. No INTEGRATION.md was present in the supplied target, so no additional enumerated human-only items could be inspected. The prior-art limitation above remains a human decision rather than an inferred patch defect.

<!-- pdca:leaf-complete -->

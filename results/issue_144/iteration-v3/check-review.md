Review Unicode 16.0 character-safety rules that reject hidden characters, excessive combining marks and mixed-script proposal words while escaping unsafe displayed text.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | Acceptance vectors and scope define a testable policy, including quoted commands and interpreter-independent Unicode properties (brief.md:7–20; target/tests/test_charsafety.py:96). |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing production render/parser changes produced 40 failures across 47 direct parser/render checks; frozen pytest red leg records 43 failures and 6 passes (gate-logs/C4-verify.log:1125). |
| C3 Change | PASS | Rejection and display share the policy; data generation adds no runtime dependency and the parser retains its strict schema boundary (target/src/nl_shell/proposal.py:127; target/src/nl_shell/render.py:129). |
| C4 Verification (red→green) | PASS | Independent direct checks went 40 failures → zero after stash/pop; frozen end-to-end pytest records 49 green tests; local pytest cannot run because the module is absent (gate-logs/C4-verify.log:12). |
| C5 Causal adequacy | PASS | Property-based rejection closes the specified holes at parsing and display, with no capability-probe fallback; Common characters preserve script intersection rather than masking a mix (target/src/nl_shell/render.py:165; target/src/nl_shell/proposal.py:133). |
| T1 Structure | PASS | One policy module serves parser and renderer, and generated sorted ranges isolate Unicode data from runtime interpreter variation (target/src/nl_shell/render.py:129; target/src/nl_shell/_unicode_tables.py:3). |
| T2 Shape | PASS | Direct inspection confirms the threat-model bullet documents the policy and quoted-command strictness; the scanner's “no security-relevant path touched” alone would not establish this (target/.oss-scanner/threat_model.md:130; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen suite evidence shows 530 passes with one forkpty warning; local full-suite rerun is unavailable without pytest, while direct parser/render checks pass (gate-logs/T3-suite.log:25). |
| T4 Contribution | N/A | Contribution artifacts are absent by design; the substantive audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art against merged history and closed/rejected work — the provided target has only one synthetic base commit, and the brief's keyword searches do not establish that path-based review (brief.md:25). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Confirm the Plan choices on mixed-script rejection, two-mark cap, pinned Unicode and quoted-command strictness are acceptable for real command workflows — automated vectors establish policy behavior, not usability or universal font visibility (brief.md:28; target/.oss-scanner/threat_model.md:136). |

Independent evidence and limits:

- The disposable target was readable and patched. Production changes were stashed and restored in place; direct checks exercised 23 rejected commands, seven accepted commands and 17 escaped characters. Both green runs passed all 47 checks; the red run failed 40.
- Loaded `scripts/gen_unicode_tables.py` and called `generate(Path('/usr/share/unicode'), '16.0.0')`: its output exactly matched the committed module. The build-only Unicode-data dependency was present and exercised, without a shim or curated replacement.
- Pytest invocation failed with `/usr/bin/python3: No module named pytest`. The frozen C4 and T3 logs supply the end-to-end and full-suite evidence; those suites were not independently rerun. Gate wrappers are instance-scoped and absent here as expected.
- Inspected all four supplied gate logs. T4 remains deferred to publish. No INTEGRATION.md was present in the supplied target, so no project-specific human-only checklist could be inspected.
- Affected-path history inspection (`git log --all -- src/nl_shell/render.py src/nl_shell/proposal.py tests/test_charsafety.py`) returned only the synthetic base commit; closed/rejected work is not supplied. No other checkout was consulted.

<!-- pdca:leaf-complete -->

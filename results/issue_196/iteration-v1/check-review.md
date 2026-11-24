Review the new fail-closed AST policy gate shell layer, invocation context, parser pins, stubs, and conformance tests for #196.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The shell-layer scope and deliberate command/live-resolution stubs have explicit success criteria and exclusions; brief.md:28 and brief.md:112. |
| C2 Reproduction (red pre-fix) | PASS | The frozen red leg executes all 78 tests and fails on the absent gate, matching the new-feature baseline; gate-logs/C4-verify.log:2226. |
| C3 Change | PASS | The patch stays within the parser, classification pipeline, staged stubs, vectors and tests authorized by the brief; target/src/nl_shell/gate/__init__.py:106 and target/pyproject.toml:17. |
| C4 Verification (red→green) | PASS | Captured execution shows 78 green tests and 78 red failures without collection errors; this is log-backed evidence, not an independent rerun; gate-logs/C4-verify.log:10 and gate-logs/C4-verify.log:2227. |
| C5 Causal adequacy | PASS | The absent shell layer is supplied with explicit fail-closed handling and shared budget; no capability-probe symptom guard was introduced; target/src/nl_shell/gate/parse.py:234 and target/src/nl_shell/gate/__init__.py:90. |
| T1 Structure | PASS | Separate walker, verdict, command and resolution modules provide the intended sibling extension points without REPL coupling; target/src/nl_shell/gate/__init__.py:118. |
| T2 Shape | NEEDS-HUMAN | Decide whether the new parser input and fail-closed properties require a threat-model update — the security-path scanner found no corresponding update; gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | The captured full suite reports 1179 passed, one skipped and one forkpty warning; local Python lacks pytest and tree_sitter, so independent execution was unavailable; gate-logs/T3-suite.log:34. |
| T4 Contribution | N/A | Contribution artifacts are absent by design and their substantive audit reruns at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Approve decision C, stricter descriptor rejection and quote-blind hidden-character rejection, confirm parser dependency licensing, and settle affected-path prior art across merged and closed/rejected work — the disposable repository has only one base commit and no remotes, so complete history cannot be checked; target/docs/design/specs/policy-gate/v1.md:238, target/pyproject.toml:19, brief.md:127 and brief.md:139. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether this intentionally unwired, always-at-least-mutating shell layer is a suitable foundation for later command and live-session policy work — green component tests do not demonstrate end-to-end execution safety; target/src/nl_shell/gate/__init__.py:25 and brief.md:120. |

Evidence limits: `python3 -m pytest` cannot run here because pytest is absent; importing tree_sitter also fails. No stash cycle was performed because neither leg could execute in this host. The frozen C4 log exercises the actual parser (including grammar enumeration), so the declared tree-sitter-bash dependency was exercised by the gates; no shim or curated replacement is shown. Wrapper absence is expected and is not a patch defect. The complete captured C4 and T3 outputs, and both scanner/contribution logs, were inspected. No target-state mismatch was found.

Prior art: affected-path `git log --all` exposes only the synthetic base commit; `git ls-tree` confirms the gate and policy test were absent there. The brief records a rejected v2 attempt and its stdin bug, but the supplied bundle cannot establish a complete merged/closed-work search. This remains the T5 human decision above.

A direct Bash check, `bash -c 'read -r line <>brief.md; printf "%s\\n" "$line"'`, read the first line of the file. Source inspection confirms `<>` is covered by the `<` prefix at target/src/nl_shell/gate/parse.py:75 and becomes file stdin at target/src/nl_shell/gate/parse.py:557; no finding is raised for it.

<!-- pdca:leaf-complete -->

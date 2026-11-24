Review replacing the policy gate’s all-mutating command stub with a reviewed command table and generic argv engine for destructive commands, elevation, wrappers, and opaque code execution (#204).

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The scoped closed-world rules distinguish elevation, unread argv, opaque text, and accepted floor gaps; acceptance criteria are falsifiable (target/docs/design/specs/policy-gate/v1.md:177, :190, :204). |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence demonstrates behavioral failures for recursive rm and sudo password-input rejection, beyond missing-new-module setup errors (gate-logs/C4-verify.log:2170, :3477, :7547); independent rerun unavailable here. |
| C3 Change | PASS | Meaning comes from reviewed rows and a fixed loader location rather than caller-controlled paths; the command-layer decoder preserves shell-layer literal semantics (target/src/nl_shell/gate/commands.py:311; target/src/nl_shell/gate/rules.py:119). |
| C4 Verification (red→green) | PASS | Frozen gate output establishes 164 assertion failures plus 12 setup errors pre-fix and 413 passing tests patched; this is log-supported verification, not an independent rerun (gate-logs/C4-verify.log:17, :7547). |
| C5 Causal adequacy | PASS | Replacing the absent command semantics addresses the stated cause; elevation and opaque-command scans cover the carried-forward bypass classes, with no capability-probe symptom guard found (target/src/nl_shell/gate/rules.py:299, :349, :389; target/tests/test_gate_commands.py:465, :532, :561, :578). |
| T1 Structure | PASS | Separate immutable table loading and one effect-driven engine keep command-specific meaning in data; seven affected Python files pass independent syntax compilation (target/src/nl_shell/gate/commands.py:336; target/src/nl_shell/gate/rules.py:404; review-checks.log:1). |
| T2 Shape | PASS | Threat-model claims and explicit residual gaps accompany the security change; independently harvested inventory is byte-identical and all 152 names match rows (target/.oss-scanner/threat_model.md:194; review-checks.log:2, :3; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen full-suite output records 1,546 passed, one skipped and five forkpty warnings; local pytest/parser dependencies are absent, so runtime success is supported by that log only (gate-logs/T3-suite.log:33, :43; review-checks.log:4). |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm prior art by every affected file path across merged history and closed/rejected work — the synthetic single-commit repository has no remote, so duplicate or previously rejected work cannot be ruled out (review-checks.log:5). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the documented security tradeoffs for this child — opaque quoted text and named floor gaps remain mutating, while decision A can over-raise until the allowlist child; passing tests cannot decide suitability for intended use (target/docs/design/specs/policy-gate/v1.md:204; brief.md:26). |

Evidence and limits:

- Grounding used only the supplied patched target. Its local base is the stated pre-fix snapshot; no stale-target issue was observed. No target source was edited.
- This reviewer’s Python has neither pytest nor tree_sitter/tree_sitter_bash. Consequently no independent stash/red/restore/green or full-suite run was possible. All four supplied gate logs were opened. The C4 log includes genuine assertion failures as well as fixture ImportErrors; those fixture errors alone are not the reproduction claim. The external parser dependency was exercised by the frozen successful gates, rather than replaced with a shim or code-read.
- Independently ran `python3 scripts/harvest_inventory.py --output ../review-inventory.toml` from target: successful, byte-identical inventory on Ubuntu 26.04.1. Parsed the command table and checked inventory-name coverage with stdlib TOML/fnmatch; this is not a substitute for the production loader tests. `git diff --check` passed; `python3 scripts/docs_links.py` reported 65 links, zero broken. `docs_checks.py` without arguments printed its required immutability BASE/HEAD usage and did not perform an audit.
- Prior-art investigation: path-filtered `git log --all` exposes only synthetic base b6e4e2d; `git remote -v` is empty. No closed/rejected-work records or INTEGRATION.md human-only checklist are supplied. The prior-art decision remains open; no external checkout was consulted.
- No grounded implementation defect found. The scope’s size and previous iteration are explicitly accepted in brief.md:277; they are not newly reopened here.

<!-- pdca:leaf-complete -->

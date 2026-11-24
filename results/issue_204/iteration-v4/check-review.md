Review issue #204: replace the command-policy stub with a reviewed command table and generic engine, including fail-closed unreadable command words and the carried-forward §5 bypass fixes.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The brief defines decisions A–D, accepted gaps, and carry-forward cases explicitly; the elevation contract is reflected at target/docs/design/specs/policy-gate/v1.md:179. |
| C2 Reproduction (red pre-fix) | NEEDS-HUMAN | Confirm the public-API pre-fix red leg in an equipped environment — pytest and tree-sitter are unavailable locally, and the frozen verification stops during its green leg without recording red-leg execution (gate-logs/C4-verify.log:81). |
| C3 Change | PASS | The patch supplies the requested reviewed data, closed-schema loader and generic engine; fixed-root loading rejects escape paths and malformed input (target/src/nl_shell/gate/commands.py:322); git diff --check passes. |
| C4 Verification (red→green) | FAIL | A successful red→green is absent: both frozen green-leg attempts fail the 5-second size-cap test, with 473 other tests passing; this is observed test evidence, not a confirmed attribution of the slowdown (gate-logs/C4-verify.log:76). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Bound bracket recovery work before scanning every malformed node — repeated scans of the same unrecognized word can consume quadratic work without reaching the successful-recovery deduplication, undermining bounded classification (target/src/nl_shell/gate/parse.py:685). |
| T1 Structure | PASS | Per-command behavior remains reviewed data consumed by a common grammar/effect engine, and loader failures flow into the existing fail-closed sink (target/src/nl_shell/gate/rules.py:93). |
| T2 Shape | PASS | Security documentation changes with the engine, including locale quoting and unreadable-command handling; independently confirmed the threat-model diff and frozen touch-check output (target/.oss-scanner/threat_model.md:194; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | FAIL | The frozen whole-suite runs remain red on the same latency assertion; the last run reports 1606 passed, 1 skipped and 1 failed, so whole-suite success is not established (gate-logs/T3-suite.log:129; target/tests/test_policy_gate.py:716). |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive contribution audit must run at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art against merged and closed/rejected work — the brief records that search, but this target has only one synthetic base commit and no supplied closed-work evidence to independently settle duplication (brief.md:365). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the accepted class-7/path-resolution gaps and conservative rejections fit the intended release, after obtaining a successful public-API red→green run; tree-sitter-bash was exercised in frozen logs but is unavailable for this independent review (brief.md:357; target/docs/design/specs/policy-gate/v1.md:176). |

Independent checks and limits:

- The target is a readable disposable patched copy with a synthetic pre-fix base; no stale-target caveat was found. No source files were changed. Stashing the patch would not enable a meaningful classifier run without the unavailable dependencies, so no stash/red/pop sequence was performed.
- `python3` is 3.14.4; importing pytest fails. An offline uv attempt using a cache inside this scratch root cannot resolve tree-sitter==0.26.0. Instance-root wrappers were not run; their full frozen logs were read. The logs show actual classifier tests executing, not a missing-tool failure, but contain no pre-fix timing comparison.
- Ran `python3 target/scripts/harvest_inventory.py --output inventory-review.toml` and compared with the checked-in inventory: exact match, including mount.cifs and mount.smb3. The local VERSION is Ubuntu 26.04.1 LTS (Resolute Raccoon), matching the inventory.
- Independently executed the unchanged `_word_start`, `_raw_words`, and `_unquoted_bracket` helper bodies extracted with Python AST, once per two-byte position in repeated `$[` input. At 2048/4096/8192 bytes this took 1.569/6.652/27.128 seconds. This isolates quadratic helper work; it is not a public-classifier benchmark or a claim that every offset is visited by the parser. `_error` calls recovery for each error node (target/src/nl_shell/gate/parse.py:711), while unsuccessful candidates never enter `bracket_words` (target/src/nl_shell/gate/parse.py:689). Fix the repeated work and re-run the existing latency test rather than weakening its threshold.
- The C5 capability-probe smell-test does not fire: missing/invalid-table handling is the specified fail-closed dependency boundary, not a probe masking eager capability use. No INTEGRATION.md was present in the supplied target.
- The brief records prior-art searches by affected paths, including closed/unmerged PRs; the synthetic local history cannot independently corroborate those results. No other checkout was consulted.

<!-- pdca:leaf-complete -->

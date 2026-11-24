Review issue #196: add the fail-closed AST policy gate shell layer, six conservative parsing rules, and downstream stubs.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The brief defines six falsifiable rules and explicitly excludes command semantics and REPL integration; the target preserves human review of policy raises (docs/design/specs/policy-gate/v1.md:238). |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence shows all 157 tests executed and failed because the gate package was absent, with no collection errors (gate-logs/C4-verify.log:3635); independent execution is unavailable here. |
| C3 Change | PASS | Changes stay within the planned gate package, dependency pins, vectors, tests and threat-model properties; dependencies are pinned in pyproject.toml:19 and the threat-model addition begins at .oss-scanner/threat_model.md:157. |
| C4 Verification (red→green) | PASS | The captured gate demonstrates 157 green tests and 157 red tests (gate-logs/C4-verify.log:14, gate-logs/C4-verify.log:3635); this is log-backed evidence, not an independent rerun, and does not cover the additional defect below. |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Preserve ordinary words adjacent to redirects: descriptor recovery removes any adjacent word without validating it as a descriptor, losing arguments such as `secret` in `echo secret>out` and potentially a command name; add real-parser word-preservation regressions (src/nl_shell/gate/parse.py:664). |
| T1 Structure | PASS | Parsing facts, command policy, live resolution and vector validation have distinct modules, and the pipeline calls the planned downstream steps (src/nl_shell/gate/__init__.py:198). |
| T2 Shape | PASS | The threat-model gate records the required update; source inspection places the addition under “What must hold” and leaves Known gaps unchanged (gate-logs/T2-threat-model.log:10; .oss-scanner/threat_model.md:157). |
| T3 Runtime | PASS | The captured full-suite run reports 1,258 passed, one skipped and one forkpty warning; no independent runtime rerun was possible in this sandbox (gate-logs/T3-suite.log:35). |
| T4 Contribution | N/A | Contribution artifacts are intentionally drafted later; the substantive contribution audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm dependency-license acceptability and the affected-path prior-art check across merged and closed/rejected work: local history contains only a synthetic base and no remotes, so the brief’s historical check cannot be independently confirmed here (pyproject.toml:19; brief.md:312). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Approve decision C, stricter redirect rejection, rejection of untrusted proposals and quoted hidden characters, and the 8 KiB cap; decide whether to record the proposal ruling on #196 or require the spec edit now, since these change accepted policy behavior (docs/design/specs/policy-gate/v1.md:238; brief.md:296; brief.md:337). |

The C5 finding is grounded on the patched target. At src/nl_shell/gate/parse.py:667–672, every adjacent token is removed from the word list when the redirect lacks a descriptor field. Unlike `_descriptor` at :775, this code never checks whether that token denotes a descriptor. The later visit of the removed node at :683 satisfies walk coverage but does not restore it to the invocation words at :695. Thus node-count tests can pass while invocation contents are incomplete. The current always-mutating stub masks the downstream classification impact.

I executed the original `_simple` function extracted with Python’s AST, supplying an explicit ordinary-argument/no-descriptor node shape for `echo secret>out`: expected words `['echo', 'secret']`, observed `['echo']`. This isolates the filtering defect; it is not a tree-sitter integration reproduction. The builder should verify `echo secret>out`, `cat /etc/passwd>out`, and `echo>out` against the pinned parser and assert complete invocation words, then retain valid descriptor-recovery cases such as `cat 0>&-`.

Independent verification limits: `python` is absent; `/usr/bin/python3` has neither pytest nor tree_sitter, and pip is absent. I therefore did not stash the target merely to attempt an unavailable test runner. I read all four frozen logs, including their command/worktree headers, and adjudicated the executed gates from their captured output. The logs show real pytest execution with the parser dependency, so they do not establish an undischarged external dependency for those runs. `git diff --check` passed locally. The wrappers belong to the harness instance and their absence from the target is expected.

The affected-path history investigation returned no commits for `src/nl_shell/gate`; the disposable repository has a single synthetic base commit and no remotes. That is insufficient to independently establish merged and closed/rejected prior art. No INTEGRATION.md is present in the supplied target; the human-only policy and dependency-license decisions explicitly identified by the brief remain above. No capability-probe symptom guard was found.

All source citations above are relative to `$PDCA_TARGET`; brief and frozen-log citations refer to the supplied review bundle. This review is advisory and does not gate acceptance.

<!-- pdca:leaf-complete -->

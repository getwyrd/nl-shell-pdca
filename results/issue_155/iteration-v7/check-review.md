Review the new trusted-facts failure classifier for #155, including the multiline-alias and alias-depth regressions, under the agreed stateless P1–P5 rule.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The brief defines precedence, accepted over-matches, explicit gaps and a bounded review scope; the trusted result fields exist on this target (src/nl_shell/session.py:375). |
| C2 Reproduction (red pre-fix) | PASS | Frozen execution shows 269 failures and one intentionally unchanged ASCII self-check without production changes; these are test failures rather than collection errors (gate-logs/C4-verify.log:17). |
| C3 Change | PASS | The patch stays within the classifier, its tests and the required Known-gaps bullet; trusted status and text determine routing (src/nl_shell/failure_classes.py:118; .oss-scanner/threat_model.md:190). |
| C4 Verification (red→green) | PASS | Frozen evidence shows 270 passing with the patch and 269 failing without it; local pytest is unavailable, so this verdict rests on the captured run, supplemented by direct alias checks (gate-logs/C4-verify.log:10). |
| C5 Causal adequacy | PASS | Direct execution confirms multiline aliases and depth-sensitive revisits are privileged, while a short tail and a self-naming plain alias remain ordinary; no capability-probe symptom guard was introduced (src/nl_shell/failure_classes.py:236; src/nl_shell/failure_classes.py:300). |
| T1 Structure | PASS | Immutable results, separate privilege and suggestion helpers, and bounded alias recursion fit this standalone classifier; no parser or provider integration expands the slice (src/nl_shell/failure_classes.py:57; src/nl_shell/failure_classes.py:221). |
| T2 Shape | PASS | The actual threat-model bullet documents all five accepted gap categories; the touch gate merely reports no matched security path, so substantive coverage comes from source review ( .oss-scanner/threat_model.md:190; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Captured whole-suite execution reports 922 passed and one forkpty warning; local direct imports and alias probes also succeed, but pytest cannot be independently repeated here (gate-logs/T3-suite.log:30). |
| T4 Contribution | N/A | Contribution artifacts are intentionally absent at Check; the substantive contribution audit must re-run at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm merged and closed/rejected prior work by both affected paths before sign-off — this disposable one-commit history cannot establish prior art, and the GitHub query failed to connect; the brief records the earlier path check and rejected iterations (src/nl_shell/failure_classes.py:1; tests/test_failure_classes.py:332). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the documented false positives and privilege misses for this slice, and choose waiting for #140 or publishing against its branch — the folded target exercises CommandResult, but publication against main still depends on that prerequisite (.oss-scanner/threat_model.md:190; src/nl_shell/session.py:375). |

Evidence and limits:

- Read all four supplied gate logs. The C4 log records 270 green tests, then 269 failures and one pass on the reverted tree; T3 records 922 passing tests. Instance-scoped wrappers are not present here, and `python3 -m pytest -q tests/test_failure_classes.py` fails because pytest is not installed. No independent pytest red→green is claimed; the target was left intact.
- Independently imported the actual target module with bytecode writes disabled. `s x` with the multiline sudo alias returned True; `a8; a0`, `a8 a0`, and `a7; a0` on the ten-alias chain returned True; `a8; a9` and the self-naming plain ls alias returned False. These exercise the fixes at src/nl_shell/failure_classes.py:238 and src/nl_shell/failure_classes.py:317.
- Independently confirmed `2>&1 sud${X}o x` returns False. This is the explicitly accepted rule gap documented at .oss-scanner/threat_model.md:200, not a new implementation finding.
- `git log --all -- src/nl_shell/failure_classes.py tests/test_failure_classes.py` returned no entries in the disposable target. `gh pr list --repo eduralph/nl-shell --state all --search failure_classes --json number,state,title` could not connect to api.github.com. The merged/closed/rejected path audit therefore remains unconfirmed, rather than inferred from the empty local history.
- The target contains the required #140 CommandResult fields; no stale-target caveat applies. No INTEGRATION.md was present among target files. No real privilege command or external package provider was exercised; both are explicitly outside this slice, whose brief lists no external dependencies.

<!-- pdca:leaf-complete -->

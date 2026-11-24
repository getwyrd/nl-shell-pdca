Review issue #77: add an OpenAI-compatible teacher client with constrained proposal decoding, explicit endpoint opt-in, REPL integration, and endpoint status.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The brief supplies observable endpoint-safety and response-rejection criteria, a fake-server oracle, and explicit scope boundaries (brief.md:17–27). |
| C2 Reproduction (red pre-fix) | FAIL | No executed pre-fix feature failure is supplied: the verification gate stopped before testing because the bundle contained no patch (gate-logs/C4-verify.log:10). |
| C3 Change | FAIL | The supplied patch.diff is zero bytes; there is no submitted implementation or test change to assess against the requested feature (brief.md:18; gate-logs/C4-verify.log:10). |
| C4 Verification (red→green) | FAIL | Neither red nor green feature evidence exists: C4 exited 77 for the absent patch, independently confirmed as an empty input; this is a submission-evidence failure, not a compilation defect attributed to the target (gate-logs/C4-verify.log:7–10). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Supply the implementation and discriminating tests before causal adequacy can be judged — an empty submission cannot establish the endpoint-safety or rejection guarantees (brief.md:18; gate-logs/C4-verify.log:10). |
| T1 Structure | N/A | There is no submitted code structure or dependency change to review; patch.diff is empty (gate-logs/C4-verify.log:10). |
| T2 Shape | N/A | No security-relevant diff exists to audit; the scanner explicitly skipped substantive checking, so its pass is not evidence of threat-model coverage (gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen evidence records 330 existing tests passing; this supports baseline runtime health only, with no feature coverage asserted (gate-logs/T3-suite.log:10–17). |
| T4 Contribution | NEEDS-HUMAN | Confirm the actual contribution artifacts meet the opener and tracker requirements — the log records exit zero but contains no captured check output or artifact content to inspect (gate-logs/T4-contribution.log:7–9). |
| T5 Judgment | NEEDS-HUMAN | Confirm the loopback opt-in rule, service-start deferral, and optional model-name scope; also refresh closed/rejected prior art by affected path, since available local history cannot establish that remote work was checked (brief.md:29,65–72). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide fitness only after a substantive bundle and executable feature evidence are available; then confirm the intentionally manual real-teacher behavior and the project's human-only requirements (brief.md:19,63–72). |

Evidence and limitations:

- Independently checked the supplied patch: `wc -c patch.diff` returned `0`. There is nothing to stash or restore, so no target mutation was performed.
- Read all four frozen logs. C4 explicitly reports missing patch evidence; T2 explicitly reports nothing to check. T3 reports 330 passing tests. T4 records a successful process exit with no substantive output. No row is marked deferred.
- Attempted an independent feature-test collection using `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider --collect-only -q "$PDCA_TARGET/tests/test_teacher_client.py"`; the available interpreter reported `/usr/bin/python3: No module named pytest`. This is a reviewer-host limitation, not a patch defect. Runtime adjudication above therefore rests on the frozen suite log, not an independent suite rerun. The instance-root gate wrappers are outside the permitted grounding scope and were not sought in other checkouts.
- Target-state caveat: `$PDCA_TARGET` is clean at `0771812`, but its REPL still contains the pre-backend placeholder (`src/nl_shell/repl.py:25–28,74–78`), rather than the #16 interface required by the brief. The CLI parser is at `src/nl_shell/cli.py:26–33`. The teacher test file is absent. These observations do not establish a patch regression or an ordering blocker; this target does not supply the promised folded prerequisite base, and the empty diff offers no alternate implementation grounding.
- Prior-art investigation: local `git log --all -- src/nl_shell/teacher_client.py tests/test_teacher_client.py` returned no entries; history for `src/nl_shell/cli.py`, `src/nl_shell/repl.py`, and `src/nl_shell/config.py` contains scaffold, routing, input-mode, and target-selection work. The brief's broad historical claim does not independently confirm closed/rejected work by those affected paths. No external service was contacted.
- No `INTEGRATION.md` was found within the target, so its enumerated human-only items could not be independently read. No capability-probe smell-test can be applied to an empty diff.

<!-- pdca:leaf-complete -->

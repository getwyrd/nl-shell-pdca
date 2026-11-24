Review issue #141: detect persistent Bash and PTY tampering before another confirmed paste can execute altered bytes.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The closed attack list, accepted gaps and reason-code requirements make the intended behavior falsifiable; brief.md:19 and brief.md:30. |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing the patch left `stty -isig`, the post-D DEBUG attack and an Enter macro healthy; frozen evidence additionally records 48 failures without collection errors (gate-logs/C4-verify.log:1606). |
| C3 Change | FAIL | Criterion (s) requires `h-changed` for disabled hook builtins unless record writing stops; `set` instead writes a malformed D and returns `other`, reproduced directly, while the test accepts this unbriefed exception (target/tests/test_session.py:1362; brief.md:30). |
| C4 Verification (red→green) | PASS | Restoring the patch independently made all three smoke attacks degrade and refuse the next command; the captured full session run reports 148 green and 48 red tests (gate-logs/C4-verify.log:10; gate-logs/C4-verify.log:1606). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Correct the disabled-`set` reason-code behavior and tighten its test to criterion (s): permitting `other` hides a diagnostic contract failure despite safe refusal (target/src/nl_shell/session.py:164; target/tests/test_session.py:1378). |
| T1 Structure | PASS | The hook handshake and outside observations address the two terminal states within the existing Session boundary; protocol changes retain existing reason text (target/src/nl_shell/session.py:850; target/src/nl_shell/pty_protocol.py:298). |
| T2 Shape | PASS | Independent Python/Bash syntax and diff whitespace checks pass; builtin coverage matches hook calls and the reference rcfile matches using the repository test's extraction; threat-model coverage is updated (target/tests/test_session.py:930; target/.oss-scanner/threat_model.md:181; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Captured suite output shows 385 passing tests; independent real-PTY smoke runs confirm ordinary output, tamper detection and refusal here; full pytest cannot be repeated because this sandbox lacks pytest (gate-logs/T3-suite.log:17; target/src/nl_shell/session.py:623). |
| T4 Contribution | N/A | Contribution artifacts are absent by design; the substantive audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm the affected-path prior-art search across merged history and closed/rejected work: the brief claims it ran, but this target has one synthetic base commit, no remote and no independently inspectable PR evidence (brief.md:48). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the bounded protection and documented operational restrictions are fit for this milestone, retaining the explicit downstream integration restriction for #145/#147/#148 (target/.oss-scanner/threat_model.md:199; target/.oss-scanner/threat_model.md:204). |

Independent execution used the supplied disposable target only. `git stash` restored its pre-fix tree and `git stash pop` restored all five patch files. `review-smoke.py` runs three real Bash/PTY attacks: each stayed healthy before the fix; afterwards the two terminal attacks produced `outside-check`, the Enter macro produced `h-changed`, and each subsequent command was refused. Ordinary `echo hello` returned exactly `hello\n`. A separate live run of `enable -n set` produced `other: malformed control record: malformed D record: 'D 1  '`. This is a reason-code mismatch, not evidence of a successful paste bypass.

The frozen C4 log shows both legs actually executed (148 passed; 48 failed and 100 passed, zero collection/setup errors), and the T3 log shows 385 passed. The instance-scoped gate wrappers are unavailable here; their logs supply the full-suite evidence. Real Bash 5.3.9, ptyprocess, child `/proc` access and the real PTY were exercised independently without a shim. The default TIOCSTI check allowed healthy startup. No target staleness was observed. No capability-probe symptom guard requiring a separate root-cause decision was identified.

Prior-art investigation: `git log --all -- <all five affected paths>` returned only synthetic commit `3103c55` (pre-fix base 0771812); `git remote -v` returned no remotes. The brief's path-based historical claim cannot be independently completed from this artifact bundle. No INTEGRATION.md was supplied in the available target tree.

<!-- pdca:leaf-complete -->

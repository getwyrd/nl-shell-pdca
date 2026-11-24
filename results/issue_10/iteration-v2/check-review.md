Review issue #10: implement a persistent bash PTY session with control-channel completion, state snapshots, output capture, and terminal forwarding.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The bounded session scope and observable conformance requirements establish a reviewable contract; REPL integration remains a separate issue — target/docs/design/specs/pty-protocol/v1.md:98, brief.md:16. |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing the patch makes the session import fail; the frozen red leg additionally records 39 executed test failures from missing production modules, with no collection errors — gate-logs/C4-verify.log:14. |
| C3 Change | PASS | The five affected files belong to the planned session, dependency, tests, and threat-model scope; the previous numeric-parser and hook-redefinition concerns are addressed — target/src/nl_shell/pty_protocol.py:205, target/src/nl_shell/session.py:113. |
| C4 Verification (red→green) | PASS | Frozen evidence shows 39 failures without production changes and 39 passes with them; independent restored-tree bash/PTY smoke checks pass, although local pytest is unavailable — gate-logs/C4-verify.log:10, target/tests/test_session.py:144. |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Require the matching alternate-screen reset before resuming capture — a live 1049h/47l sequence captures SECRET2 before 1049l, violating the specified exclusion; add a regression for mismatched resets — target/src/nl_shell/session.py:199, target/docs/design/specs/pty-protocol/v1.md:127. |
| T1 Structure | PASS | The pure record state machine is separated from process and terminal ownership, giving downstream consumers typed results without REPL coupling — target/src/nl_shell/pty_protocol.py:146, target/src/nl_shell/session.py:166. |
| T2 Shape | PASS | The security-relevant files have the required threat-model exercise update; the touch gate confirms that limited assertion, not a comprehensive security audit — target/.oss-scanner/threat_model.md:178, gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | The frozen suite reports 187 passes; independent real bash 5.3.9/ptyprocess 0.7.0 checks confirm persistent state, pipeline status, hook refusal and malformed-number degradation; the capture defect remains separately recorded — gate-logs/T3-suite.log:14, target/tests/test_session.py:414. |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive contribution audit must run at publish — gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path merged and closed/rejected prior art before accepting novelty — the supplied history is one synthetic base commit, and the brief's broader src/ search does not independently establish history for every affected path — brief.md:26. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept or revise the prompt-detection trade-off and capture loss after forwarded input, and assign output-filter ownership before user-facing integration — these affect usability and safety beyond passing vectors — target/src/nl_shell/session.py:531, target/src/nl_shell/session.py:618, brief.md:105. |

Independent evidence and limits:

- All source citations above were checked against the supplied target. Its patch was stashed and restored successfully; no source changes were made. The pre-fix import raised `ModuleNotFoundError: No module named 'nl_shell.session'`. After restoration, a real session preserved `cd /tmp` and `export FOO=bar`, returned `(1, 0)` for `false | true`, and reported status 0 for ordinary commands.
- Local Python has ptyprocess 0.7.0 but no pytest. Therefore the complete red/green and whole-suite verdicts rely on the inspected frozen logs, not a claimed independent pytest rerun. The gate logs show actual executed tests, not an alias or code-read substitute. Real bash and ptyprocess were also exercised independently here, so those external dependencies are discharged.
- The previous iteration's oversized D record independently produced sticky malformed-record degradation. Attempts to redefine `__nls_done` and assign `__nls_user_pc` each returned status 1 without changing the protected hooks. These fix causes rather than adding a capability probe around a load-time side effect.
- `git diff --check` passed for tracked changes. The documentation link scanner independently reported 60 links in 53 Markdown files, zero broken. The threat-model touch claim was checked against the patch and its frozen log. The docs immutability tool requires base/head arguments and was not counted as a successful scanner run.
- Affected-path history was queried for both new modules, the session tests, pyproject.toml, and the threat model. It yielded only synthetic base commit `0112440`. No INTEGRATION.md is supplied in this target; no additional human-only rules could be read from it. Closed/rejected work cannot be established from this artifact bundle.

Builder-fixable capture finding:

At target/src/nl_shell/session.py:199, an active alternate screen accepts every member of `_ALT_OFF`, and line 211 toggles a boolean without remembering the activating mode. In an actual `Session.run`, sending the shell command below returned `b'beforeSECRET2\x1b[?1049lafter'`:

```bash
printf 'before\033[?1049hSECRET1\033[?47lSECRET2\033[?1049lafter'
```

The contract requires capture to resume on the matching reset (target/docs/design/specs/pty-protocol/v1.md:127). Expected capture under that contract is `b'beforeafter'`. Track the relevant active mode and add mismatched-reset coverage, including fragmented escape sequences. The existing test at target/tests/test_session.py:298 covers matching resets only.

Human validation context: the brief explicitly accepts a one-second false positive for blocking builtins, and the implementation stops capture permanently for a command once input is forwarded. Decide whether those limitations fit the next consumers. The rendering filter is explicitly deferred in the brief and must have an owner before #78 exposes the mirror. This report is advisory and does not gate acceptance.

<!-- pdca:leaf-complete -->

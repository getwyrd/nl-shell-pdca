Review issue #140: add an unwired persistent bash PTY session with fd-3 protocol snapshots, exact command pasting, and sticky degradation under the brief's closed guarantees.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The closed guarantees and explicit exclusions give a bounded acceptance contract; no general tamper resistance is required (brief.md:7; target/docs/design/specs/pty-protocol/v1.md:144). |
| C2 Reproduction (red pre-fix) | N/A | New functionality has no existing symptom to reproduce; removal sensitivity is assessed under C4 (brief.md:31). |
| C3 Change | PASS | Changes stay within the session, parser, dependency, tests, and specified design documents; the core remains unwired (target/src/nl_shell/session.py:9; target/pyproject.toml:15). |
| C4 Verification (red→green) | PASS | Independent stash/restore smoke check went from missing session module to passing real bash checks; frozen evidence additionally shows 90/90 red and 90 green, although pytest is unavailable for a full local rerun (reviewer-red.log:1; reviewer-green.log:1; gate-logs/C4-verify.log:13; gate-logs/C4-verify.log:3323). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Close the I2-b value-change detection gap: confirmed scratch-state assignments remain healthy because their values are overwritten before H, contradicting the promised own-command degradation (target/src/nl_shell/session.py:128; target/docs/design/specs/pty-protocol/v1.md:148; target/tests/test_session.py:522). |
| T1 Structure | PASS | Pure protocol sequencing is separated from PTY lifecycle and I/O, making failure transitions independently inspectable (target/src/nl_shell/pty_protocol.py:157; target/src/nl_shell/session.py:322). |
| T2 Shape | PASS | Threat-model coverage explicitly limits the claim and prohibits wiring confirmed commands before #141; the frozen touch-check passes and the independent docs-link scan found zero broken links (target/.oss-scanner/threat_model.md:181; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen full-suite evidence reports 267 passing tests; independent real-bash smoke checks exercised persistence, output, pipeline status, refusal, degradation, and restart, but did not replace the unavailable pytest rerun (gate-logs/T3-suite.log:15; reviewer-green.log:1). |
| T4 Contribution | N/A | Contribution artifacts are absent by design; the substantive contribution audit is deferred to the mandatory publish rerun (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm the path-based prior-art disposition against merged and closed/rejected work: the brief records that check, but this one-commit target has no remote or PR evidence with which to independently settle it (brief.md:38). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the completed closed guarantees meet the intended standalone-core milestone after the C5 discrepancy is resolved; retain the already accepted unwired scope and #141 integration prerequisite (target/.oss-scanner/threat_model.md:181; target/docs/design/specs/pty-protocol/v1.md:144). |

Independent finding: ordinary value assignments evade the promised I2-b degradation

Using real bash 5.3.9 and the installed ptyprocess, I started a fresh session for each of these confirmed commands with `Session.start(env=env, cwd=home, timeout=5)` and `session.run(command, timeout=5)`:

```text
'__nls_n=42'       ran=True healthy=True status=0
'__nls_st=42'      ran=True healthy=True status=0
'__nls_v=changed'  ran=True healthy=True status=0
'__nls_c=changed'  ran=True healthy=True status=0
'__nls_ps=(42)'    ran=True healthy=True status=0
```

These are ordinary assignments within the explicit I2-b claim, not excluded DEBUG/functrace or builtin-shadowing evasions. The hooks overwrite the values before recording H (target/src/nl_shell/session.py:111, target/src/nl_shell/session.py:128, target/src/nl_shell/session.py:139). The test matrix checks an integer attribute change, but not these plain value changes (target/tests/test_session.py:530). Add regression coverage for the promised own-command degradation and resolve the implementation/contract discrepancy. This finding does not demonstrate a hidden executed command; it demonstrates failure of the expressly claimed degradation behavior. Narrowing that guarantee instead would require a human scope decision.

Verification limits and grounding

- The disposable target identifies its base as c47c5c2 and its applied changes match the supplied patch scope. Citations above were checked against this target; no stale-target caveat was needed. The patch was restored after the independent red leg.
- `reviewer-smoke.py` is the independent runnable check. Run from this review directory with `TMPDIR="$PWD/reviewer-tmp" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/target/src" python3 reviewer-smoke.py`. Red failed importing the absent implementation; green exercised real PTY and proc-syscall behavior. Neither external dependency was replaced with a shim or fixture.
- Python cannot import pytest in this reviewer environment. Therefore the complete 90-test and 267-test results above are attributed to the frozen gate logs, not represented as independent full-suite reproductions. All four supplied gate logs were read; the wrappers are harness-scoped. No missing-log escalation applies.
- Independent `git diff --check` passed. `python3 scripts/docs_links.py` reported 63 links in 55 Markdown files, zero broken; it also emitted three host messages, `Failed to create stream fd: Operation not permitted`, while exiting successfully.
- The target has one synthetic base commit, no configured remote, and no history entries for the three new affected paths. The brief names the prior path-based search and merged design PRs, but closed/rejected upstream work cannot be independently established from this bundle. No INTEGRATION.md was supplied or found in the target.
- The C5 symptom-guard smell test found no eager/load-time capability workaround: the `os.ptsname` feature check selects a platform/Python compatibility implementation, and `/proc` failures fail closed rather than conceal a load-time cause (target/src/nl_shell/session.py:740).

This report is advisory; deterministic gates retain their separate role.
<!-- pdca:leaf-complete -->

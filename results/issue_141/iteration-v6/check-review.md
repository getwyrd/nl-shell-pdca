Review issue #141: detect persistent bash/readline and terminal tampering before another confirmed paste, with option B’s explicitly limited after-the-fact terminal checks.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The closed attack list, three terminal guarantees and accepted gaps define an assessable scope; brief.md:15–22, brief.md:45–49. |
| C2 Reproduction (red pre-fix) | PASS | Independently stashed the patch: `trap ':' USR1` left the session healthy and a subsequent `echo hello` executed; the frozen broader red leg reports 60 failures and 103 passes, gate-logs/C4-verify.log:2022. |
| C3 Change | FAIL | Table A explicitly requires EXIT coverage, but the patch deliberately removes EXIT from H; this narrows the agreed contract without an authorized exception, target/src/nl_shell/session.py:200 and target/docs/design/specs/pty-protocol/v1.md:283; brief.md:17. |
| C4 Verification (red→green) | PASS | After stash restoration, the same USR1 probe degraded with `h-changed` and the following paste was refused; frozen full session evidence shows 163 green versus 60 red failures, gate-logs/C4-verify.log:14 and gate-logs/C4-verify.log:2022; full pytest repetition unavailable locally because pytest is absent. |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Restore the promised every-trap coverage and add an EXIT regression: independently executing `trap ':' EXIT` on the patched session returned healthy and the next `echo hello` ran, leaving a required case outside enforcement; target/src/nl_shell/session.py:200, target/tests/test_session.py:1086, brief.md:17. |
| T1 Structure | PASS | Outside readings and comparisons are separated into focused methods, while degradation remains centralized in the tracker; source AST parsing and `git diff --check` pass, target/src/nl_shell/session.py:890 and target/src/nl_shell/session.py:941. |
| T2 Shape | PASS | Independently confirmed the spec reference rcfile equals RCFILE after its header and the security paths include a threat-model update; the frozen scanner also confirms that coverage, target/tests/test_session.py:932 and gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | Frozen suite output records 400 passes, and independent real bash 5.3.9/PTTY sessions exercised healthy output and signal-trap refusal without shims; gate-logs/T3-suite.log:17 and target/src/nl_shell/session.py:685; this sandbox lacks pytest for the full repeat. |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive audit must rerun at publish, gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm the affected-path merged and closed/rejected prior-art check — brief.md:52 reports it for all five paths, but this target has only one synthetic base commit and no frozen remote-history evidence, so that claim cannot be independently settled here. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the implemented protection is fit for confirmed-command use after the EXIT mismatch is resolved, including acceptance of gaps #147–#150 and PS4/MAILCHECK compatibility costs; brief.md:18–22 and target/docs/design/specs/pty-protocol/v1.md:283. |

Independent evidence and limits:

- The disposable target identifies its base as 0771812 and contains the five-file patch; no stale-target condition was observed. The stash was popped successfully and all five modifications restored.
- Direct probe environment: bash 5.3.9, real PTY via installed ptyprocess, actual Linux `/proc` readers and the default TIOCSTI path. Startup was healthy. No replacement service, shim or fake proc tree was used. Full suite results above are attributed to frozen logs, not claimed as independently rerun.
- EXIT discrepancy is a specification/coverage defect, not a demonstrated paste-byte exploit: the documented rationale that EXIT runs only at exit does not authorize dropping the brief’s explicit requirement. The patched direct probe observed healthy output `hello\n` after installing the EXIT trap. Add a case beside the Table A tests requiring `h-changed` and refusal, then rerun.
- No INTEGRATION.md is present in the supplied target; no additional enumerated human-only checklist could be inspected. The affected-path prior-art report is present in the brief, but remote merged/closed/rejected history is outside the frozen bundle.
- No capability-probe symptom guard matching the specified C5 smell-test was identified. Terminal sampling fails closed when its shell-state provenance cannot be established; this is explicitly required by option B, target/src/nl_shell/session.py:916.

<!-- pdca:leaf-complete -->

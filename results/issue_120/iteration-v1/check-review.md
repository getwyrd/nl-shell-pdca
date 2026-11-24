Review #120: continuously drain idle PTY output into a bounded, labelled background buffer without leaking it to the terminal or later command results.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The brief gives observable idle-reading, overflow, isolation and lifecycle criteria, with REPL display deferred; target docs/design/specs/pty-protocol/v1.md:489 and tests/test_session_terminal.py:717 ground the session slice. |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing only session.py reproduced the missing background_waiting API on real bash; the frozen test run also shows the chatty job stalling and four ordinary failures, not collection errors (gate-logs/C4-verify.log:116). |
| C3 Change | PASS | Changes stay within session buffering, regression coverage and the corresponding spec/threat model; independent syntax parsing and git diff --check passed (src/nl_shell/session.py:530; tests/test_session_terminal.py:717). |
| C4 Verification (red→green) | PASS | Restoring the stash independently passed real-PTY idle buffering, exact take/reset, next-command isolation and thread cleanup; frozen pytest evidence shows 24 green versus four red (gate-logs/C4-verify.log:118). |
| C5 Causal adequacy | PASS | Autonomous draining removes the unread-PTY cause of writer stalls, with exclusive reader handover before command execution; no optional-capability probe papers over a load-time cause (src/nl_shell/session.py:856; src/nl_shell/session.py:927). |
| T1 Structure | PASS | One locked tail buffer and explicit wake/join ownership keep idle reading separate from command protocol tracking and terminal rendering (src/nl_shell/session.py:530; src/nl_shell/session.py:844). |
| T2 Shape | PASS | Threat-model changes disclose buffering, deferred UI controls and discarded-output limits; the frozen scanner confirms the required threat-model touch (gate-logs/T2-threat-model.log:11; .oss-scanner/threat_model.md:150). |
| T3 Runtime | PASS | Frozen full-suite evidence reports 1105 passed, one skipped and five forkpty warnings; local pytest is unavailable, so this is log-supported rather than an independent suite rerun (gate-logs/T3-suite.log:27; gate-logs/T3-suite.log:37). |
| T4 Contribution | N/A | Contribution artifacts are absent by design; the substantive audit must rerun at publish (gate-logs/T4-contribution.log:11). |
| T5 Judgment | NEEDS-HUMAN | Decide whether the additional post-read(0) discard interval of up to 50 ms is acceptable scope, since it can lose genuine background bytes beyond the brief's boundary; also confirm affected-path merged and closed/rejected prior art, since this snapshot has only one base commit and no remotes, while the brief records a narrower history search (docs/design/specs/pty-protocol/v1.md:495; brief.md:113). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the session-only delivery and documented loss window for the intended workflow; real-PTY smoke and frozen tests establish buffering, but confirm notices and filtered prompt display remain future work (docs/design/specs/pty-protocol/v1.md:544; src/nl_shell/session.py:806). |

Verification limits: Python 3.14 and ptyprocess were available; pytest was not installed. Instance-root gate wrappers were unavailable here, so their complete frozen logs were inspected. Host-dependent PTY functionality was exercised directly, without a shim or curated topology. The independent buffer check also confirmed the exact 65,536-byte tail, 983,040 dropped-byte count and reset after a 1 MiB input. The disposable target's production stash was restored. No stale-target caveat was needed. No INTEGRATION.md was present in the provided target.

The first local smoke assertion mistakenly treated the repeated command text in bash's Done notice as leaked payload. Repeating the check with an escaped payload distinguished the two and passed; job notices remain legitimate command output as required by the brief.

<!-- pdca:leaf-complete -->

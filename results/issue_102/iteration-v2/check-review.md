Review terminal ownership for running session commands: raw input forwarding, alternate-screen capture exclusion, resizing, restoration, and typed-ahead isolation.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The brief supplies bounded, falsifiable terminal behavior and explicitly identifies the residual race; normative requirements are present at target/docs/design/specs/pty-protocol/v1.md:430. |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing the patch made importing nl_shell.session_terminal fail with ModuleNotFoundError; the frozen gate records all 17 individual pre-fix failures, gate-logs/C4-verify.log:558. |
| C3 Change | PASS | The change stays within session integration, the new terminal component, tests and protocol/security documentation; the existing session loop remains responsible for completion, target/src/nl_shell/session.py:735. |
| C4 Verification (red→green) | PASS | Restored-patch import and real-bash PTY checks passed independently; the readable frozen gate shows 17 green and 17 red tests, gate-logs/C4-verify.log:12 and gate-logs/C4-verify.log:558; pytest is unavailable locally, so the full test transition rests on that captured execution. |
| C5 Causal adequacy | NEEDS-HUMAN | Accept the remaining typed-ahead injection race for v1 or require the acknowledgement back-channel — the quiet-window drain cannot guarantee isolation when control-channel reading lags; target/.oss-scanner/threat_model.md:212. |
| T1 Structure | PASS | Terminal lifecycle and forwarding are isolated behind an injectable descriptor interface, with restoration in the caller's finally block; target/src/nl_shell/session_terminal.py:111 and target/src/nl_shell/session.py:725. |
| T2 Shape | PASS | Security documentation names both typed-ahead leakage and unfiltered terminal escape effects, and prohibits REPL integration without mirror filtering; target/.oss-scanner/threat_model.md:212 and target/.oss-scanner/threat_model.md:228; frozen touch check also passes, gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | Independent real-bash PTY exercise confirmed alternate-screen exclusion, forwarded Ctrl-C status 130, input flag and termios restoration; frozen full-suite output reports 498 passing tests with one forkpty warning, gate-logs/T3-suite.log:24. |
| T4 Contribution | N/A | Contribution artifacts are intentionally absent during Check; the substantive audit runs at publish, gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm decisions 6/7, strict alternate-mode pairing and the added bounded-loss mirror policy match intended scope; copying may drop output under backpressure, target/docs/design/specs/pty-protocol/v1.md:449. Also confirm affected-path merged and closed/rejected prior art: this target exposes only one synthetic base commit and no remotes, so the brief's prior-art claim cannot be independently settled here. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether this session API meets v1 interaction needs despite the acknowledged race and lossy output policy; OSC 52 passthrough was independently observed, so retain the rendering-filter prerequisite before user-facing integration, target/.oss-scanner/threat_model.md:220. |

Independent checks used the supplied target only. Its base and applied patch were readable; no target-state caveat was necessary. `git diff --check` passed. The stash was restored, leaving the original patch present.

The local Python has ptyprocess 0.7.0 and exercised real bash successfully. It has no pytest executable/module, so the full C4/T3 reruns were unavailable; their complete frozen logs were read instead. No unmet real-bash/ptyprocess dependency is inferred from the review sandbox's missing pytest, since the captured gates actually exercised those dependencies.

The original output-backpressure concern is addressed by nonblocking queued writes and bounded settling (target/src/nl_shell/session_terminal.py:263). Frozen tests include full blocking and nonblocking output pipes (target/tests/test_session_terminal.py:460). The previous security-documentation concern is addressed explicitly (target/.oss-scanner/threat_model.md:220). No new capability-probe symptom guard was found.

For final interaction validation after the filter prerequisite is satisfied, run `python3 -m pytest tests/test_session.py tests/test_session_terminal.py` from the repository root in the gate environment. The API remains deliberately unwired to the REPL, so these PTY exercises establish protocol behavior rather than a completed user-facing terminal workflow. No INTEGRATION.md is present in the supplied target; any additional harness-level human-only requirements remain outside the available evidence.

<!-- pdca:leaf-complete -->

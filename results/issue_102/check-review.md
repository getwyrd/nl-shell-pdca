Review terminal ownership during commands: raw input forwarding, alternate-screen capture suppression, resize propagation, and reliable terminal restoration, including the UTF-8 CSI correction.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The draft protocol defines the forwarding window, discard limitation and paired alternate-screen resets explicitly; target/docs/design/specs/pty-protocol/v1.md:428. |
| C2 Reproduction (red pre-fix) | PASS | Frozen executable evidence shows 19 per-test failures without production changes, rather than collection failures; gate-logs/C4-verify.log:622. |
| C3 Change | PASS | Terminal mechanics stay in the new module and reuse the session record loop; the prompt drain precedes E as required; target/src/nl_shell/session.py:261 and target/src/nl_shell/session.py:739. |
| C4 Verification (red→green) | PASS | Captured gate output shows 19 green and 19 red tests with real session fixtures; local repetition is unavailable because python3 lacks pytest, so this verdict rests on the frozen run; gate-logs/C4-verify.log:11 and gate-logs/C4-verify.log:622. |
| C5 Causal adequacy | PASS | UTF-8 continuation context prevents false screen switches, including across read boundaries; independent standard-library checks passed all chunk sizes for UTF-8 and combined mode cases; target/src/nl_shell/session_terminal.py:80 and target/tests/test_session_terminal.py:216. |
| T1 Structure | PASS | One ownership object is cleaned up through finally and forwarding stops when D is processed, preserving the existing sequencing authority; target/src/nl_shell/session.py:720 and target/src/nl_shell/session.py:755. |
| T2 Shape | PASS | Threat-model evidence and source agree on the new security surface, explicitly documenting the three accepted risks and the rendering-filter prerequisite; gate-logs/T2-threat-model.log:11 and target/.oss-scanner/threat_model.md:212. |
| T3 Runtime | PASS | The frozen full-suite output records 500 passes and one forkpty deprecation warning; the host gate exercised the real dependencies, although this review sandbox lacks pytest; gate-logs/T3-suite.log:24. |
| T4 Contribution | N/A | Contribution artifacts are absent by design; the substantive contribution audit runs at publish; gate-logs/T4-contribution.log:11. |
| T5 Judgment | NEEDS-HUMAN | Confirm the affected-path prior-art search covers merged and closed/rejected work — the brief records merged-path history and earlier attempts, but this target contains only one synthetic base commit and no remotes, so closed/rejected coverage cannot be established; brief.md:15. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Confirm decisions 6/7 and strict alternate-screen pairing satisfy the intended interactive experience — automated PTY coverage establishes mechanics, while normative intent remains a human decision; brief.md:20 and target/tests/test_session_terminal.py:174. |

Evidence limits: `python3 -m pytest tests/test_session_terminal.py -q` failed before collection with `No module named pytest`. I therefore did not stash the patch for an inoperative test runner. The instance-root gate wrappers are not supplied here; their captured logs above provide the gate verdicts. The target is readable and contains the patched source. No external dependency is left unexercised by the recorded session tests merely because the review host lacks pytest.

Independent check: importing the standard-library-only terminal module and feeding UTF-8 continuation cases and combined private-mode sequences through `_AltScreen` at every fixed chunk size passed. This supplements, rather than replaces, the frozen real-bash tests.

Prior-art investigation: `git -C target log --all --oneline -- src/nl_shell/session.py src/nl_shell/session_terminal.py tests/test_session_terminal.py` returns only synthetic base commit `5f92619`; `git -C target remote -v` is empty. No INTEGRATION.md is present in the supplied target. The residual drain race, Ctrl-C-at-command-end race and unfiltered mirror were explicitly accepted in brief.md:33–37 and are documented at target/.oss-scanner/threat_model.md:212–234; this review does not reopen those decisions.

<!-- pdca:leaf-complete -->

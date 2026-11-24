Review the model-server chat-completions transport and recoverable, escaped REPL failure replies, without CLI or endpoint-selection changes.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | Request shape, deadline, hostile-output handling and exclusions give falsifiable acceptance criteria; brief.md:3. |
| C2 Reproduction (red pre-fix) | PASS | Independent production-only stash confirmed that the pre-fix tree has neither teacher_client nor BackendError; the frozen run records 79 failing tests, not collection errors; gate-logs/C4-verify.log:15, target/src/nl_shell/backend.py:28. |
| C3 Change | PASS | The four affected files stay within the transport/backend/REPL/test scope and retain the existing strict proposal parser; target/src/nl_shell/repl.py:170, target/src/nl_shell/teacher_client.py:357. |
| C4 Verification (red→green) | PASS | Captured gate output establishes 79 failed pre-fix and 79 passed post-fix; independent stash/import checks agree, but full local repetition was unavailable because pytest is absent and socket creation is denied; gate-logs/C4-verify.log:13, gate-logs/C4-verify.log:1913. |
| C5 Causal adequacy | PASS | The total-deadline worker addresses blocking lookup/read causes directly; oversized integers and unbounded exception text are corrected at their origins, with no capability-probe symptom guard; focused local checks passed; target/src/nl_shell/teacher_client.py:180, target/src/nl_shell/teacher_client.py:130, target/src/nl_shell/teacher_client.py:365. |
| T1 Structure | PASS | Transport concerns remain behind the existing backend interface and raw answers still enter the shared parser; target/src/nl_shell/backend.py:22, target/src/nl_shell/repl.py:164. |
| T2 Shape | NEEDS-HUMAN | Decide whether the new network/error trust boundary requires a threat-model update despite the documentation exclusion — the scanner explicitly leaves this security decision to sign-off; gate-logs/T2-threat-model.log:10, target/src/nl_shell/teacher_client.py:413. |
| T3 Runtime | PASS | The frozen whole-suite log shows 560 passed with one forkpty deprecation warning; this host cannot independently repeat pytest/network execution, so this verdict rests on that captured run; gate-logs/T3-suite.log:26. |
| T4 Contribution | N/A | Contribution artifacts are drafted after Check; the substantive audit is deferred to the mandatory publish rerun; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art across merged history and closed/rejected work — local git history is only one synthetic base commit and returns no path history, so the brief's earlier-attempt account cannot independently establish that coverage; brief.md:20. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the demonstrated transport contract and interim failure replies meet the intended child-1 use — fake-server coverage establishes protocol behavior while real-model/CLI integration belongs to later work; brief.md:12, target/src/nl_shell/repl.py:39. |

Independent evidence: production-only `git stash push -u` followed by imports confirmed both new API surfaces absent; `git stash pop` restored the original patch. Restored-code checks passed for `timeout_s=10**400` and `10**5000` becoming BackendError, acceptance of `1e10`, schema object identity, omitted model, and bounded one-line excerpts. No production edits were made.

Local execution limits: `python3 -m pytest tests/test_teacher_client.py` reports `No module named pytest`; a stdlib live HTTP smoke attempt fails at socket creation with `PermissionError: [Errno 1] Operation not permitted`. These are host caveats, not patch defects. The frozen C4 and T3 logs contain actual successful executions, including prompt-loading tests; PyYAML 6.0.3 is also available here, so the brief's named external dependency is discharged. Instance-scoped gate wrappers are unavailable here; their captured outputs were read. No INTEGRATION.md is supplied in the target snapshot.

No implementation defect was established by this review. Human decisions above remain advisory.

<!-- pdca:leaf-complete -->

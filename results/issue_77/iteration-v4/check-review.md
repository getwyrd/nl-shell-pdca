Review issue #77: add an OpenAI-compatible teacher client, explicit session opt-in for TCP endpoints, and safe REPL integration with a total request deadline.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The binding transport, endpoint isolation, error filtering, and integration criteria are explicit and falsifiable; prerequisite #143 and deferred behavior are declared (brief.md:19–35, brief.md:87–99). |
| C2 Reproduction (red pre-fix) | FAIL | No feature tests or red execution are supplied: patch.diff is zero bytes and the verification gate stopped before running tests (gate-logs/C4-verify.log:10). |
| C3 Change | FAIL | The supplied patch.diff is empty, so there is no implementation or test change to assess against the requested feature (brief.md:32). |
| C4 Verification (red→green) | FAIL | No red→green evidence exists because the bundle lacks a patch; this is an artifact omission, not a compile failure attributed to the stale target (gate-logs/C4-verify.log:7–10). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Supply the implementation and discriminating tests before causal adequacy can be assessed—the empty patch cannot demonstrate restoration of the three invariants (brief.md:31). |
| T1 Structure | N/A | No changed files exist in patch.diff, so there is no new structure to assess. |
| T2 Shape | N/A | The threat-model scanner explicitly skipped substantive inspection because no patch was available; its green exit is not evidence of security coverage (gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen evidence records 330 existing tests passing in 47.31 seconds; this establishes only that recorded suite result, not feature coverage, and an independent attempt found python3 lacks pytest (gate-logs/T3-suite.log:16). |
| T4 Contribution | NEEDS-HUMAN | Confirm the actual contribution artifacts meet the opener and issue-reference rules—the log shows exit zero but no inspected content or substantive findings, and neither artifact is supplied (gate-logs/T4-contribution.log:7–9). |
| T5 Judgment | NEEDS-HUMAN | Confirm closed/rejected prior art by the affected file paths before accepting novelty—local history was checked, but the supplied evidence does not independently establish the brief's closed-PR claim (brief.md:37); also ratify the blocking-request and recovery deferrals (brief.md:91–98). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the eventual real teacher interaction and bounded synchronous wait meet M0 needs; no implementation can be exercised here, prerequisite #143 is absent from this target, and the required PyYAML-dependent CLI path has not been demonstrated for #77 (brief.md:26–34, brief.md:91–98). |

Evidence and limitations:

- Independently confirmed patch.diff is zero bytes and the target has a clean worktree. There is nothing to stash or restore, so no target mutation was performed.
- Target-state caveat: `$PDCA_TARGET` is readable but lacks tracked `src/nl_shell/backend.py`, `src/nl_shell/proposal.py`, and `tests/test_teacher_client.py`. Its CLI constructs `Repl.interactive(status_lines=status_lines)` at `src/nl_shell/cli.py:64`; its REPL still returns the placeholder at `src/nl_shell/repl.py:25`. This target predates prerequisite #143. Those absences are not asserted as defects in an unseen patch. C2–C4 concern the independently confirmed missing submission/evidence.
- Attempted `python3 -m pytest -q -p no:cacheprovider "$PDCA_TARGET/tests/test_teacher_client.py"`; the interpreter reported `No module named pytest`. No target-local `.venv/bin/python` exists. Read all four frozen gate logs instead; instance-scoped wrappers were not sought in other checkouts. The host limitation is not a patch defect.
- Re-ran affected-path history with `git -C "$PDCA_TARGET" log --all --oneline -- src/nl_shell/teacher_client.py tests/test_teacher_client.py src/nl_shell/cli.py src/nl_shell/repl.py src/nl_shell/config.py`. It returned only `4c755f2`, `89373a4`, `dc784f0`, and `305d8a4`, with no teacher-client history. Closed/rejected remote work is not established by those local refs. No INTEGRATION.md was found in the target's file listing.
- No capability probe or runtime guard can be evaluated because the patch is empty. PyYAML availability and the new CLI path are not established by the old suite result; no shim or curated substitute was used.
- After implementation on the folded #143 base, run `python3 -m pytest tests/test_teacher_client.py` with pytest and PyYAML installed. For manual teacher validation, start the supported teacher on a loopback port, run `nl-shell --dev-teacher http://127.0.0.1:<port>`, submit a natural-language request, and check the framed proposal and `:status` endpoint/backend. Repeat with `teacher_url` configured but no flag: expect refusal on stderr and only the Unix-socket path. Confirm the synchronous wait and deferred recovery scope at sign-off; these checks cannot currently run against this submission.

<!-- pdca:leaf-complete -->

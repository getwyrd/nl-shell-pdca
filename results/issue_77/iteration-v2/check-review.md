Review issue #77: add an OpenAI-compatible teacher client with explicit session opt-in for TCP endpoints, strict response rejection, and local-socket defaults.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The binding criterion names observable endpoint-safety, transport, rejection, and REPL outcomes, with an explicit dependency wave and bounded scope (brief.md:18–27). |
| C2 Reproduction (red pre-fix) | FAIL | No feature tests or executed pre-fix failures were submitted; the asserted falsifiability is a plan rather than reproduced evidence (brief.md:19; gate-logs/C4-verify.log:10). |
| C3 Change | FAIL | The submitted patch.diff is zero bytes, so no implementation or test contribution fulfills the requested feature (patch.diff, empty; brief.md:18). |
| C4 Verification (red→green) | FAIL | The bundle supplies no patch for a red→green comparison; the gate explicitly reports unverifiable rather than verified, independently of the local pytest limitation (gate-logs/C4-verify.log:7–10). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Supply the implementation and discriminating tests — the repeated empty submission establishes none of the endpoint-safety or rejection guarantees (brief.md:18; brief.md:83–85; gate-logs/C4-verify.log:10). |
| T1 Structure | N/A | No submitted code exists whose structural fit can be assessed (patch.diff, empty). |
| T2 Shape | N/A | The threat-model scanner explicitly checked nothing because the patch is absent; its exit zero does not establish security coverage for the planned feature (gate-logs/T2-threat-model.log:10; brief.md:10–13). |
| T3 Runtime | PASS | Frozen evidence records 330 existing tests passing; this establishes baseline suite health only, with no teacher-client tests or independent rerun available here (gate-logs/T3-suite.log:10–17). |
| T4 Contribution | NEEDS-HUMAN | Confirm the actual contribution artifacts satisfy the user-impact opener and tracker requirements — the frozen log records exit zero but no check output or artifact content to inspect (gate-logs/T4-contribution.log:7–9). |
| T5 Judgment | NEEDS-HUMAN | Resolve the loopback opt-in interpretation, deferred server startup, and model-name scope, and confirm closed/rejected prior art by affected file — these acceptance choices and historical coverage are not settled by the supplied evidence (brief.md:29; brief.md:65–72). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the eventual implementation meets the intended teacher workflow after feature verification exists — no submitted client can currently be exercised, and the real teacher check remains manual (brief.md:18–19; gate-logs/C4-verify.log:10). |

Evidence and limits:

- Independently measured `patch.diff`: 0 bytes. There is no fix to stash or restore, so no target mutation was warranted. The clean target's CLI parses arguments without a dev-teacher option (`src/nl_shell/cli.py:26–33`); this is grounding context, not a defect attributed to potentially missing prerequisite commits.
- Attempted `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_teacher_client.py` in `$PDCA_TARGET`: `/usr/bin/python3: No module named pytest`, plus stream-fd permission errors. This is a host caveat, not a failing feature test. The frozen suite log supplies the actual executed suite result; C4 fails the evidence requirement because the submitted patch is empty, not because of this host limitation.
- Read every supplied gate log. Instance-root gate wrappers were not assumed runnable from the target. T4's exit status alone cannot independently substantiate its artifact-content requirements. No row is marked deferred.
- Prior-art investigation was confined to `$PDCA_TARGET`: local history for `src/nl_shell/cli.py`, `src/nl_shell/repl.py`, and `tests/test_teacher_client.py` showed existing scaffold/router/input-mode/config work; history for `src/nl_shell/teacher_client.py` and `tests/test_teacher_client.py` returned no entries. The brief's merged-history search covers `src/nl_shell` broadly, but its closed-unmerged assertion supplies no affected-file query evidence (brief.md:29). No supplied INTEGRATION.md was found in the target, so additional enumerated human-only requirements could not be checked.
- Once an implementation is supplied, first run the binding fake-server suite. For the expressly manual real-teacher check, start an OpenAI-compatible server, launch `nl-shell --dev-teacher http://<teacher-host>:<port>`, inspect `:status`, and submit a natural-language request; expect the selected endpoint/backend and a valid proposal, with the SSH/TLS warning for non-loopback HTTP. Repeat without the flag using `teacher_url` in config and confirm refusal of that URL and use of the local socket. These are future acceptance steps, not observed outcomes of this empty submission.

<!-- pdca:leaf-complete -->

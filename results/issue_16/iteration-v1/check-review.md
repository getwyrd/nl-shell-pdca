Review issue #16: editable YAML prompts, a recording model stub, strict proposal parsing, and exact last-request `:context` output without command execution.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The bounded stub-only scope has explicit acceptance vectors and excludes execution and HTTP transport; proposal rejection is required by target/docs/design/specs/proposal/v1.md:62 and brief.md:18. |
| C2 Reproduction (red pre-fix) | PASS | Independent stash/run confirms the backend is absent before the change (review-red.log:1); frozen tests additionally record 82 failures, 93 passes and 12 setup errors, with no collection errors (gate-logs/C4-verify.log:3304). |
| C3 Change | PASS | The patch addresses the specified request-to-proposal flow and preserves the no-backend default; target/src/nl_shell/repl.py:140 and target/src/nl_shell/cli.py:46 ground the integration. |
| C4 Verification (red→green) | PASS | Independent smoke changes from missing-backend failure to successful recording, proposal and exact context after stash/pop (review-green.log:1); frozen focused suite shows 187 passes (gate-logs/C4-verify.log:14), subject to the additional defects below. |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Close the reproduced rejection/error-boundary gaps before treating malformed inputs as handled: large JSON integers and unpaired surrogates terminate the REPL, while sequence YAML keys escape startup error handling (target/src/nl_shell/proposal.py:112, target/src/nl_shell/proposal.py:138, target/src/nl_shell/prompts.py:86; review-probes.log:1). |
| T1 Structure | PASS | Immutable messages shared by backend and context avoid divergent representations, with loading, parsing and rendering separated; target/src/nl_shell/backend.py:30 and target/src/nl_shell/repl.py:147. |
| T2 Shape | PASS | Threat-model documentation describes the implemented stub exercise, satisfying the touch gate; target/.oss-scanner/threat_model.md:175 and gate-logs/T2-threat-model.log:10; diff whitespace check passes. |
| T3 Runtime | PASS | Frozen full-suite evidence records 311 passes (gate-logs/T3-suite.log:16); independent real-PyYAML smoke passes, but pytest is unavailable locally and the additional malformed-input probes expose uncovered cases. |
| T4 Contribution | N/A | Contribution artifacts are intentionally absent at Check; the substantive contribution audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-file prior art across merged and closed/rejected work: the supplied target has one synthetic base commit and no remotes, and the brief's directory-level claim does not establish that complete audit (brief.md:30); this matters before introducing reusable backend/parser interfaces. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether stub-only transparency and the accepted M0 installed-package/default-prompts limitation meet this milestone's needs; real HTTP/model behavior remains explicitly outside scope (brief.md:25; target/src/nl_shell/repl.py:100). |

Evidence and limitations:

- The target is the supplied self-contained patched checkout; citations above ground on its current files. Stash/pop restored the supplied patch, without implementation edits. `review-smoke.py` exercises `@show disk usage`, proposal display, recorded input and independently serialized context. Its pre-fix failure is an import failure, not a substitute for the frozen pytest red leg.
- Both available Python interpreters lack pytest. Therefore the C4/T3 suite verdicts rely on the frozen logs, whose complete contents were read; they are not claims of independent full-suite reproduction. System Python has real PyYAML 6.0.3, exercised by the smoke and malformed-YAML probe. The declared PyYAML dependency is satisfied; the stub is the specified product under test, not a substitute for an unmet model dependency.
- The instance-scoped T2 wrapper is unavailable here; its frozen log confirms the limited threat-model-touch check, and the actual documentation diff was inspected. No INTEGRATION.md is present in the supplied target or input bundle, so no additional project-specific human-only list could be consulted.

Builder-fixable findings (all independently reproduced on the patched source):

1. **Malformed model output can terminate the request loop.** `proposal.parse('{"kind":' + '9' * 5000 + '}')` raises `ValueError` at target/src/nl_shell/proposal.py:112 rather than returning `Rejected`. Sending that same response through `RecordingStub` and `Repl.run()` propagates the exception. Handle JSON decoder resource/number conversion rejection and add a regression asserting the normal unusable-proposal reply and continued loop operation. Evidence: review-probes.log:1.
2. **An unpaired surrogate reaches terminal encoding.** The response `{"kind":"command","command":"\ud800","risk":"read-only"}` is accepted at target/src/nl_shell/proposal.py:138; through the REPL with a strict UTF-8 output stream it raises `UnicodeEncodeError`. Reject non-encodable surrogate command text before display and test the real encoded-output boundary. Evidence: review-probes.log:2; target/src/nl_shell/repl.py:121.
3. **Malformed YAML mapping keys bypass the promised diagnostic.** A user file containing `? [system]\n: value\n` raises `TypeError` at target/src/nl_shell/prompts.py:86. That exception is outside both `_read_layer`'s YAML-error catch and the CLI's configuration-error catch (target/src/nl_shell/cli.py:56), so startup produces a traceback instead of its controlled path-qualified error. Preserve SafeLoader's invalid-key handling or translate this failure to `PromptsError`, and add a CLI regression. Evidence: review-probes.log:3; input retained as review-invalid-prompts.yaml.

No capability-probe/load-time symptom guard was introduced: the explicit absent-backend and absent-prompts branches implement the brief's supported configurations.

<!-- pdca:leaf-complete -->

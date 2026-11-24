Review the new persistent Bash PTY session, fd-3 protocol, state snapshots, command framing, and degraded-mode behavior for issue #101.

Source citations below are relative to `$PDCA_TARGET` (`target/`); evidence citations are relative to this review directory.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The brief defines observable session behavior, explicit exclusions, and conformance vectors; the target spec supplies sequencing and command-byte requirements (`docs/design/specs/pty-protocol/v1.md:144`, `brief.md:3`). |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing production changes makes the session import fail; frozen pytest evidence additionally shows all 55 tests failing individually without production changes (`gate-logs/C4-verify.log:14`). |
| C3 Change | PASS | The patch stays within the session, parser, dependency, tests, and authorized protocol/threat-model documentation surfaces; REPL and CLI are untouched (`src/nl_shell/session.py:1`, `src/nl_shell/pty_protocol.py:1`, `brief.md:9`). |
| C4 Verification (red→green) | PASS | Frozen evidence establishes 55/55 red→green; restored-target direct probes independently pass persistent cwd, pipeline status, and output checks; pytest itself is unavailable in this reviewer sandbox (`gate-logs/C4-verify.log:10`, `tests/test_session.py:101`). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Preserve truthful output capture when Readline settings change: disabling bracketed paste makes a subsequent successful `printf hello` return empty output with a healthy session; the capture path silently discards bytes unless it sees the Readline marker (`src/nl_shell/session.py:189`, `src/nl_shell/session.py:107`). |
| T1 Structure | PASS | Pure protocol parsing/state transitions are separated from PTY lifecycle and I/O; the change introduces no REPL or terminal-ownership coupling (`src/nl_shell/pty_protocol.py:156`, `src/nl_shell/session.py:211`). |
| T2 Shape | PASS | Independently checked the touched paths and threat-model additions; the frozen scanner confirms the required security-document update, without claiming a broader security audit (`.oss-scanner/threat_model.md:168`, `gate-logs/T2-threat-model.log:10`). |
| T3 Runtime | PASS | The frozen full-suite run reports 232 passing tests; independent real-Bash probes corroborate core execution, while the additional uncovered output case is recorded in C5 (`gate-logs/T3-suite.log:16`, `src/nl_shell/session.py:361`). |
| T4 Contribution | N/A | Contribution artifacts are deliberately not drafted at Check; the substantive audit must rerun at publish (`gate-logs/T4-contribution.log:10`). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art across merged history and closed/rejected work: the brief reports a broad src/dependency search, but this one-commit target has no remote/history evidence to verify all affected documentation/test paths or rejected attempts (`brief.md:14`). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the documented one-second fail-closed limit for Bash builtins and intentional hook-subversion boundary, and confirm the policy-gate wording change is appropriate within draft v1; passing conformance tests cannot settle those product/scope decisions (`.oss-scanner/threat_model.md:168`, `docs/design/specs/policy-gate/v1.md:192`, `brief.md:17`). |

Independent verification and limitations:

- Bash is the real host 5.3.9; `ptyprocess` is 0.7.0. Direct sessions exercised `true`, `false | true`, `printf hello`, persistent `cd /tmp` followed by `pwd`, multiline commands, and 100,000 output bytes. After stashing production changes, import failed with `ModuleNotFoundError`; after restoring them, pipeline and output assertions passed. The target's original patch state was restored.
- `python3` cannot import pytest. Consequently the complete 55-test red→green and 232-test suite results are adjudicated from the captured logs, not claimed as independent pytest reruns. The runtime dependencies were exercised directly; there is no unmet real-Bash/ptyprocess dependency. Instance-scoped gate wrappers were not available here. All four supplied gate logs were inspected; none is missing.
- `git diff --check` passed. The threat-model touch requirement was independently checked against the patch and target. No `INTEGRATION.md` is present in the supplied target, so no additional enumerated human-only criteria could be extracted. No other checkout was consulted.
- The capability-probe smell test found no new optional-capability/load-time fallback requiring a contested-root-cause verdict. C5 instead records an observed implementation defect.

C5 reproduction, using the restored target and a temporary HOME under this review directory:

```python
from nl_shell.session import Session

with Session.start(timeout=5) as session:
    assert session.run('printf hello', timeout=5).output == b'hello'
    session.run("bind 'set enable-bracketed-paste off'", timeout=5)
    result = session.run('printf hello', timeout=5)
    print(result.output, result.status, result.ran, session.degraded)
    # Observed: b'' 0 True False
```

`echo one\necho two` also returned empty captured output after that setting change. This needs a regression test and a correction that preserves the output contract or detects loss of its prerequisite before reporting a healthy result. The existing bracketed-paste test only covers a startup `.bashrc` setting (`tests/test_session.py:484`); startup enforcement (`src/nl_shell/session.py:76`) does not protect later commands. The runtime Readline setting is absent from the hook snapshot (`src/nl_shell/session.py:107`).

<!-- pdca:leaf-complete -->

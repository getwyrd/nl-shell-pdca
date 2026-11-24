# Result — issue 77 / teacher-client-dev-teacher-flag

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: nl-shell can send its model input to an OpenAI-compatible chat endpoint (llama.cpp `llama-server` or vLLM, no API key) and get a `proposal/v1` answer back, with constrained decoding. By default it talks only to the local model socket. Any other endpoint URL is used only when the user passes `--dev-teacher` for that session; a URL in `config.toml` alone is refused with a message. A non-loopback plain-HTTP URL gets a warning to use an SSH tunnel or TLS, since the state block goes out in clear.
- Success criterion: `python3 -m pytest tests/test_teacher_client.py` passes, against a fake OpenAI-compatible HTTP server started by the test on `127.0.0.1` (port 0) and on a Unix socket in `tmp_path`, covering: (a) a valid response carrying a `proposal/v1` object in `choices[0].message.content` → the parsed proposal; the request the fake server received is `POST /v1/chat/completions` with the model input's messages, a JSON-schema `response_format` whose schema is the `proposal/v1` schema (the same object #16's parser uses), and no `Authorization` header; with `teacher_model = "m1"` in `config.toml` the request body has `"model": "m1"`, and without it the body has no `model` key. (b) rejected, never repaired, each with a reason and no retry: an HTTP error status; a 3xx redirect (not followed — the fake server sees one request and nothing goes to the redirect target); a body that isn't JSON; JSON without `choices[0].message.content`; content that fails `proposal/v1` — each `proposal/v1` §Conformance reject case delivered as `message.content`: extra property, missing `risk`, `command` with `reason`, `command` over 2000 code points, invalid JSON, a JSON array (the "risk lower than the gate's class" case needs the policy gate, #12, which is not a dependency here; #12 adds it); a body over the size cap (the client stops reading past the cap); a server that doesn't answer within the timeout (the test builds the client with a 0.5 s read timeout and the fake server sleeps 2 s; the test finishes in under 2 s); an `https://127.0.0.1:<port>` URL pointed at the plain-HTTP fake server → rejected with a TLS error as the reason, and no plain-HTTP request is sent instead (certificate and protocol checks are on; no fallback). (c) endpoint rules: no flag and no config URL → the default endpoint `$XDG_RUNTIME_DIR/nl-shell/model.sock` is used (a fake server on that path answers); `teacher_url` in `config.toml` without `--dev-teacher` → refused with a message, and the fake server at that URL receives nothing; the same URL with `--dev-teacher` → used; `--dev-teacher <URL>` on the command line → used; a non-loopback `http://` URL with the flag → the warning (checked on the endpoint decision, without connecting anywhere off the host). (d) through `Repl` with the client pointed at the fake server: a natural-language line shows the fake server's proposal; when the default socket is absent, the reply says the model server isn't running, and nothing crashes. (e) `:status` shows the endpoint in use and the backend kind. (f) no TCP on the default path: with `socket.socket.connect` and `socket.create_connection` patched to record their calls, `cli.main([])` (with a matching os-release injected as #92's tests do, and a scripted stdin) with `teacher_url` in `config.toml` and no flag, followed by one natural-language line, makes no `AF_INET` / `AF_INET6` connection at all (only the `AF_UNIX` attempt to the default socket).
- Repo + branch target: eduralph/nl-shell @ main (built in a later wave than #14, #16 and #92: per `Depends on` the driver folds their accepted patches into the wave's integration branch and verifies against it via `$PDCA_VERIFY_BASE`, so #16's backend interface, parser and schema, #92's `config.toml` unit and #14's `:status` exist when this bundle builds; if any is not accepted, this bundle is not scheduled. Use their names as they landed; do not invent stand-ins.)
- Scope (one logical fix) / out of scope: (1) A backend for #16's interface that speaks the OpenAI chat-completions API over HTTP, both to a TCP URL (`http://`, `https://`) and to the local Unix socket (ADR-0018 §1); the request carries the model input's messages and a JSON-schema `response_format` built from the single `proposal/v1` schema #16 keeps (ADR-0018 §2); an optional model name from `config.toml` (`teacher_model`, sent only if set — vLLM needs it, llama-server ignores it). (2) Strict response handling (ADR-0018 §3): non-2xx, redirects, oversize bodies, invalid JSON, a missing content field, and content failing `proposal/v1` are rejected; no retry, no repair; connect and read timeouts as named module constants (`CONNECT_TIMEOUT_S = 5`, `READ_TIMEOUT_S = 120` — a CPU-only teacher can be slow) that the client's constructor accepts as overrides, so tests pass short values. (3) Endpoint selection (ADR-0020 §3): default is `$XDG_RUNTIME_DIR/nl-shell/model.sock`; `--dev-teacher [URL]` in `cli.py` enables a non-default endpoint for this session, taking the URL from the flag or else from `teacher_url` in `config.toml`; `teacher_url` without the flag is refused with a message and the default is used; a non-loopback `http://` host gets the SSH-tunnel / TLS warning. (4) The interactive REPL uses this backend instead of #16's "no backend configured" reply; an unreachable default socket gives a plain "the model server isn't running" reply per request. (5) `:status`: endpoint and backend lines (ADR-0020 §4). / out of scope: starting or installing `llama-server` / the systemd user service (#48); the student model (#42); the reader's request (#61); API keys or any credential (the teacher has none; ADR-0006/0015 forbid sending credentials to a model server); retries, streaming; the rendering of the proposal (#16 owns it); any change to `proposal/v1`; the architecture doc 05 table (one docs pass after the batch).

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): unverifiable — bundle has no patch.diff
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — no patch.diff, nothing to check
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: pass — ./scripts/pdca contribcheck
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review issue #77: add an OpenAI-compatible teacher client with constrained proposal decoding, explicit endpoint opt-in, REPL integration, and endpoint status.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The brief supplies observable endpoint-safety and response-rejection criteria, a fake-server oracle, and explicit scope boundaries (brief.md:17–27). |
| C2 Reproduction (red pre-fix) | FAIL | No executed pre-fix feature failure is supplied: the verification gate stopped before testing because the bundle contained no patch (gate-logs/C4-verify.log:10). |
| C3 Change | FAIL | The supplied patch.diff is zero bytes; there is no submitted implementation or test change to assess against the requested feature (brief.md:18; gate-logs/C4-verify.log:10). |
| C4 Verification (red→green) | FAIL | Neither red nor green feature evidence exists: C4 exited 77 for the absent patch, independently confirmed as an empty input; this is a submission-evidence failure, not a compilation defect attributed to the target (gate-logs/C4-verify.log:7–10). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Supply the implementation and discriminating tests before causal adequacy can be judged — an empty submission cannot establish the endpoint-safety or rejection guarantees (brief.md:18; gate-logs/C4-verify.log:10). |
| T1 Structure | N/A | There is no submitted code structure or dependency change to review; patch.diff is empty (gate-logs/C4-verify.log:10). |
| T2 Shape | N/A | No security-relevant diff exists to audit; the scanner explicitly skipped substantive checking, so its pass is not evidence of threat-model coverage (gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen evidence records 330 existing tests passing; this supports baseline runtime health only, with no feature coverage asserted (gate-logs/T3-suite.log:10–17). |
| T4 Contribution | NEEDS-HUMAN | Confirm the actual contribution artifacts meet the opener and tracker requirements — the log records exit zero but contains no captured check output or artifact content to inspect (gate-logs/T4-contribution.log:7–9). |
| T5 Judgment | NEEDS-HUMAN | Confirm the loopback opt-in rule, service-start deferral, and optional model-name scope; also refresh closed/rejected prior art by affected path, since available local history cannot establish that remote work was checked (brief.md:29,65–72). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide fitness only after a substantive bundle and executable feature evidence are available; then confirm the intentionally manual real-teacher behavior and the project's human-only requirements (brief.md:19,63–72). |

Evidence and limitations:

- Independently checked the supplied patch: `wc -c patch.diff` returned `0`. There is nothing to stash or restore, so no target mutation was performed.
- Read all four frozen logs. C4 explicitly reports missing patch evidence; T2 explicitly reports nothing to check. T3 reports 330 passing tests. T4 records a successful process exit with no substantive output. No row is marked deferred.
- Attempted an independent feature-test collection using `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider --collect-only -q "$PDCA_TARGET/tests/test_teacher_client.py"`; the available interpreter reported `/usr/bin/python3: No module named pytest`. This is a reviewer-host limitation, not a patch defect. Runtime adjudication above therefore rests on the frozen suite log, not an independent suite rerun. The instance-root gate wrappers are outside the permitted grounding scope and were not sought in other checkouts.
- Target-state caveat: `$PDCA_TARGET` is clean at `0771812`, but its REPL still contains the pre-backend placeholder (`src/nl_shell/repl.py:25–28,74–78`), rather than the #16 interface required by the brief. The CLI parser is at `src/nl_shell/cli.py:26–33`. The teacher test file is absent. These observations do not establish a patch regression or an ordering blocker; this target does not supply the promised folded prerequisite base, and the empty diff offers no alternate implementation grounding.
- Prior-art investigation: local `git log --all -- src/nl_shell/teacher_client.py tests/test_teacher_client.py` returned no entries; history for `src/nl_shell/cli.py`, `src/nl_shell/repl.py`, and `src/nl_shell/config.py` contains scaffold, routing, input-mode, and target-selection work. The brief's broad historical claim does not independently confirm closed/rejected work by those affected paths. No external service was contacted.
- No `INTEGRATION.md` was found within the target, so its enumerated human-only items could not be independently read. No capability-probe smell-test can be applied to an empty diff.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 77 (teacher-client-dev-teacher-flag)

There is no fix to refute. `patch.diff` is 0 bytes, so this round shipped no code and no test. The "overall: pass" in `check-gates.json` should not be read as acceptance.

- NEEDS-HUMAN [human] — **Empty patch; the gated proof never ran.** `gate-logs/C4-verify.log` shows exit 77, `PDCA-UNVERIFIABLE: bundle has no patch.diff`. No red→green was shown. `tests/test_teacher_client.py` does not exist at `$PDCA_TARGET`, and nothing in `src/` mentions a teacher, an HTTP client or `--dev-teacher`. The argument parser at `src/nl_shell/cli.py:26-33` still only has `--version` and `--target`, so `cli.main(["--dev-teacher", …])` would still exit 2. None of the success-criterion items (a)–(f) is met.

- NEEDS-HUMAN [human] — **The claim `"overall": "pass"` in `check-gates.json` is not earned.** It comes from gates that pass when there is nothing to check. T2 passes with `no patch.diff, nothing to check` (`gate-logs/T2-threat-model.log`), even though the brief touches threat-model items 5, 8 and 11. T3 passes because the old suite (330 tests) still passes on an unchanged worktree (`gate-logs/T3-suite.log`). The one gate that matters, C4, is `unverifiable`, not pass. A human should not sign off on this round as if it delivered the feature.

- NEEDS-HUMAN [human] — **The dependency this bundle needs may be missing from the base, which would explain the empty patch.** The brief says it builds on #16's backend interface, the `proposal/v1` parser/schema and the "no backend configured" reply, and that "if any is not accepted, this bundle is not scheduled." At `$PDCA_TARGET` (HEAD `0771812 pdca-integrate: issue_140`) none of #16's work exists. `src/nl_shell/repl.py:27` still says "the model backend arrives in M0.8". `src/nl_shell/input_modes.py:102` still has the placeholder reply "command proposals arrive in M0.8". There is no schema file and no backend class anywhere under `src/nl_shell/`. #92 (`config.py`, `targets.py`) and the `:status` hook (`src/nl_shell/input_modes.py:77-87`) are present. Either the wave was scheduled before #16 was accepted, or #16 was not folded into the integration branch. The human needs to fix the scheduling and order. Iterating on Do won't help: the brief tells the builder not to invent stand-ins for #16's names.

I tried to refute the evidence, the fix and the verdict. There was no evidence or fix to attack. The only real finding is that the round's "pass" is empty and the base is missing a prerequisite.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory) — issue 77 / teacher-client-dev-teacher-flag

Attacker-reachable inputs this diff touches: **none — there is no diff.** The bundle has no `patch.diff`, so nothing was reviewed.

## What I checked

- The scratch directory has `brief.md`, `check-gates.json` and `gate-logs/`, but no `patch.diff`.
- `gate-logs/C4-verify.log` ends with `PDCA-UNVERIFIABLE: bundle has no patch.diff` (exit 77). `gate-logs/T2-threat-model.log` passed only because there was nothing to check (`no patch.diff, nothing to check`). The T3 pass (330 tests) ran on an unchanged tree, so it says nothing about this issue.
- The target worktree at `$PDCA_TARGET` is clean (`git status` is empty; HEAD is `0771812 pdca-integrate: issue_140`). It has no teacher client, no `--dev-teacher` flag and no `tests/test_teacher_client.py`. `src/nl_shell/repl.py:27` still prints the placeholder "the model backend arrives in M0.8."
- The base also has none of #16's work (no backend interface, no `proposal/v1` parser or schema under `src/nl_shell`). The brief says this bundle builds on #16 and "if any is not accepted, this bundle is not scheduled." That missing dependency is the likely reason no patch exists.
- I read `.oss-scanner/threat_model.md`, which exists. The inputs this issue would affect are item 8 (the local model socket), item 11 (the dev teacher endpoint), item 5 (model output), and the must-hold rule "no outbound connection in the default config." With no code, none of them is touched, so there are no findings and no severity ratings.

## Findings

- NEEDS-HUMAN [human] — `gate-logs/C4-verify.log` (no `path:line`, because no code changed): the bundle reached Check with no `patch.diff`, so there was nothing to security-review. The wave base at `$PDCA_TARGET` (HEAD `0771812`) lacks #16's backend interface and `proposal/v1` schema, which the brief lists as a hard dependency. A human needs to decide whether to reschedule #77 after #16 lands, or find out why Do produced no patch. Treat this round's "pass" on T2 and T3 as meaningless for #77. When a real patch exists, it needs a fresh security pass. Focus on: redirects not followed, the body size cap actually stopping the read, no TLS fallback, no TCP connection without `--dev-teacher`, no `Authorization` header or credential sent, and model `content` treated as untrusted (threat model items 5, 8, 11).

No security findings against code: there is no code change to assess.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C5 Causal adequacy — Supply the implementation and discriminating tests before causal adequacy can be judged — an empty submission cannot establish the endpoint-safety or rejection guarantees (brief.md:18; gate-logs/C4-verify.log:10).
- [ ] T4 Contribution — Confirm the actual contribution artifacts meet the opener and tracker requirements — the log records exit zero but contains no captured check output or artifact content to inspect (gate-logs/T4-contribution.log:7–9).
- [ ] T5 Judgment — Confirm the loopback opt-in rule, service-start deferral, and optional model-name scope; also refresh closed/rejected prior art by affected path, since available local history cannot establish that remote work was checked (brief.md:29,65–72).
- [ ] Validation — fitness-to-purpose — Decide fitness only after a substantive bundle and executable feature evidence are available; then confirm the intentionally manual real-teacher behavior and the project's human-only requirements (brief.md:19,63–72).
- [ ] **Empty patch; the gated proof never ran.** `gate-logs/C4-verify.log` shows exit 77, `PDCA-UNVERIFIABLE: bundle has no patch.diff`. No red→green was shown. `tests/test_teacher_client.py` does not exist at `$PDCA_TARGET`, and nothing in `src/` mentions a teacher, an HTTP client or `--dev-teacher`. The argument parser at `src/nl_shell/cli.py:26-33` still only has `--version` and `--target`, so `cli.main(["--dev-teacher", …])` would still exit 2. None of the success-criterion items (a)–(f) is met.
- [ ] **The claim `"overall": "pass"` in `check-gates.json` is not earned.** It comes from gates that pass when there is nothing to check. T2 passes with `no patch.diff, nothing to check` (`gate-logs/T2-threat-model.log`), even though the brief touches threat-model items 5, 8 and 11. T3 passes because the old suite (330 tests) still passes on an unchanged worktree (`gate-logs/T3-suite.log`). The one gate that matters, C4, is `unverifiable`, not pass. A human should not sign off on this round as if it delivered the feature.
- [ ] **The dependency this bundle needs may be missing from the base, which would explain the empty patch.** The brief says it builds on #16's backend interface, the `proposal/v1` parser/schema and the "no backend configured" reply, and that "if any is not accepted, this bundle is not scheduled." At `$PDCA_TARGET` (HEAD `0771812 pdca-integrate: issue_140`) none of #16's work exists. `src/nl_shell/repl.py:27` still says "the model backend arrives in M0.8". `src/nl_shell/input_modes.py:102` still has the placeholder reply "command proposals arrive in M0.8". There is no schema file and no backend class anywhere under `src/nl_shell/`. #92 (`config.py`, `targets.py`) and the `:status` hook (`src/nl_shell/input_modes.py:77-87`) are present. Either the wave was scheduled before #16 was accepted, or #16 was not folded into the integration branch. The human needs to fix the scheduling and order. Iterating on Do won't help: the brief tells the builder not to invent stand-ins for #16's names.
- [ ] `gate-logs/C4-verify.log` (no `path:line`, because no code changed): the bundle reached Check with no `patch.diff`, so there was nothing to security-review. The wave base at `$PDCA_TARGET` (HEAD `0771812`) lacks #16's backend interface and `proposal/v1` schema, which the brief lists as a hard dependency. A human needs to decide whether to reschedule #77 after #16 lands, or find out why Do produced no patch. Treat this round's "pass" on T2 and T3 as meaningless for #77. When a real patch exists, it needs a fresh security pass. Focus on: redirects not followed, the body size cap actually stopping the read, no TLS fallback, no TCP connection without `--dev-teacher`, no `Authorization` header or credential sent, and model `content` treated as untrusted (threat model items 5, 8, 11).
- [ ] C4 fix verified: bundle test red pre-fix, green post-fix (pytest) unverifiable — bundle has no patch.diff
- [ ] external dependency: issue-16-core (#143: backend interface, `proposal/v1` parser + schema, "no backend configured" reply) — absent from the wave base `pdca-integration/main-r2546dbf9639f` @ 0771812; the client, its test and criteria (a)–(f) cannot be built without inventing stand-ins, which the brief forbids
- [ ] **The base branch can't support the plan as written.** The brief targets `eduralph/nl-shell @ main` and "Depends on: 16, 92, 14", but `dependency-state.json` lists all three as `"state": "PLANNED"`, so none is merged. On `main` none of what the brief builds on exists yet:
- [ ] **The brief leaves out a conformance rule that names #77.** `docs/design/specs/proposal/v1.md:70-72` says: "The parser tests (#16, #77) MUST include: each valid shape; extra properties; a missing `risk`; `command` with `reason`; an over-long `command`; invalid JSON; a JSON array; and a `risk` lower than the gate's class". Criterion (b) covers all of that with one case ("content that fails `proposal/v1`"). The Citations line lists only spec "§1, §5" as normative, not Conformance. The brief should either:
- [ ] **The brief says the REPL "starts it on demand", but ADR-0018 says otherwise.** `docs/design/adr/0018-model-serving-and-wire-format.md:34` says "The REPL connects to it and starts it on demand." The brief puts "starting or installing `llama-server` / the systemd user service (#48)" out of scope, and scope item (4) replies "the model server isn't running". That may be the right split, but the brief claims to build on ADR-0018 §1 and never mentions this difference. It should be stated in Alternatives or Open questions so sign-off doesn't treat it as an ADR violation.
- [ ] **The scope goes beyond the issue, and two scope items aren't tested.**
- [ ] **The timeout case in (b) can't be run with a short timeout unless the brief says how.** (b) requires "a server that doesn't answer within the timeout", and the Test-file note says "every network wait has a short timeout". The Design section, though, gives a constant for the size cap (64 KiB) and nothing for the connect/read timeouts. It doesn't say whether they are injectable either. If Do hard-codes a realistic read timeout (tens of seconds), that test either becomes slow or gets weakened. The brief should name the timeout constants and require them to be overridable from tests.
- [ ] **The "no TCP connection" promise has no test.** Impact says "With no flag nl-shell makes no TCP connection at all", which is the ADR-0003 must-hold ("no outbound connection in the default config", threat model line 130). (c) only shows that a fake server at the config URL "receives nothing". That doesn't prove no other TCP connection was opened, for example to a guessed default. One option is a test that patches `socket.create_connection` / `socket.socket.connect` and asserts no AF_INET connection on the default path. Without some such test, the main security claim is something a reviewer has to trust.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: iterated-to-Do
- Iteration delta (if iterating): Auto-iterate (round 1): rebuilding for the implementation-level findings — C5 Causal adequacy — Supply the implementation and discriminating tests before causal adequacy can be judged — an empty submission cannot establish the endpoint-safety or rejection guarantees (brief.md:18; gate-logs/C4-verify.log:10).; T4 Contribution — Confirm the actual contribution artifacts meet the opener and tracker requirements — the log records exit zero but contains no captured check output or artifact content to inspect (gate-logs/T4-contribution.log:7–9).. Deferred, not addressed here: 12 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- By / date: auto-iterate / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 6 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

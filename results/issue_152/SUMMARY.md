# Result — issue 152 / teacher-endpoint-dev-teacher-flag

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: 
- Success criterion: `python3 -m pytest tests/test_teacher_endpoint.py` passes, covering:
  **(a) config.** `config.load` on a file without `[model]` → `model_timeout_s == 10`; `[model]\ntimeout_s = 0.5` → `0.5`; a non-number, a bool, a value <= 0, and a value above the chosen upper bound (e.g. `1e10`; name the bound as a constant) → `ConfigError`. `teacher_url` and `teacher_model` load as strings and a non-string raises `ConfigError` (same style as `target`).
  **(b) endpoint rules**, by calling `teacher_client.select_endpoint(dev_teacher, teacher_url, runtime_dir)` directly (nothing connects): no flag and no URL → `Endpoint("unix", "<runtime_dir>/nl-shell/model.sock")`, no messages; `runtime_dir` unset, empty or relative → `Endpoint("unix", None)` (no guess at `/run/user/<uid>`); `teacher_url` without the flag → default socket plus a refusal message; same URL with `dev_teacher=True` → that URL; `dev_teacher="<URL>"` → that URL, winning over `teacher_url`; `dev_teacher=True` with no `teacher_url` → a message saying `--dev-teacher` needs a URL (on the flag or in `teacher_url`) and the default socket; a URL whose scheme is not `http` or `https` (`ftp://x`, `unix:/x`, a bare `host:port`, an unparsable string), from either source → a refusal message naming the URL (escaped) and the default socket, never passed to `TeacherClient`; non-loopback `http://` with the flag → the warning (loopback = `localhost`, `127.0.0.0/8`, `::1`; any other hostname counts as non-loopback, no DNS lookup); loopback `http://` and any `https://` → no warning.
  **(c) through `cli.main` with `capsys`:** the refusal reaches stderr once, and the warning reaches stderr once. `cli.main([... "--dev-teacher" ...])` parses (today argparse exits 2).
  **(d) timeout reaches the client:** `cli.main` with `[model] timeout_s = 0.5`, a slow-drip fake server on the default socket and one natural-language line → `out` shows the `could not be used` reply and the run ends in under 2 s.
  **(e) `:status`:** `cli.main` builds `:status` lines naming the endpoint in use and the backend kind, captured the way `tests/test_cli.py:29-46` captures `status_lines`.
  **(f) no TCP on the default path:** `socket.socket.connect` and `socket.create_connection` patched to record calls; `cli.main([], targets_root=…, os_release_paths=[…])` with a matching os-release, a target with a valid `prompts/prompts.yaml`, `teacher_url = "http://127.0.0.1:<port>"` in `config.toml`, no flag, a fake server at that URL, a fake server on the default socket, and scripted input of one natural-language line then EOF → zero `AF_INET`/`AF_INET6` connects, at least one `AF_UNIX` connect and every `AF_UNIX` connect to `$XDG_RUNTIME_DIR/nl-shell/model.sock`, the default-socket server received the request, and the server at the URL received nothing. Red if selection leaks the config URL, and red if the REPL is not wired to the client.
  Import `nl_shell.teacher_client` and `nl_shell.prompts` inside test functions or fixtures; at module level only the stdlib, pytest, `nl_shell.cli`, `nl_shell.config` and `nl_shell.repl.Repl`. Red with the change reverted: `select_endpoint` does not exist, `--dev-teacher` exits 2, `config.Config` has no `model_timeout_s`, and (f) sees zero `AF_UNIX` connects and #143's `NO_BACKEND` reply. The red proof must come from this file's own assertions, not from `:status` churn in `tests/test_cli.py` / `tests/test_targets.py`.
- Repo + branch target: eduralph/nl-shell @ main, built on the integration base with #143's accepted patch and child-1's accepted patch folded in (verify via `$PDCA_VERIFY_BASE`). Use child-1's names (`TeacherClient`, `Endpoint`, `MAX_RESPONSE_BYTES`, `backend.BackendError`) as they landed.
- Scope (one logical fix) / out of scope: 

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (110 of 243 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — no security-relevant path touched
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review wiring the REPL to the local model socket by default, with explicit per-session opt-in for developer teacher URLs and configurable request deadlines.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | Endpoint consent and timeout expectations are concrete and consistent with the governing endpoint rule; target/docs/design/adr/0020-configuration-and-file-locations.md:32 and brief.md:4. |
| C2 Reproduction (red pre-fix) | PASS | Frozen red output shows assertion failures for missing selection, rejected flag, missing timeout and zero Unix connections, rather than collection errors; gate-logs/C4-verify.log:17 and target/tests/test_teacher_endpoint.py:632. |
| C3 Change | PASS | The diff stays within endpoint selection, configuration and CLI wiring, with status-only adjustments in existing tests; target/src/nl_shell/cli.py:83 and target/tests/test_backend.py:544. |
| C4 Verification (red→green) | PASS | Captured gate execution reports 243 green tests and 110 red failures without production changes, including the new file's own assertions; independent pytest execution was unavailable because this sandbox has no pytest; gate-logs/C4-verify.log:10. |
| C5 Causal adequacy | PASS | The missing backend is supplied at the actual REPL construction point, and the end-to-end assertion requires a received Unix request plus a rendered proposal; no optional-capability probe masks a load-time cause; target/src/nl_shell/cli.py:98 and target/tests/test_teacher_endpoint.py:634. |
| T1 Structure | PASS | Pure selection is separated from connection execution and CLI presentation; the existing transport implementation remains intact; target/src/nl_shell/teacher_client.py:213 and target/src/nl_shell/cli.py:88. |
| T2 Shape | PASS | Default selection refuses configured TCP URLs before client creation and the test checks both connection families and server receipt; the scanner log only asserts no recognized security path, not a substantive security audit; target/tests/test_teacher_endpoint.py:600 and gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | Frozen full-suite evidence records 753 passing tests with one forkpty deprecation warning; independent timeout checks passed, but this sandbox lacks pytest for a suite re-run; gate-logs/T3-suite.log:23 and target/src/nl_shell/config.py:93. |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive contribution audit must run at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art across merged history and closed/rejected work before treating this as new work — the brief records only cli.py/config.py history and parent attempts, while the supplied target has one synthetic commit and no remotes; brief.md:22. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether local fake-server evidence suffices for the intended deployment and whether refusal followed by local fallback is acceptable — no real LAN teacher/model was exercised; target/tests/test_teacher_endpoint.py:98 and brief.md:27. |

Evidence and limits:

- Target source was readable and contained the applied patch with the required prerequisite client and REPL interface. Citations beginning `target/` refer to that supplied target, not another checkout. No target-state mismatch was found.
- Attempted `python3 -m pytest tests/test_teacher_endpoint.py -q` from the target: `/usr/bin/python3: No module named pytest`. Therefore no stash/red/pop cycle was attempted: the same missing runner would prevent either leg. C2/C4/T3 verdicts rely explicitly on the complete frozen logs, not on an independently reproduced pytest run. The logs show actual tests executing, including YAML-backed prompt fixtures; there is no evidence of an undischarged PyYAML dependency in the gate environment.
- Independently ran `git -C target diff --check` successfully and eight direct config timeout checks covering 0.5, booleans, zero, negative values, NaN, infinity, an excessive value and a string. No product source was modified.
- Read all four supplied gate logs. Wrapper absence in this artifact sandbox is expected. T2's narrow path classification does not establish that this endpoint change is security-irrelevant; source review and the no-TCP regression test provide the substantive basis above.
- Prior-art investigation: `git -C target remote -v` returned no remotes; `git -C target log --all --oneline -- src/nl_shell/cli.py src/nl_shell/config.py src/nl_shell/teacher_client.py tests/test_teacher_endpoint.py` returned only `09b25de pre-fix base`. No closed/rejected-work evidence or INTEGRATION.md was supplied. The human must supply or confirm the broader affected-path search.
- Deployment validation: with a matching installed OS target and a running compatible model server, run `nl-shell --dev-teacher http://TEACHER_HOST:PORT`, enter `:status`, then `show disk usage`; confirm endpoint/backend, the non-loopback HTTP warning, and a usable proposal without accepting execution. Repeat without the flag while that URL is configured: confirm the refusal, local-socket status and absence of requests at the teacher. This checks the real service/topology beyond the captured local fixtures.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue_152 (teacher-endpoint-dev-teacher-flag), iteration 2

**Bottom line:** I tried to refute the fix on the evidence, the endpoint rules, the escaping, the config parsing and the wiring, and could not. I have no NEEDS-HUMAN findings. The notes below are observations only.

## Evidence (red→green)

- I could not re-run pytest myself: the system `python3` here has no `pytest`, and there is no `.venv` in `$PDCA_TARGET`. So I judged the gate from the frozen log `gate-logs/C4-verify.log`. Green leg: 243 passed (`:15`). Red leg: 110 failed (`:2724`). Every test in `tests/test_teacher_endpoint.py` is among the failures. The 133 tests that passed on the red leg are all in other files, so the red proof comes from this file's own assertions, as the brief requires. It does not depend on `:status` changes in `test_cli.py` / `test_targets.py`. T3 shows the full suite green (`gate-logs/T3-suite.log:28`, 753 passed).
- Test (f) exercises the real code path and is not a copy of it: `tests/test_teacher_endpoint.py:600-638` runs `cli.main` for real, with `socket.socket.connect` and `socket.create_connection` patched to record calls. It asserts zero `AF_INET`/`AF_INET6` connects, at least one `AF_UNIX` connect, every one of them to the default socket, the default server got the request, and the server at the URL got nothing (`:627-638`). Without the fix there is no backend, so `on_socket.requests` is empty and the test goes red. I found no way for it to pass for the wrong reason.

## Fix: inputs I tried against `select_endpoint` (`src/nl_shell/teacher_client.py:213-263`)

I ran `select_endpoint` directly on the patched target. Each input gave a safe result:
- `http://[::1%25eth0]`, `http://[::ffff:127.0.0.1]`, `http://127.1`, `http://localhost.`, `http://0.0.0.0` are all treated as not loopback and get the warning (`is_loopback`, `:200-210`). That is a false alarm in some of these cases, but it is the cautious direction and matches the brief's "no DNS lookup" rule. None of them gets past the warning.
- `HTTP://127.0.0.1` is accepted with no warning. That is correct: `urlsplit` lowercases the scheme, so the `http_target` check at `:168` agrees.
- `https://[::1` gets "does not parse (Invalid IPv6 URL)". This fixes the iteration-1 finding about `_scheme` giving the wrong reason (`:275-289`, which now checks the raw prefix).
- `teacher_url = ""` without the flag is refused. `dev_teacher=False` is handled like `None`. A runtime dir holding ESC goes into the socket path as raw text, but `:status` output is escaped by `Repl` (`src/nl_shell/repl.py:138`), and start-up messages go through `_shown` and then `_error`. The `render.escape` in `_error` does not double backslashes, so messages are escaped once, as `test_url_reaches_stderr_exactly_as_shown` pins. This fixes the iteration-1 double-escape finding.
- Accepted URLs with odd but harmless shapes: `http://h:` (falls back to port 80), `http://h/v1/../x`, `http://h\x` (backslash in the host). These fail at connect time with the client's normal error and leak nothing. I don't count them as defects in this diff.

## Config (`src/nl_shell/config.py:70-102`)

- I checked `timeout_s` with an int too large for a float (compared before conversion, `:97`), with `nan` and `inf` (both fail the `0 < v <= MAX` check), with a bool (rejected first, `:94`), and with `[model]` not being a table (`:74`). All are refused as the brief asks. `MAX_MODEL_TIMEOUT_S = 3600.0` is the named bound.

## Things the reviewer might have taken on trust

- `check-gates.json` T2 row: "no security-relevant path touched". This diff chooses the network endpoint (`teacher_client.py`, `cli.py`), which is about as security-relevant as this project gets. The row is non-gating, and the threat model already states the rule this patch puts into code (`.oss-scanner/threat_model.md:100-101,154`), so nothing is missing. But the T2 path list evidently does not cover `teacher_client.py`. That is a gate-configuration gap, not a defect in this patch, so it is not a NEEDS-HUMAN item.

I tried to refute the evidence (could the red proof be tautological or borrowed from other files), the endpoint rules (loopback spoofing, scheme case, URLs that don't parse, empty or false values, a bad runtime dir), the escaping, and the config bounds. I could not break any of them.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory): teacher-endpoint-dev-teacher-flag

**Attacker-reachable inputs this diff touches:** the dev teacher endpoint (threat model item 11, LAN peer), which this patch now wires into the REPL, plus the rule that decides when that endpoint is used instead of the local socket (item 8). `teacher_url`/`teacher_model`/`[model] timeout_s` in `config.toml`, the `--dev-teacher` argument and `XDG_RUNTIME_DIR` all come from the user. The threat model trusts them, with one exception: a model endpoint in config is refused without `--dev-teacher`.

**Result: no finding.** Here is what I checked against the threat model's "What must hold" list:

- **"No outbound connection in the default config"** (`.oss-scanner/threat_model.md:186`) and **"a model endpoint in [config] is refused without `--dev-teacher`"** (`:132-133`). `src/nl_shell/teacher_client.py:238-245`: with `dev_teacher` set to `None`/`False`, `select_endpoint` returns only `default_socket(...)`, an `Endpoint("unix", …)`, whatever `teacher_url` holds. `src/nl_shell/cli.py:83-90` builds the one `TeacherClient` from that result alone, so the config URL cannot reach the client. `tests/test_teacher_endpoint.py:600-638` patches `socket.socket.connect` and `socket.create_connection` and runs the real `cli.main` with a loopback `teacher_url` and a live TCP server. It asserts zero `AF_INET`/`AF_INET6` connects, that every `AF_UNIX` connect goes to the default socket, and that the TCP server got nothing. This is the attacker-relevant case, not only the friendly one. C4 shows this test red before the fix (`gate-logs/C4-verify.log`). `TeacherClient` ignores `HTTP(S)_PROXY` (`teacher_client.py:19`), so the environment cannot reroute the default path either.
- **No guessed socket path.** `teacher_client.py:206-208`: an unset, empty or relative `XDG_RUNTIME_DIR` gives `Endpoint("unix", None)`, with no fallback to `/run/user/<uid>` or to TCP.
- **Untrusted or odd bytes in start-up text.** URLs and the socket path in stderr messages go through `_shown` (`teacher_client.py:277-283`, `render.escape(..., backslash=True)`) and then through `cli._error`'s `render.escape` (`cli.py:109-111`). The second pass is harmless because the first already removed every hidden character. Tests `:375-425` cover ESC, U+202E (a bidi override character), a literal `\x1b` and a `'` in the URL, and show the iteration-1 double-escaping finding is fixed. The `:status` lines (`cli.py:91-96`, `describe_endpoint` at `teacher_client.py:331-337`) show the raw socket path or URL, but every REPL reply, `:status` included, is printed through `render.escape` (`src/nl_shell/repl.py:138`). An accepted URL is also limited to ASCII with no controls (`teacher_client.py:309-310`).
- **Credentials in the URL.** `teacher_client.py:316-317` refuses user info (`http://u:p@h`), so a password cannot end up in `:status` or stderr through the URL.
- **LAN peer with `--dev-teacher`.** Non-loopback `http://` gets the warning (`teacher_client.py:268-273`). `is_loopback` (`:211-221`) does no DNS lookup and fails safe: `127.1`, `::ffff:127.0.0.1` and any hostname other than `localhost` count as non-loopback, so they warn. The patch does not change TLS (`check_hostname`/`CERT_REQUIRED`, `:443-445`) or the no-redirect rule (`:599`). Teacher answers still go through #143's proposal parser as untrusted model output (item 5). Sending the state block to a flagged teacher is the documented design (item 11), not a regression.
- **Resource use / hang.** `[model] timeout_s` is bounded to (0, 3600] and rejects bool and NaN (`src/nl_shell/config.py:149-159`). It compares before converting, so a huge TOML integer cannot overflow. Only the user's own config can set it, and the client clamps waits anyway (`teacher_client.py:33`).
- **argparse edge cases.** `--dev-teacher=` (empty) reaches `_scheme` → `None` → refused, falling back to the default socket. `--dev-teacher --target X` parses as `dev_teacher=True` and does not swallow `--target`.

Side note, not a finding: the T2 gate log says "no security-relevant path touched" (`gate-logs/T2-threat-model.log`). This patch does touch the endpoint choice behind the "locally complete" property. The review above covers it, but the gate's classifier may be too narrow for endpoint and network changes.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] T5 Judgment — Confirm affected-path prior art across merged history and closed/rejected work before treating this as new work — the brief records only cli.py/config.py history and parent attempts, while the supplied target has one synthetic commit and no remotes; brief.md:22.
- [x] Validation — fitness-to-purpose — Decide whether local fake-server evidence suffices for the intended deployment and whether refusal followed by local fallback is acceptable — no real LAN teacher/model was exercised; target/tests/test_teacher_endpoint.py:98 and brief.md:27.
- [x] **Declared prerequisite #151 has not landed.** `dependency-state.json` lists `"151": {"exists": true, "state": "PLANNED"}`. The brief's base needs "child-1's accepted patch folded in" (Repo + branch target), and the Falsifiability section says "Precondition: #143 and child-1 are in the verify base". The brief also names `TeacherClient`, `Endpoint`, `MAX_RESPONSE_BYTES` and `backend.BackendError` "as they landed". None of them has landed yet. If Do starts now, the bundle is stranded. If #151 lands with different names or a different `Endpoint` shape, criteria (b), (d) and (f) are wrong. Hold this bundle until #151 is COMPLETE, or mark it explicitly as stacked.
- [x] **I could not check any #143 or child-1 anchor against `$PDCA_TARGET`.** The target is plain main. It has no `backend.py`, `prompts.py`, `teacher_client.py` or `tests/test_backend.py` (Glob over `src/nl_shell/*.py`, `tests/*.py`). `cli.py:64` is `Repl.interactive(status_lines=status_lines).run()`, with no `prompts=`. So these brief claims cannot be checked here: "`cli.main` passes `prompts=` but no `backend=`" (Reproduction), "#143's `:539-559`" in `test_backend.py` (Scope 4), and the `NO_BACKEND` reply text. The brief already says "re-derive the lines". The human should confirm that the gate's `$PDCA_VERIFY_BASE` really contains both patches. Without them, the red proof's "#143's `NO_BACKEND` reply" in (f) has nothing to rest on.
- [x] **Criterion (d) tests child-1's deadline, but the scope forbids fixing it.** (d) uses a slow-drip fake server and expects the run to end "in under 2 s" with `timeout_s = 0.5`. A slow drip defeats a per-`recv` socket timeout and only passes against a total request deadline. Meanwhile Scope says "Out of scope: any transport, deadline or error-handling change in `TeacherClient` (child-1 owns it; if a transport bug shows up, report it, don't fix it here)". If #151's client uses per-read timeouts, (d) can never go green inside this bundle's scope. Also, the expected `could not be used` reply text belongs to the repl/backend error path (#143 / child-1), not to this change. (d) can only check that `timeout_s` reaches the constructor. A unit check of `TeacherClient(..., timeout_s=0.5)` would do that more cheaply. Either confirm that #151's criterion already pins a total deadline against a slow drip, or narrow (d).
- [x] **`:status` is a second feature.** ADR-0020 §4 (`docs/design/adr/0020-configuration-and-file-locations.md:36`) is a separate decision item from §3, the endpoint rule (`:32-35`), which is the invariant this brief restores. Adding two `:status` lines is why the brief must edit `tests/test_cli.py`, `tests/test_targets.py` and `tests/test_backend.py`. That is three existing test files of churn, and the brief itself warns that the red proof "must not come from `:status` churn". Consider splitting criterion (e) and Scope 3's status lines into a follow-up. If they stay, accept that review surface knowingly.
- [x] **"Refused" is interpreted as "fall back and continue", which is a policy choice.** ADR-0020 §3 says "A URL in `config.toml` alone is refused with a message" (`:34`). The threat model says "a model endpoint in them is refused without `--dev-teacher`" (`.oss-scanner/threat_model.md:100-101`). The brief makes refusal mean "default socket plus a refusal message" and carry on. Today, other config faults are fatal: `cli.py:53-55` returns 1 on `ConfigError`. Both readings fit the ADR. The human should confirm "warn and continue" over "exit 1" at sign-off, because (b) and (c) bake it in.
- [x] **The criterion leaves two branches open, so (b) is not fully specified.** For "`dev_teacher=True` with no `teacher_url` → a clear message and the default socket (or an argparse error — pick one and test it)", the builder's choice becomes the spec. (b) also never says what `select_endpoint` does with a URL that is neither `http://` nor `https://` (`ftp://x`, `unix:/…`, a bare `host:port`, an unparsable string). Without that, a bundle that silently passes such a URL to `TeacherClient` still goes green. Pin one behaviour for each case, for example: reject with a message, fall back to the default socket.
- [x] **"Exactly one `AF_UNIX` connect" in (f) depends on how child-1 connects.** This is a brittle assertion on behaviour that is out of scope here. If #151's client connects more than once per request (e.g. a probe connect, a reconnect after a short read), (f) goes red for reasons this brief may not fix. "≥1 `AF_UNIX` connect to the socket path, and zero `AF_INET`/`AF_INET6`" proves the invariant equally well.
- [x] **ADR-0018 §5 is left contradicting the chosen rule.** `docs/design/adr/0018-model-serving-and-wire-format.md:46-48` still says only "A non-loopback URL needs the explicit `--dev-teacher` flag". The brief adopts the stricter ADR-0020 §3 rule ("confirmed by the human at Plan") and rules out only the "architecture doc 05 table". Decide whether ADR-0018's wording gets a one-line amendment in this bundle or a tracked follow-up. Otherwise the next planner reads the looser rule.
- [x] T5 Judgment — Confirm affected-path prior art across merged and closed/rejected work before sign-off — the disposable target exposes only one synthetic base commit, so the brief's history claim cannot be independently established, including teacher_client.py; target/src/nl_shell/teacher_client.py:213.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: merged-wider
- Iteration delta (if iterating):
- By / date: Eduard Ralph / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 8 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)
- Doc follow-up: amend ADR-0018 §5 (`docs/design/adr/0018-model-serving-and-wire-format.md:46-48`) to match ADR-0020 §3 — loopback TCP also needs `--dev-teacher`.
- Gate gap: T2's security-path list does not count `src/nl_shell/teacher_client.py` / endpoint selection in `cli.py` as security-relevant (flagged by adversary + security review).

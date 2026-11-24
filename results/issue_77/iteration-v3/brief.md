# Design proposal — issue 77 / teacher-client-dev-teacher-flag

> The Plan artifact. Do reads ONLY this file and implements it; Check runs the regular
> gated check on the code.
> Milestone: **M0** (tracker eduralph/nl-shell#8, work item M0.8b, split from #16 in the
> design review). Builds on ADR-0018 §1–§3 and §5 (local socket, constrained decoding,
> reject not repair, the teacher through the same client), ADR-0020 §3–§4 (endpoint rules,
> `:status`), spec `proposal/v1`, and ADR-0003 (locally complete: no outbound connection
> in the default config).
> Threat-model inputs affected: item 11 (the dev teacher endpoint), item 8 (the local model
> socket), item 5 (model output), the trusted-input exception "a model endpoint in config
> is refused without `--dev-teacher`", and the must-hold "no outbound connection in the
> default config".

- **Slug:** teacher-client-dev-teacher-flag
- **Kind:** enhancement (design proposal)
- **Goal:** nl-shell can send its model input to an OpenAI-compatible chat endpoint (llama.cpp `llama-server` or vLLM, no API key) and get a `proposal/v1` answer back, with constrained decoding. By default it talks only to the local model socket. Any other endpoint URL is used only when the user passes `--dev-teacher` for that session; a URL in `config.toml` alone is refused with a message. A non-loopback plain-HTTP URL gets a warning to use an SSH tunnel or TLS, since the state block goes out in clear.
- **Success criterion:** `python3 -m pytest tests/test_teacher_client.py` passes, against a fake OpenAI-compatible HTTP server started by the test on `127.0.0.1` (port 0) and on a Unix socket in `tmp_path`, covering: (a) a valid response carrying a `proposal/v1` object in `choices[0].message.content` → the parsed proposal; the request the fake server received is `POST /v1/chat/completions` with the model input's messages, a JSON-schema `response_format` whose schema is the `proposal/v1` schema (the same object #16's parser uses), and no `Authorization` header; with `teacher_model = "m1"` in `config.toml` the request body has `"model": "m1"`, and without it the body has no `model` key. (b) rejected, never repaired, each with a reason and no retry: an HTTP error status; a 3xx redirect (not followed — the fake server sees one request and nothing goes to the redirect target); a body that isn't JSON; JSON without `choices[0].message.content`; content that fails `proposal/v1` — each `proposal/v1` §Conformance reject case delivered as `message.content`: extra property, missing `risk`, `command` with `reason`, `command` over 2000 code points, invalid JSON, a JSON array (the "risk lower than the gate's class" case needs the policy gate, #12, which is not a dependency here; #12 adds it); a body over the size cap (the client stops reading past the cap); a server that doesn't answer within the timeout (the test builds the client with a 0.5 s read timeout and the fake server sleeps 2 s; the test finishes in under 2 s); an `https://127.0.0.1:<port>` URL pointed at the plain-HTTP fake server → rejected with a TLS error as the reason, and no plain-HTTP request is sent instead (certificate and protocol checks are on; no fallback). (c) endpoint rules: no flag and no config URL → the default endpoint `$XDG_RUNTIME_DIR/nl-shell/model.sock` is used (a fake server on that path answers); `teacher_url` in `config.toml` without `--dev-teacher` → refused with a message, and the fake server at that URL receives nothing; the same URL with `--dev-teacher` → used; `--dev-teacher <URL>` on the command line → used; a non-loopback `http://` URL with the flag → the warning (checked on the endpoint decision, without connecting anywhere off the host). (d) through `Repl` with the client pointed at the fake server: a natural-language line shows the fake server's proposal; when the default socket is absent, the reply says the model server isn't running, and nothing crashes. (e) `:status` shows the endpoint in use and the backend kind. (f) no TCP on the default path: with `socket.socket.connect` and `socket.create_connection` patched to record their calls, `cli.main([])` (with a matching os-release injected as #92's tests do, and a scripted stdin) with `teacher_url` in `config.toml` and no flag, followed by one natural-language line, makes no `AF_INET` / `AF_INET6` connection at all (only the `AF_UNIX` attempt to the default socket).
- **Falsifiability:** RED is reachable on the shipped C4 gate (`engine/scripts/run-verify.sh`, plain pytest on the host). With the production change reverted, the client module doesn't exist (each test's in-function import fails) and `cli.main(["--dev-teacher", …])` exits 2 from argparse — tests ran, failures > 0. The fake server runs in-process on loopback / a Unix socket, so no network, model or GPU is needed; the real LAN teacher check is manual (issue: "the real LAN check is manual") and is not part of the binding criterion.
- **Repo + branch target:** eduralph/nl-shell @ main (built in a later wave than #14, #16 and #92: per `Depends on` the driver folds their accepted patches into the wave's integration branch and verifies against it via `$PDCA_VERIFY_BASE`, so #16's backend interface, parser and schema, #92's `config.toml` unit and #14's `:status` exist when this bundle builds; if any is not accepted, this bundle is not scheduled. Use their names as they landed; do not invent stand-ins.)
- **Depends on:** 16, 92, 14
- **Ordering note:** After #16 (the backend interface this client implements, the `proposal/v1` parser and schema, the "no backend configured" path it replaces), #92 (`config.toml` loading) and #14 (`:status`). It can share a wave with #62 (no common files).
- **Surfaces:** data
- **Scope:** (1) A backend for #16's interface that speaks the OpenAI chat-completions API over HTTP, both to a TCP URL (`http://`, `https://`) and to the local Unix socket (ADR-0018 §1); the request carries the model input's messages and a JSON-schema `response_format` built from the single `proposal/v1` schema #16 keeps (ADR-0018 §2); an optional model name from `config.toml` (`teacher_model`, sent only if set — vLLM needs it, llama-server ignores it). (2) Strict response handling (ADR-0018 §3): non-2xx, redirects, oversize bodies, invalid JSON, a missing content field, and content failing `proposal/v1` are rejected; no retry, no repair; connect and read timeouts as named module constants (`CONNECT_TIMEOUT_S = 5`, `READ_TIMEOUT_S = 120` — a CPU-only teacher can be slow) that the client's constructor accepts as overrides, so tests pass short values. (3) Endpoint selection (ADR-0020 §3): default is `$XDG_RUNTIME_DIR/nl-shell/model.sock`; `--dev-teacher [URL]` in `cli.py` enables a non-default endpoint for this session, taking the URL from the flag or else from `teacher_url` in `config.toml`; `teacher_url` without the flag is refused with a message and the default is used; a non-loopback `http://` host gets the SSH-tunnel / TLS warning. (4) The interactive REPL uses this backend instead of #16's "no backend configured" reply; an unreachable default socket gives a plain "the model server isn't running" reply per request. (5) `:status`: endpoint and backend lines (ADR-0020 §4). / out of scope: starting or installing `llama-server` / the systemd user service (#48); the student model (#42); the reader's request (#61); API keys or any credential (the teacher has none; ADR-0006/0015 forbid sending credentials to a model server); retries, streaming; the rendering of the proposal (#16 owns it); any change to `proposal/v1`; the architecture doc 05 table (one docs pass after the batch).
- **Difficulty:** medium
- **External dependencies:** none (the client uses the standard library's HTTP support; the fake server is the standard library's too)
- **Test file:** `tests/test_teacher_client.py` (new). The C4 red leg reverts every non-`tests/` file and re-runs this file; a module-level import of the new client would fail to IMPORT and make the run UNVERIFIABLE instead of red. Import new modules inside the test functions; module level only the standard library, pytest, and names on `main` (`nl_shell.cli`, `nl_shell.repl.Repl`). Every server thread is shut down in teardown and every network wait has a short timeout. Don't mark these tests `teacher` — they never reach a real teacher. `tests/conftest.py` does NOT isolate `XDG_RUNTIME_DIR` (it sets HOME and the four other XDG variables only), so every test that touches the default socket must `monkeypatch.setenv("XDG_RUNTIME_DIR", …)` to a temp dir, and an unset `XDG_RUNTIME_DIR` must mean "no default socket" (the "model server isn't running" reply), never a guess at `/run/user/<uid>`. A Unix socket path must fit in about 107 bytes (`sun_path`), and pytest's `tmp_path` can be longer: put the socket in a short directory (e.g. `tempfile.mkdtemp(prefix="nls-")`), removed in teardown.
- **Citations expected:** Do must cite path:line on `main` (or the wave base for #14/#16/#92 code) for every change. Wiring points: the argument parser at `src/nl_shell/cli.py:12-18`; `Repl.interactive` at `src/nl_shell/repl.py:40-45`; #16's backend interface, schema and "no backend configured" reply, #92's `config.toml` unit (extend that unit only — #62 edits #92's target loader in the same wave) and #14's `:status` on the wave base. Peer to mirror: implement the backend exactly as #16's stub implements the same interface, so the REPL can't tell them apart. Normative: ADR-0018 §1–§3, §5; ADR-0020 §3–§4; `docs/design/specs/proposal/v1.md` §1, §5 and §Conformance (which names #77).
- **Prior-art check (triage cycles):** `git -C ../nl-shell log origin/main -- src/nl_shell` → scaffold, router, isolation only; `git grep -n -i -E 'http|teacher|openai' origin/main -- src` → nothing. Closed-unmerged PRs touching `src/`: none. Open PRs: #100 only (docs). Issue search "teacher" / "openai": #77 itself, #16 (split parent), #45 (when to fall back to the teacher — later), #33 (teacher license). No prior work.
- **Disposition hint:** new-feature

## Motivation

M0 runs on the teacher (proposal 0001 §M0: "with the teacher proposing"). Without a
client nothing proposes. The endpoint rules exist because a copied config with a LAN URL
would otherwise send the user's state block over the network silently (ADR-0020 Context).

## Design

- Size cap: pick one that comfortably holds a maximal `proposal/v1` answer plus the
  chat-completions envelope (64 KiB is ample: `command` is at most 2000 code points) and
  name it as a constant.
- Loopback test for the warning: `localhost`, `127.0.0.0/8`, `::1`. Hostnames other than
  `localhost` count as non-loopback (no DNS lookup to decide).
- Redirects: never followed — a redirect could send the state block to a host the user
  didn't name.
- The fake server in the test is a small `http.server` handler recording each request.

## Alternatives considered

- `requests` / `httpx`: a new dependency for one POST; the standard library suffices.
- Following ADR-0018 §5 / the issue's wording ("a non-loopback URL requires
  `--dev-teacher`"), which would let a loopback TCP URL from `config.toml` work without
  the flag: not chosen — ADR-0020 §3 is explicit that any URL other than the local socket,
  "including a loopback TCP port", needs the flag. The stricter rule satisfies the issue's
  done-when too.

## Impact & compatibility

`--dev-teacher` is a new CLI flag; `teacher_url` and `teacher_model` are new
`config.toml` keys. With no flag nl-shell makes no TCP connection at all.

## Open questions

- Confirm the ADR-0020 reading above (loopback TCP also needs `--dev-teacher`). If the
  looser ADR-0018 §5 reading is wanted instead, one ADR needs correcting.
- ADR-0018 §1 says "The REPL connects to it and starts it on demand." This bundle only
  connects: starting `llama-server` (the systemd user service) belongs to #48, so an absent
  socket gives "the model server isn't running". This is a deliberate split, not an ADR
  violation; the human confirms it at sign-off.
- `teacher_model` is not in the issue or the ADRs. It is kept because vLLM rejects a
  request without a model name; it is tested in (a). Drop it at sign-off if unwanted.

## STOP discipline

Draft only until Check sign-off. Pushing to a feature/draft branch and opening a
draft PR MAY happen during the cycle (useful for CI feedback). The PR MUST NOT be
marked ready before sign-off accepts.

Plan-review response: (1) addressed — the branch-target line names the folded wave base of #14/#16/#92 and says the bundle is not scheduled without them; (2) addressed — (b) runs every `proposal/v1` reject case through `message.content`, and says the risk-vs-gate case waits for #12; (3) addressed — the ADR-0018 "starts it on demand" difference is recorded under Open questions as a split to #48; (4) addressed — `teacher_model` is tested and justified, and `https://` is exercised by a no-fallback TLS-failure case; (5) addressed — timeout constants are named and injectable, with a 0.5 s test; (6) addressed — (f) asserts no AF_INET/AF_INET6 connection on the default path.

## Iteration 1 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 1): rebuilding for the implementation-level findings — C5 Causal adequacy — Supply the implementation and discriminating tests before causal adequacy can be judged — an empty submission cannot establish the endpoint-safety or rejection guarantees (brief.md:18; gate-logs/C4-verify.log:10).; T4 Contribution — Confirm the actual contribution artifacts meet the opener and tracker requirements — the log records exit zero but contains no captured check output or artifact content to inspect (gate-logs/T4-contribution.log:7–9).. Deferred, not addressed here: 12 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v1/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 2 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 2): rebuilding for the implementation-level findings — C5 Causal adequacy — Supply the implementation and discriminating tests — the repeated empty submission establishes none of the endpoint-safety or rejection guarantees (brief.md:18; brief.md:83–85; gate-logs/C4-verify.log:10).; T4 Contribution — Confirm the actual contribution artifacts satisfy the user-impact opener and tracker requirements — the frozen log records exit zero but no check output or artifact content to inspect (gate-logs/T4-contribution.log:7–9).. Deferred, not addressed here: 12 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v2/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 3 — carry-forward (from the previous attempt)
- Sign-off rationale: Root cause is scheduling, not implementation: the brief says "Depends on: 16", but #16 was split and its backend interface, proposal/v1 parser + schema and "no backend configured" reply now live in #143, which is not accepted (sent back iterate-do this session). So #77 was scheduled onto a base without them: rounds 1-2 produced empty patches, round 3 used a stand-in schema (tests/test_teacher_client.py:28) and never wired TeacherClient into the REPL (cli.py:82 still builds Repl with no backend). Re-plan: change the dependency to #143 (keep #92, #14) so #77 is not scheduled until #143 is accepted and folded into the wave base; re-cite #143's names as they landed. Do not iterate Do on the current base. Carry forward into the brief for the next build: - strip or escape control characters in server-provided text that reaches TeacherError.reason (HTTP reason phrase at teacher_client.py:312-314, and `{exc}` text at :257, :278); add a fake-server test with ESC/OSC 52 in the reason phrase; - READ_TIMEOUT_S must be a total deadline for the whole response (time.monotonic), not per socket read; add a slow-drip body test; - criterion (f) must assert exactly one AF_UNIX connect to the default socket, so it goes red if choose_endpoint leaks the config URL; - the C4 red leg should not lean on :status text churn in test_cli.py / test_targets.py.
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Root cause is scheduling, not implementation: the brief says "Depends on: 16", but #16 was split and its backend interface, proposal/v1 parser + schema and "no backend configured" reply now live in #143, which is not accepted (sent back iterate-do this session). So #77 was scheduled onto a base without them: rounds 1-2 produced empty patches, round 3 used a stand-in schema (tests/test_teacher_client.py:28) and never wired TeacherClient into the REPL (cli.py:82 still builds Repl with no backend).
  Re-plan: change the dependency to #143 (keep #92, #14) so #77 is not scheduled until #143 is accepted and folded into the wave base; re-cite #143's names as they landed. Do not iterate Do on the current base.
  Carry forward into the brief for the next build:
  - strip or escape control characters in server-provided text that reaches TeacherError.reason (HTTP reason phrase at teacher_client.py:312-314, and `{exc}` text at :257, :278); add a fake-server test with ESC/OSC 52 in the reason phrase;
  - READ_TIMEOUT_S must be a total deadline for the whole response (time.monotonic), not per socket read; add a slow-drip body test;
  - criterion (f) must assert exactly one AF_UNIX connect to the default socket, so it goes red if choose_endpoint leaks the config URL;
  - the C4 red leg should not lean on :status text churn in test_cli.py / test_targets.py.
- Full previous attempt preserved in `iteration-v3/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

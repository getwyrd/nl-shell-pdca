<!-- pdca:split-proposal v1 -->
# Split proposal — issue 77

<!-- Each child is a COMPLETE brief, not a sketch. A filled Slug alone makes `state.state`
     classify the materialised file as PLANNED, so `pdca flow` skips Plan and sends it
     straight to Do — a child missing `Repo + branch target` then builds successfully and
     has nowhere to publish. Fill every field. -->

<!-- Delimiters are HTML comments, not headings, DELIBERATELY: each child body is a full
     draft brief and may contain arbitrary headings and fenced code blocks, so anything
     that could also appear inside a child cannot be its boundary. `pdca split --accept`
     parses these markers; keep them exactly as written. -->

## Why this slice is oversized

The brief (22.9 KB, six scope items, six criterion groups) holds two separate pieces of work.
The last attempt was a 64 KB patch over 10 files after five iterations, and sign-off asked
for a split along the same line used here.

1. **The transport.** An HTTP / Unix-socket client that implements #143's `Backend`
   protocol: request shape, strict response handling, a total deadline, a size cap, TLS
   checks, plus `backend.BackendError` and the `Repl._propose` catch that turns a failure
   into a fixed, escaped reply. This is where every real bug in iterations 4–6 came from
   (OverflowError on a huge timeout, the deadline lost once `http.client` hands the socket
   to the response, connect/DNS not under the deadline, TimeoutError and InvalidURL thrown
   outside the `try`, missing default port for `http://[::1]/`). It can be fully tested by
   building `Repl(..., backend=<client>)` directly against a fake server, with no
   `config.py` or `cli.py` change. Criteria (a), (b) except the config/CLI timeout parts, and (d).

2. **Endpoint policy and wiring.** The `config.toml` keys (`teacher_url`, `teacher_model`,
   `[model] timeout_s`), the pure `select_endpoint` rules (default socket, the refusal of a
   config URL without the flag, the plain-HTTP warning), the `--dev-teacher [URL]` flag,
   building the client in `cli.main` and passing it as `backend=`, and the two `:status`
   lines. This is the security policy (ADR-0003, ADR-0020 §3) and the user-visible part.
   Criteria (c), (e), (f), and the config/CLI timeout parts of (b).

The seam is the client's constructor: `TeacherClient(endpoint, *, timeout_s,
max_response_bytes, model)`. Child-1 defines it and the `Endpoint` dataclass. Child-2
decides which values to pass. Each child ships its own PR with its own test file.

A three-way split (config keys alone, `select_endpoint` alone, wiring alone) was considered
and rejected. The config keys and the selection rules have no use without the wiring, and
each extra child costs a full cycle.

**#144 overlap (sign-off asked for this to be settled here).** The v6 patch edited
`tests/test_backend.py`. #144 does NOT edit that file: its brief only requires that
`tests/test_backend.py` still passes. #144 edits `render.py`, `proposal.py`,
`_unicode_tables.py` and `tests/test_charsafety.py`. Settled as follows: neither child
touches `render.py`, `proposal.py` or `_unicode_tables.py`. Child-1 does not touch
`tests/test_backend.py`. Child-2 must make ONE edit there:
`test_status_lists_the_loaded_prompt_files` (#143's `tests/test_backend.py:539-559`)
compares the whole `:status` output with `==`, so the two new `:status` lines have to be
appended to its expected list, with `XDG_RUNTIME_DIR` pinned in that test. That is the
only edit allowed in that file. #144 has no hunk there, so there is no shared-file
conflict, and #144 may share a wave with either child.

## Wave sketch

- **Wave A — child-1** (transport + `BackendError` + `Repl._propose` catch).
- **Wave B — child-2** (config keys, `select_endpoint`, `--dev-teacher`, `cli.main`
  wiring, `:status`). `Depends on: child-1`.

Why they stack and don't run in parallel: child-2's `cli.main` builds child-1's
`TeacherClient` and its `Endpoint`, and its criterion (f) sends a real request through the
client over the default socket. Building child-2 alone would mean writing a stand-in client,
which the parent brief forbids. They also both edit `src/nl_shell/teacher_client.py`
(child-1 creates it, child-2 adds `select_endpoint`), so they could not share a wave anyway.
The dependency covers that, so no separate `Conflicts with` is needed.

Both children need #143's accepted patch in the base (`nl_shell.backend`, `proposal`,
`render.escape`, `prompts`, `Repl(..., backend=, prompts=)`). The `Depends on` field can
only name sibling children, so this is not machine-checked here: **before accepting,
confirm #143 is accepted and folded into the integration base** (iteration 6 failed C4
only because base `0771812` lacked `backend.py`/`proposal.py`/`render.py`). #144 may run in
Wave A or B next to either child (no shared files, per the rule above).

<!-- pdca:child child-1 -->
- **Slug:** teacher-client-transport
- **Kind:** enhancement
- **Defect / goal:** After #143, nothing implements `Backend` except `RecordingStub`, so no real model can answer. Add `src/nl_shell/teacher_client.py` with a `TeacherClient` that speaks OpenAI chat-completions (llama.cpp `llama-server` or vLLM, no API key) over the stdlib `http.client` to an `http://` / `https://` URL or to a Unix socket, and returns the raw `choices[0].message.content` string. Add `backend.BackendError` to #143's interface and make `Repl._propose` catch it and show a fixed, escaped reply, so a failing server never crashes the REPL or writes raw server text to the terminal. No config, CLI or endpoint-choice changes (that is child-2).
- **Success criterion:** `python3 -m pytest tests/test_teacher_client.py` passes. The test runs a fake OpenAI-compatible server (stdlib `http.server`) on `127.0.0.1` port 0 and on a Unix socket, builds `TeacherClient(Endpoint(...), timeout_s=…, max_response_bytes=…, model=…)` directly, and covers:
  **(a) request shape.** A valid answer → `complete(messages)` returns the content string. The server saw exactly one `POST /v1/chat/completions`, with `messages` equal to `[{"role": m.role, "content": m.content}, …]` in order, `response_format == {"type": "json_schema", "json_schema": {"name": "proposal_v1", "strict": True, "schema": proposal.SCHEMA}}` (compared to #143's imported object, never a copy), no `Authorization` header, `"model": "m1"` when built with `model="m1"`, and no `model` key when `model=None`. The Unix-socket request sends `Host: localhost`.
  **(b) strict handling.** Each of these raises a `BackendError` subclass with a reason, with no retry and no repair: an HTTP error status; a 3xx (not followed: a second listener named in `Location` gets nothing); a non-JSON body; JSON without a string `choices[0].message.content`; a body over the cap (the client stops reading past it); a server that never answers (`timeout_s=0.5`, server sleeps 2 s, test ends in under 2 s); a slow-drip body (one byte per 0.2 s, `timeout_s=0.5`, gives up in under 2 s); a **chunked slow drip** (`Transfer-Encoding: chunked` plus `Connection: close`, chunk-size line dripped past the deadline, gives up in under 2 s, the iteration-5 finding 2 regression); an `https://127.0.0.1:<port>` URL pointed at the plain-HTTP fake → TLS error and no plain-HTTP request seen. Constructor and edge cases, all of which must raise `BackendError` (never `OverflowError`, `TimeoutError`, `http.client.InvalidURL` or any other exception): `timeout_s=1e10` against a working server either works or raises `BackendError`; `timeout_s=1e-5` → `BackendError`; a URL host with a space or a control character → `BackendError`; a URL with userinfo → refused. `http://[::1]:<port>/` and `http://localhost/`-style URLs with no port use the scheme's default port (test the default-port case by checking the address the client would connect to, not by binding port 80). A URL ending in `/v1` does not produce `/v1/v1/chat/completions` (either stripped or the path is used as the base; test whichever is chosen and document it in the docstring).
  **(c) deadline covers resolve and connect.** For a TCP endpoint the one deadline covers name lookup, connect, send and read. `socket.getaddrinfo` patched to sleep 2 s, `timeout_s=0.5` → `BackendError` in under 2 s (`getaddrinfo` has no timeout of its own, so the lookup must run where the deadline can abandon it; iteration-v6 did this in a worker thread). `socket.getaddrinfo` patched to return several addresses whose connects all hang, `timeout_s=0.5` → `BackendError` in under 2 s in total, not 0.5 s per address. This is binding: do not narrow the docstring or the threat model instead.
  **(d) through `Repl`.** `Repl(read, out, backend=<client>, prompts=<loaded prompts>)` pointed at the fake: a natural-language line → `out` shows #143's framed proposal (`Proposed command (risk: …`). Each `proposal/v1` §Conformance reject case delivered as `message.content` (extra property, missing `risk`, `command` with `reason`, `command` over 2000 code points, invalid JSON, a JSON array) → `out` shows exactly `No usable proposal came back from the model.` and the next line is still read. A client whose Unix socket path does not exist → `out` shows exactly `The model server isn't running (no answer at <socket path>).`, nothing raises, next line read. A server whose status line is `HTTP/1.1 500 \x1b]52;c;ZWNobyBwd25lZA==\x07\x1b[2K\rnl> fake` plus an error body → no ESC, BEL or CR reaches `out`, and `"\x1b" not in` the raised error's reason string either. Any other failure → `out` shows `The model server could not be used: <reason>.`
  Imports of `nl_shell.teacher_client`, `nl_shell.backend`, `nl_shell.proposal` and `nl_shell.prompts` happen inside test functions or fixtures (C4's red leg reverts non-`tests/` files; a module-level import would make the run UNVERIFIABLE, not red). Red with the change reverted: the client import fails and `backend.BackendError` does not exist.
- **Repo + branch target:** eduralph/nl-shell @ main, built on the integration base with #143's accepted patch folded in (verify via `$PDCA_VERIFY_BASE`). Do not schedule if #143 is not in the base. Use #143's names as they landed; no stand-ins (no schema copy, no own escape function, no own backend protocol).
- **Reproduction:** n/a (new functionality). Today, after #143, `Repl` built without a backend answers every request with #143's `NO_BACKEND` reply, and no module can talk to a model server.
- **Scope (one logical fix) / out of scope:** (1) New `src/nl_shell/teacher_client.py`: frozen dataclass `Endpoint(kind: "unix" | "http" | "https", address: str | None)` (`address=None` means "no default socket"; `complete` then raises the "isn't running" error), `MAX_RESPONSE_BYTES = 64 * 1024`, `TeacherClient(endpoint, *, timeout_s, max_response_bytes=MAX_RESPONSE_BYTES, model=None)` whose `complete(messages) -> str` mirrors `RecordingStub.complete` (same signature, raw text out, no parsing). An `http.client.HTTPConnection` subclass whose `connect` opens `AF_UNIX`. `http.client`, not `urllib` (ignores `HTTP(S)_PROXY`, never follows redirects). TLS: certificate and hostname checks on, no plain-HTTP fallback. One **total** deadline tracked with `time.monotonic()`: build the connection, connect, send and read **all inside the `try`** that maps errors to `BackendError`; keep the deadline enforced on the response's socket after `http.client` moves it off the connection; bound connect to the time left; clamp the value passed to `settimeout`/timers so large values cannot overflow. Read in chunks, check the cap and the deadline per chunk; check the redirect status before reading the body. (2) `src/nl_shell/backend.py`: add `class BackendError(Exception)` only (if #143 already added it on the base, use it and skip this). The client's errors subclass it. Server text in the reason (reason phrase, body excerpt, `{exc}` text) goes through `render.escape` when the error is built. (3) `src/nl_shell/repl.py` `Repl._propose`: catch `BackendError` around `self._backend.complete(...)` and return the fixed reply (exact texts in the criterion); the REPL keeps running. (4) `.oss-scanner/threat_model.md` item 11: only if the connect deadline is narrowed (criterion (c)). Out of scope: `config.py`, `cli.py`, endpoint selection, `--dev-teacher`, `:status`, and the `tests/test_cli.py` / `tests/test_targets.py` files (all child-2); starting `llama-server` (#48); retries, streaming, `/health`, the ADR-0018 §7 unavailable state and non-blocking requests (deferred by Plan decision); API keys; any change to `proposal.py`, `render.py`, `_unicode_tables.py` or **`tests/test_backend.py`** (#143/#144 own them; put `BackendError` tests in this child's test file).
- **External dependencies:** `pyyaml`
- **Test file:** `tests/test_teacher_client.py` (new)
- **Difficulty:** medium
- **Falsifiability:** RED on the shipped C4 gate (`engine/scripts/run-verify.sh`, plain pytest on the host via `.venv`): it reverts every non-`tests/` file and re-runs `tests/test_teacher_client.py`. With the change reverted, `nl_shell.teacher_client` does not exist (each in-function import fails) and `backend.BackendError` does not exist, so tests run and fail. Everything runs in-process on loopback or a Unix socket: no network, model or GPU. Precondition: #143's accepted patch must be in the verify base, or the test cannot import `nl_shell.backend` / `proposal` / `prompts` even when green.
- **Invariant to restore:** (1) No text that came from the model server reaches the terminal unescaped, including HTTP reason phrases, error bodies and exception text (threat model "Output rendering is filtered everywhere", `.oss-scanner/threat_model.md:131`). (2) Every model answer goes through #143's one strict parser; the client returns raw content and never parses, repairs or retries (ADR-0018 §3). (3) A failing or hostile server, or any `timeout_s` value the client accepts, never ends the REPL session: every failure becomes one fixed reply, and no request outlives its deadline.
- **Surfaces:** data
- **Disposition hint:** new-feature
- **Prior-art check (triage cycles):** `git -C ../nl-shell log --all --oneline -- src/nl_shell/teacher_client.py tests/test_teacher_client.py` → only the local WIP folds of #77 itself; nothing on main. Earlier attempts: parent #77 iterations v1–v6 (never published). v4–v6 hold a reviewed transport; sign-off asked to keep that design and fix the listed crashes.
- **Design notes carried from the parent:** `tests/conftest.py` does not isolate `XDG_RUNTIME_DIR`; set it with `monkeypatch` where a default-socket path is built. Unix socket paths must fit about 107 bytes: use `tempfile.mkdtemp(prefix="nls-")`, removed in teardown. Shut down every server thread in teardown; every network wait in tests has a short timeout. Do not mark the tests `teacher`. The prompts for (d) come from #143's `prompts.load` on a target folder with a valid `prompts/prompts.yaml` (copy `targets/ubuntu-26.04/prompts/prompts.yaml` or write a minimal one). Cite `path:line` on the folded base for every change: `backend.py` (`Backend`, `RecordingStub`), `repl.py` (`Repl._propose`), `proposal.py` (`SCHEMA`), `render.py` (`escape`) — re-derive the lines, the parent's numbers are hints. Prior attempt to reuse, not redo: `results/issue_77/iteration-v6/patch.diff` and `patch-77-on-143.diff` hold a mostly sound transport that sign-off reviewed; fix the listed crashes rather than rewriting the design.
- **Depends on:**
- **Conflicts with:**
<!-- pdca:end child-1 -->

<!-- pdca:child child-2 -->
- **Slug:** teacher-endpoint-dev-teacher-flag
- **Kind:** enhancement
- **Defect / goal:** After child-1 a working `TeacherClient` exists, but `cli.main` still builds the interactive `Repl` with no backend, so the REPL never proposes. Wire it in, under the endpoint rules of ADR-0003 and ADR-0020 §3: by default nl-shell talks only to `$XDG_RUNTIME_DIR/nl-shell/model.sock` over `AF_UNIX` and opens no TCP connection. Any other endpoint, loopback TCP included, needs `--dev-teacher` for that session. A `teacher_url` in `config.toml` without the flag is refused with a stderr message. A non-loopback `http://` URL gets a warning to use an SSH tunnel or TLS. The request deadline comes from `[model] timeout_s` (ADR-0018 §7, ADR-0020 §5, default 10). `:status` names the endpoint and backend kind.
- **Success criterion:** `python3 -m pytest tests/test_teacher_endpoint.py` passes, covering:
  **(a) config.** `config.load` on a file without `[model]` → `model_timeout_s == 10`; `[model]\ntimeout_s = 0.5` → `0.5`; a non-number, a bool, a value <= 0, and a value above the chosen upper bound (e.g. `1e10`; name the bound as a constant) → `ConfigError`. `teacher_url` and `teacher_model` load as strings and a non-string raises `ConfigError` (same style as `target`).
  **(b) endpoint rules**, by calling `teacher_client.select_endpoint(dev_teacher, teacher_url, runtime_dir)` directly (nothing connects): no flag and no URL → `Endpoint("unix", "<runtime_dir>/nl-shell/model.sock")`, no messages; `runtime_dir` unset, empty or relative → `Endpoint("unix", None)` (no guess at `/run/user/<uid>`); `teacher_url` without the flag → default socket plus a refusal message; same URL with `dev_teacher=True` → that URL; `dev_teacher="<URL>"` → that URL, winning over `teacher_url`; `dev_teacher=True` with no `teacher_url` → a clear message and the default socket (or an argparse error — pick one and test it); non-loopback `http://` with the flag → the warning (loopback = `localhost`, `127.0.0.0/8`, `::1`; any other hostname counts as non-loopback, no DNS lookup); loopback `http://` and any `https://` → no warning.
  **(c) through `cli.main` with `capsys`:** the refusal reaches stderr once, and the warning reaches stderr once. `cli.main([... "--dev-teacher" ...])` parses (today argparse exits 2).
  **(d) timeout reaches the client:** `cli.main` with `[model] timeout_s = 0.5`, a slow-drip fake server on the default socket and one natural-language line → `out` shows the `could not be used` reply and the run ends in under 2 s.
  **(e) `:status`:** `cli.main` builds `:status` lines naming the endpoint in use and the backend kind, captured the way `tests/test_cli.py:29-46` captures `status_lines`.
  **(f) no TCP on the default path:** `socket.socket.connect` and `socket.create_connection` patched to record calls; `cli.main([], targets_root=…, os_release_paths=[…])` with a matching os-release, a target with a valid `prompts/prompts.yaml`, `teacher_url = "http://127.0.0.1:<port>"` in `config.toml`, no flag, a fake server at that URL, a fake server on the default socket, and scripted input of one natural-language line then EOF → zero `AF_INET`/`AF_INET6` connects, **exactly one** `AF_UNIX` connect, to `$XDG_RUNTIME_DIR/nl-shell/model.sock`, and the server at the URL received nothing. Red if selection leaks the config URL, and red if the REPL is not wired to the client.
  Import `nl_shell.teacher_client` and `nl_shell.prompts` inside test functions or fixtures; at module level only the stdlib, pytest, `nl_shell.cli`, `nl_shell.config` and `nl_shell.repl.Repl`. Red with the change reverted: `select_endpoint` does not exist, `--dev-teacher` exits 2, `config.Config` has no `model_timeout_s`, and (f) sees zero `AF_UNIX` connects and #143's `NO_BACKEND` reply. The red proof must come from this file's own assertions, not from `:status` churn in `tests/test_cli.py` / `tests/test_targets.py`.
- **Repo + branch target:** eduralph/nl-shell @ main, built on the integration base with #143's accepted patch and child-1's accepted patch folded in (verify via `$PDCA_VERIFY_BASE`). Use child-1's names (`TeacherClient`, `Endpoint`, `MAX_RESPONSE_BYTES`, `backend.BackendError`) as they landed.
- **Reproduction:** `nl-shell --dev-teacher` exits 2 (unknown argument). With child-1 in the base, the interactive REPL still answers every request with #143's `NO_BACKEND` reply, because `cli.main` passes `prompts=` but no `backend=` to `Repl.interactive`.
- **Scope (one logical fix) / out of scope:** (1) `src/nl_shell/config.py`: `teacher_url: str | None`, `teacher_model: str | None` (type-checked like `target`), and `model_timeout_s: float = 10` from `[model] timeout_s` (int or float, > 0 and <= a named upper bound; bool and other types → `ConfigError`). (2) `src/nl_shell/teacher_client.py`: add the pure function `select_endpoint(dev_teacher: str | bool | None, teacher_url: str | None, runtime_dir: str | None) -> tuple[Endpoint, list[str]]` returning child-1's `Endpoint` and the refusal/warning texts. It opens no connection and does not change `TeacherClient`. (3) `src/nl_shell/cli.py`: `--dev-teacher [URL]` (`nargs="?"`, `const=True`); call `select_endpoint` with the flag, `config.teacher_url` and `os.environ.get("XDG_RUNTIME_DIR")`; write each message to stderr; build `TeacherClient(endpoint, timeout_s=config.model_timeout_s, model=config.teacher_model)` and pass it as `backend=` to `Repl.interactive` (replacing #143's interactive no-backend default; `NO_BACKEND` stays for a `Repl` built without a backend); append two `:status` lines (endpoint in use, backend kind) with the other session lines (ADR-0020 §4). (4) `tests/test_cli.py` / `tests/test_targets.py`: update only where the two new `:status` lines change what they pin. `tests/test_backend.py`: ONE edit only, in `test_status_lists_the_loaded_prompt_files` (#143's `:539-559`, which pins the full `:status` output with `==`): pin `XDG_RUNTIME_DIR` in that test and append the two new lines to its expected list. Nothing else in that file. Out of scope: any transport, deadline or error-handling change in `TeacherClient` (child-1 owns it; if a transport bug shows up, report it, don't fix it here); `backend.py`, `repl.py`; starting `llama-server` (#48); retries, `/health`, the unavailable state, `model.cpu_fallback`, non-blocking requests (deferred by Plan decision); API keys; `proposal.py`, `render.py`, `_unicode_tables.py` (#143/#144), and any `tests/test_backend.py` change beyond the one `:status` pin above; the architecture doc 05 table.
- **External dependencies:** `pyyaml`
- **Test file:** `tests/test_teacher_endpoint.py` (new)
- **Difficulty:** medium
- **Falsifiability:** RED on the shipped C4 gate (`engine/scripts/run-verify.sh`, plain pytest via `.venv`; reverts every non-`tests/` file, re-runs `tests/test_teacher_endpoint.py`). With the change reverted: `teacher_client.select_endpoint` does not exist, `cli.main([... "--dev-teacher" ...])` exits 2 from argparse, `Config` has no `model_timeout_s`, and in (f) `cli.main` builds `Repl` with no backend, so there are zero `AF_UNIX` connects. Tests run and fail. All in-process; the real LAN teacher check is manual (the issue says so) and not part of the criterion. Precondition: #143 and child-1 are in the verify base.
- **Invariant to restore:** With no `--dev-teacher`, nl-shell opens no TCP connection: the only model connection is `AF_UNIX` to `$XDG_RUNTIME_DIR/nl-shell/model.sock` (ADR-0003; ADR-0020 §3, `docs/design/adr/0020-configuration-and-file-locations.md:32-35`; threat model "Locally complete … no outbound connection in the default config", `.oss-scanner/threat_model.md:143`; the config exception "refused without `--dev-teacher`", `:101`).
- **Surfaces:** data
- **Disposition hint:** new-feature
- **Prior-art check (triage cycles):** `git -C ../nl-shell log origin/main --oneline -- src/nl_shell/cli.py src/nl_shell/config.py` → `4c755f2` (#92), `89373a4` (#14), router; none adds an endpoint or a teacher flag. Earlier attempts: parent #77 iterations v1–v6 (never published).
- **Design notes carried from the parent:** Loopback TCP also needs `--dev-teacher` (ADR-0020 §3 `docs/design/adr/0020-configuration-and-file-locations.md:32-34`, chosen over ADR-0018 §5's looser wording; confirmed by the human at Plan). `teacher_model` is kept because vLLM rejects a request without a model name. `tests/conftest.py` does not isolate `XDG_RUNTIME_DIR`: every test touching the default socket sets it with `monkeypatch`, to a short dir from `tempfile.mkdtemp(prefix="nls-")` removed in teardown. Shut down every server thread in teardown. Do not mark tests `teacher`. Cite `path:line` on the folded base for every change: the argument parser and the `config.load` and `Repl.interactive(...)` calls in `cli.py`, `Config` / `load` in `config.py`, `Repl.interactive` in `repl.py` — re-derive the lines; the parent's numbers (`cli.py:27-33,41,65`, `config.py:29,60-63`) are hints.
- **Depends on:** child-1
- **Conflicts with:**
<!-- pdca:end child-2 -->

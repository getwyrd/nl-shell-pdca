# Build notes — issue 151 (teacher-client-transport)

Target: eduralph/nl-shell, worktree `$PDCA_WORKTREE` at `cefb359` (`pdca-integrate: issue_143`,
stack base `pdca-integration/main-r2546dbf9639f`). #143 is in the base: `backend.py`
(`Backend`, `RecordingStub`), `proposal.SCHEMA` (`src/nl_shell/proposal.py:18`),
`render.escape` (`src/nl_shell/render.py:64`), `prompts.load` / `Message`
(`src/nl_shell/prompts.py:89`, `:55`), `Repl._propose` (`src/nl_shell/repl.py:142` on the base).
Line numbers below are on the patched tree.

## What changed

1. **`src/nl_shell/backend.py:28`** — `class BackendError(Exception)` only, plus a docstring
   paragraph (`:9-11`) saying the REPL shows one reply for it and that backends escape server
   text. No other symbol added.
2. **`src/nl_shell/repl.py`**
   - `:39-43` `SERVER_NOT_RUNNING` / `SERVER_UNUSABLE`, with the "interim until ADR-0018 §7"
     comment the brief asks for.
   - `:74-80` `backend_failure(exc)`: `ServerNotRunning` → "isn't running (…)", anything else
     → "could not be used: <reason>." It imports `teacher_client.ServerNotRunning` lazily, so
     `backend.py` stays at "add `BackendError` only".
   - `:162-169` `_propose` wraps only `self._backend.complete(messages)` in
     `try/except BackendError`. The parse path is unchanged, so invalid proposals still go
     through `show_proposal` → `NO_USABLE_PROPOSAL`.
3. **`src/nl_shell/teacher_client.py`** (new)
   - `Endpoint` `:74`, `HttpTarget` `:82`, `MAX_RESPONSE_BYTES` `:59`, `MAX_WAIT_S` `:62`.
   - Error classes `:91-121`, all subclasses of `BackendError`.
   - `http_target()` `:134`: refuses non-ASCII / space / control characters in the **raw**
     URL (`:139`). This check runs *before* `urlsplit`, because `urlsplit` silently deletes
     TAB/CR/LF, so `http://bad\nhost/` would otherwise turn into a valid host. It also refuses
     userinfo (`:150`), a query or fragment, and a scheme that is not the endpoint kind. Missing
     port → 80/443. A trailing `/v1` is dropped and any other base path is kept (`:158`); this is
     documented in the module docstring.
   - `_Exchange` `:173`: one deadline from `time.monotonic()`, the request's sockets, and
     `abandon()` (`:210`), which calls `shutdown(SHUT_RDWR)` on every socket to wake a blocked
     read. It never `close()`s from the other thread, because that would race fd reuse.
   - `_UnixConnection` `:231` (an `AF_UNIX` connect; Host is `localhost`) and `_TcpConnection`
     `:247`. The latter runs its own `socket.getaddrinfo` + per-address connect loop (`:269`),
     each connect bounded by the time left, then TLS via `ssl.create_default_context()`
     (`:261`) with `CERT_REQUIRED` + `check_hostname` set explicitly.
   - `TeacherClient.complete` `:341`: the whole exchange (URL parse, connection build,
     lookup, connect, handshake, send, read) runs in a daemon worker thread. The caller waits
     with `done.wait(clamped time left)` in a loop (`:360`). At the deadline it calls
     `abandon()` and raises `DeadlineExceeded` (`:366`), including on Ctrl-C (`finally`).
   - The worker also re-arms each socket's timeout to the time left before every blocking
     step (`arm()` `:201`) and reads the body with `read1` per chunk (`:453`), checking both
     the cap and the deadline each time. A 3xx is refused before any body read (`:424`).
     `Content-Length` over the cap is refused up front.
   - `_as_backend_error` `:372` maps every `Exception` from the worker to a `BackendError`.
     Server-derived text always passes through `render.escape` (`_quote` `:123`,
     `_describe` `:128`) when the error is built.

## Why this design (and what I ruled out)

- **The worker thread plus caller-side deadline is what removes the cause** of crashes (2)
  and (3) in the brief. `getaddrinfo` has no timeout, and `http.client` reads the status
  line, headers and chunk-size lines through a buffered `readline` that calls `recv` many
  times. A per-`recv` socket timeout cannot bound a drip, and once `http.client` hands the
  socket to the response, nothing on the connection object reaches it any more. Running the
  exchange in a worker and waiting with the deadline bounds all of those in one place.
  The mutation check below shows that four legs depend on exactly this.
- **Rejected: socket timeouts only, re-armed per call.** This bounds the
  "never answers" and plain body-drip cases. The mutant run below shows it does **not**
  bound the chunked drip, a status-line drip, a hanging DNS lookup or several hanging
  connects (each took 5.0 s against the 2 s bound).
- **Rejected: a `threading.Timer` that shuts the socket down at the deadline, with no
  worker.** It still cannot abandon `getaddrinfo` (no socket exists yet), so DNS would need
  a separate thread anyway. That gives two mechanisms instead of one.
- **The connection is built inside the worker**, so `InvalidURL`, `TimeoutError` (1e-5) and
  `OverflowError` cannot escape before the error-mapping code (crashes 4 and 5).
  `OverflowError` is removed at the cause: every wait goes through `_wait_for`, which clamps
  to `[0, MAX_WAIT_S]`. The clamp also stops a negative remainder from reaching
  `Event.wait` or `settimeout` (`settimeout(0)` would make the socket non-blocking). The
  deadline itself is not clamped. `timeout_s=1e10` returns the content (tested).
- **URL validation happens in `complete`, not the constructor.** A bad URL from config then
  becomes a REPL reply instead of a startup crash. The constructor raises `BadEndpoint`
  only for an unknown kind, a non-positive / non-finite `timeout_s`, or a bad cap.
- **TCP `ConnectionRefusedError` also maps to `ServerNotRunning`** ("no answer at <url>").
  The brief pins the text only for the Unix-socket cases; I applied the same wording to a
  refused TCP connect because it means the same thing. Child-2 / ADR-0018 §7 can change it.
- **Abandoned worker threads** can outlive the call: up to the hang itself (e.g. a stuck
  `getaddrinfo`). They are daemon threads, hold no REPL state, and the caller never reads
  their result. This is the cost of abandoning a call that has no timeout of its own.

## Tests (`tests/test_teacher_client.py`, 72 cases)

Fake server: `socketserver` TCP / Unix-stream servers with a `BaseHTTPRequestHandler`
that writes raw bytes, so tests control the status line, headers and pace. Every nl_shell
import is inside a test or fixture. Unix socket dirs come from `tempfile.mkdtemp(prefix="nls-")`
and are removed in teardown. Server threads are stopped through a `stop` event plus
`shutdown()`, and `block_on_close = False`. No test is marked `teacher`.
The TLS context is captured by wrapping `ssl.create_default_context` with `monkeypatch`
(documented in the test module docstring).

Coverage by criterion item:
- (a) request shape (TCP, `model="m1"`, `model=None`), Unix `Host: localhost`, `/v1` suffix
  variants, base path kept.
- (b) 500, 307 with a second listener that sees nothing, non-JSON, 10 bad-content shapes,
  endless body over the cap (a client that kept reading would get `DeadlineExceeded`
  instead of `ResponseTooLarge`), `Content-Length` over the cap, body exactly at the cap,
  never answers / body drip / chunked drip / status-line drip (5 s stall vs 2 s bound),
  https→plain fake (TLS error, no request seen, context is `CERT_REQUIRED` +
  `check_hostname`), `1e10` returns content, `1e-5` fails, bad timeouts, 13 bad URLs (no
  lookup happens), userinfo never reaches the server, default ports checked through
  `http_target` **and** through the `(host, port)` passed to `getaddrinfo`, a live `[::1]:port`
  request (skips if the host has no IPv6 loopback).
- (c) `getaddrinfo` sleeping 5 s; four addresses whose patched `connect` sleeps 5 s and ignores
  the socket timeout; and an unpatched real hang (a full accept queue on `listen(0)`; skips if
  the kernel never fills it — it ran here).
- (d) framed proposal through `Repl`; the six §Conformance rejects, each followed by a valid
  answer to prove the next line is read; missing socket; `Endpoint("unix", None)`; a stub
  `BackendError("boom")` with no `teacher_client` import; the hostile status line (no ESC /
  BEL / CR in the reason or in `out`); any other failure → "could not be used: <reason>.";
  refused TCP.

## Refute-your-own-test (forced)

- **(a) Genuine red? Yes.** `engine/scripts/run-verify.sh` (the C4 gate, run with
  `PDCA_BUNDLE`/`PDCA_WORKTREE` set) reverted every non-`tests/` hunk: `ran 72, failed 72,
  import/collection errors 0` → `PDCA-EVIDENCE: C4 PASS — red without the fix (72 of 72
  failed), green with it`. Narrower reverts:
  - Only the `repl.py` hunk reverted (`git apply -R --include=src/nl_shell/repl.py`):
    `test_repl_catches_any_backend_error` FAILS (the `BackendError` escapes `Repl.run`). That
    is the brief's "fails if only the catch is reverted" leg.
  - Mutant: caller waits with `done.wait()` (no deadline) at `teacher_client.py:360`:
    `test_a_chunked_slow_drip`, `test_a_slow_drip_status_line`,
    `test_a_hanging_name_lookup_is_abandoned`, `test_hanging_connects_share_one_deadline` all
    FAIL (5.0 s vs 2 s). The tree was restored and `git diff HEAD` compared byte-equal to
    `patch.diff`.
- **(b) Production path? Yes.** Every leg constructs the real
  `teacher_client.TeacherClient` / `Endpoint` and the real `Repl` with
  `prompts.load(...)`. Nothing is mocked except the network fault being injected
  (`getaddrinfo` / `socket.socket.connect` in (c), and `ssl.create_default_context` wrapped
  to *record* the real context it returns). The stub-backend leg uses a test-defined backend
  on purpose, as the brief requires.
- **(c) Fixture includes the fault? Yes.** The servers actually stall, drip, send an endless
  body, send the hostile status line and redirect to a live second listener. The https leg
  talks to a real plain-HTTP socket. The missing-socket leg points at a path that does not
  exist. One connect-hang leg uses a real full accept queue, not a patch.

## Runs

- New file alone: `72 passed in ~10.4 s`.
- `engine/scripts/run-verify.sh`: C4 PASS (above).
- `engine/scripts/run-suite.sh` (T3): `553 passed, 1 warning` → `T3 PASS`. The warning
  (`forkpty()` in a multi-threaded process) is raised in
  `tests/test_session.py::test_busy_python_thread_stays_healthy`. That test starts its own
  thread and runs before this file in collection order, so it is not caused by this patch.

## Commit-readiness

The target configures no formatter or commit hook: there is no `.pre-commit-config.yaml`,
no `[tool.ruff]` / `[tool.black]` in `pyproject.toml`, and `.github/workflows/tests.yml` runs
only `pytest`. `black` and `ruff` are not installed in `.venv`. I kept to the repo's style
(about 88 columns). A few lines run to 92, and the base already has lines up to 108
(`git show HEAD:` scan).

## Housekeeping note

While preparing the mutation check I ran `cp src/nl_shell/teacher_client.py
/tmp/nls151-tc.bak`. That is outside the harness roots and was never used; the mutation was
done and reversed in place instead. Per the no-`rm` rule I left it. It is a stray copy of
the new module that the human may delete.

## Out of scope, left alone

`config.py`, `cli.py`, endpoint selection, `tests/test_backend.py`, `proposal.py`,
`render.py`, `pyproject.toml`, docs and the threat model. `NO_BACKEND`'s text (still mentions
#77) is untouched: child-2 wires the client in and owns that reply.

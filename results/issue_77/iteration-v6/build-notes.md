# Build notes — issue 77, iteration 6

## What this iteration is

The iteration-5 carry-forward said: keep the round-4/5 design, fix three live findings
(plus one nice-to-have), and rebuild only #77's part on the #143 base. So this patch is
`patch-77-on-143.diff` (the v5 #77 part) plus the fixes below. Nothing else in the design
changed.

## Base

The worktree HEAD was `0771812` (`pdca-integration/main-r2546dbf9639f`), which does **not**
contain #143 (no `backend.py` / `proposal.py`). I applied #143's accepted patch
(`results/issue_143/patch.diff`, sign-off outcome `merged-wider`, 2026-10-15) on top and
committed it as a scratch base, `885c2d9`. `patch.diff` is the diff from that base, so it
holds #77's part only (files: `.oss-scanner/threat_model.md`, `backend.py`, `cli.py`,
`config.py`, `repl.py`, `teacher_client.py` (new), and four test files). It must be
applied on main + #143, which is what `$PDCA_VERIFY_BASE` gives the C4 gate.

Scratch commits left in the worktree: `885c2d9` (#143 folded), `01a8bd4` (v5 #77 part),
and a final `WIP: #77 v6` commit. The harness owns the worktree; I removed nothing.

Line numbers below are on main + #143 + this patch (the worktree HEAD).

## Fix 1 — huge `[model] timeout_s` crashed the REPL (OverflowError)

Cause: `config.load` accepted any finite number > 0, and `threading.Timer` /
`socket.settimeout` raise `OverflowError` above about 9.2e9 s. That error is not an
`OSError`, so it escaped `_exchange` and killed the REPL.

Fix (both places, so neither path can reach the overflow):
- `src/nl_shell/config.py:26-28` — `MAX_MODEL_TIMEOUT_S = 3600.0`.
- `src/nl_shell/config.py:93-100` — `valid_timeout()`: number, not bool, finite,
  `0 < x <= 3600`. `load` uses it (`config.py:79-84`) and raises `ConfigError`, which
  `cli.main` already turns into a one-line error and exit 1.
- `src/nl_shell/teacher_client.py` `TeacherClient.__init__` — the same check; a bad
  `timeout_s` raises `ValueError` at construction, before any timer exists.

Why 3600: an hour is far longer than anyone waits at a prompt, and five orders of magnitude
under the overflow. It is a new bound the brief did not name (the brief says "> 0"); the
sign-off asked for "an upper bound". The human can pick another number at sign-off.

Rejected: only catching `OverflowError` in `_exchange`. It would turn a config mistake into a
"could not be used" reply on every request instead of one clear start-up error, and the
`Timer` is created in `complete()` outside `_exchange`, so the catch would need a second
site.

Tests: `test_model_timeout_from_config` now adds `3600` (accepted), `3600.5` and `1e10`
(refused); `test_huge_timeout_is_refused_by_the_client`; `test_cli_refuses_a_huge_timeout`
(through `cli.main`: exit 1, `timeout_s` on stderr, the REPL is never built). On the v5
code the CLI test failed with the real `OverflowError`.

## Fix 2 — the total deadline was lost once http.client gave the socket to the response

Cause: on `Connection: close` (or HTTP/1.0), `HTTPConnection.getresponse()` calls
`self.close()`, which sets `conn.sock = None`; the response keeps reading from its own
`makefile()` of the socket. v5's `_cut` and `_tick` only looked at `conn.sock`, so after
`getresponse` the timer cut nothing and `settimeout` set nothing. A body read through
`read1` with `Content-Length` still stopped (one recv per call, deadline checked between
calls), which is why v5's slow-drip test was green. But chunked encoding reads the
chunk-size line with `readline()`, which loops over many `recv`s inside one `read1`, each
with the full per-read timeout. A server dripping one chunk-size byte every 0.2 s ran for
20 s with `timeout_s=0.5`.

Fix: `teacher_client.py` `class _Watch` holds the deadline and the socket the request is
using *right now*, set by `track()` from the connection's own `connect()`. The deadline
timer calls `_Watch.cut()`, which shuts that socket down (base-class `socket.shutdown`, so
an `SSLSocket` is cut at the fd), whatever object http.client has moved it to. `tick()`
sets the per-read timeout to what is left, on the same socket. `release()` is called in
`complete()`'s `finally` before `conn.close()`, under the same lock as `cut()`, so a timer
that fires late can't shut down a closed (and possibly reused) fd. `tick()` skips a socket
whose `fileno()` is -1: the response closes the socket itself once it has read the whole
body (I hit `EBADF` there on the first run, `teacher_client.py` `_Watch.tick`).

Test: `test_chunk_size_drip_after_connection_close_hits_the_deadline[tcp|unix]` — a real
fake server sends `HTTP/1.1 200`, `Transfer-Encoding: chunked`, `Connection: close`, then
a `0` every 0.2 s on the chunk-size line, never ending it. Client `timeout_s=0.5`; must end
in under 2 s with the "within 0.5 s" reason. On v5: took 20 s on each transport (red).

## Fix 3 — the deadline did not cover DNS and connect on the `--dev-teacher` TCP path

Cause: v5 used `http.client`'s default `socket.create_connection`, which resolves without
a timeout and gives each resolved address the full `timeout_s`.

I chose "bound it" over "narrow the docstring", because the sign-off listed both and
bounding keeps the one-deadline promise true everywhere. Cost: about 45 lines
(`_resolve`, `_connect_tcp`, two small connection subclasses).

- `teacher_client.py` `_resolve()` — `getaddrinfo` has no timeout, so it runs in a daemon
  thread joined with `watch.left()`; if the deadline passes first, `TimeoutError` (the
  lookup thread is abandoned; it is a daemon and holds nothing).
- `_connect_tcp()` — resolves **once**, then tries each address with
  `settimeout(watch.left())`; once time is up the next `left()` raises `TimeoutError`.
  Sets `TCP_NODELAY` like `HTTPConnection.connect` does.
- `_HTTPConnection.connect` uses it. `_HTTPSConnection.connect` uses it, then wraps with
  `do_handshake_on_connect=False`, tracks the `SSLSocket` in the watch, and only then runs
  `do_handshake()`, so a handshake that drips is also cut by the timer. The TLS context is
  `ssl.create_default_context()` (certificate and host-name checks on), kept on the
  instance as `_tls` so I don't read http.client's private `_context`.
- `_UnixHTTPConnection.connect` tracks its socket the same way.

Tests:
- `test_dns_lookup_is_inside_the_deadline` — `socket.getaddrinfo` patched to block 3 s
  then fail; `timeout_s=0.5` must end in under 2 s with "within 0.5 s". v5: 3 s (red).
- `test_connect_attempts_share_the_deadline` — a real loopback listener with
  `listen(0)` and its one backlog slot already taken, so a further `connect` really hangs
  (kernel drops the SYN; I checked this on this host first: 0.3 s timeouts, every time).
  `getaddrinfo` patched to return that address three times. Must end under 1.2 s. v5:
  1.50 s (three attempts × 0.5 s, red). It also asserts one lookup.

Neither test touches the network: the DNS test never resolves anything, the connect test
only connects to 127.0.0.1.

## Nice-to-have — trailing `/v1` in the URL

`teacher_client.py` `chat_path()`: a base path ending in `/v1` (or `/v1/`) has that part
dropped before `/v1/chat/completions` is added, since llama-server and vLLM both print
`http://host:port/v1` as their API base. The `--dev-teacher` help text in `cli.py` now
says the URL is the base URL with an example of each form.
Test: `test_trailing_v1_in_the_url_is_not_doubled` (v5: 404 → red).

## Threat model

`.oss-scanner/threat_model.md` item 11 now says the deadline is at most 3600 s and covers
DNS lookup, connect, TLS handshake, send and read.

## Commit-readiness

The target has no formatter or commit hooks: no pre-commit config, no ruff/black/flake8
settings in `pyproject.toml`, `core.hooksPath` unset. CI (`.github/workflows/`) runs
`python -m pytest`, `scripts/docs_checks.py` and `scripts/docs_links.py`. Full suite through
`engine/scripts/run-suite.sh`: **448 passed**. `scripts/docs_links.py`: 0 broken. No unused
imports in the touched modules (checked by hand; no pyflakes/ruff installed).

## Line index — `src/nl_shell/teacher_client.py` (worktree HEAD)

`_Watch` :162 (`cut` :184, `release` :190, `tick` :202, closed-socket skip :206-207);
`_shutdown` :211; `_resolve` :220; `_connect_tcp` :241; `_UnixHTTPConnection` :263;
`_HTTPConnection` :284; `_HTTPSConnection` :295 (handshake after tracking :317);
`TeacherClient` :320 (timeout check :333); `chat_path` :453; `_read` :463.

## Self-refutation (the three questions)

- **(a) Genuine red?** Yes. Two reverts:
  1. The C4 shape: every non-`tests/` file put back to the #143 base and
     `teacher_client.py` moved aside → `38 failed in 1.47s`, no collection error (all
     #77/#143 imports are inside test functions). Restored → `38 passed`.
  2. The iteration delta: the 8 new tests against the v5 code (`01a8bd4`) → all 8 failed,
     each for the reason sign-off named (20 s chunk drip on tcp and unix, 3 s DNS, 1.50 s
     connect, `OverflowError` through `cli.main`, no `ValueError`, `/v1/v1/...` 404, `1e10`
     accepted).
- **(b) Production path?** Yes. Every test drives `nl_shell.teacher_client.TeacherClient`,
  `config.load` or `cli.main` itself, against real sockets. The only patches are
  `socket.getaddrinfo` (DNS and connect tests, so nothing resolves off-host) and the
  recording wrappers in (f), which call through to the real `connect`.
- **(c) Fixture includes the fault?** Yes. The chunk-drip server really sends
  `Connection: close` + chunked and drips past the deadline; the connect test uses a
  listener whose backlog is really full, so the kernel really hangs the connect; the DNS
  fake really blocks for 3 s. Each was measured going over time on v5.

## Open points for the human

- `tests/test_backend.py` is touched (v5 did the same, kept unchanged here): its
  `test_status_lists_the_loaded_prompt_files` pins the exact `:status` output, so the two
  new model lines must be added there or the suite goes red. The brief lists
  `tests/test_backend.py` among #144's files that "this bundle must not edit", while also
  saying to update `:status`-pinning tests. These two rules conflict for this one test; the
  change is 8 lines and only appends the two lines plus pins `XDG_RUNTIME_DIR`. If #144
  lands first, expect a trivial merge.
- The 3600 s cap is my number (see Fix 1).
- The request still blocks the prompt for up to `model.timeout_s` (a recorded Plan
  decision, not changed here).

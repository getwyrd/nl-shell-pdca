## Summary
**User impact:** nl-shell can't answer a plain-English request with a real model yet. It can build the request and check a proposal, but the only thing that can send a request is a test stand-in. Without a way to reach a local model server (llama.cpp or vLLM), the natural-language half of the shell doesn't work for users.

This PR adds the client that sends the request to a local model server and returns its answer. If that server is down, slow, broken or hostile, the shell shows one short message and keeps running. It never crashes, and the server can't write its own text to your terminal.

Reported in [#151](https://github.com/eduralph/nl-shell/issues/151).

**Depends on #153** (#143: prompts, the proposal parser, the escaping helper and the backend interface). This branch is built on top of it, so review or merge #153 first.

## What to look at
- **The new client** (`src/nl_shell/teacher_client.py`). It sends one chat request to an OpenAI-compatible server over a Unix socket or an `http://` / `https://` URL, and it gives up when one overall time limit runs out.
- **The REPL's error handling** (`src/nl_shell/repl.py`, a few lines). When the client fails, the user sees one fixed line, and the next prompt still works.

To try it, run `python3 -m pytest tests/test_teacher_client.py`. The tests start fake servers on loopback and on a Unix socket: one that answers correctly, one that never answers, one that drips a byte at a time, one that redirects, one that sends huge or broken bodies, and one whose status line holds terminal escape codes. They need no real model, network or GPU. Nothing in the CLI uses the client yet. A follow-up will pick the endpoint from config.

## Root cause
Before this change, `Backend` had no real implementation, only `RecordingStub`. The REPL also had no way to report a backend failure: any exception from `complete()` would have ended the session.

## Fix
- `src/nl_shell/backend.py:28`: new `BackendError`, the one error type a backend raises when it can't get an answer.
- `src/nl_shell/teacher_client.py` (new):
  - `Endpoint` holds a Unix path or an http(s) URL. `TeacherClient(endpoint, *, timeout_s, max_response_bytes=64 KiB, model=None)` has a `complete(messages) -> str` that returns `choices[0].message.content` raw. It never parses, repairs or retries the answer.
  - The request asks for constrained decoding with `proposal.SCHEMA` itself (no copy) and sends no `Authorization` header.
  - It uses `http.client`, not `urllib`, so it ignores `HTTP(S)_PROXY` and never follows a redirect. A 3xx is an error and is checked before the body is read.
  - `https://` uses `ssl.create_default_context()` with `CERT_REQUIRED` and `check_hostname`, and never falls back to plain HTTP.
  - URLs with user info, a query, a fragment, spaces or control characters are refused. A URL with no port uses the scheme's default. A trailing `/v1` is dropped, so the path never becomes `/v1/v1/…`.
- **One total deadline:** the whole exchange (name lookup, each connect attempt, TLS, send and read) runs in a worker thread. The caller waits only until the deadline, then shuts down the exchange's sockets. This is the only way to bound `getaddrinfo`, which has no timeout of its own, and a status line or chunk header that `http.client` reads byte by byte after the socket has moved to the response. Wait values are clamped, so a huge `timeout_s` can't overflow `settimeout`. Bad `timeout_s` values (≤ 0, NaN, inf, `10**400`) are refused as `BackendError`.
- **Safe error text:** any text from the server (reason phrase, body excerpt, exception text such as `BadStatusLine`) is folded to one line, cut to 200 characters and passed through `render.escape` when the error is built.
- `src/nl_shell/repl.py`: `Repl._propose` catches `BackendError` around `complete()` only. It shows `The model server isn't running (…).` or `The model server could not be used: <reason>.` These texts are interim, marked as such in a comment, until the "model unavailable" state from ADR-0018 §7 is built.

## Verification
Line numbers are on this branch (main + #153 + this change).

- **Claim:** every model answer still goes through the one strict parser. The client returns raw text and the request uses the shared schema object.
  - **Checked:** `src/nl_shell/teacher_client.py:365` (`complete` returns content only), `:352` (`response_format` built from `proposal.SCHEMA`, `src/nl_shell/proposal.py:18`).
  - **Test:** `test_returns_the_content_and_sends_the_chat_completions_request` compares the request to the imported `SCHEMA`. `test_repl_rejects_a_bad_proposal_and_reads_on` sends each schema reject case as content.
- **Claim:** no request outlives its deadline, including lookup and connect.
  - **Checked:** `src/nl_shell/teacher_client.py:206` (`_Exchange`), `:243` (`abandon` shuts the sockets down), `:380`–`:384` (worker plus deadline wait), `:201` (wait clamp), `:180` (`_timeout`).
  - **Test:** `test_a_server_that_never_answers`, `test_a_slow_drip_body`, `test_a_chunked_slow_drip`, `test_a_slow_drip_status_line`, `test_a_hanging_name_lookup_is_abandoned` and `test_hanging_connects_share_one_deadline` each run against a 5 s server delay with a 0.5 s timeout, and each must finish in under 2 s. `test_a_huge_timeout_is_clamped_and_works` uses `1e10` and must still return content.
- **Claim:** no server text reaches the terminal unescaped or in bulk.
  - **Checked:** `src/nl_shell/teacher_client.py:130` (`_excerpt` → `render.escape`, `src/nl_shell/render.py:64`).
  - **Test:** `test_a_hostile_status_line_never_reaches_the_terminal` (OSC 52 / ESC / BEL / CR in the status line) and `test_a_long_status_line_is_cut_to_one_short_line`.
- **Claim:** TLS verification is on, redirects aren't followed, and the size cap holds.
  - **Checked:** `src/nl_shell/teacher_client.py:294` (context), `:448` (3xx refused before the body), `:457` (declared length over the cap).
  - **Test:** `test_https_to_a_plain_http_server_is_a_tls_error` (also asserts `CERT_REQUIRED` and `check_hostname` on the captured context), `test_a_redirect_is_not_followed` (the redirect target gets no request), `test_a_body_over_the_cap_stops_the_read`.
- **Claim:** a failing backend never ends the REPL session.
  - **Checked:** `src/nl_shell/repl.py:168` (`except BackendError`), `:74` (`backend_failure`), `:42`–`:43` (reply texts).
  - **Test:** `test_repl_catches_any_backend_error` uses a stub backend with no client import, so it fails if only the `repl.py` catch is reverted. `test_repl_with_no_socket_says_the_server_is_not_running` and `test_repl_with_no_socket_path_says_the_server_is_not_running` check that the next line is still read.
- **Regression test:** `tests/test_teacher_client.py`. With the non-test changes reverted, all 79 tests fail. With the change, all pass. The full suite passes (560 tests).

## Not in this PR
- **Ctrl-C during a slow request ends the session.** `Repl.run` catches `KeyboardInterrupt` only while it reads input. This can't happen yet, because nothing in the CLI uses the client. The follow-up that wires the client in (#152) will handle it in `_propose`.
- **Threat model update.** The new client adds an outbound connection whose answer reaches the terminal. It relies on rules the threat model already states (output is filtered everywhere, and the local model socket and dev-teacher endpoint are listed as inputs). The line for this client will be added with #152, when it becomes reachable from config.
- Config and CLI endpoint selection, retries, streaming, health checks and the ADR-0018 §7 "model unavailable" state.

Fixes #151

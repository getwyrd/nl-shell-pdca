# Build notes — issue 77 (teacher-client-dev-teacher-flag), iteration 3

## Outcome: partly built. The parts that don't need #16 are done and tested; the rest is still blocked on #16

Iterations 1 and 2 shipped nothing, because #16's backend interface, `proposal/v1` schema
and parser are not on the base. Both carry-forwards asked for "the implementation and
discriminating tests". They are still not on the base: the worktree is detached at
`0771812` (= `origin/pdca-integration/main-r2546dbf9639f`, unchanged after `git fetch`),
and `git grep -l -i "proposal/v1" HEAD origin/main -- src` finds nothing. `$PDCA_VERIFY_BASE`
is unset. `results/issue_143/` (the #16 core split) still has no `patch.diff` and no
`close-disposition`.

So this round does something different from the rejected empty patch: it builds every
part of #77 that does **not** use a #16 name, and leaves only the #16 hookup out. Nothing
here is a stand-in for #16. The client takes the response schema as a constructor argument
and returns the raw `choices[0].message.content` string. The #16 hookup will pass #16's
schema object in, and hand the content to #16's parser.

NEEDS-HUMAN external dependency: issue-16-core (#143: backend interface, `proposal/v1` parser + schema) — still not on the wave base `0771812`; without it this patch cannot (1) send #16's own schema object (criterion (a), "the same object #16's parser uses"), (2) reject the `proposal/v1` §Conformance content cases (criterion (b), second half), (3) wire the client into `Repl` as #16's backend (criterion (d)), or (4) show the AF_UNIX attempt for a natural-language line (criterion (f), last clause). Those four are unverified, not faked.

```toml
[[doctor.checks]]
id    = "issue-16-core"
cmd   = "git -C ../nl-shell grep -q -i 'proposal/v1' \"${PDCA_VERIFY_BASE:-origin/main}\" -- src"
hint  = "Sign off #143 (the #16 core split) and fold it into the wave base before scheduling #77; don't put #77 in the same wave as #143"
level = "MISSING"
```

## What the patch does (cited against `0771812` + patch)

1. **New `src/nl_shell/teacher_client.py`** (335 lines).
   - Named constants: `CONNECT_TIMEOUT_S = 5`, `READ_TIMEOUT_S = 120`,
     `MAX_RESPONSE_BYTES = 64 * 1024` (`teacher_client.py:43-47`), as the brief's Scope (2)
     and Design ask. The constructor takes overrides (`teacher_client.py:200-217`).
   - `Endpoint` / `EndpointDecision` (`:81-113`), with the two `:status` lines
     (`EndpointDecision.status_lines`, `:104-113`).
   - `default_socket` (`:116-122`): `$XDG_RUNTIME_DIR/nl-shell/model.sock`; unset or
     relative `XDG_RUNTIME_DIR` → `None`, never a guess at `/run/user/<uid>` (brief, Test
     file).
   - `is_loopback_host` (`:125-132`): `localhost`, `127.0.0.0/8`, `::1`; any other name is
     non-loopback, no DNS (brief, Design).
   - `check_url` (`:135-145`): only `http`/`https` with a host; also refuses a URL with
     user:password in it (the teacher has no credential; ADR-0006/0015 per the brief's
     out-of-scope line).
   - `choose_endpoint` (`:148-176`) — ADR-0020 §3: no flag → default socket, and a config
     `teacher_url` gives the refusal message; flag → flag URL, else config URL, else an
     error; non-loopback `http://` → the SSH-tunnel / TLS warning. Loopback TCP also needs
     the flag (the brief's "Alternatives considered" reading).
   - `_UnixHTTPConnection` (`:179-194`): HTTP over `AF_UNIX`.
   - `TeacherClient.request_body` (`:219-234`): `messages`, `response_format` of type
     `json_schema` carrying the caller's schema, and `model` only if set. No
     `Authorization` header anywhere (`complete`, headers at `:264-267`).
   - `TeacherClient.complete` (`:236-281`): one connect, one POST, no retry. Absent socket /
     refused → `ModelServerUnavailable("the model server isn't running")`; TLS failure →
     `TeacherError("TLS error: …")` with `ssl.create_default_context()` (cert + hostname
     checks on, `:294-298`) and no plain fallback; read timeout → reason names the
     seconds.
   - `_read_body` (`:305-321`): 3xx → rejected, not followed (`http.client` never follows
     redirects, and we don't add a loop); non-2xx → rejected; over the cap by
     `Content-Length` or by reading `cap + 1` bytes → rejected (reading stops there).
   - `_content` (`:324-335`): not JSON / no `choices[0].message.content` / not a string →
     rejected.
2. **`src/nl_shell/config.py`**: `teacher_url`, `teacher_model` on `Config`
   (`config.py:33-34`), loaded with the same "must be a string" check as `target`
   (`config.py:64-70`, replacing base `config.py:60-63`). Docstring updated
   (`config.py:9-12`, replacing base `config.py:9-10`, which said "Later issues (#77) add
   their keys").
3. **`src/nl_shell/cli.py`**: `--dev-teacher [URL]` (`cli.py:33-41`, after base
   `cli.py:28-32`), `nargs="?"`, `const=""` so a bare flag means "use `teacher_url`".
   The decision is made inside the existing `try` (`cli.py:53-57`) and `EndpointError` joins
   the existing exit-1 branch (`cli.py:67`). Messages go to stderr as
   `nl-shell: warning: …` like the target mismatch (`cli.py:77-78`). The endpoint and
   backend lines go after the target lines (`cli.py:79-81`), as the comment at
   `src/nl_shell/input_modes.py:300-302` on the base already plans ("#77 endpoint and
   backend").
4. **Tests changed outside the new file**: `tests/test_targets.py` and `tests/test_cli.py`
   compare the full `:status` output, so they now expect the two new lines. Their fixtures
   unset `XDG_RUNTIME_DIR` so the host's value can't change the expected text.

The brief's wiring point "`Repl.interactive` at `src/nl_shell/repl.py:40-45`" is not
touched: the REPL change is the #16 hookup (criterion (d)).

## Criteria status

| Criterion | Status | Test(s) in `tests/test_teacher_client.py` |
|---|---|---|
| (a) valid response, POST path, messages, json_schema `response_format`, no `Authorization`, `model` only if set | built and tested; schema is a test dict, not #16's object (blocked) | `test_valid_response_returns_the_content_and_the_request_is_the_chat_api`, `test_teacher_model_from_config_is_sent_only_when_set` |
| (b) HTTP error, redirect not followed, not JSON, no content, oversize, timeout (0.5 s vs 2 s, test < 2 s), https → TLS error, no fallback | built and tested | `test_bad_responses_…` (8 cases), `test_an_oversize_body_without_a_length_…`, `test_a_redirect_is_not_followed`, `test_no_answer_within_the_read_timeout_is_rejected`, `test_https_to_a_plain_http_server_…` |
| (b) `proposal/v1` §Conformance content rejects | **blocked on #16** (the parser) | none |
| (c) default socket used; config URL refused + server gets nothing; with flag used; flag URL used; non-loopback `http://` warned without connecting | built and tested | `test_default_endpoint_is_the_runtime_socket`, `test_config_url_without_the_flag_…`, `test_config_url_with_the_flag_is_used`, `test_flag_url_is_used_over_the_config_url`, `test_plain_http_to_a_non_loopback_host_is_warned` (7 cases, `create_connection` patched to record) |
| (d) through `Repl` | **blocked on #16** (the backend interface) | none; only the client-level "model server isn't running" (`test_no_runtime_dir_…`, `test_absent_default_socket_…`) |
| (e) `:status` endpoint + backend | built and tested | `test_status_shows_the_dev_teacher_endpoint_and_backend`, `test_status_shows_the_default_socket` |
| (f) no AF_INET/AF_INET6 on the default path with `teacher_url` in config | built and tested for start-up plus one natural-language line; the "only the AF_UNIX attempt" part is **blocked on #16** (the REPL doesn't call the client yet) | `test_config_url_without_the_flag_makes_no_tcp_connection` |

## Self-refutation (forced)

- **(a) Genuine red?** Yes. Run through the project's C4 script
  (`engine/scripts/run-verify.sh`, with `PDCA_BUNDLE` and `PDCA_WORKTREE` set): green leg
  "98 passed"; red leg with the production hunks reverted "43 failed, 55 passed" →
  `PDCA-EVIDENCE: C4 PASS — red without the fix (43 of 98 failed), green with it`. The 98
  are this file plus `test_cli.py` and `test_targets.py`, which the patch also touches. On
  the first run (only this file) all 36 failed with the fix reverted: the in-function
  imports fail, and the cli tests fail on argparse exit 2 or on the missing stderr message.
  `test_config_url_without_the_flag_makes_no_tcp_connection` on its own would pass on the
  base (the base makes no connection at all), so it also asserts the refusal message and
  the `endpoint: unix:` status line, and those make it go red.
- **(b) Production path?** Yes. Every test calls the real `teacher_client.TeacherClient`,
  `choose_endpoint`, `config.load` or `cli.main`. The only fakes are the HTTP servers (as
  the brief asks) and the `Repl.interactive` swap that `tests/test_cli.py` and
  `tests/test_targets.py` already use. The `SCHEMA` dict is test data passed to the real
  client, not a stand-in for code.
- **(c) Fixture includes the fault?** Yes. Each reject case has the fake server actually
  send the bad answer: a real 500/404, a real 307 with a `Location` pointing at a second
  live fake (which is checked to get nothing), a real 2 s stall, a real oversize body (one
  with `Content-Length`, one chunked with no length that would send 4 MiB), a real
  plain-HTTP server under an `https://` URL. The "config URL refused" test runs a live fake
  at that URL and checks it gets no request.

## Other checks

- Whole suite through `engine/scripts/run-suite.sh`: `366 passed`, T3 PASS.
- The target repo has no formatter or commit hooks (no `.pre-commit-config.yaml`, no ruff
  or black config in `pyproject.toml`). I matched the existing style by hand: no new line
  over 92 characters in `teacher_client.py`.
- No new dependency: `http.client`, `ssl`, `socket`, `ipaddress`, `json` only (brief,
  "Alternatives considered").

## Options I ruled out

1. **A third empty patch.** Rejected twice by the auto-iterate; most of #77 doesn't need #16.
2. **Write my own `proposal/v1` schema / parser / backend interface.** The brief forbids
   stand-ins, and they would clash with #143's `backend.py`, `proposal.py` and `repl.py`
   edits when folded.
3. **Wire the client into `Repl` now with a temporary reply format.** That is #16's
   rendering and backend interface (brief: "the rendering of the proposal (#16 owns it)").
   Doing it here would mean guessing #16's names.

## What the #16 hookup needs (small, once #143 lands)

- Build `TeacherClient(decision.endpoint, <#16 schema object>, model=settings.teacher_model)`
  in `cli.main` and pass it to `Repl` as #16's backend; its `propose` method calls
  `complete(messages)` and hands the string to #16's parser; `TeacherError.reason` and
  `ModelServerUnavailable` become #16's reject / "isn't running" replies.
- Add tests for the `proposal/v1` reject cases as `message.content`, the `Repl` path (d),
  and the AF_UNIX-attempt clause of (f).

## Notes for the human at sign-off

- The `:status` lines are `endpoint: <url> (dev teacher)` /
  `endpoint: unix:<path> (local model socket)` / `endpoint: none (…)`, and
  `backend: OpenAI chat completions (no API key)`. I haven't read ADR-0020 §4 (Do reads
  the brief only), so check that wording against it.
- The URL path rule: `http://host:port`, `http://host:port/` and `http://host:port/v1` all
  post to `/v1/chat/completions`; any other path is kept as a prefix.
- The brief's open questions (loopback TCP needs the flag; no auto-start, #48;
  `teacher_model`) are built as the brief proposes them.

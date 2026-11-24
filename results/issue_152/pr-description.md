## Summary
**User impact:** the interactive shell never suggests a command. Whatever you type
in plain language, it answers that no model is connected, even when a model server
is running. There is also no way to point a development session at a model server
on another machine: `nl-shell --dev-teacher` stops with "unrecognized arguments".

This PR connects the shell to the local model server by default, and adds a
`--dev-teacher [URL]` flag for using any other server during development. Without
the flag, nl-shell still makes no network connection at all.

Reported in [#152](https://github.com/eduralph/nl-shell/issues/152).

## What to look at
The main question for review is the rule for picking a server, which lives in one
small function with no side effects:

- **No flag:** always the local socket `$XDG_RUNTIME_DIR/nl-shell/model.sock`. If
  `config.toml` sets `teacher_url`, nl-shell says on stderr that it is refused and
  keeps using the socket. This includes `http://127.0.0.1:…`; ADR-0020 §3 requires the
  flag for loopback TCP too.
- **`--dev-teacher URL`:** that URL. **`--dev-teacher` alone:** `teacher_url` from
  `config.toml`, or a message that a URL is needed.
- **Unusable URL** (not `http://`/`https://`, user info, query, no host, does not
  parse): refused with the reason, and the local socket is used. The URL is shown in
  single quotes and escaped, so terminal control characters cannot get through.
- **Plain `http://` to a host that is not loopback:** used, with a warning to use an
  SSH tunnel or `https://`. Loopback means `localhost`, `127.0.0.0/8` or `::1`. There
  is no DNS lookup.

New `config.toml` keys: `teacher_url`, `teacher_model` (vLLM rejects a request with no
model name), and `[model] timeout_s` (request deadline in seconds, default 10, at most
3600). `:status` gains two lines: the endpoint in use and the backend kind.

To try it:

```sh
nl-shell --dev-teacher                         # needs a URL: message, local socket
nl-shell --dev-teacher http://<lan-host>:8080  # plain-http warning; :status shows the URL
printf 'teacher_url = "http://127.0.0.1:8080"\n' >> ~/.config/nl-shell/config.toml
nl-shell                                       # refused on stderr; :status shows the socket
```

The real LAN model check (`--dev-teacher http://<lan-host>:8080`, then a plain-language
line) is manual. The automated tests use in-process fake servers.

## Root cause
`cli.main` built the interactive `Repl` with prompts but no `backend=`, so every
request fell through to the "no backend" reply. Nothing chose an endpoint, built a
`TeacherClient`, or parsed a dev-teacher option.

## Fix
- `src/nl_shell/teacher_client.py`: new pure `select_endpoint(dev_teacher,
  teacher_url, runtime_dir)` returns the `Endpoint` and the stderr messages. It
  connects to nothing. It uses `default_socket`, `is_loopback` and a URL check that
  gives the real reason a URL is refused. As a final guard it still runs the existing
  `http_target`, so a URL the client would reject is never handed to it.
  `TeacherClient`'s transport, deadline and error handling are not changed.
- `src/nl_shell/config.py`: `teacher_url`, `teacher_model` (string-checked like
  `target`) and `model_timeout_s` from `[model] timeout_s`. A bool, a non-number,
  `<= 0` or `> MAX_MODEL_TIMEOUT_S` raises `ConfigError`.
- `src/nl_shell/cli.py`: `--dev-teacher [URL]`. Each message goes to stderr once. It
  builds `TeacherClient(endpoint, timeout_s=…, model=…)` and passes it as `backend=`.
  The two `:status` lines are added. A `Repl` built without a backend still gives the
  "no backend" reply.
- `tests/test_cli.py`, `tests/test_targets.py`, `tests/test_backend.py`: pin
  `XDG_RUNTIME_DIR` and expect the two new `:status` lines. Nothing else changes there.

Not in this PR: ADR-0018 §5 says only "non-loopback" endpoints need the flag
(`docs/design/adr/0018-model-serving-and-wire-format.md:46-48`). That is looser than
ADR-0020 §3, which this PR follows. Bringing ADR-0018 §5 in line is a separate doc
follow-up.

## Verification
- **Claim:** with no `--dev-teacher`, nl-shell opens no TCP connection; the only model
  connection is `AF_UNIX` to `$XDG_RUNTIME_DIR/nl-shell/model.sock` (ADR-0003; ADR-0020 §3).
  - **Checked:** `src/nl_shell/teacher_client.py:213-263` (`select_endpoint`: with no
    flag it returns `default_socket(...)`, `:188-197`, whatever `teacher_url` says);
    `src/nl_shell/cli.py:82-100` (the only client built is from that endpoint, passed as
    `backend=`).
  - **Test:** `tests/test_teacher_endpoint.py:600-638`
    (`test_default_path_opens_no_tcp_connection`). It patches `socket.connect` and
    `create_connection`, runs `cli.main` with `teacher_url = "http://127.0.0.1:<port>"`
    and a live fake server there, and asserts: zero `AF_INET`/`AF_INET6` connects, every
    `AF_UNIX` connect goes to the default socket, the socket server got the request, and
    the URL server got nothing.
- **Claim:** the endpoint rules (refusal, flag URL wins, missing URL, unusable URL,
  plain-http warning) hold, and every URL in a message is shown once, escaped.
  - **Checked:** `src/nl_shell/teacher_client.py:200-317` (`is_loopback`,
    `select_endpoint`, `_shown`, `_scheme`, `_url_problem`).
  - **Test:** `tests/test_teacher_endpoint.py:314-490` (calls `select_endpoint` directly)
    and `:493-518` (through `cli.main`: `--dev-teacher` parses, refusal and warning each
    reach stderr once).
- **Claim:** `[model] timeout_s` loads with the stated bounds and reaches the client.
  - **Checked:** `src/nl_shell/config.py:25-28` (`DEFAULT_MODEL_TIMEOUT_S`,
    `MAX_MODEL_TIMEOUT_S`), `:55-102` (`load`, `_string`, `_timeout`);
    `src/nl_shell/cli.py:88-90`.
  - **Test:** `tests/test_teacher_endpoint.py:240-292` (config), `:521-554`
    (`timeout_s = 0.5` against a slow-drip server on the socket: "could not be used"
    reply, run ends in under 2 s), `:582-597` (client gets the config settings).
- **Claim:** `:status` names the endpoint and backend kind.
  - **Test:** `tests/test_teacher_endpoint.py:557-580`. The existing `:status` pins in
    `tests/test_cli.py`, `tests/test_targets.py` and `tests/test_backend.py` are updated.
- **Red/green:** with every non-test change reverted, 110 of the 243 tests in the
  touched files fail, and every test in `tests/test_teacher_endpoint.py` fails on its own
  assertions: no `select_endpoint`, `--dev-teacher` exits 2, no `model_timeout_s`, and zero
  `AF_UNIX` connects. With the change, all 243 pass, and the full suite passes (753).

Fixes #152

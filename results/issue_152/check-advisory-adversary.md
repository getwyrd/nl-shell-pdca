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

# Build notes — issue 152 (teacher endpoint, `--dev-teacher`)

Base: the worktree `nl-shell.pdca-wt-l0` at `5d3d291 pdca-integrate: issue_151` (folded on
`0017a0e` issue_144 and the #143 integration). `$PDCA_VERIFY_BASE` was empty in my shell,
so I checked the base by content instead: `TeacherClient`, `Endpoint`, `BackendError` and
`MAX_RESPONSE_BYTES` are in `src/nl_shell/teacher_client.py` (#151). `NO_BACKEND` is at
`src/nl_shell/repl.py:34`. Before this patch, `cli.main` called
`Repl.interactive(status_lines=..., prompts=loaded)` with no `backend=`
(base `src/nl_shell/cli.py:65`).

## What changed (line numbers are post-patch, in the worktree)

1. **`src/nl_shell/config.py`**
   - `DEFAULT_MODEL_TIMEOUT_S = 10.0` and `MAX_MODEL_TIMEOUT_S = 3600.0` (`:26-27`).
   - `Config` gets `teacher_url`, `teacher_model` and `model_timeout_s` (`:35-40`).
   - `load` (`:54`) reads the two strings with `_string` (`:84`), which works the same way
     as the old inline `target` check, so the error text for `target` is unchanged and
     `tests/test_targets.py` still matches it exactly. It reads `[model] timeout_s` with
     `_timeout` (`:91`): bool and non-numbers are rejected. The value must satisfy
     `0 < v <= MAX`, checked before converting to float, so NaN, inf, 1e10 and huge
     integers are all rejected without an `OverflowError`. A `model` key that is not a
     table is a `ConfigError`.
   - The bound is one hour. The brief only asked for a named constant. An hour is far
     above any real request, and a larger value is almost surely a typo.
2. **`src/nl_shell/teacher_client.py`** (no change to `TeacherClient` or the transport)
   - `default_socket(runtime_dir)` (`:188`): the XDG rule. Unset, empty or relative gives
     `Endpoint("unix", None)`. There is no `/run/user/<uid>` guess.
   - `is_loopback(host)` (`:200`): `localhost` (case-insensitive), `127.0.0.0/8`, `::1`.
     It uses `ipaddress` parsing only, with no DNS lookup.
   - `select_endpoint(dev_teacher, teacher_url, runtime_dir)` (`:213`), a pure function:
     - no flag → always the default socket; a `teacher_url` gives a refusal message;
     - the flag with a URL wins over `teacher_url`; `True` uses `teacher_url`;
     - `True` with no URL → a "needs a URL" message plus the default socket;
     - a scheme that is not http/https → a refusal plus the default socket. URLs that
       pass the scheme check also go through child-1's own `http_target` validation
       (user info, query, bad port, no host, control characters). A URL the client would
       reject on every request is therefore refused at start-up, never handed to
       `TeacherClient`. Same rule, one implementation: no copy of the URL checks;
     - non-loopback `http://` → the endpoint plus a warning (SSH tunnel or https://).
     Every URL in a message goes through `render.escape` (`_quote`). `cli._error`
     escapes again, which does nothing the second time, because `escape` leaves
     backslashes alone by default.
   - `describe_endpoint` (`:282`) builds the `:status` text.
3. **`src/nl_shell/cli.py`**
   - `--dev-teacher [URL]`, `nargs="?"`, `const=True`, `default=None` (`:42-52`).
   - After target and prompts are loaded: `select_endpoint(args.dev_teacher,
     settings.teacher_url, os.environ.get("XDG_RUNTIME_DIR"))` (`:83-85`). Each message
     goes to stderr through `_error` with a `nl-shell: ` prefix. Then
     `TeacherClient(endpoint, timeout_s=settings.model_timeout_s,
     model=settings.teacher_model)` is passed as `backend=` to `Repl.interactive`
     (`:86-100`).
   - Two new `:status` lines go after the target and prompts lines:
     `model endpoint: ...` and `model backend: ...` (`:90-95`, `_backend_kind` `:103`).
4. **Tests pinning `:status`**
   - `tests/test_cli.py`: pin `XDG_RUNTIME_DIR` and add the two lines to the expected
     list.
   - `tests/test_targets.py`: the `start` fixture pins `XDG_RUNTIME_DIR`. `MODEL_LINES`
     is added after each of the 5 full `run.out ==` pins.
   - `tests/test_backend.py`: the one allowed edit, in
     `test_status_lists_the_loaded_prompt_files`: pin `XDG_RUNTIME_DIR` and add the two
     lines. Nothing else changed in that file.
   The pinned runtime dir is a path that does not exist (`/nonexistent/...`). If any of
   those tests sends a natural-language line, the request fails fast as "isn't running";
   it never reaches a socket on the host.

## Choices and what I ruled out

- **Refusal means: use the default socket and keep running.** The brief carries this
  over from the earlier rounds, and I followed it. I did not exit non-zero.
- **The two `:status` lines are always present.** That is why the three test files
  needed updating. I considered showing them only on `--dev-teacher` but ruled it out:
  the brief asks `:status` to name the endpoint, and the default socket path is exactly
  what a user needs to see when the server "isn't running".
- **Built the client in `cli.main`, not in `Repl.interactive`.** `repl.py` is out of
  scope, and `Repl.interactive` already takes `backend=` (`src/nl_shell/repl.py:109-121`).
- **I did not write a second URL validator** in `select_endpoint`. It calls child-1's
  `http_target`, which keeps the client and the selection in agreement.
- **The double escape is harmless.** `select_endpoint` escapes because the brief asks
  for the URL to be escaped in the message itself. `_error` escapes again. Escaping
  again changes nothing, since `escape` only touches hidden characters, so I left
  `_error` as is.

## Tests (`tests/test_teacher_endpoint.py`, 78 tests)

At module level the file imports only the stdlib, pytest, `nl_shell.cli`,
`nl_shell.config` and `nl_shell.repl.Repl`. `teacher_client` is imported inside the
functions. The (a)–(f) sections follow the brief. The fake servers are hand-written on
plain sockets (Unix socket under a `mkdtemp(prefix="nls-")` runtime dir, and TCP on
`127.0.0.1:0`). They poll a stop event and are joined in teardown. The runtime dir is
removed in teardown. No `teacher` marker.

## Refuting my own test

- **(a) Genuine red? Yes.** `engine/scripts/run-verify.sh` (the C4 gate, run with
  `PDCA_BUNDLE`/`PDCA_WORKTREE` set) reverted the production hunks:
  `87 failed, 133 passed` → `PDCA-EVIDENCE: C4 PASS — red without the fix (87 of 220
  failed), green with it`. The new file has 78 tests. The gate also ran the other test
  files in the patch, whose `:status` pins go red too, so I did not separately confirm
  that every one of the 78 is among the 87 failures. The failures come from this
  file's own assertions: no `select_endpoint`, `SystemExit` 2 from argparse on
  `--dev-teacher`, no `model_timeout_s`. With only `cli.py` reverted to base,
  (d) fails with `assert 'could not be used' in "No model backend is configured…"` and
  (f) fails with `assert 0 >= 1` (zero `AF_UNIX` connects). Those are the red reasons
  the brief predicts.
  - Mutation: I changed `select_endpoint` so that without the flag it uses `teacher_url`.
    (f) then fails at `assert tcp == []`, with an `AF_INET` connect to `127.0.0.1:<port>`
    recorded. So (f) also catches a selection that leaks the config URL. The mutation was
    restored afterwards; the worktree diff equals `patch.diff` byte for byte (checked with
    `cmp`).
- **(b) Production path? Yes.** (c)–(f) run the real `cli.main`. Only
  `Repl.interactive` is swapped, to build a real `Repl` with scripted input, and it
  passes on every keyword `cli.main` gives it, including the real `TeacherClient`.
  (d) and (f) make real HTTP requests over a real Unix socket to a fake server. (b)
  calls the production `select_endpoint`.
- **(c) Fixture includes the fault? Yes.** (f) puts a *live* server at the config
  `teacher_url`, so a leak would actually connect and be recorded, and checks it got
  nothing. (d) uses a slow-drip server that never finishes. (b) includes the bad URLs
  (`ftp://`, `unix:`, bare `host:port`, an unparsable one, an escape sequence) from
  both the flag and the config.

## Runs

- Full suite through `engine/scripts/run-suite.sh`: `730 passed, 1 warning`
  (`PDCA-EVIDENCE: T3 PASS`). The one warning is a forkpty DeprecationWarning in
  `tests/test_session.py`, which runs before this file.
- Final check after a docstring re-wrap: the five touched or related test files,
  `299 passed`.
- Commit-ready: the target has no formatter or pre-commit config (no
  `.pre-commit-config.yaml`, no ruff/black config). CI runs `scripts/docs_checks.py`,
  `scripts/docs_links.py` and pytest. `docs_links` is clean (0 broken). Every added line
  is ≤ 91 characters, and the existing source already has lines up to 92.

## Notes for sign-off

- `results/issue_152/.tc_backup.py` is a scratch copy of `teacher_client.py` I made
  during the mutation check. It is not part of the patch and can be ignored or deleted.
- No transport bug turned up in `TeacherClient`: (d) ends in about 0.5 s with the
  "could not be used" reply.
- Manual check, not part of the criterion: run `nl-shell --dev-teacher http://<lan-host>:8080`
  against the real LAN teacher. Expect the plain-http warning on stderr, `:status`
  showing the URL and `dev teacher`, and a proposal for a natural-language line.

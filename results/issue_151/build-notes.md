# Build notes — issue 151 (teacher-client-transport), iteration 3

Target: eduralph/nl-shell, worktree `$PDCA_WORKTREE` at `cefb359` (`pdca-integrate: issue_143`,
stack base `pdca-integration/main-r2546dbf9639f`, `stack-base-tip` matches). #143 is in the
base: `Backend` / `RecordingStub` in `src/nl_shell/backend.py`, `proposal.SCHEMA`
(`src/nl_shell/proposal.py:18`), `render.escape` (`src/nl_shell/render.py:64`),
`prompts.load` (`src/nl_shell/prompts.py:89`), `Repl._propose` (`src/nl_shell/repl.py:156`
on the patched tree). Line numbers below are on the patched tree.

## What this iteration does: re-ships the iteration-v2 patch unchanged

`patch.diff` is byte-identical to `iteration-v2/patch.diff` (checked with `cmp` after
applying it to the fresh worktree and regenerating the diff with `git add -N` + `git diff`).
The test file is the same too (`diff` against the bundle copy: no difference).

Why no code change: the round-2 carry-forward names exactly one item, the T2 threat-model
question, and it is not build work:

- The brief puts `.oss-scanner/threat_model.md` and every doc edit **out of scope**
  (brief.md, "Scope / out of scope": "`.oss-scanner/threat_model.md` and any doc edit").
  Editing it would break the brief, so Do cannot "fix" T2.
- The T2 gate is advisory and itself says the decision belongs to sign-off
  (`iteration-v2/gate-logs/T2-threat-model.log`). It fires because `src/nl_shell/backend.py`
  is on its security-relevant path list; it would fire on any patch that adds `BackendError`,
  which the brief requires.
- The v2 reviewer, adversary and security review found **no implementation defect**
  (`iteration-v2/check-review.md`: "No implementation defect was established by this
  review"; security review: "Verdict: no finding").

So the "don't re-submit the rejected approach unchanged" rule does not apply here in
substance: the approach was not rejected; the round was sent back for a human decision that
an automatic rebuild cannot make. Changing code just to look different would add risk with no
finding behind it.

### For the human at sign-off — decisions only you can make

1. **T2 threat model.** The new surface is an outbound HTTP / Unix-socket client whose
   answer text reaches the terminal. It relies on invariants the threat model already states
   ("Output rendering is filtered everywhere", `.oss-scanner/threat_model.md:131`; the local
   model socket and the dev teacher endpoint are already listed as inputs, per the v2
   security review's "input 8" / "input 11"). This patch keeps them: all server text is
   folded, cut to 200 characters and escaped (`_excerpt`, `src/nl_shell/teacher_client.py:130`),
   and raw content goes only to #143's strict parser. Options: accept with no threat-model
   edit, or ask child-2 (#152, which wires the endpoint into config) to add a line.
2. **Ctrl-C during a request ends the REPL** (v2 adversary finding). `Repl.run` catches
   `KeyboardInterrupt` only around `self._read` (`src/nl_shell/repl.py:130`); during
   `complete` it propagates out of the worker wait (`src/nl_shell/teacher_client.py:384`).
   I did not change this: catching it needs a new reply text, and the brief defers
   "non-blocking requests" and the ADR-0018 §7 unavailable state. The brief's invariant (3)
   is about a failing server, not a user interrupt. The fix, if wanted here, is small:
   in `Repl._propose` (`repl.py:168`) add `except KeyboardInterrupt: return <new text>`
   (about 3 lines in `repl.py` plus one test that sends SIGINT to a hung fake). Decide
   whether it belongs in this bundle or the §7 bundle.

## Design (unchanged since iteration v1, kept by sign-off)

One daemon worker runs the whole exchange (lookup, connect, TLS, send, read); the caller
waits only until one `time.monotonic()` deadline, then shuts down every socket the exchange
tracks. This is the one mechanism that bounds `getaddrinfo` (no timeout of its own), several
hanging connects, and `http.client`'s buffered `readline` on a dripped status or chunk-size
line after the socket moves to the response. Per-`recv` socket timeouts alone were measured
in v1 to miss four timing legs (5.0 s each against the 2 s bound). Round-1 fixes
(`_timeout` float conversion for huge ints, `:180`; `_excerpt` for status-line text, `:130`)
are in, as described in `iteration-v2/build-notes.md`.

## What changed overall (patched-tree lines)

1. `src/nl_shell/backend.py:28` — `class BackendError(Exception)` only, plus a docstring
   paragraph (`:9-11`).
2. `src/nl_shell/repl.py` — `SERVER_NOT_RUNNING` / `SERVER_UNUSABLE` with the "interim until
   ADR-0018 §7" comment (`:39-43`); `backend_failure()` (`:74`); `_propose` catches
   `BackendError` around `self._backend.complete(...)` only (`:168`). Unchanged from v1.
3. `src/nl_shell/teacher_client.py` (new) — `Endpoint` `:76`, `MAX_RESPONSE_BYTES` `:61`,
   error classes `:93-121`, `_excerpt` `:130`, `http_target` `:146` (raw-URL character check
   `:151` before `urlsplit`, userinfo refused `:162`, trailing `/v1` dropped `:170`, default
   ports), `_timeout` `:180`, `_wait_for` clamp `:201`, `_Exchange` `:206` (deadline,
   `arm` `:234`, `abandon` `:243` via `shutdown(SHUT_RDWR)`), `_UnixConnection` `:264`,
   `_TcpConnection` `:280` (own `getaddrinfo` + per-address connect `:302`, TLS through
   `ssl.create_default_context()` `:294` with `CERT_REQUIRED` + `check_hostname`),
   `TeacherClient.complete` `:365` (exchange runs in a daemon worker; caller waits until the
   deadline `:384`, then abandons `:390`), redirect refused before the body `:448`, chunked
   reads with cap + deadline per chunk `:477`.

Design reasons (from v1, unchanged): the worker thread with a caller-side deadline is the one
mechanism that bounds `getaddrinfo` (no timeout of its own), several hanging connects, and
`http.client`'s buffered `readline` on a dripped status or chunk-size line once the socket
has moved to the response. Per-`recv` socket timeouts alone were measured in v1 to miss four
of the timing legs (5.0 s each against the 2 s bound).


## Refute-your-own-test (forced, this run)

- **(a) Genuine red? Yes.** `engine/scripts/run-verify.sh` (the C4 gate, run with
  `PDCA_BUNDLE` and `PDCA_WORKTREE` set) reverted every non-`tests/` hunk and re-ran
  `tests/test_teacher_client.py`: `79 failed in 6.93s (pytest exit 1; ran 79, failed 79,
  setup errors 0, import/collection errors 0)` →
  `PDCA-EVIDENCE: C4 PASS — red without the fix (79 of 79 failed), green with it`.
  Imports are inside test functions, so the red is real failures, not a collection error.
  The repl-catch-only leg (`test_repl_catches_any_backend_error`) uses a stub backend with no
  `teacher_client` import; in v1 reverting only the `repl.py` hunk made it fail, and neither
  file changed since. The round-1 legs (`10**400` timeout, oversized status line) were shown
  red against the v1 client in iteration v2.
- **(b) Production path? Yes.** Every leg builds the real `teacher_client.TeacherClient` /
  `Endpoint` and the real `Repl` with `prompts.load(...)`, against real fake servers on
  `127.0.0.1` and on a Unix socket, through the real `http.client`. The only patching is of
  `socket.getaddrinfo` / connect for the lookup and multi-address legs, and of
  `ssl.create_default_context` to record (not replace) the context it returns.
- **(c) Fixture includes the fault? Yes.** The fake server actually sleeps, drips bytes and
  chunk-size lines, sends redirects, oversized bodies, hostile status lines with
  ESC/BEL/CR, and the reject-case JSON; the Unix-socket "not running" leg points at a path
  that does not exist.

## Runs (this iteration)

- `engine/scripts/run-verify.sh`: C4 PASS (79/79 red without the fix, green with it).
- `engine/scripts/run-suite.sh` (T3): `560 passed, 1 warning in 123.15s` → `T3 PASS`. The
  warning is the existing `forkpty()`-in-a-threaded-process one.

## Commit-readiness

The target has no formatter or commit hook: no `.pre-commit-config.yaml`, no
`[tool.ruff]` / `[tool.black]` in `pyproject.toml`, and `.github/workflows/` has only
`tests.yml`, `docs-checks.yml` and two issue workflows (a grep for ruff/black/flake8/lint/
format in the workflows and `CONTRIBUTING.md` finds nothing). The new files keep the base's
style (v2 checked line lengths; unchanged since).

## Housekeeping

I wrote the regenerated diff to `/tmp/p151.diff` before copying it into the bundle; that is
outside the harness roots. Per the no-`rm` rule it was left; the human may delete it, along
with `/tmp/x` and `/tmp/nls151-tc.bak` from earlier iterations if they still exist.

## Out of scope, left alone

`config.py`, `cli.py`, endpoint selection, `tests/test_backend.py`, `proposal.py`,
`render.py`, `pyproject.toml`, docs and the threat model. `NO_BACKEND`'s text is untouched;
child-2 wires the client in and owns that reply. The deferred findings in
`deferred-findings.json` are for the human, not build work.

# Build notes — issue 151 (teacher-client-transport), iteration 2

Target: eduralph/nl-shell, worktree `$PDCA_WORKTREE` at `cefb359` (`pdca-integrate: issue_143`,
stack base `pdca-integration/main-r2546dbf9639f`). #143 is in the base: `backend.py`
(`Backend`, `RecordingStub`), `proposal.SCHEMA` (`src/nl_shell/proposal.py:18`),
`render.escape` (`src/nl_shell/render.py:64`), `prompts.load` / `Message`
(`src/nl_shell/prompts.py:89`, `:55`), `Repl._propose` (`src/nl_shell/repl.py:142` on the base).
Line numbers below are on the patched tree.

This iteration keeps the iteration-v1 design (worker thread + one caller-side deadline,
reviewed and kept by sign-off) and fixes the two implementation findings in the
carry-forward. The full v1 rationale is in `iteration-v1/build-notes.md`; its design
section still holds and is summarised at the end.

## Carry-forward findings and what I did

### 1. `timeout_s=10**400` → uncaught `OverflowError` (fixed)

Cause: the constructor checked `isinstance(timeout_s, (int, float))` and then called
`math.isfinite(timeout_s)`. Any Python int passes the type check, and `math.isfinite` (like
`float()`) raises `OverflowError` for an int too big for a float.

Fix: new `_timeout()` at `src/nl_shell/teacher_client.py:180`, called from
`TeacherClient.__init__` at `:334`. It converts with `float(timeout_s)` inside a
`try/except OverflowError` → `BadEndpoint("timeout_s is too large to use")`, then checks
`isfinite` and `> 0` on the float. The error texts no longer include `repr(timeout_s)` or
`repr(max_response_bytes)`: for an int with more than 4300 digits, Python 3.12's
int-to-string limit makes `repr` itself raise `ValueError`, so a message built from it would
crash in the same way. They name the type instead.

Choice: refuse a too-big int rather than clamp it to `MAX_WAIT_S`. The brief only requires
"`BackendError`, never `OverflowError`", and the reviewer suggested mapping to `BadEndpoint`.
`1e10` (a float) still works through the existing wait clamp (`_wait_for`, `:201`); that leg
is unchanged and green.

Test: `tests/test_teacher_client.py:487` `test_an_unusable_timeout_is_refused` now also
covers `10**400`, `-(10**400)`, `10**5000` (the repr-limit case), `"5"` and `None`.

### 2. Untrimmed server text via `BadStatusLine` / reason phrase (fixed)

Cause: `_describe` escaped `str(exc)` but never shortened it, and `http.client`'s
`BadStatusLine` holds the whole raw status line (up to ~64 KiB, trailing LF included —
`render.escape` leaves LF alone). The reason phrase of a status line that *does* parse had
the same gap (`_quote(response.reason)`, no cut).

Fix: one helper, `_excerpt()` at `:130`: fold whitespace runs to one space
(`" ".join(text.split())`, which removes LF/CR), cut to `EXCERPT_CHARS` (`:69`, 200),
then `render.escape`. Cutting happens **before** escaping, so a cut never splits an escape
like `\x1b`. Used in three places:
- `_describe` (`:140`), which every exception-text error goes through, including
  `BadStatusLine` and TLS errors;
- the reason phrase (`:447`);
- the error-body excerpt (`:454`), which already folded and cut; it now shares the helper.

Test: `tests/test_teacher_client.py:818` `test_a_long_status_line_is_cut_to_one_short_line`,
two cases: a malformed status line (`HTTP/1.1 Proposed command (risk: read-only) AAAA…×5000
\x1b[2K\r\n` → `BadStatusLine`, the reviewer's reproducer) and a parsing `500` whose reason
phrase is the same long text. Each checks: no LF/ESC/CR in the reason, at most
`EXCERPT_CHARS` `A`s, and through `Repl`: `out` is exactly one line
`The model server could not be used: <reason>.`, shorter than 600 characters, no ESC/BEL/CR.

### 3. T2 threat-model advisory (not changed — sign-off decision)

The brief puts `.oss-scanner/threat_model.md` and any doc edit **out of scope**
(brief.md:12) and the gate itself leaves the question to sign-off. I did not edit it. For the
human: the new surface is an outbound HTTP/Unix-socket client whose answer text reaches the
terminal. The invariants it relies on are already in the threat model ("Output rendering is
filtered everywhere", `.oss-scanner/threat_model.md:131`), and this patch keeps them (all
server text escaped, folded and cut; raw content goes only to the strict parser). Whether to
add a line for the new endpoint is a doc decision for child-2 or a follow-up.

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

## Refute-your-own-test (forced)

- **(a) Genuine red? Yes.**
  - `engine/scripts/run-verify.sh` (C4 gate, run with `PDCA_BUNDLE` / `PDCA_WORKTREE` set):
    `ran 79, failed 79, setup errors 0, import/collection errors 0` →
    `PDCA-EVIDENCE: C4 PASS — red without the fix (79 of 79 failed), green with it`.
  - Fix-specific red: I put the **iteration-v1** `teacher_client.py` back in the worktree
    (extracted from `iteration-v1/patch.diff`) and ran `engine/scripts/run-suite.sh`:
    `5 failed, 555 passed` — exactly the five new legs:
    `test_an_unusable_timeout_is_refused[10**400]`, `[-10**400]`, `[10**5000]`,
    `test_a_long_status_line_is_cut_to_one_short_line[malformed]`, `[long-reason]`.
    Then I restored this iteration's file and confirmed `git diff` is byte-equal to
    `patch.diff` (`cmp` → match).
  - The repl-catch-only leg (`test_repl_catches_any_backend_error`) is unchanged from v1,
    where reverting only the `repl.py` hunk made it fail; neither the test nor `repl.py`
    changed this iteration.
- **(b) Production path? Yes.** Every leg builds the real `teacher_client.TeacherClient` /
  `Endpoint` and the real `Repl` with `prompts.load(...)`. The new status-line legs go through
  a real TCP fake server and the real `http.client` parse (that is what raises
  `BadStatusLine`); nothing is mocked.
- **(c) Fixture includes the fault? Yes.** The fake server actually sends the malformed
  5000-character status line with ESC/CR/LF, and the oversized ints are passed straight to
  the real constructor.

## Runs

- `engine/scripts/run-verify.sh`: C4 PASS (79/79 red without the fix, green with it).
- `engine/scripts/run-suite.sh` (T3): `560 passed, 1 warning` → `T3 PASS`. The warning is
  the existing `forkpty()`-in-a-threaded-process one from `tests/test_session.py`, as in v1.

## Commit-readiness

The target has no formatter or commit hook: no `.pre-commit-config.yaml`, no
`[tool.ruff]` / `[tool.black]` in `pyproject.toml`, CI (`.github/workflows/tests.yml`) runs
only `pytest`, and neither `ruff` nor `black` is installed. No line in the two new files is
over 92 columns (checked with `awk`), matching the base's style.

## Housekeeping

While writing `patch.diff` I ran a `git diff > /tmp/x` by mistake (outside the harness
roots, never used). Per the no-`rm` rule it was left; the human may delete `/tmp/x`. The v1
stray `/tmp/nls151-tc.bak` noted in iteration-v1 may still exist too.

## Out of scope, left alone

`config.py`, `cli.py`, endpoint selection, `tests/test_backend.py`, `proposal.py`,
`render.py`, `pyproject.toml`, docs and the threat model (see finding 3). `NO_BACKEND`'s text
is untouched; child-2 wires the client in and owns that reply. The 12 deferred findings in
`deferred-findings.json` are for the human, not build work.

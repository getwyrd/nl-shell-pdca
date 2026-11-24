# Build notes — issue 152, iteration 2 (teacher endpoint, `--dev-teacher`)

Base: worktree `nl-shell.pdca-wt-l0` at `5d3d291 pdca-integrate: issue_151` (= `stack-base-tip`;
folded on #143, #102, #144 and #151). `$PDCA_VERIFY_BASE` was empty in my shell, so I checked
the base by content, as in v1: `TeacherClient`, `Endpoint`, `BackendError`, `http_target`
are in `src/nl_shell/teacher_client.py`; before the patch `cli.main` called
`Repl.interactive(status_lines=..., prompts=loaded)` with no `backend=` (base
`src/nl_shell/cli.py:65`).

I started from the v1 patch (`iteration-v1/patch.diff`, applied cleanly) and changed only
what the carry-forward asked for, plus one docstring wrap. Everything in v1's notes about
`config.py`, `cli.py`, the `:status` lines and the three pinned test files still holds
(`iteration-v1/build-notes.md` §1, §3, §4).

## Carry-forward finding 1 — URLs escaped twice and shown ambiguously

v1 built `f"{_quote(url)!r}"`. `_quote` turned ESC into the text `\x1b`, then `!r` doubled
the backslash, so `http://h<ESC>` and a URL holding a real `\x1b` printed the same, and a
`'` in the URL flipped repr to double quotes.

Fix (`src/nl_shell/teacher_client.py`, post-patch lines):
- New `_shown(text)` (`:266-272`): `"'" + render.escape(text, backslash=True) + "'"`. One
  escape pass. Literal single quotes. `backslash=True` turns a real `\` into `\\`, so ESC
  shows as `\x1b` and a real backslash-x-1-b shows as `\\x1b`; they can no longer be
  confused.
- Every URL in a `select_endpoint` message now goes through `_shown` (`:232, :254, :259`).
- The default socket path in those messages (`_socket_text`, `:314-317`) uses `_shown`
  too. It had the same ambiguity (it was `_quote`, no backslash flag), and it sits in the
  same messages.
- `cli._error` (`src/nl_shell/cli.py:109-111`) still runs `render.escape` over the line. I
  left it: after `_shown` there are no hidden characters left, and `escape` without
  `backslash=True` leaves backslashes alone, so the second pass changes nothing. `_error`
  also guards the other start-up messages (target/prompt errors), which are not mine to
  change. The finding listed this as part of the problem; with the `!r` gone it no
  longer alters the text, which is what the tests below pin through `cli.main`.
- The refusal no longer embeds `str(exc)` from `http_target`. Those messages are child-1's
  (`teacher_client.py:154-176`) and carry their own `{url!r}` / `{_quote(url)!r}`, so
  reusing them would show the URL twice and double-escaped again. Changing child-1's
  texts is out of scope, so I did not touch `http_target`.

## Carry-forward finding 2 — wrong reason for an `http://` URL that will not parse

v1's `_scheme` used `urlsplit`; on `http://[::1` it raised, `_scheme` returned `None`, and
the message said "must be an http:// or https:// URL".

Fix:
- `_scheme(url)` (`:275-289`) reads the raw prefix before `://` (lower-cased), with no
  `urlsplit`. `ftp://x`, `unix:/x`, `localhost:8080`, `not a url` still give `None`.
- New `_url_problem(url)` (`:292-311`) gives the reason without repeating the URL: a
  space/control/non-ASCII character, "does not parse (ValueError: Invalid IPv6 URL)",
  user info, query or fragment, no host. These are the same checks as `http_target`, in
  the same order.
- `select_endpoint` (`:213-263`) then still calls child-1's `http_target` on a URL that
  passed `_url_problem`, as a final guard, so a URL the client would reject is never handed
  to `TeacherClient`. If it ever raises there, the reason is a generic "it cannot be used
  as a server address".

Cost of what I chose over the alternative: `_url_problem` is 20 lines that repeat
`http_target`'s five checks (`:154-176`). The alternative was to edit `http_target`'s
seven `raise BadEndpoint(...)` texts to drop the URL, which would change child-1's error
texts (and the tests that pin them in `tests/test_teacher_client.py`). The brief puts
`TeacherClient`'s error handling out of scope, so I took the duplicate and kept
`http_target` as the final check. The two can drift; if they do, the guard still refuses
the URL, just with the generic reason.

## Tests added (`tests/test_teacher_endpoint.py`, now 101 tests; v1 had 78)

- `SHOWN_URLS`: `http://h<ESC>` → `'http://h\x1b'`, `http://h\x1b` (real backslash) →
  `'http://h\\x1b'`, `http://h'<ESC>` → `'http://h'\x1b'`.
- `test_url_in_a_message_is_shown_once_and_exactly` — each URL, from the flag, from config
  with the flag, and from config without the flag: the exact shown form is in the message
  and the URL appears once.
- `test_escape_and_backslash_urls_give_different_messages` — no-flag path, where only the
  URL differs: three distinct messages.
- `test_url_reaches_stderr_exactly_as_shown` — through `cli.main`; the exact form reaches
  stderr once, no raw ESC.
- `test_socket_path_in_a_message_is_shown_exactly` — same rule for the socket path.
- `test_http_url_that_does_not_parse_says_so` — `http://[::1`, `https://[::1]x`,
  `http://h:99999`, `http://h:port`: "does not parse", never "must be an http://…".
- `test_refusal_gives_the_real_reason` — user info, query, no host, space, `ftp://`.

## Refuting my own test

- **(a) Genuine red? Yes.**
  - Full revert: `engine/scripts/run-verify.sh` (C4 gate, `PDCA_BUNDLE` set):
    `110 failed, 133 passed` → `PDCA-EVIDENCE: C4 PASS — red without the fix (110 of 243
    failed), green with it`. Separately, with `git checkout -- src/` and only
    `tests/test_teacher_endpoint.py` run: `101 failed` — every test in this file goes red
    on its own assertions (no `select_endpoint`, argparse exit 2, no `model_timeout_s`,
    (f) zero `AF_UNIX` connects), not from `:status` churn in other files.
  - Against the v1 code (v1's `teacher_client.py` put back, rest of v2 kept): 16 of the new
    tests fail — all ESC and `'` cases, the socket path, both unparsable-IPv6 cases, the
    four "real reason" cases, and the different-messages check. The real-backslash case
    alone passes on v1 (v1 also printed it as `'http://h\\x1b'`; the bug was that ESC
    printed the same). The different-messages check first passed on v1 because the URLs
    hit different reasons; I moved it to the no-flag path, where the text is otherwise
    the same, and it then failed on v1 and passes on v2.
- **(b) Production path? Yes.** The (b) tests call the production `select_endpoint`; the
  stderr test runs the real `cli.main` with only `Repl.interactive` swapped for a scripted
  `Repl` that keeps every keyword `cli.main` passes. (d) and (f) make real requests over a
  real Unix socket.
- **(c) Fixture includes the fault? Yes.** The URLs carry a real ESC byte, a real
  backslash and a real `'`; the IPv6 case is the exact input from the finding. (f) still
  runs a live server at the config `teacher_url`, so a leak would connect and be recorded.

## Runs

- Full suite through `engine/scripts/run-suite.sh`: `753 passed, 1 warning`
  (`PDCA-EVIDENCE: T3 PASS`; the warning is the pre-existing forkpty one in
  `tests/test_session.py`).
- After the final docstring wrap in `src/nl_shell/config.py:8-12`: the touched test files
  plus `tests/test_teacher_client.py`, `322 passed`.
- C4 gate: PASS (above). Worktree diff equals `patch.diff` byte for byte (`cmp`).

## Commit-ready

The target has no `.pre-commit-config.yaml` and no ruff/black/line-length config. CI runs
pytest plus the docs scripts; `scripts/docs_links.py`: 0 broken. `git diff --check`: clean.
Added lines are at most 91 characters; the base already has lines up to 92
(`src/nl_shell/teacher_client.py`). I wrapped v1's one 101-character docstring line in
`src/nl_shell/config.py`.

## Notes for sign-off

- Scratch files I left in the worktree, untracked and not in the patch:
  `.tc_v2.py.keep` and `.tc_v2.diff.keep` (copies of `teacher_client.py` made while
  swapping in v1's code for the red check). v1's `results/issue_152/.tc_backup.py` may also
  still be there. All can be ignored.
- No transport bug turned up in `TeacherClient`.
- Manual check, not part of the criterion: `nl-shell --dev-teacher http://<lan-host>:8080`
  against the real LAN teacher. Expect the plain-http warning on stderr, `:status` showing
  the URL and `dev teacher`, and a proposal for a natural-language line.

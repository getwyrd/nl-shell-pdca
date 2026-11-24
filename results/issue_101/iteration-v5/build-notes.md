# Build notes — issue 101 / persistent-bash-session-core (iteration 5: v4 sign-off items)

All `path:line` references are on the patched tree built on `c47c5c2` (current `main`).

## Read this first: the base is still stale (carry-forward item 3)

The harness again gave me a worktree at `8c95e05`, and this bundle's `stack-base` still
names `pdca-integration/main-r2546dbf9639f` (`stack-base-tip` = `8c95e05`). That is the
exact reason the v4 round failed C4 ("patch.diff did not apply onto
'origin/pdca-integration/main-r2546dbf9639f'"). I did not edit or delete those two files:
they are the driver's state, and the brief's Ordering note says the human clears them.

I moved the worktree to `c47c5c2` (`git checkout --detach c47c5c2`) and built there.
Checked with a temporary index of each tree (`git read-tree` + `git apply --cached --check`):

- `c47c5c2`: `patch.diff` applies.
- `8c95e05`: does NOT apply (`docs/design/specs/pty-protocol/v1.md` and the threat model
  differ: #131/#132/#133 are not on that branch).

**Action for the human before Check's gates run:** clear the stale marker
(`publish.clear_stack_base`, i.e. remove `results/issue_101/stack-base` and
`stack-base-tip`), so the gate exports `PDCA_BRIEF_BASE=origin/main`
(`src/pdca_harness/gates.py:566-573`). If it is left, C4 fails a third time for a reason
that has nothing to do with the patch.

When I ran the project's C4 gate myself against `main`:

```
PDCA_BUNDLE=… PDCA_WORKTREE=… PDCA_BRIEF_BASE=origin/main engine/scripts/run-verify.sh
PDCA-EVIDENCE: C4 PASS — red without the fix (106 of 106 failed), green with it   (rc 0)
```

The second half of item 3 (the security-review advisory produced no verdict last round)
is a Check-beat leaf. Nothing in Do can make it produce one; it needs re-running at Check.

## What changed since v4

The starting point is `iteration-v4/patch.diff`, applied unchanged to `c47c5c2`. Its design
notes (`iteration-v4/build-notes.md`) still hold; line numbers there are now shifted by the
additions below. This round adds two fixes, five new test functions (8 cases), and the
matching spec text.

### 1. xtrace / PS4 / BASH_XTRACEFD in H (sign-off item 1, new Table A "detect" row)

The v4 hole: `exec 9>/dev/null; BASH_XTRACEFD=9; PS4='$(echo x >> MARK)'; set -x`. The hook
turned xtrace off for its own body and back on at its end
(`src/nl_shell/session.py:196` in v4), so tracing stayed on for every later command and
the PS4 payload ran each time while `H` stayed the same.

Fix, in the rcfile's `H` block:

- `src/nl_shell/session.py:175-177`: `declare -p PS4 BASH_XTRACEFD` (full value and
  attributes; `NAME unset` when unset, so the text doesn't depend on bash's error wording).
- `src/nl_shell/session.py:178`: `xtrace $__nls_x`. xtrace is already off when `H` is
  built (the hook turned it off), so the flag `__nls_done` saved
  (`session.py:151-152`, `:160`) is the honest value. `__nls_x` is in `HOOK_STATE_VARS`,
  so a `readonly __nls_x=0` changes `H` too.

So `set -x`, a changed `PS4` and a set `BASH_XTRACEFD` each degrade at that command's own
snapshot, and decision 10 means no later paste is written, so the payload never runs for a
later command. The payload can still run once, for the traced call of the hook itself
(`\__nls_done` is traced before it can turn xtrace off). That is the attacking command's
own prompt time, before its snapshot, which is what I3 allows. The test records the
marker's size after the degrade and checks no later command adds to it.

I kept the "turn xtrace back on at the end of the hook" line. Once `H` catches xtrace, the
session is already degraded whenever that line fires, so no paste follows it either way.
Dropping it would only change what a user sees if the REPL later lets them type into a
degraded bash, which decision 10 rules out.

Spec: `docs/design/specs/pty-protocol/v1.md:157-160` (rcfile note) and `:197-199` (§3 `H`
list).

Tests (`tests/test_session.py`):
- `:691` `test_xtrace_ps4_payload_never_runs_in_a_later_command`: the exact sign-off
  command, payload only appends to a marker (no CR rebind, so nothing else in `H` changes).
  Asserts degraded at its own snapshot (`result.seq == 1`, reason "H differs"), then
  `true` and `echo hello` are refused with nothing written to the PTY, and the marker
  doesn't grow.
- `:720` `test_xtrace_settings_degrade_at_their_own_snapshot` [xtrace, ps4, xtrace-fd]:
  each of the three settings alone degrades at its own snapshot.

### 2. Output boundary taken from the PTY stream (sign-off item 2)

The v4 cause: output was cut by read order. `__nls_done` wrote `D`, then ran the user's
`PROMPT_COMMAND`; nl-shell, on reading `D`, drained the PTY and kept what it got. Whatever
the user hook had already printed by then was taken as the command's.

Fix: bash marks the end of the output on the PTY itself, before `D` and before the user
hook.

- `src/nl_shell/session.py:154`: `__nls_done` prints `ESC ] 7700 ; <token> BEL` on its
  stdout (the PTY) right before writing `D`. The order on the PTY is therefore: command
  output, marker, user hook output, next prompt.
- `session.py:224-233`: `_END_TOKEN` placeholder and `_end_marker()`. `session.py:469`:
  `_spawn` puts a fresh `secrets.token_hex(16)` in the rcfile each start/restart, so
  text a command prints (e.g. `cat` of a hostile file) can't end its output early by
  chance. The token is visible to confirmed code (`declare -f __nls_done`), and it is in
  the hook function's text, so changing it changes `H`.
- `session.py:302-363` `_Output`: keeps bytes after readline's end-of-paste
  (`ESC[?2004l`, unchanged from v4) and before the end marker; drops everything after the
  marker. A marker split across two reads is handled by holding back the last
  `len(marker)-1` bytes.
- `session.py:627-640`: the result loop now feeds every PTY read to `_Output` (no "stop at
  `D`"), and after `E` and the check point calls `_await_output_end`
  (`session.py:676-698`). That reads the PTY until the marker shows up (normally already
  read; the wait covers only the PTY's own delay, bounded by `_SETTLE`). If the command ran
  and either marker is missing, the session degrades with "output could not be delimited",
  with the result attached since this is the command's own snapshot. Before, this
  degrade happened at `D` with no result. Moving it after `E` lets the `exec >/dev/null`
  case (the marker goes to `/dev/null`) be reported by the fd outside check, which already
  runs at the check point, and keeps `result is not None` there.

Why not the sign-off's example ("an fd-3 record written before the user hook runs"):
`D` already is that record. The problem is that fd 3 and the PTY are two separate streams,
and no record on fd 3 can say where in the PTY byte stream it was written. A sync point
(bash writes `D`, then waits on fd 4 while nl-shell drains the PTY) was the other option.
It still can't prove the PTY has delivered everything: the slave-to-master copy goes
through the kernel's flip buffer, so "nothing readable yet" doesn't mean "nothing more is
coming". It also costs a second check point per command (one more rcfile line, a second
`_check_point`-style wait of about 25 lines, and another spec paragraph). A marker in the
same stream as the output has no ordering question.

Spec: `v1.md:161-164` (rcfile note), `:229-233` (§4.1: the output is between readline's
end of the paste and the end marker, not "between `S` and `D`"), and `:251-253` (§4.2 trigger
wording for a missing marker).

Tests:
- `:743` `test_user_prompt_hook_output_is_not_the_commands` [text, osc7]: a `~/.bashrc`
  hook that prints text, and one that prints VTE's OSC 7. Thirty rounds of `echo helloN`,
  `printf abc` and `true`, each asserting `output` is exactly the command's own bytes.
- `:756` `test_system_vte_prompt_hook_output_is_not_the_commands`: sets `VTE_VERSION` so
  this host's real `/etc/bash.bashrc` sources `/etc/profile.d/vte-2.91.sh` (present here),
  the case the sign-off measured (25 of 40 leaks). Thirty rounds, exact output. On a host
  without that file it checks the plain case.

The shared fixture still unsets `VTE_VERSION` for every other test (v4 behaviour). That is
no longer needed for correctness, but it keeps those tests independent of the developer's
terminal. I left it.

## Refutation — answered

**(a) Genuine red? Yes.**
- Whole change: the project's C4 gate (`engine/scripts/run-verify.sh`, run against
  `origin/main`): 106 of 106 red with every production hunk reverted, green with the patch.
- The two fixes specifically: I put v4's `session.py` back (extracted from
  `iteration-v4/patch.diff`, everything else as now) and ran the new tests: all 7 new
  cases failed — the four xtrace ones with `DID NOT RAISE SessionDegraded`, and the hook
  output ones with e.g. `b'abcHOOK-OUTPUT\r\n' == b'abc'` and `b'\x1b]7;file…' == b''`.
  The real VTE case also failed. With the fixed file back (`cmp` against my backup): green.
- Before writing any fix, the same new tests against v4 code: 6 failed (the VTE test was
  added after), 1 passed (the existing v4 PS4 test).

**(b) Production path? Yes.** Every test starts the real `Session` from
`nl_shell.session` on real bash 5.3.9 through ptyprocess, with the production `RCFILE`.
The hook output tests use a real `~/.bashrc` in the suite's temporary HOME, and one uses
the host's real `/etc/bash.bashrc` VTE hook. The only test double is the v4 spy on
`session._write_all`, which records and then calls the real writer.

**(c) Fixture includes the fault? Yes.** The xtrace test runs the exact command from the
sign-off, with a real `BASH_XTRACEFD` on a real fd 9 and a PS4 payload that really writes
a file. The hook tests really print from a prompt hook on every prompt; the VTE test turns
the system hook on rather than leaving it off as the shared fixture does.

## Runs

- `tests/test_session.py`: 106 passed; whole suite (`tests/`): 282 passed (64 s).
  The hook-output, `.bashrc`, xtrace and interrupt tests: 3 more runs, all green.
- `scripts/docs_checks.py immutability c47c5c2 <temp commit>` → `docs-immutability: OK`;
  `scripts/docs_links.py` → 0 broken; `git diff --check` clean. (Temp commit made in the
  worktree, then `git reset --mixed c47c5c2`.)
- No formatter or pre-commit hook is configured in the target (no
  `.pre-commit-config.yaml`; CI runs pytest and the two docs scripts). No line over 100
  columns in the Python files.
- Test runs used `python3 -m pytest tests/…` from the target root (the repro runner named
  in `docs/INTEGRATION.md` §3), wrapped in `timeout`, plus the C4 script above.

## Housekeeping I should own up to

- Scratch files are in the worktree's untracked `.scratch/` (backups, v4 file, temp
  indexes); not in the patch.
- By mistake I also copied `session.py` once to `/tmp/nls_session_fixed.py`, outside the
  roots I was given. It's a copy of the patched file, nothing else; I did not delete it
  because removing files is not mine to do.

No external dependency beyond the brief's list (`ptyprocess`, `proc-syscall`,
`tiocsti-off`, `ptrace-scope`) was needed.

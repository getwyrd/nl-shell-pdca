# Build notes — issue 10 / persistent-bash-pty-session (iteration 2)

Target: eduralph/nl-shell @ main (`e7bb63c`), worktree `nl-shell.pdca-wt-l0`. All `path:line`
below are in the patched tree. Spec = `docs/design/specs/pty-protocol/v1.md`; ADR =
`docs/design/adr/0014-pty-session-protocol.md`.

This iteration starts from the iteration-1 patch (`iteration-v1/patch.diff`, applied
unchanged) and fixes the two findings in the carry-forward, plus one more gap of the
same kind found while probing. Everything else from iteration 1 still holds; its notes
are carried below with updated line numbers.

## Iteration 2 — what changed and why

### 1. A huge number in a record raised `ValueError` instead of degrading

Carry-forward: `pty_protocol.py:248` (v1) did `int(n)` on a `D` record's fields. Python's
`int()` refuses strings over 4300 digits, so `printf 'D <5000 nines> 0 0\n' >&3` raised
`ValueError` out of `Session.run()` and left `degraded == False` — against §4.2 ("a record
… malformed" → degraded mode).

Fix, two layers:
- `pty_protocol.py:41` `_NUM = r"\d{1,18}"` and the `S`/`D`/`J` patterns at `:44–:46`: a
  number field of more than 18 digits now fails `parse_record` as malformed (`ProtocolError`).
  18 digits is far beyond any sequence number or exit status and stays below `int()`'s limit.
- `pty_protocol.py:205–:213`: `_handle` now wraps both parsing and the state machine
  (moved into `_sequence`) in `except (ProtocolError, ValueError)` → `degrade("malformed
  control record: …")`. So any conversion error left anywhere in the state machine also
  degrades instead of raising.

Test: `tests/test_session.py:414` `test_oversized_numeric_field_degrades` — feeds the
record to a bare `ProtocolTracker`, then writes it from a live session to fd 3 and
expects `SessionDegraded` with a "malformed" reason. Against the iteration-1 code it fails
with the exact `ValueError` the finding names (output captured during the build).

### 2. The hook code itself was outside `H` and could be redefined

Carry-forward: `H` covered `declare -p PROMPT_COMMAND PS0` only. A sourced script could
redefine `__nls_done` to write well-formed but false records (e.g. an `L` that hides a new
alias), or set `__nls_user_pc` (eval'd at every prompt) to any code, without changing `H`.

Fix (rcfile, `session.py:77` onward):
- `session.py:114–:115`: `builtin readonly -f __nls_done __nls_ret` and
  `builtin readonly __nls_user_pc`, after the definitions. Probed: redefining fails with
  "readonly function", `unset -f __nls_done` fails with "cannot unset: readonly function",
  assigning `__nls_user_pc` fails with "readonly variable"; the session keeps working and
  is not degraded. `builtin` is used so a `readonly` function from `~/.bashrc` can't
  quietly skip this.
- `session.py:104–:105`: `H` is now a cksum of `declare -p PROMPT_COMMAND PS0 __nls_user_pc`
  plus `declare -f __nls_done __nls_ret`. With the read-only lines this should never
  change; it is a second check in case it does.
- The `H`-mismatch reason now says "nl-shell's hooks changed (PROMPT_COMMAND, PS0 or the
  hook functions)" (`pty_protocol.py:287`). `Snapshot.hooks_sum` comment updated (`:88`).

Tests, written so they would catch the attack the finding describes, not a weaker one:
- `test_replaced_done_hook_cannot_hide_state` (`tests/test_session.py:369`): rewrites
  `__nls_done` with `eval "$(declare -f __nls_done | sed …)"` so its `L` filters out
  `evil_nls`, then defines `alias evil_nls=…`. Passes if the session degrades, or if the
  alias shows up in the next snapshot (the redefinition was refused). I did NOT use the
  finding's simpler `__nls_done(){ :; }`: an empty hook writes no `D`, so even the old
  code degrades by the back-at-a-prompt rule and the test would pass without the fix.
- `test_replaced_user_prompt_command_does_not_run` (`:388`): sets
  `__nls_user_pc='touch ~/pwned'`, runs one more command (so the earlier prompt's hooks
  have finished), and checks the file does not exist (or the session degraded).

Both fail against the iteration-1 code (the alias is missing from `L`; `~/pwned` exists).

### 3. Found while probing: a new function could be hidden from `F`

The reference hook sends `F` only when `cksum` of the function list differs from
`$__nls_fsum`, a normal shell variable. Probed: the command
`evil_fn(){ :; }; __nls_fsum=$(builtin compgen -A function | cksum)` makes the next
snapshot skip `F`, the tracker keeps the old list, and `evil_fn` never shows up. Not
degraded. Same threat as finding 2 (item 4: session state from a sourced script), and
it matters once #12 relies on `F`.

Fix: `session.py:95–:96` sends `F` in every snapshot; `__nls_fsum` is gone. The parser
already accepted `F` in any snapshot (`pty_protocol.py`, `_end_snapshot`), so nothing on
the Python side changed. Test: `test_new_function_cannot_be_hidden_from_the_snapshot`
(`tests/test_session.py:402`). I put the old "send only when changed" logic back in
`session.py` and ran it: red; restored: green.

Rejected alternative: keep "only when changed" and protect the stored cksum. It has to
change after each new function, so it can't be `readonly`; the only way I found is a new
read-only variable per command (`declare -gr __nls_fsum_<n>=…`) plus a pointer to the
latest one, which the attacker can still point at an older entry. About 6 more lines of
bash, one leaked variable per command, and still forgeable. The cost of always sending
`F` is the size of `compgen -A function` per command (a few KB with bash-completion
loaded) over a local pipe.

**Spec note for the human:** §2's table says `F` is "sent only when it changed". This
patch sends it every time. A reader that follows the spec still works (it accepts both);
the spec's reference rcfile has this hole and should probably say "sent in every
snapshot". Reported, spec not edited.

### Residual risk, not fixable inside bash (human call)

`builtin` and `command` are not reserved words: a function named `builtin` takes over
every `builtin printf …` in the hook. Probed: `builtin(){ :; }` makes the hook write
nothing, and the session degrades after 1 s (back-at-a-prompt rule). But a crafted
`builtin` function that passes most calls through and edits only the `F`/`L` lines could
write a believable snapshot, and since `H` is also computed through `builtin`, it can
forge that too. Bash has no command that a function can't shadow, so the rcfile can't
fully defend itself; this is a limit of in-shell hooks (ADR-0014's design), not of this
patch. A fix would have to sit outside bash (e.g. reading bash state with a debugger, or
the policy gate refusing `builtin()`/`command()` definitions, #12). Flagging so the human
can decide whether #12 should own it.

What is still writable and why it is fail-closed: `__nls_seq`, `__nls_started`,
`__nls_ps0`, `__nls_once` must change every command, so they can't be read-only. Changing
any of them makes the next `S`/`D` carry the wrong number, or none, which degrades the
session (out-of-order record or back-at-a-prompt rule). They can't make it report a false
state silently.

## What the patch adds

| File | What | Spec |
|---|---|---|
| `src/nl_shell/pty_protocol.py` (new, 293 lines) | Pure logic, no I/O. `parse_record` (:101), `check_command` (:123), `ProtocolTracker` (:146), the S → D → snapshot → E state machine (`_sequence` :213). | §2, §3, §4, §5.2, §Versioning |
| `src/nl_shell/session.py` (new, 674 lines) | `RCFILE` (:77–:117), `Session.start/run/restart/close` (:309–:470), the forwarding loop `_wait_for_result` (:472), output splitting and alternate-screen capture (`_Capture` :183, `_OutputSplitter` :231), the back-at-a-prompt rule (`_back_at_prompt` :601, `_shell_busy` :618). | §1, §4.2, §5, §6; ADR Decision 1–4 |
| `tests/test_session.py` (new, 560 lines) | 39 tests, criteria (a)–(k) plus the iteration-2 cases. | §Conformance 1–12 |
| `pyproject.toml:15` | `ptyprocess>=0.7` | ADR-0021 |
| `.oss-scanner/threat_model.md:178` | §How to exercise it: how the session tests run, that they need only bash + ptyprocess. | — |

Split into two modules so the record parser and state machine can be tested without a
PTY (criterion (j)'s "a record containing `\r` fed to the record parser"). The session
uses the same `ProtocolTracker`, so that test drives production code.

### Spec section → code

- §1.1 start-up: `session.py:349` `_spawn` runs `bash --noprofile --rcfile <tmp> -i` via
  `ptyprocess.PtyProcess.spawn(..., pass_fds=(write_end,), preexec_fn=...)`; the
  `preexec_fn` (`:356`) `dup2`s the pipe's write end to fd 3. ptyprocess closes every other
  fd before calling `preexec_fn` (checked in ptyprocess 0.7.0 source), so the child holds
  only fd 3 of the pipe. The parent closes its write end right after spawn, so EOF on the
  read end means bash (and anything that inherited fd 3) closed it.
- §1.2/§1.3 rcfile: `session.py:77–117`. Written to a private `mkdtemp` dir, removed once
  the baseline snapshot has arrived (bash has read it) and on `close()`.
- TERM: `Session.__init__` sets `TERM` in the session's env; `dumb`/unset is replaced by
  `xterm-256color` because readline turns bracketed paste off on a dumb terminal.
- §2 records + §Versioning: `pty_protocol.py:101` (`\r` → malformed at `:106`; numbers
  bounded at `:41`), unknown types ignored at `:215`.
- §3 snapshot: rcfile `:89–114`; parsed in `pty_protocol.py:259`; required types missing →
  degraded (`:267`); baseline kept on the first `E`; `H` ≠ baseline → degraded (`:287`).
- §4.2 triggers: malformed / out of order (`pty_protocol.py:205` onward), control channel
  closed (`eof`, `:182`), back at a prompt (`session.py:601`), `H` changed (`:287`). Also:
  the shell exited (PTY EOF/EIO) and the caller's timeout ran out. Every trigger stores a
  human-readable reason; degraded is sticky (`ProtocolTracker.degrade` keeps the first
  reason) until `Session.restart()` (`session.py:319`).
- §5: `check_command` (`pty_protocol.py:123`) refuses paste-end, ESC, any C0 except TAB/LF,
  and blank commands, before anything is written. The paste + single CR is written in
  `run()` (`session.py:421`).
- §6: `run(..., terminal=Terminal(in_fd, out_fd))`: raw mode on `in_fd`, saved and restored
  with `TCSADRAIN` in `finally` (`:467`); input forwarded with `_forward` (`:639`; bytes go
  straight from `os.read` to `os.write`, never stored); PTY output mirrored to `out_fd`;
  `SIGWINCH` handler (`:458`, main thread only) pokes a self-pipe and the size is copied
  from `in_fd` to the PTY; the size is also copied once at the start of `run()`.

## Findings in the reference rcfile (report; spec not edited)

1. **`S 1\r\n`** — confirmed the planner's finding: `PS0` is decoded as a prompt string, so
   `\n` becomes CR LF. Fixed with `\\n` (`session.py:87`). Mutation check (iteration 1):
   putting `\n` back fails 34 of 35 tests.
2. **Multi-line commands write one `S` per line.** Probed: pasting `echo a\necho b` gave
   `S 2`, `S 2`, `D 2 0 0` — bash expands `PS0` for each command line. Fix (`session.py:87`):
   the `$(...)` part prints only if `__nls_ps0` isn't already this sequence number, and
   `${__nls_once[__nls_ps0=__nls_seq]-}` sets it (the array subscript is evaluated by the
   shell itself, so the assignment sticks and expands to nothing). `__nls_done` unsets it.
3. **`H` over every `PROMPT_COMMAND` element**: `declare -p` instead of `$PROMPT_COMMAND`, as
   the brief directs. Iteration 2 widens it to the hook functions and `__nls_user_pc`. The
   spec's wording "a cksum of `$PROMPT_COMMAND` and `$PS0`" should say so.
4. **`F` only when changed** is forgeable (iteration 2, §3 above). Now sent every time.
5. **The hooks were redefinable** (iteration 2, §2 above). Now read-only.
6. Smaller hardening, not in the reference: `__nls_done` uses `builtin`/`command` and is
   defined with alias expansion off (`:82`, restored at the end), so an alias or function
   named `printf`/`tr`/`cksum` doesn't rewrite the hook (but see the residual about a
   function named `builtin`); the user's saved `PROMPT_COMMAND` sees the command's real
   `$?` (`__nls_ret`). On this host `/etc/bash.bashrc` leaves `PROMPT_COMMAND` as an array
   (VTE / systemd OSC hooks). Element 0 is replaced; elements 1+ keep running after ours,
   which matches §1.2's ordering.
7. **Bracketed paste**: readline binds `ESC [200~` to paste handling regardless of
   `enable-bracketed-paste`, so a two-line command arrives intact even with `~/.bashrc`
   turning it off (and in vi mode). Forcing it on (`:81`) still matters: with it on,
   readline always writes `ESC [?2004l` when it hands the line to bash, which is where
   capture starts. Test (h) checks the setting survives `~/.bashrc`.

## Capture boundaries (the part the brief left open)

The two streams (PTY and fd 3) have no shared ordering, so "output between `S` and `D`"
can't be read off arrival order alone:

- **Start.** Readline's echo of the pasted command is written before `PS0`; a fast builtin
  (`pwd`) prints within ~100 µs after `S`. Capture starts after readline's `ESC [?2004l`
  (+ its `\r`), the first one after the send (`session.py:121`, `_OutputSplitter` `:231`).
  It can't be forged in that window: no command has started yet and the pasted bytes
  can't contain ESC (§5.2). If it never shows up, the fallback is "bytes read after `S`".
  This only places the capture boundary; start, done, status and snapshot still come only
  from fd 3 (vectors 4/5 pass).
- **End.** When `D` is read, the PTY is drained without waiting (`session.py:508`) and
  capture stops. The command's output was written before bash wrote `D`; the prompt comes
  only after the whole snapshot (several forks, ~10 ms). Heuristic, not a guarantee: a
  reader stalled >~10 ms right after `D` could pick up prompt bytes. In iteration 2: 4
  sequential runs and 1 run pinned to one core (`taskset -c 0`), 39/39 each time.
- **Alternate screen** (§6.2): `_Capture` (`:183`) drops everything between
  `ESC[?1049h`/`l`, `ESC[?47h`/`l` (and `ESC[?1047h`/`l`), handling sequences split
  across reads. Mirroring continues.
- **Forwarded input stops capture** (`session.py:529`). The PTY echoes typed input back as
  output; filtering it out would mean keeping the typed bytes (forbidden by §6.1). So once
  any byte is forwarded, capture stops for the rest of that command and
  `CommandResult.input_forwarded` is True. Trade-off: interactive commands lose captured
  output after the first keystroke.

## The back-at-a-prompt rule (§4.2 third trigger)

As the brief specified: after the send, if no `D` has arrived and the PTY's foreground
process group has been bash's own pid continuously for 1 s (`PROMPT_GRACE`,
`session.py:129`), the session degrades. Refinement: `_shell_busy` (`:618`) excludes bash
in state `R` and bash with a direct child in its own process group (`x=$(sleep 1.5)`),
read from `/proc`; without `/proc` it falls back to the brief's rule.

**Known false positives, accepted as fail-closed (the human should confirm at sign-off, as
the brief asks):** `read x`, `wait` on a background job, `select` degrade after 1 s. A
command left incomplete (unclosed quote, trailing `\`) leaves bash at `PS2` and also
degrades after 1 s.

## Other behaviour worth knowing for #78 / #12

- Degraded `run()` refuses (`SessionDegraded`); this slice offers only `restart()`. #78
  decides the UX for §4.3.
- Comment-only commands (`# x`) run no `PS0`, so `D` arrives without `S` → degraded.
  Blank commands are refused up front by `check_command`.
- `run(timeout=…)` running out degrades the session (the command may still be running).
- Between commands nobody reads the PTY; `run()` drains stale bytes before sending
  (`:441`). A background job writing >~4 KiB while idle would block until the next
  `run()`. #78 should keep reading the PTY at its prompt.
- A control record with `\r` (e.g. an alias value containing CR) degrades. Fail-closed.
- `SIGWINCH` is handled only when `run()` is called from the main thread.
- New in iteration 2: `F` comes in every snapshot, so `Snapshot.functions` is always the
  current list (not carried over).

## Rejected alternatives (with cost)

- Tolerate a repeated `S n` in the parser instead of the PS0 guard: ~4 lines in the
  tracker; rejected because it weakens the §4.2 order check. The guard is one line of bash.
- A nonce marker printed on the PTY to delimit capture: ~15 lines and changes what bash
  prints; readline's `ESC[?2004l` gives the start boundary with nothing added.
- Strip the echo of forwarded input from capture: needs the typed bytes kept. Ruled out by
  §6.1 and test (k).
- Iteration 2, finding 1: only catching `ValueError` (no digit bound) would also pass the
  test (1 line instead of 4). I kept both: the bound rejects the record at parse time with
  a clear reason, the `except` covers any conversion I missed.
- Iteration 2, finding 2: only adding the hook code to `H` (no `readonly`) would also pass
  the tests (they accept degrade). Rejected as the sole fix: it detects the change one
  prompt late, after the replaced hook has already run once and written its own snapshot
  and `__nls_user_pc` has already been eval'd. `readonly` stops it before it runs. Cost: 2
  lines of bash.
- Iteration 2, `F`: see §3 above.

## Test

`tests/test_session.py` — 39 tests. The session module is imported inside each test
(`importlib.import_module` via `_session_module()`), never at module level or in a
fixture, so the C4 red leg counts failures, not import errors. Every wait is bounded
(`START_TIMEOUT` 10 s, `RUN_TIMEOUT` 5 s, helper threads joined with timeouts); every
session is closed in `finally`. The `_session` helper checks after each test that every
record read ends in `\n` with no `\r` (criterion (j)).

Criteria → tests: (a) `:143`, `:149` · (b) vectors 1–8, 10 at `:158`–`:234` · (c) `:255`
· (d) `:279` · (e) `:298` · (f) `:323`, `:330` · (g) `:345`, `:361` · (h) `:433`, `:455` ·
(i) `:471` · (j) `:480`, `:486` + the `_session` teardown · (k) `:499`, `:507`, `:543`.
Iteration 2: `:369`, `:388`, `:402`, `:414`.

Runs (iteration 2):
- C4 gate (`engine/scripts/run-verify.sh` with `PDCA_BUNDLE`/`PDCA_WORKTREE` set): green leg
  ran 39, failed 0; red leg ran 39, failed 39, 0 import errors →
  `PDCA-EVIDENCE: C4 PASS — red without the fix (39 of 39 failed), green with it`.
- T3 (`engine/scripts/run-suite.sh`): 187 passed, `T3 PASS`.
- Repeat runs of the file: 4 sequential + 1 pinned to one core, 39/39 every time.

## Refuting my own test

- **(a) Genuine red?** Yes. The gate's red leg (all production hunks reverted): 39 of 39
  fail with `ModuleNotFoundError: No module named 'nl_shell.session'`. Since that red is
  just "module missing", I also checked the iteration-2 fixes one level finer, test
  unchanged:
  - New tests against the iteration-1 code (fix 1 and 2 absent): the done-hook test, the
    user-PC test and the oversized-number test all failed — the last with the exact
    `ValueError: Exceeds the limit (4300 digits)` at the old `pty_protocol.py:248`.
  - The old "send `F` only when changed" logic restored in `session.py`: the hidden-function
    test failed; fix restored: passed.
  - Iteration-1 mutation results (PS0 `\n`, PS0 guard, `H` element coverage, capture after
    input, alternate screen, forced bracketed paste, SIGWINCH, termios restore, prompt rule)
    still apply; the code they cover did not change.
- **(b) Production path?** Yes. Every session test drives `nl_shell.session.Session` on a
  real bash 5.3.9 on a real PTY through ptyprocess, with the real `RCFILE`. The parser
  tests drive `pty_protocol.ProtocolTracker`, the same class `Session` uses; the
  oversized-number test also drives it through a live session. The "real terminal" in (k)
  is an `os.openpty()` pair, as the brief specifies. No mocks.
- **(c) Fixture includes the fault?** Yes. Each attack runs in the live session: a real
  `eval` of a rewritten `__nls_done` plus a real new alias, a real assignment to
  `__nls_user_pc` with a real file it would create, a real `__nls_fsum` forgery with a
  real new function, and a real 5000-digit record written to fd 3. The tests check the
  observable harm (alias missing from `L`, file created, function missing from `F`,
  exception escaping), not just that a command returned non-zero.

## Commit-readiness

nl-shell has no formatter, linter config or commit hook (no `.pre-commit-config.yaml`, no
`core.hooksPath`, nothing in `pyproject.toml`; CI runs pytest and the docs checks only).
`git diff --check` is clean; all files compile. The new code follows the existing style;
the one line over 100 columns is the bash `PS0` string (`session.py:87`), which can't be
wrapped. No Markdown links or ADRs touched.

## Environment

`ptyprocess` 0.7.0 is importable from the gate venv; host bash is 5.3.9. No external
dependency beyond what the brief listed. Scratch probes live in `.probe/` in the worktree
(untracked, not in `patch.diff`).

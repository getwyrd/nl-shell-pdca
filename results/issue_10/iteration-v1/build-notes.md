# Build notes — issue 10 / persistent-bash-pty-session

Target: eduralph/nl-shell @ main (`e7bb63c`), worktree `nl-shell.pdca-wt-l0`. All `path:line`
below are in the patched tree. Spec = `docs/design/specs/pty-protocol/v1.md`; ADR =
`docs/design/adr/0014-pty-session-protocol.md`.

## What the patch adds

| File | What | Spec |
|---|---|---|
| `src/nl_shell/pty_protocol.py` (new, 284 lines) | Pure logic, no I/O. `parse_record` (:96), `check_command` (:118), `ProtocolTracker` (:141), the S → D → snapshot → E state machine. | §2, §3, §4, §5.2, §Versioning |
| `src/nl_shell/session.py` (new, 667 lines) | `RCFILE` (:70–:110), `Session.start/run/restart/close` (:302–:463), the forwarding loop `_wait_for_result` (:465), output splitting and alternate-screen capture (`_Capture` :176, `_OutputSplitter` :224), the back-at-a-prompt rule (`_back_at_prompt` :594, `_shell_busy` :611). | §1, §4.2, §5, §6; ADR Decision 1–4 |
| `tests/test_session.py` (new, 499 lines) | 35 tests, criteria (a)–(k). | §Conformance 1–12 |
| `pyproject.toml:15` | `ptyprocess>=0.7` | ADR-0021 |
| `.oss-scanner/threat_model.md:178` | §How to exercise it: how the session tests run, that they need only bash + ptyprocess. | — |

Split into two modules so the record parser and state machine can be tested without a
PTY (criterion (j)'s "a record containing `\r` fed to the record parser"). The session
uses the same `ProtocolTracker`, so that test drives production code.

### Spec section → code

- §1.1 start-up: `session.py:342` `_spawn` runs `bash --noprofile --rcfile <tmp> -i` via
  `ptyprocess.PtyProcess.spawn(..., pass_fds=(write_end,), preexec_fn=...)`; the
  `preexec_fn` (`:349`) `dup2`s the pipe's write end to fd 3. ptyprocess closes every other
  fd *before* calling `preexec_fn` (checked in ptyprocess 0.7.0 source), so the child holds
  only fd 3 of the pipe. The parent closes its write end right after spawn, so EOF on the
  read end means bash (and anything that inherited fd 3) closed it.
- §1.2/§1.3 rcfile: `session.py:70–110`. Written to a private `mkdtemp` dir, removed once
  the baseline snapshot has arrived (bash has read it) and on `close()`.
- TERM: `session.py:284–289` sets `TERM` in the session's env; `dumb`/unset is replaced by
  `xterm-256color` because readline turns bracketed paste off on a dumb terminal.
- §2 records + §Versioning: `pty_protocol.py:96` (`\r` → malformed at `:98`), unknown
  types ignored at `:207`.
- §3 snapshot: rcfile `:82–107`; parsed in `pty_protocol.py:251`; required types missing →
  degraded (`:259`); baseline kept on the first `E`; `H` ≠ baseline → degraded (`:279`).
- §4.2 triggers: malformed / out of order (`pty_protocol.py:200` onward), control channel
  closed (`eof`, `:177`), back at a prompt (`session.py:594`), `H` changed (`:279`). Also:
  the shell exited (PTY EOF/EIO) and the caller's timeout ran out. Every trigger stores a
  human-readable reason; degraded is sticky (`ProtocolTracker.degrade` keeps the first
  reason) until `Session.restart()` (`session.py:312`).
- §5: `check_command` (`pty_protocol.py:118`) refuses paste-end, ESC, any C0 except TAB/LF,
  and blank commands, *before* anything is written. The paste + single CR is written in
  `run()` (`session.py:414`).
- §6: `run(..., terminal=Terminal(in_fd, out_fd))`: raw mode on `in_fd`, saved and restored
  with `TCSADRAIN` in `finally` (`:460`); input forwarded with `_forward` (bytes go straight
  from `os.read` to `os.write`, never stored); PTY output mirrored to `out_fd`; `SIGWINCH`
  handler (`:451`, main thread only) pokes a self-pipe and the size is copied from `in_fd`
  to the PTY; the size is also copied once at the start of `run()`.

## Findings in the reference rcfile (report; spec not edited)

1. **`S 1\r\n`** — confirmed the planner's finding: `PS0` is decoded as a prompt string, so
   `\n` becomes CR LF. Fixed with `\\n` (`session.py:80`). Mutation check: putting `\n` back
   fails 34 of 35 tests (every session degrades on the first `S`).
2. **Multi-line commands write one `S` per line.** Probed: pasting `echo a\necho b` gave
   `S 2`, `S 2`, `D 2 0 0` — bash expands `PS0` for each command line it reads from the
   buffer. The brief's (f) needs exactly one pair. Fix (`session.py:80`): the `$(...)`
   part only prints if `__nls_ps0` isn't already this sequence number, and
   `${__nls_once[__nls_ps0=__nls_seq]-}` sets it. The `$(...)` runs in a subshell, but the
   array subscript is arithmetic evaluated by the shell itself, so the assignment sticks
   and expands to nothing. `__nls_done` unsets it. (The ADR's "PS0 can't advance a
   counter" holds for the `$(...)` only.) Mutation check: without the guard, the
   multi-line, multi-line-function and vi-mode tests fail.
3. **`H` over every `PROMPT_COMMAND` element**: `declare -p PROMPT_COMMAND PS0 2>&1 | cksum`
   (`:100`), as the brief directs. The spec's wording "a cksum of `$PROMPT_COMMAND`" should
   say every element. Mutation check: hashing `"$PROMPT_COMMAND" "$PS0"` instead makes the
   `PROMPT_COMMAND+=(':')` test fail.
4. Smaller hardening, not in the reference: `__nls_done` uses `builtin`/`command` and is
   defined with alias expansion off (`:75`, restored at the end), so an alias or function
   named `printf`/`tr`/`cksum` doesn't rewrite the hook; the user's saved `PROMPT_COMMAND`
   sees the command's real `$?` (`__nls_ret`). On this host `/etc/bash.bashrc` is still
   read before the rcfile and leaves `PROMPT_COMMAND` as an array (VTE / systemd OSC
   hooks). Element 0 is replaced; elements 1+ keep running after ours, which matches
   §1.2's ordering.
5. **Bracketed paste**: probing showed readline binds `ESC [200~` to paste handling no
   matter what `enable-bracketed-paste` says, so a two-line command arrives intact even with
   `~/.bashrc` turning it off (and in vi mode). Forcing it on (`:74`) still matters: with it
   on, readline always writes `ESC [?2004l` when it hands the line to bash, and that's the
   exact point where capture starts (next section). Test (h) checks the setting survives
   `~/.bashrc`; removing the `bind` line fails it.

## Capture boundaries (the part the brief left open)

The two streams (PTY and fd 3) have no shared ordering, so "output between `S` and `D`"
can't be read off arrival order alone:

- **Start.** Readline's echo of the pasted command is written *before* `PS0`; a fast builtin
  (`pwd`) prints within ~100 µs *after* `S`. If the reader is slow, both are already
  buffered when `S` is read. The fix: capture starts after readline's `ESC [?2004l` (+ its
  `\r`), the first one after the send (`session.py:114`, `_OutputSplitter` `:224`). It can't
  be forged in that window: no command has started yet and the pasted bytes can't contain
  ESC (§5.2). If it never shows up, the fallback is "bytes read after `S`". This only reads
  the PTY to place the capture boundary; start, done, status and snapshot still come only
  from fd 3 (vectors 4/5 pass).
- **End.** When `D` is read, the PTY is drained without waiting (`session.py:500`) and
  capture stops. The command's output was written before bash wrote `D`; bash's prompt
  comes only after the whole snapshot (several forks, ~10 ms) and the user's
  `PROMPT_COMMAND`. Heuristic, not a guarantee: a reader stalled for >~10 ms right after
  `D` could pick up prompt bytes. Under 6 test runs pinned to one CPU core
  (`taskset -c 0`), all 35 tests passed in all 6.
- **Alternate screen** (§6.2): `_Capture` (`:176`) drops everything between
  `ESC[?1049h`/`ESC[?1049l`, `ESC[?47h`/`l` (and `ESC[?1047h`/`l`, the third variant),
  handling sequences split across reads. Mirroring continues.
- **Forwarded input stops capture** (`session.py:522`). Criterion (k) requires the sentinel
  typed into `cat > /dev/null` to be absent from the captured output, but the PTY echoes
  typed input back as *output*. Filtering the echo out would mean matching it against the
  typed bytes, which means keeping them (forbidden by §6.1). So once any byte is forwarded,
  capture stops for the rest of that command and `CommandResult.input_forwarded` is True.
  Trade-off: interactive commands lose captured output after the first keystroke. It also
  covers ADR-0015's "a program that echoes its input" for #13. Mutation check: not
  stopping capture fails the sentinel test.

## The back-at-a-prompt rule (§4.2 third trigger)

As the brief specified: after the send, if no `D` has arrived and the PTY's foreground
process group (`os.tcgetpgrp(master)`) has been bash's own pid continuously for 1 s
(`PROMPT_GRACE`, `session.py:122`), the session degrades.

One refinement, found by probing (`/proc/<bash>/syscall`, `wchan`): `x=$(sleep 1.5)` also
leaves bash in the foreground (the substitution child stays in bash's process group), as
does a CPU-bound bash loop. With the brief's rule alone, `for f in $(find / …)` running
over 1 s would degrade a healthy session. `_shell_busy` (`:611`) excludes two cases: bash
in state `R`, and bash with a direct child in its own process group (`/proc/<pid>/task/<pid>/children`).
At a real readline prompt neither holds (bash sleeps in `pselect6` on fd 0, no child), so
this can't hide a real missing `D`. Without `/proc` it falls back to the brief's rule.
Probe: `x=$(sleep 1.5); echo y` → status 0, no degrade; `PROMPT_COMMAND=:` → degraded
after 1.01 s. Mutation check: disabling the rule fails vector 8 (it would hang until the
5 s timeout).

**Known false positives, accepted as fail-closed (the human should confirm at sign-off, as
the brief asks):** a builtin waiting on the terminal or a job with no child in bash's
group — `read x`, `wait` on a background job, `select` — degrades after 1 s. Also: a
command that leaves the input incomplete (unclosed quote, trailing `\`) leaves bash at
`PS2`; that degrades after 1 s too (no `S` ever comes, and nothing else could recover it
without parsing the PTY).

## Other behaviour worth knowing for #78 / #12

- **Degraded `run()` refuses** (`SessionDegraded`) instead of running commands with records
  it can no longer trust. Spec §4.3 says "every command MUST need a confirm" in degraded
  mode; with the record stream broken there is no reliable completion signal, so this
  slice offers only `restart()`. #78 decides the UX.
- **Comment-only commands** (`# x`) run no `PS0`, so a `D` arrives without an `S` → degraded
  ("without a start record"). Blank commands are refused up front by `check_command`.
  Detecting comment-only input would mean parsing shell syntax; left fail-closed.
- **Timeout** (`run(timeout=…)`) degrades the session: the command may still be running.
  `timeout=None` (the default) waits as long as the command runs.
- **Between commands nobody reads the PTY.** `run()` drains stale bytes (the prompt, job
  notices) before sending (`:434`). A background job that writes >~4 KiB while idle would
  block on the full PTY buffer until the next `run()`. #78 should keep reading (or
  mirroring) the PTY while the REPL is at its prompt.
- **A control record with a `\r`** (e.g. an alias whose value contains CR) degrades the
  session, as the brief requires for `\r` in records. Fail-closed.
- `SIGWINCH` can only be handled when `run()` is called from the main thread (Python's
  rule); off the main thread the size is copied once at the start of `run()` only.
- `fork` happens in `Session.start()`; Python 3.12+ warns if other threads are running at
  that point. The tests start sessions before their helper threads.

## Rejected alternatives (with cost)

- **Tolerate a repeated `S n` in the parser** instead of the PS0 guard: ~4 lines in
  `ProtocolTracker._handle` (accept `S seq+1` while RUNNING). Rejected: it weakens the
  order check that §4.2 relies on, and the brief's (f) asks for one pair *on the channel*.
  The guard costs one line of bash.
- **A nonce marker printed by `PS0`/`PROMPT_COMMAND` on the PTY** to delimit capture:
  ~15 lines (nonce, scan, strip from mirror), and it changes what bash prints. Rejected
  for the start because readline's `ESC[?2004l` already gives the same boundary with
  nothing added; for the end because anything bash prints, a command can print too.
- **Strip the echo of forwarded input from capture**: needs the typed bytes kept for
  matching. Ruled out by §6.1 and by test (k).

## Test

`tests/test_session.py` — 35 tests. The session module is imported inside each test
(`importlib.import_module` via `_session_module()`), never at module level or in a
fixture: a fixture import error counts as a *setup error*, not a failure, in
`engine/scripts/lib/junit_count.py`, so the C4 red leg would come out UNVERIFIABLE. Every
wait is bounded (`START_TIMEOUT` 10 s, `RUN_TIMEOUT` 5 s, helper threads bounded and
joined with timeouts); every session is closed in `finally`. The `_session` helper checks
after each test that every record read ends in `\n` with no `\r` (criterion (j)).

Criteria → tests: (a) `:143`, `:149` · (b) vectors 1–8, 10 at `:158`–`:234` · (c) `:255`
· (d) `:279` (6 forbidden-byte cases; checks no record arrived, no file was touched, and
the next command is seq 1) · (e) `:298` · (f) `:323`, `:330` · (g) `:345`, `:361` · (h)
`:372`, `:394` · (i) `:410` · (j) `:419`, `:425` + the `_session` teardown · (k) `:438`,
`:446`, `:482`.

Runs:
- C4 gate script (`engine/scripts/run-verify.sh`, with `PDCA_BUNDLE`/`PDCA_WORKTREE` set):
  green leg ran 35, failed 0; red leg ran 35, failed 35, 0 import errors →
  `PDCA-EVIDENCE: C4 PASS`. The tree was restored afterwards.
- T3 (`engine/scripts/run-suite.sh`): 183 passed.
- Repeat runs: 6 sequential, 8 in parallel, 6 pinned to one core: all 35 green every time.

## Refuting my own test

- **(a) Genuine red?** Yes. With the production hunks reverted (the gate's red leg) all 35
  fail with `ModuleNotFoundError: No module named 'nl_shell.session'` — failures, not
  import errors, because the import is inside each test body. That red is "module
  missing", so I also broke individual parts of the fix with the test unchanged, and the
  matching tests went red each time:

  | Mutation | Tests that went red |
  |---|---|
  | `\n` in PS0 (reference bug) | 34 of 35 |
  | no once-per-command guard in PS0 | multi-line, multi-line-function, vi-mode/bracketed-paste |
  | `H` over `$PROMPT_COMMAND $PS0` | `test_changed_hooks_degrade[pc-array]` |
  | capture keeps going after input | `test_forwarded_input_is_never_kept` |
  | no alternate-screen pause | `test_vector11_…` |
  | bracketed paste not forced | `test_bashrc_cannot_turn_bracketed_paste_off` |
  | no SIGWINCH handler | `test_window_size_follows_sigwinch` |
  | termios not restored | `test_terminal_attributes_are_restored`, `test_forwarded_input_is_never_kept` |
  | prompt rule disabled | `test_vector8_…` |

  The first "bracketed paste not forced" mutation stayed green, which showed the test
  didn't bind that line; I added the `bind -v` check and it now goes red. One mutation
  run also showed a real race in the `~/.bashrc` test (the user's `PROMPT_COMMAND` runs
  after `E`), now fixed with a bounded wait.
- **(b) Production path?** Yes. Every test drives `nl_shell.session.Session` on a real
  `bash` 5.3.9 on a real PTY through ptyprocess. The `\r` parser test drives
  `pty_protocol.ProtocolTracker`, the same class `Session` uses. The "real terminal" in (k)
  and vectors 10/11 is an `os.openpty()` pair, as the brief specifies: the session owns
  the slave side exactly as it would own `/dev/tty`. No mocks.
- **(c) Fixture includes the fault?** Yes. Each fault is really injected into the live
  session: forged `D`/OSC 133 records printed on the PTY, `PROMPT_COMMAND=:`, `exec 3>&-`
  (real EOF on the pipe), real `PS0` and array-`PROMPT_COMMAND` changes, a real
  `~/.bashrc` turning bracketed paste off with `set -o vi`, a real `\x03` byte typed on
  the fake terminal (`sleep` gets SIGINT, status 130), a real resize + `SIGWINCH`, and a
  real sentinel typed into `cat`. The sentinel test also has a positive control: the
  sentinel *is* found in the mirrored output and in the fake-terminal object, so the
  recursive `vars()` scan does find a copy when one exists.

## Commit-readiness

nl-shell has no formatter, linter config or pre-commit hook (no `.pre-commit-config.yaml`,
no hooks in the git dir; CI runs `pytest` and the docs checks only). The new code follows
the existing style (`from __future__ import annotations`, docstrings, ~90-column lines;
the one longer line is the bash `PS0` string, which can't be wrapped). Checked with an
`ast` pass: no unused imports. No relative links were added to Markdown, so
`scripts/docs_links.py` is unaffected; no ADR was touched.

## Environment

`ptyprocess` 0.7.0 is importable from the gate venv (the brief's doctor row is satisfied);
host bash is 5.3.9. No external dependency beyond what the brief listed.

Scratch probes live in `.probe/` in the worktree (untracked, not in `patch.diff`).

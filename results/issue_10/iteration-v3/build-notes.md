# Build notes — issue 10 / persistent-bash-pty-session (iteration 3)

Target: eduralph/nl-shell @ main (`e7bb63c`), worktree `nl-shell.pdca-wt-l0`. All `path:line`
below are in the patched tree. Spec = `docs/design/specs/pty-protocol/v1.md`; ADR =
`docs/design/adr/0014-pty-session-protocol.md`.

This iteration starts from the iteration-2 patch (`iteration-v2/patch.diff`, applied
unchanged) and fixes the three findings in the iteration-2 carry-forward. Everything
else from iterations 1 and 2 still holds; the full rationale for that part is in
`iteration-v2/build-notes.md` and is summarised below with updated line numbers.

## Iteration 3 — what changed and why

### 1. Alternate screen: capture resumed on any reset, not the matching one (§6.2)

Finding: `_Capture` (iteration 2, `session.py:199`) flipped a single on/off flag, and in
the "on" state any of `ESC[?1049l` / `ESC[?1047l` / `ESC[?47l` turned capture back on. So
`1049h … 47l SECRET2 … 1049l` captured `SECRET2`. Spec §6.2 (`v1.md:127-128`): "capture
MUST stop on `ESC [?1049h` / `ESC [?47h` … and resume on the matching reset".

Fix: `_Capture` (`session.py:200`) now parses DEC private-mode sequences in general,
`ESC [ ? <params> h|l` (`_MODE_SEQ`, `session.py:132`), and keeps a set of the
alternate-screen modes that are on (`_ALT_MODES` = 47, 1047, 1049, `session.py:131`).
`h` adds the sequence's alt modes, `l` removes only its own (`session.py:260`). Nothing is
captured while the set is non-empty (`_keep`, `session.py:219`). This also covers two
gaps of the same kind that the old fixed-string matcher had:
- several modes in one sequence (`ESC[?1;1049h`), which xterm accepts;
- leading zeros (`ESC[?01049h`), which xterm reads as 1049.
Mode sequences that set no alt mode (cursor `?25l`, paste `?2004h`, …) are captured as
text, as before. A sequence split across reads is held back until complete, up to
`_MODE_MAX` = 4096 bytes (`session.py:137`); a longer run is treated as text.

Tests: `test_alternate_screen_capture_resumes_only_on_the_matching_reset`
(`tests/test_session.py:311`, live session + fake terminal: mismatched `47l` inside
`1049h`, and `?1;1049h` / `?1049;1l`; checks the hidden parts are still mirrored) and
`test_alternate_screen_switch_split_across_reads` (`:325`, feeds production `_Capture`
one byte at a time, with a leading-zero switch and a mismatched reset).

Not handled: the 8-bit CSI form (byte 0x9b instead of `ESC [`). Terminals only honour it
outside UTF-8 mode; I left it out rather than guess. Reporting it for the human.

Real-terminal note: in xterm, `47l` after `1049h` actually switches the display back to
the normal screen. The spec says "matching reset", and the finding asks for that, so I
followed the spec; this errs towards capturing less, which is the fail-safe side.

### 2. A newline in `PATH` could inject records and forge the snapshot

Finding: `P` was written raw (`builtin printf 'P %s\n' "$PATH"`). A `PATH` ending in
`\nJ 0\nH <baseline H>\nV <baseline V>\nE\nZ` closed the snapshot early with the
baseline's `H`/`V`, so an `LD_PRELOAD` set in the same command was hidden, and `run()`
returned the forged snapshot as success. Two Python-side gaps let it through: `run()`
sent the next command without reading the control channel first, and the `E` branch
returned before the degraded check.

Three fixes, one per cause:

a. **Root cause — encode `P`** (`session.py:105`): `P` now goes through
   `command tr '\n' '\036'` like `L`/`T`/`B`. The parser decodes it back
   (`pty_protocol.py:279`: strip the one trailing `\x1e` the here-string adds, then
   `\x1e` → `\n`), so `Snapshot.path` is the real `PATH`, newline and all, which is what
   a gate needs to see. I checked every other snapshot record for raw session state:
   `F` (via `tr`), `L`/`T`/`B` (via `tr`), `X` (fixed text), `J` (a count), `H`/`V`
   (`cksum`), `D` (numbers). None carries a raw newline now. A `\r` in any value makes
   the record malformed and degrades (fail-closed, unchanged).
   Trade-off: a `PATH` that really contains byte `\x1e` is reported with `\n` in its
   place. Either is an odd `PATH` a gate should flag; I did not add an escape scheme for
   it (would need changes to `L`/`T`/`B` too, for the same ambiguity they already have
   under the spec's own encoding).
   Rejected alternative: refuse a `PATH` with a newline (degrade). It costs the same
   (the rcfile still has to encode or test for the newline so it can't inject records,
   plus one parser line to degrade on `\x1e`), so cost doesn't decide it. It would end
   the session over a state the gate could simply report. Encoding matches how the spec
   already treats `L`.
b. **Read stray records before sending** (`session.py:506`, `_drain_control` at
   `:658`): `run()` reads whatever is waiting on fd 3 before `command_sent()`. The
   tracker is IDLE then, and any record in IDLE is "out of order" (`pty_protocol.py:223`),
   so the session degrades and `run()` raises before bash gets the command.
c. **`E` no longer returns early** (`session.py:582-612`): the `E` event only records the
   snapshot; the loop then reads anything else already in the pipe (`:586`), runs the
   degraded check (`:600`), and only then builds the result (`:602`). A record after `E`
   in the same read, or already waiting, now degrades instead of being left for later.

Tests:
- `test_newline_in_path_cannot_forge_the_snapshot` (`tests/test_session.py:456`) — the
  finding's reproducer with the live baseline's `H`/`V`: expects `vars_sum` to differ
  from the baseline (LD_PRELOAD visible), `snapshot.path == baseline.path + injected`,
  not degraded, and the next command works.
- `test_record_after_the_end_of_a_snapshot_degrades` (`:491`) — a command writes a full
  forged snapshot plus one more `D` to fd 3 in a single `printf`; expects
  `SessionDegraded` ("out of order") instead of the forged result.
- `test_stray_records_degrade_before_the_next_command_is_sent` (`:503`) — a command
  writes a forged snapshot to fd 3 then sleeps 0.5 s, so the real `D 1` and snapshot
  arrive after `run()` returned; the next `run("touch <marker>")` must raise and the
  marker must not exist (the command never reached bash).

**Residual, for the human (out of this slice's scope):** any command can still write a
complete, well-formed forged `D`/snapshot/`E` to fd 3 and then stall (the third test does
exactly that). `run()` returns that forged result; the real records are caught before the
next command is sent, so the session degrades one command later, never silently. Closing
this fully needs the command to be unable to write fd 3 at all, which is the policy
gate's fd-3 rejection (#12, out of scope per the brief) or a protocol change (e.g. a
per-command nonce the command can't read — it can, it runs in the same shell). Worth
stating in #12: the gate's fd-3 rule is what makes the `run()` result trustworthy, not
just defence in depth.

### 3. Captured output had no size limit

Finding: `_Capture.data` and `_OutputSplitter._since_start` grew without bound (e.g.
`run("yes")` with no timeout → OOM).

Fix: `MAX_OUTPUT` = 1 MiB (`session.py:141`), overridable per session with
`Session(max_output=…)` (`session.py:342`). `_Capture._keep` (`:219`) drops the oldest
bytes past the limit and sets `truncated`; `_OutputSplitter` bounds its fallback buffer
the same way (`:310`). `CommandResult.output_truncated` (`:192`, default False so the
field is additive) reports it (`:612`). The mirror to the terminal is not affected —
only the copy kept for the caller. The remaining buffers are already bounded: the
`_LINE_ACCEPTED` window (7 bytes), the capture's held-back partial sequence (≤ 4096),
and the control channel (`MAX_RECORD`, 1 MiB).

1 MiB is a guess at "comfortably more than a state block needs". The state block (#11)
truncates further anyway. Easy to change.

Tests: `test_captured_output_is_bounded_and_keeps_the_tail` (`tests/test_session.py:659`;
live: 1 MB of output with `max_output=65536` → truncated, ≤ 64 KiB, ends in the
`END_MARK` line; a small command is not truncated; the default is `MAX_OUTPUT`) and
`test_output_before_the_line_is_accepted_is_bounded` (`:672`; production
`_OutputSplitter` fed 100 kB without the accept marker → ≤ 100 bytes).

I did not add a test with `yes` and no timeout: it would need a timeout to stop, and a
bounded `head -c 1000000` exercises the same code path deterministically.

## What the patch adds (all iterations)

| File | What | Spec |
|---|---|---|
| `src/nl_shell/pty_protocol.py` (new, 295 lines) | Pure logic, no I/O. `parse_record` (:101), `check_command` (:123), `ProtocolTracker` (:146), the S → D → snapshot → E state machine (`_sequence` :213, `_end_snapshot` :259). | §2, §3, §4, §5.2, §Versioning |
| `src/nl_shell/session.py` (new, 754 lines) | `RCFILE` (:81–:121), `Session.start/restart/run` (:370, :380, :482), the forwarding loop `_wait_for_result` (:539), capture (`_Capture` :200, `_OutputSplitter` :280), the back-at-a-prompt rule (`_back_at_prompt` :681, `_shell_busy` :698). | §1, §4.2, §5, §6; ADR Decision 1–4 |
| `tests/test_session.py` (new, 682 lines) | 46 tests: criteria (a)–(k) plus the iteration-2 and -3 cases. | §Conformance 1–12 |
| `pyproject.toml` | `ptyprocess>=0.7` in `dependencies` | ADR-0021 |
| `.oss-scanner/threat_model.md` | §How to exercise it: how the session tests run; they need only bash + ptyprocess. | — |

### Spec section → code (carried from iteration 2, line numbers updated)

- §1.1 start-up: `_spawn` (`session.py:410`) runs `bash --noprofile --rcfile <tmp> -i` via
  ptyprocess with `pass_fds` and a `preexec_fn` that `dup2`s the pipe's write end to fd 3.
  The parent closes its write end, so EOF on the read end means the channel closed.
- §1.2/§1.3 rcfile: `session.py:81–121`; written to a private `mkdtemp` dir, removed once
  the baseline snapshot arrived and on `close()`.
- `TERM`: set in the session env; `dumb`/unset → `xterm-256color` (readline turns
  bracketed paste off on a dumb terminal).
- §2/§Versioning: `parse_record` (`\r` → malformed; numbers bounded to 18 digits at
  `pty_protocol.py:41`); unknown types ignored in `_sequence`.
- §3: rcfile records; baseline kept on the first `E`; `H` ≠ baseline → degraded
  (`pty_protocol.py:290`).
- §4.2 triggers: malformed / out of order (incl. stray records after `E` — iteration 3),
  control channel closed, back at a prompt, `H` changed; also shell exited and caller
  timeout. Degraded is sticky until `restart()`.
- §5: `check_command` refuses paste-end, ESC, any C0 except TAB/LF, and blank commands,
  before any write; paste + single CR in `run()`.
- §6: raw mode on `terminal.in_fd`, restored with `TCSADRAIN` in `finally`
  (`session.py:534`); input forwarded by `_forward` (`:719`) and never stored; PTY output
  mirrored; `SIGWINCH` (`:525`, main thread only) copies the size.

### Findings in the reference rcfile (reported; spec not edited)

1. `S 1\r\n`: `PS0` is decoded as a prompt string, `\n` → CR LF. Fixed with `\\n`.
2. Multi-line commands wrote one `S` per line; `PS0` guarded with `__nls_ps0`.
3. `H` must cover every `PROMPT_COMMAND` element (`declare -p`), plus the hook functions
   and `__nls_user_pc` (iteration 2). The spec's "a cksum of `$PROMPT_COMMAND` and `$PS0`"
   should say so.
4. `F` "only when changed" is forgeable (iteration 2); sent every time now. The spec's §2
   table should say "every snapshot".
5. Hooks were redefinable (iteration 2); now `readonly`.
6. **New in iteration 3:** `P` must be encoded (`$PATH` can hold a newline). The spec's §3
   says "`P` (`$PATH`)"; it should say "with newlines as `\x1e`, like `L`".

### Residual risks (human call)

- A function named `builtin` (or `command`) shadows the hook's calls; bash has no
  unshadowable command. Detailed in `iteration-v2/build-notes.md` §Residual. Suggest #12
  refuse defining those names.
- Forged fd-3 records from a command (above, iteration 3 §2): caught one command late.
- Back-at-a-prompt false positives (`read x`, `wait`, `select`, an unclosed quote at
  `PS2`) degrade after 1 s — fail-closed, as the brief accepted; the human should confirm.

## Test runs (iteration 3)

- C4 gate (`engine/scripts/run-verify.sh`, `PDCA_BUNDLE`/`PDCA_WORKTREE` set): red leg
  ran 46, failed 46, 0 import errors; green leg 46/46 →
  `PDCA-EVIDENCE: C4 PASS — red without the fix (46 of 46 failed), green with it`.
- T3 (`engine/scripts/run-suite.sh`): 194 passed, three runs in a row, plus one run pinned
  to one core (`taskset -c 0`): 194 passed each time.

## Refuting my own test

- **(a) Genuine red?** Yes, at two levels.
  - Gate red leg (all production files reverted): 46 of 46 fail. That red is only
    "module missing", so I also ran the suite runner against the **iteration-2**
    `session.py`/`pty_protocol.py` with the new test file: exactly the 7 new tests
    failed, 187 passed.
  - Then I reverted each iteration-3 fix **alone** on the final code (suite runner,
    full suite each time):
    - `P` written raw again → only `test_newline_in_path_cannot_forge_the_snapshot` fails.
    - pre-send `_drain_control` removed → only
      `test_stray_records_degrade_before_the_next_command_is_sent` fails.
    - `E` returns before the degraded check, no post-`E` drain → only
      `test_record_after_the_end_of_a_snapshot_degrades` fails.
    - any reset clears all alt modes → the two alternate-screen tests fail.
    - cap disabled (`if False:` in `_keep`) → only
      `test_captured_output_is_bounded_and_keeps_the_tail` fails.
    Each fix restored → 194 passed.
- **(b) Production path?** Yes. Live tests drive `nl_shell.session.Session` on real bash
  5.3.9 through ptyprocess with the real `RCFILE`. The two unit tests drive the
  production `_Capture` and `_OutputSplitter` classes, the same ones `run()` uses. No
  mocks or copies.
- **(c) Fixture includes the fault?** Yes. The `PATH` attack is the finding's reproducer
  run in the live session with the live baseline's `H`/`V`; the fd-3 forgeries are real
  writes to the real control pipe; the mismatched reset is a real `printf` through the
  PTY into the real capture; the output cap test pushes 1 MB through the real PTY. Each
  test checks the harm itself (forged `V` accepted, marker file created, `SECRET2`
  captured, buffer size), not a proxy.

## Commit-readiness

nl-shell has no formatter, linter config or commit hook (no `.pre-commit-config.yaml`, no
`core.hooksPath`, no ruff/black/flake8 config in `pyproject.toml`). `git diff --check` is
clean; all files compile. The one line over 100 columns is the bash `PS0` string
(`session.py:91`), which can't be wrapped. No Markdown links or ADRs touched in this
iteration.

## Environment

`ptyprocess` 0.7.0 in the gate venv; host bash 5.3.9. No external dependency beyond the
brief's list. Scratch files (iteration-2 sources and a mutation helper used for the checks
above) are in `.probe/` in the worktree, untracked and not in `patch.diff`.

# Build notes — #102 session terminal ownership (pty-protocol v1 §6), iteration 4

Target: eduralph/nl-shell, integration branch at `cefb359` (#140 + #141 + #143 folded onto
`main`). Line numbers are on that tree with this `patch.diff` applied (worktree
`nl-shell.pdca-wt-l0`).

## What this iteration changes

I applied `iteration-v3/patch.diff` unchanged (it applied cleanly to `cefb359`) and made only
the two changes the round-3 sign-off asked for. `session.py`, ADR-0014 and the rest of the
patch are as in v3.

### 1. A `0x9b` inside a UTF-8 character is no longer read as 8-bit CSI (fixed)

Cause: v3's `_PRIVATE_MODE` matched any `0x9b` byte as CSI. In UTF-8 that byte is also a
continuation byte (`Û` = C3 9B, `ћ` = D1 9B), so `printf 'Û?1049h'` stopped capture, and on
the alternate screen a `Û?1049l` resumed it while the terminal was still there.

Fix (§6.2), `src/nl_shell/session_terminal.py`:
- `_c1_csi_at(text, i)` (`:79`) walks back up to three bytes from the `0x9b` to find the
  lead byte of the character it sits in. If a lead byte other than C2 (C3–F4) starts a
  character long enough to contain the `0x9b`, it is text. C2 9B is U+009B,
  the CSI character itself, so it still counts. A stray `0x9b` (after ASCII, or after a
  character that already ended) is the raw C1 code and still counts, as in v3.
- `_PRIVATE_MODE` (`:70`) and `_PRIVATE_MODE_START` (`:72`) now take `\xc2?\x9b`, so for
  U+009B the C2 lead byte is part of the sequence. Without that, v3 left a lone C2 in the
  capture before the text after a U+009B sequence (it showed up as `�A11` in the red run
  below).
- `_AltScreen.filter` (`:135`) skips a match that starts with a `0x9b` inside a character
  (`:143`); the bytes stay plain output. It keeps the last three bytes before the held tail
  in `self._before` (`:133`, set at `:161`), so a character cut between its lead byte and
  the `0x9b` by a PTY read boundary is still seen as one character.
- `_held_tail` (`:101`) does not hold back a tail that starts with such a `0x9b`, and holds a
  trailing C2 so a U+009B split across reads is matched whole.
- Spec §6.2 (`docs/design/specs/pty-protocol/v1.md:449-451`) now says the 8-bit CSI is
  `0x9b` alone or U+009B, and that a `0x9b` inside another UTF-8 character is text.

Tests:
- `test_alternate_screen_is_mirrored_but_not_captured` (`tests/test_session_terminal.py:174`)
  gains four `printf` lines (`:191-194`): `Û?1049h … ћ?47l` on the main screen (captured as
  text), `ћ?47l` and `Û?1049l` while on the alternate screen (capture must stay off until
  the real reset), and U+009B set/reset (still treated as CSI). Octal escapes, so the
  command does not depend on bash's locale.
- New `test_utf8_text_is_not_read_as_8_bit_csi_when_split_across_reads` (`:216`) feeds the
  production `_AltScreen` whole and one byte at a time, for the 2-byte, 3-byte, U+009B and
  stray-`0x9b` cases. Split reads cannot be forced from bash, so this test calls the filter
  directly.

Choice between the two options in the carry-forward: I kept 8-bit CSI matching and made it
UTF-8 aware rather than dropping it. Dropping it would bring back the round-2 finding (a
C1-accepting terminal switches screens on `0x9b?1049h` while capture continues) and change
the v3 `\233?47h` test line the human asked to keep. Cost of the kept option: about 30 lines
(`_c1_csi_at` 21 lines, plus 9 changed lines in `_held_tail`/`filter`).

### 2. Known-gaps line for the Ctrl-C-at-command-end race (added)

`.oss-scanner/threat_model.md:226-231`: a Ctrl-C typed in the few milliseconds after a
command ends reaches bash while its prompt hook runs and degrades the session until
`restart()`. Accepted for v1 by the human at round-3 sign-off; this only documents it. No
code change.

## Results

- `tests/test_session_terminal.py` alone (venv python, `timeout 200`): `19 passed` in 22 s.
- Whole suite through `engine/scripts/run-suite.sh` (`PDCA_WORKTREE` set to the worktree,
  wrapped in `timeout 590`): `500 passed, 1 warning`, `PDCA-EVIDENCE: T3 PASS`. That
  includes `tests/test_session.py` unchanged. The warning (`forkpty()` in a multi-threaded
  process) was there in earlier iterations.
- `python -I scripts/docs_links.py` → `63 relative links in 55 Markdown files, 0 broken`.

## Refutation (forced)

**(a) Genuine red? Yes.**
- Whole patch: with `src/` at the base, every test in the file fails (no
  `nl_shell.session_terminal`), same as v1–v3.
- This iteration: I moved the fixed module aside, re-created v3's `session_terminal.py`
  from `iteration-v3/patch.diff` (`git apply --include=…`), kept the new tests, and ran the
  two alt-screen tests: `2 failed`. The e2e test failed on content
  (`'…HIDDEN12…A10\n�A11\n'` vs the expected text: the `Û?1049h` line was cut and a stray
  C2 was left). The split test failed on its first case (`b'A\xc3'` vs
  `b'A\xc3\x9b?1049hB\n'`). Then I put the fixed module back: `19 passed`.

**(b) Production path? Yes.** The e2e test calls the real `Session.run(…,
terminal=Terminal(…))` against real bash on a ptyprocess PTY; bash's `printf` emits the
bytes and they go through `_Output` → `capture()` → `_AltScreen.filter`. The split test
calls the same production `_AltScreen` class, no copy.

**(c) Fixture includes the fault? Yes.** The commands print exactly the bytes from the
finding (C3 9B and D1 9B followed by `?1049h` / `?47l`), both on the main screen and inside
an alternate screen, and the split test cuts between lead byte and `0x9b`.

## Open for sign-off

- **Stray `0x9b` on a UTF-8 terminal (not fixed, same class, low).** A UTF-8 terminal
  shows a lone `0x9b` as U+FFFD, not CSI. So a program on the alternate screen (entered
  with a real `ESC [?1049h`) can print a stray `\x9b?1049l` and capture resumes while the
  user still sees the alternate screen. The human asked to keep the 8-bit handling
  otherwise as is, so I did not change it. A fix that closes it: let 8-bit forms only stop
  capture and resume only on `ESC [` resets (about 3 lines in `filter`: skip the
  `self.mode = None` branch when the match does not start with `\x1b`). It changes the
  expected capture of the v3 `\233?47h…\233?47l A7` line (`A7` would no longer be
  captured), which is why it needs a human call.
- Carried from v3, already decided: the residual drain race, the Ctrl-C race and the
  unfiltered mirror are accepted for v1. The rendering-filter issue still needs a number in
  the threat model Known gaps and the #78 gate line.

## The v1–v3 design (unchanged, re-cited)

Full detail is in `iteration-v3/build-notes.md`. `session.py` line numbers there still hold;
`session_terminal.py` numbers from `Terminal` onwards are now:
`Terminal` `:202`, `own()` `:210`, `_Ownership` `:215`, `begin()` `:242` (§6.1 start:
termios saved, raw mode, `tcflush(TCIFLUSH)`), `stop()` `:261` (at `D`), `end()` `:266`
(§6.5, nested `finally`s), `pump()` `:312` (§6.1 forwarding, ≤ `CHUNK = 1024` per write,
fd-3 check before each), `mirror()` `:357` / `_write_mirror` `:370` / `settle()` `:395`
(§6.2 copy, non-blocking through `_open_private` `:171`), `capture()` `:424` (decision 7),
`_on_winch` / `_copy_size` `:437`, `:440` (§6.3). §6.4 needs no code (raw mode clears ISIG
on the real terminal).

## Housekeeping

- No formatter or commit hook is configured in the target (no `.pre-commit-config.yaml`,
  no ruff/black/flake8 config in `pyproject.toml`; CI runs pytest and the docs checks). No
  line over 100 characters in the touched Python files (`awk 'length > 100'`).
- Untracked in the worktree, not in the patch: `src/nl_shell/session_terminal.py.v3` (the
  v3 module used for the red run) and two `tmp.*` pycache dirs from the direct pytest runs.
  `patch.diff` was made with `git diff` on the six touched paths only. New files are
  intent-to-add (`git add -N`). Nothing deleted; the harness reclaims the worktree.
- Nothing pushed, no PR opened.

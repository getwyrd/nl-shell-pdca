## Summary
**User impact:** when nl-shell runs a command for you in its bash session, your
keyboard and window are not connected to that command. A program that asks you
something (a pager, an editor, a `y/n` prompt) gets no keys, Ctrl-C does not stop a
command that hangs, resizing the window does not reach it, and keys you type while it
runs could end up anywhere — including in front of the next command you confirm. This
matters once the session runs confirmed commands (#78); today the session is built but
not wired up yet.

This PR hands the real terminal to the running command, from the moment it is sent
until it finishes, and gives it back cleanly afterwards.

Reported in [#102](https://github.com/eduralph/nl-shell/issues/102).

Builds on #140 (PR #146, commit `7d657847d4a701d5f676429807ca2b3e40640024`) and #141
(PR #154, commit `3e30813047f3a5bb6beb2d9d28c21be352a4dc12`) and should merge after
them.

## What to look at
- **The idea:** while a command runs, your keys go straight to it, unchanged, and are
  never logged or kept. Its output is shown to you and also saved for later use, except
  what a full-screen program draws (like `less` or `vim`), which you see but nl-shell
  does not save. Once you have typed into a command, the rest of its output is not saved
  either, and the result says so.
- **Keys typed ahead are thrown away, not reused.** Anything you typed that the command
  did not read is cleared before bash reads its next line, so it can never be glued onto
  the next command you confirm.
- **Your terminal is always put back** the way it was: after a normal run, after the
  session breaks, and after an error halfway through.
- **Try it:** the new tests use a fake terminal pair, so no real terminal is needed:
  `python3 -m pytest tests/test_session.py tests/test_session_terminal.py`. They type
  Ctrl-C into `sleep 5`, type a secret into `cat > /dev/null` and search everywhere for
  it, type ahead during `sleep 2`, resize the window during `sleep 1; stty size`, and
  compare the terminal's settings before and after.
- **Known limits, written down in the threat model:** a narrow timing race can still let
  a typed-ahead key reach the next command; the copied output is not filtered yet (the
  rendering filter is a separate issue and #78 must wait for it); and a Ctrl-C pressed in
  the few milliseconds after a command ends breaks the session until it is restarted. One
  more small gap: a lone `0x9b` byte after plain ASCII text is still read as the start of
  a terminal control sequence, so crafted output can resume saving while a full-screen
  program is still showing. The follow-up is to treat only the two-byte UTF-8 form
  (`C2 9B`) that way. The impact is low, because saved output is treated as untrusted
  anyway.

## Root cause
`Session.run()` from #140 only wrote the command to bash and read its output; nothing
connected the user's terminal to the session's PTY (the pseudo-terminal bash runs on)
while the command ran. Spec `pty-protocol/v1` §6 described what should happen, but no
code implemented it.

## Fix
- New module `src/nl_shell/session_terminal.py`. `Terminal` wraps the real terminal's
  fds (so tests can pass an `os.openpty()` pair). `_Ownership` does the work for one run:
  `begin()` saves the settings, sets raw mode and flushes earlier input; `pump()`
  forwards input in chunks of at most 1 KB and checks bash's control channel before each
  write; `stop()` ends forwarding at the done record; `end()` restores everything in
  nested `finally` blocks. Output is copied through a private non-blocking handle (so
  other writers to the same terminal are not affected), with a 1 MiB queue and a 1 s
  final flush, so a terminal that stops reading cannot stall the run.
- `_AltScreen` stops capture on modes 1049, 47 and 1047 and resumes only on the reset of
  the same mode. It reads the whole parameter list (`ESC [?25;1049h`), accepts the 8-bit
  CSI form, does not mistake a `0x9b` byte inside a UTF-8 character (`Û` is `C3 9B`) for
  one, and handles sequences split across reads.
- `src/nl_shell/session.py`: `run()` takes an optional `terminal=`; the result gains
  `input_forwarded` and `mirror_dropped`; the prompt hook drains bash's stdin with
  `builtin read -N 4096 -t 0.05` as its last step before `E`. `SIGWINCH` copies the
  terminal size to the PTY, and the previous handler is restored after the run.
- Docs: spec §1.3 (reference rcfile), §6.1 (discard and the known race) and §6.2 (all
  three modes, matching reset, 8-bit CSI and UTF-8); ADR-0014 Decision 4 now says the
  window runs from sending the command to the done record; the threat model gets the
  test description and three Known-gaps entries.

## Verification
- **Claim:** keys reach the command unchanged and are kept nowhere.
  **Checked:** `src/nl_shell/session_terminal.py:312` (`pump`), `:242-250` (`begin`,
  raw mode), `src/nl_shell/session.py:755` (forwarding stops at `D`).
  **Test:** `test_forwarded_input_reaches_the_program_and_is_kept_nowhere`
  (`tests/test_session_terminal.py:303`) scans the result, the session and terminal
  objects (including closures), module globals and DEBUG logs for the typed sentinel;
  `:353` and `:381` check nothing is forwarded after `D` or before the run.
- **Claim:** Ctrl-C typed on the terminal interrupts the command (status 130 within 2 s)
  and the session stays healthy.
  **Test:** `tests/test_session_terminal.py:238`.
- **Claim:** typed-ahead input never joins the next command, in emacs and vi mode, even
  for a 200 KB burst, and the drain keeps a plain `true` under 0.5 s.
  **Checked:** `src/nl_shell/session.py:258-262` (drain before `E`).
  **Test:** `tests/test_session_terminal.py:398`, `:414`, `:451`, `:574`.
- **Claim:** full-screen output is shown but not saved; capture resumes only on the
  matching reset; UTF-8 text with a `0x9b` byte is not read as a control sequence.
  **Checked:** `src/nl_shell/session_terminal.py:70-98` (`_PRIVATE_MODE`,
  `_c1_csi_at`), `:124-161` (`_AltScreen.filter`); spec
  `docs/design/specs/pty-protocol/v1.md:444-451`.
  **Test:** `tests/test_session_terminal.py:174` (real bash, `printf`) and `:216` (the
  filter fed whole and one byte at a time).
- **Claim:** capture stops at the first typed byte and the result says so.
  **Test:** `tests/test_session_terminal.py:588`.
- **Claim:** a window resize reaches the command (`stty size` prints `40 100`).
  **Checked:** `src/nl_shell/session_terminal.py:437-440`.
  **Test:** `tests/test_session_terminal.py:610`.
- **Claim:** the terminal's settings are restored after a normal run, a broken session
  and an exception mid-command; a slow terminal does not stall the run; the terminal's
  shared fd flags are left alone.
  **Checked:** `src/nl_shell/session_terminal.py:266-292` (`end`).
  **Test:** `tests/test_session_terminal.py:638`, `:648`, `:664`, `:499`, `:552`.
- **Red/green:** all 19 tests in `tests/test_session_terminal.py` fail without the change
  (the module does not exist) and pass with it. The whole suite passes (500 tests),
  including `tests/test_session.py` from #140/#141 unchanged; the docs link check finds
  no broken links.
- **Known gaps:** `.oss-scanner/threat_model.md:212-232`.

Fixes #102

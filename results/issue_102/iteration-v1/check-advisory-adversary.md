# Adversarial review — #102 session-terminal-ownership

Tooling: pytest is not installed in this sandbox, so I could not re-run the suite as-is. Real bash 5.3 and `ptyprocess` are present, so I drove the patched `Session.run(…, terminal=Terminal(fd))` directly with standalone scripts (an `os.openpty()` pair as the user's terminal, scratch `HOME`). I took the red→green evidence from the frozen logs: `gate-logs/C4-verify.log` shows 15/15 failing before the fix and 15/15 passing after; `gate-logs/T3-suite.log` shows 496 passed; `tests/test_session.py` has no diff.

## Findings

- NEEDS-HUMAN [human] — `src/nl_shell/session_terminal.py:46-49`: the alternate-screen check only matches the three sequences as single parameters, so a multi-parameter DECSET (a "set private mode" sequence that sets several modes at once, which xterm accepts) gets past it and the alternate-screen output is captured. Reproduced: `printf 'A\n\033[?1049;25hSECRET1\033[?1049;25lB\n'; printf '\033[?25;1049hSECRET2\033[?25;1049lC\n'` returned `result.text` with `SECRET1` and `SECRET2` in it. This does follow the letter of the new §6.2 text (`docs/design/specs/pty-protocol/v1.md` §6.2 names the literal sequences), so the gap is in the spec as much as in the code. A human should decide whether §6.2 means "mode 1049/47/1047 set by any `CSI ? Pm h`" (then the regex should parse the parameter list, and probably 8-bit CSI `\x9b` too) or only the literal forms. It is rare in practice (most TUIs send `\x1b[?1049h` on its own), but it is a concrete capture leak.

- C4 red leg is weaker evidence than it looks: `tests/test_session_terminal.py` imports the new module inside each test, so all 15 reds are `ModuleNotFoundError`. That proves the tests depend on the module. It does not prove each test catches its own defect. I checked the one that matters most, decision 6 (`tests/test_session_terminal.py:359`), by removing the drain from `RCFILE` (`src/nl_shell/session.py:258-262`) and replaying its scenario. Without the drain the next `true` returned `'INJECTED\n'`; with it, `''`. So that test really checks the drain. I did not do the same mutation check for the other 14 tests. Not a refutation.

## Attempted refutations that failed (the fix held)

- Ctrl-C mashed across the command's end (`\x03` every 2 ms from 0.1 s to 0.7 s around `sleep 0.3`, 5 trials): I wanted a `\x03` to land in the prompt hook or drain (`src/nl_shell/session.py:258-262`), abort it before `E`, and degrade the session. Every trial gave status 130, no degrade, and the next `echo ok` was clean.
- Typed-ahead edge cases during `sleep 2`, each followed by `true`: a lone Ctrl-D (`\x04`), `\x04\x04\x04`, `abc\x04`, 5000 NUL bytes followed by `echo INJECTED; ` (to make `read -N` return a chunk that is all NULs and end the drain loop early), and a full line `echo INJECTED\r`. In every case the next result was `''` with status 0, no degrade, and bash did not exit.
- Window size at the start of a run (`_copy_size` in `begin()`, `session_terminal.py:150`) with the terminal at 40×100, 50×132 and 24×80: `stty size` reported the right size each time, and readline's redraw did not upset output delimiting.
- Ctrl-Z during `sleep 2`: status 148, session not degraded.
- A command that reads its input late (`sleep 0.6; read -t 1 x`) with `abc\r` typed at 0.3 s: the input reached the program (`input_forwarded=True`), and its output was not captured, as decision 7 says.
- The paste sent after `begin()` sets the master non-blocking (`session_terminal.py:146`): `_write_all` (`session.py:1229-1237`) handles `BlockingIOError`, so a long paste is not cut short.
- The `_marker_start` change (`session.py:1178`) also changes `_Output` when no terminal is passed; T3 (496 passed) and the unchanged `tests/test_session.py` show no regression.

## Reviewer-verdict notes

- The residual drain race (a byte forwarded after bash writes `D` but before nl-shell reads it) is real and only documented, not closed. The brief already routes the decision to accept it to the human at sign-off, so I am not filing a separate item. My probes did not trigger it.

I found no other concrete failing case in the diff.

<!-- pdca:leaf-complete -->

# Security review — issue 120 / buffer-background-pty-output

**Attacker-reachable input touched:** command output (threat model "Where untrusted input enters" item 1), specifically PTY bytes a background job writes between commands. It is now read by a new reader thread, kept in a 64 KiB buffer and handed to the caller through `take_background_output()`. No other untrusted input is touched: there is no gate, confirm, sudo, model-context or logging change.

Rated against `.oss-scanner/threat_model.md`. `AGENTS.md` has no reviewer protocol that changes this review.

## Findings

No finding at any severity on the threat model's scale. Here is what I checked:

- **Background bytes cannot reach the real terminal in this slice.** The reader thread only calls `os.read` and `_Background.add` (`src/nl_shell/session.py:858-894`). It never writes to the PTY or to the terminal. `run()` stops and joins the thread before its first read (`session.py:929`). The thread starts again only in the outer `finally` (`session.py:968`), after the inner `finally` has already called `owner.end()`. So the §6 mirror (`session_terminal.py:357-395`) never runs while the thread reads, and idle bytes never go through it. The "High: background output shown during a confirm" row cannot be reached, because nothing shows the block yet.
- **Untrusted bytes are not relabelled, and nothing new goes into a `CommandResult`.** Once armed, idle bytes go only to `_Background` (`session.py:1417-1418`, `:891-892`). `_bg_armed` is cleared before the paste (`session.py:948`), so the command's own output still goes to the result as it did before. Bytes that land between the last `_drain_pty` and the paste become the command's output. That is the existing §4.1 rule, and that output is untrusted anyway. No path takes the buffer into the state block, the reader, `on_record` or a log.
- **Moving the arming point does not give an attacker anything.** A background writer can only change *when* its bytes are counted. The worst it can do is get its bytes dropped (prompt window, or fd 0 redirected). This patch adds that case to "Known gaps" (`threat_model.md:273-278`). It cannot push bytes into a command's result or onto the screen.
- **Resource use is in proportion to the input.** The buffer has a fixed size (`BACKGROUND_LIMIT`, `session.py:314`). A job that floods the PTY costs one 64 KiB read plus at most a 64 KiB `bytearray` trim per chunk. The dropped count is a plain int.
- **Hangs.** `_stop_background` calls `join()` with no timeout (`session.py:853-854`). The thread is woken by a pipe it also selects on. Its only blocking calls are `select`, an `os.read` made only after `select` reported the fd readable (no other reader is active then), and short `/proc` reads. I found no input that keeps it from waking. Test (e) runs `close()` with output still waiting, and it returns.
- **Sudo password.** `session.py` has no sudo passthrough yet. Keys are forwarded only while `owner` is active, and the thread never runs then. So no typed key passes through the new buffer.
- **Tests cover the attacker case.** `test_background_output_is_held_back_while_idle` uses confirm-shaped text (`Run this? [y/N] `) and checks that it stays off the stand-in screen and out of the next result. The 1 MiB flood test checks the size cap and the dropped count. Both exception-path tests check that the reader comes back after a failed `run()`. C4 is red before the fix (6 of 26) and green after. T3 passes with 1107 tests (`gate-logs/C4-verify.log`, `gate-logs/T3-suite.log`).

## Notes (not findings, nothing to adjudicate)

- `take_background_output()` returns raw bytes, including any OSC 52 or terminal-query escapes. The docstring says to show them only through the mirror filter (`session.py:814-816`). This is safe until #78 wires display. #78 must apply the #163 filter to this block, and the threat model's "#78 MUST NOT wire…" paragraph already requires that. A job run in the background that reads a sensitive file (`cat ~/.ssh/id_ed25519 &`) also ends up in this buffer without a secret label. That is fine today because the buffer only reaches the caller. #78/#11 need to keep it screen-only and out of logs and history.
- If the reader thread hits an exception it does not expect, it ends silently and a chatty job stalls again. That is a reliability problem, not one of the threat model's properties, so I did not rate it.

<!-- pdca:leaf-complete -->

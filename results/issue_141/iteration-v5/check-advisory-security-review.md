# Security review (advisory) — issue 141, round 4

**Attacker-reachable inputs this diff touches:** session state (threat model input 4). That means commands the user confirms (including a confirmed `source` of a file from a cloned repo) and `~/.bashrc`, which can change traps, readline, `stty`, fds and variables, and can start background jobs. The patch's new fd-4 handshake (a pipe that bash reads as fd 4; nl-shell writes the go-ahead line) and the two outside readings are the parts that defend against this input.

## Findings

- NEEDS-HUMAN [human] — **Medium** (threat model: "the session doesn't enter degraded mode when its hooks were changed". It also breaks the brief's invariant and I1's "or nothing is sent"). `src/nl_shell/session.py:246` (the hook's `\builtin read -r -u 4`), `src/nl_shell/session.py:890` (nl-shell writes the go-ahead line), `docs/design/specs/pty-protocol/v1.md:301-309,317-318`, `.oss-scanner/threat_model.md:199-200`.
  **Input:** a background job started by a confirmed command (for example from a sourced `env.sh`).
  **What goes wrong:** the handshake assumes only nl-shell can let the hook go on after the hook-time reading. That assumption is false. Any process of the user can reopen bash's fd 4 through `/proc/<bash-pid>/fd/4`. On Linux, opening a pipe through `/proc` gives a new read or write end, and Yama `ptrace_scope = 1` does not block it. A job that blocks reading the pipe before bash does gets woken first. So it takes nl-shell's line, runs `stty -isig` *after* the hook-time reading, then writes its own line so bash goes on. When readline starts, it saves `-isig` as bash's own setting. It then turns ISIG on while it holds the terminal, so the pre-paste reading (`session.py:938`, `_prompt_check`) matches the baseline. The paste is written and runs with signals off while the session counts as healthy. The session degrades only at that command's own hook check, after the paste has already run. This is the same window as round 3's MAILPATH finding, reached through a different route.
  **Reproducer (run here on the patched target, real bash 5.3.9, `ptrace_scope=1`, `legacy_tiocsti=0`: 5 of 5 runs):**
  1. `run("(trap '' TTOU; exec 5</proc/$$/fd/4 6>/proc/$$/fd/4; IFS= read -r -u 5 x; stty -isig; printf '\\n' >&6; sleep 30) >/dev/null 2>&1 &")` → healthy.
  2. `run("stty -a > MARK")` → **1 PTY write** (spy on `_write_all`). `MARK` contains `-isig`. Only then does it raise `SessionDegraded` with code `outside-check` ("terminal settings at the end of the hooks … lflag 0x8a3b -> 0x8a3a").
  3. `run("echo hello")` → refused, 0 writes.
  
  **Why it needs a human decision:** the known gap #147 (threat model `:199-200`, spec `:317-318`) covers only "between the second (pre-paste) reading and the write". This window, from the hook-time reading to readline's terminal setup, is not listed, and spec `:304-308` says "nothing but nl-shell's own hook code runs" there. A local check won't close it. Any same-user process can reopen the pipe, and decision 2 rules out a `/proc/*/fd` scan. Even without the pipe trick, a job can hit the same window by timing alone. The human needs to choose one of two paths. (a) Widen #147 (or file a new gap) to name "a background job changing the terminal between the hook-time reading and readline's setup, including by reopening fd 4 through `/proc`", and correct spec `:304-308`. (b) Ask for a design that does not depend on nl-shell being the only writer to fd 4. The briefed tests do not cover this case: the (j) background-job rows only change settings while readline already holds the terminal.

## Checked, no finding

- **(h2) DEBUG-trap self-removal.** The DEBUG trap runs before `__nls_snap`'s arguments are expanded and can remove itself. Its `stty -isig` still happens before `E`, and the fd-4 reading comes after `E`, so it is caught. The functrace variant is read from `$-` at the top level, and a `~/.bashrc` that turns functrace on makes the session start degraded.
- **Mail check (round 3 finding).** `unset MAILCHECK; readonly MAILCHECK` (`session.py:150`) turns bash's mail check off. If `~/.bashrc` already pinned `MAILCHECK` to a value, `H` will not show the bare `declare -r MAILCHECK` line and the session starts degraded. That fails safe.
- **Planting lines in fd 4.** If a command writes extra lines into fd 4 through `/proc`, the hook never blocks. `_wait_for_hook` then times out and degrades with `outside-check` before any paste. That fails safe.
- **fd 4 swapped.** If a command swaps fd 4 (`exec 4</dev/zero`), the `(st_dev, st_ino)` check at `_wait_for_hook` catches it.
- **`read` disabled.** `enable -n read` makes the hook skip its wait, and the timeout catches that too.
- **Removing the `history-size` line from `H`.** The removal (`${__nls_v/…/}`) takes out exactly one `set history-size <value>` line. A readline variable's value can't contain a newline, so it can't be used to hide another line.
- **`PS4` and stderr capture.** `PS4` is readonly, and every substitution in the hooks now keeps stderr (`2>&1`), so a disabled builtin can't produce an empty value that matches the baseline.
- **`tiocsti_path`.** It is read once, and a missing file, a read error or any value other than `0` makes the session start degraded.
- **Stopped check.** `/proc/<pid>/stat` is parsed after the last `)`, so a crafted process name can't fake the state field.
- **Panics and hangs from untrusted input.** `_read_fds`, `_check_stopped` and `_termios_diff` catch read and parse errors and degrade. They don't raise uncaught. The stopped check runs on every poll tick, so a `kill -STOP $$` can't hang `run()`.

<!-- pdca:leaf-complete -->

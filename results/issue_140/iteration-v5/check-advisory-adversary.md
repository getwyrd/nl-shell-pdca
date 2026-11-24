# Adversarial review — issue 140 / persistent-bash-session-core

I drove the real `nl_shell.session.Session` (target `src/`, system `ptyprocess`, bash 5.3.9)
from scratch scripts in this sandbox. pytest is not installed here, so I could not re-run
`tests/test_session.py` itself. I judged C4/T3 from the frozen logs instead.

## Evidence (C4 / T3)

- `gate-logs/C4-verify.log`: green 90/90; red 90/90, every failure is
  `ModuleNotFoundError: No module named 'nl_shell.session'` from the in-test import
  (`tests/test_session.py:28`, `:67`). For two new modules that is the only red the gate
  can show, and no test passed with the fix reverted, so no test is a tautology that
  ignores the module. The tests drive the production `Session`/`ProtocolTracker`, not a
  copy (`tests/test_session.py:904-912` also pins the spec's reference rcfile to `RCFILE`).
  T3: 267 passed. I found no problem with the evidence.

## Refutation attempts that failed (the fix held)

- I2-a, multi-line input where the first line runs nothing (`'# x\ntouch MARK'`,
  `'\ntouch MARK'`, `')\ntouch MARK'`, `'fi\ntouch MARK'`) and the reverse (`'true\n# x'`):
  every case gave `ran=True`, the right status, a healthy session, and MARK existed only
  when it should (`src/nl_shell/pty_protocol.py:227-241`).
- Hooks under user shell options: `set -u` (+ an empty line), `set -e`, `IFS=x`,
  `shopt -s failglob nullglob extglob`, `set -f`, `set -o pipefail`, `shopt -s lastpipe`,
  `LC_ALL=C`, `set -o posix`. Each one, followed by `true` and then
  `touch MARK; echo printed; (exit 7)`, reported the third command as ran with status 7.
  The only exception was `set -e`, where bash itself exits on `(exit 7)` and the session
  degrades with "the shell exited". That is correct, not a lie.
- I2-b attributes: `declare -n V=PS1`, `declare -i V`, `declare -u V` and `export V` on
  every non-function name in `HOOK_STATE_VARS` (`src/nl_shell/session.py:59-72`). Every
  change bash accepted degraded at that command's own snapshot. The two that did not
  degrade (`declare -n __nls_ps`, `declare -n __nls_user_pc`) were refused by bash
  ("reference variable cannot be an array"), so nothing changed.
- A PTY write deadlock in `run()`. `_write_all` (`src/nl_shell/session.py:509`, `:739-747`)
  is a blocking write that runs before the timeout loop, so a deadlock would ignore
  `timeout=`. I tried single lines up to 100 KB and pastes of up to 5000 lines (315 KB).
  All finished in at most 2.2 s with correct output. No hang.

## Findings

- NEEDS-HUMAN [impl] — The docs claim more than the code gives for I3 (R1 makes this a
  defect). `docs/design/specs/pty-protocol/v1.md:153-157` says "nothing confirmed code sets
  runs after the snapshot" and "one to `PS1`/`PS2` is overwritten".
  `docs/design/specs/pty-protocol/v1.md:51-52` says "no prompt string the user or a command
  set is ever expanded". `.oss-scanner/threat_model.md:184` repeats the first claim.
  Concrete failing case: the confirmed command `readonly PS1='$(touch PS1_RAN)\$ '`.
  `__nls_snap` skips the reset because the attributes are `-r`
  (`src/nl_shell/session.py:135`). The final `PS1='\$ '` then fails on the readonly
  variable (`src/nl_shell/session.py:167`), so bash expands the user's `PS1` after `E`, and
  `PS1_RAN` is created after the snapshot. The session does degrade ("H differs", result
  seq 1), so I2 holds, but the code did run after the snapshot and `PS1` was not
  overwritten. The same happens with `PROMPT_COMMAND+=('touch PC_RAN')`: the appended
  element runs after nl-shell's hook in that same prompt cycle, and `PC_RAN` exists after
  the snapshot. Here the doc's own next clause ("degrades (`H`)") describes it honestly,
  but the lead sentence does not. (`readonly PS2=…` did not run, since PS2 is never
  shown.) Fix: reword those three places to say what really happens. A confirmed change to
  `PROMPT_COMMAND`, `PS0`, or a readonly/attributed `PS1`/`PS2` degrades the session at
  that command's snapshot, but may run once after it. Only a plain or exported `PS1`/`PS2`
  is overwritten. The brief's own I3 wording has the same gap, so the human may want to
  confirm the new wording at sign-off.
- Note, not a defect of this child: after the confirmed command `set -v`, every result's
  `output` includes bash's echo of the hook text
  (`\__nls_done; \__nls_snap "$(\builtin trap -p)"`), because verbose mode prints the
  `PROMPT_COMMAND` text before the end marker (`src/nl_shell/session.py:117`, `:171`). Exact
  output is claimed only for the (q) `HOOK-OUTPUT` case, and `set -v` is next to the
  xtrace/`PS4` family that the brief leaves to #141/#145. No doc claims otherwise, so I am
  only recording it for #145.

Apart from the I3 doc overclaim above, I could not refute the fix. I tried multi-line
not-run handling, shell-option safety of the hooks, attribute tampering on hook state, and
a large-paste deadlock.

<!-- pdca:leaf-complete -->

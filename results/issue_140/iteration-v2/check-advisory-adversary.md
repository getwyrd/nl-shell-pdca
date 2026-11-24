# Adversarial review — issue_140 (persistent-bash-session-core)

I tried to break the fix by running `nl_shell.session.Session` directly against the host's bash 5.3.9, with `ptyprocess` and `python3 -I`. pytest is not installed in this sandbox, so I could not re-run the suite. Instead I drove the production class itself, not a copy. Scripts and output are in `scratch/` (`probe.py`, `probe2.py`).

## Evidence (C4 red→green)

- `gate-logs/C4-verify.log`: the red leg is 86/86 `ModuleNotFoundError: No module named 'nl_shell.session'`. That is the right shape for new code, and it shows each test imports the module inside the test. It does **not** show that any single test is sharp, because no test ever ran against a partly wrong implementation. I read the key tests for tautologies and found none:
  - the I2 test (`tests/test_session.py:660-680`) asserts `ran/status/text == (True, 7, "printed\n")` and that the marker file exists on its healthy path;
  - `tests/test_session.py:945-957` pins the exact output bytes;
  - the prompt-rule tests check the reason text and that nothing was written to the PTY.
  
  Not a refutation.

## Attacks that failed (the fix held)

- **An alias that suppresses `S` (I2).** `PS0` re-parses `$(builtin printf "S …")` with the user's aliases at prompt time, and the comment at `src/nl_shell/session.py:113` ("defined with alias expansion off") does not cover that. But `alias builtin=:` and `alias builtin='builtin '; alias printf=:` both degrade at **their own** snapshot. The `H` command substitution at `src/nl_shell/session.py:153-169` is re-parsed the same way, so its text changes. The next command never ran (MARK absent). It fails closed. To hide `S` selectively you would need a deliberate wrapper function, which is I1 tampering and belongs to child-2.
- **`set -u`, `set -e`, `set -o posix`.** All stay healthy with correct status and output.
- **Multi-line input.** `echo a\necho b; (exit 4)` gives one S/D pair, status 4. `echo a\nfi` reports ran, status 2, both outputs.
- **Leading CR in output.** `printf '\rX'` and `printf '\r\rY'` come back exact. The single-CR skip at `src/nl_shell/session.py:326-330` does not eat command output.
- **Turning off line editing.** `set +o emacs +o vi` and `bind 'set enable-bracketed-paste off'`: the next command degrades with "output could not be delimited" (`src/nl_shell/session.py:639-643`). It is never reported healthy. Note that with editing off, the pasted bytes still reach bash and run as a garbled command (status 127) before the degrade. That is readline state, Table A row 6, which belongs to child-2.
- **`unset PROMPT_COMMAND`.** Degrades by the prompt rule in 1.0 s.

## Findings

- NEEDS-HUMAN [human] — `src/nl_shell/session.py:283-338` (`_Output`): **bash's own job notices are reported as the next command's output.** Reproduced: run `sleep 0.2 &`, wait, then `sleep 0.6; echo x`. The result's `output` is `b'[1]+  Done                       sleep 0.2\r\nx\r\n'`, with the session healthy. With `set -b` it is `...sleep 0.2\r\r\nx\r\n`. Bash prints the notice after readline's `ESC [?2004l` and before the command runs, so it falls inside the S..D window by design. The brief's (q) says "return exactly the command's own output", but tests only the user `PROMPT_COMMAND` case. The brief forbids parsing PTY text, so the builder can't fix this by iterating. A human should decide whether job notices count as "PTY output between S and D" (and say so in the spec) or need another cut point.
- NEEDS-HUMAN [human] — `src/nl_shell/session.py:709-724` (prompt rule): **healthy commands that end by themselves get degraded.** `read -t 2 x; echo st=$?` degrades after 1.0 s with "no done record after the shell returned to a prompt" and `result=None`, even though it would finish with status 142. The same goes for any timed or single-key read from the terminal (`read -n1 -t …`, a `select` menu). This sits in the same class as the accepted `read x` limit (#136, brief (k)), so it is not a defect against this brief. But the spec, threat model and #136 should name timed reads explicitly, so nobody later reads "only `read x` with no input" as the whole limit.
- `src/nl_shell/session.py:113`: the comment says the hooks are "defined with alias expansion off". In fact every `$( … )` inside `PS0`, `__nls_snap` and `__nls_enc`'s callers is re-parsed at run time with the user's aliases (shown above). It fails closed today only because `H` is itself built inside such a substitution. A future edit that moves `H` out of a command substitution would quietly open an I2 hole. This is a comment-accuracy nit; it does not refute the fix.
- Out of scope, noted only: with `stty -isig`, `interrupt()` returns True, writes `^C`, and `sleep 5` runs the full 5 s. With `stty -echo`, `echo hi` returns `b'\r\nhi\r\n'`, an extra blank line. Both are termios state, which is Table B (child-2). I am not filing them against this diff.

## Verdict on check-gates.json

I see no unwarranted claim. The C4 "red without the fix (86 of 86 failed)" is literally true but weak as evidence (see above). T4 is honestly marked `deferred`. I attempted to refute I2 (aliases, shell options), output delimiting (CR, multi-line, line editing off), sequencing (multi-line, syntax errors) and the prompt rule (unset hooks, timed reads), and could not break the brief's stated invariants. The two NEEDS-HUMAN items are limits of the chosen design, not builder bugs.

<!-- pdca:leaf-complete -->

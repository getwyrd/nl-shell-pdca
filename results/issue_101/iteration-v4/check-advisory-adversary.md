# Adversarial review — issue 101 / persistent-bash-session-core

All line numbers point at `c47c5c2` (current `main`) with `patch.diff` applied. I rebuilt
that tree in the sandbox from `git archive c47c5c2`. The patch applies cleanly there.

## Evidence (red→green)

- C4's red is a driver fault, not a broken fix. `check-gates.json` C4 reports
  `worktree-mismatch`: the patch "did not apply onto
  'origin/pdca-integration/main-r2546dbf9639f'". The target worktree is still on `8c95e05`,
  the stale `stack-base` that brief.md:37 says must be cleared before Do. On `c47c5c2` I
  re-ran the gate myself. With the patch, `tests/test_session.py` gives 99 passed in 52 s
  (bash 5.3.9, ptyprocess 0.7.0). With every production hunk reverted (main's `src/`, the
  patch's tests), it gives 99 failed in 1.2 s, each test failing on its own (the imports
  sit inside the tests). The tests import the real `nl_shell.session`, not a copy.
- NEEDS-HUMAN [human] — The gating C4 row stays red until someone clears or re-resolves the
  bundle's `stack-base` to `main` (`c47c5c2`) and re-runs Check. My run above is
  provisional evidence, not the gate.

## The fix: inputs that break it

- NEEDS-HUMAN [human] — **A confirmed command can make bash run extra code during every
  later command, with the session left healthy and nothing reported** (I1, I3). Concrete
  case: `exec 9>/dev/null; BASH_XTRACEFD=9; PS4='$(echo x >> MARK)'; set -x`, then
  `echo hi`. Measured: `echo hi` returns `hi\n`, `ran True`, `degraded False`, and the
  PS4 payload ran 9 more times during that one command. H (`src/nl_shell/session.py:164-190`)
  leaves out `xtrace`, `PS4` and `BASH_XTRACEFD`. The hooks save xtrace in `__nls_x`
  (`session.py:143`) and turn it back on after the snapshot (`session.py:196`), but H only
  records the variable's attributes, not its value (`session.py:169-170`). V
  (`session.py:85-88`) and T/X don't cover these either, so the gate (#12) can't see it.
  This acts like a DEBUG trap, which Table A marks "detect". Table A has no row for
  xtrace/PS4, so this is a missing *category*, which brief.md:8 counts as a real finding.
  The test `tests/test_session.py:675-688` passes only because its PS4 payload also
  rebinds CR, which H does catch. A payload that changes nothing H covers gets through.
  The fix is small (add `xtrace`, `declare -p PS4 BASH_XTRACEFD` to H, plus a test whose
  PS4 payload only touches a marker), but it adds a row to the closed list, so a human
  should approve the scope.
- NEEDS-HUMAN [impl] — **Output from the user's `PROMPT_COMMAND` gets counted as the
  command's output.** Concrete case: `~/.bashrc` with `PROMPT_COMMAND='printf USERHOOK'`,
  then `run("true")` 40 times: 25 of 40 results had `USERHOOK` in `output`. The same
  thing happens with no setup at all on this host: `/etc/bash.bashrc` loads the vte hook,
  and `\x1b]666;vte.shell.postexec=0\x1b\\` showed up in 5 of 30 `echo HELLO` results.
  Cause: `__nls_done` writes `D` and then runs the user hook (`session.py:147-150`). The
  wait loop reads the PTY before it handles the control record from the same select round
  (`session.py:575-585`), so text printed after `D` gets added to the command's output
  whenever both are ready together. That breaks the brief's "PTY output between `S` and
  `D`" (brief.md:14). Decision 6 is what made the user hook print between `D` and `E`, so
  the output should be cut at a point bash marks (for example, an fd-3 record or ack
  written before the user hook runs), not by read order. No test checks command output
  when a user hook prints; (m) only checks that the hook runs.

## Tried and could not refute

- I2 attacks: `readonly` / `declare -n` / `declare -i` on hook variables show up in H
  through the attribute lines (`session.py:169-173`). Changing `__nls_seq`'s value is
  overwritten in `__nls_done` before PS0 reads it (`session.py:145`). A bad value causes
  a sequence error, which fails closed.
- `enable -n printf` / `read` / `declare`: the hooks break, then the prompt rule, the
  check-point wait (`session.py:679-683`) or a changed H degrades the session. It fails
  closed.
- A background loop flipping `stty iuclc` on and off (with SIGTTOU ignored) to race the
  check that runs just before the paste: 30 runs of `echo HELLO` all returned `HELLO`.
  No changed bytes ran.
- `trap … ERR` / `CHLD` also run code during later commands, but Table A lists only
  DEBUG/RETURN traps for H, and T reports these traps to the gate. They are inside the
  brief's design, so I don't count them as findings against this diff.

<!-- pdca:leaf-complete -->

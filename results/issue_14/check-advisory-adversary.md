# Adversarial review — issue 14 / input-mode-prefix-dispatch (iteration 3)

**Bottom line: I tried to refute the evidence, the fix and the verdict, and could not.** None of the findings below is a NEEDS-HUMAN item.

## Evidence (red → green)

- `gate-logs/C4-verify.log`: the red leg is real. With the fix reverted, 23 of 29 tests failed. Every failure is an assertion failure on a reply, except `test_status_lines_can_be_extended`, which hits an ImportError *inside* the test function, as the brief allows. There were 0 collection errors, so the run counts as red, not UNVERIFIABLE. The 6 tests that pass on `main` are the ones the brief expects to pass: `\ls -la`, `ls -la`, `show disk usage`, `:quit`, `:exit`, plus the distinctness count. The red comes from rows the brief names as carrying it (`\frobnicate`, `?why`, `:status`, `:frobnicate`, the extension point). The new `: quit` / `:  exit` rows (`tests/test_input_modes.py:184-188`) also go red on `main`, so the iteration-2 fix has its own red.
- Green, re-run by me: `tests/test_input_modes.py` + `tests/test_repl.py` give 51 passed on `$PDCA_TARGET`. I confirmed that `nl_shell` was imported from `target/src`, not from another checkout. The tests go through the production path: `Repl(...).run()` → `input_modes.is_exit` / `Repl._reply` (`src/nl_shell/repl.py:62-77`). There is no copied logic. Every reply is pinned as a literal (`tests/test_input_modes.py:9-45`), and the only module-level import is `Repl` (`tests/test_input_modes.py:5`). T3 shows the full suite green (177 passed).

## Attempts on the fix (inputs I ran on the patched tree)

- Exit handling (`src/nl_shell/input_modes.py:67-74`): `:QUIT`, `:quit now` and `:quit\x00` don't exit. They get the unknown reply. That matches the brief's rule of exact, case-sensitive, whole-name matching. Unlike iteration 2, the reply isn't contradicting itself: the name it reports (`quit now`) really isn't in the known list. `\:quit` takes the command route and doesn't exit, which is correct because the prefix wins. Not a refutation.
- Prefix order (`src/nl_shell/input_modes.py:47-53`): `@@@x` → agent-reserved, `?:status` → ask, `::status` → unknown `::status`, `:\tstatus` → status block. All follow the stated rules. Not a refutation.
- `:status` table row (`tests/test_input_modes.py:30,152-155`): it now checks only the first line. If the output is empty, `splitlines()[0]` raises IndexError, so the row still fails rather than passing by accident. The iteration-1 finding is fixed.
- Minor, not NEEDS-HUMAN: `src/nl_shell/input_modes.py:142` echoes the raw payload, control characters included (`:\x1b[2J` would print the escape sequence back). It's the user's own input, and nothing runs yet. I note it for #78 / #17, not as a defect of this diff.
- Minor, not NEEDS-HUMAN: `test_replies_are_distinct` (`tests/test_input_modes.py:107-108`) uses the placeholder key `"nl-shell "` for `:status` instead of the real output. So it doesn't prove the status block differs from the other replies. It obviously does differ (`nl-shell 0.0.0`), so this weakens the test without hiding a bug.
- `\cmd` drops the payload at `src/nl_shell/repl.py:72-76` and returns the fixed command reply. The brief puts running anything and the gate (#78) out of scope, and the comment cites ADR-0013 §7 (Proposed) and #64 as the brief asks. Not a refutation.

## Verdict

- I found no claim in `check-gates.json` that the logs don't support. C4 and T3 PASS match `gate-logs/`. T4 is deferred until publish, which is correct because no PR body exists yet. I could not refute the red→green evidence, the prefix grammar, the exit-on-payload change or the extension point.

<!-- pdca:leaf-complete -->

# Adversarial review — issue 14 / input-mode-prefix-dispatch

I tried to break the evidence, the fix and the verdict. I could not refute the fix. The red→green proof is real. There is one test-design weakness worth sending back, and two minor notes.

## Evidence (red→green)

- Attempted: the red leg passing for the wrong reason. `gate-logs/C4-verify.log:601-603` shows 15 of 21 failing on the reverted tree. They fail on assertion mismatches (each prefixed line gets the natural-language reply), not on a collection error: "import/collection errors 0". The extension test fails with `ImportError` inside the function body (`tests/test_input_modes.py:147`), which is how the brief asked for it. The 6 rows that pass on `main` are the ones the brief predicted (`\ls -la`, bare `:`, the two plain-input rows, the two exit-command tests) plus `test_replies_are_distinct`. Green: 21 passed (`C4-verify.log:12`). The full suite is green, 169 passed (`gate-logs/T3-suite.log:14`). I could not re-run pytest myself because the sandbox has no `pytest` module. The frozen logs are consistent, so this does not count against the fix.
- Attempted: a test that mirrors production instead of exercising it. Every row goes through `Repl(...).run()` (`tests/test_input_modes.py:76-79`), which reaches `Repl._reply` at `src/nl_shell/repl.py:64-77`. The replies are pinned as literals and not imported, so a wrong constant in production would fail the test. Not refuted.
- Attempted: mutation of the `@@`-before-`@` order (`src/nl_shell/input_modes.py:45-51`). If `@` came first, `@@clean…` would get the PROPOSE reply and bare `@@` would too. Both rows (`tests/test_input_modes.py:111,120`) would go red. Not refuted.

## Fix (edge inputs probed against `input_modes.parse` / `reply`)

- `: > f` (the bash truncate idiom) now gets "Unknown meta-command : > f." when on `main` it routed as a command through the `:` builtin. `??x`, `::status`, `:Status` and `@ @x` all go where the brief's rules send them. All of this matches the brief's "a prefix always wins" rule (`src/nl_shell/input_modes.py:54-63`). It is a design choice, not a defect.
- `src/nl_shell/input_modes.py:118-134`: `input_modes.reply(Prefixed(Mode.COMMAND, "ls"))` raises `KeyError` (I confirmed this by calling it). The REPL never makes this call, because `repl.py:72-76` handles `\cmd` first, and the docstring warns about it. #78 wires `\cmd` to the gate, and anyone who calls `reply` straight from that code gets a crash. This is a minor API sharp edge, not a current bug, so it is not tagged.

## Verdict / test design

- NEEDS-HUMAN [impl] — `tests/test_input_modes.py:28,114`: the `:status` table row asserts that the *whole* output equals `"nl-shell 0.0.0\n"`. The brief's criterion says only that the block "includes the line `nl-shell <version>`", and the whole point of `STATUS_LINES` (`src/nl_shell/input_modes.py:68-70`) is that #92, #16 and #77 append lines "and change nothing else". Concrete failing case: the moment #92 appends its active-target line, `test_prefix_dispatch[:status-status]` goes red. A version bump in `src/nl_shell/__init__.py:3` does the same. So the extension point can't actually be used "with no other change", which the brief and the `STATUS_LINES` comment both promise. Fix: in the table, check only that the first line of the `:status` output is the version line, or drop the `:status` row from the exact-match table. `test_status_prints_the_version_line` (`tests/test_input_modes.py:137-142`) already checks the version line in a way that won't break when lines are added. Keep a red-on-`main` row for `:status`; that test still gives one.
- The rest of the reviewer's verdict looks warranted. I found no claim in `check-gates.json` that the logs don't back up.

<!-- pdca:leaf-complete -->

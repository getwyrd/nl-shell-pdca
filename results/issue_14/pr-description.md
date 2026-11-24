## Summary
**User impact:** The input prefixes promised in the plan don't work yet. Typing
`\frobnicate` to force a shell command, `?why did that fail` to ask a question, or
`:status` to see what's running all get the same "looks like a natural-language request"
reply, because the REPL guesses at every line and never looks at the prefix.

This PR makes the REPL read the prefix first: `\`, `?`, `@`, `@@` and `:` each go to
their own route, `:status` prints the version, and the routes that aren't built yet say
which milestone brings them. Lines without a prefix behave exactly as before.

Reported in [#14](https://github.com/eduralph/nl-shell/issues/14).

## What to look at
The new file `src/nl_shell/input_modes.py` holds the whole prefix grammar; `repl.py`
only calls it. To try it, run `nl-shell` and type:

```
nl> \frobnicate the widgets   → shell-command reply (the router alone would say natural language)
nl> ?why did that fail        → ask-mode reply (arrives in M0.8)
nl> @show disk usage          → one-command proposal reply (arrives in M0.8)
nl> @@clean up my downloads   → reserved reply naming #76
nl> :status                   → nl-shell <version>
nl> :frobnicate               → unknown meta-command, with the list of known ones
nl> ?                         → a one-line usage hint
nl> : quit                    → exits, same as :quit
```

Two scope decisions worth a look:

- **`@@` is reserved, not built.** The issue moved `@@` to #76. This PR still catches
  `@@` with one fixed reply, so `@@goal` doesn't fall into the `@` route as `@goal`. #76
  owns the grammar and replaces that reply.
- **`\cmd` skips the router, not the safety gate.** That follows ADR-0013 §7, which is
  still Proposed (#64 closed on it). Nothing runs yet; #78 wires the gate in, and the
  code comment says so.

## Root cause
`Repl.run` sent every non-exit line straight to the router heuristic
(`src/nl_shell/repl.py:57-62` on `main`), and the exit check matched only the exact
strings `:quit` / `:exit` (`repl.py:18`). Nothing looked at the input-mode prefixes.

## Fix
- New module `src/nl_shell/input_modes.py`: `parse` (`:55-64`) finds the prefix, checking
  `@@` before `@` (`PREFIXES`, `:46-52`), and strips the text after it. `reply`
  (`:131-146`) gives the fixed reply per mode, the usage line for a bare prefix, and the
  meta-command lookup by exact, case-sensitive name (`META_COMMANDS`, `:104-108`).
- `:status` prints one line per entry of `STATUS_LINES` (`:80-82`), a list of zero-argument
  callables. #92, #16 and #77 add their lines by appending to it.
- Exit commands go through the same parse (`is_exit`, `:67-74`), so `: quit` exits instead
  of being called an unknown `:quit`. The "Known:" list is built from the same names
  (`known_meta_commands`, `:111-112`), so the two can't drift apart.
- `src/nl_shell/repl.py:62-77`: the loop calls `is_exit`, then `_reply`, which sends a
  `\cmd` line to the existing shell-command reply and any other prefixed line to
  `input_modes.reply`. Unprefixed lines still go to `route()` with byte-identical replies.
  The router module is unchanged; #40 replaces it later.

## Verification
- **Claim:** each prefix wins over the router, with its own fixed reply.
  - **Checked:** `tests/test_input_modes.py:111-153`, a table run through the real
    `Repl(...).run()` with `$PATH` set to a temp dir holding only fake `ls`, `git`, `find`.
    Every reply is pinned as a string literal; `test_replies_are_distinct` (`:107-108`)
    checks they are all different.
- **Claim:** `@@` never reaches the `@` route.
  - **Checked:** the `@@clean up my downloads` row and the bare `@@` row in the same table.
- **Claim:** later issues can add `:status` lines without changing anything else.
  - **Checked:** `test_status_lines_can_be_extended` (`:164-180`) appends a callable and
    sees its line after the version line. The `:status` table row checks only the first
    line, so it won't break when lines are added.
- **Claim:** `:quit`, `:exit`, `: quit` and `:  exit` all end the loop.
  - **Checked:** `test_exit_commands_still_stop_the_loop` (`:184-188`).
- **Claim:** plain input is unchanged.
  - **Checked:** the `ls -la` and `show disk usage` rows, and `tests/test_repl.py` passes
    without edits.
- **Test:** `tests/test_input_modes.py` imports only `Repl` from `nl_shell.repl` at module
  level, so it loads on `main`. With the production changes reverted, 23 of its 29 tests
  fail. The 6 that pass on `main` are expected to: `\ls -la` (shlex drops the backslash),
  the two plain-input rows, the distinct-replies check, and `:quit` / `:exit`. With the
  change, all 29 pass, and the full suite passes (177 tests).

Fixes #14

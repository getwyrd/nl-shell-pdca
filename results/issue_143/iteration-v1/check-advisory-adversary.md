# Adversarial review — issue #143 (prompts YAML, `:context`, recording stub)

**Overall:** I tried to break the red→green proof, the parser, the prompts loader and the escaping. The fix holds up. I found one real test gap in a safety property the brief requires, a few smaller unpinned behaviours, and no input that makes production misbehave in scope.

## Red→green proof re-run

I re-ran the proof myself, using the pytest from the `nl-shell-pdca` venv as a tool against copies of `$PDCA_TARGET`:
- **Green:** `tests/test_backend.py` gives 58 passed. The whole suite gives 388 passed, the same as `gate-logs/T3-suite.log`.
- **Red:** with `backend.py`, `prompts.py`, `proposal.py`, `render.py` and the `src/` edits reverted, `tests/test_backend.py` gives 58 failed. This matches `gate-logs/C4-verify.log` (78 of 171 failed across the bundle files).

Most red failures are `ModuleNotFoundError` from the imports inside test functions. The brief planned this, so it counts as red, not "unverifiable". The green side runs the production path: `cli.main` → `prompts.load` → `Repl` → `prompts.build` → `RecordingStub` → `proposal.parse`. The `:context` oracle (`tests/test_backend.py:57-93`) is a separate copy of the predicate. The brief asks for that, and it means the byte-for-byte check can't pass by calling the same code.

## Findings

- NEEDS-HUMAN [impl] — No test covers the REPL-wide escape at `src/nl_shell/repl.py:124` (`print(render.escape(self._reply(text)), ...)`). The brief's invariant says every REPL reply passes through the escape function. I changed that line to `print((self._reply(text)), ...)` and the whole suite still passed (388/388).
  - **Concrete case:** with no backend, type `:foo` followed by a real U+202E, then ESC `[2J`. The patched code prints `Unknown meta-command :foo\u202e\x1b[2J. ...` as visible escape text. With the mutation, the raw RLO and the clear-screen ESC sequence reach the terminal, and no test notices.
  - `:context` hides the gap because `prompts.render_input` already escapes. Proposals hide it because the parser has already rejected hidden characters.
  - **Fix:** add a test that sends an unknown meta-command (or a `:status` line) containing ESC and U+202E through `Repl`, and asserts the escaped form appears.
- NEEDS-HUMAN [impl] — No test covers three documented strictness rules. Each of these mutations left the suite at 388/388:
  - Removing the duplicate-key rejection at `src/nl_shell/proposal.py:107`. A response `{"kind":"refuse","kind":"command",...}` would then be read as last-key-wins instead of rejected.
  - Removing the check that each few-shot `response` is a valid proposal, at `src/nl_shell/prompts.py:164` (a contract stated in the module docstring).
  - Removing the `{state}`-before-`{request}` order check at `src/nl_shell/prompts.py:176`.

  None of these is in the brief's (a)–(g) list. But the code claims them, and a later edit could drop any of them silently. Add one malformed-response case and two malformed-prompts cases.
- Low: the `target.toml` bidi test (`tests/test_backend.py:330-357`) does not test what criterion (c) describes. Criterion (c) asks for U+202E in the *broken line*. The test's `shell = "<U+202E>bash"` (`:342`) is valid TOML that fails validation, and `targets.py:180` already prints it with `!r`, which escapes it before `cli._error` runs. So `assert "\\u202e" in err` (`:355`) would pass without the fix. The test only fails without the fix because of the U+202E placed in the root folder name (`:333`), as its own comment admits. It does go red: dropping the escape in `cli._error` fails 2 tests. So the escape is covered, just not through the vector the brief names. Not tagged; no action strictly needed.
- Low, outside this diff's scope: `RecordingStub.complete` raises `StubExhausted` (`src/nl_shell/backend.py:43`), and `Repl._propose` (`src/nl_shell/repl.py:150`) does not catch backend errors. Any exception from `complete` therefore ends the REPL with a traceback. That's fine for the test-only stub. #77 should decide whether a backend failure becomes the "no usable proposal" reply. Not tagged.

## Attempted and could not refute

- **Parser** (`src/nl_shell/proposal.py:101-151`) correctly rejects: NEL U+0085, VT, U+2029, a lone low surrogate `\udc00`, `NaN`, `[` nested 100,000 deep (`RecursionError` is caught), a boolean `risk`, an object as `command`, and a leading BOM.
- **Accepted, but not a spec violation:**
  - Leading and trailing whitespace around the JSON object.
  - `clarify`/`refuse` with an extra `risk` field. Rule 2 does not forbid it.
  - A whitespace-only or LF-only `command`. `minLength: 1` is met. It shows as blank `  | ` lines, which are still visibly framed.
- **Header spoofing:** this is not possible. Every command line gets the `  | ` prefix (`src/nl_shell/repl.py` `show_proposal`). Dropping the per-line prefix fails 2 tests.
- **Double escaping:** escaping the `:context` text twice is harmless. The output of `escape` contains no hidden characters, so the second pass changes nothing.
- **Prompts loader:**
  - It only ever uses `yaml.safe_load`, and non-UTF-8 bytes are refused.
  - YAML parse errors quote the raw line. `cli._error` escapes it, and the bidi prompts test fails without that escape.
  - An `XDG_CONFIG_HOME` with undecodable bytes (surrogate-escaped path) is escaped, not crashed on.
- **Scope note:** U+115F (Hangul filler) passes the parser. That falls under Default_Ignorable outside Cf, which the brief assigns to #144.
<!-- pdca:leaf-complete -->

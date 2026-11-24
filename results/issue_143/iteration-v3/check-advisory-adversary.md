# Adversarial review — #143 prompts YAML, `:context`, recording stub

I could not refute the fix. The red→green evidence holds, and nothing I fed the production code got past it. One test gap is worth a rebuild. The rest are notes.

**What I tried**

- **Red→green evidence.** `gate-logs/C4-verify.log` shows all 68 `tests/test_backend.py` cases failing with the production change reverted (88 of 181 failures in the bundle) and passing with it. The full suite is green at 398/398 (`gate-logs/T3-suite.log`). The tests drive the real `Repl`, `cli.main`, `targets.load` and `prompts.load`. The only parallel copy is the `:context` oracle (`tests/test_backend.py:57-92`), and the brief asks for that on purpose. I could not re-run pytest here (it is not installed in this sandbox), so I judged from the frozen logs and ran direct probes against `$PDCA_TARGET/src` with Python 3.14 and PyYAML 6.0.3.
- **Parser (`src/nl_shell/proposal.py:176-218`).** These were all handled correctly: trailing garbage, a BOM, NaN, duplicate keys, a lone surrogate, the 8-bit CSI control U+009B, U+2029, an emoji written as an escaped surrogate pair (counted as one code point), and an extra key. A `clarify` that also has a `risk` is accepted. Spec rule 2 allows that, so it is not a defect. A command of `" "` or `"\n"` is accepted, but that matches the spec's `minLength: 1`.
- **Prompts loader (`src/nl_shell/prompts.py:112-146`).** I tried bad `<<` merges, a set used as a key, a NaN key, a timestamp with year 0, a bad `!!omap`, recursive anchors, non-UTF-8 bytes, a huge float, and non-string example fields. Each one either loads cleanly or raises `PromptsError` naming the file. None escaped as an uncaught exception.
- **Display paths.** The only `print` calls in `src/` are `src/nl_shell/cli.py:70` and `src/nl_shell/repl.py:124`, and both go through `render.escape`. No path prints model or file text raw. Splitting the proposal on LF (`src/nl_shell/repl.py:57`) cannot be spoofed by another line break: CR, VT, FF, NEL, U+2028 and U+2029 are all rejected first.

**Findings**

- NEEDS-HUMAN [impl] — `tests/test_backend.py:493-503`: the hidden-character vectors test only one point inside each range, so narrowing the predicate in `src/nl_shell/render.py:39-47` would not turn the suite red. Three examples:
  - Changing `0x7F <= code <= 0x9F` to `<= 0x85` still passes, yet it lets U+009B (CSI, the 8-bit start of a terminal escape sequence) through in a proposal.
  - Dropping `0x2029` from `LINE_AND_PARAGRAPH_SEPARATORS` still passes. U+2029 is category Zp, not Cf, so nothing else catches it, and a terminal that breaks the line there would show an unprefixed line inside the framed proposal.
  - Cutting `TAG_BLOCK` short (anything above U+E0041) still passes.

  The test file mentions U+009B, U+2029 and U+E007F only in its own oracle (`tests/test_backend.py:63-66`), never as input. Fix: add U+009B, U+2029, U+E007F, U+0000/U+001F and U+061C to `HIDDEN`. The code is correct today; the problem is that the tests would not catch a regression in a must-hold rule.
- Note, no action needed — `src/nl_shell/prompts.py:127`: `yaml.safe_load` takes the last value when a key is repeated. With `system: a` and later `system: b`, the loader quietly uses `b`. The JSON parser rejects repeated keys (`src/nl_shell/proposal.py:157-161`), so the two loaders treat the same mistake differently. The brief does not require rejecting repeated YAML keys, so this is not a defect against the success criterion.
- Note, out of scope — `src/nl_shell/proposal.py:205`: U+00A0 (no-break space) and U+115F (a Hangul filler that draws as a blank) pass the parser and would show inside a command. The brief assigns blank glyphs and non-ASCII whitespace to #144, so I am recording this for #144, not counting it against this patch.
- Reviewer's verdict: nothing in `check-gates.json` looks overstated. T4 is `deferred` (no PR text drafted yet), which is expected at this stage, not a pass someone argued their way into.

<!-- pdca:leaf-complete -->

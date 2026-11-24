# Security review (advisory) — prompts YAML, `:context`, recording stub (#143)

Attacker-reachable inputs this diff touches: **the model's raw response** (threat model "Where untrusted input enters" item 5), parsed by `src/nl_shell/proposal.py:168` and shown by `src/nl_shell/repl.py:52-66`. The other new inputs are trusted under the threat model: the prompts YAML files (the user's own config and the shipped target default, "Trusted" list, `.oss-scanner/threat_model.md:100-101`) and the request text the user types. They are still escaped on output, which I checked as defence in depth.

## Findings

No findings. What I checked:

- **Hidden characters in a proposal (must-hold "What the user confirms is exactly what runs", `threat_model.md:127-130`).** `proposal._parse` rejects any `command` that `render.has_hidden` flags (`src/nl_shell/proposal.py:205-206`). I fed crafted responses to the patched parser. U+0085 (NEL, a C1 control), U+00AD (soft hyphen, Cf) and U+FFF9 (Cf) were rejected. A real surrogate pair (`"😀"`) was accepted as one emoji, which is correct. The lone-surrogate, ESC, CR, DEL, U+202E, U+200B, U+FEFF, U+2028 and tag-block cases are in the suite, along with the iteration-3 boundary vectors U+0000, U+001F, U+009B, U+061C, U+2029 and U+E007F (`tests/test_backend.py:493-509`).
- **Spoofing the proposal frame (rating High if it worked: "spoofs the confirm UI").** A `command` of `ls\nProposed command (risk: read-only, 1 line):\n  | rm -rf /` prints every line behind `  | ` (`src/nl_shell/repl.py:57-60`), and the line count says 3. CR is rejected, so a line can't be overwritten in place. No spoof.
- **Parser crash or hang from model output.** Invalid JSON, a number with more than 4300 digits (`ValueError`) and deep nesting (`RecursionError`) all become `Rejected` (`src/nl_shell/proposal.py:183-185`). Duplicate keys and `NaN`/`Infinity` are rejected (`:157-165`). `1e999` turns into `inf` but can only end up in an enum field, where any non-string is rejected (`:221-225`). `Rejected.why` is never printed, so no model text gets out through it.
- **Output filter (must-hold "Output rendering is filtered everywhere", `threat_model.md:132-134`).** Every REPL reply goes through `render.escape` (`src/nl_shell/repl.py:124`). `:context` escapes hidden characters and backslashes (`src/nl_shell/prompts.py:216-221`). Start-up errors, including YAML parser messages that quote file text, go through `cli._error` → `render.escape` (`src/nl_shell/cli.py` `_error`). Running the outer escape again over `:context` text that is already escaped changes nothing, because escaping with `backslash=False` leaves plain ASCII as it is.
- **YAML loading.** Only `yaml.safe_load` is used (`src/nl_shell/prompts.py:127`). The `!!python/object/apply` vector is tested. The file is trusted config in any case, so alias-expansion or size problems would at most be Low (a misconfiguration the user made).
- **Accepted but out of scope.** The parser accepts U+034F (combining grapheme joiner), U+115F and U+3164 (Hangul fillers) and U+00A0 (no-break space) in a `command`. The brief hands Default_Ignorable code points outside Cf, blank glyphs and non-ASCII whitespace to #144 (`brief.md` Scope, out of scope), so I am not filing these here. #144 should cover them before #74/#78 put a proposal in front of the user to confirm.
- **Not yet reachable.** `RecordingStub.complete` raises `StubExhausted` straight out of `Repl._propose` (`src/nl_shell/backend.py:263-264`, `src/nl_shell/repl.py:150`). That only happens in tests. The real backend (#77) will need its own error handling, but this diff doesn't create that path.

Gates: C4 and T3 pass (T3: 410 passed, `gate-logs/T3-suite.log`). T2 confirms the threat model was updated for `backend.py`.

<!-- pdca:leaf-complete -->

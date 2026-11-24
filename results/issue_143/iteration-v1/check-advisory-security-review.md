# Security review (advisory): prompts YAML, `:context`, recording stub (#143)

**Attacker-reachable inputs this diff touches:** the model's raw response (threat model "Where untrusted input enters" item 5). It reaches the strict `proposal/v1` parser (`src/nl_shell/proposal.py:168-218`), the proposal display (`src/nl_shell/repl.py:52-66`, `:124`) and `:context` (`src/nl_shell/prompts.py:210-215`). Everything else is trusted under the threat model: the user's typed request, `prompts.yaml` in the user's config dir, and the target's shipped default `prompts.yaml` / `target.toml`.

## Findings

No finding at any severity on the threat model's scale.

## What I checked

- **The parser rejects instead of repairing** (`src/nl_shell/proposal.py:176-218`). I ran these against the patched source and each one was rejected:
  - a duplicate `risk` key (`..."risk":"read-only","risk":"privileged"}`) → `duplicate key` (`:157-161`). Python's default would keep the last value silently.
  - `NaN` → rejected (`:164`)
  - 100,000-deep nesting → `RecursionError`, caught (`:183`)
  - a list in place of `risk` → `unknown risk`
  - VT and U+2029 in `command` → hidden character

  Integers over 4300 digits are rejected because of `requires-python >=3.12` (`pyproject.toml:12`). `Rejected.why` holds only fixed text or counts, never response text, and is never printed.
- **The parser and the display use one predicate.** `render.has_hidden` (`src/nl_shell/render.py:50`) gates `command` at `proposal.py:205`, so a command that gets accepted has nothing for `render.escape` at `repl.py:124` to change. What is shown is byte for byte the parsed command, which keeps "What the user confirms is exactly what runs" intact as far as this patch reaches. The predicate covers C0 except LF/TAB, DEL, C1 (including NEL U+0085), the bidi controls, all of Cf, U+2028/9, the tag block and surrogates (`render.py:34-47`).
- **Spoofing the UI through LF.** Every command line is printed behind `  | ` (`repl.py:57-60`), and the header's `risk` is an enum value, so the model can't print an unprefixed line or a fake header. CR is rejected, so it can't overwrite the prefix either. The test is `tests/test_backend.py:454-462`.
- **`:context` output** escapes hidden characters and backslashes (`prompts.py:213`), so a real ESC and the typed text `\x1b` print differently (criterion b). The second `escape` pass at `repl.py:124` leaves that ASCII-only text unchanged, so nothing is escaped twice.
- **Start-up errors** all go through `cli._error` → `render.escape` (`src/nl_shell/cli.py:68-70`), including PyYAML's quoted problem line. The YAML file is loaded with `yaml.safe_load` only (`prompts.py:127`), and the `!!python/object/apply` vector is tested. These files are trusted config, so this is defence in depth, not an attacker path.
- **The tests cover the hostile cases, not just the friendly ones.** Every hidden-character class is rejected in `command`, with `ensure_ascii` both on and off (`tests/test_backend.py:466-486`). The full §Conformance rejection list is tested (`:362-390`), the lone surrogate is tested on a real UTF-8 stream (`:396-408`), and so is the header spoof.

## Notes (not findings)

- No test pins the duplicate-key and `NaN` rejections, which the code handles correctly (probe above). Adding a duplicate-`risk` vector to `REJECTED` in `tests/test_backend.py:364` would pin the case where the risk label is ambiguous. That matters once #12 lets the model's risk label raise the gate's class. It is optional and not required by the brief.
- NBSP inside `command` (`ls -la`) is accepted and shown raw. That is non-ASCII whitespace, which the brief explicitly leaves to #144, and the threat model's Known gaps don't call for raising it here.
- `cli._error` escapes without `backslash=True`, so in a start-up error a real U+202E and the typed text `\u202e` print the same way. The only text that reaches it comes from the user's own paths and config files, which the threat model trusts. The brief only requires the `\u202e` form there, which the patch meets.

<!-- pdca:leaf-complete -->

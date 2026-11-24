## Summary
**User impact:** Today, typing a plain-language request or an `@request` in nl-shell only gets a "the model backend arrives in M0.8" placeholder, and `:context` shows nothing useful. There is no way to see or edit what nl-shell would send to a model, and nothing stops a model answer from putting terminal escape codes or right-to-left override characters on your screen.

This PR adds the request path a model will use: an editable prompts file, a model backend interface (with a recording stub for tests), and a strict parser for the model's answer. `:context` now shows the exact model input of the last request. Every text nl-shell prints from a model answer, `:context` or a start-up error is shown with hidden characters made visible.

Reported in [#143](https://github.com/eduralph/nl-shell/issues/143).

**Depends on #142** (OS target folder and selection): the default prompts file is found through the target loader that PR adds, and this branch is built on top of it. Merge #142 first.

## What to look at
- **What the user sees now.** With no model client yet (that arrives with #77), a plain-language line or `@request` replies `No model backend is configured, so nl-shell can't answer this yet: the model client arrives with #77.` `:context` before any request says `No model input yet: :context shows the model input of the last request.` `:status` gains one `prompts: <path>` line per loaded file.
- **Editable prompts.** The defaults are in `targets/ubuntu-26.04/prompts/prompts.yaml` (system prompt, three examples, request template). Put a `prompts.yaml` in `~/.config/nl-shell/` to override any key. A broken file stops start-up with the file's path, the same as a broken `target.toml`.
- **How a model answer is shown.** A valid command is framed as `Proposed command (risk: read-only, 1 line):`, then each line prefixed `  | `, then `Nothing runs yet: …`. A model answer that breaks the schema in any way, or has a hidden character in the command, gets `No usable proposal came back from the model.` It is never "fixed up".
- **Try it:** `python3 -m pytest tests/test_backend.py`. The tests drive the real REPL with the recording stub, so no model or GPU is needed. Start `nl-shell` with a `~/.config/nl-shell/prompts.yaml` containing `bogus: 1` to see start-up refuse it.
- **New dependency:** `PyYAML>=6` (loaded with the safe loader only).

## Root cause
This is new functionality, not a bug fix: the M0 plan has requests go through prompts → backend → strict parser, and until now none of those parts existed. The display side had no single place that decides which characters are unsafe to print, so each new output path would have needed its own filtering.

## Fix
- `src/nl_shell/render.py` (new): one predicate `is_hidden` and one `escape` function. Hidden means C0 controls except LF and TAB, DEL, C1, the bidi controls, every Unicode format character (category Cf), U+2028/U+2029, the tag block U+E0000–U+E007F, and lone surrogates. They print as `\xHH`, `\uHHHH` or `\UHHHHHHHH`. `:context` also prints a real backslash as `\\`, so a typed `\x1b` and a real ESC look different. #144 can change the character policy in this one file.
- `src/nl_shell/proposal.py` (new): the `proposal/v1` schema, kept once (so #77 can send the same schema for constrained decoding), and `parse()`, which returns a command, a clarify/refuse answer, or a rejection. It rejects bad JSON, duplicate keys, NaN/Infinity, wrong types, unknown values, rule breaks between fields, length limits, too-large integers, too-deep nesting, and any command with a hidden character.
- `src/nl_shell/prompts.py` (new): loads the target's default prompts and the optional user file with `yaml.safe_load`, checks a fixed set of keys (`system`, `examples`, `request_template`), and builds the message list in a fixed order: system prompt first, then the examples in file order, then the request last. Example answers must themselves be valid proposals. `render_input()` is the text form `:context` prints.
- `src/nl_shell/backend.py` (new): a `Backend` interface (`complete(messages) -> str`) and `RecordingStub`, which returns preset answers and records each input in `inputs`.
- `src/nl_shell/repl.py`: `Repl` and `Repl.interactive` take optional `backend=` and `prompts=` keyword arguments (the existing positional calls still work). Plain-language input and `@request` go through `_propose`. Every reply is printed through `render.escape`.
- `src/nl_shell/input_modes.py`: the `:context` placeholder is replaced by the real model input.
- `src/nl_shell/cli.py`: prompts are loaded right after target selection; a prompts error is reported like a config or target error. All start-up messages, including the existing `target.toml` error, go through one `_error()` that escapes them.
- `.oss-scanner/threat_model.md`: the rejection of proposals with bidi or control characters is now credited to the proposal parser (#74 keeps the confirm-screen escaping), and the "How to exercise it" note describes the stub.
- Tests: new `tests/test_backend.py`. `tests/test_repl.py` and `tests/test_input_modes.py` pin the new reply texts. `tests/test_cli.py` and `tests/test_targets.py` give their fake target folders a small prompts file and expect the new `prompts:` status line.

**Design choice to check:** the target's default `prompts/prompts.yaml` is *required*. A target folder without it refuses start-up, like a missing `target.toml`. The other option was to start fine and fail on the first request, but that would break only once #77 lands. Making it optional is a two-line change in `prompts.load` if you prefer that.

## Verification
Line numbers are on this PR's branch (main plus #142).

- **Claim:** `:context` prints exactly what the backend was sent, in the required order (system, examples, request last).
  **Checked:** `src/nl_shell/prompts.py:205-216` (`build`, `render_input`), `src/nl_shell/input_modes.py:101-110`.
  **Test:** `tests/test_backend.py:157` rebuilds the expected text inline from the stub's recorded messages and compares byte for byte, for both a plain line and `@show disk usage`; `:178` pins the reply before any request.
- **Claim:** hidden characters in a request reach the backend unchanged but show escaped in `:context`; a typed backslash shows differently from a real ESC.
  **Checked:** `src/nl_shell/render.py:34-64`.
  **Test:** `tests/test_backend.py:194`, `:525` (one case per character class, including the range ends U+0000, U+001F, U+009B, U+061C, U+2029, U+E007F).
- **Claim:** model answers that break `proposal/v1` are rejected, never repaired, and the REPL keeps running.
  **Checked:** `src/nl_shell/proposal.py:94-147`; `src/nl_shell/repl.py:52-66,142`.
  **Test:** `tests/test_backend.py:386-418` (the spec's conformance list plus duplicate keys, deep nesting, too-large integers), `:424` (lone surrogate on a real UTF-8 stream), `:453` (the three valid shapes are accepted), `:514` (hidden character in a command is rejected).
- **Claim:** a command can't pass itself off as nl-shell's own UI. Every line is prefixed, and TAB and multi-line commands are shown as-is.
  **Checked:** `src/nl_shell/repl.py:52-62`.
  **Test:** `tests/test_backend.py:461`, `:472`, `:482`.
- **Claim:** the user prompts file overrides the default, and a malformed one stops start-up with its path. That includes invalid YAML, wrong types, unknown keys, `!!python/object` tags (not run), huge integers, deep nesting and bad dates.
  **Checked:** `src/nl_shell/prompts.py:89-176`; `src/nl_shell/cli.py:44-54`.
  **Test:** `tests/test_backend.py:259`, `:279-313` (runs the real `cli.main` and checks that `<tmp>/pwned` is never created).
- **Claim:** start-up errors never print a raw bidi override, for prompts files and for the existing `target.toml` error.
  **Checked:** `src/nl_shell/cli.py:53-54,68-70`.
  **Test:** `tests/test_backend.py:329`, `:347`.
- **Claim:** every REPL reply is escaped, not only proposals.
  **Checked:** `src/nl_shell/repl.py:124`.
  **Test:** `tests/test_backend.py:575`.
- **Claim:** `:status` lists the loaded prompts files in load order, and the no-backend reply is exact.
  **Checked:** `src/nl_shell/cli.py:62-65`; `src/nl_shell/repl.py:34-37,145`.
  **Test:** `tests/test_backend.py:539`, `:566`.
- **Fails before, passes after:** with every non-test file reverted, 100 of the 193 tests in `tests/test_backend.py` fail (none fail to import). With the change, all of them pass. The full suite passes (410 tests).

**Known follow-up (tests only):** the hidden-character tests don't yet pin U+E0000 (first tag-block code point) or U+009F (last C1 control). The code handles both correctly today, but narrowing either range end would not turn the suite red. These vectors are planned for #144.

Fixes #143

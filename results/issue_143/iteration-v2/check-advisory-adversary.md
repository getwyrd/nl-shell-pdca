# Adversarial review — prompts YAML, `:context`, recording stub (issue #143)

I could not re-run pytest here (pytest is not installed in this sandbox; PyYAML 6.0.3 is). I read the frozen gate logs instead and ran the production modules directly with `python3 -I` against `$PDCA_TARGET/src` to try inputs the suite does not.

## Evidence (red→green)

- I tried to refute C4 and could not. `gate-logs/C4-verify.log` shows all 64 `tests/test_backend.py` tests red with the fix reverted (the first 64 `F`s; 84 of 177 failed across the bundle) and 177/177 green with it. T3 is 394 passed. The tests go through the production path: a real `Repl` built with `backend=`/`prompts=` (`tests/test_backend.py:131-139`), the real `cli.main` (`tests/test_backend.py:222-249`, which swaps only `Repl.interactive` so it can inject the stub), and the real target loader (`tests/test_backend.py:123-128`). The `:context` oracle (`tests/test_backend.py:57-92`) is a separate copy of the escape rules, as the brief requires. It does not call `render.escape` or `prompts.render_input`.
- Both iteration-1 carry-forward findings are now covered. `tests/test_backend.py:561-569` goes red if the escape is dropped at `src/nl_shell/repl.py:383`: an unknown meta-command echoes a raw U+202E/ESC. The duplicate-key rule (`tests/test_backend.py:404-406`) and the two `request_template` ordering rules (`tests/test_backend.py:290-291`) now have tests.

## Findings

- NEEDS-HUMAN [impl] — `src/nl_shell/prompts.py:126-129`: `_read` catches only `yaml.YAMLError` around `yaml.safe_load`, but PyYAML's safe loader can also raise `ValueError` and `RecursionError`. Two concrete failing cases:
  1. A user `$XDG_CONFIG_HOME/nl-shell/prompts.yaml` holding `system: 999…9` (5000 digits). PyYAML's `construct_yaml_int` calls `int()`, which raises `ValueError: Exceeds the limit (4300 digits)`.
  2. A file holding `system: [[[[…]]]]` (5000 levels deep), which raises `RecursionError`.

  Neither error is a `PromptsError`, so `src/nl_shell/cli.py:52` does not catch it. I ran `cli.main([])` with a matching os-release injected. Both cases exit 1 with a raw Python traceback on stderr, the user file's path appears **0** times in stderr, and the message skips `cli._error` / `render.escape`. This breaks Scope (1), "a malformed file refuses start-up the way #92 refuses a malformed `target.toml`", and criterion (c), "stderr contains the file's full path". It also contradicts this patch's own JSON side: `src/nl_shell/proposal.py:109` already catches `(ValueError, RecursionError)` for exactly these two inputs. Fix: catch `(yaml.YAMLError, ValueError, RecursionError)` at `prompts.py:128`, or wrap the whole `safe_load`, and add both vectors to `MALFORMED` at `tests/test_backend.py:279-292`.
- NEEDS-HUMAN [impl] — `src/nl_shell/proposal.py:109`: the `RecursionError` half of this `except` has no test. With it removed, a model response of `"[" * 100000 + "]" * 100000` would raise out of `Repl._propose` (`src/nl_shell/repl.py:409-410`) and kill the REPL instead of printing `No usable proposal came back from the model.`. I checked that `proposal.parse` returns `Rejected('not valid JSON: RecursionError')` for it today. No test in `REJECTED` (`tests/test_backend.py:381-407`) would go red if the clause were deleted. Add a deep-nesting vector.
- `src/nl_shell/repl.py:316-319` (note, not a blocker): a `command` with a trailing LF (`"ls\n"`), or one that is only `"\n"` or `" "`, is accepted and shown as `2 lines` with empty `  | ` rows. This fits the spec (minLength 1, newlines allowed). Blank or whitespace-only commands belong to #144 ("blank glyphs"), so I'm not filing it as a defect here. It may still be worth a line in the #144 hand-off.
- I also tried these and could not break them: a BOM before the JSON (rejected), duplicate keys (rejected), `clarify` with a `risk` (accepted, which spec rule 2 allows), Cf characters U+00AD, U+FFF9 and U+1D173 (flagged as hidden), double escaping of `:context` by the second `render.escape` pass in `run()` (none: the first pass leaves no hidden characters, and the second leaves backslashes alone), and the safe loader on a `!!python/object/apply` tag (the error is raised and nothing runs). Hangul fillers, CGJ and variation selectors are not flagged, but they are Default_Ignorable characters outside Cf, which the brief places in #144.

## Verdict

C4 and T3 hold up. The `pass` in `check-gates.json` is earned for the criteria the brief lists. The one place I think the review was too generous is the start-up error path. "Malformed prompts refuse start-up cleanly, naming the file" holds only for the inputs PyYAML reports as `YAMLError`. The two inputs above still crash with a traceback, and the builder can fix both by iterating.

<!-- pdca:leaf-complete -->

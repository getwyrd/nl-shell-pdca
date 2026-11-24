# Build notes — #143 (iteration 4) prompts YAML, `:context`, recording stub backend (core of #16)

Base: worktree at `pdca-integration/main-r2546dbf9639f` @ 0771812 (folds #92's 4c755f2 and
#140). Line numbers below are on that base ("base:") or in the patched tree ("new:").

## What changed and why

| File | Change | Wiring point on base |
|---|---|---|
| `src/nl_shell/render.py` (new) | One predicate `is_hidden` and one `escape(text, *, backslash=False)`. Hidden = C0 except LF/TAB, DEL, C1, bidi controls (U+061C, U+200E/F, U+202A–E, U+2066–9), all Cf, U+2028/9, tag block U+E0000–E007F, lone surrogates. Escapes `\xHH` / `\uHHHH` / `\UHHHHHHHH`, lowercase. | Scope (6) |
| `src/nl_shell/proposal.py` (new) | `SCHEMA` (spec's schema, verbatim, kept once; enums/lengths read from it), `parse(raw) -> Command | Answer | Rejected`. Rejects invalid JSON, non-object, extra keys, missing `kind`, unknown enums, wrong types, length outside 1..2000 code points, rule-2 breaks, duplicate keys, NaN/Infinity, the >4300-digit int (Python raises `ValueError`, caught), and any `command` with `render.has_hidden` (covers the lone surrogate). Never repairs. | spec `proposal/v1` §Requirements 1–5; ADR-0018 §3 |
| `src/nl_shell/prompts.py` (new) | Two layers: `<target folder>/prompts/prompts.yaml` (required) then `$XDG_CONFIG_HOME/nl-shell/prompts.yaml` (optional, overrides key by key). `yaml.safe_load` only. Keys `system`, `examples`, `request_template`; unknown keys, wrong types, non-mapping, YAML errors → `PromptsError` naming the file. `build()` makes the ordered message list (system, example user/assistant pairs in file order, request last). `render_input()` is the `:context` text form from the Design. | ADR-0020 §1–§2; ADR-0018 §4; target folder from `targets.py:127` (`Target.folder`) |
| `src/nl_shell/backend.py` (new) | `Backend` protocol (`complete(messages) -> str`), `RecordingStub(responses)` with public `inputs` list, one entry per request. | Scope (3) |
| `src/nl_shell/repl.py` | `Repl.__init__`/`interactive` gain keyword-only `backend=None, prompts=None` (base `repl.py:38-55`); old positional `Repl(read, out[, status_lines])` unchanged. NL replies (base `repl.py:24-31`) and `@request` go through `_propose` (new `repl.py:142`): build → backend → parse → `show_proposal` (new `repl.py:52`). No backend → `NO_BACKEND` literal (new `repl.py:34`). `_reply` (base `repl.py:74-84`) routes `@payload` to the REPL and passes the `:context` text to `input_modes.reply`. Every reply printed through `render.escape` (new `repl.py:124`). | base `repl.py:24-31,38-55,74-84` |
| `src/nl_shell/input_modes.py` | `:context` placeholder (base `input_modes.py:105,112`) replaced by `context(model_input)` (new `:107`) with the fixed `NO_MODEL_INPUT_YET` reply (new `:101`). Meta-command callables now take `(status_lines, model_input)`. `PROPOSE_NOT_YET` removed (the REPL owns `@payload`). | base `input_modes.py:105,112` |
| `src/nl_shell/cli.py` | Loads prompts right after target selection (new `cli.py:44`), inside the same `try` as #92's errors; `PromptsError` joins the `ConfigError`/`TargetError` print (base `cli.py:53-55`, new `:54`). All three start-up prints (no-match, error, mismatch warning) go through one `_error()` that applies `render.escape` (new `cli.py:68`). `:status` lines gain `prompts: <path>` per loaded file after the target lines (new `:62`, base `cli.py:64`). `prompts=` passed to `Repl.interactive`; no backend until #77. | base `cli.py:53-55,64` |
| `targets/ubuntu-26.04/prompts/prompts.yaml` (new) | Default layer: system prompt, three few-shot examples (one per kind), template `State:\n{state}\nRequest: {request}`. | ADR-0023 `prompts/` |
| `pyproject.toml` | `PyYAML>=6` in `dependencies`. | Scope (8) |
| `.oss-scanner/threat_model.md` | Rejection of bidi/control proposals attributed to the parser (M0.8, #143), #74 keeps the confirm-UI escaping; "How to exercise it" stub sentence updated. | `threat_model.md:128-129`, `:198-199` |
| `tests/test_repl.py`, `tests/test_input_modes.py` | Pin the new no-backend literal and the `:context` literal. `PROPOSE` now equals `NATURAL_LANGUAGE`, so the distinct-replies count goes 15 → 14. | brief Test file |
| `tests/test_cli.py`, `tests/test_targets.py` | Fake `interactive` accepts the new keyword args; fake target folders get a minimal `prompts/prompts.yaml`; exact `:status` pins gain the `prompts:` line; the "no allowlist needed" folder listing now includes `prompts`. | see decision 1 |

## Decisions and alternatives

1. **Default prompts layer is required.** A target folder without `prompts/prompts.yaml`
   refuses start-up with `"<path>: missing"`, the same shape as a missing `target.toml`.
   Alternative: skip a missing default and only fail on the first request. Ruled out:
   with no backend today the REPL would start fine and then break the day #77 lands, which
   is the late failure the brief's "malformed file refuses start-up" wants to avoid. Cost of
   the choice: #92's test fakes needed a prompts file — `tests/test_targets.py` +22/−3,
   `tests/test_cli.py` +12/−1. The human may prefer the lenient option; it is a two-line
   change in `prompts.load` (`required=True` → `False`, plus a "no prompts loaded" error
   moved to `_propose`).
2. **Escape at the print point.** `Repl.run` prints `render.escape(reply)`, so every REPL
   reply passes the one function, not just proposals. `:context` text is escaped with
   `backslash=True` when rendered; the second pass is a no-op on it (its output has no
   hidden characters). Proposal lines are not backslash-escaped: commands contain real
   backslashes, and a real hidden character never reaches the display because the parser
   rejects it.
3. **Template validation.** `request_template` must hold `{state}` once and end with
   `{request}` (its only other placeholder); see Iteration 2 for why the separate
   order check was dropped. That makes "the user message ends with the
   request" (criterion (a)) hold for any valid user override. Filling is plain splicing,
   not `str.format`, so braces in the request are kept as typed.
4. **Few-shot `response` values must parse as valid proposals** at load time, so a user
   file cannot teach the model a broken format.
5. **No `:context` record without a backend**: nothing was sent, so `:context` keeps the
   "No model input yet" reply. Not pinned by the brief; my call.
6. **Lazy imports** of `prompts`/`proposal` inside `repl.py` functions keep `Repl` free of
   a PyYAML import when no backend is set. Not required for the test; it keeps
   `from nl_shell.repl import Repl` light.
7. **`target.toml` U+202E vector.** `tomllib` never quotes the offending line (checked:
   `"Invalid value (at line 1, column 6)"`), and #92's value errors use `repr()`, which
   already writes U+202E as `‮`. So a U+202E only in the broken line would pass even
   without the escape. To make the test bind the escape in the start-up print, the
   injected targets root's own name also holds U+202E (`targets‮root`); the error
   prints that path. The broken line still holds U+202E (`shell = "‮bash"`), as the
   criterion asks.

## Iteration 2 — what the carry-forward asked, and what I did

The production design from iteration 1 is unchanged (its review passed C1–C5 and T1–T3).
The carry-forward named test gaps, not wrong behaviour, so this round adds tests that bind
them, plus one production edit where a "rule" turned out to be unreachable code.

| Finding | Change | Proof it now binds |
|---|---|---|
| No test covers the REPL-wide escape, new `src/nl_shell/repl.py:124` | New `test_every_repl_reply_escapes_hidden_characters` (`tests/test_backend.py:561`): no backend, types `:foo` + U+202E + ESC `[2J`; asserts the reply starts `Unknown meta-command :foo‮\x1b[2J. Known: :` and holds no raw U+202E or ESC. | Mutating `:124` to `print((self._reply(text)), …)` → 1 failed, 393 passed (this test). |
| Duplicate-key rejection unpinned, new `src/nl_shell/proposal.py:107` | New `REJECTED["duplicate-key"]` (`tests/test_backend.py:404`): `{"kind":"refuse","kind":"command","command":"ls","risk":"read-only"}`. Last-key-wins would make it a valid command, so it binds. | Dropping `object_pairs_hook=_no_duplicates` → 1 failed (this case). |
| Few-shot `response` validity unpinned, new `src/nl_shell/prompts.py:164` | New `MALFORMED["invalid-example-response"]` (`tests/test_backend.py:286`): a user file whose example response is `df -h` → start-up refused, path in stderr. | Replacing the check with `if False:` → 1 failed (this case). |
| `{state}`-before-`{request}` check unpinned, base-of-iteration `prompts.py:176` | **Removed the check** (new `src/nl_shell/prompts.py:170-177`, with a one-line comment why). It could never fire: `value.endswith(REQUEST)` plus `count(REQUEST) == 1` means `{request}` is the last 9 characters, and the one `{state}` (7 characters, not a substring of `{request}`) can't start inside them, so it is always earlier. That is why the mutation survived: no input reaches it. A test can't go red on removing dead code, so keeping it would leave a "rule" no test could ever bind. The order rule itself is now pinned by `MALFORMED["state-after-request"]` (`'{request}{state}'`) and `MALFORMED["template-not-ending-in-request"]` (`tests/test_backend.py:290-291`). Diff cost: −1 line, +1 comment line. | Dropping `or not value.endswith(REQUEST)` → 2 failed (both new cases). |
| (Low, not required) `target.toml` U+202E vector only bound via the path | `test_bidi_control_in_a_broken_target_toml_is_escaped` is now parametrized (`tests/test_backend.py:337-341`): `bad-value` (`shell = "‮bash"`, as before) and `bad-toml-syntax` (`shell = ‮bash`, unquoted, so the line itself is invalid TOML). The path still holds U+202E: `tomllib` says only `Invalid value (at line 2, column 9)` (checked) and the validator quotes with `!r`, so neither puts a raw U+202E on stderr; the path is what makes the escape in `cli._error` observable. The comment says so plainly. | Covered by the C4 red leg (both cases fail with the fix reverted). |

Mutation runs: each mutation applied to the patched tree in memory, full `tests/` run
under `timeout 120` with the bundle venv's pytest, file restored right after. Clean tree
after all four: `394 passed`.

## Iteration 3 — what the carry-forward asked, and what I did

Started from the iteration-2 patch unchanged (it applied cleanly to 0771812) and fixed
the two round-2 findings. Nothing else moved: `diff iteration-v2/patch.diff patch.diff`
shows only the hunks below.

| Finding | Change | Proof it now binds |
|---|---|---|
| `prompts._read` caught only `yaml.YAMLError`; PyYAML's safe loader also raises `ValueError` (5000-digit int → `int()` digit limit) and `RecursionError` (5000-deep `[[[…]]]`), which escaped `cli.main` as a raw traceback without the file path | New `except (ValueError, RecursionError)` right after the `YAMLError` one (new `src/nl_shell/prompts.py:130-135`) → `PromptsError("<path>: not valid YAML: <ExcType>: <msg>")`, so it goes through #92's start-up error print and `cli._error`'s escape like every other prompts error. I also checked that a bad date (`system: 2024-13-45`) raises a bare `ValueError` from the timestamp constructor (ran `yaml.safe_load('x: 2024-13-45')` on the gate venv: `ValueError`), so it is covered by the same clause. | Three new `MALFORMED` cases (`tests/test_backend.py:294-296`: `huge-integer`, `deep-nesting`, `bad-timestamp`), run through the real `cli.main`; each asserts non-zero exit, no REPL read, the full path in stderr and no `Traceback`. |
| `proposal._parse`'s `RecursionError` catch (`src/nl_shell/proposal.py:109`) had no test | New `REJECTED["deep-nesting"]` (`tests/test_backend.py:409`): `"[" * 100000 + "]" * 100000` fed as the stub's raw response through `Repl`; expects `No usable proposal came back from the model.` and the REPL then handles the next request. No production change. | See mutation run below. |

Rejected alternative: wrapping `yaml.safe_load` in `except Exception`. It would also
swallow real bugs in the loader call as "not valid YAML". The three types listed are the
ones the safe loader is known to raise for bad input; the diff is the same size either way
(one `except` clause), so this is a choice of precision, not cost.

Mutation run (red leg for the new cases): with `prompts.py`'s new clause neutralised
(`except ZeroDivisionError`) and `proposal.py:109` cut to `except ValueError`, the full
suite via `engine/scripts/run-suite.sh` gave exactly
`3 failed, 394 passed` — `test_malformed_user_prompts_refuse_start_up[huge-integer]`,
`[deep-nesting]` and `test_non_conforming_response_is_rejected_and_the_repl_keeps_running[deep-nesting]`.
(`bad-timestamp` was added after that run; it fails the same way on the red leg of C4,
where `prompts.py` does not exist at all.) Both files restored after; clean run below.

## Iteration 4 — what the carry-forward asked, and what I did

The sign-off said production code is fine; the gap was that `HIDDEN`
(`tests/test_backend.py:493-503` in v3) tested one point per range, so narrowing
`render.is_hidden` (`src/nl_shell/render.py:34-47`, new file) would not go red.

- I re-applied the v3 patch unchanged (`git apply iteration-v3/patch.diff` on 0771812,
  clean) and added six boundary vectors to `HIDDEN` (new `tests/test_backend.py:503-509`):
  U+0000, U+001F, U+009B (C1 CSI), U+061C, U+2029, U+E007F. Each feeds both
  `test_command_with_a_hidden_character_is_rejected` (`:514`, proposal rejected → "No
  usable proposal…") and `test_hidden_character_in_a_request_is_escaped_in_context`
  (`:525`, raw in the recorded input, escaped in `:context`).
- No production change: all six new vectors passed on the v3 code. The only diff from
  v3's `patch.diff` is those 7 lines in the test.
- Nothing widened: blank glyphs, non-ASCII whitespace and duplicate YAML keys are left
  as they were.

### Mutation evidence for the new vectors (full suite via `engine/scripts/run-suite.sh`)

| Mutation in `render.py` | Result |
|---|---|
| `code < 0x20` → `0 < code < 0x20` (drop U+0000) | 2 failed (`c0-first-u0000`, both tests) |
| `code < 0x20` → `code < 0x1f` (drop U+001F) | 2 failed |
| `0x7F <= code <= 0x9F` → `<= 0x9A` (drop U+009B) | 2 failed (`c1-nel` U+0085 alone stayed green — the gap the sign-off named) |
| `LINE_AND_PARAGRAPH_SEPARATORS` = `{0x2028}` | 2 failed |
| `TAG_BLOCK` end 0xE0080 → 0xE007F | 410 passed |
| drop 0x061C from `BIDI_CONTROLS` | 410 passed |
| drop the `category == "Cf"` clause **and** both narrowings above | 8 failed, including all four `u061c` / `ue007f` cases |

The two green rows are not a test gap: U+061C and U+E007F are both category Cf, so the
Cf clause (`render.py:46`) still catches them and the behaviour does not change. The
explicit sets exist so the policy does not depend on Python's Unicode version
(`render.py:23-24` comment). The last row shows the new vectors do bind once the Cf
clause stops covering them. `render.py` was restored after each run and checked
byte-identical to the patch's hunk.

## Verification

- C4 gate, project runner (`PDCA_BUNDLE=results/issue_143 PDCA_WORKTREE=…
  engine/scripts/run-verify.sh`): `PDCA-EVIDENCE: C4 PASS — red without the fix (100 of
  193 failed), green with it`; `setup errors 0, import/collection errors 0` on the red leg.
- Full suite, patched tree (`engine/scripts/run-suite.sh`): `410 passed`, `T3 PASS`.
- `patch.diff` and `test_backend.py` in the bundle are byte-identical to the worktree
  (`cmp`).
- Commit-readiness: nl-shell has no formatter or pre-commit config (no
  `.pre-commit-config.yaml`, no ruff/black section in `pyproject.toml`); the only change
  since v3 is 7 test lines in the existing style.

## Refute-your-own-test

- **(a) Genuine red?** Yes. C4 red leg with all production hunks reverted: 100 of 193
  fail, none fail to import. Each new boundary vector also goes red under a mutation that
  narrows the predicate at that boundary (table above).
- **(b) Production path?** Yes. The vectors go through the real `Repl.run` →
  `RecordingStub` → `proposal.parse` → `render.has_hidden`, and `:context` through
  `prompts.render_input` → `render.escape`. The test's expected `:context` text is
  rebuilt inline, not with the module's serializer.
- **(c) Fixture includes the fault?** Yes. Each fault character is placed in the model's
  raw response (both `ensure_ascii=True` and `False` JSON) and in the typed request;
  nothing filters it out before production code sees it.

## Housekeeping

- The worktree index has intent-to-add entries for the new files (`git add -N`), used to
  produce the diff.
- I wrote two backup files outside the worktree during the mutation runs, which I should
  not have: `/home/eddie/nl-shell/render.py.orig` and `/home/eddie/nl-shell/.r` (copies
  of `render.py`). They are not part of the patch. I did not delete them because cleanup
  belongs to the harness; the human may want to remove them.

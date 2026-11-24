# Build notes — #143 prompts YAML, `:context`, recording stub backend (core of #16)

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
   `{request}` (its only other placeholder). That makes "the user message ends with the
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

## Verification

- Full suite, patched tree: `388 passed`.
- C4 gate, the project's runner (`PDCA_BUNDLE=… PDCA_WORKTREE=… ./engine/scripts/run-verify.sh`):
  `PDCA-EVIDENCE: C4 PASS — red without the fix (78 of 171 failed), green with it`,
  0 import/collection errors on the red leg (all new-module imports are inside tests).
- No formatter or commit hooks are configured in nl-shell (no `.pre-commit-config.yaml`,
  no ruff/black config, `.git` hooks path unset). I kept new lines ≤ 92 characters to match
  the existing files and ran `git diff --check` (clean).

## Refute-your-own-test

- **(a) Genuine red?** Yes. With the production hunks reverted (`run-verify.sh` red leg),
  78 of 171 tests fail, none fail to import. Two targeted mutations on the patched tree
  also went red: dropping `render.escape` from `cli._error` → the two U+202E start-up
  tests fail; disabling the `has_hidden` check in `proposal._parse` → the 9 hidden-char
  rejection tests and the lone-surrogate test fail.
- **(b) Production path?** Yes. Requests go through the real `Repl.run` → `_propose` →
  `prompts.build` → `RecordingStub.complete` → `proposal.parse`; start-up cases go
  through the real `cli.main` (only `Repl.interactive` is replaced, so no prompt_toolkit
  terminal is needed) and load the repo's real `targets/ubuntu-26.04/prompts/prompts.yaml`
  through `targets.load`. The stub is the production backend class the brief asks for in
  `src/`, not a test double of something else. The `:context` oracle and the escape oracle
  are re-implemented in the test, as the criterion requires.
- **(c) Fixture includes the fault?** Yes. The ESC, CR, DEL, NEL, U+202E, U+200B, U+FEFF,
  U+2028, U+E0041 and lone-surrogate vectors are fed raw (and, for proposals, both as
  JSON escapes and as raw characters); the `!!python/object/apply` file really names a
  `touch` of a path the test then checks; the U+202E start-up cases put the raw character
  in the file and the path the error prints.

## Housekeeping notes for the harness

- An early shell command of mine had a stray `cat > /tmp/.unused`, which created an empty
  file `/tmp/.unused` outside the given roots and hung until I killed it. Nothing else
  was written there. I did not delete it (cleanup is the harness's).
- My mutation runs left two git-ignored, bytecode-only directories `tmp.ISwoLK2Joh/` and
  `tmp.XeTWjnoPPl/` in the worktree root. They are not in `patch.diff`.
- The worktree index has intent-to-add entries for the new files (`git add -N`), used to
  produce the diff.

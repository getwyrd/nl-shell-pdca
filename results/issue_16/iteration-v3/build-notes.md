# Build notes — issue 16 / prompts-yaml-context-recording-stub (iteration 3)

Base: the wave integration branch @ `2ddc3e8` (main + #14 + #92 folded). All `path:line`
below are on the patched worktree.

This iteration starts from the iteration-2 patch (`iteration-v2/patch.diff`, applied
unchanged). Per the sign-off, it keeps the rest of that build and changes only the three
display / hidden-character points. The iteration-2 and iteration-1 notes follow below and
are still accurate, except where this section says otherwise.

## Iteration 3 — what the sign-off asked for, and what changed

### 1. A wider hidden-character set (`render.is_hidden`, shared by parser and escaping)

- `src/nl_shell/render.py:50-64`: `is_hidden` now also returns True for every character
  of Unicode category Cf (`unicodedata.category(char) == "Cf"`, line 63), U+2028/U+2029
  (`SEPARATORS`, line 43) and the whole tag block U+E0000–U+E007F (`TAG_CHARACTERS`,
  line 45). I list the tag block as a range because not all of it is Cf: U+E0000 and
  U+E0002–U+E001F are unassigned (Cn). U+00AD, U+200B, U+200D, U+2060, U+FEFF and the
  bidi controls are all Cf.
- The parser uses the same `is_hidden` (`src/nl_shell/proposal.py:144`), so a `command`
  holding any of these is rejected → "No usable proposal came back from the model." The
  docstring list is updated (`proposal.py:14-18`).
- **New escape form for code points above U+FFFF.** The old `\uHHHH` written with
  `{cp:04x}` printed U+E0041 as `1`, which reads the same as U+E004 followed by
  "1". So `escape_char` (`render.py:67-73`) now writes `\UHHHHHHHH` (8 hex digits, as
  Python does) above U+FFFF. Before this iteration no hidden character was above U+FFFF,
  so nothing that used to print changes.
- Tests: `HIDDEN` gains 11 parser-reject vectors (`tests/test_backend.py:587-597`: U+00AD,
  U+200B, U+200D, U+2060, U+FEFF, U+2028, U+2029, U+E0000, U+E0001, U+E0041, U+E007F).
  `test_invisible_characters_in_a_request_are_shown_escaped` (`tests/test_backend.py:661`)
  covers the `:context` side for 9 of them, with the escaped text pinned as literals
  (`​`, `\xad`, `﻿`, ` `, `\U000e0041`, ...). The test's own inline
  `hidden`/`escape` helpers apply the same rule (`tests/test_backend.py:86-117`); they use
  the standard library's `unicodedata`, not the module under test.

### 2. One-to-one `:context` escaping (backslash escaped too)

- `src/nl_shell/render.py:76-87`: `escape_hidden(text, *, backslash=False)`. With
  `backslash=True` a literal `\` prints as `\\`. Every backslash in the output then starts
  an escape (`\\`, `\xHH`, `\uHHHH`, `\UHHHHHHHH`), so the output can be decoded back to
  exactly one input.
- `src/nl_shell/repl.py:180`: `_context` returns
  `escape_hidden(context_text(...), backslash=True)`. The print in `Repl.run`
  (`repl.py:133`) still escapes hidden characters. After `_context` has escaped, nothing
  hidden is left, so that second pass changes nothing.
- **Only `:context` doubles backslashes. Other replies don't.** I ruled out doubling them
  in every reply. A proposed `grep -E 'a\|b'` would then show as `grep -E 'a\\|b'`, which
  is not the command that would run. A command can never hold a hidden character (the
  parser rejects it), so any `\x1b` the user sees in a shown command is literal text and
  nothing is ambiguous. Pinned by the `backslash` case of
  `test_newline_and_tab_in_a_command_are_shown_as_is` (`tests/test_backend.py:544`).
  Other replies that echo user text (e.g. #14's unknown-meta-command reply) remain
  escape-only, not one-to-one. The sign-off scoped this point to `:context`.
- Tests: `test_context_escaping_is_one_to_one` (`tests/test_backend.py:671`) sends a real
  ESC and the typed four characters `\x1b`. The stub records them raw and differently.
  `:context` prints `\x1b` for the ESC and `\\x1b` (two backslashes, pinned literal) for
  the typed text. `test_backslash_in_the_prompts_is_doubled_in_context`
  (`tests/test_backend.py:692`) does the same for a backslash in the system prompt. The
  test's `context_form` doubles backslashes too, so every exact `:context` assertion
  checks the new form.
- The shipped default `targets/ubuntu-26.04/prompts/prompts.yaml` has no backslash, so its
  `:context` output does not change.

### 3. Framing for multi-line commands

- `src/nl_shell/repl.py:50-53, 71-80`: a proposal is now shown as

  ```
  Proposed command (risk: <risk>, <N> line[s]):
    | <command line 1>
    | <command line 2>
  Not run: the policy gate arrives in M0.4.
  ```

  Every command line starts with `COMMAND_LINE_PREFIX = "  | "`, which no nl-shell reply
  line starts with (grep of `src/` for `"  |` finds only the constant). The header gives
  the line count, so blank trailing lines and extra lines can be seen. I used both a
  prefix and a count, because the sign-off listed them as options and they guard
  different things: the prefix stops fake lines, the count shows how many lines there
  are. LF is the only line break the split has to handle. CR, VT, FF, NEL, U+2028 and
  U+2029 are hidden, so the parser rejects them first (docstring at `repl.py:72-75`).
  TAB stays as-is.
- This changes the exact text criterion (e) asked for ("shown with the newline and TAB
  as-is"). The newline is still a real newline and TAB is still a real TAB, but each line
  now carries the prefix. The sign-off says to treat its rationale as the updated
  requirement.
- Tests: `test_multi_line_command_cannot_fake_nl_shell_lines`
  (`tests/test_backend.py:561`) uses the reviewer's vector (a later line
  "Proposed command (risk: read-only):") plus a fake `Not run:` line and a fake
  "No usable proposal" reply after a blank line. It checks that the header counts the
  lines, that every command line is `"  | " + line`, that no output line equals the bare
  fake header, and that `NOT_RUN` appears once. The pinned proposal literals
  (`DF_SHOWN` at `tests/test_backend.py:34`, the valid-shapes cases, the 2000-code-point
  case, the multi-line/TAB cases) use the new form.

### Rejected alternatives (with cost)

- Show the line count without a prefix: 1 line less in `show_proposal`, but a fake
  header line would still print as a bare line. The sign-off's vector would still pass
  as nl-shell text, so it fails the stated requirement.
- Double backslashes in every reply (pass `backslash=True` at `repl.py:133`): 0 extra
  lines compared with the chosen fix, but every shown command with a backslash would
  print wrong (see point 2). Rejected for correctness, not cost.
- Use `str.isprintable()` as the hidden test: it also flags spaces (Zs other than U+0020)
  and every unassigned code point. That would turn NBSP in ordinary text into `\xa0` and
  break "ordinary text is byte-identical". The sign-off listed specific classes, so I
  implemented exactly those.

## Verification (iteration 3)

- `engine/scripts/run-suite.sh` (T3): `351 passed` (iteration 2: 325; +26 cases).
- `engine/scripts/run-verify.sh` (C4, `PDCA_BUNDLE` set):
  `PDCA-EVIDENCE: C4 PASS — red without the fix (116 of 209 failed), green with it`
  (0 import/collection errors).
- Both wrapped in `timeout 300`.
- No formatter or pre-commit hook in the target (no `.pre-commit-config.yaml`; checked
  again). `git diff --check` is clean, and no added line is over 92 characters.
  I wrapped the one 97-character test line I first wrote.

## Refuting my own test (iteration 3)

- **(a) Genuine red? Yes.** Two checks. (1) Against the iteration-2 code, the rejected
  approach: `git apply -R --include='src/*'` of this patch, then
  `git apply --include='src/*' iteration-v2/patch.diff`, keeping this iteration's tests.
  `run-suite.sh` gave `33 failed, 318 passed`. The failures were exactly the new or
  changed cases: 11 Cf/separator/tag parser vectors, 9 `:context` escape vectors, the
  two backslash tests, the 3 fake-line framing cases, and 8 pinned-proposal-format cases.
  Then I swapped the source back. The worktree diff matched `patch.diff` byte for byte
  (`cmp`), and the suite gave `351 passed`. (2) The C4 gate reverts all production code:
  116 of 209 fail.
- **(b) Production path? Yes.** Every new case drives the real `Repl` with the real
  `RecordingStub` and the real `prompts.load`, or the real `proposal.parse`. The expected
  `:context` text is rebuilt by the test's own inline escaping. It does not call
  `escape_hidden`.
- **(c) Fixture includes the fault? Yes.** The raw characters themselves (U+200B, U+FEFF,
  U+2028, U+E0041, ...) are in the request lines and the JSON commands. The reviewer's
  fake-header command is fed as the stub's raw response. The ESC-vs-typed-`\x1b` pair is
  sent through the same session.

## Housekeeping (iteration 3)

- While comparing the worktree to the patch, a mistyped redirect created an untracked
  file `.git-cmp` in the worktree root. It is not intent-added, so it is not in
  `patch.diff` (15 files, same list as iteration 2). I did not remove it, per the
  no-cleanup rule. Nothing was written outside the worktree and the bundle folder.

---

# Iteration 2 notes (carried over)

Base: the wave integration branch `pdca-integration/main-r2546dbf9639f` @ `2ddc3e8`
(main + #14 + #92 folded). All `path:line` below are on the patched worktree.

This iteration starts from the iteration-1 patch (`iteration-v1/patch.diff`, applied
unchanged) and fixes the three crash paths the review reproduced. The iteration-1 notes
follow below, still accurate except where this section says otherwise.

## Iteration 2 — what the carry-forward asked for, and what changed

### 1. Huge JSON integers crashed the parser (and the REPL)

`json.loads` raises a plain `ValueError` (not `JSONDecodeError`) for an integer longer
than `sys.get_int_max_str_digits()` (4300). Only `JSONDecodeError` and `RecursionError`
were caught.

- Fix: `src/nl_shell/proposal.py:118-121` adds `except ValueError` after the
  `JSONDecodeError` clause (that clause stays first so its `exc.msg` wording is kept).
  The response is `Rejected`, so the REPL says "No usable proposal came back from the
  model."
- Ruled out: `parse_int=` with a length guard. It only covers integers. Catching
  `ValueError` covers any other plain `ValueError` `json.loads` might raise, in one line.

### 2. Lone surrogates were accepted and crashed the print to a UTF-8 stream

JSON `"\ud800"` decodes to a lone surrogate. `is_hidden` did not count it, so the command
was accepted, and `print` to `sys.stdout` raised `UnicodeEncodeError`.

- Fix: `src/nl_shell/render.py:25, 29-40` adds U+D800–U+DFFF to `is_hidden`. Because the
  parser uses the same function (`src/nl_shell/proposal.py:144`), a `command` holding a
  lone surrogate is now rejected. `escape_hidden` writes any other lone surrogate that
  reaches a reply (for example from undecodable terminal input, which Python's
  `surrogateescape` turns into U+DC80–U+DCFF) as `\udXXX`. That covers `:context`, since
  every reply goes through the single escaped print at `src/nl_shell/repl.py:115`.
- Why add it to the hidden set instead of a separate parser check: one test for "what is
  rejected" and "what is escaped" keeps the two from drifting, which was the design of
  `render.py`. The brief's escape set (criterion (e) plus C0) does not name surrogates.
  The brief also requires ordinary text to stay byte-identical, and a lone surrogate
  can't be written as UTF-8 at all, so escaping it is the only way to print it. This
  goes beyond the brief's list. Flagging it for the human.
- Prompts: a YAML `"\ud800"` escape also gives a lone surrogate, which would crash
  `:context` and could not be sent by #77's HTTP client. `src/nl_shell/prompts.py:155-158`
  rejects it in any prompt string (system, example request, template), naming the file.
  Example responses already go through `proposal.parse`, so they are covered by fix 2.

### 3. Some malformed `prompts.yaml` files escaped start-up error handling

I probed the safe loader with the gate venv's PyYAML. Before the fix, these raised a
non-`YAMLError` that left `cli.main` as a traceback instead of the "names the file,
non-zero exit" refusal:

| Input | Exception |
|---|---|
| `[a, b]: x` (sequence key), `? {a: 1}\n: x` (mapping key), `examples: [ {[request]: x} ]` | `TypeError` (unhashable key) in `_construct_mapping` |
| `system: 111…` (5000 digits) | `ValueError` from PyYAML's int constructor |
| `system: [[[…]]]` (5000 levels) | `RecursionError` |

- Fix: `src/nl_shell/prompts.py:92-97` turns an unhashable key into a
  `ConstructorError` ("a mapping key must be a scalar"), which the existing
  `except yaml.YAMLError` reports. `src/nl_shell/prompts.py:128-133` catches `ValueError`
  and `RecursionError` around `yaml.load` and raises `PromptsError` naming the file.
- Ruled out: a catch-all `except Exception` around `yaml.load`. It would also hide real
  bugs in the loader. The three classes above are all I could reproduce.

### Tests added (all in `tests/test_backend.py`)

- `test_invalid_responses_are_rejected_not_repaired`: 4 vectors — integer over the digit
  limit as `kind` and as an extra property; lone high and low surrogate in `command`
  (`tests/test_backend.py:458-463` vectors, `488-491` ids).
- `test_command_with_a_hidden_character_is_rejected`: U+D800 and U+DFFF
  (`tests/test_backend.py:526-527`).
- `test_lone_surrogate_in_a_command_is_rejected_on_a_utf8_stream` and
  `test_lone_surrogate_in_a_request_is_shown_escaped_on_a_utf8_stream`
  (`tests/test_backend.py:544-573`): the REPL writes to
  `io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="strict")`, the same kind of
  stream as `sys.stdout`, as the reviewer asked. `io.StringIO` accepts surrogates, which is
  why iteration 1's tests missed this.
- `test_other_invalid_user_prompts_refuse_start_up`: 6 vectors — sequence key, mapping
  key, sequence key inside an example, 5000-digit integer, 5000-deep nesting, lone
  surrogate (`tests/test_backend.py:355-364`). These go through the real `cli.main`; the
  `start` fixture also asserts `"Traceback" not in err`.
- The test's own `escape()` helper now also escapes U+D800–U+DFFF
  (`tests/test_backend.py:77-78, 88-90`), matching the documented escaping.

## Verification (iteration 2)

- `engine/scripts/run-suite.sh` (T3): `325 passed` (was 311 in iteration 1; +14 cases).
- `engine/scripts/run-verify.sh` (C4, `PDCA_BUNDLE` set):
  `PDCA-EVIDENCE: C4 PASS — red without the fix (90 of 183 failed), green with it`.
- Both wrapped in `timeout 300`.
- No formatter or pre-commit hook in the target (same as iteration 1). `git diff --check`
  is clean; I also removed the extra blank line at the end of `prompts.py` that the
  iteration-1 patch carried (`git apply` warned "new blank line at EOF"). No new line is
  over 92 characters.

## Refuting my own test (iteration 2)

- **(a) Genuine red? Yes.** Two checks. First, against the iteration-1 code (the rejected
  approach): I moved my fixed `render.py`, `proposal.py`, `prompts.py` aside, restored the
  iteration-1 versions from `iteration-v1/patch.diff`, and ran `run-suite.sh`: exactly the
  14 new cases failed (`14 failed, 311 passed`), each of the three bugs among them. Then I
  put the fixed files back: `325 passed`. Second, the C4 gate reverts every production
  hunk: 90 of 183 fail, 0 collection errors.
- **(b) Production path? Yes.** The new cases call the real `proposal.parse`, the real
  `Repl` with the real `RecordingStub` and `prompts.load`, and the real `cli.main` for the
  prompts cases. The UTF-8 tests use a real `TextIOWrapper`, not a stand-in stream.
- **(c) Fixture includes the fault? Yes.** The exact reproducers from the review: a
  5000-digit integer, `\ud800` in a JSON string, YAML sequence keys, written into the real
  `$XDG_CONFIG_HOME/nl-shell/prompts.yaml` the loader reads. The output stream is one that
  rejects surrogates, the property that made the bug crash.

## Housekeeping (iteration 2)

- To hold the fixed files during the check against iteration-1 code, I made an untracked
  folder `.pdca-scratch/` inside the worktree. It is not in `patch.diff` (the patch lists
  only the 15 intended files). Not removed, per the no-cleanup rule. Nothing was written
  outside the worktree and the bundle folder this time.

---

# Iteration 1 notes (carried over)

Base: the wave integration branch `pdca-integration/main-r2546dbf9639f` @ `2ddc3e8`
(main + #14 + #92 folded). All `path:line` below are on the patched worktree unless marked
"base".

## What changed and why

| Piece | Where | Brief scope item |
|---|---|---|
| Hidden-character test + escaping (`is_hidden`, `escape_hidden`, `BIDI_CONTROLS`) | `src/nl_shell/render.py:20-41` (new) | (4), (5) |
| `proposal/v1` parser, `SCHEMA` kept once, typed `CommandProposal` / `Decline` / `Rejected` | `src/nl_shell/proposal.py:29-155` (new) | (4) |
| `Message`, `ModelInput`, `Backend` protocol, `BackendError`, `context_text`, `RecordingStub` | `src/nl_shell/backend.py:30-67` (new) | (2), (3) |
| prompts loader (two layers, safe loader, fixed keys, validation), `build_messages`, `status_line` | `src/nl_shell/prompts.py:50-235` (new) | (1), (2), (6) |
| default prompts layer | `targets/ubuntu-26.04/prompts/prompts.yaml` (new) | (1) |
| REPL wiring: `backend=` / `prompts=` keywords, NL + `@` → prompt → backend → parser, `:context`, print-time escaping | `src/nl_shell/repl.py:36-62, 68-98, 115, 117-160` (base wiring points `repl.py:25-32`, `38-55`, `72`, `74-84`) | (5), (6) |
| reply constants for `@` with no backend, `:context` before any request | `src/nl_shell/input_modes.py:101-108, 115, 136` | (5), (6) |
| start-up: load prompts after target selection, refuse on `PromptsError`, `:status` line, pass prompts to `Repl.interactive` | `src/nl_shell/cli.py:10, 44-46, 56, 66-68` (base `cli.py:9, 127, 137, 147-148`) | (1), (6) |
| `PyYAML>=6` dependency | `pyproject.toml:15` | (7) |
| threat model `How to exercise it` sentence | `.oss-scanner/threat_model.md:175-178` | (7) |

### Design choices made at build time (not pinned by the brief)

- **Prompt keys:** `system` (non-empty string), `examples` (list of `{request, response}`;
  `response` is a YAML mapping that must parse as a valid `proposal/v1` object, so a few-shot
  can never teach an invalid shape), `request_template` (must hold `{state}` once and end
  with `{request}`). `system` and `request_template` must be set by some layer; `examples`
  defaults to none. Substitution is plain string replacement, never `str.format`, so braces
  in a request are text (`prompts.py:220-222`).
- **Few-shot messages:** each example is a `user` message (the template rendered with an
  empty state) then an `assistant` message (the response as `json.dumps(..., ensure_ascii=False)`).
- **Strictness beyond the brief, all in the "reject not repair" spirit:** duplicate keys
  are refused both in `prompts.yaml` (custom `SafeLoader` subclass, `prompts.py:77-96`) and
  in a model response (`object_pairs_hook`, `proposal.py:85-91`); `NaN`/`Infinity` are
  refused as not RFC 8259 JSON (`proposal.py:81-82`); trailing text after the object is
  refused (json.loads does this already).
- **Not rejected:** `risk` on a `clarify`/`refuse` response. Spec rule 2 forbids only
  `command` there, and the schema allows `risk`. I first rejected it, then removed that
  check so the parser matches the normative spec exactly. Worth a spec clarification
  (open question for the human / #68).
- **Empty `prompts.yaml`** is an empty layer (no keys), not an error: a user who creates
  the file to start editing should not be locked out. "Not a mapping" (e.g. a list) is
  still an error.
- **A target with no `prompts/prompts.yaml` and no user file** loads as `None`: start-up
  still works (the #92 test targets have no prompts folder), `:status` says
  `prompt files: none`, and a request with a backend gets a fixed `NO_PROMPTS` reply
  (`repl.py:40-43, 139-140`). A layer that exists but leaves a required key unset is an
  error naming the file (`prompts.py:200-204`).
- **Escaping is applied once, at the single print in `Repl.run` (`repl.py:115`)**, so every
  reply is filtered, not only `:context`. The backend gets raw text; `:context` prints
  `context_text` of the very tuple the backend was handed (`repl.py:141-144, 156-160`).
- **Interactive REPL gets the prompts but no backend** (`repl.py:87-98`), so #77 only has to
  add the backend. `cli.main` passes `prompts=` to `Repl.interactive`.

### Changes to existing tests (necessary, not weakening)

- `tests/test_repl.py`, `tests/test_input_modes.py`: the pinned NL, `@` and `:context`
  literals change to the new no-backend / no-input-yet texts (the brief asked for the
  `test_repl.py` literal update). The 15 replies are still distinct.
- `tests/test_cli.py`, `tests/test_targets.py` (#92's): the fake `Repl.interactive` now
  accepts `prompts=None`, and the exact `:status` expectations gain the new last line
  `prompt files: none` (5 literals). This is criterion (f) showing up in #92's exact-output
  tests. Rejected alternative: omit the line when nothing was loaded — zero edits to #92's
  tests, but `:status` would then be silent about why no prompts are in use, and ADR-0020 §4
  says `:status` shows which files were loaded.

## Verification

- Project runners only: `engine/scripts/run-suite.sh` (T3) → `311 passed`;
  `engine/scripts/run-verify.sh` (C4, with `PDCA_BUNDLE` set) →
  `PDCA-EVIDENCE: C4 PASS — red without the fix (82 of 175 failed), green with it`.
  Both wrapped in `timeout 300`.
- No formatter or pre-commit hook is configured in the target (no `.pre-commit-config.yaml`,
  no ruff/black in `pyproject.toml`; CI runs only pytest and the docs checks).
  `scripts/docs_links.py` → 0 broken links. `docs_checks.py immutability` concerns ADRs,
  none touched. Line widths match the repo's existing style (up to ~92).

## Refuting my own test

- **(a) Genuine red? Yes.** The C4 red leg reverts every production hunk and re-runs the
  changed test files: 82 of 175 fail, 12 setup errors, 0 collection errors. The
  `test_backend.py` tests fail at their in-function imports of `nl_shell.backend` /
  `prompts` / `proposal`, and the `Repl` asserts get today's "can't answer it yet" and
  #14's `:context` placeholder. Mutation checks on the fixed tree, each run through
  `run-suite.sh` and then undone:
  - `Repl.run` printing without `escape_hidden` → 2 failures (ESC and bidi/C1 `:context` tests);
  - parser hidden-character check removed → 22 failures (every hidden-character vector);
  - `yaml.UnsafeLoader` instead of the safe loader → `python-tag` and `duplicate-key` fail.
    **This one first stayed green.** My autouse fixture empties `$PATH` (so `show ...`
    routes as natural language), so the tag's `touch` was never found and no file
    appeared. Fixed: that test sets `PATH=os.defpath` (`tests/test_backend.py`,
    `test_malformed_user_prompts_refuse_start_up`). It now goes red under the unsafe loader.
- **(b) Production path? Yes.** Every REPL case builds the real `Repl` with the real
  `RecordingStub` and prompts loaded by the real `prompts.load`; (c) and (f) go through the
  real `cli.main` with only `Repl.interactive` swapped, so that the REPL gets the stub, the
  same way #92's tests do. The `:context` expected text is rebuilt in the test from the
  stub's recorded list with an inline copy of the documented form and escaping, as the
  brief requires. It does not call `context_text` / `escape_hidden`. One test loads the
  shipped `targets/ubuntu-26.04/prompts/prompts.yaml` through `targets.load(...).folder`.
- **(c) Fixture includes the fault? Yes.** Raw ESC / U+202E / U+0085 in request lines; the
  real `!!python/object/apply:os.system` tag with a real `touch` on `PATH` and a check that
  the file does not exist; each malformed `prompts.yaml` written to the real
  `$XDG_CONFIG_HOME/nl-shell/` the loader reads; every conformance vector fed as the stub's
  raw response.

## Mistakes during the build, fixed

- During a mutation check I ran `git checkout -- src/nl_shell/repl.py` to undo the
  mutation. That reset the whole file to the base and dropped my `repl.py` changes. I
  restored them at once from the saved `patch.diff`
  (`git apply --include=src/nl_shell/repl.py`), then checked that the regenerated diff's
  production hunks match the saved one byte for byte (the only difference was the test fix).
- I wrote one stray file outside the harness roots, `/tmp/x.diff` (a copy of `git diff`
  used while comparing). It holds only the patch. Not removed, per the no-cleanup rule.

## Out of scope / left for others

- HTTP client, endpoints, `--dev-teacher` (#77); `?` ask mode stays #14's placeholder; the
  state block (#11) is an empty `{state}` slot; the "risk lower than the gate's class"
  vector (#12); confirm UI (#74); architecture doc 05.
- Packaging: a non-editable install has no `targets/`, so no default prompts until #48/#50,
  as the brief accepts.

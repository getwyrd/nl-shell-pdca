# Build notes — #144 character-safety policy based on UTS #39

Base: the wave base `pdca-integration/main-r2546dbf9639f` @ `cefb359` (folds #143, #141,
#140). Worktree: `/home/eddie/nl-shell/nl-shell.pdca-wt-l1`. Line numbers below are in the
patched tree unless marked "base".

## What changed and why

1. **`scripts/gen_unicode_tables.py` (new).** Reads the UCD from `/usr/share/unicode/`
   (`unicode-data` 16.0.0) and writes `src/nl_shell/_unicode_tables.py`. It refuses to run
   if any of the files it reads is not version `--expect` (default `16.0.0`), so a regen on
   a host with a different UCD can't quietly change the pinned version. Tables written:
   CF, CO, CN (any code point UnicodeData doesn't list is Cn), MARK (Mn+Me),
   DEFAULT_IGNORABLE, WHITE_SPACE, SCRIPT_EXTENSIONS (scx with Zyyy/Zinh removed; code
   points with nothing left are left out, which the lookup reads as "Common/Inherited,
   ignore"). Scope (4).
2. **`src/nl_shell/_unicode_tables.py` (new, generated, committed).** 2137 lines, 63 KB,
   `UNICODE_VERSION = "16.0.0"` at line 10. I checked it against Python 3.14's
   `unicodedata` (which is also 16.0.0): CF, CO, CN and MARK match code point for code
   point (170 / 137468 / 819533 / 2033). Regenerating gives a byte-identical file.
3. **`src/nl_shell/render.py`** — base lines 34-47 (`is_hidden` with its hand-picked
   checks plus `unicodedata.category == "Cf"`) are replaced by one merged range table,
   `_HIDDEN` (render.py:94-108): #143's control/bidi/separator/tag/surrogate ranges + Cf + Co
   + Cn + Default_Ignorable + White_Space minus SPACE/LF/TAB + U+2800. `is_hidden` is still
   the one predicate (render.py:125). `import unicodedata` is gone; every property comes
   from the vendored module. New helpers: `is_mark` / `too_many_marks` (render.py:135-147,
   Scope 2, `MAX_MARKS = 2`), `scripts` + `mixed_script_word` (render.py:150-172, Scope 3,
   with the UTS #39 §5.1 Hanb/Jpan/Kore augmentation in `AUGMENTED`, render.py:113, and word
   splitting at `string.whitespace + string.punctuation`, render.py:120). `escape`
   (render.py:184) now also escapes the 3rd and later mark in a row. The marks run counts
   every Mn/Me, including ones that are also hidden (U+034F), since they still stack on
   the base.
4. **`src/nl_shell/proposal.py:133-138`** — next to #143's hidden check (base
   `proposal.py:131-132`), add the combining-mark and mixed-script rejections. The check
   runs on the whole `command` string, so it applies inside quotes too (Scope 5). Docstring
   updated (proposal.py:3-8).
5. **`.oss-scanner/threat_model.md:127-137`** — the "What the user confirms is exactly what
   runs" bullet now names the policy and records that rejecting inside quotes is stricter
   than `docs/design/specs/policy-gate/v1.md:58-61`, which #12 may relax. The sudo bullets
   are untouched. The spec is not edited (a frozen record; brief Scope 5).

## Choices and what I ruled out

- **Policy location.** All checks live in `render.py` so there is still one place for the
  character policy (its docstring already said "#144 refines it"). proposal.py only calls
  them. Putting the script logic in proposal.py would split the policy across two modules.
- **One merged hidden table vs. a check per table.** Merging at import costs one sort of
  ~1000 ranges once; each lookup is then one bisect. Separate checks would be 6+ bisects per
  character. Either is fine for a 2000-char command; merged is simpler to read.
- **Keeping #143's ranges as code, not in the tables.** C0/C1/DEL are Cc, which isn't one of
  the property tables the brief lists. The ranges are fixed by definition, not version
  dependent, so they stay as constants in render.py:47-53.
- **Not stored: Hanb/Jpan/Kore in the table.** The augmentation is policy, so it's in code
  (`AUGMENTED`), not baked into the generated data.
- **Known strictness (follows the brief, worth a human look):** single-script
  intersection rejects Latin+Han in one word, e.g. `file日本.txt` (word `file日本`). UTS #39's
  "Highly Restrictive" level would allow Latin+Jpan. The brief asks for intersection after
  augmentation (§5.1), which rejects it. Words split at ASCII punctuation, so
  `日本/file.txt` passes.

## Tests — `tests/test_charsafety.py` (43 tests)

All go through the real `Repl` with `RecordingStub` and the real ubuntu-26.04 prompts.
Commands are sent both as `\uXXXX` JSON and as raw UTF-8. Mapping to the Success criterion:
(1) `test_command_with_a_hidden_character_is_rejected` (15 vectors, unquoted and quoted) and
`test_hidden_character_in_a_request_is_escaped_in_context` (lowercase escapes pinned as
literals, e.g. `\xa0`, `\U000e0100`); (2) the three combining-mark tests, including the
`e`, two raw U+0301, `́` `:context` line; (3) three mixed-script vectors; (4) five
accepted commands shown unchanged; (5) `test_tables_record_unicode_16` and
`test_policy_reads_the_vendored_tables_not_unicodedata`. The second one patches
`unicodedata.category` so the interpreter claims U+0378 is assigned and U+1C89 is not, and
sets `unidata_version` to 15.0.0. `ls Ᲊ` is still accepted and `ls ͸` still
rejected. This shows the policy ignores the runtime database, which is the point of (5).
On 3.14 a plain run can't show this, because the runtime is already 16.0.

## Runs (project runners)

- `engine/scripts/run-verify.sh` (C4): `PDCA-EVIDENCE: C4 PASS — red without the fix (37 of
  43 failed), green with it`. Green: 43 passed.
- `engine/scripts/run-suite.sh` (T3): `524 passed` — `tests/test_backend.py` included.
  #143's `oracle_hidden` there only checks #143's own set, which is still hidden.
- Formatter / hooks: the target has none configured (no `.pre-commit-config.yaml`, no
  ruff/black config, no git hooks). I kept every changed hand-written line at or under 91
  characters, the existing maximum in `src/nl_shell/*.py`. Files compile with
  `python3 -I -m py_compile`.

## Refuting my own test

- **(a) Genuine red?** Yes. run-verify.sh reverted the production hunks (render.py,
  proposal.py, the tables module, the generator) and re-ran: 37 of 43 failed, 0 collection
  errors (the test imports `nl_shell` modules inside functions, so it loads). The 6 that
  pass without the fix are the accept cases in (4) and "two marks accepted" in (2). They
  pass on #143's code too, which is correct: they guard against over-rejection, not the
  defect.
- **(b) Production path?** Yes. Each vector goes through `Repl.run` → `proposal.parse` →
  `render.has_hidden` / `too_many_marks` / `mixed_script_word` → `render.escape`, exactly
  as at runtime. Nothing is mocked except the model (the project's `RecordingStub`). The
  only patch is to `unicodedata` in test (5), to show production doesn't read it.
- **(c) Fixture includes the fault?** Yes. Every character the iteration-3 reviews showed
  passing (U+3164, U+115F, U+1160, U+FFA0, U+034F, U+FE00, U+FE0F, U+E0100, U+17B4,
  U+180B, U+2800) is a vector, plus U+00A0, U+3000, U+E000, U+0378, the three-mark stack
  and the three mixed-script words from the brief.

## Housekeeping

- I copied the generated module once to `/tmp/x` to compare it byte for byte with a
  regenerated copy. That's a file outside the worktree/bundle roots, which I shouldn't
  have made. It's a throwaway copy of a committed file; I left it for the harness to
  reclaim rather than run `rm`.
- External dependency `unicode-data` was present (pdca.toml already has a doctor row for
  it). No NEEDS-HUMAN dependency.
- Not pushed; no PR opened.

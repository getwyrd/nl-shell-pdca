# Build notes — #144 character-safety policy based on UTS #39 (iteration 2)

Base: the wave base `pdca-integration/main-r2546dbf9639f` @ `cefb359` (folds #143, #141,
#140). Worktree: `/home/eddie/nl-shell/nl-shell.pdca-wt-l1`. Line numbers are in the
patched tree unless marked "base".

## What this iteration changed

I started from the iteration-1 patch (`iteration-v1/patch.diff`, applied cleanly to
`cefb359`) and fixed the two items in the carry-forward. The rest of the design is the
same; its rationale is repeated below so this file stands alone.

1. **Test (5) was only binding for Cn.** `tests/test_charsafety.py:194-226` now fakes the
   interpreter's `unicodedata` on every property the policy uses: U+0378 → Lu and U+1C89 →
   Cn (Cn), U+0301 → Lo (Mn), U+FE0F → Lo (Default_Ignorable + Mn), U+00A0 → Lo
   (White_Space), U+E000 → Lo (Co), U+200B → Lo (Cf). It also patches
   `unicodedata.combining` to return 0 and `unidata_version` to 15.0.0. Then it asserts
   `ls Ᲊ` is accepted and `ls ͸`, `echo é́́`, `ls️ -la`,
   `ls\xa0-la`, `ls -la`, `ls​ -la` are all rejected (line 219-226).
   Default_Ignorable and White_Space aren't exposed by `unicodedata` at all, so faking the
   general category of a DI / White_Space code point is the closest a rewrite could come.
2. **U+1D159 MUSICAL SYMBOL NULL NOTEHEAD** (So, drawn blank) is now hidden. In
   `src/nl_shell/render.py:55-56` the iteration-1 constant `BRAILLE_PATTERN_BLANK` became
   `BLANK_SYMBOLS = ((0x2800, 0x2800), (0x1D159, 0x1D159))`, used in `_HIDDEN` at
   render.py:108. The module docstring (render.py:22-23) and the threat-model bullet
   (`.oss-scanner/threat_model.md:133-134`) name both. The test gets the vector the
   reviewer gave, `tests/test_charsafety.py:112`, so it runs in both the
   "rejected in a command" and "escaped in `:context`" parametrized tests. This is a named
   two-entry list of So symbols the brief already allowed one of (U+2800); the rest of the
   set is still property-based.

The 11 deferred findings in `deferred-findings.json` were left for the human, as the
carry-forward says.

## Whole change and why

1. **`scripts/gen_unicode_tables.py` (new).** Reads the UCD from `/usr/share/unicode/`
   (`unicode-data` 16.0.0) and writes `src/nl_shell/_unicode_tables.py`. It refuses to run
   if any file it reads is not version `--expect` (default `16.0.0`). Tables: CF, CO, CN,
   MARK (Mn+Me), DEFAULT_IGNORABLE, WHITE_SPACE, SCRIPT_EXTENSIONS (Zyyy/Zinh removed).
   Brief Scope (4).
2. **`src/nl_shell/_unicode_tables.py` (new, generated, committed).** 2137 lines,
   `UNICODE_VERSION = "16.0.0"` at line 10. Unchanged from iteration 1 (checked then
   against Python 3.14's `unicodedata` 16.0.0 code point for code point; a regen is
   byte-identical).
3. **`src/nl_shell/render.py`** — base lines 34-47 (#143's `is_hidden` with
   `unicodedata.category == "Cf"`) are replaced by one merged range table `_HIDDEN`
   (render.py:96-110). `is_hidden` is still the one predicate (render.py:127). No
   `unicodedata` import. New: `is_mark` / `too_many_marks` (render.py:137-149, Scope 2,
   `MAX_MARKS = 2` at :58), `scripts` / `mixed_script_word` (render.py:152-174, Scope 3,
   UTS #39 §5.1 augmentation in `AUGMENTED` at :115, word split at
   `string.whitespace + string.punctuation` at :122). `escape` (render.py:186) also escapes
   the 3rd and later mark in a row.
4. **`src/nl_shell/proposal.py:133-138`** — next to #143's hidden check (base
   `proposal.py:131-132`), the combining-mark and mixed-script rejections. They run on the
   whole `command`, so quoted text is covered (Scope 5).
5. **`.oss-scanner/threat_model.md:127-138`** — the "What the user confirms is exactly what
   runs" bullet names the policy and records that rejecting inside quotes is stricter than
   `docs/design/specs/policy-gate/v1.md:58-61`, which #12 may relax. Sudo bullets untouched;
   spec not edited.

## Choices and what I ruled out

- **All policy in `render.py`;** proposal.py only calls it. One place for the policy.
- **One merged table** (one bisect per character) instead of 6+ separate lookups.
- **#143's C0/C1/DEL ranges stay as code constants:** they are Cc, not a table the brief
  lists, and fixed by definition.
- **U+1D159 as a named constant, not a new table.** No Unicode property marks "drawn
  blank" for So symbols; the alternative of hiding all So would reject every emoji and
  symbol. Cost of the chosen fix: one tuple entry plus a rename (render.py:55-56, :108).
- **Known strictness (worth a human look):** intersection after augmentation rejects
  Latin+Han in one word, e.g. `file日本.txt`. UTS #39 "Highly Restrictive" would allow
  Latin+Jpan. The brief asks for the §5.1 intersection, so it's rejected. `日本/file.txt`
  passes because `/` splits words.

## Runs (project runners)

- `engine/scripts/run-verify.sh` (C4): `PDCA-EVIDENCE: C4 PASS — red without the fix (39 of
  45 failed), green with it`.
- `engine/scripts/run-suite.sh` (T3): `526 passed, 1 warning`; `PDCA-EVIDENCE: T3 PASS`.
  `tests/test_backend.py` is included.
- **Mutation check for the carry-forward.** I temporarily changed `is_mark` to
  `unicodedata.category(char) in ("Mn", "Me")` and moved Co out of `_HIDDEN` into an
  `unicodedata.category(char) == "Co"` check, then ran run-suite.sh: `1 failed, 525
  passed` — the one failure is `test_policy_reads_the_vendored_tables_not_unicodedata`.
  So the rewrite the reviewer described is now caught. The file was then restored (the
  diff was compared byte for byte against the bundle's `patch.diff`: unchanged).
- Formatter / hooks: the target has none configured (no `.pre-commit-config.yaml`, no
  ruff/black/flake8 in `pyproject.toml`). Every hand-written line is at or under 91
  characters, the existing maximum in `src/nl_shell/*.py`.

## Refuting my own test

- **(a) Genuine red?** Yes. run-verify.sh reverted the production hunks and re-ran: 39 of
  45 failed, 0 collection errors. The 6 that pass without the fix are the accept cases
  in (4) and "two marks accepted" in (2) — they guard against over-rejection and pass on
  #143's code too, as they should. U+1D159 is red on revert in both of its tests.
- **(b) Production path?** Yes. Every vector goes through `Repl.run` → `proposal.parse` →
  `render.has_hidden` / `too_many_marks` / `mixed_script_word` → `render.escape`. Only the
  model is replaced (the project's `RecordingStub`). The only other patch is to
  `unicodedata` in test (5), to show production does not read it — and the mutation run
  shows that test fails when production does read it.
- **(c) Fixture includes the fault?** Yes. Every character the iteration-3 reviews showed
  passing (U+3164, U+115F, U+1160, U+FFA0, U+034F, U+FE00, U+FE0F, U+E0100, U+17B4,
  U+180B, U+2800), the brief's U+00A0, U+3000, U+E000, U+0378, the reviewer's U+1D159, the
  three-mark stack and the three mixed-script words are all vectors.

## Housekeeping

- For the mutation run I copied `render.py` to `render.py.orig` inside the worktree and
  moved it back afterwards; nothing is left over. `git add -N` was used in the worktree so
  the new files appear in `git diff`.
- External dependency `unicode-data` was present (pdca.toml already has a doctor row). No
  NEEDS-HUMAN dependency.
- Not pushed; no PR opened.

# Build notes — #144 character-safety policy based on UTS #39 (iteration 4)

Base: the wave base `pdca-integration/main-r2546dbf9639f` @ `cefb359` (folds #143, #141,
#140). Worktree: `/home/eddie/nl-shell/nl-shell.pdca-wt-l1`. Line numbers are in the
patched tree unless marked "base".

## What this iteration changed

I started from the iteration-3 patch (`iteration-v3/patch.diff`, applies cleanly to
`cefb359`) and applied the four human decisions from the iteration-3 sign-off. I did not
re-open any of them.

1. **Blank-glyph policy, option (a).** U+13441 EGYPTIAN HIEROGLYPH FULL BLANK and
   U+13442 HALF BLANK (both Lo in UCD 16.0, neither Default_Ignorable nor White_Space)
   added to `BLANK_SYMBOLS` (`src/nl_shell/render.py:67-72`, comment at :64-66). Test
   vectors `egyptian-full-blank-u13441` / `-u13442` at `tests/test_charsafety.py:114-115`,
   so each runs in the "rejected in a command" test and the "escaped in `:context`"
   test. The quoted form `echo '<char>'` is what binds the rejection: there the glyph is a
   word on its own, so the mixed-script rule does not catch it.
   The wording is narrowed to say what the policy actually is — "the set the properties
   define, plus a short named list of known blank glyphs; a blank glyph on neither is not
   caught" — in the render.py docstring (:14-26) and the threat-model bullet
   (`.oss-scanner/threat_model.md:130-141`). I cannot edit `brief.md`'s Invariant line
   (Do reads the brief, Plan owns it); the human may want to narrow it there too.
2. **Look-alikes: a known gap, no §3.1 claim.** New entry under "Known gaps"
   (`.oss-scanner/threat_model.md:184-188`): `ｃurl`, `𝐜url`, `ⅽurl` pass; no §3.1,
   no confusable matching, no NFKC; left to #74's escaped confirm UI. The render.py
   docstring no longer says the policy "follows UTS #39"; it says so explicitly at
   render.py:37-39. No NFKC code was added.
3. **Mixed script relaxed to UTS #39 §5.2 "Highly Restrictive".**
   `HIGHLY_RESTRICTIVE` at render.py:139-143 (Latn+Hani+Hira+Kana, Latn+Hani+Bopo,
   Latn+Hani+Hang). `_highly_restrictive` at render.py:185-190: a word passes if the
   intersection of its characters' augmented script sets is non-empty (the old rule), or
   if for one allowed set every scripted character's set meets it. `mixed_script_word`
   (render.py:193-198) now calls it. Proposal docstring updated (`proposal.py:4-9`).
   Accepted vectors `cat iPhone用.txt` and `cat 2024年report.txt` at
   `tests/test_charsafety.py:185-186`. To keep the relaxation from being too loose I added
   two rejected vectors (test file :168-169): `cat файл用.txt` (Cyrillic+Han) and
   `cat 한국カタ.txt` (Hangul+Katakana — no allowed set holds both).
4. **Static check for `unicodedata`.** `test_policy_modules_never_use_unicodedata`
   (`tests/test_charsafety.py:200-208`) finds each of `nl_shell.render`,
   `nl_shell.proposal`, `nl_shell._unicode_tables` with `importlib.util.find_spec` and
   asserts the text `unicodedata` is not in its source. This catches
   `from unicodedata import category`, which the monkeypatch in test (5) cannot see. For
   it to hold, the render.py docstring no longer contains the word (it now says "the
   interpreter's own Unicode database", render.py:9-12). The generator script still names
   `unicodedata` in its docstring; it is not one of the three modules and is not shipped
   at runtime.

The deferred findings in `deferred-findings.json` were left for the human.

### Cost of the Highly Restrictive change

7 lines of code (the `HIGHLY_RESTRICTIVE` tuple and `_highly_restrictive`), replacing
the 10-line body of the old `mixed_script_word`. I considered computing the UTS #39
"resolved script set" over the whole word and comparing against the three sets as
supersets; the per-character "meets an allowed set" test gives the same verdict for
these three sets and is shorter. I ruled out the Identifier_Status=Allowed restriction,
as the human said.

## Whole change and why (carried over, still true)

1. **`scripts/gen_unicode_tables.py` (new).** Reads the UCD from `/usr/share/unicode/`
   (`unicode-data` 16.0.0), refuses to run if a file is not version `--expect` (default
   16.0.0), writes `src/nl_shell/_unicode_tables.py`: CF, CO, CN, MARK (Mn+Me),
   DEFAULT_IGNORABLE, WHITE_SPACE, SCRIPT_EXTENSIONS (Zyyy/Zinh removed). Scope (4).
   Unchanged this iteration.
2. **`src/nl_shell/_unicode_tables.py` (new, generated, committed).**
   `UNICODE_VERSION = "16.0.0"` at line 10. Unchanged.
3. **`src/nl_shell/render.py`** — base lines 34-47 (#143's `is_hidden` using
   `unicodedata.category == "Cf"`) are replaced by one merged range table `_HIDDEN`
   (render.py:112-126). `is_hidden` is still the one predicate. `is_mark` /
   `too_many_marks` (Scope 2, `MAX_MARKS = 2` at :74); `scripts` with the §5.1
   augmentation (`AUGMENTED` at :131); `escape` (:210) also escapes the 3rd and later mark
   in a row.
4. **`src/nl_shell/proposal.py:135-138`** — after #143's hidden check (base
   `proposal.py:131-132`), the combining-mark and mixed-script rejections, on the whole
   `command`, quoted or not (Scope 5).
5. **`.oss-scanner/threat_model.md`** — the "What the user confirms is exactly what runs"
   bullet (:127-141) names the policy and the quoted-text difference from
   `docs/design/specs/policy-gate/v1.md:58-61`, which #12 may relax. Sudo bullets
   untouched; spec not edited.
6. **`tests/test_charsafety.py` (new)** — the brief's (1)-(5), reviewer vectors from
   iterations 1-2, and this iteration's vectors and static check.

## Runs (project runners)

- `engine/scripts/run-verify.sh` (C4), with `PDCA_BUNDLE` set to this bundle:
  `PDCA-EVIDENCE: C4 PASS — red without the fix (50 of 58 failed), green with it`.
  0 collection errors on the red leg.
- `engine/scripts/run-suite.sh` (T3): `539 passed, 1 warning`;
  `PDCA-EVIDENCE: T3 PASS`. `tests/test_backend.py` is included.
- Mutation checks (one Python script that edited render.py, ran pytest on the test file
  under the venv with a timeout, and restored the file; `git diff` afterwards matched
  `patch.diff` byte for byte):
  - drop U+13441-13442 from `BLANK_SYMBOLS` → 4 failed (both Egyptian vectors, both tests);
  - make `_highly_restrictive` the old strict rule → 2 failed (`latin-and-han`,
    `digits-han-latin`);
  - make it accept every word → 7 failed (all MIXED vectors, including the two new ones);
  - add `from unicodedata import category` to render.py → 1 failed
    (`test_policy_modules_never_use_unicodedata`).
- Formatter / hooks: the target has none (no `.pre-commit-config.yaml`; no
  ruff/black/flake8 in `pyproject.toml` or the venv). `git diff --check` is clean.

## Refuting my own test

- **(a) Genuine red?** Yes. run-verify.sh reverted the production hunks and re-ran: 50 of
  58 failed. The 8 that pass on revert are the accept cases in (4), including the two new
  Latin+Han ones, and "two marks accepted" — they guard against over-rejection and are
  green on #143's code too. Each of this iteration's four changes was also reverted on
  its own (mutations above) and each one turned its tests red.
- **(b) Production path?** Yes. Every vector goes through `Repl.run` → `proposal.parse` →
  `render.has_hidden` / `too_many_marks` / `mixed_script_word` → `render.escape`; only the
  model is replaced (the project's `RecordingStub`). The static check reads the real
  module files that are imported.
- **(c) Fixture includes the fault?** Yes. Every character the reviews showed passing
  (U+3164 … U+2800, U+1D159, U+16FE4) and the two Egyptian blanks named at sign-off are
  vectors; so are the brief's U+00A0, U+3000, U+E000, U+0378, the three-mark stack, the
  mixed-script words, and the exact `from unicodedata import category` form the sign-off
  named.

## Housekeeping

- `git add -N` was used in the worktree so new files appear in `git diff`.
- External dependency `unicode-data` was present. No NEEDS-HUMAN dependency. The tables
  were not regenerated this iteration (no table change was needed).
- Not pushed; no PR opened.

# Build notes — #144 character-safety policy based on UTS #39 (iteration 5)

Base: the wave base `pdca-integration/main-r2546dbf9639f` @ `cefb359` (folds #143, #141,
#140). Worktree: `/home/eddie/nl-shell/nl-shell.pdca-wt-l0`. Line numbers are in the
patched tree unless marked "base".

## What this iteration changed

I applied the iteration-4 patch (`iteration-v4/patch.diff`, applies cleanly to
`cefb359`) and made only the two changes the iteration-4 sign-off asked for. Everything
else is byte-for-byte as in iteration 4. The round-3 decisions (named blank list,
same-script look-alikes left to #74, Highly Restrictive) are not re-opened.

1. **Quote bypass of the mixed-script rule — fixed.** `WORD_SEPARATORS` used to split at
   every character of `string.punctuation`, so `"с"url` became `с` and `url`, each
   single-script. Bash joins those pieces back into one word. New `WORD_JOINERS`
   (`src/nl_shell/render.py:149`: `"`, `'`, `\`, `$`, backtick) are taken out of the
   separator class (`render.py:150-157`). The quote characters themselves are Common, so
   they are ignored by the script check and the joined word `"с"url` is judged as
   Cyrillic+Latin → rejected. Comment at `render.py:147-148`; module docstring at
   `render.py:31-33` says the split excludes these and why. `mixed_script_word`
   (`render.py:204`) and the parser call (`src/nl_shell/proposal.py:137`) are unchanged.
   New rejected vectors in `MIXED` (`tests/test_charsafety.py:170-178`): the five from
   the sign-off (`"с"url example.com`, `с''url x`, `с\url x`, `ls /tmp/с""url`,
   `cat D""окумент.txt`) plus `с$''url x` (empty ANSI-C quote) and `` с``url x `` (empty
   command substitution), one for each joiner character.
   The threat-model claim "rejected anywhere in a `command`, quoted or not"
   (`.oss-scanner/threat_model.md:127-141`) now holds for all three rules: hidden
   characters and the mark limit always ran on the whole string; the mixed-script rule
   now treats quoted and unquoted text the same.
2. **Cross-script look-alikes allowed by Highly Restrictive — documented and tested.** The
   known-gap bullet (`.oss-scanner/threat_model.md:184-192`) now also names Latin mixed
   with Han/Hangul/Bopomofo look-alikes as allowed by design and left to #74: `curㅣ`
   (U+3163), `ech〇` (U+3007), `ls 一la` (U+4E00), `cat ㄧetc` (U+3127). I checked all four
   pass `has_hidden` and `mixed_script_word` on the patched code, so the bullet is
   accurate. The render.py docstring gap note (`render.py:39-42`) says the same in one
   line. Accepted vector `latin-and-hangul-i-look-alike`: `curㅣ example.com`
   (`tests/test_charsafety.py:196-198`). No rule change.

### Alternative considered for (1)

Stripping the joiners before splitting (`text.translate(...)` then the old regex) gives
the same verdicts, but the rejected word reported back would lose its quotes; keeping
them out of the separator class is a 6-line change to one constant and keeps
`mixed_script_word` returning the word as written. Either is fine; I took the one that
touches less.

### Residual, not fixed (for the human)

The sign-off named exactly five joiner characters, and I kept to that. Bash brace
expansion also builds words across `{`, `,`, `}`: `с{,}url x` expands to `сurl сurl x`,
and the policy accepts it, because `{`, `,`, `}` still split words. The text the user
sees (`с{,}url`) does not read as `curl`, so the look-alike risk is lower than for
`"с"url`. Adding `{ } ,` to `WORD_JOINERS` would close it, but `,` joining words would
start rejecting things like `ls Документы,files`. That is a policy call, so I left it.
Also, a quoted space (`ls "с url"`) is still split at the space; bash sees one argument
with a space, the user sees two separate words, each single-script — accepted, and I
think correctly so.

## Whole change and why (carried over from iteration 4, still true)

1. **`scripts/gen_unicode_tables.py` (new).** Reads the UCD from `/usr/share/unicode/`
   (`unicode-data` 16.0.0), refuses to run if a file is not version `--expect` (default
   16.0.0), writes `src/nl_shell/_unicode_tables.py`: CF, CO, CN, MARK (Mn+Me),
   DEFAULT_IGNORABLE, WHITE_SPACE, SCRIPT_EXTENSIONS (Zyyy/Zinh removed). Scope (4).
2. **`src/nl_shell/_unicode_tables.py` (new, generated, committed).**
   `UNICODE_VERSION = "16.0.0"` at line 10. Not regenerated this iteration.
3. **`src/nl_shell/render.py`** — base lines 34-47 (#143's `is_hidden` using
   `unicodedata.category == "Cf"`) are replaced by one merged range table `_HIDDEN`
   (`render.py:115`), built from #143's set, CF/CO/CN, Default_Ignorable, White_Space
   minus space/LF/TAB, and `BLANK_SYMBOLS` (`render.py:70`: U+2800, U+13441-13442,
   U+16FE4, U+1D159). `is_hidden` is still the one predicate. `is_mark` /
   `too_many_marks` (`MAX_MARKS = 2`, `render.py:77`); `scripts` with the §5.1
   augmentation; `HIGHLY_RESTRICTIVE` (`render.py:142`); `escape` (`render.py:221`) also
   escapes the 3rd and later mark in a row. No `unicodedata` anywhere in the module.
4. **`src/nl_shell/proposal.py:135-138`** — after #143's hidden check (base
   `proposal.py:131-132`), the combining-mark and mixed-script rejections, on the whole
   `command`, quoted or not (Scope 5).
5. **`.oss-scanner/threat_model.md`** — the "What the user confirms is exactly what runs"
   bullet (`:127-141`) names the policy, the named blank list, and the quoted-text
   difference from `docs/design/specs/policy-gate/v1.md:58-61`, which #12 may relax. Sudo
   bullets untouched; spec not edited. Known-gap bullet at `:184-192`.
6. **`tests/test_charsafety.py` (new)** — the brief's (1)-(5), reviewer vectors from
   iterations 1-4, the static `unicodedata` check, and this iteration's vectors.

The brief's Invariant line still says "no character that renders as nothing or as blank
reaches the user unmarked"; the threat model and docstring now say the narrower true
thing (property-defined set plus a named list). Plan owns `brief.md`, so I did not edit
it.

## Runs (project runners)

- `engine/scripts/run-suite.sh` on iteration-4 code + this iteration's tests (before the
  fix): `7 failed, 540 passed` — exactly the seven new joiner vectors; `curㅣ` already
  passed (expected, no rule change).
- `engine/scripts/run-verify.sh` (C4), `PDCA_BUNDLE` = this bundle, after the fix:
  `PDCA-EVIDENCE: C4 PASS — red without the fix (57 of 66 failed), green with it`;
  0 collection errors on the red leg. `git diff` of the worktree matches `patch.diff`
  byte for byte after the gate restored it.
- `engine/scripts/run-suite.sh` (T3) after the fix: `547 passed, 1 warning`;
  `PDCA-EVIDENCE: T3 PASS`. `tests/test_backend.py` is included.
- Formatter / hooks: the target has none (no `.pre-commit-config.yaml`; no
  ruff/black/flake8 configured). `git diff --check` is clean. Changed lines stay within
  the base file's longest line (91 chars).

## Refuting my own test

- **(a) Genuine red?** Yes. With the whole production change reverted (C4 red leg), 57 of
  66 fail. The 9 that still pass are the accept cases in (4) (now including `curㅣ`) and
  "two marks accepted" — they guard against over-rejection and are green on #143's code
  too. For this iteration's fix on its own: with only the old `WORD_SEPARATORS` (the
  iteration-4 code), the 7 new joiner vectors fail and nothing else does.
- **(b) Production path?** Yes. Each vector goes through `Repl.run` → `proposal.parse` →
  `render.has_hidden` / `too_many_marks` / `mixed_script_word` → `render.escape`; only the
  model is replaced (the project's `RecordingStub`). Each command is sent both as
  `\u`-escaped JSON and as raw UTF-8 JSON.
- **(c) Fixture includes the fault?** Yes. The five exact bypass strings from the sign-off
  are vectors, plus one each for `$` and backtick; the documented look-alike `curㅣ` is an
  accepted vector, so the threat-model statement is pinned by a test.

## Housekeeping

- `git add -N` was used in the worktree so new files appear in `git diff`.
- External dependency `unicode-data` was present; tables not regenerated (no table
  change needed). No NEEDS-HUMAN dependency.
- Not pushed; no PR opened.

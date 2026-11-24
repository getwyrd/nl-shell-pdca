# Build notes — #144 character-safety policy based on UTS #39 (iteration 3)

Base: the wave base `pdca-integration/main-r2546dbf9639f` @ `cefb359` (folds #143, #141,
#140). Worktree: `/home/eddie/nl-shell/nl-shell.pdca-wt-l1`. Line numbers are in the
patched tree unless marked "base".

## What this iteration changed

I started from the iteration-2 patch (`iteration-v2/patch.diff`, applies cleanly to
`cefb359`) and fixed the two items in the iteration-2 carry-forward. The rest of the
design is unchanged; its rationale is repeated below so this file stands alone.

1. **U+16FE4 KHITAN SMALL SCRIPT FILLER** (Mn, script Kits, neither Default_Ignorable
   nor White_Space in UCD 16.0) is now hidden. `src/nl_shell/render.py:56-58`:
   `BLANK_SYMBOLS = ((0x2800, 0x2800), (0x16FE4, 0x16FE4), (0x1D159, 0x1D159))`, with the
   comment changed to say these are characters drawn blank that no Unicode property
   flags (the new one is Mn, not So). Module docstring updated at render.py:22-24. The
   threat-model bullet names it (`.oss-scanner/threat_model.md:133-134`). Test vector
   `"khitan-filler-u16fe4"` at `tests/test_charsafety.py:113`, so it runs in both the
   "rejected in a command" test (including the quoted `echo '…'` form, where the filler
   is a word on its own and would pass the mixed-script check) and the "escaped in
   `:context`" test. The reviewer's exact input now holds:
   `render.has_hidden("ls /tmp/\U00016fe4")` is `True` and `escape` prints
   `ls /tmp/\U00016fe4`.
2. **Common character inside a mixed word.** `tests/test_charsafety.py:162-164` adds
   `"cyrillic-es-hyphen-latin": "echo с‐url"` and
   `"cyrillic-es-middle-dot-latin": "echo с·url"` to `MIXED`.
   Mutation check (in a Python one-liner, not by editing files): a version of
   `mixed_script_word` that resets the running intersection on a character with no
   script lets `echo с‐url` through, so the hyphen vector catches that regression.
   The middle-dot vector does **not** catch that particular mutation: in UCD 16.0
   U+00B7 has its own Script_Extensions list (Avst, Cari, Copt, Dupl, Elba, Geor, Glag,
   Gong, Goth, Grek, Hani, Latn, Lydi, Mahj, Perm, Shaw), so it is not "no script". It
   still guards a different mistake (treating non-ASCII punctuation as a word break),
   and the reviewer asked for it, so I kept it.

The 10 deferred findings in `deferred-findings.json` were left for the human, as the
carry-forward says.

Cost of fix 1: one tuple entry, a comment and a docstring line. This keeps the named
list at three code points next to a property-based set. No Unicode property marks
"drawn blank" for these; hiding all So or all Mn would reject every emoji and every
accent, which the brief's accept cases (4) forbid.

## Whole change and why

1. **`scripts/gen_unicode_tables.py` (new).** Reads the UCD from `/usr/share/unicode/`
   (`unicode-data` 16.0.0) and writes `src/nl_shell/_unicode_tables.py`. Refuses to run
   if any file it reads is not version `--expect` (default `16.0.0`). Tables: CF, CO, CN,
   MARK (Mn+Me), DEFAULT_IGNORABLE, WHITE_SPACE, SCRIPT_EXTENSIONS (Zyyy/Zinh removed).
   Brief Scope (4).
2. **`src/nl_shell/_unicode_tables.py` (new, generated, committed).**
   `UNICODE_VERSION = "16.0.0"` at line 10. Unchanged since iteration 1.
3. **`src/nl_shell/render.py`** — base lines 34-47 (#143's `is_hidden` using
   `unicodedata.category == "Cf"`) are replaced by one merged range table `_HIDDEN`
   (render.py:98-112, `BLANK_SYMBOLS` at :58). `is_hidden` is still the one predicate. No `unicodedata` import.
   New: `is_mark` / `too_many_marks` (Scope 2, `MAX_MARKS = 2` at render.py:60),
   `scripts` / `mixed_script_word` (Scope 3, UTS #39 §5.1 augmentation in `AUGMENTED`,
   word split at `string.whitespace + string.punctuation`). `escape` also escapes the 3rd
   and later mark in a row.
4. **`src/nl_shell/proposal.py:135-138`** — right after #143's hidden check
   (`proposal.py:133-134`; base `proposal.py:131-132`), the combining-mark and mixed-script rejections. They run on the
   whole `command`, so quoted text is covered (Scope 5).
5. **`.oss-scanner/threat_model.md:127-138`** — the "What the user confirms is exactly what
   runs" bullet names the policy and records that rejecting inside quotes is stricter than
   `docs/design/specs/policy-gate/v1.md:58-61`, which #12 may relax. Sudo bullets
   untouched; spec not edited.
6. **`tests/test_charsafety.py` (new)** — the brief's (1)-(5), plus the reviewer vectors
   from iterations 1 and 2. Test (5) fakes the interpreter's `unicodedata` on every
   property the policy uses and asserts the verdicts don't change.

## Choices and what I ruled out

- **All policy in `render.py`;** proposal.py only calls it. One place for the policy.
- **One merged table** (one bisect per character) instead of 6+ separate lookups.
- **#143's C0/C1/DEL ranges stay as code constants:** they are Cc, fixed by definition.
- **Known strictness (worth a human look):** intersection after augmentation rejects
  Latin+Han in one word, e.g. `file日本.txt`. UTS #39 "Highly Restrictive" would allow
  Latin+Jpan. The brief asks for the §5.1 intersection, so it's rejected. `日本/file.txt`
  passes because `/` splits words.

## Runs (project runners)

- `engine/scripts/run-verify.sh` (C4): `PDCA-EVIDENCE: C4 PASS — red without the fix (43 of
  49 failed), green with it`. All four new test cases are among the 43 red ones.
- `engine/scripts/run-suite.sh` (T3): `530 passed, 1 warning`; `PDCA-EVIDENCE: T3 PASS`.
  `tests/test_backend.py` is included.
- After those runs I only re-wrapped lines in the threat-model bullet (Markdown text,
  no code), so the results still apply.
- Formatter / hooks: the target has none configured (no `.pre-commit-config.yaml`, no
  ruff/black/flake8 in `pyproject.toml`). Every hand-written line is at or under 91
  characters, the existing maximum in `src/nl_shell/*.py` and in the threat model.

## Refuting my own test

- **(a) Genuine red?** Yes. run-verify.sh reverted the production hunks and re-ran: 43 of
  49 failed, 0 collection errors. The 6 that pass without the fix are the accept cases
  in (4) and "two marks accepted" in (2); they guard against over-rejection and pass on
  #143's code too, as they should. U+16FE4 is red on revert in both its tests, and both
  new mixed-script vectors are red on revert.
- **(b) Production path?** Yes. Every vector goes through `Repl.run` → `proposal.parse` →
  `render.has_hidden` / `too_many_marks` / `mixed_script_word` → `render.escape`. Only the
  model is replaced (the project's `RecordingStub`). Test (5) also patches `unicodedata`
  to show production does not read it.
- **(c) Fixture includes the fault?** Yes. Every character the reviews showed passing
  (U+3164, U+115F, U+1160, U+FFA0, U+034F, U+FE00, U+FE0F, U+E0100, U+17B4, U+180B,
  U+2800, U+1D159, U+16FE4), the brief's U+00A0, U+3000, U+E000, U+0378, the three-mark
  stack, and the mixed-script words (including the two with a Common character inside)
  are all vectors.

## Housekeeping

- `git add -N` was used in the worktree so new files appear in `git diff`.
- External dependency `unicode-data` was present (pdca.toml already has a doctor row). No
  NEEDS-HUMAN dependency.
- Not pushed; no PR opened.

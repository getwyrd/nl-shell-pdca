# Adversarial review — issue 144 / charsafety-uts39-policy

I tried to break the evidence, the tables, the predicate, the mark cap and the threat-model text. The production change held up. The one real finding is in the test file.

## Refutation attempts

- **Evidence (C4), could not refute.** `gate-logs/C4-verify.log` shows the production change reverted on the wave base: 65 of 72 failed, 7 passed, 0 collection errors. The 7 that pass while red are the ones that should: the five accept rows in (3) and the two "two marks accepted" rows. Every reject and escape row goes through the real `Repl` → `proposal.parse` → `render.escape` path (`tests/test_charsafety.py` `session()` / `assert_rejected`), with both `ensure_ascii` encodings. Nothing is mocked away. I could not re-run pytest here (no `pytest` module on this host's `python3`), so for green I rely on the frozen T3 log (553 passed).
- **Tables, could not refute.** I compared `src/nl_shell/_unicode_tables.py` CF/CO/CN/MARK with Python 3.14.4's `unicodedata` (16.0.0) over all 0x110000 code points: zero differences. `scripts/gen_unicode_tables.py:126` `generate()` run on this host's `/usr/share/unicode` (header `# DerivedCoreProperties-16.0.0.txt`) gives a module byte-identical to the committed one.
- **Predicate, could not refute.** `src/nl_shell/render.py:113-127` (`_HIDDEN`) flags all 19 brief vectors and also U+00AD, U+0085, U+1680, U+200B and U+2062. U+1C89 is not flagged. One predicate serves both rejection (`proposal.py:133`) and escaping (`render.py:175`), as the brief requires.
- **Mark cap, could not refute.** `render.py:146-156` resets the run on any non-Mn/Me character, so it covers runs after a letter, at the start and after LF. A hidden character between marks (ZWJ, CGJ) is rejected by `has_hidden` first. Mc (spacing marks) is not counted, which is what the brief says (Mn/Me only). `escape` runs over the whole formatted reply (`repl.py:124`), but the template text around the command is ASCII, so no run can join across it.
- **Display paths, could not refute.** The only prints in `src/nl_shell` are `repl.py:124` and `cli.py:70`, and both go through `render.escape`. So the threat-model claim "every display path escapes" (`.oss-scanner/threat_model.md:136-137`) holds on this base.
- NEEDS-HUMAN [impl] — `tests/test_charsafety.py:6-8`: the docstring says "Every non-ASCII character in this file is written as a Python escape, never pasted, so the source shows exactly what it tests." That is false. Lines 34, 120-138, 192-195, 228, 236, 237 and 239 hold the raw characters. These include invisible ones: U+0301 as `ACUTE`, U+3164, U+115F, U+FE0F, U+00A0, U+3000, U+E000 and unassigned U+0378. Concrete failure: an editor or formatter that changes NBSP or U+3000 to a space, or drops a variation selector, turns a reject row into `ls -la` or `ls  -la`. That row then fails for the wrong reason, or the `faked` dict at :228 stops keying on the intended code point, and the source looks the same in review. Rewrite these literals as `"ㅤ"`, `"\U00013441"` and so on (the escaped-expected column and `"\\u0301"` at the third-mark test already do this).
- `.oss-scanner/threat_model.md:188-189` (added known-gap bullet): "the user's own reading of the confirm prompt is the only check". This base has no confirm prompt. Proposals print "Nothing runs yet", and the brief says #74's confirm UI is not on this base. The statement is harmless today, because nothing runs, but the wording names a check that does not exist yet. Minor wording nit, not a §6 item. (The older "(#74)" claim at :128-129 predates this diff.)
- `check-gates.json` T2 row: "no security-relevant path touched", although the diff changes `src/nl_shell/render.py` and `proposal.py`, the character-safety policy. The threat model was updated anyway, so there is no harm in this round. But the T2 gate's path list does not treat these files as security-relevant, so a future change to them would pass T2 without a threat-model touch. That is gate configuration, not this diff, so it is noted only.

## Housekeeping

My table check imported `nl_shell` from `$PDCA_TARGET`, and that wrote `__pycache__` files into `target/scripts/` and `target/src/nl_shell/` (timestamps 03:25:05). They are bytecode caches only, not part of the patch, and the harness disposes of the target copy.

## Verdict

I tried to refute the red→green proof, the 16.0.0 tables, the hidden set, the mark cap (start, after LF, broken by hidden or Mc characters), the escape paths and the generator's regeneration, and could not. The one item to send back is the pasted invisible characters in the test file, together with its false docstring claim.

<!-- pdca:leaf-complete -->

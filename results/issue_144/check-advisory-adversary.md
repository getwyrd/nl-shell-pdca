# Adversarial review — issue 144 / charsafety-uts39-policy (iteration 7)

**Result: I could not refute the fix.** I tried to break the evidence, the tables, the
generator, the parser rejection and the escape path. Nothing failed. pytest is not
installed in this sandbox, so I did not re-run the suite. I checked the frozen gate logs
instead, and imported the patched modules under Python 3.14.4 (whose `unicodedata` is
16.0.0) to probe them directly. None of the findings below is NEEDS-HUMAN.

## What I attacked, and what held

- **The red→green evidence is real and runs the production code.** `gate-logs/C4-verify.log`
  shows 73/73 green, and 65 of 73 red with the production change reverted. The 8 that stay
  green in the red leg are the ones that should: `test_this_file_is_ascii`, the 5
  accepted-command rows and the two "two marks accepted" rows
  (`tests/test_charsafety.py:37`, `:174`, `:182`, `:209`). Every reject and escape row goes
  through the real `Repl` → `proposal.parse` → `render.escape`
  (`tests/test_charsafety.py:96-121`). It checks the exact output against a pinned
  `NO_USABLE` / `DF_SHOWN`, so it cannot pass by accident. Each row runs with both
  `ensure_ascii` settings, and a second request follows, so a crash or a stuck REPL would
  also fail.
- **The round-3 carry-forward is fixed.** `tests/test_charsafety.py` decodes as pure ASCII
  (grep for non-ASCII bytes finds nothing). `test_this_file_is_ascii`
  (`tests/test_charsafety.py:37-41`) now enforces the docstring's promise at `:6-8`.
- **The vendored tables are right.** I compared each table at `src/nl_shell/_unicode_tables.py:13`,
  `:39`, `:47` and `:783` (CF, CO, CN, MARK) with Python 3.14's `unicodedata` 16.0.0 over
  every code point. They match exactly (170 / 137468 / 819533 / 2033 code points).
  `gen_unicode_tables.generate(/usr/share/unicode, "16.0.0")` gives byte-for-byte the
  committed module.
- **Edge inputs I tried against `proposal.parse` and `render.escape`, all handled as the
  brief says:** NBSP inside quotes; three marks at the start, after a letter and after LF;
  Me marks (U+20DD, U+0489); U+2063; U+E01EF; noncharacters U+FDD0 / U+FFFF / U+10FFFF;
  U+0085; U+001C; U+00AD; U+2003; U+115F+U+1160; a ZWJ between marks; and runs of 3 Thai,
  Kana and U+1ABE marks. All are rejected, and on display only the 3rd and later marks
  are escaped (`e` + 5×U+0301 → `é́́́́`).
- **Every display path goes through the one escape function.** The only callers are
  `src/nl_shell/repl.py:124`, `src/nl_shell/prompts.py:219` and `src/nl_shell/cli.py:70`.
  Each escapes the whole string in one call, so a mark run can't be split across separately
  escaped pieces. There is one predicate (`src/nl_shell/render.py:131-133`), used both by
  the rejection (`src/nl_shell/proposal.py:133-136`) and by `escape`
  (`src/nl_shell/render.py:175`).
- **There is no `unicodedata` left in the policy.** `render.py` no longer imports it, and
  the static check at `tests/test_charsafety.py:222-227` also catches a
  `from unicodedata import …`.

## Observations (not refutations, no action needed to accept)

- `src/nl_shell/render.py:175` / `tests/test_charsafety.py:190-193`: the escape test only
  covers the 3rd mark. If `run > MAX_MARKS` were changed to `run == MAX_MARKS + 1`, the 4th
  and later marks would print raw and no test would fail. The current code is correct (I
  checked 5 marks by hand). Adding a 4-mark row would pin it down. This is a nice-to-have,
  not a defect.
- `scripts/gen_unicode_tables.py:33` checks the version only on
  `DerivedCoreProperties.txt` and `PropList.txt`, because `UnicodeData.txt` has no header.
  A mixed install (an older UnicodeData next to 16.0.0 property files) would get past the
  version check and produce wrong CF/CN/MARK tables. Test (5) catches that only on a host
  that has the right files. The brief's wording ("version header") is still met, so this
  is outside the slice.
- The 2-mark cap is the brief's own rule (round-3/4 sign-off), and it has a known cost.
  Fully pointed Hebrew such as U+05D1 U+05BC U+05B8 U+0591 (bet + dagesh + qamats + a
  cantillation mark) is three Mn in a row, so `too_many_marks` rejects it. A spacing mark
  (Mc, e.g. U+0903) between marks ends the run, also as the brief says. Both are policy
  choices already made, not bugs in this diff.
- `gate-logs/T2-threat-model.log`: the T2 gate printed "no security-relevant path touched",
  even though this diff changes `render.py` and `proposal.py`. That is a gap in the gate's
  path list, not in this patch: the threat model *is* updated
  (`.oss-scanner/threat_model.md:130-140`, `:183-189`), as the brief's Scope (4) asks.
  The edits don't cite #74 as a defence, and they don't claim confusable or mixed-script
  detection.

<!-- pdca:leaf-complete -->

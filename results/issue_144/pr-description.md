## Summary
**User impact:** a command the model proposes could contain characters that print as
nothing or as a plain blank. The user saw `ls` at the confirm step, but bash received
`ls` plus an invisible letter, so what ran was not what they read and approved. Piles
of accent marks stacked on one letter could also draw over the characters next to it.

This PR widens the hidden-character check so those commands are refused, and shows the
same characters as visible escapes (like `ㅤ`) everywhere nl-shell prints text.

Reported in [#144](https://github.com/eduralph/nl-shell/issues/144).

This stacks on #153 (the proposal parser and its first hidden-character check) and
should be merged after it.

## What to look at
The heart of the change is one rule, "which characters count as hidden", now defined by
Unicode's own properties instead of a short hand-made list, plus a limit of two
combining marks in a row. The same rule decides both what gets rejected and what gets
escaped on screen, so the two cannot disagree.

To try it, feed the parser a command ending in U+3164 (HANGUL FILLER, which renders as
blank):

```
python3 -c 'import json; from nl_shell import proposal; print(proposal.parse(json.dumps({"kind":"command","command":"lsㅤ","risk":"read-only"})))'
```

Before this PR it returns a `Command`; after it, it is rejected. Normal non-Latin text
such as `ls Документы` or `cat 日本語ファイル.txt` is still accepted and shown as is.

What this PR does **not** do: it does not catch look-alike letters (`ｃurl`, `сurl` with
a Cyrillic `с`). The threat model now lists that as a known gap. Rejecting words that
mix scripts needs the real bash word boundaries, so it moves to the parser-based policy
gate in #12.

## Root cause
The check from #153 covered controls, bidi controls, format characters (Cf), line and
paragraph separators, the tag block and surrogates. Characters such as U+3164, U+115F,
U+FFA0, variation selectors (U+FE00–U+FE0F, U+E0100), U+034F, U+2800, no-break spaces,
private-use and unassigned code points fall outside those groups, and there was no limit
on combining marks.

## Fix
- `src/nl_shell/render.py`: the hidden set is now the union of the old set with every
  Default_Ignorable_Code_Point, every White_Space character except space/LF/TAB, general
  categories Co and Cn, and a named list of blank glyphs (U+2800, U+1D159, U+16FE4,
  U+13441, U+13442), following UTS #39 §3.1. A new mark-run counter caps runs of Mn/Me
  at two (UTS #39 §5.4), whatever comes before the run. `is_hidden`, `has_hidden`,
  `escape_char` and `escape` keep their names and signatures, so no caller changes.
- `src/nl_shell/proposal.py`: rejects a command with too many marks, next to the
  existing hidden-character rejection.
- `src/nl_shell/_unicode_tables.py` (new, generated): Unicode 16.0.0 ranges for Cf, Co,
  Cn, Mn/Me, Default_Ignorable_Code_Point and White_Space. The policy reads only these
  and never imports `unicodedata`, because Python 3.12/3.13 ship older Unicode data and
  the result would depend on the interpreter.
- `scripts/gen_unicode_tables.py` (new): rebuilds that module from the UCD (Unicode
  Character Database) files in `/usr/share/unicode/` (Ubuntu package `unicode-data`) and
  refuses to run unless they are version 16.0.0.
- `.oss-scanner/threat_model.md`: describes the policy under "What the user confirms is
  exactly what runs", including that rejecting quoted text is stricter than the
  policy-gate spec's "outside quotes" rule (a superset of it, so the spec is unchanged),
  and adds a known-gap entry for look-alike and mixed-script words.

No new runtime dependency; `requires-python` is unchanged.

## Verification
- **Claim:** every listed blank/invisible character in a proposed command is rejected,
  quoted or not, and is escaped in `:context`.
  **Checked:** `src/nl_shell/render.py:113-138` (one hidden table and predicate),
  `src/nl_shell/proposal.py:133-134` (rejection on the raw command string, before any
  parsing). **Test:** `tests/test_charsafety.py:126-166` — 19 code points, each sent
  unquoted, single-quoted and double-quoted, as escaped and as raw JSON.
- **Claim:** more than two combining marks in a row are rejected, whether they follow a
  letter, start the command or follow a line feed; on display only the 3rd and later
  marks are escaped.
  **Checked:** `src/nl_shell/render.py:141-179` (`_mark_runs` is shared by
  `too_many_marks` and `escape`), `src/nl_shell/proposal.py:135-136`.
  **Test:** `tests/test_charsafety.py:170-196`.
- **Claim:** ordinary non-Latin and accented text is not affected.
  **Test:** `tests/test_charsafety.py:198-213` (Cyrillic, Greek, Japanese, precomposed
  `é` and `e` + one U+0301 are accepted and shown byte for byte).
- **Claim:** the policy uses only the vendored 16.0.0 tables, never `unicodedata`.
  **Checked:** `src/nl_shell/render.py:44-47` (imports), `src/nl_shell/_unicode_tables.py:9`
  (`UNICODE_VERSION = "16.0.0"`). **Test:** `tests/test_charsafety.py:216-264` — a
  source check for `unicodedata`, and a run with `unicodedata` faked to give wrong
  answers (U+0378 → `Lu`, U+1C89 → `Cn`, U+0301 → `Lo`, U+3164 → `Lo`) that still
  gives the right results.
- **Claim:** the committed tables match the generator.
  **Checked:** `scripts/gen_unicode_tables.py:69-80` (version check), `:127` (`generate`).
  **Test:** `tests/test_charsafety.py:267-277` — regenerates and compares byte for byte;
  skips with the reason when `/usr/share/unicode/` is missing or not 16.0.0 (for
  example Ubuntu 24.04's 15.1.0 on `ubuntu-latest` CI). The tables were also compared
  code point by code point against Python 3.14's `unicodedata` (Unicode 16.0.0): no
  differences.
- **Red/green:** with the `src/` and `scripts/` changes reverted and the new test file
  kept, 65 of 73 tests in `tests/test_charsafety.py` fail; with them, all pass. The 8
  that pass either way are the "still accepted" rows and a check that the test file
  itself is pure ASCII (every test character is written as an escape, so an editor
  cannot silently swap one). Full suite: 554 passed, including `tests/test_backend.py`.

Known trade-offs, chosen on purpose: up to two stacked marks are still allowed, so fully
pointed Hebrew with three marks on one letter is rejected; a blank-looking glyph that is
in neither the property set nor the named list (for example U+FFFC) is not caught, as
the threat model states.

Fixes #144

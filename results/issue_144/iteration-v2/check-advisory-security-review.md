# Security review (advisory) — #144 charsafety-uts39-policy

**Attacker-reachable inputs this diff touches:** the model's proposal `command` (threat model "Where untrusted input enters" item 5, steerable by the text-only attacker through items 1–2), and request / `:context` text shown through `render.escape` (display path for item 1–2 text). The generator script `scripts/gen_unicode_tables.py` reads only the local UCD files at build time (trusted); it has no `exec`/`eval`/subprocess.

Rubric: `.oss-scanner/threat_model.md` (read in full). Relevant must-hold: "What the user confirms is exactly what runs" (`.oss-scanner/threat_model.md:127-138`, updated by this patch to describe the policy).

## What I checked (no finding)

- **Tables match the brief and the runtime.** On Python 3.14.4 (`unicodedata` 16.0.0) I swept all 0x110000 code points: `render.is_mark` matches `category in (Mn, Me)` exactly, and every Cn code point (noncharacters U+FFFE, U+FDD0, U+10FFFF, the DI-reserved U+E01F0.. range included) is hidden. Zero mismatches.
- **Hidden set** (`src/nl_shell/render.py:96-110`): U+115F/1160/3164/FFA0, U+2800, U+1D159, U+1680, U+180E, U+200D, U+2062, U+1BCA0, CR/VT/FF/NEL are all hidden. LF/TAB/SPACE are the only whitespace left visible. The iteration-1 U+1D159 finding is fixed (`render.py:56`) and has a test (`tests/test_charsafety.py:112`).
- **Mixed-script check** (`render.py:163-174`, called at `src/nl_shell/proposal.py:137-138`): Common characters inside a word do not hide mixing. `echo с‐url` (U+2010), `echo с·url`, `rm -rf /еtc`, `curl exаmple.com`, `ls a١` and `ls abـc` (Arabic tatweel, whose Script_Extensions has no Latin) are all rejected. Single-script and UTS #39 combinations pass as the brief asks: `ls 中国한국`, `cat 日本語ファイル.txt`, `ls Ᲊ` (U+1C89).
- **Mark cap** (`render.py:142-149`, `proposal.py:135-136`): `x` + U+0300 U+0301 U+0302 is rejected, two marks are accepted. `escape` escapes the 3rd and later marks, and a backslash in between resets the run correctly (`'a\\' + 3×U+0301` → `a\\\\́́́`).
- **Resource use:** the `command` is capped at 2000 characters by the schema (`proposal.py:26`). The checks are linear scans plus a bisect per character, and the separator regex is a single character class with `+`, so it can't backtrack badly. No hang or blow-up from crafted input.
- **Test (5) from the carry-forward:** it now fakes `unicodedata` for Cn, Mn (U+0301), Default_Ignorable (U+FE0F), White_Space (U+00A0), Co and Cf (`tests/test_charsafety.py:194-225`), so a regression to `unicodedata` would turn the test red. The iteration-1 [impl] finding is addressed.
- **Gates:** C4 is red before the fix (39 of 45 failed) and green after. T3 is green (526 passed).

## Findings

- NEEDS-HUMAN [human] — **Low** (deception on the confirm path; the bytes still match, so this is not a Critical "what runs differs") — `src/nl_shell/render.py:152-174` / `src/nl_shell/proposal.py:137`. **Input:** a proposal `command` from the model, which a text-only attacker can steer. **What goes wrong:** the mixed-script check looks only at Script_Extensions. So look-alike *compatibility* letters pass. Fullwidth Latin is script Latn, so it mixes freely with ASCII. Mathematical alphanumerics are script Common, so the check ignores them. Each of these is a different word to bash than the one it looks like. **Reproducer** (run through `proposal._parse`, this build): `ｃurl example.com` (U+FF43 + ASCII) → accepted. `c𝐮rl example.com` (U+1D42E) → accepted. `ls Ⅰ` (U+2160 ROMAN NUMERAL ONE) → accepted. Compare `сurl example.com` → rejected. UTS #39 §3.1 (General Security Profile, Identifier_Status=Restricted / Identifier_Type=Not_NFKC), which the brief cites, would exclude these. The brief's Scope implements only the hidden set, the mark cap and §5.1, and puts confusables out of scope, with #74's non-ASCII escaping in the confirm UI as the backstop. The human should decide one of two things. Either a cheap `unicodedata`-free "word ≠ its NFKC form → reject" rule belongs in this slice (it would need an NFKC or Identifier_Status table vendored the same way). Or record this as a known gap until #74 lands. It is not an implementation defect against the brief as written.

- NEEDS-HUMAN [impl] — **Low** (test only covers the easy case) — `tests/test_charsafety.py:156-166`. The mixed-script vectors all put two scripts side by side with nothing between them. No test checks that a Common or Inherited character *inside* a word does not hide the mix. A regression that, for example, treated any Common character as a word break, or reset `common` on an ignored character, would let `echo с‐url` (U+2010 HYPHEN, a Common, non-ASCII character) or `echo с·url` through, and every current test would still pass. Today the code rejects both (checked above). **Fix:** add `"cyrillic-es-hyphen-latin": "echo с‐url"` and one with U+00B7 to `MIXED`.

## Not a finding (noted for the record)

- The T2 gate log says "no security-relevant path touched" (`gate-logs/T2-threat-model.log`), but the patch changes the proposal parser and the render filter. The patch updates the threat model anyway (`.oss-scanner/threat_model.md:130-138`), so nothing is missing here. The gate's path list may be too narrow; that belongs to the harness, not this diff.
- Combining marks right after an escaped hidden character (`"\x01" + 2×U+0301` → `\x01́́`) stack on the last character of the escape text in `:context`. The proposal is rejected anyway, and the escape text stays readable, so I'm not filing this.

<!-- pdca:leaf-complete -->

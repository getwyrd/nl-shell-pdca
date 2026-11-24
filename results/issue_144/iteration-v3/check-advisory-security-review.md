# Security review (advisory) — #144 charsafety-uts39-policy

Attacker-reachable inputs this diff touches: **the model's proposal `command`** (threat model "Where untrusted input enters" item 5, which can carry text steered by the text-only attacker, items 1–2) through `proposal._parse` → `render.has_hidden` / `too_many_marks` / `mixed_script_word` (`src/nl_shell/proposal.py:133-138`); and **text printed through `render.escape`** (proposal display, `:context`, errors; `src/nl_shell/render.py:188-201`). The property broken if this fails is the must-hold "What the user confirms is exactly what runs" (`.oss-scanner/threat_model.md:127-138`), rated Critical if a confirm shows something other than what runs.

**No finding at any severity.** What I checked:

- **The vendored tables match the UCD.** I regenerated `src/nl_shell/_unicode_tables.py` from `/usr/share/unicode` (16.0.0) with `scripts/gen_unicode_tables.py --output <scratch>`. The output is byte-identical to the committed module (`cmp` reports no difference), so the tables carry no hand edits and no widened gaps.
- **Hidden set (`src/nl_shell/render.py:98-112`).** I ran the usual "invisible character" list through `render.is_hidden` and every one is flagged: U+00AD, U+034F, U+061C, U+115F, U+1160, U+17B4, U+17B5, U+180E, U+2000–U+200F, U+202F, U+205F, U+2060–U+2064, U+206A–U+206F, U+3000, U+2800, U+3164, U+FEFF, U+FFA0, U+1D159, U+1D173–U+1D17A, U+16FE4 and U+1680. The fillers from earlier rounds (U+1D159, U+16FE4) are in `BLANK_SYMBOLS` (`render.py:58`) and are tested (`tests/test_charsafety.py`, `HIDDEN`).
- **Combining-mark cap (`render.py:144-151`, `:193-198`).** `e`+3×U+0301 is rejected, and `escape` gives `é́́`. `e`+2×U+0301 is accepted. The counter in the parser and in `escape` is the same Mn/Me run, so what gets rejected matches what gets escaped. A spacing mark (Mc) breaks the run, but it draws its own visible glyph, so no stacking hides behind it.
- **Mixed script (`render.py:165-176`).** `сurl x` is rejected. So are a Common or Inherited character inside the word (`с‐url`, `с·url`, both tested) and `cat aあ`. `cat 日本語ファイル.txt` and `ls Ᲊ` are accepted, as the brief requires. Words split only at ASCII whitespace and punctuation, and the ASCII separator is shown as itself, so splitting cannot hide anything.
- **Quoted text.** Rejection applies to the whole `command` string, quoted or not (tested with `echo '<char>'`). That is stricter than policy-gate v1, and the threat model now records the difference.
- **Resource use.** Each lookup is a binary search over prebuilt ranges, and the word split is one linear regex. Command length is already capped (`proposal.py:131`). No input can make this slow out of proportion to its size.
- **Tests cover the attacker cases, not just the easy ones.** Test (5) fakes `unicodedata` to disagree on Cn, Mn, Default_Ignorable, White_Space, Co and Cf. That closes the round-1 gap: a rewrite back to `unicodedata` would now fail. Both earlier-round vectors are present (U+16FE4; the hyphen and middle-dot mixes). The gate logs agree: C4 is red without the fix (43 of 49 failed) and green with it; T3, the full suite, passes.

For context only. This is not a finding, because the brief puts confusables out of scope and leaves them to #74:

- Characters that look like Latin letters but are Common script, or are Latin script themselves, pass the mixed-script rule and print raw today. Examples: `𝚌url x` (U+1D68C MATHEMATICAL MONOSPACE SMALL C, Common, so the check ignores it; in a monospace terminal it looks the same as `c`), `ⅽurl x` (U+217D, Latin) and `ｃurl x` (U+FF43, Latin). `proposal.parse` returns `Command` for all three. The brief scopes out confusable and skeleton matching (UTS #39's test for look-alike text), and #74's plan to show non-ASCII as escapes in the confirm UI is the stated cover. Nothing in this patch makes that gap worse. If #74 slips, the math-alphanumeric case (U+1D400–U+1D7FF) is the one to look at first, because "ignore Common" lets it into an otherwise Latin word.

No NEEDS-HUMAN items.

<!-- pdca:leaf-complete -->

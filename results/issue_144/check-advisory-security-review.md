# Security review (advisory) — issue 144 / charsafety-uts39-policy

Attacker-reachable inputs this diff touches: **the model's own output** (threat model item 5, the proposal `command` string, checked at `src/nl_shell/proposal.py:133-136`) and, through the shared `render.escape`, text shown from `:context` (`src/nl_shell/prompts.py:219`), REPL replies (`src/nl_shell/repl.py:124`) and start-up errors (`src/nl_shell/cli.py:70`). The property it serves is the must-hold "What the user confirms is exactly what runs" (`.oss-scanner/threat_model.md:127-140` in the patched tree).

**No finding.** What I checked:

- **Vendored tables are correct.** I compared every code point U+0000–U+10FFFF in `src/nl_shell/_unicode_tables.py` against Python 3.14's `unicodedata` (Unicode 16.0.0 on this host) for CF, CO, CN and MARK (Mn/Me), and against `/usr/share/unicode/` 16.0.0 for DEFAULT_IGNORABLE and WHITE_SPACE. Zero mismatches. So no hidden character slips through a wrong table range.
- **Probes through `proposal.parse`** (each as a `{"kind":"command",...}` JSON proposal): `lsㅤ`, `ls⠀`, `ls \x85` (NEL), `ls​`, `ls\r`, `lsᅟ`, `é́́`, and `é́⃝` (mixing Mn and Me in one run) are all `Rejected`. `render.escape` writes each one as an escape, and only the third mark of a run is escaped (`src/nl_shell/render.py:146-179`).
- **One predicate.** Rejection (`has_hidden`, `too_many_marks`) and display (`escape`) use the same `_HIDDEN` / `_MARKS` tables and the same `_mark_runs` counter (`src/nl_shell/render.py:113-179`). What the parser accepts can't show differently from what it checks.
- **No `unicodedata` at runtime.** `render.py` imports only `bisect`, `collections.abc` and the vendored module (`src/nl_shell/render.py:44-47`), so the policy doesn't change with the Python version.
- **The rejection covers the whole `command`, quoted or not.** It runs on the raw string before any parsing (`src/nl_shell/proposal.py:133-136`). The test covers the quoted case (`tests/test_charsafety.py:155`). That is the attacker-reachable case, not only the friendly path. The test file now has no raw non-ASCII bytes (I grepped and found none), so the previous round's finding about invisible literals is fixed.
- **Generator** (`scripts/gen_unicode_tables.py`) runs at build time only, reads trusted local UCD (Unicode Character Database) files, and writes only formatted integers (`scripts/gen_unicode_tables.py:123-124`). No untrusted input reaches it, and nothing can be injected into the generated module.
- **Resource use.** `has_hidden` / `too_many_marks` are O(n) with a binary search per character, and `COMMAND_MAX` bounds n. No hang or blow-up can be reached.
- **Gates.** C4 red 65/73 without the fix, green with it (`gate-logs/C4-verify.log`). T3 shows 554 passed (`gate-logs/T3-suite.log`).

Leftover risks the patch states itself, so not findings (threat model "Known gaps" and the brief's scope):
- Up to two stacked marks are still allowed. For example, `rm -rf /` + U+0336 U+0336 (combining long stroke overlay) is accepted as `Command` and shown raw, drawn as struck-through text. The cap of 2 is the brief's sign-off decision (UTS #39 §5.4), and the text is still visible, so this is not a hidden-character bypass.
- Blank or near-blank glyphs outside the properties and the named list (for example U+FFFC, which most terminals draw as a box) pass. The threat model says so ("a blank glyph on neither is not caught").
- Look-alike letters and mixed-script words pass. They are listed under Known gaps and moved to #12.

<!-- pdca:leaf-complete -->

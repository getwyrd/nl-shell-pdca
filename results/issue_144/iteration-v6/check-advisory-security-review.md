# Security review: issue 144 / charsafety-uts39-policy

**Attacker-reachable input this diff touches:** the model's proposal `command` (threat model "Where untrusted input enters" item 5, `.oss-scanner/threat_model.md:74-76`). It is checked by `render.has_hidden` / `render.too_many_marks` at `src/nl_shell/proposal.py:133-136`. The same predicate drives `render.escape`, which every display path calls (`src/nl_shell/repl.py:124`, `src/nl_shell/prompts.py:219`, `src/nl_shell/cli.py:70`). The generator `scripts/gen_unicode_tables.py` reads `/usr/share/unicode/` at build time only. That is trusted local data, not an attacker input.

**Result: no finding.** The patch makes "What the user confirms is exactly what runs" (`threat_model.md:127-140`) stricter and does not weaken it anywhere I could find.

What I checked, and what I saw:

- **The vendored tables are correct.** I compared `CF`, `CO`, `CN` and `MARK` in `src/nl_shell/_unicode_tables.py` against Python 3.14.4's `unicodedata` (Unicode 16.0.0) for every code point from U+0000 to U+10FFFF: 0 mismatches. The host's `/usr/share/unicode/DerivedCoreProperties.txt` header is `16.0.0`, so test (5), the regenerate-and-compare test, runs here and does not skip.
- **No gaps in the hidden set by category.** Every code point that is Cc, Cf, Co, Zl, Zp or Zs (other than space, LF and TAB) is hidden under `render.is_hidden` (`src/nl_shell/render.py:113-133`). None were missed.
- **The vectors in the brief are rejected.** By hand, `lsᅟ`, `x\U000e0100` and `a` + 3×U+20E3 (an enclosing mark, category Me) all come back `Rejected` from `proposal.parse`.
- **Mark counting can't be beaten by putting something between the marks.** Any character that isn't a mark resets the run (`render.py:146-151`). A hidden character used as the separator (for example ZWJ, U+200D) is rejected on its own grounds, and on display it shows as a visible `‍`, so it can't quietly join two runs.
- **No hang or blow-up from untrusted input.** Both checks make one pass over the text and do a binary search per character. `escape("e" + 100000×U+0301)` plus `too_many_marks` on 1M characters took 0.15 s in total. `COMMAND_MAX` (`proposal.py:131`) also caps the input length before these checks run.
- **Attacker-path test coverage.** `tests/test_charsafety.py` covers a hidden character placed bare and inside quotes (lines 143, 148), mark runs after a letter, at the start of the command and after LF (lines 163-179), escaping in `:context` (lines 154, 183), and the fake-`unicodedata` test (line 222). These are the attacker cases, not only the normal ones. The C4 gate log shows 65 of 72 tests red with the fix reverted and all green with it. T3 shows 553 passed.
- **Threat-model edits** (`threat_model.md:130-140`, `183-189`) describe what the code does. They also add an honest known gap for look-alike letters (confusables) and mixed-script words, instead of claiming those are caught.

Observation, not a finding (inside the brief's scope and UTS #39 §5.4, which counts only nonspacing marks): a spacing combining mark (category Mc) ends a mark run. So `e` + (U+0301 U+0301 U+1D165)×5 is accepted: `echo é𝅥𝅥𝅥𝅥𝅥́́́́́́́́́` came back as a `Command`. Each Mc character takes up its own cell in glibc's `wcwidth` (the C function terminals use to decide how many columns a character takes), so the nonspacing marks can't pile up on one spot. I could not confirm how every terminal draws this. If #12 or a later slice wants a stricter cap, counting Mc in the run would be a one-line change. Nothing is needed for this slice.

No NEEDS-HUMAN items.

<!-- pdca:leaf-complete -->

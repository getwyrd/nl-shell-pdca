# Security review — #144 character-safety policy (UTS #39)

Attacker-reachable inputs this diff touches: **the model's proposal `command`** (threat model item 5, checked by `src/nl_shell/proposal.py:133-138`), plus model replies, `:context` text and start-up error text printed through `render.escape` (`src/nl_shell/render.py:184`; called from `repl.py:124`, `prompts.py:219`, `cli.py:70`). `scripts/gen_unicode_tables.py` runs only at build time on the trusted local UCD files, so it is not attacker-reachable.

Severity uses the threat model's scale (`.oss-scanner/threat_model.md:236-269`). One caveat applies to both findings: nothing runs yet (the reply is "Nothing runs yet", `tests/test_charsafety.py:19`), and #74's confirm UI will escape all non-ASCII. So neither finding currently gets a deceptive command executed. Both are gaps in the stated invariant ("What the user confirms is exactly what runs", `.oss-scanner/threat_model.md:127-137`), not working exploits. I rate both **Low** today. They would become High ("spoofs the confirm UI") if #74 shipped without its non-ASCII escaping.

## What I checked and found sound

I ran the patched `nl_shell.render` on Python 3.14.4, tables at 16.0.0.
- Every brief vector is rejected or escaped as specified.
- U+2061/U+2062 and U+1D173 (Cf) are hidden, and so are U+FFFE and U+10FFFF (Cn, noncharacters) and U+D800 (lone surrogate).
- The `SCRIPT_EXTENSIONS` table holds no Zyyy/Zinh/Zzzz entries, so Common and Inherited really are ignored as documented.
- Rejection reasons (`proposal.py:134-138`) do not echo attacker text into errors.
- Only `command` is free text. `kind`, `risk` and `reason` are enums (`proposal.py:122-126`), so no other proposal field gets past the policy.
- The `escape` mark counter (`render.py:188-193`) and `too_many_marks` (`render.py:140-147`) count the same way.
- `WORD_SEPARATORS` is a single character class with `+`, so there is no ReDoS (a regular expression that can be made to take exponential time). The work is linear in a `command` that is already length-capped.
- The tests feed every vector as a stub model response through the real `Repl`, both JSON-escaped and raw (`tests/test_charsafety.py:79-94`). That is the attacker path, not just the friendly path.
- The threat-model edit stays inside the named bullet and leaves the sudo bullets alone.

## Findings

- NEEDS-HUMAN [impl] — **Low** — `src/nl_shell/render.py:96-106` (the `_HIDDEN` set). **Input:** proposal `command`, controlled by the model / text-only attacker. **What goes wrong:** U+1D159 MUSICAL SYMBOL NULL NOTEHEAD (category So, not Default_Ignorable, not White_Space) renders as blank in common fonts and is on the usual lists of invisible characters. It passes every check and prints raw. That breaks the brief's invariant "no character that renders as nothing or as blank reaches the user unmarked". **Reproducer:** `render.has_hidden("ls\U0001d159")` → `False`, and `render.escape("ls\U0001d159")` returns it unchanged. As a test, add `"musical-null-notehead-u1d159": ("\U0001d159", "\\U0001d159")` to `HIDDEN` in `tests/test_charsafety.py:98`; it fails today. **Fix:** add it next to U+2800 as a named blank glyph. This adds one code point to the property-based set; it does not go back to a hand-kept list.
- NEEDS-HUMAN [human] — **Low** — `src/nl_shell/render.py:150-172` (`scripts` / `mixed_script_word`). **Input:** proposal `command`, controlled by the model. **What goes wrong:** Mathematical Alphanumeric Symbols (U+1D400–U+1D7FF) have Script=Common. The mixed-script check ignores Common, so a word made of Latin letters plus look-alike math letters passes as single-script Latin. Fullwidth Latin (`ｃurl`) and Roman-numeral letters (`ⅽurl`, U+217D, Script=Latin) pass the same way. **Reproducer:** `render.mixed_script_word("\U0001d5bcurl")` → `None` (`𝖼url` looks like `curl` in many terminal fonts), and the same for `"ⅽurl"` and `"ｃurl"`. Bash sees a different command word. This is how UTS #39 §5.1 is written, so the patch matches its brief. UTS #39's identifier profile (§3.1) and confusable skeletons are what catch these, and the brief puts skeletons out of scope (#74). **The human needs to decide** whether to accept that #74's non-ASCII escaping covers this, or to widen this policy, for example by rejecting characters whose NFKC (Unicode compatibility normalization) form differs from the character itself (`Identifier_Status=Restricted`).

No other finding. The brief's attacker-reachable cases are covered by tests that drive the real parser and display path.

<!-- pdca:leaf-complete -->

# Adversarial review — issue #144 (charsafety-uts39-policy), iteration 4

Target: `/tmp/pdca-advisory-1kkgx980/target` (patched tree, Python 3.14.4). I could not
re-run pytest myself (`No module named pytest` here). That is a missing tool, not a
refutation. I judged C4/T3 from `gate-logs/` and called the production functions
(`nl_shell.proposal.parse`, `nl_shell.render`) directly.

## Findings

- NEEDS-HUMAN [human] — `src/nl_shell/render.py:144-146` and `:193-197` (`WORD_SEPARATORS` / `mixed_script_word`). **Shell quotes and backslashes get around the mixed-script rule.** The word splitter breaks at every ASCII punctuation character, including `"`, `'` and `\`. Bash does the opposite: it joins `"с"url` back into the single word `сurl`. Reproduced on the patched tree with `proposal.parse(...)`:
  - `"с"url example.com` → accepted (bash runs the word `сurl`, with Cyrillic U+0441)
  - `с''url x`, `с\url x`, `с$@url x` → accepted
  - `ls /tmp/с""url` → accepted (bash opens the path `/tmp/сurl`), while `ls /tmp/сurl` is rejected
  - `cat D""окумент.txt` → accepted, while `cat Dокумент.txt` is rejected

  `WORD_SEPARATORS.split('ls /tmp/с""url')` gives `['ls', 'tmp', 'с', 'url']`, so each piece has one script and passes. A proposer only needs one pair of empty quotes to defeat test vectors (3) completely. The builder followed the brief here: Scope (3) says to split "at ASCII whitespace and ASCII punctuation (`string.punctuation`)". So the defect is in the brief, and changing the split rule is a scope decision, not a slip. Possible fix: drop `"`, `'`, `\` (and maybe `$`, `` ` ``) from the separator set, or remove them before splitting, so a shell-concatenated word is checked as one word. Then add `"с"url`, `ls /tmp/с""url` and `с\url` to `MIXED` in `tests/test_charsafety.py:160`. The other option is to record this as a known gap for #12's bash parser in the threat model. As it stands, `.oss-scanner/threat_model.md` (the new text at the "What the user confirms is exactly what runs" bullet) says a word that mixes scripts is rejected "anywhere in a `command`, quoted or not". For words built by quote concatenation, that claim is wrong.

- `tests/test_charsafety.py:79-86` (`assert_rejected`). Minor, not a NEEDS-HUMAN item. The test checks only that a proposal was rejected, not which rule rejected it. I checked every vector in `MIXED` and the mark vectors, and none of them trips a different rule (none holds a hidden character), so for now each vector really does test the rule it is named for. A future vector could pass for the wrong reason, though.

## What I tried to refute and could not

- **Red→green evidence.** `gate-logs/C4-verify.log`: with the fix reverted, 50 of 58 fail. The 8 that pass on the old code are the accepted vectors, which is expected. Every rejection vector goes red, including test (5) and the static `unicodedata` check. The tests go through the real `Repl` → `proposal.parse` → `render`, not a copy of it.
- **Vendored tables.** I re-ran `scripts/gen_unicode_tables.py` against `/usr/share/unicode` (16.0.0). Its output is **byte-identical** to the committed `src/nl_shell/_unicode_tables.py`. None of `render.py`, `proposal.py` or `_unicode_tables.py` mentions `unicodedata`.
- **Highly Restrictive logic** (`render.py:185-190`). Latin+Han, Latin+Hiragana, Han+Hangul and `iPhoneの用` are accepted. Hiragana+Hangul, Bopomofo+Hiragana, Cyrillic+Han and Cyrillic + Arabic-Indic digit (`с١`) are rejected. All of these match UTS #39 §5.2.
- **Mark limit** (`render.py:164-171` and the run counter in `escape`). The parser and `escape` agree. A spacing mark (Mc, e.g. U+0903) between marks resets the run in both, so nothing gets past the parser that `escape` would still show raw. Runs of Mc or Lo (`ििि`, `ำำำ`, `ᅡᅡᅡ`) are accepted, but the brief limits the rule to Mn/Me, so this is not a defect of this diff.
- **Hidden set.** U+2003, U+2061, U+200D, U+3164, U+1D173 and U+0D4D inside a Latin word are all rejected. U+0F0C, U+115A and an all-Cyrillic `ас` are accepted, but the human's iteration-3 decisions put look-alikes and blank glyphs outside the named list out of scope.

## Side note

Importing the modules wrote `src/nl_shell/__pycache__/*.cpython-314.pyc` into the target tree (`python3 -I` does not turn off bytecode writes). These are build artifacts, not part of the patch, and I did not delete them.

<!-- pdca:leaf-complete -->

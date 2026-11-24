# Security review (advisory): issue 155, failure-classifier-by-exit-code, iteration 7

Attacker-reachable inputs this diff touches: **session state** (threat model item 4: `snapshot.aliases`, `snapshot.functions`, `snapshot.path`, `snapshot.disabled_builtins`) and **the model's proposal as confirmed text** (item 5, the `command` argument). Command output (item 1) is not read: `classify` takes no output parameter (`src/nl_shell/failure_classes.py:118`), and only `to_reader` gates it.

The property at stake is "wrappers, aliases, functions and session hooks don't hide a privileged step" (`.oss-scanner/threat_model.md:109-112`). A miss here would be **High** ("a privileged or destructive step is classed lower"). The accepted text-only misses are recorded in Known gaps (`.oss-scanner/threat_model.md:190-203`), so they are not findings.

## Findings

No new finding for this round.

## What I checked

- **Fix 1, the alias parse** (`src/nl_shell/failure_classes.py:300-346`). Values are now read by their single-quote and backslash structure, which is how `alias -p` prints them. They are no longer read by where lines start. I ran `_parse_aliases` and `is_privileged` against the target:
  - The sign-off repro `alias s='sudo -v\nalias s=ls #'` with `s x` is now privileged. The value is kept whole.
  - A repeated name gives `None`, which counts as privileged (`:324`).
  - An unclosed quote marks every later line-start name as `None` (`:325-328`).
- **A newline inside an alias value.** I checked whether `" ".join(shlex.split(raw))` (`:320`) folds a newline into a space and so hides a second command, for example `alias s='ls\nsud${X}o x'`. It does not: bash always quotes the whole value, so `shlex.split` returns one word with the newline kept, and P3 still cuts there. Result: privileged. The same holds with `'\''` escapes in the value.
- **Fix 2, the depth memo** (`:236-250`). The memo now stores the chain height and applies the depth cut-off on a repeat visit (`depth + height - 1 > MAX_ALIAS_DEPTH`).
  - `a8; a0`, `a8 a0`, `a5; a0` and `a1; a0` on the 10-alias chain are all privileged.
  - I also compared it against a reference with no memo (`fuzz_memo.py` in this sandbox). Over 20,000 random alias graphs (2–14 aliases, 0–2 references each, 1–4 command segments) there were 0 mismatches. "Privileged" answers are never saved, and a cycle ends the call (`:236`), so a cached "not privileged" cannot hide a cycle.
- **Cost.** Each alias value is checked at most once per call, because "not privileged" is saved and "privileged" ends the call. `_parse_aliases` is one forward pass. The C4 log shows the 1200-group, cycle and 10-deep timing rows green.
- **The patch's own tests cover the attacker case.** The rows are at `tests/test_failure_classes.py:333-349`:
  - The multi-line value row (`:341`) is red on the old line-start parser. The repeated-name rows (`:344-345`) and the unclosed-quote row (`:346`) cover the safe direction.
  - The order-sensitive rows `a8; a0` and `a8 a0` (`:348-349`) are red on the old memo.
  - The plain controls (`:370-372`) keep the fix from over-matching ordinary aliases.
- **Display safety and the reader route** are unchanged from the reviewed design:
  - Only printable ASCII words of 64 characters or fewer reach `message` (`:412-415`).
  - The lookup is read under a bound and a raised exception gives no suggestion (`:390-409`).
  - `to_reader` is True only for OTHER (`:140`).
- **Gates.** C4 passes (269 of 270 red without the fix, all green with it). T3 suite: 922 passed. T2 found no security-relevant path. I could not re-run pytest here because it is not installed, so I relied on the frozen C4 and T3 logs. My direct probes ran the module itself with `python3 -I`.

Not re-raised, because the brief's review bound settles them as rule gaps tracked in #12:
- the P3 redirection-with-`&`/`|` gap, now item (5) of the Known-gaps bullet;
- `PATH`, `trap` and `PROMPT_COMMAND` misses.

<!-- pdca:leaf-complete -->

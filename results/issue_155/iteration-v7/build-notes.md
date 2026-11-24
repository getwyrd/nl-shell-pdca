# Build notes — issue 155, iteration 7

Base: `5d3d291` (worktree `/home/eddie/nl-shell/nl-shell.pdca-wt-l0`). Line numbers below
are in the patched tree.

## What this round does

The carry-forward said: fix two P5 build bugs, keep the rest of the v6 patch, and record
the redirection gap in the Known-gaps bullet. I applied `iteration-v6/patch.diff` unchanged
and then made only these edits.

### 1. Alias parse by quoting (`src/nl_shell/failure_classes.py:300-351`)

v6 split `alias -p` text at every line that starts `alias NAME=`. A multi-line value can
hold such a line, which then overwrote the real value (`alias s='sudo -v\nalias s=ls #'`
→ `s x` was OTHER).

Now `_parse_aliases` walks the text in order. At each line start it matches
`alias NAME=` (`_ALIAS_START`, `:113`) and reads the value as one shell word by its
quoting (`_word_end`, `:333`): a `'...'` run is skipped to its closing quote, a backslash
skips the next character, and whitespace ends the word. That is how bash prints values
(single quotes, `'\''` for an embedded quote). Parsing then resumes at the next line after
the word ends, so lines inside a quoted value are never read as new aliases. The value is
then unquoted with `shlex.split` (or used as written if that raises), as the brief's rule
P5 says.

I also took the safe-direction fallbacks the carry-forward offered, because they cost a
few lines and cover text that bash would never print:
- a name that appears twice → value `None` → privileged (`:325`);
- an unclosed quote → that value is the rest of the text as written, and every name that
  starts a line in that rest is `None` (`:326-329`).
`_alias_privileged` treats `None` as privileged (`:242-243`).

Work stays linear: one forward pass; each `find` moves forward.

### 2. Depth-correct memo (`src/nl_shell/failure_classes.py:191-250`)

v6 returned the saved result before the depth check, so `a8; a0` saved `a8` as "not
privileged" at depth 1 and reused it at depth 9 → OTHER.

Swapping the two checks is not enough. I tested that: with only the swap, `a7; a0` still
gives OTHER, because `a7` is saved as not privileged at depth 1 and then reached at depth 8,
where the depth check passes but its own chain (`a7→a8→a9`) would go to depth 10. So the
memo now stores, for each "not privileged" alias, the height of its chain (how many alias
levels it reaches, itself included). On reuse at depth `d`, it is privileged if
`d + height - 1 > MAX_ALIAS_DEPTH` (`:238-240`), which is exactly what a fresh walk would
find. `_privileged` returns `(verdict, height)` to carry this up (`:191-218`).

Only "not privileged" results are saved. A "privileged" result returns straight up to
`is_privileged` and ends the call, so saving it could never be used. A "not privileged"
result cannot have touched a cycle or a depth cut-off (both return privileged, which would
have ended the call), so it does not depend on the path taken to reach it. Each alias value
is still walked at most once per call.

### 3. Known-gaps bullet (`.oss-scanner/threat_model.md:200-202`)

Added kind (5): a redirection that holds `&` or `|` in front of the command word
(`2>&1 sud${X}o x`, `<&0 sud${X}o x`, `>| out sud${X}o x`), because P3 cuts at `&` and `|`
before it skips redirections. P3 itself is unchanged, as the carry-forward asked. This is
for #12.

### Test rows added (`tests/test_failure_classes.py`)

- P5 privileged (`:338-351`): multi-line value, an alias defined after a multi-line value,
  repeated name (privileged and plain values), unclosed quote, and the order rows
  `a8; a0`, `a8 a0`, `a7; a0` on the 10-deep chain.
- Not privileged (`:365-375`): a multi-line plain value (`m`), a value with an escaped
  quote (`'echo it'\''s'`), and `a8; a9` (a short chain tail stays OTHER, so the memo fix
  does not over-match).
- The threat-model test also checks `2>&1 sud` inside the classifier bullet (`:789`).

Every new row also goes through the existing "no `None` in any message" table, since that
test pulls in all of `PRIVILEGED_P5`.

## Ruled out

- Treating a repeated name as privileged *instead of* parsing by quoting. That fixes the
  sign-off repro but not a value whose inner line names a *different* alias: with
  `alias s='echo\nalias t=x\nsudo'`, the line-start split cuts `s` to `'echo` and hands
  `sudo` to a fake `t`, so `s x` would be OTHER. The quoting parse reads `s` as
  `echo\nalias t=x\nsudo` and gives privileged (checked by running it). The parse is about
  40 lines; the repeated-name rule stays as a fallback on top.
- Swap-only memo fix: rejected by the `a7; a0` row above (measured, not guessed).

## Refuting my own test

- **(a) Genuine red?** Yes. Whole fix reverted by the C4 gate
  (`engine/scripts/run-verify.sh`): "red without the fix (269 of 270 failed), green with
  it", `PDCA-EVIDENCE: C4 PASS`. The one green-in-both test is the ASCII self-check, by
  design. Sharper check: with v6's `failure_classes.py` put back (the rejected code), all 7
  new P5 privileged rows fail (`7 failed, 263 passed`) and pass with this round's code
  (`270 passed`). With a swap-only memo fix, `alias-chain-10-a7-first` fails.
- **(b) Production path?** Yes. Every row calls `nl_shell.failure_classes.classify` with a
  real `session.CommandResult` and a real `pty_protocol.Snapshot`; the alias text is what
  P5's production parser reads. No mocks.
- **(c) Fixture includes the fault?** Yes. The multi-line row is the exact repro from the
  sign-off (`alias s='sudo -v\nalias s=ls #'` as `alias -p` prints it), and the order rows
  use the 10-alias chain that triggered the memo bug.

## Other checks

- Whole suite: `engine/scripts/run-suite.sh` → `922 passed`, `T3 PASS`.
- Formatter / hooks: the target has no formatter, linter or pre-commit config
  (nothing in `pyproject.toml`, `CONTRIBUTING.md`, `AGENTS.md`; no
  `.pre-commit-config.yaml`). No line is over 99 characters.

## Housekeeping the human should know about

While doing the red check I left three scratch files that are not part of the patch and
that I did not delete (cleanup is the harness's job):
- `/home/eddie/nl-shell/nl-shell.pdca-wt-l0/tests/_v6_fc.txt` and `tests/_new_fc.txt`
  (untracked, inside the worktree; `.txt`, so pytest does not collect them);
- `/home/eddie/nl-shell/fc_new.py.keep` — a copy of the new module that a stray `cp`
  wrote **outside** the worktree, by mistake. It is safe to delete.

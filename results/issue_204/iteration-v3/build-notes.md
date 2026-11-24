# Build notes — issue 204 / gate-command-table-engine (v3)

Target: eduralph/nl-shell @ main (`1a1e980`). Worktree: `$PDCA_WORKTREE`
(`/home/eddie/nl-shell/nl-shell.pdca-wt-l1`). Line numbers below are in the patched tree
(base + `patch.diff`).

## Starting point

The brief says v2's table and engine stand, and that v3 only adds decision D (b1), the
path-lookup rule, the recorded path gap, `$"…"` decoding and the "with no command"
reason assertions. It also names v2's handling of an undecodable `$'…'` as the peer
to generalise. So I applied `iteration-v2/patch.diff` unchanged onto `1a1e980` as the
base and built the v3 delta on top. That is the only prior-cycle file I opened besides
the brief. I did not read v2's review or sign-off files.

## What v3 changes (on top of v2)

### Engine — `src/nl_shell/gate/rules.py`

- `rules.py:56-57` — two new reasons: `UNREADABLE_COMMAND` ("command word the gate
  cannot read", decision D) and `OUTSIDE_SYSTEM` (the path reason for a `~/…` word).
- `rules.py:116` `readable()` — now also decodes locale quoting `$"…"` like `"…"`
  (`rules.py:166-167`): the `$` is skipped and the existing double-quote branch reads
  the body, so a `$"…"` with `$` or a backtick inside stays unreadable. `lex_word`,
  `make_word` and `Word.literal` are untouched, as the brief requires.
- `rules.py:253` `command_name()` — the command-word reader. Same as `readable()`, except
  a word whose only non-literal cause is `leading-tilde` (`parse.py:262-265`) comes
  back as its text plus a "this is a `~` path" flag. Only the command word goes through
  it, so `~` in arguments is unchanged.
- `rules.py:328` `argv()` — one fail-closed path, `_fail_closed` (`rules.py:373`), now
  serves both the v2 undecodable-`$'…'` argument rule (`command_word=False`,
  `rules.py:336`: `privileged`, proposal rejected, same as v2) and decision D for the
  command word (`command_word=True`, `rules.py:339`). This is the "generalise it, do
  not add a second path" instruction. For a command word, `_fail_closed` also:
  - rejects for every origin when stdin is not `terminal`/`file` (pipe, here-doc,
    here-string, and `unknown` counted as a pipe, as v2's `_elevation` does);
  - for every elevating row with rejected options (the sudo family, data-driven through
    `Table.rejecting_elevators()`, `commands.py:286`), runs `_rejecting_options`
    (`rules.py:391`). That reads **each** argument word on its own with that row's own
    grammar reader (`_Engine._option`), so bundled (`-nS`), attached (`-px`), `=` forms
    and long prefixes (`--stdi`, `--pro`) are found the same way the `sudo` row finds
    them. It also parses the args with that grammar and rejects when a word the gate
    cannot read stands where sudo reads options (v2's `sudo "$P" true` rule). A `~`
    word is read as its path for that check (`rules.py:420`), because `~` always expands
    to a path and never to an option. Without that, typed `$(echo rm) -rf ~` was
    rejected.
  - Decision A still runs over the arguments (`$x sudo` keeps "argument names an
    elevating command").
- The v2 rule "inner command the gate cannot read ⇒ `destructive`" is gone: an inner
  command word the gate cannot read now goes through the same decision D path, which is
  `privileged`. That covers `find -exec {}` (`{}` has lex cause `brace`, so it is
  unreadable) and `xargs` replace strings (v2 already turns those words into the
  unseen-input placeholder `_INPUT`, whose empty source makes it unreadable).
- `~/x` with no row: the command layer raises to `mutating` with `OUTSIDE_SYSTEM`
  (`argv()`, right after the row lookup). `~/sudo` hits the `sudo` row through the
  existing last-part lookup (`commands.py` `Table.lookup`). `./sudo` already worked in
  v2. The shell layer is unchanged and still says "command word is not a literal" for
  `~/…`.

### Data / spec / threat model

- `commands.py:286` `Table.rejecting_elevators()` — the grammars of elevating rows that
  have rejected options. Kept in the table module so decision D names no command in code.
- `docs/design/specs/policy-gate/v1.md`: §2 command-word bullet split (`:90-94`): the
  non-literal part points at decision D, the path part stays `mutating`. §4 wrappers
  (`:131-132`): "non-literal inner command ⇒ destructive" became "⇒ `privileged`
  (decision D)". §4.1 item 1: `$"…"` decoding; undecodable argument vs command word.
  Item 3 (decision A): limited to commands with neither row nor allowlist entry,
  matching #197's tracker wording. New item 6 (`:186`) decision D, item 7 (`:206`)
  path lookup + the **known path gap** (`:211`, pointing at #192). §5 (`:263`): decision
  D bullet. Conformance rows 53–55 (`:440-442`). Row 16 already said "destructive
  (ANSI-C decodes to `rm`)" from v2. Nothing claims recursion, B′, classes 3–6, or that
  text / stored code is read.
- `targets/ubuntu-26.04/gate-vectors.toml:217-236` — vectors for rows 53, 54, 55.
- `.oss-scanner/threat_model.md:194-206` — command-layer paragraph now states decision D
  and the path lookup, and limits decision A to commands with no row. "Known gaps"
  (`:280`) gains the path-command-word gap pointing at #192. The "What must hold" sudo
  sentence (`:121-125`) is unchanged and still true: D is what makes `x=sudo; echo pw |
  $x -S true` rejected.

### Tests

- `tests/test_gate_commands.py` (bundle copy alongside). New or changed v3 cases:
  - `test_class2_no_command_opens_a_shell_under_sudo` (`:304`) now asserts a reason of
    the form `root shell: <command> [<sub>] … with no command` for every such row.
    `test_class2_no_command_reason` (`:341`) asserts it for `sudo chroot /` and
    `sudo unshare`.
  - `test_class7_floor_path_gap_documented_not_raised` (`:368`): `./x -i`, `/tmp/x -i`,
    `~/bin/x -i` as proposals, `mutating`, not rejected, reason includes "path outside
    the system directories".
  - `test_spec4_path_lookup_uses_the_last_part` (`:395`): `./sudo -i`, `~/sudo -i`.
  - Wrapper property (`:455`): `<prefix> $x -i` rejected as a proposal with the D reason
    for every `runs-command-at` row.
  - `test_decision_a_locale_quoting` (`:606`); `$x rm -rf x` raised to `privileged`.
  - `test_decision_d_*` (`:676-713`): every proposal and typed case the brief lists,
    plus bundled/attached/prefix forms (`$x -nS`, `$x -px`, `$x --stdi`,
    `$x --prompt=x`).
- `tests/test_policy_gate.py:196-221` — two regression rows raised (never lowered):
  - `$(echo rm) -rf ~`: `destructive` → `privileged` (the brief's `:193`).
  - **`PATH=x >/dev/null; cat`: `session-altering`, not rejected → `privileged`,
    rejected.** The brief did not predict this one. tree-sitter-bash cannot parse that
    line, so the walker passes `;` to the command layer as a command word in untrusted
    text. `;` cannot be read (lex cause `metacharacter`) and its stdin is `unknown`,
    which §5 counts as a pipe, so decision D rejects it. It is a raise, so `v1.md:241`
    allows it, and it is consistent with v2 (a `sudo` in untrusted text is rejected the
    same way). But a valid typed line is now rejected because of a parser misread.
    **The human should look at this at sign-off.** The other option was to apply D only
    to the causes the brief lists (expansion, glob, brace, …) and leave
    `metacharacter`/`unclosed quote`/`line continuation`/`tilde` words at v2's
    `mutating`. I did not take it: those words only appear in broken parses or in
    spellings like `su\⏎do` (which bash reads as `sudo`), and the invariant says a word
    the gate cannot read is never below its worst run-time meaning. The diff for the
    other option is about 4 lines in `command_name()` plus reverting the test row.

## Choices and what I ruled out

- **Per-word scan vs. sudo-grammar positional parse for rejected options.** The brief
  says "any argument word that the `sudo` row's grammar reads as a rejecting option".
  I scan every argument word, not just the ones before sudo's first operand. Reason:
  `$x` may split or be a different elevator, so position is not reliable. Cost: typed
  `$x ls -A` is rejected (`-A` read as sudo's askpass). Same class of cost as the
  brief's accepted `$EDITOR -p a b`.
- **Unreadable word where sudo reads options** (`$x "$P" true`): rejected, positionally
  (only before the first operand, as v2's `sudo "$P" true`). Without it `x=sudo;
  P=-S; echo pw | $x "$P" true` is still caught by the pipe rule, but typed
  `$x "$P" true` with `P=-A` would not be. Cost: typed `$EDITOR "$f"` is rejected.
  This goes past the brief's listed costs; noting it here for the human.
- **Hard-coding `sudo`** in decision D: ruled out. D uses every elevating row with
  rejected options (`Table.rejecting_elevators()`), so it stays table-driven
  (sudo/sudo-rs/sudo.ws and sudoedit share one rule set today).
- **Changing `lex_word` to mark `$"…"` literal:** ruled out by the brief (it would lower
  shell-layer verdicts). The decoding is in `readable()` only.

## Runs (project runner only)

- `engine/scripts/run-suite.sh` (T3) on the final tree: **1586 passed, 1 skipped**,
  `PDCA-EVIDENCE: T3 PASS`.
- `engine/scripts/run-verify.sh` (C4) with `PDCA_BUNDLE` set: green leg passes; red leg
  (production hunks reverted, tests kept): **203 of 441 failed**, `PDCA-EVIDENCE: C4
  PASS`. The worktree was restored to base + patch afterwards (`git diff` matches
  `patch.diff`).
- Extra red check for the v3 delta alone: put v2's `rules.py`/`commands.py` back with the
  v3 tests and data, ran `run-suite.sh`: **40 failed** — every `test_decision_d_*` case,
  the path-lookup and path-gap `~` cases, the wrapper `$x -i` property,
  `test_decision_a_locale_quoting`, the two raised `test_policy_gate.py` rows and the
  row 53–55 vectors. `test_class2_no_command_*` passed on v2 too, since v2 already gave
  that reason; v3 only asserts it now. Then restored the v3 files.
- Commit-readiness: the target has no formatter or pre-commit config (`pyproject.toml`
  has none; no `.pre-commit-config.yaml`). Ran its CI doc checks:
  `scripts/docs_links.py` (0 broken) and `scripts/docs_checks.py immutability 1a1e980
  HEAD` (OK).

## Refuting my own test

- **(a) Genuine red?** Yes. With the production hunks reverted (`run-verify.sh` red leg)
  203 of 441 bundle tests fail. With only the v3 engine change reverted (v2 engine), 40
  fail, covering every v3 group: decision D, `$"…"`, `~` path lookup and gap, the
  wrapper `$x` property.
- **(b) Production path?** Yes. Every case calls the public `nl_shell.gate.classify(cmd,
  origin=…)`, which goes through the real walker (tree-sitter-bash) into
  `rules.classify` and the real `targets/ubuntu-26.04/commands.toml`. No mocks. The only
  monkeypatching is the loader root for the decision C / fixed-location tests, as the
  brief prescribes.
- **(c) Fixture includes the fault?** Yes. The cases are the brief's literal bypass
  strings (`/usr/bin/sud? -i`, `x=sudo; $x -i`, `echo pw | /usr/bin/s*do -S true`,
  `git log | $PAGER`, `~/sudo -i`, `find … -exec {} -i \;`, `xargs -o -I% % -i`), run
  against the full checked-in table, with `sudo` rows present and nothing filtered out.

## Not done / out of scope

- No `scripts/harvest_inventory.py` re-run. The inventory is v2's, unchanged. The brief
  makes inventory drift a human check at Check, not a gate.
- No PR pushed or opened.

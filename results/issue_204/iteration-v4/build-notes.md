# Build notes — issue 204 / gate-command-table-engine (iteration 4)

Target: eduralph/nl-shell @ main (`1a1e980`). Worktree: `$PDCA_WORKTREE`
(`/home/eddie/nl-shell/nl-shell.pdca-wt-l1`). Line numbers below are in the patched tree
(base + `patch.diff`).

## Starting point

The carry-forward says "Core engine and table are sound; keep the slice" and lists five
in-scope bypasses. So I applied `iteration-v3/patch.diff` unchanged onto `1a1e980` and
built only those five fixes on top. Base + v3 ran green first (`run-suite.sh`: 1586
passed, 1 skipped). I read `iteration-v3/build-notes.md` for v3's own choices; I did not
read v3's review or sign-off files beyond the carry-forward block in the brief.

Everything in v3's notes still holds (decision D design, the `PATH=x >/dev/null; cat`
raise, the `$x "$P"` cost). This file covers the iteration-4 delta only.

## The five fixes

### 1. Bracket-glob command word (`sud[o]`, `[s]udo`, `su[d]o`) — walker fix

tree-sitter-bash misreads an unquoted `[` in a command word, two ways (dumped the trees):

- `sud[o] -i` → `ERROR('sud[o] -')` holding a `subscript`, then `command('i')`. The
  command layer only ever saw `i`.
- `[s]udo -i` → `test_command('[s]')` (inside an ERROR, or with only a MISSING `;` and
  no ERROR at all for `ls; [s]udo -S x`), then `command('udo -i')`.

bash reads one glob word there and runs whatever it matches (with a file named `sudo`
in the cwd, `sud[o] -i` runs `/usr/bin/sudo -i`).

Fix, in the walker, since only it has the source bytes (the brief allows "a walker bug a
case here exposes"; this is that):

- `parse.py:678` `_bracket_command`: from the shell word that holds the node's start
  (`_word_start`, `parse.py:670`), read the raw words to the end of the simple command
  (`_raw_words`, `parse.py:610`, quote-aware, stops at an unquoted `;&|()<>` or newline).
  If the first word holds a real bracket glob (`_unquoted_bracket`, `parse.py:644`: an
  unquoted, unescaped `[` with a `]` after it; bash reads a lone `[` as itself), append
  one more `Invocation` with those words, built by the existing `make_word`. The command
  word is not literal, so decision D applies unchanged in `rules.py`.
- Called from `_error` (`parse.py:712`) and `_test_command` (`parse.py:747`).
  `walker.bracket_words` (`parse.py:521`) stops an ERROR around a test command from
  making two.
- `{a[0]}>x` (bash's named-descriptor redirect) is skipped (`parse.py:692-694`); only
  the `{…}` form against `<`/`>`, so `sud[o]</dev/null -i` is still caught.
- `_check_walk` (`parse.py:1181`) now subtracts these invocations
  (`walker.from_text`, `parse.py:520`) so its "one invocation per simple command node"
  check still holds. `tests/test_policy_gate.py::test_rule2_one_invocation_per_simple_command`
  is unchanged and green: I checked every input in its corpus gives the same count.

`lex_word`, `make_word`, `Word.literal` and every shell-layer rule are unchanged.

**Tried and ruled out:** a trigger on any glob character (`*`, `?`, `[`) in an ERROR's
first word. It broke 8 existing tests: extglob arguments (`ls *(a)`, `ls ?(a)`,
`ls *.@(c|h) 2>/dev/null`) also give ERROR nodes, and typed they went from `mutating`,
not rejected, to rejected. The misparse is specific to `[`, so the trigger is too. Then a
lone `[` (`[ a \> b ]` gives ERROR at `[`) was caught; requiring a `]` after the `[`
fixed that, which is also how bash decides. Then `{a[0]}>x` changed the invocation count;
fixed by the named-fd skip.

**For the human:** typed `sud[o] -i` is `privileged` **and rejected**, not just
`privileged` as the carry-forward wrote. Reason: the tree is untrusted, so the shell
layer sets every stdin to `unknown` (`parse.py` `shell_layer`, unchanged), and decision D
counts `unknown` as a pipe ("pipe, here-doc or here-string into a command word the gate
cannot read"). That is the same thing v3 already does for any command word the gate
cannot read inside untrusted text. It is a raise. The test asserts `privileged` and the
D reason and does not pin the rejected flag for the typed case. A trusted `[s]` (no
glued text) is `privileged`, not rejected, like `$x -i`.

### 2. `< /dev/stdin` counts as a pipe

`rules.py:280` `fed(stdin)`: `terminal` → no; anything but `file` → yes (as before);
`file` → yes when the path's last part is `stdin` or a number (`/dev/stdin`,
`//dev//stdin`, `/dev/fd/0`, `/proc/self/fd/0`, `/proc/1234/fd/0`, a relative `stdin`).
Used at both §5 pipe checks: decision D (`rules.py:442`) and `_elevation`
(`rules.py:555`), and by the new text scan (`rules.py:536`). `sudo tee /x < input.txt`
is still not rejected (test `test_section5_stdin_from_a_plain_file_is_not_a_pipe`).

I matched by last path part, not by a list, because the gate cannot follow a symlink or
place a relative path; a symlink with any other name is the same class as the recorded
path gap (§7, #192). I left `_effect`'s `bash /dev/stdin` operand check
(`_STDIN_FILES`) as v3 had it: widening it would turn `bash 0` (a file named `0`) from
`destructive` into "opens a shell", which is lower for typed input.

### 3. Inventory drift

Re-ran `scripts/harvest_inventory.py` on this host (`VERSION="26.04.1 LTS (Resolute
Raccoon)"`). The only difference from v3's file: `mount.cifs` (setuid) and `mount.smb3`
(same file). Added both to the `mount` row (`commands.toml:999-1009`; the list is now one
name per line). Re-ran the harvest after the row edit: same bytes (md5 unchanged). Both
names added to the test's `REQUIRED_INVENTORY` (`tests/test_gate_commands.py:141-143`).

### 4. `$"…"` fails closed

- `rules.py:176-177` `readable()`: an unquoted `$"` now returns None (was: read like
  `"…"`). Docstring updated.
- `rules.py:255` `undecodable()`: true for a word holding `$'` or `$"` that `readable`
  cannot read. So an argument `$"…"` goes through the same `_fail_closed` path v3 uses
  for an undecodable `$'…'` (no second path), and `foo $"sudo"` stays `privileged`.
- `CANNOT_DECODE` (`rules.py:63`) now names both quotings.
- Spec §4.1 item 1, item 3 and item 6, threat model command-layer paragraph: rewritten
  so nothing says `$"…"` reads like `"…"`.

Cost: any `$"…"` argument is now `privileged` (typed `echo $"hello"` is privileged; a
proposal with it is rejected). The carry-forward asked for fail-closed and this is what
closed means for a word bash translates through a catalog the session chooses.
`tests/test_policy_gate.py`'s KIND_COVERAGE input `echo $"x" …` only checks the walk, and
stays green.

### 5. Decision A's scan over text-effect arguments (option (b))

`rules.py:508` `_text_scan(args, stdin)`, called when a non-gap text effect applies:
fixed rows (`rules.py:422-423`) and parsed rows (`rules.py:636-637`). It cuts the
readable arguments into words with `text_words` (`rules.py:300`: `shlex` with
`punctuation_chars`, `#` not a comment, backticks as spaces, each token cut again at
white space; an unclosed quote falls back to a regex split). Separators split it into
segments. For each word that names a row with `elevates`:

- `privileged`, "sudo named in code the gate cannot read"; a proposal is rejected;
- a fed stdin (`fed()`) rejects, for every origin;
- if that row has options it rejects, `_rejecting_options` (v3's per-word reader, same
  one decision D uses) runs over the words after it in the segment, for every origin.

No recursion, no parse: the row stays decision B and the B reason stays. Class-7 gap
effects are skipped, so `git -c core.pager=sh log` and the awk program operand keep
their floor.

Costs (all raises): typed `bash -c 'make && sudo make install'` is `privileged`, not
rejected; with a pipe in front it is rejected. `python3 -c 'print("sudo")'` typed is
`privileged`. Gaps left (child-2's recursion closes them): `$'\x73udo'` inside the text
is not decoded; an elevating word built by the text at run time is not seen.

## Spec / threat model

- `docs/design/specs/policy-gate/v1.md`: §4.1 item 1 (`:157-166`, `$"…"`), item 3
  (`:173`), item 6 decision D (`:188-212`: `$"…"`, the bracket-glob misread, fd-0
  stdin), item 9 (`:255-263`, the text-argument scan), §5 pipe bullet (`:274-278`).
  Nothing claims recursion, B′, classes 3–6, or that text is parsed.
- `.oss-scanner/threat_model.md:200-224`: same points. The "What must hold" lines
  (`:115-130`) are byte-identical to base (checked with `diff`).

## Runs (project runner only)

- `engine/scripts/run-suite.sh` (T3) on the final code: **1607 passed, 1 skipped**,
  `PDCA-EVIDENCE: T3 PASS`. (Only Markdown line wrapping changed after that run;
  `scripts/docs_links.py` re-run: 0 broken.)
- `engine/scripts/run-verify.sh` (C4) with `PDCA_BUNDLE` set: **red leg 223 of 462
  failed** (plus 12 setup errors) with production hunks reverted, green with them,
  `PDCA-EVIDENCE: C4 PASS`. Worktree restored; `git diff` byte-equal to `patch.diff`.
- Iteration-4 delta alone: put v3's `rules.py`, `parse.py`, `commands.toml` and
  `inventory.toml` back (via `git apply -R`/`git apply --include`), kept the v4 tests, ran
  `run-suite.sh`: **19 failed**: the inventory coverage test, both `$"…"` tests, all 4
  bracket-glob D cases, all 3 bracket-glob §5 cases, 3 of the 5 `/dev/stdin` cases, all
  4 text-argument §5 cases and both text-argument proposal cases. Then restored v4 and
  checked `git diff` equals `patch.diff`.
  - The `/dev/fd/0` and `/proc/self/fd/0` variants already passed on v3 (another rule
    rejects them); they stay as coverage. `test_bracket_builtin_is_not_a_glob_command_word`
    and `test_section5_stdin_from_a_plain_file_is_not_a_pipe` pass on both; they guard
    against over-raising.
- Commit-readiness: the target has no formatter, linter or pre-commit config
  (`pyproject.toml`, no `.pre-commit-config.yaml`; CI runs pytest and the docs checks).
  `scripts/docs_links.py`: 0 broken. `docs_checks.py immutability`: the spec is
  `status: draft`, so not frozen.

## Refuting my own test

- **(a) Genuine red?** Yes. Full revert (C4 red leg): 223 of 462 fail. Iteration-4
  revert only (v3 engine and data, v4 tests): 19 fail, covering each of the five
  carry-forward items.
- **(b) Production path?** Yes. Every case calls the public
  `nl_shell.gate.classify(cmd, origin=…)`: real tree-sitter-bash parse, the real walker
  (where fix 1 lives), `rules.classify`, and the checked-in `commands.toml`. No mocks;
  the only monkeypatching is the loader root in the decision-C / fixed-location tests,
  as the brief prescribes.
- **(c) Fixture includes the fault?** Yes. The cases are the carry-forward's own bypass
  strings (`echo pw | sud[o] -S true`, `[s]udo -i`, `echo x | sudo tee /x < /dev/stdin`,
  `echo pw | $"ls" -S true`, `eval sudo -S true`, `env -S 'sudo -S true'`, …), plus
  `ls; [s]udo -S x`, the no-ERROR parse shape. They run against the full table with the
  sudo rows present. The inventory test reads the regenerated file, which holds the two
  names that were missing.

## Not done / out of scope

- `hash -p` / `BASH_CMDS` (#206) and destructive rows for `git checkout`, `stash drop`,
  `branch -D`, `rsync -e`: the carry-forward puts these out of scope.
- No new `gate-vectors.toml` rows for the iteration-4 cases; the brief only asks for
  vectors for the decision-D Conformance rows, which v3 added.
- No PR pushed or opened.

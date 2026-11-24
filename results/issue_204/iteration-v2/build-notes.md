# Build notes — #204 gate command-table engine (iteration 2)

Target: `eduralph/nl-shell @ main` (`1a1e980`), worktree `nl-shell.pdca-wt-l1`. Line
numbers are in the patched tree unless marked "base".

## How this iteration was built

I started from the previous attempt's patch (`iteration-v1/patch.diff`, applied cleanly
to `1a1e980`). The human's carry-forward kept the slice and asked for six bypasses to be
fixed, so I did not rebuild from scratch. I first added the carry-forward's test cases
to `tests/test_gate_commands.py`. On the iteration-1 tree, 20 of them failed (all six
items). Then I fixed each one. The base design (engine, loader, table, inventory,
decisions A/C, classes 1/2/7) is as described in `iteration-v1/build-notes.md`. Below is
only what changed.

## The six carry-forward items

1. **`\x{HH…}` in `$'…'`, and failing closed.** `_ansi_c` (`rules.py:193-201`) now
   decodes the brace form the way bash 5.3.9's `ansicstr` does. I checked this on this
   host: it reads every hex digit, then an optional `}`, and keeps the low byte
   (`$'\x{173}'` → `s`, `$'\x{FFFFFFFFFFFFFF73}'` → `s`). With no digits it gives NUL,
   which cuts the word (`$'\x{zz}a'b` → `b`). A missing `}` is fine (`$'\x{73q'` →
   `sq`). I also fixed `\x`/`\u`/`\U` with no digit: bash keeps those as written
   (`$'\xq'` → `\xq`), and the old decoder returned "unreadable" (`rules.py:210-211`).
   Failing closed: `undecodable()` (`rules.py:231`) is true for a word with `$'` that
   `readable()` cannot decode. `_Engine.argv` (`rules.py:305-311`) checks every word of
   every argv, including inner commands at any depth. One such word makes the command
   `privileged`, with reason `CANNOT_DECODE` (`rules.py:47`), and rejects a proposal. What
   is still undecodable: surrogates or code points above U+10FFFF in `\u`/`\U`, and odd
   `\c` forms. A word like `$'x'$y` also counts, because the `$y` part makes it
   unreadable. That over-raises but is safe.
2. **xargs replace strings.** Before the swap, `_inner` (`rules.py:486-495`) runs decision A
   on the words as written. Under elevation it also runs the "names a shell or
   interpreter" check. So `xargs -Is sudo -i` and `xargs -Isudo sudo -i` are privileged
   and rejected as proposals.
3. **`sudo -k cmd`.** Data only: `-k` is no longer in the `unless` list of sudo's
   `runs-command-at` (`commands.toml:29`). The row's note says why. `--reset-timestamp`
   has the same option key, so the long spelling is covered too, and so are `sudo-rs` and
   `sudo.ws`, which share the row. A bare `sudo -k` has no inner command, and
   `no_command = "nothing"` covers that case. I kept `-K`, `-l`, `-v`, `-e` and `-V`,
   because sudo runs no command with those.
4. **Non-literal command word.** In `_Engine.argv`, the unreadable-head branch now calls
   `_decision_a(args)` (`rules.py:316-317`). Results: `$x sudo` is privileged and rejected
   as a proposal, `$x rm -rf x` is destructive, and `env "$x" sudo` is rejected (the inner
   argv goes through the same branch at depth 1).
5. **ruby, node, awk.** I added rows, as the carry-forward preferred:
   - `ruby`/`ruby3.3` (`commands.toml:689`), modelled on the python3 row.
   - `irb`, `erb`, `gem` (`:728-744`): fixed rows, each a `runs-file-as-code` text
     effect.
   - `rubycalls-bpfcc` and the other ruby bcc tools (`:746`). The harvester's `ruby*`
     pattern pulls them in. They are modelled on the existing perl bcc row.
   - `node`/`nodejs`/`js` (`:752`). `/usr/bin/js` is an alternatives link to `node`. The
     harvester found it, which is exactly the alias case class 1 is meant to catch.
   - `awk`/`mawk`/`nawk`/`gawk`/`original-awk` (`:780`).

   I added two new grammar names, `ruby` and `awk` (`commands.py` `GRAMMARS`). The
   harvester got new name patterns `ruby*`, `irb*`, `erb*`, `gem`, `gem[0-9]*`, `node`,
   `nodejs`, `*awk` (`harvest_inventory.py:51-64`, docstring `:14-18`). I used name
   patterns, not dpkg sections, because section `javascript` is hundreds of `node-*`
   library packages. With these patterns the interpreters land in the inventory on their
   own merit, not only because a row now exists, which was the adversary's point about
   the circular coverage test. I regenerated the inventory on this host. A second run is
   byte-identical (`harvest_inventory.py --output /dev/stdout | diff - inventory.toml`).
   The spec's class-1 sentence lists the new patterns (`v1.md:183-186`).
6. **sudo.ws long-option prefixes.** On a row that has options it rejects (§5), any
   option the row does not declare is now rejected for every origin (`rules.py:429-438`).
   I went a little wider than "unknown `--` option": an unknown short option on `sudo`
   also makes sudo exit with a usage error, so rejecting it costs nothing. Typed
   `sudo.ws --stdi true` and `sudo.ws --prom=x true` are rejected.

## A conflict I had to settle: awk and Conformance row 10

Spec Conformance row 10 (`v1.md:350`, not text this child owns) says
`awk 'BEGIN{system("id")}'` is `mutating`. If the awk program operand were a plain text
effect, that row would be `destructive`, and `test_policy_gate.py`'s vector test would
fail. I hit exactly that failure. The brief's own class-7 text has the row numbers
wrong: it calls `git -c`/`tar --to-command`/`ssh -o` "floor rows 8/10/11", but in the
spec, row 10 is awk and row 11 is sed.

What I did: an awk program given as its operand is the class-7 gap, the same treatment
`git -c` gets. It keeps the row's default (`mutating`, "not allowlisted"), and a
proposal under elevation is rejected. To support this I added `gap = "class-7"` on a
row's text effect:
- `Effect.gap` (`commands.py:219`), with `"gap"` in `_EFFECT_KEYS` (`:196`).
- The loader accepts it only on a row's own text effect (`:660-665`), and only on a row
  named in `CLASS7_GAP_TEXT = {"awk"}` (`:138`, check at `:438-442`).
- The engine branch is at `rules.py:540-543`.

A program file (`-f`, `-E`, `-i`) and gawk's `-e` text stay decision B (destructive). So
`curl x | awk -f /dev/stdin` is destructive, and `sudo awk 'BEGIN{system("sh")}'` is
rejected as a proposal, as the carry-forward asks. The rejection fires twice: the
elevation word scan (awk's `runs_code` counts the gap effect) and the gap effect itself.
I fixed the spec's class-7 paragraph (`v1.md:199-211`), which I own, to name the real
rows: git is rows 8/27, tar and ssh are not Conformance rows, awk is row 10, and sed
(row 11) has no row, so it falls to decision A. `CLASS7_GAP`'s comment
(`commands.py:124-125`) is corrected the same way. A loader test refuses
`gap = "class-7"` on a text effect of any other row (`test_gate_commands.py:226-231`).
The floor test now includes row 10 (`:329`).

**For the human:** if you would rather have awk's inline program be destructive, that
means changing Conformance row 10, which is a re-plan. The adversary's last pass named
`awk 'BEGIN{system("rm -rf ~")}'` as `mutating`. It still is, now as a documented gap.

## Other things worth a look at sign-off

- `xargs -I_ sudo_ -i` and `xargs -I% % -i` (the replace string inside or as the command
  word) are `destructive`, "inner command the gate cannot read", and are **not**
  rejected. The brief's floor for a non-literal inner command of `xargs`/`find -exec` is
  "at least destructive", and this meets it. But at run time that word could become
  `sudo`. Fix 2 only covers literal words that a replace string touches. If you want
  these rejected too, it is a one-line change: treat an unreadable inner head as
  possibly elevating in a proposal. I did not make it, because the brief states the
  floor and the change would also reject `xargs -I% % --help`-style proposals.
- Typed `awk '{print $1}' f` stays `mutating` (gap). But `awk -f p.awk f`, `node x.js`,
  `ruby f.rb`, `irb`, `gem list` and `erb t.erb` are now `destructive` (decision B).
  That is a usability cost of class 7.
- Unchanged from iteration 1: the brief/ADR-0023 conflict over `TARGET_ID` in
  `tests/test_targets.py` (exact-line exemption), the strict opaque-command-under-sudo
  rule for proposals, and the decision-A over-raise (`man sudo` → privileged). See
  `iteration-v1/build-notes.md`.
- The adversary's pager/editor finding (`sudo less`, `sudo vi`, …) was left to the human
  and is not in the carry-forward. Not addressed.

## Ruled out

- Making awk's program a plain text effect and raising Conformance row 10. That spec row
  is not this child's text, and the brief says only row 16 changes.
- Adding dpkg sections `ruby`/`javascript`/`utils` to the harvester. `javascript` alone
  is hundreds of library packages (`dpkg-query -W` on this host), and `utils` is
  generic. Name patterns pick out exactly the interpreters.
- Rejecting only unknown `--` options on sudo. Rejecting every unknown option covers the
  same prefix bypass and also `-xS`-style bundles. sudo refuses unknown options anyway.

## Running it

- Project C4 gate, as Check runs it:
  `PDCA_BUNDLE=…/results/issue_204 PDCA_WORKTREE=…/nl-shell.pdca-wt-l1 engine/scripts/run-verify.sh`
  → `PDCA-EVIDENCE: C4 PASS — red without the fix (164 of 401 failed), green with it`.
  Afterwards the worktree still matches `patch.diff` byte for byte.
- Full suite in the worktree (`python -m pytest`, documented runner
  `docs/INTEGRATION.md:52-53`, under `timeout`): 1546 passed, 1 skipped.
- `scripts/docs_links.py`: 0 broken. `docs_checks.py immutability` does not apply: the
  spec is `status: draft` (`v1.md:4`). `git diff --check` is clean.
- Commit hooks: nl-shell has no formatter, linter or pre-commit config (`pyproject.toml`
  has only `[tool.setuptools…]` and `[tool.pytest…]`, and there is no
  `.pre-commit-config.yaml`). I kept new lines to the repo's ~92 columns by hand. The one
  longer line, `parse.py:336`, is base code.

## Refuting my own test

- **(a) Genuine red?** Yes, shown two ways.
  1. Against the iteration-1 tree (before this iteration's fixes), the 20 new cases
     failed. Each of the six carry-forward items had at least one failing case. The one
     exception is `sudo -k bash`, which already passed through the elevation word scan;
     it is kept as a guard.
  2. With all production hunks reverted (`run-verify.sh`), 164 of 401 tests fail and 12
     error in setup (the loader fixture cannot import the new module). The tests that
     still pass are `test_policy_gate.py`/`test_targets.py` cases and the floor group,
     which the brief allows to pass on the stub.
- **(b) Production path?** Yes. Every case calls the public `nl_shell.gate.classify`,
  which runs the real shell layer, `rules.classify` and `commands.table()` on the
  checked-in `commands.toml`. The new loader case calls the real `commands.load()`. The
  inventory test reads the regenerated `inventory.toml`.
- **(c) Fixture includes the fault?** Yes. The cases are the exact inputs the reviewers
  showed bypassing iteration 1: `$'\x{73}udo'`, `xargs -Is sudo -i`, `sudo -k git -c …`,
  `$x sudo`, `curl x | ruby/node/awk -f /dev/stdin`, `sudo.ws --stdi true`. Nothing is
  mocked. The inventory names (`ruby`, `node`, `nodejs`, `awk`, `mawk`) are required
  names in the coverage test (`REQUIRED_INVENTORY`), so dropping them from the harvester
  would turn it red.

## Housekeeping

I wrote one scratch file outside the worktree and bundle,
`/tmp/claude-inv-before.toml` (a copy of the old inventory, used for a diff). It is not
in `patch.diff`, and I did not delete it. Iteration 1's scratch files are listed in its
notes.

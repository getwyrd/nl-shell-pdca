# Build notes — issue 204 / gate-command-table-engine (iteration 5)

Target: eduralph/nl-shell @ main (`1a1e980`). Worktree: `$PDCA_WORKTREE`
(`/home/eddie/nl-shell/nl-shell.pdca-wt-l1`). Line numbers are in the patched tree
(base + `patch.diff`).

## Starting point

The iteration-4 carry-forward says "Rebuild the same slice; fix the v4 Check findings,
keep the v3 brief's design." So I applied `iteration-v4/patch.diff` unchanged onto
`1a1e980` and built only the five findings on top. I read `iteration-v4/build-notes.md`
and the v4 gate logs (C4 and T3 both failed on the one timing test
`tests/test_policy_gate.py::test_rule5_size_cap_at_8_kib[$[]`, 5.9 s against a 5 s
limit). Everything in the v3/v4 notes about the rest of the design still holds; this
file covers the iteration-5 delta.

## The five findings

### 1. Slowdown in the bracket-glob repair (C4/T3 red)

Profiled 8 KiB of `$[`: 820 nested ERROR nodes, each calling `_word_start` (scan back
to a word end), `_raw_words` (scan forward to the end of the command) and
`_unquoted_bracket` (`"]" in word[i+2:]` for every `[`). All three were O(n) per node,
so O(n²) overall: 4.7 s of the 5.2 s run.

Fix (`src/nl_shell/gate/parse.py`):

- `_SourceWords` (`parse.py:625`), built once per source and only when a node needs it
  (`Walker.source_words`, `parse.py:525`):
  - `starts`: where the word holding each byte begins, one pass;
  - `link(p)`: one word read from `p`, cached (`links`), so each word is read once and
    the words of a simple command are a chain of cached links;
  - `seen`: every place looked at, hit or miss (the carry-forward's "cache misses too");
  - `segments_in` (`parse.py:695`): the places a simple command may start inside a node,
    each handed out once (a skip list with path compression), so nested ERROR nodes do
    not walk the same places again;
  - a byte bound: more than 32 × the input read raises `GateFailure` (decision C), so no
    crafted input can make the reader slow; it never fires on the suite.
- `_unquoted_bracket` (`parse.py:713`): one pass; `rfind("]")` once instead of a slice
  per `[`.
- Words handed to the command layer count against the walker's work budget
  (`parse.py:770`), the same budget the walk already has.

Timings, proposal origin, 8 KiB (v4 → now): `$[` 5.9 s → 0.16 s, `[$[` 19.3 s →
0.09 s, `a=(` 0.49 → 0.17 s, `{ sud[o] -i; }` 0.02 s. The 5 s test is unchanged.

### 2. `coproc` reaches its command word

tree-sitter-bash reads `coproc sud[o] -i` as a simple command named `coproc` (checked
the tree). So I gave it a wrapper row (`targets/ubuntu-26.04/commands.toml:1244`,
`runs-command-at`, at 0). The command bash starts there reads a pipe the shell writes to
(`echo pw >&${COPROC[1]}`), so I added one loader key, `piped` on `runs-command-at`
(`commands.py:194`, `:218`, `:668-672`, `:693`, docstring `:45`), and the engine gives
the inner command a pipe stdin (`rules.py:764`). Result: `coproc sudo true` is rejected
for every origin (pipe into sudo, §5); `coproc true` stays `mutating`. The row has no
options, so `coproc --x` is "option the gate does not know" (bash would run a command
named `--x`; a raise). The row joins the wrapper property test automatically (it has a
`prefix`).

Ruled out: treating `coproc` only as a reserved word in the bracket repair. That covers
`coproc sud[o]` inside an ERROR, but `echo pw | coproc sud? -S true` has no ERROR at all,
so only a row reaches it. (`coproc` is in the repair's reserved-word list as well, for
the ERROR case.)

### 3. Bracket glob after `{`, `(`, `if`, `f()` …

The ERROR node for `{ sud[o] -i; }` starts at `{`, and v4 only looked at the word
holding the node's start. Now `_bracket_command` (`parse.py:740`) checks the word
holding the node's start and the first word after every place a simple command may
start inside the node (after an unquoted-or-not `;&|()<>` or newline), skipping reserved
words (`_RESERVED_LEAD`, `parse.py:618`: `{ } ! if then else elif do while until time
coproc`) and assignment words (`_ASSIGNMENT_WORD`, `parse.py:622`). The place list is
quote-blind, so a `;` inside quotes can add a place; the only effect is an extra check
of the word after it (a possible raise, never a lower verdict). Skipping assignments
also stops `a[0]=1 ls` from being read as a glob command word (it stays `mutating`).

### 4. Attached / `=` text-option values

`_text_scan` used to scan the raw argument words, so `env -S'sudo -i'` was the one word
`-Ssudo -i`. Now the parsed rows pass the parsed option values too
(`rules.py:712`, via `_text_units`, `rules.py:539`): `-S'…'`, `--split-string='…'`,
`-c'…'`, `--command='…'` all reach the scan as the value the row's grammar reads.

The test `test_text_option_attached_values_are_scanned` (`tests/test_gate_commands.py:942`)
walks the table: every value-taking option with a `runs-text` or `stores-code` effect
(not the class-7 gap), in its attached short form and its `=` form: 52 forms over 18
rows (`awk bind complete env flock gdb gjs node perl ptyxis python3 ruby runuser screen
script strace su tar`). Each is checked as a proposal with `'sudo -i'` (rejected) and
typed and as a proposal with `echo pw | … 'sudo -S true'` (rejected, §5 reason).

### 5. Unreadable command word inside code text

`_text_scan` (`rules.py:566`) now also runs decision D over the code text. The code text
is found per effect (`_text_units`, `rules.py:539`), not over every argument:

- an option's value (attached, `=`, or the next word);
- for a value-less text option (`bash -c`), the first operand (or the inner words for
  `run0 --via-shell`);
- the operand a row's text effect names (`if = "operand"`, `at`);
- the words `watch` joins (`joined-special`);
- else every operand (unconditional row-level text effects); on a fixed row (`eval`),
  all its arguments (`rules.py:453`).

Only `runs-text` and `stores-code` count (`_runs_code_text`, `rules.py:338`): a
`runs-file-as-code` operand is a file name, not code. In each unit, cut into commands at
separators (`_segments`, `rules.py:324`), the first word past reserved words and
assignments is a command word; if it is wholly not literal, or holds `$`, a glob,
a backtick or a brace expansion (`_UNREADABLE_IN_TEXT`, `rules.py:350`), it goes through
the same `_fail_closed` path as any decision-D word (no second path), with reason
"command word the gate cannot read in code the gate cannot read" (`rules.py:69`). So a
proposal is rejected, a fed stdin rejects, and the words after it are read for sudo's
rejected options, for every origin.

Why per unit and not every argument: my first sketch scanned every argument word's
first token. That made `python3 x.py *.csv` and `bash -c 'ls' *.c` `privileged` (a glob
argument read as a command word). The unit version leaves them alone; the guard test
`test_text_scan_reads_only_command_words` (`:1006`) pins `bash -c 'ls *.c'`,
`python3 x.py *.csv`, `perl -e 'print 1'` at `destructive`, no D reason.

Costs (all raises over v4, none below `main`):
- `bash -c "$v"` and `eval "$v"` are now `privileged` typed (were `destructive`), and
  rejected as proposals. `$v` may be `sudo -i`. The existing decision-B tests use a
  floor, so they still pass.
- D runs for every text grammar, not only shell ones, so `perl -e '$x=1; print'`
  (first token `$x=1`) is `privileged` typed, rejected piped or as a proposal. I kept
  it for every grammar because `python3 -c 'os.system("sud? -S true")'` is a real way
  to run sudo; the segment cut at `(` puts `sud?` first there.
- Quotes inside the text are removed by `shlex` before the check, so a single-quoted
  `'$x'` inside the text counts as unreadable too.

## Spec / threat model

- `docs/design/specs/policy-gate/v1.md` §4.1 item 6 (`:194-205`): the ERROR that starts
  before the word, the reserved-word skip, and `coproc`'s row with a pipe stdin. Item 9
  (`:262-276`): parsed option values are scanned, and decision D over command words in
  the code text.
- `.oss-scanner/threat_model.md:204-224`: same points. The "What must hold" lines
  (`:115-130`) are not touched.

## Runs (project runner only)

- `engine/scripts/run-suite.sh` (T3) on the final tree: **1643 passed, 1 skipped**,
  `PDCA-EVIDENCE: T3 PASS` (includes `test_rule5_size_cap_at_8_kib[$[]`, which failed in
  v4).
- `engine/scripts/run-verify.sh` (C4) with `PDCA_BUNDLE` set, worktree at base +
  patch as uncommitted changes: **red leg 251 of 498 failed** (plus 12 setup errors),
  green with the fix, `PDCA-EVIDENCE: C4 PASS`. Afterwards `git diff 1a1e980`
  (intent-to-add for new files) is byte-equal to `patch.diff`.
- Iteration-5 delta alone: put the v4 `src/` and `targets/` back
  (`git checkout <v4 baseline> -- src targets`), kept the v5 tests, ran `run-suite.sh`:
  **23 failed**: the wrapper property test (no `coproc` prefix), 2 of the 8 timing cases
  (`$[`, `[$[`), the coproc test, 3 of the reserved-word cases (`{ … }`, `f() { … }`,
  `true; { … }`), the group §5 pipe case, the attached-value property test, all 8
  text-D cases, all 5 text-D §5 cases, and `test_policy_gate.py`'s `$[` timing test.
  Then restored v5.
  - Cases that passed on v4 too (kept as guards): `( sud[o] -i )`, `if …`, `while …`,
    `! sud[o] -i`, `A=1 sud[o] -i`, `{ sud[o] -S true; } <<<pw`, the other six timing
    inputs, and the three over-raise guards.
- Commit-readiness: the target has no formatter, linter or pre-commit config
  (`pyproject.toml` has none; no `.pre-commit-config.yaml`; CI runs pytest,
  `docs_links.py` and `docs_checks.py immutability`). `scripts/docs_links.py`: 0 broken.
  The spec is `status: draft`, so the immutability check does not apply. No new line in
  `src/` or `tests/` is over 88 columns (the existing style).

## Refuting my own test

- **(a) Genuine red?** Yes. Full revert (C4 red leg): 251 of 498 fail. Iteration-5
  revert only (v4 engine and data, v5 tests): 23 fail, covering all five findings (the
  timing cases fail on time, measured 5.9 s and 19 s on v4).
- **(b) Production path?** Yes. Every case calls the public
  `nl_shell.gate.classify(cmd, origin=…)`: the real tree-sitter-bash parse, the real
  walker (findings 1 and 3 live there), `rules.classify` (findings 2, 4, 5) and the
  checked-in `commands.toml` (finding 2's row). No mocks; the only monkeypatching is the
  loader root in the decision-C / fixed-location tests, as the brief prescribes.
- **(c) Fixture includes the fault?** Yes. The cases are the carry-forward's own strings
  (`coproc sud[o] -i`, `echo pw | coproc sud? -S true`, `{ sud[o] -i; }`,
  `echo pw | { sud[o] -S true; }`, `f() { sud[o] -i; }; f`, `env -S'sudo -i'`,
  `env --split-string='sudo -i'`, `script -c'sudo -i'`, `script --command='sudo -i'`,
  `eval 'sud? -i'`, `bash -c 'sud[o] -i'`, `env -S 'sud? -i'`) and the 8 KiB `$[` and
  `[$[` inputs that timed out, against the full table with the sudo rows present. The
  attached-value test is generated from the table, so it covers every such option, not
  a hand-picked few.

## Not done / out of scope

- Not decided at the v4 sign-off and left as the brief has it: opaque wrappers with no
  row (`chrt 1 sud? -i`, `ionice`, `taskset`, `nsenter` …) and the double-unquoting
  `eval "\$'\\x73udo' -i"` case (child-2, #205).
- Earlier carry-forward exclusions stand: `hash -p` / `BASH_CMDS` (#206); destructive rows
  for `git checkout`, `stash drop`, `branch -D`, `rsync -e`.
- `coproc NAME { … }` / `coproc NAME ( … )` (the named compound form): not exercised;
  how tree-sitter parses it was not checked.
- No new `gate-vectors.toml` rows for the iteration-5 cases (the brief asks for vectors
  only for the decision-D Conformance rows, added in v3).
- No PR pushed or opened.

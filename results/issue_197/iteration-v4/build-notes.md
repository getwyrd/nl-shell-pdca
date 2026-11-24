# Build notes — issue 197 (Do, pass 4)

## 0. Read this first: what was built is child-1, not the whole brief

`brief.md` (pass 4) says the command layer is split into three children, and that its own
top-level fields "are **not** the criterion any child is checked against". Each child's
criterion is in `split-proposal.md`. But `split --accept` has not run: there are no child
bundles under `results/`, and `split-lineage.json` still describes #197 itself. The driver
sent this parent bundle to Do.

I did **not** build the union (classes 1–7, recursion, budget, B′). The human split it on
purpose after three oversized attempts (v3 was 203 KB). Instead I built **child-1
(engine and table)**:

- it is wave 1 of the chain;
- it targets `main` directly;
- it uses the test path this bundle names (`tests/test_gate_commands.py`).

I built it to child-1's Success criterion (`split-proposal.md:149-237`) and to its scope
and spec-ownership rules (`:138-148`, `:256-279`).

**Consequence for Check.** Judged against `brief.md`'s top-level Success criterion, this
patch is incomplete **by design**. None of these are in it:

- the class 3, 4, 5 and 6 cases;
- recursion and decision B′;
- the shared work budget;
- the `parse.py` `shell_layer(budget=)` seam.

They belong to child-2 and child-3. If the human wants this bundle checked against
child-1, run `split --accept` and move this patch to the child-1 bundle. Otherwise, read
this bundle's Check as a child-1 Check.

This is a process or brief defect, not an external dependency, so I have not used the
NEEDS-HUMAN external-dependency marker. It still needs the human's call at sign-off.

## 1. What changed (paths and lines are in `$PDCA_WORKTREE`, base `main` `1a1e980`)

### `src/nl_shell/gate/commands.py` (new): the loader

- `ROOT = targets.TARGETS_ROOT` (`:38`) is the test seam.
- `load()` (`:245`) takes no argument. It reads `ROOT / TARGET_ID / "commands.toml"`
  (`path()`, `:240`) and refuses a resolved path outside `ROOT`. This mirrors
  `targets.py:153-155` (the plain-id check, the `is_relative_to` refusal, the
  missing-file error).
- `table()` is cached (`:272`); `clear_cache()` is at `:277`.
- `validate()` (`:284` on) is strict. It refuses:
  - unknown keys, with an explicit message for `raw` (`_check_keys`, `:341`);
  - unknown effect kinds, conditions, `at` forms and grammars;
  - a text effect with no grammar;
  - a row with `runs-command-at` or `runs-stdin-as-code` that does not declare both
    `no_command` and `terminal_stdin`;
  - a `runs-command-at` row with no `prefix`;
  - an operand-position inner command with `permute = true`;
  - a class below `mutating`;
  - `class_7_gap` on any (name, option) outside `CLASS_7_GAP` (`:97`), which mirrors the
    spec's class-7 list.

### `src/nl_shell/gate/rules.py` (rewritten): the engine, replacing the stub at `rules.py:26-28`

- `classify(invocation, origin)` (`:113`) is the entry point. It turns `CommandsError`
  into `GateFailure`, which the existing sink at `__init__.py:143-157` makes decision C.
- `_command` (`:131`) looks the command word up by its last path component. A word that
  is non-literal only because of a tilde (`_fixed_path`, `:153`) is still looked up.
- `_decision_a` (`:165`) reads each argument word, its basename, and the part after `=`.
- `_parse` (`:327`) and `_option` (`:442`) form one argv parser. It handles:
  - short bundles, attached and `=` values, and unique long prefixes;
  - `+` options, `--`, `max_options`, `final`, chmod modes and tar's dashless first word;
  - subcommands, with option inheritance;
  - inner commands at an operand (skipping `NAME=VALUE`), `until:` captures (`find -exec`)
    and `rest:` captures (`gdb --args`, `x-terminal-emulator -e`).
- A non-literal word in option position counts as a possible option only if it can expand
  to one (`_may_be_option`, `:405`). `~/x` and `a$b` cannot; `"$P"`, `*` and `{}` can.
- `_report_options` (`:248`) handles undeclared or unreadable options:
  - they make the command `destructive`;
  - on an elevating row, a proposal with one is rejected;
  - on a row with `rejected` options, the command is rejected outright (`sudo "$P"`,
    `sudo --st`, `sudo --stdin=x`).
- `_effects` (`:588`) applies each active effect:
  - `runs-command-at` recurses through `_inner` (`:701`), with the inner stdin the row
    declares (`inherit`, `pipe`, `null`, `terminal`);
  - every text effect is decision B;
  - `reads-terminal` rejects a pipe, a literal or unknown stdin, or a `/dev`/`/proc`
    stdin file (`_plain_file`, `:683`);
  - "opens a shell" comes from `no_command`, an `opens-shell` effect, terminal stdin into
    a code-reading row, or a stdin path as the script. It propagates up through wrappers.
    An elevating row plus a shell is "opens an interactive root shell", rejected as a
    proposal.
- `MAX_NESTING` (`:46`) bounds wrapper depth: 1000 nested `env`s are decision C. The word
  backstop is at `:49`.

### The other files

- **`src/nl_shell/gate/__init__.py:196`**: `rules.classify(invocation, origin)`. That is the
  only code change in this file; the docstring line about the stub is updated too.
- **`src/nl_shell/gate/parse.py`**: `lex_word` decodes ANSI-C `$'…'` (`:254-264`, the new
  `_ansi_c` at `:304`). A NUL, a `\xHH` or octal byte ≥ 0x80 (a raw byte that may be part
  of a UTF-8 sequence), a bad code point, or a trailing `\c` leaves the word non-literal.
  Nothing else in `parse.py` changed.
- **`targets/ubuntu-26.04/commands.toml`** (new): 82 rows and 180+ names, grouped as:
  - elevation: the sudo family, sudoedit, su, pkexec, doas, run0, machinectl
    shell/login, systemd-run;
  - wrappers;
  - shells and text-runners, which cover class 7's named list;
  - the setuid and capability binaries that do not elevate;
  - destructive commands;
  - the floor rows git, tar and ssh, with `class_7_gap`;
  - the §3 builtins.
- **`targets/ubuntu-26.04/inventory.toml`** (new, generated): 95 names.
  `scripts/harvest_inventory.py` (new, in the style of `gen_unicode_tables.py`) writes it
  and records the host `VERSION` line. A second run on this host gives the same file.
- **`targets/gate.toml`** (new): the fixed target id. See §2.
- **`targets/ubuntu-26.04/gate-vectors.toml`**: I appended rows 8, 9, 17, 18, 21 (×3), 22,
  24, 26, 27, 29 and 32. I also **edited row 16** (see §3).
- **Spec `docs/design/specs/policy-gate/v1.md`** (status draft, so editable):
  - a §4 row-9 derivation;
  - a new §4.1 (table, rows, decisions A and C, classes 1, 2 and 7, inner commands, the
    "text is decision B" placeholder, ANSI-C words);
  - a Versioning sentence.

  It does not claim recursion, B′, or classes 3–6.
- **Threat model `.oss-scanner/threat_model.md`**: the "command layer … still stubs"
  sentence is replaced with what child-1 does. It says outright that text is not read yet.
- **`tests/test_gate_commands.py`** (new) and **`tests/test_policy_gate.py`** (expectations
  raised; see §3).

## 2. One deliberate departure from the brief: where `TARGET_ID` lives

The child-1 brief asks for `TARGET_ID = "ubuntu-26.04"` as a literal in the loader. That
breaks ADR-0023 ("code names no OS"), which `tests/test_targets.py:677-689`
(`test_no_os_name_in_package_code`) enforces. My first build had the literal and that
test went red.

I kept what the brief is after:

- a module constant;
- one fixed target;
- not chosen from `/etc/os-release`, the environment, the cwd or a config file;
- `load()` takes no path;
- the test seam is a monkeypatched module root.

The id now lives in reviewed data. `TARGET_ID = _fixed_target_id(targets.TARGETS_ROOT)`
(`commands.py:43-58`) reads `targets/gate.toml` once at import, from the repository's own
folder (not `ROOT`). A missing or invalid file gives `None`, and then every command is
decision C (tested in `test_decision_c_without_the_fixed_target`).

Rejected alternatives:

- editing the ADR test to allow one line (that weakens a guard);
- spelling the string so the regex misses it (that games the test);
- taking "the only folder under `targets/`" (the drift the brief forbids).

**The human should confirm this departure at sign-off.**

## 3. Expectations I raised in existing files (raise only, except one corner, flagged)

### `tests/test_policy_gate.py`

All of these are higher class, or newly rejected, compared to the stub. Each follows from
a §4/§5 rule in the brief:

- `cat <<E | sudo tee`, `cat <<E | doas id`: now rejected with the pipe reason (§5;
  the brief's child-1 list has both);
- `curl x > >(sh)`: now `destructive` (decision B);
- `cat <<E > >(sudo tee)`, and `f(){ sudo tee; }` fed by a pipe: now `privileged`;
- `f(){ sh; }; curl x | f`, `bash <<<'rm -rf ~'`: now `destructive`;
- `rm -rf />/dev/null`, `rm -rf ~>/dev/null`: now `destructive`;
- `sudo rm -rf /etc>x`: now `privileged`;
- `exec </tmp/x; sudo tee`: now rejected (stdin not proven);
- `while …; exec <x`: now `session-altering`;
- `$'\x72m' -rf ~`: now `destructive` (the scope line names it);
- `$(echo rm) -rf ~`: now `destructive` (decision A reads `echo rm`);
- `declare -x A=1; unset A`: now `session-altering`.

The three monkeypatched `rules.classify` fakes now accept `origin`.

In `test_rule3_literal_flag`, `cat $'x'` moved from the non-literal list to the literal
list. `cat $'\x80'` takes its place on the non-literal side. I also added a decode check.

### Vector row 16

The file says "appended rows only", but row 16 asserted exactly `mutating`, "command word
is not a literal". With ANSI-C decoding, that is `destructive`, "rm -r". The spec's row-16
text ("mutating at least … never read-only") still holds.

### Corner to review (a lowering)

Because `$'…'` is now literal, a redirect target like `echo x >$'out'` is now accepted
like `>out`. Before, it was rejected as "target is not a literal path". `>$'/dev/fd/3'`
and `>$'3'` are still rejected (by path and by the descriptor rule). This matches bash.
It is the only place the change lowers anything, and no test covered it.

### Row 33

`alias ll='ls -l'` is `destructive` in this child, because stored code is decision B
(child-1 brief: "every text effect … is decision B"). The spec table says
`session-altering`. §4.1 item 8 now records this as a compatible raise until the
text-reading layer lands. I added no row-33 vector.

## 4. Choices and what I ruled out

- **No per-command code.** No code path names a command. `watch`, `xargs`, `find`, `env`,
  `kill` and `tar` are handled by generic row keys:
  - `joined` (watch);
  - `appends` and `placeholder` (xargs);
  - `until` with terminators (find);
  - `skip = "assignments"` (env);
  - `max_options` and `signal_option` (kill);
  - `bundle_first` (tar).

  I did not open or port v1–v3 (`raw` rows, `_PIECE_SPLIT`).
- **Recursion entry point.** Child-2 asks Do to pick one. This child has no recursion.
  `rules.py` imports only `commands` and `parse`, never `gate/__init__.py`.
- **Decision A as written.** An argument that names an elevating row makes the command
  `privileged`, and a proposal is rejected, even for `echo sudo`, `which sudo`,
  `grep sudo /etc/group` or `man sudo`. An argument that names a destroying row (rm, git,
  find, kill, systemctl…) makes it `destructive`.

  That is the agreed decision. It is noisy until #198 allowlists `echo`, `grep`, `man` and
  similar (decision A applies only to commands with no row and no allowlist entry). Worth
  knowing before using the REPL on this build.
- **Non-literal operands.** A glob or expansion operand (not a plain `~`) makes `rm`
  destructive. It also matches `operand:`/`operand-prefix:` conditions: `kill -9 "$p"`
  is destructive, and `git push origin "$ref"` is treated as a possible force push.
  Fail-closed.
- **Unknown wrappers and interpreters not on this host** (`node`, `ruby`, `lua`, …) have
  no rows. Decision A still catches `foo sudo …`, but not `sudo node` as a root REPL.
  That is outside class 1 (which is inventory-based) and outside class 7's named list.
  It could be a follow-up.
- **Accepted gaps inside this child's classes.**
  - Class 7, by the brief: `foo 'sudo -i'`, `git -c`, `tar --to-command`, `ssh -o`.
  - Text, which is child-2's: `su -c bash`, `sudo bash -c 'sudo -i'` and
    `script -c 'sudo -i'` are `privileged`/`destructive` but not root-shell rejections
    until text is read.
  - GTFOBins escapes (`sudo vi`, then `:!sh`) fit no class here. That is a follow-up.

## 5. Running it

I used the project's runners with `PDCA_WORKTREE` set.

- **`engine/scripts/run-verify.sh`**: `PDCA-EVIDENCE: C4 PASS — red without the fix (46 of
  211 failed), green with it`. Its bundle tests were `tests/test_gate_commands.py` and
  `tests/test_policy_gate.py`.
- **`engine/scripts/run-suite.sh`**: whole suite. The result is recorded in §7.
- **Formatter or commit hook**: the target configures none. There is no pre-commit
  config, no ruff or black config, and CI runs only `pytest` and the docs checks.
  `python3 -I scripts/docs_links.py` reports 0 broken links. The spec is `status: draft`,
  so the immutability check allows edits. I wrapped my lines to ≤ 95 characters, which
  is the existing code's practice.
- CI runs on GitHub's ubuntu-latest, not 26.04. No new test runs a host binary: the
  inventory and table are checked-in files, and the harvest script is not run by tests.

## 6. Refuting my own test (forced questions)

**(a) Genuine red? Yes.** `run-verify.sh` reverted the production hunks (`src/`,
`targets/`, `scripts/`) and kept the tests. 46 tests failed or errored, including:

- every class 1, class 2, §4, §5, decision A/B/C, fixed-location and §3 test in
  `test_gate_commands.py`;
- for example `test_spec4_privileged` and `test_spec5_sudo_rules` (assertion failures on
  `mutating`), and `test_class1_*` (no inventory).

Only `test_floor_class7_accepted_gap` passed on the red leg. The brief says it may.
`nl_shell.gate` and `commands` are imported inside the test functions, so the red leg
failed at run time, not at collection (`import/collection errors 0`).

**(b) Production path? Yes.** Every behavioural case calls the public
`nl_shell.gate.classify(cmd, origin=...)`, which runs the real walker, `__init__`'s
pipeline, `rules.classify` and the real checked-in `commands.toml`. The property tests
iterate over the real table (`commands.load()`), not a fixture. Only the loader-refusal
cases call `commands.validate()` on small inline dicts, and that is the production
validator.

**(c) Fixture includes the fault? Yes.**

- The missing and invalid table cases monkeypatch the loader's `ROOT` to a `tmp_path`
  with no table, a broken one, or one with `raw`, and assert decision C.
- The fixed-location test plants a "sudo is harmless" table in the cwd, in `$HOME`, and
  behind `NL_SHELL_COMMANDS`, `NL_SHELL_TARGETS` and `XDG_CONFIG_HOME`, then shows
  `sudo -i` stays `privileged`.
- The outside-the-root test uses a real symlink escaping the root.
- The property tests run over every row, including the elevating ones.

## 7. Whole-suite result

`engine/scripts/run-suite.sh`: `1408 passed, 1 skipped … PDCA-EVIDENCE: T3 PASS — nl-shell
suite green`.

One small edit landed after that run started: `MAX_WORDS` became a pure backstop,
`MAX_NESTING * MAX_WORK`. Only `tests/test_gate_commands.py` and `tests/test_policy_gate.py`
import the gate, and both pass on the final tree. The final C4 run on the regenerated
`patch.diff` gives `C4 PASS — red without the fix (46 of 211 failed), green with it`.

Patch size is about 173 KB. Most of it is data and tests:

- `commands.toml`: 53 KB;
- `rules.py`: 29 KB;
- `commands.py`: 24 KB;
- the new test: 21 KB;
- `inventory.toml`: 13 KB;
- spec and threat model: 11 KB.

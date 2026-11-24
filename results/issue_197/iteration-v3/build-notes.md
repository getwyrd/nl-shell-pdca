# Build notes — issue 197 / ast-policy-gate-command-engine (plan pass 3)

Target: eduralph/nl-shell @ main (`1a1e980`). Worktree `$PDCA_WORKTREE` =
`/home/eddie/nl-shell/nl-shell.pdca-wt`. Line numbers below are in the patched tree.

## What the patch does

One engine over one reviewed table, with the seven class rules built into the engine and
the row format instead of into per-command code.

| File | Change |
|---|---|
| `src/nl_shell/gate/parse.py:511-517, :537-538, :1081-1089` | The one parse.py change in scope: `Budget` (a shared counter); `Walker.visit` counts into it; `shell_layer(source, *, budget=None)`. `None` gives today's per-call budget. |
| `src/nl_shell/gate/commands.py` (new) | Loader for `targets/<id>/commands.toml`. No path argument, no env/cwd/home/config read. Refuses a resolved path outside `TARGETS_ROOT` (`:326-335`, mirrors `targets.py:153-155`). Cached (`_load`, `cache_clear`). Validates every key (`raw` refused, `:399`); requires `no_command` + `terminal_stdin` on any mode that runs a command/script/stdin (`:600-606`); `class-7-gap` only on the spec's named options (`CLASS7_OPTIONS`, `:99`); every annotated field carries an `example` template the tests use (`fields`, `:757`). |
| `src/nl_shell/gate/rules.py` | Replaces the stub (`main:rules.py:26-28`). `classify(invocation, *, origin, recurse)` (`:138`), `assignment(...)` for walk-recorded assignments (`:147`), `table()` → decision C (`:111`). The engine `_Engine` (`:217` on): argv parse (`row`, `option`, `operand`, `finish`, `:304-576`), decision A (`word_a`, `:285`; `possible`, `:268`), decision B (`stdin_code`, `text`, `expansions`, `:578-673`), class 3 (`arith`, `name_field`, `:675-700`), class 5 (`write`, `declare`, `:701-756`), class 6 (`stored_value`, `:758`), grammars (`env_split`, `:836`; `_backticks`, `:912`; `_bind_x_command`, `:942`). The §3 name lists and `system_path` moved here from `__init__.py` so `rules` never imports `gate` (`:45-80`, `:119`). |
| `src/nl_shell/gate/__init__.py:147-245` | `_classify` restructured into `_Run.text` (the whole §1 pipeline, unchanged step order from `main:__init__.py:159-210`), called for the top-level command and again for inner text. `_Run` is the `rules.Recurse` callback (`bash`, `words`), holds the shared `Budget` and a nesting cap (`MAX_NESTING = 16`, `:56`). `rules.table()` is loaded first so a bad table is decision C for every command (`:149`). `_assignments` now also classes stored-code values (`:270-273`). Inner text whose tree is untrusted is decision B (`:219-221`). |
| `targets/ubuntu-26.04/commands.toml` (new) | 90 rows / 164 names: sudo family, su, pkexec, doas, run0, systemd-run, machinectl, shells, busybox (applet = inner command), screen, tmux, terminal emulators, interpreters, gdb, at/batch, sg/newgrp, wrappers, builtins, variable builtins, destructive commands, git/systemctl subcommands, and fixed rows for every non-elevating setuid/cap binary. |
| `targets/ubuntu-26.04/inventory.toml` (new, generated) + `scripts/harvest_inventory.py` (new) | 73 names. Re-running the script on this host reproduces the file byte for byte (checked: `cmp` clean). |
| `targets/ubuntu-26.04/gate-vectors.toml` | Appended rows only (rows 8, 9, 17, 18, 21×3, 22, 24, 26, 27, 29, 32, 33, and `sudo -i` both origins); header updated to say #197 rows landed. |
| `docs/design/specs/policy-gate/v1.md:118-215, :274-282, :332-336` | §4 row-9 derivation; new §4.1 (table, decisions A-C, the seven rules, the class-7 gap); §5 raises; Versioning: table/inventory rows reviewed like allowlist entries, removal is v2. Spec is `status: draft`, so the docs immutability check allows it. Raises only. |
| `.oss-scanner/threat_model.md:194-216` | The "command layer … still stubs" sentence replaced by a paragraph on the command layer, its accepted gap and the out-of-scope walker cases. |
| `tests/test_gate_commands.py` (new) | The brief's test. 26 functions, every case through `nl_shell.gate.classify`. |
| `tests/test_policy_gate.py` | See "Changes to an existing test file" below. |

## Decisions the brief left to Do

**Recursion entry point: callback.** `__init__.py` passes `recurse=_Run` into
`rules.classify` (`__init__.py:209`). I picked the callback over "rules returns a request to
class text in grammar G" because three rules need the inner result *inside* the engine,
not after it: (1) an elevating row must know whether its inner text opened a shell (`sudo
bash -c 'bash'`, `sudo env bash -s x` → root shell, rejected); (2) array values of
`PROMPT_COMMAND` need word splitting by the real parser (`Recurse.words`); (3) arithmetic and
prompt text are reclassed as a here-doc body and the result merged into the same verdict.
With a returned request list, each of these would need a second protocol back from
`__init__.py` to `rules`. `rules.py` imports only `parse` and `commands`; no cycle.

**Shared budget.** One `parse.Budget` per top-level `classify` (`__init__.py:165`, created per call at `:150`), passed
to every nested `shell_layer`. The budget test (`test_work_budget`) builds `T = ":;" ×
(MAX_WORK // 4)` = 1024 units: `bash -c 'T'` alone classes normally (no "could not
class"); three of them (6.2 KB, under the 8 KiB cap) give decision C. On the stub the three
give `mutating` with no "could not class", so it goes red (seen in the C4 run).

## Deviations — please confirm at sign-off

1. **`TARGET_ID` is a module constant, but not the literal string.** The brief asks for
   `TARGET_ID = "ubuntu-26.04"` in the loader. That literal fails the existing ADR-0023 check
   `tests/test_targets.py:680-689` ("package code names no OS", regex `ubuntu|26\.04`) — I
   hit exactly that failure on the first full-suite run. I set
   `TARGET_ID = _sole_target(TARGETS_ROOT)` (`commands.py:62-71`): the one folder under
   `targets/`, computed once at import. It is still a module constant equal to
   `"ubuntu-26.04"` (the test asserts that, `test_fixed_load_location`), still not read from
   `/etc/os-release`, env, cwd or config, and the test seam (monkeypatch `TARGETS_ROOT`,
   `cache_clear`) works unchanged. If a second target folder is ever added, `TARGET_ID`
   becomes `None` and every command is decision C until someone chooses — fail-closed,
   and forces the multi-target decision the brief deferred.
   Rejected alternatives, with cost: (a) the literal → 1 red test in the suite
   (`test_no_os_name_in_package_code`) and an ADR-0023 violation; (b) splitting the literal
   (`"ubuntu" + "-26.04"`) to dodge the regex → 1 line, but it defeats the check rather than
   meeting it; (c) editing `test_targets.py` to allow it → weakens an ADR check, out of scope.
2. **The `class-7-gap` exception (brief, plan-review point 3) is implemented as written.**
   The brief says "the human should confirm the exception at sign-off." Only git's `-c`,
   `--config-env`, `--exec-path` carry it in the table (`commands.toml`, git row); tar and
   ssh have no rows, so they are opaque and give the same floor answer.

## Changes to an existing test file (`tests/test_policy_gate.py`)

That file pinned the stub's answer (`mutating`, "not allowlisted") for 14 regression rows
whose spec class is higher. Each is now the class the spec asks for, with a `# … #197`
comment (`tests/test_policy_gate.py:139-232`): e.g. `cat <<E | sudo tee /x` → rejected
(§5 pipe), `bash <<<'rm -rf ~'` → destructive (decision B), `rm -rf />/dev/null` →
destructive, `f() { sudo tee /x; }; cat <<E | f` → rejected (stdin in a function body is
`unknown`, the worst case, per the `Stdin` docstring `parse.py:112-113`). These are raises
only. Three monkeypatched fakes of `rules.classify` took one positional argument; the call
now passes `origin=` and `recurse=` (the brief's scope item (a)), so the fakes take `**_`.
Without that, those three tests would get decision C from a `TypeError`, not a real result.

## Things I added beyond the brief's literal list (each closes a case inside a class)

Found by probing my own engine with ~150 adversarial inputs before declaring done:

- **Possible command positions** (`rules.py:258-283`). Decision A as written checks single
  words, so `ionice sh -c 'sudo -i'` (opaque wrapper + known runner) and
  `sh -c '"$@"' _ bash -c 'sudo -i'` (positional words) were `mutating`. Every word that
  names a row, in an opaque argv, a fixed row's argv or positional words, is now also read
  as the start of an inner command. Whether that reading opens a shell is dropped, so
  `sudo apt install bash` is still only `privileged`, not rejected. Capped at 256 readings
  per simple command (`MAX_READINGS`) → decision C beyond.
- **A non-literal word where an option may stand is read both ways** (`rules.py:327-335`):
  flagged as an unknown option *and* read as the operand it may be. Without this,
  `bash -c "$v"` and `eval "$v"` gave "option the gate does not know" but not decision B.
- **`xargs cmd` is classed with and without the stdin items** (`rules.py:523-527`), so
  `xargs sudo -i` is a root shell (no items) as well as a sudo with an unknown operand.
- **Backquotes.** tree-sitter-bash does not parse `` `…` `` inside a here-doc body, so
  `readonly PS4='`sudo -i`'` was only `session-altering`. `_backticks` (`rules.py:912`)
  pulls the bodies out and classes them as bash.
- **flock** reads `-c` after the file (`flock /tmp/l -c 'sudo -i'`): the row permutes.
- Rows the probes or the inventory needed: `ash`, `hush` (busybox shells), `sulogin`,
  `login`, `run-parts`, `systemd-run` (same binary as `run0`), `ptyxis` (what
  `x-terminal-emulator` points to here), `gnurm`, `halt`/`poweroff`/`reboot`/`shutdown`
  (same binary as `systemctl`), `git-receive-pack`/`-upload-pack`/`-upload-archive`.

## Known costs (false positives — all fail-closed, none lower a class)

- Decision A over every argument word of an opaque command, as the brief decides:
  `man sudo` as a proposal is rejected; `which rm`, `echo find`, `git rm x` are
  `destructive`. Typed input is only raised, never rejected, by decision A.
- A non-literal word in an option position is "option the gate does not know":
  `chmod +x "$f"`, `find "$dir" -name x`, `printf "$fmt"` are `destructive`; `sudo "$x"`
  is rejected. (The brief requires this for `sudo "$P" true`; I applied it to every row.)
- `test -v PATH` is `mutating` (subscript role, no write); `unset PS1` is
  `session-altering`; `declare -n r=PROMPT_COMMAND` is decision B.

## Known gaps (left out; candidates for follow-ups)

- `[ … ]` is a `test_command` node and gives no `Invocation`, so the `[`/`test` row only
  fires for the `test` word. `[ -v 'a[$(…)]' ]` is in the same walker bucket as the brief's
  out-of-scope `[[ -v … ]]`. Noted in the threat model.
- Run-time values: `declare -i x=y` where `y` holds `a[$(…)]`; `declare -n r` then
  `r=SUDO_PROMPT` (first assignment sets the target). Same bucket as `x=sudo; $x -i`.
- Text runners with their own text options that have no row: `vi -c '!…'`, `ed`, `nc -e`,
  busybox `httpd`/`telnetd`/`crond`, `start-stop-daemon`, `nsenter`/`setpriv` with a
  quoted command. With "possible command positions" these are caught when a known runner
  or an elevating word follows; a lone quoted text word is the class-7 accepted gap.

## Refuting my own test

- **(a) Genuine red? Yes.** `engine/scripts/run-verify.sh` (the project's C4 runner) with
  `PDCA_BUNDLE=results/issue_197`: red leg ran 206 tests, 38 failed; green leg 206 ran,
  0 failed — `PDCA-EVIDENCE: C4 PASS`. In `tests/test_gate_commands.py`, 24 of 26 functions
  go red on the stub; the two that pass are `test_class5_pinned` and
  `test_class7_floor_accepted_gap`, exactly the two the brief exempts. I split each
  property group into `…_property` (reads the table; red by ImportError on the stub) and
  `…_regressions` (named cases; red by assertion), so the red is behavioural, not only a
  missing module. The worktree was byte-identical to `patch.diff` after the run.
- **(b) Production path? Yes.** Every case calls the public `nl_shell.gate.classify`
  (`tests/test_gate_commands.py:42-45`), which runs the real `_Run.text` pipeline, the real
  `rules` engine and the real `targets/ubuntu-26.04/commands.toml`. The property groups read
  that same table through the production loader (`commands.load`, `commands.fields`). No
  mocks; the only monkeypatch is the brief's seam (`commands.TARGETS_ROOT` + `cache_clear`)
  in the two decision-C/load-location tests.
- **(c) Fixture includes the fault? Yes.** The class-1 test reads the real generated
  `inventory.toml` (73 names, including the alias names `sudo-rs`, `sudoedit-rs`, `su-rs`
  that v1/v2 missed) and fails on any name without a row. The class 2-6 property loops run
  over every row and field of the real table, with the undeclared option placed right after
  the command word / subcommand. The decision-C test uses a missing file, broken TOML, a
  `raw = true` row and a symlink that resolves outside the root; the load-location test plants
  a "sudo is harmless" table in the cwd and in `NL_SHELL_COMMANDS`, `NL_SHELL_TARGETS`,
  `XDG_CONFIG_HOME`.

## Commit-readiness

The target has no formatter or lint hook (no `.pre-commit-config.yaml`; `pyproject.toml`
has no ruff/black config; CI is docs checks + PR hygiene). I ran `git diff --check` (clean),
an AST unused-import scan over every touched Python file (clean), kept lines ≤ 100, and the
whole suite through `engine/scripts/run-suite.sh`: `1399 passed, 1 skipped`, `PDCA-EVIDENCE:
T3 PASS`. The suite includes `test_docs_checks.py` and `test_docs_links.py`. No new runtime
dependency.

## For the reviewer at Check (from the brief)

- Re-run `python3 -I scripts/harvest_inventory.py --output /tmp/x.toml` on this host and
  diff against `targets/ubuntu-26.04/inventory.toml` (I did: identical).
- The loader has no `os.environ`, `Path.cwd()`, `Path.home()` or config read
  (`grep -n "environ\|cwd\|home\|config" src/nl_shell/gate/commands.py` — the only hits are docstring text and the `--config-env` option name).

# Build notes — #204 gate command-table engine

Target: `eduralph/nl-shell @ main` (`1a1e980`), worktree `nl-shell.pdca-wt-l1`. Line
numbers below are in the patched tree unless marked "base".

## What the patch does

- **Engine** — `src/nl_shell/gate/rules.py` replaces the stub (base `rules.py:26-28`).
  `classify(invocation, origin)` at `rules.py:63` loads the table and runs one generic
  engine (`_Engine`, `rules.py:267`). It parses argv with the row's grammar
  (`_parse` `:542`, `_option` `:628`, `_old_style` `:609`, `_until` `:701`), applies the
  effects (`_effect` `:469`, `_condition` `:508`), and recurses into wrapper inner
  commands (`_inner` `:437`, depth bound `MAX_NESTING` `:44`, past it a `GateFailure` →
  decision C). Decision A is `_decision_a` `:311`; the elevation rules are `_elevation`
  `:344` and `_elevated_opaque` `:333`. No command name appears in the engine.
- **ANSI-C decoding, command layer only** — `readable()` `rules.py:101` / `_ansi_c`
  `:163`. A word is decoded only when `parse.lex_word`'s causes are exactly
  `{"expansion"}` and the source holds `$'`. It cuts one `$'…'` at `\0` and keeps the rest
  of the word, as bash 5.3.9 does on this host (`printf '[%s]' $'ab\0cd'ef` → `[abef]`).
  `\x`/`\u` with no digits, surrogates, a bad `\c` → unreadable. `lex_word`, `make_word`
  and `Word.literal` (base `parse.py:197`, `:273-275`) are untouched, so no shell-layer
  verdict moves (`cat $'x'` is still not literal; `test_policy_gate.py:517` unchanged).
- **Loader** — `src/nl_shell/gate/commands.py`, in the style of `targets.load`
  (base `targets.py:145-169`). `load()` `commands.py:301` takes no argument and reads
  `TARGETS_ROOT / TARGET_ID / COMMANDS_FILE` (`:65-69`), refusing a resolved path
  outside the root (same check as base `targets.py:153`). It reads no environment and
  does not import `os`. `validate()` `:326` refuses `raw`, unknown keys, a
  `runs-command-at` grammar with no `no_command`/`terminal_stdin`, a
  `runs-stdin-as-code` grammar with no `terminal_stdin`, text effects with no grammar,
  and `gap = "class-7"` on any option not in `CLASS7_GAP` (`:122`). The cache is
  `table()` `:296` (`functools.cache`).
- **Table** — `targets/ubuntu-26.04/commands.toml`: 92 rows, format in the loader's
  docstring. **Inventory** — `targets/ubuntu-26.04/inventory.toml` (133 names, records
  `VERSION="26.04.1 LTS (Resolute Raccoon)"`), written by
  `scripts/harvest_inventory.py` (style of `scripts/gen_unicode_tables.py`).
- **Wiring** — `src/nl_shell/gate/__init__.py:196` passes `origin`. I also corrected the
  module docstring (base `__init__.py:7-16`), which still said the command layer is a stub.
  That goes slightly past the brief's "only passing origin"; I kept it because otherwise the
  docstring would be false. It is 6 lines of docstring and no code.
- **Spec** — `docs/design/specs/policy-gate/v1.md`: §4 (`:109`, adds the alias names and the
  row-9 derivation), new §4.1 (`:135`, row format, fixed load location, decisions A and
  C, elevation, classes 1/2/7 and the class-7 gap, and a one-line "text effects are decision
  B" placeholder), §5 (`:208`, quoted `-S`, unreadable option words, and pipes into any
  elevating row), and Conformance row 16 (`:356`) → `destructive`. No recursion, B′,
  classes 3–6, or "text is read" claims.
- **Threat model** — `.oss-scanner/threat_model.md:194` replaces "The command layer, §7
  and §8 are still stubs…" with what this child does.
- **Vectors** — `gate-vectors.toml`: row 16 → `destructive`; appended rows 8, 9, 10,
  11, 12, 17, 18, 21 (×3), 22, 24, 26, 27, 29, 32, 33.

## Existing tests changed (raise only)

`tests/test_policy_gate.py`: 15 regression cases go up, none down (`:143-197` region).
Examples: `cat <<E | sudo tee /x` mutating → privileged + rejected (pipe into sudo);
`bash <<<'rm -rf ~'` → destructive; `$'\x72m' -rf ~` → destructive (the shell-layer reason
"command word is not a literal" is still there); `declare -x A=1; unset A` →
session-altering. Three fakes now take `origin` (`:813`, `:853`, and the lambda near
`:752`), because `__init__.py:196` now passes it.

`tests/test_targets.py:682-693`: **brief/ADR conflict, flag for the human.** The brief
requires `TARGET_ID = "ubuntu-26.04"` as a module-level constant. The existing guard
`test_no_os_name_in_package_code` (ADR-0023, "code names no OS") rejects any `ubuntu` or
`26.04` in `src/nl_shell/**.py`, so the two cannot both hold. I kept the name visible and
added an exact-match exemption for that one line (path + line text). I did not hide it
by building the string from pieces, because that would only defeat the guard. I also
removed the OS name from both new docstrings. If the human prefers another resolution
(for example, choosing the target from os-release now), that is a re-plan.

## Choices worth a look at sign-off

1. **Opaque command under elevation, proposals (strict reading).** "An undeclared option
   anywhere in the inner argv rejects a proposal." A command with no row declares no
   options, so `sudo apt install -y foo` *as a proposal* is rejected
   (`_elevated_opaque` `rules.py:333`). Typed input stays privileged and not rejected.
   The looser alternative (reject only unreadable words) would accept
   `sudo apt-get -o APT::Update::Pre-Invoke::=sh update` as a proposal, and that is a root
   shell. I chose strict. The cost: every proposal that runs a no-row command with options
   under sudo is rejected until those commands get rows (or #198 allowlist entries).
2. **`alias` has no `stores-code`.** Declaring it would make Conformance row 33
   `destructive`, and row 33 is spec text this child does not own. Alias values are
   child-3's stored-code rule. `trap`, `bind -x`, `complete -C/-W` and `crontab` do declare
   `stores-code`, so they are destructive now.
3. **`busybox` declares `opens-shell` unconditionally** (with its own reason, "its
   applets include shells"). This puts busybox on the brief's list of words the elevation
   rule rejects (`bash`, `sh`, `python3`, `busybox`). Without it,
   `sudo strace busybox awk 'BEGIN{system("sh")}'` would get through as a proposal. Side
   effect: typed `busybox ls` shows that reason (the class stays mutating).
4. **"Runs code whatever its options" (`Row.runs_code`, `commands.py` `_row`)** counts only
   grammar-level effects without `when`. So `env` (only `-S` runs text) and `tar` (only
   `-I` and similar) are not on the elevation word list. Their option effects are still
   caught when parsed under elevation. Rows that are on the list: shells, interpreters,
   `chroot`/`unshare`/`pkexec`/`run0`/`screen` (no command opens a shell), `watch` (joins
   its words for `sh -c`), `ssh` (a remote command is text), `su`, `script`, `gdb`, `cpp`
   and the other fixed text rows.
5. **A word the gate cannot read where an option may stand** is treated as an undeclared
   option (destructive). Under `sudo`, whose options include ones §5 rejects, it is
   rejected for any origin (`sudo "$P" true`). This also catches `git reset %` under
   `xargs -I%`. Over-raise: `chmod 644 ~/f` and `rm "$f"` are destructive, because `~`
   and `$f` are unreadable words in a GNU option position.
6. **Decision A over-raises, as accepted by the brief:** `echo su`, `man sudo` →
   privileged; `which git`, `man kill`, `ls /usr/bin/rm` → destructive (any row with
   `destroys` anywhere, matched by name or basename).
7. **Pipe into an elevating row** uses `stdin.kind not in ("terminal", "file")`, so
   `unknown` counts as a pipe (per the `Stdin` docstring, base `parse.py:112-113`).
   `cat list | xargs sudo rm` is rejected (xargs's inner stdin is treated as inherited,
   which errs toward rejecting).
8. **Row choices outside the brief's list, all raises:** rows for `halt`/`poweroff`/
   `reboot`/`shutdown` (the same file as `systemctl`), `ptyxis` (the
   `x-terminal-emulator` on this host), `gnurm` (`/usr/bin/rm` is that file), and the
   `git-*-pack` names (the same file as `git`). The harvester's "every name of a row's
   file" step found them. `strace -o` is declared `runs-text`, because a value starting
   with `|` or `!` runs a command. That makes every `strace -o log` destructive, which is
   the cost of not reading the value.
9. **Text-reading layer hand-off:** every text effect names a grammar from `GRAMMARS`
   (`commands.py`). Name operands carry `name = true` (`export`, `unset`, `declare`,
   `env -u`). Child-2 and child-3 can add their rules on top without a format change.

## Ruled out

- Per-command code paths, `raw` rows, or `_PIECE_SPLIT` (forbidden; v1–v3).
- ANSI-C in `lex_word`: it feeds redirect targets, `_stdin_after`, declarations,
  here-string feeds and cd placement (base `parse.py:315`, `:595`, `:821-826`, `:1004`,
  `:1104-1189`). Marking `$'…'` literal there would lower `ls > $'/etc/x'` from rejected
  to accepted.
- Picking the target folder by "the only folder under `targets/`" (v3's drift).

## Running it

- Project gate, as Check runs it:
  `PDCA_BUNDLE=… PDCA_WORKTREE=… engine/scripts/run-verify.sh` →
  `PDCA-EVIDENCE: C4 PASS — red without the fix (144 of 380 failed), green with it`. It
  runs every changed test file: `test_gate_commands.py`, `test_policy_gate.py` and
  `test_targets.py`.
- Full suite in the worktree (`python -m pytest`, final tree): 1524 passed, 1 skipped.
  (Before the `test_targets.py` exemption above it was 1523 passed, 1 failed.)
- Commit hooks: nl-shell has no formatter, linter or pre-commit config (no
  `[tool.*]` in `pyproject.toml`, no `.pre-commit-config.yaml`). CI runs `pytest` and
  `scripts/docs_checks.py` / `scripts/docs_links.py`: links 0 broken, `git diff --check`
  clean. I wrapped new code to the repo's ~92 columns by hand.

## Refuting my own test

- **(a) Genuine red?** Yes. With `git apply -R --exclude='tests/*'` (the stub back,
  `commands.toml`/`inventory.toml`/harvester gone), `tests/test_gate_commands.py` alone
  gives 129 failed, 11 setup errors (the `fresh_table` fixture cannot import the loader),
  and 11 passed. The passing ones are the floor group
  `test_class7_floor_documented_not_raised` (5) and
  `test_spec4_wrappers_are_at_least_mutating` (6), both of which the brief expects to pass
  on the stub. Every other group is red. The project gate reports the same: C4 PASS.
- **(b) Production path?** Yes. Every case calls the public `nl_shell.gate.classify`,
  which runs the real shell layer, the real `rules.classify` and the real
  `commands.table()` on the checked-in `commands.toml`. The loader tests call the real
  `commands.load()`. The properties (class 2, wrappers, no-command shells) iterate over the
  checked-in TOML with `tomllib`, not over a copy.
- **(c) Fixture includes the fault?** Yes. Decision C points the loader's own root at a
  `tmp_path` with a missing, broken, wrong-format or empty file. The cwd/env test plants a
  "sudo is harmless" table in the cwd, `targets/…` under it, `XDG_CONFIG_HOME`,
  `HOME`, `NL_SHELL_COMMANDS` and `NL_SHELL_TARGETS`, then classes `sudo -i`. The
  path-outside test makes the target folder a symlink out of the root. The inventory test
  reads the real harvested file.

## For the human at Check

- **Inventory drift (human-judged, not a gate):** on this host run
  `python3 -I scripts/harvest_inventory.py --output /tmp/inv.toml` and diff it against
  `targets/ubuntu-26.04/inventory.toml`. Any difference is a finding. (It reads
  `commands.toml` row names, so re-run it after any row change.)
- Settle the ADR-0023 / `TARGET_ID` conflict above.
- Review the strict opaque-under-sudo choice (item 1).
- Housekeeping: I wrote two scratch files outside the worktree and bundle,
  `/tmp/try_cases.py` and `/tmp/claude-1000/patch.check`, and an ignored bytecode folder
  `.pyc.u9X9/` inside the worktree. None is in `patch.diff`, and I did not delete them.

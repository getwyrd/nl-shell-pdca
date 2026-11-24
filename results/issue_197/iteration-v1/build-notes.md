# Build notes — issue #197 (policy gate command layer)

Base: the wave's folded branch `pdca-integration/main-r47cf951baa2a` at `0b6f18f`
(holds #196). All `path:line` below are in the patched worktree.

## What the patch does

- **Engine** — `src/nl_shell/gate/rules.py` replaces #196's stub. One generic interpreter:
  `_invocation` (`rules.py:206`) looks up the command word in the table, then either
  applies decision A (`_decision_a`, `rules.py:230`) or reads the argv with the row's
  grammar (`read_argv`, `rules.py:317`), checks each effect's condition (`holds`,
  `rules.py:423`) and runs one handler per effect type (`_HANDLERS`, `rules.py:778`; one
  handler for each of the nine effect types, asserted against `commands.EFFECTS`). No
  command name appears in the engine. When the argv cannot be read (an unlisted option,
  or a non-literal word in option position) every condition is taken to hold (the
  `unread` flag in `holds`).
- **Loader** — `src/nl_shell/gate/commands.py` (new), in the style of
  `src/nl_shell/targets.py:145-247`: strict validation, `CommandsError` naming the file
  and row. `load(target_id=None)` (`commands.py:218`) takes no path, reads
  `targets.TARGETS_ROOT / <id> / "commands.toml"` and refuses a resolved path outside the
  root, as `targets.py:153` does. No `os.environ`, `Path.cwd`, `Path.home`, config read
  (the test greps the module source for these). With no target named, the default is
  "the only target folder there is" (`default_target`, `commands.py:206`). I did this
  because `tests/test_targets.py:676-688` forbids an OS name in package code, so I could
  not hard-code `ubuntu-26.04`. With zero or several folders there is no default, which
  gives decision C. `classify()` gained an optional `target=` keyword
  (`__init__.py:129`) for the REPL wiring (#78) to pass the active target.
- **Data** — `targets/ubuntu-26.04/commands.toml` (new): the format is documented in its
  header. It has rows for the sudo family (sudo/sudoedit, su, pkexec, doas, run0,
  machinectl shell/login, systemd-run without `--user`), wrappers (env, nice, nohup,
  timeout, time, stdbuf, setsid, flock, ionice, chrt, taskset, chroot, unshare, xargs,
  find, watch, script), shells (bash/sh/dash/rbash), the §3 builtins, the
  variable-assigning builtins (export, declare/typeset/local, readonly, read,
  mapfile/readarray, printf, getopts, let) and the §4 destructive commands.
- **Shared budget** — `src/nl_shell/gate/parse.py`: `Work` (`parse.py:76`) counts units
  (nodes visited, plus one for each command or text classed again) against `MAX_WORK`
  (`parse.py:39`, the named constant the brief asks for). One `Work` is shared by the
  whole classification. `shell_layer` (`parse.py:986`) takes `stdin=` (the stdin that
  nested text starts with) and `work=`. These are not walker bug fixes. The brief's
  budget item needs them ("work units across recursion", "a named value in
  gate/parse.py"). The walker's logic is unchanged.
- **Pipeline** — `src/nl_shell/gate/__init__.py`: `_analyse` (`__init__.py:177`) is the
  old `_classify` body minus the label step. `nested()` (`__init__.py:166`) runs it for
  text a command runs (decision B recursion), under the same origin and budget. The
  table is loaded up front (`__init__.py:156`), so a missing or invalid table is
  decision C for every command, including `PATH=x`. `Result.work` (`__init__.py:65`)
  holds the units used. It is not part of `as_log`. The §3 name lists moved to `rules.py`
  so the shell layer and the engine share one copy.
- **Spec** — `docs/design/specs/policy-gate/v1.md`: §4.1 "The command table" (`:131`)
  covers the effects, the "cannot read ⇒ every condition holds" rule, decisions A
  (`:165`), B (`:172`) and C (`:177`), and rows being reviewed like allowlist entries
  (`:181`, Versioning `:303`). It also adds the row-9 derivation (`:125`) and #196's
  stricter fd wording in §5 (`:187`).
- **Threat model** — `.oss-scanner/threat_model.md:182` (command layer, A/B/C, the fixed
  load location, why the file is not signed) and `:121-124` (the SUDO_* forms and the
  su/pkexec/doas pipe rule).
- **Vectors** — `targets/ubuntu-26.04/gate-vectors.toml`: rows 8, 9, 10, 11, 17, 18, 21
  (×3), 22, 24, 26, 27, 29, 32, 33 and three unnumbered rows. `tests/test_policy_gate.py`
  runs them through `test_regression_table_from_vectors`. The new test does not read
  them.

## Changes to #196's tests (`tests/test_policy_gate.py`)

16 cases asserted the stub's answer, which the engine now raises (raises only):
`cat <<E | sudo tee`, `… | doas id`, `f() { sudo tee …; }; … | f`,
`exec </tmp/x; sudo tee` → privileged and rejected (pipe reason; in the last two, stdin
is `unknown`, which `parse.py:109-110` says consumers treat as a pipe).
`curl x > >(sh)`, `f() { sh; }; curl x | f` → destructive (B). `bash <<<'rm -rf ~'`,
`rm -rf />/dev/null`, `rm -rf ~>/dev/null` → destructive. `sudo rm -rf /etc>x` →
privileged. `cat <<E > >(sudo tee …)` → privileged. `while …; exec <x` and
`declare -x A=1; unset A` → session-altering. `$(echo rm) -rf ~` → destructive (decision
A: `echo` is opaque and names `rm`). `/tmp/rm x`, `./rm x` → destructive (see the decision
A extension below). `test_vectors_file_loads` now also asserts the new rows.

## Decisions and trade-offs for the human

- **Decision A's false positives (accepted trade-off, per the brief).** Until #198's
  allowlist exists, `echo`, `man`, `which`, `apt` and `dpkg` are opaque. So
  `man sudo` / `which sudo` / `apt show sudo` as a *proposal* are **rejected**, and
  `echo rm` is `destructive`. Reviewed table rows are not opaque (`git log sudo`,
  `printf sudo` stay `mutating`; these are floor cases).
- **Decision A extension (a raise beyond the agreed text, please review).** A word names
  a command by its last path component, and the command word itself counts when it is a
  path outside the system directories (`rules.py:223-245`; spec `:165-171`). Without
  this, a proposal of `/usr/local/bin/sudo -i` was only `mutating` and not rejected.
  Cost: `./rm x` and `/tmp/rm x` are now `destructive`.
- **"Cannot read the argv ⇒ every condition holds"** gives over-raises such as
  `systemctl restart "$svc"` → destructive, `rm "$f"` → destructive,
  `kill "$pid"` → destructive (the pid may be -1), and `find "$d" -name x` → destructive.
  For sudo, a non-literal option word is rejected (it may be `-S`); the brief requires
  this. For `printf "$fmt" …`, `read "$v"`, `export "$n"=…` and `declare -n r` (no
  target), the variable name is unreadable, so the command is **rejected**
  ("assignment to a variable the gate cannot name"): it may be SUDO_PROMPT. That is
  strict for `printf "$fmt"` with a non-literal format. I kept it fail-closed.
- **`xargs sudo …` typed is rejected**, not just privileged: xargs appends input words,
  which may be `-S`. The test asserts only the class for that typed half
  (`test_wrapped_root_shell_is_rejected`).
- **Raises beyond the spec's §4 list (please review):** `systemctl kexec`,
  `soft-reboot`, `emergency`, `rescue`; `reboot` / `poweroff` / `halt` / `shutdown`;
  `cfdisk`, `sgdisk`, `cgdisk`, `blkdiscard`, `mke2fs`, `mkswap`; `chgrp -R`;
  `git push --mirror` / `+refspec` / `-f`; `systemd-run` without `--user` as elevating;
  `let` / subscripts with `$` in them as B (bash evaluates them again, so
  `let 'a[$(rm -rf ~)]=1'` runs `rm`).
- **`reads-terminal`** is in the format and on `read` / `mapfile`, but the engine gives
  it no class (`rules.py:511`). The terminal-read rule is #198's.
- Interpreters other than the four shells (python, perl, zsh, fish) have no row. They
  are opaque, so `curl x | python3` is only `mutating`, though decision A still catches
  `python3 … sudo`. This is a candidate follow-up, not in this scope.

## Gaps found, out of scope (for follow-ups)

- **Walker (child-1):** arithmetic assignments `$((SUDO_ASKPASS=1))` and
  `(( SUDO_PROMPT=1 ))` produce no `variable_assignment` and no invocation, so neither
  layer sees them. I did not fix this in the walker (the brief: fix child-1 only if a
  case here exposes a bug; none of the brief's cases do). Worth an issue.
- `git -c core.sshCommand='sudo x' fetch` / `git -c alias.x='!…'` stay `mutating`: git
  has a row, so decision A does not scan it. This matches the brief's floor
  (`git -c core.pager=sh log` stays mutating).
- `x=sudo; $x -i` is `mutating` (row 16 semantics: a non-literal command word).

## Alternatives ruled out

- **Pass `origin` into `rules.classify(invocation, origin)`** instead of a
  `ContextVar` run state. Three monkeypatched fakes in `tests/test_policy_gate.py`
  (`:679`, `:738` used at `:751` and `:762`, `:778`) take one argument, and the budget and
  nested callback would need threading through too. The context keeps
  `rules.classify(invocation)`'s signature and puts the per-run state (origin, `Work`,
  table, depth, cache) in one place (`rules.py:122-147`).
- **No memo for nested text.** Without the cache in `_inner_text` (`rules.py:262`), the
  brief's nine-deep `{ bash;bash;bash;bash; } <<'E…'` input does 4^9 = 262 144 nested
  classifications. That is decision C, which fails the brief's "units stay below the
  budget". With the cache it uses 250 units of 4096 (323-byte input, result `destructive`).
- **Recurse on `runs-stdin-as-code` with the outer stdin.** `bash <<<'bash'` would then
  recurse on the same text forever (only the budget would stop it). The commands inside
  get `unknown` instead (`rules.py:643-653`). That is also what makes
  `bash <<<'sudo ls'` hit the pipe rule.
- **A separate `session` row key for §3.** The brief fixes the effect set, so §3 builtins
  are `sets-variable from = "state"`, plus `in_shell = true` on the runs-* effects of
  eval/source/./exec/command/builtin/trap.

## Verification

- C4 through the project runner (`engine/scripts/run-verify.sh`, with `PDCA_BUNDLE` and
  `PDCA_WORKTREE` set), on the final patch: green leg 392 passed; red leg 222 of 392
  failed → `PDCA-EVIDENCE: C4 PASS`. The tree was restored byte for byte afterwards
  (`git diff` = `patch.diff`).
- On the red leg, the only cases in `tests/test_gate_commands.py` that stay green are
  the 18 floor cases (`test_floor_cases_are_not_raised`). I checked this by comparing the
  collected ids with the red leg's FAILED list.
- T3 through `engine/scripts/run-suite.sh`, on the final tree: 1493 passed, 1 skipped
  → `PDCA-EVIDENCE: T3 PASS`.
- Formatter / hooks: nl-shell configures none (no `.pre-commit-config.yaml`, no
  ruff/black config in `pyproject.toml`). CI runs `scripts/docs_links.py` (0 broken) and
  pytest. I kept the repo's 92-column limit by hand (the existing files peak at 92).

### Refuting my own test

- **(a) Genuine red?** Yes. `run-verify.sh` reverted every production hunk (rules.py,
  commands.py, commands.toml, parse.py, `__init__.py`, gate-vectors.toml) and re-ran both
  changed test files: 222 of 392 failed. Every non-floor case in the new file failed.
- **(b) Production path?** Yes. Every case calls `nl_shell.gate.classify` (the real
  pipeline) on the real `targets/ubuntu-26.04/commands.toml` through the real loader. The
  only stand-ins are tmp `TARGETS_ROOT` folders in the four load tests, which test the
  loader's refusal paths and must not touch the real file. No mock of the engine.
- **(c) Fixture includes the fault?** Yes. The cases are the brief's attack strings
  themselves (the v1/v2 regressions, the nested-heredoc budget input, a decoy table in
  the cwd plus `NL_SHELL_COMMANDS`, `NL_SHELL_TARGETS`, `XDG_CONFIG_HOME` and `HOME`
  pointing at decoys that declare sudo harmless, a symlink out of the root). Nothing is
  curated out.

## Process note

I wrote one scratch file outside the harness roots by mistake early on,
`/tmp/probe_gate.py` (a parse probe). It is not part of the patch. Later scratch files
are in the worktree's untracked `.scratch/`, which the patch leaves out. I did not
delete either: cleanup is the harness's job.

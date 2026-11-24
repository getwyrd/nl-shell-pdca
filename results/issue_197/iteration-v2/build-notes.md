# Build notes — issue #197 (policy gate command layer), iteration 2

Base: the wave's folded branch `pdca-integration/main-r47cf951baa2a` at `0b6f18f` (holds
#196). All `path:line` below are in the patched worktree.

This iteration starts from the iteration-1 patch (`iteration-v1/patch.diff`, applied
unchanged) and closes the bypasses the human confirmed at sign-off. The design the human
accepted (one engine, rows as data, decisions A/B/C) is not changed. Everything below
"Carried over from iteration 1" still holds, with line numbers updated.

## Iteration 2 — what changed, item by item

Each item has a full-pipeline regression case in `tests/test_gate_commands.py`
(`nl_shell.gate.classify`, the real table, the real loader), as a proposal where the
finding is about a rejection.

1. **sudo family names on the target.** `targets/ubuntu-26.04/commands.toml:81` adds
   `sudo-rs`, `sudoedit-rs`, `sudo.ws` to the sudo/sudoedit row; `:116` adds `su-rs` to the
   su row. Data only. Tests: `test_sudo_family_names_shipped_on_the_target`
   (`tests/test_gate_commands.py:379`: `sudo-rs -i`, `sudo.ws -i`, `su-rs`,
   `/usr/bin/sudo-rs -i` as proposals, rejected with the root-shell reason) and
   `test_sudo_family_names_sudo_rules` (`:385`: `echo pw | sudo-rs -S true`,
   `sudo-rs -S true`, `foo sudo-rs` through decision A, `sudoedit-rs /etc/shadow`).
   `sudoedit-rs /etc/shadow` is `privileged` and not rejected, same as `sudoedit` (it
   edits a file; it opens no shell).
2. **`env -S` uses env's split syntax, not bash's.** New runs-text key
   `unreadable_chars` (`commands.toml:287`, loader `src/nl_shell/gate/commands.py:107`,
   `:164`, `:427`). The env row lists `\` and `$`: `-S` text holding either is text the
   gate cannot read, so decision B (at least `destructive`)
   (`src/nl_shell/gate/rules.py:651`). The carry-forward also says `env -S 'sudo\_-i'`
   **must be rejected**, which decision B alone does not do. So the engine also runs
   decision A over the pieces of that text, split at any character that cannot be in a
   command name (`_PIECE_SPLIT`, `rules.py:78`, used at `:657`). `sudo\_-i` holds the
   piece `sudo`, so the proposal is `privileged` and rejected. A second fix in the same
   handler: with `with_rest`, the operands after `-S` are now passed to the nested
   classification as words of their own (`shlex.quote`, `rules.py:664`), not glued on as
   more shell text. Before this, an operand holding a quote could change how bash reads
   the joined text. Tests: `test_env_split_string_syntax_is_not_read_as_bash` (`:398`).
3. **`getopts -- x SUDO_PROMPT`.** The getopts row is no longer `raw`
   (`commands.toml:755`). With no options listed, the default `end_of_options` drops `--`,
   so `SUDO_PROMPT` is operand 1 again. An option-like optstring (`getopts -x …`) now makes
   the argv unreadable, so every word may be the name (fail-closed). Test: the form
   `getopts -- x {}` in `SETS` (`tests/test_gate_commands.py:345`), run for SUDO_PROMPT,
   SUDO_ASKPASS (rejected), PATH and LD_PRELOAD (session-altering).
4. **Non-literal inner command runs decision A.** When a row's inner command word is not
   a literal, the engine now also runs decision A over the row's literal arguments
   (`rules.py:567`). This applies to every runs-command-at row, not only the ones with
   `unreadable_inner`: the inner command is opaque either way, and decision A is what the
   spec gives an opaque command. Raises only. Tests:
   `test_non_literal_inner_command_runs_decision_a` (`:412`:
   `find /usr/bin -name sudo -exec {} -i \;` and `printf x | xargs -I% % sudo -i`, both
   proposals, rejected).
5. **Root-shell gaps.**
   - `_from_stdin` now marks `opens_shell` when stdin is the terminal (`rules.py:674`).
     Code read from the terminal is an interactive shell. This covers `sudo bash -s x`,
     `sudo bash -is x`, `sudo dash -s x`, `sudo env bash -s x`, `pkexec bash -s x` and
     `sudo bash /dev/stdin` (runs-file-as-code on /dev/stdin goes through `_from_stdin`).
   - The shell row also gets `opens-shell when { option = ["-s"], not_option = ["-c"] }`
     (`commands.toml:566`), so the data states it too.
   - `chroot`: `opens-shell when { max_operands = 1 }` (`commands.toml:416`), with a new
     condition key `max_operands` (`commands.py:80`, `:141`, `:398`; engine
     `rules.py:458`). `unshare`: `opens-shell when { no_operands = true }`
     (`commands.toml:436`).
   - Tests: `test_more_root_shells_are_rejected` (`:440`, all eight carry-forward forms;
     typed, each is `privileged` without the root-shell reason) and
     `test_chroot_with_a_command_opens_no_shell` (`:446`, an over-raise guard:
     `sudo chroot / ls` is not rejected).
6. **`mapfile`/`readarray -C`.** A runs-text effect on `-C` with `in_shell = true` and
   `appends = true` (`commands.toml:727`). Bash evaluates the callback with the index and
   the line appended, and the line comes from the input, so `appends` (now valid on
   runs-text, `commands.py:106`) adds one word the gate cannot read (`"$1"`,
   `rules.py:665`). So `mapfile -C eval …` is decision B, and `mapfile -C 'sudo -i'` is
   sudo with a non-literal option word, rejected. Tests: `test_mapfile_callback_is_code`
   (`:451`).
7. **`wait -p NAME`.** New row (`commands.toml:735`): sets-variable `from = "option"`,
   `option = ["-p"]`. Test: the form `wait -p {}` in `SETS` (`:346`).
8. **`enable -f`.** `enable` is split out of the shared raw row into its own row
   (`commands.toml:637`) with its flags, `-f` as a value option, the old
   `sets-variable from = "state"` effect, and `runs-file-as-code option = ["-f"]
   in_shell = true` (`:648`). `enable -f x.so foo` is at least `destructive`, reason
   "runs code the gate cannot read". Test: `test_enable_loads_native_code` (`:461`).

Spec (`docs/design/specs/policy-gate/v1.md:146-169`, `:199`, `:205`) and threat model
(`.oss-scanner/threat_model.md:121-125`, `:191-196`) describe the new behaviour. Two
vector rows were added (`targets/ubuntu-26.04/gate-vectors.toml:228`, `:234`).

Not in this rebuild, as the carry-forward says: interpreters python3/perl/busybox (#198)
and assignments with no simple command, `(( X=1 ))`, `for X in` (walker, #196).

### Alternatives ruled out in this iteration

- **Translate `env -S` text into bash words** instead of marking it unreadable. GNU/uutils
  split-string has single quotes with `\\` and `\'` escapes, double quotes with
  `\" \\ \$ \_`, `\_`/`\t`/`\n`/`\v`/`\f`/`\r` outside quotes, `\c` to stop, `#` comments
  and `${VAR}` expansion. A faithful translator is about 60–80 lines of code that only env
  uses: a per-command code path, which the brief rules out ("express each rule as a
  row"). It would also still have to give up on `${VAR}`. The chosen fix is one data key
  (`unreadable_chars`), about 15 engine lines, and it fails closed. Cost of the choice: any
  `env -S` text with a backslash or `$` is `destructive` even when harmless
  (`env -S 'echo\_hi'`).
- **Decision A over the pieces only when `unreadable_chars` fires**, not for every
  non-literal runs-text. `bash -c "$v"` has no pieces to read, so there is nothing to
  scan; the brief keeps `bash -c "$v"` at `destructive`, not rejected.
- **Data-only fix for the `-s` root shells** (just the new opens-shell row effect). It
  would miss `sudo bash /dev/stdin` and any other row whose stdin reaches the terminal
  through runs-file-as-code. The one-line engine change at `rules.py:674` covers both.

### Over-raises added in this iteration (fail-closed; please weigh at sign-off)

- `env -S` text with `\` or `$` → `destructive`.
- A wrapper whose inner command word is not a literal now runs decision A over all of
  its arguments: `nice -- "$x" rm f` → `destructive`; `find . -name rm -exec {} \;`
  (already `destructive`) gets an extra "names a destructive command" reason. (A
  non-literal word in option position, `env "$x" rm f`, was already handled by the
  iteration-1 "argv cannot be read" path.)
- `getopts -x …` (an optstring that starts with `-`) → argv unreadable; with a
  non-literal word after it, rejected.

## Carried over from iteration 1 (unchanged design; line numbers updated)

- **Engine** — `src/nl_shell/gate/rules.py`: `_invocation` (`:208`) looks up the command
  word, then applies decision A (`_decision_a`, `:232`) or reads the argv with the row's
  grammar (`read_argv`, `:322`), checks each effect's condition (`holds`, `:428`) and
  runs one handler per effect type (`_HANDLERS`, `:807`, asserted against
  `commands.EFFECTS`). No command name appears in the engine. An argv the gate cannot
  read makes every condition hold.
- **Loader** — `src/nl_shell/gate/commands.py`, in the style of
  `src/nl_shell/targets.py:145-247`. `load(target_id=None)` (`:231`) takes no path, reads
  `targets.TARGETS_ROOT / <id> / "commands.toml"` and refuses a resolved path outside the
  root, as `targets.py:153` does. No `os.environ`, `Path.cwd`, `Path.home` or config read.
  With no target named, the default is the only target folder there is
  (`default_target`, `:219`), because `tests/test_targets.py:676-688` forbids an OS name
  in package code. Zero or several folders give decision C.
- **Budget** — `src/nl_shell/gate/parse.py`: `Work` counts units against `MAX_WORK`, one
  `Work` shared across the whole classification. The nested-text cache in `_inner_text`
  (`rules.py:267`) keeps the nine-deep here-doc input well under budget.
- **Pipeline** — `src/nl_shell/gate/__init__.py`: the table is loaded up front, so a
  missing or invalid table is decision C for every command.
- **Changes to #196's tests** (`tests/test_policy_gate.py`): 16 cases that asserted the
  stub's answer now assert the raised class (raises only). Unchanged from iteration 1.

### Decisions and trade-offs for the human (from iteration 1, still open)

- **Decision A false positives (accepted trade-off, per the brief).** Until #198's
  allowlist exists, `echo`, `man`, `which`, `apt`, `dpkg` are opaque, so `man sudo` /
  `which sudo` / `apt show sudo` as proposals are rejected, and `echo rm` is
  `destructive`.
- **Decision A extension:** a word names a command by its last path component, and a
  command word that is a path outside the system directories counts too
  (`/usr/local/bin/sudo -i` rejected as a proposal; cost: `./rm x` is `destructive`).
- **"Cannot read the argv ⇒ every condition holds"** over-raises `rm "$f"`,
  `kill "$pid"`, `systemctl restart "$svc"` to `destructive`, and rejects
  `printf "$fmt" …` / `read "$v"` (the name may be SUDO_PROMPT).
- Raises beyond the spec's §4 list: `systemctl kexec/soft-reboot/emergency/rescue`,
  `reboot`/`poweroff`/`halt`/`shutdown`, more disk tools, `chgrp -R`, more
  `git push` force forms, `systemd-run` without `--user` as elevating.
- `reads-terminal` is data only; the terminal-read rule is #198's.

### Gaps out of scope (follow-ups)

- Walker (#196): `(( X=1 ))`, `$((X=1))`, `: ${X:=v}`, `for X in` assign with no simple
  command.
- Interpreters (python3, perl, busybox, zsh) have no row; left for #198 per sign-off.
- `systemd-run --user -M root@.host bash` (security-review note, unconfirmed): drops
  `elevates` because of `--user`. Not in the carry-forward list; not changed.

## Verification

- **C4** through the project runner (`engine/scripts/run-verify.sh`, `PDCA_BUNDLE` and
  `PDCA_WORKTREE` set), on the final patch: green leg 418 passed; red leg 248 of 418
  failed → `PDCA-EVIDENCE: C4 PASS`. Afterwards `git diff` in the worktree equals
  `patch.diff` byte for byte.
- On the red leg, every case in `tests/test_gate_commands.py` failed except the 18 floor
  cases (`test_floor_cases_are_not_raised`). I checked by comparing the collected ids
  with the red leg's FAILED list.
- **Iteration-1 red leg.** I swapped in the iteration-1 versions of `rules.py`,
  `commands.py` and `commands.toml` (keeping the new test file) and ran
  `engine/scripts/run-suite.sh`: 25 failed, and all 25 are this iteration's new cases
  (every `test_sudo_family_*`, `test_env_split_*`, `test_non_literal_inner_*`,
  `test_more_root_shells_*`, `test_mapfile_*`, `test_enable_*`, and the `getopts --` and
  `wait -p` forms of both `SETS` tests). The only new test that stays green there is
  `test_chroot_with_a_command_opens_no_shell`, which guards against over-raising. Then I
  restored my files and checked `git diff` = `patch.diff`.
- **T3** through `engine/scripts/run-suite.sh` on the final tree: 1519 passed, 1 skipped
  → `PDCA-EVIDENCE: T3 PASS`. The one warning is a `forkpty` DeprecationWarning from
  `tests/test_session.py`, which this patch does not touch.
- **Formatter / hooks:** nl-shell configures none (no `.pre-commit-config.yaml`, no
  ruff/black config in `pyproject.toml`). CI runs `scripts/docs_links.py` (I ran it: 0
  broken of 64) and pytest. I kept lines added in this iteration within the repo's
  92-column limit. Some `# ---` section-header lines in `commands.toml` from iteration 1
  reach 95-96 columns; no tool checks TOML line length here.

### Refuting my own test

- **(a) Genuine red?** Yes. `run-verify.sh` reverted every production hunk and re-ran the
  bundle's tests: 248 of 418 failed, every non-floor case in the new file among them. In
  addition, against the iteration-1 engine all 25 new regression cases fail, so they bind
  this iteration's fixes, not only the stub-to-engine step.
- **(b) Production path?** Yes. Every case calls `nl_shell.gate.classify` (the full
  pipeline: parse, shell layer, engine) on the real `targets/ubuntu-26.04/commands.toml`
  through the real loader. No mock of the engine. The only stand-ins are tmp
  `TARGETS_ROOT` folders in the four loader-refusal tests, unchanged from iteration 1.
- **(c) Fixture includes the fault?** Yes. The cases are the confirmed attack strings
  from the sign-off carry-forward, typed in as given (`sudo-rs -i`,
  `env -S 'sudo\_-i'`, `getopts -- x SUDO_PROMPT`,
  `find /usr/bin -name sudo -exec {} -i \;`, `sudo bash /dev/stdin`, `sudo chroot /`,
  `mapfile -C 'sudo -i' …`, `wait -p SUDO_PROMPT`, `enable -f /tmp/x.so foo`). Nothing is
  curated out.

## Process note

Scratch files (a probe script, logs, a copy of my files during the iteration-1 swap) are
in the worktree's untracked `.scratch/`, which `patch.diff` leaves out. During the swap I
removed `commands.py` and `commands.toml` from the worktree before re-applying the
iteration-1 versions of them; both were restored from `.scratch/cur/` afterwards and the
final `git diff` equals `patch.diff`.

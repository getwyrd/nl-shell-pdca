# Brief — issue 197 / ast-policy-gate-command-engine

> Plan pass 3 (after `iterate-plan` at v2 sign-off). Re-planned around **bypass classes**:
> v1 and v2 each closed the bypasses the last review listed, and each review found a new
> batch of the same kinds. This brief states one rule per class, and the success criterion
> checks each rule over the whole table, so a new row or option cannot skip it.
> The human chose one bundle (no split) and accepted the seven classes below on 2026-10-26.

- **Slug:** ast-policy-gate-command-engine
- **Kind:** enhancement
- **Defect:** On `main` (`1a1e980`, #196 merged) the gate's command layer is a stub:
  `src/nl_shell/gate/rules.py:26-28` returns `mutating`, "not allowlisted" for every simple
  command. So `rm -rf build` is not `destructive`, `sudo apt update` is not `privileged`,
  `sudo -S true` is not rejected, and none of spec §3–§5's per-command rules fire. Add the
  **command layer**: a reviewed data table `targets/ubuntu-26.04/commands.toml` (format,
  loader, rows) and one generic engine in `gate/rules.py` that reads it. Wrappers, the sudo
  family, destructive commands, interpreters and builtins are data rows, not code paths.
  Each row gives the command's argv grammar (flags; value-taking options in short, attached
  and long `=` forms; end-of-options; where an inner command starts) and its effects from
  one fixed set: `runs-command-at`, `runs-text`, `runs-stdin-as-code`, `runs-file-as-code`,
  `stores-code`, `sets-variable`, `elevates`, `destroys` (with a condition),
  `reads-terminal`, `opens-shell`. Do may refine the effect names, but every rule below must
  be expressible in the table.

  **Decisions** (agreed in the #189 split plan, `results/issue_189/brief.md:99-112` in the
  pdca checkout):
  - **A**: an opaque command (no `commands.toml` row and no allowlist entry) is at least
    `mutating`, "not allowlisted". If any argument word, after quote removal, names a row
    with `elevates`, the command is `privileged` and a proposal is rejected. If one names a
    row with `destroys`, it is at least `destructive`.
  - **B**: code the gate cannot read (`runs-stdin-as-code` fed by a pipe or file;
    `runs-text` whose text is not literal or not in a grammar the gate parses;
    `runs-file-as-code`) is at least `destructive`, reason "runs code the gate cannot read".
    Literal text in a grammar the gate parses is classed recursively, within the budget.
    **Recursion runs the whole pipeline, not only `rules`.** Inner text goes through the
    same steps as the outer command (`gate/__init__.py:159-210`: §1.1 characters,
    `shell_layer`, untrusted features, `_redirects`, `_assignments` (where the
    `SUDO_PROMPT` rejection is, `:229-244`), `_shell_rules`, `rules.classify`, `live`,
    `sensitive`, `words`). So `bash -c 'export SUDO_PROMPT=x'` is rejected. The recursion
    entry point is `gate._classify`, or a function pulled out of it that takes the shared
    budget (below) and gives back a verdict. `rules.py` must not import `gate/__init__.py`
    (it is imported by it, `:31`). Either `rules.classify` returns "class this text in
    grammar G" and `__init__.py` does the recursion, or `__init__.py` passes in a callback.
    Do picks one and says which in build notes.
    **Shared work budget.** Today every `shell_layer` call builds a new `Walker` with
    `work = 0` (`parse.py:516`, `:1077`), so each nested layer gets its own `MAX_WORK`. The
    budget has to be one counter for the whole top-level `classify` call. The one
    `parse.py` change in scope: `shell_layer(source, *, budget=None)` takes an optional
    shared counter that `Walker.visit` (`:526-528`) adds to. When it is `None` you get
    today's behaviour. The recursion passes the outer call's counter to each inner call.
  - **C**: a gate failure (unhandled node, work budget used up, missing or invalid
    `commands.toml`, internal error) is `privileged`, rejected, reason "could not class".
    #196 already implements this (`src/nl_shell/gate/__init__.py:18-19`, `:48`, `:143`);
    this bundle sends its own failures there.

  **The seven bypass classes.** Each one is an invariant the engine must hold for every
  row. The v1/v2 findings are instances of these classes, listed as regressions in the
  success criterion.
  1. **Coverage.** Every binary on the target that elevates, or that runs a shell or an
     interpreter, has a row. That includes every alias name pointing at the same file as
     such a binary (`sudo-rs`, `sudo.ws`, `sudoedit-rs`, `su-rs` →
     `/usr/lib/cargo/bin/{sudo,su}`). The checked-in inventory (below) is the list a test
     checks this against.
  2. **No unread argv.** No row skips argv parsing (v2's `raw = true` rows are gone). An
     option a row does not declare is **never** read as a harmless flag: the command is at
     least `destructive`, reason "option the gate does not know". On a row with `elevates`,
     a proposal with such an option is also rejected. A row may describe only some
     subcommands (`git clean|reset|push`). Other subcommands get the row's stated default,
     at least `mutating`, so floor rows 8 and 27 stay as the spec says. **One named
     exception to this class:** the code-running options of the class-7 floor commands
     (`git`'s global `-c`/`--config-env`/`--exec-path`, and `tar --to-command`/`ssh -o` if
     those get rows) are declared on the row with a `class-7-gap` marker, not as harmless
     flags. They give the row's default (`mutating`, "not allowlisted"), not `destructive`.
     The loader accepts `class-7-gap` only on options named in the spec's class-7 text,
     and refuses it anywhere else. Every other undeclared option on these rows still
     follows the rule above. A row whose effects
     do not depend on argv (e.g. a non-elevating setuid binary such as `passwd`) may say so
     and give a fixed class (at least `mutating`). The undeclared-option rule then does not
     apply, but decision A still runs over its words. Every row that runs
     an inner command declares what it does when no command is given (for example
     `chroot`/`unshare` start `$SHELL`) and when stdin is the terminal (`bash -s x`,
     `bash /dev/stdin`). The loader refuses a row that leaves either one undeclared.
  3. **Grammar.** Every text effect names the grammar its text is read in: `bash`,
     `env-split` (uutils env 0.10.0 `-S`), `arithmetic` (bash arithmetic and `name[subscript]`
     evaluation), or another named one. The engine classes text only with a parser for that
     grammar. Text in any other grammar, or text the parser cannot fully translate, is
     decision B. bash is a parsed grammar. `env-split` is parsed, so `env -S 'sudo -i'` and
     `env -S '\_sudo -i'` are seen as `sudo -i`. Any escape it cannot translate (for example
     `${VAR}`) is decision B. In `arithmetic`, any `$`, backtick or `$(` in a subscript or
     value is decision B, and a name assigned inside the expression (`x=SUDO_PROMPT=1`)
     counts as a variable write under class 5. Every word bash evaluates as arithmetic or as
     a subscripted name is in the `arithmetic` grammar: `declare`/`typeset`/`local -i`
     values, `let`, and the name operands of `unset`, `test -v`/`[ -v`, `printf -v`, `read`,
     `mapfile`/`readarray`, `getopts`, `wait -p` and `declare`.
  4. **Run-time command words.** Every word that can reach command position when the command
     runs goes through the command-word check (decision A over it). That covers the words
     after `-c` text (they become `$0`, `$1`, …), the words after a script operand or
     `bash -s`, the literal arguments around `{}` in `find -exec`/`xargs`, and a non-literal
     inner command word.
  5. **Protected variables.** Every row that takes variable names marks which operands or
     option values are names. Changing the value of `SUDO_PROMPT`/`SUDO_ASKPASS`, exporting
     them, or making a nameref point at them is rejected, with or without `=` (`export
     SUDO_PROMPT`, `declare -x`, `typeset -x`, `readonly -x`, `local -x`, `declare -n`). The
     same forms on a §3 session name (`PATH`, `LD_*`, …) are at least `session-altering`.
  6. **Stored code.** Text kept to run later is classed as if it ran now, in its own
     grammar: `trap` text, `alias` values, `complete -C` text, the command part of
     `bind -x '"keys":cmd'` (decision B if it cannot be split), `mapfile -C` text, and
     the values of `PROMPT_COMMAND` (scalar or array) and `PS0`–`PS4` (a `$(…)`/backtick
     in a prompt string is classed as bash text). This holds however the value is set: a
     plain assignment, `export`/`declare`, or `printf -v`. A file that will be run later
     (`BASH_ENV=`, `ENV=`, `enable -f x.so`) is decision B.
  7. **Real text-runners get rows. The leftover gap is written down.** Every text-runner on
     the target inventory gets a row with its text effects: `busybox` (applet = inner
     command), `python3`, `perl`, `tclsh`, `gjs`, `gdb -ex`, `screen`. Rows are also added
     by name for runners the reviews found that this host lacks: `sg`/`newgrp`
     (`runs-text`, sh), `at`/`batch` (`runs-stdin-as-code`), `zsh`, `tmux`,
     `x-terminal-emulator -e`. Interpreter text in a grammar the gate does not parse
     (python, perl, tcl, js) is decision B. One gap is accepted and written into the spec
     and threat model: an unknown command that takes command text as one quoted word
     (`foo 'sudo -i'`). The same goes for code-running options of commands the spec leaves
     at the floor (`git -c core.pager=sh`, `tar --to-command=sh`, `ssh -o ProxyCommand=sh`,
     rows 8/10/11). These stay `mutating` "not allowlisted" and go to the confirm prompt.
     Decision A does not split quoted words.

  **Inventory.** `scripts/harvest_inventory.py` (style of `scripts/gen_unicode_tables.py`)
  writes `targets/ubuntu-26.04/inventory.toml` from this Ubuntu 26.04.1 host:
  - setuid/setgid/file-capability binaries in `/usr/bin`, `/usr/sbin`, `/usr/lib/cargo/bin`;
  - every name in those folders whose `realpath` is the same file as a listed binary or a
    row's binary;
  - `/etc/shells`;
  - the binaries of dpkg packages in sections `shells` and `interpreters`;
  - `python3*`, `perl*`, `busybox`, `gdb`.

  The file is checked in and reviewed like an allowlist change. The script records the
  host's `VERSION` line and is not run by any test. On this host today: 20 setuid/setgid
  binaries (e.g. `pkexec`, `su`, `sudo.ws`, `/usr/lib/cargo/bin/{su,sudo}`, `passwd`,
  `chsh`, `crontab`, `mount`); `/etc/shells` lists `sh`, `bash`, `rbash`, `dash`, `screen`.
  A row for a setuid binary that does not elevate (for example `passwd`) may just say so.
  What the check requires is that a row exists, so someone has reviewed it.

  Write the command table, decisions A–C, the seven class rules and the class-7 accepted
  gap into the spec (`docs/design/specs/policy-gate/v1.md` §4/§5 and a new §4.1) and the
  threat model (`.oss-scanner/threat_model.md:171-195`, the gate paragraph that still says
  "The command layer … still stubs").
- **Success criterion:** `tests/test_gate_commands.py` passes. Every case goes through the
  public `nl_shell.gate.classify(cmd, origin=...)`. Case groups:
  - **Class 1, coverage (property).** Every name in `targets/ubuntu-26.04/inventory.toml`
    has a `commands.toml` row. So the inventory cannot quietly shrink, the test also checks
    that it lists at least these names: `sudo`, `sudo.ws`, `sudo-rs`, `sudoedit-rs`, `su`,
    `su-rs`, `pkexec`, `passwd`, `chsh`, `crontab`, `mount`, `sh`, `bash`, `rbash`, `dash`,
    `screen`, `python3`, `perl`, `busybox`, `gdb`. Reviewer check at Check: re-run
    `scripts/harvest_inventory.py` on this host and diff it against the checked-in
    `inventory.toml`. Any difference is a finding. Regressions: `sudo-rs -i`, `sudo.ws -i`, `su-rs`,
    `/usr/bin/sudo-rs -i`, `sudoedit-rs /etc/shadow` are `privileged`. As proposals the
    first four are rejected. `echo pw | sudo-rs -S true` is rejected. `foo sudo-rs` is
    `privileged` and rejected as a proposal (decision A). `sg adm -c 'sudo -i'`,
    `busybox sh -c 'sudo -i'` as proposals are rejected (by recursion, as `bash -c 'sudo
    -i'`). `at now <<<'sudo rm -rf /'` is `privileged` (literal stdin, classed by
    recursion). `echo 'sudo rm -rf /' | at now` is at least `destructive` (decision B,
    piped stdin).
    `curl x | python3`, `python3 -c "$v"`, `perl -e 'system 1'` are at least `destructive`,
    "runs code the gate cannot read". `sudo zsh`, `sudo busybox sh` as proposals are
    rejected (root shell).
  - **Class 2, unread argv (property).** The loader refuses a row with `raw`, an unknown
    key, or a `runs-command-at` row with no no-command/terminal-stdin declaration. Every row
    carries a minimal example invocation. For every row that reads argv, that example plus
    an undeclared option (a test-chosen string such as
    `--pdca-undeclared`) is at least `destructive`, "option the gate does not know". The
    option goes **right after the command word**, before any operand, option value or
    inner command (`sudo --pdca-undeclared true`, `timeout --pdca-undeclared 5 true`), so
    it is the row's own option and not one of the inner command's arguments. For a row that
    describes subcommands, there is one more case with the option right after each described
    subcommand (`git clean --pdca-undeclared`). `class-7-gap` options (class 2's exception)
    are not undeclared and are tested in the floor group. For
    every row with `elevates` it is also rejected as a proposal. For every row declaring
    "opens a shell with no command", `sudo <row example with no command>` as a proposal is
    rejected. Regressions: `getopts -- x SUDO_PROMPT` rejected;
    `mapfile -C 'rm -rf ~' -c 1 a < f` at least `destructive`; `mapfile -C 'sudo -i' -c 1 a
    < f` rejected; `enable -f /tmp/x.so foo` at least `destructive`; `wait -p SUDO_PROMPT`
    rejected. As proposals these are rejected (root shell): `sudo bash -s x`,
    `sudo bash -is x`, `sudo dash -s x`, `sudo env bash -s x`, `pkexec bash -s x`,
    `sudo bash /dev/stdin`, `sudo chroot /`, `sudo unshare`.
  - **Class 3, grammar (property).** For every row field in the `arithmetic` grammar,
    putting `'a[$(rm -rf ~)]'` there gives at least `destructive`, "runs code the gate
    cannot read". For every text effect in an unparsed grammar, literal text is decision B.
    Regressions: `env -S 'sudo -i'`, `env -S 'sudo\_-i'`, `env -S '\_sudo -i'`,
    `env -S '\_sudo\_-i'`, `env -S '-i\_sudo\_-i'` as proposals are `privileged` and
    rejected. `env -S 'rm\_-rf\_/'` is at least `destructive`. `env -S '${X}'` is decision
    B. These are at least `destructive`: `declare -i x='a[$(rm -rf ~)]'`,
    `a=(1); unset -v 'a[$(rm -rf ~)]'`, `test -v 'a[$(rm -rf ~)]'`,
    `printf -v 'a[$(rm -rf ~)]' x`. As proposals these are rejected:
    `typeset -i x='a[$(sudo -i)]'`, `unset 'x[$(sudo -i)]'`, `declare -i x=SUDO_PROMPT=1`.
  - **Class 4, run-time command words (property).** For every row with a `runs-text`
    effect that passes later words as positional parameters, `<row> '"$@"' _ sudo -i` (or
    the row's equivalent form) as a proposal is rejected. Regressions (proposals): `sh -c
    '$0 -i' sudo` and `bash -c '"$0" -S true' sudo` rejected; `sh -c '"$@"' _ rm -rf ~` at
    least `destructive`; `bash -s _ sudo -i <<<'"$@"'` and `bash /dev/stdin sudo -i
    <<<'"$@"'` rejected; `find /usr/bin -name sudo -exec {} -i \;` rejected;
    `printf rm | xargs -I% % -rf ~` at least `destructive`.
  - **Class 5, protected variables (property).** For every row field marked as a name,
    putting `SUDO_PROMPT` there gives a rejection as a proposal, and `PATH` gives at least
    `session-altering`. Regressions (rejected): `export SUDO_PROMPT`,
    `export "SUDO_PROMPT"=x`, `declare -x SUDO_ASKPASS`, `typeset -x SUDO_PROMPT`,
    `readonly -x SUDO_PROMPT`, `local -x SUDO_PROMPT` (inside a function body),
    `declare 'SUDO_ASKPASS'=/x`, `declare -n r=SUDO_ASKPASS; r=/x`,
    `printf -v SUDO_ASKPASS /x`, `read SUDO_PROMPT <<<x`, `mapfile SUDO_PROMPT <x`,
    `getopts x SUDO_PROMPT`, `let SUDO_ASKPASS=1`, `wait -p SUDO_PROMPT`. The same
    forms naming `PATH` or `LD_PRELOAD` are `session-altering`. `export "SUDO_PROMPT"=x` and
    `declare 'SUDO_ASKPASS'=/x` are **already rejected on `main`** (checked at Plan:
    `_declared`, `parse.py:813-828`, then `__init__.py:236-237`). They are pinned against
    regression and are not part of the red-leg claim. Put them in their own test function
    (for example `test_class5_pinned`) so Check does not read a stub pass there as a test
    defect.
  - **Class 6, stored code (property).** For every row with a `stores-code` effect, the
    row's example with stored text `sudo -i` as a proposal is rejected, and with
    `rm -rf ~` it is at least `destructive`. Regressions: `trap 'rm -rf ~' EXIT` at least
    `destructive`. These are rejected as proposals: `trap -- 'sudo -i' EXIT`,
    `alias ls='sudo -i'`, `export PROMPT_COMMAND='sudo -i'`, `PROMPT_COMMAND='sudo -i'`,
    `PROMPT_COMMAND=('sudo -i')`, `PS1='$(sudo -i)'`. These are at least `destructive`:
    `complete -C 'rm -rf ~' x`, `bind -x '"\C-x":rm -rf ~'`, `BASH_ENV=/tmp/x`.
    `alias ll='ls -l'` (row 33) stays `session-altering`, never lower.
  - **Class 7, accepted gap (documented, not raised).** `foo 'sudo -i'` is `mutating`,
    "not allowlisted", and so are floor rows 8, 10, 11, 27 (`git -c core.pager=sh log`,
    `git status`, `tar --to-command=sh -xf a.tar`, `ssh -o ProxyCommand=sh h`). These sit in
    a test function named for the floor group. They are not part of the red-leg claim,
    since the stub gives the same answer. The spec states the gap.
  - **Spec §4 privileged:** row 24 (`sudo apt update`) `privileged`; `su`, `pkexec`,
    `doas`, `run0`, `machinectl shell`, `machinectl shell root@`; `//usr/bin/sudo true`
    `privileged`, never lower.
  - **Spec §4 destructive:** row 26 (`rm -rf build`), row 17 (`"r"m -rf ~`), row 18
    (`ls; rm -rf ~`), row 29 (`systemctl stop ssh`), row 9 (`find . -exec rm {} \;`), and
    `dd`, `mkfs.ext4`, `wipefs`, `shred`, `truncate`, `chmod -R`, `find -delete`,
    `git clean`, `git reset --hard`, `git push --force`, `kill -9 -1`. Row 9 is derived
    (record it in the spec): `{}` is a non-literal operand of the inner command, and `rm`
    with a non-literal operand is classed like `rm` with a glob (§4) ⇒ `destructive`.
  - **Spec §4 wrappers (property + regressions).** Every row with `runs-command-at` carries
    a minimal example prefix (e.g. `timeout 5`). For every such row, `<prefix> rm -rf x` is
    at least `destructive` and `<prefix> sudo -i` as a proposal is `privileged` and
    rejected. Named: `env rm -rf x` (row 32) `destructive`; `nice`, `nohup`, `timeout`,
    `time`, `xargs`, `watch`, `bash -c`, `sh -c` take the inner class and are at least
    `mutating`; `xargs`/`find -exec` with a non-literal inner command at least
    `destructive`. These proposals are `privileged` and rejected (typed: `privileged`):
    `env - sudo -i`, `env 'A=1' sudo -i`, `env -a x sudo -i` (uutils env 0.10.0 takes a
    value for `-a`/`--argv0`), `exec -a x sudo -i`, `nice -n5 sudo -i`,
    `timeout -s9 5 sudo -i`, `stdbuf -o0 sudo -i`, `setsid sudo -i`, `flock /tmp/l sudo -i`,
    `script -c 'sudo -i'`. `env - rm -rf ~` is `destructive`. Ten nested `env`s around
    `sudo -i` as a proposal: `privileged` and rejected, never lower.
  - **Spec §5 sudo rules.** Rejected: row 21 (`sudo -S true`, `sudo -p x true`,
    `sudo -A true`); row 22 (`echo pw | sudo -S true`); `sudo "-S" true`; `sudo $'-S' true`;
    `sudo "$P" true`; `sudo -s <<<x`; `printf x | sudo -i`; a pipe, here-doc or here-string
    into `sudo`, `su`, `pkexec`, `doas`; `cat <<E | sudo tee /x` and `cat <<E | doas id`
    (with the pipe reason). Proposals `sudo -i`, `sudo -s`, `sudo su`, `sudo bash`, bare
    `su`, `pkexec bash` are rejected; typed, they are `privileged`.
  - **Spec §3 builtins.** Row 33 and `unalias`, `source`, `.`, `eval`, `exec`, `trap`,
    `enable`, `set`, `shopt`, `bind`, `complete`, `hash`, `builtin`, `command` (except
    `command -v`/`-V`, `v1.md:101`), `export`, `declare`/`typeset`/`local`/`readonly` with
    assignments, and `unset` are at least `session-altering`.
  - **Decision A:** `foo sudo x` is `privileged` and rejected as a proposal; `foo rm -rf x`
    is at least `destructive`.
  - **Decision B:** `x | sh`, `bash < f`, `bash f.sh`, `bash -c "$v"`, `eval "$v"`, `. ./f`,
    `echo 'sudo rm -rf /' | bash` are `destructive`, "runs code the gate cannot read".
    `bash -c 'rm -rf ~'`, `bash <<<'rm -rf ~'`, `bash -s <<<'rm -rf /'`,
    `. /dev/stdin <<<'rm -rf /'` and a quoted here-doc running `rm -rf ~` are `destructive`
    by recursion. `bash <<<'sudo ls'` as a proposal is rejected. `bash -c 'true'` is not
    raised by decision B (floor group).
  - **Work budget.** `{ bash;bash;bash;bash; } <<'E0'` nested nine deep (about 320 bytes;
    v2 grew ×4 per level) gives a result never below `mutating` (decision C if the budget
    runs out), under a loose 10 s timeout that only guards against a hang. Sharing is
    tested through the public API by its effect, not by reading a counter (`Result`,
    `__init__.py:83-88`, has no work count, and none is added). The test builds one text
    `T` (for example a run of `:;`, sized by the test from `MAX_WORK`) that `bash -c 'T'`
    classes normally on its own, with no "could not class". `bash -c 'T'; bash -c 'T';
    bash -c 'T'` (still under the 8 KiB input cap) must then be decision C, "could not
    class", because the inner walks add up past `MAX_WORK`. On the stub this case is
    `mutating` with no "could not class", so it goes red. Do may change the size of `T` or
    the repeat count, but must keep "alone fits, together does not".
  - **Decision C on table failure.** A missing or invalid `commands.toml` gives decision C
    for every command, never a silent `mutating`.
  - **Fixed load location.** The loader takes no path argument. It reads
    `TARGETS_ROOT / <id> / "commands.toml"` (`src/nl_shell/targets.py:28`) and refuses a
    resolved path outside that root, as `targets.py:153-155` does. **`<id>` is a
    module-level constant, `"ubuntu-26.04"`**, in the loader module. v1 ships one target,
    and `classify()` (`__init__.py:147`) has no target argument. Choosing the target from
    `/etc/os-release` (`targets.select`, `:249`) is out of scope: it would make the gate's
    answer depend on the host file. **Test seam for the missing/invalid-table cases:** the
    test monkeypatches the loader module's root constant to a `tmp_path` holding a missing
    or broken `commands.toml`, and clears the loader's cache if it has one. That is the only
    seam. It is a test-time patch of a module attribute, not an env/cwd/config read, so it
    does not break the reviewer check below. Reviewer check: no
    `os.environ`, `Path.cwd()`, `Path.home()` or config read in the loader. Test: with a
    `commands.toml` in the test's cwd that says `sudo` is harmless, and `NL_SHELL_COMMANDS`,
    `NL_SHELL_TARGETS`, `XDG_CONFIG_HOME` pointing at a folder holding such a file,
    `sudo -i` stays `privileged`.
  - **Assertions.** Every case asserts the class (or a floor), a reason substring, and that
    no reason is "could not class". The exceptions: the missing/invalid-table cases assert
    "could not class"; the ten-`env` and budget cases accept the engine's reason or "could
    not class", but never a class below the one stated.
- **Falsifiability:** Plain pytest on this host (Ubuntu 26.04.1, bash 5.3.9, `.venv` with
  tree-sitter-bash). C4 (`engine/scripts/run-verify.sh`) reverts the production hunks
  (`src/`, `targets/`, `scripts/`) and keeps `tests/test_gate_commands.py`. That restores
  the stub at `rules.py:26-28` and removes `commands.toml` and `inventory.toml`. Checked at
  Plan on `main`: one case from each class 1–6 (`sudo-rs -i`, `getopts -- x SUDO_PROMPT`,
  `sudo chroot /`, `env -S '\_sudo -i'`, `declare -i x='a[$(rm -rf ~)]'`,
  `sh -c '$0 -i' sudo`, `export SUDO_PROMPT`, `alias ls='sudo -i'`) comes out `mutating`,
  not rejected, so every non-floor group goes red. The red-leg claim is per group, not per
  case: the floor group and `test_class5_pinned` may pass on the stub. The budget-sharing
  case goes red on the stub too (`mutating`, not "could not class"). The test lists its cases inline (no
  dependence on new vector rows) and reads the inventory and table inside test functions,
  so the red leg fails at run time, not at collection. Import `nl_shell.gate` and any new
  loader module inside test functions. A module-level import of an API the patch adds turns
  the red leg into UNVERIFIABLE (`run-verify.sh:196`).
- **Invariant to restore:** Meaning is closed-world. A command gets a meaning only from
  reviewed data (`commands.toml`, later the allowlist). Every part of a command that can
  run code, elevate, or change a protected variable is read by the engine in its own
  grammar or gets an explicit fail-closed default: an unknown command, an undeclared
  option, a foreign grammar, a run-time command word, stored code. It is never silently
  `mutating`. This holds over every row, not only the rows the tests name. Sources:
  ADR-0013, ADR-0015; `policy-gate/v1` §1 step 4, §3–§5, Versioning (`v1.md:238-239`:
  raising a class is compatible within v1 but needs human review); threat model "What must
  hold" (`.oss-scanner/threat_model.md:121-125`, the `SUDO_PROMPT`/`SUDO_ASKPASS` and
  pipe-into-sudo rules).
- **Repo + branch target:** eduralph/nl-shell @ main
- **Depends on:** 196
- **Ordering note:** #196 is merged and closed (`1a1e980`, PR #203), so this builds on
  `main` directly. Sibling #198 (allowlist) is not a prerequisite. It builds on this
  table, and the file both touch is `targets/ubuntu-26.04/gate-vectors.toml` (appended
  rows only).
- **Milestone / ADRs:** M0 — REPL prototype. ADR-0013, ADR-0015, ADR-0023.
- **Surfaces:** data
- **Difficulty:** high
- **Scope:** The command layer as above. Files in scope:
  - `src/nl_shell/gate/rules.py` (engine, replacing the stub);
  - a `commands.toml` loader in the style of `src/nl_shell/targets.py:145-247`;
  - `targets/ubuntu-26.04/commands.toml`;
  - `targets/ubuntu-26.04/inventory.toml` and `scripts/harvest_inventory.py`;
  - `gate-vectors.toml` rows for this child;
  - `src/nl_shell/gate/__init__.py`: (a) the `rules.classify` call at `:196` gets the
    origin. `Invocation` already carries `assignments` (`parse.py:805`), which class 6
    reads for plain `PROMPT_COMMAND=`, `PS1=`, `BASH_ENV=`. (b) The recursion entry point
    (decision B): `_classify` (`:159-210`) is restructured so inner text re-enters the full
    pipeline with the shared budget, without a `rules` → `gate` import cycle. Assignments
    with no simple command are out of scope (below);
  - `src/nl_shell/gate/parse.py`: **only** the shared-budget seam, an optional
    `budget` argument on `shell_layer` (`:1070`) that `Walker` (`:516`, `:526-528`) counts
    into. No other walker change, except the walker-bug escape hatch below;
  - spec and threat-model text (raises only);
  - `tests/test_gate_commands.py`.

  Out of scope:
  - the walker and stdin context (#196), apart from the `shell_layer` budget seam named
    above. Fix there only if a case here exposes a walker bug, and say so in build notes;
  - assignments and expansions with no simple command: `(( SUDO_ASKPASS=1 ))`,
    `for SUDO_PROMPT in x`, `: ${SUDO_ASKPASS:=/x}`, `[[ -v 'a[$(…)]' ]]`, `x=sudo; $x -i`.
    These are walker work; the human files a follow-up;
  - the allowlist, the terminal-read rule, the here-doc exemption (#198);
  - §7 (#192); §8 and the "`>` truncates an existing file outside the cwd" rule (#190);
  - mixed-script words (#191); confirm UI (#74); REPL wiring (#78); sudo passthrough (#13);
  - `systemd-run --user -M root@.host` (unconfirmed in v1; follow-up only if checked in
    the reference VM).

  Do not reuse `src/nl_shell/failure_classes.py:199` `is_privileged`. Its name list at
  `:97-99` may be cited as a cross-check for class 1.

  **Review contract:** Check's reviewers test the seven class rules. A bypass inside one of
  these classes is a defect in this bundle. A bypass that fits no class here goes to a
  follow-up issue and does not by itself reject this bundle.
- **Repro instruction:** In the `main` checkout (`/home/eddie/nl-shell/nl-shell`), with the
  pdca venv: `PYTHONPATH=src /home/eddie/nl-shell/nl-shell-pdca/.venv/bin/python3 -c 'from nl_shell.gate import classify; print(classify("rm -rf build"), classify("sudo -S true", origin="proposal"))'`
  gives `mutating`, "not allowlisted", not rejected, for both.
- **External dependencies:** `tree-sitter-bash`
- **Test file:** tests/test_gate_commands.py
- **Citations expected:** Do must cite path:line on the target branch for every change.
  Peer to mirror for the loader: `src/nl_shell/targets.py:145-160` (plain-id check,
  `is_relative_to` refusal, missing-file error). Peer for decision C:
  `src/nl_shell/gate/__init__.py:143-157` (`_could_not_class`, `classify` never raises).
  Peer for the work budget: `src/nl_shell/gate/parse.py:39-41` and the counter at
  `:516`/`:526-528`. Peer for the recursion entry point: `_classify`,
  `src/nl_shell/gate/__init__.py:159-210`.
- **Prior-art check (triage cycles):** By path on eduralph/nl-shell: `rules.py`,
  `commands.toml` and `tests/test_gate_commands.py` have only #196's stub commit
  (`59ce736`). No open or closed PR or branch for #197. Two earlier attempts exist in this
  bundle: `iteration-v1/` and `iteration-v2/`, about 135 KB each. Their reviews
  (`check-advisory-adversary.md`, `check-advisory-security-review.md`) are the source of
  the regression cases. Both hand-coded per-command exceptions (`raw` rows,
  `_PIECE_SPLIT`, per-builtin special cases), which is why each review found more of the
  same kind. Do not port those code paths. Build the class rules into the engine and the
  row format, then write the rows.
- **Impact & compatibility:** No new runtime dependency. The spec gains the command table,
  decisions A–C, the seven class rules and the class-7 gap (raises only; compatible within
  v1; human-reviewed at sign-off). The spec states that `commands.toml` and
  `inventory.toml` rows are reviewed like allowlist entries. Removing a row or an effect
  can lower a class, so that is a v2 change (spec Versioning). Expect the size backstop to
  fire (about 100 KB or more): the human chose one bundle with this scope.
- **Disposition hint:** new-feature

Plan-review response: all seven findings in `plan-advisory-plan-reviewer.md` were accepted
and the brief was revised in place. (1) Budget: `parse.py`'s `shell_layer(budget=)` seam is
now in scope, and the "units used" assertion is replaced by a public-API case ("alone fits,
three together give decision C"), sized at Plan: `:;`×1000 is about 3000 units and 2 KB.
(2) The recursion entry point is `_classify`, with no `rules` → `gate` import cycle. The
`__init__.py` scope line is corrected (only `origin` is missing; `Invocation.assignments`
already exists). (3) git/tar/ssh code-running options are a named `class-7-gap` exception to
class 2, limited to the spec's class-7 list. This follows the human's accepted class-7 gap;
**the human should confirm the exception at sign-off.** (4) The inventory test asserts the
named members (all checked present on this host), and Check re-runs the harvest script and
diffs it. (5) The undeclared option goes right after the command word (and after each
described subcommand). (6) The target id is a module constant `"ubuntu-26.04"`, and the
test seam is a monkeypatched root constant. (7) `export "SUDO_PROMPT"=x` and
`declare 'SUDO_ASKPASS'=/x` were confirmed rejected on `main` and moved to a pinned group
outside the red-leg claim.

## STOP discipline

Draft only until Check sign-off. Pushing to a feature/draft branch and opening a
draft PR MAY happen during the cycle (useful for CI feedback). The PR MUST NOT be
marked ready before sign-off accepts.

## Iteration 3 — carry-forward (from the previous attempt)
- Sign-off rationale: Slice too big; split it in Plan rather than rebuild. Third round with the same pattern: each build closes the last review's bypass list and the reviewers find a new batch of the same kinds. Patch is 203 KB (2x the 100 KB backstop). v3 still has in-class bypasses: `[ -v 'a[$(…)]' ]`; nameref target subscripts (`declare -n r='x[$(sudo -i)]'; r=1`); quoted compound array values (`declare -a PROMPT_COMMAND='("sudo -i")'`, `declare -a x='($(sudo -i))'`); run-time command words filled by non-literal/stdin positionals (`bash -c '"$@"' _ "$v"`, `xargs sh -c '"$@"' _`); undecoded ANSI-C words (`$'\x73udo' -i`); stdin into shells opened with no command (`unshare <<<'sudo -i'`, `chroot /`, `script`, `sg`, `newgrp`); `fc -e` text read as a file, not bash; `BASH_FUNC_*%%` env assignments. Also a scope drift: target id picked as the sole folder under targets/ instead of the agreed constant "ubuntu-26.04" (commands.py:63-73). Open spec question for the re-plan: should non-literal parsed text that names sudo / a §5 form (`bash -c "sudo -i $x"`, `eval "sudo -S true${x:-}"`) be rejected rather than decision B "destructive"? The threat-model text added in v3 claims it cannot hide. Split with `nl-shell-pdca split 197` so each child owns a small set of classes and its own adversarial review, instead of one bundle carrying all seven.
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Slice too big; split it in Plan rather than rebuild. Third round with the same pattern:
  each build closes the last review's bypass list and the reviewers find a new batch of the
  same kinds. Patch is 203 KB (2x the 100 KB backstop). v3 still has in-class bypasses:
  `[ -v 'a[$(…)]' ]`; nameref target subscripts (`declare -n r='x[$(sudo -i)]'; r=1`);
  quoted compound array values (`declare -a PROMPT_COMMAND='("sudo -i")'`,
  `declare -a x='($(sudo -i))'`); run-time command words filled by non-literal/stdin
  positionals (`bash -c '"$@"' _ "$v"`, `xargs sh -c '"$@"' _`); undecoded ANSI-C words
  (`$'\x73udo' -i`); stdin into shells opened with no command (`unshare <<<'sudo -i'`,
  `chroot /`, `script`, `sg`, `newgrp`); `fc -e` text read as a file, not bash;
  `BASH_FUNC_*%%` env assignments. Also a scope drift: target id picked as the sole folder
  under targets/ instead of the agreed constant "ubuntu-26.04" (commands.py:63-73).
  Open spec question for the re-plan: should non-literal parsed text that names sudo /
  a §5 form (`bash -c "sudo -i $x"`, `eval "sudo -S true${x:-}"`) be rejected rather than
  decision B "destructive"? The threat-model text added in v3 claims it cannot hide.
  Split with `nl-shell-pdca split 197` so each child owns a small set of classes and its own
  adversarial review, instead of one bundle carrying all seven.
- Full previous attempt preserved in `iteration-v3/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

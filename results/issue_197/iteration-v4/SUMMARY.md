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
  - **B′** (human's decision at pass 4, raises only): before decision B applies to
    non-literal text in a parsed grammar, the engine parses the text with each expansion
    (`$x`, `${…}`, `$(…)`, backticks) standing as one unknown word, and classes what it can
    see. The result is the higher of that class and decision B's `destructive`. So
    `bash -c "sudo -i $x"`, `eval "sudo -S true${x:-}"`, `trap "sudo -i $x" EXIT`,
    `alias ls="sudo -i $x"`, `PROMPT_COMMAND="sudo -i $x"` as proposals are rejected, the
    same as the literal form. An expansion inside the command word (`"sud${x}o -i"`) leaves
    it unreadable: decision B only. If the text with holes does not parse, decision B only.
    This makes the threat-model claim "`sudo -S` … cannot hide" true; the spec states B′
    as part of §4.1.
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
    `_declared`, `parse.py:816-828`, then `__init__.py:236-237`). They are pinned against
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
    runs out), under a loose 10 s timeout that only guards against a hang. (This departs
    from the tracker's "under one second"; the reason and the human's call are recorded in
    child-2's criterion in `split-proposal.md`.) Sharing is
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
    origin. `Invocation` already carries `assignments` (`parse.py:171`), which class 6
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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (46 of 211 failed), green with it
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

Review child A of #197: replace the policy gate's command stub with a reviewed command table and generic engine for elevation, destruction, wrappers, argv coverage, and sudo restrictions.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | Child A's engine/table boundary is explicit; recursive text and protected-variable work belong to B/C, rather than being promised by this patch (brief.md:461; target/tests/test_gate_commands.py:1). |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence demonstrates behavioral red, including sudo-rs returning mutating instead of privileged; 46 failures are separate from four missing-module setup errors (gate-logs/C4-verify.log:1511; target/tests/test_gate_commands.py:149). |
| C3 Change | PASS | The patch addresses the command-layer stub within A's scope, including the expressly assigned ANSI-C quoting case; source parses and git diff --check succeeds (target/src/nl_shell/gate/rules.py:117; target/src/nl_shell/gate/parse.py:254). |
| C4 Verification (red→green) | PASS | Frozen logs show 215 focused tests green and 46 assertion failures pre-fix; local pytest/tree-sitter are absent, so this is log-supported verification, not an independent public-API rerun (gate-logs/C4-verify.log:14; gate-logs/C4-verify.log:1511). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Fix ANSI-C NUL truncation before relying on command recognition: Bash resolves the tested quoted word to sudo, but the decoder marks sudoignored nonliteral and the engine skips lookup, leaving the sudo rejection path bypassable (target/src/nl_shell/gate/parse.py:352; target/src/nl_shell/gate/rules.py:138). |
| T1 Structure | PASS | Command policy lives in reviewed rows with a generic recursive argv engine and strict loader; no new optional-capability probe masks a load-time cause (target/src/nl_shell/gate/commands.py:283; target/src/nl_shell/gate/rules.py:131). |
| T2 Shape | PASS | Security behavior and its accepted text-reading/class-7 limitations are documented in the threat model; the touch gate's captured output confirms the required update (target/.oss-scanner/threat_model.md:192; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | The frozen full-suite run reports 1408 passed, one skipped and five PTY warnings; the independent inventory harvest matches exactly and all 95 inventory names have rows (gate-logs/T3-suite.log:41; target/scripts/harvest_inventory.py:177; target/targets/ubuntu-26.04/inventory.toml:1). |
| T4 Contribution | N/A | Contribution artifacts are intentionally absent at Check; the substantive audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art across merged and closed/rejected work, and approve the new policy rows: the brief records only three paths, the sandbox has one synthetic base commit, and INTEGRATION §4 is not supplied (brief.md:401; target/docs/design/specs/policy-gate/v1.md:320). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether A's conservative unreadable-code floor and documented class-7 confirmation gap fit the staged rollout before B/C land; passing classifier tests do not establish that product/security tradeoff (brief.md:466; target/tests/test_gate_commands.py:287; target/docs/design/specs/policy-gate/v1.md:320). |

Independent checks and actionable finding:

- Ran `python3 target/scripts/harvest_inventory.py --output inventory-rerun.toml`, then diffed it against the target inventory: no differences. Parsed the TOML independently: 82 command rows cover all 95 harvested names. Python source AST parsing and `git -C target diff --check` passed.
- The sandbox's `python3` lacks both `pytest` and `tree_sitter`, and no target `.venv` exists. Therefore a stash/red/pop/green run here cannot execute the classifier. Read all four frozen gate logs instead; their original runs exercised the real parser and full suite, without evidence of a substitute tool or fixture. No target changes were made.
- Executed the actual `lex_word` and `_ansi_c` function definitions extracted via Python AST, with their actual constant definitions, and compared them with `bash --noprofile --norc -c` using only `printf` to observe quote removal. No sudo or destructive command was executed. For the source word `$'sudo\0ignored'`, Bash printed `sudo`; `lex_word` returned `('sudoignored', frozenset({'ANSI-C escape the gate cannot decode'}))`. `$'rm\0ignored'` similarly became `rm` in Bash and nonliteral `rmignored` in the decoder. The existing `$'\x73udo'` control correctly became literal `sudo` in both.
- The impact follows from target source: `make_word` preserves that nonliteral status (target/src/nl_shell/gate/parse.py:364), `_command` returns before table lookup for such a head (target/src/nl_shell/gate/rules.py:138), and the shell-level command-word rule raises only to mutating (target/src/nl_shell/gate/__init__.py:255). Thus the source path predicts `$'sudo\0ignored' -i` avoids privileged/root-shell rejection, and `$'rm\0ignored' -rf build` avoids destructive classification. This is a directly reproduced decoder discrepancy plus a code-grounded consequence, not a claimed end-to-end classifier observation.
- Correctly truncate the ANSI-C quoted segment at NUL while preserving any concatenated suffix outside that segment, or fail closed. Add public-classifier regressions for the two examples above and `foo $'sudo\0ignored'` (decision A). Existing ANSI-C tests cover hex spelling but not truncation (target/tests/test_gate_commands.py:429). Rerun those regressions in the real parser environment, with an independent red→green.
- Prior-art investigation in the supplied target returned only `284104e pre-fix base ...` for affected-path history. The synthetic history cannot confirm merged history or closed/rejected PRs; the brief's recorded prior-art search does not cover every changed path. This limitation is a human decision item, not evidence of conflicting prior work.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — #197 child A (engine + table)

I re-ran about 230 probe commands through the public `nl_shell.gate.classify` on the patched
tree at `$PDCA_TARGET`, using the pdca venv. I also re-ran `scripts/harvest_inventory.py --output`
into my scratch folder and read the frozen C4/T3 logs. Two fixable bypasses survive, plus one
scope question for the human.

## Findings

- NEEDS-HUMAN [impl] — **A root shell slips through when an unreadable word sits on the inner command's argv.** Proposals `sudo bash $x`, `sudo env $x bash`, `sudo nice $x bash`, `sudo xargs -o bash` and `sudo busybox --pdca` all come back `privileged` with `rejected=False`. With `x` unset, `sudo bash $x` runs as `sudo bash`, which §5 says must be rejected (`sudo bash` alone is rejected). Cause: `elevated` is computed separately for each row (`src/nl_shell/gate/rules.py:212-222`). The inner `bash` row is not elevating, so its unreadable or undeclared word only raises the class to `destructive` (`rules.py:252-265`) and never calls `reject_proposal`. The unreadable word also keeps `opens` from being set, so the root-shell check at `rules.py:656-664` never fires either. The class-2 property test (`tests/test_gate_commands.py:233-252`) only puts the undeclared option on the elevating row itself, so it cannot catch this. Fix: pass the outer row's `elevated` down through `_inner`/`_command`, so an undeclared option or unreadable word in any command run under elevation rejects the proposal. Then add `sudo bash $x` and `sudo env $x bash` as regressions.

- NEEDS-HUMAN [impl] — **`script` has no row, so `sudo script` is an unrejected root shell.** With no command, `/usr/bin/script` (present on this host) starts `$SHELL`. `sudo script`, `sudo -u root script` and `sudo busybox script` come back `privileged`, `rejected=False`, and plain `script` is `mutating`, "not allowlisted". `targets/ubuntu-26.04/commands.toml` has no `script` row (no `names` entry matches; the wrappers sit around `:427`-`:631`). The brief lists `script -c 'sudo -i'` among the §4 wrappers. Class 2 says a command that runs an inner command must declare its no-command behaviour. The split hands "stdin into `script`" to child B, which assumes child A already gave `script` a row. Fix: add a row with `no_command = "opens-shell"` and `-c` as `runs-text` (bash). Child A classes that text as decision B for now.

- NEEDS-HUMAN [human] — **Wrappers with no row hide a root shell from decision A.** Proposals `sudo strace bash`, `sudo setarch x86_64 bash`, `sudo taskset -c 0 bash`, `sudo chrt -f 1 bash`, `sudo prlimit bash`, `sudo dbus-run-session bash`, `sudo systemd-inhibit bash`, `sudo setpriv bash` and `sudo runuser -u root bash` all give `privileged`, `rejected=False`. All of these binaries are on this host. Decision A (`rules.py:165-178`) only checks whether an argument names an `elevates` or `destroys` row. It never checks for a row that opens a shell. That matches the brief's wording of decision A, and class 1's inventory criteria do not cover plain wrappers, so this is not a slip against the letter of the brief. But it makes §5's "`sudo bash` is rejected" easy to sidestep. A human should pick one of three: (a) under an elevating row, treat an argument that names an `opens-shell` row as a root shell; (b) widen class 1's inventory to cover wrappers that run commands; (c) record it as a follow-up outside this bundle's classes.

- Not a child-A defect, noted for child B: `su -c bash` and `su - root -c id` are `privileged` plus decision B, not rejected (`su -c bash` with a terminal is an interactive root shell). Child A classes text as decision B by design, so this depends on child B's recursion. Child B should include `su -c bash` as a regression.

## Attempts that did not refute the fix

- **Red→green evidence.** `gate-logs/C4-verify.log`: every test function in `tests/test_gate_commands.py` fails on the stub except `test_floor_class7_accepted_gap`, which the brief exempts. Failures come at run time, not at import or collection. The tests call the public `classify` (`tests/test_gate_commands.py:98`), not a copy of the engine. T3 is green (1408 passed).
- **Inventory.** I re-harvested on this host and diffed against `targets/ubuntu-26.04/inventory.toml`. The two files are identical.
- **§5 sudo rules.** These were all handled correctly: abbreviations (`--st`, `--as`), bundles (`-Si`, `-iS`, `-uroot -S`), `$'-S'`, `"$P"`, `sudo $x`, here-strings, pipes through `nice`/`timeout`/`env`/`setsid`/`find -exec`, and pipes into `su`/`pkexec`/`doas`.
- **§4 wrappers.** Every named wrapper form wrapped around `sudo -i` is rejected, including ten nested `env`s. ANSI-C and backslash command words (`$'\x73udo' -i`, `s\udo -i`, `foo $'\x73udo'`) are rejected. So are `{sudo,-i}` and `{sudo,bash}`, as unparseable proposals.
- **Decision A** catches `--exec=/usr/bin/sudo`, `x=sudo`, `./sudo`, `sudo.ws` and the cargo `su` path. `foo -esudo` and `foo SUDO` stay `mutating`. Both fit the documented gap (quoted or joined words are not split).
- **§4 destructive** rows all reach `destructive`. `rm -f x`, `cp /dev/zero /dev/sda`, `rsync --delete` and `git branch -D` stay `mutating`, but the brief's §4 list does not name them.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review — issue 197, child A (command engine + table)

**Attacker-reachable inputs this diff touches:** the model's proposed command (threat model item 5) and, through wrappers, the data a wrapper feeds into its inner command at run time (file contents and command output piped into `xargs`, items 1–2). All of it reaches the new engine in `src/nl_shell/gate/rules.py` and the table `targets/ubuntu-26.04/commands.toml`.

How I checked: I ran the patched gate (`nl_shell.gate.classify`, with the target's `src/` first on the path) against about 130 crafted commands. These covered sudo option tricks, wrapper nesting, stdin into sudo, decision A, destructive rows, worst-case input size, and hidden characters in reason strings. One real bypass turned up. It is listed below.

## Findings

- NEEDS-HUMAN [impl] — **Medium** (threat-model row: "a destructive command is classed as merely mutating"; the same hole also drops the §5 sudo rejections back to a plain privileged confirm). `src/nl_shell/gate/rules.py:711-718` together with `src/nl_shell/gate/rules.py:405-416` and `:351`. With `xargs -I<str>` / `-i` / `--replace=<str>`, the engine marks the inner words that hold the replace string as non-literal but keeps their source text (`%`, `x`, `@`). `_may_be_option` then judges "could this be an option?" from that source's first character. So a placeholder like `%` is never treated as a possible option. At run time xargs puts each input line there, and the input comes from a file or a pipe the attacker controls. That line can be `--hard`, `-R`, `-S`, `-A` or `-s`. Reproduced on the patched tree (proposal origin):
  - `xargs -I% git reset %` → `mutating` "not allowlisted". An input line `--hard` runs `git reset --hard` (`destructive` when typed directly).
  - `xargs -I% chown % bob /` → `mutating`. Input `-R` runs `chown -R bob /`.
  - `xargs -I% sudo % true`, `xargs -Ix sudo x true`, `xargs --replace=@ sudo @ true`, `cat list | xargs -I% sudo -u root % true` → `privileged`, **rejected=False**. Input `-S`/`-A`/`-p` gives the sudo forms that §5 and the threat model's "What must hold" say the gate rejects. Compare `sudo "$P" true` and `xargs -i sudo {} true`, which are both rejected, because their source starts with `$` / `{`.
  - `xargs -o -I% sudo %` → `privileged`, not rejected. Input `-s` or `-i` opens an interactive root shell on the terminal, which should be rejected as a proposal ("opens an interactive root shell").

  The class shown is never below `mutating`, so a confirm still happens. That is why I rate this Medium and not Critical. Suggested fix, within child A's own scope (§4 wrappers, §5 sudo rules): give a replaced word a source that `_may_be_option` treats as unknown (as `_ARGUMENTS_FROM_INPUT` already does for the appended case, `rules.py:60`), or make `_parse` treat any non-literal word that came from a placeholder as possibly an option.

- NEEDS-HUMAN [impl] — **Medium** (test gap for the finding above). `tests/test_gate_commands.py:359-364`: the wrapper tests cover `xargs rm -rf x` and `xargs "$c"`, but nothing covers `xargs -I`/`-i`/`--replace` with a replace string that does not start with `$`, `{` or `-`. Add regressions such as: `xargs -I% sudo % true` and `xargs -o -I% sudo %` rejected as proposals; `xargs -I% git reset %` and `xargs -I% chown % bob /` at least `destructive`.

## Checked, no finding

- **§5 sudo rules through wrappers and quoting:** `sudo -S`, `-uroot -Sk`, `--stdi` (unique abbreviation), `--pr` (ambiguous, may be `--prompt`), `--preserve-env=PATH -S`, `-iS`. These are covered with `env`, `env -u`, `env --`, `env -i A=1`, `nice -5`/`-n5`, `timeout -s KILL 5`, `stdbuf`, `setsid`, `flock`, `ionice`, `nohup`, `time -p`, `watch` / `watch -x`, `command -p`, `exec`, `~/bin/sudo`, `~+/sudo`, `s''udo` and `"sudo"`. All are rejected as proposals.
- **Pipes and stdin into sudo:** `echo pw | sudo|env sudo|timeout 5 sudo|watch sudo|find -exec sudo|systemd-run -P sudo|run0`, `sudo true </dev/stdin` and `sudo true <<<pw` are all rejected. `echo pw | xargs sudo true` is not rejected, which is correct: xargs gives its inner command `/dev/null`, and `-a /dev/stdin` passes the pipe through and is rejected.
- **Root shells:** `sudo -i`/`-s`, `sudo bash -s x`, `sudo env bash`, `sudo chroot /`, `sudo -u bob python3`, `pkexec`, `run0`, `su`, `doas -s` and `systemd-run -t bash` are all rejected.
- **Decision A:** `chrt 1 sudo -S x` and `taskset 1 sudo -S x` are privileged and rejected.
- **Table location:** `commands.py:43-58,240-268` reads from `targets.TARGETS_ROOT` (fixed relative to the package, `targets.py:28`) and `targets/gate.toml`. Nothing in `gate/` reads the environment. Paths outside the root are refused.
- **Resource use:** 8 KiB of `env a=1 …`, nested `env`/`sudo`, `rm -r …`, `find … -exec …` and `xargs -I% % …` each take ≤ 0.13 s. Deep nesting ends in decision C ("nesting too deep").
- **Reason strings:** hidden and control characters in option words and non-literal words (`sudo --x‮y`, `env "$x‮"`, `"$v\x1b[2J"`) come out escaped (property 6 holds).
- **Inventory:** I re-ran `scripts/harvest_inventory.py --output <scratch>` on this host (Ubuntu 26.04.1). The output matches the checked-in `targets/ubuntu-26.04/inventory.toml` byte for byte.

## Seen but not filed (owned by later children, per brief.md "Split plan")

- `env SUDO_ASKPASS=/x sudo true` and `env SUDO_PROMPT=x sudo true` are `privileged` but not rejected. An `env` assignment to a protected variable belongs to class 5, which is child C (brief.md:485-489). It is not a regression from `main`, where everything was `mutating`.
- `env -S 'sudo -i'`, `su -c '…'`, `flock /tmp/l -c 'sudo -S x'` and `sg root -c id` stay at decision B (`destructive`, not rejected). Reading that text is child B's job (brief.md:476-484), and the patched threat model already says so.
- `script -qc 'sudo -S x' /dev/null` → `mutating`. This is the accepted class-7 gap (a command word quoted as one argument), and the threat model records it.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C5 Causal adequacy — Fix ANSI-C NUL truncation before relying on command recognition: Bash resolves the tested quoted word to sudo, but the decoder marks sudoignored nonliteral and the engine skips lookup, leaving the sudo rejection path bypassable (target/src/nl_shell/gate/parse.py:352; target/src/nl_shell/gate/rules.py:138).
- [ ] T5 Judgment — Confirm affected-path prior art across merged and closed/rejected work, and approve the new policy rows: the brief records only three paths, the sandbox has one synthetic base commit, and INTEGRATION §4 is not supplied (brief.md:401; target/docs/design/specs/policy-gate/v1.md:320).
- [ ] Validation — fitness-to-purpose — Decide whether A's conservative unreadable-code floor and documented class-7 confirmation gap fit the staged rollout before B/C land; passing classifier tests do not establish that product/security tradeoff (brief.md:466; target/tests/test_gate_commands.py:287; target/docs/design/specs/policy-gate/v1.md:320).
- [ ] **A root shell slips through when an unreadable word sits on the inner command's argv.** Proposals `sudo bash $x`, `sudo env $x bash`, `sudo nice $x bash`, `sudo xargs -o bash` and `sudo busybox --pdca` all come back `privileged` with `rejected=False`. With `x` unset, `sudo bash $x` runs as `sudo bash`, which §5 says must be rejected (`sudo bash` alone is rejected). Cause: `elevated` is computed separately for each row (`src/nl_shell/gate/rules.py:212-222`). The inner `bash` row is not elevating, so its unreadable or undeclared word only raises the class to `destructive` (`rules.py:252-265`) and never calls `reject_proposal`. The unreadable word also keeps `opens` from being set, so the root-shell check at `rules.py:656-664` never fires either. The class-2 property test (`tests/test_gate_commands.py:233-252`) only puts the undeclared option on the elevating row itself, so it cannot catch this. Fix: pass the outer row's `elevated` down through `_inner`/`_command`, so an undeclared option or unreadable word in any command run under elevation rejects the proposal. Then add `sudo bash $x` and `sudo env $x bash` as regressions.
- [ ] **`script` has no row, so `sudo script` is an unrejected root shell.** With no command, `/usr/bin/script` (present on this host) starts `$SHELL`. `sudo script`, `sudo -u root script` and `sudo busybox script` come back `privileged`, `rejected=False`, and plain `script` is `mutating`, "not allowlisted". `targets/ubuntu-26.04/commands.toml` has no `script` row (no `names` entry matches; the wrappers sit around `:427`-`:631`). The brief lists `script -c 'sudo -i'` among the §4 wrappers. Class 2 says a command that runs an inner command must declare its no-command behaviour. The split hands "stdin into `script`" to child B, which assumes child A already gave `script` a row. Fix: add a row with `no_command = "opens-shell"` and `-c` as `runs-text` (bash). Child A classes that text as decision B for now.
- [ ] **Wrappers with no row hide a root shell from decision A.** Proposals `sudo strace bash`, `sudo setarch x86_64 bash`, `sudo taskset -c 0 bash`, `sudo chrt -f 1 bash`, `sudo prlimit bash`, `sudo dbus-run-session bash`, `sudo systemd-inhibit bash`, `sudo setpriv bash` and `sudo runuser -u root bash` all give `privileged`, `rejected=False`. All of these binaries are on this host. Decision A (`rules.py:165-178`) only checks whether an argument names an `elevates` or `destroys` row. It never checks for a row that opens a shell. That matches the brief's wording of decision A, and class 1's inventory criteria do not cover plain wrappers, so this is not a slip against the letter of the brief. But it makes §5's "`sudo bash` is rejected" easy to sidestep. A human should pick one of three: (a) under an elevating row, treat an argument that names an `opens-shell` row as a root shell; (b) widen class 1's inventory to cover wrappers that run commands; (c) record it as a follow-up outside this bundle's classes.
- [ ] **Medium** (threat-model row: "a destructive command is classed as merely mutating"; the same hole also drops the §5 sudo rejections back to a plain privileged confirm). `src/nl_shell/gate/rules.py:711-718` together with `src/nl_shell/gate/rules.py:405-416` and `:351`. With `xargs -I<str>` / `-i` / `--replace=<str>`, the engine marks the inner words that hold the replace string as non-literal but keeps their source text (`%`, `x`, `@`). `_may_be_option` then judges "could this be an option?" from that source's first character. So a placeholder like `%` is never treated as a possible option. At run time xargs puts each input line there, and the input comes from a file or a pipe the attacker controls. That line can be `--hard`, `-R`, `-S`, `-A` or `-s`. Reproduced on the patched tree (proposal origin):
- [ ] **Medium** (test gap for the finding above). `tests/test_gate_commands.py:359-364`: the wrapper tests cover `xargs rm -rf x` and `xargs "$c"`, but nothing covers `xargs -I`/`-i`/`--replace` with a replace string that does not start with `$`, `{` or `-`. Add regressions such as: `xargs -I% sudo % true` and `xargs -o -I% sudo %` rejected as proposals; `xargs -I% git reset %` and `xargs -I% chown % bob /` at least `destructive`.
- [x] **The split has no per-child success criterion, red leg or scope.** brief.md:3-8 says "This brief is split into three children", but the Success criterion (`:156-308`), Falsifiability (`:309-322`) and Scope (`:342-358`) still describe the whole v3 bundle. They are one `tests/test_gate_commands.py` with groups for classes 1–7, budget, B and C. The Split plan (`:424-456`) assigns classes to A/B/C. It does not say which test functions each child adds, what each child's red-leg claim is, or which production hunks each child's C4 reverts. Child B's and C's red legs revert only their own hunks over a predecessor that already has an engine. "on the stub … comes out `mutating`" (`:313-316`) is then false for B and C: their "before" state is A's or B's engine, not the stub. Each child needs its own criterion, red-leg statement and file list. Otherwise every Check for B or C is judged against a falsifiability claim that no longer applies.
- [x] **Child A's assigned groups contain cases that only B's recursion or C's class 5/6 can turn green.** The split says "A needs no recursion" and "A classes every one of them [text effects] as decision B" (`:437-439`). A still owns these cases:
- [x] **Decision B′ has no test case.** Pass 4 adds B′ (`:52-61`): `bash -c "sudo -i $x"`, `eval "sudo -S true${x:-}"`, `trap "sudo -i $x" EXIT`, `alias ls="sudo -i $x"` and `PROMPT_COMMAND="sudo -i $x"` are rejected as proposals. Expansion in the command word or unparsable text with holes gets decision B only. None of these appear in the Success criterion. The only Decision B group case is `bash -c "$v"` → `destructive` (`:271`). Today B′ is unverifiable, and nothing would catch its absence. That is the regression B′ exists to close ("`sudo -S` … cannot hide", `:60`). Add B′ cases to child B (and C for the trap/alias/PROMPT_COMMAND forms), plus negatives (`"sud${x}o -i"` → B only, not rejected).
- [x] **The v3 findings are listed but have no expected results.** brief.md:7-8 says pass 4 "adds … the v3 review findings as regressions in the child that owns their class". Yet the findings appear only as prose in the Split plan (`:439-441`, `:445-450`, `:453-456`). None of these is in the Success criterion with a class, reason or proposal/typed origin: `$'\x73udo' -i`, `foo $'\x73udo'`, `unshare <<<'sudo -i'`, `echo 'rm -rf ~' | unshare`, `fc -e`, `[ -v 'a[$(…)]' ]`, `bash -c '"$@"' _ "$v"`, `declare -a PROMPT_COMMAND='("sudo -i")'`, `declare -n r='x[$(sudo -i)]'; r=1`, `BASH_FUNC_<name>%%`. Some are stated as decision B, but "rejected" vs "at least destructive" is not stated for most. A Check reviewer cannot falsify them.
- [x] **The tracker's work-budget criterion was quietly weakened.** The issue body (notes.json) says the nine-deep `{ bash;bash;bash;bash; } <<'E0'` case "classifies in under one second". The brief replaces that with "a loose 10 s timeout that only guards against a hang" (`:277-279`). It does not say this departs from the tracker or why. The human should accept the relaxation explicitly, or the brief should keep a tighter bound.
- [x] **Spec and threat-model text is shared across a three-child chain with no split.** Scope (`:152-155`, `:357`) has one bundle write "the command table, decisions A–C, the seven class rules and the class-7 accepted gap". It also writes B′ "as part of §4.1" (`:60-61`). All three children edit the same spec and threat-model paragraph (`:427-429`), but the brief does not say which child writes which section. If A lands the full §4.1, the spec claims B/B′ protections (and the threat-model "cannot hide" claim) before they exist on `main`. Say which spec sections each child writes, and that A's text must not claim recursion or B′.
- [x] **The scope is far beyond the tracker issue, and the second change is not called out.** The issue body's scope lists `rules.py`, a loader, `commands.toml`, vector rows, spec/threat-model text and the test. It names no `parse.py` change, no inventory harvesting and no classes 3–6. The brief adds:
- [x] **One citation has drifted (minor, but "cite path:line for every change" is required).** brief.md:349-350 cites `Invocation` "already carries `assignments` (`parse.py:805`)". On the target, the field is at `src/nl_shell/gate/parse.py:171`. `_declared` is at `:816`, not `:813`. Fix these so Do's citations are not copied from a wrong anchor.
- [ ] size backstop — this slice is behaving oversized: patch is 169 KB (threshold 100 KB). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.

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
- Iteration delta (if iterating): The split agreed at v3 was never filed: v4 built child A (engine + table) inside the #197 parent bundle, still 173 KB against the 100 KB backstop. In Plan, run `nl-shell-pdca split 197` then `--accept` so child A/B/C become their own issues and bundles; do not rebuild #197 as a whole. Carry into child A's brief as regressions (all in-class bypasses found in v4): - ANSI-C NUL truncation: `$'sudo\0ignored' -i` must be rejected, and `$'rm\0ignored' -rf build` must be destructive (bash cuts at the NUL; the decoder marks the word nonliteral and skips lookup). Also `foo $'sudo\0ignored'` (decision A). - Elevation must reach inner commands: `sudo bash $x`, `sudo env $x bash`, `sudo nice $x bash`, `sudo xargs -o bash`, `sudo busybox --pdca` rejected as proposals (an unreadable word or undeclared option under an elevating row rejects). - `script` needs a row (no command opens $SHELL; `-c` is runs-text bash): `sudo script` rejected. - xargs replace strings (`-I%`, `-i`, `--replace=@`) may become options at run time: `xargs -I% sudo % true`, `xargs -o -I% sudo %` rejected; `xargs -I% git reset %`, `xargs -I% chown % bob /` at least destructive. Add these tests. Still open for the human at the re-plan: wrappers with no row hiding a root shell (`sudo strace bash`, `sudo setpriv bash`, `sudo runuser -u root bash`, ...) — pick (a) treat an opens-shell argument under elevation as a root shell, (b) widen the inventory to wrappers, or (c) follow-up issue.
- By / date: Eduard Ralph / 2026-10-26

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 8 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

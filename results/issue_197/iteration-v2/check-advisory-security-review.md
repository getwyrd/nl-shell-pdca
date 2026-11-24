# Advisory security review: issue #197 (policy-gate command engine)

**Attacker-reachable input this diff touches:** the command string the gate classes, in particular a model proposal (threat model item 5, `.oss-scanner/threat_model.md:77-79`). This includes text that a proposal hands to `bash -c`, `env -S`, `eval`, `find -exec` and `xargs`, plus the argument words of opaque commands. The table file `commands.toml` is not attacker input: it is read only from `TARGETS_ROOT`, and anyone who can write it can also write the gate's code (`:54`).

I ran each case below through `nl_shell.gate.classify(cmd, origin="proposal")` against the patched source at `$PDCA_TARGET/src`. This host's `python3` has no `tree_sitter`, so I borrowed only the interpreter from `/home/eddie/nl-shell/nl-shell-pdca/.venv`. All code came from `$PDCA_TARGET`.

## Findings

- NEEDS-HUMAN [impl] — **High** (privileged step classed lower; proposal opening a root shell not rejected), `targets/ubuntu-26.04/commands.toml:537-540` and `src/nl_shell/gate/rules.py:623-627`. The words after a `-c` text become the script's `$0`, `$1`, … and are never classed. The bash/sh/dash row's `runs-text` uses `operand = 0`, so `_text_words` returns only the text word. The words after it don't go through recursion, and they don't go through decision A either, because `bash` has a row. The text then has a non-literal command word, which is only `mutating`. Who controls it: the model's proposal. Reproducers (all proposals):
  - `sh -c '$0 -i' sudo` gives `mutating`, not rejected. It runs `sudo -i`.
  - `bash -c '"$0" -S true' sudo` gives `mutating`, not rejected.
  - `sh -c '"$@"' _ rm -rf ~` gives `mutating`. It runs `rm -rf ~`.
  - `bash -s _ sudo -i <<<'"$@"'` and `bash /dev/stdin sudo -i <<<'"$@"'` give `mutating`.

  Fix: run decision A over the operands after the text, as `rules.py:567` already does for a non-literal inner command, or raise when the text uses `$0`/`$@`/`$N` and words follow. Add these cases to `tests/test_gate_commands.py`.

- NEEDS-HUMAN [impl] — **High** (same class of break), `src/nl_shell/gate/rules.py:78` and `:653-660`. Decision A over `env -S` text misses a name that comes right after `\_`. `_PIECE_SPLIT` keeps `_` as a word character, so `\_sudo` becomes the piece `_sudo`, which names no row. env reads `\_` as a space, so the command runs `sudo -i`. Reproducers (proposals):
  - `env -S '\_sudo -i'`, `env -S '\_sudo\_-i'` and `env -S '-i\_sudo\_-i'` all give `destructive`, `rejected=False`. Each should be `privileged` and rejected.
  - `env -S 'sudo\_-i'` is rejected, but only because the name comes first.

  The tests at `tests/test_gate_commands.py:401-403` only cover the friendly spot, with the name before the escape. Fix: turn env escapes into spaces (or split on them) before running decision A. Add leading-`\_` and option-first cases.

- NEEDS-HUMAN [impl] — **High**, `targets/ubuntu-26.04/commands.toml`, which has no `sg` or `newgrp` row. `sg GROUP -c 'TEXT'` and `sg GROUP 'TEXT'` run the text through `/bin/sh -c`. With no row, decision A only checks whole words, and `'sudo -i'` is one word. Reproducer: proposal `sg adm -c 'sudo -i'` gives `mutating`, not rejected. Run with the user's own primary group, it needs no group password and opens a root shell. I believe `sg` ships in Ubuntu's `login` package, but I have not checked this on the reference VM. The fix is a row with `runs-text`. In the same group: `at now <<<'sudo rm -rf /'` and `echo 'sudo rm -rf /' | at now` give `mutating`. `at` runs its stdin as code, so it needs a `runs-stdin-as-code` row, if `at` is installed on the target.

- NEEDS-HUMAN [human] — **High if counted as lowering a class; within the letter of agreed decision A**, `src/nl_shell/gate/rules.py:225-249`. Decision A matches only a whole argument word, after quote removal, against a row name. An opaque command that takes command text as one quoted word is therefore only `mutating`, not rejected:
  - `foo 'sudo -i'`
  - `x-terminal-emulator -e 'sudo -i'`
  - `tmux new 'sudo -i'`
  - `zsh -c 'sudo -i'`
  - `gdb -ex 'shell sudo -i'`
  - `"$SHELL" -c 'sudo -i'`

  The patch already splits text into pieces for `env -S` (`:653-660`). Doing the same for every opaque argument would close this, but it would reject far more harmless proposals (`foo 'remove sudo'`). The brief already flags decision A's false-positive cost for the human. This is the same trade-off and widens it.

## Checked, no finding

- **sudo-family forms:** short, clustered, attached, long and abbreviated options (`--st`, `--prompt=x`). Paths: `//usr/bin`, `/usr/local/bin`, `..`. Quoting: `\sudo`, `s\udo`, `'sudo'`. All of `sudo-rs`, `sudo.ws`, `su`, `pkexec`, `doas`, `run0`, `machinectl shell` and `systemd-run --shell` are `privileged`, with root-shell and `-S`/`-p`/`-A` rejection.
- **Wrapper rows:** `env` (`-u`, `-C`, `--chdir=`, `-i`, `-vS`, `-S"…"`, `--split-string=`), `nice`, `nohup`, `time -p`, `timeout -k/--signal=`, `stdbuf`, `setsid -w`, `flock -c` in either order, `script -qc`, `watch`, `ionice`, `taskset`, `chrt`, `chroot`, `command`/`builtin`/`exec`, `find -exec/-ok`, `xargs -0/-a/-I`. All carry the inner class.
- **Decision A** catches unquoted `sudo` and `rm` after an opaque command: `strace`, `setarch`, `fakeroot`, `prlimit`, `ssh host sudo -i`.
- **sets-variable** for `SUDO_PROMPT`/`SUDO_ASKPASS`: `export`, `declare -x/-gx/-n`, `local -n`, `typeset -n`, `readonly`, `read -r/-a/-p/-d/-u/-t`, `printf -v` (attached, quoted, subscript), `mapfile`/`readarray`, `getopts --`, `let` (quoted, comma list), `wait -p/-fp/-n -p`, `env NAME=`, `sudo NAME=`, `builtin`/`command`/`eval export`. Every one is rejected. `select X in` and `(( X=1 ))` are walker cases already left to #196.
- **Work budget:** `bash -c` nested so the work doubles at each level reaches decision C ("work budget exceeded") at level 5 (6.7 KB) in 0.01 s. A 1500× `eval` chain, 2000× `env`, 1300× `xargs` and 1600 `true;` inside `bash -c` all end in decision C in under 0.03 s. A 3000× `\_` `env -S` string takes 0.02 s. I found no hang and no work out of proportion to the input.
- **Loader** (`src/nl_shell/gate/commands.py:231-266`): takes no path from the caller, the environment or the cwd. It resolves the path, refuses one outside `TARGETS_ROOT`, and turns a decode or validation error into `CommandsError`, which is decision C.
- **Cosmetic, not a security finding:** `sudo -e /etc/shadow` and `sudoedit /etc/shadow` show the reason "command word is a path outside the system directories: /etc/shadow". The sudo row treats the edited file as an inner command. The class is still `privileged`.

<!-- pdca:leaf-complete -->

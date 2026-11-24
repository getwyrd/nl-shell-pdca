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

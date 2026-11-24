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

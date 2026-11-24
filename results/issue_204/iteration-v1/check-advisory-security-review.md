# Security review — gate-command-table-engine (#204)

**Attacker-reachable inputs this diff touches:** the model's proposal text (threat model "Where untrusted input enters" item 5), which now flows through the new command-layer engine (`src/nl_shell/gate/rules.py`), the new ANSI-C `$'…'` decoder (`rules.readable`) and the table in `targets/ubuntu-26.04/commands.toml`. Indirectly, file contents and command output (item 1/2) reach the engine only as xargs/find input, which the gate never sees. The table itself is read from a fixed path inside the package (`commands.py:65`, `targets.py:28`). No environment variable, cwd or `HOME` is used, so the table is not attacker input.

I tested the patched tree at `$PDCA_TARGET` with the harness venv, calling `nl_shell.gate.classify(cmd, origin=…)` directly. I compared the decoder against real bash 5.3.9 on this host.

## Findings

- NEEDS-HUMAN [impl] — **High** (a privileged step is classed lower; the §5 pipe-into-sudo rule is bypassed). `src/nl_shell/gate/rules.py:188-199` (`_ansi_c`, the `\x`/`\u`/`\U` branch). **Input:** the model's proposal. **What goes wrong:** bash 5.3 accepts the brace form `\x{HH…}` inside `$'…'` (`bash -c "printf %s \$'\x{73}udo'"` prints `sudo`). The decoder sees `{`, finds no hex digits and returns `None`. A word the gate cannot read is then dropped from row lookup (`rules.py:278-288`, depth 0 gives only `mutating`) and from decision A (`rules.py:313-315`, `continue`). The patch claims that `$'…'` is "decoded as bash does" (threat model and `rules.py:25`), and this escape breaks that claim. Measured results:
  - `$'\x{73}udo' -i` as a proposal: `mutating`, **not rejected** (`$'\x73udo' -i` is rejected).
  - `echo pw | $'\x{73}udo' -S true` as a proposal: `mutating`, **not rejected**.
  - `foo $'\x{73}udo'`: `mutating` (should be `privileged`).
  - `$'\x{72}m' -rf build`: `mutating` (should be `destructive`).

  **Fix:** decode `\x{…}` the way bash does. Also fail closed: when a `$'…'` word cannot be decoded, a proposal should be rejected, or the word should at least count as possibly elevating. Today it silently falls back to the opaque `mutating` path. **Add tests:** the four cases above in `tests/test_gate_commands.py`'s decision A group.

- NEEDS-HUMAN [impl] — **High** (a privileged proposal is classed `destructive`, so clean-room re-derivation is skipped). `src/nl_shell/gate/rules.py:446-450` (`_inner`, xargs replace strings). **Input:** the model's proposal, plus the xargs input, which can be file or command output. **What goes wrong:** any inner word that *contains* the replace string is swapped for an opaque "input" word before the inner command is classed. That throws away a literal `sudo` that is plainly in the proposal. Measured results:
  - `printf 's\n' | xargs -Is sudo -i` as a proposal: `destructive`, "inner command the gate cannot read", **not rejected**. With that input, xargs runs `sudo -i` (a root shell).
  - `xargs -Isudo sudo -i`: same result.
  - The brief's own case `xargs -I% sudo % true` is rejected, but only because `%` does not occur inside `sudo`.

  **Fix:** before the swap, run the elevation and decision-A checks on the original words, so a word that names an elevating or shell row still raises and rejects. **Add tests:** `xargs -Is sudo -i` and `xargs -Isudo sudo -i` as proposals, both rejected.

- NEEDS-HUMAN [impl] — **Low** (typed input only; the user is trusted, but a spec §5 MUST is missed). `targets/ubuntu-26.04/commands.toml:21-33` and `src/nl_shell/gate/rules.py:396-399`. **Input:** a typed command, or a command the user copies from a README (text-only attacker). **What goes wrong:** the row says `sudo.ws` "takes the same options" as sudo-rs. But the original sudo parses with `getopt_long`, which accepts any unambiguous prefix of a long option. So `sudo.ws --stdi true`, `sudo.ws --askp true` and `sudo.ws --prom=x true` mean `-S`/`-A`/`-p`. Typed, these come out `privileged` and **not rejected**. Typed `sudo -S true` is rejected (row 21). Proposals with the same words are rejected (unknown option under elevation), and a pipe into them is rejected by the stdin rule. So the gap is typed input with terminal stdin. If sudo passthrough (#13) keys on the session's own `SUDO_PROMPT`, `--prom=` could keep passthrough from starting. That part is unconfirmed, because passthrough is not built. **Fix:** on a row that has rejecting options, treat any unknown `--` option as rejected too, or list the getopt prefixes for the sudo.ws name. **Add test:** typed `sudo.ws --stdi true` rejected.

## Checked, no finding

- **sudo family and §5.** `sudo -S/-A/-p`, bundled (`-iS`, `-nS`, `-px`) and quoted or ANSI-C spellings (`"-"S`, `-'S'`, `$'\x2dS'`) are all rejected. So are `--stdin`, `--askpass` and `--prompt=`, `SUDO_ASKPASS=… sudo -A`, `sudo env SUDO_ASKPASS=… sudo -A`, and pipes into `sudo.ws`. `sudo -E/-R/--/-u … bash`, `su -c`, `su -`, `su -s`, `pkexec --user`, `doas -s`, `run0` and `systemd-run -t/--pty bash` are all `privileged`, and rejected where the brief says.
- **Wrappers.** I tried `env -u/-C/--chdir=/-iC//--block-signal`, unknown wrapper options (`env --ch / sudo -i` is caught by decision A), `nice -5`, `nice --adjustment=`, `timeout --foreground`, `strace`, `setsid`, `stdbuf`, `nohup`, `time -p`, `command`, `builtin`, `exec`, `watch`, `xargs`, `busybox`, a second `-exec` in `find`, and unknown wrappers (`ionice`, `chrt`, `taskset`). Every `sudo -i` underneath is `privileged`, and rejected as a proposal.
- **Destructive rows.** All of the brief's §4 list, plus `rm` via `\rm`, `/bin/rm`, `./rm`, `command rm` and `--recursive`. `unlink`, `mv … /dev/null`, `pkill`, `killall`, `rsync --delete` and `git branch -D` stay `mutating`. That is not a lowering: the stub gave the same, and the brief does not list them.
- **Text effects.** `env -S 'sudo -i'` and `bash -c 'sudo -i'` are `destructive`, not rejected. This is decision B as the brief and the updated threat model state it (the text is not read until child-2). It is pre-existing (the stub gave `mutating`), not made worse, so I did not raise it.
- **ANSI-C decoder against bash.** It matches on `\NNN`, `\0163`, `\uHHHH`, `\UHHHHHHHH`, `\x7`, NUL cut-off, `\400`, unknown escapes and mixed quoting. Besides `\x{…}` (above), `\c?` decodes to 0x1f where bash gives 0x7f. That is harmless: no `\c` form yields a letter. The other mismatches (`$'\''`, `$'\xs'`) fail toward unreadable.
- **Loader.** It uses a fixed `TARGETS_ROOT / "ubuntu-26.04" / "commands.toml"` (`commands.py:65-69`) and checks `resolve()` against the root (`commands.py:306-310`). Any load error becomes decision C (`rules.py:67-70`).
- **Resource use.** 8 KB inputs (4000 plain words, 1000 nested `env`, 400 nested `find -exec env`, 700 ANSI-C words) each class in ≤ 0.06 s. Nesting over 32 is decision C.
- **`scripts/harvest_inventory.py`.** It passes list-form `subprocess` arguments with no shell, and it runs only by hand on the reference host. I did not re-run it for inventory drift: it writes into the target tree, which is read-only for me. That drift check is the human/reviewer step the brief names.

<!-- pdca:leaf-complete -->

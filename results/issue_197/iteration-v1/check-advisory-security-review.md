# Security review — issue #197 (policy gate command engine)

**Attacker-reachable inputs this diff touches:** the model's proposal (threat model input 5) and typed commands built from untrusted text (inputs 1–2). Both reach the new engine in `src/nl_shell/gate/rules.py` and the data in `targets/ubuntu-26.04/commands.toml`. The `commands.toml` loader takes no attacker input: its path is fixed, with no environment, cwd or config lookup (`src/nl_shell/gate/commands.py:218-253`).

I checked each finding below by running the patched gate (`nl_shell.gate.classify`, both origins) from the `nl-shell-pdca` venv, which has tree-sitter-bash. Severities use the scale in `.oss-scanner/threat_model.md:329-362`.

## Findings

- NEEDS-HUMAN [impl] — **High** ("a privileged step is classed lower"). `targets/ubuntu-26.04/commands.toml:75-76`: the sudo-family rows leave out the names the target actually ships. The target's sudo is sudo-rs (`targets/ubuntu-26.04/target.toml:32`), and the project's own list of privilege programs includes `sudo-rs`, `sudo.ws` and `sudoedit-rs` (`src/nl_shell/failure_classes.py:98`). None of them has a row, so each is an opaque command, and decision A does not catch it either, because it only looks up names that *have* rows. Who controls it: the model, through a proposal. Results seen:
  - `sudo-rs -i` as a proposal gives `mutating`, "not allowlisted", not rejected. `sudo -i` gives `privileged`, rejected.
  - `echo pw | sudo-rs -S true` gives `mutating`, not rejected. This skips both §5 sudo rules (the pipe rule and the `-S` rule).
  - `sudo.ws -i` and `sudoedit-rs /etc/shadow` both give `mutating`.

  Fix: add these names to the sudo/sudoedit row (and any other alias names the target installs). Add test cases `sudo-rs -i`, `sudo.ws -i` and `echo pw | sudo-rs -S true` to `tests/test_gate_commands.py`.

- NEEDS-HUMAN [impl] — **High** (breaks the "What must hold" rule at `.oss-scanner/threat_model.md:121-124`: the gate rejects overrides of `SUDO_PROMPT` "also through … `getopts`"). `targets/ubuntu-26.04/commands.toml:697-704`: the `getopts` row is `raw = true` and takes the variable from `operand = 1`, so `--` counts as an operand. `getopts -- x SUDO_PROMPT` as a proposal gives `mutating`, not rejected; `getopts x SUDO_PROMPT` is rejected. Bash 5.3.9 accepts the `--` and does assign the variable: `bash -c 'set -- -x; getopts -- x SUDO_PROMPT; echo "$SUDO_PROMPT"'` prints `x`. Changing `SUDO_PROMPT` is the step that would stop password passthrough from starting. Fix: drop `raw` so `--` is handled (`end_of_options` is on by default), or treat any `--` before the name operand as "argv cannot be read". Add the `--` case to the test. Other `raw` rows (`source`/`.`, `alias`/`unset`/…, `let`) are fine: there a stray `--` only makes the result stricter.

- NEEDS-HUMAN [impl] — **High by the scale, though it meets the letter of spec §4.** `src/nl_shell/gate/rules.py:554-557`: when a row's inner command word is not a literal (`find -exec {}`, `xargs -I% %`), the engine raises to `destructive` but never runs decision A over the row's literal arguments. `_decision_a` is called only on the "unparsed" paths (`rules.py:529`, `:536`). Result: `find /usr/bin -name sudo -exec {} -i \;` (which really runs `/usr/bin/sudo -i`) gives `destructive`, not rejected, while the same words under an opaque command, `foo /usr/bin -name sudo -exec {} -i \;`, give `privileged`, rejected. A command with a row is treated more loosely than one with no row. Fix: when `unreadable_inner` fires, also call `_decision_a(state, acc, args)`. This only raises classes, so it stays compatible within v1. Add the test case above.

- NEEDS-HUMAN [impl] — **Below High: the class is right (`privileged`, always confirmed), but a §5 rejection is missed.** `targets/ubuntu-26.04/commands.toml:540-542`: the bash row's `opens-shell` fires only with no operands and no `-c`. Bash also runs interactively with `-s` plus operands when stdin is a terminal, and `bash /dev/stdin` reads the terminal too (`rules.py:645-646` returns without marking a shell). So these root shells, reached through a proposal, are not rejected:
  - `sudo bash -s x`
  - `sudo dash -s x`
  - `sudo env bash -s x`
  - `pkexec bash -s x`
  - `sudo bash /dev/stdin`

  Each gives `privileged` with no "proposal opens an interactive root shell" reason, while `sudo bash` is rejected. This breaks spec `docs/design/specs/policy-gate/v1.md:195`. Fix: add an `opens-shell` effect `when = { option = ["-s"] }`, and mark `opens_shell` in `_from_stdin` when stdin is `terminal`. Add these cases to the test.

- Unconfirmed note (no tag; I could not check polkit behaviour here). `targets/ubuntu-26.04/commands.toml:239-241`: `systemd-run` drops `elevates` whenever `--user` is given. But `systemd-run --user -M root@.host bash` connects to root's user manager (systemd docs, `--machine=USER@.host`). The proposal gives `mutating`, not rejected. Consider raising to `elevates` when `-M`/`--machine` or `-H`/`--host` is present. Confirm in the reference VM before acting.

## Checked, no finding

- **Loader** (`commands.py:218-253`): reads only from `TARGETS_ROOT/<id>/commands.toml`, rejects ids that are not plain, rejects a resolved path outside the root, and reads no `os.environ`, cwd or home. A missing or invalid table becomes a `GateFailure`, then decision C (`rules.py:155-161`).
- **Reason strings**: they quote raw input (`head.source`, `word.source`), but `gate/__init__.py:117` escapes every reason. A probe with ESC/OSC-52 bytes in a word came back escaped, so property (6) holds.
- **Rows that worked as intended**:
  - abbreviated sudo long options: `--s` expands to every flag it could stand for; `--p` is ambiguous and gets rejected;
  - sudo option clusters (`-iu root`);
  - `env`/`exec`/`nice`/`timeout`/`stdbuf`/`setsid`/`flock`/`script` around `sudo -i`;
  - `eval SUDO_PROMPT=x` (rejected through recursion);
  - `let -- SUDO_ASKPASS=1` (rejected).
- **Over-raising**, such as `find (-delete)` reported for a word that is not a literal, is fail-closed and not a security issue.
- **Gaps that were already there**: `git push --delete` / `git push origin :main`, `kill -9 0` and `pkill` stay `mutating`. They are outside this brief's list and the stub gave the same answer, so I'm not filing them against this diff.

<!-- pdca:leaf-complete -->

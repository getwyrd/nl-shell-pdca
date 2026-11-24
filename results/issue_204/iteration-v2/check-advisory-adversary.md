# Adversarial review: gate-command-table-engine (issue_204)

Target: `$PDCA_TARGET` = `/tmp/pdca-advisory-80ry68vz/target` (patched worktree). I ran probes through the public `nl_shell.gate.classify(cmd, origin=...)` with the project venv (bash 5.3.9 on this host).

**The red→green evidence holds.** `gate-logs/C4-verify.log` shows 164 of 401 tests failing with `src/`, `targets/` and `scripts/` reverted, and all green with the fix. The tests call the public `classify` (`tests/test_gate_commands.py:39-49`), not a copy of the engine. T3 is green (1546 passed). I found one real bypass, one weak test and two scope questions:

- NEEDS-HUMAN [impl] — **Locale-quoted words (`$"…"`) get past decisions A and §5.** In bash 5.3.9, `printf '[%s]' $"sudo"` prints `[sudo]`, because with no message catalogue `$"…"` is just `"…"`. The gate gets these wrong:
  - `$"sudo" -i` as a proposal comes out `mutating`, "not allowlisted", **not rejected**.
  - `$"rm" -rf build` comes out `mutating` instead of `destructive`.
  - `foo $"sudo"` comes out `mutating` instead of `privileged`.

  Cause: `readable()` sends `$` followed by `"` to the `_UNQUOTED_SPECIAL` branch and returns None (`src/nl_shell/gate/rules.py:160-161`). `undecodable()` only fails closed when the word contains `$'` (`rules.py:236`). So the word counts as an ordinary non-literal word and is never looked up. `$(echo sudo) -i` is caught, through decision A on the substitution, so `$"…"` is the odd one out. Fix: decode `$"…"` like `"…"` for row lookup, or treat it like undecodable ANSI-C (`privileged`, proposal rejected). Then add `$"sudo" -i`, `$"rm" -rf build` and `foo $"sudo"` to `test_decision_a`. This is a decision-A / §5 bypass, which the brief's review contract counts as a defect here.

- NEEDS-HUMAN [impl] — **The no-command test passes for the wrong reason.** `test_class2_no_command_opens_a_shell_under_sudo` (`tests/test_gate_commands.py:290-294`) asserts only `rejected=True` and no reason. The same goes for the `sudo chroot /` and `sudo unshare` regressions (`:306-307`, reason `"shell"`). `commands.py:457-459` folds `no_command == "opens-shell"` into `runs_code`. As a result, `_elevation` rejects `sudo chroot …` just because the word `chroot` appears (`rules.py:391-393`, reason "proposal runs a shell or interpreter under sudo: chroot"), before the no-command path at `rules.py:468-469` matters. Proof: `sudo chroot / ls`, `sudo unshare ls` and `sudo screen ls` are all rejected the same way. If `_opens_shell(... "with no command")` broke, these tests would stay green. Fix: assert the `"with no command"` reason in the test (for example, `sudo chroot /` should carry "opens an interactive shell: chroot with no command").

- NEEDS-HUMAN [human] — **The elevation rule rejects common harmless proposals.** `_elevation` looks up *every* later argument word, operands included (`rules.py:386-393`). `_elevated_opaque` rejects any dash word under a command with no row (`rules.py:367-376`). Proposals that come out rejected (not just confirm-gated):
  - `sudo systemctl restart ssh`: the operand `ssh` is a code-running row.
  - `sudo apt install python3`: the package name `python3` is a code-running row.
  - `sudo chown -R bob .`: the operand `.` matches the `.` builtin row, which sudo cannot even exec.
  - `sudo apt install -y python3` and `sudo dpkg -i x.deb`: `-y` and `-i` are treated as unknown options under elevation.

  The brief asks for this behaviour almost word for word ("any later argument word names a row … whatever command sits between"). Still, until #198's allowlist lands, a large share of ordinary `sudo` proposals can't be run. Matching bash-only builtin rows (`.`, `source`, `eval`) against arguments of an exec-style wrapper looks wider than intended. A human should confirm this over-raise is accepted, the same way decision A's `man sudo` over-raise was accepted explicitly.

- NEEDS-HUMAN [human] — **The class-7 gap is wider than the brief listed.** The brief names the accepted code-running gap as `git -c` / `--config-env` / `--exec-path`, `tar --to-command` and `ssh -o`. The patch adds "an `awk` program given as its operand" (`docs/design/specs/policy-gate/v1.md:208-212`), so `awk 'BEGIN{system("rm -rf ~")}'` stays `mutating`, "not allowlisted", typed or proposed. This matches the original spec's Conformance row 10 (`awk … | mutating`, `v1.md:358`). The brief's mapping "floor rows 8/10/11 = git/tar/ssh" was itself inconsistent with the spec. A human should confirm that the awk program operand belongs in the reviewed gap.

- Minor decoder nit, no security impact: `$'\c?'` decodes to `\x1f`, while bash 5.3.9 gives `\x7f` (DEL) (`rules.py:218-220`). Neither can spell a command name. I compared 6,000 other random ANSI-C bodies (`\x`, `\x{…}`, `\u`, `\U`, octal including `\400`/`\777`, `\0` cut-off, `\c`, unknown escapes) against `bash -c 'printf %s …'`: zero mismatches. The NUL cut-off (`$'sudo\0x'y` gives `sudoy`) also matches bash.

- Not a refutation, noted for the record: `env -S 'sudo -i'`, `watch 'sudo -i'`, `script -c 'sudo -i'` and `su -c …` as proposals are `destructive` ("runs code the gate cannot read") but not rejected, unless an elevating row is outside them. That is decision B as the brief scoped it for this child (`v1.md:213-214`). Child-2's text reading has to close it.

Things I tried that held: wrappers around `sudo -i` (`env -u/-C/-i/--unset=`, `nice -5`, `nice -n -5`, `timeout -k 1 5`, `timeout --foreground`, `strace -f`, `find -exec/-execdir/-ok`, `xargs`, `watch`, `busybox`, `command`/`builtin`/`exec`); `chrt`/`ionice`/`taskset` (no row, so decision A); every §5 sudo spelling (`--stdin`, the `--std` prefix, `-kS`, `-AS`, `-px`, `--prompt=`, `$"-S"`, `"$P"`); pipes or here-strings into `sudo` through wrappers; `s$'u'do -i`; `$'s'"u"do -i`; path forms of `sudo`/`bash`. All came out `privileged` and rejected as proposals, or failed closed.

<!-- pdca:leaf-complete -->

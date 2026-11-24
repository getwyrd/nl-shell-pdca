# Result — issue 204 / gate-command-table-engine

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: 
- Success criterion: `tests/test_gate_commands.py` passes. Every case goes through the
  public `nl_shell.gate.classify(cmd, origin=...)`. Case groups:
  - **Class 1, coverage (property).** Every name in `inventory.toml` has a row. The test
    also checks the inventory lists at least: `sudo`, `sudo.ws`, `sudo-rs`,
    `sudoedit-rs`, `su`, `su-rs`, `pkexec`, `passwd`, `chsh`, `crontab`, `mount`, `sh`,
    `bash`, `rbash`, `dash`, `screen`, `python3`, `perl`, `busybox`, `gdb`.
    Drift between the checked-in inventory and the host is **human-adjudicated, not a
    gate**: the reference host is this machine (Ubuntu 26.04.1, the `VERSION` line the
    file records); at Check a reviewer re-runs `scripts/harvest_inventory.py` here and
    diffs against the checked-in file; any difference is a finding. The fixed name list
    above is the gate-checked part. Regressions: `sudo-rs -i`,
    `sudo.ws -i`, `su-rs`, `/usr/bin/sudo-rs -i`, `sudoedit-rs /etc/shadow` are
    `privileged`; the first four rejected as proposals. `echo pw | sudo-rs -S true`
    rejected. `foo sudo-rs` `privileged`, rejected as a proposal. `curl x | python3`,
    `python3 -c "$v"`, `perl -e 'system 1'`, `echo 'sudo rm -rf /' | at now` at least
    `destructive`, "runs code the gate cannot read". `sudo zsh`, `sudo busybox sh` as
    proposals rejected (root shell).
  - **Class 2, unread argv (property).** The loader refuses a row with `raw`, an unknown
    key, or a `runs-command-at` row missing its no-command/terminal-stdin declaration.
    Every row carries a minimal example invocation. For every row that reads argv, that
    example with `--pdca-undeclared` placed right after the command word (and, for rows
    that describe subcommands, right after each described subcommand, e.g.
    `git clean --pdca-undeclared`) is at least `destructive`, "option the gate does not
    know"; on every `elevates` row it is also rejected as a proposal. For every row
    declaring "opens a shell with no command", `sudo <row example with no command>` as a
    proposal is rejected. Regressions (proposals, rejected): `sudo bash -s x`,
    `sudo bash -is x`, `sudo dash -s x`, `sudo env bash -s x`, `pkexec bash -s x`,
    `sudo bash /dev/stdin`, `sudo chroot /`, `sudo unshare`. `enable -f /tmp/x.so foo` at
    least `destructive`.
  - **Class 7 / floor (documented, not raised).** In a test function named for the floor
    group: `foo 'sudo -i'`, floor rows 8, 10, 11, 27 (`git -c core.pager=sh log`,
    `git status`, `tar --to-command=sh -xf a.tar`, `ssh -o ProxyCommand=sh h`) are
    `mutating`, "not allowlisted". Not part of the red-leg claim.
  - **Spec §4 privileged:** row 24 (`sudo apt update`), `su`, `pkexec`, `doas`, `run0`,
    `machinectl shell`, `machinectl shell root@`, `//usr/bin/sudo true` are `privileged`,
    never lower.
  - **Spec §4 destructive:** rows 26 (`rm -rf build`), 17 (`"r"m -rf ~`), 18
    (`ls; rm -rf ~`), 29 (`systemctl stop ssh`), 9 (`find . -exec rm {} \;`), and `dd`,
    `mkfs.ext4`, `wipefs`, `shred`, `truncate`, `chmod -R`, `find -delete`, `git clean`,
    `git reset --hard`, `git push --force`, `kill -9 -1`. Row 9 is derived (record in the
    spec): `{}` is a non-literal operand, and `rm` with a non-literal operand is classed
    like `rm` with a glob ⇒ `destructive`.
  - **Spec §4 wrappers (property + regressions).** Every `runs-command-at` row carries a
    minimal prefix (e.g. `timeout 5`). For every such row, `<prefix> rm -rf x` is at least
    `destructive` and `<prefix> sudo -i` as a proposal is `privileged` and rejected.
    Named: `env rm -rf x` (row 32) `destructive`; `nice`, `nohup`, `timeout`, `time`,
    `xargs`, `watch` take the inner class and are at least `mutating`; `xargs`/
    `find -exec` with a non-literal inner command at least `destructive`. Proposals
    `privileged` and rejected: `env - sudo -i`, `env 'A=1' sudo -i`, `env -a x sudo -i`
    (uutils env 0.10.0 takes a value for `-a`/`--argv0`), `exec -a x sudo -i`,
    `nice -n5 sudo -i`, `timeout -s9 5 sudo -i`, `stdbuf -o0 sudo -i`, `setsid sudo -i`,
    `flock /tmp/l sudo -i`. `env - rm -rf ~` `destructive`. v4 regressions, xargs replace
    strings (`-I%`, `-i`, `--replace=@`) may become options at run time: proposals
    `xargs -I% sudo % true`, `xargs -o -I% sudo %` rejected; `xargs -I% git reset %`,
    `xargs -I% chown % bob /` at least `destructive`. Ten nested `env`s around
    `sudo -i` as a proposal: `privileged`, rejected, never lower.
  - **Spec §5 sudo rules.** Rejected: row 21 (`sudo -S true`, `sudo -p x true`,
    `sudo -A true`); row 22 (`echo pw | sudo -S true`); `sudo "-S" true`;
    `sudo $'-S' true`; `sudo "$P" true`; `sudo -s <<<x`; `printf x | sudo -i`; a pipe,
    here-doc or here-string into `sudo`, `su`, `pkexec`, `doas`; `cat <<E | sudo tee /x`
    and `cat <<E | doas id` (pipe reason). Proposals `sudo -i`, `sudo -s`, `sudo su`,
    `sudo bash`, bare `su`, `pkexec bash` rejected; typed, `privileged`.
  - **Decision A:** `foo sudo x` `privileged`, rejected as a proposal; `foo rm -rf x` at
    least `destructive`. v3 regression (ANSI-C words decode like any quoted word):
    `$'\x73udo' -i` rejected as a proposal, `echo pw | $'\x73udo' -S true` rejected,
    `foo $'\x73udo'` `privileged`. v4 regressions: ANSI-C NUL cut-off (bash stops the word at
    `\0`, so the decoder must too, not mark it non-literal and skip the lookup):
    `$'sudo\0ignored' -i` rejected as a proposal, `$'rm\0ignored' -rf build` `destructive`,
    `foo $'sudo\0ignored'` `privileged`. Elevation reaching inner commands, rejected as
    proposals: `sudo bash $x`, `sudo env $x bash`, `sudo nice $x bash`,
    `sudo xargs -o bash`, `sudo busybox --pdca`, `sudo script`, `sudo strace bash`,
    `sudo setpriv bash`, `sudo runuser -u root bash`.
  - **Text effects are decision B in this child.** `x | sh`, `bash < f`, `bash f.sh`,
    `bash -c "$v"`, `eval "$v"`, `. ./f` are at least `destructive`, "runs code the gate
    cannot read". Only cases that stay decision B after child-2 (piped, file or wholly
    non-literal text) are listed, so child-2's recursion and B′ cannot break them. Literal
    text (`bash -c 'rm -rf ~'`) is NOT asserted here: after child-2 its reason is the inner
    command's, not "runs code the gate cannot read".
  - **Decision C on table failure.** A missing or invalid `commands.toml` gives decision
    C for every command, never a silent `mutating`.
  - **Fixed load location.** The loader takes no path argument. It reads
    `TARGETS_ROOT / TARGET_ID / "commands.toml"` (`src/nl_shell/targets.py:28`) with
    `TARGET_ID = "ubuntu-26.04"` a module-level constant (v3 drifted to "the only folder
    under `targets/`", `commands.py:63-73` in `iteration-v3/`; do not repeat). It refuses
    a resolved path outside that root, as `targets.py:153-155` does. Choosing the target
    from `/etc/os-release` is out of scope. Test seam: monkeypatch the loader module's
    root constant to a `tmp_path` with a missing or broken file, and clear the loader's
    cache. A test (not only a reviewer check) reads the loader module's source with `ast`
    inside the test function and fails if it uses `os.environ`, `os.getenv`, `Path.cwd`,
    `os.getcwd`, `Path.home`, `expanduser` or opens any path but the fixed one. Test: with a `commands.toml` in cwd saying `sudo` is harmless, and
    `NL_SHELL_COMMANDS`, `NL_SHELL_TARGETS`, `XDG_CONFIG_HOME` pointing at a folder with
    such a file, `sudo -i` stays `privileged`.
  - **Spec §3 builtins (floor only).** Row 33 (`alias ll='ls -l'`) and `unalias`,
    `source`, `.`, `eval`, `exec`, `trap`, `enable`, `set`, `shopt`, `bind`, `complete`,
    `hash`, `builtin`, `command` (except `command -v`/`-V`, `v1.md:101`), `export`,
    `declare`/`typeset`/`local`/`readonly` with assignments, and `unset` are at least
    `session-altering`. (Rows exist here because class 1/2 needs them; child-3 adds the
    name and stored-code rules on top.)
  - **Assertions.** Every case asserts the class (or a floor), a reason substring, and
    that no reason is "could not class". Exceptions: missing/invalid-table cases assert
    "could not class"; the ten-`env` case accepts the engine's reason or "could not
    class", but never a class below the one stated.
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: 

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (164 of 401 failed), green with it
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

Review replacing the policy gate’s all-mutating command stub with a reviewed command table and generic argv engine for destructive commands, elevation, wrappers, and opaque code execution (#204).

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The scoped closed-world rules distinguish elevation, unread argv, opaque text, and accepted floor gaps; acceptance criteria are falsifiable (target/docs/design/specs/policy-gate/v1.md:177, :190, :204). |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence demonstrates behavioral failures for recursive rm and sudo password-input rejection, beyond missing-new-module setup errors (gate-logs/C4-verify.log:2170, :3477, :7547); independent rerun unavailable here. |
| C3 Change | PASS | Meaning comes from reviewed rows and a fixed loader location rather than caller-controlled paths; the command-layer decoder preserves shell-layer literal semantics (target/src/nl_shell/gate/commands.py:311; target/src/nl_shell/gate/rules.py:119). |
| C4 Verification (red→green) | PASS | Frozen gate output establishes 164 assertion failures plus 12 setup errors pre-fix and 413 passing tests patched; this is log-supported verification, not an independent rerun (gate-logs/C4-verify.log:17, :7547). |
| C5 Causal adequacy | PASS | Replacing the absent command semantics addresses the stated cause; elevation and opaque-command scans cover the carried-forward bypass classes, with no capability-probe symptom guard found (target/src/nl_shell/gate/rules.py:299, :349, :389; target/tests/test_gate_commands.py:465, :532, :561, :578). |
| T1 Structure | PASS | Separate immutable table loading and one effect-driven engine keep command-specific meaning in data; seven affected Python files pass independent syntax compilation (target/src/nl_shell/gate/commands.py:336; target/src/nl_shell/gate/rules.py:404; review-checks.log:1). |
| T2 Shape | PASS | Threat-model claims and explicit residual gaps accompany the security change; independently harvested inventory is byte-identical and all 152 names match rows (target/.oss-scanner/threat_model.md:194; review-checks.log:2, :3; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen full-suite output records 1,546 passed, one skipped and five forkpty warnings; local pytest/parser dependencies are absent, so runtime success is supported by that log only (gate-logs/T3-suite.log:33, :43; review-checks.log:4). |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm prior art by every affected file path across merged history and closed/rejected work — the synthetic single-commit repository has no remote, so duplicate or previously rejected work cannot be ruled out (review-checks.log:5). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the documented security tradeoffs for this child — opaque quoted text and named floor gaps remain mutating, while decision A can over-raise until the allowlist child; passing tests cannot decide suitability for intended use (target/docs/design/specs/policy-gate/v1.md:204; brief.md:26). |

Evidence and limits:

- Grounding used only the supplied patched target. Its local base is the stated pre-fix snapshot; no stale-target issue was observed. No target source was edited.
- This reviewer’s Python has neither pytest nor tree_sitter/tree_sitter_bash. Consequently no independent stash/red/restore/green or full-suite run was possible. All four supplied gate logs were opened. The C4 log includes genuine assertion failures as well as fixture ImportErrors; those fixture errors alone are not the reproduction claim. The external parser dependency was exercised by the frozen successful gates, rather than replaced with a shim or code-read.
- Independently ran `python3 scripts/harvest_inventory.py --output ../review-inventory.toml` from target: successful, byte-identical inventory on Ubuntu 26.04.1. Parsed the command table and checked inventory-name coverage with stdlib TOML/fnmatch; this is not a substitute for the production loader tests. `git diff --check` passed; `python3 scripts/docs_links.py` reported 65 links, zero broken. `docs_checks.py` without arguments printed its required immutability BASE/HEAD usage and did not perform an audit.
- Prior-art investigation: path-filtered `git log --all` exposes only synthetic base b6e4e2d; `git remote -v` is empty. No closed/rejected-work records or INTEGRATION.md human-only checklist are supplied. The prior-art decision remains open; no external checkout was consulted.
- No grounded implementation defect found. The scope’s size and previous iteration are explicitly accepted in brief.md:277; they are not newly reopened here.

<!-- pdca:leaf-complete -->

### Advisory — adversary

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

### Advisory — security-review

# Security review — gate-command-table-engine (#204)

**Attacker-reachable inputs this diff touches:** the model's proposal text (threat model "Where untrusted input enters" item 5) and typed or retrieved command text. Both reach `nl_shell.gate.classify`, then `rules.classify` (`src/nl_shell/gate/__init__.py:196`), and from there the new engine (`src/nl_shell/gate/rules.py`) and the table loader (`src/nl_shell/gate/commands.py`).

I ran about 200 crafted commands against the patched tree through the public `classify(cmd, origin=...)` (harness venv, tree-sitter-bash present). One finding. It is High on the threat model's scale ("a privileged … step is classed lower"), but it comes from a floor the spec already sets, so a human has to decide what to do with it.

## Findings

- NEEDS-HUMAN [human] — **High** — `src/nl_shell/gate/rules.py:312-322` (with `docs/design/specs/policy-gate/v1.md:90-92` and `:162-163`). **Input:** the command word of a model proposal. **What goes wrong:** when the command word is a glob, a variable or a find/xargs placeholder that bash turns into `sudo` at run time, the engine classes it `mutating` or `destructive`. The proposal is **not rejected** and the §5 sudo rules never run. Results seen on the patched tree:
  - `/usr/bin/sud? -i` → `mutating`, proposal accepted (bash globs it to `/usr/bin/sudo -i`, a root shell).
  - `/usr/bin/s*do -S true` → `mutating`, accepted for both `proposal` and `typed`. This gets around §5's `sudo -S` rejection. The threat model's "What must hold" says the gate rejects `sudo -S`. Passthrough starts only for privileged commands, so the password prompt for this command would come up outside passthrough.
  - `/usr/*/sudo -i` → `mutating`, accepted. `x=sudo; $x -i` → `mutating`, accepted.
  - `find /usr/bin -name 'sud?' -exec {} -i \;` and `ls /usr/bin/sud? | xargs -o -I% % -i` → `destructive`, accepted.

  The patch fails closed on the same risk elsewhere. An undecodable `$'…'` word "may spell any command, `sudo` included" and is made `privileged` and rejected (`rules.py:305-311`). A glob or variable in the command word may spell `sudo` just as easily, but stays at the `mutating` floor. That floor is older than this patch: spec §2 (`v1.md:90`) and the new §4.1 decision A text (`v1.md:162-163`, "whose command word the gate cannot read … is at least `mutating`"). So this is a scope or spec decision, not a builder slip. Options: (a) for a command word whose only non-literal part is a glob, match its last path part with `fnmatch` against row names and apply the elevating/destroying rows (`sud?` and `s*do` match `sudo`, `r?` matches `rm`), and reject proposals whose command word is a variable or placeholder; (b) reject every proposal whose command word the gate cannot read; (c) write the case into the threat model's "Known gaps" so it is accepted on purpose. Neither the patch's tests nor `gate-vectors.toml` cover a glob command word that resolves to `sudo`. Reproducer: `classify("/usr/bin/sud? -i", origin="proposal")` should come back `privileged`, rejected. Today it gives `mutating`, not rejected.

## Checked, no finding

- **Sudo family and §5:** `-S`/`-A`/`-p` in every spelling I tried (`-nS`, `-Sn`, `"-S"`, `$'-\x53'`, `-$'S'`, `--stdin`, `--prompt=x`, the `--pro` and `--stdi` prefixes on `sudo`, `sudo.ws` and `sudo-rs`, and `sudoedit-rs -S`) are all rejected. Pipes, here-docs and here-strings into sudo are rejected. `sudo -- -S true` is `privileged` and not rejected, which is correct: after `--`, `-S` is the name of the program to run.
- **Elevation reaching inner commands:** `sudo` + `bash`/`zsh`/`python3.14`/`perl5.40.1`/`awk`/`tclsh`/`gjs`/`gdb`/`screen`/`tmux`/`busybox`/`at`/`crontab`/`./bash`/`/bin/bash`, `sudo env -S bash`, `sudo xargs bash`, `sudo systemd-run bash`, `sudo sudo -i` and `sudo -u root -s` are all rejected as proposals.
- **Wrappers:** `env` (`-C`, `-u`, `--chdir=`, `-P`, `-`), `nice --`, `nohup --`, `timeout -k`/`--signal=`, `stdbuf`, `setsid -w`, `time -p`, `watch -x`, `command -p`, `exec -c`/`-l`, `builtin`, `find -exec`/`-execdir`/`-ok`/`-okdir`, `strace`/`ltrace`, `chrt`/`taskset` (decision A), and `busybox env` each followed by `sudo -i` are all `privileged` and rejected.
- **xargs replace strings:** `-I sudo`, `-Isudo`, `--replace`, `-i … {}` and `-I"$r"` before `sudo` are rejected. `-I$'s' s -i` is `destructive`; that is the placeholder part of the finding above.
- **ANSI-C decoding** (`rules.py:106-228`): `\u`, `\U`, octal, `\x{…}` (including more than 2 digits and an 8000-digit body) and the NUL cut-off all decode to the expected command name. Double-quoted `$'` gives no readable word and fails closed.
- **Decision B:** `x | sh`, `sh < f`, `bash -c "$v"`, `eval "$v"`, `. ./f`, `source f`, `python3 -m`/`-c`/file, `perl -M`, `ruby -e`, `node -e`/`--eval=`, `awk -f /dev/stdin`, `env -S`, `flock -c`, `script -c`, `watch 'text'` and `enable -f` are all at least `destructive`. `awk '<program>'` stays `mutating`; that is the documented class-7 gap in the threat model.
- **Loader** (`commands.py:305-330`): one fixed path, resolved and kept under `TARGETS_ROOT`. No environment variable, cwd or `HOME` lookup. The harvester (`scripts/harvest_inventory.py:98,109`) calls `subprocess.run` without a shell and is run only by a developer, so no attacker input reaches it.
- **Resource limits:** 40 nested `env`s, 1500 `nice`s and 500 nested `find -exec`s all hit `MAX_NESTING` and become decision C ("could not class", rejected) in about 10 ms. 700 nested `xargs -I%` and an 8 KB argv take under 0.1 s. Nothing raised or hung.

Not a security issue, but worth a look: `sudo find . -name x` is rejected as a proposal because the operand `.` matches the `.` (source) builtin row ("runs a shell or interpreter under sudo: ."). This over-rejects. It never classes anything lower.
<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T5 Judgment — Confirm prior art by every affected file path across merged history and closed/rejected work — the synthetic single-commit repository has no remote, so duplicate or previously rejected work cannot be ruled out (review-checks.log:5).
- [ ] Validation — fitness-to-purpose — Accept the documented security tradeoffs for this child — opaque quoted text and named floor gaps remain mutating, while decision A can over-raise until the allowlist child; passing tests cannot decide suitability for intended use (target/docs/design/specs/policy-gate/v1.md:204; brief.md:26).
- [ ] **Locale-quoted words (`$"…"`) get past decisions A and §5.** In bash 5.3.9, `printf '[%s]' $"sudo"` prints `[sudo]`, because with no message catalogue `$"…"` is just `"…"`. The gate gets these wrong:
- [ ] **The no-command test passes for the wrong reason.** `test_class2_no_command_opens_a_shell_under_sudo` (`tests/test_gate_commands.py:290-294`) asserts only `rejected=True` and no reason. The same goes for the `sudo chroot /` and `sudo unshare` regressions (`:306-307`, reason `"shell"`). `commands.py:457-459` folds `no_command == "opens-shell"` into `runs_code`. As a result, `_elevation` rejects `sudo chroot …` just because the word `chroot` appears (`rules.py:391-393`, reason "proposal runs a shell or interpreter under sudo: chroot"), before the no-command path at `rules.py:468-469` matters. Proof: `sudo chroot / ls`, `sudo unshare ls` and `sudo screen ls` are all rejected the same way. If `_opens_shell(... "with no command")` broke, these tests would stay green. Fix: assert the `"with no command"` reason in the test (for example, `sudo chroot /` should carry "opens an interactive shell: chroot with no command").
- [ ] **The elevation rule rejects common harmless proposals.** `_elevation` looks up *every* later argument word, operands included (`rules.py:386-393`). `_elevated_opaque` rejects any dash word under a command with no row (`rules.py:367-376`). Proposals that come out rejected (not just confirm-gated):
- [ ] **The class-7 gap is wider than the brief listed.** The brief names the accepted code-running gap as `git -c` / `--config-env` / `--exec-path`, `tar --to-command` and `ssh -o`. The patch adds "an `awk` program given as its operand" (`docs/design/specs/policy-gate/v1.md:208-212`), so `awk 'BEGIN{system("rm -rf ~")}'` stays `mutating`, "not allowlisted", typed or proposed. This matches the original spec's Conformance row 10 (`awk … | mutating`, `v1.md:358`). The brief's mapping "floor rows 8/10/11 = git/tar/ssh" was itself inconsistent with the spec. A human should confirm that the awk program operand belongs in the reviewed gap.
- [ ] **High** — `src/nl_shell/gate/rules.py:312-322` (with `docs/design/specs/policy-gate/v1.md:90-92` and `:162-163`). **Input:** the command word of a model proposal. **What goes wrong:** when the command word is a glob, a variable or a find/xargs placeholder that bash turns into `sudo` at run time, the engine classes it `mutating` or `destructive`. The proposal is **not rejected** and the §5 sudo rules never run. Results seen on the patched tree:
- [ ] **The tracker record is missing, so the problem framing cannot be checked against the thread.** The bundle has no `notes.json`, no `sources/` and no `dependency-state.json` (cwd holds only `brief.md` and `.claude/`). The brief takes its decisions (A, C, "elevation reaches inner commands", option (a) "at the re-plan") from `results/issue_189/brief.md:99-112` and from the v3/v4 sign-offs, and it relies on `engine/scripts/run-verify.sh:196` and `iteration-v3/commands.py:63-73`. None of these files is in the target or in the bundle. Nothing in the record I was given shows that the maintainer chose these decisions. A human should confirm that the bundle was assembled with its thread before sign-off.
- [ ] **The ANSI-C change to `lex_word` is a hidden second change to the shell layer, and it can lower verdicts.** The brief puts it in scope as a narrow fix (`parse.py` "**only** `lex_word`"). But `lex_word`/`make_word` feed the literal flag to every shell-layer rule, not just to the command layer:
- [ ] **Decision A over-raises now, and #198 would later have to lower those classes.** The allowlist is out of scope (#198), so on this child's output every command without a row is "opaque". Under decision A, any argument word that names an `elevates` row makes the command `privileged` and rejected as a proposal. That catches `man sudo`, `which sudo`, `apt show sudo`, `dpkg -L sudo` and `echo su`, unless each of those commands has a row (the brief does not say so). All of these are allowlist-table commands (`v1.md:165-176`) that should end up `read-only`. When #198 makes them allowlisted, their class drops from `privileged` to `read-only`, which `v1.md:241` counts as a v2-only change. The brief should say whether decision A skips allowlisted commands by design, so that #198's drop is defined and not a lowering. It should also either list the rows that keep these commands out of decision A here, or say that the temporary over-raise is accepted.
- [ ] **Spec row 16 contradicts the new behaviour, and the brief does not hand that text to anyone.** `v1.md:268` reads "`$'\x72m' -rf ~` | mutating at least (non-literal word)". After this child, the word is literal and the command is `destructive`. That is a raise, so it is allowed, but the stated reason in the conformance row becomes false. The brief's list of spec text owned here covers "§4/§5 rows, the new §4.1 …" but not the Conformance table. The planner should add row 16 to that list (with the `gate-vectors.toml` row as well), or the Check step will find the spec and the code out of step.
- [ ] **This is several deliverables, not one logical fix.** The listed work includes a generic argv-grammar engine; a TOML format and loader with refusal rules; a full command table covering wrappers, the sudo family, destructive commands, text-runners and every §3 builtin; a host-harvesting script plus a checked-in inventory; the `lex_word` parser change; changes to `test_policy_gate.py`; and new spec §4.1 and threat-model text. The success criterion has about 150 named cases. `scripts/harvest_inventory.py` + `inventory.toml` is its own reviewable change: the brief says it is "reviewed like an allowlist change" and "not run by any test", and its only check is a reviewer re-running it on "this Ubuntu 26.04.1 host". Splitting it out, or the parser change, would cut the review surface Do has to spend. If the human keeps one bundle, the size should be a stated decision.
- [ ] **Some success checks can't be reproduced by a gate.** The class-1 coverage property ("every name in `inventory.toml` has a row") checks the table against an inventory the same builder writes. The only independent check is a reviewer re-running the harvester "on this host" and diffing the output. That depends on the host and isn't a gate, so a missing alias name (`sudoedit-rs`-style) can only be caught by a human. The fixed minimum name list in the test only partly fills that gap. Two more checks are also reviewer-only: "no `os.environ`, `Path.cwd()` … in the loader" (this one could be a grep or AST test), and the `.venv` path in the Reproduction step, which points outside the repo (`/home/eddie/nl-shell/nl-shell-pdca/.venv`). The planner should turn the loader ban into a test, and either state in the brief that harvester drift is human-adjudicated or give the reference host explicitly.
- [ ] size backstop — this slice is behaving oversized: patch is 199 KB (threshold 100 KB). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.

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
- Iteration delta (if iterating): Re-plan needed for a spec decision, not more build work. The security review found that a proposal whose command word the gate cannot read (a glob like `/usr/bin/sud? -i` or `/usr/bin/s*do -S true`, a variable like `x=sudo; $x -i`, or a find/xargs placeholder) is classed `mutating` and not rejected. That gets past §5 and decision A. The cause is the spec floor (v1.md §2 :90 and §4.1 decision A :162-163: "command word the gate cannot read is at least mutating"). The re-plan must decide: (a) fnmatch glob command words against row names and reject variable/placeholder command words in proposals, (b) reject every proposal whose command word is unreadable, or (c) record it in the threat model's Known gaps. Then update spec and brief to match. Carry into the revised brief as well: - `$"…"` locale quoting is a bypass in this patch: `$"sudo" -i` (proposal) must be rejected, `$"rm" -rf build` destructive, `foo $"sudo"` privileged. Decode `$"…"` like `"…"` for row lookup, or fail closed like undecodable `$'…'`. - `test_class2_no_command_opens_a_shell_under_sudo` and the `sudo chroot /` / `sudo unshare` regressions must assert the "with no command" reason, not just rejected.
- By / date: Eduard Ralph / 2026-10-26

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 6 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

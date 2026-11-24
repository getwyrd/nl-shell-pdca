# Result — issue 197 / ast-policy-gate-command-engine

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: 
- Success criterion: `tests/test_gate_commands.py` passes, covering:
  - §4 privileged: row 24 (`sudo apt update`) `privileged`; `su`, `pkexec`, `doas`,
    `run0`, `machinectl shell`, `machinectl shell root@`; `//usr/bin/sudo true` is
    `privileged`, never lower.
  - §4 destructive: row 26 (`rm -rf build`), row 17 (`"r"m -rf ~`), row 18
    (`ls; rm -rf ~`), row 29 (`systemctl stop ssh`), row 9 (`find . -exec rm {} \;`),
    and `dd`, `mkfs.ext4`, `wipefs`, `shred`, `truncate`, `chmod -R`, `find -delete`,
    `git clean`, `git reset --hard`, `git push --force`, `kill -9 -1`. Row 9 is derived
    (decided at Plan, record it in the spec): find substitutes `{}` with paths unknown at
    classification time, so for `find -exec/-execdir/-ok/-okdir` (and xargs's appended or
    `-I` operands) `{}` is a non-literal operand of the inner command, and `rm` with a
    non-literal operand is classed like `rm` with a glob operand (§4) ⇒ `destructive`.
  - §4 wrappers: the `env rm -rf x` half of row 32 is `destructive`; `nice`, `nohup`,
    `timeout`, `time`, `xargs`, `watch`, `bash -c`, `sh -c` take their inner command's
    class and are at least `mutating`; `xargs` / `find -exec` with a non-literal inner
    command are at least `destructive`. v1/v2 regressions, each as a proposal
    `privileged` and rejected (typed: `privileged`): `env - sudo -i`, `env 'A=1' sudo -i`,
    `env -a x sudo -i` (uutils env 0.10.0 on the target takes a value for `-a`/`--argv0`),
    `env -S 'sudo -i'`, `exec -a x sudo -i`, `nice -n5 sudo -i`, `timeout -s9 5 sudo -i`,
    `stdbuf -o0 sudo -i`, `setsid sudo -i`, `flock /tmp/l sudo -i`, `script -c 'sudo -i'`.
    `env - rm -rf ~` and `printf rm | xargs -I% % -rf ~` are `destructive`. Ten nested
    `env`s around `sudo -i` as a proposal: `privileged` and rejected (through the inner
    command or decision C — never lower).
  - Property test over the data: every `commands.toml` row with `runs-command-at` carries
    a minimal example prefix in the row (e.g. `timeout 5`); for every such row,
    `<prefix> rm -rf x` is at least `destructive` and `<prefix> sudo -i` as a proposal is
    `privileged` and rejected.
  - §5 sudo rules: row 21 (`sudo -S true`, `sudo -p x true`, `sudo -A true`), row 22
    (`echo pw | sudo -S true`), `sudo "-S" true`, `sudo $'-S' true`, `sudo "$P" true`
    (a non-literal word in sudo's option position may be `-S`: rejected),
    `sudo -s <<<x`, `printf x | sudo -i`, `sudo -s` / `-i` with a pipe or here-doc, a pipe / here-doc /
    here-string into `sudo`, `su`, `pkexec`, `doas` — all rejected. v2 regressions:
    `cat <<E | sudo tee /x` and `cat <<E | doas id` are rejected with the pipe reason.
    Proposals `sudo -i`, `sudo -s`, `sudo su`, `sudo bash`, bare `su`, `pkexec bash` are
    rejected; typed, they are `privileged`.
  - §3 builtins: row 33 (`alias ll='ls -l'`) and `unalias`, `source`, `.`, `eval`,
    `exec`, `trap`, `enable`, `set`, `shopt`, `bind`, `complete`, `hash`, `builtin`,
    `command` (but not `command -v` / `command -V`, per `v1.md:101`), `export`, `declare` / `typeset` / `local` /
    `readonly` with assignments, `unset` are at least `session-altering`.
  - `sets-variable`, v2 regressions (forms with no plain `variable_assignment` node, so
    child-1 cannot see them): `export "SUDO_PROMPT"=x`,
    `declare 'SUDO_ASKPASS'=/x`, `declare -n r=SUDO_ASKPASS; r=/x`,
    `printf -v SUDO_ASKPASS /x`, `read SUDO_PROMPT <<<x`, `mapfile SUDO_PROMPT <x`,
    `getopts x SUDO_PROMPT`, `let SUDO_ASKPASS=1` are rejected; the same forms
    naming `PATH` or `LD_PRELOAD` are `session-altering`.
  - Decision A: `foo sudo x` is `privileged` and a proposal is rejected;
    `foo rm -rf x` is at least `destructive`. Decision A applies only to a command with
    neither a `commands.toml` row nor an allowlist entry.
  - Floor cases (no-regression group, *not* part of the red-leg claim, since the stub
    gives the same answer): row 8 (`git -c core.pager=sh log`), row 10, row 11, row 27
    (`git status`), `tar --to-command=sh -xf a.tar`, `ssh -o ProxyCommand=sh h` stay
    `mutating` "not allowlisted"; `bash -c 'true'` is not raised by decision B. They
    live in a separately named test function so a reviewer can see they guard against
    over-raising, not prove the engine.
  - Decision B: `x | sh`, `bash < f`, `bash f.sh`, `bash -c "$v"`, `eval "$v"`,
    `. ./f`, `echo 'sudo rm -rf /' | bash` are `destructive`, reason "runs code the gate
    cannot read"; `bash -c 'rm -rf ~'`, `bash <<<'rm -rf ~'`, `bash -s <<<'rm -rf /'`,
    `. /dev/stdin <<<'rm -rf /'` and a quoted here-doc running `rm -rf ~` are
    `destructive` by recursion; `bash <<<'sudo ls'` as a proposal is rejected.
  - Work budget across recursion, v2 regression: `{ bash;bash;bash;bash; } <<'E0'` nested
    nine deep (about 320 bytes; v2 grew ×4 per level). The budget is counted in work
    units (nodes visited plus recursive classifications), not time: the test asserts
    the units used stay below the budget constant, which exists as a named value in
    `gate/parse.py`, and that the result is never below `mutating` (decision C if the
    budget runs out). A loose 10 s wall-clock timeout is only a backstop against a hang.
  - A missing or invalid `commands.toml` gives decision C for every command (`privileged`,
    rejected, "could not class"), never a silent `mutating`.
  - Fixed load location: the loader takes no path argument; it reads
    `TARGETS_ROOT / <id> / "commands.toml"` (`src/nl_shell/targets.py:27-28` — the
    checkout's `targets/` while the package is not packaged yet, #48/#50) and refuses a
    resolved path outside that root as `:153` does. Reviewer check: no `os.environ`,
    `Path.cwd()`, `Path.home()` or config read in the loader. Test: with a `commands.toml`
    in the test's cwd that declares `sudo` harmless, and `NL_SHELL_COMMANDS`,
    `NL_SHELL_TARGETS` and `XDG_CONFIG_HOME` set to a folder holding such a file,
    `sudo -i` stays `privileged`. No signature: anyone able to write that folder can also
    write `rules.py` (threat model `.oss-scanner/threat_model.md:54`, code running as the
    user is out of scope; install integrity is the supply-chain row `:299`, release-wide).
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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (222 of 392 failed), green with it
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

Review the data-driven command policy engine for wrappers, privilege escalation, destructive commands, variable assignments, and unreadable code (#197).

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The intended fail-closed command meanings and proposal rejection rules are explicit and bounded to this child; target/docs/design/specs/policy-gate/v1.md:122 and :195. |
| C2 Reproduction (red pre-fix) | PASS | Frozen execution demonstrates the stub misclassifies sudo as mutating and produces 222 failures out of 392 tests, rather than collection failures; gate-logs/C4-verify.log:28 and :9419. |
| C3 Change | PASS | Reviewed command data and a shared interpreter replace the stub within the specified scope, with shared recursion accounting; target/src/nl_shell/gate/rules.py:456 and target/src/nl_shell/gate/commands.py:221. |
| C4 Verification (red→green) | PASS | Frozen evidence records 392 passing patched tests and 222 pre-fix failures; independent pytest execution was unavailable here, so this verdict rests on the captured execution; gate-logs/C4-verify.log:17 and :9419. |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Close the interactive-root-shell bypass for positional arguments with -s/-is: sudo bash -is dummy is privileged but unrejected in the isolated engine probe, contrary to the proposal rule; target/targets/ubuntu-26.04/commands.toml:542 and target/docs/design/specs/policy-gate/v1.md:195. |
| T1 Structure | PASS | A validated fixed vocabulary and effect dispatch preserve the requested data-driven architecture without command-specific interpreter branches; target/src/nl_shell/gate/commands.py:31 and target/src/nl_shell/gate/rules.py:777. |
| T2 Shape | PASS | The security model documents command-table trust and decisions A/B/C, and the independent whitespace check is clean; target/.oss-scanner/threat_model.md:182 and gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | Captured full-suite execution reports 1493 passed and one skipped; this is log-supported evidence, not an independent local rerun; gate-logs/T3-suite.log:38. |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive audit reruns at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Complete affected-path merged-history and closed/rejected-work prior-art review before sign-off: this disposable checkout has only one synthetic base commit and no remotes, and the frozen logs contain no such audit; brief.md:149. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the broader class increases and decision A false positives are acceptable for user confirmation and proposal rejection, after the root-shell bypass is addressed; target/docs/design/specs/policy-gate/v1.md:301 and brief.md:171. |

Independent checks and limitations:

- `git -C target diff --check` passed. Target citations above refer to the supplied patched source; no stale-target problem was observed.
- `python -m pytest -q tests/test_gate_commands.py tests/test_policy_gate.py` could not start because `python` is absent. The same command with `python3` failed because pytest is absent; importing tree_sitter also failed. With no runnable local test toolchain, no stash/red/unstash/green sequence was performed. The complete frozen C4 and T3 logs show actual pytest execution, including the parser-dependent tests; the declared parser dependency was exercised there. This sandbox limitation is not a patch defect.
- `python3 engine_probe.py` exercised the actual command loader and interpreter with terminal-stdin Invocation objects. It loaded only the parser module's data definitions, omitting tree-sitter imports and initialization; it did not exercise parsing or the full gate. Results: `sudo bash` → privileged, rejected=True, opens_shell=True; `sudo bash -s dummy` and `sudo bash -is dummy` → privileged, rejected=False, opens_shell=False. The latter explicitly requests an interactive shell, and -s treats dummy as a positional argument rather than a script filename. The stdin handler returns without setting opens_shell for terminal input (target/src/nl_shell/gate/rules.py:643); the shell row's no_operands condition suppresses the marker. Fix the row and add full-pipeline proposal regressions for these forms and an elevating wrapper such as pkexec.
- Prior-art investigation ran `git log --all` restricted to every affected path: only `b37591f pre-fix base 0b6f18f4f70efd77d9981ee3f574a335f9ae94fc` was available. `git remote -v` returned nothing. No INTEGRATION.md was supplied or found inside the target; its enumerated human-only checklist could not be inspected. The brief references earlier v2 review findings but does not provide merged-history or closed-work audit evidence.
- The capability-probe symptom-guard trigger does not fire: the patch's exception handling implements table validation and fail-closed classification rather than probing an optional capability around a load-time side effect.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue #197 (policy gate command engine)

**Evidence.** I re-ran the bundle tests on the patched target (`tests/test_gate_commands.py` and `tests/test_policy_gate.py`), using a venv in my sandbox with the pinned `tree-sitter==0.26.0` / `tree-sitter-bash==0.25.1`: **392 passed**. That matches the green leg in `gate-logs/C4-verify.log`. The red leg in that log (222 of 392 fail with `rules.py` / `commands.toml` reverted) goes through the production entry point `nl_shell.gate.classify`, not a copy of it. The edits to `tests/test_policy_gate.py` only raise expected classes, never lower them. The floor group passes on both legs, as the brief says it should. I found no tautology in the proof. The weak spots are in the data: some commands are missing from the table. My sandbox host is Ubuntu 26.04.1 with uutils `env` 0.10.0, which is the real target, so the cases below were checked against the actual binaries.

## Findings

- NEEDS-HUMAN [impl] — `targets/ubuntu-26.04/commands.toml:76`: the sudo family is missing the binary names that actually ship on the target. On this Ubuntu 26.04 host, `/usr/bin/sudo-rs`, `/usr/bin/su-rs`, `/usr/bin/sudoedit-rs` (links to setuid `/usr/lib/cargo/bin/{sudo,su}`) and setuid `/usr/bin/sudo.ws` all exist. The threat model even names sudo-rs as the target's sudo (`.oss-scanner/threat_model.md:216`). Probe results: proposal `sudo-rs -i` → `mutating`, not rejected. `sudo.ws -i`, `su-rs` and `/usr/bin/sudo-rs -i` → the same. Typed `sudo-rs -S true` → `mutating`, not rejected. `foo sudo-rs` → `mutating`, so decision A misses it too. `rules.py:106-114` (`command_name`) matches only exact row names, so every §4/§5 sudo rule is bypassed by adding a suffix. Fix: add `sudo-rs`, `sudo.ws`, `sudoedit-rs` to the sudo row and `su-rs` to the su row. Add test cases for each.

- NEEDS-HUMAN [impl] — `targets/ubuntu-26.04/commands.toml:275-278` with `src/nl_shell/gate/rules.py:634-639`: the `env -S` text is classed as **bash** text, but env's split-string syntax is different. uutils env 0.10.0 on the target treats `\_` as a word separator and expands `${VAR}`. I checked on the host: `env -S 'id\_-u'` prints `1000`. So proposal `env -S 'sudo\_-i'` runs `sudo -i`, yet the gate gives `mutating`, not rejected ("not allowlisted"). `env -S 'rm\_-rf\_/'` gives `mutating`. This bypasses the v2 regression `env -S 'sudo -i'` that the brief lists by name. Fix: treat an `-S` string that holds `\_`, `${` or another env-only escape as text the gate cannot read (decision B, at least `destructive`), or convert it to bash words before classing it.

- NEEDS-HUMAN [impl] — `targets/ubuntu-26.04/commands.toml:394-420`: `chroot` and `unshare` start `$SHELL` when given no command, but their rows have no `opens-shell` effect. Proposals `sudo chroot /` and `sudo unshare` both give `privileged`, **not rejected**, even though each opens an interactive root shell (§5 root-shell rule). Compare `sudo bash`, which is rejected. Fix: add `opens-shell` with `when = { has_operands = false }` or the right operand count (chroot: no operand after the root dir; unshare: `no_operands`).

- NEEDS-HUMAN [impl] — `targets/ubuntu-26.04/commands.toml:675-686`: the `mapfile`/`readarray` row lists `-C` (callback) only as a value option. But bash **evaluates** the `-C` text as code every `-c` lines. `mapfile -C 'rm -rf ~' -c 1 arr < /etc/passwd` → `mutating`. `mapfile -C 'sudo -i' -c 1 arr < f` → `mutating`. The fix is one data line: add a `runs-text` effect with `option = ["-C"]` and `in_shell = true`.

- NEEDS-HUMAN [impl] — `targets/ubuntu-26.04/commands.toml:658-711` (the sets-variable builtins): there is no row for `wait`, and bash 5.1+ `wait -p NAME` assigns a variable. `wait -p SUDO_PROMPT` gives `mutating`, not rejected, while the equivalent `read SUDO_PROMPT <<<x` is rejected. The brief says "builtins that assign variables are data rows", and this one is missing. Fix: add a `wait` row with a `sets-variable` effect, `from = "option"`, `option = ["-p"]`.

- NEEDS-HUMAN [impl] — `targets/ubuntu-26.04/commands.toml:605`: `enable -f /tmp/x.so foo` loads a shared object into the running bash. That is native code the gate cannot read, yet the result is only `session-altering`. Decision B says code the gate cannot read is at least `destructive`. Fix: add a `runs-file-as-code` effect on `option = ["-f"]` for `enable`. This needs `enable` split out of the shared `raw` row.

- NEEDS-HUMAN [human] — `src/nl_shell/gate/rules.py:230-244` (decision A) and the table scope: on this target, decision B covers only `bash`/`sh`/`dash`/`rbash` (`commands.toml:506`). `curl x | python3`, `curl x | perl` and `python3 -c "$v"` all give `mutating`, and `python3`, `perl` and `busybox` are all installed on the host. Decision A reads only whole argument words, so proposals `busybox sh -c 'sudo -i'` and `foo bash -c 'sudo -i'` give `mutating`, not rejected. Proposals `sudo zsh` and `sudo busybox sh` are `privileged` but not rejected as root shells. This follows decisions A and B as written, but the brief's invariant says "any code the gate cannot read gets an explicit fail-closed default". A human should decide whether default-installed interpreters (`python3`, `perl`, `busybox`) belong in `commands.toml` now or wait for the #198 allowlist.

- NEEDS-HUMAN [human] — out of this diff's code, but in its stated goal: assignments with no simple command still slip past sets-variable. `(( SUDO_ASKPASS=1 ))` gives `mutating` ("no simple command to class"), even though the `let SUDO_ASKPASS=1` regression from the brief is rejected. `: ${SUDO_ASKPASS:=/x}` and `for SUDO_PROMPT in x; do :; done` give `mutating`. These are walker (#196) territory. A human should decide whether this bundle's "v2 regressions with no `variable_assignment` node" claim covers them or a follow-up issue does.

- Attempted and **could not refute**: wrapper option forms (`nice -5`, `timeout -k1 5`, `env -u X`, `env --chdir=/`, `env -vS'…'`, `env --split-string=…`, `exec -a`, `command -p`, `builtin eval`, `time -p`, `flock … -c`, `script -qc` / `--command=`); sudo option forms (`--stdin`, `-kS`, the ambiguous prefix `--pr`, `-u root -- bash`, `/bin/bash`, `env bash`, `-E -s`, `/usr/lib/cargo/bin/sudo -i` through decision A); stdin aliases (`/dev//stdin`, `/proc/self/fd/0`, `/dev/fd/0`, `sh -`); find/xargs (`-execdir`, `+`, `-i {}`, `-I{} sh -c '{}'`, `find -delete` with no path); git force forms (`+refspec`, `-f`, `--force-with-lease`, `-C x reset --hard`); `kill -KILL -1` and `kill -s 9 -- -1`; `chmod --recursive`; `rm --rec` (prefix match), `rm -f *`, `rm ~/x`. All of these fail closed as the brief requires.

<!-- pdca:leaf-complete -->

### Advisory — security-review

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

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C5 Causal adequacy — Close the interactive-root-shell bypass for positional arguments with -s/-is: sudo bash -is dummy is privileged but unrejected in the isolated engine probe, contrary to the proposal rule; target/targets/ubuntu-26.04/commands.toml:542 and target/docs/design/specs/policy-gate/v1.md:195.
- [ ] T5 Judgment — Complete affected-path merged-history and closed/rejected-work prior-art review before sign-off: this disposable checkout has only one synthetic base commit and no remotes, and the frozen logs contain no such audit; brief.md:149.
- [ ] Validation — fitness-to-purpose — Decide whether the broader class increases and decision A false positives are acceptable for user confirmation and proposal rejection, after the root-shell bypass is addressed; target/docs/design/specs/policy-gate/v1.md:301 and brief.md:171.
- [ ] `targets/ubuntu-26.04/commands.toml:76`: the sudo family is missing the binary names that actually ship on the target. On this Ubuntu 26.04 host, `/usr/bin/sudo-rs`, `/usr/bin/su-rs`, `/usr/bin/sudoedit-rs` (links to setuid `/usr/lib/cargo/bin/{sudo,su}`) and setuid `/usr/bin/sudo.ws` all exist. The threat model even names sudo-rs as the target's sudo (`.oss-scanner/threat_model.md:216`). Probe results: proposal `sudo-rs -i` → `mutating`, not rejected. `sudo.ws -i`, `su-rs` and `/usr/bin/sudo-rs -i` → the same. Typed `sudo-rs -S true` → `mutating`, not rejected. `foo sudo-rs` → `mutating`, so decision A misses it too. `rules.py:106-114` (`command_name`) matches only exact row names, so every §4/§5 sudo rule is bypassed by adding a suffix. Fix: add `sudo-rs`, `sudo.ws`, `sudoedit-rs` to the sudo row and `su-rs` to the su row. Add test cases for each.
- [ ] `targets/ubuntu-26.04/commands.toml:275-278` with `src/nl_shell/gate/rules.py:634-639`: the `env -S` text is classed as **bash** text, but env's split-string syntax is different. uutils env 0.10.0 on the target treats `\_` as a word separator and expands `${VAR}`. I checked on the host: `env -S 'id\_-u'` prints `1000`. So proposal `env -S 'sudo\_-i'` runs `sudo -i`, yet the gate gives `mutating`, not rejected ("not allowlisted"). `env -S 'rm\_-rf\_/'` gives `mutating`. This bypasses the v2 regression `env -S 'sudo -i'` that the brief lists by name. Fix: treat an `-S` string that holds `\_`, `${` or another env-only escape as text the gate cannot read (decision B, at least `destructive`), or convert it to bash words before classing it.
- [ ] `targets/ubuntu-26.04/commands.toml:394-420`: `chroot` and `unshare` start `$SHELL` when given no command, but their rows have no `opens-shell` effect. Proposals `sudo chroot /` and `sudo unshare` both give `privileged`, **not rejected**, even though each opens an interactive root shell (§5 root-shell rule). Compare `sudo bash`, which is rejected. Fix: add `opens-shell` with `when = { has_operands = false }` or the right operand count (chroot: no operand after the root dir; unshare: `no_operands`).
- [ ] `targets/ubuntu-26.04/commands.toml:675-686`: the `mapfile`/`readarray` row lists `-C` (callback) only as a value option. But bash **evaluates** the `-C` text as code every `-c` lines. `mapfile -C 'rm -rf ~' -c 1 arr < /etc/passwd` → `mutating`. `mapfile -C 'sudo -i' -c 1 arr < f` → `mutating`. The fix is one data line: add a `runs-text` effect with `option = ["-C"]` and `in_shell = true`.
- [ ] `targets/ubuntu-26.04/commands.toml:658-711` (the sets-variable builtins): there is no row for `wait`, and bash 5.1+ `wait -p NAME` assigns a variable. `wait -p SUDO_PROMPT` gives `mutating`, not rejected, while the equivalent `read SUDO_PROMPT <<<x` is rejected. The brief says "builtins that assign variables are data rows", and this one is missing. Fix: add a `wait` row with a `sets-variable` effect, `from = "option"`, `option = ["-p"]`.
- [ ] `targets/ubuntu-26.04/commands.toml:605`: `enable -f /tmp/x.so foo` loads a shared object into the running bash. That is native code the gate cannot read, yet the result is only `session-altering`. Decision B says code the gate cannot read is at least `destructive`. Fix: add a `runs-file-as-code` effect on `option = ["-f"]` for `enable`. This needs `enable` split out of the shared `raw` row.
- [ ] `src/nl_shell/gate/rules.py:230-244` (decision A) and the table scope: on this target, decision B covers only `bash`/`sh`/`dash`/`rbash` (`commands.toml:506`). `curl x | python3`, `curl x | perl` and `python3 -c "$v"` all give `mutating`, and `python3`, `perl` and `busybox` are all installed on the host. Decision A reads only whole argument words, so proposals `busybox sh -c 'sudo -i'` and `foo bash -c 'sudo -i'` give `mutating`, not rejected. Proposals `sudo zsh` and `sudo busybox sh` are `privileged` but not rejected as root shells. This follows decisions A and B as written, but the brief's invariant says "any code the gate cannot read gets an explicit fail-closed default". A human should decide whether default-installed interpreters (`python3`, `perl`, `busybox`) belong in `commands.toml` now or wait for the #198 allowlist.
- [ ] out of this diff's code, but in its stated goal: assignments with no simple command still slip past sets-variable. `(( SUDO_ASKPASS=1 ))` gives `mutating` ("no simple command to class"), even though the `let SUDO_ASKPASS=1` regression from the brief is rejected. `: ${SUDO_ASKPASS:=/x}` and `for SUDO_PROMPT in x; do :; done` give `mutating`. These are walker (#196) territory. A human should decide whether this bundle's "v2 regressions with no `variable_assignment` node" claim covers them or a follow-up issue does.
- [ ] **High** ("a privileged step is classed lower"). `targets/ubuntu-26.04/commands.toml:75-76`: the sudo-family rows leave out the names the target actually ships. The target's sudo is sudo-rs (`targets/ubuntu-26.04/target.toml:32`), and the project's own list of privilege programs includes `sudo-rs`, `sudo.ws` and `sudoedit-rs` (`src/nl_shell/failure_classes.py:98`). None of them has a row, so each is an opaque command, and decision A does not catch it either, because it only looks up names that *have* rows. Who controls it: the model, through a proposal. Results seen:
- [ ] **High** (breaks the "What must hold" rule at `.oss-scanner/threat_model.md:121-124`: the gate rejects overrides of `SUDO_PROMPT` "also through … `getopts`"). `targets/ubuntu-26.04/commands.toml:697-704`: the `getopts` row is `raw = true` and takes the variable from `operand = 1`, so `--` counts as an operand. `getopts -- x SUDO_PROMPT` as a proposal gives `mutating`, not rejected; `getopts x SUDO_PROMPT` is rejected. Bash 5.3.9 accepts the `--` and does assign the variable: `bash -c 'set -- -x; getopts -- x SUDO_PROMPT; echo "$SUDO_PROMPT"'` prints `x`. Changing `SUDO_PROMPT` is the step that would stop password passthrough from starting. Fix: drop `raw` so `--` is handled (`end_of_options` is on by default), or treat any `--` before the name operand as "argv cannot be read". Add the `--` case to the test. Other `raw` rows (`source`/`.`, `alias`/`unset`/…, `let`) are fine: there a stray `--` only makes the result stricter.
- [ ] **High by the scale, though it meets the letter of spec §4.** `src/nl_shell/gate/rules.py:554-557`: when a row's inner command word is not a literal (`find -exec {}`, `xargs -I% %`), the engine raises to `destructive` but never runs decision A over the row's literal arguments. `_decision_a` is called only on the "unparsed" paths (`rules.py:529`, `:536`). Result: `find /usr/bin -name sudo -exec {} -i \;` (which really runs `/usr/bin/sudo -i`) gives `destructive`, not rejected, while the same words under an opaque command, `foo /usr/bin -name sudo -exec {} -i \;`, give `privileged`, rejected. A command with a row is treated more loosely than one with no row. Fix: when `unreadable_inner` fires, also call `_decision_a(state, acc, args)`. This only raises classes, so it stays compatible within v1. Add the test case above.
- [ ] **Below High: the class is right (`privileged`, always confirmed), but a §5 rejection is missed.** `targets/ubuntu-26.04/commands.toml:540-542`: the bash row's `opens-shell` fires only with no operands and no `-c`. Bash also runs interactively with `-s` plus operands when stdin is a terminal, and `bash /dev/stdin` reads the terminal too (`rules.py:645-646` returns without marking a shell). So these root shells, reached through a proposal, are not rejected:
- [x] **The tracker record is missing, so the problem statement can't be checked against the thread.** The cwd has `brief.md` and `dependency-state.json` only. There is no `notes.json` and no `sources/`. I could not compare the stated defect, the "decisions A–C" or the "v2 regressions" list with any maintainer comment. The brief cites `iteration-v2/check-advisory-adversary.md` as the source of the regression cases, but that file is not in the bundle or under `$PDCA_TARGET`, so none of those cases trace to the record. A human should confirm that the thread asks for this engine and these decisions.
- [x] **The prerequisite is not merged, and the base branch does not have the code the brief edits.** `dependency-state.json` lists `"196": {"declared": "Depends on", "exists": true, "state": "PLANNED"}`. On `eduralph/nl-shell@main` (`$PDCA_TARGET`) there is no `src/nl_shell/gate/` package, no `gate/rules.py` stub, no `tests/test_gate*`, and no `targets/ubuntu-26.04/gate-vectors.toml`. `targets/ubuntu-26.04/` holds only `target.toml`, `sensitive.toml` and `prompts/`. The Reproduction ("with child-1 merged, `classify("rm -rf build")` gives `mutating`") and the red leg ("leaving child-1's stub") both need code that is not on the target. The bundle should either wait for #196 to land or be declared `Stacks on: 196` with #196's branch as its base. As written, Do starts on `main` with nothing to replace.
- [x] **Decision C is used but never defined, so its cases can't be verified.** The goal says "Write … decisions A–C into the spec", but only A and B get a definition. C shows up only by reference, and the references disagree. The work-budget case says the result is "never below `mutating` (decision C if the budget runs out)". The ten-nested-`env` case says it is "`privileged` and rejected (through the inner command or decision C)". The missing-`commands.toml` case says only "fails closed (decision C)". Is the outcome `mutating`, `destructive` or rejected? What is its reason string? Without those, the budget, missing-file and invalid-file cases have no expected value.
- [x] **The falsifiability rule contradicts itself and fails for some cases.** (a) "Every case asserts … that the reason is not 'could not class'" can't hold for the cases that are supposed to end in decision C (missing or invalid `commands.toml`, budget exhaustion, the ten-`env` case "through … decision C"). Presumably C's reason is something like "could not class", though C has no defined reason (finding above). (b) Several cases expect exactly what the stub already returns, so they pass on the red leg. The Decision A cases (rows 8, 10, 11, 27, `tar --to-command=sh -xf a.tar`, `ssh -o ProxyCommand=sh h`) are specified as "`mutating` 'not allowlisted'". That is the stub's output by the brief's own words ("every command is `mutating` / 'not allowlisted'"). `bash -c 'true'` "is not raised by decision B" also passes on the stub. So "stub results … fail every case" is false. Either these cases go into a separate negative or regression group, or they need an assertion the stub can't meet.
- [x] **Scope: this is several logical changes, not one fix.** "Scope (one logical fix)" covers:
- [x] **The brief's `command` exception is narrower than the spec it says it implements.** The brief has "`command` (but not `command -v`)". Spec §3 (`v1.md:101`) says "`command` (except `command -v`/`-V`)". As written, the brief would class `command -V` as `session-altering`, which also conflicts with "raises only … per spec". The brief should say `-v`/`-V`.
- [x] **"Fixed load location" misstates the root, and its test can't cover the claim.** The brief calls it "the package's own `targets/<id>/` folder". `src/nl_shell/targets.py:27-28` says `TARGETS_ROOT = Path(__file__).resolve().parents[2] / "targets"` with the comment "Not packaged yet (#48, #50)". That is the repository checkout, not the package. The claim "No env variable, cwd, `$HOME`, config or session value can point it elsewhere" is universal, but the test samples only one cwd file and "environment variables naming another file". The criterion should name the exact variables tested, or be stated as "the loader takes no path parameter other than `TARGETS_ROOT`", which a reviewer can check at `path:line`. The other citations resolve: `targets.py:153` (the `is_relative_to` refusal), threat model `:54` (code running as the user is out of scope), `:296`/`:299`/`:303`, and `failure_classes.py:199` `is_privileged`.
- [x] **The work-budget criterion is a wall-clock assertion.** "Classifies in under one second" depends on the host, and so does the "v2 took 5.3 s" baseline. A CI or sandbox host under load can flip it. A deterministic budget measure would be more stable: work units or nodes visited, asserted below a bound, plus a loose timeout as a backstop.
- [x] **Decision A's argument-word rule has a false-positive cost that the brief doesn't address.** "An argument word naming an `elevates` row ⇒ `privileged` and a proposal rejected" applies to any command with no row and no allowlist entry. For example, `make sudo-check` doesn't qualify, but `foo sudo` (an opaque tool taking `sudo` as a plain operand such as a search term or package name) is rejected outright as a model proposal. The brief gives no failure mode for legitimate operands. A human should accept this trade-off explicitly at sign-off, since it adds a rejection rule beyond §5.
- [x] size backstop — this slice is behaving oversized: patch is 126 KB (threshold 100 KB). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: iterated-to-Do
- Iteration delta (if iterating): Human overrode the size backstop: keep this as one bundle, no split. Design and plan-review answers are accepted; rebuild to close these confirmed bypasses (each needs a full-pipeline regression case in tests/test_gate_commands.py, as a proposal where the finding concerns rejection): - sudo family is missing the names shipped on Ubuntu 26.04: add sudo-rs, sudo.ws, sudoedit-rs to the sudo/sudoedit row and su-rs to the su row (cases: `sudo-rs -i`, `sudo.ws -i`, `su-rs`, `/usr/bin/sudo-rs -i`, `echo pw | sudo-rs -S true`, `foo sudo-rs` via decision A, `sudoedit-rs /etc/shadow`). - `env -S` text uses env's split-string syntax, not bash: `env -S 'sudo\_-i'` must be rejected and `env -S 'rm\_-rf\_/'` at least destructive (treat `\_`, `${` and other env-only escapes as unreadable text under decision B, or translate the string to bash words before classing it). - `getopts -- x SUDO_PROMPT` must be rejected: the raw getopts row counts `--` as an operand. - Non-literal inner command (`find -exec {}`, `xargs -I% %`): also run decision A over the row's literal args, so `find /usr/bin -name sudo -exec {} -i \;` is privileged and rejected. - Root-shell rejection gaps: `sudo bash -s x`, `sudo bash -is x`, `sudo dash -s x`, `sudo env bash -s x`, `pkexec bash -s x`, `sudo bash /dev/stdin` (opens-shell on -s; mark opens_shell when stdin is the terminal), plus `sudo chroot /` and `sudo unshare` (opens-shell when no command is given). - `mapfile`/`readarray -C '<text>'`: add a runs-text effect (in_shell) on -C. - `wait -p NAME`: add a wait row with sets-variable from option -p (`wait -p SUDO_PROMPT` rejected). - `enable -f x.so`: runs-file-as-code on -f (at least destructive); split enable out of the shared raw row. Not in this rebuild unless the human says otherwise: interpreters python3/perl/busybox (left for #198) and assignments with no simple command such as `(( X=1 ))` and `for X in` (walker, #196).
- By / date: Eduard Ralph / 2026-10-24

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 9 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

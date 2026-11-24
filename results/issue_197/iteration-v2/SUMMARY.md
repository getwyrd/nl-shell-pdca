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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (248 of 418 failed), green with it
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

Review the data-driven AST policy command engine, including wrapper recursion, privilege rejection, destructive effects, variable assignments, and fail-closed decisions A–C.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The command grammar, fixed effects, conservative defaults, and root-shell rejection have explicit acceptance contracts; target docs/design/specs/policy-gate/v1.md:131 and :194. |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence demonstrates the stub misclassifies sudo as mutating and reports 248 failures out of 418 with production changes reverted; gate-logs/C4-verify.log:19 and :65. |
| C3 Change | PASS | Reviewed changes address the specified command engine and exposed walker integration cases; command semantics remain target data interpreted by generic handlers; target src/nl_shell/gate/rules.py:455 and targets/ubuntu-26.04/commands.toml:77. |
| C4 Verification (red→green) | PASS | Captured actual pytest execution shows 418 passing post-fix tests and 248 failing pre-fix tests, without setup/collection errors; gate-logs/C4-verify.log:10. Local reproduction is unavailable because pytest and tree_sitter are absent. |
| C5 Causal adequacy | PASS | Command meaning replaces the stub at the classification boundary, and nested work shares a bounded budget; no added capability probe papers over a load-time cause; target src/nl_shell/gate/rules.py:214 and :251. |
| T1 Structure | PASS | Target-data loading, argv interpretation, effect dispatch, and shell walking have separate responsibilities; target src/nl_shell/gate/commands.py:1 and src/nl_shell/gate/rules.py:455. |
| T2 Shape | PASS | Independent AST syntax checks and TOML parsing passed for the gate modules and 49 command rows; the threat-model change is present, matching the captured touch scanner; target targets/ubuntu-26.04/commands.toml:77; gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | Frozen full-suite output records 1519 passed, 1 skipped, and one forkpty deprecation warning, with exit zero; gate-logs/T3-suite.log:10. This is captured gate evidence, not an independent local suite run. |
| T4 Contribution | N/A | Contribution artifacts are drafted after Check; the substantive contribution audit is required again at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm prior art by every affected file path across merged history and closed/rejected work before accepting duplication risk — the provided target has only one synthetic base commit and no closed-work evidence; target .git/HEAD:1; affected paths are listed in patch.diff. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the conservative false-positive cost of decision A and the class-raising command policy for intended use — passing classifier tests cannot decide whether these rejection defaults fit users; target docs/design/specs/policy-gate/v1.md:174 and :310. |

Evidence limits: attempted `python -m pytest -q tests/test_gate_commands.py tests/test_policy_gate.py` in the target failed because `python` is unavailable; `python3 -m pytest` failed because pytest is absent, and importing tree_sitter failed. Consequently no stash/red/pop/green sequence was performed. The frozen C4 and T3 logs contain actual successful test execution, rather than code-read or shim evidence, so the review host's missing tools do not establish an unmet dependency in those recorded runs. Instance-scoped gate wrappers were assessed through their supplied logs. The target is readable and contains the patch; no stale-target caveat was needed.

No grounded implementation defect was identified. No INTEGRATION.md was present in the supplied target, so no additional enumerated human-only items could be inspected. The prior-art limitation above remains a human decision rather than an inferred patch defect.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue #197 (command engine)

**Evidence.** I re-ran the bundle tests on the patched target (`tests/test_gate_commands.py tests/test_policy_gate.py`: 418 passed). The red leg in `gate-logs/C4-verify.log` (248 of 418 failed with `rules.py`/`commands.toml` reverted) fits the brief's design: cases are inline, go through the public `nl_shell.gate.classify`, and assert class plus reason. I did not find a test that is true by construction or one that runs a copy of the production code. I also could not break any of the carry-forward bypasses from iteration 1: sudo-rs/sudo.ws/su-rs, `env -S` with `\_`/`\t`/`\c`, `getopts -- x SUDO_PROMPT`, `wait -p`, `mapfile -C`, `enable -f`, `sudo bash -s x`, `sudo chroot /`, and `find -exec {}` with decision A. Roughly 150 wrapper and option forms of `sudo -i` (`nice -5`, `timeout -k1`, `stdbuf -oL`, `flock -c`, `script -qc`, `env --chdir`, `xargs -o`, `watch -x`, …) were all rejected. The two bypasses below are real: I checked both with bash 5.3.

- NEEDS-HUMAN [impl] — `declare -i` / `typeset -i` / `local -i` run code from a quoted literal, and the gate does not see it. `targets/ubuntu-26.04/commands.toml:665-680`: the declare row lists `-i` as a plain flag and treats the value as data. With `-i`, bash evaluates the value as arithmetic: it expands array subscripts and assigns embedded names. Failing cases: `declare -i x='a[$(rm -rf ~)]'` is classed `session-altering` (I checked that bash runs the `$(…)`). It should be at least `destructive`, "runs code the gate cannot read". `typeset -i x='a[$(sudo -i)]'` comes out `session-altering`, not rejected. `declare -i x=SUDO_PROMPT=1` is not rejected, though bash sets `SUDO_PROMPT=1`, so the §5 SUDO_PROMPT/SUDO_ASKPASS rule is bypassed. The `let` row already handles this exact case (`src/nl_shell/gate/rules.py:786-795`, `source == "arithmetic"`), so the fix is to apply that arithmetic effect to the value of each assignment when `-i` is set. Add the three cases above as proposals in `tests/test_gate_commands.py`.
- NEEDS-HUMAN [impl] — `unset` runs a subscript expansion, and the gate does not see it. `targets/ubuntu-26.04/commands.toml:629-634` puts `unset` in the shared `raw = true` row, so its operands never reach `_target` (`src/nl_shell/gate/rules.py:722-730`). That function already raises `read`/`printf -v`/`declare`/`wait -p`/`getopts`/`mapfile` names that hold `x[$(…)]`. Failing case: `a=(1); unset -v 'a[$(rm -rf ~)]'` is classed `session-altering`, but bash runs the substitution (checked: `RAN2`). `unset 'x[$(sudo -i)]'` as a proposal is not rejected. Fix: give `unset` its own row whose operands go through the same subscript check.
- NEEDS-HUMAN [impl] — The spec's "exports of SUDO_PROMPT/SUDO_ASKPASS" rule is not enforced. `docs/design/specs/policy-gate/v1.md:201` rejects "assignments **or exports** of `SUDO_PROMPT` or `SUDO_ASKPASS`". But `export SUDO_PROMPT` is classed `session-altering` and not rejected. `declare -x SUDO_ASKPASS`, `typeset -x SUDO_PROMPT` and `readonly -x SUDO_PROMPT` are only `mutating`: they are not rejected and not even `session-altering`, because the declare/readonly `state` effect only fires on words with `=` (`commands.toml:677-680`, `:690-693`). An export with no value moves a value already set in the shell into sudo's environment. The `export`/`declare -x` row should run the name check on bare operands too.
- NEEDS-HUMAN [human] — Stored code is only raised to `session-altering`, never classed for what it will run. `trap 'rm -rf ~' EXIT` and `trap -- 'sudo -i' EXIT` get a `runs-text` treatment: they are `destructive` and rejected. But `alias ls='sudo -i'`, `complete -C 'rm -rf ~' x`, `bind -x '"\C-x":rm -rf ~'` and `export PROMPT_COMMAND='sudo -i'` stay `session-altering` and are not rejected (`commands.toml:629-634`). Once #198 allowlists `ls`, the alias makes a later `ls` proposal open a root shell. Whether alias/complete/bind/PROMPT_COMMAND values should be classed like trap text, or left to the confirm prompt and the shell-state check (`.oss-scanner/threat_model.md:241`), is a scope decision. The trap/alias split is not explained in the spec.
- Out of this diff's rows, for the record only: `test -v 'a[$(rm -rf ~)]'` (bash runs it, checked) and `x=sudo; $x -i` stay `mutating`. `test` has no row and the command-word rule is child-1's, so I am not filing them against this patch.
- Cosmetic, not filed: `sudoedit /etc/shadow` reports "command word is a path outside the system directories: /etc/shadow". The sudo row's `runs-command-at operand 0` (`commands.toml:106-109`) is shared with `sudoedit`, which takes files, not a command. The class (`privileged`) is right. `source -- f` reports "runs the file --".

The reviewer's pass is justified for the cases the brief lists. It is not justified as a claim that the `sets-variable`/runs-code effects are complete over the builtins: the declare `-i` and `unset` gaps above are the same kind of bypass the builder already closed for `let`, `read` and `printf -v`.

<!-- pdca:leaf-complete -->

### Advisory — security-review

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

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T5 Judgment — Confirm prior art by every affected file path across merged history and closed/rejected work before accepting duplication risk — the provided target has only one synthetic base commit and no closed-work evidence; target .git/HEAD:1; affected paths are listed in patch.diff.
- [ ] Validation — fitness-to-purpose — Accept the conservative false-positive cost of decision A and the class-raising command policy for intended use — passing classifier tests cannot decide whether these rejection defaults fit users; target docs/design/specs/policy-gate/v1.md:174 and :310.
- [ ] `declare -i` / `typeset -i` / `local -i` run code from a quoted literal, and the gate does not see it. `targets/ubuntu-26.04/commands.toml:665-680`: the declare row lists `-i` as a plain flag and treats the value as data. With `-i`, bash evaluates the value as arithmetic: it expands array subscripts and assigns embedded names. Failing cases: `declare -i x='a[$(rm -rf ~)]'` is classed `session-altering` (I checked that bash runs the `$(…)`). It should be at least `destructive`, "runs code the gate cannot read". `typeset -i x='a[$(sudo -i)]'` comes out `session-altering`, not rejected. `declare -i x=SUDO_PROMPT=1` is not rejected, though bash sets `SUDO_PROMPT=1`, so the §5 SUDO_PROMPT/SUDO_ASKPASS rule is bypassed. The `let` row already handles this exact case (`src/nl_shell/gate/rules.py:786-795`, `source == "arithmetic"`), so the fix is to apply that arithmetic effect to the value of each assignment when `-i` is set. Add the three cases above as proposals in `tests/test_gate_commands.py`.
- [ ] `unset` runs a subscript expansion, and the gate does not see it. `targets/ubuntu-26.04/commands.toml:629-634` puts `unset` in the shared `raw = true` row, so its operands never reach `_target` (`src/nl_shell/gate/rules.py:722-730`). That function already raises `read`/`printf -v`/`declare`/`wait -p`/`getopts`/`mapfile` names that hold `x[$(…)]`. Failing case: `a=(1); unset -v 'a[$(rm -rf ~)]'` is classed `session-altering`, but bash runs the substitution (checked: `RAN2`). `unset 'x[$(sudo -i)]'` as a proposal is not rejected. Fix: give `unset` its own row whose operands go through the same subscript check.
- [ ] The spec's "exports of SUDO_PROMPT/SUDO_ASKPASS" rule is not enforced. `docs/design/specs/policy-gate/v1.md:201` rejects "assignments **or exports** of `SUDO_PROMPT` or `SUDO_ASKPASS`". But `export SUDO_PROMPT` is classed `session-altering` and not rejected. `declare -x SUDO_ASKPASS`, `typeset -x SUDO_PROMPT` and `readonly -x SUDO_PROMPT` are only `mutating`: they are not rejected and not even `session-altering`, because the declare/readonly `state` effect only fires on words with `=` (`commands.toml:677-680`, `:690-693`). An export with no value moves a value already set in the shell into sudo's environment. The `export`/`declare -x` row should run the name check on bare operands too.
- [ ] Stored code is only raised to `session-altering`, never classed for what it will run. `trap 'rm -rf ~' EXIT` and `trap -- 'sudo -i' EXIT` get a `runs-text` treatment: they are `destructive` and rejected. But `alias ls='sudo -i'`, `complete -C 'rm -rf ~' x`, `bind -x '"\C-x":rm -rf ~'` and `export PROMPT_COMMAND='sudo -i'` stay `session-altering` and are not rejected (`commands.toml:629-634`). Once #198 allowlists `ls`, the alias makes a later `ls` proposal open a root shell. Whether alias/complete/bind/PROMPT_COMMAND values should be classed like trap text, or left to the confirm prompt and the shell-state check (`.oss-scanner/threat_model.md:241`), is a scope decision. The trap/alias split is not explained in the spec.
- [ ] **High** (privileged step classed lower; proposal opening a root shell not rejected), `targets/ubuntu-26.04/commands.toml:537-540` and `src/nl_shell/gate/rules.py:623-627`. The words after a `-c` text become the script's `$0`, `$1`, … and are never classed. The bash/sh/dash row's `runs-text` uses `operand = 0`, so `_text_words` returns only the text word. The words after it don't go through recursion, and they don't go through decision A either, because `bash` has a row. The text then has a non-literal command word, which is only `mutating`. Who controls it: the model's proposal. Reproducers (all proposals):
- [ ] **High** (same class of break), `src/nl_shell/gate/rules.py:78` and `:653-660`. Decision A over `env -S` text misses a name that comes right after `\_`. `_PIECE_SPLIT` keeps `_` as a word character, so `\_sudo` becomes the piece `_sudo`, which names no row. env reads `\_` as a space, so the command runs `sudo -i`. Reproducers (proposals):
- [ ] **High**, `targets/ubuntu-26.04/commands.toml`, which has no `sg` or `newgrp` row. `sg GROUP -c 'TEXT'` and `sg GROUP 'TEXT'` run the text through `/bin/sh -c`. With no row, decision A only checks whole words, and `'sudo -i'` is one word. Reproducer: proposal `sg adm -c 'sudo -i'` gives `mutating`, not rejected. Run with the user's own primary group, it needs no group password and opens a root shell. I believe `sg` ships in Ubuntu's `login` package, but I have not checked this on the reference VM. The fix is a row with `runs-text`. In the same group: `at now <<<'sudo rm -rf /'` and `echo 'sudo rm -rf /' | at now` give `mutating`. `at` runs its stdin as code, so it needs a `runs-stdin-as-code` row, if `at` is installed on the target.
- [ ] **High if counted as lowering a class; within the letter of agreed decision A**, `src/nl_shell/gate/rules.py:225-249`. Decision A matches only a whole argument word, after quote removal, against a row name. An opaque command that takes command text as one quoted word is therefore only `mutating`, not rejected:
- [ ] **The tracker record is missing, so the problem statement can't be checked against the thread.** The cwd has `brief.md` and `dependency-state.json` only. There is no `notes.json` and no `sources/`. I could not compare the stated defect, the "decisions A–C" or the "v2 regressions" list with any maintainer comment. The brief cites `iteration-v2/check-advisory-adversary.md` as the source of the regression cases, but that file is not in the bundle or under `$PDCA_TARGET`, so none of those cases trace to the record. A human should confirm that the thread asks for this engine and these decisions.
- [ ] **The prerequisite is not merged, and the base branch does not have the code the brief edits.** `dependency-state.json` lists `"196": {"declared": "Depends on", "exists": true, "state": "PLANNED"}`. On `eduralph/nl-shell@main` (`$PDCA_TARGET`) there is no `src/nl_shell/gate/` package, no `gate/rules.py` stub, no `tests/test_gate*`, and no `targets/ubuntu-26.04/gate-vectors.toml`. `targets/ubuntu-26.04/` holds only `target.toml`, `sensitive.toml` and `prompts/`. The Reproduction ("with child-1 merged, `classify("rm -rf build")` gives `mutating`") and the red leg ("leaving child-1's stub") both need code that is not on the target. The bundle should either wait for #196 to land or be declared `Stacks on: 196` with #196's branch as its base. As written, Do starts on `main` with nothing to replace.
- [ ] **Decision C is used but never defined, so its cases can't be verified.** The goal says "Write … decisions A–C into the spec", but only A and B get a definition. C shows up only by reference, and the references disagree. The work-budget case says the result is "never below `mutating` (decision C if the budget runs out)". The ten-nested-`env` case says it is "`privileged` and rejected (through the inner command or decision C)". The missing-`commands.toml` case says only "fails closed (decision C)". Is the outcome `mutating`, `destructive` or rejected? What is its reason string? Without those, the budget, missing-file and invalid-file cases have no expected value.
- [ ] **The falsifiability rule contradicts itself and fails for some cases.** (a) "Every case asserts … that the reason is not 'could not class'" can't hold for the cases that are supposed to end in decision C (missing or invalid `commands.toml`, budget exhaustion, the ten-`env` case "through … decision C"). Presumably C's reason is something like "could not class", though C has no defined reason (finding above). (b) Several cases expect exactly what the stub already returns, so they pass on the red leg. The Decision A cases (rows 8, 10, 11, 27, `tar --to-command=sh -xf a.tar`, `ssh -o ProxyCommand=sh h`) are specified as "`mutating` 'not allowlisted'". That is the stub's output by the brief's own words ("every command is `mutating` / 'not allowlisted'"). `bash -c 'true'` "is not raised by decision B" also passes on the stub. So "stub results … fail every case" is false. Either these cases go into a separate negative or regression group, or they need an assertion the stub can't meet.
- [ ] **Scope: this is several logical changes, not one fix.** "Scope (one logical fix)" covers:
- [ ] **The brief's `command` exception is narrower than the spec it says it implements.** The brief has "`command` (but not `command -v`)". Spec §3 (`v1.md:101`) says "`command` (except `command -v`/`-V`)". As written, the brief would class `command -V` as `session-altering`, which also conflicts with "raises only … per spec". The brief should say `-v`/`-V`.
- [ ] **"Fixed load location" misstates the root, and its test can't cover the claim.** The brief calls it "the package's own `targets/<id>/` folder". `src/nl_shell/targets.py:27-28` says `TARGETS_ROOT = Path(__file__).resolve().parents[2] / "targets"` with the comment "Not packaged yet (#48, #50)". That is the repository checkout, not the package. The claim "No env variable, cwd, `$HOME`, config or session value can point it elsewhere" is universal, but the test samples only one cwd file and "environment variables naming another file". The criterion should name the exact variables tested, or be stated as "the loader takes no path parameter other than `TARGETS_ROOT`", which a reviewer can check at `path:line`. The other citations resolve: `targets.py:153` (the `is_relative_to` refusal), threat model `:54` (code running as the user is out of scope), `:296`/`:299`/`:303`, and `failure_classes.py:199` `is_privileged`.
- [ ] **The work-budget criterion is a wall-clock assertion.** "Classifies in under one second" depends on the host, and so does the "v2 took 5.3 s" baseline. A CI or sandbox host under load can flip it. A deterministic budget measure would be more stable: work units or nodes visited, asserted below a bound, plus a loose timeout as a backstop.
- [ ] **Decision A's argument-word rule has a false-positive cost that the brief doesn't address.** "An argument word naming an `elevates` row ⇒ `privileged` and a proposal rejected" applies to any command with no row and no allowlist entry. For example, `make sudo-check` doesn't qualify, but `foo sudo` (an opaque tool taking `sudo` as a plain operand such as a search term or package name) is rejected outright as a model proposal. The brief gives no failure mode for legitimate operands. A human should accept this trade-off explicitly at sign-off, since it adds a rejection rule beyond §5.
- [ ] size backstop — this slice is behaving oversized: patch is 135 KB (threshold 100 KB). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.

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
- Iteration delta (if iterating): Rejected: slice is oversized (135 KB patch, 100 KB threshold) after two build attempts, and the adversary/security reviews found eight gate bypasses (three High: words after `-c` text unclassed, `env -S '\_sudo'`, missing `sg`/`at` rows; plus `declare -i`, `unset` subscripts, bare `export SUDO_PROMPT`, stored code in alias/complete/bind/PROMPT_COMMAND, quoted command text to opaque tools). No split is prescribed — the human will rethink the slicing at Plan.
- By / date: Eduard Ralph / 2026-10-26

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 9 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

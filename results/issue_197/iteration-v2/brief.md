- **Slug:** ast-policy-gate-command-engine
- **Kind:** enhancement
- **Defect / goal:** After child-1 the gate's command layer is a stub: every command is
  `mutating` / "not allowlisted", so `rm -rf build` is not `destructive`, `sudo apt
  update` is not `privileged`, and none of the sudo rejections fire. Add the **command
  layer**: `targets/ubuntu-26.04/commands.toml` (format, loader, rows) and one generic
  engine in `gate/rules.py` that interprets the rows. Each row gives a command's argv
  grammar (flags; value-taking options in short, attached and long `=` forms;
  end-of-options; where an inner command starts) and its effects from one fixed set:
  `runs-command-at`, `runs-text`, `runs-stdin-as-code`, `runs-file-as-code`,
  `sets-variable`, `elevates`, `destroys` (with a condition), `reads-terminal`,
  `opens-shell`. Wrappers, sudo-family commands, destructive commands and builtins that
  assign variables are data rows, not code paths. Enforce decision A (opaque command:
  at least `mutating` "not allowlisted"; an argument word naming an `elevates` row ⇒
  `privileged` and a proposal rejected; naming a `destroys` row ⇒ at least
  `destructive`) and decision B (code the gate cannot read ⇒ at least `destructive`,
  reason "runs code the gate cannot read"; literal text is classed recursively within
  the budget). Write the command table and decisions A–C into the spec and the threat
  model.
  The decisions, as agreed with the human in the #189 split plan
  (`results/issue_189/brief.md:99-112` in the pdca checkout): **A** — opaque command (no
  `commands.toml` row and not allowlisted): at least `mutating`, reason "not
  allowlisted"; if any argument word, after quote removal, names a command whose row has
  `elevates`, the command is `privileged` and a model proposal is rejected; if one names a
  row with `destroys`, at least `destructive`. **B** — `runs-stdin-as-code` fed by a pipe
  or file, `runs-text` with non-literal text, `runs-file-as-code`: at least `destructive`,
  reason "runs code the gate cannot read"; literal text is classed recursively within the
  budget. **C** — gate failure (unhandled node kind, work budget exceeded, a missing or
  invalid `commands.toml`, any internal error): `privileged`, rejected, reason "could not
  class" (implemented by #196; this child routes its own failures to it). Bundle names:
  "child-1" = #196, "child-2" = #197 (this), "child-3" = #198.
- **Success criterion:** `tests/test_gate_commands.py` passes, covering:
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
- **Falsifiability:** plain pytest on the host. On the red leg C4 reverts `rules.py`,
  `commands.toml` and any new `gate-vectors.toml` rows, leaving #196's stub. The test
  lists its cases inline (it does not depend on new vector rows), so stub results
  (`mutating` "not allowlisted") fail every case except the floor group, which is
  named as such. Every case asserts class, a reason substring, and that the reason is not
  "could not class" — otherwise a rejected case could pass on the red leg through
  decision C. The exceptions are the missing/invalid-`commands.toml` cases, which assert
  "could not class", and the ten-`env` and budget cases, which accept either the
  engine's reason or "could not class" but never a class below the stated one. Import `nl_shell.gate` inside test
  functions.
- **Invariant to restore:** Meaning is closed-world: a command gets a meaning only from
  reviewed data (`commands.toml`, later the allowlist); every other command, and any code
  the gate cannot read, gets an explicit fail-closed default, never a silent `mutating`.
  Sources: ADR-0013, ADR-0015; `policy-gate/v1` §3–§5 and Versioning ("raising a class is
  a compatible change within v1 but MUST be reviewed by a human"); threat model rows
  `.oss-scanner/threat_model.md:296` and `:303`.
- **Repo + branch target:** eduralph/nl-shell @ main
- **Milestone / ADRs:** M0 — REPL prototype. ADR-0013, ADR-0015, ADR-0023.
- **Reproduction:** with #196 merged, `classify("rm -rf build")` gives `mutating`,
  reason "not allowlisted", instead of `destructive`; `classify("sudo -S true")` is not
  rejected.
- **Surfaces:** data
- **Scope (one logical fix) / out of scope:** In scope: `gate/rules.py` (the engine,
  replacing child-1's stub); a `commands.toml` loader in the style of
  `src/nl_shell/targets.py:145-247`; `targets/ubuntu-26.04/commands.toml`;
  `gate-vectors.toml` rows for this child; spec `docs/design/specs/policy-gate/v1.md`
  text for the command table and decisions A, B, C, plus #196's stricter fd wording ("a
  descriptor the gate cannot prove is below 3") (raises classes only); the matching
  threat-model text; `tests/test_gate_commands.py`. Out of scope: the walker and stdin
  context (child-1 — fix there only if a case here exposes a walker bug, and say so in
  build notes); the allowlist, the terminal-read rule and the here-doc exemption
  (child-3); §7 (#192); §8 and the filesystem-state rule "`>` truncates an existing file
  outside the cwd" (#190); mixed-script words (#191); confirm UI (#74); REPL wiring
  (#78); sudo passthrough (#13). Do not reuse `src/nl_shell/failure_classes.py:199`
  `is_privileged`.
- **External dependencies:** `tree-sitter-bash`
- **Test file:** tests/test_gate_commands.py
- **Difficulty:** high
- **Citations expected:** Do must cite path:line on the target branch for every change.
  Peers to mirror: `src/nl_shell/targets.py:145-247`.
- **Prior-art check (triage cycles):** v2's `rules.py` hand-coded each rule; its review
  findings (`iteration-v2/check-advisory-adversary.md`) are the regression cases above.
  Do not port its code paths; express each rule as a row.
- **Impact & compatibility:** no new dependency. Spec gains the command table and the
  opaque-command / unreadable-code / gate-failure rules (raises only; compatible within
  v1; human-reviewed at sign-off). The spec text states that `commands.toml` rows are
  reviewed like allowlist entries: removing a row or an effect can lower a class, so it
  is a v2 change (spec Versioning).
- **Disposition hint:** new-feature
- **Depends on:** 196
- **Ordering note:** after #196 (wave dependency). `Depends on` puts this bundle in a later
  wave than #196 and Do builds on that wave's folded branch (`$PDCA_VERIFY_BASE`), which
  holds #196's accepted patch. `Repo + branch target: main` is where the result lands, not
  the build base. If #196 is not accepted, the flow does not build this bundle.

Plan-review response: findings taken except the split. Decisions A–C are stated inline
with their source, and C's outcome and reason are defined. The cases that equal the stub's
output now sit in a named floor group outside the red-leg claim. The decision-C cases have
explicit reason rules. `command -v`/`-V` matches the spec. The load-location rule is now
something a reviewer can check in code (no path argument, `TARGETS_ROOT` only), and the
test names the variables it sets. The budget is counted in work units, with only a loose
timeout as backstop. The PLANNED prerequisite is handled by the wave fold (Ordering note).
The scope stays one bundle: the engine, A, B and C came out of the #189 split agreed with
the human, and this pass adds no bundles. Splitting A/B out is the human's call at
sign-off, as is decision A's false-positive cost (`foo sudo` rejected as a proposal), which
Do records in build-notes as an accepted trade-off.

## Iteration 1 — carry-forward (from the previous attempt)
- Sign-off rationale: Human overrode the size backstop: keep this as one bundle, no split. Design and plan-review answers are accepted; rebuild to close these confirmed bypasses (each needs a full-pipeline regression case in tests/test_gate_commands.py, as a proposal where the finding concerns rejection): - sudo family is missing the names shipped on Ubuntu 26.04: add sudo-rs, sudo.ws, sudoedit-rs to the sudo/sudoedit row and su-rs to the su row (cases: `sudo-rs -i`, `sudo.ws -i`, `su-rs`, `/usr/bin/sudo-rs -i`, `echo pw | sudo-rs -S true`, `foo sudo-rs` via decision A, `sudoedit-rs /etc/shadow`). - `env -S` text uses env's split-string syntax, not bash: `env -S 'sudo\_-i'` must be rejected and `env -S 'rm\_-rf\_/'` at least destructive (treat `\_`, `${` and other env-only escapes as unreadable text under decision B, or translate the string to bash words before classing it). - `getopts -- x SUDO_PROMPT` must be rejected: the raw getopts row counts `--` as an operand. - Non-literal inner command (`find -exec {}`, `xargs -I% %`): also run decision A over the row's literal args, so `find /usr/bin -name sudo -exec {} -i \;` is privileged and rejected. - Root-shell rejection gaps: `sudo bash -s x`, `sudo bash -is x`, `sudo dash -s x`, `sudo env bash -s x`, `pkexec bash -s x`, `sudo bash /dev/stdin` (opens-shell on -s; mark opens_shell when stdin is the terminal), plus `sudo chroot /` and `sudo unshare` (opens-shell when no command is given). - `mapfile`/`readarray -C '<text>'`: add a runs-text effect (in_shell) on -C. - `wait -p NAME`: add a wait row with sets-variable from option -p (`wait -p SUDO_PROMPT` rejected). - `enable -f x.so`: runs-file-as-code on -f (at least destructive); split enable out of the shared raw row. Not in this rebuild unless the human says otherwise: interpreters python3/perl/busybox (left for #198) and assignments with no simple command such as `(( X=1 ))` and `for X in` (walker, #196).
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Human overrode the size backstop: keep this as one bundle, no split. Design and plan-review answers are accepted; rebuild to close these confirmed bypasses (each needs a full-pipeline regression case in tests/test_gate_commands.py, as a proposal where the finding concerns rejection):
  - sudo family is missing the names shipped on Ubuntu 26.04: add sudo-rs, sudo.ws, sudoedit-rs to the sudo/sudoedit row and su-rs to the su row (cases: `sudo-rs -i`, `sudo.ws -i`, `su-rs`, `/usr/bin/sudo-rs -i`, `echo pw | sudo-rs -S true`, `foo sudo-rs` via decision A, `sudoedit-rs /etc/shadow`).
  - `env -S` text uses env's split-string syntax, not bash: `env -S 'sudo\_-i'` must be rejected and `env -S 'rm\_-rf\_/'` at least destructive (treat `\_`, `${` and other env-only escapes as unreadable text under decision B, or translate the string to bash words before classing it).
  - `getopts -- x SUDO_PROMPT` must be rejected: the raw getopts row counts `--` as an operand.
  - Non-literal inner command (`find -exec {}`, `xargs -I% %`): also run decision A over the row's literal args, so `find /usr/bin -name sudo -exec {} -i \;` is privileged and rejected.
  - Root-shell rejection gaps: `sudo bash -s x`, `sudo bash -is x`, `sudo dash -s x`, `sudo env bash -s x`, `pkexec bash -s x`, `sudo bash /dev/stdin` (opens-shell on -s; mark opens_shell when stdin is the terminal), plus `sudo chroot /` and `sudo unshare` (opens-shell when no command is given).
  - `mapfile`/`readarray -C '<text>'`: add a runs-text effect (in_shell) on -C.
  - `wait -p NAME`: add a wait row with sets-variable from option -p (`wait -p SUDO_PROMPT` rejected).
  - `enable -f x.so`: runs-file-as-code on -f (at least destructive); split enable out of the shared raw row.
  Not in this rebuild unless the human says otherwise: interpreters python3/perl/busybox (left for #198) and assignments with no simple command such as `(( X=1 ))` and `for X in` (walker, #196).
- Full previous attempt preserved in `iteration-v1/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 2 — carry-forward (from the previous attempt)
- Sign-off rationale: Rejected: slice is oversized (135 KB patch, 100 KB threshold) after two build attempts, and the adversary/security reviews found eight gate bypasses (three High: words after `-c` text unclassed, `env -S '\_sudo'`, missing `sg`/`at` rows; plus `declare -i`, `unset` subscripts, bare `export SUDO_PROMPT`, stored code in alias/complete/bind/PROMPT_COMMAND, quoted command text to opaque tools). No split is prescribed — the human will rethink the slicing at Plan.
- Full previous attempt preserved in `iteration-v2/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

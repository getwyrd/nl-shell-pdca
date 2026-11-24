- **Slug:** gate-command-table-engine
- **Kind:** enhancement
- **Defect / goal:** On `main` (`1a1e980`, #196 merged) the gate's command layer is a
  stub: `src/nl_shell/gate/rules.py:26-28` returns `mutating`, "not allowlisted" for every
  simple command. So `rm -rf build` is not `destructive`, `sudo apt update` is not
  `privileged`, `sudo -S true` is not rejected, and none of spec §4–§5's per-command rules
  fire. Add the reviewed data table `targets/ubuntu-26.04/commands.toml` (format, loader,
  rows) and one generic engine in `gate/rules.py` that reads it. Wrappers, the sudo
  family, destructive commands, interpreters and builtins are data rows, not code paths.
  Each row gives the command's argv grammar (flags; value-taking options in short,
  attached and long `=` forms; end-of-options; where an inner command starts) and its
  effects from one fixed set: `runs-command-at`, `runs-text`, `runs-stdin-as-code`,
  `runs-file-as-code`, `stores-code`, `sets-variable`, `elevates`, `destroys` (with a
  condition), `reads-terminal`, `opens-shell`. Do may refine effect names, but the later
  children's rules (text in a named grammar, name operands, stored code) must be
  expressible in the format: every text effect names its grammar (`bash`, `env-split`,
  `arithmetic`, or a named unparsed one such as `python`), and operands/option values
  that are variable names are marked as names.

  **In this child every text effect** (`runs-text`, `runs-stdin-as-code`,
  `runs-file-as-code`, `stores-code`) **is decision B**: at least `destructive`, reason
  "runs code the gate cannot read". No recursion. Inner commands of wrappers
  (`runs-command-at`) are argv, not text, and are classed by the same engine.

  **Decisions** (from #189's split plan, `results/issue_189/iteration-v3/brief.md:99-112`; restated in
  #197's tracker body, `results/issue_197/notes.json`):
  - **A**: an opaque command (no row, no allowlist entry) is at least `mutating`, "not
    allowlisted". If any argument word, after quote removal (including ANSI-C `$'…'`
    decoding), names a row with `elevates`, the command is `privileged` and a proposal is
    rejected. If one names a row with `destroys`, it is at least `destructive`.
    Decision A applies **only** to a command with neither a row nor an allowlist entry
    (#197's tracker body says so). Until #198 lands there is no allowlist, so `man sudo`,
    `which sudo`, `apt show sudo`, `dpkg -L sudo`, `echo su` come out `privileged` here.
    That over-raise is accepted: it is safe, and when #198 allowlists those commands
    their class drops by an allowlist entry, which `v1.md:238-239` counts as a compatible,
    human-reviewed v1 change, not a lowering. Do not add rows here just to avoid it.
  - **Elevation reaches inner commands** (v4 sign-off, option (a) chosen at the re-plan):
    under a row with `elevates`, a proposal is rejected if any later argument word names a
    row that opens a shell or has a text effect (`bash`, `sh`, `python3`, `busybox`, …),
    whatever command sits between (`sudo strace bash`, `sudo setpriv bash`,
    `sudo runuser -u root bash`). Under an `elevates` row, a non-literal word or an
    undeclared option anywhere in the inner argv also rejects a proposal.
  - **C**: a gate failure (unhandled node, work budget used up, missing or invalid
    `commands.toml`, internal error) is `privileged`, rejected, "could not class". #196
    already implements the sink (`src/nl_shell/gate/__init__.py:18-19`, `:48`, `:143`);
    this child sends its own failures there.

  **Classes owned here** (class numbers as in #197's brief):
  1. **Coverage.** Every binary on the target that elevates, or that runs a shell or an
     interpreter, has a row, including every alias name pointing at the same file
     (`sudo-rs`, `sudo.ws`, `sudoedit-rs`, `su-rs` → `/usr/lib/cargo/bin/{sudo,su}`).
     `scripts/harvest_inventory.py` (style of `scripts/gen_unicode_tables.py`) writes
     `targets/ubuntu-26.04/inventory.toml` from this Ubuntu 26.04.1 host:
     setuid/setgid/file-capability binaries in `/usr/bin`, `/usr/sbin`,
     `/usr/lib/cargo/bin`; every name there whose `realpath` matches a listed binary or a
     row's binary; `/etc/shells`; binaries of dpkg packages in sections `shells` and
     `interpreters`; `python3*`, `perl*`, `busybox`, `gdb`. Checked in, reviewed like an
     allowlist change, records the host's `VERSION` line, not run by any test. A row for a
     non-elevating setuid binary (e.g. `passwd`) may just say so.
  2. **No unread argv.** No row skips argv parsing (no `raw = true`). An option a row
     does not declare is at least `destructive`, "option the gate does not know"; on an
     `elevates` row a proposal with it is also rejected. A row may describe only some
     subcommands (`git clean|reset|push`); others get the row's stated default (at least
     `mutating`), so floor rows 8 and 27 stay as the spec says. Named exception: the
     code-running options of the class-7 floor commands (`git` global
     `-c`/`--config-env`/`--exec-path`, `tar --to-command`, `ssh -o`) carry a
     `class-7-gap` marker and give the row's default (`mutating`, "not allowlisted"). The
     loader accepts `class-7-gap` only on options named in the spec's class-7 text. A row
     whose effects do not depend on argv (e.g. `passwd`) may give a fixed class (at least
     `mutating`); decision A still runs over its words. Every `runs-command-at` row
     declares what it does with no command (`chroot`/`unshare` start `$SHELL`) and when
     stdin is the terminal (`bash -s x`, `bash /dev/stdin`). The loader refuses a row that
     leaves either undeclared.
  7. **Real text-runners get rows; the leftover gap is written down.** Rows with their
     text effects for `busybox` (applet = inner command), `python3`, `perl`, `tclsh`,
     `gjs`, `gdb -ex`, `screen`, `script` (no command opens `$SHELL`; `-c` is
     `runs-text` bash), and by name for `sg`/`newgrp` (`runs-text`, sh),
     `at`/`batch` (`runs-stdin-as-code`), `zsh`, `tmux`, `x-terminal-emulator -e`.
     Accepted gap, written into spec and threat model: an unknown command that takes
     command text as one quoted word (`foo 'sudo -i'`), and the code-running options of
     floor rows 8/10/11 (`git -c core.pager=sh`, `tar --to-command=sh`,
     `ssh -o ProxyCommand=sh`). These stay `mutating`, "not allowlisted". Decision A does
     not split quoted words.

  Write the command table, decisions A and C, classes 1, 2, 7 and the class-7 gap into
  the spec (`docs/design/specs/policy-gate/v1.md` §4/§5 and a new §4.1) and the threat
  model (`.oss-scanner/threat_model.md:171-195`, the paragraph that still says "The
  command layer … still stubs"). State in §4.1 that text effects are decision B until
  the text-reading layer lands (child-2). **Spec text owned by this child:** §4/§5 rows,
  the new §4.1 sections for the row format, decisions A and C, classes 1, 2 and 7 and the
  class-7 gap, a one-line "text effects are decision B" placeholder, and Conformance
  row 16 (`v1.md:268`, `$'\x72m' -rf ~`), whose stated reason "(non-literal word)" this
  child makes false: change it to `destructive` (ANSI-C decodes to `rm`) and append the
  matching `gate-vectors.toml` row. In the threat
  model, replace "The command layer … still stubs" (`:194-195`) with what this child
  does. This child's text must **not** claim recursion, decision B′, classes 3–6, or that
  text, stored code or protected-variable spellings are read. Child-2 and child-3 write
  those sections.
- **Success criterion:** `tests/test_gate_commands.py` passes. Every case goes through the
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
- **Falsifiability:** Plain pytest on this host (Ubuntu 26.04.1, bash 5.3.9, `.venv` with
  tree-sitter-bash). C4 (`engine/scripts/run-verify.sh`) reverts `src/`, `targets/`,
  `scripts/` and keeps the test, which restores the stub at `rules.py:26-28` and removes
  `commands.toml`/`inventory.toml`. On the stub `sudo-rs -i`, `sudo chroot /`,
  `rm -rf build`, `sudo -S true` come out `mutating`, not rejected, so every non-floor
  group goes red. The floor group may pass on the stub. Cases are listed inline; read the
  inventory and table inside test functions; import `nl_shell.gate` and any new loader
  module inside test functions (a module-level import of a new API makes the red leg
  UNVERIFIABLE, `run-verify.sh:196`).
- **Invariant to restore:** Meaning is closed-world. A command gets a meaning only from
  reviewed data. An unknown command or undeclared option is never silently `mutating`
  below its stated floor. ADR-0013, ADR-0015; `policy-gate/v1` §1 step 4, §4–§5,
  Versioning (`v1.md:238-239`); threat model "What must hold"
  (`.oss-scanner/threat_model.md:121-125`).
- **Repo + branch target:** eduralph/nl-shell @ main
- **Reproduction:** In `/home/eddie/nl-shell/nl-shell` on `main`:
  `PYTHONPATH=src /home/eddie/nl-shell/nl-shell-pdca/.venv/bin/python3 -c 'from nl_shell.gate import classify; print(classify("rm -rf build"), classify("sudo -S true", origin="proposal"))'`
  gives `mutating`, "not allowlisted", not rejected, for both.
- **Scope (one logical fix) / out of scope:** In scope: `src/nl_shell/gate/rules.py`
  (engine, replacing the stub); a `commands.toml` loader in the style of
  `src/nl_shell/targets.py:145-247`; `targets/ubuntu-26.04/commands.toml` (all rows,
  including text-runner and builtin rows with their text effects, grammar names and name
  markers declared); `targets/ubuntu-26.04/inventory.toml` and
  `scripts/harvest_inventory.py`; `gate-vectors.toml` rows (appended); in
  `src/nl_shell/gate/__init__.py` only passing `origin` to the `rules.classify` call at
  `:196`; ANSI-C `$'…'` decoding **for the command layer only**: a new helper (in `rules.py`,
  or in `parse.py` next to `lex_word`) that decodes `$'…'` from `Word.source` as bash
  does, cutting at `\0`, and is used for row lookup, option parsing under a row, and
  decision A. It counts a word as readable only when ANSI-C quoting is its sole
  non-literal cause (today `$'…'` falls into the "expansion" cause at `:252-253`); an
  undecodable escape stays unreadable. **`lex_word` (`:197`), `make_word` (`:273-275`)
  and `Word.literal` do not change**: they feed every shell-layer rule (redirect targets
  `:315`/`:330`, `_stdin_after` `:595`, declarations `:821-826`, here-string feed
  `:1004`, cd placement and `_may_rewire_stdin` `:1104-1189`), and marking `$'…'` literal
  there would lower verdicts (`ls > $'/etc/x'` from rejected to accepted), which
  `v1.md:241` forbids. So `tests/test_policy_gate.py:517` (`cat $'x'` not literal) stays
  as is;
  `tests/test_policy_gate.py` expectations this child raises (raise only, never lower;
  e.g. `:192` `$'\x72m' -rf ~` goes from `mutating` to `destructive`; the shell layer
  still reports "command word is not a literal"); spec and threat-model text (raises only); `tests/test_gate_commands.py`.
  Out of scope: recursion into text, the shared work budget, other `parse.py` changes, decision
  B′, classes 3 and 4 (child-2); protected-variable names and stored code, classes 5 and 6
  (child-3); the walker (#196) except a walker bug a case here exposes (say so in build
  notes); the allowlist, terminal-read rule, here-doc exemption (#198); §7 (#192); §8
  (#190); mixed-script words (#191); confirm UI (#74); REPL wiring (#78); sudo
  passthrough (#13); `systemd-run --user -M root@.host`. Do not reuse
  `src/nl_shell/failure_classes.py:199` `is_privileged` (its list at `:97-99` may be
  cited as a class 1 cross-check). Do not port v1–v3's per-command code paths (`raw`
  rows, `_PIECE_SPLIT`, per-builtin special cases). Review contract: a bypass inside
  classes 1, 2, 7, decisions A/C or §4/§5 is a defect here; anything else goes to the
  child that owns it or a follow-up.
- **External dependencies:** `tree-sitter-bash`
- **Test file:** tests/test_gate_commands.py
- **Difficulty:** high
- **Surfaces:** data
- **Milestone / ADRs:** M0 — REPL prototype. ADR-0013, ADR-0015, ADR-0023.
- **Citations expected:** path:line on `main` for every change. Loader peer:
  `src/nl_shell/targets.py:145-160`. Decision C peer:
  `src/nl_shell/gate/__init__.py:143-157`.
- **Disposition hint:** new-feature
- **Plan-review response:** Revised for: ANSI-C decoding moved out of `lex_word` into a
  command-layer-only helper so no shell-layer verdict changes (finding 2); decision A's
  over-raise before #198 stated and accepted, with #198's drop defined as an allowlist
  entry (finding 3); Conformance row 16 added to owned spec text (finding 4); loader ban
  is now a test, and harvester drift is stated as human-adjudicated on this host
  (finding 6); broken `results/issue_189/brief.md` cite fixed. Stands on: the tracker
  thread (finding 1) — it lives in the parent bundle (`results/issue_197/notes.json`;
  option (a) at `results/issue_197/split-proposal.md:97`), which the reviewer's sandbox
  did not mount; `run-verify.sh` is the harness's `engine/scripts/run-verify.sh:190-198`
  in nl-shell-pdca, not a target file; the `.venv` path in Reproduction is the harness
  venv, used only by a human. Size (finding 5) — this bundle is already split depth 3
  (`split-lineage.json`), so `split --accept` refuses without `--force`, and the human
  accepted this three-child shape at #197's re-plan; moving the harvester out would need
  a new bundle, which this pass does not create. Left to the human at sign-off.

## Iteration 1 — carry-forward (from the previous attempt)
- Sign-off rationale: Human chose iterate-do over the size backstop: most of the 184 KB is table data (commands.toml, inventory.toml); keep the slice, fix the demonstrated bypasses. The rebuild must: - Decode bash's `\x{HH..}` brace form in `$'…'` (rules.py `_ansi_c`), and fail closed: an undecodable `$'…'` word in a proposal is rejected (or treated as possibly elevating), never silently `mutating`. Tests: `$'\x{73}udo' -i` rejected; `echo pw | $'\x{73}udo' -S true` rejected; `foo $'\x{73}udo'` privileged; `$'\x{72}m' -rf build` destructive. - xargs replace strings (rules.py `_inner`): run the elevation and decision-A checks on the original words before swapping in the opaque input word. Tests: `xargs -Is sudo -i` and `xargs -Isudo sudo -i` as proposals rejected. - `sudo -k <cmd>` (and alias spellings) must keep classifying the inner argv; `-k` only disables runs-command-at when no command follows. Tests: `sudo -k true --pdca-undeclared` and `sudo -k git -c core.pager=sh log` rejected as proposals. - Apply the decision-A argument scan when the command head is non-literal. Tests: `$x sudo` privileged and rejected as a proposal; `$x rm -rf x` destructive; `env "$x" sudo` rejected as a proposal. - Add rows for ruby*, node/nodejs, awk/mawk (and widen the harvester so they land in the inventory), or else narrow the v1.md class-1 sentence to what the harvester collects. Prefer adding rows. Tests: `curl x | ruby`/`node`, `curl x | awk -f /dev/stdin` destructive; `sudo ruby`, `sudo node`, `sudo awk ...` rejected as proposals. - sudo.ws getopt_long prefixes: on a row with rejecting options, reject any unknown `--` option, or list the prefixes. Test: typed `sudo.ws --stdi true` rejected.
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Human chose iterate-do over the size backstop: most of the 184 KB is table data (commands.toml, inventory.toml); keep the slice, fix the demonstrated bypasses. The rebuild must:
  - Decode bash's `\x{HH..}` brace form in `$'…'` (rules.py `_ansi_c`), and fail closed: an undecodable `$'…'` word in a proposal is rejected (or treated as possibly elevating), never silently `mutating`. Tests: `$'\x{73}udo' -i` rejected; `echo pw | $'\x{73}udo' -S true` rejected; `foo $'\x{73}udo'` privileged; `$'\x{72}m' -rf build` destructive.
  - xargs replace strings (rules.py `_inner`): run the elevation and decision-A checks on the original words before swapping in the opaque input word. Tests: `xargs -Is sudo -i` and `xargs -Isudo sudo -i` as proposals rejected.
  - `sudo -k <cmd>` (and alias spellings) must keep classifying the inner argv; `-k` only disables runs-command-at when no command follows. Tests: `sudo -k true --pdca-undeclared` and `sudo -k git -c core.pager=sh log` rejected as proposals.
  - Apply the decision-A argument scan when the command head is non-literal. Tests: `$x sudo` privileged and rejected as a proposal; `$x rm -rf x` destructive; `env "$x" sudo` rejected as a proposal.
  - Add rows for ruby*, node/nodejs, awk/mawk (and widen the harvester so they land in the inventory), or else narrow the v1.md class-1 sentence to what the harvester collects. Prefer adding rows. Tests: `curl x | ruby`/`node`, `curl x | awk -f /dev/stdin` destructive; `sudo ruby`, `sudo node`, `sudo awk ...` rejected as proposals.
  - sudo.ws getopt_long prefixes: on a row with rejecting options, reject any unknown `--` option, or list the prefixes. Test: typed `sudo.ws --stdi true` rejected.
- Full previous attempt preserved in `iteration-v1/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 2 — carry-forward (from the previous attempt)
- Sign-off rationale: Re-plan needed for a spec decision, not more build work. The security review found that a proposal whose command word the gate cannot read (a glob like `/usr/bin/sud? -i` or `/usr/bin/s*do -S true`, a variable like `x=sudo; $x -i`, or a find/xargs placeholder) is classed `mutating` and not rejected. That gets past §5 and decision A. The cause is the spec floor (v1.md §2 :90 and §4.1 decision A :162-163: "command word the gate cannot read is at least mutating"). The re-plan must decide: (a) fnmatch glob command words against row names and reject variable/placeholder command words in proposals, (b) reject every proposal whose command word is unreadable, or (c) record it in the threat model's Known gaps. Then update spec and brief to match. Carry into the revised brief as well: - `$"…"` locale quoting is a bypass in this patch: `$"sudo" -i` (proposal) must be rejected, `$"rm" -rf build` destructive, `foo $"sudo"` privileged. Decode `$"…"` like `"…"` for row lookup, or fail closed like undecodable `$'…'`. - `test_class2_no_command_opens_a_shell_under_sudo` and the `sudo chroot /` / `sudo unshare` regressions must assert the "with no command" reason, not just rejected.
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Re-plan needed for a spec decision, not more build work. The security review found that a proposal whose command word the gate cannot read (a glob like `/usr/bin/sud? -i` or `/usr/bin/s*do -S true`, a variable like `x=sudo; $x -i`, or a find/xargs placeholder) is classed `mutating` and not rejected. That gets past §5 and decision A. The cause is the spec floor (v1.md §2 :90 and §4.1 decision A :162-163: "command word the gate cannot read is at least mutating"). The re-plan must decide: (a) fnmatch glob command words against row names and reject variable/placeholder command words in proposals, (b) reject every proposal whose command word is unreadable, or (c) record it in the threat model's Known gaps. Then update spec and brief to match.
  Carry into the revised brief as well:
  - `$"…"` locale quoting is a bypass in this patch: `$"sudo" -i` (proposal) must be rejected, `$"rm" -rf build` destructive, `foo $"sudo"` privileged. Decode `$"…"` like `"…"` for row lookup, or fail closed like undecodable `$'…'`.
  - `test_class2_no_command_opens_a_shell_under_sudo` and the `sudo chroot /` / `sudo unshare` regressions must assert the "with no command" reason, not just rejected.
- Full previous attempt preserved in `iteration-v2/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

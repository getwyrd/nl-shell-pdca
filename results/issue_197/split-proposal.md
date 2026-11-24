<!-- pdca:split-proposal v1 -->
# Split proposal — issue 197

<!-- Each child is a COMPLETE brief, not a sketch. A filled Slug alone makes `state.state`
     classify the materialised file as PLANNED, so `pdca flow` skips Plan and sends it
     straight to Do — a child missing `Repo + branch target` then builds successfully and
     has nowhere to publish. Fill every field. -->

<!-- Delimiters are HTML comments, not headings, DELIBERATELY: each child body is a full
     draft brief and may contain arbitrary headings and fenced code blocks, so anything
     that could also appear inside a child cannot be its boundary. `pdca split --accept`
     parses these markers; keep them exactly as written. -->

## Why this slice is oversized

#197 is already a split child of #189 (depth 2), so inherited size alone would not justify
another split. The case here is the brief's own new scope. Three builds were made and sent
back: v1 and v2 were about 135 KB each, v3 was 203 KB. Each adversarial review found more
bypasses of the same kind, because one review had to cover seven bypass classes at once.
At pass 4 the human decided to split (`split --force`, 2026-10-26), and the brief already
has an agreed "Split plan" with three children: A = engine and table, B = reading text,
C = variables and stored code. This proposal keeps those three seams and writes each one
out as a full brief.

Each seam ships on its own, with its own test that goes red on the code below it:

1. **Engine and table (child-1).** Row format, loader, the rows, decisions A and C, and
   classes 1, 2 and 7, plus spec §4/§5 rules for commands whose inner command is argv
   (wrappers, sudo family, destructive commands). Text effects may be declared on rows but
   are all classed as decision B (`destructive`, "runs code the gate cannot read"). With
   only this child, the gate is useful and fails closed: `rm -rf build` is `destructive`,
   `sudo -S true` is rejected, and `bash -c 'sudo -i'` is at least `destructive`.
2. **Reading text (child-2).** Recursion through the whole pipeline, the shared work
   budget (`parse.py` seam), decision B′, class 3 (grammars) and class 4 (run-time command
   words). This raises text that child-1 left at `destructive` to its real class
   (`bash -c 'sudo -i'` rejected) and finds hidden command words (`sh -c '$0 -i' sudo`).
3. **Variables and stored code (child-3).** Spec §3 builtins, class 5 (protected
   variables) and class 6 (stored code). Stored text is classed by child-2's recursion,
   and variable names in subscripts use child-2's `arithmetic` grammar.

Splitting further would cost more than it saves: classes 1, 2 and 7 all describe the row
format and must land together for the loader to refuse bad rows, and classes 5 and 6 both
read the same builtins (`declare`/`export`/`printf -v`) and the same assignment record.

## Wave sketch

- **Wave 1: child-1** (engine and table). Nothing in this split comes before it; it
  builds on `main` (#196 merged, `1a1e980`).
- **Wave 2: child-2** (reading text). Depends on child-1: it replaces child-1's "every
  text effect is decision B" with recursion, and it reads the grammar names and text
  effects that child-1's row format declares.
- **Wave 3: child-3** (variables and stored code). Depends on child-2: `stores-code` text
  is classed by child-2's recursion entry point, and class 5's subscript names use
  child-2's `arithmetic` grammar.

All three edit `src/nl_shell/gate/rules.py`, `targets/ubuntu-26.04/commands.toml`,
`targets/ubuntu-26.04/gate-vectors.toml`, the spec and the threat model, so none of them
can share a wave. The `Depends on:` chain already keeps them in three separate waves, so no
`Conflicts with:` fields are needed. To cut down on merge pain, each child gets its own
test file instead of all three appending to `tests/test_gate_commands.py`.

Outside this split: sibling #198 (allowlist) builds on the command table. After this
split it needs only child-1, not all of #197; the human should point #198's
`Depends on:` at child-1's tracker id when filing. #198 and every child here append rows
to `gate-vectors.toml`, which is append-only and merges cleanly.

<!-- pdca:child child-1 -->
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

  **Decisions** (from #189's split plan, `results/issue_189/brief.md:99-112`):
  - **A**: an opaque command (no row, no allowlist entry) is at least `mutating`, "not
    allowlisted". If any argument word, after quote removal (including ANSI-C `$'…'`
    decoding), names a row with `elevates`, the command is `privileged` and a proposal is
    rejected. If one names a row with `destroys`, it is at least `destructive`.
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
  class-7 gap, and a one-line "text effects are decision B" placeholder. In the threat
  model, replace "The command layer … still stubs" (`:194-195`) with what this child
  does. This child's text must **not** claim recursion, decision B′, classes 3–6, or that
  text, stored code or protected-variable spellings are read. Child-2 and child-3 write
  those sections.
- **Success criterion:** `tests/test_gate_commands.py` passes. Every case goes through the
  public `nl_shell.gate.classify(cmd, origin=...)`. Case groups:
  - **Class 1, coverage (property).** Every name in `inventory.toml` has a row. The test
    also checks the inventory lists at least: `sudo`, `sudo.ws`, `sudo-rs`,
    `sudoedit-rs`, `su`, `su-rs`, `pkexec`, `passwd`, `chsh`, `crontab`, `mount`, `sh`,
    `bash`, `rbash`, `dash`, `screen`, `python3`, `perl`, `busybox`, `gdb`. Reviewer
    check at Check: re-run `scripts/harvest_inventory.py` on this host and diff against
    the checked-in file; any difference is a finding. Regressions: `sudo-rs -i`,
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
    cache. Reviewer check: no `os.environ`, `Path.cwd()`, `Path.home()` or config read in
    the loader. Test: with a `commands.toml` in cwd saying `sudo` is harmless, and
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
  `:196`; in `src/nl_shell/gate/parse.py` **only** `lex_word` (`:197`): decode ANSI-C
  `$'…'` quoting as bash does (it is a fixed value, not an expansion; today it falls into
  the `$` "expansion" cause at `:252-253`); an undecodable escape stays non-literal;
  `tests/test_policy_gate.py` expectations this child raises (raise only, never lower;
  e.g. `:192` `$'\x72m' -rf ~` goes from `mutating` "command word is not a literal" to
  `destructive`); spec and threat-model text (raises only); `tests/test_gate_commands.py`.
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
<!-- pdca:end child-1 -->

<!-- pdca:child child-2 -->
- **Slug:** gate-read-command-text
- **Kind:** enhancement
- **Defect / goal:** After child-1, every text effect (`runs-text`, `runs-stdin-as-code`,
  `runs-file-as-code`, `stores-code`) is decision B: at least `destructive`, "runs code
  the gate cannot read". That is safe but too coarse in both directions: `bash -c 'sudo
  -i'` as a proposal is only `destructive`, not rejected, and words that reach command
  position at run time (`sh -c '$0 -i' sudo`) are not checked. Add reading of text:
  - **Decision B with recursion.** Code the gate cannot read (`runs-stdin-as-code` fed by
    a pipe or file; `runs-text` whose text is not literal or not in a parsed grammar;
    `runs-file-as-code`) stays at least `destructive`, "runs code the gate cannot read".
    Literal text in a parsed grammar is classed recursively. **Recursion runs the whole
    pipeline, not only `rules`:** §1.1 characters, `shell_layer`, untrusted features,
    `_redirects`, `_assignments` (the `SUDO_PROMPT` rejection, `__init__.py:229-244`),
    `_shell_rules`, `rules.classify`, `live`, `sensitive`, `words`
    (`gate/__init__.py:159-210`). So `bash -c 'export SUDO_PROMPT=x'` is rejected. The
    entry point is `gate._classify` or a function pulled out of it that takes the shared
    budget and returns a verdict. `rules.py` must not import `gate/__init__.py` (imported
    by it, `:31`): either `rules.classify` returns "class this text in grammar G" and
    `__init__.py` recurses, or `__init__.py` passes a callback. Do picks one and says
    which in build notes. The recursion entry point is what child-3 calls for stored
    code, so keep it a named function.
  - **Shared work budget.** Today each `shell_layer` call builds a new `Walker` with
    `work = 0` (`parse.py:516`, `:1077`), so each nested layer gets its own `MAX_WORK`.
    Add `shell_layer(source, *, budget=None)`: an optional shared counter that
    `Walker.visit` (`:526-528`) adds to; `None` keeps today's behaviour. The recursion
    passes the outer call's counter to each inner call.
  - **Decision B′** (raises only): before decision B applies to non-literal text in a
    parsed grammar, parse the text with each expansion (`$x`, `${…}`, `$(…)`, backticks)
    standing as one unknown word, and class what can be seen. The result is the higher of
    that class and decision B's `destructive`. An expansion inside the command word
    (`"sud${x}o -i"`) leaves it unreadable: decision B only. If the text with holes does
    not parse, decision B only. This makes the threat-model claim "`sudo -S` … cannot
    hide" true; the spec states B′ as part of §4.1.
  - **Class 3, grammar.** Every text effect names its grammar; the engine classes text
    only with a parser for that grammar, else decision B. `bash` is parsed. `env-split`
    (uutils env 0.10.0 `-S`) is parsed, so `env -S 'sudo -i'` and `env -S '\_sudo -i'`
    are seen as `sudo -i`; any escape it cannot translate (`${VAR}`) is decision B.
    `arithmetic` (bash arithmetic and `name[subscript]` evaluation): any `$`, backtick or
    `$(` in a subscript or value is decision B; a name assigned inside the expression
    (`x=SUDO_PROMPT=1`) is reported as a variable write (child-1's name check already
    rejects a write to `SUDO_PROMPT`/`SUDO_ASKPASS` through `_assignments`; this child
    feeds it the name). Every word bash evaluates as arithmetic or a subscripted name is
    in `arithmetic`: `declare`/`typeset`/`local -i` values, `let`, and the name operands
    of `unset`, `test -v`/`[ -v`, `printf -v`, `read`, `mapfile`/`readarray`, `getopts`,
    `wait -p`, `declare`. Interpreter text (python, perl, tcl, js) stays decision B.
  - **Class 4, run-time command words.** Every word that can reach command position at
    run time goes through the command-word check (decision A): words after `-c` text
    (`$0`, `$1`, …), words after a script operand or `bash -s`, literal arguments around
    `{}` in `find -exec`/`xargs`, a non-literal inner command word. When `-c` text's
    command word is filled by a non-literal or stdin word (`bash -c '"$@"' _ "$v"`,
    `xargs sh -c '"$@"' _`, `find . -exec sh -c '"$@"' _ {} \;`), it is decision B.
  - **Stdin into a shell a row opens.** Using child-1's no-command and terminal-stdin
    declarations: literal stdin into a shell opened with no command is classed by
    recursion (`unshare <<<'sudo -i'`, `chroot / <<<'sudo -i'`, `sg`, `newgrp`,
    `script`); piped stdin is decision B (`echo 'rm -rf ~' | unshare`).
  - `fc -e` text is bash text, not a file.
- **Success criterion:** `tests/test_gate_text.py` passes. Every case goes through the
  public `nl_shell.gate.classify(cmd, origin=...)`. Case groups:
  - **Recursion (decision B).** `bash -c 'rm -rf ~'`, `bash <<<'rm -rf ~'`,
    `bash -s <<<'rm -rf /'`, `. /dev/stdin <<<'rm -rf /'` and a quoted here-doc running
    `rm -rf ~` are `destructive` by recursion. Rejected as proposals: `bash <<<'sudo ls'`,
    `bash -c 'sudo -i'`, `bash -c 'export SUDO_PROMPT=x'`, `sg adm -c 'sudo -i'`,
    `busybox sh -c 'sudo -i'`, `script -c 'sudo -i'`. `at now <<<'sudo rm -rf /'` is
    `privileged`. Still decision B: `x | sh`, `bash f.sh`, `bash -c "$v"`, `eval "$v"`,
    `echo 'sudo rm -rf /' | bash`, `echo 'sudo rm -rf /' | at now`. `bash -c 'true'` is
    not raised by decision B (floor function).
  - **Decision B′.** Rejected as proposals: `bash -c "sudo -i $x"`,
    `eval "sudo -S true${x:-}"`. Decision B only (`destructive`, "runs code the gate
    cannot read"), not lower and not rejected: `bash -c "sud${x}o -i"` (expansion in the
    command word) and `bash -c "sudo -i $x ("` (text with holes does not parse). The
    stored-code forms of B′ (`trap`, `alias`, `PROMPT_COMMAND`) are tested in child-3.
  - **Class 3, grammar (property).** For every row field in the `arithmetic` grammar,
    `'a[$(rm -rf ~)]'` there gives at least `destructive`, "runs code the gate cannot
    read". For every text effect in an unparsed grammar, literal text is decision B.
    Regressions: `env -S 'sudo -i'`, `env -S 'sudo\_-i'`, `env -S '\_sudo -i'`,
    `env -S '\_sudo\_-i'`, `env -S '-i\_sudo\_-i'` as proposals `privileged` and
    rejected; `env -S 'rm\_-rf\_/'` at least `destructive`; `env -S '${X}'` decision B.
    At least `destructive`: `declare -i x='a[$(rm -rf ~)]'`,
    `a=(1); unset -v 'a[$(rm -rf ~)]'`, `test -v 'a[$(rm -rf ~)]'`,
    `[ -v 'a[$(rm -rf ~)]' ]`, `printf -v 'a[$(rm -rf ~)]' x`. Rejected as proposals:
    `typeset -i x='a[$(sudo -i)]'`, `unset 'x[$(sudo -i)]'`, `declare -i x=SUDO_PROMPT=1`.
    `fc -e 'rm -rf ~'` is classed as bash text (at least `destructive`, by recursion).
  - **Class 4, run-time command words (property).** For every row with a `runs-text`
    effect that passes later words as positional parameters, `<row> '"$@"' _ sudo -i` (or
    the row's equivalent) as a proposal is rejected. Regressions (proposals): `sh -c
    '$0 -i' sudo` and `bash -c '"$0" -S true' sudo` rejected; `sh -c '"$@"' _ rm -rf ~`
    at least `destructive`; `bash -s _ sudo -i <<<'"$@"'` and `bash /dev/stdin sudo -i
    <<<'"$@"'` rejected; `find /usr/bin -name sudo -exec {} -i \;` rejected;
    `printf rm | xargs -I% % -rf ~` at least `destructive`. Decision B (at least
    `destructive`): `bash -c '"$@"' _ "$v"`, `printf x | xargs sh -c '"$@"' _`,
    `find . -exec sh -c '"$@"' _ {} \;`.
  - **Stdin into an opened shell.** Rejected as proposals: `unshare <<<'sudo -i'`,
    `chroot / <<<'sudo -i'`, `sg adm <<<'sudo -i'`, `newgrp adm <<<'sudo -i'`.
    `echo 'rm -rf ~' | unshare` is decision B.
  - **Work budget.** `{ bash;bash;bash;bash; } <<'E0'` nested nine deep (about 320 bytes)
    gives a result never below `mutating` (decision C if the budget runs out), under a
    loose 10 s timeout that only guards against a hang. Sharing is tested by effect, not
    by reading a counter (`Result`, `__init__.py:83-88`, has no work count; none is
    added): one text `T` (e.g. `:;` repeated, sized by the test from `MAX_WORK`; at Plan
    `:;`×1000 was about 3000 units and 2 KB) that `bash -c 'T'` classes alone with no
    "could not class"; `bash -c 'T'; bash -c 'T'; bash -c 'T'` (under the 8 KiB input
    cap) is decision C, "could not class". Do may change the size of `T` or the repeat
    count, but must keep "alone fits, together does not". **Departure from the tracker,
    for the human to accept at sign-off:** the issue text says the nine-deep case
    "classifies in under one second". This brief tests the bound by work units (the shared
    budget), not wall time, because a 1 s wall-clock assert flakes on a loaded CI runner
    and proves nothing the budget case does not. The 10 s timeout only catches a hang.
    If the human wants the 1 s bound kept, Do adds it as a separate test marked slow.
  - **Assertions.** Every case asserts the class (or a floor), a reason substring, and
    that no reason is "could not class", except the budget cases (which accept the
    engine's reason or "could not class", never a class below the one stated, and the
    sharing case which asserts "could not class").
- **Falsifiability:** C4 reverts this child's `src/`, `targets/`, `scripts/` hunks and keeps
  the test, which leaves child-1's engine (text effects all decision B, one budget per
  `shell_layer` call). There: `bash -c 'sudo -i'`, `env -S '\_sudo -i'`,
  `sh -c '$0 -i' sudo`, `unshare <<<'sudo -i'` are `destructive` or `mutating`, not
  rejected; `bash -c 'T'` ×3 is not "could not class". So every group goes red except the
  decision-B-floor cases and the floor function, which may pass. Import `nl_shell.gate`
  inside test functions (`run-verify.sh:196`).
- **Invariant to restore:** Every part of a command that can run code is read in its own
  grammar or gets an explicit fail-closed default; text the gate can read is classed as
  if typed. One work budget covers a whole top-level `classify` call. ADR-0013, ADR-0015;
  `policy-gate/v1` §1 step 4, §4.1; threat model "What must hold"
  (`.oss-scanner/threat_model.md:121-125`).
- **Repo + branch target:** eduralph/nl-shell @ main
- **Reproduction:** With child-1 merged, in `/home/eddie/nl-shell/nl-shell`:
  `PYTHONPATH=src /home/eddie/nl-shell/nl-shell-pdca/.venv/bin/python3 -c 'from nl_shell.gate import classify; print(classify("bash -c \"sudo -i\"", origin="proposal"), classify("sh -c \"\$0 -i\" sudo", origin="proposal"))'`
  gives a non-rejected result for both (decision B `destructive` for the first; the
  second is not rejected).
- **Scope (one logical fix) / out of scope:** In scope: `src/nl_shell/gate/rules.py`
  (text effects, grammars, run-time command words); `src/nl_shell/gate/__init__.py`
  (`_classify`, `:159-210`, restructured into a recursion entry point that takes the
  shared budget, with no `rules` → `gate` import cycle); `src/nl_shell/gate/parse.py`
  **only** the `shell_layer(budget=)` seam (`:1070`, `Walker` `:516`, `:526-528`); an
  `env-split` parser and an `arithmetic` subscript scanner (new module or in
  `rules.py`); `commands.toml` row edits needed to name grammars or positional-parameter
  behaviour; `gate-vectors.toml` rows (appended); spec §4.1 (decision B, B′, class 3, 4,
  replacing child-1's "text effects are decision B" placeholder) and threat-model text
  (raises only; this child may say text run now cannot hide `sudo -S`, but must not
  claim stored code or protected-variable spellings, which are child-3's); `tests/test_policy_gate.py` and
  `tests/test_gate_commands.py` expectations this child raises (raise only, never lower,
  and say which in build notes); `tests/test_gate_text.py`. Out of scope: row
  format, loader, coverage, undeclared options (child-1); protected-variable name
  operands and stored code — `trap`, `alias`, `PROMPT_COMMAND`, `PS0`–`PS4`,
  `complete -C`, `bind -x`, `mapfile -C`, `BASH_ENV` (child-3); assignments and
  expansions with no simple command (`(( SUDO_ASKPASS=1 ))`, `for SUDO_PROMPT in x`,
  `: ${SUDO_ASKPASS:=/x}`, `[[ -v 'a[$(…)]' ]]`, `x=sudo; $x -i`) — walker work, human
  files a follow-up; any other walker change unless a case exposes a walker bug (say so
  in build notes); #198, #192, #190, #191, #74, #78, #13. Review contract: a bypass in
  decisions B/B′, classes 3/4 or the budget is a defect here.
- **External dependencies:** `tree-sitter-bash`
- **Test file:** tests/test_gate_text.py
- **Difficulty:** high
- **Surfaces:** data
- **Milestone / ADRs:** M0 — REPL prototype. ADR-0013, ADR-0015, ADR-0023.
- **Citations expected:** path:line on the target branch for every change. Budget peer:
  `src/nl_shell/gate/parse.py:39-41`, `:516`, `:526-528`. Recursion peer: `_classify`,
  `src/nl_shell/gate/__init__.py:159-210`.
- **Disposition hint:** new-feature
- **Depends on:** child-1
<!-- pdca:end child-2 -->

<!-- pdca:child child-3 -->
- **Slug:** gate-protected-vars-stored-code
- **Kind:** enhancement
- **Defect / goal:** After child-2 the gate reads text it is asked to run now, but not
  text kept to run later, and it checks protected variables only for plain `NAME=value`
  assignments (`__init__.py:229-244`, `_declared` `parse.py:816-828`). So
  `export SUDO_PROMPT`, `declare -n r=SUDO_ASKPASS; r=/x`, `read SUDO_PROMPT <<<x`,
  `alias ls='sudo -i'` and `PROMPT_COMMAND='sudo -i'` are not rejected. Add:
  - **Spec §3 builtins.** Row 33 and `unalias`, `source`, `.`, `eval`, `exec`, `trap`,
    `enable`, `set`, `shopt`, `bind`, `complete`, `hash`, `builtin`, `command` (except
    `command -v`/`-V`, `v1.md:101`), `export`, `declare`/`typeset`/`local`/`readonly`
    with assignments, and `unset` are at least `session-altering`. (child-1 sets the
    floor; this child adds the name and stored-code rules and keeps that floor.)
  - **Class 5, protected variables.** Every row that takes variable names marks which
    operands or option values are names (child-1's format has the marker). Changing the
    value of `SUDO_PROMPT`/`SUDO_ASKPASS`, exporting them, or pointing a nameref at them
    is rejected, with or without `=` (`export SUDO_PROMPT`, `declare -x`, `typeset -x`,
    `readonly -x`, `local -x`, `declare -n`, `printf -v`, `read`, `mapfile`, `getopts`,
    `let`, `wait -p`). The same forms on a §3 session name (`PATH`, `LD_*`, …) are at
    least `session-altering`. A nameref target with a subscript
    (`declare -n r='x[$(sudo -i)]'; r=1`) goes through child-2's `arithmetic` grammar.
  - **Class 6, stored code.** Text kept to run later is classed as if it ran now, in its
    own grammar, through child-2's recursion entry point: `trap` text, `alias` values,
    `complete -C` text, the command part of `bind -x '"keys":cmd'` (decision B if it
    cannot be split), `mapfile -C` text, the values of `PROMPT_COMMAND` (scalar or array)
    and `PS0`–`PS4` (a `$(…)`/backtick in a prompt string is classed as bash text). This
    holds however the value is set: a plain assignment (`Invocation.assignments`,
    `parse.py:171`), `export`/`declare`, or `printf -v`. Quoted compound array values are
    parsed as the array they become (`declare -a PROMPT_COMMAND='("sudo -i")'`,
    `declare -a x='($(sudo -i))'`, `declare -a x='([0]=$(rm -rf ~))'`). `BASH_FUNC_<name>%%`
    env assignments are stored bash code. A file run later (`BASH_ENV=`, `ENV=`,
    `enable -f x.so`) is decision B. Decision B′ (child-2) applies to stored text too, so
    `trap "sudo -i $x" EXIT`, `alias ls="sudo -i $x"`, `PROMPT_COMMAND="sudo -i $x"` are
    rejected.
- **Success criterion:** `tests/test_gate_stored_code.py` passes. Every case goes through
  the public `nl_shell.gate.classify(cmd, origin=...)`. Case groups:
  - **Class 5, protected variables (property).** For every row field marked as a name,
    `SUDO_PROMPT` there is rejected as a proposal, and `PATH` gives at least
    `session-altering`. Regressions (rejected): `export SUDO_PROMPT`,
    `declare -x SUDO_ASKPASS`, `typeset -x SUDO_PROMPT`, `readonly -x SUDO_PROMPT`,
    `local -x SUDO_PROMPT` (inside a function body), `declare -n r=SUDO_ASKPASS; r=/x`,
    `printf -v SUDO_ASKPASS /x`, `read SUDO_PROMPT <<<x`, `mapfile SUDO_PROMPT <x`,
    `getopts x SUDO_PROMPT`, `getopts -- x SUDO_PROMPT`, `let SUDO_ASKPASS=1`,
    `wait -p SUDO_PROMPT`, `declare -n r='x[$(sudo -i)]'; r=1`. The same forms naming
    `PATH` or `LD_PRELOAD` are `session-altering`.
  - **Class 5 pinned (`test_class5_pinned`).** `export "SUDO_PROMPT"=x` and
    `declare 'SUDO_ASKPASS'=/x` are already rejected on `main` (`parse.py:816-828`, then
    `__init__.py:236-237`). Pinned against regression; not part of the red-leg claim.
  - **Class 6, stored code (property).** For every row with a `stores-code` effect, the
    row's example with stored text `sudo -i` as a proposal is rejected, and with
    `rm -rf ~` at least `destructive`. Regressions: `trap 'rm -rf ~' EXIT` at least
    `destructive`. Rejected as proposals: `trap -- 'sudo -i' EXIT`, `alias ls='sudo -i'`,
    `export PROMPT_COMMAND='sudo -i'`, `PROMPT_COMMAND='sudo -i'`,
    `PROMPT_COMMAND=('sudo -i')`, `PS1='$(sudo -i)'`,
    `declare -a PROMPT_COMMAND='("sudo -i")'`, `declare -a x='($(sudo -i))'`,
    `mapfile -C 'sudo -i' -c 1 a < f`, `trap "sudo -i $x" EXIT`, `alias ls="sudo -i $x"`,
    `PROMPT_COMMAND="sudo -i $x"`, `env 'BASH_FUNC_ls%%=() { sudo -i; }' bash`. At least
    `destructive`: `complete -C 'rm -rf ~' x`, `bind -x '"\C-x":rm -rf ~'`,
    `BASH_ENV=/tmp/x`, `mapfile -C 'rm -rf ~' -c 1 a < f`,
    `declare -a x='([0]=$(rm -rf ~))'`. `alias ll='ls -l'` (row 33) stays
    `session-altering`, never lower.
  - **Spec §3 builtins.** The list above is at least `session-altering` (re-asserted so
    this child cannot lower child-1's floor).
  - **Assertions.** Every case asserts the class (or a floor), a reason substring, and
    that no reason is "could not class".
- **Falsifiability:** C4 reverts this child's `src/`, `targets/`, `scripts/` hunks and keeps
  the test, which leaves child-1 + child-2. There `export SUDO_PROMPT` and
  `read SUDO_PROMPT <<<x` are `session-altering` or `mutating`, not rejected, and
  `alias ls='sudo -i'`, `PROMPT_COMMAND='sudo -i'` are decision B (`destructive`) or
  `session-altering`, not rejected. So the class 5 and class 6 groups go red;
  `test_class5_pinned` and the §3 floor group may pass. Import `nl_shell.gate` inside
  test functions (`run-verify.sh:196`).
- **Invariant to restore:** A change to a protected variable is rejected however it is
  spelled, and code stored to run later is classed as if it ran now. ADR-0013, ADR-0015;
  `policy-gate/v1` §3, §4.1, §5; threat model "What must hold"
  (`.oss-scanner/threat_model.md:121-125`, the `SUDO_PROMPT`/`SUDO_ASKPASS` rules).
- **Repo + branch target:** eduralph/nl-shell @ main
- **Reproduction:** With child-1 and child-2 merged, in `/home/eddie/nl-shell/nl-shell`:
  `PYTHONPATH=src /home/eddie/nl-shell/nl-shell-pdca/.venv/bin/python3 -c 'from nl_shell.gate import classify; print(classify("export SUDO_PROMPT", origin="proposal"), classify("alias ls=\"sudo -i\"", origin="proposal"))'`
  gives a non-rejected result for both.
- **Scope (one logical fix) / out of scope:** In scope: `src/nl_shell/gate/rules.py`
  (name operands, stored-code effects, compound array values);
  `src/nl_shell/gate/__init__.py` (calling child-2's recursion entry point for stored
  text; reading `Invocation.assignments`, `parse.py:171`, for plain `PROMPT_COMMAND=`,
  `PS1=`, `BASH_ENV=`, `BASH_FUNC_*%%=`); `commands.toml` edits to builtin rows (name
  markers, `stores-code` grammar); `gate-vectors.toml` rows (appended); spec §3/§4.1/§5
  and threat-model text (raises only); `tests/test_policy_gate.py`,
  `tests/test_gate_commands.py` and `tests/test_gate_text.py` expectations this child
  raises (raise only, never lower, and say which in build notes);
  `tests/test_gate_stored_code.py`. Out of scope:
  row format and loader (child-1); recursion, budget, grammars, B′ (child-2) — use them,
  do not change them except to fix a bug a case here exposes (say so in build notes);
  any `parse.py` change; assignments with no simple command (`(( SUDO_ASKPASS=1 ))`,
  `for SUDO_PROMPT in x`, `: ${SUDO_ASKPASS:=/x}`) — walker follow-up; #198, #192, #190,
  #191, #74, #78, #13. Review contract: a bypass in classes 5/6 or §3 builtins is a
  defect here.
- **External dependencies:** `tree-sitter-bash`
- **Test file:** tests/test_gate_stored_code.py
- **Difficulty:** high
- **Surfaces:** data
- **Milestone / ADRs:** M0 — REPL prototype. ADR-0013, ADR-0015, ADR-0023.
- **Citations expected:** path:line on the target branch for every change. Peers:
  `_assignments`, `src/nl_shell/gate/__init__.py:229-244`; `_declared`,
  `src/nl_shell/gate/parse.py:816-828`.
- **Disposition hint:** new-feature
- **Depends on:** child-2
<!-- pdca:end child-3 -->

# Brief — issue 204 / gate-command-table-engine

> Re-plan (v3). v1 and v2 are archived in `iteration-v1/` and `iteration-v2/`. v2 built the
> table and the engine and passed every gate. It was stopped at sign-off because of a spec
> hole (a command word the gate cannot read was only "at least `mutating`"). The human chose
> **decision D, option (b1)** below to close it. Everything else in v2's brief stands.
> Changes from v2 are marked **[v3]**.

- **Slug:** gate-command-table-engine
- **Kind:** enhancement
- **Defect:** On `main` (`1a1e980`, #196 merged) the gate's command layer is a
  stub: `src/nl_shell/gate/rules.py:26-28` returns `mutating`, "not allowlisted" for every
  simple command. So `rm -rf build` is not `destructive`, `sudo apt update` is not
  `privileged`, `sudo -S true` is not rejected, and none of spec §4–§5's per-command rules
  fire. A command word the gate cannot read (`/usr/bin/sud? -i`, `x=sudo; $x -i`) is only
  `mutating` (`src/nl_shell/gate/__init__.py:255-256`, spec `v1.md:90-91`), so it gets past
  §5 even once the table exists **[v3]**. Add the reviewed data table
  `targets/ubuntu-26.04/commands.toml` (format, loader, rows) and one generic engine in
  `gate/rules.py` that reads it. Wrappers, the sudo family, destructive commands,
  interpreters and builtins are data rows, not code paths. Each row gives the command's
  argv grammar (flags; value-taking options in short, attached and long `=` forms;
  end-of-options; where an inner command starts) and its effects from one fixed set:
  `runs-command-at`, `runs-text`, `runs-stdin-as-code`, `runs-file-as-code`,
  `stores-code`, `sets-variable`, `elevates`, `destroys` (with a condition),
  `reads-terminal`, `opens-shell`. Do may refine effect names, but the later children's
  rules (text in a named grammar, name operands, stored code) must be expressible in the
  format: every text effect names its grammar (`bash`, `env-split`, `arithmetic`, or a
  named unparsed one such as `python`), and operands/option values that are variable
  names are marked as names.

  **In this child every text effect** (`runs-text`, `runs-stdin-as-code`,
  `runs-file-as-code`, `stores-code`) **is decision B**: at least `destructive`, reason
  "runs code the gate cannot read". No recursion. Inner commands of wrappers
  (`runs-command-at`) are argv, not text, and are classed by the same engine.

  **Decisions** (from #189's split plan, `results/issue_189/iteration-v3/brief.md:99-112`,
  checked at this revision; #204's tracker body cites `results/issue_189/brief.md`, which
  does not exist because #189 was archived, so that path is stale. Restated in #197's
  tracker body, `results/issue_197/notes.json`, whose decision-A bullet ends "Decision A
  applies only to a command with neither a `commands.toml` row nor an allowlist entry"):
  - **A**: an opaque command (no row, no allowlist entry) is at least `mutating`, "not
    allowlisted". If any argument word, after quote removal (including ANSI-C `$'…'` and
    locale `$"…"` decoding), names a row with `elevates`, the command is `privileged` and a
    proposal is rejected. If one names a row with `destroys`, it is at least
    `destructive`. Decision A applies **only** to a command with neither a row nor an
    allowlist entry (#197's tracker body says so). Until #198 lands there is no
    allowlist, so `man sudo`, `which sudo`, `apt show sudo`, `dpkg -L sudo`, `echo su`
    come out `privileged` here. That over-raise is accepted: it is safe, and when #198
    allowlists those commands their class drops by an allowlist entry, which
    `v1.md:238-239` counts as a compatible, human-reviewed v1 change, not a lowering. Do
    not add rows here just to avoid it.
  - **Elevation reaches inner commands** (option (a) chosen at #197's re-plan):
    under a row with `elevates`, a proposal is rejected if any later argument word names a
    row that opens a shell or has a text effect (`bash`, `sh`, `python3`, `busybox`, …),
    whatever command sits between (`sudo strace bash`, `sudo setpriv bash`,
    `sudo runuser -u root bash`). Under an `elevates` row, a non-literal word or an
    undeclared option anywhere in the inner argv also rejects a proposal.
  - **C**: a gate failure (unhandled node, work budget used up, missing or invalid
    `commands.toml`, internal error) is `privileged`, rejected, "could not class". #196
    already implements the sink (`src/nl_shell/gate/__init__.py:18-19`, `:48`, `:143-144`);
    this child sends its own failures there.
  - **D — a command word the gate cannot read is a possible `sudo` [v3, human's choice
    (b1) at the v2 sign-off/re-plan].** The options (a)/(b)/(c) are on record at
    `iteration-v2/SUMMARY.md:210` and `:254`. (b1) is option (b) plus "§5 rules apply to
    typed commands too", chosen by the human in the v3 re-plan session; it is not yet in
    the #204 tracker body. A command word is *unreadable* when the command
    layer cannot turn it into one fixed string: it has an expansion (`$x`, `${…}`, `$(…)`,
    backticks, `$((…))`), a glob (`*`, `?`, `[`), brace expansion, an undecodable `$'…'`,
    or a `$"…"` with an expansion inside. Placeholders that stand as an **inner** command
    word count too: `find -exec {}`/`-execdir {}`/`-ok {}`, and an `xargs` replace string
    (`-I%`, `-i`, `--replace=@`) used as the command word. The rule applies to the outer
    command word and to every inner command word a `runs-command-at` row (or the
    `busybox` applet slot) reaches. For an unreadable command word:
    1. The command is `privileged`, reason "command word the gate cannot read".
    2. A proposal is rejected.
    3. For **every** origin (typed included), every §5 rule that would reject `sudo` in the
       same spot rejects it: a pipe, here-doc or here-string feeding it, and any argument
       word that the `sudo` row's grammar reads as a rejecting option (`-S`, `-p`, `-A`,
       their bundled and attached forms, `--stdin`, `--prompt`, `--askpass`, and the long
       prefixes `sudo` accepts). Reason: the matching §5 reason.
    Accepted cost (human-confirmed): typed `git log | $PAGER` and `$EDITOR -p a b` are
    rejected; the user retypes them with a plain command word. A command word whose
    **only** non-literal cause is `leading-tilde` (`parse.py:262-265`, a leading `~` or
    `~/`) is NOT unreadable under D. The **command layer** (`rules.py`, not `lex_word`)
    treats it as a literal path: it takes the last path part of the word's text and looks
    it up as a row name, like any path (`~/sudo -i` hits the `sudo` row). If no row
    matches, the command layer itself raises to `mutating` with the reason "command word is
    a path outside the system directories: <word>". The shell layer never gives that reason
    for such a word, because `Word.literal` is False and `_shell_rules` stops at the
    "command word is not a literal" branch (`gate/__init__.py:255-256`; the path `elif` at
    `:257-261` is not reached). Both reasons will appear; that is expected. The shell layer
    stays frozen.
    D raises the old floor (`v1.md:90-91`, "not a literal … at least `mutating`") and
    never lowers anything, so it is a compatible v1 change (`v1.md:238-241`). The
    shell-layer rule at `src/nl_shell/gate/__init__.py:255-256` and its reason stay as they
    are; D lives in the command layer.

  **Path lookup [v3].** For a command word that is a literal path (system directory or
  not, including `./x` and `~/x`), the row lookup uses its last path part:
  `/usr/bin/sudo-rs -i`, `./sudo -i` and `~/sudo -i` all hit the `sudo` family rows.
  For a `~/…` word the command layer does this itself (see decision D's leading-`~`
  rule), since the shell layer treats that word as non-literal.

  **Known gap, recorded not fixed [v3, human's choice].** A literal command word that is a
  path outside the system directories (`./x -i`, `/tmp/x -i`, `~/bin/x -i`) whose last
  part names no row stays `mutating`, "path outside the system directories", not
  rejected. If that file is a symlink to `/usr/bin/sudo` it is a root shell. Knowing what
  a path points to is §7 live-session resolution (#192; `src/nl_shell/gate/live.py` is a
  stub). Write this into the threat model's "Known gaps" (`.oss-scanner/threat_model.md:220`)
  and into spec §4.1 next to decision D, pointing at #192.

  **Classes owned here** (class numbers as in #197's brief):
  1. **Coverage.** Every binary on the target that elevates, or that runs a shell or an
     interpreter, has a row, including every alias name pointing at the same file
     (`sudo-rs`, `sudo.ws`, `sudoedit-rs`, `su-rs` → `/usr/lib/cargo/bin/{sudo,su}`).
     `scripts/harvest_inventory.py` (style of `scripts/gen_unicode_tables.py`) writes
     `targets/ubuntu-26.04/inventory.toml` from this Ubuntu 26.04.1 host:
     setuid/setgid/file-capability binaries in `/usr/bin`, `/usr/sbin`,
     `/usr/lib/cargo/bin`; every name there whose `realpath` matches a listed binary or a
     row's binary; `/etc/shells`; binaries of dpkg packages in sections `shells` and
     `interpreters`; `python3*`, `perl*`, `ruby*`, `node`, `nodejs`, `awk`, `mawk`,
     `gawk`, `busybox`, `gdb`. Checked in, reviewed like an allowlist change, records the
     host's `VERSION` line, not run by any test. A row for a non-elevating setuid binary
     (e.g. `passwd`) may just say so.
  2. **No unread argv.** No row skips argv parsing (no `raw = true`). An option a row
     does not declare is at least `destructive`, "option the gate does not know"; on an
     `elevates` row a proposal with it is also rejected. On a row with rejecting options
     (the sudo family), an unknown `--` option is rejected for every origin, since
     getopt_long accepts any unique prefix. A row may describe only some subcommands
     (`git clean|reset|push`); others get the row's stated default (at least
     `mutating`), so floor rows 8 and 27 stay as the spec says. Named exception: the
     code-running options of the class-7 floor commands (`git` global
     `-c`/`--config-env`/`--exec-path`, `tar --to-command`, `ssh -o`) carry a
     `class-7-gap` marker and give the row's default (`mutating`, "not allowlisted"). The
     loader accepts `class-7-gap` only on options named in the spec's class-7 text. A row
     whose effects do not depend on argv (e.g. `passwd`) may give a fixed class (at least
     `mutating`); decision A still runs over its words. Every `runs-command-at` row
     declares what it does with no command (`chroot`/`unshare` start `$SHELL`) and when
     stdin is the terminal (`bash -s x`, `bash /dev/stdin`). The loader refuses a row that
     leaves either undeclared. An option that only changes what happens with no command
     (`sudo -k`) does not stop the inner argv from being classed when a command follows.
  7. **Real text-runners get rows; the leftover gap is written down.** Rows with their
     text effects for `busybox` (applet = inner command), `python3`, `perl`, `ruby`,
     `node`/`nodejs`, `awk`/`mawk`/`gawk` (`-f` is `runs-file-as-code`), `tclsh`, `gjs`,
     `gdb -ex`, `screen`, `script` (no command opens `$SHELL`; `-c` is `runs-text` bash),
     and by name for `sg`/`newgrp` (`runs-text`, sh), `at`/`batch`
     (`runs-stdin-as-code`), `zsh`, `tmux`, `x-terminal-emulator -e`.
     Accepted gap, written into spec and threat model: an unknown command that takes
     command text as one quoted word (`foo 'sudo -i'`), an `awk` program given as an
     operand, and the code-running options of floor rows 8/10/11 (`git -c core.pager=sh`,
     `tar --to-command=sh`, `ssh -o ProxyCommand=sh`). These stay `mutating`, "not
     allowlisted". Decision A does not split quoted words.

  Write the command table, decisions A, C and D, the path-lookup rule, classes 1, 2, 7,
  the class-7 gap and the path-outside-system-directories gap into the spec
  (`docs/design/specs/policy-gate/v1.md` §2, §4/§5 and a new §4.1) and the threat model
  (`.oss-scanner/threat_model.md:171-195`, the paragraph that still says "The command
  layer … still stubs"; and "Known gaps" at `:220`). In §2, the non-literal part of the
  command-word bullet (`v1.md:90-91`) points at decision D; the "path outside the
  package-owned system directories" part stays at `mutating`. State in §4.1 that text
  effects are decision B until the text-reading layer lands (child-2). **Spec text owned
  by this child:** §2's command-word bullet, §4/§5 rows, the new §4.1 sections for the
  row format, decisions A, C and D, the path-lookup rule, classes 1, 2 and 7, the class-7
  gap and the path gap, a one-line "text effects are decision B" placeholder, and
  Conformance rows: row 16 (`v1.md:268`, `$'\x72m' -rf ~`), whose stated reason
  "(non-literal word)" this child makes false (change it to `destructive`, ANSI-C decodes
  to `rm`), plus new rows for decision D (`/usr/bin/sud? -i` proposal rejected,
  `x=sudo; $x -i` proposal rejected, `echo pw | /usr/bin/s*do -S true` typed rejected),
  each with a matching appended `gate-vectors.toml` row. The threat model's "What must
  hold" sentence on sudo (`:121-125`) must stay true as written; D is what keeps it true
  for unreadable command words. This child's text must **not** claim recursion, decision
  B′, classes 3–6, or that text, stored code or protected-variable spellings are read.
  Child-2 and child-3 write those sections.
- **Success criterion:** `tests/test_gate_commands.py` passes. Every case goes through the
  public `nl_shell.gate.classify(cmd, origin=...)`. Case groups:
  - **Class 1, coverage (property).** Every name in `inventory.toml` has a row. The test
    also checks the inventory lists at least: `sudo`, `sudo.ws`, `sudo-rs`,
    `sudoedit-rs`, `su`, `su-rs`, `pkexec`, `passwd`, `chsh`, `crontab`, `mount`, `sh`,
    `bash`, `rbash`, `dash`, `screen`, `python3`, `perl`, `ruby`, `node`, `awk`,
    `mawk`, `busybox`, `gdb` (all present on this host at Plan). Drift between the checked-in inventory and the host is
    **human-adjudicated, not a gate**: the reference host is this machine (Ubuntu
    26.04.1, the `VERSION` line the file records); at Check a reviewer re-runs
    `scripts/harvest_inventory.py` here and diffs against the checked-in file; any
    difference is a finding. Regressions: `sudo-rs -i`, `sudo.ws -i`, `su-rs`,
    `/usr/bin/sudo-rs -i`, `sudoedit-rs /etc/shadow` are `privileged`; the first four
    rejected as proposals. `echo pw | sudo-rs -S true` rejected. `foo sudo-rs`
    `privileged`, rejected as a proposal. `curl x | python3`, `python3 -c "$v"`,
    `perl -e 'system 1'`, `echo 'sudo rm -rf /' | at now`, `curl x | ruby`,
    `curl x | node`, `curl x | awk -f /dev/stdin` at least `destructive`, "runs code the
    gate cannot read". `sudo zsh`, `sudo busybox sh`, `sudo ruby`, `sudo node`,
    `sudo awk 'BEGIN{}'` as proposals rejected (root shell / interpreter under sudo).
  - **Class 2, unread argv (property).** The loader refuses a row with `raw`, an unknown
    key, or a `runs-command-at` row missing its no-command/terminal-stdin declaration.
    Every row carries a minimal example invocation. For every row that reads argv, that
    example with `--pdca-undeclared` placed right after the command word (and, for rows
    that describe subcommands, right after each described subcommand, e.g.
    `git clean --pdca-undeclared`) is at least `destructive`, "option the gate does not
    know"; on every `elevates` row it is also rejected as a proposal. For every row
    declaring "opens a shell with no command", `sudo <row example with no command>` as a
    proposal is rejected **and its reasons include the row's "with no command" reason
    text [v3]** (not just `rejected`). Regressions (proposals, rejected): `sudo bash -s x`,
    `sudo bash -is x`, `sudo dash -s x`, `sudo env bash -s x`, `pkexec bash -s x`,
    `sudo bash /dev/stdin`; `sudo chroot /` and `sudo unshare` rejected **with the "with no
    command" reason asserted [v3]**. `enable -f /tmp/x.so foo` at least `destructive`.
    Carried from v1's sign-off: `sudo -k true --pdca-undeclared` and
    `sudo -k git -c core.pager=sh log` rejected as proposals; typed `sudo.ws --stdi true`
    and `sudo --pro x true` rejected.
  - **Class 7 / floor (documented, not raised).** In a test function named for the floor
    group: `foo 'sudo -i'`, floor rows 8, 10, 11, 27 (`git -c core.pager=sh log`,
    `git status`, `tar --to-command=sh -xf a.tar`, `ssh -o ProxyCommand=sh h`) are
    `mutating`, "not allowlisted". **[v3]** The path gap, as proposals: `./x -i`,
    `/tmp/x -i`, `~/bin/x -i` are `mutating`, not rejected, reason includes "path outside
    the system directories" (for `~/bin/x -i` that reason comes from the command layer;
    the shell layer's "not a literal" reason is also present and allowed). Not part of
    the red-leg claim.
  - **Spec §4 privileged:** row 24 (`sudo apt update`), `su`, `pkexec`, `doas`, `run0`,
    `machinectl shell`, `machinectl shell root@`, `//usr/bin/sudo true` are `privileged`,
    never lower. **[v3]** Path lookup: `./sudo -i` and `~/sudo -i` as proposals
    `privileged`, rejected.
  - **Spec §4 destructive:** rows 26 (`rm -rf build`), 17 (`"r"m -rf ~`), 18
    (`ls; rm -rf ~`), 29 (`systemctl stop ssh`), 9 (`find . -exec rm {} \;`), and `dd`,
    `mkfs.ext4`, `wipefs`, `shred`, `truncate`, `chmod -R`, `find -delete`, `git clean`,
    `git reset --hard`, `git push --force`, `kill -9 -1`. Row 9 is derived (record in the
    spec): `{}` is a non-literal operand, and `rm` with a non-literal operand is classed
    like `rm` with a glob ⇒ `destructive`.
  - **Spec §4 wrappers (property + regressions).** Every `runs-command-at` row carries a
    minimal prefix (e.g. `timeout 5`). For every such row, `<prefix> rm -rf x` is at least
    `destructive`, `<prefix> sudo -i` as a proposal is `privileged` and rejected, and
    **[v3]** `<prefix> $x -i` as a proposal is `privileged` and rejected with the
    decision-D reason. Named: `env rm -rf x` (row 32) `destructive`; `nice`, `nohup`,
    `timeout`, `time`, `xargs`, `watch` take the inner class and are at least `mutating`.
    Proposals `privileged` and rejected: `env - sudo -i`, `env 'A=1' sudo -i`,
    `env -a x sudo -i` (uutils env 0.10.0 takes a value for `-a`/`--argv0`),
    `exec -a x sudo -i`, `nice -n5 sudo -i`, `timeout -s9 5 sudo -i`,
    `stdbuf -o0 sudo -i`, `setsid sudo -i`, `flock /tmp/l sudo -i`. `env - rm -rf ~`
    `destructive`. xargs replace strings (`-I%`, `-i`, `--replace=@`) may become options
    at run time: proposals `xargs -I% sudo % true`, `xargs -o -I% sudo %`,
    `xargs -Is sudo -i`, `xargs -Isudo sudo -i` rejected; `xargs -I% git reset %`,
    `xargs -I% chown % bob /` at least `destructive`. Ten nested `env`s around `sudo -i`
    as a proposal: `privileged`, rejected, never lower.
  - **Spec §5 sudo rules.** Rejected: row 21 (`sudo -S true`, `sudo -p x true`,
    `sudo -A true`); row 22 (`echo pw | sudo -S true`); `sudo "-S" true`;
    `sudo $'-S' true`; `sudo "$P" true`; `sudo -s <<<x`; `printf x | sudo -i`; a pipe,
    here-doc or here-string into `sudo`, `su`, `pkexec`, `doas`; `cat <<E | sudo tee /x`
    and `cat <<E | doas id` (pipe reason). Proposals `sudo -i`, `sudo -s`, `sudo su`,
    `sudo bash`, bare `su`, `pkexec bash` rejected; typed, `privileged`.
  - **Decision A:** `foo sudo x` `privileged`, rejected as a proposal; `foo rm -rf x` at
    least `destructive`. ANSI-C words decode like any quoted word: `$'\x73udo' -i`
    rejected as a proposal, `echo pw | $'\x73udo' -S true` rejected,
    `foo $'\x73udo'` `privileged`; brace form `$'\x{73}udo' -i` rejected as a proposal,
    `echo pw | $'\x{73}udo' -S true` rejected, `foo $'\x{73}udo'` `privileged`,
    `$'\x{72}m' -rf build` `destructive`. NUL cut-off (bash stops the word at `\0`):
    `$'sudo\0ignored' -i` rejected as a proposal, `$'rm\0ignored' -rf build`
    `destructive`, `foo $'sudo\0ignored'` `privileged`. **[v3]** Locale quoting decodes
    like `"…"`: `$"sudo" -i` rejected as a proposal, `$"rm" -rf build` `destructive`,
    `foo $"sudo"` `privileged`. Elevation reaching inner commands, rejected as
    proposals: `sudo bash $x`, `sudo env $x bash`, `sudo nice $x bash`,
    `sudo xargs -o bash`, `sudo busybox --pdca`, `sudo script`, `sudo strace bash`,
    `sudo setpriv bash`, `sudo runuser -u root bash`.
  - **Decision D [v3].** All `privileged` with reason "command word the gate cannot read"
    unless a §5 reason is named. Proposals, rejected: `/usr/bin/sud? -i`,
    `/usr/bin/s*do -i`, `/usr/*/sudo -i`, `/usr/bin/{sudo,x} -i`, `x=sudo; $x -i`,
    `$x sudo`, `$(echo sudo) -i`, `` `echo sudo` -i ``, `${x} -i`, `$"$x" -i`, `env "$x" sudo`, `find /usr/bin -name 'sud?' -exec {} -i \;`,
    `ls /usr/bin/sud? | xargs -o -I% % -i`. Typed, rejected with the §5 reason:
    `/usr/bin/s*do -S true`, `$x -p '' true`, `$x -A true`, `$x --stdin true`,
    `echo pw | $x -S true`, `$x -S <<<pw`, `cat <<E | $x tee /x`, `git log | $PAGER`.
    Typed, `privileged`, not rejected: `$x -i`, `$EDITOR f`. Typed `$x rm -rf x` and
    `$(echo rm) -rf ~` `privileged`.
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
    `TARGET_ID = "ubuntu-26.04"` a module-level constant (an earlier attempt drifted to
    "the only folder under `targets/`"; do not repeat). It refuses a resolved path outside
    that root, as `targets.py:153-155` does. Choosing the target from `/etc/os-release` is
    out of scope. Test seam: monkeypatch the loader module's root constant to a
    `tmp_path` with a missing or broken file, and clear the loader's cache. A test reads
    the loader module's source with `ast` inside the test function and fails if it uses
    `os.environ`, `os.getenv`, `Path.cwd`, `os.getcwd`, `Path.home`, `expanduser` or opens
    any path but the fixed one. Test: with a `commands.toml` in cwd saying `sudo` is
    harmless, and `NL_SHELL_COMMANDS`, `NL_SHELL_TARGETS`, `XDG_CONFIG_HOME` pointing at a
    folder with such a file, `sudo -i` stays `privileged`.
  - **Spec §3 builtins (floor only).** Row 33 (`alias ll='ls -l'`) and `unalias`,
    `source`, `.`, `eval`, `exec`, `trap`, `enable`, `set`, `shopt`, `bind`, `complete`,
    `hash`, `builtin`, `command` (except `command -v`/`-V`, `v1.md:101`), `export`,
    `declare`/`typeset`/`local`/`readonly` with assignments, and `unset` are at least
    `session-altering`. (Rows exist here because class 1/2 needs them; child-3 adds the
    name and stored-code rules on top.)
  - **Assertions.** Every case asserts the class (or a floor), the rejected flag where
    stated, a reason substring, and that no reason is "could not class". Exceptions:
    missing/invalid-table cases assert "could not class"; the ten-`env` case accepts the
    engine's reason or "could not class", but never a class below the one stated.
- **Falsifiability:** Plain pytest on this host (Ubuntu 26.04.1, bash 5.3.9, the harness
  `.venv` with tree-sitter-bash). C4 (`engine/scripts/run-verify.sh` in nl-shell-pdca)
  reverts `src/`, `targets/`, `scripts/` and keeps the test, which restores the stub at
  `rules.py:26-28` and removes `commands.toml`/`inventory.toml`. Checked on `main` at Plan:
  `rm -rf build`, `sudo -S true`, `/usr/bin/sud? -i`, `x=sudo; $x -i`, `$"sudo" -i` all
  come out `mutating`, not rejected, as proposals, so every non-floor group goes red. The
  floor group may pass on the stub. Cases are listed inline; read the inventory and table
  inside test functions; import `nl_shell.gate` and any new loader module inside test
  functions (a module-level import of a new API makes the red leg UNVERIFIABLE,
  `run-verify.sh:194-198`).
- **Invariant to restore:** Meaning is closed-world. A command gets a meaning only from
  reviewed data. An unknown command, an undeclared option, or a command word the gate
  cannot read is never silently below the worst meaning it could have at run time.
  ADR-0013, ADR-0015; `policy-gate/v1` §1 step 4, §2, §4–§5, Versioning
  (`v1.md:238-241`); threat model "What must hold" (`.oss-scanner/threat_model.md:121-125`).
- **Repo + branch target:** eduralph/nl-shell @ main
- **Ordering note:** No `Depends on` or `Conflicts with`. This is wave 1 of #197's split;
  #205 and #206 depend on it (their briefs say `Depends on: 204`). `main` has not moved
  since v2 (`1a1e980`).
- **Surfaces:** data
- **Difficulty:** high
- **Scope:** In scope: `src/nl_shell/gate/rules.py` (engine, replacing the stub; decision
  D lives here); a `commands.toml` loader in the style of `src/nl_shell/targets.py:145-160`;
  `targets/ubuntu-26.04/commands.toml` (all rows, including text-runner and builtin rows
  with their text effects, grammar names and name markers declared);
  `targets/ubuntu-26.04/inventory.toml` and `scripts/harvest_inventory.py`;
  `gate-vectors.toml` rows (appended); in `src/nl_shell/gate/__init__.py` only passing
  `origin` (and whatever stdin fact decision D's §5 check needs, already on the
  invocation) to the `rules.classify` call at `:196`; ANSI-C `$'…'` and locale `$"…"`
  decoding **for the command layer only**, cutting `$'…'` at `\0`, used for row lookup,
  option parsing under a row, decision A and decision D. A word counts as readable only
  when that quoting is its sole non-literal cause (today both fall into the "expansion"
  cause at `parse.py:252-253`); an undecodable escape stays unreadable. **`lex_word`
  (`parse.py:197`), `make_word` (`:273-275`) and `Word.literal` do not change**: they
  feed every shell-layer rule, and marking `$'…'` literal there would lower verdicts
  (`ls > $'/etc/x'` from rejected to accepted), which `v1.md:241` forbids. So
  `tests/test_policy_gate.py:517` (`cat $'x'` not literal) stays as is;
  `tests/test_policy_gate.py` expectations this child raises (raise only, never lower;
  e.g. `:192` `$'\x72m' -rf ~` goes from `mutating` to `destructive`, `:193`
  `$(echo rm) -rf ~` from `mutating` to `privileged`; the shell layer still reports
  "command word is not a literal"); spec and threat-model text (raises only, plus the two
  recorded gaps); `tests/test_gate_commands.py`.
  / out of scope: recursion into text, the shared work budget, other `parse.py` changes,
  decision B′, classes 3 and 4 (child-2, #205); protected-variable names and stored code,
  classes 5 and 6 (child-3, #206); resolving what a path command word points to (§7,
  #192 — recorded as a gap here); the walker (#196) except a walker bug a case here
  exposes (say so in build notes); the allowlist, terminal-read rule, here-doc exemption
  (#198); §8 (#190); mixed-script words (#191); confirm UI (#74); REPL wiring (#78); sudo
  passthrough (#13); `systemd-run --user -M root@.host`; the over-rejection of
  `sudo find . -name x` (the operand `.` matches the `.` builtin row; safe, left as is).
  Do not reuse `src/nl_shell/failure_classes.py:199` `is_privileged` (its list at
  `:97-99` may be cited as a class 1 cross-check). Do not port per-command code paths
  (`raw` rows, `_PIECE_SPLIT`, per-builtin special cases). Review contract: a bypass
  inside classes 1, 2, 7, decisions A/C/D or §4/§5 is a defect here; anything else goes
  to the child that owns it or a follow-up.
- **Repro instruction:** In `/home/eddie/nl-shell/nl-shell` on `main`:
  `PYTHONPATH=src /home/eddie/nl-shell/nl-shell-pdca/.venv/bin/python3 -c 'from nl_shell.gate import classify; [print(c, classify(c, origin="proposal")) for c in ["rm -rf build", "sudo -S true", "/usr/bin/sud? -i", "x=sudo; $x -i"]]'`
  gives `mutating`, not rejected, for all four (run at Plan, 2026-10-27).
- **External dependencies:** `tree-sitter-bash`
- **Test file:** tests/test_gate_commands.py
- **Milestone / ADRs:** M0 — REPL prototype. ADR-0013, ADR-0015, ADR-0023.
- **Citations expected:** path:line on `main` for every change. Loader peer:
  `src/nl_shell/targets.py:145-160`. Decision C peer:
  `src/nl_shell/gate/__init__.py:143-157`. Decision D's fail-closed peer is v2's handling
  of an undecodable `$'…'` (privileged, rejected); generalise it, do not add a second
  path.
- **Prior-art check (triage cycles):** By path (`src/nl_shell/gate/rules.py`,
  `targets/ubuntu-26.04/commands.toml`, `scripts/harvest_inventory.py`): only `59ce736`
  (#203, the shell layer that added the stub). `gh pr list --state all`: no open or
  closed-unmerged PR for a command table. Earlier attempts live only in this bundle
  (`iteration-v1/`, `iteration-v2/`) and #189/#197's archived iterations.
- **Disposition hint:** new-feature
- **Plan-review response:** v3 re-plan. Adds decision D (b1), the path-lookup rule, the
  recorded path gap, `$"…"` decoding, and the "with no command" reason assertions. Folds
  v1's sign-off regressions (brace `$'\x{…}'`, xargs replace strings, `sudo -k`,
  non-literal head, ruby/node/awk rows, getopt_long prefixes) into the success criterion
  instead of leaving them as appended carry-forward. Size: split depth 3
  (`split-lineage.json`), so `split --accept` refuses without `--force`; most of the patch
  is table data, and the human kept this slice at both earlier sign-offs.
- **Plan-review response (v3 revision):** (3) Fixed: the `~/bin/x -i` and `~/sudo -i`
  cases now say the command layer does the last-part lookup and gives the path reason
  itself, with the shell layer left frozen, since `leading-tilde` makes `Word.literal`
  False (`parse.py:262-265`, `gate/__init__.py:255-261`, checked). (4) Checked: #189's
  decisions are at `results/issue_189/iteration-v3/brief.md:99-112` (the issue body's
  `results/issue_189/brief.md` is stale), and decision A's "only" limit is in #197's
  body as quoted above. (1, 2) Stands: **where the #204 tracker body and this brief
  differ, this brief governs.** That covers `lex_word`/`make_word`/`Word.literal` staying
  unchanged (the issue says to change `lex_word`; doing so would lower verdicts,
  `v1.md:241`), decision D, the path-lookup rule, the path gap, `$"…"` decoding, and the
  added `ruby`/`node`/`awk` coverage. Check reviewers must grade against this brief, not
  the issue body. Keeping D and the path rules in this child was the human's call at the
  v2 sign-off (the v2 patch was stopped for exactly this hole, `iteration-v2/SUMMARY.md:254`);
  moving them to a follow-up would ship a §5 bypass. The override, including the (b1)
  choice, is now recorded on the tracker:
  https://github.com/eduralph/nl-shell/issues/204#issuecomment-6440748785.

## Iteration 3 — carry-forward (from the previous attempt)
- Sign-off rationale: Core engine and table are sound; keep the slice (size is mostly table data). Fix these in-scope bypasses, each with tests: - Bracket-glob command word with no `/` (`sud[o]`, `[s]udo`, `su[d]o`): tree-sitter-bash misparses it, so decision D never sees the word. Fix the walker/command layer so it is unreadable under D. Tests: typed `echo pw | sud[o] -S true` rejected (§5 reason); typed `sud[o] -i` privileged; proposal `sud[o] -i` rejected with the decision-D reason (not only "unparseable"). - `< /dev/stdin` (and the other `_STDIN_FILES` paths) as stdin counts as a pipe for the §5 rule and decision D (rules.py :385, :466). Tests: `echo x | sudo tee /x < /dev/stdin` and `echo x | $x tee /x < /dev/stdin` rejected, typed and proposal. - Inventory drift: regenerate `targets/ubuntu-26.04/inventory.toml` on the reference host (adds `mount.cifs`, `mount.smb3`) and add both names to the `mount` row. - `$"…"` locale quoting: fail closed. A `$"…"` command word is unreadable under decision D (bash translates it via TEXTDOMAIN/TEXTDOMAINDIR). Update spec §4.1/threat model text that says `$"…"` is read like `"…"`. Tests: `$"ls" -i` proposal rejected; typed `echo pw | $"ls" -S true` rejected; update the existing `$"sudo"` cases to the decision-D reason. - Item 6, option (b): run decision A's argument word scan over the arguments of text-effect rows too (still decision B, no recursion). Tests: typed `eval sudo -S true`, `echo pw | bash -c 'sudo -S true'`, `env -S 'sudo -S true'`, `echo pw | script -qc 'sudo -S true'` privileged and rejected; proposals `eval sudo -i`, `env -S 'sudo -i'` rejected. Keep the threat model's sudo sentence (:121-125) true as written. Out of scope (follow-ups, do not fix here): `hash -p`/`BASH_CMDS` stored lookup (#206); git checkout/stash drop/branch -D and rsync -e destructive rows.
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Core engine and table are sound; keep the slice (size is mostly table data). Fix these in-scope bypasses, each with tests:
  - Bracket-glob command word with no `/` (`sud[o]`, `[s]udo`, `su[d]o`): tree-sitter-bash misparses it, so decision D never sees the word. Fix the walker/command layer so it is unreadable under D. Tests: typed `echo pw | sud[o] -S true` rejected (§5 reason); typed `sud[o] -i` privileged; proposal `sud[o] -i` rejected with the decision-D reason (not only "unparseable").
  - `< /dev/stdin` (and the other `_STDIN_FILES` paths) as stdin counts as a pipe for the §5 rule and decision D (rules.py :385, :466). Tests: `echo x | sudo tee /x < /dev/stdin` and `echo x | $x tee /x < /dev/stdin` rejected, typed and proposal.
  - Inventory drift: regenerate `targets/ubuntu-26.04/inventory.toml` on the reference host (adds `mount.cifs`, `mount.smb3`) and add both names to the `mount` row.
  - `$"…"` locale quoting: fail closed. A `$"…"` command word is unreadable under decision D (bash translates it via TEXTDOMAIN/TEXTDOMAINDIR). Update spec §4.1/threat model text that says `$"…"` is read like `"…"`. Tests: `$"ls" -i` proposal rejected; typed `echo pw | $"ls" -S true` rejected; update the existing `$"sudo"` cases to the decision-D reason.
  - Item 6, option (b): run decision A's argument word scan over the arguments of text-effect rows too (still decision B, no recursion). Tests: typed `eval sudo -S true`, `echo pw | bash -c 'sudo -S true'`, `env -S 'sudo -S true'`, `echo pw | script -qc 'sudo -S true'` privileged and rejected; proposals `eval sudo -i`, `env -S 'sudo -i'` rejected. Keep the threat model's sudo sentence (:121-125) true as written.
  Out of scope (follow-ups, do not fix here): `hash -p`/`BASH_CMDS` stored lookup (#206); git checkout/stash drop/branch -D and rsync -e destructive rows.
- Full previous attempt preserved in `iteration-v3/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 4 — carry-forward (from the previous attempt)
- Sign-off rationale: Rebuild the same slice; fix the v4 Check findings, keep the v3 brief's design. 1. Slowdown (C4/T3 red): `_bracket_command` (parse.py:678-708) rescans per ERROR node -> quadratic. 8 KiB `$[` goes 0.43 s -> 5.85 s, `[$[` 19 s. Compute word starts/ends once per source, make `_unquoted_bracket` linear, cache misses too. Do not loosen the 5 s test. 2. Bypass: `coproc sud[o] -i` / typed `echo pw | coproc sud? -S true` not rejected. Give `coproc` a runs-command-at row (or equivalent) so decision D reaches its command word. Add both tests. 3. Bypass: `{ sud[o] -i; }`, `echo pw | { sud[o] -S true; }`, `f() { sud[o] -i; }; f` not caught. The ERROR node starts at `{`; check every word start inside the node (skip leading reserved words), not only node.start_byte. Add tests. 4. Bypass (High): attached / `=` text-option values are not scanned: `env -S'sudo -i'`, `env --split-string='sudo -i'`, `script -c'sudo -i'`, `script --command='sudo -i'`, and piped `-S true` forms. Scan the parsed option values, not the raw argv words. Add tests for the attached and `=` forms of every text option on a runs-text row, typed-with-pipe and proposal. 5. Unreadable first word in text-effect scan (`eval 'sud? -i'`, `bash -c 'sud[o] -i'`, `env -S 'sud? -i'`): treat it as decision D's unreadable word in `_text_scan` (rules.py:527-531) so the threat-model sudo sentence stays true. Not decided at this sign-off: opaque wrappers with no row (`chrt 1 sud? -i`, ionice, taskset, nsenter, ...) and the double-unquoting `eval "\$'\\x73udo' -i"` case (child-2 / #205). Follow the brief as written for these. Human chose iterate-do over the size backstop's iterate-plan suggestion (patch 232 KB, attempt 4).
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Rebuild the same slice; fix the v4 Check findings, keep the v3 brief's design.
  1. Slowdown (C4/T3 red): `_bracket_command` (parse.py:678-708) rescans per ERROR node -> quadratic. 8 KiB `$[` goes 0.43 s -> 5.85 s, `[$[` 19 s. Compute word starts/ends once per source, make `_unquoted_bracket` linear, cache misses too. Do not loosen the 5 s test.
  2. Bypass: `coproc sud[o] -i` / typed `echo pw | coproc sud? -S true` not rejected. Give `coproc` a runs-command-at row (or equivalent) so decision D reaches its command word. Add both tests.
  3. Bypass: `{ sud[o] -i; }`, `echo pw | { sud[o] -S true; }`, `f() { sud[o] -i; }; f` not caught. The ERROR node starts at `{`; check every word start inside the node (skip leading reserved words), not only node.start_byte. Add tests.
  4. Bypass (High): attached / `=` text-option values are not scanned: `env -S'sudo -i'`, `env --split-string='sudo -i'`, `script -c'sudo -i'`, `script --command='sudo -i'`, and piped `-S true` forms. Scan the parsed option values, not the raw argv words. Add tests for the attached and `=` forms of every text option on a runs-text row, typed-with-pipe and proposal.
  5. Unreadable first word in text-effect scan (`eval 'sud? -i'`, `bash -c 'sud[o] -i'`, `env -S 'sud? -i'`): treat it as decision D's unreadable word in `_text_scan` (rules.py:527-531) so the threat-model sudo sentence stays true.
  Not decided at this sign-off: opaque wrappers with no row (`chrt 1 sud? -i`, ionice, taskset, nsenter, ...) and the double-unquoting `eval "\$'\\x73udo' -i"` case (child-2 / #205). Follow the brief as written for these.
  Human chose iterate-do over the size backstop's iterate-plan suggestion (patch 232 KB, attempt 4).
- Failing gate: C4 fix verified: bundle test red pre-fix, green post-fix (pytest) — C4 FAIL — bundle test red (or not importable) WITH the fix applied
- Failing gate: T3 runtime: the whole nl-shell pytest suite on the patched worktree — T3 FAIL — nl-shell suite red (pytest exit 1)
- Full previous attempt preserved in `iteration-v4/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

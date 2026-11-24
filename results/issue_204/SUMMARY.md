# Result — issue 204 / gate-command-table-engine

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: On `main` (`1a1e980`, #196 merged) the gate's command layer is a
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
- Success criterion: `tests/test_gate_commands.py` passes. Every case goes through the
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
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: In scope: `src/nl_shell/gate/rules.py` (engine, replacing the stub; decision
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

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (251 of 498 failed), green with it
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

Review issue #204: replace the command-classification stub with a reviewed command table and generic engine enforcing decisions A–D and policy §4–§5.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The brief defines observable classes, rejection rules, accepted gaps and iteration regressions; locale quoting follows the later carry-forward requirement (brief.md:174, brief.md:396, brief.md:409). |
| C2 Reproduction (red pre-fix) | PASS | Frozen execution demonstrates substantive pre-fix assertion failures, including sudo-rs remaining mutating; the red leg has 251 failures, 247 passes and 12 setup errors, rather than relying solely on missing new APIs (gate-logs/C4-verify.log:11818). |
| C3 Change | PASS | The reviewed source supplies a generic row-driven engine, fixed-location validated loader and bounded bracket-glob recovery within the authorized scope (target/src/nl_shell/gate/rules.py:413, target/src/nl_shell/gate/commands.py:325, target/src/nl_shell/gate/parse.py:740). |
| C4 Verification (red→green) | PASS | Frozen gate output records 510 green targeted tests and 251 pre-fix assertion failures; independent execution is unavailable because local python3 lacks pytest and tree_sitter, so this verdict rests on captured gate execution (gate-logs/C4-verify.log:10, gate-logs/C4-verify.log:11818). |
| C5 Causal adequacy | PASS | The engine replaces the absent command semantics and recovers command words the parser misreads; no optional-capability probe masks a load-time cause, and accepted text/path gaps remain explicit (target/src/nl_shell/gate/rules.py:413, target/src/nl_shell/gate/parse.py:740, target/.oss-scanner/threat_model.md:228). |
| T1 Structure | PASS | Row validation and command interpretation have separate responsibilities, while wrapper recursion has an explicit bound and bracket recovery charges work (target/src/nl_shell/gate/commands.py:349, target/src/nl_shell/gate/rules.py:414, target/src/nl_shell/gate/parse.py:777). |
| T2 Shape | PASS | Security policy documentation covers unreadable command words, text scanning and retained gaps; independently regenerated inventory is byte-identical, including CIFS/SMB mount aliases (target/.oss-scanner/threat_model.md:194, target/targets/ubuntu-26.04/commands.toml:1007, gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen full-suite execution reports 1643 passed, one skipped and five forkpty deprecation warnings; local runtime reproduction is blocked by missing test/parser packages, not a demonstrated patch failure (gate-logs/T3-suite.log:34, gate-logs/T3-suite.log:44). |
| T4 Contribution | N/A | Contribution artifacts are intentionally absent during Check; the deferred audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm the affected-path search covers merged history and closed/rejected work before treating the contribution as new — the brief records that search, but this target has only a synthetic base commit and no remote to independently corroborate it (brief.md:365). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the documented conservative rejections and accepted path/text gaps are suitable for this milestone — automated classification tests and a matching host inventory cannot establish operational fitness (brief.md:81, brief.md:104, target/.oss-scanner/threat_model.md:228). |

Verification details: attempted `python -m pytest` (python unavailable), then `python3 -m pytest -q tests/test_gate_commands.py tests/test_policy_gate.py tests/test_targets.py` (pytest unavailable). A direct import also confirms tree_sitter is unavailable. Therefore no local stash/red/pop/green sequence was attempted after discovering the missing toolchain; the target patch remains untouched. The frozen logs show the real parser-dependent tests executed successfully, so the dependency was exercised by the gate despite its absence from this reviewer environment.

Independently ran `python3 target/scripts/harvest_inventory.py --output inventory-review.toml` on Ubuntu 26.04.1 and `diff -u target/targets/ubuntu-26.04/inventory.toml inventory-review.toml`; exit 0 with no differences. Inspected affected-path git history: only synthetic base commit `39fa2e0` is available; `git remote -v` returns no entries. No INTEGRATION.md was present in the supplied target. No implementation defect was established by this review.
<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 204 / gate-command-table-engine (attempt 5)

I re-ran the patched classifier at `$PDCA_TARGET` with the harness venv and tried about 300 inputs. The evidence holds up. C4's red leg is real: 251 failures plus 12 import errors across 55 test functions, and the floor group goes red too. Every case calls the public `classify()`. `scripts/harvest_inventory.py`, re-run into my scratch folder on this host (26.04.1), matches the checked-in `inventory.toml` byte for byte. All five v4 sign-off items work on the exact inputs named at sign-off. Near variants of item 5 still get through, and the new text scan brings back the slowdown that v4 was stopped for.

- NEEDS-HUMAN [impl] — v4 item 5 is only half done: a wrapper or `exec` in front of an unreadable command word in code text hides it. `_text_scan` (`src/nl_shell/gate/rules.py:599-614`) checks only the first word of each segment, past the words in `_TEXT_LEAD` (`rules.py:344-347`), and that set has no `exec`, `command`, `builtin`, `env`, `nice`, `nohup`, `sudo` and so on. Proposals that come out `destructive` and are **not rejected**: `eval 'exec sud? -i'`, `eval 'command sud? -i'`, `eval 'env $x -i'`, `bash -c 'nice sud? -i'`, `env -S'nice sud? -i'`, `script -qc 'nice sud? -i'`. Typed §5 bypass: `echo pw | bash -c 'nice sud? -S true'` and `echo pw | eval 'env $x -S true'` come out `destructive`, rejected=False. The same words at top level (`nice sud? -i`) are rejected, and the threat model (`.oss-scanner/threat_model.md:227-228`) says an unreadable command word in code text is decision D. Fix: run the D check on every word of the segment, or at least on every word after a readable word that names a `runs-command-at` row. Add these cases to the test.
- NEEDS-HUMAN [impl] — The text splitter does not treat a newline as a command separator. `_TEXT_SEPARATORS = ";&|()<>"` (`rules.py:298`), and `text_words` splits on whitespace, so `\n` just separates words. The proposal `eval $'true\nsud? -i'` is `destructive`, not rejected, while `eval 'true;sud? -i'` is rejected. `bash -c` text across several lines is the normal case for this bypass. Add `\n` as a separator, here and in spec `v1.md:265`.
- NEEDS-HUMAN [impl] — Backticks are replaced by a space (`rules.py:307`), so a command substitution inside code text never starts a segment. The proposal ``eval 'echo `sud? -i`'`` is `destructive`, not rejected. The `$(…)` form (`eval 'echo $(sud? -i)'`) is rejected, so the two spellings disagree. Treat a backtick as a separator.
- NEEDS-HUMAN [impl] — The new text scan takes quadratic time and breaks the 5 s budget that v4 was stopped for. For each elevating word in a segment, `_text_scan` calls `_rejecting_options(row.grammar, segment[k + 1:], …)` (`rules.py:583-596`), so it re-parses the whole rest of the segment every time. Timings on this host, all under the 8 KiB cap: `bash -c '` + `'sudo -ux '*905` + `'` (8155 B) takes **6.9 s**; `'sudo -i '*1015` takes 5.0 s; `'sudo -u x '*815` takes 4.0 s. `tests/test_policy_gate.py:711-716` checks only `$[`, `a=(`, `${`, so the gate stays green. Fix: stop each scan at the next elevating word, or scan the segment once. Add a 5 s size-cap case for code text full of `sudo`.
- NEEDS-HUMAN [impl] — The bracket-glob repair gives a false "pipe" reason and over-rejects typed input. `_bracket_command` hands the new invocation `stdin=ctx.stdin` (`src/nl_shell/gate/parse.py:781`), which is "unknown" at an ERROR node, and `fed()` counts unknown as fed (`rules.py:288-291`). So typed `sud[o] -i`, `{ sud[o] -i; }` and `( sud[o] -i )` are rejected with "pipe, here-doc or here-string into a command word the gate cannot read" when nothing is piped. Typed `$x -i` and `{ $x -i; }` are correctly privileged and not rejected. Failing closed is safe, but the reason is wrong, and the brief's typed decision-D rule ("privileged, not rejected") is not applied the same way to both spellings. Either take the real pipe fact for the word or use a reason that says the parse failed.
- NEEDS-HUMAN [human] — The decision-A scan of non-shell code (`text_words`, `rules.py:301-321`) catches some interpreter calls only by luck, while the threat model (`threat_model.md:223-227`) states it as a rule. These get caught: `python3 -c 'os.system("sudo -i")'`, `node -e …spawn("sudo",…)`, `ruby -e 'system("sudo -S true")'`. These do not, because the comma glues the words together (`sudo,-i`): proposals `perl -e 'exec "sudo","-i"'` and `ruby -e 'exec("sudo","-i")'` (`destructive`, not rejected), and typed `echo pw | perl -e 'exec "sudo","-S","true"'` (not rejected). Pipes and here-strings *inside* bash text are not seen either: typed `bash -c 'echo pw|sudo true'`, `bash -c 'sudo true <<< pw'` and `eval 'sudo true < /dev/stdin'` are privileged but not rejected, because the scan only checks the outer stdin (`rules.py:593`). The brief leaves text as decision B, and child-2 (#205) does the parsing. So a human should decide whether to accept these, and should either record them in the threat model's accepted-gap list or narrow the wording at `:223-228`, which currently reads as a promise.
- Not filed as a defect, for context only: `chrt 1 sud? -i` (and likewise `X sud? -i`, `coproc X sud? -i`, where bash's `coproc NAME` before a simple command makes `X` the command word) is `mutating`, not rejected. The v4 sign-off left "opaque wrappers with no row" undecided and said to follow the brief, and the brief's decision A only reads arguments that name a row. Named-row wrappers (`ionice`, `taskset`, `nsenter` with literal `sudo`) are caught.

Attempted to refute and could not: §5 option spellings (bundled, attached, quoted, ANSI-C, `--stdi`/`--pr`/`--a` prefixes, `-u -S`, `-k$x`), stdin forms (`<&0`, `0</dev/stdin`, `/proc/self/fd/0`, `|&`, subshells, `<<<`), path lookup (`//usr/bin/sudo`, `/usr/bin/./sudo`, `~/sudo`, `s\udo`, `su''do`), decision D through every named wrapper (`env -C/-u/--chdir=`, `timeout -k`, `exec -a`, `command -p`, `time -p`, `strace -o`, `setpriv`, `runuser`, `unshare`, `chroot`, `flock`, `setsid -f`, `watch`), xargs and find placeholders (`-I{}`, `-iX`, `--replace=@`, `-ok`, `-okdir`, `/usr/bin/{}`, `{}x`), elevation reaching inner commands, and the inventory drift check.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory): issue 204, gate command table and engine

**Attacker-reachable inputs this diff touches:** the model's proposal (threat model input 5) and typed `\cmd` input, both of which pass through `nl_shell.gate.classify`. The new engine (`src/nl_shell/gate/rules.py`) and table (`targets/ubuntu-26.04/commands.toml`) now decide the class and the reject flag for every simple command. The table loader reads a fixed, trusted path. `scripts/harvest_inventory.py` is a dev-host script that only runs `dpkg-query`.

Rated on the scale in `.oss-scanner/threat_model.md` ("How we rate severity"). I tested every finding by running the patched gate at `$PDCA_TARGET` (`classify(cmd, origin=...)`) with the harness venv.

## Findings

- NEEDS-HUMAN [impl] — **High** (a privileged step classed lower; §5 bypass). `src/nl_shell/gate/rules.py:298` and `:597-614`. The scan for unreadable command words in code text (decision D in `_text_scan`) treats `<` and `>` as command separators. After a redirect, the redirect *target* becomes the "first word", and the real command word is never checked. The patched threat model says a command word in code text that the gate cannot read is decision D (`.oss-scanner/threat_model.md:238-239`), but for this form that is false. Who controls it: the model (proposal) or the user (typed). Reproducers on the patched tree:
  - proposal `bash -c '>/dev/null sud? -i'` gives `destructive`, not rejected (expected: `privileged`, rejected).
  - The same happens with `bash -c '</dev/null sud? -i'` and `eval '>x sud? -i'`.
  - typed `echo pw | bash -c '2>/dev/null sud? -S true'` gives `destructive`, not rejected, so a pipe feeds `sudo -S`.

  A literal `sudo` in the same spot is caught (`bash -c '>/dev/null sudo -S true'` is rejected), so only the decision-D path has the hole. Fix: skip redirect operators and their targets before taking the command word. Add these cases to `tests/test_gate_commands.py`; it has none today.

- NEEDS-HUMAN [impl] — **High** (same class of bypass). `src/nl_shell/gate/rules.py:307` replaces every backtick with a space before splitting, so the backtick in `_UNREADABLE_IN_TEXT` (`:350`) can never match. A command word built by command substitution joined to literal text is split into harmless-looking words. Bash runs the joined word: I checked that `` bash -c '`printf ech`o hi' `` prints `hi` on bash 5.3.9. Reproducers:
  - proposal `` eval '`printf sud`o -i' `` gives `destructive`, not rejected.
  - proposal `` bash -c '`printf sud`o -i' `` gives the same.
  - typed `` echo pw | eval '`printf sud`o -S true' `` gives `destructive`, not rejected.

  The `$(…)` form (`eval '$(printf sud)o -i'`) is caught, because the lone `$` becomes its own first word. Fix: mark a backtick in the text as unreadable instead of erasing it. There is no test for it today.

- NEEDS-HUMAN [human] — **High** if this patch owns it. `src/nl_shell/gate/rules.py:344-347`: `_TEXT_LEAD` lists reserved words only. When code text starts with a wrapper that has its own row, the unreadable word after it is not checked: proposals `bash -c 'exec sud? -i'`, `bash -c 'command sud[o] -i'`, `bash -c 'env sud? -i'`, `bash -c 'nice sud? -i'` and `bash -c 'time -p sud? -i'` all give `destructive`, not rejected. Typed `echo pw | bash -c 'exec sud[o] -S true'` is not rejected either. This is the same promise as the two findings above (threat model `:238-239`). Fixing it means either following `runs-command-at` rows inside text, which the brief calls recursion and gives to #205, or listing wrapper names as leads. A human should decide whether that belongs here or in #205. If it is deferred, the threat-model sentence should name the gap.

- NEEDS-HUMAN [impl] — **High** (a privileged step classed `mutating`; §5 bypass). The bash builtins `mapfile` and `readarray` have no row in `targets/ubuntu-26.04/commands.toml`, but `-C` evaluates its argument as bash code, just as `eval`, `trap`, `complete -C` and `bind -x` do (those got rows). Reproducers:
  - proposal `mapfile -c 1 -C 'sudo -i' a < f` gives `mutating` ("not allowlisted"), not privileged and not rejected.
  - typed `printf 'a\npw\n' | mapfile -c 1 -C 'sudo -S true' a` gives `mutating`, not rejected.

  I checked on bash 5.3.9 that the callback reads the remaining pipe: `printf 'a\nSECRET\n' | mapfile -c 1 -C 'read v; echo $v' x` prints `SECRET`. In the threat model's wording this falls under the accepted gap "an unknown command given command text as one quoted word". But this is a bash builtin, next to builtin rows this patch already adds, so the fix is one row (`names = ["mapfile", "readarray"]`, `-C` as `runs-text` bash with a value, `-c`/`-n`/`-O`/`-s`/`-u`/`-d` declared). `fc -s`/`fc -e` (which re-run history) may need the same look, but I did not confirm it against nl-shell's history setup.

- NEEDS-HUMAN [human] — **unrated (design scope)**. Shells and interpreters that are not on the reference host have no row, so under `sudo` a proposal is only `privileged` (confirm), not rejected as a root shell: `sudo fish`, `sudo ksh`, `sudo tcsh`, `sudo lua`, `sudo python3.14t` and `sudo ipython3` are all `privileged`, `rejected=False`. This matches the stated design ("every … binary on the reference host has a row"), and the confirm still holds. A user who installed one of these packages gets weaker proposal rejection, though. A human should decide whether the reference-host inventory is enough or whether names from common Ubuntu shell/interpreter packages should be added.

## Checked, no finding

- **sudo grammar (§5).** I tried bundled and attached forms (`-kS`, `-Sk`, `-uroot -S`, `--user=root -S`), long prefixes (`--stdi`, `--pro`), quoted and backslash spellings (`s\udo -S`, `"-S"`), `/usr/lib/cargo/bin/sudo`, `./sudo`, `\sudo`, and a pipe, here-string or `< /dev/stdin` into sudo through the `timeout`, `find -exec`, `env`, `nice`, `xargs -o` and `coproc` wrappers. All were rejected or `privileged` as expected. Every undeclared option on the sudo row is rejected, which closes the getopt-prefix route.
- **Wrappers with rows.** I checked `env` (`-C`, `--chdir=`, `-u`, `-i`, `-S`/`-vS`/`-iS'…'`/`--split-string`), `nice -n -5`/`-n-5`/`-5`/`--adjustment=`, `timeout -k`/`--signal=`/`--foreground`, `xargs -a`/`-n1`/`-d`, `find -exec`/`-execdir`/`-ok`, `watch` (with `-x`, `--`, and joined text), `time -p`, `command [-p]`, `exec [-c|-l]`, `builtin exec`, `nohup`, `stdbuf`, `setsid`, `strace` (`-f`, `-o`), `ssh-agent`, `screen`, `tmux`, `x-terminal-emulator -e`, `ptyxis --`, `busybox su`/`sh -c`, and `systemd-run`/`run0`/`machinectl shell`/`doas`. Each reached the inner `sudo` correctly. No-row wrappers (`chrt`, `taskset`, `nsenter`, `ltrace`, `valgrind`) are caught by decision A for a literal or path `sudo` argument.
- **Elevation reaching inner commands.** `sudo -u root env bash`, `sudo env -- bash`, `sudo nice -- bash`, `sudo timeout 5 bash`, `sudo find . -exec bash \;`, `sudo xargs bash` and `sudo git -c core.pager=sh log` are all rejected as proposals.
- **ANSI-C decoding.** I compared `readable()` with bash 5.3.9 on 25 edge cases (`\x{…}` with long or empty digits, octal over 3 digits, `\c`, `\u`/`\U`, NUL cut-off, joined quotes). It matches bash on every case that could spell an ASCII command name. The only differences are bytes 0x80 and up (a Latin-1 char where bash gives a raw byte, which cannot form a row name) and one case where the gate returns None, which fails closed.
- **Resource use.** Inputs near the 8 KiB limit (2,700 `-S` flags on sudo, 1,150 `--stdi` after `$x`, 2,000 nested `env`, 800 nested `timeout`, 500 `find -exec`, 2,700 xargs replace words, 1,000-command `bash -c` text, an 8 KB `\x{` escape) each classify in 0.15 s or less. Nesting past 32 gives "could not class".
- **Loader.** `commands.py:325` reads only `TARGETS_ROOT / TARGET_ID / commands.toml` and refuses a resolved path outside the root. It uses no environment variable, cwd or HOME.
- **Not raised (outside this child's scope, and not made worse):** `env SUDO_PROMPT=x sudo true` and `env SUDO_ASKPASS=… sudo true` are `privileged` but not rejected, while the shell-layer prefix form is rejected. That breaks the "overrides of `SUDO_PROMPT`" sentence in the threat model, but protected-variable names belong to #206, and these forms were `mutating` before the patch too. Also not raised: the double-unquoting `eval "\$'\\x73udo' -i"` case and no-row wrappers with an unreadable word (`chrt 1 sud? -i`), which the sign-off explicitly left undecided.

## Side effect of this review

The target checkout now has git-ignored bytecode caches (`src/nl_shell/__pycache__/`, `src/nl_shell/gate/__pycache__/`, dated 12:36:55 today). They were most likely written when I first imported the gate from `$PDCA_TARGET/src`. They are untracked and change no behaviour; the harness may want to clear them.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T5 Judgment — Confirm the affected-path search covers merged history and closed/rejected work before treating the contribution as new — the brief records that search, but this target has only a synthetic base commit and no remote to independently corroborate it (brief.md:365).
- [ ] Validation — fitness-to-purpose — Decide whether the documented conservative rejections and accepted path/text gaps are suitable for this milestone — automated classification tests and a matching host inventory cannot establish operational fitness (brief.md:81, brief.md:104, target/.oss-scanner/threat_model.md:228).
- [ ] v4 item 5 is only half done: a wrapper or `exec` in front of an unreadable command word in code text hides it. `_text_scan` (`src/nl_shell/gate/rules.py:599-614`) checks only the first word of each segment, past the words in `_TEXT_LEAD` (`rules.py:344-347`), and that set has no `exec`, `command`, `builtin`, `env`, `nice`, `nohup`, `sudo` and so on. Proposals that come out `destructive` and are **not rejected**: `eval 'exec sud? -i'`, `eval 'command sud? -i'`, `eval 'env $x -i'`, `bash -c 'nice sud? -i'`, `env -S'nice sud? -i'`, `script -qc 'nice sud? -i'`. Typed §5 bypass: `echo pw | bash -c 'nice sud? -S true'` and `echo pw | eval 'env $x -S true'` come out `destructive`, rejected=False. The same words at top level (`nice sud? -i`) are rejected, and the threat model (`.oss-scanner/threat_model.md:227-228`) says an unreadable command word in code text is decision D. Fix: run the D check on every word of the segment, or at least on every word after a readable word that names a `runs-command-at` row. Add these cases to the test.
- [ ] The text splitter does not treat a newline as a command separator. `_TEXT_SEPARATORS = ";&|()<>"` (`rules.py:298`), and `text_words` splits on whitespace, so `\n` just separates words. The proposal `eval $'true\nsud? -i'` is `destructive`, not rejected, while `eval 'true;sud? -i'` is rejected. `bash -c` text across several lines is the normal case for this bypass. Add `\n` as a separator, here and in spec `v1.md:265`.
- [ ] Backticks are replaced by a space (`rules.py:307`), so a command substitution inside code text never starts a segment. The proposal ``eval 'echo `sud? -i`'`` is `destructive`, not rejected. The `$(…)` form (`eval 'echo $(sud? -i)'`) is rejected, so the two spellings disagree. Treat a backtick as a separator.
- [ ] The new text scan takes quadratic time and breaks the 5 s budget that v4 was stopped for. For each elevating word in a segment, `_text_scan` calls `_rejecting_options(row.grammar, segment[k + 1:], …)` (`rules.py:583-596`), so it re-parses the whole rest of the segment every time. Timings on this host, all under the 8 KiB cap: `bash -c '` + `'sudo -ux '*905` + `'` (8155 B) takes **6.9 s**; `'sudo -i '*1015` takes 5.0 s; `'sudo -u x '*815` takes 4.0 s. `tests/test_policy_gate.py:711-716` checks only `$[`, `a=(`, `${`, so the gate stays green. Fix: stop each scan at the next elevating word, or scan the segment once. Add a 5 s size-cap case for code text full of `sudo`.
- [ ] The bracket-glob repair gives a false "pipe" reason and over-rejects typed input. `_bracket_command` hands the new invocation `stdin=ctx.stdin` (`src/nl_shell/gate/parse.py:781`), which is "unknown" at an ERROR node, and `fed()` counts unknown as fed (`rules.py:288-291`). So typed `sud[o] -i`, `{ sud[o] -i; }` and `( sud[o] -i )` are rejected with "pipe, here-doc or here-string into a command word the gate cannot read" when nothing is piped. Typed `$x -i` and `{ $x -i; }` are correctly privileged and not rejected. Failing closed is safe, but the reason is wrong, and the brief's typed decision-D rule ("privileged, not rejected") is not applied the same way to both spellings. Either take the real pipe fact for the word or use a reason that says the parse failed.
- [ ] The decision-A scan of non-shell code (`text_words`, `rules.py:301-321`) catches some interpreter calls only by luck, while the threat model (`threat_model.md:223-227`) states it as a rule. These get caught: `python3 -c 'os.system("sudo -i")'`, `node -e …spawn("sudo",…)`, `ruby -e 'system("sudo -S true")'`. These do not, because the comma glues the words together (`sudo,-i`): proposals `perl -e 'exec "sudo","-i"'` and `ruby -e 'exec("sudo","-i")'` (`destructive`, not rejected), and typed `echo pw | perl -e 'exec "sudo","-S","true"'` (not rejected). Pipes and here-strings *inside* bash text are not seen either: typed `bash -c 'echo pw|sudo true'`, `bash -c 'sudo true <<< pw'` and `eval 'sudo true < /dev/stdin'` are privileged but not rejected, because the scan only checks the outer stdin (`rules.py:593`). The brief leaves text as decision B, and child-2 (#205) does the parsing. So a human should decide whether to accept these, and should either record them in the threat model's accepted-gap list or narrow the wording at `:223-228`, which currently reads as a promise.
- [ ] **High** (a privileged step classed lower; §5 bypass). `src/nl_shell/gate/rules.py:298` and `:597-614`. The scan for unreadable command words in code text (decision D in `_text_scan`) treats `<` and `>` as command separators. After a redirect, the redirect *target* becomes the "first word", and the real command word is never checked. The patched threat model says a command word in code text that the gate cannot read is decision D (`.oss-scanner/threat_model.md:238-239`), but for this form that is false. Who controls it: the model (proposal) or the user (typed). Reproducers on the patched tree:
- [ ] **High** (same class of bypass). `src/nl_shell/gate/rules.py:307` replaces every backtick with a space before splitting, so the backtick in `_UNREADABLE_IN_TEXT` (`:350`) can never match. A command word built by command substitution joined to literal text is split into harmless-looking words. Bash runs the joined word: I checked that `` bash -c '`printf ech`o hi' `` prints `hi` on bash 5.3.9. Reproducers:
- [ ] **High** if this patch owns it. `src/nl_shell/gate/rules.py:344-347`: `_TEXT_LEAD` lists reserved words only. When code text starts with a wrapper that has its own row, the unreadable word after it is not checked: proposals `bash -c 'exec sud? -i'`, `bash -c 'command sud[o] -i'`, `bash -c 'env sud? -i'`, `bash -c 'nice sud? -i'` and `bash -c 'time -p sud? -i'` all give `destructive`, not rejected. Typed `echo pw | bash -c 'exec sud[o] -S true'` is not rejected either. This is the same promise as the two findings above (threat model `:238-239`). Fixing it means either following `runs-command-at` rows inside text, which the brief calls recursion and gives to #205, or listing wrapper names as leads. A human should decide whether that belongs here or in #205. If it is deferred, the threat-model sentence should name the gap.
- [ ] **High** (a privileged step classed `mutating`; §5 bypass). The bash builtins `mapfile` and `readarray` have no row in `targets/ubuntu-26.04/commands.toml`, but `-C` evaluates its argument as bash code, just as `eval`, `trap`, `complete -C` and `bind -x` do (those got rows). Reproducers:
- [ ] **unrated (design scope)**. Shells and interpreters that are not on the reference host have no row, so under `sudo` a proposal is only `privileged` (confirm), not rejected as a root shell: `sudo fish`, `sudo ksh`, `sudo tcsh`, `sudo lua`, `sudo python3.14t` and `sudo ipython3` are all `privileged`, `rejected=False`. This matches the stated design ("every … binary on the reference host has a row"), and the confirm still holds. A user who installed one of these packages gets weaker proposal rejection, though. A human should decide whether the reference-host inventory is enough or whether names from common Ubuntu shell/interpreter packages should be added.
- [x] **The brief contradicts the tracker's scope on `parse.py`, and the issue body was not updated.** The tracker (notes.json, Scope) says: "in `src/nl_shell/gate/parse.py` **only** `lex_word` (`:197`): decode ANSI-C `$'…'` quoting as bash does". It also says `test_policy_gate.py:192` goes "from `mutating` \"command word is not a literal\" to `destructive`". The brief says the opposite: "**`lex_word` (`parse.py:197`), `make_word` (`:273-275`) and `Word.literal` do not change**", and "the shell layer still reports 'command word is not a literal'". The brief's reason holds against the source: `make_word` sets `literal=not causes` (`parse.py:275`), and that flag feeds every redirect and shell rule, so changing it would lower verdicts. The brief's choice is right, but #204's body still describes the other design. A Check reviewer or code-review leaf that grounds on the issue thread will flag a correct patch as off-scope, or a builder will follow the issue instead. Before Do, record that the brief overrides this point, for example in a tracker comment.
- [x] **Most of v3 is not in the tracker.** These are absent from the #204 body: decision D, the path-lookup rule, the recorded path gap, `$"…"` decoding, and the extra coverage rows (`ruby`, `node`, `awk`/`mawk`/`gawk`). The body's decisions stop at A and C, and its inventory list is "`python3*`, `perl*`, `busybox`, `gdb`". The brief says D is the human's choice at the v2 sign-off ("decision D, option (b1)"). That choice only exists in `iteration-v2/`, which is not among my inputs, so I cannot verify it from the thread. Together these add a third decision, two spec gaps and new spec/threat-model sections to a slice already at split depth 3 ("`split --accept` refuses without `--force`"). The human should confirm that D plus the path rules belong in this child and not in a follow-up. They should also have the tracker body updated so it matches what Check will hold the patch to.
- [x] **The `~/bin/x -i` path-gap case cannot get the asserted reason from the layer the brief points at.** The class-7 group asserts that `./x -i`, `/tmp/x -i` and `~/bin/x -i` have a "reason includes 'path outside the system directories'". In the source, `lex_word` adds the cause `leading-tilde` for a leading `~/` (`parse.py:262-265`), so `Word.literal` is False. `_shell_rules` therefore takes the `not word.literal` branch and gives "command word is not a literal: ~/bin/x" (`gate/__init__.py:255-256`). The `elif` that gives "path outside the system directories" (`:257-261`) is never reached. The brief freezes `lex_word`, `make_word` and `:255-256` ("stay as they are"). So the expected reason can only come from the command layer, and nothing in the brief says the engine must emit it. The brief only says such a word "is a path outside the system directories (the known gap below)". Either state that `rules.classify` emits that reason for a word whose only cause is a leading `~`, or loosen the assertion for `~/bin/x -i`. If neither is done, Do will either fail this case or touch the frozen shell rule. The same applies to `~/sudo -i` in the path-lookup case: it hits the `sudo` row only if the command layer strips the leading `~` before taking the last path part, and the brief should say so explicitly.
- [x] **Two provenance citations cannot be checked from the record.** Decision A's added limit ("applies **only** to a command with neither a row nor an allowlist entry (#197's tracker body says so)") is cited to #197's tracker. The decisions are cited to `results/issue_189/iteration-v3/brief.md:99-112`, while this issue's body cites `results/issue_189/brief.md:99-112`. Neither file is in the inputs, and the two paths disagree. The decision-A limit is load-bearing because it is what lets `man sudo` etc. come out `privileged` without new rows. If it is wrong, the accepted over-raise and the "do not add rows" rule rest on nothing. Check the citations against the real #197 and #189 files before sign-off.
- [ ] size backstop — this slice is behaving oversized: patch is 248 KB (threshold 100 KB); 2 round(s) already spent (threshold 2). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: discontinued
- Iteration delta (if iterating): Paused to rethink the strategy. Attempt 5, patch 248 KB: the core table and engine held up, but each round the code-text scan (sudo inside bash -c / eval / env -S text) shows new bypasses and the slowdown is back. Revisit how to slice #204 vs #205 before building again.
- By / date: Eduard Ralph / 2026-10-26

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 4 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

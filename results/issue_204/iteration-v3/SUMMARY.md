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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (203 of 441 failed), green with it
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

Review issue #204: replace the command-classification stub with a reviewed command table and generic argv engine, including fail-closed handling of unreadable command words.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The v3 contract defines unreadable-command rejection, accepted path/text gaps and the boundary with later children; target/docs/design/specs/policy-gate/v1.md:186. |
| C2 Reproduction (red pre-fix) | PASS | Frozen execution demonstrates the missing behavior with 203 assertion failures, alongside 12 expected missing-loader setup errors; gate-logs/C4-verify.log:9500. |
| C3 Change | PASS | Command semantics are confined to reviewed data and the command engine, retaining shell-layer literal handling; target/src/nl_shell/gate/rules.py:116 and target/src/nl_shell/gate/commands.py:297. |
| C4 Verification (red→green) | PASS | Log establishes 453 green tests and a reverted-production red leg; local rerun is unavailable because pytest and tree-sitter-bash are absent, so this verdict rests on captured execution, not independent reproduction; gate-logs/C4-verify.log:10 and gate-logs/C4-verify.log:9500. |
| C5 Causal adequacy | PASS | Replacing the stub supplies the missing classification cause, and the common unreadable-word path applies elevation rejection through nested argv; no optional-capability probe/load-time guard smell found; target/src/nl_shell/gate/rules.py:329. |
| T1 Structure | PASS | One table loader and one generic engine separate reviewed meanings from argv interpretation; changed Python files parse successfully and git diff --check is clean; target/src/nl_shell/gate/commands.py:347 and target/src/nl_shell/gate/rules.py:321. |
| T2 Shape | PASS | Security semantics and accepted gaps are documented alongside the engine; the frozen threat-model scanner confirms the required touch; gate-logs/T2-threat-model.log:10 and target/docs/design/specs/policy-gate/v1.md:211. |
| T3 Runtime | PASS | Captured full-suite execution reports 1,586 passed, one skipped and five forkpty warnings; local pytest is unavailable, so no independent runtime claim is made; gate-logs/T3-suite.log:44. |
| T4 Contribution | N/A | Contribution artifacts are intentionally drafted after Check; the substantive audit must rerun at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Adjudicate reference-host inventory drift (mount.cifs and mount.smb3 have no rows), and confirm affected-path merged/closed/rejected prior art beyond the single supplied base commit — coverage completeness and duplication remain unsettled; target/scripts/harvest_inventory.py:26 and target/targets/ubuntu-26.04/commands.toml:999. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the user-facing rejection cost and documented residual path/text risks for this release — typed variable commands can be rejected while unknown symlink paths remain accepted; target/docs/design/specs/policy-gate/v1.md:200 and target/docs/design/specs/policy-gate/v1.md:211. |

Independent checks: ran `python3 target/scripts/harvest_inventory.py --output inventory-review.toml` successfully on Ubuntu 26.04.1 LTS. Comparing it with the checked-in inventory found exactly two additional entries: setuid `/usr/sbin/mount.cifs` and its same-file alias `/usr/sbin/mount.smb3`. Neither matches a command-table name or pattern. The generated inventory is retained as `inventory-review.toml`; drift is explicitly human-adjudicated by the contract, not treated here as a demonstrated privilege bypass.

Prior art: ran `git log --all --oneline -- src/nl_shell/gate/rules.py targets/ubuntu-26.04/commands.toml scripts/harvest_inventory.py` in the supplied target. It returns only `a2d1efe pre-fix base 1a1e980...`; the bundle's brief records an affected-path and PR-state check (brief.md:365), but original merged history and closed/rejected work are unavailable for independent confirmation.

Verification limits: `python3 -m pytest -q tests/test_gate_commands.py tests/test_policy_gate.py tests/test_targets.py` fails before collection with `No module named pytest`; importing `tree_sitter_bash` also fails locally. Consequently I did not stash the patch for a redundant unavailable red leg. All four frozen gate logs were readable and inspected. Their recorded runs exercise the parser dependency rather than substitute a code-read or shim; the missing local packages are a reviewer-host limitation, not a patch defect. Target source was readable and matched the patch; no stale-target caveat was needed. No target source was changed.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review: issue 204 / gate-command-table-engine (v3)

I re-ran no gate. The frozen C4 log (`gate-logs/C4-verify.log`) shows a real red leg: an
ImportError on `nl_shell.gate.commands` for the loader tests, plus assertion failures for
the engine groups (203 failed, 12 setup errors, 453 total). The tests go through the
public `nl_shell.gate.classify`. I then sent about 200 hand-made inputs through
`classify` at `$PDCA_TARGET`, using the harness `.venv` (it has tree-sitter-bash), and
re-ran `scripts/harvest_inventory.py`. Most attacks failed. All of these come out
`privileged` and rejected as proposals: wrappers around `sudo -i` (env, nice, timeout,
stdbuf, ionice, chrt, taskset, setpriv, flock, strace, nsenter, unshare, chroot, xargs,
find -exec/-ok, command, exec, coproc, time), bundled and prefixed sudo options
(`-Si`, `-iS`, `--std`, `--pr=x`, `--ask`, `sudo-rs --std`), `<&3` and process
substitution as stdin, brace and ANSI-C command words, and `~user/../sudo`. These are
the inputs that did get through:

- NEEDS-HUMAN [impl] — `src/nl_shell/gate/__init__.py:177-181` with `src/nl_shell/gate/rules.py:337-339`: decision D misses a **bracket glob** at the start of a command word with no `/` in it. tree-sitter-bash misparses `sud[o]`: `shell_layer("echo pw | sud[o] -S true")` gives the invocations `['echo','pw'], ['S','true']`, so the engine never sees the word. Result: typed `cd /usr/bin; echo pw | sud[o] -S true` is `mutating`, **not rejected**. Typed `sud[o] -i` is `mutating`, not `privileged` (`[s]udo`, `su[d]o` behave the same). Bash expands the glob against cwd, so in `/usr/bin` it runs sudo: I checked `cd /usr/bin; sud[o] -V`, and it prints `sudo-rs 0.2.13`. This breaks D.1 (class `privileged`) and D.3 (§5 for every origin, typed included). Proposals are still rejected, but only as "unparseable". `/usr/bin/sud[o] -S true` and `./su[d]o -S true` parse fine and are rejected, so only the bare-word form leaks. The brief lets this child fix a walker bug that one of its own cases exposes (Scope: "the walker (#196) except a walker bug a case here exposes"). At minimum, add a typed `sud[o] -S true` case to the decision-D group. The test suite has no `[`-glob command-word case.
- NEEDS-HUMAN [impl] — `targets/ubuntu-26.04/inventory.toml:317-330`: **inventory drift on the reference host.** Running `scripts/harvest_inventory.py --output` here adds `mount.cifs` (setuid root, `/usr/sbin/mount.cifs`, package cifs-utils) and `mount.smb3` (same file). Neither has a row: `table().lookup("mount.cifs")` is `None`, because the mount row at `commands.toml:999` lists only `mount.ntfs*`. So two setuid binaries on the host break class 1 ("every name in the inventory has a row"). The brief makes drift a Check finding. Fix: regenerate the inventory and add both names to the mount row.
- NEEDS-HUMAN [human] — `targets/ubuntu-26.04/commands.toml:2105-2115` (`hash` row) with `src/nl_shell/gate/rules.py:371` (`_row` never calls `_decision_a`): **`hash -p /usr/bin/sudo ls; ls -i` as a proposal is `session-altering`, not rejected.** Bash then runs sudo as `ls`: I checked `bash -c 'hash -p /usr/bin/echo ls; ls hi'`, and it runs echo. A root shell gets past §5 and the threat model's "Wrappers, aliases … don't hide a privileged step" (`.oss-scanner/threat_model.md:117-120`). Decision A would catch `/usr/bin/sudo` (lookup by last path part), but the brief limits decision A to commands with no row, and `hash` has one. `BASH_CMDS[ls]=/usr/bin/sudo; ls -i` (`mutating`) and a two-line `alias ls=sudo` / `ls -i` (`session-altering`) are the same hole, but those belong to child-3 (#206: protected variables and stored code). Someone has to decide whether `hash -p <elevating path>` goes to #206 or gets a rule here. The spec's §4.1 gap list does not name it either way.
- NEEDS-HUMAN [human] — `src/nl_shell/gate/rules.py:629-646` (decision B) with `rules.py:430` (decision A only for commands with no row): **a row with a text effect classes below what decision A gives an unknown command.** `foo sudo -S true` is `privileged`, but typed `eval sudo -S true`, `echo pw | bash -c 'sudo -S true'`, `env -S 'sudo -S true'` and `echo pw | script -qc 'sudo -S true'` are only `destructive`, **not rejected**. As proposals, `eval sudo -i` and `env -S 'sudo -i'` are `destructive`, not rejected. Under the brief this is by design (decision B until child-2), and it is no worse than `main`, where everything was `mutating`. But the threat model's "The gate rejects `sudo -S` … and pipes into sudo" (`threat_model.md:124-125`) is still false for literal text after this patch. The brief claims only that D keeps the sentence true for unreadable command words, which is accurate. A human should confirm that the interim gap is fine until #205 lands, or else ask for decision A's word scan to run over text-effect arguments now. That scan would cost little and would make all of the cases above `privileged`.
- NEEDS-HUMAN [human] — `src/nl_shell/gate/rules.py:121-123,166-167` (`$"…"` read as `"…"`): the claim "no message catalog is installed for a typed word, so bash keeps the text" assumes `TEXTDOMAIN`/`TEXTDOMAINDIR` are unset. `TEXTDOMAIN=x; $"foo" -i` comes out `mutating`, not rejected. With a catalog that maps `foo` to `sudo` (a file an earlier step would have to write), bash runs `sudo -i`. This is unlikely and needs two steps, but the decoding is only sound if those variables are guarded, and nothing here guards them (child-3 owns protected names). Either record it as a gap in §4.1, or treat `$"…"` as unreadable whenever an earlier statement in the same input assigns `TEXTDOMAIN*`.

I also tried to refute the proof itself and could not. The red leg fails for the right reasons (missing loader module, stub verdicts), not because of collection errors only. Cases call the production `classify`, not a copy of it. The `check-gates.json` C4 claim "203 of 441 failed" matches the log: 441 run plus 12 setup errors makes the 453 of the green leg. The T3 suite log shows 1586 passed and 1 skipped.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Advisory security review — issue 204 (gate command table and engine)

**Attacker-reachable inputs this diff touches:** the model's proposal text (threat model item 5) and session state (item 4) as they reach the new command layer (`src/nl_shell/gate/rules.py`, `src/nl_shell/gate/commands.py`, `targets/ubuntu-26.04/commands.toml`). The table itself is trusted: it loads from a fixed path, with no env, cwd or HOME lookup (`commands.py:316-344`).

What I checked, by running `nl_shell.gate.classify` on the patched tree for both origins (about 150 strings):
- The sudo family and §5: `-S/-p/-A` bundled, attached and long, plus prefixes (`--std`, `--s`, `--stdin=1`). Also `sudo "$@"`, `SUDO_PROMPT=`/`SUDO_ASKPASS=` prefixes, `env SUDO_ASKPASS=… sudo -A`, `sudo -k -- sudo -S`, `sudo sudo -S`.
- Wrappers: `exec`, `command`, `builtin`, `time`, `coproc`, `nohup`, `nice -n "$n"`, `env -C`, `watch -x`, `xargs -0/-a/--arg-file/-I{}`, `find -exec/-execdir/-ok {}`, `busybox`, `systemd-run`, `run0`, `doas -s`, `su -c`.
- Path lookup: `//usr//bin//sudo`, `/usr/bin/../bin/sudo`, `./sudo.ws`.
- Decision D: `$x -nS`, `$x -kS` piped, `timeout 5 $x -i`, `find -ok $x`.
- Code-running options: `tar -I/-F/--checkpoint-action/xIf`, `ssh -F`, `git --upload-pack=`, `sudo git -c/--exec-path`, `sudo rsync -e sh`.
- ANSI-C decoding against bash 5.3.9 (`$'su\0x'do`, `x$'\0'sudo`, `$'\x7375'`, `$'\x{73}udo'`, `$'sudo'`).

All of these come out at or above the class the brief and spec require. Proposals that must be rejected are rejected. The gaps below are the exceptions.

## Findings

- NEEDS-HUMAN [human] — **High on the threat model's scale ("a privileged step classed lower"), but only after a hostile session change.** `src/nl_shell/gate/rules.py:166-167` (and its docstring at `:120-123`, "no message catalog is installed") reads `$"…"` as plain `"…"`. That makes it a readable command word, so decision D never fires for it. The input is the proposal's command word (model output), and session state picks what bash actually runs. Bash translates `$"…"` through gettext using `TEXTDOMAIN`/`TEXTDOMAINDIR`, so the session can turn `$"ls"` into `sudo`. These variables can come from a direnv file or a sourced repo script (item 4), with the `.mo` (gettext message catalog) file placed by a cloned repo. Reproduced on this host: a catalog at `loc/en/LC_MESSAGES/evil.mo` (or `LANGUAGE=fr` with `loc/fr/...`) mapping `ls`→`sudo`, then `TEXTDOMAINDIR=$PWD/loc TEXTDOMAIN=evil`, then `x=$"ls"; echo "[$x]"` prints `[sudo]`. The gate classes the proposal `echo pw | $"ls" -S true` as `mutating`, not rejected, and `$"ls" -i` as `mutating`, not rejected. At run time those are `echo pw | sudo -S true` and `sudo -i`, both of which §5 says must be rejected. Main also gave `mutating` here, so this is not a regression. But the patch writes into the threat model ("What must hold", the #204 paragraph) and spec §4.1 that `$"…"` is read like `"…"`, and that decision D keeps the §5 sudo rules true for words that may be `sudo`. For `$"…"` that holds only while `TEXTDOMAIN*` is unset. Someone needs to choose one of two fixes. (a) Treat a `$"…"` command word as unreadable under D, as the shell layer already treats it as non-literal; this costs nothing for typed input, since nobody types `$"sudo"`. (b) Keep the decoding, and record in spec §4.1 and the threat model that `TEXTDOMAIN`, `TEXTDOMAINDIR`, `LANGUAGE` and `LC_*` are session state §7 (#192) or #206 must check. The test at `tests/test_gate_commands.py:607-610` covers only the friendly path. This is the same family as `alias ls=sudo` (also §7), which is why it needs a scope decision rather than a quick patch.

- NEEDS-HUMAN [impl] — **Low (a §5 rule is bypassed, but the password still can't reach sudo because `-S` is still caught).** `src/nl_shell/gate/rules.py:466` and `:385` treat stdin kind `file` as "not a pipe". But `< /dev/stdin` reopens the pipe. Typed and proposal `echo x | sudo tee /x < /dev/stdin` come out `privileged`, not rejected, and so does `echo x | $x tee /x < /dev/stdin`. The threat model says "the gate rejects … pipes into sudo". `Stdin.value` already holds the path (`parse.py:105`), and the patch already has `_STDIN_FILES` (`rules.py:61`) for `bash /dev/stdin`. The fix: count a `file` stdin whose value is in `_STDIN_FILES` as a pipe in both places, and add the two strings above as test cases.

- NEEDS-HUMAN [impl] — **Low (coverage drift; no class is lowered).** I re-ran `scripts/harvest_inventory.py --output` on this host (the reference host), and its output differs from the checked-in `targets/ubuntu-26.04/inventory.toml`. It adds `mount.cifs` (setuid, `/usr/sbin/mount.cifs`, installed 2026-10-16, before Plan) and `mount.smb3` (symlink to it). Neither has a row, so both fall to decision A (`mutating`, "not allowlisted"). The `mount` row at `targets/ubuntu-26.04/commands.toml:999` is also `mutating`, so nothing is classed lower today. But the class-1 claim ("every name of an elevating … binary on the reference host has a row") and the coverage test are now out of date. The brief says such drift is a review finding. Fix: regenerate the inventory and add both names to the `mount` row.

- NEEDS-HUMAN [human] — **Medium on the scale ("a destructive command classed as merely mutating"); a scope question, not a bypass of anything the brief lists.** The `git` row (`targets/ubuntu-26.04/commands.toml:1660`) makes `git reset --hard`, `git clean` and `git push -f` destructive. But `git checkout -- .`, `git stash drop` and `git branch -D x` come out `mutating`, and so does `rsync -e sh a b`, which has no row. The brief allows "a row may describe only some subcommands", and none of these are on the spec §4 destructive list, so this is not a defect against the brief. It is still the threat model's Medium outcome for proposals that throw away uncommitted work. Someone needs to decide whether to add these subcommands now or leave them to #198 or a follow-up.

## Not findings (checked)
- `$'\c?'`: the gate decodes it as 0x1F, bash as 0x7F. No row name contains a control character, and the proposal parser rejects control characters, so this has no security effect.
- `runuser -u root id` is `mutating`. `runuser` works only when the caller is already root, so it gives no elevation from a user session. Under `sudo`, the elevation rules apply.
- The table cannot be redirected: `commands.py:324-331` uses the fixed root, and the env/cwd tests are in the suite. The T3 log shows 1586 passed.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T5 Judgment — Adjudicate reference-host inventory drift (mount.cifs and mount.smb3 have no rows), and confirm affected-path merged/closed/rejected prior art beyond the single supplied base commit — coverage completeness and duplication remain unsettled; target/scripts/harvest_inventory.py:26 and target/targets/ubuntu-26.04/commands.toml:999.
- [ ] Validation — fitness-to-purpose — Accept the user-facing rejection cost and documented residual path/text risks for this release — typed variable commands can be rejected while unknown symlink paths remain accepted; target/docs/design/specs/policy-gate/v1.md:200 and target/docs/design/specs/policy-gate/v1.md:211.
- [ ] `src/nl_shell/gate/__init__.py:177-181` with `src/nl_shell/gate/rules.py:337-339`: decision D misses a **bracket glob** at the start of a command word with no `/` in it. tree-sitter-bash misparses `sud[o]`: `shell_layer("echo pw | sud[o] -S true")` gives the invocations `['echo','pw'], ['S','true']`, so the engine never sees the word. Result: typed `cd /usr/bin; echo pw | sud[o] -S true` is `mutating`, **not rejected**. Typed `sud[o] -i` is `mutating`, not `privileged` (`[s]udo`, `su[d]o` behave the same). Bash expands the glob against cwd, so in `/usr/bin` it runs sudo: I checked `cd /usr/bin; sud[o] -V`, and it prints `sudo-rs 0.2.13`. This breaks D.1 (class `privileged`) and D.3 (§5 for every origin, typed included). Proposals are still rejected, but only as "unparseable". `/usr/bin/sud[o] -S true` and `./su[d]o -S true` parse fine and are rejected, so only the bare-word form leaks. The brief lets this child fix a walker bug that one of its own cases exposes (Scope: "the walker (#196) except a walker bug a case here exposes"). At minimum, add a typed `sud[o] -S true` case to the decision-D group. The test suite has no `[`-glob command-word case.
- [ ] `targets/ubuntu-26.04/inventory.toml:317-330`: **inventory drift on the reference host.** Running `scripts/harvest_inventory.py --output` here adds `mount.cifs` (setuid root, `/usr/sbin/mount.cifs`, package cifs-utils) and `mount.smb3` (same file). Neither has a row: `table().lookup("mount.cifs")` is `None`, because the mount row at `commands.toml:999` lists only `mount.ntfs*`. So two setuid binaries on the host break class 1 ("every name in the inventory has a row"). The brief makes drift a Check finding. Fix: regenerate the inventory and add both names to the mount row.
- [ ] `targets/ubuntu-26.04/commands.toml:2105-2115` (`hash` row) with `src/nl_shell/gate/rules.py:371` (`_row` never calls `_decision_a`): **`hash -p /usr/bin/sudo ls; ls -i` as a proposal is `session-altering`, not rejected.** Bash then runs sudo as `ls`: I checked `bash -c 'hash -p /usr/bin/echo ls; ls hi'`, and it runs echo. A root shell gets past §5 and the threat model's "Wrappers, aliases … don't hide a privileged step" (`.oss-scanner/threat_model.md:117-120`). Decision A would catch `/usr/bin/sudo` (lookup by last path part), but the brief limits decision A to commands with no row, and `hash` has one. `BASH_CMDS[ls]=/usr/bin/sudo; ls -i` (`mutating`) and a two-line `alias ls=sudo` / `ls -i` (`session-altering`) are the same hole, but those belong to child-3 (#206: protected variables and stored code). Someone has to decide whether `hash -p <elevating path>` goes to #206 or gets a rule here. The spec's §4.1 gap list does not name it either way.
- [ ] `src/nl_shell/gate/rules.py:629-646` (decision B) with `rules.py:430` (decision A only for commands with no row): **a row with a text effect classes below what decision A gives an unknown command.** `foo sudo -S true` is `privileged`, but typed `eval sudo -S true`, `echo pw | bash -c 'sudo -S true'`, `env -S 'sudo -S true'` and `echo pw | script -qc 'sudo -S true'` are only `destructive`, **not rejected**. As proposals, `eval sudo -i` and `env -S 'sudo -i'` are `destructive`, not rejected. Under the brief this is by design (decision B until child-2), and it is no worse than `main`, where everything was `mutating`. But the threat model's "The gate rejects `sudo -S` … and pipes into sudo" (`threat_model.md:124-125`) is still false for literal text after this patch. The brief claims only that D keeps the sentence true for unreadable command words, which is accurate. A human should confirm that the interim gap is fine until #205 lands, or else ask for decision A's word scan to run over text-effect arguments now. That scan would cost little and would make all of the cases above `privileged`.
- [ ] `src/nl_shell/gate/rules.py:121-123,166-167` (`$"…"` read as `"…"`): the claim "no message catalog is installed for a typed word, so bash keeps the text" assumes `TEXTDOMAIN`/`TEXTDOMAINDIR` are unset. `TEXTDOMAIN=x; $"foo" -i` comes out `mutating`, not rejected. With a catalog that maps `foo` to `sudo` (a file an earlier step would have to write), bash runs `sudo -i`. This is unlikely and needs two steps, but the decoding is only sound if those variables are guarded, and nothing here guards them (child-3 owns protected names). Either record it as a gap in §4.1, or treat `$"…"` as unreadable whenever an earlier statement in the same input assigns `TEXTDOMAIN*`.
- [ ] **High on the threat model's scale ("a privileged step classed lower"), but only after a hostile session change.** `src/nl_shell/gate/rules.py:166-167` (and its docstring at `:120-123`, "no message catalog is installed") reads `$"…"` as plain `"…"`. That makes it a readable command word, so decision D never fires for it. The input is the proposal's command word (model output), and session state picks what bash actually runs. Bash translates `$"…"` through gettext using `TEXTDOMAIN`/`TEXTDOMAINDIR`, so the session can turn `$"ls"` into `sudo`. These variables can come from a direnv file or a sourced repo script (item 4), with the `.mo` (gettext message catalog) file placed by a cloned repo. Reproduced on this host: a catalog at `loc/en/LC_MESSAGES/evil.mo` (or `LANGUAGE=fr` with `loc/fr/...`) mapping `ls`→`sudo`, then `TEXTDOMAINDIR=$PWD/loc TEXTDOMAIN=evil`, then `x=$"ls"; echo "[$x]"` prints `[sudo]`. The gate classes the proposal `echo pw | $"ls" -S true` as `mutating`, not rejected, and `$"ls" -i` as `mutating`, not rejected. At run time those are `echo pw | sudo -S true` and `sudo -i`, both of which §5 says must be rejected. Main also gave `mutating` here, so this is not a regression. But the patch writes into the threat model ("What must hold", the #204 paragraph) and spec §4.1 that `$"…"` is read like `"…"`, and that decision D keeps the §5 sudo rules true for words that may be `sudo`. For `$"…"` that holds only while `TEXTDOMAIN*` is unset. Someone needs to choose one of two fixes. (a) Treat a `$"…"` command word as unreadable under D, as the shell layer already treats it as non-literal; this costs nothing for typed input, since nobody types `$"sudo"`. (b) Keep the decoding, and record in spec §4.1 and the threat model that `TEXTDOMAIN`, `TEXTDOMAINDIR`, `LANGUAGE` and `LC_*` are session state §7 (#192) or #206 must check. The test at `tests/test_gate_commands.py:607-610` covers only the friendly path. This is the same family as `alias ls=sudo` (also §7), which is why it needs a scope decision rather than a quick patch.
- [ ] **Low (a §5 rule is bypassed, but the password still can't reach sudo because `-S` is still caught).** `src/nl_shell/gate/rules.py:466` and `:385` treat stdin kind `file` as "not a pipe". But `< /dev/stdin` reopens the pipe. Typed and proposal `echo x | sudo tee /x < /dev/stdin` come out `privileged`, not rejected, and so does `echo x | $x tee /x < /dev/stdin`. The threat model says "the gate rejects … pipes into sudo". `Stdin.value` already holds the path (`parse.py:105`), and the patch already has `_STDIN_FILES` (`rules.py:61`) for `bash /dev/stdin`. The fix: count a `file` stdin whose value is in `_STDIN_FILES` as a pipe in both places, and add the two strings above as test cases.
- [ ] **Low (coverage drift; no class is lowered).** I re-ran `scripts/harvest_inventory.py --output` on this host (the reference host), and its output differs from the checked-in `targets/ubuntu-26.04/inventory.toml`. It adds `mount.cifs` (setuid, `/usr/sbin/mount.cifs`, installed 2026-10-16, before Plan) and `mount.smb3` (symlink to it). Neither has a row, so both fall to decision A (`mutating`, "not allowlisted"). The `mount` row at `targets/ubuntu-26.04/commands.toml:999` is also `mutating`, so nothing is classed lower today. But the class-1 claim ("every name of an elevating … binary on the reference host has a row") and the coverage test are now out of date. The brief says such drift is a review finding. Fix: regenerate the inventory and add both names to the `mount` row.
- [ ] **Medium on the scale ("a destructive command classed as merely mutating"); a scope question, not a bypass of anything the brief lists.** The `git` row (`targets/ubuntu-26.04/commands.toml:1660`) makes `git reset --hard`, `git clean` and `git push -f` destructive. But `git checkout -- .`, `git stash drop` and `git branch -D x` come out `mutating`, and so does `rsync -e sh a b`, which has no row. The brief allows "a row may describe only some subcommands", and none of these are on the spec §4 destructive list, so this is not a defect against the brief. It is still the threat model's Medium outcome for proposals that throw away uncommitted work. Someone needs to decide whether to add these subcommands now or leave them to #198 or a follow-up.
- [ ] **The brief contradicts the tracker's scope on `parse.py`, and the issue body was not updated.** The tracker (notes.json, Scope) says: "in `src/nl_shell/gate/parse.py` **only** `lex_word` (`:197`): decode ANSI-C `$'…'` quoting as bash does". It also says `test_policy_gate.py:192` goes "from `mutating` \"command word is not a literal\" to `destructive`". The brief says the opposite: "**`lex_word` (`parse.py:197`), `make_word` (`:273-275`) and `Word.literal` do not change**", and "the shell layer still reports 'command word is not a literal'". The brief's reason holds against the source: `make_word` sets `literal=not causes` (`parse.py:275`), and that flag feeds every redirect and shell rule, so changing it would lower verdicts. The brief's choice is right, but #204's body still describes the other design. A Check reviewer or code-review leaf that grounds on the issue thread will flag a correct patch as off-scope, or a builder will follow the issue instead. Before Do, record that the brief overrides this point, for example in a tracker comment.
- [ ] **Most of v3 is not in the tracker.** These are absent from the #204 body: decision D, the path-lookup rule, the recorded path gap, `$"…"` decoding, and the extra coverage rows (`ruby`, `node`, `awk`/`mawk`/`gawk`). The body's decisions stop at A and C, and its inventory list is "`python3*`, `perl*`, `busybox`, `gdb`". The brief says D is the human's choice at the v2 sign-off ("decision D, option (b1)"). That choice only exists in `iteration-v2/`, which is not among my inputs, so I cannot verify it from the thread. Together these add a third decision, two spec gaps and new spec/threat-model sections to a slice already at split depth 3 ("`split --accept` refuses without `--force`"). The human should confirm that D plus the path rules belong in this child and not in a follow-up. They should also have the tracker body updated so it matches what Check will hold the patch to.
- [ ] **The `~/bin/x -i` path-gap case cannot get the asserted reason from the layer the brief points at.** The class-7 group asserts that `./x -i`, `/tmp/x -i` and `~/bin/x -i` have a "reason includes 'path outside the system directories'". In the source, `lex_word` adds the cause `leading-tilde` for a leading `~/` (`parse.py:262-265`), so `Word.literal` is False. `_shell_rules` therefore takes the `not word.literal` branch and gives "command word is not a literal: ~/bin/x" (`gate/__init__.py:255-256`). The `elif` that gives "path outside the system directories" (`:257-261`) is never reached. The brief freezes `lex_word`, `make_word` and `:255-256` ("stay as they are"). So the expected reason can only come from the command layer, and nothing in the brief says the engine must emit it. The brief only says such a word "is a path outside the system directories (the known gap below)". Either state that `rules.classify` emits that reason for a word whose only cause is a leading `~`, or loosen the assertion for `~/bin/x -i`. If neither is done, Do will either fail this case or touch the frozen shell rule. The same applies to `~/sudo -i` in the path-lookup case: it hits the `sudo` row only if the command layer strips the leading `~` before taking the last path part, and the brief should say so explicitly.
- [ ] **Two provenance citations cannot be checked from the record.** Decision A's added limit ("applies **only** to a command with neither a row nor an allowlist entry (#197's tracker body says so)") is cited to #197's tracker. The decisions are cited to `results/issue_189/iteration-v3/brief.md:99-112`, while this issue's body cites `results/issue_189/brief.md:99-112`. Neither file is in the inputs, and the two paths disagree. The decision-A limit is load-bearing because it is what lets `man sudo` etc. come out `privileged` without new rows. If it is wrong, the accepted over-raise and the "do not add rows" rule rest on nothing. Check the citations against the real #197 and #189 files before sign-off.
- [ ] size backstop — this slice is behaving oversized: patch is 216 KB (threshold 100 KB). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.

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
- Iteration delta (if iterating): Core engine and table are sound; keep the slice (size is mostly table data). Fix these in-scope bypasses, each with tests: - Bracket-glob command word with no `/` (`sud[o]`, `[s]udo`, `su[d]o`): tree-sitter-bash misparses it, so decision D never sees the word. Fix the walker/command layer so it is unreadable under D. Tests: typed `echo pw | sud[o] -S true` rejected (§5 reason); typed `sud[o] -i` privileged; proposal `sud[o] -i` rejected with the decision-D reason (not only "unparseable"). - `< /dev/stdin` (and the other `_STDIN_FILES` paths) as stdin counts as a pipe for the §5 rule and decision D (rules.py :385, :466). Tests: `echo x | sudo tee /x < /dev/stdin` and `echo x | $x tee /x < /dev/stdin` rejected, typed and proposal. - Inventory drift: regenerate `targets/ubuntu-26.04/inventory.toml` on the reference host (adds `mount.cifs`, `mount.smb3`) and add both names to the `mount` row. - `$"…"` locale quoting: fail closed. A `$"…"` command word is unreadable under decision D (bash translates it via TEXTDOMAIN/TEXTDOMAINDIR). Update spec §4.1/threat model text that says `$"…"` is read like `"…"`. Tests: `$"ls" -i` proposal rejected; typed `echo pw | $"ls" -S true` rejected; update the existing `$"sudo"` cases to the decision-D reason. - Item 6, option (b): run decision A's argument word scan over the arguments of text-effect rows too (still decision B, no recursion). Tests: typed `eval sudo -S true`, `echo pw | bash -c 'sudo -S true'`, `env -S 'sudo -S true'`, `echo pw | script -qc 'sudo -S true'` privileged and rejected; proposals `eval sudo -i`, `env -S 'sudo -i'` rejected. Keep the threat model's sudo sentence (:121-125) true as written. Out of scope (follow-ups, do not fix here): `hash -p`/`BASH_CMDS` stored lookup (#206); git checkout/stash drop/branch -D and rsync -e destructive rows.
- By / date: Eduard Ralph / 2026-10-26

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 4 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)
- issue_204 follow-up: `hash -p <elevating path> <name>` (and `BASH_CMDS[...]=`) lets a later bare command run sudo — hand to #206 (stored code) and record it in #206's tracker/spec gap list.
- issue_204 follow-up: `git checkout -- .`, `git stash drop`, `git branch -D`, `rsync -e sh` classed only `mutating` — file as a separate issue (spec §4 destructive list decision).
- issue_204 process: the #204 tracker body was not updated after the v2 re-plan (decision D, `parse.py` scope, path rules); re-plan should update the tracker body, and #204's must be fixed before publish.

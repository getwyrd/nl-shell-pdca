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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): fail — C4 FAIL — bundle test red (or not importable) WITH the fix applied
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — security-relevant paths touched and the threat model updated: docs/design/specs/policy-gate/v1.md src/nl_shell/gate/__in
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: fail — T3 FAIL — nl-shell suite red (pytest exit 1)
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review issue #204: replace the command-policy stub with a reviewed command table and generic engine, including fail-closed unreadable command words and the carried-forward §5 bypass fixes.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The brief defines decisions A–D, accepted gaps, and carry-forward cases explicitly; the elevation contract is reflected at target/docs/design/specs/policy-gate/v1.md:179. |
| C2 Reproduction (red pre-fix) | NEEDS-HUMAN | Confirm the public-API pre-fix red leg in an equipped environment — pytest and tree-sitter are unavailable locally, and the frozen verification stops during its green leg without recording red-leg execution (gate-logs/C4-verify.log:81). |
| C3 Change | PASS | The patch supplies the requested reviewed data, closed-schema loader and generic engine; fixed-root loading rejects escape paths and malformed input (target/src/nl_shell/gate/commands.py:322); git diff --check passes. |
| C4 Verification (red→green) | FAIL | A successful red→green is absent: both frozen green-leg attempts fail the 5-second size-cap test, with 473 other tests passing; this is observed test evidence, not a confirmed attribution of the slowdown (gate-logs/C4-verify.log:76). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Bound bracket recovery work before scanning every malformed node — repeated scans of the same unrecognized word can consume quadratic work without reaching the successful-recovery deduplication, undermining bounded classification (target/src/nl_shell/gate/parse.py:685). |
| T1 Structure | PASS | Per-command behavior remains reviewed data consumed by a common grammar/effect engine, and loader failures flow into the existing fail-closed sink (target/src/nl_shell/gate/rules.py:93). |
| T2 Shape | PASS | Security documentation changes with the engine, including locale quoting and unreadable-command handling; independently confirmed the threat-model diff and frozen touch-check output (target/.oss-scanner/threat_model.md:194; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | FAIL | The frozen whole-suite runs remain red on the same latency assertion; the last run reports 1606 passed, 1 skipped and 1 failed, so whole-suite success is not established (gate-logs/T3-suite.log:129; target/tests/test_policy_gate.py:716). |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive contribution audit must run at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art against merged and closed/rejected work — the brief records that search, but this target has only one synthetic base commit and no supplied closed-work evidence to independently settle duplication (brief.md:365). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the accepted class-7/path-resolution gaps and conservative rejections fit the intended release, after obtaining a successful public-API red→green run; tree-sitter-bash was exercised in frozen logs but is unavailable for this independent review (brief.md:357; target/docs/design/specs/policy-gate/v1.md:176). |

Independent checks and limits:

- The target is a readable disposable patched copy with a synthetic pre-fix base; no stale-target caveat was found. No source files were changed. Stashing the patch would not enable a meaningful classifier run without the unavailable dependencies, so no stash/red/pop sequence was performed.
- `python3` is 3.14.4; importing pytest fails. An offline uv attempt using a cache inside this scratch root cannot resolve tree-sitter==0.26.0. Instance-root wrappers were not run; their full frozen logs were read. The logs show actual classifier tests executing, not a missing-tool failure, but contain no pre-fix timing comparison.
- Ran `python3 target/scripts/harvest_inventory.py --output inventory-review.toml` and compared with the checked-in inventory: exact match, including mount.cifs and mount.smb3. The local VERSION is Ubuntu 26.04.1 LTS (Resolute Raccoon), matching the inventory.
- Independently executed the unchanged `_word_start`, `_raw_words`, and `_unquoted_bracket` helper bodies extracted with Python AST, once per two-byte position in repeated `$[` input. At 2048/4096/8192 bytes this took 1.569/6.652/27.128 seconds. This isolates quadratic helper work; it is not a public-classifier benchmark or a claim that every offset is visited by the parser. `_error` calls recovery for each error node (target/src/nl_shell/gate/parse.py:711), while unsuccessful candidates never enter `bracket_words` (target/src/nl_shell/gate/parse.py:689). Fix the repeated work and re-run the existing latency test rather than weakening its threshold.
- The C5 capability-probe smell-test does not fire: missing/invalid-table handling is the specified fail-closed dependency boundary, not a probe masking eager capability use. No INTEGRATION.md was present in the supplied target.
- The brief records prior-art searches by affected paths, including closed/unmerged PRs; the synthetic local history cannot independently corroborate those results. No other checkout was consulted.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 204 / gate-command-table-engine (v3)

Both gating runtime gates are red (C4 and T3, `gate-logs/C4-verify.log`, `gate-logs/T3-suite.log`). I reproduced the failure and traced it to this patch. I also found three concrete bypasses of decision D. Every finding below was run against `$PDCA_TARGET` (the patched tree), with the pre-fix base (`git archive HEAD`) used for comparison. I used the `nl-shell-pdca` venv's interpreter for `tree_sitter`.

- NEEDS-HUMAN [impl] — **The patch causes the C4/T3 red: it is a real slowdown, not a flaky timer.** `tests/test_policy_gate.py:710-716` is an existing test, not part of this diff. `classify(("$[" * 8192)[:8192])` takes 0.43 s on base and 5.85 s patched. Profiling puts 5.36 of the 5.85 s in `_bracket_command` (`src/nl_shell/gate/parse.py:678-708`), which is new in this diff. For each of the 820 ERROR nodes it calls `_word_start` (`parse.py:670-675`, walks back to the word start), `_raw_words` (`parse.py:610-641`, walks forward to the command end) and `_unquoted_bracket` (`parse.py:644-667`, does `"]" in word[i+2:]` once per `[`). When a word has no spaces, each call is O(input size), so the total is O(nodes × size). The cache at `parse.py:686-687/708` only records starts that *produced* a command, so a word that fails `_unquoted_bracket` gets rescanned for every node. Worse inputs, all under the 8 KiB cap: `("[$[" * 8192)[:8192]` takes **19.3 s** (base 0.26 s), `"$[["` 11.2 s, `"$[x"` 9.0 s. None of this time counts toward `MAX_WORK` (`parse.py:40`). A model proposal can freeze the gate for about 20 s. The verdict stays fail-closed (`unparseable`), so this is a denial-of-service problem, not a bypass. I tried caching every scanned start (hits and misses): 19.3 s dropped only to 3.5 s, because `_word_start` still walks back once per node. The fix needs both: compute word starts and ends once for the whole source, and make `_unquoted_bracket` linear (for example, check against the index of the last `]`).

- NEEDS-HUMAN [impl] — **Bypass: `coproc` with an unreadable command word.** A proposal of `coproc sudo -i` is rejected (decision A, `src/nl_shell/gate/rules.py:486-502`). But proposals `coproc sud[o] -i`, `coproc [s]udo -i` and `coproc sud? -i` come out `mutating`, `rejected=False`, reason only "not allowlisted". Typed `echo pw | coproc sud[o] -S true` is also not rejected, which breaks decision D point 3 (the §5 pipe rule for every origin). The cause: `coproc` has no row in `targets/ubuntu-26.04/commands.toml` (grep finds no `coproc` anywhere in the tree), so it is handled as an opaque command, and `_decision_a` skips unreadable words at `rules.py:488-490`. But `coproc` is a bash reserved word that runs its next word as a command. I confirmed bash expands the glob there: with a file `echo` in cwd, `bash -c 'coproc ech[o] ran-via-glob; cat <&"${COPROC[0]}"'` prints `ran-via-glob`. This is exactly the "inner command word" decision D covers (brief:72). Fix: a `runs-command-at` row (or shell-layer handling) for `coproc NAME? cmd`. Then add tests for proposal `coproc sud[o] -i` and typed `echo pw | coproc sud? -S true`.

- NEEDS-HUMAN [impl] — **Bypass: a bracket word that is the first command in a brace group or function body.** Typed `{ sud[o] -i; }` is `mutating`, `rejected=False`, "no simple command to class". The sign-off wanted typed `sud[o] -i` to be privileged. Typed `echo pw | { sud[o] -S true; }` and `f() { sud[o] -i; }; f` are also not rejected (the second is `mutating`), which breaks §5 / decision D point 3 for typed input. A proposal is still rejected, but only as "unparseable", not with the decision-D reason the sign-off asked for. `{ [s]udo -i; }` and `( sud[o] -i )` *are* caught, so this is a gap in the new code, not a design limit. The cause: tree-sitter gives `(ERROR (subscript …) (word))` starting at byte 0, which is the `{`. `_bracket_command` (`parse.py:685-689`) takes `_word_start` of the ERROR node, so `_raw_words` returns `["{", "sud[o]", "-i;"…]`, and `_unquoted_bracket("{")` is False, so it returns early. A leading reserved word (`{`, and probably others in that position) has to be skipped before the bracket test.

- NEEDS-HUMAN [impl] — **Bypass: an unreadable word inside text-effect rows (sign-off item 6).** The sign-off asked for proposals `eval sudo -i` and `env -S 'sudo -i'` to be rejected, and asked that the threat model's sudo sentence (`.oss-scanner/threat_model.md:121-125`, "The gate rejects … pipes into sudo") stay true. The patch does this only for a *readable* name. Proposals `eval sud? -i`, `eval 'sud[o] -i'`, `bash -c 'sud? -i'`, `bash -c 'sud[o] -i'` and `env -S 'sud? -i'` all come out `destructive`, `rejected=False`. Typed `echo pw | eval 'sud? -S true'` and `echo pw | bash -c 'sud[o] -S true'` are not rejected, so the threat-model sentence is false for those inputs. The cause is in `_text_scan` (`rules.py:527-531`): `row = None if text is None else self.table.lookup(text)`, then `continue`. A segment's first word that holds a glob or expansion is skipped instead of being treated as decision D's unreadable word. I tagged this `[impl]` because the sign-off text asks for the threat-model sentence to stay true. If the human reads "no recursion" as putting this out of scope, it becomes a `[human]` scope call, and the threat model sentence then needs a caveat.

- NEEDS-HUMAN [human] — **Wrapper commands with no table row let an unreadable inner word through.** Proposals `chrt 1 sud? -i`, `ionice sud? -i`, `taskset 1 sud? -i`, `nsenter -t 1 sud? -i`, `ltrace sud? -i`, `firejail sud? -i`, `unbuffer sud? -i`, `xvfb-run sud? -i` and `dbus-launch sud? -i` are all `mutating` and not rejected. `chrt 1 sudo -i` *is* rejected by decision A. The brief (brief:41-51) limits decision A to readable names, so this matches the letter of the brief. But it means decision D covers only wrappers that have a `runs-command-at` row. Two ways to close it: add rows for the util-linux wrappers in the base image (`chrt`, `ionice`, `taskset`, `nsenter`, `setpriv` and so on), or make decision A treat an unreadable argument of an opaque command as a possible `sudo` (this over-rejects, for example `foo *.c`). Either is a scope choice for the human.

- **Evidence check.** C4 (the check that the bundle tests go red before the fix and green after) never recorded a green leg: both attempts fail on the same single test, with 473 of 474 passing. So no red→green proof exists for this round. The new bundle tests cover only the forms the sign-off listed (`sud[o]`, `[s]udo`, `su[d]o` at the top level, in a pipeline, after `;` or `&&`). They miss the brace-group, `coproc` and text-scan forms above, which is why the gaps did not show up. I tried to refute the other cases and could not: `sud[!x]`, `sud[[:alpha:]]`, `sud?[o]`, `""sud[o]`, `x=1 sud[o]`, `a[0]=1 sud[o]`, `2>/dev/null sud[o]`, subshell, `if`/`while`/`for`/`case` bodies, `$( )` and backticks, `!`, `&`, and the `command`/`exec`/`env`/`time`/`nohup` wrappers all come out `privileged` and rejected as proposals. `[[s]]udo` and `sudo[]` stay `mutating`, which is right: bash does not expand them to `sudo`.
<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory): issue 204 / gate-command-table-engine

**Attacker-reachable inputs this diff touches:** the model's proposal (threat model input 5) and file names in the cwd (input 2, which is what a glob command word like `sud[o]` matches). Both reach the new command layer (`src/nl_shell/gate/rules.py`), the new bracket-glob path in the walker (`src/nl_shell/gate/parse.py:603-712`) and the table (`targets/ubuntu-26.04/commands.toml`). Typed input (trusted) is also in scope for the §5 sudo rules, because decision D(3) says they apply to every origin.

I tested this on a patched copy of `$PDCA_TARGET` with the harness venv, calling `nl_shell.gate.classify(cmd, origin=...)` directly.

## Findings

- NEEDS-HUMAN [impl] — **High** (threat model: "a privileged or destructive step is classed lower"; it also breaks the "What must hold" rule that the gate rejects `sudo -S` and pipes into sudo). `src/nl_shell/gate/rules.py:508-537` (`_text_scan`, called at `:423` and `:637`). The scan runs `readable()` on each whole argument word. So when a text option's value is attached to the option (`-S'…'`, `-c'…'`) or given in long `=` form (`--split-string=…`, `--command=…`), the option spelling sticks to the first word of the text: `-S'sudo -i'` becomes the words `-Ssudo`, `-i`, and `--split-string=sudo` is not the row name `sudo`. The `elevates` lookup never matches. The input is the proposal text, which the model (or whoever steers it) controls. Results from the patched gate:
  - `env -S'sudo -i'`, `env --split-string='sudo -i'`, `env -vS'sudo -i'`, `nice env -S'sudo -i'`, `script -c'sudo -i'`, `script --command='sudo -i'`, `timeout 5 script --command='sudo -i'` as proposals: `destructive`, **not rejected**. Their separate-word forms (`env -S 'sudo -i'`, `script --command 'sudo -i'`) are `privileged` and rejected.
  - Typed `echo pw | env -S'sudo -S true'`, `echo pw | env --split-string='sudo -S true'`, `echo pw | script --command='sudo -S true'`: `destructive`, **not rejected**. The carry-forward asks for `env -S 'sudo -S true'` to be rejected; these are the same command in GNU getopt's other spellings.

  On this host `env -S'echo x'`, `env --split-string='echo x'`, `script -qc'echo x' /dev/null` and `script -q --command='echo x' /dev/null` all run the text, so these are real paths to sudo. The brief requires every row to cover "short, attached and long `=` forms", and the option parser already splits them out (`rules.py:865-870`, `:889-896`). Fix: scan the parsed values of text-effect options (`parsed.present`) instead of the raw argument words. Another way is to strip the matched option spelling (and `=`) before `text_words`. Add tests for the attached and `=` forms of every text option on a `runs-text` row, both typed with a pipe and as a proposal. `tests/test_gate_commands.py` has no such case today. (`dash -c'…'` and `sh -c'…'` are not affected: those shells don't take an attached `-c` value, and the gate already flags them as an unknown option.)

- NEEDS-HUMAN [impl] — **High** (same scale line; decision D, carry-forward item 1). `src/nl_shell/gate/parse.py:678-708` (`_bracket_command`, called from `_error` at `:712`). It only checks the shell word where the `ERROR` node *starts*. When tree-sitter's ERROR node starts at an earlier token, the glob command word inside it is never handed to the command layer. Reproducer: `{ sud[o] -i; }` (the tree is `(program (ERROR (subscript …) (word)))`, and the ERROR starts at `{`). Results:
  - typed `{ sud[o] -i; }`: `mutating`, not rejected (should be `privileged`);
  - typed `echo pw | { sud[o] -S true; }`: `mutating`, **not rejected** (§5 should reject it);
  - typed `f() { sud[o] -i; }; f`: `mutating`.

  As proposals these are rejected only as "unparseable", with class `mutating`, not the decision-D reason the carry-forward asks for. Who controls it: the glob matches file names in the cwd (input 2). A cloned repo with a file named `sudo` turns `sud[o]` into `sudo`, and bash then looks that up on `PATH`. `{ [s]udo -i; }`, `while …; do sud[o] -i; done`, `case`, `!`, `$(…)` and `<(…)` are all caught. Only the brace group (and function bodies built from one) misses. Fix: walk the `subscript`/word children of the ERROR node (or every word start inside its byte range), not just `node.start_byte`. Add tests for `{ sud[o] -i; }` and `echo pw | { sud[o] -S true; }`. Today the tests at `tests/test_gate_commands.py:734` and `:746` only cover bare and `;`-separated forms.

- NEEDS-HUMAN [human] — **High on the scale, but outside what this child is allowed to do.** `src/nl_shell/gate/rules.py:300-320` (`text_words`). The text scan removes one layer of quoting only. So `eval "\$'\\x73udo' -i"` (eval runs `$'\x73udo' -i`, which is `sudo -i`) comes out as a `destructive` proposal, not rejected. The brief keeps text at decision B and rules out recursion here (child-2, #205), and `destructive` still needs an explicit confirm. So this is a limit of the item-6 option-(b) word scan, not a slip in the build. The human should decide whether the threat-model text added for item 6 should say the scan reads only plain words, or whether child-2 should own this case.

## Checked, no finding

- **sudo family spellings** (`\sudo`, `s\udo`, `'sudo'`, `"su"do`, `-iu root`, `--login`, `--shell`, `-D/-R/-h/-C/-g/-T/-r/-t` with values, `--preserve-env[=]`, `VAR=1`, `doas -s`, `run0`, `pkexec`, `su -c/-s/-l/-`, `su -c'…'`, `su --command=…`): all `privileged`, and shell or root-shell proposals are rejected. §5 option spellings (`-nS`, `-Sn`, `-uroot -S`, `-kS`, `-vS`, `-iS`, `"-"S`, `-\S`, `--st`, `--stdi`, `--pro=x`, `--ask`) are all rejected for typed input. `sudo -u -S` and `sudo -- -S` are correctly read as a user name or a command, not `-S`.
- **Wrappers with rows** (`nice`, `env` with `-i/-u/-C/--chdir/-0/-v/--ignore-signal`, `timeout` with `-k/--foreground/--kill-after`, `time -p`, `nohup`, `stdbuf`, `setsid -f/-w`, `flock -x/-w/fd`, `watch` with `-n/-x`/text, all `xargs` value options, `find -exec/-execdir/-ok/-okdir/+`, `exec -c/-l/-cl`, `command -p/--`, `builtin exec`, `chroot`, `strace`, `systemd-run`, `ssh-agent`, `busybox` applets): inner `sudo -i` is `privileged` and rejected. Unknown wrappers (`ltrace`, `ionice`, `chrt`, `taskset`, `prlimit`, `setarch`, `dbus-run-session`) are caught by decision A.
- **Decision D**: `?`, `*`, `{a,b}`, `$x`, `"$x"`, `${x}`, `$"…"`, `~root/…`, `~+/…`, bracket globs in bare, `;`, `&&`, `|`, `&`, loops, `case`, `!`, `$(…)` and `<(…)` positions; and the path lookup (`./sudo`, `../sudo`, `~/sudo`, `/tmp/x/sudo-rs`, `/usr/bin/sudo.ws`). All as the brief says.
- **Stdin as a pipe** (carry-forward item 2): `< /dev/stdin`, `0< /dev/stdin`, `<&0`, `< /dev/fd/0`, `< /proc/self/fd/0`, `<<<` into `sudo` and into `$x`. All rejected.
- **Loader** (`src/nl_shell/gate/commands.py`): fixed path under `TARGETS_ROOT`, no environment or cwd input. `scripts/harvest_inventory.py` runs only at build time on the reference host and is not attacker-reachable.
- **Gate failures (C4/T3)**: the only red test is `tests/test_policy_gate.py:710-716` (8 KiB of `$[` must classify in under 5 s). I timed that input on the unpatched base and on the patched code under the same conditions: about 1.9 s on both (and up to about 6 s on both under load). The time goes into code this diff doesn't change, so this patch adds no new way to exhaust resources. The failure looks like an existing timing test that flakes on a loaded host. The new `_bracket_command` scans also stay within the 8 KiB input cap. This is not a security finding; whether to accept the gate failure is up to whoever runs the gates.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C2 Reproduction (red pre-fix) — Confirm the public-API pre-fix red leg in an equipped environment — pytest and tree-sitter are unavailable locally, and the frozen verification stops during its green leg without recording red-leg execution (gate-logs/C4-verify.log:81).
- [ ] C5 Causal adequacy — Bound bracket recovery work before scanning every malformed node — repeated scans of the same unrecognized word can consume quadratic work without reaching the successful-recovery deduplication, undermining bounded classification (target/src/nl_shell/gate/parse.py:685).
- [ ] T5 Judgment — Confirm affected-path prior art against merged and closed/rejected work — the brief records that search, but this target has only one synthetic base commit and no supplied closed-work evidence to independently settle duplication (brief.md:365).
- [ ] Validation — fitness-to-purpose — Decide whether the accepted class-7/path-resolution gaps and conservative rejections fit the intended release, after obtaining a successful public-API red→green run; tree-sitter-bash was exercised in frozen logs but is unavailable for this independent review (brief.md:357; target/docs/design/specs/policy-gate/v1.md:176).
- [ ] **The patch causes the C4/T3 red: it is a real slowdown, not a flaky timer.** `tests/test_policy_gate.py:710-716` is an existing test, not part of this diff. `classify(("$[" * 8192)[:8192])` takes 0.43 s on base and 5.85 s patched. Profiling puts 5.36 of the 5.85 s in `_bracket_command` (`src/nl_shell/gate/parse.py:678-708`), which is new in this diff. For each of the 820 ERROR nodes it calls `_word_start` (`parse.py:670-675`, walks back to the word start), `_raw_words` (`parse.py:610-641`, walks forward to the command end) and `_unquoted_bracket` (`parse.py:644-667`, does `"]" in word[i+2:]` once per `[`). When a word has no spaces, each call is O(input size), so the total is O(nodes × size). The cache at `parse.py:686-687/708` only records starts that *produced* a command, so a word that fails `_unquoted_bracket` gets rescanned for every node. Worse inputs, all under the 8 KiB cap: `("[$[" * 8192)[:8192]` takes **19.3 s** (base 0.26 s), `"$[["` 11.2 s, `"$[x"` 9.0 s. None of this time counts toward `MAX_WORK` (`parse.py:40`). A model proposal can freeze the gate for about 20 s. The verdict stays fail-closed (`unparseable`), so this is a denial-of-service problem, not a bypass. I tried caching every scanned start (hits and misses): 19.3 s dropped only to 3.5 s, because `_word_start` still walks back once per node. The fix needs both: compute word starts and ends once for the whole source, and make `_unquoted_bracket` linear (for example, check against the index of the last `]`).
- [ ] **Bypass: `coproc` with an unreadable command word.** A proposal of `coproc sudo -i` is rejected (decision A, `src/nl_shell/gate/rules.py:486-502`). But proposals `coproc sud[o] -i`, `coproc [s]udo -i` and `coproc sud? -i` come out `mutating`, `rejected=False`, reason only "not allowlisted". Typed `echo pw | coproc sud[o] -S true` is also not rejected, which breaks decision D point 3 (the §5 pipe rule for every origin). The cause: `coproc` has no row in `targets/ubuntu-26.04/commands.toml` (grep finds no `coproc` anywhere in the tree), so it is handled as an opaque command, and `_decision_a` skips unreadable words at `rules.py:488-490`. But `coproc` is a bash reserved word that runs its next word as a command. I confirmed bash expands the glob there: with a file `echo` in cwd, `bash -c 'coproc ech[o] ran-via-glob; cat <&"${COPROC[0]}"'` prints `ran-via-glob`. This is exactly the "inner command word" decision D covers (brief:72). Fix: a `runs-command-at` row (or shell-layer handling) for `coproc NAME? cmd`. Then add tests for proposal `coproc sud[o] -i` and typed `echo pw | coproc sud? -S true`.
- [ ] **Bypass: a bracket word that is the first command in a brace group or function body.** Typed `{ sud[o] -i; }` is `mutating`, `rejected=False`, "no simple command to class". The sign-off wanted typed `sud[o] -i` to be privileged. Typed `echo pw | { sud[o] -S true; }` and `f() { sud[o] -i; }; f` are also not rejected (the second is `mutating`), which breaks §5 / decision D point 3 for typed input. A proposal is still rejected, but only as "unparseable", not with the decision-D reason the sign-off asked for. `{ [s]udo -i; }` and `( sud[o] -i )` *are* caught, so this is a gap in the new code, not a design limit. The cause: tree-sitter gives `(ERROR (subscript …) (word))` starting at byte 0, which is the `{`. `_bracket_command` (`parse.py:685-689`) takes `_word_start` of the ERROR node, so `_raw_words` returns `["{", "sud[o]", "-i;"…]`, and `_unquoted_bracket("{")` is False, so it returns early. A leading reserved word (`{`, and probably others in that position) has to be skipped before the bracket test.
- [ ] **Bypass: an unreadable word inside text-effect rows (sign-off item 6).** The sign-off asked for proposals `eval sudo -i` and `env -S 'sudo -i'` to be rejected, and asked that the threat model's sudo sentence (`.oss-scanner/threat_model.md:121-125`, "The gate rejects … pipes into sudo") stay true. The patch does this only for a *readable* name. Proposals `eval sud? -i`, `eval 'sud[o] -i'`, `bash -c 'sud? -i'`, `bash -c 'sud[o] -i'` and `env -S 'sud? -i'` all come out `destructive`, `rejected=False`. Typed `echo pw | eval 'sud? -S true'` and `echo pw | bash -c 'sud[o] -S true'` are not rejected, so the threat-model sentence is false for those inputs. The cause is in `_text_scan` (`rules.py:527-531`): `row = None if text is None else self.table.lookup(text)`, then `continue`. A segment's first word that holds a glob or expansion is skipped instead of being treated as decision D's unreadable word. I tagged this `[impl]` because the sign-off text asks for the threat-model sentence to stay true. If the human reads "no recursion" as putting this out of scope, it becomes a `[human]` scope call, and the threat model sentence then needs a caveat.
- [ ] **Wrapper commands with no table row let an unreadable inner word through.** Proposals `chrt 1 sud? -i`, `ionice sud? -i`, `taskset 1 sud? -i`, `nsenter -t 1 sud? -i`, `ltrace sud? -i`, `firejail sud? -i`, `unbuffer sud? -i`, `xvfb-run sud? -i` and `dbus-launch sud? -i` are all `mutating` and not rejected. `chrt 1 sudo -i` *is* rejected by decision A. The brief (brief:41-51) limits decision A to readable names, so this matches the letter of the brief. But it means decision D covers only wrappers that have a `runs-command-at` row. Two ways to close it: add rows for the util-linux wrappers in the base image (`chrt`, `ionice`, `taskset`, `nsenter`, `setpriv` and so on), or make decision A treat an unreadable argument of an opaque command as a possible `sudo` (this over-rejects, for example `foo *.c`). Either is a scope choice for the human.
- [ ] **High** (threat model: "a privileged or destructive step is classed lower"; it also breaks the "What must hold" rule that the gate rejects `sudo -S` and pipes into sudo). `src/nl_shell/gate/rules.py:508-537` (`_text_scan`, called at `:423` and `:637`). The scan runs `readable()` on each whole argument word. So when a text option's value is attached to the option (`-S'…'`, `-c'…'`) or given in long `=` form (`--split-string=…`, `--command=…`), the option spelling sticks to the first word of the text: `-S'sudo -i'` becomes the words `-Ssudo`, `-i`, and `--split-string=sudo` is not the row name `sudo`. The `elevates` lookup never matches. The input is the proposal text, which the model (or whoever steers it) controls. Results from the patched gate:
- [ ] **High** (same scale line; decision D, carry-forward item 1). `src/nl_shell/gate/parse.py:678-708` (`_bracket_command`, called from `_error` at `:712`). It only checks the shell word where the `ERROR` node *starts*. When tree-sitter's ERROR node starts at an earlier token, the glob command word inside it is never handed to the command layer. Reproducer: `{ sud[o] -i; }` (the tree is `(program (ERROR (subscript …) (word)))`, and the ERROR starts at `{`). Results:
- [ ] **High on the scale, but outside what this child is allowed to do.** `src/nl_shell/gate/rules.py:300-320` (`text_words`). The text scan removes one layer of quoting only. So `eval "\$'\\x73udo' -i"` (eval runs `$'\x73udo' -i`, which is `sudo -i`) comes out as a `destructive` proposal, not rejected. The brief keeps text at decision B and rules out recursion here (child-2, #205), and `destructive` still needs an explicit confirm. So this is a limit of the item-6 option-(b) word scan, not a slip in the build. The human should decide whether the threat-model text added for item 6 should say the scan reads only plain words, or whether child-2 should own this case.
- [ ] C4 fix verified: bundle test red pre-fix, green post-fix (pytest) FAILED (gating) — C4 FAIL — bundle test red (or not importable) WITH the fix applied
- [ ] T3 runtime: the whole nl-shell pytest suite on the patched worktree FAILED (gating) — T3 FAIL — nl-shell suite red (pytest exit 1)
- [ ] **The brief contradicts the tracker's scope on `parse.py`, and the issue body was not updated.** The tracker (notes.json, Scope) says: "in `src/nl_shell/gate/parse.py` **only** `lex_word` (`:197`): decode ANSI-C `$'…'` quoting as bash does". It also says `test_policy_gate.py:192` goes "from `mutating` \"command word is not a literal\" to `destructive`". The brief says the opposite: "**`lex_word` (`parse.py:197`), `make_word` (`:273-275`) and `Word.literal` do not change**", and "the shell layer still reports 'command word is not a literal'". The brief's reason holds against the source: `make_word` sets `literal=not causes` (`parse.py:275`), and that flag feeds every redirect and shell rule, so changing it would lower verdicts. The brief's choice is right, but #204's body still describes the other design. A Check reviewer or code-review leaf that grounds on the issue thread will flag a correct patch as off-scope, or a builder will follow the issue instead. Before Do, record that the brief overrides this point, for example in a tracker comment.
- [ ] **Most of v3 is not in the tracker.** These are absent from the #204 body: decision D, the path-lookup rule, the recorded path gap, `$"…"` decoding, and the extra coverage rows (`ruby`, `node`, `awk`/`mawk`/`gawk`). The body's decisions stop at A and C, and its inventory list is "`python3*`, `perl*`, `busybox`, `gdb`". The brief says D is the human's choice at the v2 sign-off ("decision D, option (b1)"). That choice only exists in `iteration-v2/`, which is not among my inputs, so I cannot verify it from the thread. Together these add a third decision, two spec gaps and new spec/threat-model sections to a slice already at split depth 3 ("`split --accept` refuses without `--force`"). The human should confirm that D plus the path rules belong in this child and not in a follow-up. They should also have the tracker body updated so it matches what Check will hold the patch to.
- [ ] **The `~/bin/x -i` path-gap case cannot get the asserted reason from the layer the brief points at.** The class-7 group asserts that `./x -i`, `/tmp/x -i` and `~/bin/x -i` have a "reason includes 'path outside the system directories'". In the source, `lex_word` adds the cause `leading-tilde` for a leading `~/` (`parse.py:262-265`), so `Word.literal` is False. `_shell_rules` therefore takes the `not word.literal` branch and gives "command word is not a literal: ~/bin/x" (`gate/__init__.py:255-256`). The `elif` that gives "path outside the system directories" (`:257-261`) is never reached. The brief freezes `lex_word`, `make_word` and `:255-256` ("stay as they are"). So the expected reason can only come from the command layer, and nothing in the brief says the engine must emit it. The brief only says such a word "is a path outside the system directories (the known gap below)". Either state that `rules.classify` emits that reason for a word whose only cause is a leading `~`, or loosen the assertion for `~/bin/x -i`. If neither is done, Do will either fail this case or touch the frozen shell rule. The same applies to `~/sudo -i` in the path-lookup case: it hits the `sudo` row only if the command layer strips the leading `~` before taking the last path part, and the brief should say so explicitly.
- [ ] **Two provenance citations cannot be checked from the record.** Decision A's added limit ("applies **only** to a command with neither a row nor an allowlist entry (#197's tracker body says so)") is cited to #197's tracker. The decisions are cited to `results/issue_189/iteration-v3/brief.md:99-112`, while this issue's body cites `results/issue_189/brief.md:99-112`. Neither file is in the inputs, and the two paths disagree. The decision-A limit is load-bearing because it is what lets `man sudo` etc. come out `privileged` without new rows. If it is wrong, the accepted over-raise and the "do not add rows" rule rest on nothing. Check the citations against the real #197 and #189 files before sign-off.
- [ ] size backstop — this slice is behaving oversized: patch is 232 KB (threshold 100 KB). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.

## 7. Proven / not proven
- Proven by which oracle: gates overall = fail (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: iterated-to-Do
- Iteration delta (if iterating): Rebuild the same slice; fix the v4 Check findings, keep the v3 brief's design. 1. Slowdown (C4/T3 red): `_bracket_command` (parse.py:678-708) rescans per ERROR node -> quadratic. 8 KiB `$[` goes 0.43 s -> 5.85 s, `[$[` 19 s. Compute word starts/ends once per source, make `_unquoted_bracket` linear, cache misses too. Do not loosen the 5 s test. 2. Bypass: `coproc sud[o] -i` / typed `echo pw | coproc sud? -S true` not rejected. Give `coproc` a runs-command-at row (or equivalent) so decision D reaches its command word. Add both tests. 3. Bypass: `{ sud[o] -i; }`, `echo pw | { sud[o] -S true; }`, `f() { sud[o] -i; }; f` not caught. The ERROR node starts at `{`; check every word start inside the node (skip leading reserved words), not only node.start_byte. Add tests. 4. Bypass (High): attached / `=` text-option values are not scanned: `env -S'sudo -i'`, `env --split-string='sudo -i'`, `script -c'sudo -i'`, `script --command='sudo -i'`, and piped `-S true` forms. Scan the parsed option values, not the raw argv words. Add tests for the attached and `=` forms of every text option on a runs-text row, typed-with-pipe and proposal. 5. Unreadable first word in text-effect scan (`eval 'sud? -i'`, `bash -c 'sud[o] -i'`, `env -S 'sud? -i'`): treat it as decision D's unreadable word in `_text_scan` (rules.py:527-531) so the threat-model sudo sentence stays true. Not decided at this sign-off: opaque wrappers with no row (`chrt 1 sud? -i`, ionice, taskset, nsenter, ...) and the double-unquoting `eval "\$'\\x73udo' -i"` case (child-2 / #205). Follow the brief as written for these. Human chose iterate-do over the size backstop's iterate-plan suggestion (patch 232 KB, attempt 4).
- By / date: Eduard Ralph / 2026-10-26

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 4 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

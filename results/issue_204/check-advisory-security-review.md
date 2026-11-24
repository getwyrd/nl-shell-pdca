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

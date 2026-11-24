# Result — issue 204 / gate-command-table-engine

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: 
- Success criterion: `tests/test_gate_commands.py` passes. Every case goes through the
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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (144 of 380 failed), green with it
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

Review the replacement of the policy gate’s command stub with a reviewed command table, validated loader, and generic argv/effects engine (#204).

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The brief defines falsifiable class floors, proposal rejection, decision A/C, and explicit text-reading exclusions; target docs/design/specs/policy-gate/v1.md:160 and brief.md:249 establish the review boundary. |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing production changes while retaining tests reproduced 144 assertion failures, 236 passes and 11 expected missing-new-loader setup errors; review-red.log and tests/test_gate_commands.py:148 demonstrate the stub’s underclassification. |
| C3 Change | PASS | The changes stay within the specified command-table, loader, engine, inventory, tests and documentation surfaces; src/nl_shell/gate/__init__.py:196 passes origin to the new layer without changing shared word literalness. |
| C4 Verification (red→green) | PASS | Independently restoring the patch yielded 391 passing bundle tests, matching gate-logs/C4-verify.log:17; review-red.log and review-green.log reproduce the asserted red→green transition, without establishing completeness. |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Close two demonstrated in-scope policy bypasses before relying on the engine: sudo -k suppresses inner argv checks (targets/ubuntu-26.04/commands.toml:29), and nonliteral command heads skip decision A (src/nl_shell/gate/rules.py:280); exact public-API repros follow below. |
| T1 Structure | PASS | Per-command meaning resides in reviewed rows and the engine consumes validated grammar/effect objects; src/nl_shell/gate/commands.py:251 and src/nl_shell/gate/rules.py:361 keep loading and evaluation separate. |
| T2 Shape | PASS | The security contract and accepted gaps are updated with the implementation; .oss-scanner/threat_model.md:194 and docs/design/specs/policy-gate/v1.md:134 ground the frozen touch check (gate-logs/T2-threat-model.log:10); independent git diff --check is clean. |
| T3 Runtime | PASS | The complete frozen reference-host output establishes 1524 passed/1 skipped (gate-logs/T3-suite.log:43); the independent sandbox run finished with 1471 passed/2 skipped and 52 socket-permission failures, documented below as host caveats rather than patch defects. |
| T4 Contribution | N/A | Contribution artifacts are intentionally drafted later; the substantive audit must rerun at publish, as gate-logs/T4-contribution.log:10 explicitly states. |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art against merged history and closed/rejected work, and reaffirm the accepted bundle size — this copy has only a synthetic base commit and no remotes or closed-work evidence (review-prior-art.log); brief.md:271 leaves the three-child shape to human sign-off. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the deliberately conservative overclassification and accepted text/code gaps meet the intended proposal safety policy after the implementation findings are fixed; docs/design/specs/policy-gate/v1.md:160 and docs/design/specs/policy-gate/v1.md:198 define those tradeoffs. |

All source citations above and below are relative to the readable, patched PDCA_TARGET (`target/`). The independent stash/pop restored the supplied production changes. No stale-target caveat was necessary. The runtime named in brief.md:216 supplied real pytest and tree-sitter-bash; no parser shim or fixture replaced that dependency. Harness gate wrappers are outside this target by design; their complete captured logs were read. No additional scanner oracle was configured. No INTEGRATION.md was present among the supplied target files.

Independent inventory harvest: `python3 target/scripts/harvest_inventory.py --output inventory-review.toml`, followed by `diff -u target/targets/ubuntu-26.04/inventory.toml inventory-review.toml`, returned no differences. This discharges the brief’s reference-host drift investigation, not the human’s fitness decision. Affected-path history was queried for every path in patch.diff; the disposable repository has no history beyond its synthetic base and no remotes, so merged/closed/rejected prior art cannot be established from this bundle.

1. **Elevated inner-command checks disappear with sudo -k.** At targets/ubuntu-26.04/commands.toml:29, `-k` is included among options disabling `runs-command-at`. Unlike a standalone credential invalidation, `sudo -k command` still executes that command after disregarding cached credentials; the locally installed sudo manuals confirm this usage. Calling `classify("sudo -k true --pdca-undeclared", origin="proposal")` returns `privileged`, `rejected=False`; without `-k` the proposal is rejected. More concretely, `classify("sudo -k git -c core.pager=sh log", origin="proposal")` is accepted, bypassing the elevated class-7 code-option rejection at src/nl_shell/gate/rules.py:393. Keep inner argv classification active when `-k` accompanies a command, including alias spellings, and add regression cases. This violates docs/design/specs/policy-gate/v1.md:168 and docs/design/specs/policy-gate/v1.md:203, not an accepted text-reading gap.

2. **Decision A is skipped for an unreadable command word.** src/nl_shell/gate/rules.py:280 returns before scanning readable arguments when the head is nonliteral, although this command has neither a known row nor an allowlist entry. `classify("$x sudo", origin="proposal")` returns `mutating`, `rejected=False`, whereas `foo sudo` is `privileged` and rejected. Likewise `$x rm -rf x` stays `mutating` rather than reaching decision A’s destructive floor. `env "$x" sudo` only reaches `destructive` and remains accepted, so wrapping does not restore the elevation rule. Apply decision A’s argument scan to this opaque-head branch and test both top-level and wrapped cases; docs/design/specs/policy-gate/v1.md:160 requires these floors. The shell layer’s nonliteral-word reason is not a substitute for decision A.

Host caveat for sign-off: the complete independent suite run ended with 1471 passed, 2 skipped, and 52 failed in 179.27s (review-suite.log:2284). Every failure shows socket creation/bind denied with `PermissionError: [Errno 1] Operation not permitted`, or an assertion receiving that transport error instead of its intended result. They occur in reader/teacher transport tests, outside this patch’s changed files; the isolated reader test reproduces the same restriction at tests/test_reader.py:291. The frozen reference-host suite remains the available evidence for those socket-dependent tests. These failures are not C4 verification defects or evidence that the command engine is broken.

The public-API observations are captured in review-probes.log. To reproduce from the target root, use the Python runtime named in brief.md:216 with `PYTHONPATH=src` and call `nl_shell.gate.classify` on the quoted command strings above with `origin="proposal"`; these checks classify text and do not execute the commands. No capability-probe/load-time symptom guard was introduced by this patch; the C5 concerns are concrete policy omissions.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — gate-command-table-engine (issue_204)

I re-ran the probes myself against `$PDCA_TARGET/src` with the harness venv
(`/home/eddie/nl-shell/nl-shell-pdca/.venv/bin/python3`). Every probe went through the
public `nl_shell.gate.classify(cmd, origin=...)`.

## The evidence (C4 red→green)

- Attempted to refute; could not. `gate-logs/C4-verify.log:17` shows the green leg at
  391 passed. `:6690` shows the red leg at 144 failed, 236 passed, 11 errors. The 236
  passes are mostly `tests/test_policy_gate.py` / `tests/test_targets.py`, which C4 also
  runs (`:10`), plus the floor group, which the brief allows to pass on the stub. Every
  non-floor `tests/test_gate_commands.py` group goes red on the stub: either an
  `ImportError` on the new `nl_shell.gate.commands` (fixture at
  `tests/test_gate_commands.py:98`, imported inside the function as the brief requires)
  or a wrong class. The tests call production `classify`, not a copy. The "144 of 380"
  in `check-gates.json` counts all three files, so it overstates how much of the bundle
  test went red. That is cosmetic, not a refutation.
- Harvester drift check (the brief makes this a human/reviewer job): I re-ran
  `scripts/harvest_inventory.py --output ./inv-rerun.toml` on this host
  (`VERSION="26.04.1 LTS (Resolute Raccoon)"`). It matches the checked-in
  `targets/ubuntu-26.04/inventory.toml` byte for byte. No drift.

## The fix — inputs that break it

- NEEDS-HUMAN [impl] — Class 1 coverage misses interpreters that are installed on the
  reference host: `ruby` (`/usr/bin/ruby` → `ruby3.3`, dpkg section `ruby`), `node`
  (`nodejs`, section `javascript`) and `awk` (→ `/usr/bin/mawk`, section `utils`). The
  harvester only takes packages in sections `("shells", "interpreters")`
  (`scripts/harvest_inventory.py:46`, documented at `:11-13`), so these never reach the
  inventory, and `commands.toml` has no row for them. Concrete failing cases, run on the
  patched tree: `curl x | ruby`, `curl x | node`, `curl x | awk -f /dev/stdin`,
  `ruby -e 'system "rm -rf ~"'` and `awk 'BEGIN{system("rm -rf ~")}'` all come out
  `mutating`, "not allowlisted". Their twin `curl x | python3`
  (`tests/test_gate_commands.py:169`) comes out `destructive`, "runs code the gate cannot
  read". The proposals `sudo ruby`, `sudo node` and `sudo awk 'BEGIN{system("sh")}'` are
  `privileged` but **not rejected**, while `sudo python3` / `sudo perl` / `sudo tclsh`
  are rejected. That breaks the spec's own class-1 claim (`docs/design/specs/policy-gate/v1.md:177-182`,
  "Every binary on the target that … runs … an interpreter, has a row") and the
  "elevation reaches inner commands" decision for these names. The coverage test
  (`tests/test_gate_commands.py:131`) cannot catch it, because it only checks names that
  are already in the inventory. Fix: add rows for `ruby*`, `node`/`nodejs`, `awk`/`mawk`
  (and widen the harvester's name patterns or sections so they land in the inventory),
  plus a regression case for each.
- NEEDS-HUMAN [human] — Commands that can drop to a shell from inside (pagers, editors,
  `login`, `socat`) have no row, so they are not rejected under elevation. Proposals
  `sudo less /etc/shadow`, `sudo more …`, `sudo man ls`, `sudo git log`,
  `sudo journalctl` (each opens a pager where `!sh` gives a root shell), `sudo vi`,
  `sudo nano`, `sudo ed`, `sudo login` and `sudo socat - exec:bash` all come out
  `privileged`, `rejected=False`. Under the brief's harvester rules, class 1 does not
  require rows for these, so this is not a defect against the brief as written. A human
  should decide whether "runs a shell" in class 1 should cover shell escapes like these,
  or whether this goes into the written gap list next to class 7.
- Attempted to refute and could not: ANSI-C lookup (`$'\163udo' -i`,
  `$'\U00000073udo' -i`, `$'s'udo -i`, `s$'u'do -i`, `$'\x2fusr/bin/sudo' -i`,
  `$'sudo\0x' -i`, `foo $'sudo\0x'`, `sudo $'-\x53' true`, `sudo -$'S' true` are all
  caught). `$'\cSudo'` decodes to a control-S word, not `sudo`, so `mutating` is
  correct. Sudo option grammar (`-iS`, `-Si`, `-nS`, `--stdin`, `--prompt=x`,
  `--askpass`, `-uroot -i`, `--user=root -i`, `-ii`, `--login`, unknown `--stdi` →
  rejected as a proposal). Wrappers with value options before an inner `sudo -i`
  (`env -u X`, `env --unset=X`, `env -C /`, `nice -n 5 --`, `timeout --signal=9`,
  `timeout -k 1 5`, `time -p`, `stdbuf -i0 -o0`, `setsid -w`, `watch -x`, every `xargs`
  value option I tried, `find -exec/-execdir/-ok/-okdir`). Elevation reaching inner
  commands through unknown or extra wrappers (`sudo foo bash`, `sudo ltrace bash`,
  `sudo nsenter -t 1 -a`, `sudo ip netns exec x bash`, `sudo setarch x86_64 bash`,
  `sudo prlimit bash`, `sudo capsh --`, `sudo -u#0 bash`, `sudo b\ash`, `sudo "ba"sh`).
  Pipes and here-strings into `su` / `doas` / `pkexec`. Decision C fails closed
  (`src/nl_shell/gate/__init__.py:153-157`). The loader's `functools.cache`
  (`src/nl_shell/gate/commands.py:295`) does not cache a raised `CommandsError`, so a
  broken table cannot be "fixed" by a later cached success.
- Not filed (within the brief's stated gaps): `flock -c 'sudo -i' /tmp/l` and
  `env -S'sudo -i'` are only `destructive`, not rejected, as proposals. That is decision
  B as the brief requires for this child, and child-2 owns it. `foo --opt=sudo` and
  `foo -esudo` stay `mutating`, because decision A does not split words (an accepted
  gap). `sudo -- -i` / `sudo -- -S true` are not rejected, but they run a command
  literally named `-i` / `-S`, which does nothing.

## The verdict

- NEEDS-HUMAN [impl] — The only unwarranted claim is the class-1 coverage claim as the
  spec states it (`docs/design/specs/policy-gate/v1.md:177-178`) and as the green
  coverage test implies. "Every binary … that runs … an interpreter, has a row" is false
  on the reference host (ruby, node, awk; see the first bullet). The test is green only
  because the inventory and the rows share the same blind spot. Either add the rows or
  narrow the spec sentence to what the harvester actually collects.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review — gate-command-table-engine (#204)

**Attacker-reachable inputs this diff touches:** the model's proposal text (threat model "Where untrusted input enters" item 5), which now flows through the new command-layer engine (`src/nl_shell/gate/rules.py`), the new ANSI-C `$'…'` decoder (`rules.readable`) and the table in `targets/ubuntu-26.04/commands.toml`. Indirectly, file contents and command output (item 1/2) reach the engine only as xargs/find input, which the gate never sees. The table itself is read from a fixed path inside the package (`commands.py:65`, `targets.py:28`). No environment variable, cwd or `HOME` is used, so the table is not attacker input.

I tested the patched tree at `$PDCA_TARGET` with the harness venv, calling `nl_shell.gate.classify(cmd, origin=…)` directly. I compared the decoder against real bash 5.3.9 on this host.

## Findings

- NEEDS-HUMAN [impl] — **High** (a privileged step is classed lower; the §5 pipe-into-sudo rule is bypassed). `src/nl_shell/gate/rules.py:188-199` (`_ansi_c`, the `\x`/`\u`/`\U` branch). **Input:** the model's proposal. **What goes wrong:** bash 5.3 accepts the brace form `\x{HH…}` inside `$'…'` (`bash -c "printf %s \$'\x{73}udo'"` prints `sudo`). The decoder sees `{`, finds no hex digits and returns `None`. A word the gate cannot read is then dropped from row lookup (`rules.py:278-288`, depth 0 gives only `mutating`) and from decision A (`rules.py:313-315`, `continue`). The patch claims that `$'…'` is "decoded as bash does" (threat model and `rules.py:25`), and this escape breaks that claim. Measured results:
  - `$'\x{73}udo' -i` as a proposal: `mutating`, **not rejected** (`$'\x73udo' -i` is rejected).
  - `echo pw | $'\x{73}udo' -S true` as a proposal: `mutating`, **not rejected**.
  - `foo $'\x{73}udo'`: `mutating` (should be `privileged`).
  - `$'\x{72}m' -rf build`: `mutating` (should be `destructive`).

  **Fix:** decode `\x{…}` the way bash does. Also fail closed: when a `$'…'` word cannot be decoded, a proposal should be rejected, or the word should at least count as possibly elevating. Today it silently falls back to the opaque `mutating` path. **Add tests:** the four cases above in `tests/test_gate_commands.py`'s decision A group.

- NEEDS-HUMAN [impl] — **High** (a privileged proposal is classed `destructive`, so clean-room re-derivation is skipped). `src/nl_shell/gate/rules.py:446-450` (`_inner`, xargs replace strings). **Input:** the model's proposal, plus the xargs input, which can be file or command output. **What goes wrong:** any inner word that *contains* the replace string is swapped for an opaque "input" word before the inner command is classed. That throws away a literal `sudo` that is plainly in the proposal. Measured results:
  - `printf 's\n' | xargs -Is sudo -i` as a proposal: `destructive`, "inner command the gate cannot read", **not rejected**. With that input, xargs runs `sudo -i` (a root shell).
  - `xargs -Isudo sudo -i`: same result.
  - The brief's own case `xargs -I% sudo % true` is rejected, but only because `%` does not occur inside `sudo`.

  **Fix:** before the swap, run the elevation and decision-A checks on the original words, so a word that names an elevating or shell row still raises and rejects. **Add tests:** `xargs -Is sudo -i` and `xargs -Isudo sudo -i` as proposals, both rejected.

- NEEDS-HUMAN [impl] — **Low** (typed input only; the user is trusted, but a spec §5 MUST is missed). `targets/ubuntu-26.04/commands.toml:21-33` and `src/nl_shell/gate/rules.py:396-399`. **Input:** a typed command, or a command the user copies from a README (text-only attacker). **What goes wrong:** the row says `sudo.ws` "takes the same options" as sudo-rs. But the original sudo parses with `getopt_long`, which accepts any unambiguous prefix of a long option. So `sudo.ws --stdi true`, `sudo.ws --askp true` and `sudo.ws --prom=x true` mean `-S`/`-A`/`-p`. Typed, these come out `privileged` and **not rejected**. Typed `sudo -S true` is rejected (row 21). Proposals with the same words are rejected (unknown option under elevation), and a pipe into them is rejected by the stdin rule. So the gap is typed input with terminal stdin. If sudo passthrough (#13) keys on the session's own `SUDO_PROMPT`, `--prom=` could keep passthrough from starting. That part is unconfirmed, because passthrough is not built. **Fix:** on a row that has rejecting options, treat any unknown `--` option as rejected too, or list the getopt prefixes for the sudo.ws name. **Add test:** typed `sudo.ws --stdi true` rejected.

## Checked, no finding

- **sudo family and §5.** `sudo -S/-A/-p`, bundled (`-iS`, `-nS`, `-px`) and quoted or ANSI-C spellings (`"-"S`, `-'S'`, `$'\x2dS'`) are all rejected. So are `--stdin`, `--askpass` and `--prompt=`, `SUDO_ASKPASS=… sudo -A`, `sudo env SUDO_ASKPASS=… sudo -A`, and pipes into `sudo.ws`. `sudo -E/-R/--/-u … bash`, `su -c`, `su -`, `su -s`, `pkexec --user`, `doas -s`, `run0` and `systemd-run -t/--pty bash` are all `privileged`, and rejected where the brief says.
- **Wrappers.** I tried `env -u/-C/--chdir=/-iC//--block-signal`, unknown wrapper options (`env --ch / sudo -i` is caught by decision A), `nice -5`, `nice --adjustment=`, `timeout --foreground`, `strace`, `setsid`, `stdbuf`, `nohup`, `time -p`, `command`, `builtin`, `exec`, `watch`, `xargs`, `busybox`, a second `-exec` in `find`, and unknown wrappers (`ionice`, `chrt`, `taskset`). Every `sudo -i` underneath is `privileged`, and rejected as a proposal.
- **Destructive rows.** All of the brief's §4 list, plus `rm` via `\rm`, `/bin/rm`, `./rm`, `command rm` and `--recursive`. `unlink`, `mv … /dev/null`, `pkill`, `killall`, `rsync --delete` and `git branch -D` stay `mutating`. That is not a lowering: the stub gave the same, and the brief does not list them.
- **Text effects.** `env -S 'sudo -i'` and `bash -c 'sudo -i'` are `destructive`, not rejected. This is decision B as the brief and the updated threat model state it (the text is not read until child-2). It is pre-existing (the stub gave `mutating`), not made worse, so I did not raise it.
- **ANSI-C decoder against bash.** It matches on `\NNN`, `\0163`, `\uHHHH`, `\UHHHHHHHH`, `\x7`, NUL cut-off, `\400`, unknown escapes and mixed quoting. Besides `\x{…}` (above), `\c?` decodes to 0x1f where bash gives 0x7f. That is harmless: no `\c` form yields a letter. The other mismatches (`$'\''`, `$'\xs'`) fail toward unreadable.
- **Loader.** It uses a fixed `TARGETS_ROOT / "ubuntu-26.04" / "commands.toml"` (`commands.py:65-69`) and checks `resolve()` against the root (`commands.py:306-310`). Any load error becomes decision C (`rules.py:67-70`).
- **Resource use.** 8 KB inputs (4000 plain words, 1000 nested `env`, 400 nested `find -exec env`, 700 ANSI-C words) each class in ≤ 0.06 s. Nesting over 32 is decision C.
- **`scripts/harvest_inventory.py`.** It passes list-form `subprocess` arguments with no shell, and it runs only by hand on the reference host. I did not re-run it for inventory drift: it writes into the target tree, which is read-only for me. That drift check is the human/reviewer step the brief names.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C5 Causal adequacy — Close two demonstrated in-scope policy bypasses before relying on the engine: sudo -k suppresses inner argv checks (targets/ubuntu-26.04/commands.toml:29), and nonliteral command heads skip decision A (src/nl_shell/gate/rules.py:280); exact public-API repros follow below.
- [ ] T5 Judgment — Confirm affected-path prior art against merged history and closed/rejected work, and reaffirm the accepted bundle size — this copy has only a synthetic base commit and no remotes or closed-work evidence (review-prior-art.log); brief.md:271 leaves the three-child shape to human sign-off.
- [ ] Validation — fitness-to-purpose — Decide whether the deliberately conservative overclassification and accepted text/code gaps meet the intended proposal safety policy after the implementation findings are fixed; docs/design/specs/policy-gate/v1.md:160 and docs/design/specs/policy-gate/v1.md:198 define those tradeoffs.
- [ ] Class 1 coverage misses interpreters that are installed on the reference host: `ruby` (`/usr/bin/ruby` → `ruby3.3`, dpkg section `ruby`), `node` (`nodejs`, section `javascript`) and `awk` (→ `/usr/bin/mawk`, section `utils`). The harvester only takes packages in sections `("shells", "interpreters")` (`scripts/harvest_inventory.py:46`, documented at `:11-13`), so these never reach the inventory, and `commands.toml` has no row for them. Concrete failing cases, run on the patched tree: `curl x | ruby`, `curl x | node`, `curl x | awk -f /dev/stdin`, `ruby -e 'system "rm -rf ~"'` and `awk 'BEGIN{system("rm -rf ~")}'` all come out `mutating`, "not allowlisted". Their twin `curl x | python3` (`tests/test_gate_commands.py:169`) comes out `destructive`, "runs code the gate cannot read". The proposals `sudo ruby`, `sudo node` and `sudo awk 'BEGIN{system("sh")}'` are `privileged` but **not rejected**, while `sudo python3` / `sudo perl` / `sudo tclsh` are rejected. That breaks the spec's own class-1 claim (`docs/design/specs/policy-gate/v1.md:177-182`, "Every binary on the target that … runs … an interpreter, has a row") and the "elevation reaches inner commands" decision for these names. The coverage test (`tests/test_gate_commands.py:131`) cannot catch it, because it only checks names that are already in the inventory. Fix: add rows for `ruby*`, `node`/`nodejs`, `awk`/`mawk` (and widen the harvester's name patterns or sections so they land in the inventory), plus a regression case for each.
- [ ] Commands that can drop to a shell from inside (pagers, editors, `login`, `socat`) have no row, so they are not rejected under elevation. Proposals `sudo less /etc/shadow`, `sudo more …`, `sudo man ls`, `sudo git log`, `sudo journalctl` (each opens a pager where `!sh` gives a root shell), `sudo vi`, `sudo nano`, `sudo ed`, `sudo login` and `sudo socat - exec:bash` all come out `privileged`, `rejected=False`. Under the brief's harvester rules, class 1 does not require rows for these, so this is not a defect against the brief as written. A human should decide whether "runs a shell" in class 1 should cover shell escapes like these, or whether this goes into the written gap list next to class 7.
- [ ] The only unwarranted claim is the class-1 coverage claim as the spec states it (`docs/design/specs/policy-gate/v1.md:177-178`) and as the green coverage test implies. "Every binary … that runs … an interpreter, has a row" is false on the reference host (ruby, node, awk; see the first bullet). The test is green only because the inventory and the rows share the same blind spot. Either add the rows or narrow the spec sentence to what the harvester actually collects.
- [ ] **High** (a privileged step is classed lower; the §5 pipe-into-sudo rule is bypassed). `src/nl_shell/gate/rules.py:188-199` (`_ansi_c`, the `\x`/`\u`/`\U` branch). **Input:** the model's proposal. **What goes wrong:** bash 5.3 accepts the brace form `\x{HH…}` inside `$'…'` (`bash -c "printf %s \$'\x{73}udo'"` prints `sudo`). The decoder sees `{`, finds no hex digits and returns `None`. A word the gate cannot read is then dropped from row lookup (`rules.py:278-288`, depth 0 gives only `mutating`) and from decision A (`rules.py:313-315`, `continue`). The patch claims that `$'…'` is "decoded as bash does" (threat model and `rules.py:25`), and this escape breaks that claim. Measured results:
- [ ] **High** (a privileged proposal is classed `destructive`, so clean-room re-derivation is skipped). `src/nl_shell/gate/rules.py:446-450` (`_inner`, xargs replace strings). **Input:** the model's proposal, plus the xargs input, which can be file or command output. **What goes wrong:** any inner word that *contains* the replace string is swapped for an opaque "input" word before the inner command is classed. That throws away a literal `sudo` that is plainly in the proposal. Measured results:
- [ ] **Low** (typed input only; the user is trusted, but a spec §5 MUST is missed). `targets/ubuntu-26.04/commands.toml:21-33` and `src/nl_shell/gate/rules.py:396-399`. **Input:** a typed command, or a command the user copies from a README (text-only attacker). **What goes wrong:** the row says `sudo.ws` "takes the same options" as sudo-rs. But the original sudo parses with `getopt_long`, which accepts any unambiguous prefix of a long option. So `sudo.ws --stdi true`, `sudo.ws --askp true` and `sudo.ws --prom=x true` mean `-S`/`-A`/`-p`. Typed, these come out `privileged` and **not rejected**. Typed `sudo -S true` is rejected (row 21). Proposals with the same words are rejected (unknown option under elevation), and a pipe into them is rejected by the stdin rule. So the gap is typed input with terminal stdin. If sudo passthrough (#13) keys on the session's own `SUDO_PROMPT`, `--prom=` could keep passthrough from starting. That part is unconfirmed, because passthrough is not built. **Fix:** on a row that has rejecting options, treat any unknown `--` option as rejected too, or list the getopt prefixes for the sudo.ws name. **Add test:** typed `sudo.ws --stdi true` rejected.
- [ ] **The tracker record is missing, so the problem framing cannot be checked against the thread.** The bundle has no `notes.json`, no `sources/` and no `dependency-state.json` (cwd holds only `brief.md` and `.claude/`). The brief takes its decisions (A, C, "elevation reaches inner commands", option (a) "at the re-plan") from `results/issue_189/brief.md:99-112` and from the v3/v4 sign-offs, and it relies on `engine/scripts/run-verify.sh:196` and `iteration-v3/commands.py:63-73`. None of these files is in the target or in the bundle. Nothing in the record I was given shows that the maintainer chose these decisions. A human should confirm that the bundle was assembled with its thread before sign-off.
- [ ] **The ANSI-C change to `lex_word` is a hidden second change to the shell layer, and it can lower verdicts.** The brief puts it in scope as a narrow fix (`parse.py` "**only** `lex_word`"). But `lex_word`/`make_word` feed the literal flag to every shell-layer rule, not just to the command layer:
- [ ] **Decision A over-raises now, and #198 would later have to lower those classes.** The allowlist is out of scope (#198), so on this child's output every command without a row is "opaque". Under decision A, any argument word that names an `elevates` row makes the command `privileged` and rejected as a proposal. That catches `man sudo`, `which sudo`, `apt show sudo`, `dpkg -L sudo` and `echo su`, unless each of those commands has a row (the brief does not say so). All of these are allowlist-table commands (`v1.md:165-176`) that should end up `read-only`. When #198 makes them allowlisted, their class drops from `privileged` to `read-only`, which `v1.md:241` counts as a v2-only change. The brief should say whether decision A skips allowlisted commands by design, so that #198's drop is defined and not a lowering. It should also either list the rows that keep these commands out of decision A here, or say that the temporary over-raise is accepted.
- [ ] **Spec row 16 contradicts the new behaviour, and the brief does not hand that text to anyone.** `v1.md:268` reads "`$'\x72m' -rf ~` | mutating at least (non-literal word)". After this child, the word is literal and the command is `destructive`. That is a raise, so it is allowed, but the stated reason in the conformance row becomes false. The brief's list of spec text owned here covers "§4/§5 rows, the new §4.1 …" but not the Conformance table. The planner should add row 16 to that list (with the `gate-vectors.toml` row as well), or the Check step will find the spec and the code out of step.
- [ ] **This is several deliverables, not one logical fix.** The listed work includes a generic argv-grammar engine; a TOML format and loader with refusal rules; a full command table covering wrappers, the sudo family, destructive commands, text-runners and every §3 builtin; a host-harvesting script plus a checked-in inventory; the `lex_word` parser change; changes to `test_policy_gate.py`; and new spec §4.1 and threat-model text. The success criterion has about 150 named cases. `scripts/harvest_inventory.py` + `inventory.toml` is its own reviewable change: the brief says it is "reviewed like an allowlist change" and "not run by any test", and its only check is a reviewer re-running it on "this Ubuntu 26.04.1 host". Splitting it out, or the parser change, would cut the review surface Do has to spend. If the human keeps one bundle, the size should be a stated decision.
- [ ] **Some success checks can't be reproduced by a gate.** The class-1 coverage property ("every name in `inventory.toml` has a row") checks the table against an inventory the same builder writes. The only independent check is a reviewer re-running the harvester "on this host" and diffing the output. That depends on the host and isn't a gate, so a missing alias name (`sudoedit-rs`-style) can only be caught by a human. The fixed minimum name list in the test only partly fills that gap. Two more checks are also reviewer-only: "no `os.environ`, `Path.cwd()` … in the loader" (this one could be a grep or AST test), and the `.venv` path in the Reproduction step, which points outside the repo (`/home/eddie/nl-shell/nl-shell-pdca/.venv`). The planner should turn the loader ban into a test, and either state in the brief that harvester drift is human-adjudicated or give the reference host explicitly.
- [ ] size backstop — this slice is behaving oversized: patch is 184 KB (threshold 100 KB). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.

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
- Iteration delta (if iterating): Human chose iterate-do over the size backstop: most of the 184 KB is table data (commands.toml, inventory.toml); keep the slice, fix the demonstrated bypasses. The rebuild must: - Decode bash's `\x{HH..}` brace form in `$'…'` (rules.py `_ansi_c`), and fail closed: an undecodable `$'…'` word in a proposal is rejected (or treated as possibly elevating), never silently `mutating`. Tests: `$'\x{73}udo' -i` rejected; `echo pw | $'\x{73}udo' -S true` rejected; `foo $'\x{73}udo'` privileged; `$'\x{72}m' -rf build` destructive. - xargs replace strings (rules.py `_inner`): run the elevation and decision-A checks on the original words before swapping in the opaque input word. Tests: `xargs -Is sudo -i` and `xargs -Isudo sudo -i` as proposals rejected. - `sudo -k <cmd>` (and alias spellings) must keep classifying the inner argv; `-k` only disables runs-command-at when no command follows. Tests: `sudo -k true --pdca-undeclared` and `sudo -k git -c core.pager=sh log` rejected as proposals. - Apply the decision-A argument scan when the command head is non-literal. Tests: `$x sudo` privileged and rejected as a proposal; `$x rm -rf x` destructive; `env "$x" sudo` rejected as a proposal. - Add rows for ruby*, node/nodejs, awk/mawk (and widen the harvester so they land in the inventory), or else narrow the v1.md class-1 sentence to what the harvester collects. Prefer adding rows. Tests: `curl x | ruby`/`node`, `curl x | awk -f /dev/stdin` destructive; `sudo ruby`, `sudo node`, `sudo awk ...` rejected as proposals. - sudo.ws getopt_long prefixes: on a row with rejecting options, reject any unknown `--` option, or list the prefixes. Test: typed `sudo.ws --stdi true` rejected.
- By / date: Eduard Ralph / 2026-10-26

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 6 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

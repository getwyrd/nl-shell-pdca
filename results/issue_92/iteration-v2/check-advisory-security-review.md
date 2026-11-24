# Security review (advisory): issue 92 / os-target-folder-and-selection

**Attacker-reachable inputs this diff touches:** one, `targets/ubuntu-26.04/allowlist.toml`. It is data, not code, but once #12 loads it, it decides which model proposals (threat model "Where untrusted input enters" item 5) run with no confirm. Everything else in the diff reads trusted or root-owned input: `/etc/os-release` (root-owned), `config.toml` (trusted, threat model §Trusted), `--target` (typed by the user) and `target.toml` (the repo's own file). None of these is on the untrusted list.

Severity uses the threat model's scale. For the allowlist, a rating is the outcome once #12 enforces the file. Today nothing runs, so nothing in this diff can be exploited yet.

## Findings

- NEEDS-HUMAN [human] — **High (a session change the gate misses, which then leads to "a non-read-only command runs with no confirm"),** `targets/ubuntu-26.04/allowlist.toml:907-925` (`man`, `less`, `more`), `:929-940` (`systemctl`, `journalctl`, which open a pager) and `:960-964` (`dpkg`, `dpkg-query`). The file bans `-P`/`--pager`/`-H` on `man` and lists no `+` words for `less`. Its comment says the rest is covered because "pager variables must match the baseline (§7.5)". But §7.5 (`docs/design/specs/policy-gate/v1.md:193-194`) only checks `PAGER`, `MANPAGER`, `SYSTEMD_PAGER`, `GIT_PAGER`, `LESSOPEN`, `LESSCLOSE` and the loader variables. Three other variables put back exactly what the entries ban, and §3 (`v1.md:98-101`) doesn't list them as session-altering either:
  - `MANOPT` is parsed as `man` options before the real command line. Reproduced on man-db 2.13.1: `MANOPT=--pager=/usr/bin/id script -qc 'man ls' /dev/null` ran `id`. So `man ls`, which passes the entry, runs any program.
  - `DPKG_PAGER` sets the pager for `dpkg -l` / `dpkg-query -l` when the output is a terminal, and nl-shell's PTY is one. Reproduced: `DPKG_PAGER=/usr/bin/id script -qc 'dpkg-query -l dpkg' /dev/null` ran `id`.
  - `LESS` (and `SYSTEMD_LESS` for systemd's pager) holds `less` options, which can include a `+!cmd` start-up command. This would get around the `+`-word rule the `less` comment hands to #12. I could not confirm it: my `script` harness did not run even the plain `less '+!touch f' f` case, so the harness, not the variable, is the open question.
  
  The way in is threat model item 4. A repo script the user confirms once (`source scripts/env.sh`, the threat model's own example) runs `export MANOPT=--pager=...`. The gate doesn't flag that change, and every later unconfirmed `man`/`dpkg -l` runs the attacker's program. The fix is a spec decision: add these variables to §3 and §7.5, which "changing §7 requires v2" (`v1.md:207`) may block, or take `man`/`dpkg -l`/`less` off v1. That is why this is tagged [human]. A cheap step the builder can take either way: name `MANOPT`, `DPKG_PAGER`, `LESS` and `SYSTEMD_LESS` in the comments on these entries, the same way the `less` comment already warns #12. This may overlap the deferred findings from round 1. I couldn't see `deferred-findings.json`, so I'm filing it in case it's new.

- **Earlier findings: fixed.**
  - `os_release.read` now falls back only on `FileNotFoundError`. A file it can't read or decode is refused (`src/nl_shell/os_release.py:209-224`), with tests for both cases (`tests/test_targets.py`, `test_os_release_not_utf8_is_refused`, `…permission_denied_does_not_fall_back`).
  - `hostname` now allows only `-s`/`--short`/`-I`/`--all-ip-addresses` with `max_operands = 0` (`allowlist.toml:875-877`). A test pins that set (`test_real_allowlist_hostname_allows_no_resolver_lookup`).
  - The GPU tools now have `max_operands = 0` (`allowlist.toml:971-980`), with a test.
  - The `less`/`more` `+` route now has a comment for #12 (`allowlist.toml:912-918`) and a test (`test_real_allowlist_pins_plus_words_for_less_and_more`). Whether `less` stays on v1 is still the human's call, as the comment says.

## Checked, no finding

- **Path traversal through the target id.** `_ID = [a-z0-9][a-z0-9._-]*` (`src/nl_shell/targets.py:346`) is checked with `fullmatch` on both `--target`/config ids (`:441`) and the id built from os-release (`:553`). No `/` is allowed and the first character can't be `.`, so `..` and absolute paths are refused.
- **No near-match fallback.** `Target.matches` compares `ID` and `VERSION_ID` exactly (`targets.py:381-385`). The folder name and the `[match]` table both have to agree (`:553-556`). There is no `ID_LIKE` path.
- **Mismatch state.** It is recorded in `Selection.matches`/`reason` for #12 (`targets.py:388-400`). The REPL starts only after selection succeeds or refuses (`cli.py:36-50`).
- **Allowlist entries against §6.3.** I read every entry. The `-o`/`--output`/`-T` (sort), `-r` (xxd), `--pre`/`-f` (grep), `-f`/`-L`/`--rawfile`/`--slurpfile` (jq), `-z`/`-C` (file), `-o`/`-R`/`-H` (tree), `-K`/`-D`/`-N` (ss), `-o`/`-c` (apt), `-v` (printf) and the history-changing flags are all left off. The `max_operands` limits match §6.4. Apart from the environment-variable gap above, I found no listed option that writes a file, runs a program or opens a connection.
- **Display of os-release values.** They are printed in the warning and in `:status` (`targets.py:406-423`) without escaping. The file is root-owned and not on the untrusted list, so this is not a finding.
- **The T2 gate.** It reports "no security-relevant path touched" for a new allowlist. Round 1 already raised that and the human holds it, so I'm not raising it again.
- **Tests.** The tests cover the attacker-relevant shape of the allowlist (cases g, h and the new pins). The environment-variable route can't be tested until #12 exists. Nothing else is missing in the tests for this diff.

<!-- pdca:leaf-complete -->

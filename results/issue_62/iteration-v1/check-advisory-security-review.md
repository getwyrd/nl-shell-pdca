# Security review (advisory) — issue 62, failure classes by exit code

**Attacker-reachable inputs this diff touches:** the confirmed command text (trusted as a user decision, but it can be a model proposal, threat-model item 5); the done record's exit status (trusted, though fd-3 records can be forged — known gap #135); and the package names read from the target's command-not-found SQLite file. It does **not** read stderr or PTY output (threat-model item 1). `inspect.signature`, the `CommandResult.output` row and the source text confirm this.

Rubric: `target/.oss-scanner/threat_model.md`, its severity scale. I followed `AGENTS.md`; it lists no deferrals that apply here.

## Findings

- NEEDS-HUMAN [human] — **Below Low on the scale (no must-hold broken today: there are no consumers yet). It weakens the brief's own sudo rule.** `src/nl_shell/failure_classes.py:160-162`. Input: the confirmed command text, which the model can shape (item 5). The privilege-wrapper class only fires when the *first* shell word is `sudo`/`su`/`pkexec`/`doas`. Any prefix the policy gate (the deterministic check that classes each command before it runs) still treats as privileged gets past it: a wrapper, an assignment, or a list. The failed authentication then comes out as `OTHER`, with `offer_correction=True` and `to_reader=True`. Once #17 is built, it would offer a correction (likely a sudo re-run) for a failed sudo auth, which is exactly what the brief and ADR-0006 rule out. I ran the patched module against `Done(status=1)`:
  `env sudo apt update`, `command sudo apt update`, `time sudo apt update`, `FOO=1 sudo apt update` and `true && sudo apt update` → all `OTHER True True`. Plain `sudo apt update` → `PRIVILEGE_WRAPPER False False`.
  The password itself is not exposed: passthrough stops capture (ADR-0015), so the reader never sees it. The brief chose "first word" on purpose, and #12's parse replaces it. So a human decides between two options. One: accept this until #12. Two: ask for the safe-side rule now ("a wrapper word anywhere in the command plus that wrapper's failure status → wrapper failure") plus test rows for the inputs above. The test table has no row for a wrapped or listed sudo.

- NEEDS-HUMAN [impl] — **Low.** `src/nl_shell/failure_classes.py:171`. Input: the not-found command word from the confirmed text. The display guard (`isprintable()`, at most 64 chars) does its job. `'\x1b[2Jfoo‮'` gives the message `"Command not found."` with no escape and no bidi character (bidi: invisible marks that flip the display direction of text). But no test covers it: every not-found row uses plain ASCII, so taking the guard out would keep the suite green. Add rows with an ESC byte, a bidi override (U+202E) and a 65-char word, and assert none of them reach `message`. Related: `Failure.command_word` (set right after line 177) keeps the raw word unfiltered. A later consumer (#17, `?why`) that prints it would skip this guard. A docstring line saying "not display-safe" or a test that pins the behaviour would make the contract clear.

- NEEDS-HUMAN [human] — **No severity (threat-model upkeep).** `targets/ubuntu-26.04/target.toml` `[command_provider]` and `src/nl_shell/failure_classes.py:278-280` add a new trusted local input: the root-owned `/var/lib/command-not-found/commands.db`, plus a SQL query taken from `target.toml`. The threat model's "Trusted" list doesn't name it. The T2 gate said "no security-relevant path touched" (`gate-logs/T2-threat-model.log`), so nothing pushed an update. The threat model says each change that lands code updates it. A human should decide whether to add this file under "Trusted" (similar to the dpkg-owned man pages) in this patch or in the docs pass the brief defers.

## Not a security finding (correctness, for code-review)

`failure_classes.py:171-177`: if the word fails the display guard but the lookup still returns packages, the message reads `"Command not found: None. It is provided by the package htop."`. I reproduced this with a 70-char word and a fake lookup. Nothing leaks; it is just a bad template.

## Checked, no finding

- **SQL injection:** none. The command word is a bound parameter (`:280`). The query text comes from the repo's `target.toml` (trusted config). Multi-statement queries fail inside `sqlite3`, and that error is caught.
- **Read-only / no network (ADR-0003):** `mode=ro` URI, 1 s timeout, all errors give `()`. The test shows an `INSERT … RETURNING` writes nothing, and a missing file is not created.
- **Package names reaching messages:** the `re.fullmatch` Debian-name rule drops `htop; rm -rf ~`, `htop\nevil`, `HTOP` and `-htop`, and keeps at most 5 names (`_packages`). Tests cover both good and bad names.
- **Wrapper name in messages:** it only comes from the fixed `WRAPPER_FAILURE_STATUS` keys, so no attacker text gets in.
- **Path traversal through target loading:** this diff doesn't change it. `command_provider.path` must be absolute and comes from trusted repo config.
- **Resource use:** `fetchall()` has no row cap, but the source is root-owned system data, not attacker-sized.
- **Forged exit status:** a command writing a fake `D` record on fd 3 could move a failure between classes. That is known gap #135, and this patch doesn't widen it.
- **Toolchain:** none missing. I ran the reproducers above on the patched source with the host's `python3`.

<!-- pdca:leaf-complete -->

# Security review (advisory): issue 92 / os-target-folder-and-selection

**Attacker-reachable inputs touched: none.** The patch reads four inputs, and the threat model (`.oss-scanner/threat_model.md`, "Where untrusted input enters" / "Trusted") lists none of them as untrusted:

- `--target <id>`: typed by the user, so trusted.
- `$XDG_CONFIG_HOME/nl-shell/config.toml`: nl-shell's own config in the user's home, listed as trusted.
- `/etc/os-release` and `/usr/lib/os-release`: root-owned system files. They are not command output, repository content or anything else a text-only attacker writes.
- `targets/<id>/target.toml`: shipped with nl-shell. The root is fixed relative to the package (`src/nl_shell/targets.py:28`, `Path(__file__).resolve().parents[2] / "targets"`), not to the cwd. So `cd` into a cloned repository with its own `targets/` folder can't swap in a different target.

## What I checked

- **A cloned repo can't plant a target.** The targets root doesn't depend on the cwd (`targets.py:28`). A target id must be a plain folder name (`targets.py:34-35`, `:116-117`), and the resolved folder must stay under the root, so a symlink can't escape it (`targets.py:135`). The id must also equal the folder name (`_validate`).
- **A mismatch is never recorded as a match.** A named target is marked as matching only when os-release was read and its `ID`/`VERSION_ID` match exactly (`targets.py:231`). If os-release can't be read, `release is None`, so `matches=False` with the fixed reason. Automatic selection needs the folder `<ID>-<VERSION_ID>` and its `target.toml` to agree with os-release (`targets.py:252`). There is no `ID_LIKE` or near-version fallback. This matters for #12: the gate will lean on `matches=False` to force a confirm on every command, and the patch never sets it to `True` wrongly.
- **Bad files are refused cleanly.** Bad TOML, invalid UTF-8, unreadable files and wrong types in `config.toml`, `target.toml` or os-release all raise named errors. `cli.py` catches them and exits 1 with no traceback. The os-release parser (`os_release.py:_unquote`) is a single linear pass with no backtracking regex, so a large or odd file can't cause a hang.
- **`:status` lines don't leak between sessions.** They moved from a module-level list (`STATUS_LINES`) to a per-`Repl` tuple (`repl.py`, `input_modes.status`), so one session's target can't show up in another `Repl`. That fixes a small correctness risk; it doesn't add one.
- **Values printed to the terminal.** The start-up warning and `:status` print os-release `ID`/`VERSION_ID` and the target's `display_name` without escaping. A terminal escape sequence could only get in through a root-owned file or nl-shell's own target folder, and the threat model doesn't count either as untrusted. Not a finding.
- **`package_owner_query`** (`["dpkg", "-S"]`) is loaded and validated as a list of non-empty strings, but nothing runs it in this patch. Whether running it is safe belongs to the gate (#12 / ADR-0013), not this patch.
- **Tests.** The brief's cases (b), (c), (e), (f) and (g) cover the refusal and mismatch paths, including `../x`, ids containing `/`, and an unreadable os-release when a target is named. Gates C4 and T3 pass (`gate-logs/C4-verify.log`, `gate-logs/T3-suite.log`). T2 reports "no security-relevant path touched", which matches my reading.

## Findings

No findings. The patch touches no attacker-reachable input and doesn't weaken any "What must hold" property. Its one security-relevant output is the `matches` / `reason` state that #12 will read, and that state fails closed: every unclear case is recorded as "does not match".

<!-- pdca:leaf-complete -->

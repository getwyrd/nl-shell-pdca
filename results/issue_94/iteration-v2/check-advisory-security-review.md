# Security review: issue 94 / architecture-os-targets

Attacker-reachable inputs this diff touches: **none.** The patch changes only Markdown in `docs/design/architecture/` (chapters 01–08 and 10) and adds `tests/test_architecture_targets.py`, which reads those files from a fixed repo path and checks for substrings. No REPL, gate, PTY, reader, installer or loader code changes, so none of the threat model's 11 untrusted-input entry points reaches a changed line.

What I checked:

- **Weight integrity wording** (`docs/design/architecture/07-deployment-view.md:33-43`). The text requires SHA-256 checks against `model.toml` before use, says the REPL must refuse weights whose hash does not match, says downloads happen only at install or explicit update, and says adapters are tied to the target plus the base-weight hash. That matches ADR-0023 (`docs/design/adr/*0023*`, lines 62-70). It labels these as requirements that are not built yet, so the doc does not claim a supply-chain protection that does not exist. Nothing here weakens the Critical "tampered model installed without detection" property.
- **Taint labels** (`docs/design/architecture/08-crosscutting-concepts.md`, §8.2 table). The local-reference row changes from "dpkg-owned man pages" to "the active target's package-owned man pages … (dpkg for `ubuntu-26.04`)". For the only target that exists, the trust level and source stay the same. Labels for untrusted input are unchanged.
- **Gate, reader and sudo wording** (§8.3, §8.5, `06-runtime-view.md`, `10-quality-risks-glossary.md`). These edits only say which details belong to the target. The class behaviours, the reader's "no free text / no network" rule and the password-leak mitigation are unchanged. No removed line drops a confirm, taint, sensitive-read or password requirement (I grepped the removed lines for these terms).
- **Open decisions.** Both stay `[OPEN]` (`07-deployment-view.md:70,72`). Nothing commits to a network host.
- **New test.** It only reads files under a constant `ROOT`. It runs no subprocess, uses no eval and takes no outside input. A docs-only change needs no attacker-case test.

No findings.

One note, not a finding and with no action needed for this patch: "the active target's package-owned man pages" is now the general rule for local-reference trust. When a second target is added, its package database and harvest need the same review that dpkg got (root-owned, harvested in the reference VM, no arbitrary binaries run). The threat model's trusted list still names dpkg only, which is correct today.

<!-- pdca:leaf-complete -->

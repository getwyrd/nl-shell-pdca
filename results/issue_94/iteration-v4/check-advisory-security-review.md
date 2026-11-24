# Security review — issue 94 / architecture-os-targets

**Attacker-reachable inputs touched: none.** The patch changes only architecture Markdown under `docs/design/architecture/` and adds `tests/test_architecture_targets.py`, which reads those Markdown files from a fixed repo path (`tests/test_architecture_targets.py:4`, ROOT) and does string checks. None of the eleven entry points in `.oss-scanner/threat_model.md` ("Where untrusted input enters") is touched: no runtime code, gate, PTY, reader, installer or model-loading path changes. The T2 gate agrees ("no security-relevant path touched", `gate-logs/T2-threat-model.log`), and T3 is green (1334 passed, `gate-logs/T3-suite.log`).

## Findings

No finding.

## What I checked

Docs-only patches can still do harm if they misstate a security property, so a later builder implements the weaker version. I compared every security-relevant sentence the patch changes against ADR-0023 (`docs/design/adr/0023-os-targets.md:37-81`), policy-gate/v1 (`docs/design/specs/policy-gate/v1.md:33-49`) and the threat model's "What must hold":

- **Model integrity** (`docs/design/architecture/07-deployment-view.md`, new "Model integrity (planned)" paragraph): keeps both MUSTs from ADR-0023 (installer verifies SHA-256 before use; REPL refuses a weight file whose hash differs from the active target's manifest) and the "install or explicit update only, never at run time" rule. It is marked as not built, which is accurate. Nothing about signing was removed from chapter 07. That chapter never mentioned signing, so the threat model's "signed model download" wording is unaffected. The Critical item "tampered model installed without detection" is not weakened.
- **Adapters**: "stored per target and base-weight hash … must not load an adapter on different weights" matches ADR-0023:68-70.
- **Local-reference trust level** (`08-crosscutting-concepts.md`, provenance table): "dpkg-owned" becomes "the active target's package-owned … harvested in that target's reference VM". This matches policy-gate/v1's "Package-owned" definition (target's package-owner query, `dpkg -S` on ubuntu-26.04). For the only existing target it is the same set, so it does not widen what counts as trusted.
- **Quarantined reader** (§8.5): names are now "confirmed by the active target's package data/query", but the section still says the reader has no network and that names not confirmed by local lookups are dropped. This is consistent with the threat model's rule that reader lookups be local and read-only and never use `$PATH`.
- **Target mismatch** (`05-building-block-view.md`, "REPL start-up (built)" and "Gate integration (planned)"): the patch says a named-target mismatch currently only prints a warning, and that ADR-0023's "every command needs a confirm" degraded mode is planned. I checked this against the code: `src/nl_shell/cli.py:79` prints the warning, and `src/nl_shell/targets.py:9-10` does exact `ID`/`VERSION_ID` matching with no `ID_LIKE` fallback. The doc is accurate and does not claim protection that does not exist. The missing degraded-mode confirm is a gap that existed before this patch. It cannot be reached today because the gate is not yet wired to run commands. When #12/#190 wire the gate, that work needs to add the degraded-mode confirm. This patch does not change that.
- **sudo / password path** (`06-runtime-view.md` §6.2, `10-quality-risks-glossary.md` risk row): only adds "on ubuntu-26.04 / the target's sudo implementation" qualifiers. Passthrough and `SUDO_PROMPT` requirements are unchanged.
- **The new test**: it has no subprocess, network or file write. It only reads files in the repo. Its asserts check that the planned-status wording stays ("awaiting implementation", "not implemented", "not an assertion that these already ship"), which helps stop a later edit from claiming integrity checks are built when they are not.

<!-- pdca:leaf-complete -->

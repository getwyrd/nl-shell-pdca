# Security review — issue 94 / architecture-os-targets

Attacker-reachable inputs this diff touches: **none.** The patch changes only Markdown architecture chapters (`docs/design/architecture/01`–`08`, `10`) and adds a doc-assertion test (`tests/test_architecture_targets.py`). It changes no code in `src/`, so no gate, PTY, sudo, reader, taint or installer path changes behavior.

## What I checked

- **Threat model "Where untrusted input enters", items 1–11:** no changed line parses, runs or shows any of them. The only one the text touches is item 9 (downloaded weights), and only as a description of planned work.
- **Model integrity text vs ADR-0023** (Critical on the scale: "a tampered model or binary is installed without detection"). `07-deployment-view.md` (new "Model integrity (planned)" bullet, around line 23 of the patched chapter) matches `target/docs/design/adr/0023-os-targets.md:57-71`. Both say: SHA-256 is checked against `model.toml` before use, the REPL must refuse a mismatched hash, downloads happen only at install or explicit update (never at run time), and adapters are bound to target plus base-weight hash. The patch does not weaken the requirement. It labels the checks as "requirements awaiting implementation", which is accurate, so nobody reads them as already enforced.
- **Gate claims in `05-building-block-view.md`** ("Target folder and consumers"). It says the gate integration (package-owner query, `sensitive.toml`, `allowlist.toml`, confirm-everything on a mismatched named target) is planned and not built. It says a mismatched named target today only gives a warning. That is accurate and does not overstate any safety property in "What must hold". The threat model already says the gate's command layer fails closed (every simple command is at least `mutating`), so a missing allowlist cannot let a command run unconfirmed.
- **Trust labels in `08-crosscutting-concepts.md`.** The local-reference row now says "package-owned man pages … (`dpkg` ownership on `ubuntu-26.04`)" instead of "dpkg-owned". This scopes the same trust to the active target. It does not widen what counts as trusted.
- **The new test** reads only repository files under `docs/design/architecture/` through a fixed path. It takes no external input. The C4 gate is `unverifiable` (docs-only patch, `gate-logs/C4-verify.log`), which is expected for this kind of change and is not a security finding.

## Findings

No security findings. No attacker-reachable input is touched, and the changed text keeps the model-integrity and gate requirements as ADR-0023 and policy-gate/v1 state them.

One small wording point, not a finding: the threat model's Installer line still says "signed model download", while ADR-0023 and this patch describe a SHA-256 check against a shipped manifest. The patch did not touch the threat model and did not create this gap, so I am not filing it here.

<!-- pdca:leaf-complete -->

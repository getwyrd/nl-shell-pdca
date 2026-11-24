# Security review — issue 94 / architecture-os-targets

Attacker-reachable inputs touched: **none**. The patch changes only architecture docs
(`docs/design/architecture/01`–`08`, `10`) and adds a docs test
(`tests/test_architecture_targets.py`). No code that handles command output, file names,
environment, session state, model output, the reader or downloaded weights changes, so
no attacker can reach any changed line.

What I checked, since the docs restate security requirements and could weaken them on paper:

- **Weights integrity (threat model input 9, supply chain).** `07-deployment-view.md`
  (new section "Planned model integrity and personalization") matches ADR-0023
  (`target/docs/design/adr/0023-os-targets.md:62-70`): SHA-256 per file in `model.toml`,
  check before use, the REPL refuses a mismatched hash, downloads only at install or
  explicit update, adapters tied to target plus base-weight hash. Nothing is weakened, and
  it is marked planned, not built. No finding.
- **Trust labels (`08-crosscutting-concepts.md`, taint table).** "dpkg-owned" became
  "package-owned … dpkg on `ubuntu-26.04`". On the only existing target this is the same
  trusted set the threat model lists. It does not move untrusted text into
  `local-reference`. No finding.
- **Gate and reader wording (§8.3, §8.5).** It only scopes the allowlist, package-owner
  query and package index to the active target. The gate procedure, the confirm rules and
  the reader's reject-whole and drop-unconfirmed-names rules are unchanged. No finding.
- **Open decisions.** Both [OPEN] items (where `model.toml` URLs are hosted, and the
  package channel) are kept. The SHA-256 values travel inside the package, so the
  package channel is what this integrity check finally rests on. That comes from
  ADR-0023 and was already open before this patch, so it is not a finding here.
- **Test.** The new test only checks that phrases are present in the docs. That is enough
  for a docs-only change. No security behavior needs an attacker-path test.

One mismatch already existed before this patch: the threat model says "signed model
download", but ADR-0023 and these docs describe SHA-256 hashes in a manifest. The patch
neither adds nor widens that mismatch, so I am not filing it.

No findings.

<!-- pdca:leaf-complete -->

# Security review (advisory) — docs-checks-internal-links

Attacker-reachable inputs this diff touches: **none** in the threat model's sense. The patch adds a CI/dev-only docs linter (`scripts/docs_links.py`), its tests, and one workflow step. None of it runs inside nl-shell, so it touches none of the eleven "Where untrusted input enters" items (`.oss-scanner/threat_model.md`) and none of the "What must hold" properties (gate, confirm, sudo password, control channel, output rendering). The T2 gate agrees: `gate-logs/T2-threat-model.log` says "no security-relevant path touched".

The only party who controls this code's input is a PR author, who writes the Markdown files the script reads. I checked what that author could do through this patch:

- **Workflow trust boundary** (`.github/workflows/docs-checks.yml:9-14,47-48`): the trigger is still `pull_request` (not `pull_request_target`), `permissions: contents: read` is unchanged, and checkout is unchanged. The new step runs `python -I` (isolated mode, so the PR checkout is not on `sys.path`), uses no `${{ }}` expressions in `run:`, and has no secrets in its env. A PR author can already run arbitrary code in this job and in `tests.yml`, so the new step gives them nothing new. No finding.
- **PR can switch off its own link check**: the step runs the PR's copy of `scripts/docs_links.py`, unlike the freeze step, which runs the base copy (`docs-checks.yml:26-43`). A PR could edit the script so it always passes. This is about docs quality, not a security property, and the brief scoped it this way. Not a finding; noting it so the difference from the freeze step is a known choice.
- **Path traversal** (`scripts/docs_links.py:318-320`): the link target is joined and `normpath`'d, then only looked up in in-memory sets built from `git ls-files`. Nothing is opened or stat'd based on a link destination, so `../../etc/passwd` just gets reported as broken. Files that do get opened (`:308`) come only from `git ls-files`. No finding.
- **Command injection** (`scripts/docs_links.py:281-284`): `git` is called with a fixed argv list, without `shell=True` and without any value taken from file contents. No finding.
- **Resource use** (`scripts/docs_links.py:54,75`): `COMMENT_RE` (`<!--.*?-->` with DOTALL) can go quadratic on a file full of unclosed `<!--`. Only a PR author can trigger it, it only slows a CI job they already control, and it has no runtime reach. No finding.
- **Escape bytes in output** (`scripts/docs_links.py:320-323`): a broken link's destination is printed as-is, so a crafted `[x](<ESC>]52;…)` would reach the terminal of a developer who runs the script locally on an untrusted checkout. The threat model's "Output rendering is filtered" property covers nl-shell's own PTY mirror, `:context` and `:history`, not developer tooling. Also, a developer running a repo's scripts already trusts that repo's code. Out of scope; no finding.
- **Tests**: they use throwaway repos in `tmp_path` with their own git identity and `GIT_CONFIG_NOSYSTEM=1`, and they never touch host git config (`tests/test_docs_links.py:22-28`). No security-relevant behavior is in play, so a friendly-path-only test gap does not apply here.

No findings. No NEEDS-HUMAN items.

<!-- pdca:leaf-complete -->

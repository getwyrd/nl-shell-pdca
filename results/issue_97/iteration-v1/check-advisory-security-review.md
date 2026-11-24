# Security review (advisory) — docs-checks-adr-immutability

**Attacker-reachable inputs touched: none.** The patch adds a CI-only docs check (`scripts/docs_checks.py`, `.github/workflows/docs-checks.yml`), two index sentences and a test file. None of the 11 entry points in `.oss-scanner/threat_model.md` ("Where untrusted input enters": command output, file names, env, session state, model output, history, reader output, model socket, install artifacts, training data, dev teacher) reach this code, and it breaks none of the "What must hold" properties: nothing here runs in the REPL, gate, PTY, sudo path or installer. The T2 gate agrees (`gate-logs/T2-threat-model.log`: "no security-relevant path touched"). No findings are rated on the threat model's scale.

What I checked anyway, on the CI side:

- `.github/workflows/docs-checks.yml:9` uses `pull_request`, not `pull_request_target`, with `permissions: contents: read`. Fork PRs get no secrets and only a read-only token. No finding.
- `.github/workflows/docs-checks.yml:28-29` puts `${{ github.event.pull_request.base.sha }}` / `head.sha` straight into a `run:` line. These are 40-character hex SHAs that GitHub sets, not PR-author text like titles or branch names, so there's no script injection. No finding.
- `scripts/docs_checks.py:142-155` calls git with an argument list (no shell). Refs come from `rev-parse --verify` output, and blob specs are `"<rev>:<path>"`, so a file name that starts with `-` can't be read as an option. `scripts/docs_checks.py:166` uses `--name-status -z`, so names with newlines, quotes or tabs split correctly. No finding.
- Renames are checked at the old path, deletes fail, and the comparison is byte-exact (LF→CRLF fails). So a PR can't slip an edit past the check by moving or re-encoding a frozen file. The tests cover these cases, and C4 shows 63/63 red without the fix and green with it. No finding.

One note on how far the check's integrity goes (not a threat-model finding):

- NEEDS-HUMAN [human] — `.github/workflows/docs-checks.yml:27` runs `scripts/docs_checks.py` **from the PR head**, so a PR can turn off its own check. A PR that changes `scripts/docs_checks.py` so `main()` returns 0, and in the same PR edits the body of `docs/design/adr/0001-record-architecture-decisions.md`, will pass the job. This is the usual limit of a `pull_request` job, and the brief chose it on purpose (the workflow comment at `:7` says so). Fixing it means running the script as it exists at the base SHA (e.g. `git show "$BASE:scripts/docs_checks.py" | python - immutability …`, with a fallback for the first PR that adds it), or requiring CODEOWNERS review on `scripts/docs_checks.py` and the workflow. Either way, a human has to decide where this trust boundary sits, along with the already out-of-scope choice of making the job a required check. Until then, the check catches honest mistakes, not a determined PR author, and reviewers need to read changes to the script itself.

No other findings.

<!-- pdca:leaf-complete -->

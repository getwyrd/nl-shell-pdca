# Security review — issue 7 / docs-checks-adr-immutability-links

**Attacker-reachable inputs touched: none.** The patch adds a CI-only docs check (`scripts/docs_checks.py`, `.github/workflows/docs-checks.yml`), its tests, and two index sentences. None of it is on a runtime path in the threat model's "Where untrusted input enters" list (`.oss-scanner/threat_model.md`: command output, file names, env, session state, model output, history, reader output, model socket, install artifacts, training data, dev teacher). Nothing in the REPL, gate, PTY, sudo passthrough or installer changes. So no finding is rated on the threat model's scale.

What I checked anyway, on the CI side:

- Workflow trigger and token (`.github/workflows/docs-checks.yml:9-12`): `pull_request` only, not `pull_request_target`, with `permissions: contents: read`. Fork PRs get a read-only token and no secrets. This matches the peer `.github/workflows/tests.yml`. No finding.
- Script injection in `run:` (`.github/workflows/docs-checks.yml:26-29`): the only `${{ }}` values are `pull_request.base.sha` and `head.sha`, which are hex commit IDs a PR author can't shape. No title, branch name or body is put into a shell line. No finding.
- Untrusted file paths from the PR (`scripts/docs_checks.py:132-162`, `git_show` / `changed_paths`): paths come from `git diff -z` and are passed as list arguments (no shell), and `git show` gets `<sha>:<path>`, which always starts with the SHA, so a path starting with `-` can't turn into an option. No finding.
- Link mode reads tracked `.md` files with `open()` (`scripts/docs_checks.py:284`, `cmd_links`). A PR could commit a symlink named `x.md` that points outside the repo, and the runner would read and parse it. On a throwaway runner with a read-only token, the worst outcome is link targets from that file appearing in the job log. That isn't an outcome on the threat model's scale. No finding.
- Resource use: the scan is linear in the size of the tracked Markdown, and the regexes have no nested quantifiers that could backtrack badly. No finding.
- Tests: the tests build their own repos with a fixed git identity and `commit.gpgsign=false`, and they don't touch the host git config. Not security-relevant.

One note on whether the check does its job (outside the threat model, for the human to decide):

- NEEDS-HUMAN [human] — `.github/workflows/docs-checks.yml:27` and `:31` run `python scripts/docs_checks.py` from the PR's **head** checkout. A PR can therefore weaken the check and edit a frozen record in the same change. Example: a PR edits the body of ADR-0001 and also changes `AdrClass.frozen` to `return False`, and the job passes. A reviewer would still see the script edit in the diff, and the brief asks for exactly this setup, so this is a design choice, not a builder defect. If the check is later made a required status, a sturdier option is to run the **base** commit's copy of the script, for example `git show "$BASE:scripts/docs_checks.py" > "$RUNNER_TEMP/dc.py"`, falling back to the head copy when the base has none, as in the first PR. Another option is to add CODEOWNERS on `scripts/docs_checks.py`. Not a threat-model finding. No severity label.

Gate evidence: C4 pass (red 54/54 without the fix, green with it), T2 pass ("no security-relevant path touched"), T3 suite green. That agrees with the "none" verdict above.

<!-- pdca:leaf-complete -->

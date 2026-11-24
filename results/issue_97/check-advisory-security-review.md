# Advisory security review — docs-checks-adr-immutability

Attacker-reachable inputs this diff touches: **none** (from the threat model's list). The patch adds a CI job (`.github/workflows/docs-checks.yml`), a standalone script (`scripts/docs_checks.py`), its tests, and two README edits. None of it is nl-shell runtime code. It never touches command output, the state block, the gate, the PTY, sudo passthrough, the model socket, history or the installer (`.oss-scanner/threat_model.md`, "Where untrusted input enters", items 1–11). The T2 gate agrees: `gate-logs/T2-threat-model.log` says "no security-relevant path touched".

**No finding.** To be sure the CI job itself can't be abused by the one party who controls its input (whoever opens the PR: file names, file contents, the PR branch), I checked:

- **Trigger and token:** `.github/workflows/docs-checks.yml:8-12` uses `pull_request` (never `pull_request_target`) with `permissions: contents: read`. A fork PR gets no secrets and only a read-only token, so PR code running there can't write to the repo.
- **Expression injection** (a `${{ }}` value pasted into a shell script, where crafted text becomes shell code): `docs-checks.yml:32-34` passes only `base.sha` and `head.sha` through `env:` and quotes them as `"$BASE"`/`"$HEAD"`. These are commit hashes, not text the PR author writes, such as a title or branch name. Nothing is pasted into `run:` directly.
- **Shell or argument injection via file names:** `scripts/docs_checks.py:149-163` runs `git` from an argument list (no shell). PR-controlled paths only ever show up inside a `rev:path` spec (`git_blob`, `:154`), so a file named `--output=x` or `$(…)` stays a single argument and is never read as an option. `changed_paths` (`:166-183`) reads `-z` output, so names with newlines or quotes split correctly.
- **The PR switching off its own check:** `docs-checks.yml:37-39` runs the base commit's copy of the script, and `python -I` keeps planted modules (a `re.py` in the checkout) off `sys.path`. The fallback to the PR's copy (`:41-42`) only runs when the base doesn't have the script yet. That's a one-time bootstrap, it's documented in the comments, and it's an integrity question for the docs process, not a threat-model property.
- **git running PR-supplied helpers:** the script runs `git diff --name-status`, `cat-file`, `merge-base` and `rev-parse` only. None of these run textconv or external diff drivers, so a PR's `.gitattributes` can't make git execute anything.
- **Resource use:** the work grows linearly with the number of changed paths and the blob sizes. A crafted PR can't make it hang beyond what GitHub's own job timeout allows.

Actions are pinned by tag (`actions/checkout@v4`, `actions/setup-python@v5`), not by commit SHA. The existing `tests.yml:16-17` does the same, and this job has a read-only token with no secrets. It's the repo's existing convention, not something this patch introduces, so I'm not filing it.

The patch's tests (`tests/test_docs_checks.py`) cover the check's logic. No security-relevant test is needed, because no runtime trust boundary changes.

<!-- pdca:leaf-complete -->

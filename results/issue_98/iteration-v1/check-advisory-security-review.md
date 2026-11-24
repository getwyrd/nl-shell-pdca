# Security review — docs-checks-internal-links

Attacker-reachable inputs this diff touches: **none.** The threat model's untrusted inputs
(`.oss-scanner/threat_model.md`, "Where untrusted input enters", items 1–11) are all about
the running nl-shell REPL: command output, file names, env vars, session state, model
output, history, the reader, the model socket, install-time downloads, training data and
the dev teacher. This patch adds a CI-only link checker (`scripts/docs_links.py`), its test
(`tests/test_docs_links.py`) and one workflow step (`.github/workflows/docs-checks.yml:47-48`).
None of it is imported by `src/`, and none of it runs inside the REPL, the gate, the PTY
session, sudo passthrough, the installer or the training data path. The T2 gate agrees
("no security-relevant path touched"). Nothing here can break a "What must hold" property,
so no finding is rated.

What I checked anyway, all with no finding:

- **Workflow trust boundary.** The new step runs under child-1's `pull_request` trigger
  with `permissions: contents: read`. There is no `pull_request_target`, no secrets, and no
  `${{ }}` expression goes into the `run:` line (`.github/workflows/docs-checks.yml:9-13,47-48`).
  It runs the PR's own copy of `docs_links.py`, so a PR can turn off its own link check by
  editing the script. That differs from the freeze step, which runs the base copy. This is
  a check-integrity point, not a security one: the script guards doc hygiene, not a
  security property, and `tests/test_docs_links.py` repeats the check in `tests.yml`.
  `python -I` keeps the PR checkout off `sys.path`, the same way the freeze step does.
- **Path traversal / file reads.** The script opens only paths from `git ls-files` under
  the repo root (`scripts/docs_links.py:295`). Link targets are only normalized and looked
  up in in-memory sets (`scripts/docs_links.py:305`); they are never opened. So
  `[x](../../../etc/passwd)` is just reported as broken. A tracked `.md` symlink pointing
  outside the repo would be read, but only link destinations are printed, never file
  contents, and this runs on a throwaway CI runner with a read-only token.
- **Subprocess / injection.** `git` is called with a fixed argv list and no shell
  (`scripts/docs_links.py` `git()`). File names go through `-z`, so names with newlines or
  quotes can't break parsing.
- **Resource use.** `inline_links` calls `matching_bracket` (`scripts/docs_links.py:162,184`)
  from every `[`, so a file with many unclosed `[` takes quadratic time (for example, 100k
  `[` characters means about 5·10⁹ steps). Only a PR author controls tracked `.md` content.
  In this workflow they can already run any code they want, and the cost is CI minutes on
  their own PR. This is outside the threat model and needs no fix.
- **Test isolation.** The tests set their own git identity and `GIT_CONFIG_NOSYSTEM`, build
  repos only under `tmp_path`, and run the script as a subprocess with a 60s timeout
  (`tests/test_docs_links.py`). They don't touch HOME or host git config.

No findings. Nothing for a human to decide on security grounds.

<!-- pdca:leaf-complete -->

# Security review (advisory) — docs-checks-internal-links

Attacker-reachable inputs this diff touches: **none** under the threat model. The patch adds a CI-only link checker (`scripts/docs_links.py`), its tests, and one workflow step. None of it is nl-shell runtime code, so none of the threat model's "Where untrusted input enters" items (command output, file names in the shell, env, session state, model output, history, reader output, model socket, downloads, training data, dev teacher) reach it. The T2 gate agrees: `gate-logs/T2-threat-model.log` reports "no security-relevant path touched".

**Verdict: no attacker-reachable input touched; no finding.**

What I checked anyway, in case the CI job itself is the concern (none of these is rated, because the threat model doesn't cover CI):

- `.github/workflows/docs-checks.yml:46-48`: the new step runs on `pull_request` (not `pull_request_target`), with `permissions: contents: read`, no secrets, and `python -I` (isolated mode: the checkout is kept off `sys.path`, so a PR can't plant a fake `re.py`). The step runs the **PR's** copy of the script, unlike the freeze step, which runs the base copy. So a PR can turn off its own link check by editing the script. This is a hygiene check, not a protection boundary, the job is not a required check (out of scope per the brief), and the edit would show up in the diff. Not a finding.
- `scripts/docs_links.py:283`: `git` runs with a fixed argument list and no shell, so file names can't inject commands. `scripts/docs_links.py:308`: files are opened only from `git ls-files` output under the repo root. Link targets are only normalized and compared against a set (`posixpath.normpath`). They are never opened, so `../../etc/passwd`-style links can't read anything. A tracked symlink `.md` would be followed when opened, but in CI the PR author already runs their own code, so that adds nothing.
- Resource use: `matching_bracket` (`scripts/docs_links.py:189`, called at `:180` for every `[`) scans to the end of the paragraph when there is no `]`, so time grows with the square of the input. I measured it on the target copy: one paragraph of 5,000 `[` took 0.36 s, and 20,000 took 5.25 s. Inline-code matching (`find_run`, `:148`) stayed fast in the same test. Only a PR author can trigger this, and only against their own CI run (or a test run on a checkout that holds such a file). It falls outside the threat model's attackers and severity scale. I'm noting it for information only; it is not a NEEDS-HUMAN item.
- Tests: the patch is not security-relevant, so I don't require attacker-path tests. The tests set their own git identity and `GIT_CONFIG_NOSYSTEM`, and they don't depend on host config.

No findings.

<!-- pdca:leaf-complete -->

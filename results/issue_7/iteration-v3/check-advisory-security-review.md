# Security review (advisory) — issue 7 / docs-checks-adr-immutability-links

**Attacker-reachable inputs touched: none.** The diff adds a CI (continuous integration) workflow, a stdlib-only docs-check script, its tests and two README edits. None of these touch the 11 untrusted inputs listed in `.oss-scanner/threat_model.md` ("Where untrusted input enters"). Nothing ships in the REPL, the policy gate, the PTY session, the model or the installer, and none of the "What must hold" properties depend on this code. The T2 gate agrees ("no security-relevant path touched", `gate-logs/T2-threat-model.log`).

The threat model does not cover CI, so I also checked the workflow against the usual GitHub Actions risks from a fork PR author. These checks are unrated because the threat model has no severity scale for CI:

- `.github/workflows/docs-checks.yml:9`: the trigger is `pull_request`, not `pull_request_target`, so fork PRs run without repo secrets. `:11-12` sets `permissions: contents: read`. This matches the existing `tests.yml:3-9` and `require-linked-issue.yml:11-16`.
- `.github/workflows/docs-checks.yml:27-29`: the only `${{ }}` values put into a shell `run:` line are `pull_request.base.sha` and `head.sha`. GitHub sets these to 40-character hex strings and the PR author can't control their text, so there is no script injection. No PR title, body or branch name is put into the script.
- `scripts/docs_checks.py:144-158`: every git call uses an argument list (`subprocess.run([...])`) with no shell. Paths from `git diff -z` only appear after a `rev:` prefix in `cat-file` arguments, so a crafted file name (spaces, `;`, a leading `-`, a newline) can't become a shell command or a git option.
- `scripts/docs_checks.py:555`: the links check opens tracked `.md` files and only prints link targets it parses out of them. A tracked symlink pointing outside the repo would let a PR print link-shaped strings from a runner file. That gives the attacker nothing, because a PR can already run any code it likes in this read-only job.
- The actions are pinned by tag (`actions/checkout@v4`, `actions/setup-python@v5`), not by commit SHA. The existing workflows do the same, so the patch adds no new risk here.

One integrity note, not a security finding: the workflow runs the PR's own copy of `scripts/docs_checks.py` (`docs-checks.yml:27,31`). A PR that edits a frozen ADR could also weaken the script in the same PR and still pass. That PR would show a visible change to `scripts/docs_checks.py`, and the comment at `docs-checks.yml:7` shows the choice was deliberate (running PR code without privileges is the safe trade-off). If maintainers want the check to resist this, they could run the script from the base commit, e.g. `git show BASE:scripts/docs_checks.py | python -`. That is a process choice, and I'm not raising it as a NEEDS-HUMAN item.

**No findings.** There are no NEEDS-HUMAN items from this review.

<!-- pdca:leaf-complete -->

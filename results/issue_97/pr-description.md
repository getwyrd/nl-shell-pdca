## Summary
**User impact:** The design docs promise that settled decisions are never rewritten. An
accepted decision record, an accepted proposal or a stable spec is supposed to be replaced
by a new one, not edited in place. Nothing enforced that promise. Anyone could change one
of these documents in a PR, CI stayed green, and the record of what was decided and why
could quietly change after the fact.

This PR adds a CI job that fails any PR that edits, deletes or renames one of these frozen
documents. The only change it allows is moving the document's status to a listed next
state (for example "Superseded by ADR-0023"). The error message names the file and says to
write a superseding record instead.

Reported in [#97](https://github.com/eduralph/nl-shell/issues/97).

## What to look at
- The new **Docs checks** workflow and the script it runs, `scripts/docs_checks.py`.
- One added sentence each in the ADR index and the proposals index, stating the allowed
  status changes.

To try it: on a branch, edit the body of ADR-0001 (it is Accepted) and run
`python scripts/docs_checks.py immutability main HEAD`. It exits 1 and names
`docs/design/adr/0001-record-architecture-decisions.md`. Editing a Proposed ADR or a
draft spec exits 0. On this PR, the job itself should be green, since no frozen file is
touched.

Making the job a required check is a repository setting and is left to the maintainer.

## Root cause
ADR-0001 says "A docs CI check enforces immutability (Foundations milestone)", but no
workflow did: `.github/workflows/` held only `tests.yml`, `require-linked-issue.yml` and
`triage-new-issue.yml`.

## Fix
- `scripts/docs_checks.py immutability BASE HEAD` finds what the PR changed by diffing
  **merge-base → head**. For each changed ADR, proposal or spec it reads the frontmatter
  `status:` on the base side. The value is matched case-insensitively, with any trailing
  `# …` comment, quotes and a leading UTF-8 BOM removed. A file counts as frozen if it is
  frozen at the merge-base **or** at the base tip, following renames the base made since
  the merge-base. A frozen file must be byte-identical at the head except for the status
  line, and the new status must be an allowed next state:
  - ADR (`adr/NNNN-*.md`): frozen unless the status starts with `Proposed`.
    `Accepted` → `Superseded by ADR-NNNN…` only. `Superseded…` has no next state.
  - Proposal (`proposals/{draft,accepted}/NNNN-*.md`): frozen unless `draft`.
    `accepted` → `implemented` / `withdrawn`.
  - Spec (`specs/**/*.md`, not `README.md`): frozen unless `draft`.
    `stable` → `superseded` / `withdrawn`.
  New files, index pages and draft/Proposed records are never blocked. Moving a draft
  proposal from `draft/` to `accepted/` while setting its status to `accepted` passes.
- `.github/workflows/docs-checks.yml` runs on `pull_request` only (never
  `pull_request_target`), with no path filter and `contents: read`. It runs the **base
  commit's** copy of the script with `python -I` (isolated mode), so a PR can neither edit
  the script nor plant a module such as `re.py` to make it pass. The PR that first adds
  the script falls back to its own copy.
- `docs/design/adr/README.md` and `docs/design/proposals/README.md` each gain one sentence
  stating the allowed status changes.

Not covered: a PR that edits the workflow file itself. Closing that needs CODEOWNERS or
branch protection, not code.

## Verification
- **Claim:** an Accepted ADR is never edited and a docs CI check enforces it.
  **Checked:** `docs/design/adr/0001-record-architecture-decisions.md:22-23` and `:30-31`
  on `main` (`bc25e56`). The status vocabulary comes from
  `docs/design/templates/adr.md:4`.
- **Claim:** stable specs are never edited and accepted proposals are immutable.
  **Checked:** `docs/design/README.md:18-21` (class table) and
  `docs/design/proposals/README.md:9-11` on `main`, with the vocabularies in
  `docs/design/templates/{proposal,spec}.md:4`.
- **Claim:** no docs check existed. **Checked:** `.github/workflows/` on `main` holds
  only `tests.yml`, `require-linked-issue.yml` and `triage-new-issue.yml`. `tests.yml:3-6`
  also triggers on `push`, which is why the new workflow does not copy its trigger
  (`pull_request.*.sha` is empty on push).
- **Claim:** frozen edits fail and name the path; allowed changes pass.
  **Test:** `tests/test_docs_checks.py`, 71 tests, all fail without the fix and all pass
  with it. Each must-fail case also asserts the offending path is in the output, so a
  missing or crashing script cannot pass. The suite covers body edits and illegal status
  moves for all three classes, rename and delete, a stale branch that predates a status
  change on `main`, CRLF rewrites, BOM-prefixed files, and template-comment and quoted
  status values.
- **Claim:** a PR cannot switch off its own check. **Test:** the CI step is pulled out of
  the shipped workflow and run against throwaway repos.
  `test_ci_step_runs_the_base_copy_so_a_pr_cannot_disable_the_check` covers a PR that
  edits the script. `test_ci_step_ignores_a_stdlib_module_planted_by_the_pr` and
  `test_ci_step_fallback_ignores_a_module_planted_next_to_the_script` cover a planted
  `re.py`. With only the two `-I` flags removed, exactly those two tests fail.
- **Not shown locally:** that the job fires on GitHub's `pull_request` event. This PR's
  own CI run is that check.

Fixes #97

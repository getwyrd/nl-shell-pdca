# Build notes — issue 7 / docs-checks-adr-immutability-links

Target: eduralph/nl-shell @ main (`bc25e56`), worktree `$PDCA_WORKTREE`. Line numbers below
are in the patched tree unless marked "base".

## What changed

| File | What |
|------|------|
| `scripts/docs_checks.py` (new, 339 lines, stdlib only) | Two modes: `immutability BASE HEAD` and `links`. Runs from any checkout; it `chdir`s to `git rev-parse --show-toplevel` first (`:326`), so `.git` being a file (worktree) doesn't matter. |
| `tests/test_docs_checks.py` (new) | 54 tests. Throwaway git repos in `tmp_path`, the script called as a subprocess via `sys.executable` + a path resolved from `__file__`. Never imported. |
| `.github/workflows/docs-checks.yml` (new) | `pull_request` (no path filter, never `pull_request_target`), `permissions: contents: read`, `actions/checkout@v4` with `fetch-depth: 0`, `setup-python` 3.14 — same shape as `.github/workflows/tests.yml:3-22` (base). Runs both modes with `pull_request.base.sha` / `head.sha`. |
| `docs/design/adr/README.md:9-15` | The scope (2) sentence, inserted after "records the supersession." (base `:9-11`). |
| `docs/design/proposals/README.md:12-13` | The scope (3) sentence, after base `:11`. |

## How each rule is encoded (with sources)

- **Which files count (r3).** `ADR_RE` `:34` = `adr/NNNN-*.md`; `PROPOSAL_RE` `:35` =
  `proposals/{draft,accepted}/NNNN-*.md`; `SPEC_RE` `:36` + the `README.md` exclusion in
  `record_class` `:94-101` = every spec `.md` but `README.md`. Indexes are never matched.
- **Status read from frontmatter, from the base (r1, r2).** `status_line_index` `:104-114`
  finds `status:` only inside the leading `---` block; `status_value` `:117-122` strips a
  trailing `# comment` (the templates carry one, `docs/design/templates/adr.md:4` base),
  quotes, and lowercases. No frontmatter / no status → `check_record` returns early, not
  frozen (`:175-177`).
- **ADRs** (`AdrClass` `:53-61`): frozen unless the base status starts with `proposed`
  (ADR-0001 `docs/design/adr/0001-record-architecture-decisions.md:22-23` base: "starts as
  Proposed. Once Accepted it MUST NOT be edited"). Allowed: base starts with `accepted` →
  head matches `^superseded by adr-\d{4}` (`:38`, vocabulary from `templates/adr.md:4`).
  No `implemented`. A `Superseded…` base has no next state. ADR-0008's
  `Proposed (… superseded by ADR-0019)` starts with `proposed`, so it stays editable
  (decision 4).
- **Proposals** (`ProposalClass` `:64-72`): frozen unless base is `draft`; `accepted` →
  `implemented` | `withdrawn` (`templates/proposal.md:4`, `docs/design/README.md:21`,
  `docs/design/proposals/README.md:10-11` base). No `superseded` state.
- **Specs** (`SpecClass` `:75-82`): frozen unless base is `draft`; `stable` →
  `superseded` | `withdrawn` (`templates/spec.md:4`, `docs/design/README.md:18` base).
- **Only the status line may differ (r5).** `check_record` `:189-208`: line-by-line
  compare; the only differing index must be the base's status-line index, and the head's
  status line must be at the same index. Anything else fails. Delete fails (`:184`),
  rename fails at the old path (`:186`, r4). `git diff --name-status -z -M` (`:145-162`)
  gives the rename pairs. Added files and copies are ignored (`:169`).
- **Draft → accepted move (#6).** Base status `draft` → not frozen → passes, rename or not.
- **Base = merge-base(BASE, HEAD)** (`:211`). On a PR the base sha is main's tip, which
  may be ahead of the branch point; diffing `base..head` directly would blame the PR for
  main's own later commits. Using the merge-base is the `base...head` three-dot diff a PR
  view shows. In the tests history is linear so merge-base = base.
- **Error text** names the path, the class, the base status, and says how to supersede
  (`how_to_change`, `:85-91`) plus a summary line telling the author to supersede with a
  new record + index entry (`:220-225`).
- **Links** (`:232-320`): `git ls-files -z`, tracked files + all their parent dirs.
  Inline/image `](target)` and reference definitions `[t]: target`; fenced blocks
  (``` and ~~~, closing fence must be same char and at least as long) and code spans are
  skipped. Skipped targets: `#…`, `scheme:…`, `//…`. `?query`/`#fragment` are cut, `%xx`
  decoded, `/x` resolved from the repo root (GitHub's behaviour). A link escaping the repo
  fails. Live tree: `docs-links: OK (60 relative links checked)` — the brief's 60/0.

## Red → green (project runner)

`PDCA_BUNDLE=… PDCA_WORKTREE=… engine/scripts/run-verify.sh` (the C4 gate):

```
== C4 green leg: ... 54 passed (ran 54, failed 0)
== C4 red leg:   ... 54 failed (ran 54, failed 54, import/collection errors 0)
PDCA-EVIDENCE: C4 PASS — red without the fix (54 of 54 failed), green with it
```

`engine/scripts/run-suite.sh` (T3, whole suite): `89 passed`, T3 PASS.

## Refuting my own test

- **(a) Genuine red? Yes.** The C4 red leg reverts `scripts/docs_checks.py`, the workflow
  and the README sentences, and all 54 tests fail (none were collection errors, as the
  script is run as a subprocess). That red only shows "script absent", so I also mutated
  the script's rules one at a time and re-ran the test file (venv pytest under `timeout`):
  allowing proposal → `superseded` → 1 fail; letting an Accepted ADR take any status →
  2 fail; treating `Superseded` ADRs as not frozen → 3 fail; not checking renames → 2
  fail; not stripping code spans → 1 fail; ignoring the base → 22 fail. Every mutation
  was caught. The script was restored and the patch re-diffed identical afterwards.
- **(b) Production path? Yes.** Each test runs the real `scripts/docs_checks.py` as a
  subprocess with real `git` on real commits. No mock or copy of the logic. The live-tree
  test runs the same script on the nl-shell checkout itself (worktree, `.git` is a file).
- **(c) Fixture includes the fault? Yes.** Each must-fail repo has the frozen record at
  the base and the forbidden change at the head (body edit, bad status, delete, rename,
  status+body together). Each must-fail assert also checks the offending path (or the
  broken link text and file) appears in stdout, so a crash or empty run can't pass.

## Ruled out

- **Logic inside the workflow YAML** (as wyrd does): C4 classifies `.github/` as
  non-behavioural and would report UNVERIFIABLE (brief, Falsifiability).
- **Importing the script from the test:** on the red leg the import becomes a collection
  error (UNVERIFIABLE), not a red.
- **Diffing `base..head` without merge-base:** see above; false fails when main has moved.
- **Matching proposals in any subdirectory** (stricter): the brief names
  `{draft,accepted}`, so I kept that. A future `withdrawn/` dir would not be checked —
  worth a follow-up if one appears.
- **Checking `#fragment` anchors, wyrd's conformance-vector rule, `docs/plan.md`:** out of
  scope per the brief.

## Commit-readiness

nl-shell has no formatter, linter config, `.pre-commit-config.yaml` or `core.hooksPath`.
`git diff --check` is clean and both Python files compile. CONTRIBUTING requires a DCO
`Signed-off-by` on the commit — that is publish's job, not in the diff.

## Not verifiable here

The "runs on every PR" half (the workflow triggering and passing on GitHub) can only be
seen on the draft PR's own CI run, as the brief says. I did not push or open a PR.

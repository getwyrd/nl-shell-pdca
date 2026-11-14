# Repository integration — nl-shell-pdca

> What nl-shell-pdca provides to plug into the generic PDCA cycle (see
> [quality-cycle.md](../PCDA/quality-cycle.md)). This is the project's answer to the
> "which / where / how" questions the generic model deliberately leaves open.
> It does **not** restate the cycle. Conflict rule: generic wins on cycle
> *shape*; this integration wins on *instantiation*.
>
> The target project is [nl-shell](https://github.com/getwyrd/nl-shell), a
> natural-language shell for Ubuntu 26.04 (Python, pytest). The target checkout is
> the sibling `../nl-shell` (the `[publisher.checkouts]` sibling default); a required
> doctor row verifies it exists. nl-shell's own design docs are the source of truth
> for *what* to build: `docs/design/` (architecture, ADRs, proposal 0001 — the
> milestone plan) and `.oss-scanner/threat_model.md`.
> Maintained by Act (append changes; don't silently rewrite).

## 1. Tracker integration
- **System / URL:** github — https://github.com/getwyrd/nl-shell/issues
- **Issue-ID format:** `#123`
- **Cross-link form (commit/PR → tracker):** `Fixes #{id}` trailer in the commit
  message and a closing keyword (`Closes #NNN`) in the PR body — the same reference
  satisfies nl-shell's `require-linked-issue` required check.
- **Status → disposition mapping:** GitHub binary open/closed. open → in cycle;
  closed via merged PR → `fixed`; closed unmerged → the close reason is the
  disposition (`wontfix` / `duplicate` / not planned), recorded in the closing comment.
- **Per-release field updated on a fix:** the **milestone**. nl-shell plans in named
  milestones (`Foundations`, `M0`–`M5`) from proposal 0001; every issue already
  carries one. Each milestone has a tracker issue whose checklist the fix ticks. An
  issue with no milestone carries the `new` label and is backlog — the planner asks
  before taking one.
- **Plan seeding:** `[[plan.source]] type = "github", role = "tracker",
  repo = "getwyrd/nl-shell"` — the planner reads the full issue thread via `gh`. It
  should also read the milestone's tracker issue and the design docs the issue names
  (`docs/plan.md`, `docs/design/`).
- **Comment voice / template:** `templates/tracker-comment.md.tpl`

## 2. Branch-target rules
- **Per-area branch map:** everything → `main` of `getwyrd/nl-shell` (single line;
  releases are annotated `vX.Y.0` tags at ★ release points, no maintenance branches).
  Changes to **this instance itself** (pdca.toml, engine/, docs/) are ordinary
  nl-shell-pdca PRs to its own `main`, outside the cycle machinery.
- **Override convention:** the brief's `Repo + branch target` field; disputes in the PR review thread.
- **Cross-version cherry-pick rules:** none — one shipping line.
- **Master-vs-maintenance rule:** not applicable; nl-shell `README.md` §Releases is the normative statement.

## 3. Reproduction fixtures and runners
- **Canonical fixture path:** nl-shell `tests/` (pytest). Tests import from `src/`
  directly (pytest `pythonpath`), so a test always runs against the tree it sits in.
  The REPL is driven by a scripted read function, and model output comes from a stub
  backend that returns fixed proposals (architecture §13.1) — **no GPU and no model is
  ever needed to test the safety layer.**
- **Reproduction runner(s) + commands:** a failing pytest in nl-shell:
  `python3 -m pytest tests/<file>::<test>` from the target root (CONTRIBUTING.md).
- **Verification runner (test suite):** `./engine/scripts/run-verify.sh` (C4 red→green
  on the bundle's test, gating) and `./engine/scripts/run-suite.sh` (the whole suite,
  T3, gating). Hands-on validation: `nl-shell-pdca try <id>` starts the patched REPL
  (`[manual_test]`).
- **Platform variants:** Ubuntu 26.04 is the target. Tests that need a real PTY,
  bash or sudo-rs (from M0.2 on) run in a throwaway VM, never against the developer's
  live sudo; GPU backends (M4–M5) are tested on the test matrix, not in the cycle.
- **What counts as a successful repro:** a deterministic failing pytest naming the
  defect, reproducible from a clean worktree of `main`. For the policy gate, that is a
  command string in the classification table that gets the wrong class.

## 4. Conformance ruleset (answers the validation-tooling matrix for this repo)
For each tier: the **written ruleset** it consumes, its **home**, and the
**single-sourced command** the driver and CI both run. The "Written ruleset"
column is load-bearing — name the project's *normative source* for each tier (a
contributor guide, an addon-dev doc, a PEP/RFC) and, ideally, cite individual
rules back to it (`<doc>:<line>`). A gate you can trace to a written source is
auditable; one you can't is folklore.

Gating policy (see `engine/README.md`): ship every tier **advisory**
(`gating = false`) except the per-fix C4 (red→green). Runtime / conformance /
interface tiers audit code the current fix didn't introduce, so promote a tier to
gating only once its targeted artifacts are clean; gate interface/E2E on a smoke
test, not the full suite.

| Tier | Written ruleset | Home | Single-sourced command | Status |
|---|---|---|---|---|
| T1 structure | nl-shell `pyproject.toml` (package layout, pytest config) | asserted by the suite collecting at all | (inside T3) | [built — via T3] |
| T2 shape | nl-shell `docs/design/README.md` (ADR immutability, internal links) | nl-shell CI once nl-shell#7 lands | — | [planned — nl-shell#7] |
| T3 runtime | nl-shell CONTRIBUTING.md "keep the test suite green" + `.github/workflows/tests.yml` | `engine/scripts/run-suite.sh` | `./engine/scripts/run-suite.sh` | **gating**, bundle |
| T4 contribution | nl-shell CONTRIBUTING.md (DCO, one change per PR) + branch protection (`require-linked-issue`) + `templates/pr-description.md.tpl` | `./scripts/pdca contribcheck` + nl-shell CI | `./scripts/pdca contribcheck` | gating, bundle |
| T5 judgment | reviewer contract below + the threat model | Check reviewer, advisory leaves, sign-off | (model) | [built — stub leaves until #5] |

Gating policy here departs from the template default on purpose: **T3 is gating**,
because nl-shell's suite has been green since its first commit (nl-shell#9), so a red
suite was introduced by the bundle. Demote it only if the baseline ever goes red.

C4 (per-fix correctness, **gating**): `./engine/scripts/run-verify.sh` — the bundle's
test red with the production hunks reverted, green with them, each leg judged by
pytest's exit code **and** the tests that ran (JUnit XML). Contract-tested by
`engine/tests/test_run_verify.py`.

**Advisory leaves at Check** (findings route into SUMMARY §6, never gate):
`security-review` — reads the patch the way an attacker would and rates findings
against nl-shell's `.oss-scanner/threat_model.md` (`agents/security-review.md`).

- **Reviewer family (cross-vendor, ≠ builder):** claude — canonical role body
  `agents/reviewer.md`, resolved via `--agent reviewer` and the generated
  `.claude/agents/reviewer.md` wrapper. The reviewer has read/execute-only tools.
- **Builder family:** codex — canonical role body `agents/builder.md`, inlined into
  `codex exec --sandbox workspace-write`. The builder runs in the worktree cwd and receives
  the driver's `gh` STOP shim because Codex has no Claude PreToolUse hook.
- **Interactive leaves:** the planner runs a seeded Codex TUI; Sign-off, Publish and Act
  run seeded `claude --agent <name>` REPLs. The backend is configured per `[leaves.*]`
  table; there is no global interactive-family switch.
- **Role prompts (vendor-neutral source):** each leaf's instructions live once in
  `agents/<name>.md`. Claude leaves also get `.claude/agents/<name>.md` (frontmatter wrapper
  that includes that body, so `--agent` resolves); non-Claude (inline) leaves read the
  `agents/` body directly. Only Claude leaves carry a `.claude/agents/` file.
- **Vendor profiles:** every family-specific behavior (streaming, extra-dir grounding,
  role-prompt injection, STOP-guard mechanism) is data in `pdca_harness.families`,
  overridable via `pdca.toml [families.<name>]` — swapping or adding a vendor is a
  config edit, not a driver change. A non-claude builder gets the STOP discipline
  from the driver's `gh` PATH shim (same `builder_guard.py` rules as the claude hook).
- **Project-defined human-only items** (reviewer emits NEEDS-HUMAN by design):
  - Validation — fitness-to-purpose (always-human, every cycle);
  - any `PDCA-UNVERIFIABLE` C4 (docs-only / test-only bundles — you judge them by reading);
  - any change to **what runs without a confirm**: the policy gate's classes, its
    denylist, the taint rules, or the read-only allowlist (threat model: Critical);
  - any change to **sudo passthrough**, logging, history write-back or env filtering —
    anywhere the password or a secret could leak;
  - a change that adds an untrusted input or moves a trust boundary, and so must update
    `.oss-scanner/threat_model.md` in the same PR;
  - every `security-review` finding rated High or Critical;
  - a change that contradicts or extends an ADR (it needs a new or superseding ADR, not
    an edit) or departs from proposal 0001's milestone scope;
  - model, dataset or dependency **license** questions (release-gating in nl-shell).

## 5. Upstream-isn't-ahead routine
- **What "upstream" is:** `getwyrd/nl-shell` `main` itself — own-repo model, no
  fork, no divergence to reconcile. "Ahead" can only mean *already done on main or in
  flight on a branch/PR*.
- **Search routine + tokenization gotchas:** by affected file path first:
  `git -C ../nl-shell log --oneline origin/main -- <path>`; then
  `gh search issues --repo getwyrd/nl-shell "<keywords>"` (GitHub tokenizes on word
  boundaries — search bare terms like `passthrough`, not `PTY passthrough mode`), and
  scan the issue's milestone and open PRs (`gh pr list -R getwyrd/nl-shell`).
- **Merged-history check command:**
  `git -C ../nl-shell fetch origin && git -C ../nl-shell log --oneline origin/main -n 30 -- <affected paths>`
- **Closed/rejected-work check command:**
  `gh pr list -R getwyrd/nl-shell --state closed --limit 1000 --json number,title,mergedAt,files -q '.[] | select(.mergedAt == null) | select(any(.files[]; .path | IN("<path>", "<path>"))) | "\(.number) \(.title)"'`
  Record its output (or "none") in the brief's Prior-art line.

## 6. Brief and design-proposal templates
- **Brief template:** `templates/brief.md.tpl`
- **Design-proposal template:** `templates/design-proposal.md.tpl` [built] — the
  Plan artifact for the **exception** (major architecture / API / data-model / UX).
  The planner reserves it for changes that warrant a proposal; most work uses the
  brief. Any canonical upstream process (GEPS/RFC) still owns the final document;
  the cycle produces the draft + the Do spec.
- **Required project-specific frontmatter/sections:** a brief names its **milestone**
  and the ADRs it builds on. A brief touching the policy gate, PTY/sudo, taint, logging
  or the installer names the threat-model inputs it affects. A change big enough for a
  design proposal is written as an nl-shell proposal (`docs/design/proposals/`), not
  only as a PDCA design-proposal draft.

## 7. Bundle and act-log paths
- **Bundle root + ID format:** `results/issue_<id>/`
- **Act log path:** `process/act-log.md`
- **Iterate archive:** a rejected attempt is preserved in `iteration-v<N>/` in the
  bundle (the brief is archived with it on iterate-to-Plan) — fixed by the harness

## 8. Committing and PR conventions
- **Commit-message format:** conventional-commit prefix with optional scope (`fix:`,
  `feat:`, `docs:`, `ci:`, `chore:`, e.g. `feat(gate): …`), imperative subject ≤ 72
  chars, body explaining the why, wrapped at ~74. Every commit carries the DCO
  `Signed-off-by:` trailer (`git commit -s`) and ends with `Fixes #{id}`
  (`[tracker].issue_trailer`). No AI attribution trailers.
- **PR description format:** see `templates/pr-description.md.tpl` (Root cause / Fix / Verified against / Test)
- **Enforcement mechanism:** nl-shell branch protection (PR required,
  `require-linked-issue`, conversation resolution, enforce-admins) + its `Tests`
  workflow + the T4 gate at Check and publish + human review.

## 9. Repo-specific scripts and tooling
List every project-specific script the cycle invokes (role → path + invocation + status).

| Role | Path | Invocation | Status |
|---|---|---|---|
| Tracker scrape / handoff generator | (none — `gh` via `[[plan.source]] role=tracker`) | driver-run at Plan | [built] |
| Conformance gate runners | `engine/scripts/run-suite.sh`, `scripts/pdca contribcheck` | `nl-shell-pdca gates <id>` | [built] |
| Repro / verification runners | `engine/scripts/run-verify.sh` + `engine/scripts/lib/junit_count.py` (tests: `engine/tests/test_run_verify.py`) | `nl-shell-pdca gates <id>`; tests: `.venv/bin/python3 -m unittest discover -s engine/tests` | [built] |
| Target dependency bootstrap | `engine/scripts/install-target-deps.sh` (`[install].extra_bootstrap`) | `make install` | [built] |
| CLI resolver for gate rows | `scripts/pdca` | `./scripts/pdca <subcommand>` | [built] |
| Security-review advisory leaf | `agents/security-review.md` (+ `.claude/agents/`) | (model leaf, Check) | [built] |
| Threat-model touch check (T2, advisory) | `engine/scripts/check-threat-model-touch.sh` (tests: `engine/tests/test_threat_model_touch.py`) | `nl-shell-pdca gates <id>` | [built] |
| Driver | `src/pdca_harness/` | `nl-shell-pdca run <id>` | [built — stub leaves until #5] |
| Act tooling (L4) | `src/pdca_harness/act.py` | `nl-shell-pdca act index`, `nl-shell-pdca act log --date <d>` | [built] |
| Gates (single-sourced) | `pdca.toml` `[[gates.checks]]` | `nl-shell-pdca gates [<id>] [--working-tree]` | [built — C4/T3/T4 wired] |
| Reviewer role prompt | `agents/reviewer.md` (canonical body); `.claude/agents/reviewer.md` is the active Claude packaging, with inline injection available for non-Claude families | (model leaf) | [built — contract; wire command mode] |
| Builder role prompt | `agents/builder.md` (canonical body, inlined for the active Codex builder); the driver `gh` shim enforces STOP, with `.claude/agents/builder.md` + `.claude/hooks/builder_guard.py` retained as the Claude-family packaging | (model leaf) | [built — ready-mark blocked] |

## 10. Maintainer and governance
- **Who reviews:** Eduard Ralph
- **Ready-mark gate:** publish opens **draft** PRs; only the human marks a PR ready
  and merges, after §9 sign-off. The builder/publisher STOP discipline
  (`builder_guard.py` + the `gh` shim) blocks the leaves from doing either; branch
  protection (enforce-admins) binds the human to the same PR + linked-issue path.
- **External-contribution flow differences:** none — external contributors use the
  standard GitHub fork flow with DCO sign-off (nl-shell CONTRIBUTING.md); the cycle
  applies to the maintainer's own contributions.
- **MAINTAINERS file:** none — single maintainer; CONTRIBUTING.md names the process.

### Composing with the host's CI / PR governance (issue #67)

PDCA **supplements** your existing PR/issue governance; it does not replace it. Map
the harness onto what your host already enforces:

| Host gate (governance layer) | PDCA equivalent (supplement) | How they compose |
|---|---|---|
| require-linked-issue on PRs | `[tracker].issue_trailer` (`Fixes #{id}`) in the publish commit/PR | The trailer satisfies the host's linked-issue rule; `init from brief` maps onto an issue that already passes it. |
| DCO / append-only-doc / ready-mark policy | builder/publisher STOP discipline (`builder_guard.py` for Claude builder/publisher roles, driver `gh` shim for non-Claude ones) | The family-appropriate backstop blocks `gh pr ready` / `gh pr merge` on the contribution paths; your host policy is the authority. |
| nl-shell CI (`Tests` workflow: `python -m pytest`) | T3 `run-suite.sh` at Check | Same command, run earlier — Check catches before the PR what nl-shell's CI re-catches at merge. |

If the host already provides one of these, omit the shipped equivalent at render time:
`ship_ci_workflow = false` drops `.github/workflows/check-gates.yml`; `ship_merge_guard
= false` drops the `builder_guard.py` hook (and its agent wiring). Both default on for a
standalone project.

## 11. Per-repo P-/D-/C-/A- extensions
Repo-prefixed rules that *tighten or add to* a generic rule, never weaken one.

### nl-shell-pdca-C7 — VM- or hardware-validated slice

Much of nl-shell's work can't produce a C4 red→green on the developer's machine: real
sudo-rs (only in the throwaway VM), VM scripts (M1), the data pipeline with the teacher
and sandbox (M2), GPU training and inference (M3–M5). Such tests carry nl-shell's pytest
markers (`sudo`, `vm`, `gpu`, `teacher`) and are skipped outside their environment
(nl-shell #73), so C4 reports `PDCA-UNVERIFIABLE`.

For those slices:
1. **Plan:** the brief's `External dependencies` field declares the environment as
   `reference-vm` or `gpu-16gb` (with `no-check: …` if the doctor can't detect it), and
   names the marked tests.
2. **Do:** the builder writes and runs the tests that *can* run (pure logic, fakes such as
   nl-shell's fake `sudo`). It never sets `NL_SHELL_TEST_VM=1` on the host.
3. **Check:** T3 and T4 still gate. C4 may be `PDCA-UNVERIFIABLE` only if the bundle
   holds a **`manual-validation.md`**: the commands run in the declared environment, their
   output, and the marked tests' results there, with a date. Without it, the C4 item stays
   open in §6 and sign-off can't accept.
4. The doctor's WARN rows "reference VM" and "GPU" show whether the environment exists on
   this host.

### nl-shell-pdca-T2a — security-relevant changes update the threat model

`engine/scripts/check-threat-model-touch.sh` (advisory): a patch touching nl-shell's gate,
policy, PTY, session, sudo, passthrough, taint, reader, history, logging, backend,
installer, teacher endpoint, CLI, failure classification, proposal, configuration,
target loading, package-name filtering, rendering, Unicode-table, REPL, input-mode or
prompt-building code; target TOML contracts, the quarantined-reader prompt or parser
dependency pins; or the policy-gate, PTY, reader or proposal specs, without touching
`.oss-scanner/threat_model.md` lands in §6 for a human decision.

## Answering an interactive leaf from another device

The four `interactive = true` leaves — planner, sign-off, publisher, Act — hand the terminal
to a human+model REPL and block there. That means the human has to be at the terminal the
flow runs in, for the whole batch: a `nl-shell-pdca flow` over several bundles can park on one
sign-off adjudication for hours because nobody is at that machine.

Claude Code's `--remote-control` flag removes the constraint. Add it to an interactive
leaf's `argv` in `pdca.toml` — anywhere but last: the driver appends the seed prompt as a
positional after the argv, and `--remote-control` takes an optional `[name]` value, so as
the final token it would swallow the whole seed as the RC session name (issue #396; the
claude-family spawn also inserts `--` before the seed as a backstop, but no flag with an
optional value should ever sit last). With the flag in place that leaf becomes answerable
from another enrolled device; nothing else changes — `signoff-decision`, the §6 ticks and
the C6 accept-guard all run the same code path, and only the human's location differs.

Enabling Remote Control in your own shell does **not** reach the leaves: each is a separate
`claude` subprocess whose argv comes from `pdca.toml`. That is the whole reason this needs
documenting.

The headless builder and reviewer must not carry the flag — it starts an *interactive*
session, and they have no human to reach.

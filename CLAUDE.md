# nl-shell-pdca — agent guidance

PDCA quality-cycle instance: drives contributions to nl-shell with pdca-harness

This project runs the **PDCA quality cycle** ([PCDA/quality-cycle.md](PCDA/quality-cycle.md),
the reference model). Repo-specific concretizations are in [docs/INTEGRATION.md](docs/INTEGRATION.md) —
read it for tracker, branch targets, fixtures, and the conformance ruleset.

## The driver

`pdca` advances a result bundle through the cycle (`nl-shell-pdca status`, `nl-shell-pdca run <id>`,
`nl-shell-pdca signoff <id> --accept`, `nl-shell-pdca publish <id>`), or runs it as one continuous
mixed Codex/Claude flow (`nl-shell-pdca flow <id> [--from-csv …] [--no-publish] [--no-act]`). State is
the files in `results/issue_<id>/`; nothing is hidden in a database.

The driver is deterministic — **no model decides control flow**. The cycle has exactly
**four beats** (Plan · Do · Check · Act); models are invoked at **six leaves** *within*
them — review, sign-off and publish are all **steps of the Check beat**, not beats of
their own:

- **Plan** — planner (interactive): turns the human's documents into `brief.md`.
- **Do** — builder (headless): `patch.diff` + the named test + `build-notes.md`.
- **Check** — reviewer (headless, advisory) → sign-off (interactive, the human's OK)
  → publish (interactive, on accept: drafts the contribution artifacts; the driver
  then opens a **draft PR**).
- **Act** — act (interactive): cross-cycle process deltas.

The leaves fill *artifacts*; the state transitions, the gates, and the C6 accept-guard
stay deterministic code. Each leaf is configurable in `pdca.toml` (`[leaves.*]`,
`mode = stub|command`, `interactive`); `PDCA_LEAVES_MODE=stub` forces the offline
placeholders for CI / `make`. In `nl-shell-pdca flow`, an accept continues to publish then
optional Act; `--no-publish` stops at COMPLETE.

## Do (the builder leaf) — your scope when implementing

- Read **`brief.md` only**. Produce `patch.diff`, the test the brief names, and
  `build-notes.md` (your rationale — withheld from the reviewer by the driver).
- The test must fail pre-fix and pass post-fix. Cite `path:line` on the target
  branch for every change.
- **STOP discipline:** do not branch, push or open a PR; the deterministic publish step
  owns those mechanics after human sign-off. No model leaf may mark a PR ready or merge
  it. The active Codex builder receives the driver's `gh` PATH shim; if Claude is selected
  as builder, `.claude/agents/builder.md` applies the equivalent
  `.claude/hooks/builder_guard.py` PreToolUse hook.

## Check sign-off (human) — not the model's to perform

The driver assembles `SUMMARY.md` and stops at AWAITING_SIGNOFF. The human clears
§6 NEEDS-HUMAN, weighs the advisory review, and records §9. `nl-shell-pdca signoff
--accept` refuses while §6 has open items (C6). On an accept, **publish** (Check's
closing step) drafts the commit-msg + PR description and the driver opens a **draft
PR** — it never marks ready or merges; that stays the human's. `nl-shell-pdca publish <id>`
runs it standalone; `nl-shell-pdca flow` does it automatically on accept (`--no-publish` to skip).

## Act (human) — separate, cross-cycle

Process improvement (ruleset/template/gate/skill deltas) runs across frozen
bundles on a cadence, recorded in `process/act-log.md`. It never
re-decides a contribution's disposition.

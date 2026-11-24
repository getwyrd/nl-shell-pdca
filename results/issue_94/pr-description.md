## Summary
**User impact:** Anyone reading the architecture docs to learn how nl-shell works, or
to build on it, is told that Ubuntu 26.04 details apply everywhere, and that some
parts already ship when they don't. The docs leave out the per-OS target folder and
the rules that protect a user from running wrong or tampered model weights. The
result is wrong guidance for contributors and reviewers about what is shared, what
is OS-specific, and what is built today.

This PR updates the architecture docs only. They now match ADR-0023 (OS targets)
and the policy-gate spec, and each part is marked built or planned.

Reported in [#94](https://github.com/getwyrd/nl-shell/issues/94).

## What to look at
- **Chapter 05 (building blocks):** the new "Target folder and consumers" section.
  Each part that reads the target folder is marked *built* or *planned*. Check that
  this matches what you know of the code.
- **Chapter 07 (deployment):** the planned packaging, the weight download and hash
  check, the refusal on a mismatch, and adapter compatibility. The two **[OPEN]**
  distribution questions stay open, and no channel is chosen.
- **Chapters 01–04, 06, 08, 10:** short edits that tie dpkg/apt, sudo-rs and 26.04
  facts to the `ubuntu-26.04` target. Historical milestone names and existing
  uncertainty notes are kept as they were.

To try it: `python -m pytest -q tests/test_architecture_targets.py`. It reads the real
chapter files.

## Root cause
The architecture was written when Ubuntu 26.04 was the only system in view. ADR-0023
later split OS-specific data into `targets/<id>/` and added manifest and adapter rules,
but the living architecture chapters were never updated to match.

## Fix
- `docs/design/architecture/05-building-block-view.md`: adds the target folder to the
  component diagram and table, plus a consumer list with status for each part. Built:
  REPL start-up loading `target.toml` and command prompts, exact os-release match,
  a warning on a mismatched named target, gate-vector loading, and the reader module
  (not yet wired into the REPL). Planned: REPL manifest/`sensitive.toml` inputs, gate
  integration, installer, pipeline. Makes the reference VM/harvest row per target.
  Narrows the §5.3 catch-all row: it lists the target modules that exist and keeps
  PTY session, state capture, policy gate integration, confirm UI and session log
  as *(planned)*.
- `docs/design/architecture/07-deployment-view.md`: describes the planned package of
  every target's runtime files. Weights are referenced by `model.toml`, not stored
  in git or the package. They download only at install or explicit update and are
  checked by SHA-256 before use. The REPL must refuse mismatched weights, and adapters
  are bound to target + base-weight hash. All are marked as requirements awaiting
  implementation. The old single [OPEN] item is split into two: the weight URL host
  in `model.toml` and the package distribution channel.
- `docs/design/architecture/08-crosscutting-concepts.md`: reference provenance, gate
  examples, the reader's package lookup, the execution filter and offline lookup now
  refer to the active target, with dpkg/apt named as the `ubuntu-26.04` implementation.
  §8.8 is retitled `ubuntu-26.04` target specifics. Taint labels, the offline rule and
  confirm rules are unchanged.
- Chapters 01, 02, 03, 04, 06, 10: first-target wording for goals, constraints, the
  context diagram, sudo-rs behavior, training and glossary entries.
- `tests/test_architecture_targets.py`: new.

No ADR, spec, milestone plan or runtime code is changed.

## Verification
- **Claim:** chapter 05 shows `targets/<id>/` and its consumers with correct status.
  **Checked:** `docs/design/architecture/05-building-block-view.md:63-90` against
  `src/nl_shell/targets.py:1-12,27-28,145-169,249-276`, `src/nl_shell/gate/vectors.py:1-4,49-53`,
  `src/nl_shell/prompts.py:80-91`, `src/nl_shell/reader.py:198-204`, and the folder
  `targets/ubuntu-26.04/` (only `target.toml`, `sensitive.toml`, `gate-vectors.toml`,
  `prompts/`). §5.3 status rows: `05-building-block-view.md:110-114`. State capture
  stays planned per `src/nl_shell/prompts.py:47`.
- **Claim:** deployment describes manifest integrity, mismatch refusal and adapter
  binding as planned, and keeps both distribution questions open.
  **Checked:** `docs/design/architecture/07-deployment-view.md:15-33,67-72` against
  `docs/design/adr/0023-os-targets.md:57-71`. No host or channel (GitHub, Hugging
  Face, PPA) is named.
- **Claim:** OS-specific details are scoped to the target, and the gate procedure
  stays shared. **Checked:** `docs/design/architecture/08-crosscutting-concepts.md:35,54-56,114,143-149,163-166`
  against `docs/design/specs/policy-gate/v1.md:33-49` and ADR-0023:37-55,73-87. All
  other chapters, including chapter 10's sudo-rs, ROCm and point-release rows, were
  read by hand. Their existing uncertainty is kept.
- **Test:** `tests/test_architecture_targets.py`. It fails on main (9 failed) and
  passes with this change (9 passed). It checks the status wording next to each
  requirement, not just topic words. Each of 15 deliberate regressions made it fail,
  for example making the mismatch warning per-command confirmation, calling the
  reader plain "built", or naming a distribution channel.
- **Docs checks:** internal links (82 links, 0 broken), the ADR index (28 ADRs, 0
  problems) and ADR immutability all pass.
- **Limit:** these are document checks. They show the stated relationships are
  present. They do not test runtime behavior, which this PR does not change. The full
  test suite could not finish in the sandbox used for this work, because it blocks
  localhost sockets (an existing reader test). CI should run it normally.

**Not in this PR, possible follow-ups:** scope only the systemd unit (not the whole
serving bullet) to `ubuntu-26.04` in chapter 07; decide whether `gate-vectors.toml`
is a shipped runtime file or a gate-test input (ADR-0023:47 vs :121); tighten §8.5's
lookup wording to the target's `[command_provider]` data; settle one status rule for
built-but-not-wired modules (PTY session vs. reader).

Fixes #94

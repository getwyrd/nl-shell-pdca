# Build notes — issue 77 (teacher-client-dev-teacher-flag)

## Outcome: not built — a required dependency is missing from the build base

NEEDS-HUMAN external dependency: issue-16-core (#143: backend interface, `proposal/v1` parser + schema, "no backend configured" reply) — absent from the wave base `pdca-integration/main-r2546dbf9639f` @ 0771812; the client, its test and criteria (a)–(f) cannot be built without inventing stand-ins, which the brief forbids

```toml
[[doctor.checks]]
id    = "issue-16-core"
cmd   = "git -C ../nl-shell grep -q -i 'proposal/v1' \"${PDCA_VERIFY_BASE:-origin/main}\" -- src"
hint  = "Build, sign off and fold #143 (the #16 core split) into the wave base before scheduling #77"
level = "MISSING"
```

## What the brief requires

- "Repo + branch target: … so #16's backend interface, parser and schema, #92's
  `config.toml` unit and #14's `:status` exist when this bundle builds; **if any is not
  accepted, this bundle is not scheduled. Use their names as they landed; do not invent
  stand-ins.**"
- Scope (1): "A backend for #16's interface"; the `response_format` is "built from the
  single `proposal/v1` schema #16 keeps"; (a) requires "the same object #16's parser uses".
- Citations: "Peer to mirror: implement the backend exactly as #16's stub implements the
  same interface".

## What the base actually has

Worktree `$PDCA_WORKTREE` = `/home/eddie/nl-shell/nl-shell.pdca-wt-l2`, detached at
`0771812 pdca-integrate: issue_140` (= `results/issue_77/stack-base-tip`, branch
`pdca-integration/main-r2546dbf9639f`).

- #14 is present: `:status` plumbing at `src/nl_shell/input_modes.py:77-92`
  (`StatusLine`, `status()`), `Repl(..., status_lines=...)` at `src/nl_shell/repl.py:42-55`.
- #92 is present: `src/nl_shell/config.py`, `src/nl_shell/targets.py`, the parser in
  `src/nl_shell/cli.py`.
- #16 is **not** present. The REPL still carries the pre-#16 placeholder:
  `src/nl_shell/repl.py:6` ("the model backend arrive[s] in later M0 issues") and
  `src/nl_shell/repl.py:27` ("the model backend arrives in M0.8."), and
  `src/nl_shell/input_modes.py:102` ("command proposals arrive in M0.8."). There is no
  backend interface, no stub backend, no `proposal/v1` parser or schema.

Checked with `git grep -l -i -E "proposal/v1|class .*Backend|no backend configured"`
on `HEAD`, `main`, `origin/main` and `pdca-integration/main-r2546dbf9639f` (all `-- src`):
no matches on any of them.

## Why #16 is missing

`results/issue_16/close-disposition` = `split`; `results/issue_16/split-lineage.json`
names children #143 and #144. Per `results/issue_16/split-proposal.md`, #143 is "the
core — prompts YAML, model input, recording stub backend, strict `proposal/v1` parser,
`:context`, `:status` listing prompt files", i.e. exactly what #77 builds on.
`results/issue_143/` holds only `brief.md` plus plan/telemetry files — no `patch.diff`,
no `SUMMARY.md`, no sign-off. So the dependency is not accepted, and the brief says this
bundle should not have been scheduled. #77's `Depends on: 16, 92, 14` still names the
split parent #16 rather than #143, which is likely why the scheduler did not hold it back.

## What I ruled out

- **Writing my own backend interface, parser and schema inside #77.** Forbidden by the
  brief ("do not invent stand-ins"). It would also collide with #143 when that lands:
  two `proposal/v1` schemas (ADR-0018 §2 wants a single one), two backend interfaces, and
  a REPL wired twice. The C4 gate might go green on it, but the result would not be the
  thing the success criterion describes ("the same object #16's parser uses", "#16's
  'no backend configured' path it replaces").
- **Reading #143's brief to copy its intended names.** Outside the one-cited-callsite
  exception (the brief cites #16's code on the wave base, not another brief), and names
  from an unbuilt brief are not "names as they landed".
- **Shipping just the parts that don't need #16** (endpoint selection, `--dev-teacher`,
  the HTTP transport). Criteria (a), (b), (d) and (f) all go through the `proposal/v1`
  parser or the REPL backend hook, so a partial patch could not make
  `tests/test_teacher_client.py` pass as specified; it would be a green check on
  something adjacent, not the success criterion.

## Artifacts

- `patch.diff`: empty — no target-source change was made.
- `tests/test_teacher_client.py`: not shipped. A test written against invented names
  would either fail forever or pin the stand-ins this brief forbids.

## Self-refutation (a)/(b)/(c)

- (a) Genuine red? Not applicable — no test was produced, so there is no red→green claim.
- (b) Production path? No — the production code the test must drive (#16's backend
  interface and parser) does not exist on the base.
- (c) Fixture includes the fault? Not applicable.

The criterion is left honestly unverified.

## What the human should do

1. Build and sign off #143, fold it into the wave base.
2. Change #77's `Depends on` from `16` to `143` (and keep 92, 14) so the scheduler holds
   it until #143 is accepted.
3. Re-run Do for #77 on the new base; the brief needs no other change.

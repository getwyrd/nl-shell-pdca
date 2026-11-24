# Build notes — issue 77 (teacher-client-dev-teacher-flag), iteration 2

## Outcome: not built, again. The missing dependency is still missing, and Do cannot fix that

NEEDS-HUMAN external dependency: issue-16-core (#143: backend interface, `proposal/v1` parser + schema, "no backend configured" reply) — still absent from the wave base `pdca-integration/main-r2546dbf9639f` @ 0771812, and #143 is being rebuilt in the SAME wave (its own auto-iterate round 1), so it is not accepted; the client, its test and criteria (a)–(f) cannot be built without inventing stand-ins, which the brief forbids

```toml
[[doctor.checks]]
id    = "issue-16-core"
cmd   = "git -C ../nl-shell grep -q -i 'proposal/v1' \"${PDCA_VERIFY_BASE:-origin/main}\" -- src"
hint  = "Sign off #143 (the #16 core split) and fold it into the wave base before scheduling #77; do not put #77 in the same wave as #143"
level = "MISSING"
```

## About the carry-forward

The carry-forward asks Do to "supply the implementation and discriminating tests". That
finding came from an auto-iterate that read the empty patch as a build failure. It is not.
The same round's deferred findings already say why
(`results/issue_77/deferred-findings.json`, item 4: "Iterating on Do won't help: the
brief tells the builder not to invent stand-ins for #16's names"). Nothing about the base
has changed since then, so a rebuild hits the same wall. Another auto-iterate round will
hit it too. **The loop should stop here and go to the human.**

## What I checked this round

- Worktree `$PDCA_WORKTREE` = `/home/eddie/nl-shell/nl-shell.pdca-wt-l2`, detached at
  `0771812 pdca-integrate: issue_140`, clean. After `git fetch origin`,
  `origin/pdca-integration/main-r2546dbf9639f` still points at `0771812`.
- `git grep -l -i "proposal/v1" origin/pdca-integration/main-r2546dbf9639f origin/main -- src`
  gives no matches. `git grep -n -i -E "proposal/v1|Backend|no backend configured" HEAD -- src`
  finds only the pre-#16 placeholders: `src/nl_shell/repl.py:6`, `src/nl_shell/repl.py:27`
  ("the model backend arrives in M0.8.") and a comment at `src/nl_shell/input_modes.py:87`.
- #14 (`:status`, `src/nl_shell/input_modes.py:77-92`) and #92 (`src/nl_shell/config.py`,
  `src/nl_shell/targets.py`) are present, as in iteration 1.
- `results/issue_16/close-disposition` = `split`, with children #143 (core) and #144.
- `results/issue_143/`: no top-level `patch.diff`, no `close-disposition`.
  `iteration-v1/session-carry-forward` shows #143 was auto-iterated (round 1) for missing
  test coverage, so it is being rebuilt now. `results/issue_143/stack-base-tip` =
  `07718128…`, the same base as this bundle (`results/issue_77/stack-base-tip`). So #77
  and #143 are in the same wave. That breaks the brief's own ordering note ("After
  #16 …") and its rule "if any is not accepted, this bundle is not scheduled."

## Options I ruled out

1. **Write my own backend interface, `proposal/v1` schema and parser inside the client.**
   The brief forbids this ("Use their names as they landed; do not invent stand-ins").
   Criterion (a) also needs "the same object #16's parser uses", which a private copy
   can't be. And #143 adds `src/nl_shell/backend.py`, `proposal.py`, `render.py` and edits
   `repl.py`, `cli.py` and `input_modes.py` (file list from
   `results/issue_143/iteration-v1/patch.diff`, `+++` headers). A parallel version would
   clash with all six files at fold time.
2. **Build on top of #143's iteration-v1 patch.** That patch was rejected and is being
   rebuilt, so its names may change. My patch would also not apply to the C4 base
   (`0771812` has no `backend.py`), so C4 would report "does not apply" and show nothing.
3. **Put #143's changes inside this patch.** That ships another issue's unreviewed code
   under #77 and bypasses #143's own Check.
4. **Ship a test with no fix, or a test against a mock client.** A test that can't run
   production code would be a fake pass. The brief's Falsifiability needs the real client.

## Refute-your-own-test answers

There is no test this round, so none of the three can be answered "yes":

- (a) Genuine red? Not applicable. No test was shipped. `tests/test_teacher_client.py` would
  need #143's names to exist.
- (b) Production path? No production code exists for this bundle to drive.
- (c) Fixture includes the fault? Not applicable.

Criteria (a)–(f) are **unverified**, honestly.

## What the human needs to do

1. Stop the auto-iterate loop for #77. Rebuilding won't help until the base changes.
2. Finish #143's cycle and sign it off. Then fold its patch into the integration branch.
3. Reschedule #77 into a later wave whose `$PDCA_VERIFY_BASE` contains #143. The brief
   needs no changes for that. The names it asks for (backend interface, parser, schema,
   stub) will exist by then.
4. Optionally, add the doctor check above, or a scheduler rule that refuses to put a
   bundle in the same wave as an unaccepted bundle it depends on.

## Files produced

- `patch.diff`: empty, on purpose (no source change can be made honestly).
- `tests/test_teacher_client.py`: not shipped (see option 4).
- `build-notes.md`: this file.

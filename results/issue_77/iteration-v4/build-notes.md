# Build notes — issue 77 (teacher client, `--dev-teacher`) — NOT BUILT

## Outcome

No patch. `patch.diff` is empty on purpose. The brief's hard prerequisite (#143) is not in
the base this Do run was given, and the brief forbids building without it.

NEEDS-HUMAN external dependency: #143 accepted and folded into the wave base — the worktree base (`pdca-integration/main-r2546dbf9639f` @ `0771812`, i.e. main + #92 + #140) has no `src/nl_shell/backend.py`, `proposal.py`, `render.py` or `prompts.py`, and `$PDCA_VERIFY_BASE` is unset; `nl-shell-pdca status` shows `issue_143 PLANNED` and `issue_77 PLANNED [blocked-by: 143]`. Without #143 the client has no `Backend` protocol to implement, no `proposal.SCHEMA` to send, no `render.escape` for error reasons and no `Repl(..., backend=, prompts=)` to wire into, so criteria (a), (d), (e), (f) cannot be built or proven red→green.

```toml
[[doctor.checks]]
id    = "dep-143-folded"   # Depends on: 143 — the wave base must contain #143's accepted patch
cmd   = "test -f \"${PDCA_VERIFY_BASE:-$PDCA_WORKTREE}/src/nl_shell/backend.py\" && test -f \"${PDCA_VERIFY_BASE:-$PDCA_WORKTREE}/src/nl_shell/proposal.py\""
hint  = "Accept #143 at sign-off and let the driver fold it into the wave integration branch before scheduling #77"
level = "MISSING"
```

## Evidence (on the target worktree)

- `git -C $PDCA_WORKTREE rev-parse HEAD` → `07718128c109fd3b556600b3e85ba2f853319dd4`
  (`pdca-integrate: issue_140`, on top of `3cc2897` = #92 merge). Matches
  `results/issue_77/stack-base-tip`.
- `ls src/nl_shell/{backend,proposal,render,prompts}.py` → all four "No such file or directory".
- `src/nl_shell/repl.py` is 84 lines; there is no `_propose` (the brief's `repl.py:142-150`
  is a line on main + #143 only).
- `results/issue_143/` has a fresh re-planned `brief.md` and old `iteration-v1..v3` folders,
  but no current `patch.diff`; status is PLANNED, so #143 has not even been built in its
  current form, let alone accepted.

## Why I did not build anyway

- Brief, `Repo + branch target`: "If #143 is not accepted, this bundle is not scheduled. …
  Do not invent stand-ins (no local schema copy, no own escape function, no own backend
  protocol)." Brief, `Falsifiability`: "the driver must not schedule this bundle before
  #143 is accepted."
- Iterations v1–v3 of this bundle were rejected for exactly that: built on a base without
  the backend code, against a stand-in schema (carry-forward section of the brief).
- Option considered and rejected: apply #143's `iteration-v3/patch.diff` locally and build
  on it. That patch belongs to the pre-split #143 design that has since been re-planned
  (its brief now lists different scope); its names and line numbers may change, and a
  patch built on it would not apply to the real folded base. It would also be a stand-in
  in all but name. Cost of the wrong choice: a fourth rejected iteration.

## About `results/issue_77/test_teacher_client.py`

That file is left over from iteration v3 (timestamp 2026-10-17 01:31, before this run). It
uses a local stand-in `SCHEMA` (line ~27), which the current brief forbids. I did not write
it and it is not this iteration's test. I did not overwrite it with a new test, because a
test against modules that do not exist in the base cannot be shown red→green honestly.
The next Do run (after #143 is folded) should replace it.

## Refutation questions

- (a) Genuine red? — Not applicable: no fix exists to revert. Not proven.
- (b) Production path? — No: the production modules the test must drive (#143's) are absent.
- (c) Fixture includes the fault? — Not applicable: no fixture was built.

The item is not done. It should go back to the driver as blocked on #143, not to sign-off
as a feature.

## Formatter / hooks

Nothing to format: no files in the target were changed (`git -C $PDCA_WORKTREE status
--short` is clean).

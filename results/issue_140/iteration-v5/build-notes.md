# Build notes — issue 140 / persistent-bash-session-core (round 5)

## Base

Built on `origin/main` = `c47c5c2` in `$PDCA_WORKTREE`
(`/home/eddie/nl-shell/nl-shell.pdca-wt-l0`). Path:line citations for new files are on
the patched tree; doc citations are the patched line, with the `c47c5c2` anchor the brief
named.

## What I did

Started from `iteration-v4/patch.diff`, as the brief says. Every hunk except
`docs/design/specs/pty-protocol/v1.md` applied cleanly to `c47c5c2`
(`git apply --exclude=docs/design/specs/pty-protocol/v1.md`). I rewrote the spec hunks by
hand against `main`'s text, which now has §4.4–§4.5 and vectors 13–16. Then:

1. **R2: functrace handling removed.**
   - `set +H +T` → `set +H` (`src/nl_shell/session.py:95`).
   - `__nls_done` no longer runs `set +T` or saves `$-` into `__nls_f`
     (`session.py:113-115`). `__nls_snap` no longer runs `set +T` (`session.py:131`).
   - `__nls_f` is gone from `HOOK_STATE_VARS` (`session.py:59-71`) and from the rcfile.
   - The H-differs reason no longer names functrace (`src/nl_shell/pty_protocol.py:296`).
   - Tests removed: the `functrace` row of `_TABLE_A_ROW_1` (`tests/test_session.py:522`),
     `debug-trap-functrace` in `_I2_ATTACKS` (`:622`), `_FUNCTRACE_ATTACKS` and its test.
   - I also removed `test_snapshot_cut_short_after_done_degrades`. It used
     `shopt -s extdebug` + a DEBUG trap, and the brief says "No test for any … `extdebug`
     … case". Its code path (the "snapshot did not finish" reason,
     `session.py:563-566`) is now untested. That is a direct consequence of the brief's
     rule, not something I could keep without an extdebug test.
   - Every comment or spec sentence claiming "no DEBUG trap runs inside a hook" is gone
     (old `session.py:89-94`, old spec §1.3 paragraph, old §3 bullet).

2. **Vector 8 now degrades at that command's own snapshot (criterion (b), spec `:299`).**
   In v4, `PROMPT_COMMAND=:` replaced the only element (the hook), so no `D` came and the
   session degraded ~1 s later by the prompt rule, with no result. The brief asks for
   "degraded at that command's snapshot (`H` changed)". Fix: `PROMPT_COMMAND` is now the
   array `('' '<hook>')` (`session.py:171`). `PROMPT_COMMAND=:` assigns element 0 only,
   so the hook (element 1) still runs and `H` shows the change. I checked on bash 5.3.9
   that an empty element 0 keeps `$?` and `PIPESTATUS` for the hook (`false | (exit 3)`
   → `ST=3 PS=1 3`). This also matches I3's wording: "nl-shell's hook is the LAST
   `PROMPT_COMMAND` element". Test: `tests/test_session.py:227` now asserts
   `result is not None`, `seq == 1` and "H differs" in the reason.

3. **I3 bug found by the new (m) check: user `PROMPT_COMMAND` array elements ran after
   the snapshot.** v4 did `PROMPT_COMMAND='<hook>'` (a scalar assignment). When
   `~/.bashrc` set `PROMPT_COMMAND` as a two-element array, that only replaced element 0.
   The user's element 1 stayed, so it ran a second time *after* the snapshot. That breaks
   I3. Fix: `\builtin unset PROMPT_COMMAND` before setting it (`session.py:170`). The red
   run below shows the bug: `pc.log` was `['0 0', '0 0', '1 4', '1 4']`, so element 2 ran
   twice per prompt.

4. **PS1/PS2 now appear in `H` with nl-shell's fixed values (criterion (m)).** v4's `H`
   carried only PS1/PS2 *attributes* (`declare -- PS1`), because PS1 was reset after `E`.
   So the brief's check "PS1/PS2 equal nl-shell's fixed values in the `H` text" could not
   hold. Now `__nls_snap` sets `PS1='\$ '`/`PS2='> '` *before* `H` (`session.py:133-139`),
   puts `declare -p … PS1 PS2` in `H` (`:141`), and still sets them again after `E`
   (`:167`), so "nl-shell sets fixed PS1/PS2 after the snapshot" stays literally true.
   - The pre-H assignment is guarded: it only assigns when `declare -p` shows a plain
     (`--`) or exported (`-x`) variable, or none. I tested that assigning to a readonly
     PS1 aborts the whole hook, and that `declare -i PS1` + `PS1='\$ '` aborts with an
     arithmetic error. Without the guard those would kill `__nls_snap` before `H`.
     With it, `H` is always emitted and shows the odd attributes, so `readonly PS1` still
     degrades at its own snapshot ("ps1-readonly" row stays green).
   - `__nls_v= __nls_c=` after the loop (`:139`). Without it the scratch variable kept
     `declare -- PS2="more> "` and `PS2='more> '` over-degraded. The negative test
     `test_ordinary_changes_stay_healthy[ps2]` caught this in my first run.

5. **Docs narrowed to the closed list (R1).**
   - pty-protocol spec: §1.2 bullets (`:46-53`); §1.3 rcfile replaced with the new one,
     plus the notes paragraph and a "What this protects" paragraph that states the closed
     list and "nothing else is claimed yet (#141, #145)" (`:54-160`). There is no
     per-evasion list and no functrace sentence. §2 encoding (`:173`); §3 `H`/`V`
     (`:185-197`, `H` includes `TERM`); §4.1 job notices and "D without S = nothing ran"
     (`:200-209`); §4.2 first trigger exception, decision-7 rule, `/proc` fail-closed and
     #136 limits (`:210-223`); §4.3 decision 10 (`:224-225`); §4.4/§4.5 one line each
     on #121 (`:229-233`); §Versioning (`:283-284`); vector 8 (`:299`); vectors note
     (`:309-311`).
     The brief lists "output between S and D includes bash's own job notices" under §3. I
     put that sentence in §4.1, where "output between S and D" is defined.
   - Threat model: v4's long "partial" bullet is replaced by ONE interim bullet naming #141
     and #145, the `read -u 2 x` / #136 limit, and "#78 MUST NOT wire the session … before
     #141 lands" (`.oss-scanner/threat_model.md:181-187`). The §How to exercise it sentence
     about the session tests is at `:195-197`.
   - policy-gate v1 §7.5 item 5 (`:199-202`, `V` is encoded `declare -p` text) and item 6
     with the new clause about item 7 (`:203-205`). Item 7 is unchanged.
   - Glossary "Degraded mode" row (`docs/design/architecture/10-quality-risks-glossary.md:71`).
   - ADR-0014 Decision 1 (`:45-47`) and Decision 2 (`:53-55`), and ADR-0013 (`:72-74`),
     are as in v4. ADR-0023 is untouched.
   - `session.py` rcfile comment (`:80-91`) now says the same as spec §1.3 and points to
     its closed list, with no extra claims.

Not reintroduced: no guard variable on `S`, user hook still before the snapshot, no
`tcgetpgrp`, no `tr`/`cksum`, no CRC, `P` stays reversible, D-without-S stays "not run".

## Red → green (project runner)

`PDCA_BUNDLE=… PDCA_WORKTREE=… ./engine/scripts/run-verify.sh` (the C4 gate):

```
== C4 green leg: … 90 passed in 38.92s
== C4 red leg:   … 90 failed in 1.19s
PDCA-EVIDENCE: C4 PASS — red without the fix (90 of 90 failed), green with it
```

I used `python3 -m pytest tests/test_session.py` (the reproduction command in
`docs/INTEGRATION.md` §3), wrapped in `timeout`, while iterating: 90 passed.

## Self-refutation (forced)

- **(a) Genuine red?** Yes. With the production hunks reverted (run-verify red leg), all
  90 tests fail, because every test imports `nl_shell.session` / `pty_protocol` inside the
  test. That is coarse, so I also reverted *only* the new `PROMPT_COMMAND` lines
  (`session.py:170-171` back to v4's scalar). Then `test_vector8_replaced_prompt_command_degrades`
  fails (`SessionDegraded('… no done record after the shell returned to a prompt').result
  is None`) and `test_bashrc_alias_and_prompt_command_run_before_the_snapshot` fails
  (`['0 0', '0 0', '1 4', '1 4'] != ['0 0', '1 4', '2 0', '3 0']`). The tree was restored,
  and `git diff` is byte-identical to `patch.diff`.
- **(b) Production path?** Yes. Each test starts the real `Session` (`Session.start` →
  `ptyprocess` → `bash --rcfile <RCFILE>`) and reads records from the real fd-3 pipe. The
  only test double is a spy that wraps `_write_all` and still calls the real one. The
  parser tests call `pty_protocol.ProtocolTracker` directly.
- **(c) Fixture includes the fault?** Yes. The faults are injected for real: the tests
  run `PROMPT_COMMAND=:`, a two-element `PROMPT_COMMAND` in a test-HOME `~/.bashrc`,
  `exec 3>&-`, `read x`, `read x </dev/tty`, a `proc_root` with no `syscall` file, and the
  `HOOK_STATE_VARS` reproducers, all against real bash 5.3.9.

## Commit-readiness

The target has no formatter, pre-commit config or linter config (no `.pre-commit-config.yaml`,
no `[tool.ruff]`, and none installed in the venv). Its CI runs pytest, the docs
immutability check and the link check. I ran both docs checks:
- `python3 -I scripts/docs_links.py` → 0 broken.
- `scripts/docs_checks.py immutability HEAD <dangling commit of the work>` → OK. ADR-0013,
  ADR-0014 and both specs are not frozen.
No line in the new Python files is over 100 characters; the existing `src/` max is 96.

## Size

`patch.diff` is 102,072 B, over the ~100 KB target (v4: 100,456 B). Per file:
`tests/test_session.py` 38.3 KB, `session.py` 29.3 KB, pty-protocol spec 14.7 KB,
`pty_protocol.py` 12.1 KB, everything else under 2 KB each. The growth over v4 comes from
the new (m) I3 helper/test (~2 KB) and the pre-H PS1/PS2 block. That is partly offset by
the removed functrace tests. I cut no claimed test or listed doc edit.

## For the PR description (publish)

Per decision 11, the PR should say that this brief supersedes both the #101 issue text and
the #140 body where they differ: hook order, prompt rule, 5 s / < 3 s limits, decision
10, `TERM` in `H`, I2-d, `/dev/tty`, `proc_root`, the pinned job notice, and the new
threat-model bullet. It should also mention the two behaviour changes from v4 found this
round: `PROMPT_COMMAND` is now `('' hook)` after an `unset`, and PS1/PS2 are set before
`H`.

## Housekeeping

While probing bash behaviour I wrote one scratch file outside the allowed roots:
`/tmp/nls_pc_probe.sh` (a one-line rcfile, `PROMPT_COMMAND=('' 'echo "ST=$? …"')`). I
did not delete it (cleanup is the harness's). A temp index file and a copy of
`session.py` were left in the worktree's git dir (`pdca-tmp-index`, `session.py.keep`),
and there is one dangling commit object from the immutability check. None of these
affect the working tree or `patch.diff`.

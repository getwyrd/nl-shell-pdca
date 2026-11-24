# Build notes — issue 141, round 8 (option N: part 3 removed)

Base: `pdca-integration/main-r2546dbf9639f` @ `0771812`. Started from
`iteration-v7/patch.diff` (applied cleanly), then removed part 3 as the brief lists. Line
refs below are on the patched worktree unless they say `0771812`.

## Brief deviation for the human (please confirm at sign-off)

NEEDS-HUMAN brief deviation: the (j) **CSIZE guard** row ("`stty cs7 istrip` → degraded
`outside-check` before the next paste; next `run("echo hello")` refused") cannot hold on
Linux, because a Linux PTY never takes `cs7`. The kernel's PTY driver
(`drivers/tty/pty.c`, `pty_set_termios`) clears CSIZE/PARENB and sets CS8 on every
settings change. Measured on this host: after `stty cs7 istrip` in bash on a PTY,
`stty -a` shows `-parenb cs8 istrip`, and `tcgetattr` on the master shows CS8 before and
after. What is left is the shell's own ISTRIP, which is part 3 (not checked, #149,
decision 10), and readline clears it while it reads because CSIZE is CS8. So the paste
bytes are safe and the session correctly stays healthy. My first test, written as the
brief says, failed on the patched tree for exactly this reason (`DID NOT RAISE
SessionDegraded`, zero writes expected, one write seen).

What I shipped instead tests the end result the row exists for (the ISTRIP/INPCK part of
R depends on CS8): `test_character_size_change_cannot_strip_paste_bytes`
(`tests/test_session.py:1231`). After `stty cs7 istrip` the session either degrades
(fail safe) or an `é` round trip is exact (`c3 a9`, so no eighth bit was stripped), and
the PTY's CSIZE is still CS8. This is a regression guard (passes on the base too), not
red-leg evidence. If the human wants a test that a CSIZE change *would* be refused, the
only way on Linux is to fake the reading (for example a `_read_termios` wrapper that
returns CS7). I did not do that because it would not drive a real terminal state. The
spec sentence matches what I found (`docs/design/specs/pty-protocol/v1.md:322-324`).

## What changed from round 7 (the removal)

Production, `src/nl_shell/session.py`:
- Gone: `_read_shell_r`, `_check_shell_r`, the `_shell_r` attribute (was set in
  `__init__` and cleared in `close`), the `shell_r` local and its D..E reading in `_spawn`,
  and the `shell_r` local, its post-D reading and its check at `E` in `_wait_for_result`.
- `_start_checks` takes no argument and no longer degrades for "could not be read between
  its first done record and E" (`session.py:579`, `:585`). This was the round-7 false
  alarm source.
- Kept because part 2 uses them: `_R_FIELDS`, `_R_FORCED`, `_R_CONDITIONAL`
  (`session.py:317-332`), `_r_values` (`:1110`) and `_r_diff` (`:1121`). All are used
  by `_prompt_baseline` (`:879`), which checks at the first prompt that R has readline's
  values. Nothing that only part 3 used is left: `git grep` finds no `_shell_r`.
- `_prompt_check` docstring (`session.py:900-907`) now says the shell's own R is not
  checked (#149). No comment claims a reading sees the shell's own R.
- Everything else from round 7 is unchanged: the pre-paste check between
  `_wait_for_prompt` and `_write_all` (`session.py:676-683`, peer callsite
  `0771812:src/nl_shell/session.py:508-515`), fd-at-E with the re-read
  (`_check_fds_after_e`, `:931`), stopped check (`_check_stopped`, `:1014`), TIOCSTI
  (`_check_tiocsti` called at `:583`), reason codes, rcfile `H` rows, pins.
  `src/nl_shell/pty_protocol.py` is exactly round 7's.

Tests, `tests/test_session.py`:
- Removed `test_shell_own_readline_fields_degrade_by_the_next_command` (5 cases:
  foreground `stty -isig`, `-icanon -echo -isig`, `icrnl inlcr istrip inpck`,
  `lnext/discard/min/time`, v3 DEBUG trap with `stty -isig`), its `_R_CHANGES` table, and
  the helper `_assert_first_run_under_it_degrades`. These required a foreground R change
  to degrade, which decision 10 drops.
- (k) background job: `test_background_job_turning_signals_off_is_refused`
  (`:1189`) is now strict. The first `run` is healthy, wait 1.5 s, the next
  `echo hello` is refused with zero writes and code `outside-check`. Round 7 let the
  change command itself degrade at its E through part 3. That way out is gone, so the test
  now pins part 2 alone. `test_v5_fd4_bypass_shape_is_refused` is unchanged.
- New (st): `test_stall_after_each_pty_write_stays_healthy` (`:1338`),
  `test_stall_before_each_control_read_stays_healthy` (`:1351`),
  `test_busy_python_thread_stays_healthy` (`:1364`, thread started before `Session` is
  constructed, stopped in `finally`). Each does 30 × `true` and then an exact `echo hello`.
- New (rm): `test_no_reading_of_the_shells_own_readline_fields` (`:1384`) reads
  `src/nl_shell/session.py` as text and checks that none of the three names appear.
- Dropped a stale "Part 3 reads…" comment from `test_many_quick_commands_stay_healthy`.

Docs:
- Spec §1 "What this protects": "three parts" → "two parts", part 3 replaced by a
  paragraph saying the shell's own R is not checked (#149) and why
  (`v1.md:210`, `:225-228`).
- Spec §3 outside checks: item 3 replaced by a paragraph saying the shell's own R is
  not checked, why every reading without a handshake either sees readline's values or
  depends on a scheduling window, and the `interrupt()` effect with ISIG off (`v1.md:345-352`).
  The closing line also says no check depends on such a window. The R paragraph names
  the CS8 condition (`v1.md:322-324`).
- Spec §4.2: removed "or R in the shell's own settings at `E` …" from the outside-check
  trigger.
- Threat model Known gaps: the #149 bullet is reworded to "not checked" and names the
  `Session.interrupt()` hang (`.oss-scanner/threat_model.md:201-208`). #145 is its own
  bullet (`:211`). The "#145 reviews what else…" phrase is gone from the intro, so there
  is no catch-all. The #78 line is the brief's sentence exactly (`:213`).
- The spec is `status: draft`, so the docs-immutability CI check allows the edits.
  `scripts/docs_links.py`: 0 broken.

Patch size: round 7's `patch.diff` is 1779 lines, this one is 1767. The diff against
`0771812` is 5 files, +1317 / −67.

## Gates I ran (project runners)

- C4 `engine/scripts/run-verify.sh` (with `PDCA_WORKTREE` / `PDCA_BUNDLE` set):
  `PDCA-EVIDENCE: C4 PASS — red without the fix (56 of 164 failed), green with it`.
  `ran 164, failed 56, setup errors 0, import/collection errors 0`. The tree was
  restored afterwards (the `git diff` matched `patch.diff` byte for byte).
- T3 `engine/scripts/run-suite.sh`: `401 passed`, `PDCA-EVIDENCE: T3 PASS`.
- Formatter / hooks: the target configures none (`pyproject.toml` has no
  ruff/black section, and there is no `.pre-commit-config.yaml`). Its CI runs pytest,
  `docs_checks.py immutability` and `docs_links.py`. I ran `py_compile` on both Python
  files and `docs_links.py`, and kept the files' existing style. DCO sign-off is added at
  commit time by publish.

### Red-leg audit (brief: "not just the failure count")

- Not one of the 24 distinct failing test functions is a #140 test. I compared their
  names against every `def test_` on `0771812:tests/test_session.py`, and there was no
  overlap.
- No setup error or collection error. Each `TypeError`/`AttributeError` comes from a
  test body:
  - `test_tiocsti_not_off_starts_degraded[allowed|missing]`: `TypeError` on
    `tiocsti_path=`. The brief allows this: only these tests pass it, and the keyword is
    the API under test.
  - `test_fd_check_at_e_waits_out_the_e_redirect`: `AttributeError` on `_read_fds`. This
    is an (fa) regression guard that wraps a method the base doesn't have.
  - `test_hook_builtins_are_exactly_the_ones_the_hooks_call` /
    `test_disabling_any_hook_builtin_degrades`: they read `HOOK_BUILTINS` in the body
    to know what to iterate (as round 7 did).
  - **Code-only reds (not I1 evidence):**
    `test_table_a_rows_degrade_at_their_own_snapshot[xtrace]` and
    `test_redirected_shell_fds_are_refused[stdout]` fail with `AttributeError:
    degraded_code` at `tests/test_session.py:1031`. That is after the "degraded at its
    own snapshot" checks passed. On the base these two already degrade at their own
    snapshot (fail safe, for another reason), so their only red is the missing code.
    Leaving these two out still leaves 54 genuine attack failures.

## (st) re-confirmed against round 7 (brief Falsifiability)

I set my state aside in a temporary local commit, put round 7's `session.py` and
`pty_protocol.py` back (`git checkout 0771812 -- …` plus `git apply --include='src/*'
iteration-v7/patch.diff`), and ran the three (st) tests with this round's test file:
**3 failed / 3**. The reason in each was `session degraded: the shell's own terminal
settings could not be read between the done record and E …`. Then I restored my code and
soft-reset the temporary commit away (the branch is still at `0771812` and the worktree
holds only the uncommitted patch). On this round's tree all three pass, in the targeted
run and inside T3.

## Self-refutation (forced)

- **(a) Genuine red?** Yes. With production reverted (the C4 red leg), 56 of 164 fail and
  54 of those fail on the attack (marker, write count, or healthy session). (st) does not
  go red on the base by design (the base has no D..E reading), but it goes red 3/3 on
  round 7's production, which is the regression it guards. (rm) passes on the base, which
  is expected for a regression guard. The CSIZE row is a regression guard too (see the
  deviation section).
- **(b) Production path?** Yes. Every test starts the real `nl_shell.session.Session`
  on a real bash 5.3.9 on a real PTY. The (st) monkeypatches wrap the real `_write_all` /
  `Session._read_control` (they call the real one and add a `time.sleep(0.05)`), and the
  busy thread is a real thread in the test process. (rm) reads the real source file.
- **(c) Fixture includes the fault?** Yes. The attacks are real (`stty` in a real
  background job with `trap '' TTOU`, real traps, real `bind`). The stalls are real
  sleeps in the real read/write path. The busy thread runs during `Session.start` too.
  The `start_session` fixture passes no new API and no `tiocsti_path`.

## Housekeeping

- Gate logs went to `/tmp/claude-1000/{c4,t3}.log` and the failed-name lists to
  `/tmp/claude-1000/` (the harness's task directory). I removed nothing.
- The two temporary local commits (`WIP round 8`) are unreferenced objects. No branch
  points at them. Nothing was pushed and no PR was opened.

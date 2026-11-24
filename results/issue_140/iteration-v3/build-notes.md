# Build notes — issue_140 (persistent-bash-session-core), iteration 3

## Base

Built in `$PDCA_WORKTREE` = `/home/eddie/nl-shell/nl-shell.pdca-wt-l0`, HEAD `2ddc3e8`
(`origin/pdca-integration/main-r2546dbf9639f`). That is the branch C4 applies the patch to.
The brief names `c47c5c2`, but iteration 1 failed C4 because its patch did not apply to the
integration branch. The iteration-2 patch applies cleanly here (`git apply --check` passed),
so I started from it and added the fixes below. Line numbers are on this tree with
the patch applied. This base's `pty-protocol/v1.md` has no §4.4/§4.5, so the "restart lands
with #121" line sits in §4.3 (as in iteration 2).

## What changed vs. iteration 2 (the sign-off's four items, plus size)

1. **Builtin shadowing (High): docs only, as the sign-off's option (a) asks.** No code
   detects a function named `builtin`/`command`/`eval`/`return`. The text now says so in
   four places: the rcfile comment (`src/nl_shell/session.py:102-108`), spec §1.3
   (`docs/design/specs/pty-protocol/v1.md:127-134`), spec §3's "not covered yet" list and
   §4.2 (`v1.md:202-203`), and the threat model's interim Known-gaps bullet
   (`.oss-scanner/threat_model.md:168-179`). Each one names #141. The old "defined with
   alias expansion off" claim is corrected in both the comment and the spec: function
   bodies are parsed with aliases off, but every `$( … )` in PS0/`__nls_snap` is parsed
   again at run time with the user's aliases (`session.py:102-104`, `v1.md:129-131`).
   I did not try a code fix. The security review explains why it is not cheap (H is
   gathered through the same calls a shadow function would replace), and the human chose
   the docs route.
2. **`TERM` in H (the preferred option).** `__nls_snap` now puts `declare -p TERM` into
   H (`session.py:146`, the spec's rcfile copy at `v1.md:92`; the existing
   `test_spec_reference_rcfile_is_the_one_in_use` keeps the two the same). So
   `export TERM=dumb`, `unset TERM`, or any other `TERM` change degrades at that command's
   own snapshot, and the next `run()` raises without writing. The degrade reason names TERM
   (`pty_protocol.py:296`). Spec §3's H list names TERM (`v1.md:163-164`).
   `bind 'set enable-bracketed-paste off'` is still not detected. That is readline state
   (Table A row 6), which the brief puts in child-2, and it is now listed in the Known-gaps
   bullet and in spec §3 as `readline state (\`bind\`)` under #141.
   Probe: `TERM=xterm-256color` (the same value the session starts with) stays healthy,
   `unset TERM` degrades.
   Cost: one word in the rcfile. Some harmless `TERM` changes (e.g. `xterm` → `screen`)
   also degrade now. That is the over-degrade the human accepted by preferring this option.
3. **Job notices.** I measured this on this host. After `sleep 0.2 &`, a 0.6 s wait, then
   `echo x`, the output is `x\r\n[1]+  Done   sleep 0.2\r\n`. Bash prints the notice
   before its next prompt, which is before nl-shell's end marker. Spec §4.1
   (`v1.md:183-186`) now says the S..D output includes those notices. The vectors note
   (`v1.md:257-258`) says the test checks it. New test
   `test_job_notice_is_part_of_the_next_commands_output` (`tests/test_session.py:923`)
   checks for the `[1]+ Done sleep 0.2` line and `x` without fixing their order. The order
   depends on when the job ends: in a second probe, where the job ended while
   `sleep 0.6; echo y` ran, the notice came before `y`.
4. **Timed/single-key reads.** Spec §4.2 (`v1.md:198-200`) and the threat model
   (`threat_model.md:177-178`) now list `read x`, `read -t`, `read -n1 -t` and `select`
   together under #136.

**Size.** The iteration-2 patch was 102,956 bytes; this one is 98,157. To get there I
shortened docstrings and comments in `session.py` and `pty_protocol.py` (same meaning,
fewer words), cut the dash padding on the test section headers, and merged the three
`test_*_round_trips_exactly` tests into one parametrized
`test_text_fields_round_trip_exactly` (`tests/test_session.py:735`) with the same
commands and assertions. I removed no test case. There are 88 tests, up from 86: +2 new,
and the 3-to-1 merge keeps 3 parametrized cases.

## Verification (the project's runner, `engine/scripts/run-verify.sh`)

- Full patch: `C4 PASS — red without the fix (88 of 88 failed), green with it`. Green leg
  88 passed.
- That red is only `ModuleNotFoundError` (the new module is missing), which the adversary
  called weak evidence. So for the new `TERM` fix I also ran the same runner on a bundle
  (inside the worktree, `.scratch/term-bundle/`) whose patch is only the `TERM` hunks plus
  the `term-dumb` test case. Result:
  `C4 PASS — red without the fix (1 of 88 failed)`. The one failure was exactly
  `test_table_a_row_1_changes_degrade_at_their_own_snapshot[term-dumb]`. Afterwards the
  worktree matched `patch.diff` byte for byte.
- Whole suite (`engine/scripts/run-suite.sh`): `325 passed`, T3 PASS.
- `python3 -I scripts/docs_links.py`: 0 broken links.
- Formatter / hooks: the target configures none (no pre-commit, no ruff/black in
  `pyproject.toml`; CI runs pytest plus `docs_checks.py`/`docs_links.py`). Both Python
  files parse, and the doc link check passes.

## Refuting my own test

- **(a) Genuine red?** Yes. With the whole fix reverted, 88/88 fail. With only the `TERM`
  hunk reverted, the `term-dumb` case fails, because the session stays healthy and the
  test expects `SessionDegraded` with a result. The job-notice test only pins existing
  behaviour: its red comes from the missing module. It goes red if anyone later filters
  notices out of the output without updating the spec, which is its job.
- **(b) Production path?** Yes. Every session test starts a real bash 5.3.9 on a PTY
  through `nl_shell.session.Session` and reads the real fd-3 records. The no-write check
  spies on `session._write_all` and still calls the real function.
- **(c) Fixture includes the fault?** Yes. `export TERM=dumb` is run as a confirmed command
  in the real session, and the follow-up `echo hello` is checked to write nothing to the
  PTY. The job-notice test uses a real background job.

## Not done / open for the human

- Builtin shadowing is documented, not detected (item 1, by the human's choice). It is a
  real High for #141.
- The adversary's Low finding (the end-marker token can be seen through `declare -f
  __nls_done`) is unchanged; the sign-off did not ask for it.
- The brief's base (`c47c5c2`) still differs from the integration branch I built on. It
  applies here, and C4 applies here.

No external dependency beyond the brief's `ptyprocess` and `proc-syscall` was needed.

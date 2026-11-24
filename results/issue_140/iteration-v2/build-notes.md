# Build notes — issue 140 / persistent-bash-session-core (iteration 2)

All `path:line` references are on the patched worktree, which sits on `2ddc3e8`
(`origin/pdca-integration/main-r2546dbf9639f`, this bundle's `stack-base-tip`).

## What the carry-forward asked, and what I did

### 1. Failing gate: "patch.diff did not apply onto origin/pdca-integration/main-r2546dbf9639f"

Cause: iteration 1 built on `c47c5c2` (`origin/main`, as the brief says). The driver
rebuilds and verifies on the run's integration branch `2ddc3e8`, which is `8c95e05` +
issue_14 + issue_92 and does **not** contain main's #124–#133 docs. Only one file differed
in a way that mattered: `docs/design/specs/pty-protocol/v1.md`. On `c47c5c2` it has §4.4–§4.5
(session recovery, #132), §6 item 6 (background output, #131) and vectors 13–16; on `2ddc3e8`
it has none of them (`git diff 2ddc3e8 c47c5c2 -- docs/design/specs/pty-protocol/v1.md`:
27 lines). Iteration 1's first spec hunk ran through §4.4/§4.5, so it could not apply.

Fix: this time the patch is built on `2ddc3e8` (the worktree the harness gave me) and
**every hunk applies on both bases**. Checked with a throwaway index per base
(`GIT_INDEX_FILE=<git-dir>/pdca-check-index git read-tree <base>` then
`git apply --cached --check patch.diff`):

```
applies on 2ddc3e8
applies on c47c5c2
```

How: the spec file's diff is emitted with one line of context (`git diff -U1`), and no hunk
edits a line that exists on only one base. The one place that mattered:

- §4.3 item 3 (`docs/design/specs/pty-protocol/v1.md:194-197`) is the last shared line before
  the bases differ (`c47c5c2` continues with item 4; `2ddc3e8` with `### 5.`). I rewrote the
  item but kept its last line, `   nl-shell MUST offer to restart the session.`, unchanged,
  so it is the hunk's one line of trailing context and matches on both.
- **Deviation from the brief's Docs list:** the brief asks for "one line each" in §4.4 and
  §4.5 saying restore-cwd and the `session_restart` record land with #121. Those sections
  do not exist on `2ddc3e8`, so no hunk can edit them and still apply there. I put the same
  pointer in §4.3 item 3 instead (`:195-196`: "A restart gives a fresh session and baseline;
  restoring the cwd (§4.4) and the `session_restart` record (§4.5) land with #121."). On
  `main` that sentence sits just above §4.4/§4.5; on the integration branch the §4.4/§4.5
  references dangle until main's #132 is folded in. **Please check at sign-off.** The
  cleaner fix is to rebuild the integration line on current `main` and then move the two
  sentences into §4.4/§4.5 (a 4-line follow-up); that is a driver/human choice, not mine.
- The vectors note (`:255-256`) has the blank line before it as its only leading context,
  because the row above it is vector 12 on one base and vector 16 on the other.

Everything else in the patch (threat model, ADR-0013/0014, policy-gate, `pyproject.toml`,
the two new modules, the test) already applied on both bases in iteration 1 (git's offset
search handles the shifted line numbers). I reused it unchanged except for the fix below.

### 2. Reviewer finding: the prompt rule degraded healthy commands that read a redirected fd 0

Confirmed. `_reading_terminal` counted any `read(0, …)` as "back at a prompt". In
`read x < <(sleep 1.5; echo hi)`, `mapfile … < <(…)` or `while read … done < <(…)`, bash
itself (not a child) blocks in `read(0)` with fd 0 dup'ed to a pipe for well over 1 s, and the
session degraded with `result=None` though the command was running normally.

Fix (`src/nl_shell/session.py`):

- `:709-724` `_reading_terminal` now returns `blocked and self._stdin_is_terminal()`.
- `:726-746` `_stdin_is_terminal` stats `<proc_root>/<pid>/fd/0` and checks it is a
  character device whose `st_rdev` equals the session's PTY slave. If that file cannot be
  read, it raises `_ProcUnreadable` naming the path, the same fail-closed path the
  `syscall` file already used (brief: "if `/proc/<bash pid>/syscall` cannot be read … the
  session degrades with a reason naming the file (fail closed)"). The `fd/0` read is only
  made when `syscall` already says bash is blocked on fd 0, so the brief's (e) case (missing
  `syscall`) still names `syscall`.
- `:782-793` `_pty_slave_rdev` gets the slave's device number from the master fd:
  `os.ptsname` on Python 3.13+, else the Linux `TIOCGPTN` ioctl (`:234`; the target says
  `requires-python = ">=3.12"`, and 3.12 has no `os.ptsname`). Computed once at spawn
  (`:468`). If it can't be found, `_tty_rdev` stays `None` and the prompt rule fails closed
  (`:734-738`).
- Imports `stat`, `struct` (`:26-27`).
- Spec §4.2 third trigger (`docs/design/specs/pty-protocol/v1.md:187-191`) now says fd 0 must
  be the session's PTY, and that either file being unreadable degrades.

Why compare against the slave, not "bash's fd 0 at start": the master fd is ours, so the
answer doesn't depend on anything bash or the user's `~/.bashrc` did. Why not drop the
`read` case and keep only `pselect6`: `read x` with no input (brief (k), must degrade)
blocks in `read(0)` on the PTY, so the `read` case is needed; the fd-0 check is what tells
the two apart.

What still degrades by design (unchanged): `read x` from the terminal with no input
(#136), the unclosed quote, a replaced `PROMPT_COMMAND`.

Tests added (`tests/test_session.py`):

- `:699-714` `test_slow_read_from_redirected_stdin_stays_healthy` — the reviewer's three
  cases, each must finish ran, status 0, exact output, healthy.
- `:717-733` `test_unreadable_proc_stdin_fails_closed` — a fake `proc_root` where
  `<pid>/syscall` is a symlink to the real file but `fd/0` is missing: `run("read x")` raises
  `SessionDegraded` within 5 s, nothing is written to the PTY (the check runs before the paste,
  because bash at its prompt is blocked on fd 0), and the reason names `<pid>/fd/0`.

### 3. Other carry-forward items

- "Obtain a matching-base full pytest run": done below, on the base the gate uses.
- T4 prior-art (closed/rejected work evidence): not build work; the brief lists what was
  rejected in #101 and none of it is reintroduced (see iteration 1's list, unchanged).
- The 11 deferred findings are for the human; I didn't act on them. One of them (adversary:
  `export TERM=dumb` or `bind 'set enable-bracketed-paste off'` turns paste off and the next
  command then runs as keystrokes) I left alone: readline state is Table A row 6, out of scope
  here (#141), and whether `TERM` belongs in `H` is a scope call for the human.

## Results (project runners, on the `2ddc3e8` worktree)

C4 (`engine/scripts/run-verify.sh`, `PDCA_BUNDLE`/`PDCA_WORKTREE` set, absolute paths):

```
== C4 green leg: … 86 passed in 39.83s
== C4 red leg:   … 86 failed in 1.09s
   (pytest exit 1; ran 86, failed 86, setup errors 0, import/collection errors 0)
PDCA-EVIDENCE: C4 PASS — red without the fix (86 of 86 failed), green with it
```

Run twice; both PASS. T3 (`engine/scripts/run-suite.sh`): `323 passed in 45.54s`,
`PDCA-EVIDENCE: T3 PASS`. `scripts/docs_links.py`: 0 broken. `git diff --check`: clean.

Targeted red for the new fix: I replaced only `return blocked and self._stdin_is_terminal()`
with `return blocked` and re-ran the C4 runner. Green leg: `4 failed, 82 passed` — exactly
the three redirected-stdin cases and `test_unreadable_proc_stdin_fails_closed`. Then I put
the line back and confirmed the regenerated diff is byte-identical to `patch.diff`.

The spec §4.2 wording edit came after those runs; it is prose only and no test reads §4.2
(`test_spec_reference_rcfile_is_the_one_in_use` reads only the §1.3 code block).

## Commit-ready

The target has no formatter or lint hook (no ruff/black/flake8 in `pyproject.toml`, no
`.pre-commit-config.yaml`). No line over 100 chars in the touched Python; `git diff --check`
clean. Commits need a DCO `Signed-off-by` (`CONTRIBUTING.md`), which is publish's job.

## Refuting my own test

- **(a) Genuine red?** Yes. `run-verify.sh` reverts every non-`tests/` hunk and re-runs:
  86 of 86 failed (`ModuleNotFoundError`, 0 collection errors), because the test imports
  the session modules inside each test. For the new fix alone, reverting just the fd-0 check
  turned exactly the 4 new tests red (above).
- **(b) Production path?** Yes. Tests call `nl_shell.session.Session` from the worktree's
  `src/`; every session is a real `bash --noprofile --rcfile … -i` on a real PTY via
  ptyprocess. The only double is a spy around `_write_all` that records bytes and still calls
  the real function. The fake `proc_root` is the production `proc_root` keyword the brief
  specifies.
- **(c) Fixture includes the fault?** Yes. The redirected-stdin tests run the exact commands
  the reviewer used to make the old code degrade; the fd-0 test removes the real file the new
  check depends on, with `syscall` pointing at the live process so the check is really
  reached.

## External dependencies

`ptyprocess` and `proc-syscall` are listed in the brief and present. The new check also
reads `/proc/<pid>/fd/0`; for a direct child it needs less access than `syscall` (read vs.
attach mode under `ptrace_scope = 1`), so it is covered by the same `proc-syscall`
dependency; the green runs above read it on this host. No unlisted dependency.

## Docs (unchanged from iteration 1 apart from §4.2, §4.3 and the §4.4/§4.5 move)

Iteration 1's deviations still stand and still need a look at sign-off: vector 8's wording
(`PROMPT_COMMAND=:` degrades by the prompt rule, not by `H`), the §2 table update, "Table A"
not being defined in the target, and policy-gate §7.5 item 7 left as is. NEEDS-HUMAN from the
brief's plan-review response 2: confirm the §Versioning reading ("while `draft`, v1 changes
in place").

## Housekeeping

Files I left that are not part of the patch (cleanup is the harness's job, so I didn't
delete them):

- `docs/design/specs/pty-protocol/v1.md.rej` in the worktree (untracked), from applying
  iteration 1's spec hunks with `--reject`; not in `patch.diff`.
- `<worktree git dir>/pdca-check-index`, the throwaway index for the apply checks.
- `results/issue_140/patch.new`, a copy of `patch.diff` I used to confirm the diff was
  current. Identical to `patch.diff`; ignore it.
- `/tmp/x`: I mistakenly redirected one `git diff` there before switching approach. It is
  outside the allowed roots; it holds only a diff of the spec file.

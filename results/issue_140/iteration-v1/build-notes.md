# Build notes — issue 140 / persistent-bash-session-core

All `path:line` references are on the patched tree built on `c47c5c2` (= `origin/main`).

## Read this first: the base

The harness gave me a worktree at `2ddc3e8` (`pdca-integrate: issue_92`, the bundle's
`stack-base` = `pdca-integration/main-r2546dbf9639f`). The brief says to build on
`origin/main` = `c47c5c2`, not the stale stack base. I moved the worktree there
(`git checkout --detach c47c5c2`) and built on it.

Checked with a throwaway index per base (`git read-tree` + `git apply --cached --check`):

- `c47c5c2` / `origin/main`: `patch.diff` applies.
- `2ddc3e8` (the stack-base tip): does NOT apply (`docs/design/specs/pty-protocol/v1.md:45`;
  #124–#133 are not on that branch).

I did not edit `results/issue_140/stack-base` or `stack-base-tip`: they are the driver's
state. **If the driver resets C4 to the stack base, C4 fails for a reason unrelated to the
patch** (the same thing happened in #101 v4). The human should clear those two files so
the gate uses `PDCA_BRIEF_BASE=origin/main`.

## Result

The project's C4 wrapper, run against this bundle and worktree:

```
PDCA_BUNDLE=results/issue_140 PDCA_WORKTREE=…/nl-shell.pdca-wt-l0 engine/scripts/run-verify.sh
== C4 green leg: 82 passed in 34.10s
== C4 red leg:   82 failed in 1.08s
PDCA-EVIDENCE: C4 PASS — red without the fix (82 of 82 failed), green with it
```

The whole suite (`engine/scripts/run-suite.sh`) passed twice in a row: 259 passed, about 40 s each.
The repo's own CI docs checks also pass on the patched tree (checked with a throwaway
commit, then undone): `scripts/docs_checks.py immutability c47c5c2 HEAD` → OK (ADR-0013 and
ADR-0014 are `Proposed`, the specs are `draft`); `scripts/docs_links.py` → 0 broken.

There is no formatter or lint hook in the target (no ruff/black/pre-commit in
`pyproject.toml`, `.github/workflows/`, `CONTRIBUTING.md`). I matched the existing style
(no line over 100 chars, no unused imports, `git diff --check` clean). Commits need a DCO
`Signed-off-by` (CONTRIBUTING.md:7-17). That is publish's job, not part of the patch.

## What changed and why

Starting point: `results/issue_101/iteration-v5/patch.diff` (the brief allows reuse).
I kept its parser/tracker (`pty_protocol.py`) and its `_Output` output cut, and took out
everything this child puts out of scope:

- removed the fd-4 check point and every outside check (termios, fds 0-4, `TIOCSTI`,
  stopped bash): Table B → #141;
- removed Table A rows 2-7 from `H` (DEBUG/RETURN traps, extdebug/functrace, xtrace/PS4/
  BASH_XTRACEFD, histexpand, emacs/vi mode, `bind -v`/keymaps): → #141.

Then the changes this brief asks for:

1. **Hook order (decision 6, I3).** `src/nl_shell/session.py:135-149` `__nls_done`:
   save `$?`/PIPESTATUS → print the end marker → `D` → user `PROMPT_COMMAND` (sees the
   command's `$?` through `__nls_ret`) → reset scratch variables. Then `__nls_snap`
   (`:150-186`) writes the snapshot and `E`, and only then sets `PS1='\$ ' PS2='> '`
   (`session.py:185`). In v5 PS1/PS2 were set before the snapshot. The brief says after.

2. **`H` = Table A row 1, values and attributes (decision 3).** `session.py:151-167`:
   `declare -p PS0 PROMPT_COMMAND __nls_user_pc`; `shopt -p promptvars`; `declare -p` of
   every `HOOK_STATE_VARS` name (`session.py:63-76`); the *attributes* of PS1/PS2; and
   `declare -f` of the four hook functions.
   - Values. v5 printed attributes only. The brief says "value AND attributes". Scratch
     variables are reset to fixed values at the end of `__nls_done` (`session.py:148`), so
     their `declare -p` is constant at H time. The counter `__nls_seq` changes on every
     command. `pty_protocol.expected_hooks` (`src/nl_shell/pty_protocol.py:146-157`)
     substitutes the D record's number into the baseline's `__nls_seq="0"` line and
     compares the rest byte for byte (`pty_protocol.py:324`). A baseline without exactly one
     such line degrades (`:320-322`).
   - Order inside H matters. The state-variable loop runs before the PS1/PS2 attribute
     loop, which assigns `__nls_v`. My first draft had them the other way round, and
     `__nls_v` then held PS2's full value, so `PS2='x'` would have degraded. Caught in the
     smoke run and fixed; `test_ordinary_changes_stay_healthy[ps2]` pins it.
   - `promptvars` is in H, though the brief's row-1 list doesn't name it. `S` is
     written by PS0, and with `shopt -u promptvars` PS0 is not expanded, so `S` would
     silently stop and every command would read as "nothing ran" while healthy. That is
     exactly the I2 hole ("unless H covers it"). Tested in `_TABLE_A_ROW_1["promptvars-off"]`.
   - PS1/PS2 *attributes* are in H: `readonly PS1` would make the post-snapshot `PS1=`
     fail, and the user's prompt would then be expanded (I3). Values are not in H, because the hook
     overwrites them after `E`, so `PS1='x$ '` stays healthy as (f) requires.

3. **`V`** is the encoded `declare -p` text (or `NAME unset`) per variable
   (`session.py:168-174`). v5 used `declare -p a b c 2>&1`, which mixes in bash's error text.

4. **Prompt rule fails closed via `proc_root`** (`session.py:354`, `:654-713`).
   `_syscall` raises `_ProcUnreadable` with the full path if the file can't be read;
   `"running"` means not blocked. It is read at start (`session.py:476`: a session whose
   file is unreadable starts *degraded* with the path in the reason), before every paste
   (`:542`) and on every poll while a command runs. `proc_root` is a public attribute, so
   the test can take the file away mid-run (`test_unreadable_proc_syscall_during_a_run_degrades`).
   The pre-paste wait (bash must be in readline before the paste) is kept from v5. Without
   it, a paste that arrives while the tty is still cooked would be line-edited by the
   kernel (e.g. DEL).

5. **Not taken from v5:** the stopped-shell check (Table B), `tiocsti_path`, the check-point
   `read -t -u 4` in the hook. **Not reintroduced** (rejected in #101): a guard variable
   deciding whether `S` is sent, the user hook after the snapshot, the `tcgetpgrp` rule,
   `tr`/`cksum`, CRC `H`/`V`, non-reversible `P`, "D without S → degraded".

6. **pyproject.toml:15**: `ptyprocess>=0.7`.

### Docs (same patch)

- `pty-protocol/v1.md`: §1.2 (`:48-52`); §1.3 the reference rcfile is now `RCFILE`
  verbatim (`:53-...`, pinned by `test_spec_reference_rcfile_is_the_one_in_use`) plus a
  paragraph on no external programs, `\\n` in PS0 and the end marker; §2 table + encoding
  (`:136-150`); §3 `H`/`V` (`:152-174`); §4.1 (`:177-182`); §4.2 (`:183-193`); §4.3
  (`:194-195`); §4.4/§4.5 one line each (`:199`, `:203`); §Versioning (`:253`); vector 8
  (`:269`); vectors note (`:279`).
- `policy-gate/v1.md:199-204` (§7.5 items 5 and 6); ADR-0014 `:45-47`, `:53-55`;
  ADR-0013 `:72-74`; threat model `.oss-scanner/threat_model.md:181-188` (Known gaps
  interim bullet naming #141 and #78) and `:196-198` (How to exercise it).

**Deviations from the brief's Docs wording (please check at sign-off):**

- **Vector 8.** The brief asks for "degraded at that command's snapshot (`H` changed)".
  That is not what happens for `PROMPT_COMMAND=:`. The assignment replaces the hook,
  so no `D` and no snapshot ever comes. Measured: reason "no done record after the shell
  returned to a prompt", `result` None. The H path is for changes that keep the hook
  (`PROMPT_COMMAND+=(':')` → "H differs", `result` set). I wrote vector 8 to say both
  (`pty-protocol/v1.md:269`) rather than write something false. Making the brief's text
  true would need a different `PROMPT_COMMAND` layout that survives a scalar assignment.
  I found none that keeps the hook at index 0.
- **§2 table** (not in the brief's list): `F` and `L` changed format (encoded text, `F`
  sent every time, one name per line). Leaving §2 saying "space-separated / `\x1e`-joined /
  sent only when changed" would contradict the code. The brief's §Versioning sentence
  already counts `L`/`P` format changes, so I treated this as covered.
- **"Table A"** is not defined anywhere in the target repo (`grep -rn "Table A"` on
  `c47c5c2`: no hits). The spec text names the covered items directly and points at #141
  for the rest. The threat-model bullet keeps the brief's wording but says "of the #101
  design".
- **policy-gate §7.5 item 7** (`:205-206`, target mismatch) still says "degraded mode:
  everything `mutating`". The brief limits the edit to items 5 and 6, so I left it. It now
  reads inconsistently with item 6 / decision 10. Flag for #12 or a follow-up.

**NEEDS-HUMAN at sign-off (from the brief's plan-review response 2):** confirm the
§Versioning reading ("while `draft`, v1 changes in place").

## Test (tests/test_session.py, 82 cases)

Only stdlib + pytest at module level; both session modules are imported inside the tests
(`_session_module()` / `_protocol_module()`), so each test fails on its own when the fix is
reverted (red leg: 82 of 82 failed with `ModuleNotFoundError`, 0 collection errors).
Every session call has a 5 s timeout (or a thread bounded at 5 s), and the fixture closes
every session and checks every record ends in `\n` with no `\r`. Coverage by letter:
(a) cd/export; (b) vectors 1-8, 10, 12 (+ TAB/LF allowed, exact paste bytes); (c) `exec 3>&-`;
(d) one S/D pair for no-output, multi-line, here-doc, multi-line function, `sleep 1 &`;
`sleep 3 &` → `J 0`; (e) empty/comment/`fi` not-run healthy, unclosed quote, `proc_root`
at start and mid-run; (f) fields present, LD_PRELOAD in V, `PS0=` then `true` refused,
9 row-1 changes degrade at their own snapshot (`result.seq == 1`, "H differs") and the
next `echo hello` writes nothing; negatives `readonly FOO=1`, `trap 'echo hi' EXIT`
(T shows it), `PS1='x$ '`, `PS2='more> '` stay healthy; (g) three attacks × all 12
`HOOK_STATE_VARS` + the rcfile-names check; (k) slow substitutions healthy, `read x`
degrades; (l) PATH/alias/trap round-trip with `\x1e`, LF, CR, backslash; fake
`tr`/`cksum`/`wc` via `hash -p`, `BASH_CMDS`, PATH; (m first half) bashrc alias in
baseline, user hook runs before each snapshot (it re-creates an alias after `unalias`)
and sees the real `$?`; (n) HISTFILE unset, `[ -p /dev/fd/3 ]`, CR → malformed; (o)
restart; (q) user hook printing `HOOK-OUTPUT` at all 41 prompts, 20× `echo hello` and
20× `printf abc` exact.

How the (g) attacks ended, measured once (healthy = third command reported ran, status 7,
output `printed`):

- PS1 subscript: all 12 healthy and correct. The user's PS1 is never expanded.
- readonly: all 12 degraded. 6 at their own snapshot (H); 6 earlier, by sequencing or
  the hook failing.
- DEBUG trap: 10 degraded at their own snapshot. `__nls_c` and `__nls_seq` stay healthy
  and correct: the hook overwrites `__nls_c` before use, and assigning `__nls_seq` its
  own value changes nothing.

None ended "ran False" with a healthy session.

## Refuting my own test

- **(a) Genuine red?** Yes. `run-verify.sh` reverts every non-`tests/` hunk with
  `git apply -R --exclude='tests/*'` and re-runs. 82 of 82 failed, 0 collection errors.
  It then restored the tree, and I checked that `git diff` was byte-identical to
  `patch.diff` afterwards.
- **(b) Production path?** Yes. The tests call `nl_shell.session.Session` and
  `nl_shell.pty_protocol` from the worktree's `src/` (pytest `pythonpath = ["src"]`). Each
  session spawns a real `bash --noprofile --rcfile <RCFILE> -i` on a real PTY via
  ptyprocess. The only test double is a spy wrapped around `_write_all` that records the
  bytes and still calls the real function.
- **(c) Fixture includes the fault?** Yes. Each fault is injected into the live bash as
  a confirmed command: replaced `PROMPT_COMMAND`, closed fd 3, an unclosed quote,
  `read x`, readonly/DEBUG/PS1 attacks on every hook variable, fake `tr`/`cksum`/`wc`,
  a user hook that prints. The `proc_root` cases point at a directory that really lacks
  `<pid>/syscall`; nothing is mocked.

## External dependencies

Both are listed in the brief (`ptyprocess`, `proc-syscall`) and both are present
(ptyprocess 0.7.0 in the instance venv; `/proc/<child>/syscall` readable with
`ptrace_scope = 1`). Bash 5.3.9. No unlisted dependency came up.

## Housekeeping I got wrong

I wrote three scratch scripts to `/tmp` (`smoke_nls.py`, `smoke_nls2.py`,
`nls_spec_edit.py`) before remembering the rule against files outside the worktree and
bundle. I also left an empty `.home.XXXX` scratch HOME directory in the worktree root
(untracked and empty, so it is not in `patch.diff`), and a `tmp-index-check` file in the
worktree's git dir from the apply-check. None of them is part of the patch. I did not
delete them, because cleanup is the harness's job.

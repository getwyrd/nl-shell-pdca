## Summary
**User impact:** nl-shell cannot yet run your commands in a real, lasting shell. There
is nothing that keeps a `cd` or an `export` alive for the next command, and nothing that
can tell for sure whether a command actually ran and how it ended — so the planned REPL
(the interactive prompt) has nothing safe to send confirmed commands to.

This PR adds that missing piece: a long-lived bash session that runs exactly the bytes
you confirmed, reports exit status and "did it run" from a private side channel rather
than from printed text, and stops accepting commands the moment its own bookkeeping in
the shell is tampered with. Nothing calls it yet; wiring it into the REPL is #78.

Reported in [#140](https://github.com/eduralph/nl-shell/issues/140).

## What to look at
- **The session itself:** `src/nl_shell/session.py` (`Session.run`, `Session.restart`,
  the generated rcfile `RCFILE`) and the record parser in `src/nl_shell/pty_protocol.py`.
- **Try it** (bash ≥ 5.1, no VM or sudo needed):
  ```python
  from nl_shell.session import Session, SessionDegraded
  with Session.start() as s:
      s.run("cd /tmp", timeout=5)
      print(s.run("pwd", timeout=5).text)          # /tmp
      r = s.run("false | true", timeout=5)
      print(r.status, r.pipestatus)                # 0 (1, 0)
      try:
          s.run("PROMPT_COMMAND=:", timeout=5)     # raises: "H differs from the baseline"
      except SessionDegraded as e:
          print(e.result.seq, s.degraded_reason)
      s.run("echo hi")                             # raises SessionDegraded, sends nothing
  ```
- **Tests:** `python3 -m pytest tests/test_session.py` (93 tests, real bash).
- **What is and isn't protected:** spec `docs/design/specs/pty-protocol/v1.md` §1.3
  "What this protects" and the new Known-gaps bullet in `.oss-scanner/threat_model.md`.
  The claim is a closed list on purpose; see "Scope and limits" below.

## Root cause
nl-shell had no shell session at all: no module that owns a bash process, and no
protocol between nl-shell and that bash for start/done/status records. The design
(ADR-0014, spec `pty-protocol/v1`) existed, but not the code.

## Fix
- **`src/nl_shell/session.py` (new).** `Session` starts one interactive bash on a PTY via
  `ptyprocess`, with nl-shell's control channel on fd 3 and a generated rcfile
  (`RCFILE`, `session.py:95`). `PS0` writes `S`; nl-shell's hook — always the *last*
  `PROMPT_COMMAND` element — writes `D` (status, `PIPESTATUS`) and then the snapshot
  (`F L T B X P J H V E`). User `PROMPT_COMMAND` elements from `~/.bashrc` run before
  the snapshot; nl-shell then sets fixed `PS1`/`PS2`. Hooks use only builtins and
  parameter expansion, `\builtin`-quoted, so user aliases cannot change what they run,
  and they are safe under `set -u` / `set -e`.
- **`run()` (`session.py:495-516`)** refuses, before writing anything, a command
  containing `ESC`, `ESC [201~`, or a C0 control other than TAB/LF
  (`check_command`, `pty_protocol.py:139`), then writes exactly the confirmed bytes as
  one bracketed paste plus `CR`. The result carries sequence number, `$?`,
  `PIPESTATUS`, the output between start and the end marker (bounded, with a truncated
  flag) and the snapshot. `interrupt()` writes `\x03`; `restart()` gives a fresh bash
  and a fresh baseline (no cwd restore — that is #121).
- **Degraded mode.** `H` holds the exact `declare -p` text of everything the hooks
  depend on (`PS0`, every `PROMPT_COMMAND` element, the hook functions, every
  `__nls_*` variable with attributes, `TERM`) and is compared byte-for-byte with the
  baseline. Any difference, a bad or out-of-order record, a closed fd 3, or a shell
  that returns to its prompt without a done record sends the session into degraded
  mode. That state is sticky: every later `run()` raises without writing to the PTY
  until `restart()`.
- **Catching a silent return to the prompt.** Without parsing prompts, the session
  checks `/proc/<bash pid>/syscall`: if bash has been blocked reading the terminal for
  1 s with no done record, it degrades with "no done record after the shell returned to
  a prompt". If that file can't be read, it degrades with a reason naming the file
  (`_wait_for_prompt`, `_syscall`, `session.py:614-691`). The `/proc` root is a
  constructor keyword (`proc_root`) so the failure path is testable.
- **Hook scratch variables.** The hooks keep a copy of their own scratch variables
  (`__nls_pre`, `session.py:117`) before they overwrite them, and that copy goes into
  `H`. Without it, a command that assigned e.g. `__nls_v=42` would be overwritten by the
  hooks before the check and slip through.
- **`src/nl_shell/pty_protocol.py` (new):** record parsing (one reversible text
  encoding for every free-text field), sequencing (`ProtocolTracker`), and the
  forbidden-byte check. Unknown record types are ignored; a record containing `\r` is
  malformed.
- **`pyproject.toml`:** adds `ptyprocess` to `dependencies`.
- **Docs** (all `status: draft` specs or `Proposed` ADRs):
  - spec `pty-protocol/v1` §1.2 (hook order), §1.3 (reference rcfile replaced, plus a
    "What this protects" list), §3 (`H`/`V` are exact encoded `declare -p` text; job
    notices are part of the next command's output), §4.1–§4.5 (done-without-start means
    nothing ran; the prompt rule and its known limits; degraded = refuse; restart
    recovery lands with #121), vector 8, and §Versioning (v1 changes in place while
    draft);
  - policy-gate `v1` §7.5 items 5–6 (session degraded mode refuses — distinct from the
    gate-level state in item 7, which is unchanged);
  - ADR-0014 Decisions 1–2, ADR-0013 (degraded wording), the glossary "Degraded mode"
    row, and the threat model.

### Scope and limits
The session claims a **closed list** of protections, and nothing more:
- a command that ran is never reported as "nothing ran" while the session stays healthy
  — for ordinary commands; for a command that changes anything `H` covers (degrades at
  that command's own snapshot); for a `PS1` that assigns hook state, `readonly` on hook
  state, and a top-level `trap … DEBUG` that assigns hook state; and user aliases cannot
  change what the hooks run;
- of `PROMPT_COMMAND`, `PS0`, `PS1`, `PS2`: nl-shell's hook runs last and the user's
  elements run before the snapshot. A changed value of a plain or exported `PS1`/`PS2` is
  overwritten. A confirmed change to `PS0`, `PROMPT_COMMAND`, or to the *attributes* of
  `PS1`/`PS2` (e.g. `readonly`) degrades at that command's snapshot — but the code it set
  **may still run once** after that snapshot, before the session refuses further commands.

Not claimed here: function shadowing of `builtin`/`command`, DEBUG/RETURN traps inside
the hooks, readline bindings (`bind -x`), xtrace/`PS4`, and other ways around the hooks
(#141, #145); terminal reads on an fd other than 0, `read -t`, `select` (#136) — so
`run()` with no timeout can wait forever on `read -u 2 x`; a default timeout is the
caller's choice (#78). The threat model now says **#78 must not wire the session to
confirmed commands before #141 lands.** One known over-cautious case: a plain `set -a`
as a confirmed command degrades the session (the hooks' scratch variables pick up the
export flag). It fails closed and is left for #145.

### Differences from the issue text
This PR follows the #140 issue and the parent #101 design, except where review settled
otherwise; where they differ, this PR is the intended behaviour:
- hook order (user `PROMPT_COMMAND` before the snapshot, fixed `PS1`/`PS2` after);
- the prompt rule (`/proc/<pid>/syscall`, 1 s, inside a 5 s test limit; Ctrl-C ends a
  command in < 3 s), including `read … </dev/tty`;
- degraded mode means *refuse*, not "confirm every command";
- `TERM` is part of `H`; user aliases are kept out of the hooks;
- the `proc_root` constructor keyword; the background-job notice (`[1]+ Done …`) shows
  up in the next command's output, pinned by a test and documented;
- the threat-model Known-gaps bullet wording above replaces the one in the issue body;
- `H` carries `__nls_pre`, the copy of the hooks' scratch variables taken before the
  hooks change them;
- the `PS1`/`PS2`/`PROMPT_COMMAND` wording says what really happens with a readonly
  prompt string or an appended `PROMPT_COMMAND` element ("may still run once"), which is
  narrower than the issue's "nothing confirmed code sets runs after the snapshot".

## Verification
Line numbers are on this PR's tree (on top of `main` at `c47c5c2`).

| Claim | Checked at | Test (`tests/test_session.py`) |
|---|---|---|
| `cd` and `export` persist | `session.py:325` (`Session`) | `test_cd_persists_between_commands` :155, `test_export_persists_between_commands` :161 |
| Status and "ran" come only from fd-3 records; printed fake records do nothing | `pty_protocol.py:187-303` | vectors 1–5 :170-212, `test_vector6_no_history_expansion` :213 |
| Only the confirmed bytes are sent; forbidden bytes are refused unsent | `pty_protocol.py:139-148`, `session.py:501,515` | `test_vector12_forbidden_bytes_are_refused_unsent` :293, `test_paste_is_exactly_the_confirmed_bytes` :318 |
| Hook changes degrade at that command's own snapshot; nothing more is written | `pty_protocol.py:131-136`, `session.py:117,171` | `test_vector8_…` :227, `test_table_a_row_1_…` :539, `test_hook_state_value_changes_…` :554 |
| Ordinary changes don't over-degrade (`readonly FOO=1`, `trap … EXIT`, `PS1='x$ '`) | — | `test_ordinary_changes_stay_healthy` :581 |
| `PS1` side effects, `readonly`, DEBUG traps on hook state never hide a command | `session.py:60` (`HOOK_STATE_VARS`) | `test_hook_state_vars_cover_the_rcfile` :615, `test_hook_state_attacks_never_hide_a_command` :655 |
| User aliases can't change what the hooks run | `session.py:95-188` (`RCFILE`) | `test_aliases_cannot_reach_inside_the_hooks` :670 |
| Not-run input stays healthy; unclosed quote / `read x` / `read x </dev/tty` degrade within 5 s; unreadable `/proc` fails closed | `session.py:614-691` | :414, :427, :437, :451, :720, :739 |
| Slow command substitutions stay healthy | `session.py:522-580` | `test_slow_command_substitution_stays_healthy` :695 |
| Fake `tr`/`cksum`/`wc`, `hash -p`, `BASH_CMDS` can't change the snapshot | hooks use builtins only, `session.py:95-188` | `test_fake_programs_cannot_change_the_snapshot` :787 |
| `~/.bashrc` hook runs before the snapshot; nl-shell's hook stays last | `session.py:95-188` | `test_bashrc_alias_and_prompt_command_run_before_the_snapshot` :829 |
| User hook output is not the command's output; output is bounded | `session.py:262-322` (`_Output`) | :970, :982, :996 |
| Interrupt ends a command in < 3 s; restart gives a fresh baseline | `session.py:376,483` | :242, `test_restart_after_degraded_gives_a_fresh_session` :952 |
| Spec reference rcfile matches the code | spec `pty-protocol/v1.md` §1.3 | `test_spec_reference_rcfile_is_the_one_in_use` :929 |

- **Red → green:** with every non-test change reverted, all 93 tests in
  `tests/test_session.py` fail; with the change, all 93 pass (bash 5.3.9, real PTY, no
  VM, no sudo). The new scratch-variable test was also checked on its own: with only the
  `__nls_pre` copy removed, its cases fail with `DID NOT RAISE SessionDegraded`.
- **Whole suite:** `python3 -m pytest tests/` — 270 passed.
- **Docs:** `python3 scripts/docs_links.py` — 63 links, 0 broken; `git diff --check` clean.
- **Independent checks** against real bash: all 13 hook-state variables degrade on
  assignment; `set -o posix`, `set -f`, `IFS` changes, `failglob`/`nullglob`,
  `LC_ALL` and a stopped background job leave the session healthy; command bytes the
  filter lets through (DEL, C1 controls, TAB) reach bash exactly as confirmed. Refusing
  DEL/C1/bidi characters belongs to the confirm prompt (#74), not here.

Fixes #140

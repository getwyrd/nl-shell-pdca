Bash was unavailable in this run (every command failed with `apply-seccomp: … Permission denied`); this review was done with Read, Grep and Glob only.

# Plan review: issue 140 / persistent-bash-session-core (round 5 brief)

What I checked: the brief against the issue body in `notes.json` (no `sources/` dir and no `dependency-state.json` were provided), and against the target source at `/tmp/pdca-plan-target-fj5fj6a8/target`. The root cause (no session exists) and the repo/target hold up: `src/nl_shell/` has no `session.py` or `pty_protocol.py`, `pyproject.toml:13-15` lists only `prompt_toolkit`, and ADR-0021 exists. Almost all of the doc `path:line` citations match the target's text, which already has §4.4–§4.5 and vectors 13–16. The faults I found are below.

- NEEDS-HUMAN — **I3 claims more than the scope covers, and nothing tests it.** The brief says "(I3) Nothing confirmed code can install runs between the snapshot and the next paste except nl-shell's own hook". The out-of-scope list then excludes "readline state and bindings (`bind`…)" and "DEBUG/RETURN traps inside the hooks". Two problems:
  - Confirmed code can run `bind -x '"\C-m": …'`. That fires on the `CR` the session sends after the paste, which is after the snapshot. So I3, as worded, claims a case the brief itself sends to #141/#145. R1 makes such over-claiming docs a defect of this child.
  - A top-level `trap … DEBUG` fires before every top-level simple command. If any `PROMPT_COMMAND` element runs after the snapshot (e.g. a separate `PS1=…` element), the trap runs there too.

  None of criteria (a)–(q) tests I3 directly. (m) and (q) only show the user hook runs before the snapshot. Fix: narrow I3 to "of `PROMPT_COMMAND`, `PS1`, `PS2` and `PS0`, nothing runs after the snapshot". Add one criterion that pins it, e.g. the snapshot is the last thing the last `PROMPT_COMMAND` element does, or a `trap 'echo X >&2' DEBUG` gives no X after `E`.

- NEEDS-HUMAN — **Decision 10 ("degraded = refuse") is edited into some docs and left out of others, so they will contradict each other.** The brief rewrites spec §4.3, policy-gate item 6 (`:202`), ADR-0014 Decision 2 and ADR-0013 `:72-74`, and says "edit no other ADR". These still say degraded means "everything needs a confirm" or "everything `mutating`":
  - `docs/design/specs/policy-gate/v1.md:204` (item 7, "degraded mode: everything `mutating`", in the same list the brief edits);
  - `docs/design/architecture/10-quality-risks-glossary.md:71` ("everything needs a confirm until restart");
  - `docs/design/adr/0023-os-targets.md:77` (status Proposed).

  Either list these lines, or say explicitly that gate-level "degraded" (target mismatch) is a different state from the session's sticky refuse. Otherwise Check gets an inconsistency it can't trace to the brief.

- NEEDS-HUMAN — **The brief adds claims and tests that neither the tracker body nor the human's R1–R5 decisions cover.** Compared with `notes.json`:
  - `TERM` is added to what `H` covers (I2-b, criterion (f) `export TERM=dumb`). The issue says "`H` in this child covers Table A row 1 only" and does not include `TERM`.
  - I2-d (alias neutralisation of hook command words) is a whole new claim, with its own (g) tests.
  - `read x </dev/tty` and the `/dev/tty` device 5,0 rule.
  - The `proc_root` constructor keyword and its fail-closed test in (e).
  - Pinning and documenting the `[1]+ Done` job notice in (d).

  Each may be carried over from v3/v4, but none appears in the issue or in R1–R5. Each one adds review surface and adds to the 100 KB patch budget below. The brief also changes the threat-model bullet the issue asked for ("remaining Table A rows and all of Table B land with the follow-up child") with no tracker record. Decision 11 only says the brief supersedes the **#101** text, not #140's. Either have the human confirm these additions, or note "this brief supersedes the #140 body" for the PR description.

- NEEDS-HUMAN — **The "keep the patch under 100 KB" goal pulls against the scope.** The brief says "Keep the patch under 100 KB (v4 was 100,456 B; the removals should bring it under)". This round removes the functrace handling (R2). But it also adds new tests (TERM, I2-d, `/dev/tty`, `proc_root`, job notice) and new doc text (threat-model bullet, §Versioning, §4.4–§4.5 one-liners, the job-notice docs). Nobody has shown the net size will be negative. If 100 KB is a hard limit, say what gets cut when it is exceeded. If it isn't, don't state it as a success condition.

- NEEDS-HUMAN — **The base history doesn't match, and the starting artifact isn't in the record.** The brief calls the stale base `pdca-integration/main-r2546dbf9639f = 2ddc3e8` and says v4 "was built on `2ddc3e8`". The issue says "NOT the stale `stack-base` `8c95e05` (C4 failed on it in v4 and v5)". Two different stale bases are named for v4. The brief's main instruction, "Start from `iteration-v4/patch.diff` in this bundle", depends on knowing what v4 was built on. Neither that file nor the brief's "does not apply at `v1.md:43`" claim can be checked from the inputs. Reconcile the two SHAs, so Do knows which hunks were already rebased.

- NEEDS-HUMAN — **Some citations can't be checked against the target, and some are off by one.**
  - The falsifiability claim cites `engine/scripts/run-verify.sh:138`, but there is no `engine/` in the target. It belongs to the harness, so the citation can't be checked against `c47c5c2`. Say so, or drop the line number.
  - Smaller: the "vectors note `:189-190`" is at `pty-protocol/v1.md:190-191`.
  - The "Known gaps (`:165`)" anchor in the threat model is the section heading at line 165; the list runs to `:180`.

I also tried to fault the success criteria for being unverifiable and could not. Every criterion is a pytest assertion with an explicit timeout, the either/or outcomes in (g) are still falsifiable, and the C4 revert shape (imports inside each test) is sound.

> **pdca:** Bash was unavailable to this reviewer. The vendor sandbox could not start on this host, so every Bash call it made failed before running (`apply-seccomp: write /proc/self/setgroups (nested userns is capability-restricted; caller must provide CAP_SYS_ADMIN): Permission denied`) and it ran no commands; this review was delivered without Bash.

<!-- pdca:leaf-complete -->

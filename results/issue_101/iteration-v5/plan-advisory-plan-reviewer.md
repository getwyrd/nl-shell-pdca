Bash was unavailable in this run (every command failed with `apply-seccomp: ... Permission denied`); this review used Read, Grep and Glob only.

# Plan advisory — plan-reviewer — issue 101 / persistent-bash-session-core

No `sources/` dir and no `dependency-state.json` were provided. The only inputs were `brief.md` and `notes.json` (the issue body, with no comments). Target read: `$PDCA_TARGET` worktree, HEAD `8c95e059f8b35506834bda1f71e45b5c9968b3c2`.

- NEEDS-HUMAN — **The target base does not match the brief.** The Ordering note says "`main` moved since v3 (now `c47c5c2`: #131/#132/#133 edited `pty-protocol/v1.md` §4.4–§4.5, §6.6 and Conformance 13–16, and the threat model). Build on current `main`". The resolved target is HEAD `8c95e05`, and its spec has none of those edits. `docs/design/specs/pty-protocol/v1.md` §4 stops at item 3 (`:98-109`), §6 stops at item 5 (`:120-133`), and the Conformance table stops at vector 12 (`:152-163`). The policy-gate citations also point to the wrong lines on this tree. The brief puts §3 session-altering at `:98-107`, but it is at `policy-gate/v1.md:92-101`. It puts the §7.5 `V` list at `:197-201`, but it is at `:191-195`; `:196-198` are items 6–7. Either the target was resolved to a stale commit, or the brief describes a `main` that doesn't exist. In both cases the docs edits and the "cite path:line on `main`" rule will drift during Do. Re-resolve the target to `c47c5c2`, or correct the brief, before Do starts.

- NEEDS-HUMAN — **Decision 6 contradicts an ADR, and the brief forbids editing ADRs.** Scope says "do NOT edit any ADR". `docs/design/adr/0014-pty-session-protocol.md:45-46` says a user `PROMPT_COMMAND` "is kept and run after nl-shell's hook". Decision 6 and test (m) require it to run BEFORE the snapshot. ADR-0014 is the normative source the brief tells Do to cite ("Decisions 1–3"). After this patch the spec and its decision record would disagree, and a Check reviewer could fairly fault either side. The brief should either allow a one-line ADR-0014 amendment or a superseding note, or name the follow-up that will make one.

- NEEDS-HUMAN — **What degraded mode means also conflicts with ADR-0014 and the issue.** The brief says "while degraded the session object sends NOTHING more to the PTY (it raises)", and the planned §4.3 edit says "a degraded session gets no further commands until restart". `adr/0014:53-54` says: "every command needs a confirm, and nl-shell offers to restart the session". `adr/0013-policy-gate-v2.md:73` says the same ("everything needs a confirm until the session is ..."), and so does `policy-gate/v1.md:196`. The issue body (notes.json) asks only for "degraded mode ... (sticky until restart)". This is a behavior change to two decision records and the gate spec, made without editing any of them. The brief's §4.3 edit leaves `policy-gate/v1.md:196` and both ADRs saying "confirm and run".

- NEEDS-HUMAN — **The issue thread now contradicts the brief, and the brief doesn't say which one wins.** `notes.json` still asks for the user's `PROMPT_COMMAND` to run "after nl-shell's hook" (its (h)) and specifies the `os.tcgetpgrp` back-at-a-prompt rule with "degraded within 3 s" and Ctrl-C "< 2 s". The brief reverses the first (decision 6), replaces the second (decision 7, `/proc/<pid>/syscall`), and loosens the timings to 5 s and < 3 s. The decisions are recorded as human, 2026-10-15, but the tracker record was never updated. A Check or sign-off reviewer who grades against issue #101 will find "regressions" that are actually agreed decisions. Update the issue body, or have the brief say explicitly that it supersedes the issue's criterion.

- NEEDS-HUMAN — **Scope is several mechanisms, not one change.** Besides the session object and record parser, the brief adds:
  1. A Linux `/proc/<pid>/syscall` blocked-on-fd-0 watcher (decision 7).
  2. Outside termios and `/proc/<pid>/fd` checks run before every paste and at every `E` (decision 8).
  3. A `dev.tty.legacy_tiocsti` startup probe.
  4. A `/proc` stopped-state check.
  5. A full readline-state hash (`bind -v`/`-p`/`-X`) in `H`.
  6. Edits to three docs: the spec in six sections, policy-gate §7.5, and the threat model.

  Each one is independent review surface. Three earlier rounds failed on breadth, not on the core ("The core worked every round"). Splitting off Table B (the outside checks, the TIOCSTI probe and the stopped-state check) as a stacked bundle would keep I1/I2/I3 on bash state testable on their own. If the human wants one bundle, the brief should say so explicitly; the split was not considered.

- NEEDS-HUMAN — **Some sub-criteria are defined by the implementation, so Do can make them pass by construction.**
  - (g) says "adjust the variable names to whatever the new hooks use". The reproducer depends on Do's own naming, so the test proves only what Do chose to attack.
  - (j) needs "the TIOCSTI setting the session reads at startup pointed (by the test) at a file". That requires a production injection seam (a configurable sysctl path or parameter) that the Goal and Scope never mention, so its API and safety are not specified.
  - (p) says "a confirmed change that stops readline's paste markers" without naming the change. Name the exact command(s), for example `bind 'set enable-bracketed-paste off'` and `set +o emacs`, so the test is fixed before Do starts.

- NEEDS-HUMAN — **A Conformance vector would be left stale.** `pty-protocol/v1.md:159` says vector 8 (`PROMPT_COMMAND=:`) is "degraded mode at the next prompt (missing `D`)". Under the new design it degrades through `H` at that command's own snapshot (test (h)). The Docs list edits §1.2, §3 and §4.1–§4.3 but not the Conformance table. The vectors 1–7 note at `:165-166` and the "Open questions" bullet at `:170-171` (forcing `enable-bracketed-paste on`) also need resolving, because (h) and (m) now answer that question.

- NEEDS-HUMAN — **The brief's evidence can't be checked from here.** The brief relies on `iteration-v3/SUMMARY.md` §6/§9, `deferred-findings.json`, `results/issue_10/brief.md:27-57` and follow-ups #134–#138 as "filed". None of these are in the inputs. Every reproducer in (g)–(k) is justified as "reproduced live against the v3 patch". The human should confirm at sign-off that the follow-up issues exist, because the threat-model Known-gap bullets must name them.

Parts I tried to fault and could not:
- The threat-model quotes match the target: "What the user confirms is exactly what runs" at `threat_model.md:118`, Critical "differs from the one the user confirmed" at `:186`, and Medium "doesn't enter degraded mode when its hooks were changed" at `:202`.
- The pty-protocol citations `:48`, `:94` and `:104-107` are correct.
- `conftest.py:52 isolated_environment` exists.
- `pyproject.toml` has no `ptyprocess` yet, which is consistent with the Scope.
- The falsifiability shape (imports inside each test, revert all non-`tests/` code) is sound.

> **pdca:** Bash was unavailable to this reviewer. The vendor sandbox could not start on this host, so every Bash call it made failed before running (`apply-seccomp: write /proc/self/setgroups (nested userns is capability-restricted; caller must provide CAP_SYS_ADMIN): Permission denied`) and it ran no commands; this review was delivered without Bash.

<!-- pdca:leaf-complete -->

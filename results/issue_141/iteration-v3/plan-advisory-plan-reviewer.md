Bash was unavailable in this run (sandbox failed to start: `apply-seccomp: ... Permission denied`); the review used Read, Grep and Glob only.

# Plan review: persistent-bash-session-tamper-checks

Inputs available: `brief.md` and `dependency-state.json`. **There is no `notes.json` and no `sources/` in the bundle**, so I could not check the problem statement against a tracker thread. Code claims below come from `$PDCA_TARGET` (`/tmp/pdca-plan-target-f0ljol7t/target`).

- NEEDS-HUMAN — **The base and the prerequisite are not built yet.** The brief says "build on child-1's accepted result (the wave-2 integration branch)", and `dependency-state.json` gives `"140": {"exists": true, "state": "PLANNED"}`. The target has no `src/nl_shell/session.py` and no `tests/test_session.py`; `src/nl_shell/` holds only `router.py, repl.py, input_modes.py, cli.py`. So these brief references all point at code that doesn't exist yet: the `path:line` citations ("fixes the v5 hole at `session.py:211`"), `HOOK_STATE_VARS`, "child-1's interim bullet" in the threat model, and `$PDCA_VERIFY_BASE`. Nothing in the bundle shows where `session.py:211` comes from. It looks like an earlier iteration's patch, not child-1's accepted result. Hold this bundle until #140 is accepted, then re-check every `session.py`/threat-model citation against the real base.

- NEEDS-HUMAN — **The grounding is outside the bundle and can't be checked.** The brief rests on "decisions 2, 6, 8, 12, 13", "Table A"/"Table B", "the parent brief's letters", `iteration-v3/SUMMARY.md` §6, `iteration-v5/SUMMARY.md` and `deferred-findings.json`. None of these is in the bundle or the target: a grep for `Table A|Table B|TIOCSTI|tiocsti|#135|#138` finds nothing. Neither I nor Do can confirm that the "closed list" matches what the maintainer decided. The same goes for whether the follow-up issues #134–#138 exist, since the Docs section requires each Known-gap bullet to name one. These sources should be attached, or the brief should restate the decisions it depends on.

- NEEDS-HUMAN — **The falsifiability claim is wrong for some (h) and (s) cases.** The brief says reverting this child leaves child-1 healthy, so each attack "fails on their attack". Two counter-cases:
  - (h) `exec </dev/null` makes interactive bash read EOF and exit. Child-1's existing exited/recovery path (spec `pty-protocol/v1` §4.4, `docs/design/specs/pty-protocol/v1.md:110-113`) already makes the next `run` raise. So that row passes on the red leg, and it doesn't exercise "the outside fd check" the brief attributes it to.
  - (s) `enable -n printf` (and likely `eval`/`builtin`) stops the hook writing `D`/`E` records at all (reference rcfile `v1.md:59-67` writes every record with `printf`). Child-1 already degrades on that through "a record is missing" (`v1.md:104`).

  The red leg still goes red overall, but these rows don't prove what they claim. Either assert the degrade *reason* (outside-check mismatch vs. missing record vs. exited), or drop the claim.

- NEEDS-HUMAN — **(m) and (p) may already pass on child-1, and (m) is a disjunction.** The brief puts "Table A rows … made harmless by decision 6" out of scope as child-1's work. But it also has this patch close the spec Open question on forcing `enable-bracketed-paste on` (`v1.md:195-196`) "by naming decision 6".
  - If child-1 already forces bracketed paste after `~/.bashrc`, then (m) ("either works … or starts degraded") and (p) are green on the red leg, which contradicts "(m)/(p) fail on their attack".
  - (m)'s "works OR degraded" can't fail for any implementation that degrades at startup.

  Decide which child owns decision 6. Then either make (m) assert one outcome, or stop listing it as red-leg evidence.

- NEEDS-HUMAN — **The scope is two mechanisms plus a large docs rewrite, not one fix.**
  - (A) In-bash `H` widening plus `HOOK_BUILTINS` plus `2>&1` on every substitution.
  - (B) A new outside-bash checker: PTY termios via the master, `/proc/<pid>/fd` 0/1/2, `/proc` stopped state, and a `tiocsti_path` sysctl read with a new constructor keyword, run both before every paste and at every `E`.

  These have different failure modes and different test needs: (j) and the `exec` rows depend only on (B), while (h), (r) and (s) depend on (A). The spec §3/§4.2 and threat-model Known-gaps rewrite (five follow-up bullets) adds more review surface. Consider splitting (B) and its (j) tests into a sibling child. If not, at least note that `difficulty: high` comes from bundling.

- NEEDS-HUMAN — **The brief needs a host capability it never uses.** "Needs `/proc/<pid>/syscall` … readable" appears in Falsifiability and as the `proc-syscall` external dependency. No in-scope item reads `syscall`: the stopped check uses `/proc` state `T`, and the fd check uses `/proc/<pid>/fd`. The only plausible user is "builtin-only commands over 1 s degrade, #136", which the brief puts out of scope. Either a hidden piece of #136 is coming in, or the dependency is stale. Settle which, because it also gates where the tests can run.

- NEEDS-HUMAN — **The new `H` overlaps the existing `B` record, and the docs edit doesn't address it.** Spec §3 (`v1.md:92`) already defines `B` (the `enable -n` output) as a snapshot field that is only reported. Folding builtin enable-state into `H`, which makes it degrade-on-change, changes what `B` means. The listed §3 edit ("`H` covers all Table A detect rows") should say so, or §3 and §4.2 will contradict each other on whether `enable -n` merely informs the gate or degrades the session.

- NEEDS-HUMAN — **The timed assertions are flaky gates.** "degraded within 5 s" in (j) `kill -STOP` and in (s) for every name in `HOOK_BUILTINS` (13+ fresh sessions) is a wall-clock check on a real-bash, real-PTY suite. That's fine locally but brittle under a loaded CI or verify host. Say whether 5 s is a hard spec number (it isn't in `v1.md` §4) or a test timeout, and whether the outside check polls or only runs at paste/`E`. "Within 5 s" with no paste and no `E` needs a poller the brief doesn't specify.

> **pdca:** Bash was unavailable to this reviewer. The vendor sandbox could not start on this host, so every Bash call it made failed before running (`apply-seccomp: write /proc/self/setgroups (nested userns is capability-restricted; caller must provide CAP_SYS_ADMIN): Permission denied`) and it ran no commands; this review was delivered without Bash.

<!-- pdca:leaf-complete -->

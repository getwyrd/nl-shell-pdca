# Security review (advisory): issue 77, teacher-client-dev-teacher-flag

Attacker-reachable inputs this diff touches: **none. The patch is empty** (`patch.diff` is 0 bytes).

There was no code to review. The threat model (`.oss-scanner/threat_model.md`) is present. It names the inputs this bundle *would* touch: item 11 (dev teacher endpoint, `.oss-scanner/threat_model.md:90`), item 8 (local model socket) and item 5 (model output). None of them is reached by a change, because there is no change.

What I checked:
- `patch.diff` is 0 bytes. The gate logs confirm this: `gate-logs/C4-verify.log` exits 77 with `PDCA-UNVERIFIABLE: bundle has no patch.diff`, and `gate-logs/T2-threat-model.log` says `no patch.diff, nothing to check`. T3 (`gate-logs/T3-suite.log`, 330 passed) ran the suite on an unchanged worktree, so it says nothing about this feature.
- The target worktree has no uncommitted diff against HEAD (`0771812 pdca-integrate: issue_140`). `src/nl_shell/` has no `teacher_client.py`, `backend.py`, `proposal.py`, `render.py` or `prompts.py`. So the prerequisite #143 is **not** folded into this base, and the brief says this bundle must not be built without it (brief, "Falsifiability" and "Depends on: 143").

Findings:

- NEEDS-HUMAN [human] — No patch, so the security review is unrated for this round (`src/nl_shell/cli.py:1`, no change). The brief's required properties have nothing behind them yet: no TCP connection without `--dev-teacher`, escaping of server text in error reasons (the OSC 52 reason-phrase case), the total-deadline timeout, and no redirect following. The likely cause is that #143 (backend interface, `proposal.SCHEMA`, `render.escape`) is missing from the wave base: none of those modules exists under `src/nl_shell/` in `$PDCA_TARGET`. A human or the driver needs to check whether #143 was accepted and folded before scheduling Do again. Another rebuild on this base cannot meet the brief. This is a scheduling and dependency problem, not a defect the builder can fix by iterating.

No security finding against code, because no code changed.

<!-- pdca:leaf-complete -->

# Advisory security review — issue 77 (teacher client, `--dev-teacher`)

Attacker-reachable inputs this diff touches: **none — `patch.diff` is empty (0 bytes)**, so no changed line reaches anything.

The threat model is present (`.oss-scanner/threat_model.md`) and was used as the rubric. The inputs this bundle is meant to touch are item 11 (the dev teacher endpoint, `threat_model.md:90`), item 8 (the local model socket), item 5 (model output), the "endpoint in config refused without `--dev-teacher`" rule (`threat_model.md:101`), and the must-hold "no outbound connection in the default config" (`threat_model.md:143`). None of them is changed by this round.

What I checked:
- `patch.diff` is 0 bytes. `gate-logs/C4-verify.log:10` reads `PDCA-UNVERIFIABLE: bundle has no patch.diff`. `gate-logs/T2-threat-model.log:10` passed only because there was nothing to check (`no patch.diff, nothing to check`). T3 (330 passed) ran against the unchanged tree.
- The target at `$PDCA_TARGET` has no teacher or HTTP client code: `src/nl_shell/` holds `cli.py, config.py, input_modes.py, os_release.py, pty_protocol.py, repl.py, router.py, session.py, targets.py`, and a search for `teacher` in `src/` finds nothing. The working tree is clean. So today the shell makes no model connection at all, and the default-config "no outbound connection" property holds trivially.
- So there is nothing to rate. No new path exists for a LAN peer or for a copied `config.toml` to send the state block off the host, and no model-output parsing was added that could be attacked.

Finding:
- NEEDS-HUMAN [human] — `patch.diff` (empty); `gate-logs/C4-verify.log:10`. This is the second round in a row with no submission: round 1 was sent back for exactly this ("an empty submission cannot establish the endpoint-safety or rejection guarantees", brief.md Iteration 1 carry-forward), and round 2 is empty again. None of the security properties the brief promises has been built or tested: refusing `teacher_url` without `--dev-teacher`, never following redirects, no TLS-to-plain-HTTP fallback, the 64 KiB size cap, the timeouts, rejecting non-`proposal/v1` content, and no `AF_INET`/`AF_INET6` connection on the default path. Someone needs to find out why the Do step produces no patch (harness, dependency wave base for #14/#16/#92, or a builder failure) before another auto-rebuild. Another iteration with the same setup is likely to come back empty too. When a real patch arrives, the security review has to be run again from scratch. The cases to test first are: a `config.toml` holding `teacher_url = "http://192.168.1.50:8080"` and no flag (the fake server must see zero requests); a 302 to a second listener (the second listener must see nothing); and `https://127.0.0.1:<port>` pointed at a plain-HTTP server (it must be rejected, with no plain request sent).

No other findings: there is no code to review.

<!-- pdca:leaf-complete -->

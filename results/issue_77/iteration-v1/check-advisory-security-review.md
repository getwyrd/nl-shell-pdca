# Security review (advisory) — issue 77 / teacher-client-dev-teacher-flag

Attacker-reachable inputs this diff touches: **none — there is no diff.** The bundle has no `patch.diff`, so nothing was reviewed.

## What I checked

- The scratch directory has `brief.md`, `check-gates.json` and `gate-logs/`, but no `patch.diff`.
- `gate-logs/C4-verify.log` ends with `PDCA-UNVERIFIABLE: bundle has no patch.diff` (exit 77). `gate-logs/T2-threat-model.log` passed only because there was nothing to check (`no patch.diff, nothing to check`). The T3 pass (330 tests) ran on an unchanged tree, so it says nothing about this issue.
- The target worktree at `$PDCA_TARGET` is clean (`git status` is empty; HEAD is `0771812 pdca-integrate: issue_140`). It has no teacher client, no `--dev-teacher` flag and no `tests/test_teacher_client.py`. `src/nl_shell/repl.py:27` still prints the placeholder "the model backend arrives in M0.8."
- The base also has none of #16's work (no backend interface, no `proposal/v1` parser or schema under `src/nl_shell`). The brief says this bundle builds on #16 and "if any is not accepted, this bundle is not scheduled." That missing dependency is the likely reason no patch exists.
- I read `.oss-scanner/threat_model.md`, which exists. The inputs this issue would affect are item 8 (the local model socket), item 11 (the dev teacher endpoint), item 5 (model output), and the must-hold rule "no outbound connection in the default config." With no code, none of them is touched, so there are no findings and no severity ratings.

## Findings

- NEEDS-HUMAN [human] — `gate-logs/C4-verify.log` (no `path:line`, because no code changed): the bundle reached Check with no `patch.diff`, so there was nothing to security-review. The wave base at `$PDCA_TARGET` (HEAD `0771812`) lacks #16's backend interface and `proposal/v1` schema, which the brief lists as a hard dependency. A human needs to decide whether to reschedule #77 after #16 lands, or find out why Do produced no patch. Treat this round's "pass" on T2 and T3 as meaningless for #77. When a real patch exists, it needs a fresh security pass. Focus on: redirects not followed, the body size cap actually stopping the read, no TLS fallback, no TCP connection without `--dev-teacher`, no `Authorization` header or credential sent, and model `content` treated as untrusted (threat model items 5, 8, 11).

No security findings against code: there is no code change to assess.

<!-- pdca:leaf-complete -->

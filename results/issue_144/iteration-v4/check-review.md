Review #144: replace the proposal/display character filter with pinned Unicode properties, named blank glyphs, a combining-mark cap, and the approved Highly Restrictive script policy.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | Latest sign-off resolves the policy choices and supersedes the earlier broader invariant and script rule; implemented scope matches those decisions (brief.md:47; target/.oss-scanner/threat_model.md:131). |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing the patch made both Egyptian blanks, Cyrillic/Latin curl, and three combining marks parse as Command; the frozen regression run reports 50 failures (target/tests/test_charsafety.py:123; gate-logs/C4-verify.log:14). |
| C3 Change | PASS | Changes stay within character policy, generated data, generator, tests and threat-model scope; parser rejection uses the shared policy (target/src/nl_shell/proposal.py:133). |
| C4 Verification (red→green) | PASS | Independent stash/pop probes changed four unsafe commands from accepted to rejected and preserved both approved Latin/Han commands; full pytest red/green is supported by the captured 50-fail/58-pass run, not independently rerun because pytest is absent here (gate-logs/C4-verify.log:10; target/tests/test_charsafety.py:123). |
| C5 Causal adequacy | PASS | Policy derives properties from pinned tables and rejects at parsing, addressing the old predicate's omissions without capability probes or fallback guards; independently regenerated tables are byte-identical using installed Unicode 16.0.0 data (target/src/nl_shell/render.py:105; target/scripts/gen_unicode_tables.py:150). |
| T1 Structure | PASS | One shared policy keeps display and parsing consistent; generator is build-only and introduces no runtime dependency (target/src/nl_shell/render.py:148; target/src/nl_shell/proposal.py:133). |
| T2 Shape | PASS | Independently inspected threat-model changes describe the exact hidden set, quoted rejection and known confusable gap; diff whitespace check passes; automated log only says no security-relevant path touched and supplies no substantive security assurance (target/.oss-scanner/threat_model.md:127; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Captured full-suite output shows 539 passing tests and one forkpty deprecation warning; local pytest rerun is unavailable because the module is missing (gate-logs/T3-suite.log:20). |
| T4 Contribution | N/A | Contribution artifacts are deliberately absent at Check; substantive audit is deferred to the mandatory publish rerun (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm prior-art coverage by affected file path across merged history and closed/rejected work — this self-contained target has only one base commit and no remotes, while the brief records string searches rather than a reproducible path-based closed-work audit (brief.md:25; target/src/nl_shell/render.py:1). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept this slice's documented residual exposure and confirm the #74 UI dependency before relying on end-to-end visual safety — #74 was not exercised; current evidence proves parser/display policy only, and same-script/Common confusables remain accepted by design (target/.oss-scanner/threat_model.md:184). |

Independent checks used the disposable target only. Stashing included untracked patch files; popping restored the original patch. Direct parser probes ran before stashing, against the base, and after restoration. Unicode-data was present and exercised by calling the generator in memory and comparing its output with the committed module; no generated source was rewritten. `git diff --check` passed. No stale-target caveat was needed.

Read all four frozen logs. C4's captured failures include actual unsafe proposal acceptance and raw context rendering, followed by a green patched run. T3's captured full suite includes the backend tests. The instance-root gate wrappers are not available here; their absence is not treated as a defect. No INTEGRATION.md was supplied in the bundle or target file inventory.

For the remaining visual dependency, once #74 is available, launch `python3 -m nl_shell` from the configured development environment, submit a stub proposal containing `ｃurl`, `𝐜url`, or `ⅽurl`, and verify the confirmation displays explicit non-ASCII escapes before execution can be approved. This is the already documented dependency, not a request to reopen the approved policy choices.

<!-- pdca:leaf-complete -->

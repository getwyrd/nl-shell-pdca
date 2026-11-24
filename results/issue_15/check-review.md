Review issue #15: add the M0 heuristic command-versus-natural-language router while preserving the non-executing REPL and exit handling.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The bounded placeholder has explicit routing examples, exclusions, and observable replies; the tests cover the required examples (brief.md:15; target/tests/test_repl.py:87). |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing production changes reproduced the undifferentiated reply: all ten route assertions failed without import errors (review-red.log:1; target/tests/test_repl.py:107). |
| C3 Change | PASS | The change stays within the router, REPL, tests, and architecture inventory; exit handling precedes routing and nothing executes (target/src/nl_shell/repl.py:57; target/src/nl_shell/router.py:56). |
| C4 Verification (red→green) | PASS | Independent ten-case REPL probe changed from 10 failures to 10 passes after restoring production; frozen pytest evidence additionally shows 14/19 failing pre-fix and 19/19 passing post-fix (review-red.log:11; review-green.log:11; gate-logs/C4-verify.log:10). |
| C5 Causal adequacy | PASS | Classification resolves the missing routing behavior directly; PATH lookup occurs per call, and malformed-quote recovery handles allowed input rather than masking an eager capability dependency (target/src/nl_shell/router.py:38; target/src/nl_shell/router.py:56; target/tests/test_repl.py:117). |
| T1 Structure | PASS | The standalone router has no REPL dependency and remains reusable as the later classifier fallback (target/src/nl_shell/router.py:15; target/src/nl_shell/repl.py:15). |
| T2 Shape | PASS | The small enum-based interface and explicit reply mapping fit this scoped addition; independent git diff --check passed (target/src/nl_shell/router.py:21; target/src/nl_shell/repl.py:27). |
| T3 Runtime | PASS | The frozen full-suite log records 21 passing tests; the independent probe also passes, but pytest itself is unavailable in this reviewer sandbox (gate-logs/T3-suite.log:10; review-green.log:11). |
| T4 Contribution | N/A | Contribution artifacts are drafted after Check; the captured deferred result assigns the substantive audit to the mandatory publish rerun (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm the affected-path prior-art check against merged and closed/rejected work, including the architecture document — the brief reports a check for three code/test paths, but this synthetic one-commit target has no remote or PR evidence to independently establish completeness (brief.md:26; target/docs/design/architecture/05-building-block-view.md:75). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the placeholder's deliberate English/command ambiguity and route-message wording for M0 — required examples pass, but usefulness and tolerance of cases such as “find large files in my home” remain product judgments (target/tests/test_repl.py:94; target/src/nl_shell/repl.py:19). |

Evidence and limits: Source citations were checked in the supplied target; it is readable and contains the patch. Production changes were stashed for the independent red probe and restored afterward, leaving the original patch intact. The probe uses real executable-file permission checks in a controlled PATH, as the specification requires; it does not substitute an external service or tool. Its assertions identify routes and do not replace the frozen pytest tests' exact-message checks. No external dependency is declared or left undischarged by the captured gates. The reviewer sandbox's missing pytest limits local suite reproduction, not the recorded gate result. Instance-scoped wrapper scripts were adjudicated from their captured logs. No INTEGRATION.md was present in the supplied target.

Prior-art investigation: git log --all restricted to the three code/test paths returned only synthetic base commit 7a54cd6; git remote -v returned no remotes. The brief records merged-history and closed-unmerged checks, but supplies no independently inspectable PR evidence and omits the changed architecture path from its path list.

<!-- pdca:leaf-complete -->

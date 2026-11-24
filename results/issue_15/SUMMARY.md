# Result — issue 15 / heuristic-nl-vs-command-router

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: (gap, not a bug) nl-shell has no input router. Every non-empty, non-exit line gets the same reply, `NOT_YET` (`src/nl_shell/repl.py:15`, printed at `src/nl_shell/repl.py:47`), whether the user typed a shell command (`ls -la`) or a natural-language request (`show disk usage`). Issue #15 asks for the M0 placeholder router: if the first token of the input is an executable found on `$PATH` or a bash builtin, the input is a **command**; otherwise it is **natural language**.
- Success criterion: `python3 -m pytest tests/test_repl.py` passes, and it contains a table-driven test that feeds each input below through `Repl` (the scripted read function already in that file) with `$PATH` pointed at a temporary directory holding fake executables `ls`, `git` and `find` only, and asserts that the REPL's reply for that line identifies the route shown. The two replies must be distinct, fixed strings (one for each route), each still telling the user that nothing runs yet and which milestone brings it (bash session: M0.2; model backend: M0.8). Table: `ls -la` → command · `git status` → command · `find large files in my home` → command (known heuristic limitation, pinned on purpose) · `cd /tmp` → command (builtin) · `export FOO=1` → command (builtin) · `  ls` (leading spaces) → command · `show disk usage` → natural language · `what's using port 80` → natural language, and the REPL must not raise (unbalanced quote) · `frobnicate the widgets` → natural language · a path to an executable file created in the temp dir (e.g. `<tmp>/build.sh`) → command. Also: `:quit` / `:exit` still end the loop before any routing, and blank lines still print nothing (the existing tests keep passing, updated only where they assert the old `NOT_YET` reply).
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: Add the heuristic router as its own small module under `src/nl_shell/` (its own unit, so #40 can keep it as the classifier's fallback without touching the REPL), and have `Repl.run` route each non-empty, non-exit line through it and print the route-specific reply instead of the single `NOT_YET` line. Routing rule, exactly as the issue states: first token is an executable on `$PATH` (read at call time, not cached at import) or a bash builtin → command; anything else → natural language. The first token must be found without raising on input that is not valid shell quoting. A first token that contains `/` counts as a command if it names an executable file. Update the existing tests in `tests/test_repl.py` that assert the old `NOT_YET` reply, and add the module to the code-layout table in `docs/design/architecture/05-building-block-view.md` §5.3 (it is a living doc that lists modules as M0 lands). / out of scope: prefix modes and meta-commands (`\`, `?`, `@`, `@@`, `:context` … — #14); actually running anything (PTY, #10) or calling a model (#16); the trained classifier (#40); bash keywords (`if`, `for`, `while` — they collide with English and the issue names builtins only); leading env assignments (`FOO=1 make`) and aliases/functions from the user's shell — the heuristic is a placeholder, M3 replaces it; any change to `cli.py`.

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: likely-fix
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (14 of 19 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 Shape: none — (no gate configured)
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

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

### Advisory — security-review

# Security review (advisory) — issue 15 / heuristic-nl-vs-command-router

Attacker-reachable inputs this diff touches: **none**. The only input to the new code is the line the user types at the REPL, and the threat model lists "what the user types at the REPL" and "paths the user typed" as trusted (`.oss-scanner/threat_model.md`, "Where untrusted input enters", last paragraph). Nothing runs yet: both routes end in a fixed print at `src/nl_shell/repl.py:62`, so there is no gate, PTY or model to get past.

## What I checked

- **Where the routed line goes.** `route(text)` (`src/nl_shell/router.py:57-67`) returns an enum, and the REPL only uses it to pick one of two fixed strings (`src/nl_shell/repl.py:27-30`, `:62`). No user text is echoed, logged, passed to a shell or put in model context. So no escape-sequence, injection or secret-leak path exists.
- **Crashes and hangs from odd input.** `first_token` (`src/nl_shell/router.py:39-48`) catches the `ValueError` that `shlex` raises on an unbalanced quote and falls back to `str.split`. `shlex` with `whitespace_split` reads one token and stops, or, with an open quote, scans to the end of the line once. Both are linear in the line length. Inputs I traced: `what's using port 80` (covered by the test), a lone `"`, `\` (trailing escape, which also raises `ValueError` and is caught), and `''` (gives an empty token, so the result is natural language). None of them raises or loops.
- **File-system probing.** `is_executable_file` (`src/nl_shell/router.py:51-54`) calls `expanduser`, `isfile` and `os.access` on a first token that contains `/`. That path comes from the user, which is trusted, and the code only checks the file; it never opens or runs it. `shutil.which` (`:65`) reads `$PATH` from the user's own environment.
- **Wrong route.** The threat model rates this **Low** and says it does not matter much ("a wrong route still goes through the gate"). The known misroute (`find large files in my home` → command) is intended and pinned by the test.
- **Tests.** No security-relevant fix here, so a friendly-path-only test is fine. The test still covers the one robustness case that matters (unbalanced quote must not raise, `tests/test_repl.py`, the `what's using port 80` row). C4 log: red 14/19 without the fix, green with it. T3: 21 passed.

## Findings

No findings. The patch adds no attacker-reachable path and leaves no "What must hold" property weaker.

## Notes for later milestones (not findings, nothing to fix in this diff)

- When `$PATH` contains `.` or an empty entry, `shutil.which` also matches executables in the cwd. File names in the cwd are untrusted (threat-model item 2), so a cloned repo could ship an executable named `show` and send `show disk usage` down the command route. Today that only changes which fixed string prints. It is a Low misroute, and only with a PATH setup the user chose. It becomes worth a look when #10 (PTY) wires the command route to real execution. That wiring must send the command route through the policy gate and must not run "command" input directly. This patch does not do or block that, so I am not tagging it.
- In the `except ValueError` branch (`src/nl_shell/router.py:44-47`), the first token comes from `str.split`, not from how bash would parse the line. That is fine for picking a route. Later code must not reuse `first_token` to decide what runs or how a command is classed. The gate parses the AST for that.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] T5 Judgment — Confirm the affected-path prior-art check against merged and closed/rejected work, including the architecture document — the brief reports a check for three code/test paths, but this synthetic one-commit target has no remote or PR evidence to independently establish completeness (brief.md:26; target/docs/design/architecture/05-building-block-view.md:75).
- [x] Validation — fitness-to-purpose — Accept the placeholder's deliberate English/command ambiguity and route-message wording for M0 — required examples pass, but usefulness and tolerance of cases such as “find large files in my home” remain product judgments (target/tests/test_repl.py:94; target/src/nl_shell/repl.py:19).

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: merged-wider
- Iteration delta (if iterating):
- By / date: Eduard Ralph / 2026-10-14

## 10. Act candidates (hints for the next Act review)
- (empty is the common case)

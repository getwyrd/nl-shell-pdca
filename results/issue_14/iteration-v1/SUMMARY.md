# Result — issue 14 / input-mode-prefix-dispatch

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: The REPL recognises the input-mode prefixes before the heuristic router runs: `\cmd` is routed as a shell command whatever the router would say, `?question` goes to ask mode, `@request` to a one-command proposal, `@@goal` to the (not yet built) agent loop, and `:name` to a meta-command (`:context`, `:history`, `:status`, plus the existing `:quit` / `:exit`). Each route prints its own fixed reply, since nothing behind them exists yet except `:status`.
- Success criterion: `python3 -m pytest tests/test_input_modes.py` passes, and that file contains a table-driven test that feeds each line below through `Repl` (scripted read function, `$PATH` pointed at a temp dir holding only fake `ls`, `git`, `find`) and asserts the reply. Every reply named here is a fixed string, distinct from the other routes' replies, pinned as a literal in the test: `\frobnicate the widgets` → the existing shell-command reply (`COMMAND_NOT_YET`, `src/nl_shell/repl.py:19-22`), although the router alone says natural language · `\ls -la` → shell-command reply · `?why did that fail` → ask-mode reply · `@show disk usage` → one-command-proposal reply · `@@clean up my downloads` → the `@@` reserved reply (says it arrives with M0.6b, #76), and it is NOT the `@` reply · `:context` → reply saying it arrives with M0.8 (#16) · `:history` → reply saying it arrives with M0.9 (#17) · `:status` → prints a status block that includes the line `nl-shell <version>` (`nl_shell.__version__`) · extension point (separate test, imports the new module *inside* the test function): appending a zero-argument callable that returns `"extra: yes"` to the status-line list (see Design) makes `:status` print `extra: yes` after the version line, with no other change · `:frobnicate` → an "unknown meta-command" reply that lists the known ones, and nothing is routed · a prefix with nothing after it (`\`, `?`, `@`, `@@`, `:`) → a short usage reply for that prefix, nothing routed. Also: `:quit` / `:exit` still end the loop; plain input with no prefix still routes exactly as today (`ls -la` → command, `show disk usage` → natural language).
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: Prefix dispatch for one input line, checked after the exit commands and blank-line handling and before the heuristic router (`src/nl_shell/repl.py:57-62`). Rules: the prefix is the first character(s) of the stripped line; `@@` is checked before `@`; the text after the prefix (stripped) is the payload; `\` forces the command route and passes the payload on as the command text (ADR-0013 §7: it skips the classifier only, it does not skip the gate — say so in a comment that cites #64 / ADR-0013 §7 (Proposed), since #78 wires the gate); `?` → ask route; `@` → one-command proposal route; `@@` → reserved: one fixed reply naming #76, nothing else (needed only so `@@goal` does not fall into the `@` route with payload `@goal`; #76 owns the `@@` grammar and replaces this reply — this is a decision against the thread's "without `@@`", stated here on purpose); `:` → meta-command lookup by exact name (case-sensitive), with `:quit` / `:exit` handled as today. A prefix always wins over the router, even when the line would also be valid bash (`?x` is a bash glob; `\ls` is valid bash) — `docs/plan.md` §Input Modes defines the prefixes as explicit overrides. `:status` is a real meta-command that prints a block of status lines; build it so later issues can add lines to it (#92: active target; #16: prompt files loaded; #77: endpoint and backend — ADR-0020 §4) without rewriting it. Keep the dispatch a separate unit from `nl_shell.router` (the router stays the plain-input heuristic that #40 replaces). Replace `COMMAND_NOT_YET`'s and `NATURAL_LANGUAGE_NOT_YET`'s role only where needed: plain-input replies stay byte-identical, so `tests/test_repl.py` keeps passing unchanged. / out of scope: running anything (PTY #10, gate #12, orchestration #78); calling a model for `?`, `@` or natural language (#16, #77); the `@@` loop itself (#76); what `:context` and `:history` show (#16, #17); fix-on-failure and `?why` using the failure classes (#17, #62); the architecture doc 05 code-layout table (one docs pass after this batch, so six bundles don't edit the same table line); any change to `cli.py`.

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (15 of 21 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — no security-relevant path touched
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review issue #14: add explicit REPL prefix dispatch, placeholder mode replies, and extensible `:status` output while preserving plain-input routing.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The bounded placeholder feature has falsifiable reply, precedence, and extension-point criteria; no external service is required (brief.md:19, brief.md:24, brief.md:26). |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence shows 15 failures and 6 passes with production changes reverted, including actual wrong-reply assertions rather than a collection failure (gate-logs/C4-verify.log:14, gate-logs/C4-verify.log:601; target/tests/test_input_modes.py:134). |
| C3 Change | PASS | The three-file patch stays within dispatch, REPL integration, and regression tests; execution and model integration remain outside this change (patch.diff:1, patch.diff:141, patch.diff:188; target/src/nl_shell/repl.py:69). |
| C4 Verification (red→green) | PASS | Frozen C4 output establishes 21 passing feature tests after the fix and 15 failing before it; independent pytest reproduction was attempted but this host lacks pytest, so this verdict rests on captured gate evidence (gate-logs/C4-verify.log:10, gate-logs/C4-verify.log:601; review-red.log:4, review-green.log:4). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Honor the specified stripped payload for meta-commands and add a whitespace regression: directly exercising `: status` returns unknown instead of the status block because the parser exempts `:` from stripping (brief.md:24; target/src/nl_shell/input_modes.py:62; target/tests/test_input_modes.py:105). |
| T1 Structure | PASS | Explicit dispatch is separate from the replaceable heuristic router, and status contributors have a callable-list extension point exercised by a regression test (target/src/nl_shell/repl.py:69; target/src/nl_shell/input_modes.py:69; target/tests/test_input_modes.py:145). |
| T2 Shape | PASS | The frozen threat-model check reports no security-relevant path touched; source review confirms fixed replies and status callbacks introduce no command execution or model boundary (gate-logs/T2-threat-model.log:10; target/src/nl_shell/repl.py:72; target/src/nl_shell/input_modes.py:119). |
| T3 Runtime | PASS | The frozen suite output records 169 passing tests; direct local REPL exercise confirms status, ask, reserved-agent, forced-command, exact-name rejection, and exit behavior, with the whitespace defect reported under C5 (gate-logs/T3-suite.log:14; target/src/nl_shell/repl.py:49). |
| T4 Contribution | N/A | Contribution artifacts are intentionally absent at Check; the substantive contribution audit must run at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm prior-art coverage of all affected paths against merged history and closed/rejected work — the brief records a path-based check for repl/router, but the supplied target has only one synthetic base commit, no remote, and no independently inspectable closed-PR evidence for the new module/test paths (brief.md:29; patch.diff:1; patch.diff:188). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the user-facing placeholder behavior and reserved `@@` scope for this milestone — automated reply checks cannot decide whether these messages and the status extension contract meet the intended product experience (brief.md:19; target/src/nl_shell/input_modes.py:78; target/src/nl_shell/input_modes.py:89). |

Independent checks and limits:

- The supplied target is readable and contains the patch. I stashed only the production changes, attempted the red test run, restored the stash, and attempted the full green suite. Both invocations reported `/usr/bin/python3: No module named pytest`; the original patch was restored. This is a reviewer-host limitation, not a patch failure or evidence of an unmet product dependency.
- I read all four frozen gate logs. The C4 red leg contains 14 assertion failures plus one function-local import failure for the absent new module; tests collect and execute. Its red result therefore does not depend solely on that import failure. The instance-scoped scanner wrappers are not available in the target; their frozen output is the basis for the scanner verdict.
- Using the actual patched source through `PYTHONPATH=target/src`, I drove `Repl` with scripted input: `:status` produced `nl-shell 0.0.0`; `: status` produced `Unknown meta-command : status...`; `:statusx` and `:STATUS` remained unknown; padded ask input, `@@goal`, forced command input, and `:quit` produced their expected route replies. The C5 issue is a demonstrated payload-normalization mismatch, not a hypothetical runtime concern. No capability-probe symptom guard was added.
- The prior-art investigation returned only synthetic base commit `5433311` for affected-path history and no remotes. No `INTEGRATION.md` is present in the supplied target or input bundle, so additional project-specific human-only requirements could not be inspected. No other checkout was consulted.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 14 / input-mode-prefix-dispatch

I tried to break the evidence, the fix and the verdict. I could not refute the fix. The red→green proof is real. There is one test-design weakness worth sending back, and two minor notes.

## Evidence (red→green)

- Attempted: the red leg passing for the wrong reason. `gate-logs/C4-verify.log:601-603` shows 15 of 21 failing on the reverted tree. They fail on assertion mismatches (each prefixed line gets the natural-language reply), not on a collection error: "import/collection errors 0". The extension test fails with `ImportError` inside the function body (`tests/test_input_modes.py:147`), which is how the brief asked for it. The 6 rows that pass on `main` are the ones the brief predicted (`\ls -la`, bare `:`, the two plain-input rows, the two exit-command tests) plus `test_replies_are_distinct`. Green: 21 passed (`C4-verify.log:12`). The full suite is green, 169 passed (`gate-logs/T3-suite.log:14`). I could not re-run pytest myself because the sandbox has no `pytest` module. The frozen logs are consistent, so this does not count against the fix.
- Attempted: a test that mirrors production instead of exercising it. Every row goes through `Repl(...).run()` (`tests/test_input_modes.py:76-79`), which reaches `Repl._reply` at `src/nl_shell/repl.py:64-77`. The replies are pinned as literals and not imported, so a wrong constant in production would fail the test. Not refuted.
- Attempted: mutation of the `@@`-before-`@` order (`src/nl_shell/input_modes.py:45-51`). If `@` came first, `@@clean…` would get the PROPOSE reply and bare `@@` would too. Both rows (`tests/test_input_modes.py:111,120`) would go red. Not refuted.

## Fix (edge inputs probed against `input_modes.parse` / `reply`)

- `: > f` (the bash truncate idiom) now gets "Unknown meta-command : > f." when on `main` it routed as a command through the `:` builtin. `??x`, `::status`, `:Status` and `@ @x` all go where the brief's rules send them. All of this matches the brief's "a prefix always wins" rule (`src/nl_shell/input_modes.py:54-63`). It is a design choice, not a defect.
- `src/nl_shell/input_modes.py:118-134`: `input_modes.reply(Prefixed(Mode.COMMAND, "ls"))` raises `KeyError` (I confirmed this by calling it). The REPL never makes this call, because `repl.py:72-76` handles `\cmd` first, and the docstring warns about it. #78 wires `\cmd` to the gate, and anyone who calls `reply` straight from that code gets a crash. This is a minor API sharp edge, not a current bug, so it is not tagged.

## Verdict / test design

- NEEDS-HUMAN [impl] — `tests/test_input_modes.py:28,114`: the `:status` table row asserts that the *whole* output equals `"nl-shell 0.0.0\n"`. The brief's criterion says only that the block "includes the line `nl-shell <version>`", and the whole point of `STATUS_LINES` (`src/nl_shell/input_modes.py:68-70`) is that #92, #16 and #77 append lines "and change nothing else". Concrete failing case: the moment #92 appends its active-target line, `test_prefix_dispatch[:status-status]` goes red. A version bump in `src/nl_shell/__init__.py:3` does the same. So the extension point can't actually be used "with no other change", which the brief and the `STATUS_LINES` comment both promise. Fix: in the table, check only that the first line of the `:status` output is the version line, or drop the `:status` row from the exact-match table. `test_status_prints_the_version_line` (`tests/test_input_modes.py:137-142`) already checks the version line in a way that won't break when lines are added. Keep a red-on-`main` row for `:status`; that test still gives one.
- The rest of the reviewer's verdict looks warranted. I found no claim in `check-gates.json` that the logs don't back up.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory) — issue 14 / input-mode-prefix-dispatch

**Attacker-reachable inputs this diff touches: none.** The only input is the line the user types at the REPL (`src/nl_shell/repl.py:53-64`). The threat model lists "what the user types" as trusted (`.oss-scanner/threat_model.md`, "Trusted"). Nothing in the patch runs a command, reads command output, file contents, env values, history or model output (untrusted inputs 1–11). It only picks one of several fixed reply strings.

What I checked, and found nothing:

- **`\cmd` and the gate.** `src/nl_shell/repl.py:72-76` sends a non-empty `\` payload to the existing fixed command reply. Nothing runs, so no confirm can be skipped. The comment at `repl.py:73-75` keeps the ADR-0013 §7 rule visible for #78: `\` skips the router only, never the policy gate. The threat model ranks the router/classifier as lower priority because a wrong route still goes through the gate, and that still holds. No finding.
- **What is shown vs. what runs.** `src/nl_shell/input_modes.py:62` strips the `\` payload (`\  ls ` becomes `ls`). Nothing is shown to confirm or run yet, so the "confirm == runs, byte for byte" rule can't break here. When #78 wires the gate, the confirm UI must render from the same string the PTY receives. That belongs to #78, not this diff.
- **Echoed input.** `input_modes.py:130` echoes an unknown `:name` back to the screen as typed, including any control or escape characters. That text comes from the user's own keyboard or paste, which the threat model trusts, so this is not a spoofing path today. The output-filter rule applies to `:context` / `:history` content, which this patch leaves as fixed placeholders.
- **`:status` extension point.** `input_modes.py:69` is a module-level list of in-process callables. Only code inside nl-shell can append to it, and code running as the user is out of scope. `:status` prints only `nl-shell <version>` today, so no secret or env value reaches the screen. Later appenders (#92, #16, #77) should keep endpoint, token and env values filtered. That is for those issues to review.
- **Crash or hang from input.** `parse` (`input_modes.py:53-63`) is a fixed loop over five `startswith` checks. `reply` (`input_modes.py:119-134`) does dict lookups on keys that always exist for the modes it can receive (`USAGE` and `REPLIES` cover ASK/PROPOSE/AGENT, plus COMMAND with an empty payload). No regex, no recursion, nothing that grows with input size.
- **Test coverage.** The patch makes no security-relevant change, so friendly-path-only tests are not a finding. The T3 suite passed (169 passed, `gate-logs/T3-suite.log`). T2 reports no security-relevant path touched, which matches what I found.

No findings. No NEEDS-HUMAN items.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C5 Causal adequacy — Honor the specified stripped payload for meta-commands and add a whitespace regression: directly exercising `: status` returns unknown instead of the status block because the parser exempts `:` from stripping (brief.md:24; target/src/nl_shell/input_modes.py:62; target/tests/test_input_modes.py:105).
- [ ] T5 Judgment — Confirm prior-art coverage of all affected paths against merged history and closed/rejected work — the brief records a path-based check for repl/router, but the supplied target has only one synthetic base commit, no remote, and no independently inspectable closed-PR evidence for the new module/test paths (brief.md:29; patch.diff:1; patch.diff:188).
- [ ] Validation — fitness-to-purpose — Accept the user-facing placeholder behavior and reserved `@@` scope for this milestone — automated reply checks cannot decide whether these messages and the status extension contract meet the intended product experience (brief.md:19; target/src/nl_shell/input_modes.py:78; target/src/nl_shell/input_modes.py:89).
- [ ] `tests/test_input_modes.py:28,114`: the `:status` table row asserts that the *whole* output equals `"nl-shell 0.0.0\n"`. The brief's criterion says only that the block "includes the line `nl-shell <version>`", and the whole point of `STATUS_LINES` (`src/nl_shell/input_modes.py:68-70`) is that #92, #16 and #77 append lines "and change nothing else". Concrete failing case: the moment #92 appends its active-target line, `test_prefix_dispatch[:status-status]` goes red. A version bump in `src/nl_shell/__init__.py:3` does the same. So the extension point can't actually be used "with no other change", which the brief and the `STATUS_LINES` comment both promise. Fix: in the table, check only that the first line of the `:status` output is the version line, or drop the `:status` row from the exact-match table. `test_status_prints_the_version_line` (`tests/test_input_modes.py:137-142`) already checks the version line in a way that won't break when lines are added. Keep a red-on-`main` row for `:status`; that test still gives one.
- [ ] **The brief brings back the `@@` scope that the design review removed.** The issue title is "M0.6 — Input modes and meta-commands (without @@)", and the thread says: "**Split.** The `@@` agent loop moved to #76. This issue keeps `\`, `?`, `@` and `:` dispatch." The brief's own header agrees ("`@@` moved to #76", brief.md:8–9). But the Goal (brief.md:17), the Scope ("`@@` is checked before `@`; … `@@` → agent-loop route (placeholder only)", brief.md:23), the Design section and the Success criterion all add an `@@` route with its own reply, a test row (`@@clean up my downloads` → agent-loop reply, "NOT the `@` reply") and a bare-`@@` usage reply. That means this issue sets the `@@` grammar and reply wording that #76 owns. There is a real technical reason to touch `@@` here: without it, `@@goal` would fall into the `@` route with the payload `@goal`. Still, the planner should do one of two things. Either say explicitly that #14 only *reserves* `@@` (the smallest possible stub, recorded as a decision against the thread), or drop the `@@` route and test rows and leave `@@…` to the `@` route or the unknown handling until #76. Right now the brief contradicts the tracker without saying so.
- [ ] **The brief treats a question the thread leaves open as settled, citing a *Proposed* ADR.** The thread says: "Whether `\cmd` goes through the gate is decided in #64." The brief instead says the question is settled by "ADR-0013 §7" and asks Do to put that in a code comment (brief.md:5–6, 23, 54). ADR-0013 is `status: Proposed` (docs/design/adr/0013-policy-gate-v2.md:4), not Accepted. §7 says what the brief says (adr/0013:82–84), but the brief never mentions #64 or confirms that #64 closed on that ADR. Behaviour is not affected, because nothing runs yet. The comment Do is told to write would still state an unratified decision as fact. Fix: cite #64 / ADR-0013 (Proposed), or word the comment as provisional.
- [ ] **Part of the Scope cannot be checked.** "`:status` … build it so later issues can add lines to it (#92, #16, #77) … without rewriting it" (brief.md:23; Design: "its lines come from a list that later issues extend"). No test or gate covers this. The criterion only checks that a line `nl-shell <version>` appears. #92, #16 and #77 all depend on this extension point, so if it matters it needs something a reviewer can check: either a test that appends a line provider and sees it printed (using only names that exist on `main` would rule this out, so it would be a green-only test), or an explicit API named in the brief (e.g. "a module-level list of zero-argument callables in `repl.py`"). Otherwise Check can only judge it by feel.
- [ ] **Some table rows already pass on `main`. The red leg holds, but not because of the rows the brief points to.** On `main`, `\ls -la` gives the token `ls` (`shlex` posix mode drops the backslash, src/nl_shell/router.py:40–48) and so prints `COMMAND_NOT_YET`. A bare `:` hits the `:` builtin (router.py:29) and also prints the command reply. A bare `\` gives an empty or odd token. So the `\ls -la` row passes on `main` as written. The Falsifiability line (brief.md:19) is still correct overall: `\frobnicate the widgets`, `?why…`, `:status` and `:frobnicate` all route as natural language on `main` and will fail. This is a note for Do and Check, not a blocker: the red evidence should come from those rows, and nobody should read the `\ls -la` row as proof the prefix handling works.
- [ ] **Open question with no default in the criterion.** The Open questions section asks whether a bare prefix should print usage or be ignored (brief.md:64), but the Success criterion already requires a usage reply for each bare prefix (brief.md:18). Either close the question, or tell Do that the criterion wins until the human decides. Otherwise sign-off may reopen tests that Do already pinned.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: iterated-to-Do
- Iteration delta (if iterating): Auto-iterate (round 1): rebuilding for the implementation-level findings — C5 Causal adequacy — Honor the specified stripped payload for meta-commands and add a whitespace regression: directly exercising `: status` returns unknown instead of the status block because the parser exempts `:` from stripping (brief.md:24; target/src/nl_shell/input_modes.py:62; target/tests/test_input_modes.py:105).; `tests/test_input_modes.py:28,114`: the `:status` table row asserts that the *whole* output equals `"nl-shell 0.0.0\n"`. The brief's criterion says only that the block "includes the line `nl-shell <version>`", and the whole point of `STATUS_LINES` (`src/nl_shell/input_modes.py:68-70`) is that #92, #16 and #77 append lines "and change nothing else". Concrete failing case: the moment #92 appends its active-target line, `test_prefix_dispatch[:status-status]` goes red. A version bump in `src/nl_shell/__init__.py:3` does the same. So the extension point can't actually be used "with no other change", which the brief and the `STATUS_LINES` comment both promise. Fix: in the table, check only that the first line of the `:status` output is the version line, or drop the `:status` row from the exact-match table. `test_status_prints_the_version_line` (`tests/test_input_modes.py:137-142`) already checks the version line in a way that won't break when lines are added. Keep a red-on-`main` row for `:status`; that test still gives one.. Deferred, not addressed here: 6 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- By / date: auto-iterate / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 5 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

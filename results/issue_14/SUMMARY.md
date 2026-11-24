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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (23 of 29 failed), green with it
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

Review input-mode prefix dispatch for issue #14: explicit routes, extensible status output, usage replies, and consistent whitespace handling for meta-command exits.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The criterion defines observable prefix precedence, placeholders, status extensibility, and unchanged plain-input behavior; execution and model integration are explicitly outside this milestone (brief.md:19; target/src/nl_shell/repl.py:5). |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing production changes produced 16 failing smoke checks; frozen pytest evidence shows 23 failures among 29 collected tests, including incorrect forced-command and meta-command replies (review-smoke-red.log:1; gate-logs/C4-verify.log:14; target/tests/test_input_modes.py:115). |
| C3 Change | PASS | The three affected files stay within prefix dispatch and its regression coverage; plain-input fallback remains intact and no execution capability is introduced (target/src/nl_shell/repl.py:69; target/src/nl_shell/input_modes.py:55; target/tests/test_input_modes.py:111). |
| C4 Verification (red→green) | PASS | Independent production stash/restore smoke checks go from 16 failures to zero; the frozen gate records 29/29 green and 23/29 red. Local pytest reruns cannot start because pytest is absent, so full test verification rests on that captured gate output (review-smoke-green.log:23; gate-logs/C4-verify.log:10; target/tests/test_input_modes.py:145). |
| C5 Causal adequacy | PASS | Dispatch before the heuristic resolves the missing override behavior directly; shared payload parsing also resolves spaced exits, without a capability probe or symptom guard (target/src/nl_shell/repl.py:62; target/src/nl_shell/repl.py:69; target/src/nl_shell/input_modes.py:67). |
| T1 Structure | PASS | Explicit dispatch is separate from the replaceable heuristic, and status providers can be extended without editing the REPL or exact-output assertions (target/src/nl_shell/input_modes.py:80; target/tests/test_input_modes.py:148; target/tests/test_input_modes.py:164). |
| T2 Shape | PASS | No new dependency or execution sink appears; forced commands remain inert replies. The frozen threat-model gate reports no security-relevant path touched, and independent diff whitespace validation passes (target/src/nl_shell/repl.py:72; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen suite output records 177 passing tests; independent smoke checks exercise the REPL successfully, including spaced exits and appended status output. The local full-suite attempt is unavailable due to missing pytest, not a patch failure (gate-logs/T3-suite.log:14; review-suite.log:1; target/tests/test_input_modes.py:184). |
| T4 Contribution | N/A | Contribution artifacts are intentionally drafted after Check; the deferred gate explicitly assigns the substantive audit to publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm merged and closed/rejected prior art across all three affected paths — the brief reports a path-based search for repl.py/router.py, but the supplied target has only one synthetic base commit and no remotes, so that search and the new input_modes.py/test_input_modes.py paths cannot be independently settled here (brief.md:29; target/src/nl_shell/input_modes.py:1; target/tests/test_input_modes.py:1). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept prefix precedence over valid Bash syntax, reserved @@ behavior, and milestone placeholder wording for this release — tests establish dispatch behavior, but whether this interaction contract suits users remains a product decision (target/src/nl_shell/input_modes.py:3; target/src/nl_shell/input_modes.py:89; target/src/nl_shell/input_modes.py:115). |

Evidence and limits:

- Production changes were stashed and restored in the disposable target, leaving the submitted patch intact. The independent smoke check used the real REPL with scripted input, covering 22 cases: 16 failures before the fix and zero afterward. Its status substring checks alone do not establish a red status assertion; the frozen pytest log supplies exact version-line assertions. Captured patched output independently shows `nl-shell 0.0.0` for both `:status` and `: status`.
- `python3 -m pytest` was attempted for red, green, and the full suite; each failed to launch with `No module named pytest`. This is a reviewer-host limitation. The frozen gate ran real pytest successfully; no unmet product dependency is inferred from this host limitation. The fake PATH fixture isolates heuristic lookup and is adequate for this non-executing milestone.
- Instance-root scanner wrappers are not available in this target; their frozen logs were inspected. The threat-model log establishes only its path-selection verdict, not a comprehensive security audit. No stale-target evidence was found.
- No `INTEGRATION.md` was supplied or found in the target, so additional project-specific human-only items cannot be enumerated from this bundle. The brief's carry-forward mentions six deferred human findings without their contents; this report does not discharge those earlier decisions.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 14 / input-mode-prefix-dispatch (iteration 3)

**Bottom line: I tried to refute the evidence, the fix and the verdict, and could not.** None of the findings below is a NEEDS-HUMAN item.

## Evidence (red → green)

- `gate-logs/C4-verify.log`: the red leg is real. With the fix reverted, 23 of 29 tests failed. Every failure is an assertion failure on a reply, except `test_status_lines_can_be_extended`, which hits an ImportError *inside* the test function, as the brief allows. There were 0 collection errors, so the run counts as red, not UNVERIFIABLE. The 6 tests that pass on `main` are the ones the brief expects to pass: `\ls -la`, `ls -la`, `show disk usage`, `:quit`, `:exit`, plus the distinctness count. The red comes from rows the brief names as carrying it (`\frobnicate`, `?why`, `:status`, `:frobnicate`, the extension point). The new `: quit` / `:  exit` rows (`tests/test_input_modes.py:184-188`) also go red on `main`, so the iteration-2 fix has its own red.
- Green, re-run by me: `tests/test_input_modes.py` + `tests/test_repl.py` give 51 passed on `$PDCA_TARGET`. I confirmed that `nl_shell` was imported from `target/src`, not from another checkout. The tests go through the production path: `Repl(...).run()` → `input_modes.is_exit` / `Repl._reply` (`src/nl_shell/repl.py:62-77`). There is no copied logic. Every reply is pinned as a literal (`tests/test_input_modes.py:9-45`), and the only module-level import is `Repl` (`tests/test_input_modes.py:5`). T3 shows the full suite green (177 passed).

## Attempts on the fix (inputs I ran on the patched tree)

- Exit handling (`src/nl_shell/input_modes.py:67-74`): `:QUIT`, `:quit now` and `:quit\x00` don't exit. They get the unknown reply. That matches the brief's rule of exact, case-sensitive, whole-name matching. Unlike iteration 2, the reply isn't contradicting itself: the name it reports (`quit now`) really isn't in the known list. `\:quit` takes the command route and doesn't exit, which is correct because the prefix wins. Not a refutation.
- Prefix order (`src/nl_shell/input_modes.py:47-53`): `@@@x` → agent-reserved, `?:status` → ask, `::status` → unknown `::status`, `:\tstatus` → status block. All follow the stated rules. Not a refutation.
- `:status` table row (`tests/test_input_modes.py:30,152-155`): it now checks only the first line. If the output is empty, `splitlines()[0]` raises IndexError, so the row still fails rather than passing by accident. The iteration-1 finding is fixed.
- Minor, not NEEDS-HUMAN: `src/nl_shell/input_modes.py:142` echoes the raw payload, control characters included (`:\x1b[2J` would print the escape sequence back). It's the user's own input, and nothing runs yet. I note it for #78 / #17, not as a defect of this diff.
- Minor, not NEEDS-HUMAN: `test_replies_are_distinct` (`tests/test_input_modes.py:107-108`) uses the placeholder key `"nl-shell "` for `:status` instead of the real output. So it doesn't prove the status block differs from the other replies. It obviously does differ (`nl-shell 0.0.0`), so this weakens the test without hiding a bug.
- `\cmd` drops the payload at `src/nl_shell/repl.py:72-76` and returns the fixed command reply. The brief puts running anything and the gate (#78) out of scope, and the comment cites ADR-0013 §7 (Proposed) and #64 as the brief asks. Not a refutation.

## Verdict

- I found no claim in `check-gates.json` that the logs don't support. C4 and T3 PASS match `gate-logs/`. T4 is deferred until publish, which is correct because no PR body exists yet. I could not refute the red→green evidence, the prefix grammar, the exit-on-payload change or the extension point.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review — issue 14 / input-mode-prefix-dispatch

Attacker-reachable inputs this diff touches: **none**. The only input is the line the user types at the REPL, which the threat model lists as trusted ("what the user types", `.oss-scanner/threat_model.md`, Where untrusted input enters → Trusted). Nothing in the patch runs a command, calls a model, reads files, env, history or command output.

## What I checked

- **`\cmd` route** (`src/nl_shell/repl.py:72-76`): it only returns the fixed `COMMAND_NOT_YET` reply. Nothing reaches a PTY or gate. The comment states the ADR-0013 §7 rule (`\` skips the classifier, never the gate), which matches the threat model's "Raw `\cmd` input is the user's own: it goes through the gate and confirm" gap. No bypass is created, since no execution path exists yet.
- **`:` meta-commands** (`src/nl_shell/input_modes.py:131-143`): lookup is an exact `dict.get` on a fixed table. An unknown name can't reach any callable. `:context` and `:history` return fixed strings, so the threat model's output-filter rule for them ("must not let printed text write the clipboard") isn't in play yet.
- **Echo of the unknown name** (`src/nl_shell/input_modes.py:142`): `Unknown meta-command :{payload}` prints user-typed text back unescaped. The source is the user's own keyboard (trusted), so a typed escape sequence only affects the user's own terminal. No finding.
- **`:status`** (`src/nl_shell/input_modes.py:80-86`): prints only `nl_shell.__version__`. No env, path or secret is shown. Later lines added by #92/#16/#77 (endpoint, backend) are for those issues to review against the "secrets reach `:context`" rule; this diff adds none.
- **Exit handling** (`src/nl_shell/repl.py:62`, `src/nl_shell/input_modes.py:67-74`): pure string checks, no crash or hang path. `parse` is a linear scan of five fixed prefixes, so there's no resource cost out of proportion to input.
- **T2 gate** (`gate-logs/T2-threat-model.log`): "no security-relevant path touched". I agree. The threat model doesn't need an update for this patch.

## Findings

No finding.

One note for later, not rated and not a NEEDS-HUMAN item: `src/nl_shell/repl.py:75` says `prefixed.payload` "is the command text the gate will receive", and `parse` strips it (`src/nl_shell/input_modes.py:63`). When #78 wires the gate and PTY, a stripped payload is not byte-identical to what the user typed after `\`. For example, bash treats `\ ls` as a command named ` ls`, and with `HISTCONTROL=ignorespace` a leading space keeps a command out of `~/.bash_history`. Whoever builds #78 should decide whether `\` passes the raw remainder or the stripped one, and show the user exactly that in the confirm ("What the user confirms is exactly what runs"). Today nothing runs, so this has no effect.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] T5 Judgment — Confirm merged and closed/rejected prior art across all three affected paths — the brief reports a path-based search for repl.py/router.py, but the supplied target has only one synthetic base commit and no remotes, so that search and the new input_modes.py/test_input_modes.py paths cannot be independently settled here (brief.md:29; target/src/nl_shell/input_modes.py:1; target/tests/test_input_modes.py:1).
- [x] Validation — fitness-to-purpose — Accept prefix precedence over valid Bash syntax, reserved @@ behavior, and milestone placeholder wording for this release — tests establish dispatch behavior, but whether this interaction contract suits users remains a product decision (target/src/nl_shell/input_modes.py:3; target/src/nl_shell/input_modes.py:89; target/src/nl_shell/input_modes.py:115).
- [x] **The brief brings back the `@@` scope that the design review removed.** The issue title is "M0.6 — Input modes and meta-commands (without @@)", and the thread says: "**Split.** The `@@` agent loop moved to #76. This issue keeps `\`, `?`, `@` and `:` dispatch." The brief's own header agrees ("`@@` moved to #76", brief.md:8–9). But the Goal (brief.md:17), the Scope ("`@@` is checked before `@`; … `@@` → agent-loop route (placeholder only)", brief.md:23), the Design section and the Success criterion all add an `@@` route with its own reply, a test row (`@@clean up my downloads` → agent-loop reply, "NOT the `@` reply") and a bare-`@@` usage reply. That means this issue sets the `@@` grammar and reply wording that #76 owns. There is a real technical reason to touch `@@` here: without it, `@@goal` would fall into the `@` route with the payload `@goal`. Still, the planner should do one of two things. Either say explicitly that #14 only *reserves* `@@` (the smallest possible stub, recorded as a decision against the thread), or drop the `@@` route and test rows and leave `@@…` to the `@` route or the unknown handling until #76. Right now the brief contradicts the tracker without saying so.
- [x] **The brief treats a question the thread leaves open as settled, citing a *Proposed* ADR.** The thread says: "Whether `\cmd` goes through the gate is decided in #64." The brief instead says the question is settled by "ADR-0013 §7" and asks Do to put that in a code comment (brief.md:5–6, 23, 54). ADR-0013 is `status: Proposed` (docs/design/adr/0013-policy-gate-v2.md:4), not Accepted. §7 says what the brief says (adr/0013:82–84), but the brief never mentions #64 or confirms that #64 closed on that ADR. Behaviour is not affected, because nothing runs yet. The comment Do is told to write would still state an unratified decision as fact. Fix: cite #64 / ADR-0013 (Proposed), or word the comment as provisional.
- [x] **Part of the Scope cannot be checked.** "`:status` … build it so later issues can add lines to it (#92, #16, #77) … without rewriting it" (brief.md:23; Design: "its lines come from a list that later issues extend"). No test or gate covers this. The criterion only checks that a line `nl-shell <version>` appears. #92, #16 and #77 all depend on this extension point, so if it matters it needs something a reviewer can check: either a test that appends a line provider and sees it printed (using only names that exist on `main` would rule this out, so it would be a green-only test), or an explicit API named in the brief (e.g. "a module-level list of zero-argument callables in `repl.py`"). Otherwise Check can only judge it by feel.
- [x] **Some table rows already pass on `main`. The red leg holds, but not because of the rows the brief points to.** On `main`, `\ls -la` gives the token `ls` (`shlex` posix mode drops the backslash, src/nl_shell/router.py:40–48) and so prints `COMMAND_NOT_YET`. A bare `:` hits the `:` builtin (router.py:29) and also prints the command reply. A bare `\` gives an empty or odd token. So the `\ls -la` row passes on `main` as written. The Falsifiability line (brief.md:19) is still correct overall: `\frobnicate the widgets`, `?why…`, `:status` and `:frobnicate` all route as natural language on `main` and will fail. This is a note for Do and Check, not a blocker: the red evidence should come from those rows, and nobody should read the `\ls -la` row as proof the prefix handling works.
- [x] **Open question with no default in the criterion.** The Open questions section asks whether a bare prefix should print usage or be ignored (brief.md:64), but the Success criterion already requires a usage reply for each bare prefix (brief.md:18). Either close the question, or tell Do that the criterion wins until the human decides. Otherwise sign-off may reopen tests that Do already pinned.
- [x] size backstop — this slice is behaving oversized: 2 round(s) already spent (threshold 2). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.
- [x] T5 Judgment — Confirm prior-art coverage of all affected paths against merged history and closed/rejected work — the brief records a path-based check for repl/router, but the supplied target has only one synthetic base commit, no remote, and no independently inspectable closed-PR evidence for the new module/test paths (brief.md:29; patch.diff:1; patch.diff:188).
- [x] T5 Judgment — Confirm prior-art coverage for all three affected paths, including closed/rejected work — the brief records a search for repl.py/router.py only, while this snapshot has one synthetic base commit, no remotes, and no PR evidence for the new module/tests (brief.md:29; target/src/nl_shell/input_modes.py:1; target/tests/test_input_modes.py:1).

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
- By / date: Eduard Ralph / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 5 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

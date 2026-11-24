# Result — issue 108 / router-english-sentence-rule

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: Plain English that starts with a command name (`find large files in my home`,
  `who is logged in`) routes as natural language instead of as a shell command, using one
  deterministic rule in `nl_shell.router`. An unbalanced single quote (`find what's using
  port 80`) also counts as natural language.
- Success criterion: In `tests/test_repl.py`'s router table
  (`test_input_is_routed_as_command_or_natural_language`, `tests/test_repl.py:88-108`), the
  pinned vector `find large files in my home` is flipped to natural language, and the twelve
  vectors in the table under Design all pass with the route given there. Run through
  `Repl(...).run()` with a fake `$PATH` that holds every command word the vectors use.
  Every existing router and REPL test in the file still passes, and so does
  `tests/test_failure_classes.py` (the other user of `first_token`).
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: add the English-sentence rule and the unbalanced-quote signal to
  `nl_shell.router`; rewrite the module docstring's "Known limitation" paragraph
  (`src/nl_shell/router.py:8-10`) to describe the new rule and what it still misses; update
  the router table in `tests/test_repl.py` (flip the pinned vector, drop its "Known
  heuristic limitation" comment at `tests/test_repl.py:93-95`, add the vectors below); update
  the `nl_shell.router` row in `docs/design/architecture/05-building-block-view.md:75`. All in
  one PR. / out of scope: the M3 intent classifier (#40); prefix modes; any change to how a
  COMMAND or NATURAL_LANGUAGE route is handled in `repl.py`; bash keywords, aliases,
  functions and leading assignments (still unrecognised, still named in the docstring).

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (6 of 33 failed), green with it
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

Review issue #108: route command-prefixed English sentences and unbalanced apostrophes as natural language using the specified deterministic heuristic.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The routing contract defines word splitting, quote precedence, exclusions and twelve observable examples; the target tests exercise the specified REPL outcomes (target/tests/test_repl.py:89). |
| C2 Reproduction (red pre-fix) | PASS | Independently stashing only production router changes reproduced six incorrect command routes among twelve vectors (reviewer-red.log:1); frozen REPL evidence likewise shows six assertion failures without collection errors (gate-logs/C4-verify.log:275). |
| C3 Change | PASS | The patch stays within router behavior, its REPL tests and the architecture description; first_token remains unchanged for its other caller (target/src/nl_shell/router.py:53; target/docs/design/architecture/05-building-block-view.md:75). |
| C4 Verification (red→green) | PASS | Independent direct routing checks changed from six failures to twelve passes after restoring production changes (reviewer-green.log:1); frozen pytest evidence shows 33 passing REPL tests and six pre-fix failures (gate-logs/C4-verify.log:11; gate-logs/C4-verify.log:282). |
| C5 Causal adequacy | PASS | The resolved-first-token decision now applies the exact specified sentence rule and quote precedence; the six independently reproduced misroutes disappear without a capability probe or symptom guard (target/src/nl_shell/router.py:86; target/src/nl_shell/router.py:115). |
| T1 Structure | PASS | Routing remains independent of the REPL, with bounded private helpers and unchanged tokenization API; no new dependency or cross-layer coupling is introduced (target/src/nl_shell/router.py:91; target/src/nl_shell/router.py:107). |
| T2 Shape | PASS | The change preserves command handling and policy boundaries; the frozen threat-model scanner reports no security-relevant path touched, consistent with the three affected paths (gate-logs/T2-threat-model.log:10; target/src/nl_shell/router.py:115). |
| T3 Runtime | PASS | Frozen full-suite output reports 1112 passed, one skipped and one forkpty warning, covering the unchanged first_token consumer; local pytest rerun is unavailable because this reviewer host lacks pytest (gate-logs/T3-suite.log:33; target/src/nl_shell/router.py:53). |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the logged substantive audit is deferred to the mandatory publish rerun (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm the path-specific prior-art results remain current for the router, REPL tests and architecture document — the brief records router/test history and closed-PR checks, but this target has only one synthetic base commit and no remote, so merged/rejected-work overlap cannot be independently settled (brief.md:58; target/docs/design/architecture/05-building-block-view.md:75). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the deliberate usability tradeoff of sentence heuristics, including short English remaining commands and odd apostrophes overriding echo — deterministic checks establish the agreed examples, while suitability for everyday shell input remains a maintainer decision (target/src/nl_shell/router.py:7; target/src/nl_shell/router.py:22; target/tests/test_repl.py:107). |

Independent verification used rerun-router.py with all specified executable command names present on an isolated PATH and kill/echo provided by the builtin set. This fixture is appropriate to command-name resolution; real command execution and external services are not dependencies of the requested routing behavior. Only src/nl_shell/router.py was stashed for the red leg, preserving the new vectors, and the patch was restored afterward. No production source was edited by the reviewer. git diff --check passed.

The reviewer host's python3 reports “No module named pytest”; therefore the full REPL and suite conclusions above rely on the frozen gate logs, not a claimed local pytest run. The instance-scoped gate wrappers are not included here; their available logs were read. No INTEGRATION.md is present in the supplied target. No stale-target caveat was needed.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review: issue 108 / router-english-sentence-rule

I tried to break the evidence, the fix and the verdict. The red→green holds up and runs through the real code path. Two rules in the new logic have no test that would catch them being removed, and the brief's word list misroutes some real commands.

## Evidence

- Attempted to refute the red→green; could not. `gate-logs/C4-verify.log` shows the six expected vectors red before the fix: the flipped `find large files in my home`, plus `find what's…`, `watch…`, `who…`, `kill…` and `echo it's fine`. All 33 pass after the fix. The test goes through `Repl.run()`, which calls the production `route()` at `target/src/nl_shell/repl.py:144`. It does not use a copy of the router. The fake `$PATH` now holds `watch`, `who`, `free` and `sort` (`tests/test_repl.py:56`), so those vectors resolve for the right reason. `first_token` (`target/src/nl_shell/router.py:53-63`) is unchanged, and T3 is green (1112 passed), which covers `tests/test_failure_classes.py`.

## Findings

- NEEDS-HUMAN [impl] — Rule 3 (no `-` word and no shell metacharacter, `target/src/nl_shell/router.py:100-103`) is not covered by any test. I replaced `_reads_like_english` in-process with a version that drops rule 3 entirely and re-ran all 20 router vectors: none failed. The reason is that every command vector with 4+ words also fails rule 4. `find . -name '*.py'` and `git commit -m "wip` contain no function word, so rule 4 alone keeps them routed as commands. The comments "option and quotes" and "rule 3" at `tests/test_repl.py:106,112` claim coverage the vectors do not give. Concrete fix: add vectors that pass rules 2 and 4 and fail only rule 3, for example `find big files in ~/src` → command (the docstring already names it as a known limitation, `router.py:22-23`), `find the big files -size +1G` → command (`-` word), and `grep the in file|less` → command.
- NEEDS-HUMAN [impl] — The negative side of rule 4 (`router.py:104`) is also uncovered. When I made `FUNCTION_WORDS` match every word, all command vectors still passed, because each 4+ word command vector is already rejected by rule 3. Add a plain 4+ word line with no function word that must stay a command, for example `git push origin main` → command.
- NEEDS-HUMAN [impl] — The `\` and `"` exclusions in the quote signal (`router.py:88`) are uncovered. Removing the `"\\" not in text` clause leaves every vector green. The only vector with `"` (`git commit -m "wip`) has no `'` at all, so it never reaches the `"` check either. Concrete cases to pin: `grep it\'s x y` → command (the `\` turns the signal off, and the line has no function word, so it stays a command; with the `\` clause removed it flips to natural language) and `git commit -m "it's"` → command.
- NEEDS-HUMAN [human] — The word list in the brief includes one-letter and common-argument words, so some real commands now route as natural language. Checked against the patched router: `git add a b c`, `touch a b c`, `ls a b c d`, `cp this that to` and `git log the main branch` all return `natural_language` (the cause is `a`/`this`/`the` in `FUNCTION_WORDS`, `router.py:78-83`). The brief rates a false natural-language route as one model call, and `\cmd` still forces bash, so this costs usability, not safety. But `a` as a filename or branch argument is common. Whether to drop `a` (and maybe `to`/`on`/`by`, which also show up as git refs and filenames) is a decision on the spec, not a builder slip. The patch follows the brief exactly.
- Attempted and could not refute: crashes on unlexable input (`route()` only uses `first_token`, which never raises, plus `str.split()`); leading/trailing whitespace and tabs (`  find large files in my home  ` and tab-separated forms route as natural language, as intended); capitalised English (`Find large files…` already resolves as not-a-command); the order of the quote signal versus the `echo` rule (`echo it's fine` → natural language, pinned); and the docstring/architecture row matching the code (`router.py:3-25`, `05-building-block-view.md:75`).

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory) — issue 108 / router-english-sentence-rule

Attacker-reachable inputs this diff touches: **none.** The only input is the line the user types at the REPL prompt, which the threat model lists as trusted ("what the user types and their confirm and edit decisions"). The router does not read command output, file names, the state block, model output or retrieved history.

No finding. What I checked:

- **Who controls the input.** `route()` (`src/nl_shell/router.py:115-122`) gets only the typed line, from `Repl._reply` (`src/nl_shell/repl.py:144`). Prefixed input (`\cmd`, `@`, `?`, `:`) is handled by `input_modes.parse` before the router and does not reach it. So no untrusted text passes through the new rule.
- **`$PATH` lookup (session state, untrusted item 4).** The diff only moves the existing builtin / `/`-path / `shutil.which` checks into `_is_command_name` (`src/nl_shell/router.py:107-112`). The logic is the same and it still reads nl-shell's own process `PATH`, not the bash session's. No change in exposure.
- **What a misroute costs.** COMMAND → NATURAL_LANGUAGE now happens more often. The result is a model proposal, and that still has to pass the proposal parser and (once #78 lands) the gate and confirm. NATURAL_LANGUAGE → COMMAND is not made more likely by this diff. The threat model rates a wrong intent route as **Low** and says a wrong route still ends at the gate. Nothing in the diff skips the gate or the confirm. `repl.py` is untouched.
- **A secret typed as a command ending up in model context.** A line that used to route as COMMAND can now go to the local model as a request. Typical secret-carrying lines (`export TOKEN=…`, `mysql -pSECRET`, `curl -H "Authorization: …"`) contain `=`, `-` or `"`, so rule 3 (`src/nl_shell/router.py:100-103`) keeps them as COMMAND. A sentence with a pasted key in it (`find the file with key sk123abc`) would reach the local, no-network model. That is the user's own text sent to their own model, which the design allows, so it is not a finding.
- **Crash, hang or resource use.** `_has_unbalanced_single_quote` and `_reads_like_english` (`src/nl_shell/router.py:86-104`) are plain linear scans (`count`, `split`, `in` on frozensets). No regex, no shlex on the full line, so nothing can raise or backtrack badly. `first_token` (`src/nl_shell/router.py:53-63`) is unchanged and still never raises, so the other caller in `failure_classes` is unaffected.
- **Tests.** This change is not security-relevant, so friendly-path coverage is enough. Even so, the table pins the cases that matter for routing safety: option and quote lines (`find . -name '*.py'`, `git commit -m "wip`) stay COMMAND. C4 shows 6 of 33 red before the fix and all green after (`gate-logs/C4-verify.log`). T2 found no security-relevant path touched.

No NEEDS-HUMAN items.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T5 Judgment — Confirm the path-specific prior-art results remain current for the router, REPL tests and architecture document — the brief records router/test history and closed-PR checks, but this target has only one synthetic base commit and no remote, so merged/rejected-work overlap cannot be independently settled (brief.md:58; target/docs/design/architecture/05-building-block-view.md:75).
- [ ] Validation — fitness-to-purpose — Accept the deliberate usability tradeoff of sentence heuristics, including short English remaining commands and odd apostrophes overriding echo — deterministic checks establish the agreed examples, while suitability for everyday shell input remains a maintainer decision (target/src/nl_shell/router.py:7; target/src/nl_shell/router.py:22; target/tests/test_repl.py:107).
- [ ] Rule 3 (no `-` word and no shell metacharacter, `target/src/nl_shell/router.py:100-103`) is not covered by any test. I replaced `_reads_like_english` in-process with a version that drops rule 3 entirely and re-ran all 20 router vectors: none failed. The reason is that every command vector with 4+ words also fails rule 4. `find . -name '*.py'` and `git commit -m "wip` contain no function word, so rule 4 alone keeps them routed as commands. The comments "option and quotes" and "rule 3" at `tests/test_repl.py:106,112` claim coverage the vectors do not give. Concrete fix: add vectors that pass rules 2 and 4 and fail only rule 3, for example `find big files in ~/src` → command (the docstring already names it as a known limitation, `router.py:22-23`), `find the big files -size +1G` → command (`-` word), and `grep the in file|less` → command.
- [ ] The negative side of rule 4 (`router.py:104`) is also uncovered. When I made `FUNCTION_WORDS` match every word, all command vectors still passed, because each 4+ word command vector is already rejected by rule 3. Add a plain 4+ word line with no function word that must stay a command, for example `git push origin main` → command.
- [ ] The `\` and `"` exclusions in the quote signal (`router.py:88`) are uncovered. Removing the `"\\" not in text` clause leaves every vector green. The only vector with `"` (`git commit -m "wip`) has no `'` at all, so it never reaches the `"` check either. Concrete cases to pin: `grep it\'s x y` → command (the `\` turns the signal off, and the line has no function word, so it stays a command; with the `\` clause removed it flips to natural language) and `git commit -m "it's"` → command.
- [ ] The word list in the brief includes one-letter and common-argument words, so some real commands now route as natural language. Checked against the patched router: `git add a b c`, `touch a b c`, `ls a b c d`, `cp this that to` and `git log the main branch` all return `natural_language` (the cause is `a`/`this`/`the` in `FUNCTION_WORDS`, `router.py:78-83`). The brief rates a false natural-language route as one model call, and `\cmd` still forces bash, so this costs usability, not safety. But `a` as a filename or branch argument is common. Whether to drop `a` (and maybe `to`/`on`/`by`, which also show up as git refs and filenames) is a decision on the spec, not a builder slip. The patch follows the brief exactly.
- [ ] **The "peer to mirror" points at a detection that never fires for the vector it has to serve.** The brief says: "the existing `first_token` `ValueError` branch (`src/nl_shell/router.py:38-48`) is where an unbalanced quote is already detected; the new signal reuses that detection rather than re-lexing the line." But `first_token` calls `lexer.get_token()` only once (`router.py:40-43`). With `whitespace_split = True`, shlex stops reading at the first whitespace after a word, so it only raises `ValueError` when the bad quote is *inside the first word*. That is why the existing vector `what's using port 80` (`tests/test_repl.py:100`) hits the branch. For the new vector `find what's using port 80`, `get_token()` returns `"find"` and never reads `what's`, so there is no `ValueError` and nothing to reuse. Following the brief literally gives a red test on that vector. Do has to lex the whole line, which is the "re-lexing" the brief rules out. Revise the Citations line: name the full-line lex as part of the change, or drop the "rather than re-lexing" constraint.
- [ ] **A `ValueError` is not the same as "an unbalanced single quote", and the brief treats them as one.** In posix mode, shlex raises `ValueError` for an unclosed double quote ("No closing quotation") and for a trailing backslash ("No escaped character") as well as for an unclosed `'`. The Design section says an "unbalanced **single** quote (the `ValueError` branch in `first_token`)" is a natural-language signal "on its own". Two readings follow: (a) any lexer error means natural language, so `git commit -m "wip` routes to the model, or (b) only an unclosed `'` does. The brief doesn't choose, and no vector pins either one. Rule 3 rejects double quotes, but the quote signal is described as separate from the four conditions, so rule 3 doesn't settle it. Add one vector, or one sentence, that fixes which errors count.
- [ ] **How the quote signal ranks against the other conditions is unspecified.** "On its own" could mean it overrides rule 1 (`echo it's fine` → natural language?), rule 3 (`find . -name what's` → natural language despite the `-`?) and the "first token resolves" precondition. The brief also doesn't say whether it is checked before the builtin/`$PATH` lookup (`router.py:61-66`) or only after it. None of the ten vectors decides this, so two implementations can both pass the success criterion while routing these lines differently. Do and Check will each guess. State the order explicitly (e.g. "checked first, overrides rules 1–4"), or add one `echo …'…` vector.
- [ ] **`first_token` has a second caller the brief doesn't mention.** `src/nl_shell/failure_classes.py:46` imports `first_token`, and `failure_classes.py:388` relies on it returning a plain `str`, with the whitespace fallback on bad quoting. If Do follows the "reuse the `ValueError` branch" advice by changing `first_token`'s return type or behaviour (e.g. to report the quote error), it silently changes `_unresolved_word` in a module the scope never lists. Add to the brief: `first_token`'s signature and behaviour stay unchanged; the new signal lives in `route()` or a new helper. Name `tests/test_failure_classes.py` as a suite that must stay green.
- [ ] **"Words" is not defined, and the rules depend on it.** Rule 2 ("at least 4 words"), rule 3 ("no word starts with `-`") and rule 4 (function-word match, lowercased) all count "words", but the brief doesn't say whether that means `str.split()` or shlex tokens. The two differ on quoted input (`find 'my big file' in here`) and on the unbalanced-quote lines, where shlex can't split at all. The ten vectors don't tell the two apart, so this won't break the criterion, but it leaves an undocumented edge that the new docstring ("what it still misses") is meant to describe. One line in Design would close it.
- [ ] **Small accuracy point in Ordering note / Depends on.** The issue says "**Depends on** #14 (input-mode prefix dispatch, which also changes `src/nl_shell/router.py`)". The brief sets `Depends on: none` because #14 is merged, and the target bears that out: `src/nl_shell/input_modes.py` exists and `repl.py:142-151` dispatches `\cmd`. But #14 landed in `input_modes.py`/`repl.py`, not `router.py`, which matches the brief's own prior-art line ("`router.py` → only dc784f0"). So calling it "the other change to `router.py`" is wrong. It doesn't block anything; it's just inconsistent within the brief.

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
- Iteration delta (if iterating): Auto-iterate (round 1): rebuilding for the implementation-level findings — Rule 3 (no `-` word and no shell metacharacter, `target/src/nl_shell/router.py:100-103`) is not covered by any test. I replaced `_reads_like_english` in-process with a version that drops rule 3 entirely and re-ran all 20 router vectors: none failed. The reason is that every command vector with 4+ words also fails rule 4. `find . -name '*.py'` and `git commit -m "wip` contain no function word, so rule 4 alone keeps them routed as commands. The comments "option and quotes" and "rule 3" at `tests/test_repl.py:106,112` claim coverage the vectors do not give. Concrete fix: add vectors that pass rules 2 and 4 and fail only rule 3, for example `find big files in ~/src` → command (the docstring already names it as a known limitation, `router.py:22-23`), `find the big files -size +1G` → command (`-` word), and `grep the in file|less` → command.; The negative side of rule 4 (`router.py:104`) is also uncovered. When I made `FUNCTION_WORDS` match every word, all command vectors still passed, because each 4+ word command vector is already rejected by rule 3. Add a plain 4+ word line with no function word that must stay a command, for example `git push origin main` → command.; The `\` and `"` exclusions in the quote signal (`router.py:88`) are uncovered. Removing the `"\\" not in text` clause leaves every vector green. The only vector with `"` (`git commit -m "wip`) has no `'` at all, so it never reaches the `"` check either. Concrete cases to pin: `grep it\'s x y` → command (the `\` turns the signal off, and the line has no function word, so it stays a command; with the `\` clause removed it flips to natural language) and `git commit -m "it's"` → command.. Deferred, not addressed here: 8 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- By / date: auto-iterate / 2026-10-23

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 6 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

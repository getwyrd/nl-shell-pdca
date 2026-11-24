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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (6 of 41 failed), green with it
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

Review issue #108: route command-prefixed English sentences and qualifying unbalanced apostrophes as natural language while preserving explicit shell syntax.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The deterministic rule, quote precedence, exclusions and twelve required vectors define an assessable scope; implementation matches those choices at target/src/nl_shell/router.py:86. |
| C2 Reproduction (red pre-fix) | PASS | Independently executing the git-base router confirms all six intended English examples incorrectly return COMMAND; the frozen REPL run also records six assertion failures, not setup failures (gate-logs/C4-verify.log:16). |
| C3 Change | PASS | The three changed files stay within routing, regression tests and architecture documentation; first_token is independently confirmed unchanged, preserving its other caller's contract (target/src/nl_shell/router.py:53; target/docs/design/architecture/05-building-block-view.md:75). |
| C4 Verification (red→green) | PASS | Independent base-versus-patched execution confirms all six route transitions; frozen evidence shows 6 failed/35 passed before and 41 passed after. Local pytest rerun was unavailable (No module named pytest), so REPL integration confirmation rests on the captured run (gate-logs/C4-verify.log:12). |
| C5 Causal adequacy | PASS | The first-token-only decision is replaced at the routing decision point; 5,324 independent comparisons against the specified predicate passed. No capability probe or load-time symptom guard is added (target/src/nl_shell/router.py:91; target/src/nl_shell/router.py:115). |
| T1 Structure | PASS | Pure routing helpers retain the module boundary and avoid REPL coupling or new dependencies; command resolution still reads PATH per call (target/src/nl_shell/router.py:107). |
| T2 Shape | PASS | Exact quote exclusions, word splitting and function-word membership match the specification; only the three scoped files change, and the frozen threat-model scanner reports no security-relevant path touched (target/src/nl_shell/router.py:75; gate-logs/T2-threat-model.log:11). |
| T3 Runtime | PASS | Frozen full-suite output records 1,120 passed, one skipped and one forkpty warning; local pytest is absent, so this is log-supported rather than a repeated full-suite result (gate-logs/T3-suite.log:28; gate-logs/T3-suite.log:33). |
| T4 Contribution | N/A | Contribution artifacts are absent by design; the captured deferred gate explicitly requires the substantive contribution audit at publish (gate-logs/T4-contribution.log:11). |
| T5 Judgment | NEEDS-HUMAN | Confirm the path-specific merged-history and closed/rejected-work search remains sufficient — the brief records searches for router.py and test_repl.py, but this disposable target exposes only one synthetic base commit and cannot independently establish remote or rejected-work history (brief.md:58). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the deliberate usability tradeoff that sentence-shaped commands may invoke natural-language handling and short/metacharacter-containing English remains a command — the prescribed examples pass, but real-user suitability requires maintainer judgment (target/src/nl_shell/router.py:15; target/src/nl_shell/router.py:22). |

Independent checks used only the supplied disposable target: the base router was loaded from git show without changing the tree, and patched/base routes were exercised with command lookup controlled. This confirms predicate behavior, not a substitute for the REPL integration run in the gate log. The fake PATH in the actual regression tests contains every external command used; kill, echo and printf resolve as builtins (target/tests/test_repl.py:49; target/src/nl_shell/router.py:42).

The previous iteration's missing coverage is addressed: isolated negative vectors cover option words, metacharacters, absence of function words, and both exclusions on the apostrophe signal (target/tests/test_repl.py:115). No implementation defect was identified. The repository snapshot contains no INTEGRATION.md; no additional human-only checklist was available in the supplied evidence.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 108 / router-english-sentence-rule (iteration 2)

**Result:** I could not break the fix against the brief. All my findings are either one small test gap, or places where the brief's own rule misroutes real input.

**What I tried and could not refute**

- **The red→green evidence holds.** `gate-logs/C4-verify.log`: green leg 41/41. With only the production change reverted, the red leg fails 6 tests. Those are the five new natural-language vectors plus `echo it's fine`, which are exactly the ones `main` routes as commands (`target/src/nl_shell/router.py:115-122`). The test goes through `Repl(...).run()` with the extended `fake_path` fixture (`target/tests/test_repl.py:50-59`), so it runs the real code path, not a copy. `watch`, `who`, `free`, `sort` and `grep` are on the fake `$PATH`, so the command-side vectors cannot pass just because a word is missing.
- **The iteration-1 gaps are closed.** Each "one part of the rule" vector (`target/tests/test_repl.py:113-122`) does fail if its clause is removed. Rule 3 is pinned three ways (`-size`, `~/`, `|`, plus the `"` case), rule 4's negative side by `git push origin main`, and the `\`/`"` exclusions in `_has_unbalanced_single_quote` (`target/src/nl_shell/router.py:86-88`) by `grep it\'s x y` and `git commit -m "it's"`.
- **The code matches the spec.** The metacharacter set, the function-word list, `split()` words, `echo`/`printf`, and the order (unresolved token → NL, then the quote signal, then rules 1–4) all match the brief (`target/src/nl_shell/router.py:71-122`). `first_token` is unchanged (`router.py:53-63`), so its other caller `failure_classes.py:388` is not affected, and T3 (the full suite) is green: 1120 passed (`gate-logs/T3-suite.log`).
- **Odd inputs I probed** with the real `route()`: tabs and repeated spaces, upper case (`WHO IS LOGGED IN`), trailing `?`, builtins (`cd the docs in my home`), and a leading `'`. Every one routed as the spec says, and none raised.

**Findings**

- NEEDS-HUMAN [impl] — The brief says the quote signal "overrides" rules 1–4, but nothing pins it against rule 3 (`target/src/nl_shell/router.py:93-94` versus `:100-103`). I swapped in a version of `_reads_like_english` that checks rule 3 (`-` words and metacharacters) *before* the quote signal and ran all 20 new vectors: none failed. Only the spec'd output of `find . -name it's` changed, from NATURAL_LANGUAGE to COMMAND. `echo it's fine` pins the order against rule 1, and `find what's using port 80` pins it against rule 4, but no vector has an odd `'` together with a `-` word or a metacharacter. Fix: add a vector like `find . -name it's` → natural language, or `find what's in ~/src` → natural language, to `target/tests/test_repl.py:91-123`.
- NEEDS-HUMAN [human] — The function-word list in the brief includes `a`, `in`, `this`, `that` and `the`, all of which are common file and branch names. So ordinary commands now route as natural language. Probed with the real `route()`: `mv a b c`, `cat a b c`, `rm this that other`, `cp in out backup` and `git add the README` all route as NATURAL_LANGUAGE (`target/src/nl_shell/router.py:78-83,104`). The code does what the brief asks, and the brief accepts this cost (a false NL route costs one model call, and `\cmd` forces bash). But single-letter arguments like `a` are common in real typing, and the new docstring's "Known limitations" (`router.py:22-25`) only lists failures in the other direction. A human should decide whether to drop `a` from the list, or at least name this direction in the docstring.
- NEEDS-HUMAN [human] — Balanced single quotes are not treated as shell syntax. Rule 3's metacharacter set leaves out `'` (`target/src/nl_shell/router.py:75`), as the brief specifies. So a quoted command routes as natural language as long as it has no `-` word: `ssh host 'ls the dir in home'` and `grep 'the error' in logs` both go to NL. A human should decide whether a balanced `'…'` pair should count as a metacharacter.
- NEEDS-HUMAN [human] — Typographic apostrophes (`’`, U+2019, which phones and some editors insert) do not trigger the quote signal (`target/src/nl_shell/router.py:88`). `find what’s using port 80` routes as COMMAND, while the ASCII form routes as NL. This is outside the brief's spec, so it is a scope question: treat `’` as a natural-language signal, or leave it.
- No unwarranted claim found in `check-gates.json`. C4 and T3 match their logs. T4 is `deferred` because there is no PR body yet, so it proves nothing at this point and must still be checked at publish.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review — issue 108 / router-english-sentence-rule

Attacker-reachable inputs this diff touches: **none**. The only input to `route()` is the line the user types at the prompt, which the threat model lists as trusted ("what the user types", `.oss-scanner/threat_model.md`, "Trusted").

## What I checked

- **Who calls the changed code.** `route()` has one caller, `src/nl_shell/repl.py:144`. It gets the stripped prompt line after prefix parsing (`repl.py:133,142`). No command output, file name, environment value, model output or history reaches it. `failure_classes.py:46` imports only `BASH_BUILTINS` and `first_token`, and the diff leaves both unchanged (`src/nl_shell/router.py:43-53`).
- **What a wrong route can do.** A COMMAND route still returns `COMMAND_NOT_YET` (`repl.py:145`), and once #78 lands it will go to the policy gate. A NATURAL_LANGUAGE route goes to `_propose` (`repl.py:146,155-170`). That builds a prompt for the local model and shows a parsed proposal. It runs nothing. The threat model rates a misroute as Low ("the intent classifier routing input to the wrong mode") and puts the router in its lower-priority list. The new rule only moves some lines from COMMAND to NATURAL_LANGUAGE. It cannot skip the gate: `\cmd` still skips only the router (`repl.py:147-151`), and the diff does not touch `repl.py`, the gate, the PTY code, taint or logging.
- **Secrets the user typed reaching the model.** A line now routed as natural language is sent to the command model. I checked whether the usual ways people type secrets on a command line could slip through. `export TOKEN=x for the build` is rejected by rule 3 (`=`). `mysql -u root -phunter2 for the db` is rejected (a word starts with `-`). `curl https://...` is rejected (`/`). Even if a secret did get through, it would be the user's own text going to a local model on a `0600` socket, which is the normal path for any natural-language request. No finding.
- **Panic, hang or heavy work from the input.** The new helpers (`router.py:87-106`) only call `str.count`, `str.split`, `in` checks and frozenset lookups. All are linear in the line length, with no regex and no shlex. `first_token` still catches shlex's `ValueError` (`router.py:47-51`). `_is_command_name` (`router.py:109-114`) is the old resolution logic moved into a function with the same order and behaviour: builtin, then a path containing `/` checked with `is_executable_file`, then `shutil.which`.
- **`$PATH` as session state (threat model item 4).** The router reads nl-shell's own process `$PATH` through `shutil.which`, not the bash session's, and the diff does not change that. It is unchanged code, not something this patch introduces.
- **Test coverage of the security-relevant case.** None is needed, because this change has no security impact. Gate T2 (`gate-logs/T2-threat-model.log`) also reports "no security-relevant path touched", and the brief says the same ("no threat-model input changes").

## Findings

No findings. The diff touches no attacker-reachable input. Its only effect is on routing, which the threat model rates Low and says still ends at the gate.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T5 Judgment — Confirm the path-specific merged-history and closed/rejected-work search remains sufficient — the brief records searches for router.py and test_repl.py, but this disposable target exposes only one synthetic base commit and cannot independently establish remote or rejected-work history (brief.md:58).
- [ ] Validation — fitness-to-purpose — Accept the deliberate usability tradeoff that sentence-shaped commands may invoke natural-language handling and short/metacharacter-containing English remains a command — the prescribed examples pass, but real-user suitability requires maintainer judgment (target/src/nl_shell/router.py:15; target/src/nl_shell/router.py:22).
- [ ] The brief says the quote signal "overrides" rules 1–4, but nothing pins it against rule 3 (`target/src/nl_shell/router.py:93-94` versus `:100-103`). I swapped in a version of `_reads_like_english` that checks rule 3 (`-` words and metacharacters) *before* the quote signal and ran all 20 new vectors: none failed. Only the spec'd output of `find . -name it's` changed, from NATURAL_LANGUAGE to COMMAND. `echo it's fine` pins the order against rule 1, and `find what's using port 80` pins it against rule 4, but no vector has an odd `'` together with a `-` word or a metacharacter. Fix: add a vector like `find . -name it's` → natural language, or `find what's in ~/src` → natural language, to `target/tests/test_repl.py:91-123`.
- [ ] The function-word list in the brief includes `a`, `in`, `this`, `that` and `the`, all of which are common file and branch names. So ordinary commands now route as natural language. Probed with the real `route()`: `mv a b c`, `cat a b c`, `rm this that other`, `cp in out backup` and `git add the README` all route as NATURAL_LANGUAGE (`target/src/nl_shell/router.py:78-83,104`). The code does what the brief asks, and the brief accepts this cost (a false NL route costs one model call, and `\cmd` forces bash). But single-letter arguments like `a` are common in real typing, and the new docstring's "Known limitations" (`router.py:22-25`) only lists failures in the other direction. A human should decide whether to drop `a` from the list, or at least name this direction in the docstring.
- [ ] Balanced single quotes are not treated as shell syntax. Rule 3's metacharacter set leaves out `'` (`target/src/nl_shell/router.py:75`), as the brief specifies. So a quoted command routes as natural language as long as it has no `-` word: `ssh host 'ls the dir in home'` and `grep 'the error' in logs` both go to NL. A human should decide whether a balanced `'…'` pair should count as a metacharacter.
- [ ] Typographic apostrophes (`’`, U+2019, which phones and some editors insert) do not trigger the quote signal (`target/src/nl_shell/router.py:88`). `find what’s using port 80` routes as COMMAND, while the ASCII form routes as NL. This is outside the brief's spec, so it is a scope question: treat `’` as a natural-language signal, or leave it.
- [ ] **The "peer to mirror" points at a detection that never fires for the vector it has to serve.** The brief says: "the existing `first_token` `ValueError` branch (`src/nl_shell/router.py:38-48`) is where an unbalanced quote is already detected; the new signal reuses that detection rather than re-lexing the line." But `first_token` calls `lexer.get_token()` only once (`router.py:40-43`). With `whitespace_split = True`, shlex stops reading at the first whitespace after a word, so it only raises `ValueError` when the bad quote is *inside the first word*. That is why the existing vector `what's using port 80` (`tests/test_repl.py:100`) hits the branch. For the new vector `find what's using port 80`, `get_token()` returns `"find"` and never reads `what's`, so there is no `ValueError` and nothing to reuse. Following the brief literally gives a red test on that vector. Do has to lex the whole line, which is the "re-lexing" the brief rules out. Revise the Citations line: name the full-line lex as part of the change, or drop the "rather than re-lexing" constraint.
- [ ] **A `ValueError` is not the same as "an unbalanced single quote", and the brief treats them as one.** In posix mode, shlex raises `ValueError` for an unclosed double quote ("No closing quotation") and for a trailing backslash ("No escaped character") as well as for an unclosed `'`. The Design section says an "unbalanced **single** quote (the `ValueError` branch in `first_token`)" is a natural-language signal "on its own". Two readings follow: (a) any lexer error means natural language, so `git commit -m "wip` routes to the model, or (b) only an unclosed `'` does. The brief doesn't choose, and no vector pins either one. Rule 3 rejects double quotes, but the quote signal is described as separate from the four conditions, so rule 3 doesn't settle it. Add one vector, or one sentence, that fixes which errors count.
- [ ] **How the quote signal ranks against the other conditions is unspecified.** "On its own" could mean it overrides rule 1 (`echo it's fine` → natural language?), rule 3 (`find . -name what's` → natural language despite the `-`?) and the "first token resolves" precondition. The brief also doesn't say whether it is checked before the builtin/`$PATH` lookup (`router.py:61-66`) or only after it. None of the ten vectors decides this, so two implementations can both pass the success criterion while routing these lines differently. Do and Check will each guess. State the order explicitly (e.g. "checked first, overrides rules 1–4"), or add one `echo …'…` vector.
- [ ] **`first_token` has a second caller the brief doesn't mention.** `src/nl_shell/failure_classes.py:46` imports `first_token`, and `failure_classes.py:388` relies on it returning a plain `str`, with the whitespace fallback on bad quoting. If Do follows the "reuse the `ValueError` branch" advice by changing `first_token`'s return type or behaviour (e.g. to report the quote error), it silently changes `_unresolved_word` in a module the scope never lists. Add to the brief: `first_token`'s signature and behaviour stay unchanged; the new signal lives in `route()` or a new helper. Name `tests/test_failure_classes.py` as a suite that must stay green.
- [ ] **"Words" is not defined, and the rules depend on it.** Rule 2 ("at least 4 words"), rule 3 ("no word starts with `-`") and rule 4 (function-word match, lowercased) all count "words", but the brief doesn't say whether that means `str.split()` or shlex tokens. The two differ on quoted input (`find 'my big file' in here`) and on the unbalanced-quote lines, where shlex can't split at all. The ten vectors don't tell the two apart, so this won't break the criterion, but it leaves an undocumented edge that the new docstring ("what it still misses") is meant to describe. One line in Design would close it.
- [ ] **Small accuracy point in Ordering note / Depends on.** The issue says "**Depends on** #14 (input-mode prefix dispatch, which also changes `src/nl_shell/router.py`)". The brief sets `Depends on: none` because #14 is merged, and the target bears that out: `src/nl_shell/input_modes.py` exists and `repl.py:142-151` dispatches `\cmd`. But #14 landed in `input_modes.py`/`repl.py`, not `router.py`, which matches the brief's own prior-art line ("`router.py` → only dc784f0"). So calling it "the other change to `router.py`" is wrong. It doesn't block anything; it's just inconsistent within the brief.
- [ ] T5 Judgment — Confirm the path-specific prior-art results remain current for the router, REPL tests and architecture document — the brief records router/test history and closed-PR checks, but this target has only one synthetic base commit and no remote, so merged/rejected-work overlap cannot be independently settled (brief.md:58; target/docs/design/architecture/05-building-block-view.md:75).
- [ ] The word list in the brief includes one-letter and common-argument words, so some real commands now route as natural language. Checked against the patched router: `git add a b c`, `touch a b c`, `ls a b c d`, `cp this that to` and `git log the main branch` all return `natural_language` (the cause is `a`/`this`/`the` in `FUNCTION_WORDS`, `router.py:78-83`). The brief rates a false natural-language route as one model call, and `\cmd` still forces bash, so this costs usability, not safety. But `a` as a filename or branch argument is common. Whether to drop `a` (and maybe `to`/`on`/`by`, which also show up as git refs and filenames) is a decision on the spec, not a builder slip. The patch follows the brief exactly.

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
- Iteration delta (if iterating): Auto-iterate (round 2): rebuilding for the implementation-level findings — The brief says the quote signal "overrides" rules 1–4, but nothing pins it against rule 3 (`target/src/nl_shell/router.py:93-94` versus `:100-103`). I swapped in a version of `_reads_like_english` that checks rule 3 (`-` words and metacharacters) *before* the quote signal and ran all 20 new vectors: none failed. Only the spec'd output of `find . -name it's` changed, from NATURAL_LANGUAGE to COMMAND. `echo it's fine` pins the order against rule 1, and `find what's using port 80` pins it against rule 4, but no vector has an odd `'` together with a `-` word or a metacharacter. Fix: add a vector like `find . -name it's` → natural language, or `find what's in ~/src` → natural language, to `target/tests/test_repl.py:91-123`.. Deferred, not addressed here: 10 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- By / date: auto-iterate / 2026-10-23

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 6 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

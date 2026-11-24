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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (8 of 43 failed), green with it
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

Review issue #108: route command-prefixed English sentences and unbalanced apostrophes as natural language while preserving the specified shell-command exceptions.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The deterministic rule, override order, exclusions and compatibility boundary are explicit and testable; target/src/nl_shell/router.py:7, target/tests/test_repl.py:101. |
| C2 Reproduction (red pre-fix) | PASS | Independently executing all 30 table vectors against the base router reproduces exactly 8 misroutes; the frozen pytest red leg likewise reports 8 failures (gate-logs/C4-verify.log:15); target/tests/test_repl.py:101. |
| C3 Change | PASS | The three affected files stay within the routing, regression-test and architecture-documentation scope; first_token is AST-identical to the base, preserving its other caller; target/src/nl_shell/router.py:53. |
| C4 Verification (red→green) | PASS | Independent standard-library execution gives 8/30 failures on the base and 0/30 patched; frozen evidence gives 8/43 red and 43/43 green through Repl; local pytest is unavailable, so pytest confirmation rests on gate-logs/C4-verify.log:10; target/tests/test_repl.py:129. |
| C5 Causal adequacy | PASS | The change addresses the specified command-name-only classification cause; quote precedence and each independent exclusion now have distinguishing vectors, with no capability-probe workaround; target/src/nl_shell/router.py:93, target/tests/test_repl.py:115. |
| T1 Structure | PASS | Pure routing helpers preserve separation from REPL execution and retain per-call executable resolution; target/src/nl_shell/router.py:107. |
| T2 Shape | PASS | No execution, policy, PTY, sudo or taint surface changes; the frozen threat-model scanner confirms no security-relevant path touched (gate-logs/T2-threat-model.log:11); target/src/nl_shell/router.py:115. |
| T3 Runtime | PASS | Frozen full-suite output shows 1122 passed, 1 skipped and a forkpty warning; local pytest is absent, so this is log-backed rather than a reproduced suite run; gate-logs/T3-suite.log:33; target/tests/test_repl.py:129. |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive audit must rerun at publish, as recorded in gate-logs/T4-contribution.log:11. |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art across merged history and closed/rejected work before sign-off — the supplied target contains only one synthetic base commit and no remotes, so the brief's prior-art claim cannot be independently established; target/src/nl_shell/router.py:115, target/tests/test_repl.py:129. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the specified heuristic's usability tradeoff — short English and metacharacter-bearing sentences still route as commands, while apostrophes can override shell-looking syntax; target/src/nl_shell/router.py:22, target/tests/test_repl.py:124. |

Independent checks: production-only stash succeeded and was restored after pytest reported `No module named pytest`; a standard-library harness extracted the actual 30 test vectors, used executable command files on an isolated PATH, and compared the committed base router with the patched router. This fixture exercises real executable lookup and can reproduce the forbidden misroutes; no external dependency is required by the brief. `git diff --check` passed. The supplied target is current with the patch, and no INTEGRATION.md is present in it. Instance-scoped gate wrappers are not supplied; their captured logs were read instead. No implementation defect was identified.

The local full-suite and failure-class reruns could not execute without pytest; the frozen full-suite result covers the failure-class tests, and the unchanged first_token was independently checked structurally. This host limitation does not contradict the captured successful gate execution.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 108 / router-english-sentence-rule

I tried to refute the fix and could not break it against the brief. What's left is small test gaps and a few spec-level misroutes the brief allows on purpose.

**What I tried and could not refute**

- **The red→green evidence is real.** `gate-logs/C4-verify.log` shows 8 of 43 failing without the fix. Those are exactly the 8 NATURAL_LANGUAGE vectors whose first word resolves. The test (`tests/test_repl.py:127-130`) drives the production `Repl` through `run()` and checks its output, so it does not use a copy of the logic. T3 shows the full suite green (1122 passed). pytest is not installed in my sandbox, so I re-ran the 32 table vectors directly against `nl_shell.router.route` with a fake `$PATH`. All 32 match.
- **Mutation checks against the table** (each one swaps in a changed router and re-runs the vectors). Word count `< 3` fails on `ls my files`, and `< 5` fails on `who is logged in`. Removing the quote signal fails 4 vectors. Emptying `FREE_TEXT_COMMANDS` fails 2, and dropping only `printf` fails 1. Earlier rounds already showed that rule 3, rule 4, the `\`/`"` exclusions and the signal-before-rule-3 order are pinned (`tests/test_repl.py:114-125`).
- **`first_token` is unchanged** (`src/nl_shell/router.py:52-61`), so its other caller in `failure_classes.py` is not affected.

**Findings**

- NEEDS-HUMAN [impl] — The `.lower()` in rule 4 (`src/nl_shell/router.py:104`) is not tested. If I remove it, all vectors still pass. Then `Find The Big Files In My Home` would stay natural language only by luck: `Find` is not on `$PATH`. And `ls The Big Files Here` (resolved first word, function word only in title case) would flip to COMMAND without any test failing. Fix: add a vector like `watch The logs For errors` → natural language.
- NEEDS-HUMAN [impl] — 16 of the 18 shell metacharacters in `SHELL_METACHARACTERS` (`src/nl_shell/router.py:75`) are not pinned one by one. Removing any single one of `& ; < > $ * = ( ) { } [ ] ~ / backtick` from the set leaves every vector green. `~` and `/` only appear together in `find big files in ~/src`, so each one hides the loss of the other. A later edit that drops `$` or `=` would quietly send `grep the $HOME in x` or `find the x in a=b` to the model. This is a low-severity test gap, not a bug in the patch. A small parametrized test, one line per character, would close it.
- NEEDS-HUMAN [human] — The spec'd function-word list misroutes some plausible real commands. I ran these through the patched `route()` with the commands on a fake `$PATH`: `make all check install`, `cat a b c`, `touch a b c d`, `git add the file`, `grep error in log.txt` and `time make all in here` all route as natural language. The words `a`, `all`, `the` and `in` are common shell operands (file names, make targets). The patch follows the brief to the letter (brief §Design rule 4), and `\cmd` forces bash. Still, a human should confirm that `a` and `all` belong in the list. This is the brief's choice, not a builder slip.
- NEEDS-HUMAN [human] — A false natural-language route sends the raw line to the model backend, which may be remote. The brief treats this as only a usability cost ("costs one model call"). The quote signal overrides every other rule (`src/nl_shell/router.py:93-94`), so a real command with a stray apostrophe goes to the model whatever it contains, as long as it has no `"` or `\`. For example, `grep -c ' file`, `sed s/'//g f` and `git checkout -- it's` all route as natural language. Rule 3 stops most lines that hold secrets (`=`, `-`, `$`), but the quote path skips rule 3. Whether that matters depends on the backend's privacy model. ADR-0013 only covers the command side of a misroute. This is a scope call for a human, not something to fix in this patch.

No other refutation: the fix meets the brief's success criterion, and the evidence exercises the production path.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review — issue 108 / router-english-sentence-rule

Attacker-reachable inputs this diff touches: **none**. The only input is the line the user types at the prompt, and the threat model lists "what the user types" as trusted (`target/.oss-scanner/threat_model.md`, "Trusted"). The router never sees command output, file names, env values, model output or history.

## What I checked

- **Where the routed text comes from.** `route()` is called only from `Repl._reply` on the user's own stripped line, and only when there is no prefix (`target/src/nl_shell/repl.py:141-146`). `\cmd` input skips the router, as before (`repl.py:147-151`). No untrusted text reaches `_reads_like_english` or `_has_unbalanced_single_quote` (`target/src/nl_shell/router.py:87-104`).
- **What a wrong route can cause.** A COMMAND route still ends at the gate (today it shows `COMMAND_NOT_YET`; the gate comes with #78). A NATURAL_LANGUAGE route goes to `_propose`, and the proposal still goes through the strict parser, with the gate and confirm to follow. The threat model's scale rates "the intent classifier routing input to the wrong mode" as the lowest band, and lists the classifier as lower priority because "a wrong route still goes through the gate". The patch moves no trust boundary and does not touch the gate, PTY/sudo, taint, logging or rendering. Gate T2 agrees: "no security-relevant path touched" (`gate-logs/T2-threat-model.log`).
- **Typed secrets reaching model context.** The new rule sends more typed lines to the model than before. I looked for a command line holding a secret that would now go to the model instead of bash. Rule 3 rejects any word starting with `-` and any of `=`, `$`, `/`, `"` (`router.py:100-103`), so `-pSECRET`, `TOKEN=…`, `$VAR` and URLs all stay commands. A line that reaches the model has to be 4+ plain words with an English function word, or hold an odd `'` with no `"` or `\`. Either way it is the user's own typed request, sent to the local model (or to the dev teacher only behind `--dev-teacher`). This is the same exposure any natural-language request already has. Rule 1's quote signal overriding rule 3 (`find . -name it's`, `find what's in ~/src`) only affects lines bash would leave hanging at an open quote anyway. No finding.
- **First-token resolution.** `_is_command_name` (`router.py:107-112`) is the old logic moved into a helper with no change in behaviour: builtin set, `is_executable_file` for tokens holding `/`, else `shutil.which`. `$PATH` is still read on every call. `first_token` is unchanged, so its second caller (`failure_classes.py`, whose privilege check is text-only) is not affected.
- **Crash or hang.** The new helpers only use `str.count`, `str.split`, set lookups and one pass over the characters: linear time, no regex, no lexer. They cannot raise on unbalanced quotes or odd Unicode. The existing `what's using port 80` vector and the new `find what's using port 80`, `grep it\'s x y` and `git commit -m "wip` vectors exercise the unlexable cases (`target/tests/test_repl.py:99-125`). C4 and T3 are green (`gate-logs/C4-verify.log`, `gate-logs/T3-suite.log`).
- **Test coverage of an attacker case.** This change is about usability, not security, so it needs no attacker-path test.

## Findings

No security findings. The diff touches no input the threat model calls untrusted. The worst outcome of a bug here is a misroute, which the threat model rates lowest, and the gate still sees every command.
<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] T5 Judgment — Confirm affected-path prior art across merged history and closed/rejected work before sign-off — the supplied target contains only one synthetic base commit and no remotes, so the brief's prior-art claim cannot be independently established; target/src/nl_shell/router.py:115, target/tests/test_repl.py:129.
- [x] Validation — fitness-to-purpose — Accept the specified heuristic's usability tradeoff — short English and metacharacter-bearing sentences still route as commands, while apostrophes can override shell-looking syntax; target/src/nl_shell/router.py:22, target/tests/test_repl.py:124.
- [x] The `.lower()` in rule 4 (`src/nl_shell/router.py:104`) is not tested. If I remove it, all vectors still pass. Then `Find The Big Files In My Home` would stay natural language only by luck: `Find` is not on `$PATH`. And `ls The Big Files Here` (resolved first word, function word only in title case) would flip to COMMAND without any test failing. Fix: add a vector like `watch The logs For errors` → natural language.
- [x] 16 of the 18 shell metacharacters in `SHELL_METACHARACTERS` (`src/nl_shell/router.py:75`) are not pinned one by one. Removing any single one of `& ; < > $ * = ( ) { } [ ] ~ / backtick` from the set leaves every vector green. `~` and `/` only appear together in `find big files in ~/src`, so each one hides the loss of the other. A later edit that drops `$` or `=` would quietly send `grep the $HOME in x` or `find the x in a=b` to the model. This is a low-severity test gap, not a bug in the patch. A small parametrized test, one line per character, would close it.
- [x] The spec'd function-word list misroutes some plausible real commands. I ran these through the patched `route()` with the commands on a fake `$PATH`: `make all check install`, `cat a b c`, `touch a b c d`, `git add the file`, `grep error in log.txt` and `time make all in here` all route as natural language. The words `a`, `all`, `the` and `in` are common shell operands (file names, make targets). The patch follows the brief to the letter (brief §Design rule 4), and `\cmd` forces bash. Still, a human should confirm that `a` and `all` belong in the list. This is the brief's choice, not a builder slip.
- [x] A false natural-language route sends the raw line to the model backend, which may be remote. The brief treats this as only a usability cost ("costs one model call"). The quote signal overrides every other rule (`src/nl_shell/router.py:93-94`), so a real command with a stray apostrophe goes to the model whatever it contains, as long as it has no `"` or `\`. For example, `grep -c ' file`, `sed s/'//g f` and `git checkout -- it's` all route as natural language. Rule 3 stops most lines that hold secrets (`=`, `-`, `$`), but the quote path skips rule 3. Whether that matters depends on the backend's privacy model. ADR-0013 only covers the command side of a misroute. This is a scope call for a human, not something to fix in this patch.
- [x] **The "peer to mirror" points at a detection that never fires for the vector it has to serve.** The brief says: "the existing `first_token` `ValueError` branch (`src/nl_shell/router.py:38-48`) is where an unbalanced quote is already detected; the new signal reuses that detection rather than re-lexing the line." But `first_token` calls `lexer.get_token()` only once (`router.py:40-43`). With `whitespace_split = True`, shlex stops reading at the first whitespace after a word, so it only raises `ValueError` when the bad quote is *inside the first word*. That is why the existing vector `what's using port 80` (`tests/test_repl.py:100`) hits the branch. For the new vector `find what's using port 80`, `get_token()` returns `"find"` and never reads `what's`, so there is no `ValueError` and nothing to reuse. Following the brief literally gives a red test on that vector. Do has to lex the whole line, which is the "re-lexing" the brief rules out. Revise the Citations line: name the full-line lex as part of the change, or drop the "rather than re-lexing" constraint.
- [x] **A `ValueError` is not the same as "an unbalanced single quote", and the brief treats them as one.** In posix mode, shlex raises `ValueError` for an unclosed double quote ("No closing quotation") and for a trailing backslash ("No escaped character") as well as for an unclosed `'`. The Design section says an "unbalanced **single** quote (the `ValueError` branch in `first_token`)" is a natural-language signal "on its own". Two readings follow: (a) any lexer error means natural language, so `git commit -m "wip` routes to the model, or (b) only an unclosed `'` does. The brief doesn't choose, and no vector pins either one. Rule 3 rejects double quotes, but the quote signal is described as separate from the four conditions, so rule 3 doesn't settle it. Add one vector, or one sentence, that fixes which errors count.
- [x] **How the quote signal ranks against the other conditions is unspecified.** "On its own" could mean it overrides rule 1 (`echo it's fine` → natural language?), rule 3 (`find . -name what's` → natural language despite the `-`?) and the "first token resolves" precondition. The brief also doesn't say whether it is checked before the builtin/`$PATH` lookup (`router.py:61-66`) or only after it. None of the ten vectors decides this, so two implementations can both pass the success criterion while routing these lines differently. Do and Check will each guess. State the order explicitly (e.g. "checked first, overrides rules 1–4"), or add one `echo …'…` vector.
- [x] **`first_token` has a second caller the brief doesn't mention.** `src/nl_shell/failure_classes.py:46` imports `first_token`, and `failure_classes.py:388` relies on it returning a plain `str`, with the whitespace fallback on bad quoting. If Do follows the "reuse the `ValueError` branch" advice by changing `first_token`'s return type or behaviour (e.g. to report the quote error), it silently changes `_unresolved_word` in a module the scope never lists. Add to the brief: `first_token`'s signature and behaviour stay unchanged; the new signal lives in `route()` or a new helper. Name `tests/test_failure_classes.py` as a suite that must stay green.
- [x] **"Words" is not defined, and the rules depend on it.** Rule 2 ("at least 4 words"), rule 3 ("no word starts with `-`") and rule 4 (function-word match, lowercased) all count "words", but the brief doesn't say whether that means `str.split()` or shlex tokens. The two differ on quoted input (`find 'my big file' in here`) and on the unbalanced-quote lines, where shlex can't split at all. The ten vectors don't tell the two apart, so this won't break the criterion, but it leaves an undocumented edge that the new docstring ("what it still misses") is meant to describe. One line in Design would close it.
- [x] **Small accuracy point in Ordering note / Depends on.** The issue says "**Depends on** #14 (input-mode prefix dispatch, which also changes `src/nl_shell/router.py`)". The brief sets `Depends on: none` because #14 is merged, and the target bears that out: `src/nl_shell/input_modes.py` exists and `repl.py:142-151` dispatches `\cmd`. But #14 landed in `input_modes.py`/`repl.py`, not `router.py`, which matches the brief's own prior-art line ("`router.py` → only dc784f0"). So calling it "the other change to `router.py`" is wrong. It doesn't block anything; it's just inconsistent within the brief.
- [x] size backstop — this slice is behaving oversized: 2 round(s) already spent (threshold 2). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.
- [x] T5 Judgment — Confirm the path-specific prior-art results remain current for the router, REPL tests and architecture document — the brief records router/test history and closed-PR checks, but this target has only one synthetic base commit and no remote, so merged/rejected-work overlap cannot be independently settled (brief.md:58; target/docs/design/architecture/05-building-block-view.md:75).
- [x] The word list in the brief includes one-letter and common-argument words, so some real commands now route as natural language. Checked against the patched router: `git add a b c`, `touch a b c`, `ls a b c d`, `cp this that to` and `git log the main branch` all return `natural_language` (the cause is `a`/`this`/`the` in `FUNCTION_WORDS`, `router.py:78-83`). The brief rates a false natural-language route as one model call, and `\cmd` still forces bash, so this costs usability, not safety. But `a` as a filename or branch argument is common. Whether to drop `a` (and maybe `to`/`on`/`by`, which also show up as git refs and filenames) is a decision on the spec, not a builder slip. The patch follows the brief exactly.
- [x] T5 Judgment — Confirm the path-specific merged-history and closed/rejected-work search remains sufficient — the brief records searches for router.py and test_repl.py, but this disposable target exposes only one synthetic base commit and cannot independently establish remote or rejected-work history (brief.md:58).
- [x] The function-word list in the brief includes `a`, `in`, `this`, `that` and `the`, all of which are common file and branch names. So ordinary commands now route as natural language. Probed with the real `route()`: `mv a b c`, `cat a b c`, `rm this that other`, `cp in out backup` and `git add the README` all route as NATURAL_LANGUAGE (`target/src/nl_shell/router.py:78-83,104`). The code does what the brief asks, and the brief accepts this cost (a false NL route costs one model call, and `\cmd` forces bash). But single-letter arguments like `a` are common in real typing, and the new docstring's "Known limitations" (`router.py:22-25`) only lists failures in the other direction. A human should decide whether to drop `a` from the list, or at least name this direction in the docstring.
- [x] Balanced single quotes are not treated as shell syntax. Rule 3's metacharacter set leaves out `'` (`target/src/nl_shell/router.py:75`), as the brief specifies. So a quoted command routes as natural language as long as it has no `-` word: `ssh host 'ls the dir in home'` and `grep 'the error' in logs` both go to NL. A human should decide whether a balanced `'…'` pair should count as a metacharacter.
- [x] Typographic apostrophes (`’`, U+2019, which phones and some editors insert) do not trigger the quote signal (`target/src/nl_shell/router.py:88`). `find what’s using port 80` routes as COMMAND, while the ASCII form routes as NL. This is outside the brief's spec, so it is a scope question: treat `’` as a natural-language signal, or leave it.

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
- By / date: Eduard Ralph / 2026-10-23

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 6 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)
- Follow-up: router test gaps — the rule-4 `.lower()` (`router.py:104`) is untested (add e.g. `watch The logs For errors` → NL), and 16 of 18 `SHELL_METACHARACTERS` (`router.py:75`) are not pinned one by one (add a parametrized per-character test).
- Follow-up (#40): English that still reaches the shell — short sentences (<4 words), lines with shell metacharacters, `-` words, or no function word route as COMMAND; this direction matters more than false NL routes.

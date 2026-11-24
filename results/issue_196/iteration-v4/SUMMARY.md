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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (189 of 189 failed), green with it
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

Review #196: add the fail-closed AST policy gate’s shell layer, conservative command/live stubs, and conformance tests.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The shell-layer contract and explicit sibling exclusions give this increment a bounded acceptance target; src/nl_shell/gate/parse.py:15 and src/nl_shell/gate/rules.py:3 agree with brief.md. |
| C2 Reproduction (red pre-fix) | PASS | Frozen execution shows all 189 feature tests fail with production changes reverted, including missing gate imports; gate-logs/C4-verify.log:16 and gate-logs/C4-verify.log:6912. |
| C3 Change | PASS | The patch supplies the declared package, dependency pins and vectors without REPL wiring; independent AST checks passed for all nine new Python files and both TOML files parsed; pyproject.toml:17 and src/nl_shell/gate/__init__.py:26. |
| C4 Verification (red→green) | PASS | Log-supported rather than independently reproduced: 189 tests pass patched and 189 fail reverted; this sandbox has neither pytest nor either tree-sitter module, so stash/retest cannot yield meaningful evidence here; gate-logs/C4-verify.log:14 and gate-logs/C4-verify.log:6912. |
| C5 Causal adequacy | NEEDS-HUMAN | Approve decision C and the stricter descriptor and quote-blind character rejection policies as acceptable v1 raises — they intentionally refuse additional user commands; docs/design/specs/policy-gate/v1.md:238, src/nl_shell/gate/__init__.py:8 and src/nl_shell/gate/parse.py:676. |
| T1 Structure | PASS | Invocation/context records and separate command/live hooks provide the declared extension points for the sibling work; src/nl_shell/gate/parse.py:241 and src/nl_shell/gate/__init__.py:138. |
| T2 Shape | PASS | The security-path scanner reports a threat-model update, and source inspection confirms explicit parser, descriptor and residual-risk coverage; gate-logs/T2-threat-model.log:10 and .oss-scanner/threat_model.md:114. |
| T3 Runtime | PASS | Frozen full-suite execution reports 1290 passed, one skipped and one forkpty warning; actual runtime dependencies were exercised there, but are absent in this reviewer sandbox; gate-logs/T3-suite.log:35. |
| T4 Contribution | N/A | Contribution artifacts are absent by design; the substantive contribution audit must rerun at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm dependency licensing and path-based prior art across merged and closed/rejected work — the disposable target contains only one synthetic base commit, so its path-history search cannot establish that history; pyproject.toml:19 and brief.md:139. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether this unwired shell-layer increment is fit for its staged purpose, accepting documented parser latency and unresolved dynamic redirect/arithmetic cases pending sibling work — passing unit tests do not establish complete shell enforcement; .oss-scanner/threat_model.md:120, .oss-scanner/threat_model.md:126 and src/nl_shell/gate/__init__.py:26. |

Evidence limits: all four supplied gate logs were read. Independent source syntax/TOML checks passed; runtime and red→green verdicts rely on the captured executions, not fresh runs. The target is readable and matches the patched layout. No implementation defect was established in this review. No capability-probe/load-time symptom guard was identified; parser-mismatch refusals enforce the declared fail-closed syntax policy.

Prior art: `git log --all -- src/nl_shell/gate pyproject.toml tests/test_policy_gate.py` returns only the synthetic pre-fix base. The brief describes a rejected predecessor and carries forward its defects, but provides no path-based merged/closed-work search evidence; human confirmation remains owed above. INTEGRATION.md is not present among the supplied target files; the brief’s explicit human-only licensing and rule-change requirements are retained.
<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue #196, round 4

I could run the gate. tree-sitter 0.26.0 and tree-sitter-bash 0.25.1 came from the local uv cache into a scratch venv, and I compared each result with real bash 5.3.9 on this host. pytest was not available, so I did not re-run the suite. I read `gate-logs/C4-verify.log` instead. The red leg fails all 189 tests on `ModuleNotFoundError: nl_shell.gate`. That is expected for a new package, and the brief allows it (imports sit inside the test functions). It is not a refutation. The green leg runs the production `classify` and `parse.walk`, not a copy.

Most round-3 fixes hold. I could not break these:
- funsub: `${ x; }`, `${|…}`, tab, newline, inside `"…"` and in here-doc bodies all fail closed. bash rejects `${(`, `${;` and `${&` as bad substitutions, so the `_FUNSUB` regex at `parse.py:89` is complete for 5.3.9.
- Quoted here-doc delimiters: `<<E\F` gives the right body and `rm x` is reached. `<<E'F'`, `<<"E"F`, a stray `E ` or `E<tab>` end line, a here-doc in `$(…)` ended by `E)`, and two here-docs on one line all fail closed.
- `"$\⏎(…)"` and a split `{f\⏎d}>x` fail closed.
- `{a[0]}>x` and `{fd}<<<x` are rejected.
- `/dev/fd/3/`, `/dev/./fd/3`, `"/dev/fd/"3`, `/dev/fd/\3`, `/dev/fd/[3]`, `/dev/?(fd)/3` and the `/proc/self/root/` forms are all rejected.

What I could break:

- NEEDS-HUMAN [impl] — **An extglob redirect target that opens fd 3 is not rejected.** `src/nl_shell/gate/parse.py:72` (`_GLOB = "*?["`) and `_pattern` at `:396-408` treat only `* ? [` and braces as patterns. With extglob on, bash also globs `@(…)`, `+(…)` and `!(…)`. Interactive bash on Ubuntu has extglob on: `/usr/share/bash-completion/bash_completion:45` runs `shopt -s extglob`, and `bash -ic 'shopt extglob'` prints `on` here. I checked with real bash: `shopt -s extglob; exec 3>f; echo via-plus >/dev/+(fd)/3` writes to `f` through fd 3. The gate gives `classify("echo x >/dev/@(fd)/3")` → `mutating`, `rejected=False`, and the same for `+(fd)` and `!(null)`. Only the generic "unparseable" floor applies, because tree-sitter cuts the target at `(` into `>/dev/@`. This misses the round-3 instruction "reject globbed redirect targets", and it makes `threat_model.md:126` ("or a target bash would glob … is rejected") false. Fix: reject a redirect when its target, or the bytes right after it, contain an unquoted `[@+!?*](`. Or reject any redirect inside an unparseable tree, the same way here-docs are handled at `parse.py:654-657`. Add `>/dev/@(fd)/3`, `>/dev/+(fd)/3` and `>/dev/!(x)/3` to `tests/test_policy_gate.py:303`.

- NEEDS-HUMAN [impl] — **The parse-time figure in the threat model is too low by about 5×.** `.oss-scanner/threat_model.md:120-122` and `parse.py:46-47` say the quadratic worst case is "`${` repeated: about 2.4 s at this cap". Measured here at the 64 KiB cap: `"${"*n` takes 3.0 s, `"a=("*n` 7.7 s, and `"$["*n` **12.7 s** (then `mutating`, unparseable). The round-3 sign-off asked for this wording to be accurate. Fix: name `$[` as the worst known input with its real time. Or bound the parse itself: tree-sitter 0.26's `Parser.parse` takes a `progress_callback` that can cancel, and a cancelled parse can be treated as decision C. Then the "total-work budget across the whole classification" covers parsing too. Add a timing test for `"$["*n`.

- NEEDS-HUMAN [impl] — **`/proc/<pid>/cwd/` is an absolute literal path that can open a descriptor, and the gate does not reject it.** `_descriptor_path` (`parse.py:82-85`, `:496-520`) unwraps `/proc/<x>/root/` but not `/proc/<x>/cwd/`. Real bash: `exec 3>f; cd /dev/fd && echo via-proc-cwd >/proc/self/cwd/3` writes to `f`. The gate gives `classify("echo x >/proc/self/cwd/3")` → `mutating`, not rejected. `threat_model.md:124-127` says a literal target path that opens a descriptor is rejected, and only *relative* paths are excused. This is an absolute path. The attack does need a `cd` first, so it sits near the documented cwd-state gap. Fix: treat any target under `/proc/<x>/cwd` (and `/proc/<x>/task/<t>/cwd`) as `"?"` (rejected), the same way `..` is handled at `:505-508`. Or reword the threat model to cover it.

- Not a refutation, just a note: fail-closed is over-broad for some ordinary commands. `cat <<E && cat <<F …`, `cat <<E; rm z …` and `<<E"F"` all become `privileged`/rejected because `parse.py:654-657` fails closed on any here-doc in a tree with an ERROR node. This matches the round-3 instruction. I list it only so sign-off knows that normal two-here-doc lines will be refused.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory): ast-policy-gate-shell-layer, round 4

**Attacker-reachable inputs this diff touches:** the command text passed to `nl_shell.gate.classify`, which is either a model proposal (untrusted; `.oss-scanner/threat_model.md` "Where untrusted input enters") or typed input. The threat model, as changed by this patch, puts any place tree-sitter-bash reads text differently from bash in scope as a gate bypass until #191 (`.oss-scanner/threat_model.md:240-241`). The gate is not wired to the REPL yet (#78), and the stub command layer floors every command at `mutating`. So nothing below runs unconfirmed today. Each finding becomes Critical once #197/#198 let a command be `read-only`.

I probed with the pinned `tree-sitter==0.26.0` / `tree-sitter-bash==0.25.1`, installed offline into my sandbox, and with real bash 5.3.9.

## Findings

- NEEDS-HUMAN [impl] — **High** ("a privileged or destructive step is classed lower"; the step is not classed at all). `src/nl_shell/gate/parse.py:653-661` and `:824-854`. **Two here-docs joined by `|`, `&&` or `||` on one line hide a command from the gate.** Input: the model's proposal. bash reads here-doc bodies in the order the operators appear (`A`, then `B`). tree-sitter-bash nests the second statement inside the first redirect (`(heredoc_redirect (heredoc_start) (pipeline … (heredoc_redirect …)) (heredoc_body) (heredoc_end))`), so it gives the first body to `B` and the later lines to `A`. `_check_heredoc_end` checks each here-doc on its own, so both pass. Reproducer, confirmed in bash and in the gate:
  ```
  cat <<A | cat <<B
  x
  A
  y
  B
  echo RAN7-HIDDEN
  A
  ```
  bash prints `y`, then **runs `echo RAN7-HIDDEN`**. The gate returns `mutating`, `rejected=False`, reasons `['not allowlisted']`, with two invocations: `cat` with literal stdin `'x\nA\ny\n'` and `cat` with literal stdin `'echo RAN7-HIDDEN\n'`. The hidden line is never handed to the command layer. Its text is also recorded as *literal here-doc text*, which child-3's here-doc exemption is meant to trust. The same holds for `cat <<A && cat <<B …`, `cat <<A || cat <<B …` and `cat <<A | sudo tee /x <<B …` (there the gate gives `sudo tee` the wrong body). This breaks the threat-model claim this patch adds (`threat_model.md:130-132`: the gate fails closed on "a here-document whose end line the parser and bash may not agree on"). Fix: fail closed when a `heredoc_redirect` holds another `heredoc_redirect` in its continuation, or more generally check that here-doc bodies come in the same source order as their `heredoc_start` nodes. Test: add the case above, and its `&&` / `||` forms, as decision-C cases next to the existing here-doc mismatch tests. The current pipeline cases (`tests/test_policy_gate.py:545-570`) have only one here-doc each.

- NEEDS-HUMAN [impl] — **High** on the scale's closest row ("printed text forges a control-channel record"); a confirm is still needed today. `src/nl_shell/gate/parse.py:396-408` (`_pattern`) and `:684-693`. **An extglob pattern in the directory part of a redirect target opens fd 3 and is not rejected.** Input: the model's proposal. nl-shell's bash sources `~/.bashrc` (`src/nl_shell/session.py:3`), and Ubuntu's bash-completion runs `shopt -s extglob` (`/usr/share/bash-completion/bash_completion:45`; `bash -ic 'shopt extglob'` shows `on` here). With extglob on, bash globs `>/dev/+(fd)/3` into `/dev/fd/3`. I confirmed this: `shopt -s extglob; exec 3>f; echo via-plus-dir >/dev/+(fd)/3` writes to `f`, and the `@(fd)` form does too. tree-sitter-bash splits at `(` into an ERROR node, so the redirect target is just `/dev/+` or `/dev/@`. That is neither a descriptor path nor a pattern (`_GLOB` is `*?[`), so the gate returns `mutating`, `rejected=False` for `echo x >/dev/@(fd)/3`, `>/dev/+(fd)/3`, `>/proc/@(self)/fd/3`, `>/@(dev)/fd/3` and `>/dev/!(null)/3`. The round-3 sign-off asked for globbed redirect targets to be rejected (brief.md:179), and the threat model now says a target "bash would glob" is rejected (`threat_model.md:126`). When the pattern is in the last part (`>/dev/fd/@(3)`), it is rejected only by luck: `/dev/fd/@` reads as a non-numeric descriptor. Fix: treat a file-redirect target followed straight away by `(`, whose text ends in one of `?*+@!`, as a pattern. Or more simply, reject any file redirect inside a tree with an ERROR node. Test: add `echo x >/dev/+(fd)/3` and `echo x >/dev/@(fd)/3` to the descriptor rejection list (`tests/test_policy_gate.py:~300-315`).

## Checked, no finding

- Round-3 fixes all hold against the pinned parser: `>/dev/f?/3`, `>/proc/self/root/dev/fd/3`, `/proc/self/task/1/root/…`, `/proc/thread-self/fd/3`, `/dev/./fd/3`, `/dev/fd//3`, `/dev/fd/0003`, `/dev/fd/+3`, `/dev/fd/3/`, quoted forms (`"/dev/fd/3"`, `/dev/fd/'3'`), `&>`, `>&`, `<>` to `/dev/fd/3`, `{a[0]}>x`, `"$\⏎(…)"` and `${ cmd; }` are all rejected or fail closed. `/dev/fd/1`, `/dev/stderr` and `/proc/self/root/dev/fd/2` are not rejected, which is correct.
- Here-doc line continuation: a body line `E\` followed by an empty line, which bash joins into the delimiter `E` (confirmed: bash ends the here-doc there and runs the next line). It fails closed in plain and `<<-` forms, and at end of file. `cat <<A <<B` and `cat <<A; cat <<B` on one line fail closed through the ERROR check. A here-doc inside `$(…)` inside another here-doc fails closed.
- `cd /dev/fd; echo x >3` and `>$F` are not rejected. Both are known gaps the threat model now lists (`threat_model.md:126-127`), and the brief says not to widen them. Not raised.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C5 Causal adequacy — Approve decision C and the stricter descriptor and quote-blind character rejection policies as acceptable v1 raises — they intentionally refuse additional user commands; docs/design/specs/policy-gate/v1.md:238, src/nl_shell/gate/__init__.py:8 and src/nl_shell/gate/parse.py:676.
- [ ] T5 Judgment — Confirm dependency licensing and path-based prior art across merged and closed/rejected work — the disposable target contains only one synthetic base commit, so its path-history search cannot establish that history; pyproject.toml:19 and brief.md:139.
- [ ] Validation — fitness-to-purpose — Decide whether this unwired shell-layer increment is fit for its staged purpose, accepting documented parser latency and unresolved dynamic redirect/arithmetic cases pending sibling work — passing unit tests do not establish complete shell enforcement; .oss-scanner/threat_model.md:120, .oss-scanner/threat_model.md:126 and src/nl_shell/gate/__init__.py:26.
- [ ] **An extglob redirect target that opens fd 3 is not rejected.** `src/nl_shell/gate/parse.py:72` (`_GLOB = "*?["`) and `_pattern` at `:396-408` treat only `* ? [` and braces as patterns. With extglob on, bash also globs `@(…)`, `+(…)` and `!(…)`. Interactive bash on Ubuntu has extglob on: `/usr/share/bash-completion/bash_completion:45` runs `shopt -s extglob`, and `bash -ic 'shopt extglob'` prints `on` here. I checked with real bash: `shopt -s extglob; exec 3>f; echo via-plus >/dev/+(fd)/3` writes to `f` through fd 3. The gate gives `classify("echo x >/dev/@(fd)/3")` → `mutating`, `rejected=False`, and the same for `+(fd)` and `!(null)`. Only the generic "unparseable" floor applies, because tree-sitter cuts the target at `(` into `>/dev/@`. This misses the round-3 instruction "reject globbed redirect targets", and it makes `threat_model.md:126` ("or a target bash would glob … is rejected") false. Fix: reject a redirect when its target, or the bytes right after it, contain an unquoted `[@+!?*](`. Or reject any redirect inside an unparseable tree, the same way here-docs are handled at `parse.py:654-657`. Add `>/dev/@(fd)/3`, `>/dev/+(fd)/3` and `>/dev/!(x)/3` to `tests/test_policy_gate.py:303`.
- [ ] **The parse-time figure in the threat model is too low by about 5×.** `.oss-scanner/threat_model.md:120-122` and `parse.py:46-47` say the quadratic worst case is "`${` repeated: about 2.4 s at this cap". Measured here at the 64 KiB cap: `"${"*n` takes 3.0 s, `"a=("*n` 7.7 s, and `"$["*n` **12.7 s** (then `mutating`, unparseable). The round-3 sign-off asked for this wording to be accurate. Fix: name `$[` as the worst known input with its real time. Or bound the parse itself: tree-sitter 0.26's `Parser.parse` takes a `progress_callback` that can cancel, and a cancelled parse can be treated as decision C. Then the "total-work budget across the whole classification" covers parsing too. Add a timing test for `"$["*n`.
- [ ] **`/proc/<pid>/cwd/` is an absolute literal path that can open a descriptor, and the gate does not reject it.** `_descriptor_path` (`parse.py:82-85`, `:496-520`) unwraps `/proc/<x>/root/` but not `/proc/<x>/cwd/`. Real bash: `exec 3>f; cd /dev/fd && echo via-proc-cwd >/proc/self/cwd/3` writes to `f`. The gate gives `classify("echo x >/proc/self/cwd/3")` → `mutating`, not rejected. `threat_model.md:124-127` says a literal target path that opens a descriptor is rejected, and only *relative* paths are excused. This is an absolute path. The attack does need a `cd` first, so it sits near the documented cwd-state gap. Fix: treat any target under `/proc/<x>/cwd` (and `/proc/<x>/task/<t>/cwd`) as `"?"` (rejected), the same way `..` is handled at `:505-508`. Or reword the threat model to cover it.
- [ ] **High** ("a privileged or destructive step is classed lower"; the step is not classed at all). `src/nl_shell/gate/parse.py:653-661` and `:824-854`. **Two here-docs joined by `|`, `&&` or `||` on one line hide a command from the gate.** Input: the model's proposal. bash reads here-doc bodies in the order the operators appear (`A`, then `B`). tree-sitter-bash nests the second statement inside the first redirect (`(heredoc_redirect (heredoc_start) (pipeline … (heredoc_redirect …)) (heredoc_body) (heredoc_end))`), so it gives the first body to `B` and the later lines to `A`. `_check_heredoc_end` checks each here-doc on its own, so both pass. Reproducer, confirmed in bash and in the gate:
- [ ] **High** on the scale's closest row ("printed text forges a control-channel record"); a confirm is still needed today. `src/nl_shell/gate/parse.py:396-408` (`_pattern`) and `:684-693`. **An extglob pattern in the directory part of a redirect target opens fd 3 and is not rejected.** Input: the model's proposal. nl-shell's bash sources `~/.bashrc` (`src/nl_shell/session.py:3`), and Ubuntu's bash-completion runs `shopt -s extglob` (`/usr/share/bash-completion/bash_completion:45`; `bash -ic 'shopt extglob'` shows `on` here). With extglob on, bash globs `>/dev/+(fd)/3` into `/dev/fd/3`. I confirmed this: `shopt -s extglob; exec 3>f; echo via-plus-dir >/dev/+(fd)/3` writes to `f`, and the `@(fd)` form does too. tree-sitter-bash splits at `(` into an ERROR node, so the redirect target is just `/dev/+` or `/dev/@`. That is neither a descriptor path nor a pattern (`_GLOB` is `*?[`), so the gate returns `mutating`, `rejected=False` for `echo x >/dev/@(fd)/3`, `>/dev/+(fd)/3`, `>/proc/@(self)/fd/3`, `>/@(dev)/fd/3` and `>/dev/!(null)/3`. The round-3 sign-off asked for globbed redirect targets to be rejected (brief.md:179), and the threat model now says a target "bash would glob" is rejected (`threat_model.md:126`). When the pattern is in the last part (`>/dev/fd/@(3)`), it is rejected only by luck: `/dev/fd/@` reads as a non-numeric descriptor. Fix: treat a file-redirect target followed straight away by `(`, whose text ends in one of `?*+@!`, as a pattern. Or more simply, reject any file redirect inside a tree with an ERROR node. Test: add `echo x >/dev/+(fd)/3` and `echo x >/dev/@(fd)/3` to the descriptor rejection list (`tests/test_policy_gate.py:~300-315`).
- [ ] **The tracker record is missing, so the problem statement and the "ignored context" check could not be done.** `notes.json` and `sources/` are not in the bundle I was given. Several parts of the brief rest only on that thread: "decision A's floor", "decision B (child-2)", "Decision C", "child-2" and "child-3", the sibling split (#190/#191/#192) and the "v2 regression". None of the decisions A/B/C appear anywhere in the target. A grep for `decision [ABC]` and `could not class` matches only `.github/triage/triage_priority.py:42,402`, which is unrelated. The human should confirm these decisions really are in the thread, or the brief should state them inline.
- [ ] **The "§7 stub proof" criterion cannot fail.** The brief ships `rules.py` as a stub where "every simple command is `mutating`, reason 'not allowlisted'". With that stub, nothing reaches `gate/live.py` as `read-only`. So "no case returns `read-only`" passes even if `live.py` is deleted or returns `read-only`. The same applies to "§1.7 … a label never lowers the class": every command is already at least `mutating`, so a label below that can never be observed lowering anything. The tests need to exercise `live.py` directly, for example by monkeypatching `rules` to return `read-only` and asserting that live turns it into `mutating` with "live-session resolution not implemented". The label test needs a matching fixture. Otherwise these two bullets pass whether or not the code works.
- [ ] **Decision C and the fd rule go beyond the spec. The brief calls them restorations; they are new rules.** `policy-gate/v1` has no internal-error or budget rule. Decision C ("`privileged`, rejected, reason 'could not class'") is new. The spec rejects only "file descriptor 3 or higher" (`docs/design/specs/policy-gate/v1.md:126`). The brief also rejects any descriptor the gate "cannot prove is below 3" (`>&$x`, `<&$fd`, `2>&${FD}`). Both are stricter, so they are probably compatible changes. But the spec's Versioning section (`v1.md:238-241`) says raising a class "MUST be reviewed by a human". The brief does not flag either one for sign-off, and does not plan a spec edit to record them.
- [ ] **The §3 variable rule is underspecified and only partly tested.** The success criterion tests standalone assignments to `PATH`, `IFS`, `LD_PRELOAD` and `GIT_DIR` only. Spec §3 (`v1.md:104-107`) lists about 20 names and patterns (`PS0`–`PS4`, `LD_*`, `GIT_*`, `SUDO_*`, `PYTHON*`, `PERL5*`, `NODE_OPTIONS`, …) and covers them "standalone **or exported**". The brief applies the `variable_assignment`-inside-`declaration_command` handling only to `SUDO_*`. It never says whether `export PATH=./bin` (the setup for spec row 5) gets `session-altering` from the shell layer, or ends up as just `mutating` from the stub, which loses the session-altering warning. The Scope section also never says whether the full §3 list is in this child or in child-2. Do will have to guess.
- [ ] **`gate-vectors.toml` and its loader are a hidden second change that no test checks.** Scope adds `targets/ubuntu-26.04/gate-vectors.toml` "with this child's rows and a vector loader in the style of `src/nl_shell/targets.py:145-247`". No success-criterion bullet says the tests read their cases from that file, or tests the loader (missing file, bad TOML, schema). That is new data, a new module and new review surface with no red→green test. The spec also says a target's vectors file "MUST cover every row" (`v1.md:245-249`), so a partial file under that name does not meet the spec. Either drop it, or add a criterion such as "the tests read every case from the file; the loader rejects malformed entries" and say how the file relates to the full-row requirement.
- [ ] **Two citations do not resolve in the target.** `engine/scripts/run-verify.sh:196` (Falsifiability) and `results/issue_189/iteration-v2/patch.diff` with `parse.py:397,411` (Prior-art) are not in `$PDCA_TARGET`. A glob of `engine/**` and `results/**` matches nothing. They probably live in the PDCA harness checkout. The rule that Do "must cite path:line on the target branch" can't be applied to them, and a Do agent grounded on the target can't open them. Prior-art also says the v2 here-doc handling "is the bug listed above", but the brief never states that bug. The only mention is the bullet header "Stdin context, v2 regression". One sentence describing the v2 defect (stdin of the second pipeline stage recorded as terminal after a here-doc) would close the gap.
- [ ] **The §1.1 check is stricter than the spec, and the brief doesn't say so.** The brief reuses `render.has_hidden` (`src/nl_shell/render.py:136`). That function ignores quoting and covers Cf/Co/Cn/default-ignorable/surrogates (`render.py:113-127`). The spec forbids the listed characters only "outside quotes" (`v1.md:59-61`). That is fine for safety, since it only raises the class or rejects. But it means a proposal like `echo '‮'` is rejected, which differs from the spec text. A sign-off note should record that this deviation is deliberate.
- [ ] **These pinned-version claims can't be checked from the target and are load-bearing.** "tree-sitter-bash 0.25.1 has 59" named node kinds, the compatibility of `tree-sitter==0.26.0` with `tree-sitter-bash==0.25.1`, and "`case x in` parses to an `ERROR` node; `if true; then` to `MISSING "fi"`" are all assertions about third-party wheels. Nothing in the repo backs them up (`pyproject.toml:13-17` has no tree-sitter today). If either pin is wrong, Do stalls on the first install. The success criterion already makes the node-kind test enumerate the kinds at run time, so the brief should drop the hard-coded "59" rather than imply a test depends on it. The pins should be confirmed with one `pip install` before Do starts. The licence question is already deferred to sign-off.
- [ ] size backstop — this slice is behaving oversized: 3 round(s) already spent (threshold 2). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.
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
- Outcome: iterated-to-Do
- Iteration delta (if iterating): Human chose iterate-do and again explicitly overrode the size-backstop recommendation (iterate-plan); do not re-split this round. Fix the confirmed round-4 adversary/security findings, each with a test: - Two here-docs joined by |, &&, || on one line (cat <<A | cat <<B ...): tree-sitter nests the second heredoc_redirect inside the first and mis-assigns bodies, hiding a line from the gate. Fail closed when a heredoc_redirect contains another heredoc_redirect, or when here-doc bodies are not in the same source order as their heredoc_start nodes. Add the |, &&, || reproducers as decision-C cases. - Extglob redirect targets (>/dev/@(fd)/3, >/dev/+(fd)/3, >/dev/!(x)/3, >/proc/@(self)/fd/3, >/@(dev)/fd/3) must be rejected: treat a file-redirect target followed by "(" and ending in one of ?*+@! as a pattern, or reject any file redirect inside a tree with an ERROR node. - /proc/<x>/cwd/ and /proc/<x>/task/<t>/cwd/ redirect targets must be treated as unprovable descriptors (rejected), like "..". - Correct the parse-time figure in the threat model and parse.py comment: worst known input is "$[" repeated (~12.7 s at the 64 KiB cap; "a=(" ~7.7 s, "${" ~3.0 s), or bound the parse via tree-sitter's progress_callback and treat cancellation as decision C. Add a timing test. Keep the threat-model wording accurate to what the code actually rejects. Do not widen behaviour for the still-undecided scope questions (non-literal redirect targets like >$F; arithmetic assignments).
- By / date: Eduard Ralph / 2026-10-23

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 8 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

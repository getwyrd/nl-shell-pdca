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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (78 of 78 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: unverifiable — security-relevant paths changed without a threat-model update: src/nl_shell/gate/__init__.py src/nl_shell/gate/live.py s
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review the new fail-closed AST policy gate shell layer, invocation context, parser pins, stubs, and conformance tests for #196.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The shell-layer scope and deliberate command/live-resolution stubs have explicit success criteria and exclusions; brief.md:28 and brief.md:112. |
| C2 Reproduction (red pre-fix) | PASS | The frozen red leg executes all 78 tests and fails on the absent gate, matching the new-feature baseline; gate-logs/C4-verify.log:2226. |
| C3 Change | PASS | The patch stays within the parser, classification pipeline, staged stubs, vectors and tests authorized by the brief; target/src/nl_shell/gate/__init__.py:106 and target/pyproject.toml:17. |
| C4 Verification (red→green) | PASS | Captured execution shows 78 green tests and 78 red failures without collection errors; this is log-backed evidence, not an independent rerun; gate-logs/C4-verify.log:10 and gate-logs/C4-verify.log:2227. |
| C5 Causal adequacy | PASS | The absent shell layer is supplied with explicit fail-closed handling and shared budget; no capability-probe symptom guard was introduced; target/src/nl_shell/gate/parse.py:234 and target/src/nl_shell/gate/__init__.py:90. |
| T1 Structure | PASS | Separate walker, verdict, command and resolution modules provide the intended sibling extension points without REPL coupling; target/src/nl_shell/gate/__init__.py:118. |
| T2 Shape | NEEDS-HUMAN | Decide whether the new parser input and fail-closed properties require a threat-model update — the security-path scanner found no corresponding update; gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | The captured full suite reports 1179 passed, one skipped and one forkpty warning; local Python lacks pytest and tree_sitter, so independent execution was unavailable; gate-logs/T3-suite.log:34. |
| T4 Contribution | N/A | Contribution artifacts are absent by design and their substantive audit reruns at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Approve decision C, stricter descriptor rejection and quote-blind hidden-character rejection, confirm parser dependency licensing, and settle affected-path prior art across merged and closed/rejected work — the disposable repository has only one base commit and no remotes, so complete history cannot be checked; target/docs/design/specs/policy-gate/v1.md:238, target/pyproject.toml:19, brief.md:127 and brief.md:139. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether this intentionally unwired, always-at-least-mutating shell layer is a suitable foundation for later command and live-session policy work — green component tests do not demonstrate end-to-end execution safety; target/src/nl_shell/gate/__init__.py:25 and brief.md:120. |

Evidence limits: `python3 -m pytest` cannot run here because pytest is absent; importing tree_sitter also fails. No stash cycle was performed because neither leg could execute in this host. The frozen C4 log exercises the actual parser (including grammar enumeration), so the declared tree-sitter-bash dependency was exercised by the gates; no shim or curated replacement is shown. Wrapper absence is expected and is not a patch defect. The complete captured C4 and T3 outputs, and both scanner/contribution logs, were inspected. No target-state mismatch was found.

Prior art: affected-path `git log --all` exposes only the synthetic base commit; `git ls-tree` confirms the gate and policy test were absent there. The brief records a rejected v2 attempt and its stdin bug, but the supplied bundle cannot establish a complete merged/closed-work search. This remains the T5 human decision above.

A direct Bash check, `bash -c 'read -r line <>brief.md; printf "%s\\n" "$line"'`, read the first line of the file. Source inspection confirms `<>` is covered by the `<` prefix at target/src/nl_shell/gate/parse.py:75 and becomes file stdin at target/src/nl_shell/gate/parse.py:557; no finding is raised for it.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue_196 (ast-policy-gate-shell-layer)

Evidence re-run: I installed the pinned `tree-sitter==0.26.0` and `tree-sitter-bash==0.25.1` in a scratch venv and ran `tests/test_policy_gate.py` against `$PDCA_TARGET`: 78 passed. The tests import the real `nl_shell.gate` (no copied code), and they check a reason substring, not only the class, so the green leg has teeth. The C4 red leg (`gate-logs/C4-verify.log`) is 78 `ModuleNotFoundError` failures. That is expected for a new package, but it only shows the module is missing. It says nothing per case. One fd case the tests miss is below.

- NEEDS-HUMAN [impl] — **A move-descriptor redirect to fd 3 or higher is not rejected.** At `src/nl_shell/gate/parse.py:466-476`, a `>&` target that is not all digits and not `-` is treated as "`>&file`", so `>&3-` and `1>&3-` only get "output redirection" (mutating, `rejected=False`). In bash, `[n]>&digit-` *moves* descriptor `digit` onto `n`, so the command writes to fd 3. I confirmed this with real bash: `exec 3>f; echo via-move >&3-` writes to `f`. Probe results: `classify("echo hi >&3-")` gives `mutating False ["output redirection: '>&3-'", ...]`, and the same for `1>&3-`. This breaks the brief's §5 rule ("a descriptor the gate cannot prove is below 3 is rejected"), which row 25 (`echo hi >&3`) exists to enforce. The `<&3-` form is rejected, but only because it falls into the `else` branch at `:478`. Fix: when the target matches `^\d+-$`, check the digits with `_below_three`. Add `>&3-` and `1>&3-` to `test_descriptor_not_provably_below_three_is_rejected` (`tests/test_policy_gate.py:272`).
- NEEDS-HUMAN [human] — **Assignments the parser does not give a `variable_assignment` node skip §3 and §5.** The brief limits the rule to `variable_assignment` nodes (`parse.py:701-711`). But the forms below are syntax the shell layer walks, not commands, so #197's command layer will never see them as invocations. `for` and `expansion` are plain pass-through containers (`parse.py:736-749`):
  - `echo ${SUDO_PROMPT=x}` gives `mutating False`.
  - `for SUDO_PROMPT in x; do :; done` gives `mutating False`.
  - `for PATH in x; do :; done`, `select PATH in a; ...`, `: ${IFS:=x}` and `(( PATH=1 ))` all give mutating, not session-altering.

  The brief's hand-off list for #197 (`export "PATH"=x`, `read`, `printf -v`) names only command-level forms. A human should decide whether these shell-level forms belong to this child or get added to #197's scope, so they don't fall between the two.
- NEEDS-HUMAN [impl] — **The work budget does not cover parsing or the named-fd scan.** `parse.py:240` parses the whole text before any budget is spent. `parse.py:441-443` copies and regex-searches the entire source prefix (`self.source[: node.start_byte]`) for every redirect, which is quadratic. Measured: a 6 MB proposal takes 7.7 s before ending in "could not class". A 2 MB word followed by 6000 `>x` takes 3.1 s. The brief says the budget is "a total-work budget across the whole classification". Fix: cap the input length up front (decision C), and look only at a bounded window of bytes (for example the last 256) before the redirect.
- NEEDS-HUMAN [human] — **T2 is unverifiable: no threat-model update.** `gate-logs/T2-threat-model.log` shows the whole new gate package changed with no edit to `.oss-scanner/threat_model.md`. The brief cites that model's Critical row (`:296`) and High row (`:303`) as the invariant this work restores. A human should decide whether the model needs a new row now (the gate as a parse-differential surface: tree-sitter vs bash, see `cat <<E; rm x` below) or only when #78 wires the gate into the REPL.
- Not a refutation, just noted: some valid bash parses as unparseable in tree-sitter, for example `cat <<E; rm x\nx\nE` gives "unparseable". That fails closed (mutating), so it is safe. It is the kind of mismatch the differential test in #191 should catch.
- I tried to refute these and could not:
  - `classify` never raises. `None`, `bytes` and `int` inputs, a NUL byte, a lone surrogate, and 1000-deep nesting all fail closed to privileged or are rejected.
  - No result is `read-only`.
  - SUDO_ assignments are rejected inside `declare`, `readonly` and `+=` forms.
  - Descriptor 3 or higher is rejected on here-docs, here-strings, function definitions, compound statements, `time` and `!`, and in `>& 3`, `>&03`, `>&'3'`, `>&$((3))` and `{fd}` forms.
  - `>/dev/null` stays exempt only for the exact literal path.
  - The here-doc pipe stdin case (`cat <<E | sudo tee /x`) is handled.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review — ast-policy-gate-shell-layer (#196)

Attacker-reachable inputs this diff touches: **the model's proposal text** (threat model "Where untrusted input enters" item 5), which is what `nl_shell.gate.classify` parses. The gate is not wired to the REPL yet (`src/nl_shell/gate/__init__.py:25`, #78), so nothing here can run a command today. Typed input is trusted. `targets/ubuntu-26.04/gate-vectors.toml` is repo data, also trusted.

I could not run anything: `tree_sitter` / `tree_sitter_bash` are not installed in this sandbox. The findings below come from reading the code and the bash manual, not from a test run.

## What I checked, with no finding

- **No path to `read-only`.** `rules.classify` raises every simple command to at least `mutating` (`src/nl_shell/gate/rules.py:239-244`). `live.resolve` raises anything still `read-only` (`src/nl_shell/gate/live.py:213-220`). An empty or comment-only command is raised to `mutating` too (`src/nl_shell/gate/__init__.py:130-132`). So the Critical row "a non-read-only command runs with no confirm" can't be reached through this diff.
- **Fail closed (decision C).** An unhandled node kind raises `UnhandledNode` (`parse.py:402-404`). Going over the budget raises `BudgetExceeded` (`parse.py:100-103`, `:400-401`). Any `Exception`, including `RecursionError` and `UnicodeError`, becomes `privileged`, rejected (`__init__.py:93-96`). A bad `origin` or `label` also ends up there. The §1.7 label can only raise the class (`__init__.py:91`).
- **§1.1 characters.** A proposal with a hidden character is rejected before parsing (`__init__.py:113-117`). A lone surrogate is encoded with `surrogatepass`, so it does not crash the parse, and it is tested (`tests/test_policy_gate.py:148-149`).
- **Running out of time or memory.** A proposal is capped at 2000 characters (`src/nl_shell/proposal.py:26,131`). The node budget is 20,000 and the depth limit 150. The one cost that grows with the square of the input is `_NAMED_FD.search(self.source[: node.start_byte])` at `parse.py:441-443` (one prefix copy and scan per redirect). It stays small at 2000 characters. If a later caller passes longer text, read only a short window before the redirect.
- **SUDO_PROMPT / SUDO_ASKPASS.** These are rejected whenever a `variable_assignment` node names them, as a prefix, standalone, or inside `export` (`parse.py:489-492`). The array form (`SUDO_PROMPT[0]=x`) is caught through `subscript` (`parse.py:503-507`). Forms with no `variable_assignment` node (`read`, `printf -v`, `export "SUDO_PROMPT"=x`) belong to #197 under the brief, so I don't raise them here.
- **Dependency pins** (`pyproject.toml:19-20`). They are pinned to exact versions. The license question is already listed for sign-off in the brief.

## Findings

- NEEDS-HUMAN [impl] — **High on the threat model's scale ("printed text forges a control-channel record"), but a confirm is still required and the gate is not wired yet.** At `src/nl_shell/gate/parse.py:466-476`, the fd rule misses bash's fd-move form `[n]>&digit-` (it moves descriptor `digit` onto `n`, see the bash manual under REDIRECTION). Input: the model's proposal. For `echo hi >&3-`, the target value is `3-`. That is not all digits and not `-`, so the `>&` branch treats it as `&>file` and calls `_output`. The result is `mutating` with an "output redirection" reason, **not rejected**, even though the command writes to fd 3 (the control channel, ADR-0014). This breaks the brief's own rule: "a descriptor the gate cannot prove is below 3 is rejected". `<&3-` is rejected, but only by the catch-all `else` at `:477-478`. `1>&3-` and `>&'3'-` go the same wrong way as `>&3-`. Fix: treat a literal target matching `[0-9]+-` as a descriptor and run it through `_below_three`. Add `echo hi >&3-`, `1>&3-` and `cat <&3-` to `test_descriptor_not_provably_below_three_is_rejected` (`tests/test_policy_gate.py:258-273`). That test lists no move form today. Not confirmed here (no tree-sitter in this sandbox). The new test cases will confirm or refute it.
- NEEDS-HUMAN [human] — **No effect in this diff. It becomes High ("pipes into sudo" must be rejected, ADR-0015) once child-2's sudo-pipe rule reads `Invocation.stdin`.** At `src/nl_shell/gate/parse.py:714-719`, a function body is always walked with `stdin=TERMINAL`. But the body runs with the stdin of the call site. Input: the model's proposal. Example: `f() { sudo tee /x; }; cat <<E | f` (here-doc body `x`). The call `f` gets stdin = pipe, but the `sudo tee /x` invocation is recorded as reading the terminal. That is the same mistake the brief cites as v2's here-doc pipeline bug, moved into a function body. Calling `f` is opaque and the definition is `session-altering`, so the command is still confirmed. But a pipe-into-sudo *rejection* built on this field would not fire, and the sudo password could be fed from the pipe. The brief's `Stdin` sources (terminal / pipe / file / here-doc / here-string) have no "unknown" value for this case. Adding one, or making #197 treat function-body invocations as stdin-unknown, changes the contract the siblings depend on. That is a scope call for the human, not a builder iteration.

No other findings.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T2 Shape — Decide whether the new parser input and fail-closed properties require a threat-model update — the security-path scanner found no corresponding update; gate-logs/T2-threat-model.log:10.
- [ ] T5 Judgment — Approve decision C, stricter descriptor rejection and quote-blind hidden-character rejection, confirm parser dependency licensing, and settle affected-path prior art across merged and closed/rejected work — the disposable repository has only one base commit and no remotes, so complete history cannot be checked; target/docs/design/specs/policy-gate/v1.md:238, target/pyproject.toml:19, brief.md:127 and brief.md:139.
- [ ] Validation — fitness-to-purpose — Decide whether this intentionally unwired, always-at-least-mutating shell layer is a suitable foundation for later command and live-session policy work — green component tests do not demonstrate end-to-end execution safety; target/src/nl_shell/gate/__init__.py:25 and brief.md:120.
- [ ] **A move-descriptor redirect to fd 3 or higher is not rejected.** At `src/nl_shell/gate/parse.py:466-476`, a `>&` target that is not all digits and not `-` is treated as "`>&file`", so `>&3-` and `1>&3-` only get "output redirection" (mutating, `rejected=False`). In bash, `[n]>&digit-` *moves* descriptor `digit` onto `n`, so the command writes to fd 3. I confirmed this with real bash: `exec 3>f; echo via-move >&3-` writes to `f`. Probe results: `classify("echo hi >&3-")` gives `mutating False ["output redirection: '>&3-'", ...]`, and the same for `1>&3-`. This breaks the brief's §5 rule ("a descriptor the gate cannot prove is below 3 is rejected"), which row 25 (`echo hi >&3`) exists to enforce. The `<&3-` form is rejected, but only because it falls into the `else` branch at `:478`. Fix: when the target matches `^\d+-$`, check the digits with `_below_three`. Add `>&3-` and `1>&3-` to `test_descriptor_not_provably_below_three_is_rejected` (`tests/test_policy_gate.py:272`).
- [ ] **Assignments the parser does not give a `variable_assignment` node skip §3 and §5.** The brief limits the rule to `variable_assignment` nodes (`parse.py:701-711`). But the forms below are syntax the shell layer walks, not commands, so #197's command layer will never see them as invocations. `for` and `expansion` are plain pass-through containers (`parse.py:736-749`):
- [ ] **The work budget does not cover parsing or the named-fd scan.** `parse.py:240` parses the whole text before any budget is spent. `parse.py:441-443` copies and regex-searches the entire source prefix (`self.source[: node.start_byte]`) for every redirect, which is quadratic. Measured: a 6 MB proposal takes 7.7 s before ending in "could not class". A 2 MB word followed by 6000 `>x` takes 3.1 s. The brief says the budget is "a total-work budget across the whole classification". Fix: cap the input length up front (decision C), and look only at a bounded window of bytes (for example the last 256) before the redirect.
- [ ] **T2 is unverifiable: no threat-model update.** `gate-logs/T2-threat-model.log` shows the whole new gate package changed with no edit to `.oss-scanner/threat_model.md`. The brief cites that model's Critical row (`:296`) and High row (`:303`) as the invariant this work restores. A human should decide whether the model needs a new row now (the gate as a parse-differential surface: tree-sitter vs bash, see `cat <<E; rm x` below) or only when #78 wires the gate into the REPL.
- [ ] **High on the threat model's scale ("printed text forges a control-channel record"), but a confirm is still required and the gate is not wired yet.** At `src/nl_shell/gate/parse.py:466-476`, the fd rule misses bash's fd-move form `[n]>&digit-` (it moves descriptor `digit` onto `n`, see the bash manual under REDIRECTION). Input: the model's proposal. For `echo hi >&3-`, the target value is `3-`. That is not all digits and not `-`, so the `>&` branch treats it as `&>file` and calls `_output`. The result is `mutating` with an "output redirection" reason, **not rejected**, even though the command writes to fd 3 (the control channel, ADR-0014). This breaks the brief's own rule: "a descriptor the gate cannot prove is below 3 is rejected". `<&3-` is rejected, but only by the catch-all `else` at `:477-478`. `1>&3-` and `>&'3'-` go the same wrong way as `>&3-`. Fix: treat a literal target matching `[0-9]+-` as a descriptor and run it through `_below_three`. Add `echo hi >&3-`, `1>&3-` and `cat <&3-` to `test_descriptor_not_provably_below_three_is_rejected` (`tests/test_policy_gate.py:258-273`). That test lists no move form today. Not confirmed here (no tree-sitter in this sandbox). The new test cases will confirm or refute it.
- [ ] **No effect in this diff. It becomes High ("pipes into sudo" must be rejected, ADR-0015) once child-2's sudo-pipe rule reads `Invocation.stdin`.** At `src/nl_shell/gate/parse.py:714-719`, a function body is always walked with `stdin=TERMINAL`. But the body runs with the stdin of the call site. Input: the model's proposal. Example: `f() { sudo tee /x; }; cat <<E | f` (here-doc body `x`). The call `f` gets stdin = pipe, but the `sudo tee /x` invocation is recorded as reading the terminal. That is the same mistake the brief cites as v2's here-doc pipeline bug, moved into a function body. Calling `f` is opaque and the definition is `session-altering`, so the command is still confirmed. But a pipe-into-sudo *rejection* built on this field would not fire, and the sudo password could be fed from the pipe. The brief's `Stdin` sources (terminal / pipe / file / here-doc / here-string) have no "unknown" value for this case. Adding one, or making #197 treat function-body invocations as stdin-unknown, changes the contract the siblings depend on. That is a scope call for the human, not a builder iteration.
- [ ] T2 security-relevant change also updates the threat model unverifiable — security-relevant paths changed without a threat-model update: src/nl_shell/gate/__init__.py src/nl_shell/gate/live.py s
- [ ] **The tracker record is missing, so the problem statement and the "ignored context" check could not be done.** `notes.json` and `sources/` are not in the bundle I was given. Several parts of the brief rest only on that thread: "decision A's floor", "decision B (child-2)", "Decision C", "child-2" and "child-3", the sibling split (#190/#191/#192) and the "v2 regression". None of the decisions A/B/C appear anywhere in the target. A grep for `decision [ABC]` and `could not class` matches only `.github/triage/triage_priority.py:42,402`, which is unrelated. The human should confirm these decisions really are in the thread, or the brief should state them inline.
- [ ] **The "§7 stub proof" criterion cannot fail.** The brief ships `rules.py` as a stub where "every simple command is `mutating`, reason 'not allowlisted'". With that stub, nothing reaches `gate/live.py` as `read-only`. So "no case returns `read-only`" passes even if `live.py` is deleted or returns `read-only`. The same applies to "§1.7 … a label never lowers the class": every command is already at least `mutating`, so a label below that can never be observed lowering anything. The tests need to exercise `live.py` directly, for example by monkeypatching `rules` to return `read-only` and asserting that live turns it into `mutating` with "live-session resolution not implemented". The label test needs a matching fixture. Otherwise these two bullets pass whether or not the code works.
- [ ] **Decision C and the fd rule go beyond the spec. The brief calls them restorations; they are new rules.** `policy-gate/v1` has no internal-error or budget rule. Decision C ("`privileged`, rejected, reason 'could not class'") is new. The spec rejects only "file descriptor 3 or higher" (`docs/design/specs/policy-gate/v1.md:126`). The brief also rejects any descriptor the gate "cannot prove is below 3" (`>&$x`, `<&$fd`, `2>&${FD}`). Both are stricter, so they are probably compatible changes. But the spec's Versioning section (`v1.md:238-241`) says raising a class "MUST be reviewed by a human". The brief does not flag either one for sign-off, and does not plan a spec edit to record them.
- [ ] **The §3 variable rule is underspecified and only partly tested.** The success criterion tests standalone assignments to `PATH`, `IFS`, `LD_PRELOAD` and `GIT_DIR` only. Spec §3 (`v1.md:104-107`) lists about 20 names and patterns (`PS0`–`PS4`, `LD_*`, `GIT_*`, `SUDO_*`, `PYTHON*`, `PERL5*`, `NODE_OPTIONS`, …) and covers them "standalone **or exported**". The brief applies the `variable_assignment`-inside-`declaration_command` handling only to `SUDO_*`. It never says whether `export PATH=./bin` (the setup for spec row 5) gets `session-altering` from the shell layer, or ends up as just `mutating` from the stub, which loses the session-altering warning. The Scope section also never says whether the full §3 list is in this child or in child-2. Do will have to guess.
- [ ] **`gate-vectors.toml` and its loader are a hidden second change that no test checks.** Scope adds `targets/ubuntu-26.04/gate-vectors.toml` "with this child's rows and a vector loader in the style of `src/nl_shell/targets.py:145-247`". No success-criterion bullet says the tests read their cases from that file, or tests the loader (missing file, bad TOML, schema). That is new data, a new module and new review surface with no red→green test. The spec also says a target's vectors file "MUST cover every row" (`v1.md:245-249`), so a partial file under that name does not meet the spec. Either drop it, or add a criterion such as "the tests read every case from the file; the loader rejects malformed entries" and say how the file relates to the full-row requirement.
- [ ] **Two citations do not resolve in the target.** `engine/scripts/run-verify.sh:196` (Falsifiability) and `results/issue_189/iteration-v2/patch.diff` with `parse.py:397,411` (Prior-art) are not in `$PDCA_TARGET`. A glob of `engine/**` and `results/**` matches nothing. They probably live in the PDCA harness checkout. The rule that Do "must cite path:line on the target branch" can't be applied to them, and a Do agent grounded on the target can't open them. Prior-art also says the v2 here-doc handling "is the bug listed above", but the brief never states that bug. The only mention is the bullet header "Stdin context, v2 regression". One sentence describing the v2 defect (stdin of the second pipeline stage recorded as terminal after a here-doc) would close the gap.
- [ ] **The §1.1 check is stricter than the spec, and the brief doesn't say so.** The brief reuses `render.has_hidden` (`src/nl_shell/render.py:136`). That function ignores quoting and covers Cf/Co/Cn/default-ignorable/surrogates (`render.py:113-127`). The spec forbids the listed characters only "outside quotes" (`v1.md:59-61`). That is fine for safety, since it only raises the class or rejects. But it means a proposal like `echo '‮'` is rejected, which differs from the spec text. A sign-off note should record that this deviation is deliberate.
- [ ] **These pinned-version claims can't be checked from the target and are load-bearing.** "tree-sitter-bash 0.25.1 has 59" named node kinds, the compatibility of `tree-sitter==0.26.0` with `tree-sitter-bash==0.25.1`, and "`case x in` parses to an `ERROR` node; `if true; then` to `MISSING "fi"`" are all assertions about third-party wheels. Nothing in the repo backs them up (`pyproject.toml:13-17` has no tree-sitter today). If either pin is wrong, Do stalls on the first install. The success criterion already makes the node-kind test enumerate the kinds at run time, so the brief should drop the hard-coded "59" rather than imply a test depends on it. The pins should be confirmed with one `pip install` before Do starts. The licence question is already deferred to sign-off.

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
- Iteration delta (if iterating): Auto-iterate (round 1): rebuilding for the implementation-level findings — T2 Shape — Decide whether the new parser input and fail-closed properties require a threat-model update — the security-path scanner found no corresponding update; gate-logs/T2-threat-model.log:10.; **A move-descriptor redirect to fd 3 or higher is not rejected.** At `src/nl_shell/gate/parse.py:466-476`, a `>&` target that is not all digits and not `-` is treated as "`>&file`", so `>&3-` and `1>&3-` only get "output redirection" (mutating, `rejected=False`). In bash, `[n]>&digit-` *moves* descriptor `digit` onto `n`, so the command writes to fd 3. I confirmed this with real bash: `exec 3>f; echo via-move >&3-` writes to `f`. Probe results: `classify("echo hi >&3-")` gives `mutating False ["output redirection: '>&3-'", ...]`, and the same for `1>&3-`. This breaks the brief's §5 rule ("a descriptor the gate cannot prove is below 3 is rejected"), which row 25 (`echo hi >&3`) exists to enforce. The `<&3-` form is rejected, but only because it falls into the `else` branch at `:478`. Fix: when the target matches `^\d+-$`, check the digits with `_below_three`. Add `>&3-` and `1>&3-` to `test_descriptor_not_provably_below_three_is_rejected` (`tests/test_policy_gate.py:272`).; **The work budget does not cover parsing or the named-fd scan.** `parse.py:240` parses the whole text before any budget is spent. `parse.py:441-443` copies and regex-searches the entire source prefix (`self.source[: node.start_byte]`) for every redirect, which is quadratic. Measured: a 6 MB proposal takes 7.7 s before ending in "could not class". A 2 MB word followed by 6000 `>x` takes 3.1 s. The brief says the budget is "a total-work budget across the whole classification". Fix: cap the input length up front (decision C), and look only at a bounded window of bytes (for example the last 256) before the redirect.; **High on the threat model's scale ("printed text forges a control-channel record"), but a confirm is still required and the gate is not wired yet.** At `src/nl_shell/gate/parse.py:466-476`, the fd rule misses bash's fd-move form `[n]>&digit-` (it moves descriptor `digit` onto `n`, see the bash manual under REDIRECTION). Input: the model's proposal. For `echo hi >&3-`, the target value is `3-`. That is not all digits and not `-`, so the `>&` branch treats it as `&>file` and calls `_output`. The result is `mutating` with an "output redirection" reason, **not rejected**, even though the command writes to fd 3 (the control channel, ADR-0014). This breaks the brief's own rule: "a descriptor the gate cannot prove is below 3 is rejected". `<&3-` is rejected, but only by the catch-all `else` at `:477-478`. `1>&3-` and `>&'3'-` go the same wrong way as `>&3-`. Fix: treat a literal target matching `[0-9]+-` as a descriptor and run it through `_below_three`. Add `echo hi >&3-`, `1>&3-` and `cat <&3-` to `test_descriptor_not_provably_below_three_is_rejected` (`tests/test_policy_gate.py:258-273`). That test lists no move form today. Not confirmed here (no tree-sitter in this sandbox). The new test cases will confirm or refute it.. Deferred, not addressed here: 12 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- By / date: auto-iterate / 2026-10-23

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 8 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

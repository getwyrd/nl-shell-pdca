# Brief — issue 196 / ast-policy-gate-shell-layer

> Re-plan after six build rounds (`iteration-v1/` … `iteration-v6/`). Rounds 1–6 each fixed
> a few more single cases and each review found new ones. This brief replaces the
> case-by-case list with **six general rules**, agreed with the human at Plan
> (2026-10-24). Every case from those rounds is now a regression input, not a separate rule.

- **Slug:** ast-policy-gate-shell-layer
- **Kind:** enhancement
- **Defect / goal:** There is no policy gate on `main` (no `nl_shell.gate`, no tree-sitter
  dependency; `pyproject.toml:13-17` lists only `prompt_toolkit`, `ptyprocess`, `PyYAML`).
  Add the `nl_shell.gate` package and its **shell layer**. It parses a command with the
  pinned tree-sitter-bash and walks the tree with one handler per named node kind of the
  pinned grammar (listed at run time from `tree_sitter.Language`). It hands each simple
  command to the command layer as an invocation: quote-removed words, each flagged literal
  or non-literal; prefix assignments; redirects; stdin source. The command layer
  (`gate/rules.py`) ships as a **stub**: every simple command is `mutating`, reason "not
  allowlisted". The §7 step (`gate/live.py`) ships as a fail-closed stub: every simple
  command still `read-only` becomes `mutating`, reason "live-session resolution not
  implemented" (this exact string is defined here; #198 and #192 assert on it).
  `gate/sensitive.py` and `gate/words.py` ship as no-op stubs that the pipeline already
  calls, for #190 and #191 to replace.
  Decisions carried from the #189 split plan: **A**: an opaque command is at least
  `mutating`, "not allowlisted" (this child ships only that floor; the rest is #197).
  **B**: code the gate cannot read is at least `destructive` (#197). **C**: gate failure
  (unhandled node kind, work budget exceeded, input over the size cap, any internal
  error) means `privileged`, rejected, reason "could not class". `classify` never raises.
  C is this child's. Bundle names: "child-2" = #197, "child-3" = #198.

  **The one principle behind all six rules: the gate assumes nothing is safe until it
  has proof.** Every fact the gate records (the tree is right, a node was walked, a word
  is literal, stdin comes from X, a redirect is safe) starts as *not proven*. It becomes
  proven only through a short, explicit list of forms. Anything outside the list is
  handled as the worst case. Each rule below is stated as a general rule over a class of
  input. Do must implement the rule for the whole class, not just the listed cases.

  **Rule 1. Trusting the tree.** The tree is trusted only when it has no `ERROR` or
  `MISSING` node and the source has none of the features tree-sitter-bash is known to read
  differently from bash:
  backslash-newline outside single quotes (the gate does **not** remove it first; text
  holding one is always untrusted, so the outcome is one fixed path); a here-doc delimiter that is not a
  plain word or a word that is entirely single- or double-quoted (`<<\E`, `<<E"F"`,
  `<<$'E'`); `<<-`; more than one here-doc started on one line; unquoted extglob openers
  `?(` `*(` `+(` `@(` `!(`; bash 5.3 `${ ` / `${|` substitutions.
  *Untrusted outcome (human ruling):* a model **proposal** is rejected. **Typed** input is
  at least `mutating`, with a reason containing "unparseable" and naming the feature.
  The walk still runs on an untrusted tree, and all of its raises still apply. In
  untrusted text, every redirect is rejected except the §2 exempt forms (`>/dev/null`
  with a literal descriptor 0–2, `2>&1`, `1>&2`, `>&2`). This includes a redirect whose
  target is `MISSING`, and any redirect operator token (`>`, `>>`, `>&`, `<&`, `&>`, `<>`,
  `<`, `<<`, `<<<`) left loose inside an `ERROR` node. A here-doc or here-string the tree
  parsed as such is not a redirect for this clause (it only feeds stdin; Rule 3 decides
  whether its text is `literal`). A new case where tree-sitter and
  bash disagree goes to #191's differential test, not into this brief.

  **Rule 2. Walking all of it.** Every named node of the tree is visited exactly once.
  Every `command`, `declaration_command` and `unset_command` node gives exactly one
  invocation. A handler that would leave a node's named children unvisited is a gate
  failure (decision C). The check is made on every classification by comparing the walk
  with the tree, not just in tests.

  **Rule 3. Proven facts only.** Each invocation's stdin source is one of: `terminal`,
  `pipe`, `file` (with the path), `literal` (here-string or here-doc text, with the text),
  or `unknown`. Only these forms give a value other than `unknown`:
  - `terminal`: a command outside any function body and outside `>(…)`, with no redirect
    that touches fd 0, that is first in its pipeline or stands alone.
  - `pipe`: a later stage of a pipeline, or the command inside `>(…)`.
  - `file`: `<` (or `0<`) from a literal path.
  - `literal`: a here-string whose word is literal, or a here-doc whose delimiter is
    quoted. A here-doc with an unquoted delimiter is literal only if its body has no `$`,
    `` ` `` or `\`.

  Everything else is `unknown`. That includes function bodies (the caller's stdin),
  `0>&N`, `0>&-`, and a stdin redirect the gate cannot place. The `Stdin` docstring says
  consumers MUST treat `unknown` as the worst case for each rule: as a pipe for the
  sudo-pipe rule and decision B, and as the terminal for #198's terminal-read rule.
  A trailing redirect on a pipeline belongs to its **last** stage, as in bash.
  tree-sitter attaches it to the whole pipeline (`a | b <f` parses as
  `(redirected_statement body: (pipeline …) redirect: …)`).
  The same rule covers the literal flag. A word is literal only if, after quote removal,
  bash would expand nothing in it: no unquoted `$`, `` ` ``, glob, extglob or brace
  expansion, no leading unquoted `~`, and in assignment values no unquoted `~` after `=`
  or `:`.

  **Rule 4. Redirects: allow the known-safe forms, reject the rest.** (Spec §5: fd 3 is
  nl-shell's control channel, ADR-0014.) A redirect is accepted only if:
  - its descriptor is absent or a literal `0`, `1` or `2` (no named `{var}`, no larger
    number);
  - **and** its target is one of:
    - a dup, move or close (`>&N`, `<&N`, `>&N-`, `N>&-`) of a literal 0–2;
    - a file target that is literal by Rule 3, apart from an optional leading `~`;
    - `/dev/null`, `/dev/stdin`, `/dev/stdout` or `/dev/stderr`;
    - `/dev/tcp/…` or `/dev/udp/…` (accepted here, but given the §2 `/dev/tcp` reason).

  A file target must also not, once repeated slashes are collapsed, lie under `/dev/`
  (apart from the names above), `/proc/` or `/sys/`, and must have no `..` component.
  Every other redirect is rejected. Examples: a non-literal target (`>"$f"`,
  `>/proc/$$/fd/3`) and a glob or extglob anywhere in the target. Accepted output
  redirects still give §2's "output redirection" reason (`mutating`), except the exempt
  forms.

  **Rule 5. Bounded cost.** The gate's total cost is bounded, and the bound covers the
  **parse** as well as the walk. Input longer than 8 KiB (UTF-8) is decision C before it
  is parsed. Measured on this host with the pinned wheels, tree-sitter-bash parse time
  grows with the square of the input: the worst known input (`$[` repeated) takes
  0.14 s at 8 KiB, 2.1 s at 32 KiB and 8.4 s at 64 KiB. Proposals are already capped at
  2000 characters (`src/nl_shell/proposal.py:26`). The walk has a total-work budget
  across the whole classification (depth and node count); going over it is decision C.
  Do not use the parser's `progress_callback`: with tree-sitter 0.26.0 it segfaults the
  process on a non-trivial input (checked at Plan; it also crashes when the callback
  never asks to cancel).

  **Rule 6. Output never carries raw input bytes.** Every reason string that quotes input
  text escapes it. No reason string contains a C0 or C1 control character, or any
  character for which `nl_shell.render.is_hidden` (`src/nl_shell/render.py:131`) is true.

- **Success criterion:** `tests/test_policy_gate.py` passes. It holds **one general test
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
- **Falsifiability:** plain pytest on the host. `tree-sitter` 0.26.0 and
  `tree-sitter-bash` 0.25.1 are installed in the pdca `.venv`, and the tree facts above
  were checked with them at Plan. No gate exists on `main`, so every case fails on the
  red leg. In v6 the C4 gate reported 217 of 217 red for the v6 version of this test
  file, so the gate's red leg works for a new test file at this path. Import
  `nl_shell.gate` inside test functions, never at module top. The harness's C4 script
  (`engine/scripts/run-verify.sh:192-196` in the pdca checkout, not the target) reports a
  module that fails to import as unverifiable.
- **Invariant to restore:** Nothing is classed `read-only`, and no fact about a command is
  recorded as safe, unless the gate has proved it. Unproven means worst case. Syntax is
  closed: every node kind is handled and every node is walked. Anything unhandled, over
  budget, over size or erroring fails closed. Sources: ADR-0013; `policy-gate/v1` §1, §5
  and Versioning; threat model Critical row "a non-read-only command runs with no confirm"
  (`.oss-scanner/threat_model.md:296`) and High row "a privileged or destructive step is
  classed lower" (`:303`).
- **Repo + branch target:** eduralph/nl-shell @ main
- **Milestone / ADRs:** M0 — REPL prototype. ADR-0013, ADR-0014, ADR-0015, ADR-0023.
- **Reproduction:** n/a (new functionality). `python -c 'import nl_shell.gate'` fails on
  `main` (a6efb0a).
- **Surfaces:** data
- **Scope (one logical fix) / out of scope:** In scope:
  - pin `tree-sitter==0.26.0` and `tree-sitter-bash==0.25.1` in `pyproject.toml`;
  - `src/nl_shell/gate/` with `__init__.py` (the §1 pipeline, `classify`, the result type,
    decision C), `parse.py` (the walker, Rules 1–5), `rules.py` (stub), stub `live.py`,
    stub `sensitive.py`, stub `words.py`;
  - the §1.1 check, reusing `nl_shell.render.has_hidden` (`src/nl_shell/render.py:136`)
    and rejecting a proposal the way `src/nl_shell/proposal.py:133` does;
  - `targets/ubuntu-26.04/gate-vectors.toml` with this child's rows, and a vector loader
    in the style of `src/nl_shell/targets.py:145-247`;
  - an update to `.oss-scanner/threat_model.md`, **only** in the "## What must hold"
    section (`.oss-scanner/threat_model.md:108`): one bullet stating the six rules as the
    gate's properties, worded to match what the code actually does. Nothing in
    "## Known gaps" changes. In particular the `failure_classes` bullet
    (`:195-209`, ending "#12 closes this") must stay as it is:
    `tests/test_failure_classes.py:827-839` pins it, and this child does not wire the
    gate into `failure_classes`, so that gap is still open. That existing test is the
    guard and must stay green;
  - `tests/test_policy_gate.py`.

  Out of scope:
  - any per-command meaning: wrappers, sudo rules, destructive commands, builtins,
    decisions A (beyond the floor) and B (#197);
  - the allowlist, the terminal-read rule and the here-doc exemption (#198);
  - §7 (#192);
  - §8 and the filesystem-state parts of §2 / §4 (#190);
  - mixed-script words and the differential parser test (#191);
  - the confirm UI and rows 35–36 (#74); REPL wiring and taint (#78); real allowlist
    entries (#139); sudo passthrough (#13);
  - variable writes the tree gives no `variable_assignment` node for (`for PATH in …`,
    `((PATH=0))`, `${PATH:=x}`, `read`, `printf -v`): parked as a follow-up by the human
    at round-5 sign-off;
  - a relative redirect target when the session's cwd is under `/dev/fd` or `/proc`
    (needs live session state).

  Do not reuse `src/nl_shell/failure_classes.py:199` `is_privileged`.
  For sign-off (human review per spec Versioning, `v1.md:238-241`; each is a raise, so
  v1-compatible), Do lists these in build-notes:
  - decision C;
  - Rule 4 is stricter than §5's "fd 3 or higher": non-literal targets like `>"$f"` are
    rejected;
  - Rule 1 rejects untrusted proposals, where §1.2 says only "at least mutating";
  - the §1.1 check ignores quoting (`echo '‮'` is rejected);
  - the 8 KiB input cap.

  The spec text for these is #197's spec edit, not this child's.
- **External dependencies:** `tree-sitter-bash`
- **Test file:** tests/test_policy_gate.py
- **Difficulty:** high
- **Citations expected:** Do must cite path:line on the target branch for every change.
  Peers to mirror: `src/nl_shell/targets.py:145-247` (loader), `src/nl_shell/render.py:136`
  (hidden characters), `src/nl_shell/proposal.py:133` (rejecting a proposal).
- **Prior-art check (triage cycles):** no `src/nl_shell/gate` in any branch of the target
  (`git log --all -- src/nl_shell/gate` is empty). No merged, open or closed PR on
  eduralph/nl-shell touches that path; #83, #125 and #129 are spec-only. The pdca checkout
  holds six earlier attempts of this bundle (`results/issue_196/iteration-v1..v6/`). v6's
  `parse.py` is a reference for node handling only. Its per-case special handling is what
  the six rules replace, so do not carry it over case by case.
- **Impact & compatibility:** new runtime dependency. `tree-sitter-bash` declares MIT; the
  `tree-sitter` wheel declares no license field. Confirm at sign-off (INTEGRATION §4,
  human-only). `tree-sitter-bash` 0.25.1's `core` extra asks for `tree-sitter~=0.24`,
  which 0.26.0 meets. CI install: CI runs Python 3.14 on `ubuntu-latest` (x86_64) and
  installs with `pip install -e '.[dev]'` (`.github/workflows/tests.yml:17-21`). Checked
  at Plan revision: the pdca `.venv` is Python 3.14.4 and pip installed both pins from
  binary wheels — `tree-sitter` 0.26.0 tagged `cp314-cp314-manylinux_2_17_x86_64`, and
  `tree-sitter-bash` 0.25.1 tagged `cp310-abi3-manylinux_2_17_x86_64` (works on 3.14). So
  CI gets wheels, not an sdist build. No REPL change.
- **Disposition hint:** new-feature

Plan-review response: findings 1–5 and 7 are fixed in the brief (threat-model edit confined
to "What must hold" with the pinned Known-gaps bullet left alone; Rule 1 untrusted table and
the regression-table definition inlined; vector-file keys and rejected-row shape defined;
Rule 5 gating made deterministic with a 5 s loose ceiling; CI wheel availability for
Python 3.14 checked and recorded; backslash-newline fixed as always-untrusted). Finding 6
(Rule 1 "reject untrusted proposals" ruling has no tracker record): the brief stands on
scope. The ruling is a raise over §1.2's "at least mutating", so the spec's Versioning rule
(`v1.md:238-241`) treats it as v1-compatible, and it is already listed for human review at
sign-off; spec edits stay with #197. Open for the human at sign-off: post the ruling on
#196 so it has a tracker record, or pull the one-line §1.2 edit into this child if code and
spec must land together.

## Iteration 7 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 3): rebuilding for the implementation-level findings — C5 Causal adequacy — Preserve ordinary words adjacent to redirects: descriptor recovery removes any adjacent word without validating it as a descriptor, losing arguments such as `secret` in `echo secret>out` and potentially a command name; add real-parser word-preservation regressions (src/nl_shell/gate/parse.py:664).; **Arguments written right before a redirect are dropped from the invocation.** `src/nl_shell/gate/parse.py:664-672` takes any word that ends exactly where an undescribed redirect starts and removes it from `word_nodes`. It does this even when `_descriptor` (`parse.py:767-779`) has already decided that the token is *not* a descriptor. Results from the patched gate: `rm -rf />/dev/null` gives words `['rm', '-rf']`, so the `/` is gone. `sudo rm -rf /etc>x` gives `['sudo', 'rm', '-rf']`. `rm -rf ~>/dev/null` gives `['rm', '-rf']`. `cat a3>f` gives `['cat']`. Bash keeps the word as an argument: `bash -c 'printf "<%s>" a /etc>out'` writes `<a></etc>`. This breaks the brief's contract ("hands each simple command … quote-removed words"). Once #197 plugs in real rules, `rm -rf />/dev/null` reaches the command layer looking like `rm -rf` with no target. Today the stub hides this (everything is `mutating`), which is why no test goes red. The Rule 4 table (`tests/test_policy_gate.py:527`) always puts a space before the redirect, so it never builds this shape. Fix: only remove the adjacent word when it is all digits or `{name}` (the same test `_descriptor` uses), and add a regression row that asserts the words of `rm -rf />/dev/null`.; **An assignment with only a redirect and no command word is treated as a one-command prefix, so §3 misses it.** `parse.py:656-657` marks every `variable_assignment` that appears before the name as `prefix`, and `src/nl_shell/gate/__init__.py:234-235` skips §3 for prefixes. Typed `PATH=/tmp/evil >/dev/null` gives `mutating` with reasons `unparseable: missing token`, `prefix assignment: PATH`, and no `session-altering` / "assignment to PATH". `LD_PRELOAD=/tmp/x.so 2>/dev/null` and `IFS=x 2>&1` behave the same way. In bash the assignment persists: `bash -c 'PATH=/tmp/evil >/dev/null; echo $PATH'` prints `/tmp/evil`. The brief's §3 says the name list is matched on every `variable_assignment` node. A command with no name word (the code already inserts an empty non-literal word for it at `parse.py:702-705`) should give its assignments the role `standalone`.; **High (latent: "a privileged or destructive step is classed lower"; today the stub floor masks it)**. `src/nl_shell/gate/parse.py:665-672`. Input: any proposal or typed command where a word is written right against a redirect operator with no space. The model or untrusted text controls this. `_simple` collects the token right before *every* redirect that has no descriptor field, into `fd_tokens`. It does this whether or not the token is a number, then drops those tokens from `word_nodes`. `_descriptor` (`parse.py:775`) only treats digits or `{…}` as a descriptor, but the drop happens anyway. So real arguments, and even wrapped command names, vanish from the invocation handed to the command layer. They also vanish from `layer.words`, which the §8 sensitive-path and #191 word checks will read. Reproducers (invocation words as the gate records them):; **Medium (latent; it feeds the sudo-pipe rule and decision B).** `src/nl_shell/gate/parse.py:540-562` and `:708-710`. Input: a proposal that runs `exec` with a stdin redirect earlier in the same command line. `exec </tmp/x; sudo tee /etc/y` records `sudo tee /etc/y` with stdin **`terminal`**, but bash feeds it `/tmp/x`. Compare `{ sudo tee /etc/y; } </tmp/x`, which the gate correctly gives `file`. `terminal` is the best case for the sudo-pipe rule, so this is a stdin fact recorded as proven when it is not. Fix: after an `exec` invocation with any redirect touching fd 0 (or any `exec` redirect at all), set the stdin of every later invocation in that list to `unknown`. Add the input above to the Rule 3 test. An `exec` from an *earlier* command in the session needs live state (#192) and is out of scope here.. Deferred, not addressed here: 11 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v7/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

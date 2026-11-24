# Build notes — #196 policy gate, shell layer (child-1 of #189), iteration 3

Target: eduralph/nl-shell @ main (a6efb0a). All paths below are in the patched tree
(`$PDCA_WORKTREE`, base a6efb0a + `patch.diff`). `patch.diff` applies cleanly to a6efb0a
(checked with `git apply --cached --check` on a fresh index of a6efb0a).

This iteration starts from the iteration-2 patch (`iteration-v2/patch.diff`, applied
unchanged) and fixes the seven implementation findings in the round-2 carry-forward,
plus the reviewer's untagged "phantom `0` operand" note. The design notes of iterations
1 and 2 still hold; the parts that moved are cited below. Line numbers are for
`src/nl_shell/gate/parse.py` unless a file is named.

## Iteration 3: what changed and why

### 1. A line continuation hid an fd-3 redirect (and more)

- Cause: bash removes backslash-newline before it splits words; tree-sitter-bash 0.25.1
  treats it as a token break. I dumped trees to see how far this goes. It is wider
  than redirects: `r\⏎m x` parses as command `r` with argument `m` (bash runs `rm x`),
  and `$\⏎(rm x)` parses as `$` + variable name `\⏎` + a subshell (bash runs `$(rm x)`).
  So any fix limited to redirect operators would leave the command-word case open for
  #197 to trip on.
- Fix: `_check_continuations` (`:304`, called from `walk` at `:296`, right after the
  parse). For each run of backslash-newlines it finds the smallest node holding the
  backslash. If that node is a token whose own text the gate reads correctly or bash
  keeps literally (`_CONTINUATION_TOKENS`, `:88`: word, string content, raw string,
  ANSI-C string, comment, here-doc body), it is fine. Otherwise, when the bytes on both
  sides of the run are non-blank, bash joins two things the parser split, so it raises
  `SplitContinuation` (`:119`), a `GateFailure` → decision C (`privileged`, rejected,
  "could not class"). A blank on either side joins nothing, so ordinary continuations
  (`apt install \⏎  foo`, `a |\⏎  b`) are still classed.
- Each continuation costs one unit of the work budget, so the scan is linear and bounded.
- Why fail closed (decision C) and not just "reject with a descriptor reason": the gate
  does not know what bash will see, which is the definition of "could not class".
- Tests: `test_split_line_continuation_fails_closed` (`tests/test_policy_gate.py:342`)
  with the reviewer's three inputs plus `3\⏎\⏎>y`, `{f\⏎d}>x`, `r\⏎m x`, `$\⏎(rm x)`;
  `test_line_continuation_next_to_a_blank_is_classed` (`:358`) holds the common forms.

### 2. A command inside a `number` node was dropped

- Cause: `number` was a leaf, and tree-sitter-bash puts `$(rm x)` inside `number` in
  `$((10#$(rm x)))`.
- Fix, two parts: `number` moves to `_CONTAINERS` (`:971`); and `_leaf` (`:775`) now walks
  any named children it finds, so a grammar surprise in another "leaf" kind cannot drop
  a command either. This removes the cause for every leaf kind, not just `number`.
- Test: `test_every_command_node_becomes_an_invocation` (`tests/test_policy_gate.py:425`),
  the count test the reviewer asked for. For 12 inputs that bury a command in an
  arithmetic, `${…}`, `[[ ]]`, array, assignment, here-doc, `for`, `case`, `$"…"`,
  declaration and function-redirect position, it counts the `command`,
  `declaration_command` and `unset_command` nodes in the tree and asserts the same number
  of invocations reached the command layer, and that `rm` is one of them.

### 3. `<<-` here-doc with a tab-led first line: substitution recorded as literal text

- Cause: tree-sitter-bash 0.25.1 gives that body no `command_substitution` child (I
  reproduced it: `heredoc_body '$(rm x)\n'` with no children), and `_heredoc_text` only
  looked at the children and at `\`.
- Fix (`_heredoc_text`, `:687`): for an unquoted delimiter,
  - any `$`, backquote or backslash in the body makes the text non-literal (None),
    whatever the tree says;
  - `_substitutions_in` (`:710`) counts unescaped `$(` and backquote pairs in the text,
    `_substitution_nodes` (`:725`) counts `command_substitution` / `arithmetic_expansion`
    nodes under the body. Fewer nodes than the text holds raises `UnreadHeredoc` (`:128`,
    raised at `:700`) → decision C. An escaped `\$(x)` is not counted, so it does not
    fail closed.
- Tests: `test_heredoc_substitution_the_parser_missed_fails_closed`
  (`tests/test_policy_gate.py:601`; `$(…)`, backquotes, `$((…))`) and
  `test_expanded_input_text_is_not_recorded` (`:589`, the negative the reviewer asked for,
  including a `<<-` tab body with `$HOME`).

### 4. A trailing redirect of a pipeline or list went to the wrong stage

- Cause: tree-sitter-bash hangs `a | b <x` and `a && b >x` as
  `(redirected_statement body: (pipeline|list …) redirect: …)`. The walker applied the
  redirect to the whole body, so the first stage got it.
- Fix: `_redirected_statement` (`:800`) finds the stage the redirects belong to with
  `_last_stage` (`:742`; descends through `pipeline`, `list` and `negated_command`) and
  records them in `_Walker.attached` by node id. `_Walker.walk` (`:550`) applies them when
  it reaches that node, on top of whatever stdin it already has (`_apply`, `:737`), so the
  last stage of a pipe reads the file, not the pipe. A compound body (`(a | b) <x`,
  `{ …; } >x`) still gives the redirects to everything inside it, as bash does.
- Test: `test_stdin_of_every_stage` (`tests/test_policy_gate.py:556`) asserts stdin and
  redirects on **every** stage: the reviewer's `a | b <x`, `a | cat <<E | sudo tee /x`,
  `sudo -v | cat <<E`, plus `a && b >x`, `a | b && c <x`, `! a | b <x`, and the compound
  `(a | b) <x` as a control.

### 5. A redirect to a path that opens a descriptor (`/dev/fd/3`) was not rejected

- Fix: `_descriptor_path` (`:448`, pattern `_DESCRIPTOR_DIRECTORY` at `:81`). It collapses
  repeated slashes and `.`/`..` (as Linux resolves them) and matches `/dev/fd/N`,
  `/proc/<anything>/fd/N` and `/proc/<pid>/task/<tid>/fd/N`. `check_redirect` (`:614`)
  rejects any literal file target whose descriptor is not provably below 3; a name under
  such a directory that is not plain digits counts as "?", so it is rejected too. It runs
  before the operator branches, so `>`, `>>`, `<`, `<>` and `>&file` are all covered.
  `/dev/fd/2`, `/dev/stderr` stay plain output redirections.
- Tests: 12 path forms added to `test_descriptor_not_provably_below_three_is_rejected`
  (`tests/test_policy_gate.py:304`), including the reviewer's five and `/dev/./fd/3`,
  `/dev/fd/03`, a quoted target, `/proc/thread-self/…`, a task path, and a 40-digit
  descriptor; `test_descriptor_path_below_three_is_not_rejected` (`:324`) holds 0-2.
- Not covered (written up for sign-off below): a non-literal target (`>"$F"` where F is
  `/dev/fd/3`) and a symlink to `/dev/fd/3` are only `mutating` (output redirection).

### 6. An unquoted `~` was marked literal

- Fix: `_tilde` (`:363`), used by `word()`. A word whose shape starts with `~` or holds
  `=~` or `:~` is not literal (bash expands `~` after `=` and `:` in any
  assignment-looking word, not only in real assignments). The shape keeps quoted and
  escaped characters as "x", so `'~'/x`, `\~/x` and `"~/x"` stay literal. The value is
  kept (`~/x`) so a later rule can still read it.
- Tests: `test_tilde_is_not_literal` (`tests/test_policy_gate.py:486`) and
  `test_tilde_in_an_assignment_value_is_not_literal` (`:494`).

### 7. The function-definition reason held the raw name

- Fix: `f"function definition: {label!r}"` (`:944`).
- Test: `test_function_definition_reason_quotes_the_name` (`tests/test_policy_gate.py:235`)
  with a raw ESC byte in the name.

### 8. The phantom `0` of `cat 0<x` (reviewer's untagged note)

- tree-sitter-bash reads `0` (only `0`; `1>x` gets a `file_descriptor`) as a `number`
  argument followed by an fd-less redirect. It would give #197's operand rules a false
  operand (`rm -rf a 0<x`).
- Fix: `_descriptor_word` (`:867`, used at `:834`) drops a bare digit word that ends right
  before `<` or `>` (not `<<`), and `_Walker.redirect` (`:590`) reads those digits back as
  the redirect's descriptor with `_digits_before` (`:465`). It reads at most 64 bytes back;
  a longer run is "?", which is rejected. Here-strings and here-docs are left as they
  were.
- Test: `test_bare_digit_before_a_redirection_is_its_descriptor`
  (`tests/test_policy_gate.py:459`).

### 9. Threat model

`.oss-scanner/threat_model.md:121-125` (in the bullet at `:114`) extends the "gate fails closed" bullet: descriptor
paths are rejected, and the two known parser/bash differences (split continuation,
unread here-doc substitution) fail closed. `scripts/docs_links.py` is still clean.

## What I ruled out

- **Joining backslash-newlines before parsing** (removing the cause in the text rather
  than detecting it). bash does not join inside single quotes or comments, so a plain
  join is wrong, and in one case fails open: `# note \⏎rm -rf ~` would join `rm -rf ~`
  into the comment and the gate would never see it. A correct join needs a quote-,
  comment- and here-doc-aware lexer, which is a second bash parser; #191 owns the
  differential parser work. The detector is 25 lines and fails closed.
- **Rejecting every backslash-newline** (the reviewer's simplest version). It would
  reject ordinary multi-line commands (`apt install \⏎  foo`). The blank-on-either-side
  rule keeps those working and still catches every split the reviewer and I found.
- **Rejecting every non-literal redirect target** (to close `>"$F"`). It would reject
  `> "$HOME/out"` and similar. That is a policy call beyond the brief; listed for
  sign-off.

## For sign-off (each raises a class, so each is v1-compatible but needs human review per v1.md:238-241)

- **Decision C** is a new rule: an unhandled node kind, the budget exceeded (64 KiB of
  text, 20 000 nodes, depth 150), any internal error, and now a split line continuation or
  an unread here-doc substitution give `privileged`, rejected, "could not class". The
  spec text for it is #197's edit.
- **The fd rule is stricter than §5.** §5 rejects descriptors 3 and up; the gate rejects
  any descriptor it cannot prove is below 3: `>&$x`, `<&$fd`, `>&"$X"`, `2>&${FD}`, named
  fds, a non-number after `<&`, the move form `[n]>&digit-`, and now paths that open a
  descriptor (`/dev/fd/N`, `/proc/*/fd/N`) and a bare-digit run longer than 64 bytes.
- **A non-literal or symlinked path to `/dev/fd/3` is not rejected** (only `mutating`).
  The gate cannot prove where `>"$F"` points. Closing it means rejecting every
  non-literal redirect target, or #190's filesystem resolution for the symlink case.
  Your call whether that is acceptable for this child.
- **§1.1 ignores quoting.** `render.has_hidden` checks quoted text too, so `echo '‮'` as
  a proposal is rejected, although §1.1 forbids these characters only outside quotes.
- **A `~` word is now non-literal** even in shapes bash would not expand in POSIX mode
  (`a:~/x` as a plain argument). This only removes a "literal" mark, which is the
  fail-closed direction.
- **Threat model edited** (`.oss-scanner/threat_model.md:114-125, 189-194, 225-232`).
- License: `tree-sitter-bash` declares MIT; the `tree-sitter` wheel declares no license
  field. Confirm per INTEGRATION §4 (human-only).

## Refuting my own test

- **(a) Is the red genuine? Yes.**
  - Against the iteration-2 `parse.py` (extracted from `iteration-v2/patch.diff`, the
    rest of the tree as now): 36 of 153 cases failed — all 7 split-continuation cases,
    all 12 descriptor paths, the `number` coverage case, the phantom-`0` test, 4 tilde
    cases and the assignment-value tilde test, 6 of the 7 stage cases (the compound
    control passes, as it should), all 3 here-doc fail-closed cases, and the
    function-name test. So every finding has at least one case that was red before this
    iteration's fix. I restored the file afterwards (`cmp` with my saved copy: equal).
  - C4 script (`engine/scripts/run-verify.sh` with `PDCA_BUNDLE` and `PDCA_WORKTREE`
    set): red leg 153 ran, 153 failed, 0 collection errors (each test imports
    `nl_shell.gate` inside the function, and it does not exist on a6efb0a); green leg all
    passed. Verdict: `PDCA-EVIDENCE: C4 PASS — red without the fix (153 of 153 failed),
    green with it`. Afterwards `git diff a6efb0a` in the worktree is byte-identical to
    `patch.diff`.
- **(b) Does the test drive production code? Yes.** Every case calls the real
  `nl_shell.gate.classify` or `parse.walk` with the real pinned grammar. The coverage
  test parses with `parse.language()` only to count nodes; the invocations it compares
  come from the production walk. Monkeypatches only wrap `rules.classify` to record, or
  delete one `HANDLERS` entry.
- **(c) Does the fixture include the fault? Yes.** The inputs are the reviewer's own
  reproductions (`>\⏎&3`, `<\⏎&3`, `3\⏎>y`, `$((10#$(rm x)))`, `<<-E⏎\t$(rm x)`,
  `a | b <x`, `sudo -v | cat <<E`, `/dev/fd/3` forms, `~/x`, a raw ESC name), plus the
  wider shapes I found while dumping trees (`r\⏎m`, `$\⏎(`, `{f\⏎d}`).

## Environment and commit-readiness

- `tree-sitter` 0.26.0 and `tree-sitter-bash` 0.25.1 are installed in the pdca `.venv`.
  No missing external dependency.
- Full target suite (`python -m pytest`, the CI command, under `timeout`):
  1254 passed, 1 skipped (`-W error::DeprecationWarning`). `scripts/docs_links.py`:
  64 links, 0 broken.
- The target has no formatter, linter or pre-commit config. CI runs pytest and
  `scripts/docs_links.py`. `git diff --check` is clean; no line is over 92 characters,
  as in the code around it.
- Scratch files are in `$PDCA_WORKTREE/.probe/` (tree dumps, edit scripts, a saved
  `parse.py`). They are untracked and excluded from `patch.diff`; I did not delete them.
  I ran `git add -N` on the new files so `git diff a6efb0a` includes them. Nothing is
  committed.

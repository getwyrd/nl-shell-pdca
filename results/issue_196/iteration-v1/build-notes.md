# Build notes — #196 policy gate, shell layer (child-1 of #189)

Target: eduralph/nl-shell @ main (a6efb0a). All paths below are in the patched tree
(`$PDCA_WORKTREE`, base a6efb0a + `patch.diff`).

## What the patch adds

- `pyproject.toml:17-20` — pins `tree-sitter==0.26.0` and `tree-sitter-bash==0.25.1`
  (exact pins: a new grammar can add node kinds with no handler).
- `src/nl_shell/gate/__init__.py` — the §1 pipeline.
  - `classify` (`:78`) never raises: everything, including argument checks, is inside
    the `try` at `:93`; any exception gives `privileged`, rejected, reason
    "could not class: …" (decision C).
  - §1.1 (`:113`) uses `render.has_hidden` and `render.too_many_marks`, the same two
    checks `src/nl_shell/proposal.py:133-136` uses to reject a proposal. A proposal is
    rejected; typed input is at least `mutating`, reason "hidden character in typed
    input".
  - §1.2: `Walk.unparseable` comes from `root_node.has_error`, which is true for both
    ERROR and MISSING nodes.
  - Per invocation: `rules.classify` → `live.resolve` if still `read-only` →
    `sensitive.check` → `words.check`. All are called through the module attribute, so
    the tests' monkeypatches hit the real pipeline.
  - §1.7: the label raises the class, never lowers it.
  - `GateResult.as_log()` returns the session-log `gate` shape
    `{"class", "reasons", "rejected"}` (`docs/design/specs/session-log/v1.md:44`).
- `src/nl_shell/gate/parse.py` — the walker.
  - `HANDLERS` (`:751`) has one handler per named node kind, plus `ERROR`.
    `grammar_node_kinds()` (`:223`) reads the kinds from `tree_sitter.Language` at run
    time (59 for the pinned grammar; no test hard-codes the count).
  - `_Walker.walk` (`:393`) charges the `Budget` (`:93`; `MAX_WORK` = 20 000 nodes and
    `MAX_DEPTH` = 150, `:44-45`) on every node, and raises `UnhandledNode` for a kind
    with no handler.
  - `Context` (`:192`) carries stdin, the redirects around the node, depth and the
    budget. `Invocation` (`:171`) carries the quote-removed `Word`s with their literal
    flags, the prefix assignments, the redirects (own, then those around) and the stdin.
  - Shell-level findings:
    - §2 and §5 redirects: `check_redirect` (`:454`);
    - §3 and §5 assignments: `check_assignment` (`:489`);
    - command word: `_check_command_word` (`:661`);
    - process substitution: `_substitution` (`:722`);
    - function definitions: `_function_definition` (`:714`);
    - `/dev/tcp` and `/dev/udp`: in `walk` (`:233`) over the raw text, and `_check_words`
      over the quote-removed words.
- `src/nl_shell/gate/verdict.py` — the five classes, `rank`, and `Verdict`.
- `src/nl_shell/gate/rules.py:19` — the stub: `mutating`, reason "not allowlisted".
- `src/nl_shell/gate/live.py:15-25` — `STUB_REASON = "live-session resolution not
  implemented"`. `resolve(invocation, verdict)` turns `read-only` into `mutating`.
- `src/nl_shell/gate/sensitive.py:14` and `src/nl_shell/gate/words.py:14` — no-op stubs.
- `src/nl_shell/gate/vectors.py` — the vector loader (`load` `:51`, `read` `:63`,
  `_vector` `:89`). It follows `src/nl_shell/targets.py:145-171`: the plain-id check, the
  folder-inside-root check, and read → decode → `tomllib`, each with its own error. Every
  error message names the file and `vector N (row R)`.
- `targets/ubuntu-26.04/gate-vectors.toml` — rows 7, 13, 14, 15, 16, 23, 25, 30, 31. The
  header says it holds the rows landed so far and is complete (v1.md:245-249) only when
  #192 lands. Row 30's U+202E is written as the TOML escape `‮`, so the repo file
  holds no bidi character.
- `tests/test_policy_gate.py` — 78 cases. Every gate import is inside a test function.

## Design decisions worth a look

1. **The here-doc pipeline (the v2 bug).** tree-sitter-bash puts `| sudo tee /x` *inside*
   the `heredoc_redirect`, as a `pipeline` whose first child is the `|` token
   (`cat <<E | sudo tee /x` parses that way — I dumped the tree). v2 picked the stdin
   by the stage's index, so that stage got the terminal. `_pipeline` (`:579`) marks a
   stage as reading the pipe when a `|` or `|&` token comes before it, so the leading
   `|` counts. A mutation test that put back v2's index rule made the two here-doc
   cases fail (2 failed / 75 passed).
2. **The stdin of a substitution.** A substitution keeps the stdin its command had
   *before* the command's own redirections, and drops the redirects around it, because
   its output is captured. This is what bash does: expansions happen before the command's
   own redirections, inside the pipeline subshell or the redirected compound. So in
   `echo pw | x $(sudo -S id)` the inner `sudo` reads the pipe, and child-2's pipe rule
   will see it. A function body gets the terminal (it runs later).
3. **`mutating` vs `session-altering` at equal rank** (`verdict.py:27`). The spec ranks
   them equal. When both apply, the verdict names `session-altering`, so the result does
   not depend on the order in which findings arrive. I added the case
   `A=1 true; PATH=x` after a mutation test showed the other cases never put `mutating`
   first.
4. **§3 names and prefix assignments.** The §3 list is matched on every
   `variable_assignment` node that sets a shell variable: standalone, inside
   `declaration_command`, or in a `for ((…))` header. It is not matched on prefix
   assignments (`VAR=x cmd`), which do not change the session. So row 7 stays
   `mutating` (prefix-assignment reason), as the spec row expects. `SUDO_PROMPT` and
   `SUDO_ASKPASS` are rejected in both places, as §5 says.
5. **`{fd}>x`.** tree-sitter-bash parses it as ERROR (`{` followed by a
   `redirected_statement`); `exec {fd}>x` parses to an argument word plus a redirect.
   Neither form gives the named fd a node of its own, so `_NAMED_FD` (`:69`) reads the
   bytes just before each redirect. This works in both shapes.
6. **Descriptors.** `_below_three` (`:351`) never converts the number, so a 40-digit fd
   costs nothing. For `>&`/`<&`, the target must be literal ASCII digits below 3 or `-`.
   `>&file` (a literal non-number) is treated as `&>file`, an output redirection. Any
   other target is rejected.
7. **Lone surrogates.** tree-sitter splits the three surrogatepass bytes of `\udcff` into
   separate `word` nodes. My first run failed with a `UnicodeDecodeError` and fell to
   decision C. `_text` (`:258`) now falls back to `surrogateescape` for such a piece, and
   §1.1 has already flagged the input, so the case is rejected for the right reason
   ("hidden character").
8. **Nothing classed.** `""`, a comment or `a=1` have no invocation. The gate raises them
   to `mutating`, reason "no simple command was classed", so nothing is `read-only`
   without proof.
9. **An extra module, `verdict.py`.** The brief's file list has no home for the class
   constants and `Verdict`. If they lived in `rules.py`, `parse.py` would need to import
   `rules`, and `rules` imports `parse.Invocation`, so the imports would be circular.
   `verdict.py` is 62 lines with no dependencies. `vectors.py` is the loader the brief
   asks for, in its own module.

## For sign-off (each one raises a class, so each is v1-compatible but needs human review per v1.md:238-241)

- **Decision C** is a new rule: an unhandled node kind, the budget exceeded, or any
  internal error gives `privileged` and rejected, reason "could not class". The spec text
  for it is #197's edit.
- **The fd rule is stricter than §5.** §5 rejects descriptors 3 and up. The gate rejects
  any descriptor it cannot prove is below 3: `>&$x`, `<&$fd`, `>&"$X"`, `2>&${FD}`, named
  fds, and a literal non-number after `<&`.
- **§1.1 ignores quoting.** `render.has_hidden` checks quoted text too, so `echo '‮'` as a
  proposal is rejected, although §1.1 forbids these characters only outside quotes. It
  also flags more characters than §1.1 lists (Cf/Co/Cn, Default_Ignorable, …), and the
  gate applies `too_many_marks` as the proposal parser does.
- License: `tree-sitter-bash` declares MIT; the `tree-sitter` wheel declares no license
  field. Confirm per INTEGRATION §4 (human-only).

## What I ruled out

- **A raw-text regex for `{fd}`.** It would match `{fd}>` inside quotes. Reading the
  bytes just before each redirect node only fires where a redirect really is.
- **Resetting a substitution's stdin to the terminal** (v2 did this). It is wrong for
  `x $(sudo …)` inside a pipeline stage or a here-string-fed compound, and it is the same
  class of bug as the here-doc pipeline.
- **Charging input bytes to the work budget.** A pasted here-doc of 50 KB is one node.
  Charging bytes would send legitimate typed input to decision C (privileged, rejected).
  The budget counts nodes, and tree-sitter's parse is linear.

## Refuting my own test

- **(a) Is the red genuine? Yes.** `engine/scripts/run-verify.sh` with
  `PDCA_BUNDLE=results/issue_196` and `PDCA_WORKTREE` set ran both legs:
  - green: 78 ran, 0 failed;
  - red, production hunks reverted: 78 ran, 78 failed, 0 collection errors (imports
    are inside the tests, so the module loads and each test fails on its own);
  - verdict: `PDCA-EVIDENCE: C4 PASS — red without the fix (78 of 78 failed), green
    with it`.

  Beyond whole-patch revert I ran mutation checks on single rules:

  | Mutation | Result |
  |---|---|
  | v2's index-based pipeline stdin | 2 failed |
  | named-fd check off | 1 failed |
  | slash collapse off | 1 failed |
  | §3 check also applied to prefix assignments | 6 failed |
  | session-altering tie-break off | 1 failed, after adding `A=1 true; PATH=x` (it survived before) |

- **(b) Does the test drive production code? Yes.** Every case calls the real
  `nl_shell.gate.classify` or `parse.walk`, with the real pinned tree-sitter grammar.
  The monkeypatches only *wrap* `rules.classify` (recording invocations, or returning
  `read-only` for one named command) or delete one `HANDLERS` entry; the pipeline,
  walker and §7 stub under test are the production ones. The vector rows are read
  through the production loader from the real `targets/ubuntu-26.04/gate-vectors.toml`.
- **(c) Does the fixture include the fault? Yes.** The here-doc cases use the exact
  failing shape (`cat <<E | sudo tee /x` with body `x`). The decision-C cases use real
  inputs: 300-deep `$(` nesting, and a chain of `MAX_WORK // 3` substitutions that stays
  well under the depth limit (the reason names "work budget", not depth). The unparseable
  cases are checked to produce `MISSING fi` and `ERROR` in the real tree.

## Environment and commit-readiness

- `tree-sitter` 0.26.0 and `tree-sitter-bash` 0.25.1 are installed in the pdca `.venv`.
  `engine/scripts/check-target-deps.py` against the patched tree exits 0. No missing
  external dependency.
- Full target suite (`python -m pytest`, from INTEGRATION.md, under `timeout`):
  1179 passed, 1 skipped.
- The target has no formatter, linter or pre-commit config (none in `pyproject.toml`, no
  `.pre-commit-config.yaml`, and CI runs only pytest and the docs checks). So there is no
  commit hook to run. I wrapped new lines to ≤ 92 columns to match the code around them,
  and `git diff --check` is clean.
- Housekeeping: early on I created `/tmp/gate-scratch/dump.py` (a tree-dump helper) by
  mistake; the rules say scratch files belong in the worktree. Later scratch went under
  the worktree's git-ignored `.pytest_cache/scratch/`. I did not delete either; the
  harness reclaims its roots.
- Reference consulted: v2's walker (`results/issue_189/iteration-v2/patch.diff`, which
  the brief names as a reference). Quote removal (`_evaluate`) follows its approach; the
  pipeline and substitution stdin handling are new (decisions 1 and 2).

# Build notes — #196 policy gate, shell layer (child-1 of #189), iteration 2

Target: eduralph/nl-shell @ main (a6efb0a). All paths below are in the patched tree
(`$PDCA_WORKTREE`, base a6efb0a + `patch.diff`).

This iteration starts from the iteration-1 patch (`iteration-v1/patch.diff`, applied
unchanged) and fixes the three findings in the carry-forward. Everything iteration 1's
notes say about the design still holds; the parts that moved are re-cited below.

## Iteration 2: what changed and why

### 1. Move-descriptor redirects (`>&3-`, `1>&3-`) were not rejected

- Cause: `check_redirect` (`src/nl_shell/gate/parse.py:490`) took a `>&` target that was
  neither all digits nor `-` as `>&file`. bash reads `[n]>&digit-` as "move descriptor
  `digit` onto n", so `>&3-` writes to fd 3 (the reviewer confirmed this in real bash).
- I dumped the trees: tree-sitter-bash gives `>&3-` a `file_redirect` with one
  `destination: (word)` holding `3-`. `>&'3'-` gives `(concatenation (raw_string) (word))`,
  whose quote-removed value is also `3-`.
- Fix: `_MOVE_TARGET` (`parse.py:77`, `[0-9]+-`). A target whose literal value matches
  it is checked as a descriptor: the digits go through `_below_three` (`parse.py:508-511`),
  so `>&3-`, `1>&3-`, `>&'3'-`, `<&3-` and a 40-digit move are rejected. `2>&1-` passes
  with no reason, as it should: it only touches descriptors 1 and 2. Before the fix,
  `<&3-` was rejected only by the catch-all `else`. It is now rejected by this rule.
- Tests: five move forms added to `test_descriptor_not_provably_below_three_is_rejected`
  (`tests/test_policy_gate.py:272-276`); `echo x 2>&1-` added to
  `test_no_shell_level_reason` (`:218`). The reviewer asked for `>&3-`, `1>&3-` and
  `cat <&3-`; all three are there.

### 2. The work budget did not cover the parse or the named-fd scan

- Cause, part one: `walk` parsed the whole text before charging anything to the budget.
- Fix, part one: the `Budget` (`parse.py:101`) now has an input budget too
  (`input_bytes`, `read`, `spend_input` at `:115`). `MAX_INPUT_BYTES` is 64 KiB
  (`parse.py:46`).
  - `walk` charges the UTF-8 byte length before parsing (`parse.py:259`). It refuses on
    the character count first (`:255-257`), so over-long text is not even encoded.
  - `_classify` checks the length before §1.1 (`src/nl_shell/gate/__init__.py:115-117`),
    so `render.has_hidden` never scans over-long text.
  - Going over gives `BudgetExceeded`, so decision C applies: `privileged`, rejected,
    reason "could not class: input budget exceeded (65536 bytes)". The budget is shared,
    so a later walk on the same `Budget` (as `bash -c` text will be in #197) is charged
    for the bytes the first walk read.
- Cause, part two: for every redirect, the named-fd check copied and regex-searched the
  whole text before it (`self.source[: node.start_byte]`), which is quadratic.
- Fix, part two: `_named_fd_before` (`parse.py:379`, called at `:479`) checks that the
  byte just before the redirect is `}`, then walks back over name bytes to `{`. It reads
  at most `NAMED_FD_WINDOW` = 256 bytes (`parse.py:51`). A name longer than that counts
  as a named fd, so the check fails closed and still rejects. The walks of different
  redirects cover separate byte ranges, so the total cost is linear.
- Measured (pdca `.venv`, this host):

  | Input | Before | After |
  |---|---|---|
  | 6 MB proposal | 7.7 s (reviewer's measure) | 0.0 s, could not class (input budget) |
  | 2 MB word + 6000 `>x` | 3.1 s (reviewer's measure) | 0.0 s, could not class (input budget) |
  | same, `walk` with `Budget(input_bytes=4_000_000)`, old scan | 2.75 s | — |
  | same, `walk` with `Budget(input_bytes=4_000_000)`, new scan | — | 0.14 s |
  | 64 KiB text with 6000 `>x`, `classify` | — | 0.05 s, `mutating` |

- Why 64 KiB: 64 KiB is far above any real one-line proposal, and a 40 KiB literal
  here-doc is still classed normally (test at `:447`). Iteration 1 ruled out charging
  bytes to the *node* budget because a legitimate 50 KB paste would fall to decision C.
  A separate byte cap keeps that case working up to 64 KiB. Above that, typed input is
  refused (`privileged`, rejected). That is a deliberate fail-closed choice for the human
  to weigh (see sign-off items).
- Tests (`tests/test_policy_gate.py:421-470`):
  - `test_input_over_the_size_budget_fails_closed`: one case over the cap in ASCII, one
    under the cap in characters but over it in UTF-8 bytes;
  - `test_input_budget_is_shared_across_walks`;
  - `test_input_under_the_size_budget_is_classed`;
  - `test_many_redirections_after_a_long_word_stay_cheap`. It runs `walk` with a raised
    cap on the 2 MB + 6000 `>x` shape and asserts it finishes in under 1.0 s (old scan
    2.75 s, new 0.14 s). Then, under the real cap, it checks that the same shape is
    classed normally.
  - I first wrote that timing test against `classify` under the real cap. It did not
    bind: with the cap, the old scan costs only 0.12 s. So I rewrote it against `walk`
    with a raised cap, where the quadratic cost shows.

### 3. T2: threat-model update

The gate is a new trust boundary: untrusted model output now goes through an in-process
C parser, and the gate must fail closed. `.oss-scanner/threat_model.md` now says so in
three places:

- `:114-121` (What must hold), new bullet "The gate fails closed": it pins the grammar,
  every node kind has a handler, decision C applies, the budget is spent before the
  parse (input cap), and the descriptor rule rejects anything it cannot prove is 0-2,
  including `>&3-`.
- `:221-228` (Known gaps), new bullet: only the shell layer exists, and nothing is
  `read-only` yet. It is not wired (#78). It lists which sibling issue owns each
  remaining part. Until #191, a tree-sitter/bash parse difference counts as an
  in-scope gate bypass.
- `:185-189` (Out of scope): tree-sitter and its grammar are added to the third-party
  list. tree-sitter runs in-process on the model's proposal, so a crash or hang in it
  stops nl-shell, and the input budget limits the text it is given.

`scripts/docs_links.py`: 64 links, 0 broken.

## The rest of the patch (unchanged from iteration 1, re-cited)

- `pyproject.toml:19-20`: exact pins `tree-sitter==0.26.0` and `tree-sitter-bash==0.25.1`.
- `src/nl_shell/gate/__init__.py`: the §1 pipeline.
  - `classify` (`:79`) never raises; everything is inside the `try` at `:86`.
  - §1.1 (`:118`) uses `render.has_hidden` / `render.too_many_marks`, as
    `src/nl_shell/proposal.py:133-136` does.
  - The pipeline per invocation is rules → live (if still `read-only`) → sensitive →
    words.
  - §1.7: the label raises the class and never lowers it.
  - `as_log()` gives the session-log `gate` shape.
- `src/nl_shell/gate/parse.py`:
  - `HANDLERS` (`:791`), and `grammar_node_kinds()` (`:239`), which reads the kinds from
    `tree_sitter.Language` at run time;
  - `Budget` (`:101`), `Invocation` (`:187`), `Context` (`:208`);
  - `_pipeline` (`:619`), which fixes the v2 here-doc pipe bug: a stage after a leading
    `|` token reads the pipe;
  - `_check_command_word` (`:701`), `_function_definition` (`:754`), `_substitution`
    (`:762`), `check_assignment` (`:529`).
- `src/nl_shell/gate/verdict.py`, `rules.py` (stub: "not allowlisted"), `live.py`
  (`STUB_REASON = "live-session resolution not implemented"`), `sensitive.py` and
  `words.py` (no-op stubs), and `vectors.py` (the loader, following
  `src/nl_shell/targets.py:145-171`).
- `targets/ubuntu-26.04/gate-vectors.toml`: rows 7, 13, 14, 15, 16, 23, 25, 30 and 31.
  Its header says it is partial until #192.
- `tests/test_policy_gate.py`: 90 cases (78 in iteration 1, plus 12 new).

## For sign-off (each one raises a class, so each is v1-compatible but needs human review per v1.md:238-241)

- **Decision C** is a new rule: an unhandled node kind, the budget exceeded, or any
  internal error gives `privileged` and rejected, reason "could not class". The spec
  text for it is #197's edit.
- **The input cap (new this iteration) is part of decision C.** Text over 64 KiB
  (UTF-8 bytes) is `privileged` and rejected, whether it is a proposal or typed input.
  If you want long typed here-docs to pass, the cap is one constant
  (`parse.py:46`).
- **The fd rule is stricter than §5.** §5 rejects descriptors 3 and up. The gate rejects
  any descriptor it cannot prove is below 3: `>&$x`, `<&$fd`, `>&"$X"`, `2>&${FD}`,
  named fds (including a name over 256 bytes, which it does not read in full), a literal
  non-number after `<&`, and now the move form `[n]>&digit-` / `[n]<&digit-` with
  digit ≥ 3.
- **§1.1 ignores quoting.** `render.has_hidden` checks quoted text too, so `echo '‮'` as a
  proposal is rejected, although §1.1 forbids these characters only outside quotes.
- **Threat model edited** (`.oss-scanner/threat_model.md:114-121, 185-189, 221-228`).
  Please check the wording matches what you want the scanner to treat as in scope.
- License: `tree-sitter-bash` declares MIT; the `tree-sitter` wheel declares no license
  field. Confirm per INTEGRATION §4 (human-only).

## What I ruled out

- **A fixed 256-byte slice plus the old regex.** The reviewer suggested this, but it
  fails open: `{` + 300 name bytes + `}>x` has no `{` inside the last 256 bytes, so the
  regex would not match and the named fd would pass. The byte walk in `_named_fd_before`
  is 17 lines and fails closed past the window. The test cases `{a*300}>x` and
  `exec {a*300}>x` (`tests/test_policy_gate.py:278-279`) hold that.
- **Charging bytes to the node budget (`work`).** A 50 KB paste would fall to decision C
  at about 20 000 bytes. A separate byte cap does not.

## Refuting my own test

- **(a) Is the red genuine? Yes.** I ran `engine/scripts/run-verify.sh` with `PDCA_BUNDLE`
  set to the absolute bundle path and `PDCA_WORKTREE` set.
  - Red leg (production hunks reverted): 90 ran, 90 failed, 0 collection errors.
  - Green leg: all passed.
  - Verdict: `PDCA-EVIDENCE: C4 PASS — red without the fix (90 of 90 failed), green
    with it`.
  - The new cases also bind the iteration-2 changes on their own. Against the
    iteration-1 code, 8 of 90 failed:
    - `2>&1-`;
    - 4 move forms (`>&3-`, `1>&3-`, `>&'3'-`, 40-digit move; `<&3-` was already rejected
      by the catch-all);
    - 3 budget tests.
  - Mutation checks, each on the iteration-2 code:

    | Mutation | Result |
    |---|---|
    | old whole-prefix regex scan restored | 1 failed (timing test, 2.75 s > 1.0 s) |
    | move-form branch disabled (`elif False:`) | 5 failed |

- **(b) Does the test drive production code? Yes.**
  - Every case calls the real `nl_shell.gate.classify` or `parse.walk`, with the real
    pinned grammar.
  - The timing test passes a `parse.Budget` with a larger `input_bytes` to the
    production `walk`. It only raises the cap, so that the production scan's cost
    scaling shows. Nothing is stubbed.
  - Monkeypatches only wrap `rules.classify` or delete one `HANDLERS` entry.
- **(c) Does the fixture include the fault? Yes.**
  - The move-form cases are the exact inputs the reviewer reproduced in bash (`>&3-`,
    `1>&3-`) plus `>&'3'-` and `<&3-`.
  - The budget cases use the reviewer's slow shapes (a multi-MB word; a long word plus
    6000 `>x`).
  - The over-the-cap case includes one that is under the cap in characters and over it
    in bytes, so a char-only check would miss it.

## Environment and commit-readiness

- `tree-sitter` 0.26.0 and `tree-sitter-bash` 0.25.1 are installed in the pdca `.venv`.
  No missing external dependency.
- Full target suite (`python -m pytest`, the CI command, under `timeout`):
  1191 passed, 1 skipped, 1 warning. The warning is not from the gate: the gate file
  passes under `-W error`.
- The target has no formatter, linter or pre-commit config. CI runs pytest, the
  frozen-records immutability check (not touched here) and `scripts/docs_links.py`
  (clean). `git diff --check` is clean. New lines are at most 92 characters, as in the
  code around them.
- Scratch: during the mutation checks I kept a copy of `parse.py` at
  `$PDCA_WORKTREE/.pytest_cache/parse.py.keep`, which git ignores, and restored from it.
  I did not delete it; the harness reclaims the worktree.
- I ran `git add -N` in the worktree so `git diff a6efb0a` includes the new files. Nothing
  is committed.

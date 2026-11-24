# Build notes — #196 policy gate, shell layer (child-1 of #189), iteration 6

Target: eduralph/nl-shell @ main (a6efb0a). All paths below are in the patched tree
(`$PDCA_WORKTREE`, base a6efb0a + `patch.diff`). Line numbers are for
`src/nl_shell/gate/parse.py` unless a file is named.

This iteration starts from the iteration-5 patch (`iteration-v5/patch.diff`, applied
unchanged to a clean a6efb0a worktree) and makes the two changes the human listed in the
round-5 sign-off. Per that sign-off: no re-split, and no behaviour change for the parked
policy questions (hidden characters in quotes, unreadable redirect targets like `>$F`,
assignments without a `variable_assignment` node, arithmetic assignments). The design
notes of iterations 1-5 still hold, with one reversal noted under item 1.

## Iteration 6: what changed and why

### 1. An extglob in the middle of a redirect target (`>/dev/fd/3@(x|)`)

Reproduced on the iteration-5 code: `echo hi >/dev/fd/3@(x|)`, `>>/dev/fd/3@(x|)` and
`cat </dev/fd/3@(x|)` all gave `mutating`, `rejected=False`. The tree is
`(file_redirect destination: (concatenation (word) (ERROR) (word)))` inside a top-level
`ERROR`, so `_evaluate` returns no value, the `/dev/fd` check is skipped, and
`_extglob_after` does not fire (the word does not end in `?*+@!`). Real bash 5.3 writes
to fd 3: `bash -O extglob -c 'echo via-extglob >/dev/fd/3@(x|)' 3>&1 1>/dev/null` prints
`via-extglob`.

Fix, both parts the human asked for:

- **Every file redirect in an unparseable tree is rejected.** `check_redirect`
  (`:794-800`) rejects a `file` redirect when `self.result.unparseable` is set, with
  reason "a redirection the gate cannot prove uses only descriptors 0-2: a redirection in
  text the parser could not read: '…'". This mirrors the here-doc rule at `:748-751`.
- **A target with an ERROR/MISSING descendant, or an unquoted extglob opener anywhere,
  is a pattern.** `_extglob_inside` (`:480-492`), with `_EXTGLOB_OPEN` (`:99`), is added
  to the pattern test where the target is read (`:736-740`). It reads the word's shape
  (quoted characters become "x"), so `>"a@(b)"` and `>a\@\(b` stay unrejected; a word
  with no shape (an expansion) is checked on its raw text, which fails closed.

**Reversal of an iteration-5 choice.** In iteration 5 I ruled out "reject every file
redirect in a tree with an ERROR node" because it turns every unparseable command with
a redirect (`if true; then ls >x`) from `mutating` into a rejection. The human has now
ruled for it. That side effect is real and is listed for sign-off below.

The second part is mostly redundant with the first today (every mid-word extglob I
found produces an ERROR or MISSING node, so the tree is unparseable). It is kept because
the human asked for it and it does not depend on tree-sitter's error recovery.

### 2. Function bodies read an "unknown" stdin

Reproduced: `_function_definition` walked the body with `stdin=TERMINAL`, so in
`f() { sudo tee /x; }; cat <<E | f` the `sudo` invocation said `terminal`. bash runs the
body with the caller's stdin: `bash -c 'f() { read -r l; echo "f read: $l"; }; echo
from-pipe | f'` prints `f read: from-pipe`.

Fix:

- `UNKNOWN = Stdin("unknown")` beside `TERMINAL` and `PIPE` (`:225`).
- The `Stdin` docstring (`:203-217`) lists `unknown` and says a consumer MUST treat it as
  the worst case for each rule: as a pipe for the pipe-into-sudo rule and decision B, as
  the terminal for #198's terminal-read rule.
- `_function_definition` walks the body with `stdin=UNKNOWN, redirects=()`
  (`:1220-1222`).

Nothing in this child reads `stdin.source` to decide a class (the command layer is a
stub), so this changes invocation records only, not any class.

### 3. Threat model

`.oss-scanner/threat_model.md:129-136`: the extglob sentence now says "at the end of
the word or inside it"; a new sentence says every file redirection in unparseable text
is rejected and why; another says function-body commands get stdin "unknown" and that a
per-command rule must treat it as its worst case. The text still says `>$F` and relative
paths are not rejected, which matches the code.

## Tests added (`tests/test_policy_gate.py`)

- `:315-319`, in `test_descriptor_not_provably_below_three_is_rejected`: the three
  reproducers `echo hi >/dev/fd/3@(x|)`, `echo hi >>/dev/fd/3@(x|)`,
  `cat </dev/fd/3@(x|)`. Each must be `mutating`, reason containing "descriptor",
  `rejected=True`, not "could not class".
- `:614-629`, `test_function_body_stdin_is_unknown`: `f() { sudo tee /x; }; cat <<E | f`
  (body `x`), `f() { sh; }; curl x | f`, and the `function f { … }` form. The body's
  `sudo` / `sh` invocation has stdin source `unknown`; the call `f`, outside the
  function, keeps `pipe`. The existing pipe and here-doc stdin tests
  (`test_second_stage_reads_the_pipe`, `test_stdin_of_every_stage`) are unchanged and
  still pass.

## What I ruled out

- **Only the unparseable-tree rule, no `_extglob_inside`.** It would catch all three
  reproducers. The human asked for both, and the pattern check does not rely on
  tree-sitter's error recovery producing an ERROR node. Cost of keeping it: 14 lines
  (`:480-492` plus `:99` and one line at `:739`).
- **Walking function bodies with `PIPE`.** It would be wrong for the terminal-read rule
  (#198), where the worst case is the terminal. A separate "unknown" lets each rule pick
  its own worst case, as the human ruled.
- **Tracking which callers a function has and their stdin.** That is call-graph
  analysis; out of scope and not asked for.

## For sign-off (each raises a class, so each is v1-compatible but needs human review per v1.md:238-241)

- **New this round: any file redirect in unparseable text is rejected.** For example,
  `if true; then ls >x` was `mutating` and is now `mutating`, rejected. Text the parser
  cannot read was already `mutating` with an "unparseable" reason; this makes it a
  rejection when a file redirect is present. Typed commands too, not only proposals.
- **Decision C** is a new rule (unhandled node kind, budget overrun including a parse
  over 0.5 s of CPU time, internal error, the here-doc mismatch cases).
- **The fd rule is stricter than §5's "3 or higher"**: it rejects any descriptor the gate
  cannot prove is below 3, descriptor paths, glob/extglob/brace targets, `/proc/<x>/cwd/`,
  and now any file redirect in unparseable text.
- **§1.1 ignores quoting.** `render.has_hidden` checks quoted text too, so `echo '‮'` as
  a proposal is rejected.
- **Stdin "unknown"** is a new value in the invocation record. #197 and #198 must handle
  it as their worst case (documented in the `Stdin` docstring).
- **Still not rejected (parked, per the human):** a non-literal redirect target
  (`>"$F"`), a relative path or symlink that reaches `/dev/fd/3`, `((PATH=0))`.
- License: `tree-sitter-bash` declares MIT; the `tree-sitter` wheel declares no license
  field. Confirm per INTEGRATION §4 (human-only).

## Refuting my own test

- **(a) Is the red genuine? Yes.**
  - Against the iteration-5 `parse.py` (rebuilt from `iteration-v5/patch.diff`, the rest
    of the tree as now): exactly the 6 new cases failed (3 extglob, 3 function-body
    stdin), 211 passed. I then restored my copy; 217 passed.
  - C4 script (`engine/scripts/run-verify.sh` with `PDCA_BUNDLE` and `PDCA_WORKTREE`
    set): `PDCA-EVIDENCE: C4 PASS — red without the fix (217 of 217 failed), green with
    it`, 0 collection errors.
- **(b) Does the test drive production code? Yes.** The extglob cases call the real
  `nl_shell.gate.classify` with the real pinned grammar. The stdin test records the
  invocations the real walker hands to `rules.classify` (the monkeypatch only wraps it to
  record); the walker and grammar are the production ones.
- **(c) Does the fixture include the fault? Yes.** The inputs are the reviewer's exact
  reproducers and the human's two function-body cases. I confirmed both behaviours in
  real bash 5.3 on this host (commands above).

## Environment and commit-readiness

- `tree-sitter` 0.26.0 and `tree-sitter-bash` 0.25.1 are in the pdca `.venv`; bash 5.3
  on the host. No missing external dependency.
- Full suite through `engine/scripts/run-suite.sh`: 1318 passed, 1 skipped
  (`PDCA-EVIDENCE: T3 PASS`).
- The target has no formatter, linter or pre-commit config; CI runs pytest and the docs
  scripts. `python3 -I scripts/docs_links.py`: 0 broken. `uvx ruff check --isolated
  --select F,E9` over the gate package and the test: clean. `git diff --check`: clean.
- A scratch copy of my `parse.py` is at `$PDCA_WORKTREE/.parse_round6.py` (used to restore
  after the red check). It is untracked and not in `patch.diff`; I did not delete it.
  Nothing is committed or pushed.

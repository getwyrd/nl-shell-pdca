# Build notes — #196 policy gate, shell layer (child-1 of #189), iteration 4

Target: eduralph/nl-shell @ main (a6efb0a). All paths below are in the patched tree
(`$PDCA_WORKTREE`, base a6efb0a + `patch.diff`). `patch.diff` applies cleanly to a6efb0a
(checked with `git apply --cached --check` on a fresh index read from a6efb0a), and
`git diff a6efb0a` in the worktree is byte-identical to it.

This iteration starts from the iteration-3 patch (`iteration-v3/patch.diff`, applied
unchanged) and fixes the six items the human listed in the round-3 sign-off. Per that
sign-off: no re-split, and no widening for the two open scope questions (non-literal
redirect targets like `>$F`; `((PATH=0))`). Design notes of iterations 1-3 still hold.
Line numbers are for `src/nl_shell/gate/parse.py` unless a file is named.

## Iteration 4: what changed and why

Each bypass was first reproduced against the iteration-3 code (probe scripts in
`$PDCA_WORKTREE/.probe/`), and bash 5.3.9 on this host was used to confirm how bash
reads each form.

### 1. Here-doc delimiters with quotes, and here-docs in an ERROR tree

bash computes the end line from the word after `<<` by quote removal. tree-sitter-bash
0.25.1 does not always agree. Confirmed with bash:

- `cat <<E"F"` — bash ends at `EF`; tree-sitter ends at the literal line `E"F"`, so the
  lines in between are here-doc text to the parser but commands to bash.
- `cat <<$'E'` — bash 5.3 decodes `$'E'` to `E` and ends there; tree-sitter waits for
  `$'E'` and records the lines in between as literal stdin text.
- `cat <<E⏎E ⏎…` — tree-sitter ends at `E ` (trailing blank); bash does not.

Fix:

- `_heredoc_delimiter` (`parse.py:787`) computes bash's delimiter: backslash, single and
  double quotes are removed, nothing is expanded. A `$'…'` or `$"…"` part fails closed
  (`HeredocMismatch`, `:148`), because bash decodes them and the gate does not.
- `_check_heredoc_end` (`:824`) fails closed unless the **whole source line** the parser
  ends on (leading tabs stripped for `<<-`) equals that delimiter, and no body line
  before it does. I compare the whole line, not the `heredoc_end` node text, because the
  node text for `E ` is `E`. Called from `_Walker.redirect` (`:654-661`).
- A here-doc in an unparseable tree fails closed: in `_Walker.redirect` when
  `result.unparseable` is set (`:654`), and in the new `ERROR` handler `_error` (`:934`,
  registered at `:1141`) when an ERROR node holds a `<<`/`<<-` token. This covers
  `cat <<E;cat <<F` on one line, `cat <<"E"x`, and `cat <<E` with no body.

The "no body line equals the delimiter" half of `_check_heredoc_end` is defence in depth:
with the pinned grammar I found no input where the end line matches but an earlier body
line also does, so no test reaches it. It costs one pass over the body.

### 2. Descriptor paths: globs, braces, `/proc/<x>/root`, `..`

- Globbed or brace-expanded redirect targets are rejected (`check_redirect`, `:684`).
  bash expands both in a redirect word (checked: `>b{1..1}` creates `b1`;
  `>/dev/f[d]/3` writes to fd 3). `Redirect` has a new `pattern` field (`:235`), set by
  `_pattern` (`:396`) from the unquoted shape (`*?[`, `{a,b}`) or a `brace_expression`
  node — tree-sitter gives `{3..3}` its own node, so the shape check alone missed it
  (my first version did; the `{3..3}` test caught it). Quoted or escaped glob characters
  are not a pattern (`>'/tmp/a*'`, `>/tmp/a\?` stay "output redirection").
- `/proc/<pid>/root` and `/proc/<pid>/task/<tid>/root` are links to `/`, so
  `_descriptor_path` strips them, repeatedly, after `normpath` (`_PROC_ROOT` at `:85`,
  loop at `:510-513`).
- A `..` in a path that also names `dev` or `proc` returns "?" (not provably below 3,
  `:505`). Reason: `..` after a link goes where the link points, not where the text
  does. I found `/dev/fd/../root/dev/fd/3` myself: `/dev/fd` → `/proc/self/fd`, so this
  is `/proc/self/root/dev/fd/3`, i.e. fd 3, while `normpath` gives `/dev/root/dev/fd/3`.

### 3. Named fd with an array subscript

bash accepts `{a[0]}>x` as a named descriptor (checked: `exec {a[0]}>/dev/null` sets
`a[0]=10`). tree-sitter reads `{a[0]}` as an argument concatenation. `_named_fd_before`
now treats any `]}` right before the redirect as a named descriptor (`:547`). This
over-rejects a word ending in `]}` glued to a redirect (`echo a]}>x`); that is the
fail-closed direction and rare.

### 4. Line continuation after `$` or backquote

bash removes backslash-newline inside double quotes and unquoted here-docs before it
reads expansions, so `"$\⏎(rm x)"` runs `rm x`. tree-sitter reads it as plain string
content, which iteration 3 treated as "inside a token" and let through. Now a
continuation whose preceding byte is `$` or `` ` `` fails closed wherever it is
(`_EXPANSION_LEADS` at `:92`, check at `:349`). This also rejects the same bytes in
single quotes or a comment, where bash keeps them; fail-closed direction.

### 5. bash 5.3 function substitution `${ cmd; }` / `${| cmd; }`

Confirmed: bash 5.3.9 runs `echo ${ echo RAN5; }`. tree-sitter 0.25.1 gives an
`expansion` with an ERROR, or a bare ERROR, and the command is never walked. `walk` now
fails closed (`FunctionSubstitution`, `:152`) when the source matches `${` followed by a
blank, newline or `|`, with any backslash-newlines between (`_FUNSUB` at `:89`, check at
`:321`, before the parse). It is a byte scan, so it covers here-doc bodies and double
quotes too, and also over-rejects the same text in single quotes.

### 6. Threat model: the "linear time" claim

Measured on this host: `${` repeated to the 64 KiB cap takes 2.46 s to parse (8 KiB:
0.05 s, 16 KiB: 0.17 s, 32 KiB: 0.63 s — quadratic). Other repeated units I tried
(`"$(`, `$((`, `` ` ``, `"${x`) stay under 0.2 s. The comment at `parse.py:44-47` and the
threat model (`.oss-scanner/threat_model.md:114-134`) now say the byte cap bounds what
the parser sees, the walk is linear, and the parse is not (about 2.4 s at the cap). The
threat model also now says exactly what the fd rule rejects, and that `>$F` and a
relative path in a directory such as `/dev/fd` are not rejected by it (the open scope
question, left as is per the human).

### Also

- Removed an unused `classify` import in `test_many_redirections_after_a_long_word_stay_cheap`
  (left over from iteration 3; `ruff check --select F` flagged it).

## What I ruled out

- **Decoding `$'…'` delimiters** like bash does. It needs a full ANSI-C decoder for one
  rare form. Failing closed is 3 lines (`:793-796`).
- **Rejecting only absolute glob targets** (a pattern that could match `/dev/fd/N`).
  A relative glob in cwd `/dev/fd` works too, and the human asked to reject globbed
  targets; the simple rule is easier to check. It does reject `cat < *.log`.
- **Checking `${ ` only outside single quotes.** That needs quote tracking over the raw
  text, which is the second-lexer problem from iteration 3. The byte scan is one regex.
- **Rejecting every `..` path.** Only paths that also name `dev` or `proc` can reach a
  descriptor through the links this rule knows; other `..` paths are #190's
  filesystem-state question.

## For sign-off (each raises a class, so each is v1-compatible but needs human review per v1.md:238-241)

- **Decision C** is a new rule: an unhandled node kind, the budget exceeded (64 KiB of
  text, 20 000 nodes, depth 150), any internal error, a split line continuation, an
  unread here-doc substitution, and now a here-doc whose end line bash may read
  differently, a here-doc in an ERROR tree, a continuation after `$`/backquote, and
  bash 5.3's `${ cmd; }` give `privileged`, rejected, "could not class". The spec text
  for it is #197's edit.
- **The fd rule is stricter than §5.** §5 rejects descriptors 3 and up; the gate rejects
  any descriptor it cannot prove is below 3: `>&$x`, `<&$fd`, `>&"$X"`, `2>&${FD}`, named
  fds (now including `{a[0]}`), a non-number after `<&`, the move form `[n]>&digit-`,
  paths that open a descriptor (`/dev/fd/N`, `/proc/*/fd/N`, now also through
  `/proc/*/root/` and with `..`), and now **any globbed or brace-expanded redirect
  target** (`cat < *.log` is rejected).
- **Still not rejected (open, per the human's round-3 note):** a non-literal redirect
  target (`>"$F"`), a relative path or symlink that reaches `/dev/fd/3`, and
  `((PATH=0))`. These are only `mutating`.
- **§1.1 ignores quoting.** `render.has_hidden` checks quoted text too, so `echo '‮'` as
  a proposal is rejected, although §1.1 forbids these characters only outside quotes.
- **A `~` word is non-literal** even in shapes bash would not expand in POSIX mode.
- **Threat model edited** (`.oss-scanner/threat_model.md:114-134, 198-202, 234-241`).
- License: `tree-sitter-bash` declares MIT; the `tree-sitter` wheel declares no license
  field. Confirm per INTEGRATION §4 (human-only).

## Refuting my own test

- **(a) Is the red genuine? Yes.**
  - Against the iteration-3 `parse.py` (extracted from `iteration-v3/patch.diff`, the
    rest of the tree as now): 26 of 189 cases failed — all 11 new descriptor cases
    (globs, braces, `/proc/*/root`, `..`, `{a[0]}`), 2 of the 4 new continuation cases
    (`"$\⏎(…)"`, `"$\⏎{x}"`; the backquote and here-doc-body forms were already caught
    by iteration 3 and stay as regression cases), all 6 function-substitution cases, and
    all 7 here-doc end-line cases. The 5 quoted-delimiter positives pass on both, as they
    should (they guard against over-rejecting). I restored the file afterwards (`cmp`
    with my saved copy: equal).
  - C4 script (`engine/scripts/run-verify.sh` with `PDCA_BUNDLE` and `PDCA_WORKTREE`
    set): green leg 189 ran, 0 failed; red leg 189 ran, 189 failed, 0 collection errors
    (each test imports `nl_shell.gate` inside the function). Verdict:
    `PDCA-EVIDENCE: C4 PASS — red without the fix (189 of 189 failed), green with it`.
- **(b) Does the test drive production code? Yes.** Every case calls the real
  `nl_shell.gate.classify` or `parse.walk` with the real pinned grammar. Monkeypatches
  only wrap `rules.classify` to record invocations, or remove one `HANDLERS` entry.
- **(c) Does the fixture include the fault? Yes.** The inputs are the human's listed
  reproductions (`<<E"F"`, `<<$'E'`, `<<\E`, `cat <<E;cat <<F`, `>/dev/f?/3`,
  `>>/d*/fd/3`, `>/proc/self/root/dev/fd/3`, `>/proc/self/root/proc/self/fd/3`,
  `{a[0]}>&-`, `{a[0]}>x`, `"$\⏎(rm x)"`, `${ cmd; }`, `${| cmd; }`, funsub in a
  here-doc body), plus shapes I found and checked against bash (`{3..3}`, `E''`,
  trailing-blank end line, `/dev/fd/../root/…`, `/proc/self/task/1/root/…`).

## Environment and commit-readiness

- `tree-sitter` 0.26.0 and `tree-sitter-bash` 0.25.1 are installed in the pdca `.venv`;
  bash 5.3.9 on the host. No missing external dependency.
- Full target suite through `engine/scripts/run-suite.sh` on the final tree: 1290 passed,
  1 skipped. `scripts/docs_links.py`: 64 links, 0 broken. `git diff --check` clean.
- The target has no formatter, linter or pre-commit config, and CI runs only pytest and
  `scripts/docs_links.py`. I ran `uvx ruff check --isolated --select F,E9` over the gate
  package and the test as a sanity check: clean after the import fix. New lines stay
  under 92 characters, as in the code around them.
- Scratch files are in `$PDCA_WORKTREE/.probe/` (probes, bash checks, saved `parse.py`
  copies, a scratch index). They are untracked and not in `patch.diff`; I did not delete
  them. New files are `git add -N` so `git diff a6efb0a` includes them. Nothing is
  committed or pushed.

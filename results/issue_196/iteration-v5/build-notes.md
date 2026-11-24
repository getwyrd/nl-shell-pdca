# Build notes — #196 policy gate, shell layer (child-1 of #189), iteration 5

Target: eduralph/nl-shell @ main (a6efb0a). All paths below are in the patched tree
(`$PDCA_WORKTREE`, base a6efb0a + `patch.diff`). `patch.diff` applies cleanly to a6efb0a
(checked with `git apply --cached --check` on a scratch index read from a6efb0a), and
`git diff a6efb0a` in the worktree is byte-identical to it.

This iteration starts from the iteration-4 patch (`iteration-v4/patch.diff`, applied
unchanged) and fixes the four items the human listed in the round-4 sign-off. Per that
sign-off: no re-split, and no widening for the open scope questions (non-literal
redirect targets like `>$F`; arithmetic assignments). The design notes of iterations 1-4
still hold. Line numbers are for `src/nl_shell/gate/parse.py` unless a file is named.

## Iteration 5: what changed and why

Each finding was first reproduced against the iteration-4 code (probe scripts in
`$PDCA_WORKTREE/.probe/`). bash 5.3.9 on this host confirmed how bash reads each form.

### 1. Two here-docs joined on one line (`cat <<A | cat <<B`, `&&`, `||`)

Reproduced: the gate gave `mutating`, not rejected, with the line after `B` recorded as
`A`'s literal here-doc text. bash runs that line (checked with all three operators).
tree-sitter-bash puts B's `heredoc_redirect` inside A's (the pipeline after `<<A` is a
child of A's redirect node) and hands A's body to B.

The human allowed either fix ("or"). I did both, because each is small and they catch
different shapes:

- **Nesting check.** `_redirect` (`:1056-1065`) counts the here-doc redirects whose
  children are being walked (`open_heredocs`, `:658`). `_Walker.redirect` fails closed
  (`HeredocMismatch`) when a here-doc is read while another is open (`:725-728`).
- **Order check.** Each here-doc records where its delimiter and its body start (`:730`).
  After the walk, `check_heredoc_order` (`:749`, called at `:351`) fails closed if the
  bodies, sorted by delimiter position, are not in source order.

The order check is tested on its own: `test_heredoc_bodies_out_of_order_fail_closed`
(`tests/test_policy_gate.py:702`) swaps in a redirect handler that does not mark a
here-doc open, and the attack still fails closed with "out of order".

Side effect: a here-doc inside a `$(…)` inside a here-doc body also counts as nested and
fails closed. Iteration 4 already failed closed on that shape (the reviewer noted it), so
this is not a new refusal.

### 2. Extglob redirect targets (`>/dev/@(fd)/3`, `+(…)`, `!(…)`)

Reproduced: `mutating`, not rejected. With extglob on (Ubuntu's bash-completion turns it
on; `bash -ic 'shopt extglob'` prints `on` here), bash globs these. I checked that
`>/dev/+(fd)/3` and `>/dev/@(fd)/3` write to fd 3. tree-sitter-bash ends the target word
at the `(`, so the target text is `/dev/@`.

Fix: `_extglob_after` (`:460`) says a target is a pattern when its last source byte is
one of `?*+@!` and the next byte is `(` (`_EXTGLOB_LEADS`, `:97`). It is used where the
redirect's target is read (`:713`). The existing pattern rule then rejects it. A quoted
lead (`'@'(`) ends in a quote byte, so it is not a pattern. An escaped one (`\@(`) is
treated as one, which fails closed.

I chose this over the human's other option, "reject any file redirect in a tree with an
ERROR node", because that one would turn every unparseable command with a redirect
(`if true; then ls >x`, which is `mutating` today) into a rejection. The byte check is 6
lines and rejects only the extglob shape.

### 3. `/proc/<x>/cwd/` and `/proc/<x>/task/<t>/cwd/` targets

Reproduced: `mutating`, not rejected. Checked with bash: `cd /dev/fd && echo x
>/proc/self/cwd/3` writes to fd 3. Fix: `_descriptor_path` returns `"?"` (not provably
below 3, so rejected) for any path under `/proc/<x>/cwd` or `/proc/<x>/task/<t>/cwd`,
after the `/proc/<x>/root` prefixes are stripped (`_PROC_CWD` at `:93`, check at `:575`).
This also rejects an ordinary file reached that way (`>/proc/self/cwd/notes.txt`). That
is the fail-closed direction, and nobody types that path by hand.

### 4. Parse time: bounded, not just documented

Measured at the 64 KiB cap on this host: `$[` repeated takes 9.5 s, `a=(` 8.4 s, `${`
2.6 s. I bounded the parse instead of only fixing the figure, because the brief asks for
"a total-work budget across the whole classification", and a parse is part of that.

- `_parse` (`:355-379`) calls `Parser.parse` in its read-callback form, which in
  tree-sitter 0.26.0 takes a `progress_callback`. The callback returns True (cancel) once
  the parse has used the CPU time left in the budget. On a cancel, tree-sitter raises
  `ValueError("Parsing failed")`; `_parse` turns that into `BudgetExceeded`, which is
  decision C ("could not class").
- The limit is `MAX_PARSE_SECONDS = 0.5` (`:53`), held in the shared `Budget`
  (`parse_seconds`, `parsing`, `spend_parse` at `:195`), so a later walk on the same
  budget (`bash -c` text, #197) is charged too.
- CPU time (`time.thread_time`), not wall time, so a busy machine does not cancel a
  normal parse. I measured how often the callback fires: about every 14 ms on the
  slowest input, so a cancel lands within about 15 ms of the limit. Normal text at the
  cap parses in under 10 ms, so the limit has about 50x headroom.
- **`parser.reset()` after a cancel matters.** The parser is cached (`_parser`, `:317`).
  Without the reset, tree-sitter resumes the cancelled parse on the next call: I
  checked, and `walk("ls -l")` after a cancelled parse returned **no invocations**, so a
  command would vanish from the gate. `test_parse_budget_is_shared_across_walks`
  (`tests/test_policy_gate.py:800`) asserts the next walk's invocation is `ls -l`, and it
  goes red when the reset is removed (I checked).
- Comments and docs updated: `parse.py:44-53`, `src/nl_shell/gate/__init__.py:21-24`,
  `.oss-scanner/threat_model.md:114-140` (the measured figures, the 0.5 s CPU limit, the
  new rejections) and `:204-209` (the parse budget bounds tree-sitter's CPU time).

Timing test: `test_slow_parse_is_stopped` (`tests/test_policy_gate.py:784`), for `$[`,
`a=(` and `${` at the cap. Each must give "could not class" with a "parse budget" reason
in under 3 s wall time. All three took about 0.52 s.

### Also

- My first extglob comment said "Ubuntu's bash-completion". `tests/test_targets.py:680`
  (`test_no_os_name_in_package_code`) forbids OS names in package code, and the full
  suite caught it. Reworded to "bash-completion" (`:94`).

## What I ruled out

- **A node-count or callback-count limit for the parse.** Not tied to time: the
  callback fired 1572 times for 9.5 s on `$[`, but 983 times for 7 ms on ordinary
  commands. A count cannot tell those apart.
- **Wall-clock time for the parse limit.** It would cancel normal parses on a loaded
  machine. CPU time measures the parser's own work.
- **Only fixing the threat-model figure.** The human allowed it, but the next slow
  input someone finds would need another round. The bound is about 25 lines.
- **Rejecting every file redirect in an ERROR tree** (for extglob). See item 2.

## For sign-off (each raises a class, so each is v1-compatible but needs human review per v1.md:238-241)

- **Decision C** is a new rule. It now also covers a parse over 0.5 s of CPU time, and a
  here-doc on the line of another here-doc (`cat <<A | cat <<B`, `cat <<A && cat <<B`).
  Those ordinary two-here-doc lines are now refused (the round-4 reviewer flagged this
  as over-broad but intended).
- **The fd rule is stricter than §5.** In addition to iteration 4's list, it now rejects
  extglob targets (`>/dev/@(fd)/3`) and anything under `/proc/<x>/cwd/`.
- **The parse limit uses CPU time.** On a very slow machine a large but normal command
  could pass 0.5 s and be refused ("could not class"). That is the fail-closed
  direction. The limit is one constant (`MAX_PARSE_SECONDS`).
- **Still not rejected (open, per the human):** a non-literal redirect target (`>"$F"`),
  a relative path or symlink that reaches `/dev/fd/3`, and `((PATH=0))`. These are only
  `mutating`.
- **§1.1 ignores quoting.** `render.has_hidden` checks quoted text too, so `echo '‮'` as
  a proposal is rejected.
- License: `tree-sitter-bash` declares MIT; the `tree-sitter` wheel declares no license
  field. Confirm per INTEGRATION §4 (human-only).

## Refuting my own test

- **(a) Is the red genuine? Yes.**
  - Against the iteration-4 gate package (extracted from `iteration-v4/patch.diff`, the
    rest of the tree as now): 18 of 211 cases failed. They are the 5 extglob cases, the
    4 `/proc/*/cwd` cases, the 4 joined-here-doc cases, the order-check test, the 3
    slow-parse cases and the shared parse-budget test. `>/dev/fd/@(3)` passes on both:
    iteration 4 already rejected it, by luck. The two new positives (`>/tmp/a@b`,
    `>/tmp/a+`) and the two-here-docs-on-their-own-lines case pass on both, as they
    should (they guard against over-rejecting). I restored the files afterwards (`cmp`
    against my saved copies: equal).
  - With `parser.reset()` removed, `test_parse_budget_is_shared_across_walks` fails.
  - C4 script (`engine/scripts/run-verify.sh` with `PDCA_BUNDLE` and `PDCA_WORKTREE`
    set): green leg 211 ran, 0 failed; red leg 211 ran, 211 failed, 0 collection
    errors. Verdict: `PDCA-EVIDENCE: C4 PASS — red without the fix (211 of 211 failed),
    green with it`.
- **(b) Does the test drive production code? Yes.** Every case calls the real
  `nl_shell.gate.classify` or `parse.walk` with the real pinned grammar. Monkeypatches
  only wrap `rules.classify` to record invocations, remove one `HANDLERS` entry, or (in
  the order-check test) swap the here-doc redirect handler for one that skips the
  nesting mark, so the order check runs on its own.
- **(c) Does the fixture include the fault? Yes.** The inputs are the reviewers'
  reproductions (`cat <<A | cat <<B …`, the `&&`, `||` and `sudo tee` forms,
  `>/dev/@(fd)/3`, `>/dev/+(fd)/3`, `>/dev/!(x)/3`, `>/proc/@(self)/fd/3`,
  `>/@(dev)/fd/3`, `>/proc/self/cwd/3`, `>/proc/self/task/1/cwd/3`, and `$[`, `a=(`,
  `${` repeated to the real 64 KiB cap). I confirmed the here-doc, extglob and cwd
  forms run or write to fd 3 in real bash 5.3.9.

## Environment and commit-readiness

- `tree-sitter` 0.26.0 and `tree-sitter-bash` 0.25.1 are installed in the pdca `.venv`;
  bash 5.3.9 on the host. No missing external dependency.
- Full target suite through `engine/scripts/run-suite.sh` on the final tree: 1312
  passed, 1 skipped (`PDCA-EVIDENCE: T3 PASS`). `git diff --check` clean.
- The target has no formatter, linter or pre-commit config, and CI runs only pytest and
  `scripts/docs_links.py`. `uvx ruff check --isolated --select F,E9` over the gate
  package and the test: clean. New lines stay within 92 characters, like the code
  around them.
- Scratch files are in `$PDCA_WORKTREE/.probe/` (probes, saved copies of the gate files,
  a scratch index). They are untracked and not in `patch.diff`; I did not delete them.
  New files are `git add -N` so `git diff a6efb0a` includes them. Nothing is committed
  or pushed.

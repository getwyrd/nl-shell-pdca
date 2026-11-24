# Build notes — issue 196 / ast-policy-gate-shell-layer

Target: eduralph/nl-shell @ main (a6efb0a). Line numbers below are in the patched tree.

## What the patch does

| File | What |
|---|---|
| `pyproject.toml:17-20` | pins `tree-sitter==0.26.0`, `tree-sitter-bash==0.25.1` |
| `src/nl_shell/gate/__init__.py` | §1 pipeline: `classify` (`:147`), `Result` with the session-log `gate` shape (`:83`, `as_log`), decision C (`:143`, catch-all at `:152-156`), §1.1 via `render.has_hidden` (`:168`, proposal rejected like `proposal.py:133`), Rule 1 outcome (`:177-181`), shell-level §2/§3/§5 rules (`:213-264`), model label (`:208-209`), Rule 6 `escape` (`:94`) applied to every reason in `_Tally.result` |
| `src/nl_shell/gate/parse.py` | shell layer: size cap before parse (`:962`), `parse_source` (`:85`, the one parser entry point), Rule 1 `untrusted_features` (`:413`), Rule 3 `Stdin` (`:94`) and `lex_word` (`:193`), Rule 4 `judge_redirect` (`:293`), Rule 2 `HANDLERS` (`:918`, built from the grammar's named kinds at import) and `_check_walk` (`:939`, run on every classification), Rule 5 budget (`MAX_WORK`/`MAX_DEPTH` `:37-38`, enforced in `Walker.visit`) |
| `src/nl_shell/gate/rules.py:26` | command-layer stub: `mutating`, "not allowlisted" |
| `src/nl_shell/gate/live.py:12-18` | §7 stub, exact string "live-session resolution not implemented" |
| `src/nl_shell/gate/sensitive.py:12`, `words.py:12` | no-op stubs the pipeline calls (`__init__.py:199-202`) |
| `src/nl_shell/gate/vectors.py` | vector loader in the style of `targets.py:145-247` (`load` `:56`, `_validate` `:81`) |
| `targets/ubuntu-26.04/gate-vectors.toml` | rows 7, 13, 14, 15, 16, 23, 25, 30, 31 + header ("rows landed so far", complete when #192 lands) |
| `.oss-scanner/threat_model.md:157-179` | one bullet in "What must hold" stating the six rules as the code implements them. "Known gaps" untouched; `tests/test_failure_classes.py:827-839` stays green |
| `tests/test_policy_gate.py` | the test file the brief names |

## Design in one paragraph

The walk is a dispatch table (`parse.HANDLERS`) keyed by every named kind of the pinned
`tree_sitter.Language` plus `ERROR`. Most kinds use a generic "visit named children"
handler; the ones with meaning (pipeline, redirected_statement, command /
declaration_command / unset_command, function_definition, the three redirect kinds,
command/process substitution, variable_assignment, ERROR) have their own. Redirects on a
`redirected_statement` are passed down as `bound` to the node they really apply to: the
last stage of a pipeline (as bash does), the simple command itself, or a compound
command (where they set the stdin the commands inside inherit). After the walk,
`_check_walk` compares visits with the tree (each named node exactly once, one invocation
per simple-command node) and raises decision C on any mismatch. Every fact starts
unproven: `Stdin` defaults to `unknown` unless one of the listed forms applies, a word is
literal only if the lexer finds no unquoted expansion/glob/brace/extglob/tilde, and a
redirect is accepted only through `judge_redirect`'s explicit list.

## Judgment calls and deviations (please review)

1. **U5 / U8 vs the loose-operator list (brief conflict).** The brief says loose `<<`
   tokens inside an `ERROR` node are rejected, and also that typed U4–U8 are `mutating`,
   not rejected. With the pinned grammar, U5 (`cat <<E"F"`) puts a loose `<<` in an
   `ERROR` node, and U8 (`cat <<A <<B`) splits the second `<<` into a loose `<` plus a
   `file_redirect <B`. Following the loose-token list literally would reject both. I
   followed the success criterion with one sound rule: a redirect or loose operator
   whose bytes are a run of exactly two `<` in the text is a here-doc operator in every
   bash reading (never a file or dup redirect), so it is exempt from the
   untrusted-redirect clause — **only** when the text right before the run is empty or a
   literal 0–2 (`Walker.in_heredoc_run`, `parse.py:513`). Without that last condition
   `cat <<A {x}<<B` and `cat 3<<E"F"` slipped through; I found that in self-review, fixed
   it, and pinned it in `test_rule1_untrusted_redirects`. Loose `<<<`, `<`, `>&` etc. in
   `ERROR` are still rejected.
2. **`<>` never parses.** tree-sitter-bash 0.25.1 gives an `ERROR` node for `<>` after a
   command's arguments, so every `<>` input is untrusted and Rule 1's clause rejects it,
   even where Rule 4 alone would accept (`<>out.txt`). The Rule 4 table test therefore
   expects `<>` rows rejected (comment at `tests/test_policy_gate.py`, `rule4_table`), and
   a second test (`test_rule4_judge_alone`) checks `judge_redirect` on its own against
   the same oracle over the full cross product, including `<>`.
3. **No stdin fact from an untrusted tree** (`parse.py:968-970`). Stricter than the
   brief: every invocation's stdin is `unknown` when Rule 1 fires. Reason: U8's misparse
   would otherwise record `file B` for `cat`, which bash reads as a here-doc.
4. **Rule 4 path normalisation also drops `.` components**, not only repeated slashes:
   `/./dev/fd/3` would otherwise escape the `/dev/` check. `>&word` with a descriptor
   (`2>&out`) and `<&word` with a non-digit target are rejected (bash calls these
   ambiguous redirects anyway).
5. **Descriptor the tree left as a word.** The pinned grammar parses `cat 0>&-` and
   `cat 0</dev/null` as argument `0` plus a redirect with no descriptor. `_descriptor` /
   `Walker.adjacent_token` (`parse.py:505`, `:767`) take a digits-only or `{…}` token
   written right against the operator as the descriptor (and drop it from the words),
   as bash does. Any `{…}`-shaped token there is a named descriptor and never accepted.
6. **§3 name list skips prefix assignments.** `PAGER=sh git log` must stay `mutating`
   (rows 7, 13), so the name list applies to standalone and declaration assignments
   (the brief's wording); prefix ones give the §2 "prefix assignment" reason. §5's
   `SUDO_PROMPT`/`SUDO_ASKPASS` rejection applies to every `variable_assignment`,
   prefix included.
7. **No simple command ⇒ `mutating`** ("no simple command to class"). `PATH=x`, `>f`,
   a comment, or an empty string give no invocation, so nothing proves `read-only`.
8. **Work budget = 4096 named-node visits, depth 100.** Proposals are ≤ 2000 chars and the
   densest input I found (`$(:)` repeated) gives about one named node per byte, so no
   proposal reaches it. `a=(` repeated to 8 KiB (5464 named nodes) is decision C by
   budget, not by size — the brief allows this ("not decision C because of size"), and
   the test asserts exactly that. Dense typed input over ~4 K nodes is rejected
   (`privileged`, "could not class"); that is fail-closed but a user could hit it with a
   very large pasted script.
9. **Fail-closed false positives I accepted:** `$((1<<2))` counts as an unplaced here-doc
   and `$((2*(3)))` as an extglob opener — both make typed input `mutating`
   "unparseable" (a proposal is rejected). The lexer treats unquoted `{ } ( )`, any
   `~` after `=` or `:`, and `$'…'`/`$"…"` as non-literal.
10. **An extra module, `gate/vectors.py`.** The brief lists the files of `gate/` but asks
    for a loader without naming its home; I put it next to the gate rather than into
    `targets.py`, which documents that it reads only `target.toml` (`targets.py:4-6`).
11. **Rule 6 escaper.** `render.escape` leaves TAB/LF unescaped (they are in `VISIBLE`,
    `render.py:74`), but Rule 6 bans every C0 control in reasons, so `gate.escape`
    (`__init__.py:94`) escapes C0, DEL, C1, `is_hidden` characters and backslashes, using
    `render.escape_char`. It runs once, on every reason, in `_Tally.result`.
12. **Bad arguments are decision C**: a non-`str` command, an origin outside the two, a
    label outside the five. `classify` never raises (`except Exception`; a
    `KeyboardInterrupt` still propagates).

## Raises over spec v1 to confirm at sign-off (spec Versioning, `v1.md:238-241`)

- Decision C: any gate failure ⇒ `privileged`, rejected, "could not class".
- Rule 4 is stricter than §5's "fd 3 or higher": non-literal targets (`>"$f"`,
  `>/proc/$$/fd/3`), targets under `/dev` (other than the named ones), `/proc`, `/sys`,
  `..` components, and descriptors other than a literal `0`/`1`/`2` (including `01`) are
  rejected.
- Rule 1 rejects untrusted **proposals**, where §1.2 says only "at least mutating".
- The §1.1 check ignores quoting (`echo '‮'` as a proposal is rejected).
- The 8 KiB input cap (decision C before parsing).
- Also (from the list above): no stdin facts in untrusted text, `<>` always rejected by
  Rule 1 with this grammar, and the zero-invocation `mutating` floor.

## Verification

- Project runner, C4 (`engine/scripts/run-verify.sh` with `PDCA_BUNDLE` set):
  `PDCA-EVIDENCE: C4 PASS — red without the fix (157 of 157 failed), green with it`.
- Whole suite (`engine/scripts/run-suite.sh`): `1258 passed, 1 skipped` —
  `PDCA-EVIDENCE: T3 PASS`. This includes `tests/test_failure_classes.py:827-839`.
- Per-rule kill check: I switched off each rule's code in turn with a throwaway pytest
  plugin (not part of the patch) and re-ran the test file. Each rule's own test went red:
  Rule 1 (`untrusted_features` → `()`): 57 failed; Rule 2 (`_check_walk` → no-op): the 6
  skipped-children cases failed; Rule 3 (all stdin → `terminal`): `test_rule3_stdin_sources`
  failed; Rule 4 (`judge_redirect` → always accept): 15 failed incl. the table; Rule 5
  size cap off: `test_rule5_over_cap_is_never_parsed` failed; Rule 5 budget off:
  `test_rule5_work_budget_and_failures` failed; Rule 6 (`escape` → identity):
  `test_rule6_reasons_never_carry_raw_input` and the regression table failed.
- Fuzz: 30 000 random shell-like strings through `classify`; no exception, no internal
  error, no unexpected decision C.
- Rule 5 timing on this host: each 8 KiB input classifies well under the 5 s ceiling
  (the whole test file runs in about 1.4 s).

## Refuting my own test

- **(a) Genuine red?** Yes. The C4 runner reverted the production hunks (everything but
  `tests/`) and re-ran: 157 of 157 failed, collected with no import error (the test
  imports `nl_shell.gate` only inside functions). Separately, the per-rule kill check
  above shows each rule's test goes red when only that rule is off.
- **(b) Production path?** Yes. Every test calls the shipped `nl_shell.gate.classify`,
  `parse.shell_layer`, `parse.judge_redirect`, `parse.untrusted_features`, `live.resolve`
  and `vectors.load` with the real pinned tree-sitter-bash. Monkeypatching is used only to
  inject the faults the brief asks for (a removed or child-skipping handler, a failing
  parser entry point, an internal error, a `read-only` command layer for the §7 / §1.7
  proofs) — never to stand in for the code under test. The Rule 4 oracle and the grammar
  kind list in the test are written independently of the production code.
- **(c) Fixture includes the fault?** Yes. The inputs are the failing cases themselves:
  the U1–U15 untrusted inputs, `>&3` / `3>x` / `/proc/self/fd/3` / `{fd}` / 40-digit
  descriptor crossed over every operator, the misparsed here-doc descriptors, the deep
  and long inputs past the budget, the 8193-byte input, the raw ESC in a function name,
  and the real `targets/ubuntu-26.04/gate-vectors.toml` through the real loader.

## Commit-readiness

The target configures no formatter, linter or pre-commit hook (no `[tool.ruff]` /
`[tool.black]` in `pyproject.toml`, no `.pre-commit-config.yaml`; `.github/workflows` runs
only tests, docs checks and triage). I kept every new line at 92 columns or fewer (the
repo's existing files reach 97–103) and checked for unused imports and names with an AST
scan. `git apply --check -R patch.diff` succeeds on the worktree.

## Housekeeping

Scratch files I used while exploring live in the worktree only and are not in
`patch.diff`: `.explore.py`, `.t.py`, `.mut/`. The harness reclaims the worktree.

## Dependency note

`tree-sitter` and `tree-sitter-bash` were the brief's declared external dependency and are
installed in the pdca `.venv`; nothing else was needed. License confirmation
(`tree-sitter-bash` MIT; the `tree-sitter` wheel declares no license field) is the
human's at sign-off (INTEGRATION §4).

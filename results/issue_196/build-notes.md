# Build notes — issue 196, iteration 8

Target: eduralph/nl-shell @ main (a6efb0a). All paths below are in the worktree
`$PDCA_WORKTREE` with `patch.diff` applied.

## Starting point

I applied the iteration-v7 `patch.diff` (it applied cleanly on a6efb0a) and fixed only
the three implementation findings in the iteration-7 carry-forward. All 157 tests from v7
still pass. The rest of the design (six rules, stubs, loader, vectors) is unchanged from
v7. The 11 deferred findings in `deferred-findings.json` need human judgment and were not
touched.

## Changes this round

### 1. Words written against a redirect were dropped (C5 finding)

Cause: `_simple` dropped any word that ended where a redirect with no descriptor field
started, without checking that it was a descriptor. `_descriptor` already used a test
(digits or `{…}`), but the drop step did not.

Fix: one shared test, `_is_descriptor_token` (`src/nl_shell/gate/parse.py:778`), is used
both by `_descriptor` (`parse.py:790`) and by the drop step (`parse.py:679`). A token is a
descriptor only if it is all digits or has the `{…}` form. Anything else stays a word, as
in bash.

I also removed v7's `text.endswith("}")` branch in `_descriptor`. It made `echo x}>f`
treat `x}` as a descriptor (so the redirect was rejected and the word dropped). In bash,
`x}` is an ordinary word and the redirect goes to stdout. The new result is: words
`echo x}`, redirect `>f`, `mutating` with "output redirection". A `{…}` token that bash
would not take as a named descriptor (e.g. `{1x}`) is still taken as a descriptor here,
so its redirect is rejected. That is stricter than bash, and because the whole command
is rejected, losing the word does not matter.

Results after the fix:
- `rm -rf />/dev/null` → `['rm', '-rf', '/']`
- `sudo rm -rf /etc>x` → `['sudo', 'rm', '-rf', '/etc']`
- `rm -rf ~>/dev/null` → `['rm', '-rf', '~']`
- `cat a3>f` → `['cat', 'a3']`
- `cat 0>&-` → `['cat']`, descriptor `0` (unchanged)

### 2. An assignment with a redirect and no command word was treated as a prefix (C5 finding)

Cause: tree-sitter parses `PATH=/tmp/evil >/dev/null` with a zero-width `MISSING`
`command_name`. So the `name` field exists, the v7 "no name" check never fired, and the
assignment got role `prefix`. `_assignments` (`src/nl_shell/gate/__init__.py:234`) skips
§3 for prefixes.

Fix:
- `parse.py:654-663`: a `name` child counts as a name only if it has non-zero width. A
  zero-width name goes into `unread`. It is still walked (`parse.py:696`), so Rule 2's
  visit count holds, but it is not a word.
- `parse.py:686`: with no real name, assignments before it get role `standalone`.
- `__init__.py:234`: in an untrusted tree, the `prefix` role no longer excuses §3. The
  dump of `PATH=x >/dev/null; cat` shows why: tree-sitter puts the `;` in an `ERROR` node
  and takes `cat` as the command name. So the assignment looks like a prefix of `cat`,
  but bash runs `PATH=x >/dev/null` on its own and keeps `PATH`. A tree that is not
  trusted cannot prove that an assignment lasts for only one command.
- `__init__.py:249`: `_shell_rules` skips the "command word is not a literal" check when
  there is no command word (the empty word `parse.py:715` inserts). Without this, these
  inputs gave the reason "command word is not a literal: " with nothing after the colon.

Results: `PATH=/tmp/evil >/dev/null`, `LD_PRELOAD=/tmp/x.so 2>/dev/null`, `IFS=x 2>&1`
and `PATH=x >/dev/null; cat` are now `session-altering`, with "assignment to <NAME>".
They are typed, not rejected, and keep "unparseable: missing token" / "syntax error",
because the tree has a `MISSING`/`ERROR` node (Rule 1).

### 3. `exec </tmp/x; sudo tee /etc/y` recorded `sudo` stdin as `terminal` (Medium finding)

Fix: `shell_layer` (`parse.py:984-991`). If any invocation can change the shell's own
stdin, every *other* invocation's stdin becomes `unknown`. `_may_rewire_stdin`
(`parse.py:999`) is true for:
- `exec` with any redirect;
- `eval`, `source`, `.` (code the gate does not see);
- a non-literal command word (`$x <f` could be `exec <f`);
- any of these behind `command` / `builtin` (and their options).

The finding asked for "every later invocation". I chose "every other invocation"
instead, because a loop can run a command again after the `exec`:
`while :; do cat; exec <x; done` gives `cat` the file on the second pass, even though
`cat` comes first in the text. "Later in the text" would mark `cat` as `terminal`, which
is not proven. Costs of this choice:
- Over-approximation: `exec 2>/dev/null; cat` also makes `cat` `unknown`, even though
  fd 0 is not touched. Narrowing this would need a check of which fds `exec` touches,
  about 5 lines. I left it out because `unknown` is the worst case, so it only adds
  confirms and never hides a risk.
- `exec` with no redirect (`exec; cat`) and a command with no name do not count.

An `exec` from an earlier command in the session needs live state, so it is left to #192
as the finding says.

The threat model's "What must hold" bullet, property (3), now says this
(`.oss-scanner/threat_model.md:169-171`). "Known gaps" is unchanged.

## Tests added (`tests/test_policy_gate.py`)

- `test_words_next_to_redirects_are_kept` (`:462`): asserts the exact words and
  descriptors for the finding's inputs. This is a parser-level check (`shell_layer`),
  because the stub command layer classes everything `mutating`, so `classify` alone
  cannot see a lost word. It also asserts the `standalone` role for
  `PATH=/tmp/evil >/dev/null`.
- Regression-table rows (`:170-178`, `:206-210`): the word inputs, the two `exec`
  inputs, and the four assignment-with-redirect inputs. They also feed the Rule 2
  invocation-count test and the Rule 6 escape test.
- `test_rule3_stdin_sources` (`:449-458`): the `exec` / `eval` / `command exec` /
  non-literal / loop cases go `unknown`; `{ sudo tee /etc/y; } </tmp/x` stays
  `file`; `exec; cat` stays `terminal`.

## Refuting my own test

- **(a) Genuine red?** Yes. I reverted each fix on its own in the worktree, ran the test
  file, then restored the file:
  - fix 1 reverted: `test_words_next_to_redirects_are_kept` fails (1 failed, 168 passed);
  - fix 2 reverted (both the `prefix_role` line and the `__init__.py:234` guard): 5
    failures, the word test plus the four new §3 regression rows;
  - fix 3 reverted: `test_rule3_stdin_sources` fails.

  With `src/nl_shell/gate` moved away (the state on `main`), all 169 tests fail.
- **(b) Production path?** Yes. The tests call the real `nl_shell.gate.parse.shell_layer`
  and `nl_shell.gate.classify` on the pinned tree-sitter-bash 0.25.1 grammar. There is no
  mock or stand-in parser.
- **(c) Fixture includes the fault?** Yes. The inputs are the exact reproducers from the
  finding (`rm -rf />/dev/null`, `PATH=/tmp/evil >/dev/null`,
  `exec </tmp/x; sudo tee /etc/y`). On the real parser they produce the faulty tree
  shapes: an adjacent non-descriptor word, a zero-width `MISSING` name, and an `ERROR`
  `;`.

## Runs

- `python -m pytest -q tests/test_policy_gate.py` (pdca `.venv`, Python 3.14.4, with
  `timeout`): 169 passed.
- Full suite `python -m pytest -q`: 1270 passed, 1 skipped. After the threat-model wording
  edit I re-ran `tests/test_failure_classes.py` (it pins the Known-gaps bullet) together
  with the gate tests: 452 passed.
- Commit-readiness: the target configures no formatter, linter or pre-commit hook (no
  `.pre-commit-config.yaml`; no ruff/black section in `pyproject.toml`; none in
  CONTRIBUTING.md / AGENTS.md). `git diff --check` is clean.

## Housekeeping

For the revert checks I made two backup copies inside the worktree,
`src/nl_shell/gate/parse.py.keep` and `src/nl_shell/gate/__init__.py.keep`. They are
untracked and **not** in `patch.diff` (I built it with `':(exclude)*.keep'`). Cleanup is
the harness's job, so I did not delete them. Anyone who uses `git add -A` on the worktree
instead of applying `patch.diff` must leave them out.

## For sign-off (from the brief; each is a raise, so v1-compatible per `v1.md:238-241`)

- Decision C: unhandled node kind, work/depth budget, input over 8 KiB, or any internal
  error → `privileged`, rejected, "could not class". `classify` never raises.
- Rule 4 is stricter than §5's "fd 3 or higher": non-literal targets such as `>"$f"` are
  rejected.
- Rule 1 rejects untrusted proposals, where §1.2 says only "at least mutating".
- The §1.1 check ignores quoting (`echo '‮'` is rejected).
- The 8 KiB input cap.
- New this round: an untrusted tree no longer excuses a prefix assignment from §3, and
  `exec`-with-redirect / `eval` / `source` / a non-literal command word makes every other
  command's stdin `unknown`. Both are raises.
- License (INTEGRATION §4, human only): `tree-sitter-bash` declares MIT; the
  `tree-sitter` wheel declares no license field.

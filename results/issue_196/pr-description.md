## Summary
**User impact:** nl-shell has no policy gate today. Nothing reads a command the model
proposes and decides how risky it is, so there is no basis yet for asking the user to
confirm a risky command or for refusing one outright. This PR does not change what users
see yet: the gate is not wired into the REPL, and every command still comes out as
needing a confirm.

This PR adds the first part of the gate: the layer that parses a command the way bash
would and records, conservatively, what each command in it does. Anything it cannot
prove safe is treated as the worst case.

Reported in [#196](https://github.com/eduralph/nl-shell/issues/196).

## What to look at
- **The core idea:** the gate never assumes a command is safe. Text the parser may read
  differently from bash, a redirect it cannot prove is harmless, or a stdin source it
  cannot pin down all fall back to the worst case. If the gate itself fails (input too
  large, too complex, an internal error), the command is refused with "could not class".
- **Try it:** after `pip install -e '.[dev]'`,
  `python -c 'from nl_shell.gate import classify; print(classify("echo hi >&3"))'`
  is rejected (fd 3 is nl-shell's control channel), and
  `classify("if true; then", origin="proposal")` is rejected as unparseable.
  `pytest tests/test_policy_gate.py` runs the full set of cases.
- **New dependencies:** `tree-sitter==0.26.0` and `tree-sitter-bash==0.25.1`, pinned
  exactly. Both install from binary wheels on CI's Python 3.14 / x86_64.
- **Places where this is stricter than the written spec** (each only raises a class or
  rejects, so it stays compatible with v1, but the spec's Versioning section asks for a
  human to review it):
  - a gate failure is "privileged" and rejected;
  - a non-literal redirect target such as `>"$f"` is rejected, not just fd 3 or higher;
  - an unparseable *proposal* is rejected, where §1.2 says "at least mutating";
  - the hidden-character check ignores quoting, so `echo '‮'` is rejected;
  - input over 8 KiB is refused.

## Root cause
There is no `nl_shell.gate` on `main` and no shell parser dependency
(`pyproject.toml:13-17` lists only `prompt_toolkit`, `ptyprocess` and `PyYAML`).
Every later gate piece (per-command rules, the allowlist, live-session checks) needs a
shell layer that turns raw text into invocations it can trust.

## Fix
- `src/nl_shell/gate/__init__.py`: the pipeline. `classify` (`:147`) runs the
  hidden-character check (`:168`, reusing `nl_shell.render.has_hidden`), the shell
  layer, the shell-level rules (prefix assignments, non-literal command words, process
  substitution, session-altering variables, `SUDO_PROMPT`/`SUDO_ASKPASS`), then the
  command layer and the live step. It returns the session-log
  `{"class", "reasons", "rejected"}` shape, and turns any failure into "could not class"
  instead of raising. All quoted input in reasons goes through `escape` (`:94`).
- `src/nl_shell/gate/parse.py`: the walker. One handler per named node kind of the
  pinned grammar, a walk-vs-tree completeness check (`_check_walk`, `:952`), the
  untrusted-text detector (`untrusted_features`, `:413`), the redirect judge
  (`judge_redirect`, `:293`), stdin tracking including `exec`/`eval`/`source` that can
  rewire the shell's stdin (`_may_rewire_stdin`, `:999`), and the size and work limits
  (`MAX_INPUT_BYTES`, `MAX_WORK`, `MAX_DEPTH`, `:36-38`).
- `rules.py`, `live.py`, `sensitive.py`, `words.py`: stubs. `rules.py` classes every
  command "mutating", "not allowlisted"; `live.py` turns anything still read-only into
  "mutating", "live-session resolution not implemented". Later PRs (#197, #198, #190,
  #191, #192) replace them.
- `src/nl_shell/gate/vectors.py` + `targets/ubuntu-26.04/gate-vectors.toml`: a strict
  loader (unknown keys, bad types and invalid TOML are errors naming the entry) and the
  conformance rows landed so far. The file header says it is complete only once #192
  lands.
- `.oss-scanner/threat_model.md:157-181`: one "What must hold" bullet stating the six
  properties. "Known gaps" is unchanged; `tests/test_failure_classes.py:827-839` pins it
  and still passes.

## Verification
| Claim | Checked (on this branch) | Test (`tests/test_policy_gate.py`) |
|---|---|---|
| Text the parser may misread is untrusted: proposals rejected, typed input "unparseable" | `parse.py:413` | `test_rule1_untrusted_tree` (`:255`), `test_rule1_untrusted_redirects` (`:297`) |
| Every node walked, one invocation per simple command; a missing handler or skipped child fails closed | `parse.py:952` | `test_rule2_*` (`:362-407`) |
| Stdin and literal flags only from proven forms; else "unknown" | `parse.py:971`, `:999` | `test_rule3_stdin_sources` (`:427`), `test_rule3_literal_flag` (`:488`) |
| Words written right against a redirect (`rm -rf />/dev/null`) are kept | `parse.py:778` | `test_words_next_to_redirects_are_kept` (`:462`) |
| Only fd 0-2 and safe targets accepted; fd 3, `/proc/self/fd/3`, globs, `..` rejected | `parse.py:293` | `test_rule4_redirect_table` (`:585`), `test_rule4_spec_rows_and_exempt_forms` (`:611`) |
| Bounded cost: >8 KiB never parsed; work/depth budget; never raises | `parse.py:36-38`, `__init__.py:147` | `test_rule5_*` (`:626-652`) |
| No control or hidden characters in any reason | `__init__.py:94` | `test_rule6_reasons_never_carry_raw_input` (`:682`) |
| Nothing is read-only yet; live stub holds | `live.py`, `rules.py` | `test_nothing_is_read_only` (`:717`), `test_live_stub` (`:750`) |
| Vector file and loader | `vectors.py` | `test_vectors_*` (`:811-850`) |

- **Red/green:** with `src/nl_shell/gate` absent (the state of `main`) all 169 tests fail;
  with this change all 169 pass. Each of the three latest fixes was also reverted on its
  own and its test went red.
- **Mutation check:** twelve hand-made breakages of the gate (walk check turned off,
  `..` check removed, `escape` made a no-op, and others) were each caught by the test
  file.
- **Full suite:** 1270 passed, 1 skipped. `git diff --check` is clean.

## Not covered here
Review turned up more cases where tree-sitter-bash and bash disagree, or where a stdin
fact is too optimistic. None changes today's result (every command still needs a
confirm). They are known and left for follow-up work:
- assignments before a command word that may expand to nothing
  (`PATH=/tmp/evil $(true)`); `trap` and `coproc` stdin; `</dev/stdin` recorded as a file;
- nested backticks and a backtick in an unquoted here-doc body hide commands and fd-3
  redirects;
- quoted or escaped `export 'SUDO_PROMPT=x'` / `export 'PATH=…'`;
- `HOME=…; echo >~/3`, `cd /dev/fd && echo >3`, and `[ x > f ]` hiding a redirect.

Fixes #196

# Design proposal — issue 14 / input-mode-prefix-dispatch

> The Plan artifact. Do reads ONLY this file and implements it; Check runs the regular
> gated check on the code.
> Milestone: **M0** (tracker eduralph/nl-shell#8, work item M0.6). Builds on ADR-0013 §7
> (`\` skips only the intent classifier; everything still goes through the gate — the
> thread defers this to #64; #64 is closed on ADR-0013, which is still `Proposed`),
> `docs/plan.md` §Input Modes, and architecture §5.1 (the input router owns the prefix
> modes). After the 2026-10-14 design review the issue keeps `\`, `?`, `@` and `:`
> dispatch; `@@` moved to #76, `:context` is owned by #16, orchestration (gate → PTY) by #78.
> Threat-model inputs affected: none new. `:` meta-commands are "lower priority"
> (`.oss-scanner/threat_model.md`, Components), and nothing runs yet.
> Template note: a small feature; the design-proposal form is used because this batch was
> asked to brief every enhancement in it.

- **Slug:** input-mode-prefix-dispatch
- **Kind:** enhancement (design proposal)
- **Goal:** The REPL recognises the input-mode prefixes before the heuristic router runs: `\cmd` is routed as a shell command whatever the router would say, `?question` goes to ask mode, `@request` to a one-command proposal, `@@goal` to the (not yet built) agent loop, and `:name` to a meta-command (`:context`, `:history`, `:status`, plus the existing `:quit` / `:exit`). Each route prints its own fixed reply, since nothing behind them exists yet except `:status`.
- **Success criterion:** `python3 -m pytest tests/test_input_modes.py` passes, and that file contains a table-driven test that feeds each line below through `Repl` (scripted read function, `$PATH` pointed at a temp dir holding only fake `ls`, `git`, `find`) and asserts the reply. Every reply named here is a fixed string, distinct from the other routes' replies, pinned as a literal in the test: `\frobnicate the widgets` → the existing shell-command reply (`COMMAND_NOT_YET`, `src/nl_shell/repl.py:19-22`), although the router alone says natural language · `\ls -la` → shell-command reply · `?why did that fail` → ask-mode reply · `@show disk usage` → one-command-proposal reply · `@@clean up my downloads` → the `@@` reserved reply (says it arrives with M0.6b, #76), and it is NOT the `@` reply · `:context` → reply saying it arrives with M0.8 (#16) · `:history` → reply saying it arrives with M0.9 (#17) · `:status` → prints a status block that includes the line `nl-shell <version>` (`nl_shell.__version__`) · extension point (separate test, imports the new module *inside* the test function): appending a zero-argument callable that returns `"extra: yes"` to the status-line list (see Design) makes `:status` print `extra: yes` after the version line, with no other change · `:frobnicate` → an "unknown meta-command" reply that lists the known ones, and nothing is routed · a prefix with nothing after it (`\`, `?`, `@`, `@@`, `:`) → a short usage reply for that prefix, nothing routed. Also: `:quit` / `:exit` still end the loop; plain input with no prefix still routes exactly as today (`ls -la` → command, `show disk usage` → natural language).
- **Falsifiability:** RED is reachable on the shipped C4 gate (`engine/scripts/run-verify.sh`, plain pytest on the host, nothing extra). With the production change reverted, the REPL on `main` has no prefix handling: `\frobnicate the widgets` and `?why did that fail` route as natural language (`router.first_token` yields `frobnicate` / `?why`, neither on the fake `$PATH`), `:status` and `:frobnicate` route as natural language, so the table's assertions fail (tests ran, failures > 0). Some rows already pass on `main` and prove nothing on their own: `\ls -la` (`shlex` drops the backslash, `router.py:40-48`, so it routes as `ls`) and bare `:` (the `:` builtin, `router.py:29`). The red evidence is the `\frobnicate`, `?why`, `:status`, `:frobnicate` and extension-point rows. The test file must import only names that exist on `main` (see Test file), or the red leg is UNVERIFIABLE instead of red.
- **Repo + branch target:** eduralph/nl-shell @ main
- **Ordering note:** First wave. #92, #16 and #77 add lines to the `:status` this issue creates, and #16 replaces the `:context` placeholder, so they come after it (they declare `Depends on: 14`). #10 runs in the same wave: it adds new files only and does not touch `repl.py`.
- **Surfaces:** data
- **Scope:** Prefix dispatch for one input line, checked after the exit commands and blank-line handling and before the heuristic router (`src/nl_shell/repl.py:57-62`). Rules: the prefix is the first character(s) of the stripped line; `@@` is checked before `@`; the text after the prefix (stripped) is the payload; `\` forces the command route and passes the payload on as the command text (ADR-0013 §7: it skips the classifier only, it does not skip the gate — say so in a comment that cites #64 / ADR-0013 §7 (Proposed), since #78 wires the gate); `?` → ask route; `@` → one-command proposal route; `@@` → reserved: one fixed reply naming #76, nothing else (needed only so `@@goal` does not fall into the `@` route with payload `@goal`; #76 owns the `@@` grammar and replaces this reply — this is a decision against the thread's "without `@@`", stated here on purpose); `:` → meta-command lookup by exact name (case-sensitive), with `:quit` / `:exit` handled as today. A prefix always wins over the router, even when the line would also be valid bash (`?x` is a bash glob; `\ls` is valid bash) — `docs/plan.md` §Input Modes defines the prefixes as explicit overrides. `:status` is a real meta-command that prints a block of status lines; build it so later issues can add lines to it (#92: active target; #16: prompt files loaded; #77: endpoint and backend — ADR-0020 §4) without rewriting it. Keep the dispatch a separate unit from `nl_shell.router` (the router stays the plain-input heuristic that #40 replaces). Replace `COMMAND_NOT_YET`'s and `NATURAL_LANGUAGE_NOT_YET`'s role only where needed: plain-input replies stay byte-identical, so `tests/test_repl.py` keeps passing unchanged. / out of scope: running anything (PTY #10, gate #12, orchestration #78); calling a model for `?`, `@` or natural language (#16, #77); the `@@` loop itself (#76); what `:context` and `:history` show (#16, #17); fix-on-failure and `?why` using the failure classes (#17, #62); the architecture doc 05 code-layout table (one docs pass after this batch, so six bundles don't edit the same table line); any change to `cli.py`.
- **Difficulty:** low
- **External dependencies:** none
- **Test file:** `tests/test_input_modes.py` (new). The C4 red leg reverts every non-`tests/` file and re-runs this file; if it fails to IMPORT, the run is UNVERIFIABLE, not red. So import only `Repl` from `nl_shell.repl` (exists on `main`) at module level, define the scripted-read / `run` / fake-`$PATH` helpers locally (copy the pattern, don't import from `tests/test_repl.py`), and pin every reply as a string literal in the test — never import a reply constant or a new module the patch adds.
- **Citations expected:** Do must cite path:line on `main` for every change. Wiring point: the loop body at `src/nl_shell/repl.py:57-62` (strip, blank check, exit commands, then the single routed reply). Test peer to mirror: `scripted` / `run` / `make_executable` / `fake_path` in `tests/test_repl.py:20-57`, and its literal-pinning comment at `tests/test_repl.py:7-8`.
- **Prior-art check (triage cycles):** `git -C ../nl-shell log origin/main -- src/nl_shell/repl.py src/nl_shell/router.py` → 305d8a4 (scaffold), dc784f0 (router, #15), c45c53e (test isolation). Closed-unmerged PRs touching these paths: none. Open PRs: only #100 (docs link check, unrelated files). Issue search "prefix" / "meta-command": #14 itself, #76 (`@@`). No prior work.
- **Disposition hint:** new-feature

## Motivation

`docs/plan.md` §Input Modes defines five prefixes that let the user override the router.
The later M0 pieces (#16 model input, #17 history, #76 agent loop, #78 turn pipeline)
each need a place to plug in. Building the dispatch now, with honest placeholder replies,
gives them that place and pins the prefix grammar in tests before anything depends on it.

## Design

- Order of checks per line: strip → blank → exit command → prefix dispatch → router.
- `@@` before `@`; `:` matches whole names only (`:statusx` is unknown, not `:status`).
- Routes and their replies (all fixed strings, each naming the milestone that fills it):
  command (reuse today's reply), ask (`?`, M0.8), one-command proposal (`@`, M0.8), agent
  loop (`@@`, M0.6b #76), `:context` (M0.8 #16), `:history` (M0.9 #17), unknown
  meta-command (lists `:context`, `:history`, `:status`, `:quit`, `:exit`), and one usage
  reply per bare prefix.
- `:status` prints `nl-shell <version>` now. Its lines come from a module-level list of
  zero-argument callables, each returning one line (`str`), in the dispatch module; `:status`
  prints them in list order. Later issues (#92, #16, #77) append to that list and change
  nothing else. The extension-point test pins this.

## Alternatives considered

- Putting prefix handling inside `nl_shell.router.route`: rejected, the router is the
  plain-input heuristic #40 replaces and keeps as fallback; prefixes are not heuristics.
- Treating `\cmd` as "bypass everything": rejected by ADR-0013 §7.

## Impact & compatibility

Plain input behaves exactly as today. Lines that start with `\`, `?`, `@` or `:` that
used to route through the heuristic now take the prefix route. No config, no new
dependency.

## Open questions

- Closed at plan review: a bare prefix prints a usage reply (the criterion pins it). The human
  may still choose "ignore like a blank line" at sign-off; until then the criterion wins.

## STOP discipline

Draft only until Check sign-off. Pushing to a feature/draft branch and opening a
draft PR MAY happen during the cycle (useful for CI feedback). The PR MUST NOT be
marked ready before sign-off accepts.

Plan-review response: (1) addressed — `@@` is now explicitly a reserved stub only, stated as a decision against the thread, with #76 owning its grammar and reply; (2) addressed — cites #64 (closed) and marks ADR-0013 as Proposed; (3) addressed — the `:status` extension point is a named API (module-level list of zero-argument callables) with its own test; (4) addressed — Falsifiability names the rows that already pass on `main` and the rows that carry the red; (5) addressed — the open question is closed in favour of the criterion. Checked: #92, #16 and #77 each declare `Depends on` 14 in their briefs.

## Iteration 1 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 1): rebuilding for the implementation-level findings — C5 Causal adequacy — Honor the specified stripped payload for meta-commands and add a whitespace regression: directly exercising `: status` returns unknown instead of the status block because the parser exempts `:` from stripping (brief.md:24; target/src/nl_shell/input_modes.py:62; target/tests/test_input_modes.py:105).; `tests/test_input_modes.py:28,114`: the `:status` table row asserts that the *whole* output equals `"nl-shell 0.0.0\n"`. The brief's criterion says only that the block "includes the line `nl-shell <version>`", and the whole point of `STATUS_LINES` (`src/nl_shell/input_modes.py:68-70`) is that #92, #16 and #77 append lines "and change nothing else". Concrete failing case: the moment #92 appends its active-target line, `test_prefix_dispatch[:status-status]` goes red. A version bump in `src/nl_shell/__init__.py:3` does the same. So the extension point can't actually be used "with no other change", which the brief and the `STATUS_LINES` comment both promise. Fix: in the table, check only that the first line of the `:status` output is the version line, or drop the `:status` row from the exact-match table. `test_status_prints_the_version_line` (`tests/test_input_modes.py:137-142`) already checks the version line in a way that won't break when lines are added. Keep a red-on-`main` row for `:status`; that test still gives one.. Deferred, not addressed here: 6 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v1/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 2 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 2): rebuilding for the implementation-level findings — `target/src/nl_shell/repl.py:62` vs `target/src/nl_shell/input_modes.py:61`: this round's whitespace fix creates a reply that contradicts itself. The exit check matches the raw text exactly. Meta dispatch now strips the payload. So `: quit` falls through to dispatch, `quit` is not in `META_COMMANDS` (`input_modes.py:91-95`), and the user sees: `Unknown meta-command :quit. Known: :context, :history, :status, :quit, :exit.` (`: exit` gives the same.) I reproduced this on the patched tree. The REPL calls `:quit` unknown while listing it as known. The new rule "`: status` names `status`" (`input_modes.py:57-58`) should apply to the exit commands too. Fix: check exit commands on the parsed META payload (e.g. `prefixed.mode is Mode.META and prefixed.payload in {"quit", "exit"}` → return 0), or at least leave them out of the unknown reply. Add a `": quit"` row to `test_exit_commands_still_stop_the_loop` (`tests/test_input_modes.py:182-186`).. Deferred, not addressed here: 6 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v2/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

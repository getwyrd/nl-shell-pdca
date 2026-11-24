# Result — issue 16 / prompts-yaml-context-recording-stub

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: Goal (new functionality). Natural-language input and `@request` should build the model input from an editable prompts YAML, send it to a model backend, and parse the answer strictly as a `proposal/v1` object, shown without running it. A stub backend returns fixed responses and records every model input it was sent (#13 relies on this). `:context` shows the exact model input of the last request. Every character nl-shell shows from a proposal, `:context` or an error is filtered by one character-safety policy based on UTS #39, so a proposal cannot hide or disguise part of a command.
- Success criterion: Two parts, one per child. (Core) `python3 -m pytest tests/test_backend.py` passes and covers iteration-v3's criteria (a)–(f) unchanged, plus: a malformed user `prompts.yaml` whose YAML error snippet contains U+202E → `nl_shell.cli.main([])` stderr carries `‮`, never the raw character. (Character safety) `python3 -m pytest tests/test_charsafety.py` passes and covers: every Default_Ignorable_Code_Point vector (U+3164, U+115F, U+1160, U+FFA0, U+034F, U+FE00, U+FE0F, U+E0100, U+17B4, U+180B), U+2800, non-ASCII whitespace (U+00A0, U+3000), a private-use (U+E000) and an unassigned code point, and more than the allowed number of combining marks on one base character are each rejected in a proposal `command` and escaped in `:context`; a mixed-script token (`сurl`, Cyrillic U+0441 + Latin) is rejected; single-script non-Latin tokens (`ls Документы`, `cat αρχείο.txt`) are accepted and shown unchanged.
- Repo + branch target: eduralph/nl-shell @ main (the core builds on the wave base that folds #92's accepted patch; #14 is already merged on main at 2ba3fb5)
- Scope (one logical fix) / out of scope: See the two children. / out of scope: the HTTP client (#77); ask mode `?`; state block content (#11); running or gating a proposal (#12, #78); the confirm UI and its line-wrap hidden-tail handling (#74); the `--- <role> ---` separator spoof once #11 fills the state block (note for #11).

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — N/A — close disposition (no patch to verify)
- C3 Change: none — patch.diff
- C4 Verification (red→green): none — N/A — close disposition (no patch to verify)
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — N/A — close disposition (no patch to verify)
- T2 Shape: none — N/A — close disposition (no patch to verify)
- T3 Runtime: none — N/A — close disposition (no patch to verify)
- T4 Contribution: none — N/A — close disposition (no patch to verify)
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

# Advisory review — SKIPPED (close disposition)

The reviewer leaf was skipped: this bundle's Plan concluded a close / no-fix disposition (split), so there is no patch to review.

- NEEDS-HUMAN — Confirm the close disposition 'split' (no patch was built). Override to a fix path (iterate-to-Do) if the close is wrong.


## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] Confirm the close disposition 'split' (no patch was built). Override to a fix path (iterate-to-Do) if the close is wrong.
- [x] T5 Judgment — Confirm affected-file prior art across merged and closed/rejected work: the supplied target has one synthetic base commit and no remotes, and the brief's directory-level claim does not establish that complete audit (brief.md:30); this matters before introducing reusable backend/parser interfaces.
- [x] **The brief contradicts a threat-model must-hold on control characters.** `.oss-scanner/threat_model.md:119-120` says: "The confirm UI renders from the parsed command with hidden characters escaped; proposals with bidi or control characters are rejected (#74)." Criterion (e) instead says a `command` with ESC or another control character "is shown with that character escaped", which accepts and displays it. The parser in (d) is called "strict, reject not repair", yet it lets such commands through. Bidi characters (U+202E etc.) are not mentioned anywhere in (e). Fix: the brief should either reject control/bidi characters in the parser now, or say explicitly that the rejection waits for #74 and why showing the command escaped is safe until then. In both cases it should add a bidi vector.
- [x] **"Control character" is undefined, and it clashes with spec rule 3.** `proposal/v1.md:55-56` allows newlines in `command` ("as are newlines (a multi-line command)"). If (e) escapes "another control character", a newline would be escaped too and every multi-line proposal would display mangled. If newline is exempt, the test needs to say so. The criterion should name the escaped set (e.g. C0 except `\n`, C1, DEL, plus the bidi range) and pin one literal escaped form, so the test can't be satisfied by any escaping at all.
- [x] **"Byte for byte" is ambiguous, and escaping can undermine it.** Per the Design section, the model input is "an ordered list of chat messages" and `:context` prints "its canonical text form". The stub records the object, not text. Test (a) therefore compares printed text with a list, and it is not stated which function turns the list into text. If `:context` renders through that same function, the test is circular. Scope (5) also escapes control characters in `:context`, so a request containing them would make `:context` differ from what the stub received. That breaks the issue's own "byte for byte" Done-when. The criterion should give the comparison exactly: e.g. stub entry → documented serializer → equals `:context` output for ordinary text. It should also add one case with a control character in the request and state the expected outcome, since this is exactly where the two can drift.
- [x] **Two scope items have no criterion, so Check cannot falsify them.** (i) Scope (2) requires the ADR-0018 §4 ordering: stable part (system, few-shot) first, volatile part last (`docs/design/adr/0018-model-serving-and-wire-format.md:43-45`). Criterion (a) only checks that the input "contains the system prompt … and the user's request text". A reversed or interleaved order would still pass. (ii) Scope (1) says "loaded with a safe YAML loader only". No vector feeds a user `prompts.yaml` carrying a `!!python/object` tag, so a `yaml.load`/`FullLoader` regression would pass. Add one assertion for each.
- [x] **Both prerequisites are only PLANNED.** `dependency-state.json` lists #14 and #92 as `"state": "PLANNED"`. Neither has landed. The target `main` has no `:context`/`:status` dispatch, no `@` route and no target loader: `src/nl_shell/repl.py:27-30,62` is a two-route table, and there is no `targets/` directory in the tree. Criteria (a) (`@show disk usage`, `:context`), (c) (default layer in `targets/ubuntu-26.04/prompts/`) and (f) (`:status`) all build on code that doesn't exist yet. The Citations section admits this ("or the wave base, for code #14/#92 added"). It's correct for the brief to declare the dependency, but this bundle must not enter Do until both are merged into the wave base. The driver should hold it rather than let Do invent stand-ins for #14/#92.
- [x] **It's unclear what (c) "start-up refused" runs through.** `Repl.__init__` (`repl.py:36-38`) and `Repl.interactive` (`repl.py:40-45`) do no loading, and start-up lives in `src/nl_shell/cli.py`. The brief limits module-level test imports to `nl_shell.repl.Repl`. It doesn't say whether the malformed-file test calls `cli.main`, `Repl.interactive`, or a loader function. It also doesn't say what "refused" means observably: exit status, exception type, stderr text. Without that, (c)'s rejection half is something a reviewer judges by eye, not a pass/fail test. Pin the entry point, the exit code and a message literal that contains the path.
- [x] **Where the default prompts ship is unresolved against ADR-0020.** ADR-0020 §2 says "Defaults ship in the package" (`docs/design/adr/0020-configuration-and-file-locations.md:30-31`). The brief puts them in the repo's `targets/ubuntu-26.04/prompts/prompts.yaml`. `pyproject.toml:25-26` packages only `src/`, so an installed `nl-shell` would not ship the defaults. ADR-0023 hands target shipping to #48/#50 (`0023-os-targets.md:108-109`). The brief should state that the default layer is resolved through #92's target loader, and accept (or record) that a non-editable install has no defaults until #48/#50. If it doesn't, Do will either hard-code a repo-relative path or make an unplanned packaging change.
- [x] **The scope is large for "medium" and bundles separable changes.** It covers a prompts loader with schema validation, the model-input builder, the backend interface plus stub, the parser, REPL rendering with clarify/refuse templates and escaping, the `:status` extension, a `pyproject` dependency and a threat-model doc edit. Of these, the issue's post-split Done-when strictly needs only the YAML, the stub and `:context`. The parser and rendering ((d), (e)) can be justified by spec Conformance, but they are where the threat-model conflict above sits. Consider making them a stacked follow-up, or at least raise Difficulty so Do gets enough review budget.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: merged-wider
- Iteration delta (if iterating):
- By / date: Eduard Ralph / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- (empty is the common case)

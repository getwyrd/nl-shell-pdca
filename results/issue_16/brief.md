# Brief — issue 16 / prompts-yaml-context-recording-stub (re-plan after iteration 3)

> Re-plan after sign-off on iteration 3 answered `iterate-plan` (see `iteration-v3/SUMMARY.md` §9).
> The human confirmed a split into two children (session 2026-10-15): (a) the core —
> prompts YAML, recording stub, strict parser, `:context` — rebuilt from the v3 design that
> passed review, and (b) a character-safety policy grounded in UTS #39 (Unicode Security
> Mechanisms), replacing the hand-picked hidden-character list that failed three rounds.
> This parent brief carries both; `pdca split 16` divides it.

- **Slug:** prompts-yaml-context-recording-stub
- **Defect:** Goal (new functionality). Natural-language input and `@request` should build the model input from an editable prompts YAML, send it to a model backend, and parse the answer strictly as a `proposal/v1` object, shown without running it. A stub backend returns fixed responses and records every model input it was sent (#13 relies on this). `:context` shows the exact model input of the last request. Every character nl-shell shows from a proposal, `:context` or an error is filtered by one character-safety policy based on UTS #39, so a proposal cannot hide or disguise part of a command.
- **Success criterion:** Two parts, one per child. (Core) `python3 -m pytest tests/test_backend.py` passes and covers iteration-v3's criteria (a)–(f) unchanged, plus: a malformed user `prompts.yaml` whose YAML error snippet contains U+202E → `nl_shell.cli.main([])` stderr carries `‮`, never the raw character. (Character safety) `python3 -m pytest tests/test_charsafety.py` passes and covers: every Default_Ignorable_Code_Point vector (U+3164, U+115F, U+1160, U+FFA0, U+034F, U+FE00, U+FE0F, U+E0100, U+17B4, U+180B), U+2800, non-ASCII whitespace (U+00A0, U+3000), a private-use (U+E000) and an unassigned code point, and more than the allowed number of combining marks on one base character are each rejected in a proposal `command` and escaped in `:context`; a mixed-script token (`сurl`, Cyrillic U+0441 + Latin) is rejected; single-script non-Latin tokens (`ls Документы`, `cat αρχείο.txt`) are accepted and shown unchanged.
- **Falsifiability:** RED on the shipped C4 gate (`engine/scripts/run-verify.sh`, plain pytest). Core: with production reverted the new modules don't exist (in-function imports fail; through `Repl`, the M0.8 placeholder reply comes back). Character safety: with its production change reverted, the core's narrower hidden set accepts every new vector — failures > 0. No model, GPU or network.
- **Invariant to restore:** Text nl-shell shows is exactly the text that is there: no character that renders as nothing, as blank, or as a different-script look-alike reaches the user unmarked (threat model must-hold "What the user confirms is exactly what runs", `.oss-scanner/threat_model.md:117-120`; UTS #39 §3 and §5). Stated over every display path, not one module.
- **Repo + branch target:** eduralph/nl-shell @ main (the core builds on the wave base that folds #92's accepted patch; #14 is already merged on main at 2ba3fb5)
- **Depends on:** 92
- **Conflicts with:** 62
- **Ordering note:** #14 merged (PR #103). #92 is draft PR #142, folded into the integration branch. Conflicts with #62: both extend #92's target loader. Character safety stacks on the core (it changes the core's `render.py` and the parser's rejection set).
- **Surfaces:** data
- **Difficulty:** high
- **Scope:** See the two children. / out of scope: the HTTP client (#77); ask mode `?`; state block content (#11); running or gating a proposal (#12, #78); the confirm UI and its line-wrap hidden-tail handling (#74); the `--- <role> ---` separator spoof once #11 fills the state block (note for #11).
- **External dependencies:** `pyyaml`
- **Test file:** `tests/test_backend.py` (core), `tests/test_charsafety.py` (character safety)
- **Citations expected:** Do must cite path:line on the wave base. Core wiring: `src/nl_shell/repl.py:24-31` (natural-language reply), `:74-84` (`_reply`), `:38-55` (`__init__` / `interactive`); `src/nl_shell/input_modes.py:105,112` (`:context` placeholder); `src/nl_shell/cli.py:53-55` (start-up error print — mirror for `PromptsError`), `:64`.
- **Prior-art check (triage cycles):** `git -C ../nl-shell log --all -- src/nl_shell/backend.py src/nl_shell/prompts.py src/nl_shell/proposal.py src/nl_shell/render.py` → no commits on any branch. `gh pr list --state all` → no PR touching these files (merged #103 = #14; draft #142 = #92). Earlier attempts: this bundle's own iteration-v1..v3 (never published).
- **Disposition hint:** new-feature

## STOP discipline

Draft only until Check sign-off. Pushing to a feature/draft branch and opening a
draft PR MAY happen during the cycle (useful for CI feedback). The PR MUST NOT be
marked ready before sign-off accepts.

<!-- pdca:split-proposal v1 -->
# Split proposal — issue 16

<!-- Each child is a COMPLETE brief, not a sketch. A filled Slug alone makes `state.state`
     classify the materialised file as PLANNED, so `pdca flow` skips Plan and sends it
     straight to Do — a child missing `Repo + branch target` then builds successfully and
     has nowhere to publish. Fill every field. -->

<!-- Delimiters are HTML comments, not headings, DELIBERATELY: each child body is a full
     draft brief and may contain arbitrary headings and fenced code blocks, so anything
     that could also appear inside a child cannot be its boundary. `pdca split --accept`
     parses these markers; keep them exactly as written. -->

## Why this slice is oversized

The brief already describes two outcomes, and the human confirmed the split at the
iteration-3 sign-off (`iteration-v3/SUMMARY.md` §9, 2026-10-15). Each one has its own goal,
its own test file and its own success criterion:

1. **The core** — prompts YAML, model input, recording stub backend, strict `proposal/v1`
   parser, `:context`, `:status` listing prompt files. This design passed review in
   iteration 3. What sank the cycle was not the core but the character filter bolted onto
   it: three rounds of widening a hand-picked hidden-character list, with the size backstop
   firing at 15 files / ~73 KB. The core ships on its own with the hidden set iteration 3
   built and the iteration-2 sign-off required (C0 except LF/TAB, DEL, C1, bidi, Cf,
   U+2028/9, tags, surrogates; one-to-one backslash escaping in `:context`; line-prefix
   framing of multi-line commands), which meets the threat model's existing "bidi or
   control characters are rejected" line. It also picks up the one-line fix the reviewer
   flagged: the start-up error for a malformed `prompts.yaml` must escape hidden
   characters too.
2. **Character safety under UTS #39** (Unicode Security Mechanisms — the Unicode
   standard for spotting invisible and look-alike characters) — replaces the hand-picked
   list with a policy based on Unicode properties: every Default_Ignorable_Code_Point,
   non-ASCII whitespace, blank-looking characters like U+2800, private-use and unassigned
   code points, a cap on stacked combining marks, and mixed-script detection for
   look-alike letters (`сurl`). This is a separate defect (the narrow set lets these
   through) with its own test file, and it is the part that needs fresh design: which
   Unicode data to use, where the combining-mark cap sits, and reject vs. warn for
   mixed scripts.

The seam is clean because the core's `render.py` / parser check is already one predicate
("is this character hidden?") plus one escape function. Child 2 swaps what that predicate
means and adds the mixed-script check. It does not rewire the REPL, the backend or the
prompts loader.

I did not split further. Taking the parser or the prompts loader out of the core would
leave a child that cannot be tested end to end through `Repl` (criteria (a)–(f) all go
through it), and each extra child costs a full cycle.

## Wave sketch

Two waves, strictly stacked:

- **Wave A — child-1 (core).** It also needs #92's accepted patch on the wave base (as the
  parent did), and it must not share a wave with #62, since both extend #92's target loader.
  Those two links point outside this proposal, so they cannot go in the ordering fields
  (those name siblings only). They are written into child-1's `Repo + branch target` and
  `Scope` text. **The human should check after `--accept` that child-1's materialised brief
  gets `Depends on: 92` and `Conflicts with: 62`**, or the scheduler will not see them.
- **Wave B — child-2 (character safety)** `Depends on: child-1`. It changes the files
  child-1 creates (`src/nl_shell/render.py`, the rejection set in `src/nl_shell/proposal.py`)
  and its test drives the parser and `:context` through `Repl` with the recording stub.
  None of that exists until child-1 is accepted and folded. The two edit the same files,
  but `Depends on` already puts them in different waves, so I did not add a sibling
  `Conflicts with` as well. child-2 does not touch #92's target loader, so it has no
  conflict with #62.

Nothing runs in parallel here. That is expected: child-2 is a change *to* child-1's code.

<!-- pdca:child child-1 -->
# Brief — prompts YAML, `:context` and a recording stub backend (core of #16)

> Child 1 of the split of #16 (re-plan after iteration 3). This is the iteration-3 design,
> which passed review apart from the character-safety coverage that the sibling slice now
> owns. Milestone M0, work item M0.8. Normative sources: ADR-0018 (§3 strict parsing, §4
> stable prompt part first), spec `docs/design/specs/proposal/v1.md`, ADR-0020 (file
> locations, YAML for prompts, `:status` lists loaded files), ADR-0023 (the default prompts
> layer lives in the target's `prompts/`).

- **Slug:** prompts-yaml-context-recording-stub-core
- **Defect:** Goal (new functionality). Natural-language input and `@request` build the model input from an editable prompts YAML, send it to a model backend, and parse the answer strictly as a `proposal/v1` object, which the REPL shows without running it. A recording stub backend returns fixed responses and records every model input it was sent (#13 relies on this). `:context` shows the exact model input of the last request; `:status` lists the loaded prompt files. Every text shown from a proposal, `:context` or a start-up error passes through one hidden-character predicate and one escape function, so the sibling slice can replace the character policy in one place.
- **Success criterion:** `python3 -m pytest tests/test_backend.py` passes, and it covers: (a) through `Repl` with the stub backend: a natural-language line, then `:context` → `:context` prints exactly the text the test itself builds from the stub's recorded message list using the text form in Design (the test re-implements that form inline; it does not call the module's serializer), byte for byte; the recorded list's order is: the system message first, then the few-shot example messages in file order, then the user message last, whose content ends with the user's request text; the same for `@show disk usage`; `:context` before any request → the fixed reply `No model input yet: :context shows the model input of the last request.` (b) the stub's recorded inputs are a list tests can read, one entry per request, in order; a request containing ESC (`show \x1b[2J disk`) → the recorded input carries the raw ESC, and `:context` prints it as the four characters `\x1b`; a request containing a literal backslash followed by `x1b` (typed, five characters `\`, `x`, `1`, `b`) → `:context` prints `\\x1b`, so a real ESC and the typed text print differently; the rest of the text is unchanged. (c) a user `prompts.yaml` in `$XDG_CONFIG_HOME/nl-shell/` (the suite's temporary HOME) that changes the system prompt → the next recorded input and `:context` both carry the user's text; a malformed user `prompts.yaml` (invalid YAML, not a mapping, a key with the wrong type, an unknown key, a sequence used as a key, and a file whose only content is `!!python/object/apply:os.system ["touch <tmp>/pwned"]`) → `nl_shell.cli.main([])` (with a matching os-release injected as `tests/test_cli.py:29-46` does) returns non-zero before the REPL reads any line, stderr contains the file's full path, and for the tag case `<tmp>/pwned` does not exist (safe loader); a malformed file containing U+202E inside the broken line → stderr contains the six characters `‮` and never the raw U+202E. (d) the `proposal/v1` §Conformance list, each fed as the stub's raw response: every valid shape (`command` + `risk`; `clarify` + `reason`; `refuse` + `reason`) is accepted, and extra properties, a missing `risk`, `command` together with `reason`, a `command` over 2000 code points, invalid JSON, a JSON array, an integer of more than 4300 digits, and a `command` holding a lone surrogate (JSON `"\ud800"`) are each rejected, never repaired → the REPL prints `No usable proposal came back from the model.` and keeps running; the surrogate case runs with `out` a UTF-8 `io.TextIOWrapper` over `io.BytesIO`, not `io.StringIO`. (The "risk lower than the gate's class" vector needs the gate — #12 adds it.) (e) a proposal is shown as `Proposed command (risk: <risk>, <N> line[s]):`, then each command line prefixed with `  | `, then a line saying nothing runs yet; a multi-line `command` (contains LF) and one containing TAB are accepted and shown with each line prefixed and TAB as-is; a `command` whose second line is `Proposed command (risk: read-only, 1 line):` never prints that text as an unprefixed line; a `command` containing any other C0 control (ESC, CR), DEL, a C1 control, a bidi control (U+202E is the required vector), a Unicode format character (category Cf: U+200B, U+FEFF), U+2028, or a tag character (U+E0041) is rejected (→ the "no usable proposal" reply), never shown; each of those characters in a request is escaped in `:context`. (f) `:status` lists the prompt files that were loaded.
- **Falsifiability:** RED is reachable on the shipped C4 gate (`engine/scripts/run-verify.sh`, plain pytest on the host). With the production change reverted, the backend, stub, prompts loader and parser do not exist, so each test's in-function import fails; through `Repl`, natural-language input gets today's "the model backend arrives in M0.8." reply and `:context` gets #14's placeholder (`src/nl_shell/input_modes.py:105`) — tests ran, failures > 0. GREEN needs PyYAML in the gate venv (doctor row `pyyaml`). No model, GPU or network: the stub is the only backend under test.
- **Invariant to restore:** Every text nl-shell prints from a proposal, from `:context` or from a start-up error goes through one hidden-character predicate, and the parser rejects exactly what that predicate flags (threat model must-holds "Output rendering is filtered everywhere" and "What the user confirms is exactly what runs", `.oss-scanner/threat_model.md:117-120`). No display path prints model or file text raw.
- **Repo + branch target:** eduralph/nl-shell @ main, built on the wave base that folds #92's accepted patch (draft PR #142); #14 is already merged on main (PR #103, 2ba3fb5). If #92 is not accepted this bundle is not scheduled; Do must not invent stand-ins for #92's target loader.
- **Ordering note:** Depends on #92 (target loader, `config.toml` location). Conflicts with #62: both extend #92's target loader / `target.toml`. The sibling character-safety slice stacks on this one. #77 builds on this bundle's backend interface and parser.
- **Surfaces:** data
- **Difficulty:** high
- **Scope:** (1) Prompts: a default `targets/ubuntu-26.04/prompts/prompts.yaml`, found through #92's target loader (the active target's folder) — no repo-relative path in code and no packaging change (a non-editable install has no defaults until #48/#50 ship `targets/`, ADR-0023:108-109; accepted for M0); overridden key by key by `$XDG_CONFIG_HOME/nl-shell/prompts.yaml` (ADR-0020 §1–§2); loaded with a safe YAML loader only; a fixed, documented set of keys (system prompt, few-shot examples, template for the volatile part), validated, unknown keys refused; a malformed file refuses start-up the way #92 refuses a malformed `target.toml`. (2) Model input: an ordered list of chat messages in the order ADR-0018 §4 requires — stable part first (system prompt, few-shot examples), volatile part last (an empty state-block slot until #11, then the request); one canonical form that is both what the backend is handed and what `:context` prints. (3) Backend interface + recording stub in `src/` (so #13/#78 tests can use it): the interface takes the model input and returns the raw response text; the stub returns test-configured responses and records every input. (4) Strict `proposal/v1` parser: reject, never repair (ADR-0018 §3, spec rule 5); a `command` with a hidden character is rejected; schema kept in one place so #77 sends the same schema for constrained decoding. (5) REPL: natural-language input and `@request` go through prompt → backend → parser; the result is shown as text (framed proposal per criterion (e); templated replies for `clarify` / `refuse` per `reason`; the "no usable proposal" reply on rejection). With no backend configured — the interactive default until #77 — the reply says so. (6) Hidden characters, in one module with one predicate and one escape function: C0 except LF and TAB, DEL, C1, the bidi controls (U+061C, U+200E, U+200F, U+202A–U+202E, U+2066–U+2069), every category Cf character, U+2028/U+2029, the tag block U+E0000–U+E007F, and lone surrogates. Escaped as `\xHH` (≤ U+00FF), `\uHHHH` (≤ U+FFFF) or `\UHHHHHHHH`, lowercase hex; `:context` also escapes a backslash as `\\`; LF and TAB as-is; ordinary text byte-identical. Used by the parser, every REPL reply, `:context`, and the start-up error print in `cli.py`. (7) `:context` replaces #14's placeholder; `:status` gains the loaded prompt files. (8) `PyYAML` in `pyproject.toml` `dependencies`; update the threat model's `How to exercise it` sentence about the stub. / out of scope: Default_Ignorable code points outside Cf, non-ASCII whitespace, blank glyphs, private-use and unassigned code points, combining-mark caps and mixed-script detection (sibling slice); the HTTP client, endpoints, `--dev-teacher` (#77); ask mode `?`; state block content and taint (#11, #79); running or gating a proposal and the "risk below the gate's class" vector (#12, #78); a user-facing switch to pick the stub; the confirm UI and its line-wrap hidden-tail handling (#74); the `--- <role> ---` separator spoof once #11 fills the state block (note for #11); architecture doc 05.
- **External dependencies:** `pyyaml`
- **Test file:** `tests/test_backend.py` (new). The C4 red leg reverts every non-`tests/` file and re-runs this file; a module-level import of a new module would fail to import and make the run unverifiable instead of red. Import new modules inside test functions or fixtures; at module level only the standard library, pytest and `nl_shell.repl.Repl`. Pin reply texts as literals. `tests/test_repl.py:15` and `tests/test_input_modes.py:15,19,23,26` pin today's M0.8 placeholder replies; update the ones whose reply changes in the same patch. Keep `Repl(read, out)` and `Repl(read, out, status_lines)` working; build the `Repl` with the stub through the constructor parameter the patch adds, inside the test.
- **Citations expected:** Do must cite path:line on the wave base for every change. Wiring points: the natural-language reply `src/nl_shell/repl.py:24-31`; `Repl.__init__` / `Repl.interactive` `src/nl_shell/repl.py:38-55`; `_reply` `src/nl_shell/repl.py:74-84`; the `:context` placeholder `src/nl_shell/input_modes.py:105,112`; start-up errors `src/nl_shell/cli.py:53-55` (the peer callsite: print the new prompts error the same way, through the escape function) and `src/nl_shell/cli.py:64`; the target loader `src/nl_shell/targets.py:127`. Normative: `docs/design/specs/proposal/v1.md` §Requirements 1–5 and §Conformance; ADR-0018 §3–§4; ADR-0020 §1, §2, §4.
- **Prior-art check (triage cycles):** `git -C ../nl-shell log --all -- src/nl_shell/backend.py src/nl_shell/prompts.py src/nl_shell/proposal.py src/nl_shell/render.py targets/ubuntu-26.04/prompts` → no commits on any branch. `gh pr list --state all` → no PR touching these paths (#103 = #14, merged; #142 = #92, draft). Earlier attempts: parent bundle #16 iterations v1–v3 (never published).
- **Disposition hint:** new-feature

## Design

- Model input text form (what `:context` prints and the test rebuilds): for each message, a line `--- <role> ---` followed by the message content; messages separated by one `\n`; hidden characters and backslashes escaped as in Scope (6).
- Parser output: a small typed value (`command` + `risk`, or `clarify` / `refuse` + `reason`) or a rejection with a reason for the log; nothing in between.

## STOP discipline

Draft only until Check sign-off. Pushing to a feature/draft branch and opening a
draft PR MAY happen during the cycle (useful for CI feedback). The PR MUST NOT be
marked ready before sign-off accepts.
<!-- pdca:end child-1 -->

<!-- pdca:child child-2 -->
# Brief — character-safety policy based on UTS #39 (from #16)

> Child 2 of the split of #16. Replaces the core slice's hand-picked hidden-character set
> with a policy built from Unicode properties (UTS #39, Unicode Security Mechanisms), as
> the iteration-3 sign-off asked. Decisions confirmed by the human at Plan (2026-10-15):
> mixed-script words in a proposal are rejected; Unicode data is vendored from the UCD,
> pinned to Python's `unicodedata` version; at most 2 combining marks per base character;
> rejection applies anywhere in a proposal `command`, quoted or not.

- **Slug:** charsafety-uts39-policy
- **Defect:** The core slice's hidden-character predicate (`src/nl_shell/render.py`, C0/C1/DEL/bidi/Cf/U+2028-9/tags/surrogates) lets through characters that render as nothing, as blank, or as a look-alike letter from another script. A model proposal can therefore hide or disguise part of a command (`ls<U+3164>` is a different word to bash than `ls`; `сurl` with Cyrillic U+0441 is not `curl`). Verified on the iteration-3 build: U+3164, U+115F, U+1160, U+FFA0, U+034F, U+FE00–U+FE0F, U+E0100, U+17B4, U+180B and U+2800 were accepted and printed raw (`iteration-v3` adversary and security reviews).
- **Success criterion:** `python3 -m pytest tests/test_charsafety.py` passes and covers, each fed as a stub response through `Repl` with the recording stub: (1) each of U+3164, U+115F, U+1160, U+FFA0, U+034F, U+FE00, U+FE0F, U+E0100, U+17B4, U+180B, U+2800, U+00A0, U+3000, U+E000 (private use) and U+0378 (unassigned in Unicode 16.0) inside a `command` → rejected (`No usable proposal came back from the model.`); and the same character in a request → `:context` prints it as its `\xHH` / `\uHHHH` / `\UHHHHHHHH` escape (lowercase hex). (2) `e` followed by three U+0301 in a `command` → rejected; with two U+0301 → accepted. In `:context`, a request with `e` + three U+0301 prints `e`, two raw U+0301, then `́`. (3) mixed-script words in a `command` are rejected: `сurl example.com` (Cyrillic U+0441 + Latin), `ls /tmp/сurl`, `cat Dокумент.txt`. (4) these are accepted and shown unchanged: `ls Документы`, `cat αρχείο.txt`, `cat 日本語ファイル.txt` (Han + Katakana, allowed by the UTS #39 Japanese combination), `echo café` (precomposed é, and `e` + one U+0301). (5) the vendored tables record their Unicode version, and it equals `unicodedata.unidata_version`. `tests/test_backend.py` still passes.
- **Falsifiability:** RED on the shipped C4 gate (`engine/scripts/run-verify.sh`, plain pytest). With this slice's production change reverted, the core slice's predicate stays: none of the vectors in (1)–(3) is in its set (none is C0/C1/DEL/bidi/Cf/separator/tag/surrogate — U+3164 and U+115F/U+1160/U+FFA0 are Lo, U+034F/U+FE0F/U+E0100/U+17B4/U+180B are Mn, U+2800 is So, U+00A0/U+3000 are Zs, U+E000 is Co, U+0378 is Cn), so they are accepted and printed raw, and test (5)'s import of the tables module fails — failures > 0. The tests never read the UCD files, so the gate needs no extra package.
- **Invariant to restore:** Text nl-shell shows from a proposal, `:context` or an error is exactly the text that is there: no character that renders as nothing or as blank, and no word that mixes look-alike scripts, reaches the user unmarked, and a proposal carrying one is rejected (threat model must-hold "What the user confirms is exactly what runs", `.oss-scanner/threat_model.md:117-120`; UTS #39 §3.1 general security profile, §5.1 mixed-script detection). Defined by Unicode properties, not by a hand-kept list.
- **Repo + branch target:** eduralph/nl-shell @ main, built on the wave base that folds the core slice's accepted patch (and, through it, #92). If the core slice is not accepted this bundle is not scheduled.
- **Depends on:** child-1
- **Ordering note:** Stacks on the core slice: it changes `src/nl_shell/render.py` and the parser's rejection in `src/nl_shell/proposal.py`, both created there. No overlap with #92's target loader, so no conflict with #62.
- **Surfaces:** data
- **Difficulty:** medium
- **Scope:** (1) Hidden set (rejected in a proposal `command`, escaped on every display path): the core slice's set, plus every code point with Default_Ignorable_Code_Point (UCD `DerivedCoreProperties.txt`), every White_Space code point (`PropList.txt`) except U+0020, LF and TAB, U+2800 BRAILLE PATTERN BLANK, and general categories Co (private use) and Cn (unassigned, per `unicodedata`). (2) Combining marks: at most 2 consecutive characters of category Mn or Me after one base character; a `command` with more is rejected; on display, the 3rd and later marks are escaped. (3) Mixed-script words in a proposal `command`: split the `command` into words at ASCII whitespace and ASCII punctuation (Python's `string.punctuation`); a word passes if the intersection of its characters' Script_Extensions sets (UCD `ScriptExtensions.txt`, falling back to `Scripts.txt`), ignoring Common and Inherited, is non-empty, after the UTS #39 §5.1 augmentation (Han ⇒ +Bopomofo, Hiragana, Katakana, Hangul combinations: Hanb, Jpan, Kore); otherwise the proposal is rejected. Typed input and `:context` are not checked for mixed script (the gate's typed-input handling is #12's). (4) Data: vendor only the needed ranges as a generated Python module (e.g. `src/nl_shell/_unicode_tables.py`) with the Unicode version in it, produced by a generator script in `scripts/` that reads the UCD files from `/usr/share/unicode/` (Ubuntu package `unicode-data`, 16.0.0 — the same version as Python 3.14's `unicodedata`); commit the generated module; no new runtime dependency. (5) Rejection applies anywhere in a `command`, quoted or not — stricter than `docs/design/specs/policy-gate/v1.md:58-61` ("outside quotes"); say so in the threat model and note that #12, which has the bash parser, may relax it to outside-quotes only. (6) Update the threat model must-hold text (`.oss-scanner/threat_model.md:117-120`) to name this policy. Tests import changed/new modules inside test functions only. / out of scope: the prompts loader, backend, stub, `:context` wiring and REPL flow (core slice); whole-script confusables and skeleton matching against a word list (e.g. an all-Cyrillic `с` alone) — #74 shows non-ASCII as escapes in the confirm UI; the confirm UI and line-wrap handling (#74); typed-input warnings (#12); the `--- <role> ---` separator spoof (#11); the HTTP client (#77).
- **External dependencies:** `unicode-data` (build only: the generator reads it; the tests do not).
- **Test file:** `tests/test_charsafety.py` (new). Import `nl_shell` modules other than `nl_shell.repl.Repl` inside test functions, so the C4 red leg (production reverted) fails tests instead of failing to import.
- **Citations expected:** Do must cite path:line on the wave base for every change. Peer callsites: the core slice's hidden-character predicate and escape function in `src/nl_shell/render.py` (replace the policy there, keep one predicate); the parser's hidden-character rejection in `src/nl_shell/proposal.py` (add the combining-mark and mixed-script checks next to it). Normative: UTS #39 §3.1 and §5.1; `.oss-scanner/threat_model.md:117-120`; `docs/design/specs/policy-gate/v1.md:58-61`.
- **Prior-art check (triage cycles):** `git -C ../nl-shell log --all -S 'Default_Ignorable'` and `-S 'Script_Extensions'` → nothing. No PR or branch touches these paths. Earlier attempts: parent #16 iterations v2–v3 widened the list by hand (rejected at sign-off; do not repeat that approach).
- **Disposition hint:** new-feature

## STOP discipline

Draft only until Check sign-off. Pushing to a feature/draft branch and opening a
draft PR MAY happen during the cycle (useful for CI feedback). The PR MUST NOT be
marked ready before sign-off accepts.
<!-- pdca:end child-2 -->

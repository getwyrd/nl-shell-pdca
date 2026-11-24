# Result — issue 143 / prompts-yaml-context-recording-stub-core

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: Goal (new functionality). Natural-language input and `@request` build the model input from an editable prompts YAML, send it to a model backend, and parse the answer strictly as a `proposal/v1` object, which the REPL shows without running it. A recording stub backend returns fixed responses and records every model input it was sent (#13 relies on this). `:context` shows the exact model input of the last request; `:status` lists the loaded prompt files. Every text shown from a proposal, `:context` or a start-up error passes through one hidden-character predicate and one escape function, so #144 can replace the character policy in one place.
- Success criterion: `python3 -m pytest tests/test_backend.py` passes, and it covers: (a) through `Repl` with the stub backend: a natural-language line, then `:context` → `:context` prints exactly the text the test itself builds from the stub's recorded message list using the text form in Design (the test re-implements that form inline; it does not call the module's serializer), byte for byte; the recorded list's order is: the system message first, then the few-shot example messages in file order, then the user message last, whose content ends with the user's request text; the same for `@show disk usage`; `:context` before any request → the fixed reply `No model input yet: :context shows the model input of the last request.` (b) the stub's recorded inputs are a list tests can read, one entry per request, in order; a request containing ESC (`show \x1b[2J disk`) → the recorded input carries the raw ESC, and `:context` prints it as the four characters `\x1b`; a request containing a literal backslash followed by `x1b` (typed, five characters `\`, `x`, `1`, `b`) → `:context` prints `\\x1b`, so a real ESC and the typed text print differently; the rest of the text is unchanged. (c) a user `prompts.yaml` in `$XDG_CONFIG_HOME/nl-shell/` (the suite's temporary HOME) that changes the system prompt → the next recorded input and `:context` both carry the user's text; a malformed user `prompts.yaml` (invalid YAML, not a mapping, a key with the wrong type, an unknown key, a sequence used as a key, and a file whose only content is `!!python/object/apply:os.system ["touch <tmp>/pwned"]`) → `nl_shell.cli.main([])` (with a matching os-release injected as `tests/test_cli.py:29-46` does) returns non-zero before the REPL reads any line, stderr contains the file's full path, and for the tag case `<tmp>/pwned` does not exist (safe loader); a malformed file containing U+202E inside the broken line → stderr contains the six characters `\u202e` and never the raw U+202E; the same for a malformed `target.toml` (in the injected targets root) with U+202E in the broken line, because #92's existing start-up error print goes through the same escape function. (d) the `proposal/v1` §Conformance list, each fed as the stub's raw response: every valid shape (`command` + `risk`; `clarify` + `reason`; `refuse` + `reason`) is accepted, and extra properties, a missing `kind`, an unknown `kind` value, an unknown `risk` value, an unknown `reason` value, an empty `command` (`""`), `clarify` with a `command`, `refuse` without a `reason`, a missing `risk`, `command` together with `reason`, a `command` over 2000 code points, invalid JSON, a JSON array, an integer of more than 4300 digits, and a `command` holding a lone surrogate (JSON `"\ud800"`) are each rejected, never repaired → the REPL prints `No usable proposal came back from the model.` and keeps running; the surrogate case runs with `out` a UTF-8 `io.TextIOWrapper` over `io.BytesIO`, not `io.StringIO`. (The "risk lower than the gate's class" vector needs the gate — #12 adds it.) (e) a proposal is shown as `Proposed command (risk: <risk>, <N> line[s]):`, then each command line prefixed with `  | `, then a line saying nothing runs yet; a multi-line `command` (contains LF) and one containing TAB are accepted and shown with each line prefixed and TAB as-is; a `command` whose second line is `Proposed command (risk: read-only, 1 line):` never prints that text as an unprefixed line; a `command` containing any other C0 control (ESC, CR), DEL, a C1 control, a bidi control (U+202E is the required vector), a Unicode format character (category Cf: U+200B, U+FEFF), U+2028, or a tag character (U+E0041) is rejected (→ the "no usable proposal" reply), never shown; each of those characters in a request is escaped in `:context`. (f) `:status` lists the prompt files that were loaded: one line per file, in load order (the target's default first, then the user file if present), each exactly `prompts: <absolute path>`, after the existing status lines. (g) with no backend configured (plain `Repl(read, out)`), a natural-language line and an `@request` both get exactly `No model backend is configured, so nl-shell can't answer this yet: the model client arrives with #77.`; `tests/test_repl.py` and `tests/test_input_modes.py` are updated to pin that literal where the M0.8 reply changes.
- Repo + branch target: eduralph/nl-shell @ main, built on the wave base that folds #92's accepted patch (draft PR #142, branch `enhancement/92-os-target-folder-and-selection` @ 4c755f2 — every wiring citation below was checked there; plain main lacks `targets.py` and the `cli.py` error path); #14 is already merged on main (PR #103, 2ba3fb5). If #92 is not accepted this bundle is not scheduled; Do must not invent stand-ins for #92's target loader.
- Scope (one logical fix) / out of scope: (1) Prompts: a default `targets/ubuntu-26.04/prompts/prompts.yaml`, found through #92's target loader (the active target's folder) — no repo-relative path in code and no packaging change (a non-editable install has no defaults until #48/#50 ship `targets/`, ADR-0023 `docs/design/adr/0023-os-targets.md:123-124`; accepted for M0); overridden key by key by `$XDG_CONFIG_HOME/nl-shell/prompts.yaml` (ADR-0020 §1–§2); loaded with a safe YAML loader only; a fixed, documented set of keys (system prompt, few-shot examples, template for the volatile part), validated, unknown keys refused; a malformed file refuses start-up the way #92 refuses a malformed `target.toml`. (2) Model input: an ordered list of chat messages in the order ADR-0018 §4 requires — stable part first (system prompt, few-shot examples), volatile part last (an empty state-block slot until #11, then the request); one canonical form that is both what the backend is handed and what `:context` prints. (3) Backend interface + recording stub in `src/` (so #13/#78 tests can use it): the interface takes the model input and returns the raw response text; the stub returns test-configured responses and records every input. (4) Strict `proposal/v1` parser: reject, never repair (ADR-0018 §3, spec rule 5); a `command` with a hidden character is rejected; schema kept in one place so #77 sends the same schema for constrained decoding. (5) REPL: natural-language input and `@request` go through prompt → backend → parser; the result is shown as text (framed proposal per criterion (e); templated replies for `clarify` / `refuse` per `reason`; the "no usable proposal" reply on rejection). With no backend configured — the interactive default until #77 — the reply says so. (6) Hidden characters, in one module with one predicate and one escape function: C0 except LF and TAB, DEL, C1, the bidi controls (U+061C, U+200E, U+200F, U+202A–U+202E, U+2066–U+2069), every category Cf character, U+2028/U+2029, the tag block U+E0000–U+E007F, and lone surrogates. Escaped as `\xHH` (≤ U+00FF), `\uHHHH` (≤ U+FFFF) or `\UHHHHHHHH`, lowercase hex; `:context` also escapes a backslash as `\\`; LF and TAB as-is; ordinary text byte-identical. Used by the parser, every REPL reply, `:context`, and the start-up error print in `cli.py` — both the new prompts error and #92's existing `config`/`target.toml` error print at `cli.py:53-55` (criterion (c) tests both). This bundle also takes over the threat model's "proposals with bidi or control characters are rejected (#74)" duty (`threat_model.md:128-129`): the parser rejects them here; #74 keeps the confirm-UI rendering. (7) `:context` replaces #14's placeholder; `:status` gains the loaded prompt files. (8) `PyYAML>=6` in `pyproject.toml` `dependencies` (the version the gate venv has, 6.0.3); update the threat model's `How to exercise it` sentence about the stub, and change the `(#74)` attribution on the bidi/control-character rejection to this work item. / out of scope: Default_Ignorable code points outside Cf, non-ASCII whitespace, blank glyphs, private-use and unassigned code points, combining-mark caps and mixed-script detection (#144); the HTTP client, endpoints, `--dev-teacher` (#77); ask mode `?`; state block content and taint (#11, #79); running or gating a proposal and the "risk below the gate's class" vector (#12, #78); a user-facing switch to pick the stub; the confirm UI and its line-wrap hidden-tail handling (#74); the `--- <role> ---` separator spoof once #11 fills the state block (note for #11); architecture doc 05.

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (78 of 171 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — security-relevant paths touched and the threat model updated: src/nl_shell/backend.py
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review editable prompt layers, recorded model input and `:context`, strict proposal parsing, and safe display without command execution (#143).

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The bounded stub-only milestone has explicit observable acceptance criteria and defers execution/client work; brief.md:12 and target/docs/design/specs/proposal/v1.md:42. |
| C2 Reproduction (red pre-fix) | PASS | Captured pre-fix execution reaches test failures rather than collection errors: 78 of 171 fail, including missing backend functionality; gate-logs/C4-verify.log:15. |
| C3 Change | PASS | The affected surfaces fit the requested prompt/backend/parser/display feature and preserve constructor compatibility; target/src/nl_shell/repl.py:70 and target/src/nl_shell/cli.py:43. |
| C4 Verification (red→green) | PASS | Frozen gate output shows 171 green tests followed by the pre-fix failures; independent pytest rerun is unavailable because this host lacks pytest, so this verdict rests on the captured run; gate-logs/C4-verify.log:10. |
| C5 Causal adequacy | PASS | Ordered input is retained before backend invocation and strict rejection precedes display; direct REPL/context and hostile-response smoke checks passed, with no capability-probe workaround found; target/src/nl_shell/repl.py:148 and target/src/nl_shell/proposal.py:105. |
| T1 Structure | PASS | Prompt loading, backend protocol, parsing and character policy have separate responsibilities with a shared display predicate; target/src/nl_shell/prompts.py:93 and target/src/nl_shell/proposal.py:131. |
| T2 Shape | PASS | Security obligations match the parser/rendering boundary and the frozen touch scanner passed; target/.oss-scanner/threat_model.md:127 and gate-logs/T2-threat-model.log:10. |
| T3 Runtime | PASS | Captured full-suite execution reports 388 passing tests; direct smoke checks also exercised real PyYAML 6.0.3, ESC context escaping and surrogate/duplicate/huge-integer/deep-JSON rejection; gate-logs/T3-suite.log:17 and target/src/nl_shell/proposal.py:109. |
| T4 Contribution | N/A | Contribution artifacts are absent by design; substantive contribution auditing must rerun at publish; gate-logs/T4-contribution.log:10. |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art across merged history and closed/rejected PRs — the brief reports a path-based search, but this target has only one synthetic base commit and supplies no independently inspectable PR-history evidence; brief.md:25. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decide whether the stub-only proposal display and editable prompt/context behavior meet M0.8 expectations, including the deliberately unavailable interactive backend and deferred character-policy expansion; target/src/nl_shell/cli.py:73 and target/src/nl_shell/render.py:8. |

Evidence limits: the supplied target is readable and contains the patch. No production files were changed. The independent pytest attempt failed immediately with `/usr/bin/python3: No module named pytest`; therefore no stash/red rerun was attempted after that toolchain failure. The frozen C4 log was read in full and records test-level failures, not a host failure. PyYAML itself was present and exercised, so the declared external dependency is discharged. Instance-scoped gate wrappers are unavailable here; their captured outputs support the gate adjudications above. No INTEGRATION.md was present in the supplied target. Affected-path `git log --all` returned no commits for the new production paths; the synthetic history cannot establish the remote prior-art claim.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue #143 (prompts YAML, `:context`, recording stub)

**Overall:** I tried to break the red→green proof, the parser, the prompts loader and the escaping. The fix holds up. I found one real test gap in a safety property the brief requires, a few smaller unpinned behaviours, and no input that makes production misbehave in scope.

## Red→green proof re-run

I re-ran the proof myself, using the pytest from the `nl-shell-pdca` venv as a tool against copies of `$PDCA_TARGET`:
- **Green:** `tests/test_backend.py` gives 58 passed. The whole suite gives 388 passed, the same as `gate-logs/T3-suite.log`.
- **Red:** with `backend.py`, `prompts.py`, `proposal.py`, `render.py` and the `src/` edits reverted, `tests/test_backend.py` gives 58 failed. This matches `gate-logs/C4-verify.log` (78 of 171 failed across the bundle files).

Most red failures are `ModuleNotFoundError` from the imports inside test functions. The brief planned this, so it counts as red, not "unverifiable". The green side runs the production path: `cli.main` → `prompts.load` → `Repl` → `prompts.build` → `RecordingStub` → `proposal.parse`. The `:context` oracle (`tests/test_backend.py:57-93`) is a separate copy of the predicate. The brief asks for that, and it means the byte-for-byte check can't pass by calling the same code.

## Findings

- NEEDS-HUMAN [impl] — No test covers the REPL-wide escape at `src/nl_shell/repl.py:124` (`print(render.escape(self._reply(text)), ...)`). The brief's invariant says every REPL reply passes through the escape function. I changed that line to `print((self._reply(text)), ...)` and the whole suite still passed (388/388).
  - **Concrete case:** with no backend, type `:foo` followed by a real U+202E, then ESC `[2J`. The patched code prints `Unknown meta-command :foo\u202e\x1b[2J. ...` as visible escape text. With the mutation, the raw RLO and the clear-screen ESC sequence reach the terminal, and no test notices.
  - `:context` hides the gap because `prompts.render_input` already escapes. Proposals hide it because the parser has already rejected hidden characters.
  - **Fix:** add a test that sends an unknown meta-command (or a `:status` line) containing ESC and U+202E through `Repl`, and asserts the escaped form appears.
- NEEDS-HUMAN [impl] — No test covers three documented strictness rules. Each of these mutations left the suite at 388/388:
  - Removing the duplicate-key rejection at `src/nl_shell/proposal.py:107`. A response `{"kind":"refuse","kind":"command",...}` would then be read as last-key-wins instead of rejected.
  - Removing the check that each few-shot `response` is a valid proposal, at `src/nl_shell/prompts.py:164` (a contract stated in the module docstring).
  - Removing the `{state}`-before-`{request}` order check at `src/nl_shell/prompts.py:176`.

  None of these is in the brief's (a)–(g) list. But the code claims them, and a later edit could drop any of them silently. Add one malformed-response case and two malformed-prompts cases.
- Low: the `target.toml` bidi test (`tests/test_backend.py:330-357`) does not test what criterion (c) describes. Criterion (c) asks for U+202E in the *broken line*. The test's `shell = "<U+202E>bash"` (`:342`) is valid TOML that fails validation, and `targets.py:180` already prints it with `!r`, which escapes it before `cli._error` runs. So `assert "\\u202e" in err` (`:355`) would pass without the fix. The test only fails without the fix because of the U+202E placed in the root folder name (`:333`), as its own comment admits. It does go red: dropping the escape in `cli._error` fails 2 tests. So the escape is covered, just not through the vector the brief names. Not tagged; no action strictly needed.
- Low, outside this diff's scope: `RecordingStub.complete` raises `StubExhausted` (`src/nl_shell/backend.py:43`), and `Repl._propose` (`src/nl_shell/repl.py:150`) does not catch backend errors. Any exception from `complete` therefore ends the REPL with a traceback. That's fine for the test-only stub. #77 should decide whether a backend failure becomes the "no usable proposal" reply. Not tagged.

## Attempted and could not refute

- **Parser** (`src/nl_shell/proposal.py:101-151`) correctly rejects: NEL U+0085, VT, U+2029, a lone low surrogate `\udc00`, `NaN`, `[` nested 100,000 deep (`RecursionError` is caught), a boolean `risk`, an object as `command`, and a leading BOM.
- **Accepted, but not a spec violation:**
  - Leading and trailing whitespace around the JSON object.
  - `clarify`/`refuse` with an extra `risk` field. Rule 2 does not forbid it.
  - A whitespace-only or LF-only `command`. `minLength: 1` is met. It shows as blank `  | ` lines, which are still visibly framed.
- **Header spoofing:** this is not possible. Every command line gets the `  | ` prefix (`src/nl_shell/repl.py` `show_proposal`). Dropping the per-line prefix fails 2 tests.
- **Double escaping:** escaping the `:context` text twice is harmless. The output of `escape` contains no hidden characters, so the second pass changes nothing.
- **Prompts loader:**
  - It only ever uses `yaml.safe_load`, and non-UTF-8 bytes are refused.
  - YAML parse errors quote the raw line. `cli._error` escapes it, and the bidi prompts test fails without that escape.
  - An `XDG_CONFIG_HOME` with undecodable bytes (surrogate-escaped path) is escaped, not crashed on.
- **Scope note:** U+115F (Hangul filler) passes the parser. That falls under Default_Ignorable outside Cf, which the brief assigns to #144.
<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory): prompts YAML, `:context`, recording stub (#143)

**Attacker-reachable inputs this diff touches:** the model's raw response (threat model "Where untrusted input enters" item 5). It reaches the strict `proposal/v1` parser (`src/nl_shell/proposal.py:168-218`), the proposal display (`src/nl_shell/repl.py:52-66`, `:124`) and `:context` (`src/nl_shell/prompts.py:210-215`). Everything else is trusted under the threat model: the user's typed request, `prompts.yaml` in the user's config dir, and the target's shipped default `prompts.yaml` / `target.toml`.

## Findings

No finding at any severity on the threat model's scale.

## What I checked

- **The parser rejects instead of repairing** (`src/nl_shell/proposal.py:176-218`). I ran these against the patched source and each one was rejected:
  - a duplicate `risk` key (`..."risk":"read-only","risk":"privileged"}`) → `duplicate key` (`:157-161`). Python's default would keep the last value silently.
  - `NaN` → rejected (`:164`)
  - 100,000-deep nesting → `RecursionError`, caught (`:183`)
  - a list in place of `risk` → `unknown risk`
  - VT and U+2029 in `command` → hidden character

  Integers over 4300 digits are rejected because of `requires-python >=3.12` (`pyproject.toml:12`). `Rejected.why` holds only fixed text or counts, never response text, and is never printed.
- **The parser and the display use one predicate.** `render.has_hidden` (`src/nl_shell/render.py:50`) gates `command` at `proposal.py:205`, so a command that gets accepted has nothing for `render.escape` at `repl.py:124` to change. What is shown is byte for byte the parsed command, which keeps "What the user confirms is exactly what runs" intact as far as this patch reaches. The predicate covers C0 except LF/TAB, DEL, C1 (including NEL U+0085), the bidi controls, all of Cf, U+2028/9, the tag block and surrogates (`render.py:34-47`).
- **Spoofing the UI through LF.** Every command line is printed behind `  | ` (`repl.py:57-60`), and the header's `risk` is an enum value, so the model can't print an unprefixed line or a fake header. CR is rejected, so it can't overwrite the prefix either. The test is `tests/test_backend.py:454-462`.
- **`:context` output** escapes hidden characters and backslashes (`prompts.py:213`), so a real ESC and the typed text `\x1b` print differently (criterion b). The second `escape` pass at `repl.py:124` leaves that ASCII-only text unchanged, so nothing is escaped twice.
- **Start-up errors** all go through `cli._error` → `render.escape` (`src/nl_shell/cli.py:68-70`), including PyYAML's quoted problem line. The YAML file is loaded with `yaml.safe_load` only (`prompts.py:127`), and the `!!python/object/apply` vector is tested. These files are trusted config, so this is defence in depth, not an attacker path.
- **The tests cover the hostile cases, not just the friendly ones.** Every hidden-character class is rejected in `command`, with `ensure_ascii` both on and off (`tests/test_backend.py:466-486`). The full §Conformance rejection list is tested (`:362-390`), the lone surrogate is tested on a real UTF-8 stream (`:396-408`), and so is the header spoof.

## Notes (not findings)

- No test pins the duplicate-key and `NaN` rejections, which the code handles correctly (probe above). Adding a duplicate-`risk` vector to `REJECTED` in `tests/test_backend.py:364` would pin the case where the risk label is ambiguous. That matters once #12 lets the model's risk label raise the gate's class. It is optional and not required by the brief.
- NBSP inside `command` (`ls -la`) is accepted and shown raw. That is non-ASCII whitespace, which the brief explicitly leaves to #144, and the threat model's Known gaps don't call for raising it here.
- `cli._error` escapes without `backslash=True`, so in a start-up error a real U+202E and the typed text `\u202e` print the same way. The only text that reaches it comes from the user's own paths and config files, which the threat model trusts. The brief only requires the `\u202e` form there, which the patch meets.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T5 Judgment — Confirm affected-path prior art across merged history and closed/rejected PRs — the brief reports a path-based search, but this target has only one synthetic base commit and supplies no independently inspectable PR-history evidence; brief.md:25.
- [ ] Validation — fitness-to-purpose — Decide whether the stub-only proposal display and editable prompt/context behavior meet M0.8 expectations, including the deliberately unavailable interactive backend and deferred character-policy expansion; target/src/nl_shell/cli.py:73 and target/src/nl_shell/render.py:8.
- [ ] No test covers the REPL-wide escape at `src/nl_shell/repl.py:124` (`print(render.escape(self._reply(text)), ...)`). The brief's invariant says every REPL reply passes through the escape function. I changed that line to `print((self._reply(text)), ...)` and the whole suite still passed (388/388).
- [ ] No test covers three documented strictness rules. Each of these mutations left the suite at 388/388:
- [ ] **No tracker record to check the brief against.** The sandbox has `brief.md` and `dependency-state.json`, but no `notes.json` and no `sources/` directory (Glob of the cwd lists only `.claude/*`, `brief.md`, `dependency-state.json`). So I could not compare the problem statement, the claim "iteration-3 design, which passed review apart from the character-safety coverage", or the #16→#144 split against the thread. Nobody has checked the brief's framing against the tracker. The human should confirm it at sign-off, or the driver should re-run this review with the thread attached.
- [ ] **The target I was given is not the base the brief describes, so the brief's wiring citations can't be checked.** The brief targets "main, built on the wave base that folds #92's accepted patch (draft PR #142)". `$PDCA_TARGET` is plain main without #92:
- [ ] **Two cited line numbers don't match the files on main.**
- [ ] **Criterion (d) leaves out schema rules, so a parser that is too lenient still passes.** (d) lists only the spec's §Conformance list plus a few extras. Spec `docs/design/specs/proposal/v1.md:43-49` also requires:
- [ ] **Two user-visible replies change, but no text or test pins them.**
- [ ] **Scope (6) also changes #92's existing error output, and no criterion covers it.** Scope (6) says the escape function is "Used by … the start-up error print in `cli.py`". The Citations list calls `cli.py:53-55` "the peer callsite". Read together, this changes #92's existing `target.toml` error print, not just the new prompts error. Criterion (c) tests only a malformed `prompts.yaml` containing U+202E. If retrofitting #92's path is intended, add a `target.toml` U+202E vector to (c). If not, say that only the new prompts error goes through the escape function. As written it is extra review surface that nothing tests.
- [ ] **The rejection rule in Scope (4)/(6) overlaps #74, which the brief puts out of scope.** The threat model gives rejection of "proposals with bidi or control characters" to #74 (`threat_model.md:128-129`: "proposals with bidi or control characters are rejected (#74)"). The brief makes the parser reject them here, and lists "the confirm UI" (#74) as out of scope. Doing it here is defensible, because the parser has to apply the same predicate. But the brief should say that #74's rejection duty moves to this bundle, or that it is shared. Otherwise #74's plan will duplicate it, or remove it as already done.
- [ ] **The `:context` text form is underspecified, so criterion (a) partly checks itself.** Design says "a line `--- <role> ---` followed by the message content; messages separated by one `\n`". It doesn't say whether a `\n` separates the header from the content, or whether output ends with a trailing newline. Criterion (a) makes the test "re-implement that form inline". Do writes both the serializer and the test, so whatever separator Do chooses will pass "byte for byte". The form is also the contract #11 and #77 build on. Spell it out exactly, for example `"--- system ---\n" + content`, joined with `"\n"` and no trailing newline, so the test checks the brief and not Do's choice.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: iterated-to-Do
- Iteration delta (if iterating): Auto-iterate (round 1): rebuilding for the implementation-level findings — No test covers the REPL-wide escape at `src/nl_shell/repl.py:124` (`print(render.escape(self._reply(text)), ...)`). The brief's invariant says every REPL reply passes through the escape function. I changed that line to `print((self._reply(text)), ...)` and the whole suite still passed (388/388).; No test covers three documented strictness rules. Each of these mutations left the suite at 388/388:. Deferred, not addressed here: 9 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- By / date: auto-iterate / 2026-10-15

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 8 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

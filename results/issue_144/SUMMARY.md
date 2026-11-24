# Result — issue 144 / charsafety-uts39-policy

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: #143's hidden-character predicate (`src/nl_shell/render.py:34` `is_hidden` on the wave base: C0/C1/DEL, bidi controls, Cf, U+2028/U+2029, tag block, surrogates) lets through characters that render as nothing or as blank. A model proposal can hide part of a command: `ls<U+3164>` is a different word to bash than `ls`, but looks the same. Verified on the parent's iteration-3 build: U+3164, U+115F, U+1160, U+FFA0, U+034F, U+FE00–U+FE0F, U+E0100, U+17B4, U+180B and U+2800 were accepted and printed raw. Stacked combining marks (`e` + many U+0301) can also cover nearby characters.
- Success criterion: `python3 -m pytest tests/test_charsafety.py` passes and covers, each fed as a stub response through `Repl` with #143's recording stub: (1) each of U+3164, U+115F, U+1160, U+FFA0, U+034F, U+FE00, U+FE0F, U+E0100, U+17B4, U+180B, U+2800, U+1D159, U+16FE4, U+13441, U+13442, U+00A0, U+3000, U+E000 (private use) and U+0378 (unassigned in Unicode 16.0) inside a proposal `command` → rejected (`No usable proposal came back from the model.`), including when the character sits inside single or double quotes; and the same character in a typed request → `:context` prints it as its `\xHH` / `\uHHHH` / `\UHHHHHHHH` escape (lowercase hex). (2) `e` followed by three U+0301 in a `command` → rejected; with two U+0301 → accepted. In `:context`, a request with `e` + three U+0301 prints `e`, then two raw U+0301 code points, then the six-character ASCII text backslash-u-0-3-0-1 (the escape for the third mark; the test should build it as `'\\u0301'` in Python, never paste it). A `command` that starts with three U+0301 (no base character) → rejected; one that starts with two → accepted. A `command` with LF followed by three U+0301 → rejected. (3) these are accepted and shown unchanged: `ls Документы`, `cat αρχείο.txt`, `cat 日本語ファイル.txt`, `echo café` (precomposed é, and `e` + one U+0301). (4) the vendored tables record their Unicode version as `16.0.0`, and the policy takes every property it uses from them: with `unicodedata` faked (U+0378 → `Lu`, U+1C89 → `Cn`, U+0301 → `Lo`, and one Default_Ignorable code point such as U+3164 → `Lo`), U+0378 is still rejected, `ls Ᲊ` (U+1C89 CYRILLIC CAPITAL LETTER TJE, assigned in 16.0) is still accepted, `e` + three U+0301 is still rejected and U+3164 is still rejected; and a static check finds no `unicodedata` in the source of `nl_shell.render`, `nl_shell.proposal` or `nl_shell._unicode_tables`. (5) regenerating the tables with the generator script from `/usr/share/unicode/` gives a module identical to the committed one (skipped, with the reason, when `/usr/share/unicode/DerivedCoreProperties.txt` is absent **or its first line is not `# DerivedCoreProperties-16.0.0.txt`**, so a host with an older `unicode-data`, such as Ubuntu 24.04's 15.1.0 on `ubuntu-latest` CI, skips instead of failing). `tests/test_backend.py` still passes.
- Repo + branch target: eduralph/nl-shell @ main, built on the wave base that folds #143's accepted patch (`pdca-integration/main-r2546dbf9639f`, tip `cefb359`; #143 is accepted, draft PR #153).
- Scope (one logical fix) / out of scope: (1) Hidden set (rejected anywhere in a proposal `command`, quoted or not; escaped on every display path through #143's one escape function): #143's set, plus every Default_Ignorable_Code_Point (UCD `DerivedCoreProperties.txt`), every White_Space code point (`PropList.txt`) except U+0020, LF and TAB, general categories Co and Cn (from the vendored 16.0.0 tables, not the runtime `unicodedata`, which is 15.0/15.1 on the Python 3.12/3.13 that `requires-python = ">=3.12"` allows), and the named blank glyphs U+2800, U+1D159, U+16FE4, U+13441, U+13442 (human decision, round 3: a property-based set plus a short named list; do **not** switch to UTS #39 Identifier_Status=Allowed). Keep one predicate, used both for rejection and for escaping. (2) Combining marks: at most 2 consecutive characters of category Mn or Me, counted over any run of Mn/Me whatever precedes it (a base letter, nothing at the start of the `command`, LF, or any other character); every non-Mn/Me character ends the run; a `command` with more is rejected; on display, the 3rd and later marks are escaped. (3) Data: vendor only the ranges this policy uses (Cf, Co, Cn, Mn/Me, Default_Ignorable, White_Space) as a generated module `src/nl_shell/_unicode_tables.py` that records `UNICODE_VERSION = "16.0.0"`. Produce it with a generator script `scripts/gen_unicode_tables.py` that reads `/usr/share/unicode/` (Ubuntu package `unicode-data` at 16.0.0, which is the developer host's version and matches Python 3.14's `unicodedata`; the generator must refuse to run, with a clear message, when the files' version header is not 16.0.0. CI on `ubuntu-latest` may have an older package; test (5) skips there). Commit the generated module. The policy reads every property from it and never imports `unicodedata`. No new runtime dependency; `requires-python` unchanged. No script data in this slice; #12 will extend the generator when it adds the mixed-script rule. (4) Threat model: in the "What the user confirms is exactly what runs" bullet (find it by that text; do not touch the sudo bullets above it), name this policy: vendored 16.0.0 tables, the property-defined set plus the named blank list (a blank glyph on neither is not caught), the mark cap, rejection anywhere in a `command` quoted or not, and that this is stricter than `docs/design/specs/policy-gate/v1.md:58-61` ("outside quotes"). It is a superset of a MUST-reject rule, so the spec is not edited, and #12 may relax it. Add a known-gap bullet next to "A model can be talked into proposing a bad command": look-alikes are not caught by the proposal parser. This covers within one script, in Common (`ｃurl`, `𝐜url`, `ⅽurl`; no NFKC rule) and words that mix scripts (`сurl`, with Cyrillic U+0441). Mixed-script words move to #12's parser-based gate; until then they are not caught by nl-shell, and the user's own reading of the confirm prompt is the only check. Do not claim #74's confirm UI as a defence (it is not on this base). Do not claim UTS #39 §3.1 confusable or §5 mixed-script detection. / **out of scope:** any mixed-script or word-splitting rule (moved to #12; do not add a word splitter, joiner list or Script_Extensions data); confusable/skeleton matching and NFKC; the prompts loader, backend, stub, `:context` wiring and REPL flow (#143); the confirm UI and line wrapping (#74); typed-input warnings (#12); the `--- <role> ---` separator spoof (#11); the HTTP client (#77); editing the policy-gate spec.

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (65 of 73 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — no security-relevant path touched
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review #144: replace the hidden-character list with a Unicode 16.0 property policy and named blanks, cap consecutive combining marks, and keep test vectors visibly auditable.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | NEEDS-HUMAN | Confirm/update #144 to record the authorized removal of mixed-script rejection and the Unicode 16.0 pin — the brief reports its tracker still specifies different acceptance criteria (brief.md:35). |
| C2 Reproduction (red pre-fix) | PASS | Independently stashed tracked production changes: U+3164 and three U+0301 after a letter, at start, or after LF were accepted and displayed raw; frozen full-test red leg reports 65 failures (gate-logs/C4-verify.log:15; src/nl_shell/proposal.py:133). |
| C3 Change | PASS | Rejection and display share the same hidden predicate and mark-run policy; changed files stay within the brief's character-policy scope (src/nl_shell/render.py:109; src/nl_shell/proposal.py:133; tests/test_charsafety.py:34). |
| C4 Verification (red→green) | PASS | Stash/pop direct Python checks independently reproduced rejection/escaping after restoration while two marks and U+1C89 stayed accepted; full pytest rerun unavailable locally (no pytest), but captured gate shows 73 green and 65 red failures without collection errors (gate-logs/C4-verify.log:10). |
| C5 Causal adequacy | PASS | The shared property policy removes the incomplete hidden-set cause and consistently counts Mn/Me runs; no capability-probe workaround was added; independently regenerated tables matched byte-for-byte using installed Unicode 16.0.0 data (src/nl_shell/render.py:109; src/nl_shell/render.py:146; scripts/gen_unicode_tables.py:125). |
| T1 Structure | PASS | Generated data is separated from policy and regeneration; display and rejection reuse the existing render boundary rather than introducing a bash tokenizer (scripts/gen_unicode_tables.py:125; src/nl_shell/render.py:130; src/nl_shell/proposal.py:135). |
| T2 Shape | PASS | Threat-model review directly confirms policy, stricter quoted-text handling, and look-alike/mixed-script limitations; the scanner log only says no security-relevant path touched, so it alone is insufficient evidence (.oss-scanner/threat_model.md:130; .oss-scanner/threat_model.md:183; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen whole-suite output shows 554 passed with one forkpty deprecation warning; local pytest is absent, so this verdict rests on that captured execution, supplemented by direct runtime and generator checks (gate-logs/T3-suite.log:25). |
| T4 Contribution | N/A | Contribution artifacts are intentionally drafted later; the substantive audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path prior art across merged history and closed/rejected work — the disposable repository has only one synthetic base commit and GitHub querying failed, leaving the brief's triage account independently unconfirmed; the ASCII-vector defect is resolved (brief.md:32; tests/test_charsafety.py:37). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the policy's intentional limits and usability tradeoff — private-use/unassigned and quoted characters are rejected, while confusables and mixed-script words remain readable-look-alike risks until #12; automated checks cannot decide that product/security fit (.oss-scanner/threat_model.md:133; .oss-scanner/threat_model.md:183). |

Evidence and limits: all source citations refer to the patched disposable target rooted at `$PDCA_TARGET`; it was readable and restored after the red check. The red check stashed tracked changes while retaining untracked test/data/generator files, so it establishes the old production predicate's behavior rather than independently reproducing the gate's missing-module failures. No production patch was edited. The test source independently passed an ASCII-byte check. Unicode-data was present and exercised; no unmet Unicode build dependency remains. The instance-scoped wrappers were unavailable here, and their captured logs were read. No INTEGRATION.md was present in the supplied target. The prior-art query attempted was `gh pr list --repo eduralph/nl-shell --state all --search 'unicode OR charsafety OR UTS' --limit 100`; it failed to connect to api.github.com. No confirmed implementation defect was found.
<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 144 / charsafety-uts39-policy (iteration 7)

**Result: I could not refute the fix.** I tried to break the evidence, the tables, the
generator, the parser rejection and the escape path. Nothing failed. pytest is not
installed in this sandbox, so I did not re-run the suite. I checked the frozen gate logs
instead, and imported the patched modules under Python 3.14.4 (whose `unicodedata` is
16.0.0) to probe them directly. None of the findings below is NEEDS-HUMAN.

## What I attacked, and what held

- **The red→green evidence is real and runs the production code.** `gate-logs/C4-verify.log`
  shows 73/73 green, and 65 of 73 red with the production change reverted. The 8 that stay
  green in the red leg are the ones that should: `test_this_file_is_ascii`, the 5
  accepted-command rows and the two "two marks accepted" rows
  (`tests/test_charsafety.py:37`, `:174`, `:182`, `:209`). Every reject and escape row goes
  through the real `Repl` → `proposal.parse` → `render.escape`
  (`tests/test_charsafety.py:96-121`). It checks the exact output against a pinned
  `NO_USABLE` / `DF_SHOWN`, so it cannot pass by accident. Each row runs with both
  `ensure_ascii` settings, and a second request follows, so a crash or a stuck REPL would
  also fail.
- **The round-3 carry-forward is fixed.** `tests/test_charsafety.py` decodes as pure ASCII
  (grep for non-ASCII bytes finds nothing). `test_this_file_is_ascii`
  (`tests/test_charsafety.py:37-41`) now enforces the docstring's promise at `:6-8`.
- **The vendored tables are right.** I compared each table at `src/nl_shell/_unicode_tables.py:13`,
  `:39`, `:47` and `:783` (CF, CO, CN, MARK) with Python 3.14's `unicodedata` 16.0.0 over
  every code point. They match exactly (170 / 137468 / 819533 / 2033 code points).
  `gen_unicode_tables.generate(/usr/share/unicode, "16.0.0")` gives byte-for-byte the
  committed module.
- **Edge inputs I tried against `proposal.parse` and `render.escape`, all handled as the
  brief says:** NBSP inside quotes; three marks at the start, after a letter and after LF;
  Me marks (U+20DD, U+0489); U+2063; U+E01EF; noncharacters U+FDD0 / U+FFFF / U+10FFFF;
  U+0085; U+001C; U+00AD; U+2003; U+115F+U+1160; a ZWJ between marks; and runs of 3 Thai,
  Kana and U+1ABE marks. All are rejected, and on display only the 3rd and later marks
  are escaped (`e` + 5×U+0301 → `é́́́́`).
- **Every display path goes through the one escape function.** The only callers are
  `src/nl_shell/repl.py:124`, `src/nl_shell/prompts.py:219` and `src/nl_shell/cli.py:70`.
  Each escapes the whole string in one call, so a mark run can't be split across separately
  escaped pieces. There is one predicate (`src/nl_shell/render.py:131-133`), used both by
  the rejection (`src/nl_shell/proposal.py:133-136`) and by `escape`
  (`src/nl_shell/render.py:175`).
- **There is no `unicodedata` left in the policy.** `render.py` no longer imports it, and
  the static check at `tests/test_charsafety.py:222-227` also catches a
  `from unicodedata import …`.

## Observations (not refutations, no action needed to accept)

- `src/nl_shell/render.py:175` / `tests/test_charsafety.py:190-193`: the escape test only
  covers the 3rd mark. If `run > MAX_MARKS` were changed to `run == MAX_MARKS + 1`, the 4th
  and later marks would print raw and no test would fail. The current code is correct (I
  checked 5 marks by hand). Adding a 4-mark row would pin it down. This is a nice-to-have,
  not a defect.
- `scripts/gen_unicode_tables.py:33` checks the version only on
  `DerivedCoreProperties.txt` and `PropList.txt`, because `UnicodeData.txt` has no header.
  A mixed install (an older UnicodeData next to 16.0.0 property files) would get past the
  version check and produce wrong CF/CN/MARK tables. Test (5) catches that only on a host
  that has the right files. The brief's wording ("version header") is still met, so this
  is outside the slice.
- The 2-mark cap is the brief's own rule (round-3/4 sign-off), and it has a known cost.
  Fully pointed Hebrew such as U+05D1 U+05BC U+05B8 U+0591 (bet + dagesh + qamats + a
  cantillation mark) is three Mn in a row, so `too_many_marks` rejects it. A spacing mark
  (Mc, e.g. U+0903) between marks ends the run, also as the brief says. Both are policy
  choices already made, not bugs in this diff.
- `gate-logs/T2-threat-model.log`: the T2 gate printed "no security-relevant path touched",
  even though this diff changes `render.py` and `proposal.py`. That is a gap in the gate's
  path list, not in this patch: the threat model *is* updated
  (`.oss-scanner/threat_model.md:130-140`, `:183-189`), as the brief's Scope (4) asks.
  The edits don't cite #74 as a defence, and they don't claim confusable or mixed-script
  detection.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory) — issue 144 / charsafety-uts39-policy

Attacker-reachable inputs this diff touches: **the model's own output** (threat model item 5, the proposal `command` string, checked at `src/nl_shell/proposal.py:133-136`) and, through the shared `render.escape`, text shown from `:context` (`src/nl_shell/prompts.py:219`), REPL replies (`src/nl_shell/repl.py:124`) and start-up errors (`src/nl_shell/cli.py:70`). The property it serves is the must-hold "What the user confirms is exactly what runs" (`.oss-scanner/threat_model.md:127-140` in the patched tree).

**No finding.** What I checked:

- **Vendored tables are correct.** I compared every code point U+0000–U+10FFFF in `src/nl_shell/_unicode_tables.py` against Python 3.14's `unicodedata` (Unicode 16.0.0 on this host) for CF, CO, CN and MARK (Mn/Me), and against `/usr/share/unicode/` 16.0.0 for DEFAULT_IGNORABLE and WHITE_SPACE. Zero mismatches. So no hidden character slips through a wrong table range.
- **Probes through `proposal.parse`** (each as a `{"kind":"command",...}` JSON proposal): `lsㅤ`, `ls⠀`, `ls \x85` (NEL), `ls​`, `ls\r`, `lsᅟ`, `é́́`, and `é́⃝` (mixing Mn and Me in one run) are all `Rejected`. `render.escape` writes each one as an escape, and only the third mark of a run is escaped (`src/nl_shell/render.py:146-179`).
- **One predicate.** Rejection (`has_hidden`, `too_many_marks`) and display (`escape`) use the same `_HIDDEN` / `_MARKS` tables and the same `_mark_runs` counter (`src/nl_shell/render.py:113-179`). What the parser accepts can't show differently from what it checks.
- **No `unicodedata` at runtime.** `render.py` imports only `bisect`, `collections.abc` and the vendored module (`src/nl_shell/render.py:44-47`), so the policy doesn't change with the Python version.
- **The rejection covers the whole `command`, quoted or not.** It runs on the raw string before any parsing (`src/nl_shell/proposal.py:133-136`). The test covers the quoted case (`tests/test_charsafety.py:155`). That is the attacker-reachable case, not only the friendly path. The test file now has no raw non-ASCII bytes (I grepped and found none), so the previous round's finding about invisible literals is fixed.
- **Generator** (`scripts/gen_unicode_tables.py`) runs at build time only, reads trusted local UCD (Unicode Character Database) files, and writes only formatted integers (`scripts/gen_unicode_tables.py:123-124`). No untrusted input reaches it, and nothing can be injected into the generated module.
- **Resource use.** `has_hidden` / `too_many_marks` are O(n) with a binary search per character, and `COMMAND_MAX` bounds n. No hang or blow-up can be reached.
- **Gates.** C4 red 65/73 without the fix, green with it (`gate-logs/C4-verify.log`). T3 shows 554 passed (`gate-logs/T3-suite.log`).

Leftover risks the patch states itself, so not findings (threat model "Known gaps" and the brief's scope):
- Up to two stacked marks are still allowed. For example, `rm -rf /` + U+0336 U+0336 (combining long stroke overlay) is accepted as `Command` and shown raw, drawn as struck-through text. The cap of 2 is the brief's sign-off decision (UTS #39 §5.4), and the text is still visible, so this is not a hidden-character bypass.
- Blank or near-blank glyphs outside the properties and the named list (for example U+FFFC, which most terminals draw as a box) pass. The threat model says so ("a blank glyph on neither is not caught").
- Look-alike letters and mixed-script words pass. They are listed under Known gaps and moved to #12.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] C1 Spec — Confirm/update #144 to record the authorized removal of mixed-script rejection and the Unicode 16.0 pin — the brief reports its tracker still specifies different acceptance criteria (brief.md:35).
- [x] T5 Judgment — Confirm affected-path prior art across merged history and closed/rejected work — the disposable repository has only one synthetic base commit and GitHub querying failed, leaving the brief's triage account independently unconfirmed; the ASCII-vector defect is resolved (brief.md:32; tests/test_charsafety.py:37).
- [x] Validation — fitness-to-purpose — Accept the policy's intentional limits and usability tradeoff — private-use/unassigned and quoted characters are rejected, while confusables and mixed-script words remain readable-look-alike risks until #12; automated checks cannot decide that product/security fit (.oss-scanner/threat_model.md:133; .oss-scanner/threat_model.md:183).
- [x] **Test (5) can go red on a host whose UCD is not 16.0.0.** It skips only "when `/usr/share/unicode/DerivedCoreProperties.txt` is absent" (brief line 19). The brief assumes the Ubuntu `unicode-data` package is 16.0.0 (Scope (3)). CI runs on `ubuntu-latest` (`.github/workflows/tests.yml:14`, `:30`). Ubuntu 24.04's `unicode-data` is 15.1.0. If that file is present there, regenerating gives a 15.1 module, so the comparison fails instead of skipping. The skip guard should also check the version header (`# DerivedCoreProperties-16.0.0.txt`; this host's copy has that header) and skip with the reason when it differs. Otherwise criterion (5) depends on which host runs it.
- [x] **Criterion (2)'s `:context` expectation has been corrupted.** Brief line 19 says: "prints `e`, two raw U+0301, then the six characters `́`". The backticks hold one literal combining U+0301, not the six-character escape `́`. The issue body has the same corruption ("then `́`", notes.json). As written, a reviewer or Do could read it as "three raw marks", which contradicts Scope (2) ("the 3rd and later marks are escaped"). The criterion should spell out the expected output as `e` + U+0301 + U+0301 + the literal text `́`.
- [x] **The tracker record contradicts the brief, and the decisions that override it are not in the thread.** In `notes.json` (issue #144 body, `comments: []`), mixed-script rejection is still a human decision from Plan ("Decisions confirmed by the human at Plan (2026-10-15): mixed-script words in a proposal are rejected"). It is also still success criterion (3). Two things there conflict with the brief:
- [x] **Scope (4) adds a threat-model change beyond the fix: a new known-gap bullet next to `threat_model.md:170` ("A model can be talked into proposing a bad command").** It covers `ｃurl`/`𝐜url`/`ⅽurl` and mixed-script look-alikes. That records the descoped rule, not this fix. It is small and probably wanted, since it keeps the threat model from implying mixed-script coverage, but it is extra review surface the human should approve on purpose. Its claim that #74's confirm UI "shows non-ASCII characters as escapes" cannot be checked on this base: #74 is not in the target, and `threat_model.md:128` only says the UI escapes *hidden* characters.
- [x] **The mark-cap rule leaves two cases unspecified.** Scope (2) says "at most 2 consecutive characters of category Mn or Me after one base character". It does not say what happens to Mn/Me at the very start of a `command` (no base character), or to marks after a hidden character or after LF. The success criterion only tests `e`+N×U+0301. Do will have to choose, and Check cannot tell a right choice from a wrong one. Either state the rule (e.g. "count any run of Mn/Me, whatever precedes it") or add a test row for it.
- [x] C1 Spec — Record the approved mixed-script descope and Unicode 16.0.0 pin on #144 before sign-off — its reported tracker criteria still conflict with this slice (brief.md:35).
- [x] T5 Judgment — Confirm affected-path prior art across merged and closed/rejected work — the brief records a path history search but only a keyword PR search, and the disposable target contains one synthetic base commit, so closed/rejected path coverage cannot be established from this bundle (brief.md:32).

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
- Plan advisory: 5 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)
- Follow-up (sign-off 2026-10-19): update #144 on the tracker to record the mixed-script descope (moved to #12) and the Unicode 16.0.0 pin; accepted with that record still missing — revisit later.

# Build notes — issue 144 / charsafety-uts39-policy (re-plan build, after v5)

Target: eduralph/nl-shell, built on the wave base `pdca-integration/main-r2546dbf9639f`
(tip `cefb359`, which folds #143). Worktree: `$PDCA_WORKTREE` =
`/home/eddie/nl-shell/nl-shell.pdca-wt-l0`. Base line numbers are on `cefb359`; "new"
line numbers are on the patched tree.

## What changed

1. **`src/nl_shell/render.py`** (whole file re-written; base 1-75): the policy behind
   #143's `is_hidden` / `has_hidden` / `escape_char` / `escape` (base `render.py:34-74`)
   is replaced. The names and signatures stay, so the callers do not change
   (`cli.py:70`, `repl.py:124`, `prompts.py:219`, `proposal.py:131`).
   - `import unicodedata` (base `render.py:21`) is gone. Every property comes from
     `nl_shell._unicode_tables` (new `render.py:47`).
   - One hidden-set table, `_HIDDEN` (new `render.py:113-127`), is the merge of #143's
     ranges (controls minus LF/TAB, bidi, U+2028/2029, tag block, surrogates) with the
     vendored Cf, Co, Cn, Default_Ignorable, White_Space minus space/LF/TAB, and the named
     `BLANK_SYMBOLS` (new `render.py:67-72`). `is_hidden` (new `render.py:131`) is a binary
     search on it. This is still the one predicate, used for both rejection and escaping.
   - Mark cap: `MAX_MARKS = 2` (new `render.py:75`), `is_mark`, `_mark_runs`,
     `too_many_marks` (new `render.py:141-156`). The run counter resets on every non-mark
     character and starts at 0, so a run at the start of the text or after LF is counted
     the same way as a run after a letter. `escape` (new `render.py:168-179`) uses the
     same `_mark_runs` and escapes the 3rd and later marks of a run.
2. **`src/nl_shell/proposal.py`**: mark-cap rejection added right after #143's
   hidden-character rejection (base `proposal.py:131-132`, new `proposal.py:133-136`);
   module docstring updated (base `proposal.py:4-7`, new `proposal.py:4-8`).
3. **`src/nl_shell/_unicode_tables.py`** (new, generated, 1175 lines):
   `UNICODE_VERSION = "16.0.0"` and the range tables CF, CO, CN, MARK (Mn+Me),
   DEFAULT_IGNORABLE, WHITE_SPACE. No script data.
4. **`scripts/gen_unicode_tables.py`** (new): reads `UnicodeData.txt`,
   `DerivedCoreProperties.txt`, `PropList.txt` from `/usr/share/unicode/`. `check_version`
   refuses (exit 1, clear message) unless both versioned files' first lines say the
   expected version (default 16.0.0). Checked by hand: `--expect 15.1.0` on this host
   prints "the UCD in /usr/share/unicode is not Unicode 15.1.0: DerivedCoreProperties.txt
   is 16.0.0, PropList.txt is 16.0.0. Install the 15.1.0 files …" and exits 1.
5. **`.oss-scanner/threat_model.md`**: the "What the user confirms is exactly what runs"
   bullet (base `threat_model.md:127-130`) now names the policy: vendored 16.0.0 tables,
   property set plus the named blank list (and that a blank glyph on neither is not
   caught), mark cap, rejection anywhere quoted or not, stricter than policy-gate v1 §1
   step 1 (`docs/design/specs/policy-gate/v1.md:58-61`) and a superset of it, so the spec
   is unchanged and #12 may relax it. A new known-gap bullet sits right after "A model can
   be talked into proposing a bad command" (base `threat_model.md:170-172`): look-alikes
   in one script / Common (`ｃurl`, `𝐜url`, `ⅽurl`, no NFKC) and mixed-script words
   (`сurl`) are not caught; mixed-script moves to #12; until then the user's reading of
   the confirm prompt is the only check. No claim of #74 as a defence in the new text,
   and no claim of confusable or mixed-script detection. (The pre-existing "(#74)"
   sentence in that bullet is #143's text and was left alone.) The sudo bullets above
   were not touched.
6. **`tests/test_charsafety.py`** (new, 72 tests). Every vector goes through the real
   `Repl` with `RecordingStub` and the real `ubuntu-26.04` prompts, the same set-up as
   `tests/test_backend.py:123-139`. Every non-ASCII character in the source is a Python
   escape, never pasted (the earlier bundle copy pasted raw hidden characters).

## Mapping to the Success criterion

- (1) `test_command_with_a_hidden_character_is_rejected`,
  `test_hidden_character_inside_quotes_is_rejected` (single and double quotes),
  `test_hidden_character_in_a_request_is_escaped_in_context`: all 19 code points, each
  sent both as `\uXXXX` JSON and as raw UTF-8 JSON (`ensure_ascii` True/False).
  Rejection also checks the next request still works (no stuck state).
- (2) after a letter 3 → rejected / 2 → accepted; at start 3 → rejected / 2 → accepted;
  LF + 3 → rejected; `:context` prints `e`, two raw U+0301, then `'\\u0301'`.
- (3) `ls Документы`, `cat αρχείο.txt`, `cat 日本語ファイル.txt`, `echo café`
  precomposed and `e`+one U+0301: accepted and shown byte-identical.
- (4) `test_tables_record_unicode_16`, `test_policy_modules_never_use_unicodedata`
  (static: reads the source of `nl_shell.render`, `nl_shell.proposal`,
  `nl_shell._unicode_tables`), `test_policy_reads_the_vendored_tables_not_unicodedata`
  (fakes U+0378→Lu, U+1C89→Cn, U+0301→Lo, U+3164→Lo, plus `combining` and
  `unidata_version`).
- (5) `test_committed_tables_match_the_generator`: imports the generator by path and
  compares `generate()` with the committed module. Skips, with the reason, when
  `DerivedCoreProperties.txt` is absent or its first line is not
  `# DerivedCoreProperties-16.0.0.txt` (also when PropList/UnicodeData are missing). On
  this host it ran and passed (no skip).
- `tests/test_backend.py` still passes (whole suite 553 passed).

## Runs (project runners only)

- T3, `engine/scripts/run-suite.sh` with `PDCA_WORKTREE` set: **553 passed** (run twice,
  before and after the threat-model edit).
- C4, `engine/scripts/run-verify.sh` with `PDCA_BUNDLE`/`PDCA_WORKTREE` set:
  "**C4 PASS — red without the fix (65 of 72 failed), green with it**"; 0 collection
  errors. The 7 that pass on the reverted tree are the accept rows (two marks after a
  letter, two at the start, the five rows of (3)) — they guard against over-rejection
  and are meant to pass on #143's base too.

## Refute-your-own-test (forced)

- **(a) Genuine red? Yes.** `run-verify.sh` reverted the production hunks
  (`render.py`, `proposal.py`, `_unicode_tables.py`, `gen_unicode_tables.py`), kept
  `tests/test_charsafety.py`, and ran it: 65 of 72 failed, e.g. `ls ͸` came back as
  "Proposed command … | ls ͸" instead of "No usable proposal…", and test (5) failed with
  `FileNotFoundError` for the generator. With the hunks re-applied, all 72 pass.
- **(b) Production path? Yes.** The tests drive `nl_shell.repl.Repl` →
  `nl_shell.proposal.parse` → `nl_shell.render.has_hidden` / `too_many_marks` and the
  `:context` path → `nl_shell.prompts` → `render.escape(…, backslash=True)`, with the
  project's own `RecordingStub` backend. Nothing in the policy is mocked; test (4) fakes
  only the interpreter's `unicodedata`, to prove the policy ignores it. Test (5) runs the
  real generator against the real `/usr/share/unicode/` 16.0.0 files.
- **(c) Fixture includes the fault? Yes.** Each of the 19 code points the brief lists is
  in the stub response itself (unquoted, single-quoted, double-quoted; ASCII-escaped and
  raw JSON), and in the typed request for `:context`. The mark-cap rows put the 3-mark
  run after a letter, at the very start, and after LF. Nothing is curated out.

## Alternatives considered

- **Reuse v5's code as-is** (the brief allows rebuilding along its lines): taken, minus
  everything the re-plan dropped — `WORD_JOINERS`, `WORD_SEPARATORS`,
  `mixed_script_word`, `scripts()`, `AUGMENTED`, `HIGHLY_RESTRICTIVE`, and the
  generator's `script_extensions()` / `SCRIPT_EXTENSIONS` table (and with it the
  `Scripts.txt`, `ScriptExtensions.txt`, `PropertyValueAliases.txt` inputs). Dropping the
  script table also takes the generated module from the v5 size down to 1175 lines.
- **`unicodedata` at runtime instead of vendored tables:** ruled out by the brief
  (Python 3.12/3.13 ship Unicode 15.0/15.1; criterion (4)).
- **UTS #39 Identifier_Status=Allowed** instead of property set + named list: ruled out
  by the round-3 human decision quoted in the brief.
- Small changes against v5: `escape` and `too_many_marks` share one `_mark_runs`
  generator (new `render.py:146-151`) so the display rule and the reject rule cannot
  drift; `_Table` uses `__contains__`; the generator checks only files that carry a
  version header (UnicodeData.txt has none) and its refusal message names each file and
  version found.

## Commit-readiness

The target repo has no pre-commit config, no `core.hooksPath`, no hooks in
`.git/hooks`, and no formatter or linter in `pyproject.toml` or CI
(`.github/workflows/tests.yml` runs only pytest). Checked: no trailing whitespace in
added lines, no unused imports, line lengths within the repo's existing range (its
longest line is 108 chars; the new files stay ≤ 91). `ruff`/`pyflakes` are not
installed here, so no linter was run.

## For the human at sign-off

- The brief's plan-review note (e) still applies: issue #144's body lists mixed-script
  rejection and "pin to Python's `unicodedata`". It needs a comment or body edit
  recording the 2026-10-19 re-plan (mixed-script → #12) and the 16.0.0 pin before
  sign-off, or the sign-off will judge against the old text.
- One stray file outside the roots: while checking that the generator runs, I passed
  `--output /tmp/x`, which wrote a copy of the tables module to `/tmp/x`. It is not part
  of the patch and nothing reads it; leaving cleanup to the harness/human as instructed.
- No external dependency beyond what the brief named (`unicode-data` 16.0.0 is present
  on this host and test (5) ran).

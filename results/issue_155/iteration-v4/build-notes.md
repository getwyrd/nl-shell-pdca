# Build notes — issue 155 (failure-classifier-by-exit-code), re-planned Do

Base: worktree `nl-shell.pdca-wt-l0` at `5d3d291` (folded wave base with #140's
`session.CommandResult`). All line numbers below are on the patched tree.

## What changed

- `src/nl_shell/failure_classes.py` (new, 603 lines).
  - `classify(result, command, lookup=None)` at `:546`. Precedence follows the brief:
    `ran=False` blank/comment → NONE, privileged → PRIVILEGE, else OTHER; then 0 → NONE,
    130 → INTERRUPTED, privileged → PRIVILEGE, 127, 126, 129–192, OTHER.
  - `TypeError` for anything that is not a `session.CommandResult` (`:553-554`).
  - Privilege names `:55` (policy-gate spec §4 list plus variants); bash keyword set `:60`
    sits beside `router.BASH_BUILTINS` (`router.py:27-35`, which I import and do not change).
  - Word splitter `_scan` `:147`: one pass, linear. Quote removal follows bash; `$(`,
    backticks, operators, redirections (with fd number), newlines become tokens; `#` only
    at word start starts a comment. On broken quoting, `_split` `:281` scans again with
    quote characters as plain characters (the router's whitespace-fallback idea from
    `router.py:44-47`, but still splitting operators).
  - Rule 1a + quoted-word re-split + alias following: `_text_is_privileged` `:410`
    (explicit work stack for re-split levels, depth > 8 → privileged), `_alias_is_privileged`
    `:433` (recursion bounded by 8, a done set so each alias value is read once).
  - Rule 1b + functions: `_unclear_command_word` `:332`.
  - Rule 4: `_unresolved_word` `:459`, `_packages` `:488`.
- `tests/test_failure_classes.py` (new, 260 test cases). Started from the archived v3 file;
  rows changed to the re-planned rules (function row moved from "no suggestion" to
  privilege; ESC/bidi/bell 127 words now privilege by 1b; expansion look-alike rows such as
  `${X:-pseudo} x` removed from "not privilege" because 1b now makes them privileged;
  `echo {1..100000}` removed since an argument-position brace word is now other).
- `.oss-scanner/threat_model.md:190-196`: Known-gaps bullet, wording from the brief.

I also copied the new test over `results/issue_155/test_failure_classes.py` (the v3 copy
the brief pointed at as the starting point); the v3 original remains under `iteration-v3/`
if it is needed.

## Why my own scanner instead of `shlex`

The brief says to build the splitter "the same way" as `router.first_token` (shlex posix,
never raises, whitespace fallback). I kept the contract (posix quote removal, never
raises, fallback on broken quoting) but not the `shlex` class, for three concrete reasons:

1. `shlex` treats `#` inside a word as a comment start (`a#b` → `a` and the rest of the
   line dropped). `echo a#b; sudo x` would lose `; sudo x` — a direct miss of the
   invariant. Bash only starts a comment at a word start.
2. With `punctuation_chars`, `shlex` does not split backticks and splits `$(` into `$` and
   `(`; `echo \`sudo x\`` would give the word `` `sudo `` and miss 1a.
3. `shlex` loses whether tokens touch (`sud$(:)o` is one bash word); the 1b rule needs
   that to decide that a substitution sits inside a command word.

The scanner is about 130 lines (`:147-278`), a single forward pass; `find` calls jump the
index forward, so no character is read twice. Rule 4 also uses `_scan` rather than
`router.first_token`, so both rules see the same words.

## Decisions a human should look at

- **Self-referencing alias is not a cycle** (`:434-437`). `alias ls='ls --color=auto'` is
  the Ubuntu default; treating it as a cycle would make every failed `ls`/`grep`
  privileged. Bash never expands an alias inside its own value, and the value is already
  being checked, so skipping the self-reference loses nothing. The brief's 2-cycle
  (`a`→`b`→`a`) is still privileged as required. Pinned by
  `test_alias_naming_itself_is_not_a_cycle`.
- **Extra 1b positions beyond the brief's list**, all in the safe direction: the word after
  an empty `()` (function body, `f() { $X; }`), the word after `function NAME`, options
  after `time` (`time -p $X`), and the word after a `$(…)` that sits inside a leading
  assignment (`X=$(date) $Y`). Without these, `f() { $X; }; f` and `time -p $X` would slip
  past 1b. Rows added to `PRIVILEGED_UNCLEAR`; matching benign rows (`f() { ls; }; f`,
  `time -p ls`, `X=$(date) ls`) added to `NOT_PRIVILEGED`.
- A command word that *begins* with `$(`/backtick, or has one glued inside it, counts as
  unclear (`$(printf s)udo x`, `sud$(:)o x`). The brief's "word after `)` is not a command
  word" still holds for a separate word (`echo $(ls) $X` → other).
- `$'…'` is not decoded (no expander, per the brief); its `$` stays in the word, so at
  command position it is unclear. In argument position (`env $'\x73udo' x`) it is a miss,
  which I read as covered by the Known-gaps "expansion in argument position" wording.
- Lookup output is read for at most 100 items (`_MAX_LOOKUP_ITEMS`) so an endless
  generator cannot hang `classify`; package names shown must be 1–64 printable ASCII
  characters with no space (`_SHOWN_PACKAGE`), which is stricter than `str.isprintable`.
- 127 suggestion is refused when there is any operator or redirection at all, any
  `$(`/backtick in a word's source, or broken quoting — stricter than the brief's list
  (it names list/pipe/substitution/assignment). Safe direction: only loses a suggestion.

## Formatter / hooks

The target has no formatter or linter config (no ruff/black section in `pyproject.toml`,
no `.pre-commit-config.yaml`; `.github/workflows/tests.yml` only runs pytest). I kept the
files under 100 columns, matching `session.py` (max 99). Both new files are pure ASCII.

## Runs (project runners)

- C4 `engine/scripts/run-verify.sh`: green leg 260 passed; red leg 259 of 260 failed (the
  one pass is `test_this_file_writes_every_non_ascii_character_as_an_escape`, by design),
  0 collection errors → `PDCA-EVIDENCE: C4 PASS`.
- T3 `engine/scripts/run-suite.sh`: 912 passed → `PDCA-EVIDENCE: T3 PASS`.

First green run had one failure: the file writer turned my `ｃ`/`‮` escapes into
literal characters; I rewrote them as escapes and the self-check passed.

## Refuting my own test

- **(a) Genuine red?** Yes. `run-verify.sh` reverts `src/` and `.oss-scanner/` from
  `patch.diff` and re-runs the test: 259 of 260 fail as assertion failures
  (`ModuleNotFoundError` inside test bodies, since imports are inside functions) and
  `test_threat_model_names_the_classifier_gap` fails because no Known-gaps bullet names
  `failure_classes` (the existing look-alike bullet already contains `#12`, so the test
  looks for one bullet holding both strings).
- **(b) Production path?** Yes. Every test calls `nl_shell.failure_classes.classify` with a
  real `nl_shell.session.CommandResult` and real `pty_protocol.Snapshot`; no mocks of the
  classifier. The only fakes are the injected package lookup (the brief's contract) and a
  temp `$PATH` directory.
- **(c) Fixture includes the fault?** Yes. The bypass spellings that beat v1–v3
  (`${HOME//*/sud}o x`, `run${#X} x`, brace forms, line continuation, fullwidth, alias
  values, function names) are rows in the tables, the result output is deliberately
  shaped like an attack (`sudo: wrong password`) to prove output is ignored, and the
  bounded-work rows feed the 40 000-brace and 1 200-group inputs directly, timed with
  `time.monotonic()`.

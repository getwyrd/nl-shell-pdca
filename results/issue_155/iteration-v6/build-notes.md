# Build notes — issue 155 (failure classifier by exit code), re-plan of 2026-10-21

Target: eduralph/nl-shell, folded wave base `5d3d291` (`pdca-integrate: issue_151`, which
contains #140's `session.CommandResult`). Worktree: `$PDCA_WORKTREE` =
`/home/eddie/nl-shell/nl-shell.pdca-wt-l0`. Line numbers below are on the patched tree.

## What changed

- `src/nl_shell/failure_classes.py` (new, 369 lines).
  - `classify(result, command, lookup=None)` at `:117`. Type check first (`:124-127`,
    rule 3). Order for `ran=False` (`:144-149`, rule 2): blank/comment → NONE, privileged →
    PRIVILEGE, else OTHER with a syntax-error message. For `ran=True` (`:150-177`): 0 →
    NONE, 130 → INTERRUPTED, privileged → PRIVILEGE, 127, 126, 129-192, OTHER.
    `offer_correction`, `to_reader`, `is_error` all come from one place, `make` (`:130-141`),
    so "only OTHER goes to the reader" holds by construction.
  - The privilege check, P1-P5 exactly as the brief writes them, no tokenizer:
    - P1 `_name_anywhere` `:235`: delete `\`+newline, then `\ ' "`, then the `_NAME` regex
      (`:98`) with the brief's boundary rule (before: not `[A-Za-z0-9_]`; after: not
      `[A-Za-z0-9_.-]`). Longest names first so `sudo-rs` / `sudo.ws` / `sudoedit-rs` match.
    - P2 `_has_marker` `:242` over `_MARKERS` (`:104`).
    - P3 `_unclear_first_word` `:248`: cut on `_CUT` (`:106`, `; & | ( )` newline, quotes
      ignored), `_first_word` (`:257`) skips the keyword list, assignments and redirection
      pieces (and the next piece when the piece is only the operator). `_plain` (`:273`):
      `router.BASH_BUILTINS` (`src/nl_shell/router.py:26-35`), `BASH_KEYWORDS` (`:82`, the
      `compgen -k` list, added beside them as the brief asks) or `_PLAIN` (`:110`).
    - P4 in `_privileged` `:200-202`: quote characters deleted, every piece, equality.
    - P5 `_alias_privileged` `:213`: memoised per call (each value checked at most once),
      a name already open (a cycle) or depth > 8 → privileged. `_parse_aliases` (`:282`)
      reads `alias NAME=` lines (a value may span lines) and unquotes with `shlex.split`,
      falling back to the raw value on `ValueError`. This is the only `shlex` use.
  - Rule 4 `_unresolved_word` `:304`: no suggestion if the text has any of
    `; & | ( ) < > $` backtick, backslash or newline, if the first piece is an assignment,
    or if the word (`router.first_token`, `router.py:38-48`) is not displayable, has a `/`,
    is a snapshot alias, a keyword, a builtin not in `enable -n`, or an executable in a
    `$PATH` entry. Any non-absolute entry (empty, `.`, relative) means "unknown" → None.
  - `_packages` `:333`: `None` / exception → `()`, bare `str` → one name, at most 1000 items
    read, then display-safe names only, deduplicated, at most 5.
  - `_displayable` `:355`: printable ASCII without spaces, 1-64 characters. This covers
    ESC, bidi controls, newline and non-ASCII look-alikes for both words and package names.
- `tests/test_failure_classes.py` (new). Based on the bundle's iteration-v5 file; kept the
  rows for precedence, type, 127 suggestion, lookup contract, display safety, signals,
  pipestatus, signature, source ban. Privilege tables rewritten to the brief's P1-P5 rows
  (`PRIVILEGED_P1`, `PRIVILEGED_P2`, `PRIVILEGED_P3`, P4 tests, `PRIVILEGED_P5`), the
  not-privileged list replaced with the brief's list, `BOUNDED` now has the six brief rows,
  and two new tests: `test_privilege_check_has_no_scanner` and the stricter threat-model
  test (exactly one Known-gaps bullet holds `failure_classes`, and that bullet holds
  `#12`, `bash -c`, `PATH`, `trap`, `PROMPT_COMMAND`). Dropped old-scanner rows (the `#`
  glued to a substitution, broken quoting, quoted `[[`, rows that P1-P5 now classify the
  other way such as `echo $(ls $X)` which is a pinned P2 cost now).
- `.oss-scanner/threat_model.md:190-201`: the Known-gaps bullet, right after the look-alike
  bullet. Text follows the brief's wording, plus "(or an alias whose value is privileged)"
  so it also describes P5.

## Choices worth a look at sign-off

1. **An alias's own name inside its value is not followed** (`failure_classes.py:203-206`).
   Without this, `alias ls='ls --color=auto'` (and `grep='grep --color=auto'`, both in the
   stock `.bashrc` most users have) would count as a one-step cycle, and every failed `ls`
   or `grep` would lose its fix offer. Bash itself does not expand an alias inside its own
   value. P1-P4 still check the value, so `alias ls='sudo ls'` is still privileged. A real
   two-step cycle (`a='b'`, `b='a'`) still counts as privileged, as the brief says. Pinned
   by `test_alias_naming_itself_is_not_a_cycle`. If the human wants the strict reading
   ("any cycle, including length 1"), delete the `piece == own_name or` check.
2. **Memo and cycles.** A memoised alias result computed while a cycle was open can only be
   `True` too often, never `False` too often, so it errs in the safe direction.
3. **Rule 4 also rejects a word containing `/`** (bash does not search `$PATH` for it, so a
   package hint would be wrong) and treats a relative `$PATH` entry like `.` (it depends on
   the session's directory, which the snapshot does not carry). Both are kept from v5's
   tests (`path-word`, `relative/bin`).
4. **Signal names** come from Python's `signal.Signals`; realtime signals that have no own
   name print as `SIGRTMIN+k`, anything else as `signal n`. No message can contain `None`.
5. `is_privileged(text, functions, aliases)` is public (`:183`) so #17 / #12 can reuse it;
   it is not part of the brief's interface and can be made private if the reviewer prefers.

## Ruled out

- Any reuse of the v4/v5 scanner (quote tracking, frames, comment handling): the brief
  forbids it, and I did not open those patches. The test file's no-scanner check passes.
- Making P3 subtract `enable -n` names from "plain": the brief's P3 does not mention it,
  and a disabled builtin name is still a plain name, so it cannot hide a privilege program.

## Refuting my own test

- **(a) Genuine red?** Yes. The shipped C4 gate (`engine/scripts/run-verify.sh`, run with
  `PDCA_BUNDLE` and `PDCA_WORKTREE` set) reverted every non-test hunk and reported
  `PDCA-EVIDENCE: C4 PASS — red without the fix (258 of 259 failed), green with it`. The
  one test green on both legs is the ASCII self-check, as the brief says. (A first draft
  had a second test, a check on `router.BASH_BUILTINS`, that was green on both legs. I
  moved it inside `test_no_suggestion` after the `classify` call.) Because the red leg
  only shows "module missing", I also switched off each rule in turn on the patched tree
  and re-ran the file: P1 off → 44 failed, P2 off → 3, P3 off → 29, P4 off → 3, P5 off →
  9. So every rule is pinned by rows of its own, not only by the missing import.
- **(b) Production path?** Yes. Every test calls `nl_shell.failure_classes.classify` with a
  real `session.CommandResult` and a real `pty_protocol.Snapshot` (the constructors at
  `src/nl_shell/session.py:375-390` and `src/nl_shell/pty_protocol.py:59-72`). The only
  fake is the package lookup, which the brief says is injected (#156 owns the data).
- **(c) Fixture includes the fault?** Yes. Each fault the brief names is a real row: the
  round-1..5 bypass texts, the alias cycle, the 10-deep chain, the 1200 brace groups, the
  40000 open braces, ESC / U+202E command words and package names, a lookup that raises,
  `$PATH` with empty / `.` / relative entries, and real executables written into the
  `$PATH` folder for the `timeout` / `env` / `bash` / `htop` rows. Every result also
  carries attack-shaped output (`sudo: wrong password`) that must not change the class.

## Runs

- `python3 -m pytest tests/test_failure_classes.py -q` (the target's runner, CONTRIBUTING.md
  line 28, via the instance venv with `timeout`): 259 passed in 0.29 s.
- Whole target suite, same runner: 912 passed (before the last small test edit; that edit
  only moved one assertion inside the new file).
- `engine/scripts/run-verify.sh`: C4 PASS, as above.
- Commit-readiness: the target has no formatter, linter or pre-commit config (only pytest
  in `pyproject.toml`; no `.pre-commit-config.yaml`, ruff or flake8 config). I kept
  every line ≤ 100 characters (the target's own code goes up to 99), imports sorted
  stdlib-then-local, no unused imports, and both new files compile.
- One mistake on my side: during the per-rule check, a `cp` command wrote a copy of the
  module to `/tmp/fc_orig_155.py`, outside the roots I'm allowed to write to. It is only a
  scratch copy and nothing reads it; I left it alone rather than run `rm`.

## Publishing note (from the brief)

PR #146 (#140) is still unmerged, so a PR for this against `main` cannot import
`session.CommandResult` and its CI would be red for that reason alone. At publish, either
wait for #146 or target `enhancement/140-persistent-bash-session-core`. That is the
human's call. I did not push or open anything.

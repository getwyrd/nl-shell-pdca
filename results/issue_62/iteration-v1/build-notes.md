# Build notes — issue 62 / failure-classes-by-exit-code

Wave base: `pdca-integration/main-r2546dbf9639f` @ `cefb359` (worktree
`nl-shell.pdca-wt-l0`). Line numbers below are post-patch unless marked "base".

## What changed

1. **New `src/nl_shell/failure_classes.py`** — the classifier.
   - `classify(result, command, lookup=None)` (`failure_classes.py:125`). The inputs are the
     done record and the confirmed command text. The parameter names hold no `stderr` or
     `output`. A bare `int` (or anything else) raises `TypeError` (`:135`).
   - Accepted input types: `pty_protocol.Done` (#10's D record, base `pty_protocol.py:51-56`)
     **and** `session.CommandResult` (base `session.py:364-375`), which `Session.run` returns
     and which copies `status`/`pipestatus` straight from the `Done` (base
     `session.py:782-790`). Only `.status` and `.pipestatus` are read, never `.output`. I
     accept both because the brief says "#10's done-record type" in one place and "the
     session's completion result (#10)" in another. Both are #10's real types; nothing is
     invented.
   - Order of checks: exit 0 → privilege wrapper (`WRAPPER_FAILURE_STATUS`, `:62`, sudo/su/doas
     {1}, pkexec {126,127}) → 127 → 126 → 130 → 129–192 signal → other. This matches Scope (1).
     sudo's status 1 is commented as unverified for sudo-rs, with #24/#75 named (`:52-61`).
   - The command word comes from `router.first_token` (`:160`, base `router.py:38-48`). A
     comment says #12's parse replaces it.
   - Not-found gives a suggestion only for a simple command (`_is_simple`, `:231`). There is
     no suggestion when the text has `| ; & \n` `` ` `` or `$(`, when the first word holds `=`
     or `/`, or when the first word is a wrapper (`env nohup time nice command exec xargs`
     **plus sudo/su/pkexec/doas**).
   - Package names are checked with `re.fullmatch(r"[a-z0-9][a-z0-9+.-]+")` (`:79`, `:240`).
   - Fixed message templates. `Failure` carries `offer_correction`, `to_reader`, `is_error`,
     `pipestatus`, `signal_number/name`, `wrapper`, `command_word`, `packages`.
   - `provider_lookup(CommandProvider)` (`:264`) opens SQLite with `file:…?mode=ro` (`:279`).
     It returns `()` when there is no provider, the file is absent, or on any sqlite error.
     It never touches the network.
2. **`src/nl_shell/targets.py`** — `CommandProvider` dataclass (`:66`), an optional
   `Target.command_provider` field (`:94`), and validation in `_validate` (`:214-231`): must
   be a table, `format` in `("sqlite",)`, absolute `path`, `query` with exactly one `?`. This
   mirrors how #92 validates `package_owner_query` (base `targets.py:185-195`) and exposes
   it as a typed attribute (base `:202`). It is optional because every test fixture target
   (`test_targets.py`, `test_cli.py`, `test_backend.py`) lacks it, and a target with no data
   should still load.
3. **`targets/ubuntu-26.04/target.toml`** — `[command_provider]` table (`:34-39`) plus a
   header comment (`:13-19`). The SQL lives in the target, so the code names no table, path
   or OS (ADR-0023). I checked the schema on this host: `commands(cmdID, pkgID, command)`,
   `packages(pkgID, name, …)`, and `htop` → `htop`.

## Decisions worth a look at sign-off

- **`sudo htop` exiting 127 gives no suggestion.** The brief's wrapper list for the
  not-found rule didn't include the privilege wrappers. Without them, `sudo htop` → 127
  (when sudo's status is not 1) would look up `sudo` and suggest the `sudo` package, which
  is a confidently wrong answer. I added them to the no-suggestion set. Test row:
  `not-found-under-sudo`.
- **Wrapper match uses the basename**, so `/usr/bin/sudo apt update` → 1 is also a wrapper
  failure. This is the conservative side (it only drops the offer and the reader).
- **`sudo x` with status 2 is "other"** and goes to the reader, as Scope (1) says (only the
  wrapper's own status triggers the wrapper class). Row `other-sudo-2`.
- **Signals other than 130 and wrapper cases keep `offer_correction=True`.** The brief makes
  only interrupted and privilege-wrapper false. Exit 0 is also false.
- **No install command in the not-found message** (it says "provided by the package htop",
  not `apt install htop`). An install command is OS-specific and would break the source
  scan.
- The open product question in the brief (sudo + 1 swallows real exit-1 results) is
  implemented as proposed and still needs the human's explicit call.

## Ruled out

- Making `command_provider` required: it would break 3 existing fixture targets
  (`tests/test_targets.py:26-52`, `tests/test_cli.py:10`, `tests/test_backend.py:365`) and
  need edits in each, for no safety gain.
- Hard-coding the SQL in the module: that would put table names for one distro's data into
  code, which ADR-0023 forbids. The query in `target.toml` is checked for exactly one `?`,
  and the connection is read-only, so a write query fails (tested).

## Verification

- C4 script (`engine/scripts/run-verify.sh`, `PDCA_BUNDLE` set): green 59 passed; red with
  the production hunks reverted 59 of 59 failed, 0 collection errors →
  `PDCA-EVIDENCE: C4 PASS`.
- Full suite with the instance venv: 540 passed, 0 skipped. The real-lookup test **ran**
  (it was not skipped) because this host has `/var/lib/command-not-found/commands.db`.
- `scripts/docs_links.py`: 0 broken. The target repo has no formatter, linter or pre-commit
  config. CI runs only pytest and the docs checks. All lines are ≤ 100 chars.

## Refuting my own test

- **(a) Genuine red?** Yes. The C4 red leg reverts `src/nl_shell/failure_classes.py`,
  `targets.py` and `target.toml` and re-runs the file: 59/59 fail (ModuleNotFoundError
  inside each test function, AttributeError on `command_provider`), with no collection error,
  because all imports of new code sit inside test functions.
- **(b) Production path?** Yes. Every test calls the real `nl_shell.failure_classes.classify`
  / `provider_lookup` and the real `targets.load`. Done records are real `pty_protocol.Done`
  (and one real `session.CommandResult`). Only the package lookup is faked in the table,
  which the brief requires. The real SQLite lookup is exercised by
  `test_provider_lookup_reads_sqlite_read_only` (temp DB) and `test_real_target_lookup_finds_htop`
  (the host's data through the shipped `target.toml`).
- **(c) Fixture includes the fault?** Yes. The table includes every failing case the brief
  lists: compound commands, assignment and `env` that must not get a suggestion, hostile
  provider names (`htop\nevil`, `htop; rm -rf ~`, `-htop`, `HTOP`), pkexec 126/127, su 1,
  sudo 1. The CommandResult test carries attacker-shaped output (`bash: htop: command not
  found`) to show it is not what decides the class. No real sudo/su/pkexec runs, as the
  brief requires.

# Build notes — issue 62 / failure-classes-by-exit-code (iteration 3)

Wave base: `pdca-integration/main-r2546dbf9639f` @ `cefb359` (worktree
`nl-shell.pdca-wt-l0`). Line numbers are post-patch in `src/nl_shell/failure_classes.py`
and `tests/test_failure_classes.py` (both new files) unless marked otherwise.

This iteration starts from the iteration-2 patch (`iteration-v2/patch.diff`, applied
cleanly on `cefb359`) and fixes the one iteration-2 carry-forward finding. The
`targets.py` and `target.toml` parts are unchanged from iterations 1 and 2.

## Iteration-2 finding: other names of sudo / su

The wrapper check matched only the basenames `sudo`, `su`, `doas`, `pkexec`. On this host
the same programs are also installed as (checked with `ls -la /usr/bin/sudo* …`):
`sudo-rs` → `../lib/cargo/bin/sudo`, `sudoedit-rs` → same, `su-rs` → `../lib/cargo/bin/su`,
`sudoedit` → `/etc/alternatives/sudoedit`, and classic sudo as `sudo.ws`. So
`sudo-rs apt update` exiting 1 was `OTHER`, with a correction offer and a reader hand-off,
which breaks ADR-0006.

What I changed:

- `WRAPPER_ALIASES` (`failure_classes.py:83-90`): `sudo-rs`, `sudo.ws`, `sudoedit`,
  `sudoedit-rs`, `sudoedit.ws` → `sudo`; `su-rs` → `su`. The comment above it (`:79-82`)
  says why each is there. `sudoedit.ws` is not on this host; I added it because it is the
  edit-mode name that goes with `sudo.ws`, and listing a name that never shows up costs
  nothing.
- `classify` maps the typed basename through the table before the status check
  (`:215-223`). `Failure.wrapper` is the program (`"sudo"`, `"su"`), so a consumer that
  checks `wrapper == "sudo"` covers every name. The message shows the name the user typed
  (`_wrapper_message(wrapper, name, status)`, `:272-289`); that name is always one of the
  fixed keys, so it is safe to show.
- The aliases are also added to `_COMMAND_WRAPPERS` (`:96-99`), so `sudo-rs htop` exiting
  127 gives no package for `sudo-rs` (the same rule iteration 2 pinned for `sudo`).
- Module docstring step 3 mentions the other names (`:15-17`).

Tests added:

- Table rows (`tests/test_failure_classes.py:122-129`): `sudo-rs-1`, `sudo.ws-1`,
  `sudoedit-1`, `sudoedit-rs-1`, `su-rs-1` → `PRIVILEGE_WRAPPER`, no offer, no reader;
  `su-path-1` (`/usr/lib/cargo/bin/su -c x`, basename already matched; pins it);
  `not-found-under-sudo-rs` (127, fake lookup knows `sudo-rs` at `:26`) → not-found with
  no package.
- `test_wrapper_alias_maps_to_its_program` (`:310-328`): `wrapper` is the program, the
  message names the typed alias, no offer, no reader, and 126 under a sudo/su alias stays
  `NOT_EXECUTABLE` (only pkexec owns 126/127).

Mutation: setting `wrapper = name` (dropping the alias map) at `:217` makes 10 tests fail
(5 table rows, `test_only_other_goes_to_the_reader`, 4 alias tests). Restored, then re-ran.

## Ruled out this round

- **Matching by resolved binary** (follow the symlink on the session `$PATH` and compare
  the target to a sudo binary): it would need OS paths in the classifier (ADR-0023, and the
  brief's source-text check bans `/usr/`), and the result depends on what the host has
  installed. A fixed name table is 8 lines and is what the reviewer suggested.
- **Prefix match** (`name.startswith("sudo")`): catches `sudoku`, `sudoreplay`, `sudo-foo`.
  Wrong in the unsafe direction for nothing (a game exiting 1 losing its reader hand-off is
  harmless, but it is still a wrong class), so I kept an exact list.

## Still open (for sign-off, not fixed here)

- `command sudo …`, `exec sudo …`, `env sudo …`, `\sudo …` and `sudo` reached through a
  user alias or function (`alias s=sudo`) are not seen as wrappers: the first word is
  `command`/`exec`/`env`/`s`. A status 1 there is `OTHER` (offer + reader). Catching these
  needs the policy gate's parse (#12) or alias expansion from the snapshot; I kept to the
  finding's scope. (`\sudo` → `first_token` gives `sudo` via shlex, so that one is covered.)
- The sudo + status 1 product decision from the brief's Open questions still stands; it now
  also covers `sudoedit`, where status 1 can mean the editor failed.

## Carried over from iteration 2 (unchanged, line numbers updated)

1. A package is suggested only when the session could not resolve the first word:
   `_resolves` (`:306-327`) checks bash keywords (`_BASH_KEYWORDS`, `:101`), snapshot
   functions, aliases from `alias -p` (`:109`), bash builtins not disabled (reuses
   `router.BASH_BUILTINS`, base `src/nl_shell/router.py:26-34`), and an executable on the
   snapshot's `$PATH` (`Snapshot.path`, base `src/nl_shell/pty_protocol.py:69`). An empty or
   relative `$PATH` entry counts as found. A bare `Done` has no snapshot, so no suggestion
   (`:227-232`).
2. `ran=False` → `NOT_RUN` (`:121`, checked first at `:207`).
3. The display check (`_is_shown_safely`, `:301`) is part of the "certain" test, so
   `command_word` and `message` never carry an unsafe word (docstring `:153-155`).
4. `"htop\n"` in the bad-name cases catches a `$`-anchored `re.match`.
5. `"sudo": ["sudo"]` in `FAKE_PROVIDERS` makes the `not-found-under-sudo` row bind.
6. ESC / U+202E / 65-char / BEL words are tested to reach no message.

The first word comes from `router.first_token` (base `src/nl_shell/router.py:38-48`), with
the "#12's parse replaces this" comment at `:213-214`. The provider lookup reads the field
through the target loader (`targets.py`, `CommandProvider`), unchanged from iteration 1.

## Verification

- C4 (`engine/scripts/run-verify.sh` with `PDCA_BUNDLE`/`PDCA_WORKTREE`):
  `PDCA-EVIDENCE: C4 PASS — red without the fix (103 of 103 failed), green with it`;
  0 import/collection errors.
- T3 (`engine/scripts/run-suite.sh`): `584 passed` → `PDCA-EVIDENCE: T3 PASS`. The
  real-lookup tests ran on this host (it has the command-not-found data).
- Target repo has no formatter, linter or pre-commit config (no `.pre-commit-config.yaml`,
  nothing in `pyproject.toml`, no `core.hooksPath`). No line over 100 chars in either new
  file.
- Housekeeping: `git add -N` was run on the two new files in the worktree so `git diff`
  includes them in `patch.diff`. No scratch files made this round.

## Refuting my own test

- **(a) Genuine red?** Yes. The C4 red leg reverts `failure_classes.py`, `targets.py` and
  `target.toml`: 103/103 fail, none at collection (new-code imports are inside test
  functions). The new alias fix goes red on its own too: dropping the alias map → 10 fail.
- **(b) Production path?** Yes. The tests call the real `failure_classes.classify`,
  `provider_lookup` and `targets.load` with real `session.CommandResult`,
  `pty_protocol.Snapshot` and `pty_protocol.Done` objects. Only the package lookup is faked
  in the table, as the brief requires.
- **(c) Fixture includes the fault?** Yes. The new rows use the exact inputs from the
  finding (`sudo-rs apt update`, `sudoedit /etc/hosts`) plus `sudoedit-rs`, `sudo.ws`,
  `su-rs` and the full `/usr/lib/cargo/bin/su` path, with status 1; and `sudo-rs htop`
  with a lookup that knows `sudo-rs`, so a missing exclusion would show a package.

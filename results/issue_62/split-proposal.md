<!-- pdca:split-proposal v1 -->
# Split proposal — issue 62

<!-- Each child is a COMPLETE brief, not a sketch. A filled Slug alone makes `state.state`
     classify the materialised file as PLANNED, so `pdca flow` skips Plan and sends it
     straight to Do — a child missing `Repo + branch target` then builds successfully and
     has nowhere to publish. Fill every field. -->

<!-- Delimiters are HTML comments, not headings, DELIBERATELY: each child body is a full
     draft brief and may contain arbitrary headings and fenced code blocks, so anything
     that could also appear inside a child cannot be its boundary. `pdca split --accept`
     parses these markers; keep them exactly as written. -->

## Why this slice is oversized

Three rounds (iteration-v1 to v3) built one bundle that did two separate jobs, and the
sign-off on 2026-10-15 named the seam itself. The two jobs share one interface (a function
that takes a command word and returns package names) and nothing else:

1. **The classifier.** It turns a trusted `session.CommandResult` plus the confirmed command
   text into a failure class with fixed message, `offer_correction` and `to_reader` flags.
   Nearly all the repeated findings were here (the privileged-command rule, `ran=False`,
   the 127 "did the first word resolve" rule). Those are now settled by the four Plan
   decisions in the parent brief. The classifier takes the package lookup as an injected
   callable, so it can be fully tested with a fake and needs no target data, no SQLite and
   no `targets.py` change.
2. **The ubuntu-26.04 command-not-found provider.** A `[command_provider]` table in
   `targets/ubuntu-26.04/target.toml`, validation in the target loader (`targets.py`, from
   #92, already merged), a read-only SQLite reader, the Debian package-name check, and the
   threat-model "Trusted" entry for `/var/lib/command-not-found/commands.db`. It is useful
   and testable without the classifier: given a word, it returns checked package names.

Each half has its own defect, its own test file and its own PR. They touch different
files. Two children is the smallest split that separates them; splitting the classifier
further (for example "privilege rule" vs "the rest") would give children that can't be
tested alone, because the precedence order ties the classes together.

Connecting the two (building the provider's callable from the active target and passing it
to `classify`) is left out of both. It belongs with the first caller, #17 or the REPL
wiring, which the parent brief already puts out of scope.

## Wave sketch

**One wave, both children in parallel.** Neither needs the other's result, and they edit
no file in common, so there is no `Depends on` or `Conflicts with` between them.

- child-1 (classifier) edits `src/nl_shell/failure_classes.py` (new) and
  `tests/test_failure_classes.py` (new).
- child-2 (provider) edits `src/nl_shell/command_provider.py` (new), `src/nl_shell/targets.py`,
  `targets/ubuntu-26.04/target.toml`, `.oss-scanner/threat_model.md` and
  `tests/test_command_provider.py` (new).

The interface between them is a plain `Callable[[str], Iterable[str]]`. child-2 does not
import child-1's type, and child-1 does not import anything from child-2, so either can
merge first.

**One ordering the fields cannot carry: child-1 needs #140.** child-1 needs
`session.CommandResult`, which comes from #140 (PR #146: COMPLETE but not merged). The
ordering fields only accept sibling labels (`split._validate_ordering` rejects any
reference that is not `child-N`), so I could not write `Depends on: 140` in child-1's
block. **After `split --accept`, add `- **Depends on:** 140` to child-1's materialised
brief by hand.** Without it, `compute_waves` may build child-1 on plain main, where
`session.CommandResult` does not exist. child-2 builds on main as it is; #92's loader is
merged (PR #142).

<!-- pdca:child child-1 -->
# Brief — failure-classifier-by-exit-code (child-1 of #62)

> Child of #62 (M0.12), split at Plan on 2026-10-19. The four decisions the human
> confirmed at Plan for #62 bind this child and are restated below. Builds on ADR-0014
> Decision 2 (exit codes are trusted only from the control channel's done record),
> ADR-0015 / ADR-0006 (never offer anything that touches the sudo password), ADR-0017
> (only the reader sees raw untrusted text).

- **Slug:** failure-classifier-by-exit-code
- **Defect / goal:** nl-shell has no deterministic first pass that classifies a failed command from trusted facts only (the `session.CommandResult` from the done record and the command text the user confirmed) before anything goes to a model. Add `src/nl_shell/failure_classes.py` with `classify(result, command, lookup=None)` returning a `Failure` with the class, a fixed message (no model), `offer_correction` and `to_reader`. Classes: none, interrupted (130), privilege, not-found (127, with an optional package suggestion from an injected lookup), not-executable (126), killed by signal n (129–192 except 130, named, with the OOM-killer hint for 137), other.
- **Success criterion:** `python3 -m pytest tests/test_failure_classes.py` passes on the wave base, with a table-driven test covering, each as its own row or assertion:
  - precedence: `ran=False` → see decision 2; status 0 → none; 130 → interrupted (no correction offer, no message presented as an error, no reader) and this wins even for privileged commands; privileged + any other non-zero status → privilege; then 127, 126, 129–192, other.
  - **privilege (decision 1):** one fixed neutral message, `offer_correction=False`, `to_reader=False`, for each of: `sudo apt update` (1), `sudo frobnicate` (127, no package suggestion), `pkexec x` (126 and 127), `su -c x` (1), `doas x` (1), `run0 x` (1), `machinectl shell x` (1), `sudo-rs x`, `sudoedit /etc/hosts`, `sudoedit-rs f`, `/usr/bin/sudo x` (basename), `time sudo x`, `FOO=1 sudo x`, `env sudo x`, `nohup sudo x`, `cd d && sudo x`, `true; sudo x`, `a || sudo x`, `x & sudo y`, `echo pw | sudo -S x`, `echo $(sudo x)`, `` echo `sudo x` ``, and a command `s x` where the snapshot has `alias s='sudo'`. A non-privileged lookalike (`echo sudo-ish`, `pseudo x`) is not privilege.
  - **nothing ran (decision 2):** `ran=False` with `""`, `"   "`, `"# a note"` → none (even when the stale status is 127 or 1); `ran=False` with `"if then"` → other (`offer_correction=True`, `to_reader=True`).
  - **type (decision 3):** a bare `pty_protocol.Done` raises `TypeError`; so does an `int`.
  - **127 suggestion (decision 4):** `htop` with a fake lookup that knows `htop` → not-found, suggests `htop`, no reader. No suggestion (still not-found, no reader) for: an unknown word; `cat f | htop`, `make && htop`, `true; htop`, `FOO=1 htop`, `echo $(htop)`; a first word that is a snapshot function, a snapshot alias, a bash builtin or keyword (`timeout` is NOT a builtin, so use `cd`/`if`), or an executable file in a `snapshot.path` directory the test controls (covers `timeout 5 x`, `env x`, `bash -c x`); no lookup passed.
  - display safety: a not-found word with an ESC byte, a U+202E bidi override, or 65 characters never reaches `message`; a 64-character word does; a package name that is not printable or is over 64 characters is not shown; at most 5 packages are shown. No message ever renders the text `None`.
  - 126 → not-executable ("permission or noexec"); 137 → `SIGKILL` + OOM hint; 143 → `SIGTERM`; 1, 2, 100, 128, 255 for an ordinary command → other, and ONLY other has `to_reader=True`.
  - status is the last pipeline status (`$?`) and `pipestatus` stays available on the result.
  - `inspect.signature(classify)` has no parameter whose name contains `stderr` or `output`; the module source (read from `__file__`) contains none of `/var/`, `/usr/`, `commands.db`, `ubuntu`, `sqlite3`, `targets` (the lookup is injected; child-2 owns the data).
- **Falsifiability:** RED on the shipped C4 gate (`engine/scripts/run-verify.sh`). With the production change reverted `nl_shell.failure_classes` does not exist, so every test's in-function import fails as an assertion failure, not a collection error (tests ran, failures > 0). No test runs a real `sudo`, `su`, `pkexec`, `doas`, `run0` or `machinectl`; results are built directly.
- **Repo + branch target:** eduralph/nl-shell @ main (built on the folded wave base that includes #140's accepted patch, so `session.CommandResult` exists; use its fields as they landed, do not invent stand-ins).
- **Ordering note:** Needs #140 (`session.CommandResult`, PR #146, COMPLETE, not merged). That is an external dependency the split's ordering fields cannot name; the human adds `Depends on: 140` to this brief after `split --accept`. Independent of child-2: the lookup is injected.
- **Reproduction:** n/a (new functionality).
- **Surfaces:** data
- **Scope (one logical fix) / out of scope:** `src/nl_shell/failure_classes.py` (new) and `tests/test_failure_classes.py` (new; the archived `results/issue_62/test_failure_classes.py` from iteration-v3 is a starting point, minus its real-lookup and package-name-rule tests, which move to child-2). Rules, as confirmed by the human at Plan on 2026-10-19:
  1. **Privileged.** ANY shell word anywhere in the confirmed text (after `|`, `&&`, `||`, `;`, `&`, inside `$(…)` or backticks, behind `env`/`time`/`nohup`/assignments) or any word in the value of a snapshot alias whose name appears as a word, has a basename in `sudo su pkexec doas run0 machinectl` (policy-gate spec §4, `docs/design/specs/policy-gate/v1.md:111`) or `sudo-rs sudo.ws sudoedit sudoedit-rs`. Privileged + non-zero status other than 130 → privilege: one fixed neutral message (it must not claim "wrong password" or "not authorized", and must not suggest re-running anything), no correction offer, not to the reader. Accepted cost: #17 never offers a fix for a failed privileged command. Over-matching is the safe direction.
  2. **`ran=False`.** Blank or comment-only text → none. Otherwise → a syntax error, handled as other.
  3. **Input type.** Only `session.CommandResult`; anything else raises `TypeError`.
  4. **127 suggestion.** Only for one simple command (no list, pipe, substitution, leading assignment) whose first word did not resolve: not a snapshot function or alias, not a bash builtin or keyword (minus `snapshot.disabled_builtins`), not an executable file in any `snapshot.path` directory (an empty or `.` entry means "unknown": no suggestion).

  Tokenize the way the router does (`router.first_token`, `src/nl_shell/router.py:38-48`: `shlex` in posix mode, never raises, whitespace fallback on bad quoting). `first_token` only yields the first word, so rule 1 needs a whole-text word splitter built the same way that also splits shell operators off words (`a&&sudo x`, `a||sudo x`, `x;sudo y`, `$(sudo x)`, `` `sudo x` `` must each yield `sudo` as a word); rule 4 may use `first_token` itself. A comment says #12's parse replaces both. Add rows `cd d&&sudo x` and `true;sudo x` (no spaces) to the privilege table. The command word comes from the confirmed text, never from stderr. Lookup contract: `Callable[[str], Iterable[str]]`; the classifier trusts the provider to have checked names (child-2 does) and only applies display safety. / out of scope: the real package data, SQLite, `target.toml`, `targets.py` (child-2); connecting the provider to `classify` (the first caller: #17 or REPL wiring); offering or running corrections (#17); `?why` (#14); calling the reader (#61); the policy gate's parse (#12); real sudo behaviour (#24, #75); message localisation (ADR-0022).
- **External dependencies:** none
- **Test file:** `tests/test_failure_classes.py` (new). Module level: only the standard library and pytest. Import `nl_shell.failure_classes`, `nl_shell.session` and `nl_shell.pty_protocol` inside the test functions, so a reverted tree is red rather than UNVERIFIABLE. Nothing in this file may skip.
- **Difficulty:** medium
- **Citations expected:** path:line on the wave base for every change. Mirror `router.first_token` (`src/nl_shell/router.py:38-48`); take status, pipestatus, `ran` and the snapshot from `session.CommandResult` as #140's own tests do. Normative: ADR-0014 Decision 2; ADR-0015 Decisions 1–4; `bash(1)` EXIT STATUS (126, 127, 128+n); policy-gate spec §4 (`docs/design/specs/policy-gate/v1.md:111`); pty-protocol §4.1 (`docs/design/specs/pty-protocol/v1.md:370-372`, `D` without `S` means nothing ran).
- **Disposition hint:** new-feature

## STOP discipline

Draft only until Check sign-off. The PR MUST NOT be marked ready before sign-off accepts.
<!-- pdca:end child-1 -->

<!-- pdca:child child-2 -->
# Brief — ubuntu-command-not-found-provider (child-2 of #62)

> Child of #62 (M0.12), split at Plan on 2026-10-19. Builds on ADR-0023 (OS-specific
> lookups come from the target, code names no OS), ADR-0003 (local only, no network),
> and #92's target loader (merged, PR #142).

- **Slug:** ubuntu-command-not-found-provider
- **Defect / goal:** nl-shell has no way to ask the active target which package provides a command, which the "command not found" class of #62 needs for its suggestion. Add an optional `[command_provider]` table to `target.toml` (`format`, `path`, `query`), validate it in the target loader, fill it for `targets/ubuntu-26.04` (the read-only SQLite file `/var/lib/command-not-found/commands.db`, tables `commands(command, pkgID)` and `packages(pkgID, name)`), and add `src/nl_shell/command_provider.py` with `provider_lookup(provider) -> Callable[[str], tuple[str, ...]]`. The returned function opens the file read-only, never fetches, returns `()` when the data is absent or unreadable, and keeps only names that pass the Debian package-name rule.
- **Success criterion:** `python3 -m pytest tests/test_command_provider.py` passes on main, covering, each as its own assertion:
  - loader: a `target.toml` with a valid `[command_provider]` loads and exposes it on `Target.command_provider`; a target without the table loads with `command_provider is None`; each of these raises `TargetError`: unknown `format`, relative `path`, `query` with zero or two `?`, a missing key, a non-string value.
  - the shipped `targets/ubuntu-26.04/target.toml` loads and its provider is `format = "sqlite"`, `path = "/var/lib/command-not-found/commands.db"`.
  - reader, against a SQLite file the test builds in `tmp_path` with the same two tables: `htop` → `("htop",)`; a word with two packages → both, sorted; an unknown word → `()`; a missing file → `()` and the file is NOT created; a file that is not SQLite, or a schema without the tables → `()`; the database file's bytes are unchanged after lookups (opened with `mode=ro`); a word containing `'`, `;` or `%` is passed as a bound parameter and returns `()` (no SQL built by string formatting); `provider_lookup(None)` returns a function that always gives `()`.
  - name rule, whole-string (`re.fullmatch(r"[a-z0-9][a-z0-9+.-]+", name)`): `HTOP`, `htop; rm -rf ~`, `htop\nevil`, `htop\n` (the case a `$` anchor would wrongly accept), `-htop`, and a non-string value from the database are each dropped; `libc6`, `g++`, `python3.12` are kept.
  - `src/nl_shell/command_provider.py`'s source text contains none of `ubuntu`, `/var/`, `commands.db` (the path and query come from `target.toml`).
  - supplementary: the real `targets/ubuntu-26.04` lookup returns a tuple containing `htop` for `htop` when `/var/lib/command-not-found/commands.db` exists on the host; skipped otherwise. This is the only test that may skip.
- **Falsifiability:** RED on the shipped C4 gate (`engine/scripts/run-verify.sh`). With the production change reverted `nl_shell.command_provider` does not exist and `Target` has no `command_provider`, so each test's in-function import or assertion fails (tests ran, failures > 0). The binding rows use a SQLite file the test builds, so they don't depend on the host's package data.
- **Repo + branch target:** eduralph/nl-shell @ main
- **Ordering note:** No open dependency: #92 (the target loader) is merged (PR #142). Independent of child-1: it neither imports nor is imported by the classifier; the shared interface is a plain `Callable[[str], Iterable[str]]`.
- **Reproduction:** n/a (new functionality).
- **Surfaces:** data
- **Scope (one logical fix) / out of scope:** `src/nl_shell/targets.py` (a frozen `CommandProvider` dataclass, an optional `Target.command_provider`, validation in `_validate` next to the `package_owner_query` check, `COMMAND_PROVIDER_FORMATS = ("sqlite",)`); `targets/ubuntu-26.04/target.toml` (the `[command_provider]` table plus a header comment describing it, in the style of the existing `[sudo]` comment); `src/nl_shell/command_provider.py` (new: read-only SQLite via a `file:…?mode=ro` URI with `uri=True` and a short timeout, bound `?` parameter, `sqlite3.Error`/`OSError`/`ValueError` give `()`, name filter as above); `.oss-scanner/threat_model.md` (a "Trusted" entry for `/var/lib/command-not-found/commands.db`: root-owned, package-managed, read-only, not attacker-writable; names are still filtered because they end up in user-facing text); `tests/test_command_provider.py` (new). The iteration-v3 patch (`results/issue_62/iteration-v3/patch.diff`, the `targets.py` and `target.toml` hunks and `provider_lookup`) is prior art. / out of scope: the classifier and its message, count cap or display safety (child-1); connecting the provider to `classify` (the first caller: #17 or REPL wiring); any network fetch or running `/usr/lib/command-not-found` (its output is localised prose); providers for other targets or other formats; architecture doc 05.
- **External dependencies:** none for the binding criterion. The supplementary real-lookup test reads the host's command-not-found data and is skipped when it is absent.
- **Test file:** `tests/test_command_provider.py` (new). Module level: only the standard library and pytest. Import `nl_shell.command_provider` and `nl_shell.targets` inside the test functions, so a reverted tree is red rather than UNVERIFIABLE.
- **Difficulty:** low
- **Citations expected:** path:line on main for every change. Mirror how `targets.py` validates and exposes `package_owner_query` (cite it). Normative: ADR-0023; ADR-0003; Debian Policy §5.6.1 (package names: lowercase letters, digits, `+`, `-`, `.`, at least two characters, starting with an alphanumeric); `sqlite3` URI `mode=ro`.
- **Disposition hint:** new-feature

## STOP discipline

Draft only until Check sign-off. The PR MUST NOT be marked ready before sign-off accepts.
<!-- pdca:end child-2 -->

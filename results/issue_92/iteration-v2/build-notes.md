# Build notes — issue 92 / os-target-folder-and-selection (iteration 2)

## Iteration 2 — what changed against the carry-forward

I started from the previous attempt's patch (`iteration-v1/patch.diff`, applied cleanly to
the wave base `8c95e05`) and fixed the four build-level findings. The rest of the design
is unchanged and is described below the iteration section.

1. **os-release read errors** (`src/nl_shell/os_release.py:65-93`, `cli.py:36`).
   `read()` now moves to the next path only on `FileNotFoundError` (`:80`), as
   os-release(5) asks. Any other `OSError` (EACCES, EISDIR, …) and `UnicodeDecodeError`
   (`:87`) raise the new `OsReleaseError` (`:65`), whose message names the file and the
   problem and says nl-shell can't tell which OS this is. `cli.main` catches it with the
   other refusals (`cli.py:36`) → message on stderr, exit 1, REPL never starts. No more
   traceback, and no silent fall-back past an unreadable `/etc/os-release`.
   Tests: `test_os_release_not_utf8_is_refused` (`tests/test_targets.py:193`, the exact
   bytes from the finding), `test_os_release_that_exists_but_cant_be_read_does_not_fall_back`
   (`:201`, a directory at the first path — EISDIR, works even as root; the second path
   holds a matching file, so a fall-back would start the REPL), and
   `test_os_release_permission_denied_does_not_fall_back` (`:213`, mode 000, skipped as
   root). All three drive the real `cli.main([])` through `refused_by_os_release` (`:173`).
2. **`hostname` resolver flags** (`targets/ubuntu-26.04/allowlist.toml:299-306`). Now only
   `-s`, `--short`, `-I`, `--all-ip-addresses`. I checked on this host (hostname 3.25)
   with `strace -e trace=socket,connect`: `hostname -s` opens no socket; `hostname -I`
   opens only an `AF_NETLINK` socket (a local kernel query, no network). `-f -d -A -a -i
   -y` and the long forms are gone, with a comment saying why. Test:
   `test_real_allowlist_hostname_allows_no_resolver_lookup` (`:542`).
3. **GPU tools take no operands** (`allowlist.toml:397-409`). `nvidia-smi`, `rocminfo`,
   `vulkaninfo` get `max_operands = 0`, with a comment naming the `nvidia-smi`
   subcommands. Test: `test_real_allowlist_gpu_tools_take_no_operands` (`:547`).
4. **`less +cmd`** (`allowlist.toml:341-347`). I did **not** decide the security
   question: the deferred finding (leave `less` off v1, or have #12 treat `+` words as
   options, or force `LESSSECURE=1`) is the human's call, and criterion (g) still requires
   `less` in the word set. What I did is what the carry-forward asked for: a comment on
   the `[commands.less]` entry telling #12 that a `+` word is a start-up command
   (`!cmd`, `|cmd`, `v`), that the gate MUST treat it as an unlisted option (so
   `mutating`), that the same holds for `more`, and that keeping `less` on v1 depends on
   that. Test `test_real_allowlist_pins_plus_words_for_less_and_more` (`:554`) pins: no
   `+` word is allowed for `less`/`more`, and the comment block just above
   `[commands.less]` mentions `` `+` ``, `` `mutating` `` and `#12`. If the human picks
   "leave `less` off", this test and (g)'s word set both change together.

Red/green for just these fixes: I put the v1 `os_release.py`, `allowlist.toml` and the v1
`except` line in `cli.py` back (with the new tests in place) and ran the suite through
`engine/scripts/run-suite.sh`: `6 failed, 218 passed` — exactly the six new tests. The
not-UTF-8 test failed with the reported `UnicodeDecodeError`; the two no-fall-back tests
failed because the REPL started (fall-back happened); the three allowlist tests failed on
the `hostname` flags, `nvidia-smi` operands and the missing `less` comment. Then I put the
fix back. (I used a temporary local commit for this and undid it; the worktree is back on
`8c95e05` with the change uncommitted.)


Target: eduralph/nl-shell, built in `$PDCA_WORKTREE` on the wave base `8c95e05`
("pdca-integrate: issue_14", main + #14's `:status`). All `path:line` below are on the
patched tree unless marked "base".

## What changed

| File | Change |
|---|---|
| `targets/ubuntu-26.04/target.toml` (new) | ADR-0023 fields: `id`, `display_name`, `shell = "bash"`, `package_owner_query = ["dpkg", "-S"]` (argv words, not a shell string), `[match] ID/VERSION_ID`, `[sudo] implementation = "sudo-rs"`, `version = "0.2.13"` (ADR-0015 line 29). |
| `targets/ubuntu-26.04/allowlist.toml` (new) | `spec = "policy-gate/v1"` + one `[commands.<word>]` table per word, keys limited to the §6.2 five. Top comment cites §6.2, explains fail-closed and names the two omitted words (`command`, `ip`) and why (lines 1–29). 71 entries. Iteration 2: `hostname` narrowed (`:299-306`), GPU tools `max_operands = 0` (`:397-409`), `less`/`more` `+`-word comment for #12 (`:341-347`). |
| `src/nl_shell/os_release.py` (new) | `PATHS = (/etc/os-release, /usr/lib/os-release)` (`:15`), `parse()` with os-release(5) quoting (`:20`, `_unquote` `:40`), `read()` = first file that exists, `{}` if none; a file that exists but can't be read or decoded raises `OsReleaseError` (`:65-93`). |
| `src/nl_shell/config.py` (new) | `$XDG_CONFIG_HOME/nl-shell/config.toml` (default `~/.config/nl-shell/`), missing file = no settings, bad TOML or a non-string `target` → `ConfigError` naming the file, unknown keys ignored (`:39`). Separate unit as the brief asks (#77 extends it). |
| `src/nl_shell/targets.py` (new) | Loader + selection. `ROOT` = repo `targets/` next to `src/` (`:27`). `load()` validates `target.toml` (`:128`): missing file, bad TOML, each required field, `id` ≠ folder, shell ≠ `bash`, each with the file path in the message. `load_allowlist()` only parses (`:194`). `select()` (`:222`): named target → load, record match/mismatch; else candidate `targets/<ID>-<VERSION_ID>` whose `[match]` must also equal os-release; else refuse with detected OS, available targets, and how to name one. No `ID_LIKE`, no near version. `Selection.reason` = `"target does not match this OS"` (`:32`, `:87`) for #12. |
| `src/nl_shell/cli.py` | `--target ID` (`:17-22`); selection before `Repl.interactive()` (`:28-42`, catches `ConfigError`, `OsReleaseError`, `TargetError` at `:36`); refusal → message on stderr, exit 1; mismatch → warning on stderr, REPL starts. Base `cli.py:12-18` was the wiring point. |
| `src/nl_shell/repl.py` | `Repl(read, out, selection=None)` and `Repl.interactive(selection=None)` (`:45-60`); `:status` appends `selection.status_lines()` after #14's block (`:89-97`). Base: `_reply` was a staticmethod at `repl.py:66-77`. |
| `src/nl_shell/input_modes.py` | Comment only (`:78-80`): #92's lines are not appended to the module-wide `STATUS_LINES` (see below). |
| `tests/test_cli.py` | `test_main_runs_the_interactive_repl` now points `os_release.PATHS` at a fake matching file and its fake `interactive` accepts `selection` (base `tests/test_cli.py:13-19`). |
| `tests/test_targets.py` (new) | The named test; also copied into the bundle dir. |

`:status` output on a mismatch (pinned in the tests):

```
nl-shell 0.0.0
target: ubuntu-26.04 (Ubuntu 26.04 LTS)
target os: does not match this OS (detected: debian 13)
```

Refusal text (no match, e.g. Debian with `ID_LIKE=ubuntu`):

```
nl-shell: no target matches this OS (detected: debian 26.04). Available targets: ubuntu-26.04. nl-shell does not fall back to a similar OS or version. To use a target anyway, name it with --target <id> or set target = "<id>" in /home/u/.config/nl-shell/config.toml; every command will then need a confirm.
```

## Design decisions and what I ruled out

1. **`:status` lines come from the `Repl`, not from `input_modes.STATUS_LINES`.** #14's
   comment invited #92 to append a zero-argument callable to that module-wide list. The
   active target is per session (chosen in `cli.main`), so a callable there would have to
   read a module global set by `cli.main`. The cost: one more global (`ACTIVE = None` in
   `targets.py`, about 6 lines incl. a "no target" branch) plus every test that builds a
   `Repl` or calls `cli.main` having to reset it, otherwise one test's target leaks into the
   next `:status` (pytest runs them in one process). Holding the selection on the `Repl`
   instance costs 9 lines in `repl.py:89-97` and has no shared state. I updated #14's
   comment so it no longer promises #92 appends there.
2. **Injection through module attributes, not keyword arguments on `main`.** First draft
   had `main(argv, *, os_release_paths=None, targets_root=None)`. That moved the tagline
   off `cli.py:14`, and criterion (h) allows the OS name only on that exact line. So
   `main`'s signature is unchanged and the CLI reads `os_release.PATHS` and `targets.ROOT`
   at call time (`cli.py:25-34`); tests `monkeypatch.setattr` them. To keep the tagline on
   line 14 I also joined `prog=` and `description=` onto one line (`cli.py:13-15`). The
   tagline text is unchanged.
3. **os-release parser written by hand, not `shlex`.** My first version used
   `shlex.split`; my own test caught that it leaves `\$` escaped inside double quotes,
   while os-release(5) says `$ " \ \`` are backslash-escaped there. `_unquote`
   (`os_release.py:40-62`) follows the man page and rejects a value that isn't one quoted
   or one safe unquoted word.
4. **`package_owner_query` is a list of argv words** (`["dpkg", "-S"]`), so #12 can run it
   without a shell and append the path. The brief only said "package-owner query
   (`dpkg -S`)".
5. **Target ids are checked against `[a-z0-9][a-z0-9._-]*`** before building a path
   (`targets.py:35`, `:130`), so `--target ../x` is refused as "not a valid target id" and
   can't reach outside `targets/`. Tested in `test_named_target_without_folder_is_refused`.
6. **A malformed `config.toml` is refused even when `--target` is given.** The brief says
   "a malformed config.toml is refused"; it doesn't make that depend on the flag. A
   well-formed config whose `target` has no folder is ignored when the flag is given
   (flag wins, and only the winning name is loaded).
7. **Missing os-release** (both files absent) gives `{}`; detection shows
   `unknown unknown` and start-up is refused unless a target is named. An os-release that
   exists but can't be read or isn't UTF-8 is refused outright, even with `--target`
   (iteration 2): with a target named we could start in mismatch mode, but the brief says
   to read os-release, and reporting "detected: unknown" for a file that is there would
   hide the real problem. Cost of the other choice: about 4 lines in `cli.py` to catch the
   error and pass `{}` when a target is named.
8. Default arguments `root: Path = ROOT` in `targets.load/available/select` bind at
   definition time; that is fine because the CLI always passes `root=targets.ROOT`
   explicitly, and the defaults serve #12's direct use of the real folder.

## Allowlist translation — for the human reviewer (every entry is SUMMARY §6 material)

Fail-closed per brief Scope (2). Decisions beyond the §6.4 table text:

- **Omitted** (brief decision): `command`, `ip`, with the file comment at
  `allowlist.toml:20-26`.
- `date`: `max_operands = 0`, so `date +FORMAT` costs a confirm (brief decision). No
  `-s/--set`, no `-f`.
- `tr`: §6.4 groups it with "max one file operand", but `tr` takes SETs, not files. The
  criterion requires `max_operands ≤ 1`, so `tr -d SET` passes and `tr SET1 SET2` costs a
  confirm (`allowlist.toml` `[commands.tr]` comment).
- `printf`: no flags at all — `-v VAR` assigns a shell variable (session change). Table
  says "any".
- `history`: no flags (`-c -d -a -n -r -w -s` all change history or its file);
  `max_operands = 1` (`history N`).
- `dirs`: no `-c` (clears the stack). `env`: no `-i -u -C -S`. `hostname`: no `-F`, `-b`.
- `tree`: no `-o FILE`, no `-R`/`-H` (HTML mode writes files). `file`: no `-C` (compiles
  magic, writes a file), no `-z` (may run decompressors). `sort`: no `-T` either.
  `ss`: no `-K` (kills sockets), `-D` (dumps to a file), `-N`. `lspci`: no `-H`.
  `apt`/`apt-cache`: no `-o`/`-c` (APT options can set `Pre-Invoke` hooks). `jq`: no
  `-f`/`-L`, no `--arg`/`--argjson` (two values each; §6.2 `options` take one).
- `journalctl`: exactly the §6.4 list. `-b` is a flag only; `-b -1` costs a confirm
  (§6.2 can't express an optional value).
- `grep` family: no `-f` (pattern file). `egrep`/`fgrep` have no `-E`/`-F`.
- `rocminfo`: no options. `nvidia-smi`: `-L -q`; `vulkaninfo`: `--summary`. All three
  `max_operands = 0` (iteration 2).
- `hostname`: only `-s`/`--short`, `-I`/`--all-ip-addresses` (iteration 2; the rest
  resolve names).
- `less`/`more`: `+` words are start-up commands; see the entry comment and the
  deferred finding. Human decision.
- `stdin = true` on the readers named "stdin" in §6.4 plus `less`/`more` (they read the
  terminal with no file; §2's keyboard-sink rule uses this).
- `ps` BSD-style words (`ps aux`) are operands; I set no `max_operands` on `ps`. Whether
  the gate treats them as operands is #12's call.

## Refute-your-own-test (forced)

- **(a) Genuine red? Yes.** Ran the shipped C4 gate
  (`engine/scripts/run-verify.sh`, `PDCA_BUNDLE=results/issue_92`), which reverts every
  non-`tests/` hunk (loader modules, `cli.py`, `repl.py`, `input_modes.py`, `targets/`) and
  re-runs `tests/test_targets.py` + `tests/test_cli.py`:
  iteration 2: red leg "ran 43, failed 40, setup errors 6, import/collection errors 0" →
  `PDCA-EVIDENCE: C4 PASS — red without the fix (40 of 43 failed), green with it`
  (run with `PDCA_VERIFY_BASE=8c95e05…`). The six new iteration-2 tests also go red
  against the *previous attempt's* code (see the iteration section above). The three tests green on the red leg are by design: (h) is green-only (the brief
  says it already holds on main), `test_repl_without_a_target_has_no_target_lines`, and
  `test_version_flag`. Module-level imports are only stdlib, pytest, `nl_shell.cli` and
  `nl_shell.repl.Repl`, so the red leg has no import error.
- **(b) Production path? Yes.** Cases (a)–(f) call the real `cli.main(argv)` → real
  `config.load` → real `os_release.read`/`parse` → real `targets.select`/`load`, and the
  REPL is the real `Repl` class (only its `read` function and output stream are scripted,
  as in `tests/test_repl.py`). `:status` goes through the real `Repl._reply` →
  `input_modes.reply` path. Only the two file locations are redirected
  (`os_release.PATHS`, `targets.ROOT`), which the brief asks to be injectable. Case (g)
  loads the real `targets/ubuntu-26.04/` through the production `targets.load` /
  `load_allowlist`, and `test_real_target_is_selected_at_start_up` runs `cli.main([])`
  against the real `targets.ROOT`.
- **(c) Fixture includes the fault? Yes.** The no-match cases include the exact traps the
  ADR forbids: a fake targets dir that *contains* `ubuntu-26.04` while os-release says
  `VERSION_ID="26.10"` (near version) or `ID=debian` + `ID_LIKE=ubuntu` (`ID_LIKE`
  fallback) — a fallback implementation would pick it and fail the test. The mismatch case
  names a real target on a Debian 13 os-release. The broken-`target.toml` cases each break
  one thing in an otherwise valid file, via both `--target` and auto-selection. A folder
  named `ubuntu-26.04` whose `[match]` says 26.10 is also refused.

Iteration 2 fixtures include the fault too: the not-UTF-8 file is the exact bytes from
the finding; the no-fall-back fixtures put a *matching* os-release at the second path, so
a fall-back would start the REPL and fail the test.

Whole suite via the project's runner (`engine/scripts/run-suite.sh`): `224 passed`,
`PDCA-EVIDENCE: T3 PASS`.

## Commit-readiness

The target repo has no formatter or commit hook configured: no `.pre-commit-config.yaml`,
no ruff/black section in `pyproject.toml`; `.github/workflows/docs-checks.yml` only checks
Markdown, and this patch touches no Markdown. I wrapped lines to match the existing ~90
column style (the longest new line is 92; the base already has lines up to 108 characters, and nothing enforces a limit). `git diff --check` is clean. Patch adds
files with `git add -N`, so `patch.diff` includes the new files.

## Not verified here

- I did not start the interactive REPL on a real Ubuntu 26.04 machine. Manual check at
  sign-off (`nl-shell-pdca try 92`): on 26.04, `:status` should show
  `target os: matches this OS`; on another OS, `nl-shell` should refuse and
  `nl-shell --target ubuntu-26.04` should warn and start.
- Every allowlist entry needs human review (brief Impact; INTEGRATION §4). The options I
  chose for "flags" rows are from my knowledge of GNU coreutils/util-linux/procps/iproute2
  behaviour, not checked against the 26.04 man pages (uutils may differ). Fail-closed
  means a missing one only costs a confirm; an extra one is what review should look for.

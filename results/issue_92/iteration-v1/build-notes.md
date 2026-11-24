# Build notes — issue 92 / os-target-folder-and-selection

Target: eduralph/nl-shell, built in `$PDCA_WORKTREE` on the wave base `8c95e05`
("pdca-integrate: issue_14", main + #14's `:status`). All `path:line` below are on the
patched tree unless marked "base".

## What changed

| File | Change |
|---|---|
| `targets/ubuntu-26.04/target.toml` (new) | ADR-0023 fields: `id`, `display_name`, `shell = "bash"`, `package_owner_query = ["dpkg", "-S"]` (argv words, not a shell string), `[match] ID/VERSION_ID`, `[sudo] implementation = "sudo-rs"`, `version = "0.2.13"` (ADR-0015 line 29). |
| `targets/ubuntu-26.04/allowlist.toml` (new) | `spec = "policy-gate/v1"` + one `[commands.<word>]` table per word, keys limited to the §6.2 five. Top comment cites §6.2, explains fail-closed and names the two omitted words (`command`, `ip`) and why (lines 1–29). 71 entries. |
| `src/nl_shell/os_release.py` (new) | `PATHS = (/etc/os-release, /usr/lib/os-release)` (`:15`), `parse()` with os-release(5) quoting (`:20`, `_unquote` `:40`), `read()` = first existing file, `{}` if none (`:65`). |
| `src/nl_shell/config.py` (new) | `$XDG_CONFIG_HOME/nl-shell/config.toml` (default `~/.config/nl-shell/`), missing file = no settings, bad TOML or a non-string `target` → `ConfigError` naming the file, unknown keys ignored (`:39`). Separate unit as the brief asks (#77 extends it). |
| `src/nl_shell/targets.py` (new) | Loader + selection. `ROOT` = repo `targets/` next to `src/` (`:27`). `load()` validates `target.toml` (`:128`): missing file, bad TOML, each required field, `id` ≠ folder, shell ≠ `bash`, each with the file path in the message. `load_allowlist()` only parses (`:194`). `select()` (`:222`): named target → load, record match/mismatch; else candidate `targets/<ID>-<VERSION_ID>` whose `[match]` must also equal os-release; else refuse with detected OS, available targets, and how to name one. No `ID_LIKE`, no near version. `Selection.reason` = `"target does not match this OS"` (`:32`, `:87`) for #12. |
| `src/nl_shell/cli.py` | `--target ID` (`:17-22`); selection before `Repl.interactive()` (`:28-42`); refusal → message on stderr, exit 1; mismatch → warning on stderr, REPL starts. Base `cli.py:12-18` was the wiring point. |
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
7. **Unreadable/missing os-release** (both files absent) gives `{}`; detection shows
   `unknown unknown` and start-up is refused unless a target is named.
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
- `rocminfo` has an empty entry (no options). `nvidia-smi`: `-L -q`; `vulkaninfo`:
  `--summary`.
- `stdin = true` on the readers named "stdin" in §6.4 plus `less`/`more` (they read the
  terminal with no file; §2's keyboard-sink rule uses this).
- `ps` BSD-style words (`ps aux`) are operands; I set no `max_operands` on `ps`. Whether
  the gate treats them as operands is #12's call.

## Refute-your-own-test (forced)

- **(a) Genuine red? Yes.** Ran the shipped C4 gate
  (`engine/scripts/run-verify.sh`, `PDCA_BUNDLE=results/issue_92`), which reverts every
  non-`tests/` hunk (loader modules, `cli.py`, `repl.py`, `input_modes.py`, `targets/`) and
  re-runs `tests/test_targets.py` + `tests/test_cli.py`:
  green leg "ran 43, failed 0"; red leg "ran 40, failed 37, setup errors 3, import/collection
  errors 0" → `PDCA-EVIDENCE: C4 PASS — red without the fix (37 of 40 failed), green with
  it`. The three tests green on the red leg are by design: (h) is green-only (the brief
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

Whole suite via the project's runner (`engine/scripts/run-suite.sh`): `218 passed`,
`PDCA-EVIDENCE: T3 PASS`.

## Commit-readiness

The target repo has no formatter or commit hook configured: no `.pre-commit-config.yaml`,
no ruff/black section in `pyproject.toml`; `.github/workflows/docs-checks.yml` only checks
Markdown, and this patch touches no Markdown. I wrapped lines to match the existing ~90
column style (the longest new line is 92; base `repl.py:86` is already 91). Patch adds
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

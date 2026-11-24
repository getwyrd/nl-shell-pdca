# Adversarial review — issue 92 / os-target-folder-and-selection (round 3)

I could not re-run the red→green proof here: the sandbox's `python3` (3.14) has no
pytest. I judged C4 and T3 from the frozen logs instead, and ran the production modules
directly with `python3 -I` against hand-made edge cases. My verdict on the evidence rests
on the logs; that is a missing tool, not a sign the fix is wrong.

## What I tried and could not break

- **The red→green evidence holds up.** `gate-logs/C4-verify.log`: red leg 41 of 44 failed,
  green leg 50 of 50 passed. The red failures are `ImportError`s on `nl_shell.targets` /
  `nl_shell.os_release` raised inside the test functions and fixtures, so the run is red, not
  "unverifiable". The three tests that pass on `main` are the old `--version` test,
  `test_no_os_name_in_code` (`tests/test_targets.py:582`, green-only by the brief's design)
  and `test_repl_without_a_target_has_no_target_lines` (`tests/test_targets.py:596`, meant
  to pass on `main`). None of them pass for the wrong reason. The tests run the real path:
  `start()` (`tests/test_targets.py:96-118`) calls the real `cli.main`, and swaps only
  `os_release.PATHS`, `targets.ROOT` and the `Repl` read function. It builds a real `Repl`
  with the real `Selection`, so the `:status` text comes from production
  `src/nl_shell/repl.py:89-98`.
- **Exact match, no fallback** (`src/nl_shell/targets.py:315-347`). Refused as expected:
  a duplicate `VERSION_ID` (last one wins, giving 26.10), `ID = ubuntu` with spaces around
  `=`, a `export ID=…` line, `VERSION_ID=""`, and `debian` + `ID_LIKE=ubuntu`. CRLF line
  endings and single-quoted values still match. A folder named like the OS whose
  `target.toml` disagrees is refused (`targets.py:335-338`, test at `:252`).
- **Path tricks on the target name.** `target = "../../etc"` in config and
  `"ubuntu-26.04\n"` are both refused by `_ID.fullmatch` (`targets.py:128`, `:223`) before
  any path is built.
- **Round-1 os-release findings are fixed.** A directory or a mode-000 file in place of
  os-release now raises `OsReleaseError` instead of silently falling back
  (`src/nl_shell/os_release.py:80-91`). Non-UTF-8 content is refused with a message, and
  `cli.py` catches all three error types (`src/nl_shell/cli.py:28-38`). The EISDIR test
  (`tests/test_targets.py:201`) still covers this when running as root, where the chmod
  test is skipped.
- **The warning text matches the spec.** "Every command will need a confirm" in
  `targets.py:191-195` is what spec §7.7 promises (`docs/design/specs/policy-gate/v1.md:197-198`).
  It describes #12's future behaviour, not something this diff does.
- **Allowlist entries.** For each entry I looked for a listed option that writes a file,
  runs a program, opens a network connection or changes state. I found none: `uniq` and
  `xxd` have output-file operands but are capped by `max_operands = 1`; `history` has no
  flags (`-c`, `-w` are not listed); `printf` has none (`-v` is not listed); `ss` lacks
  `-K` and `-D`; `tree` lacks `-o` and `-R`; `less` lacks `-o`; `systemctl` lacks `-H`/`-M`.
  The round-2 fixes for `hostname` and the GPU tools are in place
  (`targets/ubuntu-26.04/allowlist.toml`, `[commands.hostname]` and `[commands.nvidia-smi]`).

## Findings

- NEEDS-HUMAN [human] — `targets/ubuntu-26.04/allowlist.toml:336-339`: this comment lists
  the environment variables §7.5 does not check (`MANOPT`, `LESS`) and leaves the gap to
  the human, but it misses `LESSOPEN` / `LESSCLOSE`. Those are the more direct
  "runs another program" route for the `less` entry. Ubuntu's default `~/.bashrc` sets
  `LESSOPEN="| /usr/bin/lesspipe %s"`, so on this target `less FILE` runs a helper program
  on every file it opens. A changed `LESSOPEN` would run whatever it names, with no flag on
  the command line for the allowlist to catch. This belongs with the deferred decision on
  environment variables and §7.5. I tagged it [human] because what counts as "covered" is
  the human's call; adding the two names to the comment is a one-line change once that is
  decided.
- `src/nl_shell/config.py:376-379`: `config_dir()` uses `XDG_CONFIG_HOME` even when it is
  a relative path. The XDG Base Directory spec says relative values are invalid and must
  be ignored. A concrete case: `XDG_CONFIG_HOME=cfg nl-shell`, run in a directory that holds
  `cfg/nl-shell/config.toml`, takes `target =` from that directory. The impact is low: the
  file can only name a target, and a mismatched one only makes the gate stricter. I'm
  noting it, not routing it back.
- `src/nl_shell/targets.py:120`: `ROOT = parents[2] / "targets"` only works from a source
  checkout or an editable install. After a normal `pip install .`, `targets/` is not
  shipped, so nl-shell refuses to start on every OS, including Ubuntu 26.04. Before this
  patch, that install started. The brief puts packaging out of scope (#48/#50), and
  CONTRIBUTING documents only `pip install -e`, so this is not a defect in the patch. The
  human should still know that the non-editable install now fails at sign-off.

## Verdict on the reviewer's claims

I found no unwarranted claim in `check-gates.json` about the code. The T2 row ("no
security-relevant path touched", `gate-logs/T2-threat-model.log`) is still misleading for
a patch that adds the read-only allowlist. As in rounds 1 and 2, it does not replace the
human review of each entry that spec §Versioning requires
(`docs/design/specs/policy-gate/v1.md:204-206`). That item is already deferred to the
human, so I'm not filing it again.

I tried to break selection, os-release parsing, config handling, the `:status` wiring and
the allowlist entries. I found no concrete input that defeats the fix.
<!-- pdca:leaf-complete -->

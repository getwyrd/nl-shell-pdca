## Summary
**User impact:** nl-shell starts on any operating system without checking which one it is on. It has no idea which supported release applies, and you can't tell it. So the per-OS rules that decide what is safe to run (which release ships which tools, which sudo, which package manager) have nothing to attach to.

This PR makes nl-shell check the OS at start-up. It picks the supported target that exactly matches the OS. If there is none, it refuses with a clear message unless you name a target yourself with `--target` or in `config.toml`. `:status` shows which target is active and whether it matches this OS.

Reported in [#92](https://github.com/eduralph/nl-shell/issues/92). This is a **narrowed slice** of #92 and does not close it: the allowlist moves to #139, and the "degraded" behaviour for a mismatched target is delivered by the policy gate in #12. This PR records the mismatch state for #12 to read.

## What to look at
- **How the target is chosen.** It is an exact match on the OS name and version, or the target you name. There is never a "close enough" match: Ubuntu 26.10, or Debian that says it is "like Ubuntu", does **not** pick the Ubuntu 26.04 target.
- **Behaviour change for contributors:** on a machine that is not Ubuntu 26.04, `python3 -m nl_shell` now refuses to start. Use `python3 -m nl_shell --target ubuntu-26.04` to run anyway. It starts with a warning, and `:status` says the target does not match. The test suite fakes the OS, so CI on `ubuntu-latest` is unaffected.
- **Changed extension point for `:status` (affects #16 and #77).** `:status` lines used to be a shared module-level list that later issues appended to. That list is gone. Each session now carries its own lines, so one session's target can't leak into another. A later issue adds its line by adding a callable to the tuple `nl_shell.cli.main` builds, after the target lines. Please plan #16 and #77 against this, not against the old "append to `STATUS_LINES`" comment.
- **Known limit, not fixed here:** after a non-editable `pip install .`, nl-shell refuses to start because `targets/` is not packaged yet (#48, #50). CI and CONTRIBUTING use `pip install -e`, which works.

To try it:
```
python3 -m nl_shell                         # on Ubuntu 26.04: starts; elsewhere: refused with a message
python3 -m nl_shell --target ubuntu-26.04   # elsewhere: starts with a warning
nl> :status
```

## Root cause
Nothing loaded an OS target or read `/etc/os-release`. `main` had only `targets/ubuntu-26.04/sensitive.toml`, and `cli.main` parsed `--version` and went straight to the REPL. The product tagline also named the OS in code, which ADR-0023 forbids ("Code MUST NOT name an OS outside a target folder", `docs/design/adr/0023-os-targets.md:52`).

## Fix
- `targets/ubuntu-26.04/target.toml` (new): the ADR-0023 fields. These are id, display name, exact os-release match (`ID = "ubuntu"`, `VERSION_ID = "26.04"`), shell `bash`, package-owner query `["dpkg", "-S"]` and sudo `sudo-rs` `0.2.13` (ADR-0015). The key names are documented at the top of the file. No `allowlist.toml`; that is #139.
- `src/nl_shell/os_release.py` (new): reads `/etc/os-release` and falls back to `/usr/lib/os-release` **only** when the first does not exist. Any other read or decode error is an error, not a fallback. Shell-style quoting is parsed as os-release(5) describes.
- `src/nl_shell/config.py` (new, kept apart from the loader so #77 can extend it): reads `target` from `$XDG_CONFIG_HOME/nl-shell/config.toml`. An empty or relative `XDG_CONFIG_HOME` is ignored in favour of `~/.config`. Bad TOML or a non-string `target` is refused with the file named. Unknown keys are ignored.
- `src/nl_shell/targets.py` (new): `load()` checks that the id is a plain folder name **before** building any path. It then requires the folder to stay inside the targets root and validates `target.toml`: required fields, `id` equals the folder name, shell is `bash`. `select()` returns a `Selection` (target, `matches`, detected `ID` / `VERSION_ID` or `unknown`, and `reason`), which #12 will read. Without a named target, the only candidate is the folder `<ID>-<VERSION_ID>`, and its own match fields must agree.
- `src/nl_shell/cli.py`: adds `--target ID` (the flag wins over config). Refusals print a short `nl-shell: …` message to stderr and exit 1 before the REPL starts. A mismatch prints a start-up warning. When os-release exists but can't be read, a named target starts in the mismatch state, and an unnamed one is refused.
- `src/nl_shell/input_modes.py`, `src/nl_shell/repl.py`: `:status` lines are per session (see "What to look at"). The comment that described the old extension point is rewritten to describe the new one.
- Tagline reworded in `src/nl_shell/__init__.py`, `cli.py` and `pyproject.toml` to "Natural-language shell: a small local model proposes commands, bash runs them".

## Verification
- **Claim:** an exact os-release match selects the target, which is marked as matching with no reason.
  **Checked:** `src/nl_shell/targets.py:210-260` (`select`), `Target.matches` at `:79-84`.
  **Test:** `tests/test_targets.py::test_exact_match_is_active_and_matching`, `::test_real_ubuntu_target_is_selected_on_a_matching_os`.
- **Claim:** with no match and no named target, start-up is refused with a message naming the detected OS, the available targets and both ways to name one. There is no near-version or `ID_LIKE` fallback.
  **Checked:** `src/nl_shell/cli.py:44-51` (the refusal, before `Repl.interactive` at `:64`), `targets.py:240-260`.
  **Test:** `::test_no_match_and_no_named_target_is_refused` (`26.10`; `debian` with `ID_LIKE=ubuntu`), `::test_folder_named_like_the_os_with_disagreeing_match_is_not_selected`.
- **Claim:** `--target` on another OS starts, warns, and records `matches=False` with reason exactly `"target does not match this OS"` (spec `policy-gate/v1` §7.7). `:status` shows "does not match this OS (detected: …)".
  **Checked:** `targets.py:229-238`, `Selection.status_lines` at `:102-111`.
  **Test:** `::test_named_target_on_another_os_starts_marked_not_matching`, `::test_mismatch_reason_is_the_spec_text`.
- **Claim:** config `target =` behaves like the flag, the flag wins, a broken config is refused with the file named, and an empty or relative `XDG_CONFIG_HOME` is ignored.
  **Checked:** `src/nl_shell/config.py:33-63`.
  **Test:** `::test_config_target_behaves_like_the_flag`, `::test_flag_wins_over_config`, `::test_config_that_is_not_valid_toml_is_refused`, `::test_relative_or_empty_xdg_config_home_is_ignored`.
- **Claim:** a bad target id (`../x`, empty, containing `/`) is refused without building a path outside the targets root, and every broken `target.toml` case is refused with the file and the problem.
  **Checked:** `targets.py:114-152` (`is_plain_id`, `load`), `:154-207` (`_validate`).
  **Test:** `::test_invalid_id_is_refused_before_any_path_is_built`, `::test_named_target_that_is_not_a_plain_folder_name_is_refused`, `::test_broken_target_toml_is_refused`.
- **Claim:** os-release falls back only when `/etc/os-release` is missing. An unreadable or non-UTF-8 file never falls back. Quoting is parsed per os-release(5).
  **Checked:** `src/nl_shell/os_release.py:85-104` (`read`), `:31-82` (`parse`, `_unquote`).
  **Test:** `::test_usr_lib_os_release_is_read_when_etc_is_missing`, `::test_unreadable_etc_os_release_without_named_target_is_refused`, `::test_unreadable_etc_os_release_with_named_target_starts_not_matching`, `::test_os_release_quoting_is_parsed_as_os_release_5_describes`.
- **Claim:** a target folder without `allowlist.toml` loads, and the real `targets/ubuntu-26.04/target.toml` loads with the expected values.
  **Test:** `::test_target_folder_without_allowlist_loads`, `::test_real_ubuntu_target_loads_and_matches`.
- **Claim:** no OS name in package code or in the `[project] description`. On `main` the tagline names it at `src/nl_shell/__init__.py:1`, `src/nl_shell/cli.py:14` and `pyproject.toml:8`.
  **Test:** `::test_no_os_name_in_package_code`, `::test_no_os_name_in_project_description`.
- **Claim:** `:status` lines don't leak between sessions, and a `Repl` with no target shows only the version. This replaces the module-level `STATUS_LINES` at `src/nl_shell/input_modes.py:77-82` on `main`.
  **Checked:** `input_modes.py:77-92` (new comment and `status`), `repl.py:38-55`, `:74-84`.
  **Test:** `::test_status_lines_do_not_leak_between_runs`, `::test_repl_without_target_has_no_target_lines`, `tests/test_input_modes.py::test_status_lines_can_be_extended`, `tests/test_cli.py::test_main_runs_the_interactive_repl`.
- **Red → green:** with every non-test change reverted, 61 of the 91 tests in `tests/test_cli.py`, `tests/test_input_modes.py` and `tests/test_targets.py` fail. All 91 pass with the change. The full suite passes: 237 tests. Every case fakes os-release and the targets folder, so the result doesn't depend on the host OS.

Refs #92

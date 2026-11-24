## Summary
**User impact:** when a command fails, nl-shell has no fixed, predictable answer
for what went wrong. A Ctrl-C, a typo'd program name and a failed `sudo` would
all be handled the same way, by sending the command and its output off for a
suggested fix. For a command that may have used `sudo` (or `su`, `pkexec`,
`doas`, ...) that is unsafe: nl-shell must never read that output or offer to
re-run a corrected version of it.

This PR adds a small, model-free classifier that sorts a failed command into a
fixed set of classes (interrupted, privilege, not found, not executable,
killed by a signal, other), each with a fixed message. Only "other" is marked
as eligible to be read for a suggested fix. Nothing calls it yet; the first
caller comes with the correction work (#17).

Reported in [#155](https://github.com/eduralph/nl-shell/issues/155).

**Depends on #146** (the persistent bash session, #140). This change uses that
PR's `CommandResult`, so CI against `main` stays red until #146 merges.

## What to look at
- The new module `src/nl_shell/failure_classes.py`: one entry point,
  `classify(result, command, lookup=None)`. It takes the session's result for
  the command and the command text the user confirmed. It never looks at the
  command's output.
- The privilege rule, near the top of the module. It errs on the safe side on
  purpose: if the text *could* make bash run a privilege program, the command
  is treated as privileged. The cost is that some ordinary commands, such as
  `echo $(date)`, `grep 'a\|b' f` or `git commit -m "fix: x (y)"`, get no fix
  offer.
- The new bullet under "Known gaps" in `.oss-scanner/threat_model.md`. It
  lists, in plain words, the five kinds of privileged command this text-only
  check still misses, until the parser-based policy gate (#12) closes them.
- To try it: `python3 -m pytest tests/test_failure_classes.py`. The test file
  is a set of tables, one row per command, so it also reads as a list of
  examples.

## Root cause
There was no step between "bash reported a non-zero exit" and "ask a model",
so nothing kept a privileged command's output away from the model, and no
cheap fixed answer existed for the common cases (Ctrl-C, not found, killed).
Earlier attempts at the privilege check tried to follow bash's quoting and
nesting by hand and kept missing spellings; this version keeps no state at all.

## Fix
`classify()` checks, in order, for a command that ran: status 0 is no
failure; 130 is an interrupt (shown as not an error, no fix offer); text that
could run a privilege program is "privilege"; then 127 not found, 126 not
executable, 129-192 killed by signal n (named, with an out-of-memory hint for
137), and the rest is "other". If bash read the input but ran nothing, blank
or comment-only text is no failure, privileged text is "privilege", and
anything else is a syntax error ("other").

The privilege check is regex and character tests over the raw text. It flags
the text when any of these holds:
1. a privilege program's name (`sudo su pkexec doas run0 machinectl sudo-rs
   sudo.ws sudoedit sudoedit-rs`) appears anywhere once backslashes and quote
   characters are removed;
2. the text holds `$(`, a backtick, `<(`, `>(`, `$'`, `$"` or a backslash;
3. the first word of any command segment is not a plain name, builtin or
   keyword;
4. a word names one of the user's shell functions;
5. a word names an alias whose value is privileged by these same rules
   (chains are followed; a cycle or a chain over 8 deep counts as privileged).

Alias text is read the way `alias -p` prints it, including multi-line values
and names that start with `-` (`alias -- -s='sudo'`).

For 127, a package hint comes from an injected `lookup` callable; the package
data itself is a separate change (#156). The hint is only given for a simple
one-word command whose first word does not resolve to an alias, builtin,
keyword or a file on `PATH`. Words and package names that are not plain
printable text, or are too long, are never shown.

## Verification
- **Claim:** results come only from the session's trusted done record.
  **Checked:** `src/nl_shell/session.py:375-390` (`CommandResult`: `ran`,
  `status`, `pipestatus`, `snapshot`); `classify` raises `TypeError` for
  anything else, including a bare `pty_protocol.Done`.
  **Test:** `test_bare_done_record_raises_type_error`,
  `test_int_raises_type_error`.
- **Claim:** the classifier never sees the command's output.
  **Checked:** `classify`'s signature in `src/nl_shell/failure_classes.py:119`.
  **Test:** `test_signature_takes_no_stderr_or_output`.
- **Claim:** "nothing ran" is handled as the protocol defines it.
  **Checked:** `docs/design/specs/pty-protocol/v1.md:375-377` (a done record
  without a start record means bash read the input but ran nothing).
  **Test:** `test_nothing_ran_from_blank_or_comment_is_none`,
  `test_nothing_ran_from_other_text_is_a_syntax_error`,
  `test_nothing_ran_from_privileged_text_is_privilege`.
- **Claim:** a possibly privileged command is never offered a correction and
  never goes to the reader; its message is neutral.
  **Checked:** the privilege names follow the policy-gate spec
  (`docs/design/specs/policy-gate/v1.md:111`) plus their `-rs`/`.ws`/`sudoedit`
  variants; the threat model's "What must hold"
  (`.oss-scanner/threat_model.md:109-112`).
  **Test:** `test_privileged_p1_literal_name` ... `test_privileged_p5_alias`,
  `test_privilege_message_is_neutral`, and the 127/126 privilege rows.
- **Claim:** ordinary commands keep the fix offer.
  **Test:** `test_not_privileged` (`ls $HOME`, `./build.sh`, `[[ -n $x ]]`,
  `for f in *.txt; do ...`, `make -j4`, ...), `test_name_inside_a_longer_word_is_not_privilege`
  (`pseudo x`, `echo sudo-ish`).
- **Claim:** builtins and keywords are recognised the same way the router does.
  **Checked:** reuses `router.BASH_BUILTINS` and `router.first_token`
  (`src/nl_shell/router.py:26-48`); `router.py` is unchanged.
- **Claim:** hostile input cannot make the check slow or crash it.
  **Test:** `test_bounded_work` (1200 brace groups, 40000 `{`, deep `${...}`
  nesting, a 1200-group alias, an alias cycle, a 10-deep alias chain), each
  under 2 seconds and never raising.
- **Claim:** nothing unsafe is printed back to the terminal.
  **Test:** `test_unsafe_command_word_is_privilege_and_never_shown` (an ESC
  byte or a U+202E bidi override), `test_65_char_word_is_not_shown`,
  `test_unsafe_package_is_not_shown`, `test_at_most_five_packages_are_shown`,
  `test_no_message_in_any_table_says_none`.
- **Claim:** the remaining misses are written down.
  **Checked:** the new "Known gaps" bullet at
  `.oss-scanner/threat_model.md:190-203`.
  **Test:** a test checks that the one bullet naming `failure_classes` also
  names `#12`, `bash -c`, `PATH`, `trap` and `PROMPT_COMMAND`.
- **Regression:** with the new module and the threat-model bullet reverted,
  272 of 273 tests in `tests/test_failure_classes.py` fail; with them, all
  273 pass. The one test that passes both ways only checks that the test file
  itself is plain ASCII. The full suite (`python -m pytest`) passes: 925
  tests.

Fixes #155

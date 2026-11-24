# Adversarial review — failure-classifier-by-exit-code (#155)

**Evidence.** The C4 log (`gate-logs/C4-verify.log`) shows 127 of 127 tests failed on the reverted tree. Each failure was a `ModuleNotFoundError` raised inside a test function, not a collection error. With the fix, the same tests pass, and the T3 log shows the full suite green (779 passed). The tests call the real `nl_shell.failure_classes.classify` on a real `session.CommandResult` and `pty_protocol.Snapshot`; nothing is copied or mocked away. I could not re-run pytest myself because this sandbox has no `pytest` module. Instead I loaded the module directly with `python3` and probed it by hand, and it behaved as the tests claim. I found no case where a test passes for the wrong reason.

**Where it breaks:**

- NEEDS-HUMAN [impl] — `src/nl_shell/failure_classes.py:176-196` (`words` / `_coarse`, used by `is_privileged` at :204-221): a privileged command written with ANSI-C quoting or a parameter default is not caught. `classify(status=1, "$'sudo' apt update")`, `"${X:-sudo} apt update"` and `"pk$'exec' x"` all return `OTHER` with `offer_correction=True` and `to_reader=True`. Bash runs `sudo` / `pkexec` in every one. The coarse pass keeps `$` attached (`$sudo`) and does not split on `:-`, so the basename never equals `sudo`. Decision 1 says "ANY shell word"; `$'sudo'` is a shell word whose value is `sudo`. Cheap fix: in the coarse pass, also drop `$` and split on `:` `-` `+` `?` (over-splitting is the safe direction), and add these rows to `PRIVILEGED`.
- NEEDS-HUMAN [human] — `src/nl_shell/failure_classes.py:176-196`: some obfuscated forms need a real parse to catch. `"su$()do x"`, `"su${EMPTY}do x"` and a backslash-newline continuation `"sud\<newline>o x"` all classify as `OTHER` with a correction offered and output sent to the reader. Bash runs `sudo` for each. A word splitter can't fix these without breaking the `pseudo x` lookalike row. The human should decide whether this gap is acceptable until #12's parse lands, or whether the classifier should treat any `$` / backslash-newline inside a word as possibly privileged.
- NEEDS-HUMAN [human] — `src/nl_shell/failure_classes.py:137-140`: `ran=False` comes before the privilege check, as the brief orders it. So `classify(ran=False, "sudo foo (")` returns `OTHER` with `offer_correction=True` and `to_reader=True`. #17 could then offer a corrected `sudo …` command, and ADR-0015's rule is to never offer anything that touches the sudo password. The code matches the brief, so this is not a code bug. The human should confirm at sign-off that syntax errors in privileged text are meant to get a correction offer.
- NEEDS-HUMAN [impl] — `src/nl_shell/failure_classes.py:255-260`: if the injected lookup returns a bare `str` (which is technically a valid `Iterable[str]`), the code iterates it character by character. `lookup=lambda w: "htop"` gives `packages == ('h','t','o','p')` and the message "provided by the packages h, t, o, p". A lookup that returns `None` raises `TypeError`, and a lookup that raises is passed through uncaught. #156 owns the provider, but a one-line guard (`if isinstance(result, str): result = [result]`) or a test that pins the contract would settle this.
- NEEDS-HUMAN [impl] — `tests/test_failure_classes.py:394` and `:416`: the docstring at :9 says "Every non-ASCII or control character is written as a Python escape". But the bidi rows contain a literal U+202E byte sequence (`foo‮gnp`, `ht‮op`). A literal bidi override in source is exactly the display hazard this module guards against. Write it as `"‮"`.

**Attempted and could not refute:**
- Alias chains, including real `alias -p` quoting such as `'\''`.
- `\sudo`, `s''udo`, `command sudo`, `exec sudo`, `x=sudo; $x`, `{sudo,} x` (all are caught as privilege).
- Every status from 129 to 192: no message contains `None`.
- The 127 rule with quoted, escaped and commented first words, and with `htop &`.
- Combining-mark floods in the word (they are rejected by `render.too_many_marks`).
- The output bytes never influencing the class.

The `check-gates.json` claims (C4 and T3 pass) are supported by the logs. The T4 row is marked "deferred", not passed.

<!-- pdca:leaf-complete -->

# Adversarial review: issue 155, failure-classifier-by-exit-code

I tried to break the evidence, the code and the verdict. Short version: the red→green proof holds, and I found one small build bug in the alias chain-depth rule. I also found several privilege forms that the P1–P5 rule *as written* misses. Under the brief's review bound, those are gaps for #12, not reasons to send the slice back.

How I checked: the sandbox has no `pytest`, so I could not re-run the test file. Instead I read `gate-logs/C4-verify.log` (red: 258 of 259 failed, all from `ModuleNotFoundError` inside the test functions; the one green test is the ASCII self-check, as the brief predicts) and `gate-logs/T3-suite.log` (911 passed). Then I called the real `nl_shell.failure_classes.classify` at `$PDCA_TARGET` with real `CommandResult`/`Snapshot` objects through a probe script. Every finding below comes from running production code. None is inferred.

## Findings

- NEEDS-HUMAN [impl] — `src/nl_shell/failure_classes.py:223-226`: the memo is checked before the depth limit, so a chain "over 8 deep" can count as not privileged. It depends on which alias was seen first. With the brief's own 10-alias chain (`a0`→…→`a9='ls'`, test `CHAIN_10` at `tests/test_failure_classes.py:328`), command `a0` → `privilege`, but command `a8; a0` → `other`. Here is why. `a8` is checked first at depth 1 and stored as `False`. Then the walk from `a0` reaches `a8` at depth 9, and the stored `False` comes back before the `depth > MAX_ALIAS_DEPTH` check runs. Brief rule P5 says "a chain over 8 deep counts as privileged" with no order exception. The real-world impact is low: the depth limit only ever adds `True`, so this cannot hide a real `sudo`. But it is a case the rule covers that the code gets wrong. Fix: check depth before the memo lookup, or only store results that did not depend on a depth cut-off. Add the `a8; a0` row.

- NEEDS-HUMAN [human] — rule gap, P3 cuts at `&` (`src/nl_shell/failure_classes.py:106`, the same as the brief's P3 text). A redirection that duplicates a file descriptor (fd) puts the fd digit at the start of the next segment, and that digit becomes the "first word". Probes: `2>&1 sud${X}o x` → `other`, `>&2 sud${X}o x` → `other`, `>&- sud${X}o x` → `other`. Bash runs `sudo` in all three when `X` is empty. The rule as written gives the same answer, so per the review bound this goes to #12. The Known-gaps bullet's kind (1) ("expansion behind a plain first word") does not obviously describe it: here the "plain first word" is `1`, `2` or `-`. A human should decide whether to name it in the bullet.

- NEEDS-HUMAN [human] — rule gap, the redirection list leaves out `<<-` (`src/nl_shell/failure_classes.py:109`, matching the brief). `<<- EOF sud${X}o x\nhi\nEOF` → `other`. `<<-` matches only `<<`, so the next piece is not skipped, and `EOF` is taken as the plain first word. This is a here-doc in front of a privileged command. Record it for #12.

- NEEDS-HUMAN [human] — rule gap, compound commands whose body sits in the same segment after a plain word. `function f { sud${X}o x; }; f` → `other`: `function` is not in the skip list, so it is the plain first word, and P4 only knows functions from the snapshot taken before the command. `coproc N { sud${X}o x; }` → `other`: `coproc` is skipped, and the name `N` is the plain first word. The brief's `f() { sud${X}o x; }` row is caught only because `(`/`)` cut the text. The `function` keyword form is not caught. Rule as written gives the same answer, so this goes to #12. The bullet's kind (1) covers it only loosely.

- NEEDS-HUMAN [human] — rule gap, aliases defined inside the command itself. `alias s=sud${X}o\ns x` → `other`. Bash expands the assignment to `s=sudo` and uses the alias on the next line. P5 reads only the pre-command `snapshot.aliases`. Same family: `eval $CMD` and `exec ${X} x` → `other` (builtin first word, expansion behind it). This is kind (1) in the bullet, and `bash -c "$CMD"` is already named there. I list it only so #12 has the concrete cases.

## Attempts that did not land

- A newline inside an alias value (`alias x='ls\nsud${X}o y'`): `shlex.split` keeps the quoted newline in one token, so `x` → `privilege`. Correct.
- Unicode whitespace: Python's `str.split()` splits on characters bash does not, for example U+00A0, which bash keeps inside a word. I could not make bash run a privilege program from that difference, because over-splitting only shows the checker more words. Rule 4's `first_token` plus `_displayable` keeps such a word out of `message`.
- The `own_name` skip (`:204-207`) breaks from the rule's literal "a cycle counts as privileged" only for an alias that names itself. Bash does not expand that, so it is not a miss.
- The evidence itself: the test calls the production `classify` through `nl_shell.failure_classes`, not a copy, and the output field is shaped like an attack (`tests/test_failure_classes.py:53`) without changing any class. The red is real, though it is a red from a missing module, as designed. It shows the tests need the module. It does not show that any single privilege row would fail against a wrong rule. The Plan-time prototype is the only check of that, and it is not shipped.
- T2 says "no security-relevant path touched" (`check-gates.json` row T2), even though the patch edits `.oss-scanner/threat_model.md`. The gate is not gating, and the threat model *was* updated, so this does not refute anything.

Verdict: I could not refute the red→green evidence, and the code matches P1–P5 apart from the memo-order bug above. The real exposure is the rule-level gaps, which the brief deliberately leaves to #12.

<!-- pdca:leaf-complete -->

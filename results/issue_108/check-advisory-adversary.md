# Adversarial review — issue 108 / router-english-sentence-rule

I tried to refute the fix and could not break it against the brief. What's left is small test gaps and a few spec-level misroutes the brief allows on purpose.

**What I tried and could not refute**

- **The red→green evidence is real.** `gate-logs/C4-verify.log` shows 8 of 43 failing without the fix. Those are exactly the 8 NATURAL_LANGUAGE vectors whose first word resolves. The test (`tests/test_repl.py:127-130`) drives the production `Repl` through `run()` and checks its output, so it does not use a copy of the logic. T3 shows the full suite green (1122 passed). pytest is not installed in my sandbox, so I re-ran the 32 table vectors directly against `nl_shell.router.route` with a fake `$PATH`. All 32 match.
- **Mutation checks against the table** (each one swaps in a changed router and re-runs the vectors). Word count `< 3` fails on `ls my files`, and `< 5` fails on `who is logged in`. Removing the quote signal fails 4 vectors. Emptying `FREE_TEXT_COMMANDS` fails 2, and dropping only `printf` fails 1. Earlier rounds already showed that rule 3, rule 4, the `\`/`"` exclusions and the signal-before-rule-3 order are pinned (`tests/test_repl.py:114-125`).
- **`first_token` is unchanged** (`src/nl_shell/router.py:52-61`), so its other caller in `failure_classes.py` is not affected.

**Findings**

- NEEDS-HUMAN [impl] — The `.lower()` in rule 4 (`src/nl_shell/router.py:104`) is not tested. If I remove it, all vectors still pass. Then `Find The Big Files In My Home` would stay natural language only by luck: `Find` is not on `$PATH`. And `ls The Big Files Here` (resolved first word, function word only in title case) would flip to COMMAND without any test failing. Fix: add a vector like `watch The logs For errors` → natural language.
- NEEDS-HUMAN [impl] — 16 of the 18 shell metacharacters in `SHELL_METACHARACTERS` (`src/nl_shell/router.py:75`) are not pinned one by one. Removing any single one of `& ; < > $ * = ( ) { } [ ] ~ / backtick` from the set leaves every vector green. `~` and `/` only appear together in `find big files in ~/src`, so each one hides the loss of the other. A later edit that drops `$` or `=` would quietly send `grep the $HOME in x` or `find the x in a=b` to the model. This is a low-severity test gap, not a bug in the patch. A small parametrized test, one line per character, would close it.
- NEEDS-HUMAN [human] — The spec'd function-word list misroutes some plausible real commands. I ran these through the patched `route()` with the commands on a fake `$PATH`: `make all check install`, `cat a b c`, `touch a b c d`, `git add the file`, `grep error in log.txt` and `time make all in here` all route as natural language. The words `a`, `all`, `the` and `in` are common shell operands (file names, make targets). The patch follows the brief to the letter (brief §Design rule 4), and `\cmd` forces bash. Still, a human should confirm that `a` and `all` belong in the list. This is the brief's choice, not a builder slip.
- NEEDS-HUMAN [human] — A false natural-language route sends the raw line to the model backend, which may be remote. The brief treats this as only a usability cost ("costs one model call"). The quote signal overrides every other rule (`src/nl_shell/router.py:93-94`), so a real command with a stray apostrophe goes to the model whatever it contains, as long as it has no `"` or `\`. For example, `grep -c ' file`, `sed s/'//g f` and `git checkout -- it's` all route as natural language. Rule 3 stops most lines that hold secrets (`=`, `-`, `$`), but the quote path skips rule 3. Whether that matters depends on the backend's privacy model. ADR-0013 only covers the command side of a misroute. This is a scope call for a human, not something to fix in this patch.

No other refutation: the fix meets the brief's success criterion, and the evidence exercises the production path.

<!-- pdca:leaf-complete -->

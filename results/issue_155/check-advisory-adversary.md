# Adversarial review — issue 155, round 8 (`alias -- NAME=` fix)

Bottom line: I could not break the round-7 fix. One minor finding about cost on huge alias values (below), which is not a privilege bypass.

## What I attacked and could not break

- `src/nl_shell/failure_classes.py:114-115` — the new optional `(?:-- )?` in `_ALIAS_START` / `_ALIAS_LINE`. I ran the production `is_privileged` / `_parse_aliases` directly (no pytest in this sandbox, so plain `python3 -I` scripts in cwd). All of these give the safe answer: `-s x` with `alias -- -s='sudo'` → privileged; `--x y` with `alias -- --x='sudo'` → privileged (the optional group backtracks properly); `-z x` with `alias -- -z='ls\nalias ls=sudo'` → value read as one quoted value, and `ls` is *not* turned into an alias; `alias -- s='sudo'` also works; `'\''` escapes and a value that is entirely quoted `'sudo'` both stay privileged; a missing trailing newline is fine.
- **Do the new rows really separate v7 from v8?** Yes, by working it through. The v7 regex `alias ([^=\s]+)=` does not match `alias -- -s=…`, so under v7 `-s x` has no alias. `-s` fits `_PLAIN` (`failure_classes.py:110`), so v7 gives other, and the row `alias-dash-name` (`tests/test_failure_classes.py:352`) would have gone red. For `alias -- -z='ls\nalias ls=sudo'`, v7 would have read `ls=sudo` as a real alias, so the negative row at `tests/test_failure_classes.py:377` (`ls x` → not privileged) would have gone red too. Both rows test the real fix, not a tautology.
- **C4 evidence** (`gate-logs/C4-verify.log`): the red leg fails 272 of 273 only because the module is missing. That proves the tests import production code, but not that each new row would fail against v7. The reasoning above fills that gap for the two round-7 rows. The single green-in-both test is the ASCII self-check, as the brief says.
- **Round-6 fixes still hold:** repeated name → None (privileged); the depth memo carries height (`failure_classes.py:239-241`). I checked `a8` then `a0`, and a branching value, against the depth cut-off, and the results are consistent.
- **Cost:** 5000 chained `alias -- ` names take 0.01 s; 20000 aliases spread wide take 0.16 s; 50000 `'\''` escapes take 0.04 s.
- **Threat-model bullet** (`.oss-scanner/threat_model.md:190-203`): it names gaps (1) to (5), including the round-6 redirection gap, and the test checks `2>&1 sud` inside the one bullet (`tests/test_failure_classes.py:796`). The optional rewrap nit has been done.

## Finding

- NEEDS-HUMAN [human] — `src/nl_shell/failure_classes.py:321` (`shlex.split(raw)` on each alias value) grows faster than linear in the size of the value. This conflicts with the brief's cost bound ("linear in the text plus alias values"). The cause is the stdlib `shlex`, which the brief itself prescribes for P5. Measured on one valid, closed, multi-line alias value: 150 KB → 0.15 s, 300 KB → 0.43 s, 600 KB → 1.9 s. An unclosed quote shows the same curve: 50000 lines → 1.4 s, every bit of it inside `shlex.split`. The verdict stays correct (no bypass), and a single alias this large is unrealistic. It still breaks the written bound, and a value of about 1 MB would go past the 2-second wall-time row. The choices are: accept it, cap the alias text size (treat an oversize value as privileged, the safe direction), or swap `shlex.split` for the `_word_end` quote reader the module already has. That is a scope call on the brief's prescribed tool, so I tagged it [human] rather than [impl].

## Verdict

I tried to break the `alias -- ` fix (dash names, `--` as a name, multi-line values under `-- `, escaped quotes, missing newline), the round-6 fixes it must not undo, and the red→green evidence. I could not break any of them. The only issue is the cost item above, which is advisory.

<!-- pdca:leaf-complete -->

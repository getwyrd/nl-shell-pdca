# Security review (advisory) — issue 108 / router-english-sentence-rule

Attacker-reachable inputs this diff touches: **none.** The only input is the line the user types at the REPL prompt, which the threat model lists as trusted ("what the user types and their confirm and edit decisions"). The router does not read command output, file names, the state block, model output or retrieved history.

No finding. What I checked:

- **Who controls the input.** `route()` (`src/nl_shell/router.py:115-122`) gets only the typed line, from `Repl._reply` (`src/nl_shell/repl.py:144`). Prefixed input (`\cmd`, `@`, `?`, `:`) is handled by `input_modes.parse` before the router and does not reach it. So no untrusted text passes through the new rule.
- **`$PATH` lookup (session state, untrusted item 4).** The diff only moves the existing builtin / `/`-path / `shutil.which` checks into `_is_command_name` (`src/nl_shell/router.py:107-112`). The logic is the same and it still reads nl-shell's own process `PATH`, not the bash session's. No change in exposure.
- **What a misroute costs.** COMMAND → NATURAL_LANGUAGE now happens more often. The result is a model proposal, and that still has to pass the proposal parser and (once #78 lands) the gate and confirm. NATURAL_LANGUAGE → COMMAND is not made more likely by this diff. The threat model rates a wrong intent route as **Low** and says a wrong route still ends at the gate. Nothing in the diff skips the gate or the confirm. `repl.py` is untouched.
- **A secret typed as a command ending up in model context.** A line that used to route as COMMAND can now go to the local model as a request. Typical secret-carrying lines (`export TOKEN=…`, `mysql -pSECRET`, `curl -H "Authorization: …"`) contain `=`, `-` or `"`, so rule 3 (`src/nl_shell/router.py:100-103`) keeps them as COMMAND. A sentence with a pasted key in it (`find the file with key sk123abc`) would reach the local, no-network model. That is the user's own text sent to their own model, which the design allows, so it is not a finding.
- **Crash, hang or resource use.** `_has_unbalanced_single_quote` and `_reads_like_english` (`src/nl_shell/router.py:86-104`) are plain linear scans (`count`, `split`, `in` on frozensets). No regex, no shlex on the full line, so nothing can raise or backtrack badly. `first_token` (`src/nl_shell/router.py:53-63`) is unchanged and still never raises, so the other caller in `failure_classes` is unaffected.
- **Tests.** This change is not security-relevant, so friendly-path coverage is enough. Even so, the table pins the cases that matter for routing safety: option and quote lines (`find . -name '*.py'`, `git commit -m "wip`) stay COMMAND. C4 shows 6 of 33 red before the fix and all green after (`gate-logs/C4-verify.log`). T2 found no security-relevant path touched.

No NEEDS-HUMAN items.

<!-- pdca:leaf-complete -->

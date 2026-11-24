# Security review — issue 108 / router-english-sentence-rule

Attacker-reachable inputs this diff touches: **none**. The only input to `route()` is the line the user types at the prompt, which the threat model lists as trusted ("what the user types", `.oss-scanner/threat_model.md`, "Trusted").

## What I checked

- **Who calls the changed code.** `route()` has one caller, `src/nl_shell/repl.py:144`. It gets the stripped prompt line after prefix parsing (`repl.py:133,142`). No command output, file name, environment value, model output or history reaches it. `failure_classes.py:46` imports only `BASH_BUILTINS` and `first_token`, and the diff leaves both unchanged (`src/nl_shell/router.py:43-53`).
- **What a wrong route can do.** A COMMAND route still returns `COMMAND_NOT_YET` (`repl.py:145`), and once #78 lands it will go to the policy gate. A NATURAL_LANGUAGE route goes to `_propose` (`repl.py:146,155-170`). That builds a prompt for the local model and shows a parsed proposal. It runs nothing. The threat model rates a misroute as Low ("the intent classifier routing input to the wrong mode") and puts the router in its lower-priority list. The new rule only moves some lines from COMMAND to NATURAL_LANGUAGE. It cannot skip the gate: `\cmd` still skips only the router (`repl.py:147-151`), and the diff does not touch `repl.py`, the gate, the PTY code, taint or logging.
- **Secrets the user typed reaching the model.** A line now routed as natural language is sent to the command model. I checked whether the usual ways people type secrets on a command line could slip through. `export TOKEN=x for the build` is rejected by rule 3 (`=`). `mysql -u root -phunter2 for the db` is rejected (a word starts with `-`). `curl https://...` is rejected (`/`). Even if a secret did get through, it would be the user's own text going to a local model on a `0600` socket, which is the normal path for any natural-language request. No finding.
- **Panic, hang or heavy work from the input.** The new helpers (`router.py:87-106`) only call `str.count`, `str.split`, `in` checks and frozenset lookups. All are linear in the line length, with no regex and no shlex. `first_token` still catches shlex's `ValueError` (`router.py:47-51`). `_is_command_name` (`router.py:109-114`) is the old resolution logic moved into a function with the same order and behaviour: builtin, then a path containing `/` checked with `is_executable_file`, then `shutil.which`.
- **`$PATH` as session state (threat model item 4).** The router reads nl-shell's own process `$PATH` through `shutil.which`, not the bash session's, and the diff does not change that. It is unchanged code, not something this patch introduces.
- **Test coverage of the security-relevant case.** None is needed, because this change has no security impact. Gate T2 (`gate-logs/T2-threat-model.log`) also reports "no security-relevant path touched", and the brief says the same ("no threat-model input changes").

## Findings

No findings. The diff touches no attacker-reachable input. Its only effect is on routing, which the threat model rates Low and says still ends at the gate.

<!-- pdca:leaf-complete -->

# Security review (advisory) — issue 15 / heuristic-nl-vs-command-router

Attacker-reachable inputs this diff touches: **none**. The only input to the new code is the line the user types at the REPL, and the threat model lists "what the user types at the REPL" and "paths the user typed" as trusted (`.oss-scanner/threat_model.md`, "Where untrusted input enters", last paragraph). Nothing runs yet: both routes end in a fixed print at `src/nl_shell/repl.py:62`, so there is no gate, PTY or model to get past.

## What I checked

- **Where the routed line goes.** `route(text)` (`src/nl_shell/router.py:57-67`) returns an enum, and the REPL only uses it to pick one of two fixed strings (`src/nl_shell/repl.py:27-30`, `:62`). No user text is echoed, logged, passed to a shell or put in model context. So no escape-sequence, injection or secret-leak path exists.
- **Crashes and hangs from odd input.** `first_token` (`src/nl_shell/router.py:39-48`) catches the `ValueError` that `shlex` raises on an unbalanced quote and falls back to `str.split`. `shlex` with `whitespace_split` reads one token and stops, or, with an open quote, scans to the end of the line once. Both are linear in the line length. Inputs I traced: `what's using port 80` (covered by the test), a lone `"`, `\` (trailing escape, which also raises `ValueError` and is caught), and `''` (gives an empty token, so the result is natural language). None of them raises or loops.
- **File-system probing.** `is_executable_file` (`src/nl_shell/router.py:51-54`) calls `expanduser`, `isfile` and `os.access` on a first token that contains `/`. That path comes from the user, which is trusted, and the code only checks the file; it never opens or runs it. `shutil.which` (`:65`) reads `$PATH` from the user's own environment.
- **Wrong route.** The threat model rates this **Low** and says it does not matter much ("a wrong route still goes through the gate"). The known misroute (`find large files in my home` → command) is intended and pinned by the test.
- **Tests.** No security-relevant fix here, so a friendly-path-only test is fine. The test still covers the one robustness case that matters (unbalanced quote must not raise, `tests/test_repl.py`, the `what's using port 80` row). C4 log: red 14/19 without the fix, green with it. T3: 21 passed.

## Findings

No findings. The patch adds no attacker-reachable path and leaves no "What must hold" property weaker.

## Notes for later milestones (not findings, nothing to fix in this diff)

- When `$PATH` contains `.` or an empty entry, `shutil.which` also matches executables in the cwd. File names in the cwd are untrusted (threat-model item 2), so a cloned repo could ship an executable named `show` and send `show disk usage` down the command route. Today that only changes which fixed string prints. It is a Low misroute, and only with a PATH setup the user chose. It becomes worth a look when #10 (PTY) wires the command route to real execution. That wiring must send the command route through the policy gate and must not run "command" input directly. This patch does not do or block that, so I am not tagging it.
- In the `except ValueError` branch (`src/nl_shell/router.py:44-47`), the first token comes from `str.split`, not from how bash would parse the line. That is fine for picking a route. Later code must not reuse `first_token` to decide what runs or how a command is classed. The gate parses the AST for that.

<!-- pdca:leaf-complete -->

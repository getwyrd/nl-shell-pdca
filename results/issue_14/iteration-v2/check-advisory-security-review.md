# Security review — issue 14 / input-mode-prefix-dispatch

**Attacker-reachable inputs touched: none.** The only input this diff handles is the line the user types at the REPL prompt. The threat model lists "what the user types" as trusted (`target/.oss-scanner/threat_model.md`, "Trusted"), and nothing in the patch reads command output, files, the environment, session state, model output or history (untrusted entry points 1–11).

What I checked:

- **Nothing runs.** `\cmd` with a payload returns the fixed `COMMAND_NOT_YET` string (`target/src/nl_shell/repl.py:72-76`). No subprocess, PTY or model call is added anywhere in `src/nl_shell/input_modes.py`. So "Nothing that isn't read-only runs without a confirm" and "Model output is never piped into the shell" cannot be broken by this patch.
- **`\` does not skip the gate by design.** The comment at `target/src/nl_shell/repl.py:73-75` says `\cmd` skips only the router, which matches ADR-0013 §7 (`target/docs/design/adr/0013-policy-gate-v2.md:82`). The gate itself is out of scope (#78).
- **Echoed text.** The unknown-meta reply prints the user's own payload back (`target/src/nl_shell/input_modes.py:127-128`, `Unknown meta-command :{payload}`). A line like `:\x1b]52;c;...\x07` would be echoed raw. But the source is the user's own typing, which is trusted, so this is not an output-rendering finding under the threat model ("Output rendering is filtered" covers PTY output, `:context` and `:history`, not the user's own input).
- **`:status` extension point** (`target/src/nl_shell/input_modes.py:68-74`). Today it prints only the version. Later lines (#92 target, #77 endpoint) will add data; any secret in them is a concern for those issues, not this one. No secret is printed now.
- **Exit commands and plain input** keep today's behaviour (`target/src/nl_shell/repl.py:62-71`); the router fallback is unchanged.
- **Gates.** C4 and T3 pass (`gate-logs/C4-verify.log`, `gate-logs/T3-suite.log`). T2 says no security-relevant path touched, which I agree with.
- **Severity of a wrong route.** Even if a prefix misroutes, the threat model rates intent-routing errors Low and `:` meta-commands lower priority; nothing here bypasses a later gate.

Note for #78, not a finding on this diff: `parse` strips the text after the `\` (`target/src/nl_shell/input_modes.py:62`), and the comment at `target/src/nl_shell/repl.py:75` calls `prefixed.payload` "the command text the gate will receive." When #78 wires the gate and the PTY, it should confirm that the stripped payload is exactly what gets shown in the confirm UI and sent to bash ("What the user confirms is exactly what runs"). The whole-line strip at `repl.py:59` already existed on `main` and is not new here.

No security findings. Nothing for a human to decide from this lens.

<!-- pdca:leaf-complete -->

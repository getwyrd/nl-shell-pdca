# Security review (advisory) — issue 14 / input-mode-prefix-dispatch

**Attacker-reachable inputs this diff touches: none.** The only input is the line the user types at the REPL (`src/nl_shell/repl.py:53-64`). The threat model lists "what the user types" as trusted (`.oss-scanner/threat_model.md`, "Trusted"). Nothing in the patch runs a command, reads command output, file contents, env values, history or model output (untrusted inputs 1–11). It only picks one of several fixed reply strings.

What I checked, and found nothing:

- **`\cmd` and the gate.** `src/nl_shell/repl.py:72-76` sends a non-empty `\` payload to the existing fixed command reply. Nothing runs, so no confirm can be skipped. The comment at `repl.py:73-75` keeps the ADR-0013 §7 rule visible for #78: `\` skips the router only, never the policy gate. The threat model ranks the router/classifier as lower priority because a wrong route still goes through the gate, and that still holds. No finding.
- **What is shown vs. what runs.** `src/nl_shell/input_modes.py:62` strips the `\` payload (`\  ls ` becomes `ls`). Nothing is shown to confirm or run yet, so the "confirm == runs, byte for byte" rule can't break here. When #78 wires the gate, the confirm UI must render from the same string the PTY receives. That belongs to #78, not this diff.
- **Echoed input.** `input_modes.py:130` echoes an unknown `:name` back to the screen as typed, including any control or escape characters. That text comes from the user's own keyboard or paste, which the threat model trusts, so this is not a spoofing path today. The output-filter rule applies to `:context` / `:history` content, which this patch leaves as fixed placeholders.
- **`:status` extension point.** `input_modes.py:69` is a module-level list of in-process callables. Only code inside nl-shell can append to it, and code running as the user is out of scope. `:status` prints only `nl-shell <version>` today, so no secret or env value reaches the screen. Later appenders (#92, #16, #77) should keep endpoint, token and env values filtered. That is for those issues to review.
- **Crash or hang from input.** `parse` (`input_modes.py:53-63`) is a fixed loop over five `startswith` checks. `reply` (`input_modes.py:119-134`) does dict lookups on keys that always exist for the modes it can receive (`USAGE` and `REPLIES` cover ASK/PROPOSE/AGENT, plus COMMAND with an empty payload). No regex, no recursion, nothing that grows with input size.
- **Test coverage.** The patch makes no security-relevant change, so friendly-path-only tests are not a finding. The T3 suite passed (169 passed, `gate-logs/T3-suite.log`). T2 reports no security-relevant path touched, which matches what I found.

No findings. No NEEDS-HUMAN items.

<!-- pdca:leaf-complete -->

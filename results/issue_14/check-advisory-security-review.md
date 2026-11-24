# Security review — issue 14 / input-mode-prefix-dispatch

Attacker-reachable inputs this diff touches: **none**. The only input is the line the user types at the REPL, which the threat model lists as trusted ("what the user types", `.oss-scanner/threat_model.md`, Where untrusted input enters → Trusted). Nothing in the patch runs a command, calls a model, reads files, env, history or command output.

## What I checked

- **`\cmd` route** (`src/nl_shell/repl.py:72-76`): it only returns the fixed `COMMAND_NOT_YET` reply. Nothing reaches a PTY or gate. The comment states the ADR-0013 §7 rule (`\` skips the classifier, never the gate), which matches the threat model's "Raw `\cmd` input is the user's own: it goes through the gate and confirm" gap. No bypass is created, since no execution path exists yet.
- **`:` meta-commands** (`src/nl_shell/input_modes.py:131-143`): lookup is an exact `dict.get` on a fixed table. An unknown name can't reach any callable. `:context` and `:history` return fixed strings, so the threat model's output-filter rule for them ("must not let printed text write the clipboard") isn't in play yet.
- **Echo of the unknown name** (`src/nl_shell/input_modes.py:142`): `Unknown meta-command :{payload}` prints user-typed text back unescaped. The source is the user's own keyboard (trusted), so a typed escape sequence only affects the user's own terminal. No finding.
- **`:status`** (`src/nl_shell/input_modes.py:80-86`): prints only `nl_shell.__version__`. No env, path or secret is shown. Later lines added by #92/#16/#77 (endpoint, backend) are for those issues to review against the "secrets reach `:context`" rule; this diff adds none.
- **Exit handling** (`src/nl_shell/repl.py:62`, `src/nl_shell/input_modes.py:67-74`): pure string checks, no crash or hang path. `parse` is a linear scan of five fixed prefixes, so there's no resource cost out of proportion to input.
- **T2 gate** (`gate-logs/T2-threat-model.log`): "no security-relevant path touched". I agree. The threat model doesn't need an update for this patch.

## Findings

No finding.

One note for later, not rated and not a NEEDS-HUMAN item: `src/nl_shell/repl.py:75` says `prefixed.payload` "is the command text the gate will receive", and `parse` strips it (`src/nl_shell/input_modes.py:63`). When #78 wires the gate and PTY, a stripped payload is not byte-identical to what the user typed after `\`. For example, bash treats `\ ls` as a command named ` ls`, and with `HISTCONTROL=ignorespace` a leading space keeps a command out of `~/.bash_history`. Whoever builds #78 should decide whether `\` passes the raw remainder or the stripped one, and show the user exactly that in the confirm ("What the user confirms is exactly what runs"). Today nothing runs, so this has no effect.

<!-- pdca:leaf-complete -->

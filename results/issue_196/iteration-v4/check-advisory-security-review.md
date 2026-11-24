# Security review (advisory): ast-policy-gate-shell-layer, round 4

**Attacker-reachable inputs this diff touches:** the command text passed to `nl_shell.gate.classify`, which is either a model proposal (untrusted; `.oss-scanner/threat_model.md` "Where untrusted input enters") or typed input. The threat model, as changed by this patch, puts any place tree-sitter-bash reads text differently from bash in scope as a gate bypass until #191 (`.oss-scanner/threat_model.md:240-241`). The gate is not wired to the REPL yet (#78), and the stub command layer floors every command at `mutating`. So nothing below runs unconfirmed today. Each finding becomes Critical once #197/#198 let a command be `read-only`.

I probed with the pinned `tree-sitter==0.26.0` / `tree-sitter-bash==0.25.1`, installed offline into my sandbox, and with real bash 5.3.9.

## Findings

- NEEDS-HUMAN [impl] — **High** ("a privileged or destructive step is classed lower"; the step is not classed at all). `src/nl_shell/gate/parse.py:653-661` and `:824-854`. **Two here-docs joined by `|`, `&&` or `||` on one line hide a command from the gate.** Input: the model's proposal. bash reads here-doc bodies in the order the operators appear (`A`, then `B`). tree-sitter-bash nests the second statement inside the first redirect (`(heredoc_redirect (heredoc_start) (pipeline … (heredoc_redirect …)) (heredoc_body) (heredoc_end))`), so it gives the first body to `B` and the later lines to `A`. `_check_heredoc_end` checks each here-doc on its own, so both pass. Reproducer, confirmed in bash and in the gate:
  ```
  cat <<A | cat <<B
  x
  A
  y
  B
  echo RAN7-HIDDEN
  A
  ```
  bash prints `y`, then **runs `echo RAN7-HIDDEN`**. The gate returns `mutating`, `rejected=False`, reasons `['not allowlisted']`, with two invocations: `cat` with literal stdin `'x\nA\ny\n'` and `cat` with literal stdin `'echo RAN7-HIDDEN\n'`. The hidden line is never handed to the command layer. Its text is also recorded as *literal here-doc text*, which child-3's here-doc exemption is meant to trust. The same holds for `cat <<A && cat <<B …`, `cat <<A || cat <<B …` and `cat <<A | sudo tee /x <<B …` (there the gate gives `sudo tee` the wrong body). This breaks the threat-model claim this patch adds (`threat_model.md:130-132`: the gate fails closed on "a here-document whose end line the parser and bash may not agree on"). Fix: fail closed when a `heredoc_redirect` holds another `heredoc_redirect` in its continuation, or more generally check that here-doc bodies come in the same source order as their `heredoc_start` nodes. Test: add the case above, and its `&&` / `||` forms, as decision-C cases next to the existing here-doc mismatch tests. The current pipeline cases (`tests/test_policy_gate.py:545-570`) have only one here-doc each.

- NEEDS-HUMAN [impl] — **High** on the scale's closest row ("printed text forges a control-channel record"); a confirm is still needed today. `src/nl_shell/gate/parse.py:396-408` (`_pattern`) and `:684-693`. **An extglob pattern in the directory part of a redirect target opens fd 3 and is not rejected.** Input: the model's proposal. nl-shell's bash sources `~/.bashrc` (`src/nl_shell/session.py:3`), and Ubuntu's bash-completion runs `shopt -s extglob` (`/usr/share/bash-completion/bash_completion:45`; `bash -ic 'shopt extglob'` shows `on` here). With extglob on, bash globs `>/dev/+(fd)/3` into `/dev/fd/3`. I confirmed this: `shopt -s extglob; exec 3>f; echo via-plus-dir >/dev/+(fd)/3` writes to `f`, and the `@(fd)` form does too. tree-sitter-bash splits at `(` into an ERROR node, so the redirect target is just `/dev/+` or `/dev/@`. That is neither a descriptor path nor a pattern (`_GLOB` is `*?[`), so the gate returns `mutating`, `rejected=False` for `echo x >/dev/@(fd)/3`, `>/dev/+(fd)/3`, `>/proc/@(self)/fd/3`, `>/@(dev)/fd/3` and `>/dev/!(null)/3`. The round-3 sign-off asked for globbed redirect targets to be rejected (brief.md:179), and the threat model now says a target "bash would glob" is rejected (`threat_model.md:126`). When the pattern is in the last part (`>/dev/fd/@(3)`), it is rejected only by luck: `/dev/fd/@` reads as a non-numeric descriptor. Fix: treat a file-redirect target followed straight away by `(`, whose text ends in one of `?*+@!`, as a pattern. Or more simply, reject any file redirect inside a tree with an ERROR node. Test: add `echo x >/dev/+(fd)/3` and `echo x >/dev/@(fd)/3` to the descriptor rejection list (`tests/test_policy_gate.py:~300-315`).

## Checked, no finding

- Round-3 fixes all hold against the pinned parser: `>/dev/f?/3`, `>/proc/self/root/dev/fd/3`, `/proc/self/task/1/root/…`, `/proc/thread-self/fd/3`, `/dev/./fd/3`, `/dev/fd//3`, `/dev/fd/0003`, `/dev/fd/+3`, `/dev/fd/3/`, quoted forms (`"/dev/fd/3"`, `/dev/fd/'3'`), `&>`, `>&`, `<>` to `/dev/fd/3`, `{a[0]}>x`, `"$\⏎(…)"` and `${ cmd; }` are all rejected or fail closed. `/dev/fd/1`, `/dev/stderr` and `/proc/self/root/dev/fd/2` are not rejected, which is correct.
- Here-doc line continuation: a body line `E\` followed by an empty line, which bash joins into the delimiter `E` (confirmed: bash ends the here-doc there and runs the next line). It fails closed in plain and `<<-` forms, and at end of file. `cat <<A <<B` and `cat <<A; cat <<B` on one line fail closed through the ERROR check. A here-doc inside `$(…)` inside another here-doc fails closed.
- `cd /dev/fd; echo x >3` and `>$F` are not rejected. Both are known gaps the threat model now lists (`threat_model.md:126-127`), and the brief says not to widen them. Not raised.

<!-- pdca:leaf-complete -->

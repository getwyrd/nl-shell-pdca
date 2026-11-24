# Adversarial review — issue_196 (ast-policy-gate-shell-layer)

Evidence re-run: I installed the pinned `tree-sitter==0.26.0` and `tree-sitter-bash==0.25.1` in a scratch venv and ran `tests/test_policy_gate.py` against `$PDCA_TARGET`: 78 passed. The tests import the real `nl_shell.gate` (no copied code), and they check a reason substring, not only the class, so the green leg has teeth. The C4 red leg (`gate-logs/C4-verify.log`) is 78 `ModuleNotFoundError` failures. That is expected for a new package, but it only shows the module is missing. It says nothing per case. One fd case the tests miss is below.

- NEEDS-HUMAN [impl] — **A move-descriptor redirect to fd 3 or higher is not rejected.** At `src/nl_shell/gate/parse.py:466-476`, a `>&` target that is not all digits and not `-` is treated as "`>&file`", so `>&3-` and `1>&3-` only get "output redirection" (mutating, `rejected=False`). In bash, `[n]>&digit-` *moves* descriptor `digit` onto `n`, so the command writes to fd 3. I confirmed this with real bash: `exec 3>f; echo via-move >&3-` writes to `f`. Probe results: `classify("echo hi >&3-")` gives `mutating False ["output redirection: '>&3-'", ...]`, and the same for `1>&3-`. This breaks the brief's §5 rule ("a descriptor the gate cannot prove is below 3 is rejected"), which row 25 (`echo hi >&3`) exists to enforce. The `<&3-` form is rejected, but only because it falls into the `else` branch at `:478`. Fix: when the target matches `^\d+-$`, check the digits with `_below_three`. Add `>&3-` and `1>&3-` to `test_descriptor_not_provably_below_three_is_rejected` (`tests/test_policy_gate.py:272`).
- NEEDS-HUMAN [human] — **Assignments the parser does not give a `variable_assignment` node skip §3 and §5.** The brief limits the rule to `variable_assignment` nodes (`parse.py:701-711`). But the forms below are syntax the shell layer walks, not commands, so #197's command layer will never see them as invocations. `for` and `expansion` are plain pass-through containers (`parse.py:736-749`):
  - `echo ${SUDO_PROMPT=x}` gives `mutating False`.
  - `for SUDO_PROMPT in x; do :; done` gives `mutating False`.
  - `for PATH in x; do :; done`, `select PATH in a; ...`, `: ${IFS:=x}` and `(( PATH=1 ))` all give mutating, not session-altering.

  The brief's hand-off list for #197 (`export "PATH"=x`, `read`, `printf -v`) names only command-level forms. A human should decide whether these shell-level forms belong to this child or get added to #197's scope, so they don't fall between the two.
- NEEDS-HUMAN [impl] — **The work budget does not cover parsing or the named-fd scan.** `parse.py:240` parses the whole text before any budget is spent. `parse.py:441-443` copies and regex-searches the entire source prefix (`self.source[: node.start_byte]`) for every redirect, which is quadratic. Measured: a 6 MB proposal takes 7.7 s before ending in "could not class". A 2 MB word followed by 6000 `>x` takes 3.1 s. The brief says the budget is "a total-work budget across the whole classification". Fix: cap the input length up front (decision C), and look only at a bounded window of bytes (for example the last 256) before the redirect.
- NEEDS-HUMAN [human] — **T2 is unverifiable: no threat-model update.** `gate-logs/T2-threat-model.log` shows the whole new gate package changed with no edit to `.oss-scanner/threat_model.md`. The brief cites that model's Critical row (`:296`) and High row (`:303`) as the invariant this work restores. A human should decide whether the model needs a new row now (the gate as a parse-differential surface: tree-sitter vs bash, see `cat <<E; rm x` below) or only when #78 wires the gate into the REPL.
- Not a refutation, just noted: some valid bash parses as unparseable in tree-sitter, for example `cat <<E; rm x\nx\nE` gives "unparseable". That fails closed (mutating), so it is safe. It is the kind of mismatch the differential test in #191 should catch.
- I tried to refute these and could not:
  - `classify` never raises. `None`, `bytes` and `int` inputs, a NUL byte, a lone surrogate, and 1000-deep nesting all fail closed to privileged or are rejected.
  - No result is `read-only`.
  - SUDO_ assignments are rejected inside `declare`, `readonly` and `+=` forms.
  - Descriptor 3 or higher is rejected on here-docs, here-strings, function definitions, compound statements, `time` and `!`, and in `>& 3`, `>&03`, `>&'3'`, `>&$((3))` and `{fd}` forms.
  - `>/dev/null` stays exempt only for the exact literal path.
  - The here-doc pipe stdin case (`cat <<E | sudo tee /x`) is handled.

<!-- pdca:leaf-complete -->

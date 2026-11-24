# Security review (advisory): ast-policy-gate-shell-layer, round 5

**Attacker-reachable inputs this diff touches:** the command text given to `nl_shell.gate.classify`. That means the model's proposal (threat model item 5) and, through it, anything item 1–3 text steered it to write. Typed input counts too (trusted, but it goes through the same parser). The gate is not wired to the REPL yet (#78). The command layer is a stub that makes every command at least `mutating`, so nothing can be classed `read-only` today. Each finding is therefore rated by what it would allow once #197/#198 land.

**Verdict: no new finding.** Each round-4 fix holds against real bash, and the patch's tests cover the attacker-reachable forms.

How I checked: I ran the patched gate with the pinned `tree-sitter==0.26.0` / `tree-sitter-bash==0.25.1`, using an interpreter that has them. Each probe was compared against real GNU bash 5.3.9. The probe scripts are in this leaf's `probe/` directory.

## What I checked

- **Two here-documents on one line, and body order** (`src/nl_shell/gate/parse.py:720-734`, `:749-754`, `:1014-1020`, `:1053-1065`). I ran a differential test with 25 here-document shapes × 6 joiners (`;`, `&`, `&&`, `||`, `|`, newline): 150 scripts. Shapes included braces, subshells, `if`/`while`/`for`/`case` bodies, `$(cat <<B …)` inside A's line, backquotes, `[[ $(…) ]]`, functions, quoted delimiters and `<<-`. Each script hides `touch PWN` on a line that bash runs. A bypass would be: bash creates `PWN`, the gate does not fail closed, and no invocation has `touch` as its command word. **No bypass found.** 34 scripts ran the hidden line and the gate failed closed; 14 ran it and the gate recorded the `touch` invocation. 31 more edge cases also gave no bypass: CRLF delimiters, `E\⏎`, unbalanced `$(`, `${`, `$((` or a backquote across the delimiter line, `<<-` with a space before the tab, `cat <<E <<E`, `$x`/`${x}` in the delimiter, substitutions in the delimiter, `$[$(…)]` and `\$(x)$(…)` in the body.
- **Extglob, glob and brace targets; `/proc/<pid>/cwd`; `/proc/<pid>/root`** (`parse.py:460-469`, `:557-583`, `:756-773`). I ran 50 candidate redirections under `bash -O extglob` with fd 3 open to a file, and checked whether `PWN` reached fd 3. Every write through a literal target was rejected. That covers `>/dev/fd/!(0|1|2|4|…)`, `3@()`, `3*()`, `3?()`, `3+()`, `[3]`, `/dev/f[d]/3`, `\3`, `"3"`, `/de""v/fd/3`, the `./`, `//` and `..` forms through `/sys`, `/run`, `/var/run`, `/proc/self/fdinfo` and `/proc/self/map_files`, and `>|`, `&>>`, `<>`, `2>…>&2`, and `exec 1>/dev/fd/3`. The only misses are the documented ones below.
- **Parse budget** (`parse.py:355-379`). I timed inputs at the 64 KiB cap. `$[`, `a=(`, `${` and `a=(b=(…` each stopped at about 0.51 s with "could not class: parse budget exceeded". 20 other shapes (`$((`, `[[`, `((`, `"$(`, `<(`, a run of backquotes, `${a[`, `${x/`, many redirections, many here-documents, many continuations, many words, long `case`, nested `{`/`for`) finished in 0.02–0.68 s, either classed or failed closed. After a cancelled parse, `classify("echo hi >&3")` and `classify("ls")` give the same results as before, so `parser.reset()` (`:375`) leaves no state behind.
- **Tests.** The attacker forms are in the tests: the joined here-documents (`tests/test_policy_gate.py:690-693`), the order check on its own with the nesting check disabled (`:702-717`), extglob, `/proc/*/cwd` and `/proc/*/root` (`:307-324`), and the slow-parse timing (`:783-797`). The friendly-path counter-cases are there too (`:351-360`), so the new rules are not just over-rejecting.

## Notes (known gaps, not findings)

- Literal-looking redirections the gate still lets through without rejecting, all as documented. Each one wrote to fd 3 in real bash. Only these two kinds are left:
  - **Non-literal targets.** `echo PWN >/proc/$$/fd/3`, `>/proc/self/task/$BASHPID/fd/3`, `>${X:-/dev/fd/3}`, `>/dev/fd/${X:-3}`; also `>/dev/fd/$'3'` and `>~/../../dev/fd/3`. These are classed `mutating` with "output redirection" and `rejected=False`. The patch's threat-model text says so (`.oss-scanner/threat_model.md:130-131`, "A target the gate cannot read (`>$F`) … is not rejected by this rule"), and the human explicitly left this scope question open this round. I'm not re-raising it. One input for that decision: `/proc/$$/fd/3` is a short, natural form a steered model could produce, and it needs no unusual quoting.
  - **`eval 'echo PWN >&3'`**, which also writes to fd 3. That is command-layer meaning (#197), and the stub floors it to `mutating` today.
- **Toolchain.** The target sandbox has no `tree_sitter`. I ran the probes with the pdca checkout's existing virtualenv interpreter, which has the exact pinned versions. All `path:line` citations are on the target source at `$PDCA_TARGET`.

No NEEDS-HUMAN items from this review.

<!-- pdca:leaf-complete -->

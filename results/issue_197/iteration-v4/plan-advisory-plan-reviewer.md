Bash was unavailable in this run (every command failed with `apply-seccomp: … Permission denied`). I did the review with Read, Grep and Glob only.

# Plan review: issue 197 / ast-policy-gate-command-engine (pass 4, split)

I checked these against the target source and they hold: the `rules.py:26-28` stub, `__init__.py:31` / `:143-157` / `:159-210` / `:196` / `:229-244`, `parse.py:40` (`MAX_WORK = 4096`), `:516`, `:526-528`, `:1070`, `targets.py:28`, `:153`, `:249`, and the threat-model "still stubs" text at `:194`. `Depends on: 196` resolves (`dependency-state.json`: exists, COMPLETE). The faults below are in how the pass-4 split relates to the success criterion. The root cause itself holds up.

- NEEDS-HUMAN — **The split has no per-child success criterion, red leg or scope.** brief.md:3-8 says "This brief is split into three children", but the Success criterion (`:156-308`), Falsifiability (`:309-322`) and Scope (`:342-358`) still describe the whole v3 bundle. They are one `tests/test_gate_commands.py` with groups for classes 1–7, budget, B and C. The Split plan (`:424-456`) assigns classes to A/B/C. It does not say which test functions each child adds, what each child's red-leg claim is, or which production hunks each child's C4 reverts. Child B's and C's red legs revert only their own hunks over a predecessor that already has an engine. "on the stub … comes out `mutating`" (`:313-316`) is then false for B and C: their "before" state is A's or B's engine, not the stub. Each child needs its own criterion, red-leg statement and file list. Otherwise every Check for B or C is judged against a falsifiability claim that no longer applies.

- NEEDS-HUMAN — **Child A's assigned groups contain cases that only B's recursion or C's class 5/6 can turn green.** The split says "A needs no recursion" and "A classes every one of them [text effects] as decision B" (`:437-439`). A still owns these cases:
  - Class 1 (`:167-171`): `sg adm -c 'sudo -i'` and `busybox sh -c 'sudo -i'` must be rejected "by recursion", and `at now <<<'sudo rm -rf /'` must be `privileged` "classed by recursion". Under decision B alone these are `destructive` and not rejected.
  - Class 2 (`:188-191`): `getopts -- x SUDO_PROMPT` and `wait -p SUDO_PROMPT` rejected. These are class 5 protected variables, owned by C (`:451-452`). `mapfile -C 'sudo -i' -c 1 a < f` rejected is class 6 stored code plus recursion.
  - §4 wrappers (`:250-257`): `bash -c` and `sh -c` "take the inner class", and `script -c 'sudo -i'` must be `privileged` and rejected. These are `runs-text`, so A can only give `destructive`.
  - A's Falsifiability sample uses `getopts -- x SUDO_PROMPT` as its class-2 representative (`:313-314`). That case is not A's work.

  A cannot pass its own groups as written. Move these cases to B/C, or state A's expected interim class for them.

- NEEDS-HUMAN — **Decision B′ has no test case.** Pass 4 adds B′ (`:52-61`): `bash -c "sudo -i $x"`, `eval "sudo -S true${x:-}"`, `trap "sudo -i $x" EXIT`, `alias ls="sudo -i $x"` and `PROMPT_COMMAND="sudo -i $x"` are rejected as proposals. Expansion in the command word or unparsable text with holes gets decision B only. None of these appear in the Success criterion. The only Decision B group case is `bash -c "$v"` → `destructive` (`:271`). Today B′ is unverifiable, and nothing would catch its absence. That is the regression B′ exists to close ("`sudo -S` … cannot hide", `:60`). Add B′ cases to child B (and C for the trap/alias/PROMPT_COMMAND forms), plus negatives (`"sud${x}o -i"` → B only, not rejected).

- NEEDS-HUMAN — **The v3 findings are listed but have no expected results.** brief.md:7-8 says pass 4 "adds … the v3 review findings as regressions in the child that owns their class". Yet the findings appear only as prose in the Split plan (`:439-441`, `:445-450`, `:453-456`). None of these is in the Success criterion with a class, reason or proposal/typed origin: `$'\x73udo' -i`, `foo $'\x73udo'`, `unshare <<<'sudo -i'`, `echo 'rm -rf ~' | unshare`, `fc -e`, `[ -v 'a[$(…)]' ]`, `bash -c '"$@"' _ "$v"`, `declare -a PROMPT_COMMAND='("sudo -i")'`, `declare -n r='x[$(sudo -i)]'; r=1`, `BASH_FUNC_<name>%%`. Some are stated as decision B, but "rejected" vs "at least destructive" is not stated for most. A Check reviewer cannot falsify them.

- NEEDS-HUMAN — **The tracker's work-budget criterion was quietly weakened.** The issue body (notes.json) says the nine-deep `{ bash;bash;bash;bash; } <<'E0'` case "classifies in under one second". The brief replaces that with "a loose 10 s timeout that only guards against a hang" (`:277-279`). It does not say this departs from the tracker or why. The human should accept the relaxation explicitly, or the brief should keep a tighter bound.

- NEEDS-HUMAN — **Spec and threat-model text is shared across a three-child chain with no split.** Scope (`:152-155`, `:357`) has one bundle write "the command table, decisions A–C, the seven class rules and the class-7 accepted gap". It also writes B′ "as part of §4.1" (`:60-61`). All three children edit the same spec and threat-model paragraph (`:427-429`), but the brief does not say which child writes which section. If A lands the full §4.1, the spec claims B/B′ protections (and the threat-model "cannot hide" claim) before they exist on `main`. Say which spec sections each child writes, and that A's text must not claim recursion or B′.

- NEEDS-HUMAN — **The scope is far beyond the tracker issue, and the second change is not called out.** The issue body's scope lists `rules.py`, a loader, `commands.toml`, vector rows, spec/threat-model text and the test. It names no `parse.py` change, no inventory harvesting and no classes 3–6. The brief adds:
  - the `parse.py` `shell_layer(budget=)` seam (`:46-51`, `:354-356`);
  - a restructure of `__init__._classify` for recursion (`:351-353`);
  - `scripts/harvest_inventory.py` plus `inventory.toml` (`:136-150`), a host-scanning tool.

  The human approved the split, but the tracker issue #197 still describes the smaller scope. The children need their own tracker entries (they have no ids yet; the brief gives none), or the issue body should be updated. Otherwise Check's "matches the issue" reading has nothing to anchor it.

- NEEDS-HUMAN — **One citation has drifted (minor, but "cite path:line for every change" is required).** brief.md:349-350 cites `Invocation` "already carries `assignments` (`parse.py:805`)". On the target, the field is at `src/nl_shell/gate/parse.py:171`. `_declared` is at `:816`, not `:813`. Fix these so Do's citations are not copied from a wrong anchor.

Tried and not faulted:
- The problem statement matches the target: `rules.py:28` returns `mutating`/"not allowlisted" unconditionally.
- The budget sizing ("alone fits, three together exceed") works with `MAX_WORK = 4096` and about 3000 units per `T`.
- The import-cycle constraint (`__init__.py:31`) is real.
- `Depends on: 196` resolves to a COMPLETE bundle.

> **pdca:** Bash was unavailable to this reviewer. The vendor sandbox could not start on this host, so every Bash call it made failed before running (`apply-seccomp: write /proc/self/setgroups (nested userns is capability-restricted; caller must provide CAP_SYS_ADMIN): Permission denied`) and it ran no commands; this review was delivered without Bash.

<!-- pdca:leaf-complete -->

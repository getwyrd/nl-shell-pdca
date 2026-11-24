Bash was unavailable in this run (every command failed with `apply-seccomp: write /proc/self/setgroups … Permission denied`); this review was done with Read, Grep and Glob only.

# Plan review — ast-policy-gate-command-engine

- NEEDS-HUMAN — **The tracker record is missing, so the problem statement can't be checked against the thread.** The cwd has `brief.md` and `dependency-state.json` only. There is no `notes.json` and no `sources/`. I could not compare the stated defect, the "decisions A–C" or the "v2 regressions" list with any maintainer comment. The brief cites `iteration-v2/check-advisory-adversary.md` as the source of the regression cases, but that file is not in the bundle or under `$PDCA_TARGET`, so none of those cases trace to the record. A human should confirm that the thread asks for this engine and these decisions.

- NEEDS-HUMAN — **The prerequisite is not merged, and the base branch does not have the code the brief edits.** `dependency-state.json` lists `"196": {"declared": "Depends on", "exists": true, "state": "PLANNED"}`. On `eduralph/nl-shell@main` (`$PDCA_TARGET`) there is no `src/nl_shell/gate/` package, no `gate/rules.py` stub, no `tests/test_gate*`, and no `targets/ubuntu-26.04/gate-vectors.toml`. `targets/ubuntu-26.04/` holds only `target.toml`, `sensitive.toml` and `prompts/`. The Reproduction ("with child-1 merged, `classify("rm -rf build")` gives `mutating`") and the red leg ("leaving child-1's stub") both need code that is not on the target. The bundle should either wait for #196 to land or be declared `Stacks on: 196` with #196's branch as its base. As written, Do starts on `main` with nothing to replace.

- NEEDS-HUMAN — **Decision C is used but never defined, so its cases can't be verified.** The goal says "Write … decisions A–C into the spec", but only A and B get a definition. C shows up only by reference, and the references disagree. The work-budget case says the result is "never below `mutating` (decision C if the budget runs out)". The ten-nested-`env` case says it is "`privileged` and rejected (through the inner command or decision C)". The missing-`commands.toml` case says only "fails closed (decision C)". Is the outcome `mutating`, `destructive` or rejected? What is its reason string? Without those, the budget, missing-file and invalid-file cases have no expected value.

- NEEDS-HUMAN — **The falsifiability rule contradicts itself and fails for some cases.**
  (a) "Every case asserts … that the reason is not 'could not class'" can't hold for the cases that are supposed to end in decision C (missing or invalid `commands.toml`, budget exhaustion, the ten-`env` case "through … decision C"). Presumably C's reason is something like "could not class", though C has no defined reason (finding above).
  (b) Several cases expect exactly what the stub already returns, so they pass on the red leg. The Decision A cases (rows 8, 10, 11, 27, `tar --to-command=sh -xf a.tar`, `ssh -o ProxyCommand=sh h`) are specified as "`mutating` 'not allowlisted'". That is the stub's output by the brief's own words ("every command is `mutating` / 'not allowlisted'"). `bash -c 'true'` "is not raised by decision B" also passes on the stub. So "stub results … fail every case" is false. Either these cases go into a separate negative or regression group, or they need an assertion the stub can't meet.

- NEEDS-HUMAN — **Scope: this is several logical changes, not one fix.** "Scope (one logical fix)" covers:
  1. a new data format plus a loader;
  2. a generic argv-grammar engine with nine effect kinds;
  3. decision A, a new rule that raises any opaque command whose argument word names an `elevates` or `destroys` row, and also rejects such proposals;
  4. decision B, a recursive classifier for unreadable or literal code;
  5. decision C plus a work budget with a timing requirement;
  6. new §3/§5 coverage for `sets-variable` forms (`read`, `mapfile`, `getopts`, `printf -v`, `declare -n`, `let`);
  7. a fixed-load-location hardening requirement;
  8. spec and threat-model edits.

  Decisions A and B, and the `sets-variable` extension to §5, add rules the current spec doesn't have. §5 (`docs/design/specs/policy-gate/v1.md:124-135`) rejects only the forms it lists, and `foo sudo x` is not among them. Spec Versioning (`v1.md:238-241`) requires each of these to be reviewed by a human. Splitting at least "engine + rows for existing §3–§5" from "new decisions A/B/C" would make each review surface checkable.

- NEEDS-HUMAN — **The brief's `command` exception is narrower than the spec it says it implements.** The brief has "`command` (but not `command -v`)". Spec §3 (`v1.md:101`) says "`command` (except `command -v`/`-V`)". As written, the brief would class `command -V` as `session-altering`, which also conflicts with "raises only … per spec". The brief should say `-v`/`-V`.

- NEEDS-HUMAN — **"Fixed load location" misstates the root, and its test can't cover the claim.** The brief calls it "the package's own `targets/<id>/` folder". `src/nl_shell/targets.py:27-28` says `TARGETS_ROOT = Path(__file__).resolve().parents[2] / "targets"` with the comment "Not packaged yet (#48, #50)". That is the repository checkout, not the package. The claim "No env variable, cwd, `$HOME`, config or session value can point it elsewhere" is universal, but the test samples only one cwd file and "environment variables naming another file". The criterion should name the exact variables tested, or be stated as "the loader takes no path parameter other than `TARGETS_ROOT`", which a reviewer can check at `path:line`. The other citations resolve: `targets.py:153` (the `is_relative_to` refusal), threat model `:54` (code running as the user is out of scope), `:296`/`:299`/`:303`, and `failure_classes.py:199` `is_privileged`.

- NEEDS-HUMAN — **The work-budget criterion is a wall-clock assertion.** "Classifies in under one second" depends on the host, and so does the "v2 took 5.3 s" baseline. A CI or sandbox host under load can flip it. A deterministic budget measure would be more stable: work units or nodes visited, asserted below a bound, plus a loose timeout as a backstop.

- NEEDS-HUMAN — **Decision A's argument-word rule has a false-positive cost that the brief doesn't address.** "An argument word naming an `elevates` row ⇒ `privileged` and a proposal rejected" applies to any command with no row and no allowlist entry. For example, `make sudo-check` doesn't qualify, but `foo sudo` (an opaque tool taking `sudo` as a plain operand such as a search term or package name) is rejected outright as a model proposal. The brief gives no failure mode for legitimate operands. A human should accept this trade-off explicitly at sign-off, since it adds a rejection rule beyond §5.

> **pdca:** Bash was unavailable to this reviewer. The vendor sandbox could not start on this host, so every Bash call it made failed before running (`apply-seccomp: write /proc/self/setgroups (nested userns is capability-restricted; caller must provide CAP_SYS_ADMIN): Permission denied`) and it ran no commands; this review was delivered without Bash.

<!-- pdca:leaf-complete -->

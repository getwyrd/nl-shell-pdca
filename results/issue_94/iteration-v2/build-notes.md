# Build notes — #94, iteration 1

Base: main, 4d040301a2341590ca9c574b2df1cefe34585000. All target edits are in the supplied PDCA_WORKTREE. No runtime changes, commits, pushes or PR operations.

## Rationale and citations

ADR-0023 is the plan: docs/design/adr/0023-os-targets.md:37–55 defines target data and consumers, :57–71 defines manifest integrity and adapter identity, :73–87 defines exact selection and the first target. docs/design/specs/policy-gate/v1.md:33–49 distinguishes shared procedure from target package data. Neither document is changed.

Changed paths below are under docs/design/architecture/, with line numbers in the patched target worktree:

- 05-building-block-view.md:31–35,60,63–89: add the target component and consumer/status explanation. :95 makes harvesting per target; :109–113 records built consumers without reasserting the stale catch-all planned status. Built evidence is src/nl_shell/targets.py:1–12,27–28,145–169,249–276, src/nl_shell/prompts.py:80–91 and src/nl_shell/reader.py:198–204; gate-vector and command-provider evidence is cited in the brief. Distinguish data/loading from enforcement. Gate ownership/sensitive/allowlist integration and mismatch confirmation are explicitly planned (#12/#190), as required by the carry-forward. Installer, manifests, integrity, adapters, harvest config and eval remain planned. The existing target folder is explicitly not packaged.
- 07-deployment-view.md:15,20,26–43,68–72: distinguish planned packaged runtime data from build-only material and separately downloaded weights. Record manifest contents, install/update-only downloads, SHA-256 verification before use, REPL refusal and adapter binding. Keep both host and package-channel decisions open. Package ownership and reference VM are target-specific.
- 08-crosscutting-concepts.md:35,55–60,112–114,142–146,164–165: target-owned reference provenance, shared gate procedure, scoped examples, target package lookup, per-target execution filtering and Ubuntu-only specifics. Existing taint labels and confirmation/offline requirements remain. Existing uncertainty about System V compatibility remains at :156–157.
- 01-introduction-and-goals.md:16–18,37,44: first-target scope for product, quality goal and users.
- 02-constraints.md:18: scope OS constraint to first/current target.
- 03-context-and-scope.md:20: scope sudo-rs diagram label; history trust row deliberately untouched.
- 04-solution-strategy.md:23,33: train and execute-filter per target, with first-target example.
- 06-runtime-view.md:38–39: qualify the sudo-rs sequence/cache description as ubuntu-26.04.
- 10-quality-risks-glossary.md:28,44,55,58–59,70,72,82,105: target-scoped quality goal/probes, sudo update mitigation, AMD and point-release risks, training definitions/reference VM and sandbox test example. Preserve factual uncertainty about ROCm coverage rather than certifying new facts.
- tests/test_architecture_targets.py:1–62: read real Markdown from this checkout, assert section-local consumer/status and deployment/reference relationships. Missing sections raise useful assertions rather than StopIteration. The gate assertion cannot pass from a policy-gate link alone. Planned model and adapter status is checked in chapter 05 and the planned deployment subsection.

Chapter 09 retains historical milestone names and first-target roadmap descriptions (09-build-order-and-roadmap.md:24–26), as permitted. This is a descriptive consistency patch, not a redesign. I rejected implementing gate/download/model behavior because it is explicitly out of scope, not on an unmeasured cost claim. I narrowed the stale status inventory instead of performing an unrelated code-layout audit.

## Forced refutation and evidence

(a) YES, genuine red: after making the fix, saved the document diff and actually ran `git apply -R` on it, retaining the identical regression file. Ran `/home/eddie/nl-shell/nl-shell-pdca/.venv/bin/python3 -m pytest -q tests/test_architecture_targets.py` from the target root: 3 executed, 3 failed, exit 1 (red.log). Reapplied the diff and ran the same command: 3 passed, exit 0 (green.log). The brief explicitly authorizes this direct instance-pytest docs exception; it is not C4 proof.

(b) YES, production artifact: tests/test_architecture_targets.py:4–8 reads the actual architecture Markdown relative to the test file, with no mock, fixture copy or parallel document implementation. These documents themselves are the changed product; no runtime implementation is claimed.

(c) YES, fault included: the red leg reads the original main documents, including their missing target block/integrity requirements and global reference provenance. Nothing is removed from the fixture to curate out the defect. All three tests execute and fail assertions, not collection/import.

Actual C4 runner: `PDCA_BUNDLE=.../results/issue_94 bash .../engine/scripts/run-verify.sh` exits 77, `PDCA-UNVERIFIABLE: no behavioral production change to revert (test-only or docs-only patch)`. The Plan exception still holds. This is NOT C4 PASS. Human semantic review of every chapter, particularly chapter 10's risks, goal/probe wording, glossary and testing examples, remains required; assertions are limited document evidence.

`git diff --check` passes. Target pyproject.toml contains no formatter/linter configuration; .pre-commit-config.yaml:13–39 configures secret guards, not formatting. Available gitleaks 8.30.1 scans of the changed architecture directory and regression test report no leaks. These scans do not substitute for the unavailable commit-hook runner.

NEEDS-HUMAN external dependency: pre-commit — configured target commit hooks cannot be executed because pre-commit is absent from PATH and the instance .venv; commit-hook readiness remains unverified.
```toml
[[doctor.checks]]
id = "pre-commit"
cmd = "pre-commit --version"
hint = "Install pre-commit==4.7.0 as documented by the target .pre-commit-config.yaml, then run the reviewed target secret-guard hooks."
level = "MISSING"
```

No dependency was replaced with a shim. Human should run the configured hooks and review the full document diff against ADR-0023 and policy-gate/v1 before accepting. No automated check can discharge the architecture-wide semantic criterion.

Additional verification: `python3 -I -m unittest discover -s .github/docs-check -v` completed 6 tests, OK (docs-check.log). This tests the checker itself, not the complete host-docs gate. `git apply --reverse --check patch.diff` succeeds against the final tree, confirming the artifact matches the worktree including the new test.

T3 attempt: `TMPDIR="$PWD/.pdca-run" timeout 120 bash /home/eddie/nl-shell/nl-shell-pdca/engine/scripts/run-suite.sh` exited 124 at the imposed 120-second bound. suite.log shows progress past 75%, with one `F`, but no failure detail or completed summary. Therefore the full suite is NOT reported green, and the origin of that failure is not established. Check must rerun T3 with its configured allowance and inspect the failure; this documentation-only patch does not justify changing unrelated runtime tests. The scratch directory remains harness-owned for cleanup and is excluded from patch.diff. No claim of full committability or completed success-criterion semantic review is made while these checks remain unresolved.

# Adversarial review — issue 77 (teacher-client-dev-teacher-flag)

There is no fix to refute. `patch.diff` is 0 bytes, so this round shipped no code and no test. The "overall: pass" in `check-gates.json` should not be read as acceptance.

- NEEDS-HUMAN [human] — **Empty patch; the gated proof never ran.** `gate-logs/C4-verify.log` shows exit 77, `PDCA-UNVERIFIABLE: bundle has no patch.diff`. No red→green was shown. `tests/test_teacher_client.py` does not exist at `$PDCA_TARGET`, and nothing in `src/` mentions a teacher, an HTTP client or `--dev-teacher`. The argument parser at `src/nl_shell/cli.py:26-33` still only has `--version` and `--target`, so `cli.main(["--dev-teacher", …])` would still exit 2. None of the success-criterion items (a)–(f) is met.

- NEEDS-HUMAN [human] — **The claim `"overall": "pass"` in `check-gates.json` is not earned.** It comes from gates that pass when there is nothing to check. T2 passes with `no patch.diff, nothing to check` (`gate-logs/T2-threat-model.log`), even though the brief touches threat-model items 5, 8 and 11. T3 passes because the old suite (330 tests) still passes on an unchanged worktree (`gate-logs/T3-suite.log`). The one gate that matters, C4, is `unverifiable`, not pass. A human should not sign off on this round as if it delivered the feature.

- NEEDS-HUMAN [human] — **The dependency this bundle needs may be missing from the base, which would explain the empty patch.** The brief says it builds on #16's backend interface, the `proposal/v1` parser/schema and the "no backend configured" reply, and that "if any is not accepted, this bundle is not scheduled." At `$PDCA_TARGET` (HEAD `0771812 pdca-integrate: issue_140`) none of #16's work exists. `src/nl_shell/repl.py:27` still says "the model backend arrives in M0.8". `src/nl_shell/input_modes.py:102` still has the placeholder reply "command proposals arrive in M0.8". There is no schema file and no backend class anywhere under `src/nl_shell/`. #92 (`config.py`, `targets.py`) and the `:status` hook (`src/nl_shell/input_modes.py:77-87`) are present. Either the wave was scheduled before #16 was accepted, or #16 was not folded into the integration branch. The human needs to fix the scheduling and order. Iterating on Do won't help: the brief tells the builder not to invent stand-ins for #16's names.

I tried to refute the evidence, the fix and the verdict. There was no evidence or fix to attack. The only real finding is that the round's "pass" is empty and the base is missing a prerequisite.

<!-- pdca:leaf-complete -->

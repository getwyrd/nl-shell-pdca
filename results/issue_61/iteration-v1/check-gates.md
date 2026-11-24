# Check gates — issue_61

**Overall (gating): pass**

The Check 5/5/1: 5 correctness · 5 conformance · 1 validation.

## Correctness (5)

| Check | Result | Oracle | Rule | Evidence | Gating |
|---|---|---|---|---|---|
| C1 Spec | none | brief.md | — | — | no |
| C2 Reproduction (red pre-fix) | none | (no gate configured) | — | — | no |
| C3 Change | none | patch.diff | — | — | no |
| C4 fix verified: bundle test red pre-fix, green post-fix (pytest) | pass | ./engine/scripts/run-verify.sh | C4-verify | C4 PASS — red without the fix (55 of 55 failed), green with it | yes |
| C5 Causal adequacy | none | reviewer + human sign-off | — | — | no |

## Conformance (5)

| Check | Result | Oracle | Rule | Evidence | Gating |
|---|---|---|---|---|---|
| T1 Structure | none | (no gate configured) | — | — | no |
| T2 security-relevant change also updates the threat model | unverifiable | ./engine/scripts/check-threat-model-touch.sh | T2-threat-model | security-relevant paths changed without a threat-model update: src/nl_shell/backend.py src/nl_shell/reader.py — decide a | no |
| T3 runtime: the whole nl-shell pytest suite on the patched worktree | pass | ./engine/scripts/run-suite.sh | T3-suite | T3 PASS — nl-shell suite green | yes |
| T4 PR body has a user-impact opener + tracker id in both artifacts | deferred | ./scripts/pdca contribcheck | T4-contribution | pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish | yes |
| T5 Judgment | none | reviewer + human sign-off | — | — | no |

## Validation (1)

| Check | Result | Oracle | Rule | Evidence | Gating |
|---|---|---|---|---|---|
| Validation — fitness-to-purpose | none | human at sign-off | — | — | no |

# Check gates — issue_94

**Overall (gating): pass**

The Check 5/5/1: 5 correctness · 5 conformance · 1 validation.

## Correctness (5)

| Check | Result | Oracle | Rule | Evidence | Gating |
|---|---|---|---|---|---|
| C1 Spec | none | brief.md | — | — | no |
| C2 Reproduction (red pre-fix) | none | (no gate configured) | — | — | no |
| C3 Change | none | patch.diff | — | — | no |
| C4 fix verified: bundle test red pre-fix, green post-fix (pytest) | unverifiable | ./engine/scripts/run-verify.sh | C4-verify | no behavioral production change to revert (test-only or docs-only patch) | yes |
| C5 Causal adequacy | none | reviewer + human sign-off | — | — | no |

## Conformance (5)

| Check | Result | Oracle | Rule | Evidence | Gating |
|---|---|---|---|---|---|
| T1 Structure | none | (no gate configured) | — | — | no |
| T2 security-relevant change also updates the threat model | pass | ./engine/scripts/check-threat-model-touch.sh | T2-threat-model | no security-relevant path touched | no |
| T3 runtime: the whole nl-shell pytest suite on the patched worktree | pass | ./engine/scripts/run-suite.sh | T3-suite | T3 PASS — nl-shell suite green | yes |
| T4 PR body has a user-impact opener + tracker id in both artifacts | deferred | ./scripts/pdca contribcheck | T4-contribution | pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish | yes |
| T4 host docs checks: immutability, checker tests, links, and ADR index | pass | bash -o pipefail -c 'set -euo pipefail; python3 -I -m unittest discover -s .github/docs-check -v; index=/tmp/pdca-host-docs-index-$$; test ! -e "$index"; trap "unlink \"$index\" 2>/dev/null || true" EXIT; export GIT_INDEX_FILE=$index; git read-tree HEAD; git apply --cached "$PDCA_BUNDLE/patch.diff"; base=$(git rev-parse HEAD); tree=$(git write-tree); patched=$(printf "pdca host docs\n" | git -c user.name=PDCA -c user.email=pdca@invalid commit-tree "$tree" -p "$base"); git show "${base}:scripts/docs_checks.py" | python3 -I - immutability "$base" "$patched"; git show "${base}:.github/docs-check/docs_links.py" | python3 -I -; git show "${base}:.github/docs-check/adr_index.py" | python3 -I -' | host-docs | adr_index: 28 ADRs, 0 problems | yes |
| T5 Judgment | none | reviewer + human sign-off | — | — | no |

## Validation (1)

| Check | Result | Oracle | Rule | Evidence | Gating |
|---|---|---|---|---|---|
| Validation — fitness-to-purpose | none | human at sign-off | — | — | no |

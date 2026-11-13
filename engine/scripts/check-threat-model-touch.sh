#!/usr/bin/env bash
# Advisory T2 check: a patch that touches nl-shell's security-relevant code or contracts
# should also update .oss-scanner/threat_model.md (the threat model's own rule, and the
# rubric the security-review leaf rates against). Not gating: a change can be security-
# relevant by path without changing the threat model. When the rule isn't met, report
# PDCA-UNVERIFIABLE (exit 77) so it lands in SUMMARY §6 for the human to judge.
set -euo pipefail

BUNDLE="${PDCA_BUNDLE:?run from the driver — \$PDCA_BUNDLE must be set}"
PATCH="$BUNDLE/patch.diff"
[ -s "$PATCH" ] || { echo "PDCA-EVIDENCE: no patch.diff, nothing to check"; exit 0; }

mapfile -t CHANGED < <(git apply --numstat "$PATCH" | awk -F'\t' '{print $3}')

SECURITY=() TOUCHED_TM=0
for p in "${CHANGED[@]}"; do
  case "$p" in
    .oss-scanner/threat_model.md) TOUCHED_TM=1 ;;
    src/nl_shell/*gate*|src/nl_shell/*policy*|src/nl_shell/*pty*|src/nl_shell/*session*| \
    src/nl_shell/*sudo*|src/nl_shell/*passthrough*|src/nl_shell/*taint*|src/nl_shell/*reader*| \
    src/nl_shell/*history*|src/nl_shell/*log*|src/nl_shell/*install*|src/nl_shell/*backend*| \
    src/nl_shell/*teacher*|src/nl_shell/cli.py|src/nl_shell/*failure_class*| \
    src/nl_shell/render.py|src/nl_shell/*charsafety*|targets/*/*.toml| \
    docs/design/specs/policy-gate/*|docs/design/specs/pty-protocol/*| \
    docs/design/specs/reader-schema/*|docs/design/specs/proposal/*)
      SECURITY+=("$p") ;;
  esac
done

if [ "${#SECURITY[@]}" -eq 0 ]; then
  echo "PDCA-EVIDENCE: no security-relevant path touched"
  exit 0
fi
if [ "$TOUCHED_TM" -eq 1 ]; then
  echo "PDCA-EVIDENCE: security-relevant paths touched and the threat model updated: ${SECURITY[*]}"
  exit 0
fi
echo "PDCA-UNVERIFIABLE: security-relevant paths changed without a threat-model update: ${SECURITY[*]} — decide at sign-off whether .oss-scanner/threat_model.md needs a change (new input, moved trust boundary, changed must-hold property)"
exit 77

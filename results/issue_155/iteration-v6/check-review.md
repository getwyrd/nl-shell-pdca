Review #155: add deterministic failure classification from trusted exit status and confirmed command text, with the agreed stateless P1–P5 privilege rule.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The re-plan defines precedence, P1–P5, explicit costs and accepted gaps; implementation is bounded to this slice (brief.md:85; target/.oss-scanner/threat_model.md:190). |
| C2 Reproduction (red pre-fix) | PASS | Frozen execution shows 258 assertion/test failures and one pass with production changes reverted; this establishes missing functionality, not a pre-existing runtime symptom (gate-logs/C4-verify.log:17). |
| C3 Change | PASS | The three affected files match the authorized classifier, tests and Known-gaps scope; no unrelated production edits (target/src/nl_shell/failure_classes.py:1; target/tests/test_failure_classes.py:1; target/.oss-scanner/threat_model.md:190). |
| C4 Verification (red→green) | PASS | Frozen log records 259 green then 258 red failures without collection errors; local rerun stops at missing pytest, so these counts are log evidence, not independently reproduced (gate-logs/C4-verify.log:10). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Fix depth-sensitive alias memoization: a cached shallow false bypasses the required over-eight-depth privilege result, enabling correction and reader eligibility; directly reproduced below (target/src/nl_shell/failure_classes.py:223). |
| T1 Structure | PASS | Trusted-result classification, privilege checks and injected package lookup are separated without introducing a shell scanner (target/src/nl_shell/failure_classes.py:118; target/src/nl_shell/failure_classes.py:184). |
| T2 Shape | PASS | Direct inspection confirms the classifier bullet documents all four accepted gap types; the frozen scanner merely reports no matched security path, so it alone does not establish coverage (target/.oss-scanner/threat_model.md:190; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen full-suite execution reports 911 passes and one forkpty warning; local pytest is absent, so no independent suite rerun is claimed (gate-logs/T3-suite.log:30). |
| T4 Contribution | N/A | Contribution artifacts are absent by design; substantive audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm path-based merged and closed/rejected prior-art coverage and choose the publish base while #140 remains unmerged — this sandbox has one synthetic base commit and cannot substantiate the brief's remote-history claim (brief.md:76; brief.md:35). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the documented false positives and four classes of privilege misses until #12 — passing rule tables does not establish the broader password/output isolation promise (target/.oss-scanner/threat_model.md:190). |

Independent finding: alias-depth memoization

`target/src/nl_shell/failure_classes.py:223` returns a memoized false before checking depth at line 225. Even moving that check earlier would not account for the remaining length of an already cached multi-alias tail. Cache enough information to preserve the full depth rule, and add order-sensitive shared-tail coverage while retaining the linear-work bound.

Executed directly against the patched target, using real `Snapshot`, `CommandResult`, and `classify` (no substitute modules):

```python
from nl_shell.failure_classes import classify
from nl_shell.session import CommandResult
from nl_shell.pty_protocol import Snapshot
aliases = ''.join(f"alias a{n}='a{n+1}'\n" for n in range(8)) + "alias a8='ls'\n"
snapshot = Snapshot(1, (), aliases, '', '', '', '/bin', 0, '', '')
result = CommandResult(1, True, 1, (1,), b'', False, snapshot, False)
for command in ('a0', 'a8 a0', 'a0 a8'):
    f = classify(result, command)
    print(command, f.kind.value, f.offer_correction, f.to_reader)
```

Run with `PYTHONPATH=src python3` from the target root. Observed:

```text
a0 privilege False False
a8 a0 other True True
a0 a8 privilege False False
```

P5 checks every piece and requires chains over eight deep to count as privileged; all three inputs contain the same nine-alias chain. This is an implementation defect within the agreed rule, not an accepted text-only gap.

Verification limits: `python3 -m pytest tests/test_failure_classes.py -q` returned `No module named pytest`. Therefore no stash/revert red→green or whole-suite rerun was attempted after that failed prerequisite. All four frozen gate logs were read; wrappers are instance-scoped and unavailable here. `git diff --check` produced no whitespace findings. The unrelated docs checker requires explicit BASE/HEAD arguments and was not a gate for this patch. The target includes the required session types and is usable, not stale. No production source was modified. No capability-probe/load-time symptom guard was introduced. Prior-art `git log --all -- <both affected Python paths>` returned no entries, but this single-commit snapshot cannot independently verify merged history or closed/rejected remote work; the brief does record rejected iterations v1–v5.

<!-- pdca:leaf-complete -->

Review #155: add deterministic failure classification from trusted command results, suppressing correction and reader access for privileged commands.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The bounded text-only contract states precedence, accepted misses, display safety and injected lookup behavior; the necessary result fields exist at target/src/nl_shell/session.py:375 (brief.md:15, brief.md:40). |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence demonstrates the missing functionality: 288 failures and one intentional ASCII self-check pass, with no collection/setup errors (gate-logs/C4-verify.log:7312); local pytest is unavailable. |
| C3 Change | PASS | The three affected paths match the authorized module/test/threat-model scope; trusted output remains excluded and reader eligibility is explicitly qualified (target/src/nl_shell/failure_classes.py:18, target/src/nl_shell/failure_classes.py:605; patch.diff:1). |
| C4 Verification (red→green) | PASS | The captured gate shows 289 green tests and 288 red failures after production reversal; this verifies the existing tests, not the newly discovered bypass (gate-logs/C4-verify.log:16, gate-logs/C4-verify.log:7312). |
| C5 Causal adequacy | NEEDS-HUMAN [impl] | Preserve nested substitution quoting and add a regression: a quoted hash hides a literal privilege word, enabling correction and reader access outside the documented gaps (target/src/nl_shell/failure_classes.py:232, target/src/nl_shell/failure_classes.py:200, target/src/nl_shell/failure_classes.py:488); independently reproduced below. |
| T1 Structure | PASS | The implementation separates scanning, privilege checks, unresolved-word lookup and result construction; alias and re-split depth are capped rather than implementing shell expansion (target/src/nl_shell/failure_classes.py:73, target/src/nl_shell/failure_classes.py:465, target/src/nl_shell/failure_classes.py:492). |
| T2 Shape | PASS | Independently checked syntax, ASCII test bytes, forbidden package-data references and the Known-gaps bullet; the scanner log only says no security-relevant path matched, so it supplies no substantive security assurance (target/.oss-scanner/threat_model.md:190; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | The frozen full-suite run reports 941 passing tests with one forkpty warning; local classifier import and direct reproducer ran, but local pytest is missing (gate-logs/T3-suite.log:31; target/tests/test_failure_classes.py:710). |
| T4 Contribution | N/A | Contribution artifacts are absent by design; their substantive audit must run at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm affected-path merged/closed/rejected prior-art checks and choose publication ordering for unmerged prerequisite #140/PR #146; the brief records the checks, but this flattened single-commit target cannot independently establish remote history or prerequisite discharge (brief.md:37, brief.md:61). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept the remaining text-only misses and deliberate over-matching, including the quoted-word re-split policy, before shipping; these trade correction availability against privileged-output protection (target/.oss-scanner/threat_model.md:190; brief.md:70, brief.md:77). |

Independent finding — high impact, builder-fixable:

At status 1 with `ran=True` and an empty alias/function snapshot, classify the confirmed text:

```bash
echo "$(echo "#"; sudo x)"; false
```

The actual module returned `FailureClass.OTHER`, `offer_correction=True`, `to_reader=True`. Its first scan produces the word `$(echo #; sudo x)` with the inner quotes removed (target/src/nl_shell/failure_classes.py:232). Re-splitting interprets that hash as a comment (target/src/nl_shell/failure_classes.py:200), discarding the literal `sudo`. This violates literal any-word rule 1a, rather than exercising the accepted expansion-in-argument gap.

For a safe execution check, I ran Bash with a locally defined `sudo() { printf 'PRIVILEGE_WORD_REACHED\n'; return 1; }` followed by the exact command above. Bash exited 1 and printed `#\nPRIVILEGE_WORD_REACHED\n`: the literal command is reachable. No real privilege executable ran. Preserve the nested quote/substitution structure when scanning, and add this case as a regression asserting privilege, no correction offer and no reader access. The marker function establishes shell parsing only; classification was exercised separately using the real `CommandResult` and `Snapshot` classes with no stubs.

Verification limits: `python3 -m pytest tests/test_failure_classes.py -q` failed locally because pytest is not installed. Accordingly, I did not stash the production change for an unusable local pytest replay; red/green and full-suite verdicts rely on the complete captured gate outputs. Both changed Python files compiled through Python's built-in `compile`; the source exclusions, ASCII bytes and threat-model checks passed independently. The target contains the expected prerequisite fields and is not stale. `git log --all` by affected path exposes only the harness's single synthetic base commit, so it cannot corroborate closed/rejected remote work. No INTEGRATION.md is present in the supplied target or input bundle to enumerate additional project-specific human-only checks.

<!-- pdca:leaf-complete -->

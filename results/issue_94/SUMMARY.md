# Result — issue 94 / architecture-os-targets

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: The living architecture still describes OS-specific reference data, deployment and Ubuntu 26.04 behavior as global, omits the target-folder building block, and omits model-manifest integrity and adapter compatibility requirements already specified by ADR-0023.
- Success criterion: Architecture chapters 05, 07 and 08 describe targets/<id>/ and its consumers with accurate built/planned status, per-target reference VM/harvest, intended shipped target runtime files, install/update-only weight downloads and SHA-256 verification against model.toml, REPL rejection of mismatched weights, and personalization adapters bound to target plus base-weight hash; they retain both unresolved distribution decisions (the weights' URL host in model.toml and the package distribution channel), and every architecture chapter scopes OS-specific details to the relevant target rather than treating them as universal. Document assertions pass and human review confirms agreement with ADR-0023 and policy-gate/v1 without changing their requirements.
- Repo + branch target: getwyrd/nl-shell @ main
- Scope (one logical fix) / out of scope: Remove global OS assumptions from the living architecture, with substantive target/manifest updates in chapters 05/07/08, target-consumer status corrections in §5.3, and narrowly related OS-scoping corrections elsewhere in architecture/. Preserve both open distribution questions. Out of scope: implementing or changing runtime target selection, the gate, model loading, downloads, packaging, harvesting or adapters; adding another target or shell; changing immutable ADRs, normative specs, frozen docs/plan.md or milestone commitments; unrelated architecture cleanup and history-retrieval behavior. §5.3's broad stale status row may be split only as needed to describe existing target consumers accurately; no general code-layout inventory refresh is required.

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: likely-fix
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): unverifiable — no behavioral production change to revert (test-only or docs-only patch)
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — no security-relevant path touched
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T4 host docs checks: immutability, checker tests, links, and ADR index: pass — adr_index: 28 ADRs, 0 problems
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Task under review: issue #94. Make the living architecture (chapters 01–10) match ADR-0023. That means adding the `targets/<id>/` building block and its consumers with accurate built/planned status, describing per-target reference VMs, shipped target files, model.toml SHA-256 integrity, REPL refusal on hash mismatch and adapters keyed to target plus base-weight hash, keeping both [OPEN] distribution questions, and scoping OS-specific text to `ubuntu-26.04`. This is a docs-only change plus `tests/test_architecture_targets.py`.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | Brief gives a clear defect, success criterion and scope, cited to ADR-0023:37–87 and policy-gate/v1:33–49. The prior-art check by affected architecture path is recorded in the brief (merged #58/#83/#85–#87/#201; only closed-unmerged PR is #227, which touches no architecture file). I did not re-run `gh` here. |
| C2 Reproduction (red pre-fix) | PASS | I re-ran it myself. With `git stash` (pre-fix docs, new test kept), `.venv` `python -m pytest -q tests/test_architecture_targets.py` gave 9 failed. It reads the real chapter Markdown, so red means the documented relationships were missing on main. |
| C3 Change | PASS | Only docs/design/architecture/01–08,10 and the new test changed (`git status`, 9 files, +96/−34). No runtime code, ADR, spec or plan.md changed, which matches the brief's scope. host-docs confirms immutability is OK (gate-logs/host-docs.log). |
| C4 Verification (red→green) | NEEDS-HUMAN | Decision owed: confirm that the docs-only exception you accepted in Plan (2026-11-15) still covers this round. The C4 runner exited 77 `PDCA-UNVERIFIABLE` (gate-logs/C4-verify.log), so it produced no automated red→green. My own re-run went 9 fail → 9 pass, and T3 ran the test post-fix. This proves the pinned phrases are present, not that the docs are semantically right, so it must not be read as a C4 PASS. |
| C5 Causal adequacy | PASS | The defect is missing or overclaimed document text, and the patch fixes the text itself. It adds no capability probe or runtime guard, so the symptom-guard smell-test does not fire. All round-4 asks are done: "state capture" is back in the §5.3 planned row (docs/design/architecture/05-building-block-view.md:114), matching src/nl_shell/prompts.py:47. Built claims check out against code: the mismatch warning (src/nl_shell/cli.py:79), command prompts loaded at start-up (cli.py:64), and the reader not called from cli.py/repl.py. |
| T1 Structure | N/A | Docs-only patch plus one test module. No code structure, imports or lifecycle are touched. |
| T2 Shape | PASS | The advisory threat-model gate passed: "no security-relevant path touched" (gate-logs/T2-threat-model.log). The docs keep the taint labels, offline rule and confirm rules (08-crosscutting-concepts.md §8.2/§8.5/§8.9). |
| T3 Runtime | PASS | Full suite green on the patched worktree: 1340 passed, 1 skipped (gate-logs/T3-suite.log). The new test is an ordinary unmarked pytest and runs without env flags. |
| T4 Contribution | PASS | host-docs passed: docs-check unittests 6/6, immutability OK, 82 links / 0 broken, 28 ADRs / 0 problems (gate-logs/host-docs.log). The T4-contribution row is `deferred` (pr-description.md is not drafted yet; it is re-run at publish), so it counts as N/A here and is not a finding. |
| T5 Judgment | PASS | The round-4 test gaps are closed, and I checked by mutation (each restored afterwards). These mutations all turned the suite red (1 failed): REPL start-up changed to "makes every command need confirmation"; §5.3 reader row changed to plain "built"; "state capture" dropped from the planned row; "requirements awaiting implementation" removed in ch07; "PPA" added to the channel question; "not built" removed from the REPL inputs bullet; adapter "awaiting implementation" removed. tests/test_architecture_targets.py:62–98,101–135. |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Decision owed: the human semantic sweep of every architecture chapter against ADR-0023 and policy-gate/v1, which the brief makes human-only and phrase tests cannot discharge. Three carried items are still open. (1) ch07 lists `gate-vectors.toml` as a shipped runtime file (07-deployment-view.md:22). ADR-0023:47 names its consumer as "gate tests", while :121–122 says the gate loads it from the target. Decide which reading the deployment view should follow. (2) §8.5 now says "the active target's package data/query (`dpkg`/`apt` for `ubuntu-26.04`)" (08-crosscutting-concepts.md:114), while the built lookup is `nl_shell.command_provider` over the target's `[command_provider]` data. Is that wording accurate enough? (3) One status rule for "built library, not wired": the reader is shown this way (05:82, 05:113), while PTY session is listed as planned (05:114). Also check that the chapter 10 rows (:55 sudo update mitigation, :58 ROCm, :59 point releases, goal/probe wording, glossary, testing examples) keep their existing factual uncertainty. These matter because the architecture is the reference that later builders and reviewers will treat as the truth about what ships. |

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 94 / architecture-os-targets (round 5)

**Bottom line:** I could not refute the fix. The red→green proof reproduces, the round-4 fixes landed, and no claim I checked contradicts ADR-0023 or the code. What remains is the human-only semantic review the brief already requires, plus the open items carried from round 4.

## What I tried

- **Red→green, re-run by hand.** C4 exited 77 (docs-only, `gate-logs/C4-verify.log`), so I ran `tests/test_architecture_targets.py` with the instance `.venv` pytest against copies of the docs. Against the base-commit docs (`git show HEAD:` of every `docs/design/architecture/*.md`) the result was **9 failed**. Against the patched docs it was **9 passed**. The test reads the real Markdown (`tests/test_architecture_targets.py:9`), so it is not checking a copy that only mirrors production. T3 (`gate-logs/T3-suite.log`: 1340 passed) and host-docs (`gate-logs/host-docs.log`: 0 broken links, immutability OK, ADR index OK) agree. This is still not a C4 PASS. It shows the pinned phrases are present, not that the docs are correct.
- **Built/planned claims vs code.** Each one matches:
  - Start-up loads command prompts: `src/nl_shell/cli.py:64`.
  - A mismatched named target only prints a warning: `cli.py:79`.
  - The reader has `load_prompt` (`reader.py:202`) and uses `command_provider` (`reader.py:44`), but `cli.py` and `repl.py` never call it.
  - The target folder holds only `target.toml`, `sensitive.toml`, `gate-vectors.toml` and `prompts/`.
  - `[command_provider]` is target data (`targets/ubuntu-26.04/target.toml`).
  - State capture and gate integration are still unbuilt (`repl.py:8`).

  I found no overclaim.
- **ADR-0023 conformance.** I checked the consumer table (ADR `:43-50`), manifest fields (`:61-64`), the install path, MUST-verify and MUST-refuse (`:66-68`), install/update-only downloads (`:68-69`), adapter identity (`:70-71`) and exact os-release selection with mismatch → confirm-every-command (`:73-78`). The chapter 05 bullets (`05-building-block-view.md:69-89`) and chapter 07 (`07-deployment-view.md:18-31`) match them without changing any requirement. Both **[OPEN]** questions are kept (`07-deployment-view.md:69-72`), and no channel is named.
- **Leftover unscoped OS wording.** I grepped all architecture chapters for `26.04|sudo-rs|dpkg|apt|systemd|Wayland|uutils|GNOME|Ubuntu`. What remains is either scoped or an allowed example: §8.3 apt examples under the new "examples below use `ubuntu-26.04`" lead-in at `08-crosscutting-concepts.md:55-56`, §6.2 sudo-rs under the new scope line at `06-runtime-view.md:38`, and milestone names at `09-build-order-and-roadmap.md:24,26`, which the brief allows.

## Findings

- `tests/test_architecture_targets.py:31-33`: the test only checks that phrases are present. It cannot catch a sentence that contradicts them. I tested this: appending "Today the REPL already enforces adapter and hash checks." to the adapters bullet at `07-deployment-view.md:31` still gives 9 passed. This is the known limit of a docs-only test, which the brief already accepts ("not … full semantic correctness"). No rebuild is needed. It is why the human semantic sweep cannot be skipped.
- NEEDS-HUMAN [human] — `07-deployment-view.md:34` now scopes the whole serving bullet ("one `llama-server` per user … systemd user service … serving both the command model and the reader (ADR-0018)") to `ubuntu-26.04`. ADR-0023:106-107 says "The REPL, serving, the reader … carry over unchanged". Only the systemd unit is clearly OS-specific. Scoping the per-user server and its socket too could read as "serving is target-specific". The human should decide whether to scope only the systemd user-service clause.
- NEEDS-HUMAN [human] — Carried from round 4 and still open; I add no new evidence beyond this:
  - `07-deployment-view.md:21-22` lists `gate-vectors.toml` as a shipped runtime file. ADR-0023:47 says "gate tests", but :121 says "the gate … loads … `gate-vectors.toml`".
  - `08-crosscutting-concepts.md:114` says "package data/query (`dpkg`/`apt`)". The real lookup is the command-not-found SQLite DB (`target.toml` `[command_provider]`).
  - `05-building-block-view.md:111` marks "PTY session" as *(planned)*, but `src/nl_shell/session.py` is a built library that is not wired into the REPL. That is the same situation as the reader, which the doc calls "built, not yet wired". The two need one rule.
  - The human semantic sweep of every chapter, including chapter 10 `:55`, `:58` and `:59`.
<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory) — issue 94 / architecture-os-targets

**Attacker-reachable inputs touched: none.** The patch changes only Markdown under `docs/design/architecture/` and adds a document-assertion test (`tests/test_architecture_targets.py`) that reads those Markdown files from the repo. No runtime code changes, so no item on the threat model's "Where untrusted input enters" list (command output, model proposals, downloaded weights at install time, training data, and so on) reaches a changed line.

What I checked:

- **The design text for downloaded weights (threat model input 9; Critical: "a tampered model or binary is installed without detection").** The new text in `docs/design/architecture/07-deployment-view.md` (§7.1, "Model integrity (planned)") and `05-building-block-view.md` (the "REPL target inputs" and "Installer" bullets) matches ADR-0023 lines 61–70 (`target/docs/design/adr/0023-os-targets.md:61-70`): SHA-256 verified against `model.toml` before use, the REPL refuses weights whose hash doesn't match, downloads only at install or explicit update, and adapters bound to target plus base-weight hash. The patch removes no integrity, signing or verification wording. The only removed security-adjacent line (`10-quality-risks-glossary.md`, sudo-rs row) is reworded to "target sudo updates (sudo-rs for `ubuntu-26.04`)", which keeps the same check. No weakening.
- **Built vs. planned claims against the code.** The doc says `sensitive.toml` and `model.toml` are not read yet, and that a mismatched named target only warns today. That matches the source: `src/nl_shell/gate/sensitive.py:3` still uses a built-in list until #190, nothing under `src/` reads `model.toml`, and `src/nl_shell/targets.py:32,276` only records `MISMATCH_REASON`. The policy-gate rule ("on a mismatched named target, every command must need confirmation") is kept and correctly marked as planned. So the doc does not tell a reviewer a protection exists when it doesn't.
- **The new test.** It reads fixed repo paths (`Path(__file__).resolve().parents[1] / "docs/design/architecture"`) and does string checks. No untrusted input, no subprocess, no network.
- **Gates.** T2 (threat-model touch) passed with "no security-relevant path touched", and that's correct for a docs-only change. C4 is `unverifiable` because there's no production change to revert, which is expected for a docs-only patch and is not a security problem.

No findings. One note, not a finding: the threat model's component list says "the installer (signed weights, …)" (`target/.oss-scanner/threat_model.md:211`), while ADR-0023 and this patch describe hash checking against a manifest shipped in the package, not a signature. That wording gap is older than this patch and the patch doesn't change it, so I'm not raising it here.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] C4 Verification (red→green) — Decision owed: confirm that the docs-only exception you accepted in Plan (2026-11-15) still covers this round. The C4 runner exited 77 `PDCA-UNVERIFIABLE` (gate-logs/C4-verify.log), so it produced no automated red→green. My own re-run went 9 fail → 9 pass, and T3 ran the test post-fix. This proves the pinned phrases are present, not that the docs are semantically right, so it must not be read as a C4 PASS.
- [x] Validation — fitness-to-purpose — Decision owed: the human semantic sweep of every architecture chapter against ADR-0023 and policy-gate/v1, which the brief makes human-only and phrase tests cannot discharge. Three carried items are still open. (1) ch07 lists `gate-vectors.toml` as a shipped runtime file (07-deployment-view.md:22). ADR-0023:47 names its consumer as "gate tests", while :121–122 says the gate loads it from the target. Decide which reading the deployment view should follow. (2) §8.5 now says "the active target's package data/query (`dpkg`/`apt` for `ubuntu-26.04`)" (08-crosscutting-concepts.md:114), while the built lookup is `nl_shell.command_provider` over the target's `[command_provider]` data. Is that wording accurate enough? (3) One status rule for "built library, not wired": the reader is shown this way (05:82, 05:113), while PTY session is listed as planned (05:114). Also check that the chapter 10 rows (:55 sudo update mitigation, :58 ROCm, :59 point releases, goal/probe wording, glossary, testing examples) keep their existing factual uncertainty. These matter because the architecture is the reference that later builders and reviewers will treat as the truth about what ships.
- [x] `07-deployment-view.md:34` now scopes the whole serving bullet ("one `llama-server` per user … systemd user service … serving both the command model and the reader (ADR-0018)") to `ubuntu-26.04`. ADR-0023:106-107 says "The REPL, serving, the reader … carry over unchanged". Only the systemd unit is clearly OS-specific. Scoping the per-user server and its socket too could read as "serving is target-specific". The human should decide whether to scope only the systemd user-service clause.
- [x] Carried from round 4 and still open; I add no new evidence beyond this:
- [x] C4 fix verified: bundle test red pre-fix, green post-fix (pytest) unverifiable — no behavioral production change to revert (test-only or docs-only patch)
- [x] external dependency: localhost-sockets — sandbox denies AF_INET socket creation; full T3 reader/teacher-client integration cannot be validated here.
- [x] **Chapter 05 coverage leaves out target code that already exists, which pushes Do toward writing "planned" over built code.** Brief item 1 says "Mark not-yet-built pieces as planned". It never says which target consumers are already built. On main, target selection and loading exist: `src/nl_shell/targets.py:1,145,249` (load and select via os-release), `src/nl_shell/os_release.py`, `src/nl_shell/gate/vectors.py:1,49` (loads `targets/<id>/gate-vectors.toml`), `src/nl_shell/prompts.py:89` and `src/nl_shell/reader.py:202` (load from the target folder), with `tests/test_targets.py`. Meanwhile `docs/design/architecture/05-building-block-view.md:71-76` (§5.3) lists only cli/repl/router as built and the gate as "planned". The scope's "unrelated architecture cleanup" exclusion leaves it unclear whether §5.3 may be touched. The brief should state the built-vs-planned status of each consumer: built are target selection, gate vectors, prompts and reader prompt. Planned are `model.toml`, `allowlist.toml`, `harvest.toml`, `eval/`, the installer and packaging; `targets/ubuntu-26.04/` holds only `target.toml`, `sensitive.toml`, `gate-vectors.toml` and `prompts/`, and `targets.py:27` says "Not packaged yet (#48, #50)". It should also say whether the §5.3 rows for target modules are in scope.
- [x] **Narrowing the [OPEN] item can silently drop the open package-distribution decision.** `07-deployment-view.md:51-52` keeps open the "Distribution channel for weights **and package**: GitHub releases, Hugging Face, a PPA, or a mix (M5.4)". The issue and the brief turn this into "the URL host in `model.toml`" (brief Success criterion: "retain the unresolved URL-host distribution decision"). ADR-0023 decides only that weights are referenced by manifest. It does not decide how the package itself is distributed (ADR-0021 leaves packaging to #50). The brief should require the [OPEN] item to keep covering the package channel, with the weights part reworded to the `model.toml` URL host. As written, Do can follow the brief and lose an open question without anyone noticing.
- [x] **The milestone claim does not match the tracker record.** The brief's Milestone line says "as confirmed by the selected issue's tracker milestone". `notes.json` has no milestone field, and the only comment (triage bot) says "The milestone is left to the maintainer." Either cite where "Foundations" was confirmed or mark it as the planner's assumption.
- [x] **The red→green evidence is weak by construction, so human review carries the criterion.** Do writes `tests/test_architecture_targets.py` itself against wording it is about to add, so failing on main is nearly guaranteed and proves little. The clause "every architecture chapter scopes OS-specific details to the relevant target" has no mechanical check at all. The brief acknowledges this (C4 exit 77, human semantic review). Check should still treat the sweep as human-only: chapter 10 also has unqualified OS facts the citation list leaves out (`10-quality-risks-glossary.md:55` "re-verify on sudo-rs updates", `:58` "ROCm doesn't list 26.04", `:59` "26.04 point releases"). Consider adding these to "Supporting scoping sites" so the human checklist is complete.
- [x] size backstop — this slice is behaving oversized: 4 round(s) already spent (threshold 2). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.
- [x] C5 Causal adequacy — The human-only architecture-wide sweep is still owed. The patch removes the cause (missing or unscoped text) and adds no capability probe or guard, so the symptom-guard check does not fire. But the brief requires a human to confirm that every chapter scopes OS facts and agrees with ADR-0023 and policy-gate/v1. That includes ch10 :55 (sudo-rs re-verify), :58 (ROCm/26.04, uncertainty kept), :59 (point releases), the Q7/probe rows and the glossary. I read all of them and found them scoped. Leftover 26.04 mentions are the historical M1/M3 milestone names (`docs/design/architecture/09-build-order-and-roadmap.md:24,26`) and §8.8 content under its new scoped heading (`08-crosscutting-concepts.md:148`). Both are allowed by the brief.
- [x] Two checks remain for a human by design (brief §Check evidence): the semantic OS-scoping sweep of every chapter, and agreement with ADR-0023/policy-gate/v1. "overall: pass" in check-gates.json covers only T3 and host-docs. It does not prove either of these, and C4 is unverifiable by agreement.
- [x] T5 Judgment — Decide whether dropping the §5.3 catch-all row is acceptable. The brief allowed only splitting it. The patch deletes the row (PTY session, policy gate, confirm UI, backend, prefix modes, session log) and adds "Other module statuses are outside this target-consumer inventory" (`05-building-block-view.md:109-113`). That removes a stale "planned" claim, but §5.3 now silently omits built modules such as `session.py` and `backend.py`. Minor point for the same decision: the component diagram's dotted `targets -.-> gate` edge (`:31-34`) has no legend, while the gate's target reads are only planned.
- [x] §5.3 now deletes the catch-all planned row and replaces it with "Other module statuses are outside this target-consumer inventory" (`05-building-block-view.md:113`). The test enforces this (`tests/test_architecture_targets.py:35`, `"Remaining M0 work" not in layout`). The result is a "Code layout" table that leaves out built modules that exist (`gate/parse.py`, `rules.py`, `live.py`, `backend.py`, `session.py`, `input_modes.py`). The table also no longer records anything as planned. The brief allowed splitting the row "only as needed" and said no general refresh is required. Whether dropping the row entirely, rather than narrowing it, is acceptable is a scope call for the human. The `:35` assertion locks in a wording choice made in response to round-1 feedback, not a fact from ADR-0023.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: merged-wider
- Iteration delta (if iterating):
- By / date: Eduard Ralph / 2026-11-14

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 4 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)
- Follow-up (issue 94): architecture wording — scope only the systemd unit in 07 serving bullet; settle whether `gate-vectors.toml` ships; tighten §8.5 lookup wording to `[command_provider]`; one status rule for built-but-unwired modules (PTY session vs reader).

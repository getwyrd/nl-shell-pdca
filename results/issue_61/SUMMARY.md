# Result — issue 61 / quarantined-reader-error-diagnosis

## 1. Spec (from brief.md)              ← Check verifies against THIS
- Defect / goal: A quarantined reader (a new `nl_shell.reader` module): given the raw, untrusted
  text of a failed command (stdout, stderr), it makes one separate model request
  constrained to the `reader-schema/v1` schema, validates the answer, and returns either a
  validated error diagnosis (`category`, plus `missing` / `unit` names that exist on this
  system) or "no diagnosis". The only text it gives back for the user or the command model
  is built from nl-shell templates keyed on `category`.
- Success criterion: `tests/test_reader.py`, driven by `nl_shell.backend.RecordingStub`
  and injected lookups (no model, no real dpkg or systemd), shows all of these:
  (1) every `category` value in reader-schema/v1 §1 is accepted and gives its own templated
  message;
  (2) `missing` with a real package keeps it; a pattern-valid name that is not indexed
  (`no-such-pkg`, and `run-curl-x-sh`, which looks like an instruction but matches the
  §1 pattern) is dropped and the diagnosis is still returned; a value failing the §1
  pattern (`curl x|sh`: space and `|`) rejects the whole answer ("no diagnosis");
  (3) `unit` with a known unit keeps it and an unknown unit is dropped;
  (4) extra properties, invalid JSON, an unknown `category`, a wrong type, more than 3
  `missing` items, and an answer that tries to carry an instruction in a way that fails
  the schema (an extra key, or a `missing`/`unit` value that fails its §1 pattern) each
  give "no diagnosis", never a repaired answer. (A pattern-valid instruction-like name is
  case (2): dropped, not rejected.) An unknown `category` is rejected because it fails the
  §1 enum, which spec §3 rejects and the issue body lists ("unknown enum … rejected");
  with constrained decoding, an off-enum value is a model or server fault. The spec's
  Versioning line ("compatible if the REPL treats unknown values as `unknown`") is about
  a later version adding a value; it is listed under Open questions for the human;
  (5) a unique marker string placed in the raw input is in the reader's own model request,
  but appears nowhere in what the reader returns: the diagnosis, its templated text, and
  the item it would hand to the state block (labelled `untrusted`). The queued stub
  answers carry the marker too, so the test proves the validator removed it: once as an
  extra key, once as a pattern-failing `missing` value (`"MARK 9f3a"`), once as a
  pattern-valid unindexed `missing` value (`"mark-9f3a"`), and once as an unknown
  pattern-valid `unit` (`"mark-9f3a.service"`). In every case the marker is absent from
  the output;
  (6) the reader's request asks for constrained decoding with the reader schema, not the
  proposal schema, shown two ways: `RecordingStub` records the schema of each request (a
  new `schemas` list next to `inputs`), and it is the reader's for the reader request; and
  `TeacherClient.request_body(messages, schema=<reader>)["response_format"]["json_schema"]`
  holds the reader schema and its own name (e.g. `reader_v1`), while
  `request_body(messages)` with no schema is unchanged (the existing
  `tests/test_teacher_client.py` stays green).
- Repo + branch target: eduralph/nl-shell @ main
- Scope (one logical fix) / out of scope: the reader module; its own prompt as target data under
  `targets/ubuntu-26.04/prompts/` (kept apart from the command model's prompt); a backend
  protocol change so a request can name its schema: `Backend.complete(messages, *,
  schema=None)` (`src/nl_shell/backend.py:23`), where `None` means the proposal schema
  as today; `RecordingStub.complete` (`:48`) accepts it and appends it to a new
  `schemas` list (`inputs` keeps its shape, so `tests/test_backend.py`,
  `tests/test_failure_classes.py` and `tests/test_charsafety.py` stay green);
  `TeacherClient.request_body` / `complete` (`src/nl_shell/teacher_client.py:494-514`,
  today hard-wired to `SCHEMA_NAME`/`proposal.SCHEMA`, `:73`) take the same keyword; the
  caller `repl.py:167` is unchanged. Validation of `missing` and `unit` goes through
  lookups the caller passes in (`package_exists`, `command_package` — the caller can pass
  `command_provider.provider_lookup` — and `unit_exists`), which the tests fake. This
  slice adds **no** real dpkg/apt or systemd reader and no new `target.toml` field: those
  come with the wiring (#14/#17), so `targets.py` and its tests are untouched; the per-`category` message templates; and the
  `untrusted` state-block item. Docs: architecture §8.5
  (`docs/design/architecture/08-crosscutting-concepts.md`) points at reader-schema/v1 for the
  schema (it already exists; edit the spec only if the build shows it is wrong). / out of
  scope: wiring the reader into `?why` (#14) or fix-on-failure (#17), and with it the
  issue's done-when "raw output never appears in the command model's prompt (`:context`)
  after the reader is used", which can only be shown once the reader is wired; the PR
  says "Refs #61", not "Closes", and names #14/#17 for that check; building the state
  block (#11); history or the session log (#18); a dedicated reader LoRA (ADR-0017 §6,
  M5); running the reader in a separate OS process. ADR-0017 §5 (which supersedes
  ADR-0007's reader part, and the issue body's older "own process") makes it a separate
  *request* to the model server with no tools, no PTY and no network.

## 2. Disposition claimed               ← sign-off confirms or overrides
- Outcome: new-feature
- Confidence: medium
- Recommendation: (set by Do)

## 3. Correctness (Check — chain)
- C1 Spec: none — brief.md
- C2 Reproduction (red pre-fix): none — (no gate configured)
- C3 Change: none — patch.diff
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (56 of 56 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: pass — security-relevant paths touched and the threat model updated: src/nl_shell/backend.py src/nl_shell/reader.py
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review the quarantined error-diagnosis reader for #61: isolate raw command output in a separate schema-constrained request and return only validated, templated, untrusted diagnoses.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | NEEDS-HUMAN | Confirm rejection of unknown categories for v1 despite the compatibility statement about mapping them to unknown — this determines future-version behavior; target/docs/design/specs/reader-schema/v1.md:54, target/docs/design/specs/reader-schema/v1.md:62. |
| C2 Reproduction (red pre-fix) | PASS | Frozen evidence demonstrates the missing feature with 56 per-test failures and no collection/setup errors; local pytest is unavailable, so this is log-supported rather than independently reproduced (gate-logs/C4-verify.log:14; target/tests/test_reader.py:44). |
| C3 Change | PASS | The changed surfaces fit the agreed standalone reader slice and preserve the proposal-schema default; REPL integration remains outside this slice (target/src/nl_shell/reader.py:244; target/src/nl_shell/teacher_client.py:496; target/.oss-scanner/threat_model.md:38). |
| C4 Verification (red→green) | PASS | Frozen C4 output shows 56 green and 56 red, not merely an asserted status; pytest is absent locally, but independent Python smoke checks passed category handling, filtering, marker isolation, rejection, and complete() schema serialization (gate-logs/C4-verify.log:10; target/src/nl_shell/teacher_client.py:530). |
| C5 Causal adequacy | PASS | Strict rejection and index-backed filtering close the free-text return channel; no capability probe or symptom guard was introduced, and the transport regression now exercises the posted reader schema (target/src/nl_shell/reader.py:275; target/src/nl_shell/reader.py:316; target/tests/test_reader.py:278). |
| T1 Structure | PASS | Schema selection belongs at the backend boundary while reader-specific parsing and target prompt loading remain separate; git diff --check passed (target/src/nl_shell/backend.py:27; target/src/nl_shell/reader.py:202). |
| T2 Shape | PASS | The threat model now explicitly states schema separation, rejection rules, injected lookup obligations, and unwired integration status; frozen scanner confirms the required update (target/.oss-scanner/threat_model.md:35; target/.oss-scanner/threat_model.md:159; gate-logs/T2-threat-model.log:10). |
| T3 Runtime | PASS | Frozen full-suite output records 1157 passed, 1 skipped and a forkpty deprecation warning; local pytest is absent, so no independent full-suite rerun is claimed (gate-logs/T3-suite.log:28; gate-logs/T3-suite.log:34). |
| T4 Contribution | N/A | Contribution artifacts are intentionally absent at Check; substantive contribution audit must rerun at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm prior art by every affected file path across merged history and closed/rejected work — the brief reports reader-path triage only, and this disposable target contains one synthetic base commit, so the broader check cannot be established here (brief.md:117; target/src/nl_shell/backend.py:27; target/src/nl_shell/teacher_client.py:496). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept this standalone, stub-driven boundary as the intended deliverable — real model decoding, real package/systemd lookups, and command-model context isolation after integration are not exercised and remain work for #14/#17; no external dependency is declared for this slice (target/.oss-scanner/threat_model.md:38; target/.oss-scanner/threat_model.md:161; target/tests/test_reader.py:278). |

Evidence limits: `/usr/bin/python3 -m pytest --version` reports `No module named pytest`; therefore no stash/red/pop/green pytest run was attempted. The target was left unchanged. Instance-scoped gate wrappers are unavailable here; their complete frozen logs were read. No INTEGRATION.md was present in the supplied target. The target source matches the reviewed patch; no target-state caveat was found.

Independent checks: `git -C target diff --check` passed. A direct Python smoke run against `target/src` passed all ten categories, indexed package/command retention, unindexed name/unit dropping, raw-marker exclusion, four invalid-answer cases, and reader schema serialization through `TeacherClient.complete()` with captured `_post` bytes. This capture checks serialization only; it does not claim real server constrained decoding. The frozen transport test additionally uses a local HTTP server (target/tests/test_reader.py:278).

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 61 / quarantined-reader-error-diagnosis

Target checked: `$PDCA_TARGET` (patched tree). I could not re-run pytest here (`No module named pytest`), so for C4/T3 I relied on the frozen logs. `gate-logs/C4-verify.log` shows 56/56 green with the fix and 56/56 red without it. Every red test fails on `ModuleNotFoundError` from the per-test `reader()` import, as the brief asked. `gate-logs/T3-suite.log` shows 1157 passed. I probed the production `nl_shell.reader` directly with `python3 -I` instead.

## Findings

- NEEDS-HUMAN [impl] — `src/nl_shell/reader.py:320`: the command half of the `missing` check keeps a name if `command_package` returns *any* name that passes the package-name pattern. It never checks that the providing package is in the index. Spec §2 (`docs/design/specs/reader-schema/v1.md:51-52`) and the brief both say "a command provided by an **indexed** package". Concrete case: with `package_exists=lambda n: False` and `command_package=lambda w: ("ghost-pkg",)`, `validate('{"category":"not-found","missing":["rg"]}', …)` returns `Diagnosis(missing=('rg',))`. `rg` is kept even though `ghost-pkg` is not indexed. The `is_package_name` call does nothing extra, because `provider_lookup` already filters on it (`src/nl_shell/command_provider.py:66`). The test fixture states the weaker reading: `COMMANDS = {"rg": ("ripgrep",)}` while `ripgrep` is not in `PACKAGES` (`tests/test_reader.py:38-39`), and `tests/test_reader.py:98-100` asserts `rg` is kept. So the suite would go red on a spec-faithful fix unless the fixture changes too. Fix: `any(lookups.package_exists(p) for p in lookups.command_package(name))`, add `ripgrep` to `PACKAGES`, and add a test where the provider is not indexed and the name is dropped. The risk is low (the name still comes from local target data, not from the attacker), but it is a spec-conformance gap the reviewer could have missed.
- NEEDS-HUMAN [impl] — `src/nl_shell/reader.py:249-253,308-311`: `diagnose` maps only `BackendError` to `NoDiagnosis`. An exception from an injected lookup goes straight out to the caller. Concrete case: `package_exists` raising `OSError("db locked")` makes `diagnose(...)` raise `OSError`, not return "no diagnosis". The shipped `provider_lookup` catches its own errors, but the real `package_exists` / `unit_exists` (dpkg-query, systemctl) are not written yet (#14/#17), and this module's docstring promises a `Diagnosis` or a `NoDiagnosis`. Either catch errors around the lookups and drop the name (the safe default: "can't confirm" counts as "not found"), or write the "lookups must not raise" rule into the `Lookups` docstring so #14/#17 follows it. Small, builder-fixable.

## Attempted refutations that did not land

- Duplicate keys (`"missing"` twice), a leading BOM, `NaN`, nesting deep enough to hit `RecursionError`, a trailing newline inside a name, and a non-string `category` are all rejected (`reader.py:264-305`). Whitespace around the JSON object is accepted. That is still one JSON object, so not a defect.
- Marker leak (criterion 5): `NoDiagnosis.why` only ever holds fixed strings (`reader.py:276`), and `message()` / `state_item()` are built only from the enum and the kept names. I found no path where answer or input text reaches the output.
- `TeacherClient.complete` dropping `schema=` (the round-1 finding) is now covered end to end by a real HTTP round-trip that checks the posted bytes (`tests/test_reader.py:279-302`). Building the body moved into the worker's `try` (`teacher_client.py:530-531`), so a serialization error is still handed to the caller as before.
- Default path: `request_body(messages)` without a schema still sends `SCHEMA_NAME` / `proposal.SCHEMA` (`teacher_client.py:500-501`). T3 is green, including `test_teacher_client.py`.
- The threat-model text (`.oss-scanner/threat_model.md:37-40,159-165`) matches what the code does, apart from the "indexed package" wording in the first finding.

No finding here argues the approach is wrong. Both are small conformance or robustness fixes inside this diff.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory) — issue 61, quarantined reader

**Attacker-reachable inputs this diff touches:** command output (threat model "Where untrusted input enters" item 1), which goes into the reader's request through `reader.build`/`diagnose`; and the reader's own answer (item 7, model output, item 5), which goes into `reader.validate`. The reader is not wired into `?why` (#14) or fix-on-failure (#17) yet, so today both are reachable only through the module's API and its tests.

## Findings

No finding at any severity on the threat model's scale.

## What I checked

- **Validator, reject-not-repair** (`src/nl_shell/reader.py:406-444`). I ran the patched `validate` on crafted answers. Cyrillic `сurl` and fullwidth `ｃurl` in `missing` are rejected, because the `[a-z0-9]` ranges are ASCII-only. A `unit` with a trailing newline is rejected (`fullmatch`, `:217-218`). JSON nested 100k deep and a 10,000-digit integer give "not valid JSON" with no crash: `RecursionError` and `ValueError` are caught at `:412`. `{"category": true}` is rejected. Duplicate keys and `NaN` are rejected (`:395-403`). A `y`-escaped key decodes to `category` and is accepted. That is correct, since it is the same JSON key. No case got repaired, and none raised.
- **Marked text cannot get through** (`:287-303`). `message()` and `state_item()` are built only from `TEMPLATES` (`:229-240`), the enum value and names that passed both the pattern and a lookup. Both run through `render.escape`. `NoDiagnosis.why` is always a fixed phrase. No `_Reject` text includes an answer value (`:407`), and a `BackendError`'s server text is dropped (`:382-383`; the test is at `tests/test_reader.py` `test_backend_error_gives_no_diagnosis`).
- **Taint label.** `Diagnosis.label` defaults to `untrusted` (`:285`), and `state_item` carries it. Nothing in the diff labels reader output as trusted.
- **Lookups.** No check uses `$PATH`. `_exists` (`:447-451`) uses only the injected lookups and `command_provider.is_package_name`. The existing `provider_lookup` binds the word as an SQL parameter and opens the database read-only (`src/nl_shell/command_provider.py:58-61`).
- **Schema routing** (`src/nl_shell/teacher_client.py:496-520`). `schema=None` still sends `proposal_v1`. `complete()` now builds the body with the caller's schema, and the new test `test_reader_over_teacher_client_posts_the_reader_schema` checks the bytes actually posted. That closes the "reader request silently held to proposal/v1" gap from iteration 1. The request is now built inside the worker thread, as before, so its errors are still mapped the same way.
- **Prompt loading** (`reader.py:333-361`). It uses `yaml.safe_load`, takes exactly two keys and checks the placeholders. `build` splices the output as plain text, not with `str.format`, so braces in attacker output can't reach Python formatting. `test_raw_text_is_spliced_as_is` covers this.
- **Tests cover the attacker side, not only the friendly path.** The marker tests (`tests/test_reader.py`, criterion 5) put the marker in the raw input and in four kinds of hostile answer, and check that it appears in no output. The `REJECTED` table covers instruction-shaped extra keys, `missing` and `unit` values, and pattern failures.

## Notes for the wiring work (#14/#17), not findings against this diff

- The `unit` pattern allows a leading `-`, and `-.mount` is a real systemd unit (accepted above). When the real `unit_exists` is written, it must compare against the `systemctl list-unit-files` output, or pass the name after `--`. It must never pass the name as a bare argument, where `-` would make it an option. The threat model's "local and read-only" rule (`.oss-scanner/threat_model.md:172-174`) does not spell this out.
- `diagnose` passes stdout/stderr through at any size and with no secret filter (`reader.py:364-369`). The threat model says secret-labelled output never goes to the reader (`.oss-scanner/threat_model.md:441-445`), and the state block truncates output. Both rules fall to the caller in #14/#17. If an injected lookup raises an exception, it also goes straight up out of `diagnose` (`:440-444`). The real lookups should return False on error, as `provider_lookup` does.
- In dev-teacher mode the reader request, raw output included, goes to the LAN teacher. This is the existing, documented dev-only gap (threat model item 11), not something new.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [x] C1 Spec — Confirm rejection of unknown categories for v1 despite the compatibility statement about mapping them to unknown — this determines future-version behavior; target/docs/design/specs/reader-schema/v1.md:54, target/docs/design/specs/reader-schema/v1.md:62.
- [x] T5 Judgment — Confirm prior art by every affected file path across merged history and closed/rejected work — the brief reports reader-path triage only, and this disposable target contains one synthetic base commit, so the broader check cannot be established here (brief.md:117; target/src/nl_shell/backend.py:27; target/src/nl_shell/teacher_client.py:496).
- [x] Validation — fitness-to-purpose — Accept this standalone, stub-driven boundary as the intended deliverable — real model decoding, real package/systemd lookups, and command-model context isolation after integration are not exercised and remain work for #14/#17; no external dependency is declared for this slice (target/.oss-scanner/threat_model.md:38; target/.oss-scanner/threat_model.md:161; target/tests/test_reader.py:278).
- [x] `src/nl_shell/reader.py:320`: the command half of the `missing` check keeps a name if `command_package` returns *any* name that passes the package-name pattern. It never checks that the providing package is in the index. Spec §2 (`docs/design/specs/reader-schema/v1.md:51-52`) and the brief both say "a command provided by an **indexed** package". Concrete case: with `package_exists=lambda n: False` and `command_package=lambda w: ("ghost-pkg",)`, `validate('{"category":"not-found","missing":["rg"]}', …)` returns `Diagnosis(missing=('rg',))`. `rg` is kept even though `ghost-pkg` is not indexed. The `is_package_name` call does nothing extra, because `provider_lookup` already filters on it (`src/nl_shell/command_provider.py:66`). The test fixture states the weaker reading: `COMMANDS = {"rg": ("ripgrep",)}` while `ripgrep` is not in `PACKAGES` (`tests/test_reader.py:38-39`), and `tests/test_reader.py:98-100` asserts `rg` is kept. So the suite would go red on a spec-faithful fix unless the fixture changes too. Fix: `any(lookups.package_exists(p) for p in lookups.command_package(name))`, add `ripgrep` to `PACKAGES`, and add a test where the provider is not indexed and the name is dropped. The risk is low (the name still comes from local target data, not from the attacker), but it is a spec-conformance gap the reviewer could have missed.
- [x] `src/nl_shell/reader.py:249-253,308-311`: `diagnose` maps only `BackendError` to `NoDiagnosis`. An exception from an injected lookup goes straight out to the caller. Concrete case: `package_exists` raising `OSError("db locked")` makes `diagnose(...)` raise `OSError`, not return "no diagnosis". The shipped `provider_lookup` catches its own errors, but the real `package_exists` / `unit_exists` (dpkg-query, systemctl) are not written yet (#14/#17), and this module's docstring promises a `Diagnosis` or a `NoDiagnosis`. Either catch errors around the lookups and drop the name (the safe default: "can't confirm" counts as "not found"), or write the "lookups must not raise" rule into the `Lookups` docstring so #14/#17 follows it. Small, builder-fixable.
- [x] **Criterion (6) can't be checked with the stub the brief requires.** The brief says the tests are "driven by `nl_shell.backend.RecordingStub`" (brief:16). It also says criterion (6) must show "the reader's request asks for constrained decoding with the reader schema". But `Backend.complete(self, messages)` (`src/nl_shell/backend.py:23`) has no schema argument. `RecordingStub.inputs` stores only the message tuples (`backend.py:41-42,48-49`). The schema lives only inside `TeacherClient.request_body`, fixed to `SCHEMA_NAME = "proposal_v1"` and `proposal.SCHEMA` (`teacher_client.py:73,504-506`). To make (6) testable, the brief must say how. Either the `Backend` protocol and `RecordingStub` change (which affects the caller `repl.py:167` and the stub tests in `test_backend.py`, `test_failure_classes.py` and `test_charsafety.py`), or (6) is tested against `TeacherClient.request_body` instead of the stub. Today, Scope's "a way for a backend request to name the reader schema" hides a protocol change, and nothing in the criterion pins it.
- [x] **Criteria (2) and (4) contradict each other on `missing`/`unit` values.** (2) says a non-existent package "is dropped", and spec §2 says values that fail the lookup "are dropped" (reader-schema/v1.md:51-53). (4) says an answer carrying an instruction "in ... a `missing`/`unit` value" gives "no diagnosis". An instruction-like value that matches the schema pattern `^[a-z0-9][a-z0-9.+@_-]{0,62}$` (spec:44, e.g. `run-curl-x-sh`) fails no schema check. It is just not in the index, so under (2) it is dropped and a diagnosis is still returned. Under (4) the same input must give no diagnosis. Do can't pass both. The brief must split the cases: pattern failure (e.g. `curl x|sh` with a space or `|`) means reject; pattern-valid but not indexed means drop. (4) should name only the first case.
- [x] **Rejecting an unknown `category` conflicts with the spec's compatibility rule.** (4) requires that an unknown `category` gives "no diagnosis". reader-schema/v1.md:62 says "Adding a `category` value is compatible if the REPL treats unknown values as `unknown`". That reads as mapping unknown values to `unknown`, not rejecting them, while spec §3 (:54-55) says a schema failure is rejected. The brief picks one reading without noting the tension. Either cite why rejection is right (constrained decoding makes an off-enum value a model or server fault), or flag a spec fix. Otherwise Check can fault Do whichever way Do goes.
- [x] **Criterion (5) can pass trivially.** The marker is placed in the raw input, and the test only checks that it is absent from the output. But the stub's answer is whatever the test queues (`backend.py:39-52`). If that answer never contains the marker, the reader passes (5) without validating anything. To make (5) a real red→green test, the brief should require the queued stub answers to carry the marker too: as a `missing` value, a `unit` value and an extra key. Then the output test proves the validator stripped or rejected it, not just that the stub never echoed it.
- [x] **One of the issue's done-when lines is silently dropped.** The issue's done-when includes "Raw output never appears in the command model's prompt (`:context`) after the reader is used" (notes.json body). The brief puts wiring into `?why`/fix-on-failure (#14/#17) out of scope and only tests the reader's own return (criterion 5). That is reasonable, but the brief never says the `:context` check moves to #14/#17. As written, merging this slice could close #61 with that done-when unmet. Say where it goes, or say this PR must not close #61.
- [x] **"Exists on this system" depends on an index that doesn't exist yet.** Criterion (2) needs "a real package" check against the "local dpkg/apt index", but no such lookup exists in the target. The only existing lookups are `command_provider` (command → package, over the command-not-found DB, `target.toml:35-40`) and `package_owner_query = ["dpkg","-S"]` (file → package, `target.toml:25`). The brief leaves the package-name index to Do (Open questions), and says it must come from a new target field (ADR-0023). That is a second piece of work: a new `target.toml` field, a `targets.py` parser change and its tests. It is not listed under Scope or Surfaces (`data` only). It also widens review: `test_targets.py` and the target schema. Name it in Scope, or have the injected lookup be the only package-name source in this slice.
- [x] **Minor citation mismatch.** The Falsifiability note cites `tests/test_repl.py:7-8` for "the same trick" (importing per test). That file does import its module at the top (`test_repl.py:5`, `from nl_shell.repl import Repl`). What it does at :7-8 is pin reply *literals* so the module imports. Do mirroring that citation may get the pattern wrong; the per-test import rule stated in the brief is the one to follow.
- [x] size backstop — this slice is behaving oversized: 2 round(s) already spent (threshold 2). Recommend answering `iterate-plan` at sign-off and authoring the split in the re-plan (`pdca split`), rather than `iterate-do`: a slice that is too big yields implementation-shaped findings every round, and splitting authors briefs, which is Plan's beat.
- [x] T5 Judgment — Confirm prior art by every affected file path across merged history and closed/rejected work — the brief records only reader/spec triage, and investigation here found one synthetic base commit and no remotes, so historical coverage for backend/client and other paths cannot be established (brief.md:117; target/src/nl_shell/backend.py:35; target/src/nl_shell/teacher_client.py:497).
- [x] C1 Spec — Confirm rejection of unknown categories for this version, or clarify compatibility wording — the normative rejection rule and future-version fallback wording require different handling (target/docs/design/specs/reader-schema/v1.md:54; target/docs/design/specs/reader-schema/v1.md:62).
- [x] T5 Judgment — Confirm prior art by every affected path across merged history and closed/rejected work — the supplied repository has only one synthetic base commit and no remotes, so the brief's prior-art claims cannot be independently settled here (target/.git/HEAD:1; patch.diff:1).

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
- By / date: Eduard Ralph / 2026-10-23

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 7 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)
- Follow-up (#14/#17): `reader.py:451` `_exists` keeps a command if any provider passes the name pattern — require the provider to be indexed (`package_exists`), fix the `ripgrep` test fixture, add an unindexed-provider test.
- Follow-up (#14/#17): `diagnose` lets exceptions from injected lookups escape — catch and treat as not-found, or document "lookups must not raise" in `Lookups`.

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
- C4 fix verified: bundle test red pre-fix, green post-fix (pytest): pass — C4 PASS — red without the fix (55 of 55 failed), green with it
- C5 Causal adequacy: none — reviewer + human sign-off

## 4. Conformance (Check — stack)
- T1 Structure: none — (no gate configured)
- T2 security-relevant change also updates the threat model: unverifiable — security-relevant paths changed without a threat-model update: src/nl_shell/backend.py src/nl_shell/reader.py — decide a
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review the issue #61 quarantined reader: classify failed-command output through a separate schema-constrained request and return only validated, templated, untrusted diagnosis data.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | PASS | The bounded module/API slice has explicit rejection, lookup, taint and compatibility criteria; real lookup adapters and REPL integration are deliberately later work (brief.md:14, brief.md:102; target/docs/design/specs/reader-schema/v1.md:50). |
| C2 Reproduction (red pre-fix) | PASS | Frozen red evidence records 55 assertion-time failures, no collection/setup errors, with the reader absent; local pytest rerun was unavailable, so this verdict rests on the captured run (gate-logs/C4-verify.log:14; target/tests/test_reader.py:43). |
| C3 Change | PASS | Scope remains the reader, target prompt, schema-selection API, tests and architecture references; the default proposal request retains its schema and diff whitespace checks pass (target/src/nl_shell/backend.py:35; target/src/nl_shell/teacher_client.py:500). |
| C4 Verification (red→green) | PASS | The captured gate shows 55 green and 55 red tests without collection failures; independent smoke exercised ten categories, marker removal, four rejections and teacher request schema successfully; full pytest reproduction is limited by missing pytest here (gate-logs/C4-verify.log:10; target/tests/test_reader.py:224). |
| C5 Causal adequacy | PASS | The actual trust boundary rejects malformed structure before local name filtering, returns fixed rejection reasons and permits no free-text answer field; no capability-probe symptom guard was introduced (target/src/nl_shell/reader.py:275, target/src/nl_shell/reader.py:316). |
| T1 Structure | PASS | Existing provider and rendering helpers serve the new boundary, with local lookups injected and request-schema selection contained in the backend contract (target/src/nl_shell/reader.py:125, target/src/nl_shell/reader.py:156; target/src/nl_shell/backend.py:27). |
| T2 Shape | NEEDS-HUMAN | Decide whether the existing threat model adequately covers this implementation or needs an update — the security-path gate explicitly leaves this decision open, while current reader and taint controls already describe this boundary (gate-logs/T2-threat-model.log:10; target/.oss-scanner/threat_model.md:35, target/.oss-scanner/threat_model.md:154). |
| T3 Runtime | PASS | Frozen suite output records 1156 passed, one skipped and one forkpty warning; independent reader smoke passes, but this host lacks pytest and cannot independently reproduce that full run (gate-logs/T3-suite.log:29; gate-logs/T3-suite.log:34). |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive audit must rerun at publish, as the deferred gate records (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm prior art by every affected file path across merged history and closed/rejected work — the brief records only reader/spec triage, and investigation here found one synthetic base commit and no remotes, so historical coverage for backend/client and other paths cannot be established (brief.md:117; target/src/nl_shell/backend.py:35; target/src/nl_shell/teacher_client.py:497). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept this module-only slice as useful pending #14/#17 integration, and confirm rejection of unknown categories despite the future-compatibility wording — stub/injected-lookup evidence proves the narrow boundary, not live-model diagnosis quality or end-to-end command-context isolation (target/docs/design/specs/reader-schema/v1.md:54, target/docs/design/specs/reader-schema/v1.md:62; target/src/nl_shell/reader.py:291; brief.md:190). |

Evidence limits: `python3 -m pytest -q tests/test_reader.py` could not run (`No module named pytest`); no stash/red transition was attempted because there was no runnable pytest leg. The complete frozen C4 and T3 logs were read instead. Independent Python smoke used the actual patched reader, prompt loader, RecordingStub and TeacherClient request builder with injected lookups; it did not substitute for the full suite. The target is readable and contains the patch; no stale-target caveat arose. No INTEGRATION.md was supplied or found within the allowed input/target tree. External dependencies are explicitly none for this slice (brief.md:104); production model/index/systemd integration remains outside its claimed verification.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 61 / quarantined-reader-error-diagnosis

Bottom line: I could not break the validator, and the red→green evidence is real. One test gap stands: the real client's `complete()` path has no test showing it passes the reader schema on.

## Findings

- NEEDS-HUMAN [impl] — `src/nl_shell/teacher_client.py:530`: no test covers `TeacherClient.complete()` actually passing `schema=` to `request_body`. I changed that line to `self.request_body(messages)` in a sandbox copy (so `complete()` drops the schema) and ran `tests/test_reader.py` plus `tests/test_teacher_client.py`: **137 passed**. With that bug the real reader request would be held to the proposal/v1 schema. Every answer would then come back as `{"kind": ...}`, fail with "extra properties", and turn into `NoDiagnosis`. The reader would be dead in production while the whole suite stays green. Criterion (6) at `tests/test_reader.py:239` only calls `request_body` directly, so it covers what the brief literally asked for but not the path that sends requests. Fix: add one test that runs `complete(..., schema=reader.RESPONSE_SCHEMA)` against the existing fake server in `tests/test_teacher_client.py` (or monkeypatch `_post` to capture the payload) and checks that `response_format.json_schema.name == "reader_v1"` in the bytes it posts.

- Note (not gating) — `src/nl_shell/reader.py:251`, `:311`, `:318`: `diagnose` only catches `BackendError`. If an injected lookup raises (e.g. `package_exists` raises `OSError` because dpkg is unreadable), the exception goes straight up to the caller instead of becoming "no diagnosis"; I reproduced this with a lookup that raises. Today's `command_provider.provider_lookup` swallows its own errors, and the real dpkg/systemd lookups come with #14/#17. So this is a contract question for that wiring, not a defect in this slice. Either way, the `Lookups` docstring should say whether lookups may raise.

- T2 (threat model) — `.oss-scanner/threat_model.md:35-37,80,169` still describe this code correctly: a separate request, fixed choices plus validated names, output labelled untrusted. I see no new input or moved trust boundary that would need an edit. The unverifiable T2 row can be closed at sign-off as "no change needed".

## Attacks that did not land

- **Red→green evidence** (`gate-logs/C4-verify.log`): 55 of 55 fail on the red leg with 0 import/collection errors. Each test imports the module itself, as the brief requires. The tests go through the production `diagnose` → `validate` path with `RecordingStub`, not a copy of the logic. The categories list in the test is written out by hand rather than read from the module, so the test can't just agree with itself.
- **Validator inputs I tried** (`reader.py` `_validate`): `true` as category, `1e999` / `Infinity` / `NaN` in `missing`, a BOM before the JSON, 100k-deep nesting, a full-width `ｃurl`, an Arabic-Indic digit in `unit`, duplicate keys, an empty `missing` list, duplicate `missing` names. Every one was rejected or handled correctly; nothing was repaired and nothing crashed. `re.fullmatch` closes the trailing-newline hole that `$` alone leaves open.
- **Marker leak (5):** the reject reasons are fixed strings, and `Diagnosis` / `StateItem` are built only from the enum value and names the lookups confirmed. I found no route for answer text or raw input to reach `message()` or `state_item()`.
- **Backward compatibility:** the `_post` signature changed, but the monkeypatch at `tests/test_teacher_client.py:422` takes its arguments by position, so it still works. T3 (the full suite) is green.
- **Unknown `category` rejected vs. the spec's Versioning line:** the brief already lists this under Open questions for the human, so I'm not raising it again.
<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory): issue 61, quarantined reader

**Attacker-controlled inputs this diff touches:** command output (threat model item 1: the `stdout`/`stderr` passed to `reader.diagnose`) and quarantined-reader output (item 7: the model's raw answer passed to `reader.validate`). `backend.py` and `teacher_client.py` change only how a request names its schema. That value comes from code constants, not from an attacker.

**Verdict: no finding at or above Low in this diff.** The reader is not wired into the REPL yet (#14/#17), so no attacker input reaches it in the running program today. I reviewed it as the control the threat model describes ("the reader's schema validation", component 6).

## What I checked, with no finding

- **Answer parsing rejects without repairing** (`src/nl_shell/reader.py:574-612`). I fed `validate` crafted answers directly. 100 000 nested `[` gives `NoDiagnosis('not valid JSON')`, because `RecursionError` is caught at `:580`. A duplicate key nested inside an extra property is rejected. `NaN` and `Infinity` are rejected by `parse_constant` at `:570`. Oversized integer literals raise `ValueError`, which is also caught. Every `_Reject` reason is a fixed string, so no answer text reaches `NoDiagnosis.why` or a log.
- **Patterns use `re.fullmatch`** (`:600`, `:603`), so `"curl\n"` is rejected. That case is tested (`tests/test_reader.py:898`). `missing` has at most 3 items, and duplicates are removed before the lookups run (`:608`), so a hostile answer costs at most 3 package lookups and 1 unit lookup.
- **Nothing derived from attacker text reaches the output except checked values.** `Diagnosis.message` and `state_item` (`:455-471`) are built only from the `TEMPLATES` constant, the enum value, and names that passed both the pattern and a lookup. Both run through `render.escape`. Neither the raw input nor `why` can reach the command model.
- **The result stays marked untrusted.** `label` defaults to `UNTRUSTED` (`:453`) and `_validate` never sets it, so "Untrusted text never becomes trusted" (`threat_model.md:154`) holds for this slice.
- **The `missing` check never reads `$PATH`** (`:615-619`). Only the injected `package_exists` and `command_package` lookups run, and `command_package` output is filtered again with `is_package_name`.
- **Raw text is spliced in as-is** (`build`, `:532-537`), with no `str.format`. So braces in attacker output can't pull other template fields into the request. This is tested at `tests/test_reader.py:958`.
- **Backend errors hide server text.** `diagnose` turns a `BackendError` into a fixed `NoDiagnosis` (`:550-551`). The test at `tests/test_reader.py:916` shows that an escape sequence in the server's error text doesn't reach the result.
- **Teacher client** (`src/nl_shell/teacher_client.py:496-530`). Building the request body moved from `_post` into `work()`, but it is still inside the same `try` (`:528-530`), so error handling is unchanged. `schema=None` still sends `proposal.SCHEMA` under `SCHEMA_NAME`, which is tested at `tests/test_reader.py:997`. The reader's request asks for no tools and no network.
- **The patch's tests cover the attacker cases, not just the normal path.** They include instruction-shaped extra keys, values with shell metacharacters, trailing text, a marker string checked across all four ways it could leak (`:930-945`), and backend error text.
- **T2 gate** (`gate-logs/T2-threat-model.log`: "unverifiable"). The threat model's reader text (`threat_model.md:35-37`) still describes this code: a separate request returning fixed choices and validated names. In my judgment no update is needed for this slice. The human makes that call at sign-off.

## Notes for the wiring work (#14/#17): outside this diff, not findings

These are rules the future caller must follow. They are listed so they don't get lost.

- **Secret output must not reach the reader.** `diagnose` (`src/nl_shell/reader.py:543`) sends whatever `stdout`/`stderr` it is given. It has no check for the ADR-0025 "secret" label (the threat model requires that secret output "never [be] sent to … the reader"). That check falls to the caller. If the wiring skips it, `env` output with a token in it would reach the reader, which the threat model rates High.
- **Raw input size is not capped.** `build` splices the full output (`:536`). A failed command that prints megabytes produces a request that big. Today that probably ends as a server error and then "no diagnosis", but the caller should truncate first, the same way the state block does.
- **Don't pass the unit name to `systemctl` as an argument.** The spec's `unit` pattern allows a leading `-`. Systemd needs this for `-.mount`, the root mount unit. As a result, `{"category":"service-failed","unit":"-H.service"}` passes validation, and I confirmed `unit_exists` is called with `'-H.service'`. If the real `unit_exists` ran `systemctl list-unit-files <unit>`, systemctl would read that as `-H .service`, a remote-host option, which goes over SSH, i.e. network access from the reader path. The real lookup should check the name against the parsed output of `systemctl list-unit-files` with no unit argument, or pass `--` first. The `Lookups` docstring (`:425-431`) could say this.

## Toolchain

- pytest is not installed in this sandbox, so I did not re-run the suite. I used the frozen gates instead: C4 (`gate-logs/C4-verify.log`: 55 of 55 tests red before the fix, green after) and T3 (the whole suite green). I did run the validator probes above directly with `python3 -I` against the patched source.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] T2 Shape — Decide whether the existing threat model adequately covers this implementation or needs an update — the security-path gate explicitly leaves this decision open, while current reader and taint controls already describe this boundary (gate-logs/T2-threat-model.log:10; target/.oss-scanner/threat_model.md:35, target/.oss-scanner/threat_model.md:154).
- [ ] T5 Judgment — Confirm prior art by every affected file path across merged history and closed/rejected work — the brief records only reader/spec triage, and investigation here found one synthetic base commit and no remotes, so historical coverage for backend/client and other paths cannot be established (brief.md:117; target/src/nl_shell/backend.py:35; target/src/nl_shell/teacher_client.py:497).
- [ ] Validation — fitness-to-purpose — Accept this module-only slice as useful pending #14/#17 integration, and confirm rejection of unknown categories despite the future-compatibility wording — stub/injected-lookup evidence proves the narrow boundary, not live-model diagnosis quality or end-to-end command-context isolation (target/docs/design/specs/reader-schema/v1.md:54, target/docs/design/specs/reader-schema/v1.md:62; target/src/nl_shell/reader.py:291; brief.md:190).
- [ ] `src/nl_shell/teacher_client.py:530`: no test covers `TeacherClient.complete()` actually passing `schema=` to `request_body`. I changed that line to `self.request_body(messages)` in a sandbox copy (so `complete()` drops the schema) and ran `tests/test_reader.py` plus `tests/test_teacher_client.py`: **137 passed**. With that bug the real reader request would be held to the proposal/v1 schema. Every answer would then come back as `{"kind": ...}`, fail with "extra properties", and turn into `NoDiagnosis`. The reader would be dead in production while the whole suite stays green. Criterion (6) at `tests/test_reader.py:239` only calls `request_body` directly, so it covers what the brief literally asked for but not the path that sends requests. Fix: add one test that runs `complete(..., schema=reader.RESPONSE_SCHEMA)` against the existing fake server in `tests/test_teacher_client.py` (or monkeypatch `_post` to capture the payload) and checks that `response_format.json_schema.name == "reader_v1"` in the bytes it posts.
- [ ] T2 security-relevant change also updates the threat model unverifiable — security-relevant paths changed without a threat-model update: src/nl_shell/backend.py src/nl_shell/reader.py — decide a
- [ ] **Criterion (6) can't be checked with the stub the brief requires.** The brief says the tests are "driven by `nl_shell.backend.RecordingStub`" (brief:16). It also says criterion (6) must show "the reader's request asks for constrained decoding with the reader schema". But `Backend.complete(self, messages)` (`src/nl_shell/backend.py:23`) has no schema argument. `RecordingStub.inputs` stores only the message tuples (`backend.py:41-42,48-49`). The schema lives only inside `TeacherClient.request_body`, fixed to `SCHEMA_NAME = "proposal_v1"` and `proposal.SCHEMA` (`teacher_client.py:73,504-506`). To make (6) testable, the brief must say how. Either the `Backend` protocol and `RecordingStub` change (which affects the caller `repl.py:167` and the stub tests in `test_backend.py`, `test_failure_classes.py` and `test_charsafety.py`), or (6) is tested against `TeacherClient.request_body` instead of the stub. Today, Scope's "a way for a backend request to name the reader schema" hides a protocol change, and nothing in the criterion pins it.
- [ ] **Criteria (2) and (4) contradict each other on `missing`/`unit` values.** (2) says a non-existent package "is dropped", and spec §2 says values that fail the lookup "are dropped" (reader-schema/v1.md:51-53). (4) says an answer carrying an instruction "in ... a `missing`/`unit` value" gives "no diagnosis". An instruction-like value that matches the schema pattern `^[a-z0-9][a-z0-9.+@_-]{0,62}$` (spec:44, e.g. `run-curl-x-sh`) fails no schema check. It is just not in the index, so under (2) it is dropped and a diagnosis is still returned. Under (4) the same input must give no diagnosis. Do can't pass both. The brief must split the cases: pattern failure (e.g. `curl x|sh` with a space or `|`) means reject; pattern-valid but not indexed means drop. (4) should name only the first case.
- [ ] **Rejecting an unknown `category` conflicts with the spec's compatibility rule.** (4) requires that an unknown `category` gives "no diagnosis". reader-schema/v1.md:62 says "Adding a `category` value is compatible if the REPL treats unknown values as `unknown`". That reads as mapping unknown values to `unknown`, not rejecting them, while spec §3 (:54-55) says a schema failure is rejected. The brief picks one reading without noting the tension. Either cite why rejection is right (constrained decoding makes an off-enum value a model or server fault), or flag a spec fix. Otherwise Check can fault Do whichever way Do goes.
- [ ] **Criterion (5) can pass trivially.** The marker is placed in the raw input, and the test only checks that it is absent from the output. But the stub's answer is whatever the test queues (`backend.py:39-52`). If that answer never contains the marker, the reader passes (5) without validating anything. To make (5) a real red→green test, the brief should require the queued stub answers to carry the marker too: as a `missing` value, a `unit` value and an extra key. Then the output test proves the validator stripped or rejected it, not just that the stub never echoed it.
- [ ] **One of the issue's done-when lines is silently dropped.** The issue's done-when includes "Raw output never appears in the command model's prompt (`:context`) after the reader is used" (notes.json body). The brief puts wiring into `?why`/fix-on-failure (#14/#17) out of scope and only tests the reader's own return (criterion 5). That is reasonable, but the brief never says the `:context` check moves to #14/#17. As written, merging this slice could close #61 with that done-when unmet. Say where it goes, or say this PR must not close #61.
- [ ] **"Exists on this system" depends on an index that doesn't exist yet.** Criterion (2) needs "a real package" check against the "local dpkg/apt index", but no such lookup exists in the target. The only existing lookups are `command_provider` (command → package, over the command-not-found DB, `target.toml:35-40`) and `package_owner_query = ["dpkg","-S"]` (file → package, `target.toml:25`). The brief leaves the package-name index to Do (Open questions), and says it must come from a new target field (ADR-0023). That is a second piece of work: a new `target.toml` field, a `targets.py` parser change and its tests. It is not listed under Scope or Surfaces (`data` only). It also widens review: `test_targets.py` and the target schema. Name it in Scope, or have the injected lookup be the only package-name source in this slice.
- [ ] **Minor citation mismatch.** The Falsifiability note cites `tests/test_repl.py:7-8` for "the same trick" (importing per test). That file does import its module at the top (`test_repl.py:5`, `from nl_shell.repl import Repl`). What it does at :7-8 is pin reply *literals* so the module imports. Do mirroring that citation may get the pattern wrong; the per-test import rule stated in the brief is the one to follow.

## 7. Proven / not proven
- Proven by which oracle: gates overall = pass (stub oracles).
- Unproven / needs manual run: anything flagged in §6.

## 8. Ready-to-ship attachments
- patch.diff
- tracker-comment.md     (ALWAYS, every tracker item)
- build-notes.md         (builder rationale — for the human, not the reviewer)

## 9. Check sign-off                     ← human completes Check here
- Disposition confirmed / overridden:
- Outcome: iterated-to-Do
- Iteration delta (if iterating): Auto-iterate (round 1): rebuilding for the implementation-level findings — T2 Shape — Decide whether the existing threat model adequately covers this implementation or needs an update — the security-path gate explicitly leaves this decision open, while current reader and taint controls already describe this boundary (gate-logs/T2-threat-model.log:10; target/.oss-scanner/threat_model.md:35, target/.oss-scanner/threat_model.md:154).; `src/nl_shell/teacher_client.py:530`: no test covers `TeacherClient.complete()` actually passing `schema=` to `request_body`. I changed that line to `self.request_body(messages)` in a sandbox copy (so `complete()` drops the schema) and ran `tests/test_reader.py` plus `tests/test_teacher_client.py`: **137 passed**. With that bug the real reader request would be held to the proposal/v1 schema. Every answer would then come back as `{"kind": ...}`, fail with "extra properties", and turn into `NoDiagnosis`. The reader would be dead in production while the whole suite stays green. Criterion (6) at `tests/test_reader.py:239` only calls `request_body` directly, so it covers what the brief literally asked for but not the path that sends requests. Fix: add one test that runs `complete(..., schema=reader.RESPONSE_SCHEMA)` against the existing fake server in `tests/test_teacher_client.py` (or monkeypatch `_post` to capture the payload) and checks that `response_format.json_schema.name == "reader_v1"` in the bytes it posts.. Deferred, not addressed here: 8 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- By / date: auto-iterate / 2026-10-23

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 7 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

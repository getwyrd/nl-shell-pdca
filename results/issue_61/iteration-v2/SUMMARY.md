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
- T2 security-relevant change also updates the threat model: unverifiable — security-relevant paths changed without a threat-model update: src/nl_shell/backend.py src/nl_shell/reader.py — decide a
- T3 runtime: the whole nl-shell pytest suite on the patched worktree: pass — T3 PASS — nl-shell suite green
- T4 PR body has a user-impact opener + tracker id in both artifacts: deferred — pr-description.md not drafted yet — the substantive T4 audit of the contribution artifacts runs at publish
- T5 Judgment: none — reviewer + human sign-off
- T5 judgment: → see §5.

## 5. Advisory review (artifact-only, decorrelated)
Reviewer ran without build-notes.md. Summary:

Review the quarantined error-diagnosis reader for #61: constrain a separate model request, reject malformed answers, and return only locally validated names and templated untrusted output.

| Item | Verdict | Basis |
|------|---------|-------|
| C1 Spec | NEEDS-HUMAN | Confirm rejection of unknown categories for this version, or clarify compatibility wording — the normative rejection rule and future-version fallback wording require different handling (target/docs/design/specs/reader-schema/v1.md:54; target/docs/design/specs/reader-schema/v1.md:62). |
| C2 Reproduction (red pre-fix) | PASS | Stashing production changes independently made the reader import fail; the frozen gate additionally records 56 test failures without collection errors before the fix (gate-logs/C4-verify.log:14; target/tests/test_reader.py:44). |
| C3 Change | PASS | The change stays within the agreed reader/backend/prompt slice and leaves REPL integration to subsequent work; request-specific schemas preserve the proposal default (target/src/nl_shell/teacher_client.py:496; target/src/nl_shell/reader.py:244). |
| C4 Verification (red→green) | PASS | Frozen evidence shows 56 failures before and 56 passes after; independent restored-tree category, rejection and marker checks passed, but local pytest/socket restrictions prevent an independent full rerun (gate-logs/C4-verify.log:10; target/tests/test_reader.py:278). |
| C5 Causal adequacy | PASS | Strict validation closes the free-text channel, and the added HTTP regression checks the actual posted reader schema rather than only body construction; no capability-probe symptom guard was introduced (target/src/nl_shell/reader.py:275; target/tests/test_reader.py:278; target/src/nl_shell/teacher_client.py:530). |
| T1 Structure | PASS | Schema selection remains a backend concern and target prompt data remains separate; the existing command-provider interface supplies indexed command checks (target/src/nl_shell/backend.py:28; target/src/nl_shell/reader.py:316; target/targets/ubuntu-26.04/prompts/reader.yaml:12). |
| T2 Shape | NEEDS-HUMAN | Decide whether the current threat model sufficiently describes the implemented reader or needs updating — existing separate-request and taint controls cover the boundary, but the security-path scanner explicitly leaves this decision open (gate-logs/T2-threat-model.log:10; target/.oss-scanner/threat_model.md:35; target/.oss-scanner/threat_model.md:154). |
| T3 Runtime | PASS | The captured full suite reports 1157 passed and 1 skipped; local direct validator checks and the documentation-link scanner passed, while pytest is unavailable locally (gate-logs/T3-suite.log:34; target/tests/test_reader.py:74). |
| T4 Contribution | N/A | Contribution artifacts are absent by design at Check; the substantive contribution audit must run at publish (gate-logs/T4-contribution.log:10). |
| T5 Judgment | NEEDS-HUMAN | Confirm prior art by every affected path across merged history and closed/rejected work — the supplied repository has only one synthetic base commit and no remotes, so the brief's prior-art claims cannot be independently settled here (target/.git/HEAD:1; patch.diff:1). |
| Validation — fitness-to-purpose | NEEDS-HUMAN | Accept this as the isolated reader slice and assess diagnostic usefulness — injected lookups and a simulated model do not establish real diagnosis quality or end-to-end exclusion of raw output from command-model context; that integration remains owed in #14/#17 (target/tests/test_reader.py:48; target/tests/test_reader.py:251; target/docs/design/specs/reader-schema/v1.md:26). |

Evidence and limits: all source citations above were read in the supplied patched target. The target was restored after the stash-based pre-fix check. `git diff --check` passed. `python3 scripts/docs_links.py` reported 65 relative links in 57 Markdown files, zero broken. `docs_checks.py` without arguments returned usage, so it is not counted as a successful immutability scan. The instance-root gate wrappers are not supplied here; their captured logs were inspected instead.

Independent execution: `python3 -m pytest tests/test_reader.py tests/test_teacher_client.py -q` could not run because pytest is absent. A direct smoke exercise passed all ten categories, four malformed-answer cases, indexed-name filtering and untrusted state output. After stash restoration, direct calls to the test functions passed all ten category cases, all twenty malformed answers, and all four marker cases. These calls used a temporary in-memory no-op parametrization decorator solely to load the test file; they are not represented as a pytest rerun. The subsequent HTTP test reached server construction and failed with `PermissionError: Operation not permitted` because this sandbox disallows sockets. The frozen C4 green run includes that test and reports all 56 passing; the local host restriction is not a patch defect or evidence of an unmet dependency in that captured run.

No implementation defect was confirmed. The existing provider lookup's contract supplies indexed package results, so accepting its pattern-valid package names is consistent with the injected-lookup design (target/src/nl_shell/command_provider.py:43; target/src/nl_shell/reader.py:320). Real package/systemd adapters, actual model quality and REPL wiring remain outside this slice; the automated evidence supports this narrower contract.

<!-- pdca:leaf-complete -->

### Advisory — adversary

# Adversarial review — issue 61 / quarantined-reader-error-diagnosis

**Result: I could not refute the fix.** All bullets below are minor test gaps. None is a defect in production behaviour, so none is flagged NEEDS-HUMAN.

## What I attacked

- **The red→green evidence.** `gate-logs/C4-verify.log` shows 56 of 56 tests failing on the pre-fix tree with real `ModuleNotFoundError` failures, with 0 import or collection errors. The tests import `nl_shell.reader` once per test (`tests/test_reader.py:44-45`), as the brief asks. I re-ran `tests/test_reader.py` and `tests/test_teacher_client.py` on a scratch copy of the patched tree: 138 passed. The tests call the production path, `reader.diagnose` → `backend.complete(..., schema=RESPONSE_SCHEMA)` → `validate`. They do not use a copy of it. The round-1 gap (`TeacherClient.complete` not passing `schema=` on) is now closed: `test_reader_over_teacher_client_posts_the_reader_schema` (`tests/test_reader.py:279-302`) sends a request to a real local HTTP server and checks the bytes it receives. That forwarding is at `src/nl_shell/teacher_client.py:530-531`.
- **Mutations that the tests do catch.** Each of these turned at least one test red: allowing duplicate keys; `match` instead of `fullmatch` for `missing`; skipping the unit lookup; catching the wrong exception around `backend.complete`.
- **Inputs that might break the validator** (`src/nl_shell/reader.py:275-316`). I tried: `null` / `true` / a number as `category`, `missing`, a `missing` item or `unit`; `NaN` / `1e999`; very deep nesting; long integers (Python raises ValueError above 4300 digits, which is caught); non-ASCII lookalike letters (`ı`) in `missing` (`[a-z]` is a plain codepoint range, so they are rejected); duplicate names within `missing`; trailing text after the object; `{stderr}` placed inside the raw stdout (`build` splits the *template* before splicing, `src/nl_shell/reader.py:233-238`, so it can't be swapped twice). Every one of these was either rejected or handled correctly. I found no input that gets free text, or the marker, into `message()` or `state_item()`.
- **Changes to the API contract.** `schema=None` still sends proposal/v1 (`src/nl_shell/teacher_client.py:500-501`). The request body is still built in the worker thread, as it was before the change, and its errors still go through `_as_backend_error`. The only other code that touches `_post` is the monkeypatch at `tests/test_teacher_client.py:431`, and T3 is green: 1157 passed (`gate-logs/T3-suite.log`).
- **The T2 "unverifiable" row.** `.oss-scanner/threat_model.md:35-37` already describes the reader as "a separate request to the same model server" bound by `reader-schema/v1`, and `:169` lists the reader's schema validation as a control. This patch builds exactly that control, so the threat-model text is still true. The missing threat-model edit is therefore no reason to refute the fix.

## Minor gaps (advisory, no rebuild needed)

- `tests/test_reader.py:157`: the `"NaN"` case is vacuous. Its answer also has an extra key `"x"`, so it is rejected for "extra properties" whatever `_no_constant` does. When I changed `parse_constant=_no_constant` to `float` at `src/nl_shell/reader.py:280`, all 138 tests still passed. No real input gets through because of this: NaN can only appear in fields that must be strings, and those reject it anyway. The guard is untested, not broken.
- `src/nl_shell/reader.py:320`: removing the `is_package_name` filter (`return bool(lookups.command_package(name))`) leaves every test green. In production the injected `provider_lookup` already filters on that rule (`src/nl_shell/command_provider.py:65`), so the extra check here is a second layer of protection.
- `src/nl_shell/reader.py:163,172`: removing `render.escape` from `message()` / `state_item()` leaves every test green. It can't matter today: the only text that reaches these lines is the fixed templates plus names already limited by the §1 patterns, and none of that can hold a control character. Still, no test fails if someone later removes the escaping.
- `src/nl_shell/reader.py:309`: removing the duplicate check (`name not in kept`) leaves every test green. The only effect would be "Missing: curl, curl." in the text shown to the user.

## Open item already sent to the human (not filed again)

The spec's Versioning line says a later version may add `category` values and the REPL should treat unknown ones as `unknown`. §3 says to reject anything that fails the schema, and this slice rejects. The brief already lists this under Open questions, so I have not filed it again.

<!-- pdca:leaf-complete -->

### Advisory — security-review

# Security review (advisory) — issue 61, quarantined reader

Attacker-reachable inputs this diff touches: **command output** (threat model "Where untrusted input enters" item 1: the raw `stdout`/`stderr` handed to `reader.diagnose`) and **quarantined-reader output** (item 7: the model's answer that `reader.validate` checks). The backend/teacher-client change touches **model output** (item 5) only by choosing which schema the answer is held to.

## Findings

No finding. Nothing on the threat model's severity scale is broken by this diff.

## What I checked

- **The raw text never reaches what the reader returns.** `src/nl_shell/reader.py:156-172`: `message()` and `state_item()` are built only from `TEMPLATES[category]`, the closed enum, and names that passed both the §1 pattern and an injected lookup. `NoDiagnosis.why` (`reader.py:177-185`, `:276-305`) is always a fixed phrase with no answer text in it. Test (5), `tests/test_reader.py:193`, puts a marker in the raw input and in four kinds of stub answer, and checks that it shows up in none of the outputs.
- **Strict parse, no repair** (`reader.py:275-313`). I ran crafted answers against the patched module myself. All of these give `NoDiagnosis`: a leading BOM (byte-order mark), a `unit` with a trailing `\n` (`fullmatch`, `reader.py:304`), four copies of one name (the count is checked before duplicates are removed, so it rejects), and 100,000 nested `[` (the `RecursionError` is caught at `:281`). A JSON-escaped `"network"` decodes to a valid category, which is correct. The suite also covers duplicate keys (`:264`), `NaN` (`:271`), `null` unit, bool or number category, and trailing text (`tests/test_reader.py:136-157`).
- **Names that come back from the lookups.** `_exists` (`reader.py:316-320`) keeps a command only if one of its providers passes `command_provider.is_package_name`. I faked a provider that returned `("bad pkg\n", "x")`, and the name was dropped. `$PATH` is never read. Kept names are ASCII-only because of the §1 patterns, and `render.escape` runs on top of that.
- **A real name the attacker picks is kept.** For example `{"category":"network","missing":["sudo"]}` gives `Missing: sudo.` and a state item `missing sudo`. Spec §2 and ADR-0017 allow this by design. The item is labelled `untrusted` (`reader.py:154`, test `tests/test_reader.py:202`), so the taint rules and clean-room re-derivation (rebuilding a privileged proposal from trusted context only) still apply. This is not a finding.
- **Schema selection** (`src/nl_shell/teacher_client.py:496-531`, `src/nl_shell/backend.py:35-72`). `schema=None` still sends `proposal.SCHEMA` under `proposal_v1`, so the command-model path is unchanged (`tests/test_teacher_client.py:233-234` stays green; T3 suite: 1157 passed). Last round's finding that `complete()` could drop `schema=` is now covered end to end. `tests/test_reader.py:279` posts through a real HTTP stand-in and checks the `reader_v1` schema in the bytes sent. Moving body encoding from `_post` into `work()` changes no auth, endpoint or size handling.
- **Splicing the prompt** (`reader.py:233-238`). The raw text is joined in as plain strings, with no `str.format`, so braces in the output can't pull in template fields (test `tests/test_reader.py:212`). The prompt file is loaded with `yaml.safe_load` and refuses unknown keys (`reader.py:202-230`).
- **T2 (did the threat model need an update?).** I think no change is needed. `.oss-scanner/threat_model.md:35-37` (reader: "fixed choices and validated names … never sees the raw text"), `:80-81` (item 7) and `:154` ("reader output is untrusted") all still describe what the code does. The diff adds no new input, no network path and no new trust level. Rows 6 ("reader's schema validation") and 4 (taint) in "Components that matter most" are what this slice builds. The human makes this call at sign-off; this is my read.

## Notes for the wiring (#14 / #17), not findings against this diff

- `diagnose` (`reader.py:244`) takes `stdout`/`stderr` with no size cap and no taint label. Two "What must hold" rules then fall on the caller. First, output labelled secret (from `env`, `printenv` or a sensitive-location read) must never be sent to the reader (ADR-0025). Second, the output needs truncating before the request, so a command that prints a lot can't make the request huge. The wiring PR should test both.
- An injected lookup that raises an exception passes it straight up through `diagnose`. The real dpkg/systemd lookups (#14/#17) should return `False` on error, as `provider_lookup` does (`src/nl_shell/command_provider.py:63`), so text the attacker shapes can't crash the caller.

<!-- pdca:leaf-complete -->

## 6. NEEDS-HUMAN — items the human must clear before sign-off
- [ ] C1 Spec — Confirm rejection of unknown categories for this version, or clarify compatibility wording — the normative rejection rule and future-version fallback wording require different handling (target/docs/design/specs/reader-schema/v1.md:54; target/docs/design/specs/reader-schema/v1.md:62).
- [ ] T2 Shape — Decide whether the current threat model sufficiently describes the implemented reader or needs updating — existing separate-request and taint controls cover the boundary, but the security-path scanner explicitly leaves this decision open (gate-logs/T2-threat-model.log:10; target/.oss-scanner/threat_model.md:35; target/.oss-scanner/threat_model.md:154).
- [ ] T5 Judgment — Confirm prior art by every affected path across merged history and closed/rejected work — the supplied repository has only one synthetic base commit and no remotes, so the brief's prior-art claims cannot be independently settled here (target/.git/HEAD:1; patch.diff:1).
- [ ] Validation — fitness-to-purpose — Accept this as the isolated reader slice and assess diagnostic usefulness — injected lookups and a simulated model do not establish real diagnosis quality or end-to-end exclusion of raw output from command-model context; that integration remains owed in #14/#17 (target/tests/test_reader.py:48; target/tests/test_reader.py:251; target/docs/design/specs/reader-schema/v1.md:26).
- [ ] T2 security-relevant change also updates the threat model unverifiable — security-relevant paths changed without a threat-model update: src/nl_shell/backend.py src/nl_shell/reader.py — decide a
- [ ] **Criterion (6) can't be checked with the stub the brief requires.** The brief says the tests are "driven by `nl_shell.backend.RecordingStub`" (brief:16). It also says criterion (6) must show "the reader's request asks for constrained decoding with the reader schema". But `Backend.complete(self, messages)` (`src/nl_shell/backend.py:23`) has no schema argument. `RecordingStub.inputs` stores only the message tuples (`backend.py:41-42,48-49`). The schema lives only inside `TeacherClient.request_body`, fixed to `SCHEMA_NAME = "proposal_v1"` and `proposal.SCHEMA` (`teacher_client.py:73,504-506`). To make (6) testable, the brief must say how. Either the `Backend` protocol and `RecordingStub` change (which affects the caller `repl.py:167` and the stub tests in `test_backend.py`, `test_failure_classes.py` and `test_charsafety.py`), or (6) is tested against `TeacherClient.request_body` instead of the stub. Today, Scope's "a way for a backend request to name the reader schema" hides a protocol change, and nothing in the criterion pins it.
- [ ] **Criteria (2) and (4) contradict each other on `missing`/`unit` values.** (2) says a non-existent package "is dropped", and spec §2 says values that fail the lookup "are dropped" (reader-schema/v1.md:51-53). (4) says an answer carrying an instruction "in ... a `missing`/`unit` value" gives "no diagnosis". An instruction-like value that matches the schema pattern `^[a-z0-9][a-z0-9.+@_-]{0,62}$` (spec:44, e.g. `run-curl-x-sh`) fails no schema check. It is just not in the index, so under (2) it is dropped and a diagnosis is still returned. Under (4) the same input must give no diagnosis. Do can't pass both. The brief must split the cases: pattern failure (e.g. `curl x|sh` with a space or `|`) means reject; pattern-valid but not indexed means drop. (4) should name only the first case.
- [ ] **Rejecting an unknown `category` conflicts with the spec's compatibility rule.** (4) requires that an unknown `category` gives "no diagnosis". reader-schema/v1.md:62 says "Adding a `category` value is compatible if the REPL treats unknown values as `unknown`". That reads as mapping unknown values to `unknown`, not rejecting them, while spec §3 (:54-55) says a schema failure is rejected. The brief picks one reading without noting the tension. Either cite why rejection is right (constrained decoding makes an off-enum value a model or server fault), or flag a spec fix. Otherwise Check can fault Do whichever way Do goes.
- [ ] **Criterion (5) can pass trivially.** The marker is placed in the raw input, and the test only checks that it is absent from the output. But the stub's answer is whatever the test queues (`backend.py:39-52`). If that answer never contains the marker, the reader passes (5) without validating anything. To make (5) a real red→green test, the brief should require the queued stub answers to carry the marker too: as a `missing` value, a `unit` value and an extra key. Then the output test proves the validator stripped or rejected it, not just that the stub never echoed it.
- [ ] **One of the issue's done-when lines is silently dropped.** The issue's done-when includes "Raw output never appears in the command model's prompt (`:context`) after the reader is used" (notes.json body). The brief puts wiring into `?why`/fix-on-failure (#14/#17) out of scope and only tests the reader's own return (criterion 5). That is reasonable, but the brief never says the `:context` check moves to #14/#17. As written, merging this slice could close #61 with that done-when unmet. Say where it goes, or say this PR must not close #61.
- [ ] **"Exists on this system" depends on an index that doesn't exist yet.** Criterion (2) needs "a real package" check against the "local dpkg/apt index", but no such lookup exists in the target. The only existing lookups are `command_provider` (command → package, over the command-not-found DB, `target.toml:35-40`) and `package_owner_query = ["dpkg","-S"]` (file → package, `target.toml:25`). The brief leaves the package-name index to Do (Open questions), and says it must come from a new target field (ADR-0023). That is a second piece of work: a new `target.toml` field, a `targets.py` parser change and its tests. It is not listed under Scope or Surfaces (`data` only). It also widens review: `test_targets.py` and the target schema. Name it in Scope, or have the injected lookup be the only package-name source in this slice.
- [ ] **Minor citation mismatch.** The Falsifiability note cites `tests/test_repl.py:7-8` for "the same trick" (importing per test). That file does import its module at the top (`test_repl.py:5`, `from nl_shell.repl import Repl`). What it does at :7-8 is pin reply *literals* so the module imports. Do mirroring that citation may get the pattern wrong; the per-test import rule stated in the brief is the one to follow.
- [ ] T5 Judgment — Confirm prior art by every affected file path across merged history and closed/rejected work — the brief records only reader/spec triage, and investigation here found one synthetic base commit and no remotes, so historical coverage for backend/client and other paths cannot be established (brief.md:117; target/src/nl_shell/backend.py:35; target/src/nl_shell/teacher_client.py:497).

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
- Iteration delta (if iterating): Auto-iterate (round 2): rebuilding for the implementation-level findings — T2 Shape — Decide whether the current threat model sufficiently describes the implemented reader or needs updating — existing separate-request and taint controls cover the boundary, but the security-path scanner explicitly leaves this decision open (gate-logs/T2-threat-model.log:10; target/.oss-scanner/threat_model.md:35; target/.oss-scanner/threat_model.md:154).. Deferred, not addressed here: 9 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- By / date: auto-iterate / 2026-10-23

## 10. Act candidates (hints for the next Act review)
- Plan advisory: 7 finding(s); brief revised: yes (plan-advisory-*.md)
- (empty is the common case)

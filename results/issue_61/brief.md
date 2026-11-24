# Design proposal — issue 61 / quarantined-reader-error-diagnosis

> Plan artifact (planner leaf). Do reads ONLY this file. The `- **Label:** value` lines
> are parsed by the driver. The design is already decided in ADR-0017 and
> `docs/design/specs/reader-schema/v1.md` (#68, closed); this proposal fixes the build
> slice. No new nl-shell proposal under `docs/design/proposals/` is needed.

- **Slug:** quarantined-reader-error-diagnosis
- **Kind:** enhancement (design proposal)
- **Goal:** A quarantined reader (a new `nl_shell.reader` module): given the raw, untrusted
  text of a failed command (stdout, stderr), it makes one separate model request
  constrained to the `reader-schema/v1` schema, validates the answer, and returns either a
  validated error diagnosis (`category`, plus `missing` / `unit` names that exist on this
  system) or "no diagnosis". The only text it gives back for the user or the command model
  is built from nl-shell templates keyed on `category`.
- **Success criterion:** `tests/test_reader.py`, driven by `nl_shell.backend.RecordingStub`
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
- **Falsifiability:** Plain pytest on the host. On `main` there is no reader, so every test
  fails. The test module MUST import `nl_shell.reader` inside each test (or a helper the
  tests call), not at module top. A top-level import of the new module is an *import
  error* on the C4 red leg, which the gate reports as UNVERIFIABLE, not as red
  (`engine/scripts/run-verify.sh`: "the red leg's test module failed to IMPORT"). Imported
  per test, the red leg gets a `ModuleNotFoundError` *failure* in each test, which counts.
  (`tests/test_repl.py:7-8` does something related, pinning reply literals so the module
  imports on `main`; follow the per-test import rule stated here, not that file's shape.)
- **Invariant to restore:** Raw untrusted text reaches the command model only through
  values a deterministic check has confirmed: a closed `category` enum, and names that
  exist in the local dpkg/apt index or `systemctl list-unit-files`. No free text from the
  reader ever reaches the command model or the screen. Sources: ADR-0017 §2–§5;
  reader-schema/v1 §2–§5; threat model "Untrusted text never becomes trusted"
  (`.oss-scanner/threat_model.md:154`).
- **Repo + branch target:** eduralph/nl-shell @ main
- **Milestone / ADRs:** M0 — REPL prototype. ADR-0017 (reader), ADR-0016 (taint: reader
  output is `untrusted`), ADR-0018 (serving, constrained decoding), ADR-0023 (target data).
  Threat-model inputs: the quarantined reader (threat model, the reader item and its
  "reader's schema validation" control, `.oss-scanner/threat_model.md:35-37,169`). This
  slice builds that control, so the threat model's reader text must still be true after it;
  update it in the same PR if anything changes.
- **Depends on:** none
- **Conflicts with:** none
- **Ordering note:** independent of the rest of the batch. It may touch
  `src/nl_shell/backend.py` / `teacher_client.py` and the target's prompt data; nothing else
  in this batch edits those.
- **Surfaces:** data
- **Scope:** the reader module; its own prompt as target data under
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
- **Difficulty:** medium
- **Test environment note:** the tests use the stub backend and injected lookups, so neither the
  real dpkg index nor systemd is needed.
- **External dependencies:** none
- **Test file:** tests/test_reader.py
- **Citations expected:** Do must cite path:line on the target branch for every change.
  Peers to mirror:
  - the strict proposal parser `nl_shell.proposal.parse` (`src/nl_shell/proposal.py`,
    `SCHEMA` at `:20`, required-key loop at `:119`): reject, never repair. The reader's
    validator follows the same shape.
  - `command_provider.provider_lookup` (`src/nl_shell/command_provider.py:43-67`) and
    `is_package_name` (`:34-36`): the existing local, read-only "which package provides this
    command" lookup over the target's data. Use it for the "command an indexed package
    provides" half of the `missing` check rather than writing a second one.
  - `TeacherClient.request_body` (`src/nl_shell/teacher_client.py:494-512`): where the
    `response_format` / `json_schema` is set.
- **Prior-art check (triage cycles):** no `src/nl_shell/reader.py` on `origin/main`;
  `git log origin/main -- docs/design/specs/reader-schema/v1.md` → 03251e4 only (the spec,
  #68). No branch named for the reader. Closed-unmerged PRs touching the reader paths: none.
  Open PRs: none.
- **Disposition hint:** new-feature

## Motivation

Fix on failure (#17) and `?why did that fail` (#14) both need to say something about a
failed command's output. That output is attacker-influenced (a file name, a web page, a
log line). If it reached the command model directly, it could carry instructions. The
reader is the narrow channel: a second model call reads the raw text and may only answer
with fixed choices and names that already exist on the system (dual-LLM pattern with
constrained output, ADR-0017 §1 — not CaMeL).

## Design

- **Request.** One model request per diagnosis, with the reader's own prompt and the raw
  text as its input, sent through the `Backend` protocol (`src/nl_shell/backend.py`), so
  `RecordingStub` drives the tests and `TeacherClient` the real thing. Constrained decoding
  uses reader-schema/v1 §1, single-sourced from one constant in the reader module (as
  `proposal.SCHEMA` is for proposals, never a copy).
- **Validation** (reader-schema/v1 §2–§3), after decoding, because the schema alone is not
  enough:
  - parse as one JSON object; reject on any parse error, extra property, wrong type,
    unknown `category`, a `missing` item failing the pattern, more than 3 items, or a
    `unit` failing the pattern;
  - each `missing` value is kept only if it is a package in the local dpkg/apt index or a
    command an indexed package provides; others are dropped (not a rejection). Never
    validated against `$PATH` (attacker-influenced, ADR-0017 Context);
  - `unit` is kept only if it is in `systemctl list-unit-files`; otherwise dropped;
  - a rejected answer → "no diagnosis" (ADR-0017 §3). Nothing is repaired.
- **Output.** A small value object: `category`, the kept `missing` names, the kept `unit`,
  labelled `untrusted` (ADR-0016). The user-facing text comes from templates keyed on
  `category` with the kept names filled in (reader-schema/v1 §4). There is no free-text
  field anywhere. Every string shown goes through `nl_shell.render.escape`, like every other
  reply (`src/nl_shell/repl.py:11-12`).
- **Isolation.** The reader request carries no tools and nothing it can run. The reader's
  input never becomes part of the command model's messages; only the validated value does.

## Alternatives considered

- A free-text `summary` (the original issue text): an injection channel no deterministic
  check can close; dropped by the 2026-10-14 design review and ADR-0017 §2.
- Validating `missing` against `$PATH`: attacker-influenced; dropped (ADR-0017).
- A separate OS process for the reader: the issue body asks for it, but ADR-0017 §5 decided
  on a separate model request, and the model server already has no network or PTY. Not
  re-litigated here.

## Impact & compatibility

New module and target prompt data; a backend request can now name its schema. The default
(proposal schema) must stay as it is for the existing proposal path; the existing
teacher-client and backend tests must stay green. No settings change.

## Open questions

- (For #14/#17, not Do here.) How the real dpkg/apt package-name index is read
  (`dpkg-query -W` vs. the apt lists): local and read-only (ADR-0003), from a target
  field (ADR-0023).
- (For the human.) reader-schema/v1's Versioning line about unknown `category` values vs.
  §3's rejection: this slice rejects; confirm, or ask for a spec wording fix.

## STOP discipline

Draft only until Check sign-off. Pushing to a feature/draft branch and opening a
draft PR MAY happen during the cycle (useful for CI feedback). The PR MUST NOT be
marked ready before sign-off accepts.

Plan-review response: all findings taken. (6) is testable through a named protocol change
(`schema` keyword, `RecordingStub.schemas`) and `request_body`; (2)/(4) now split
pattern failure (reject) from pattern-valid-but-unindexed (drop); unknown `category` is
rejected with the reason given and the spec tension sent to Open questions; (5)'s stub
answers carry the marker; the `:context` done-when moves to #14/#17 and the PR refs #61;
the lookups are injected only, so no new target field or index reader is in this slice;
the test_repl.py citation is corrected.

## Iteration 1 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 1): rebuilding for the implementation-level findings — T2 Shape — Decide whether the existing threat model adequately covers this implementation or needs an update — the security-path gate explicitly leaves this decision open, while current reader and taint controls already describe this boundary (gate-logs/T2-threat-model.log:10; target/.oss-scanner/threat_model.md:35, target/.oss-scanner/threat_model.md:154).; `src/nl_shell/teacher_client.py:530`: no test covers `TeacherClient.complete()` actually passing `schema=` to `request_body`. I changed that line to `self.request_body(messages)` in a sandbox copy (so `complete()` drops the schema) and ran `tests/test_reader.py` plus `tests/test_teacher_client.py`: **137 passed**. With that bug the real reader request would be held to the proposal/v1 schema. Every answer would then come back as `{"kind": ...}`, fail with "extra properties", and turn into `NoDiagnosis`. The reader would be dead in production while the whole suite stays green. Criterion (6) at `tests/test_reader.py:239` only calls `request_body` directly, so it covers what the brief literally asked for but not the path that sends requests. Fix: add one test that runs `complete(..., schema=reader.RESPONSE_SCHEMA)` against the existing fake server in `tests/test_teacher_client.py` (or monkeypatch `_post` to capture the payload) and checks that `response_format.json_schema.name == "reader_v1"` in the bytes it posts.. Deferred, not addressed here: 8 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v1/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

## Iteration 2 — carry-forward (from the previous attempt)
- Sign-off rationale: Auto-iterate (round 2): rebuilding for the implementation-level findings — T2 Shape — Decide whether the current threat model sufficiently describes the implemented reader or needs updating — existing separate-request and taint controls cover the boundary, but the security-path scanner explicitly leaves this decision open (gate-logs/T2-threat-model.log:10; target/.oss-scanner/threat_model.md:35; target/.oss-scanner/threat_model.md:154).. Deferred, not addressed here: 9 finding(s) that need human judgment, held in deferred-findings.json for the human at handover — not build work
- Full previous attempt preserved in `iteration-v2/` (patch.diff, build-notes.md, SUMMARY.md, check-*).
- Address the above; do NOT re-attempt the rejected approach unchanged. Satisfy the brief's Success criterion (the end result).

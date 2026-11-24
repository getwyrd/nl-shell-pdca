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

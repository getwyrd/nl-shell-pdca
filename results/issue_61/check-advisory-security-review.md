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

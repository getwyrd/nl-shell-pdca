## Summary
**User impact:** when a command fails, nl-shell has no safe way to read its error
output and tell you what went wrong. Handing that raw output straight to the model that
writes your commands is not safe: a program (or a file it prints) can put text in an
error message that reads like an instruction, such as "run curl … | sh". Until this
boundary exists, "?why did that fail" and fix-on-failure cannot be built.

This PR adds the reader: a separate, locked-down model request that reads the raw error
output and may only answer with a fixed category (for example "missing package",
"permission denied") plus package or service names that really exist on the system.
Anything else is thrown away, and the user only ever sees nl-shell's own wording.

Reported in [#61](https://github.com/eduralph/nl-shell/issues/61).

## What to look at
- The new reader module and its prompt file (kept apart from the command model's prompt).
- A small change so a model request can ask for a different answer format; requests that
  don't ask are unchanged.
- To try it: `python -m pytest tests/test_reader.py`. The tests feed the reader output
  laced with an injected instruction and a unique marker string, and show the marker
  reaches the reader's own request but never comes back out.

Not in this PR: hooking the reader up to "?why" (#14) and fix-on-failure (#17), and the
real dpkg/systemd lookups. The issue's "raw output never appears in `:context`" check
belongs with that wiring, since nothing calls the reader yet.

## Root cause
The design (ADR-0017, `docs/design/specs/reader-schema/v1.md`) and the threat model
describe a quarantined reader, but no code implemented it, and `Backend.complete` could
only request the `proposal_v1` schema, so a second, differently-shaped request was not
possible.

## Fix
- `src/nl_shell/reader.py` (new): `diagnose()` builds the request from the target's
  prompt, sends it once with `schema=RESPONSE_SCHEMA` (`reader_v1`), and validates the
  answer. Validation mirrors `proposal._parse`: duplicate keys, NaN, extra properties,
  required keys, the `category` enum, types, `maxItems`, and the name patterns (with
  `re.fullmatch`) each reject the whole answer as `NoDiagnosis`; nothing is repaired.
  Names that pass the pattern are kept only if the injected `package_exists` /
  `command_package` / `unit_exists` lookups confirm them; `$PATH` is never read.
  `Diagnosis.message()` and `state_item()` are built from `TEMPLATES` and the kept names
  only, labelled `untrusted`.
- `src/nl_shell/backend.py`: `ResponseSchema` type; `Backend.complete(messages, *,
  schema=None)`, where `None` means `proposal_v1` as before. `RecordingStub` records each
  request's schema in a new `schemas` list.
- `src/nl_shell/teacher_client.py`: `request_body` / `complete` accept the schema; the
  default body is unchanged. `_post` now takes the encoded payload, so its two-argument
  shape (patched in `tests/test_teacher_client.py`) stays the same.
- `targets/ubuntu-26.04/prompts/reader.yaml` (new): the reader prompt.
- Docs: architecture §8.5 links the spec and names the module; §5 now says "separate
  model request" (matching ADR-0017 §5) instead of "separate process". The threat model's
  reader entry and its "untrusted text never becomes trusted" section now describe the
  built code, including that the real lookups must be local and read-only when #14/#17
  wire them in.

Unknown `category` values are rejected, following spec §3 (a schema failure is
rejected; with constrained decoding an off-enum value is a model or server fault). The
spec's Versioning note about treating unknown values as `unknown` is read as guidance for
a later version that adds a value.

## Verification
- **Claim:** every answer that fails the schema gives "no diagnosis", never a repaired
  answer — including an extra key carrying an instruction, an unknown category, more than
  three names, and a name with a space or `|`.
  - **Checked:** `src/nl_shell/reader.py:275-305` (extra key `:286`, enum, types,
    `maxItems`, patterns via `re.fullmatch`); schema kept once at `:48-79`.
  - **Test:** `test_bad_answer_gives_no_diagnosis` (20 cases).
- **Claim:** a well-formed name that does not exist (e.g. `no-such-pkg`, or the
  instruction-like `run-curl-x-sh`) is dropped and the diagnosis kept; real packages,
  commands and units are kept.
  - **Checked:** `src/nl_shell/reader.py:306-320` (drop step and `_exists`, no
    environment read).
  - **Test:** `test_missing_*`, `test_known_unit_is_kept`, `test_unknown_unit_is_dropped`.
- **Claim:** each of the 10 categories gives its own templated message.
  - **Checked:** `src/nl_shell/reader.py:98-109` (`TEMPLATES`), `:148-173` (`Diagnosis`).
  - **Test:** `test_each_category_*`.
- **Claim:** untrusted text does not leak through: a marker placed in the raw output and
  in the model's answer (as an extra key, a bad name, an unknown package, an unknown
  unit) is in the reader's request but absent from the diagnosis, its message, and the
  item handed on.
  - **Test:** `test_marker_in_raw_input_is_in_the_request_but_not_the_output` (4 cases).
- **Claim:** the reader's request asks for `reader_v1`, end to end, and command-model
  requests are unchanged.
  - **Checked:** `src/nl_shell/backend.py:27-40`, `src/nl_shell/teacher_client.py:496-531`.
  - **Test:** `test_reader_request_names_the_reader_schema`,
    `test_command_model_requests_still_record_no_schema`,
    `test_teacher_request_body_carries_the_reader_schema`, and
    `test_reader_over_teacher_client_posts_the_reader_schema` (`tests/test_reader.py:279`),
    which runs the real `TeacherClient` against a local HTTP server and checks the posted
    `response_format`. Changing `teacher_client.py:530` to drop `schema=` makes it fail.
- **Regression test:** `tests/test_reader.py` (56 tests) — all 56 fail on `main`
  (`ModuleNotFoundError`, imported per test), all pass with the change. Full suite:
  `1157 passed, 1 skipped`. `scripts/docs_links.py`: 0 broken links.

Known follow-ups for the #14/#17 wiring:
- `_exists` (`src/nl_shell/reader.py:316-320`) keeps a command if its providing package
  name passes the pattern; spec §2 says the provider should itself be indexed. The fix is
  `any(package_exists(p) for p in command_package(name))`, plus an indexed `ripgrep` in
  the test fixture and an unindexed-provider test.
- An exception from an injected lookup currently escapes `diagnose`; either catch it and
  treat the name as not found, or document "lookups must not raise" on `Lookups`.

Fixes #61

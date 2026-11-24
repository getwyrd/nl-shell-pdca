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

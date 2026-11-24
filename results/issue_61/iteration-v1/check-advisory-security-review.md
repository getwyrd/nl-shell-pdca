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

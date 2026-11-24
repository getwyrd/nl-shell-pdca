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

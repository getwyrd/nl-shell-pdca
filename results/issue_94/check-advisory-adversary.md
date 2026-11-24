# Adversarial review — issue 94 / architecture-os-targets (round 5)

**Bottom line:** I could not refute the fix. The red→green proof reproduces, the round-4 fixes landed, and no claim I checked contradicts ADR-0023 or the code. What remains is the human-only semantic review the brief already requires, plus the open items carried from round 4.

## What I tried

- **Red→green, re-run by hand.** C4 exited 77 (docs-only, `gate-logs/C4-verify.log`), so I ran `tests/test_architecture_targets.py` with the instance `.venv` pytest against copies of the docs. Against the base-commit docs (`git show HEAD:` of every `docs/design/architecture/*.md`) the result was **9 failed**. Against the patched docs it was **9 passed**. The test reads the real Markdown (`tests/test_architecture_targets.py:9`), so it is not checking a copy that only mirrors production. T3 (`gate-logs/T3-suite.log`: 1340 passed) and host-docs (`gate-logs/host-docs.log`: 0 broken links, immutability OK, ADR index OK) agree. This is still not a C4 PASS. It shows the pinned phrases are present, not that the docs are correct.
- **Built/planned claims vs code.** Each one matches:
  - Start-up loads command prompts: `src/nl_shell/cli.py:64`.
  - A mismatched named target only prints a warning: `cli.py:79`.
  - The reader has `load_prompt` (`reader.py:202`) and uses `command_provider` (`reader.py:44`), but `cli.py` and `repl.py` never call it.
  - The target folder holds only `target.toml`, `sensitive.toml`, `gate-vectors.toml` and `prompts/`.
  - `[command_provider]` is target data (`targets/ubuntu-26.04/target.toml`).
  - State capture and gate integration are still unbuilt (`repl.py:8`).

  I found no overclaim.
- **ADR-0023 conformance.** I checked the consumer table (ADR `:43-50`), manifest fields (`:61-64`), the install path, MUST-verify and MUST-refuse (`:66-68`), install/update-only downloads (`:68-69`), adapter identity (`:70-71`) and exact os-release selection with mismatch → confirm-every-command (`:73-78`). The chapter 05 bullets (`05-building-block-view.md:69-89`) and chapter 07 (`07-deployment-view.md:18-31`) match them without changing any requirement. Both **[OPEN]** questions are kept (`07-deployment-view.md:69-72`), and no channel is named.
- **Leftover unscoped OS wording.** I grepped all architecture chapters for `26.04|sudo-rs|dpkg|apt|systemd|Wayland|uutils|GNOME|Ubuntu`. What remains is either scoped or an allowed example: §8.3 apt examples under the new "examples below use `ubuntu-26.04`" lead-in at `08-crosscutting-concepts.md:55-56`, §6.2 sudo-rs under the new scope line at `06-runtime-view.md:38`, and milestone names at `09-build-order-and-roadmap.md:24,26`, which the brief allows.

## Findings

- `tests/test_architecture_targets.py:31-33`: the test only checks that phrases are present. It cannot catch a sentence that contradicts them. I tested this: appending "Today the REPL already enforces adapter and hash checks." to the adapters bullet at `07-deployment-view.md:31` still gives 9 passed. This is the known limit of a docs-only test, which the brief already accepts ("not … full semantic correctness"). No rebuild is needed. It is why the human semantic sweep cannot be skipped.
- NEEDS-HUMAN [human] — `07-deployment-view.md:34` now scopes the whole serving bullet ("one `llama-server` per user … systemd user service … serving both the command model and the reader (ADR-0018)") to `ubuntu-26.04`. ADR-0023:106-107 says "The REPL, serving, the reader … carry over unchanged". Only the systemd unit is clearly OS-specific. Scoping the per-user server and its socket too could read as "serving is target-specific". The human should decide whether to scope only the systemd user-service clause.
- NEEDS-HUMAN [human] — Carried from round 4 and still open; I add no new evidence beyond this:
  - `07-deployment-view.md:21-22` lists `gate-vectors.toml` as a shipped runtime file. ADR-0023:47 says "gate tests", but :121 says "the gate … loads … `gate-vectors.toml`".
  - `08-crosscutting-concepts.md:114` says "package data/query (`dpkg`/`apt`)". The real lookup is the command-not-found SQLite DB (`target.toml` `[command_provider]`).
  - `05-building-block-view.md:111` marks "PTY session" as *(planned)*, but `src/nl_shell/session.py` is a built library that is not wired into the REPL. That is the same situation as the reader, which the doc calls "built, not yet wired". The two need one rule.
  - The human semantic sweep of every chapter, including chapter 10 `:55`, `:58` and `:59`.
<!-- pdca:leaf-complete -->

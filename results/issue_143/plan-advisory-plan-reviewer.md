Bash was unavailable in this run (every command failed with `apply-seccomp: write /proc/self/setgroups ... Permission denied`); this review used only Read, Grep and Glob.

# Plan review: prompts-yaml-context-recording-stub-core (core of #16)

- NEEDS-HUMAN — **No tracker record to check the brief against.** The sandbox has `brief.md` and `dependency-state.json`, but no `notes.json` and no `sources/` directory (Glob of the cwd lists only `.claude/*`, `brief.md`, `dependency-state.json`). So I could not compare the problem statement, the claim "iteration-3 design, which passed review apart from the character-safety coverage", or the #16→#144 split against the thread. Nobody has checked the brief's framing against the tracker. The human should confirm it at sign-off, or the driver should re-run this review with the thread attached.

- NEEDS-HUMAN — **The target I was given is not the base the brief describes, so the brief's wiring citations can't be checked.** The brief targets "main, built on the wave base that folds #92's accepted patch (draft PR #142)". `$PDCA_TARGET` is plain main without #92:
  - `src/nl_shell/targets.py` does not exist. The brief cites `targets.py:127`.
  - `src/nl_shell/cli.py` has only 19 lines and no start-up error path. The brief cites `cli.py:53-55` and `cli.py:64`.
  - `tests/test_cli.py` has only 20 lines. Criterion (c) depends on "a matching os-release injected as `tests/test_cli.py:29-46` does".
  - `Repl.__init__` takes only `(read, out)` (`src/nl_shell/repl.py:38`). The brief requires "Keep `Repl(read, out)` and `Repl(read, out, status_lines)` working".
  - `_reply` is at `repl.py:66-77`, not `74-84`.

  `dependency-state.json` says 92 is `COMPLETE`, but the brief itself calls PR #142 a *draft*. COMPLETE means the bundle finished, not that the patch is merged. If Do's worktree is plain main, as mine is, criterion (c) and Scope (1) have nothing to build on, and the brief tells Do "must not invent stand-ins". The bundle would stall. Before scheduling, confirm that the Do/Check worktree really is the #92-folded wave base, and give its ref or commit in `Repo + branch target`.

- NEEDS-HUMAN — **Two cited line numbers don't match the files on main.**
  - Invariant cites `.oss-scanner/threat_model.md:117-120` for "Output rendering is filtered everywhere" and "What the user confirms is exactly what runs". On main, lines 117-120 are about the sudo password and the sudo cache. The two must-holds are at `threat_model.md:127-133`.
  - Scope (1) cites "ADR-0023:108-109" for "non-editable install has no defaults until #48/#50". Lines 108-109 of `docs/design/adr/0023-os-targets.md` are about repository size. The installer and packaging follow-up is at `0023-os-targets.md:123-124`.

  If #92 doesn't shift these files, the citations are simply wrong. The brief requires Do to cite `path:line` for every change, and these would carry the errors forward.

- NEEDS-HUMAN — **Criterion (d) leaves out schema rules, so a parser that is too lenient still passes.** (d) lists only the spec's §Conformance list plus a few extras. Spec `docs/design/specs/proposal/v1.md:43-49` also requires:
  - `kind` (`"required": ["kind"]`);
  - only the listed enum values for `kind`, `risk` and `reason`;
  - `command` with `minLength: 1`.

  Rule 2 (`v1.md:53-54`) also forbids `clarify`/`refuse` with a `command`, and `clarify`/`refuse` without a `reason`. None of these cases is in (d). For example, a parser that accepts `{"kind":"command","command":"","risk":"bogus"}`, or one that accepts a body with no `kind`, passes every listed test. That breaks "reject, never repair" (ADR-0018 §3, `0018-model-serving-and-wire-format.md:40`) without any gate noticing. Add to (d): missing `kind`, unknown `kind`/`risk`/`reason` values, an empty `command`, `clarify` with `command`, and `refuse` without `reason`.

- NEEDS-HUMAN — **Two user-visible replies change, but no text or test pins them.**
  - Scope (5): "With no backend configured — the interactive default until #77 — the reply says so." The brief gives no literal and no criterion item for it. The plain `Repl(read, out)` used by `tests/test_repl.py:13-16` and `tests/test_input_modes.py:13-16,21-24` is exactly the no-backend case. Their pinned M0.8 replies will be rewritten to whatever Do picks, and nothing in the criterion checks it.
  - Criterion (f), "`:status` lists the prompt files that were loaded", gives no line format. `tests/test_input_modes.py:28-30` pins only the first status line.

  Pin both texts as literals in the criterion, as (a) and (d) already do for their replies.

- NEEDS-HUMAN — **Scope (6) also changes #92's existing error output, and no criterion covers it.** Scope (6) says the escape function is "Used by … the start-up error print in `cli.py`". The Citations list calls `cli.py:53-55` "the peer callsite". Read together, this changes #92's existing `target.toml` error print, not just the new prompts error. Criterion (c) tests only a malformed `prompts.yaml` containing U+202E. If retrofitting #92's path is intended, add a `target.toml` U+202E vector to (c). If not, say that only the new prompts error goes through the escape function. As written it is extra review surface that nothing tests.

- NEEDS-HUMAN — **The rejection rule in Scope (4)/(6) overlaps #74, which the brief puts out of scope.** The threat model gives rejection of "proposals with bidi or control characters" to #74 (`threat_model.md:128-129`: "proposals with bidi or control characters are rejected (#74)"). The brief makes the parser reject them here, and lists "the confirm UI" (#74) as out of scope. Doing it here is defensible, because the parser has to apply the same predicate. But the brief should say that #74's rejection duty moves to this bundle, or that it is shared. Otherwise #74's plan will duplicate it, or remove it as already done.

- NEEDS-HUMAN — **The `:context` text form is underspecified, so criterion (a) partly checks itself.** Design says "a line `--- <role> ---` followed by the message content; messages separated by one `\n`". It doesn't say whether a `\n` separates the header from the content, or whether output ends with a trailing newline. Criterion (a) makes the test "re-implement that form inline". Do writes both the serializer and the test, so whatever separator Do chooses will pass "byte for byte". The form is also the contract #11 and #77 build on. Spell it out exactly, for example `"--- system ---\n" + content`, joined with `"\n"` and no trailing newline, so the test checks the brief and not Do's choice.

What I could not fault: the falsifiability path. Imports happen inside test functions; on main, natural-language input gets the M0.8 reply (`repl.py:25-28`) and `:context` gets the placeholder (`input_modes.py:98,105`). Both give a real RED. The 4300-digit and lone-surrogate vectors are valid, the escaping rules separating a real ESC from typed `\x1b` are falsifiable, and `Conflicts with: 62` and `Depends on: 92` resolve in `dependency-state.json` (92 exists, COMPLETE).

> **pdca:** Bash was unavailable to this reviewer. The vendor sandbox could not start on this host, so every Bash call it made failed before running (`apply-seccomp: write /proc/self/setgroups (nested userns is capability-restricted; caller must provide CAP_SYS_ADMIN): Permission denied`) and it ran no commands; this review was delivered without Bash.

<!-- pdca:leaf-complete -->

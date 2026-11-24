Bash was unavailable in this run (apply-seccomp: nested userns denied); the review used Read/Grep/Glob only.

# Plan advisory — plan-reviewer (issue 141, re-plan round 4)

What I checked and found correct: the target and dependency. `dependency-state.json` shows `140` exists and is `COMPLETE`. Every `session.py` citation matches the target source: `D` write `:125`, user loop `:126-131`, hook element `:177`, `H` capture `:145-154`, stderr dropped at `:139`/`:151`/`:159`/`:177`. The spec lines `:62`, `:148-165`, `:183-205`, `:217-231` and `:323-324`, and the threat model's `:181-188`, are also correct. The v3 defect framing holds up against the source: user `PROMPT_COMMAND` elements run after the `D` write, and the top-level DEBUG trap fires before `\__nls_snap "$(\builtin trap -p)"`. The findings below are the real faults.

- NEEDS-HUMAN — **The Docs list leaves out the spec's reference rcfile, and an existing test requires it to match the code byte for byte.** `tests/test_session.py:932-937` asserts `session_mod.RCFILE.split("\n", 1)[1] == reference`, the code block at `docs/design/specs/pty-protocol/v1.md:58-137`. Spec §1.2 (`v1.md:44-54`) is the normative "rcfile MUST" list. Every rcfile change in this brief will break that #140 test unless the reference block is updated in the same way: the new `H` rows, `2>&1` on every substitution, `readonly PS4`, and the new reading point or record. `readonly PS4` also needs a §1.2 MUST bullet. The brief's Docs section names §1 "What this protects", §3, §4.2 and Open questions, but not §1.2 or the §1.3 code block. Also, `v1.md:139` says "The hooks call no external program, only bash builtins". Any record or fd added for the reading point (the v3 approach was an "fd-4 wait after `D`") has to keep that sentence true, or the brief should say to change it.

- NEEDS-HUMAN — **The scope contradicts its own out-of-scope list (sequencing and the prompt rule).** In scope: "`pty_protocol.py` (reason codes, any record or sequencing change the reading points need)". It also says to check for a stopped bash "on every poll tick of #140's prompt-rule wait loop". Out of scope: "anything #140 owns (parser, sequencing, paste filter, prompt rule, …)". Do will have to break one of these two lines.
  - The name "#140's prompt-rule wait loop" is ambiguous. `session.py:614` `_wait_for_prompt` runs only before a paste. The loop that can hang on a stopped bash is `_wait_for_result` (`session.py:531-578`): a SIGSTOPped bash never shows "reading terminal", so with `timeout=None` it waits forever.
  - Name the method, and state that editing it is an allowed exception to "#140 owns the prompt rule".

- NEEDS-HUMAN — **Reason codes are a hidden second change with no defined interface.** "Every degrade reason carries a fixed machine-checkable code (at least `h-changed`, …, plus #140's)". On the base, degrade reasons are free text: `ProtocolTracker.degrade(self, reason: str)` (`pty_protocol.py:172-175`) and many literal strings in `session.py` (`:562`, `:568-572`, `:577`, `:593-596`, `:625`, `:702`). "Plus #140's" means going back over every #140 degrade site, which is code #140 owns. The brief also never says how the code is exposed: an attribute on `SessionDegraded`, a `degraded_code` property, or a prefix in `reason`. Yet tests (h), (j), (r) and (s) assert on it.
  - Either limit codes to the new triggers, or name the API and accept the #140 call-site edits explicitly.
  - Say whether #140's existing tests that match `degraded_reason` text must stay unchanged.

- NEEDS-HUMAN — **`HOOK_BUILTINS` is defined as "every builtin the hooks call", but the listed minimum doesn't match the rcfile.**
  - The list includes `read`, which no hook calls. Grep finds no `read` builtin in `RCFILE` `session.py:95-179`.
  - Test (s) checks "each appears in the rcfile text", so `read` would pass only as a substring of the new `readonly PS4`. That check can't tell a called builtin from a substring.
  - The list leaves out builtins the hooks do call: `return` (`:107`), `shift` (`:120`), `:` (`:118`, `:128`, `:130`), and `unset` (`:176`, `:178`, start-up only).
  - Either derive the tuple from the rcfile, with the test matching `\builtin <name>` tokens rather than substrings, or say why `return`, `shift` and `:` are left out.

- NEEDS-HUMAN — **The falsifiability claim about v3 is internally inconsistent, so the (h2) red-leg argument doesn't stand yet.** Prior art says v3 had a "full termios compare at the prompt", and Defect says v3 "read the terminal at `D`" and the `-isig` paste went through 10 of 10 times. Readline's prep leaves ISIG as the shell set it, so a full compare at the prompt against a startup baseline should have caught `stty -isig`, unless v3's prompt baseline or reference was the `D`-time reading.
  - The brief should say why v3's prompt-time compare missed it, for example "compared against the D reading, not the first-prompt baseline".
  - Otherwise the claim that "(h2) goes red against v3's approach" can't be checked, and Do may rebuild the same blind spot.
  - Relatedly, reading point (b) alone (pre-paste, readline state, against the first-prompt baseline) seems to cover every (h2) `stty` variant. The brief should say which test needs reading point (a) and would fail with only (b). If none does, (a) is extra scope without a test that proves it.

- NEEDS-HUMAN — **The tracker issue and the brief disagree on PS4.** notes.json (issue body) says "`xtrace`, `PS4`, `BASH_XTRACEFD` values (decision 13; reuse the v5 detection)" go in `H`. The brief moves PS4 out of `H` and makes it `readonly` (decision 3, human 2026-10-17). It also changes the (r) expectation to "output contains `PS4: readonly variable`, degraded `h-changed` (from `BASH_XTRACEFD`)". Same for (j): the issue says "`stty icanon`/`-echo` not tested: readline resets both per line", but the brief adds `stty -icanon -echo -isig`. The human settled these, which is fine, but the issue body is now stale against the brief.
  - Record the divergence in the PR or issue so Check reviewers grade against the brief.
  - The brief should also say whether `declare -p PS4`, the readonly attribute, belongs in `H`. As written, nothing would notice if `PS4` lost its readonly state on some path.

> **pdca:** Bash was unavailable to this reviewer. The vendor sandbox could not start on this host, so every Bash call it made failed before running (`apply-seccomp: write /proc/self/setgroups (nested userns is capability-restricted; caller must provide CAP_SYS_ADMIN): Permission denied`) and it ran no commands; this review was delivered without Bash.

<!-- pdca:leaf-complete -->

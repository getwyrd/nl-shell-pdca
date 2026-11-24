# Adversarial review — ast-policy-gate-shell-layer (round 5)

I re-ran the proof myself instead of relying on the gate logs. I installed the pinned `tree-sitter==0.26.0` and `tree-sitter-bash==0.25.1` into a venv in my scratch directory. `tests/test_policy_gate.py` gives 211 passed against `$PDCA_TARGET`. The red leg is trivially true: `nl_shell.gate` does not exist on `main`, so every test fails on import (gate-logs/C4-verify.log). The tests call the production `classify` / `walk`; I found no mirror copy of the code. I checked the round-4 fixes against real bash 5.3.9 and the pinned grammar:

- Here-docs on one line (`|`, `&`, `;`, two `<<` on one command, a function body piped into a here-doc) all fail closed.
- Descriptor paths (`/dev/fd/3/`, `/proc/self/fd/./3`, `/proc/1/../self/fd/3`, `/proc/self/cwd/…`) are rejected.
- The parse-time cap holds: `$[`, `a=(` and `${` at the 64 KiB cap stop at about 0.52 s, and node-heavy inputs stop at 0.6 s or less.

One required fix is still open:

- NEEDS-HUMAN [impl] — **An extglob pattern in the middle of a redirect target is not rejected.** This breaks the round-4 requirement and the threat model's claim. The check `_extglob_after` (`src/nl_shell/gate/parse.py:460-469`, called at `:713`) only fires when the target word *ends* in `?*+@!` and a `(` follows. For `echo hi >/dev/fd/3@(x|)`, tree-sitter-bash parses the target as `(concatenation (word) (ERROR) (word))`, with text `/dev/fd/3@(x`. That word ends in `x`, so `_extglob_after` is False. `_pattern` (`:445-457`) gets `shape=None` from `_evaluate` because of the ERROR child, so it is False too. `target.value` is None, so the `/dev/fd` check at `:767-773` is skipped as well.
  - Gate result: `mutating`, `rejected=False`, reasons `("unparseable…", "output redirection: '>/dev/fd/3@(x'", "not allowlisted")`. `>>/dev/fd/3@(x|)` and `cat </dev/fd/3@(x|)` give the same unrejected result.
  - Real bash 5.3.9 with extglob: `exec 3>f1; echo via-ext >/dev/fd/3@(x|)` writes `via-ext` into `f1`. That is fd 3, the control channel. `3*(x)` also writes to fd 3, but the gate does catch that one, through the `*`.
  - This contradicts `.oss-scanner/threat_model.md:129-130` ("a target bash would glob, extglob (`@(…)`, `+(…)`, `!(…)`) … is rejected"). It also does not meet the round-4 sign-off item, which said: "treat a file-redirect target followed by "(" … as a pattern, **or reject any file redirect inside a tree with an ERROR node**". Neither was done for this shape. The parser does see an ERROR here, but only for the target's *content*.
  - Fix: in `_Walker.redirect`, treat the target as a pattern when it contains an `ERROR` descendant or any unquoted `?(`/`*(`/`+(`/`@(`/`!(`. Simpler: reject every `file_redirect` when `self.result.unparseable` is set, the same way the here-doc path already does at `:721-724`.
  - Test: add `echo x >/dev/fd/3@(x|)`, `echo x >>/dev/fd/3@(x|)` and `cat </dev/fd/3@(x|)` to the extglob cases at `tests/test_policy_gate.py:309-314`. All four current cases there put the extglob at the end of a word, so this shape is never exercised.

- NEEDS-HUMAN [human] — **A tilde target and a cd-then-relative target both reach fd 3. This is disclosed, but the human should rule on it with the open `>$F` question.** In real bash, `exec 3>f4; echo via-tilde >~/../../../../../../dev/fd/3` writes to `f4`. So does `(cd /dev/fd; echo via-cd >3)`. The gate classes both as `mutating`, not rejected:
  - In `_descriptor_path` (`src/nl_shell/gate/parse.py:562-563`), the value starts with `~`, not `/`, so the function returns None.
  - In `cd /dev/fd; echo hi >3`, the target `3` is relative.
  - `threat_model.md:131-132` does disclose both: "A target the gate cannot read (`>$F`) or a relative path in a directory such as `/dev/fd` is not rejected".
  - The cwd case is inconsistent with this round's `/proc/<pid>/cwd/` rule (`parse.py:91-93`, `:575-576`). That rule rejects reaching fd 3 through an unknown working directory. The same move with a relative path in the same line is allowed, even though the earlier `cd /dev/fd` is visible to the gate.
  - This is the same undecided scope question the sign-off kept open (non-literal / unknowable targets), so I am not filing it as a builder defect. Impact today is limited: the confirm prompt still shows, and the gate is not wired into the REPL yet.

- Could not refute:
  - The heredoc-ordering and nesting checks (`parse.py:725-730`, `:749-754`, `:1014-1020`).
  - `${ cmd; }` detection, which runs before the parse (`:342-344`). A `$\⏎{` form is caught by `_check_continuations`.
  - Moved and named descriptors: `>&3-` and `{a[0]}>` are rejected.
  - Decision C: `classify` catches every `Exception` (`src/nl_shell/gate/__init__.py:94-97`).
  - The C4 and T3 gate claims in `check-gates.json`: I reproduced the 211 green results locally, and gate-logs/T3-suite.log shows 1312 passed.

<!-- pdca:leaf-complete -->

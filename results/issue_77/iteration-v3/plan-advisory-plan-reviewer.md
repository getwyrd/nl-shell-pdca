Bash was unavailable in this run (every command failed with `apply-seccomp: write /proc/self/setgroups ... Permission denied`); this review was done with Read, Grep and Glob only.

# Plan review: issue 77 / teacher-client-dev-teacher-flag

I tried to fault the root cause and could not. The brief matches the thread (#77 body: "A non-loopback URL requires an explicit `--dev-teacher` flag ... recommend an SSH tunnel or TLS ... rejected not repaired; a LAN URL without the flag is refused"). It also flags, as an open question, where it reads the rules more strictly than the issue (ADR-0020 §3 vs ADR-0018 §5), and that reading is right: `docs/design/adr/0020-configuration-and-file-locations.md:32-34` says "Any other URL, including a loopback TCP port, is used only when the user passes `--dev-teacher`". The issues are with the base and dependencies, a conformance list the brief leaves out, and scope.

- NEEDS-HUMAN — **The base branch can't support the plan as written.** The brief targets `eduralph/nl-shell @ main` and "Depends on: 16, 92, 14", but `dependency-state.json` lists all three as `"state": "PLANNED"`, so none is merged. On `main` none of what the brief builds on exists yet:
  - `src/nl_shell/repl.py:23-26` still has the M0.8 placeholder `NATURAL_LANGUAGE_NOT_YET`. There is no backend interface, no `proposal/v1` parser or schema object, and no "no backend configured" reply.
  - `src/nl_shell/cli.py:11-18` only has `--version`. There is no `config.toml` loader and no `:status`.

  The brief admits this indirectly ("or the wave base for #14/#16/#92 code"; "#16's backend interface ... on the wave base"), but the target line still says `main`. Criterion (a) needs "the same object #16's parser uses", (c) needs #92's `config.toml` reading, and (e) needs #14's `:status`. None of these can go red→green against `main`. The brief should name the wave base or stacked branch explicitly, or be held until #16, #92 and #14 merge. Otherwise Do invents those interfaces and they conflict with the real ones.

- NEEDS-HUMAN — **The brief leaves out a conformance rule that names #77.** `docs/design/specs/proposal/v1.md:70-72` says: "The parser tests (#16, #77) MUST include: each valid shape; extra properties; a missing `risk`; `command` with `reason`; an over-long `command`; invalid JSON; a JSON array; and a `risk` lower than the gate's class". Criterion (b) covers all of that with one case ("content that fails `proposal/v1`"). The Citations line lists only spec "§1, §5" as normative, not Conformance. The brief should either:
  - list these cases in (b), going through the client's `message.content` path, or
  - state that #16's tests satisfy the rule for #77 and why.

  The last case (risk vs the gate's class) needs the policy gate, which isn't in #77's dependencies. The brief should say so rather than skip it silently.

- NEEDS-HUMAN — **The brief says the REPL "starts it on demand", but ADR-0018 says otherwise.** `docs/design/adr/0018-model-serving-and-wire-format.md:34` says "The REPL connects to it and starts it on demand." The brief puts "starting or installing `llama-server` / the systemd user service (#48)" out of scope, and scope item (4) replies "the model server isn't running". That may be the right split, but the brief claims to build on ADR-0018 §1 and never mentions this difference. It should be stated in Alternatives or Open questions so sign-off doesn't treat it as an ADR violation.

- NEEDS-HUMAN — **The scope goes beyond the issue, and two scope items aren't tested.**
  - `teacher_model` (scope (1)) appears nowhere in #77's thread or in ADR-0018/0020. It's a new config key and a new request field. The criterion never tests that it is "sent only if set".
  - Scope (1) promises `https://` (TLS), but criterion (a)–(e) only tests `http://` and the Unix socket. As written, the TLS path ships without being exercised.

  Either cut both or add a test for each. (`:status` in (5) is fine: ADR-0020 §4 requires it.)

- NEEDS-HUMAN — **The timeout case in (b) can't be run with a short timeout unless the brief says how.** (b) requires "a server that doesn't answer within the timeout", and the Test-file note says "every network wait has a short timeout". The Design section, though, gives a constant for the size cap (64 KiB) and nothing for the connect/read timeouts. It doesn't say whether they are injectable either. If Do hard-codes a realistic read timeout (tens of seconds), that test either becomes slow or gets weakened. The brief should name the timeout constants and require them to be overridable from tests.

- NEEDS-HUMAN — **The "no TCP connection" promise has no test.** Impact says "With no flag nl-shell makes no TCP connection at all", which is the ADR-0003 must-hold ("no outbound connection in the default config", threat model line 130). (c) only shows that a fake server at the config URL "receives nothing". That doesn't prove no other TCP connection was opened, for example to a guessed default. One option is a test that patches `socket.create_connection` / `socket.socket.connect` and asserts no AF_INET connection on the default path. Without some such test, the main security claim is something a reviewer has to trust.

> **pdca:** Bash was unavailable to this reviewer. The vendor sandbox could not start on this host, so every Bash call it made failed before running (`apply-seccomp: write /proc/self/setgroups (nested userns is capability-restricted; caller must provide CAP_SYS_ADMIN): Permission denied`) and it ran no commands; this review was delivered without Bash.

<!-- pdca:leaf-complete -->

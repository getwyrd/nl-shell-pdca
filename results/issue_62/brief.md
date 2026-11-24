# Brief — issue 62 / failure-classes-by-exit-code (parent, split)

> Re-plan after iterate-plan (iteration-v3 sign-off: "too big; split in Plan; settle the
> product calls at Plan"). This parent is split into two children; the decisions below
> were confirmed by the human at Plan on 2026-10-19 and bind both children.

- **Slug:** failure-classes-by-exit-code
- **Defect:** nl-shell has no deterministic first pass that classifies a failed command by its trusted exit status before anything is sent to a model (issue #62, M0.12).
- **Success criterion:** both children are accepted: (child-1) `tests/test_failure_classes.py` passes on the wave base; (child-2) `tests/test_command_provider.py` passes on main.
- **Falsifiability:** per child — each child's test file goes red on the shipped C4 gate (`engine/scripts/run-verify.sh`) with its production change reverted.
- **Repo + branch target:** eduralph/nl-shell @ main
- **Depends on:** 140
- **Ordering note:** #92 (target loader) is merged (PR #142). #10 was split; its done-record type `session.CommandResult` comes from #140 (PR #146, COMPLETE, not yet merged), so the classifier child depends on 140 and builds on the folded wave base. The provider child depends on nothing open. #65 (the thread's prerequisite) is met: closed with ADR-0014 and `pty-protocol/v1`.
- **Surfaces:** data
- **Difficulty:** medium
- **Scope:** split into (1) the failure classifier with an injected lookup callable, (2) the ubuntu-26.04 command-not-found provider. / out of scope: offering/running corrections (#17), `?why` (#14), calling the reader (#61), the policy gate's parse (#12), REPL wiring.
- **External dependencies:** none
- **Test file:** `tests/test_failure_classes.py` (child-1), `tests/test_command_provider.py` (child-2)
- **Disposition hint:** new-feature

## Decisions confirmed by the human at Plan (bind the children)

1. **Privileged rule.** The command is privileged if ANY shell word anywhere in the confirmed text — after `|`, `&&`, `||`, `;`, `&`, inside `$(…)`/backticks, behind `env`/`time`/`nohup`/assignments — or any word in the value of a snapshot alias whose name appears as a word, has a basename in: `sudo su pkexec doas run0 machinectl` (policy-gate spec §4, `docs/design/specs/policy-gate/v1.md:111`) plus the host aliases `sudo-rs sudo.ws sudoedit sudoedit-rs`. A privileged command with any non-zero status other than 130 → privilege class: one fixed neutral message, no correction offer, not sent to the reader. Accepted cost: #17 never offers a fix for a failed privileged command.
2. **Nothing ran (`ran=False`).** Confirmed text blank or comment-only → no failure. Otherwise → syntax error, handled as "other" (correction allowed, to the reader).
3. **Only `session.CommandResult` is accepted.** A bare `pty_protocol.Done` (no `ran`) raises `TypeError`.
4. **127 suggestion rule.** Suggest a package only when the command is one simple command (no list, pipe, substitution, leading assignment) AND its first word did not resolve: not a snapshot function or alias, not a bash builtin/keyword, not an executable file in any `snapshot.path` directory.

## STOP discipline

Draft only until Check sign-off. The PR MUST NOT be marked ready before sign-off accepts.

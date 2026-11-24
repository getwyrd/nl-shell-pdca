"""The policy gate's command layer (issue #204, spec ``policy-gate/v1`` §4, §4.1, §5).

Covers the command table's coverage (class 1), unread argv (class 2), the class-7 and
path gaps (documented, not raised), §4/§5, decisions A, B (placeholder), C and D (a
command word the gate cannot read is a possible ``sudo``), and the fixed load location.

Every case goes through the public ``nl_shell.gate.classify``. ``nl_shell.gate`` and the
table loader are imported inside each test, and the command table and the inventory are
read inside each test, so a tree without them fails tests instead of failing to collect.

Each case asserts a class (exact, or a floor), a reason substring, and that no reason is
"could not class" (decision C), except where a case is about decision C.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = REPO_ROOT / "targets" / "ubuntu-26.04"
RANK = {
    "read-only": 0,
    "mutating": 1,
    "session-altering": 1,
    "destructive": 2,
    "privileged": 3,
}
COULD_NOT = "could not class"
NA = "not allowlisted"
CANNOT_READ = "runs code the gate cannot read"
UNKNOWN_OPTION = "option the gate does not know"
PIPE_INTO = "pipe, here-doc or here-string into"
UNDECLARED = "--pdca-undeclared"
ELEVATING = "elevating command"
NAMES_ELEVATING = "argument names an elevating command"
ROOT_SHELL = "root shell"
UNREADABLE = "command word the gate cannot read"
OUTSIDE = "path outside the system directories"
NO_COMMAND = "with no command"


def classify(command: str, origin: str = "typed"):
    from nl_shell import render
    from nl_shell.gate import classify as gate_classify

    result = gate_classify(command, origin=origin)
    for reason in result.reasons:  # Rule 6 holds for the new reasons too
        for char in reason:
            code = ord(char)
            assert not (code < 0x20 or 0x7F <= code <= 0x9F), (command, reason)
            assert not render.is_hidden(char), (command, reason)
    return result


def has_reason(result, needle: str) -> bool:
    return any(needle in reason for reason in result.reasons)


def check(
    command: str,
    *,
    floor: str | None = None,
    exact: str | None = None,
    reason: str | None = None,
    rejected: bool | None = None,
    origin: str = "typed",
    decision_c: bool = False,
):
    result = classify(command, origin)
    where = (command, origin, result)
    if exact is not None:
        assert result.cls == exact, where
    if floor is not None:
        assert RANK[result.cls] >= RANK[floor], where
    if rejected is not None:
        assert result.rejected is rejected, where
    if reason is not None:
        assert has_reason(result, reason), where
    if not decision_c:
        assert not has_reason(result, COULD_NOT), where
    return result


def rejected_proposal(command: str, reason: str):
    return check(
        command, exact="privileged", reason=reason, rejected=True, origin="proposal"
    )


def table_doc() -> dict:
    return tomllib.loads((TARGET / "commands.toml").read_text(encoding="utf-8"))


def effect_names(effects) -> set[str]:
    return {e if isinstance(e, str) else e["effect"] for e in effects or []}


@pytest.fixture
def fresh_table():
    """Clear the loader's cache before and after, so a test's table never leaks."""
    from nl_shell.gate import commands

    commands.table.cache_clear()
    yield commands
    commands.table.cache_clear()


# --- class 1: coverage -----------------------------------------------------------------

REQUIRED_INVENTORY = (
    "sudo",
    "sudo.ws",
    "sudo-rs",
    "sudoedit-rs",
    "su",
    "su-rs",
    "pkexec",
    "passwd",
    "chsh",
    "crontab",
    "mount",
    "sh",
    "bash",
    "rbash",
    "dash",
    "screen",
    "python3",
    "perl",
    "busybox",
    "gdb",
    # Iteration 2: interpreters outside the dpkg sections `shells`/`interpreters`.
    "ruby",
    "node",
    "nodejs",
    "awk",
    "mawk",
    # Iteration 4: setuid on the reference host, found by re-running the harvest there.
    "mount.cifs",
    "mount.smb3",
)


def test_class1_every_inventory_name_has_a_row():
    from nl_shell.gate import commands

    inventory = tomllib.loads((TARGET / "inventory.toml").read_text(encoding="utf-8"))
    assert inventory["host_version"].startswith("26.04.1"), inventory["host_version"]
    names = [entry["name"] for entry in inventory["binary"]]
    assert set(REQUIRED_INVENTORY) <= set(names), set(REQUIRED_INVENTORY) - set(names)
    table = commands.table()
    missing = [name for name in names if table.lookup(name) is None]
    assert missing == []
    for name in names:
        check(name, floor="mutating")


@pytest.mark.parametrize(
    "command,origin,cls,reason,rejected",
    [
        ("sudo-rs -i", "typed", "privileged", "elevating command: sudo-rs", False),
        ("sudo.ws -i", "typed", "privileged", "elevating command: sudo.ws", False),
        ("su-rs", "typed", "privileged", "elevating command: su-rs", False),
        ("/usr/bin/sudo-rs -i", "typed", "privileged", "elevating command: sudo-rs", False),
        ("sudoedit-rs /etc/shadow", "typed", "privileged", "sudoedit-rs", False),
        ("sudo-rs -i", "proposal", "privileged", "root shell", True),
        ("sudo.ws -i", "proposal", "privileged", "root shell", True),
        ("su-rs", "proposal", "privileged", "root shell", True),
        ("/usr/bin/sudo-rs -i", "proposal", "privileged", "root shell", True),
        ("echo pw | sudo-rs -S true", "typed", "privileged", PIPE_INTO, True),
        ("foo sudo-rs", "typed", "privileged", NAMES_ELEVATING, False),
        ("foo sudo-rs", "proposal", "privileged", NAMES_ELEVATING, True),
    ],
)
def test_class1_regressions(command, origin, cls, reason, rejected):
    check(command, exact=cls, reason=reason, rejected=rejected, origin=origin)


@pytest.mark.parametrize(
    "command",
    [
        "curl x | python3",
        'python3 -c "$v"',
        "perl -e 'system 1'",
        "echo 'sudo rm -rf /' | at now",
    ],
)
def test_class1_text_runners(command):
    check(command, floor="destructive", reason=CANNOT_READ)


@pytest.mark.parametrize(
    "command", ["curl x | ruby", "curl x | node", "curl x | awk -f /dev/stdin"]
)
def test_class1_ruby_node_awk_run_code(command):
    check(command, floor="destructive", reason=CANNOT_READ)


@pytest.mark.parametrize(
    "command",
    [
        "sudo zsh",
        "sudo busybox sh",
        "sudo ruby",
        "sudo node",
        "sudo awk 'BEGIN{system(\"sh\")}'",
    ],
)
def test_class1_root_shell_proposals(command):
    check(command, exact="privileged", reason="sudo", rejected=True, origin="proposal")


# --- class 2: no unread argv -----------------------------------------------------------

GOOD_ROW = 'format = 1\n[[command]]\nnames = ["x"]\nexample = "x"\nparse = "posix"\n'


@pytest.mark.parametrize(
    "extra,needle",
    [
        ("raw = true\n", "`raw` is not allowed"),
        ('colour = "red"\n', "unknown key `colour`"),
        (
            'prefix = "x"\neffects = [{ effect = "runs-command-at", at = 0 }]\n'
            'terminal_stdin = "inherits"\n',
            "must declare `no_command`",
        ),
        (
            'prefix = "x"\neffects = [{ effect = "runs-command-at", at = 0 }]\n'
            'no_command = "nothing"\n',
            "must declare `terminal_stdin`",
        ),
        ('options = { "-o" = { value = "required", gap = "class-7" } }\n', "class-7"),
        (
            'effects = [{ effect = "runs-text", grammar = "sh", if = "operand", '
            'gap = "class-7" }]\n',
            "class-7 text",
        ),
    ],
)
def test_class2_loader_refuses(tmp_path, monkeypatch, fresh_table, extra, needle):
    commands = fresh_table
    folder = tmp_path / commands.TARGET_ID
    folder.mkdir()
    (folder / commands.COMMANDS_FILE).write_text(GOOD_ROW + extra, encoding="utf-8")
    monkeypatch.setattr(commands, "TARGETS_ROOT", tmp_path)
    with pytest.raises(commands.CommandsError) as info:
        commands.load()
    assert needle in str(info.value)
    # Through the gate: decision C, never a silent mutating.
    check("x", exact="privileged", rejected=True, reason=COULD_NOT, decision_c=True)


def undeclared_cases() -> list[tuple[str, bool]]:
    """``(command, elevating)``: each row's example with ``--pdca-undeclared`` right after
    the command word, and right after each described subcommand."""
    out = []
    for row in table_doc()["command"]:
        if row.get("fixed"):
            continue
        word, _, rest = row["example"].partition(" ")
        elevating = "elevates" in effect_names(row.get("effects"))
        out.append((f"{word} {UNDECLARED} {rest}".strip(), elevating))
        for key, sub in (row.get("subcommands") or {}).items():
            sub_elevating = elevating or "elevates" in effect_names(sub.get("effects"))
            for name in key.split("|"):
                out.append((f"{word} {name} {UNDECLARED}", sub_elevating))
    return out


def test_class2_undeclared_option_on_every_row():
    cases = undeclared_cases()
    assert len(cases) > 80
    assert ("git clean " + UNDECLARED, False) in cases
    for command, elevating in cases:
        check(command, floor="destructive", reason=UNKNOWN_OPTION)
        if elevating:
            check(command, floor="privileged", rejected=True, origin="proposal")


def test_class2_every_row_has_an_example():
    rows = table_doc()["command"]
    assert all(isinstance(row.get("example"), str) and row["example"] for row in rows)
    for row in rows:
        check(row["example"], floor="mutating")


def no_command_shells() -> list[str]:
    out = []
    for row in table_doc()["command"]:
        grammars = [row, *(row.get("subcommands") or {}).values()]
        if any(g.get("no_command") == "opens-shell" for g in grammars):
            out.append(row["prefix"])
    return out


def gives_no_command_reason(prefix: str, reason: str) -> bool:
    """The engine's reason for a row (or its subcommand) that opens a shell with no
    command: ``proposal opens a root shell: <command> [<subcommand>] with no command``."""
    head = f"root shell: {prefix.split()[0]}"
    return head in reason and reason.endswith(NO_COMMAND)


def test_class2_no_command_opens_a_shell_under_sudo():
    prefixes = no_command_shells()
    assert {"chroot /", "unshare", "pkexec", "screen"} <= set(prefixes)
    for prefix in prefixes:
        result = check(f"sudo {prefix}", exact="privileged", rejected=True, origin="proposal")
        # The rejection comes from the row's "with no command" declaration, not only
        # from the name rule.
        assert any(gives_no_command_reason(prefix, r) for r in result.reasons), (
            prefix,
            result,
        )


@pytest.mark.parametrize(
    "command",
    [
        "sudo bash -s x",
        "sudo bash -is x",
        "sudo dash -s x",
        "sudo env bash -s x",
        "pkexec bash -s x",
        "sudo bash /dev/stdin",
        "sudo chroot /",
        "sudo unshare",
    ],
)
def test_class2_regressions(command):
    check(command, exact="privileged", reason="shell", rejected=True, origin="proposal")


@pytest.mark.parametrize(
    "command,reason",
    [
        ("sudo chroot /", "root shell: chroot with no command"),
        ("sudo unshare", "root shell: unshare with no command"),
    ],
)
def test_class2_no_command_reason(command, reason):
    check(command, exact="privileged", reason=reason, rejected=True, origin="proposal")


def test_class2_enable_loads_code():
    check("enable -f /tmp/x.so foo", floor="destructive", reason=CANNOT_READ)


# --- class 7 and the floor: documented, not raised -------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "foo 'sudo -i'",
        "git -c core.pager=sh log",
        "git status",
        "tar --to-command=sh -xf a.tar",
        "ssh -o ProxyCommand=sh h",
        "awk 'BEGIN{system(\"id\")}'",
    ],
)
def test_class7_floor_documented_not_raised(command):
    check(command, exact="mutating", reason=NA, rejected=False)


@pytest.mark.parametrize("command", ["./x -i", "/tmp/x -i", "~/bin/x -i"])
def test_class7_floor_path_gap_documented_not_raised(command):
    # A path outside the system directories whose last part names no row: what it
    # points to is §7 live-session resolution (#192), recorded as a gap.
    check(command, exact="mutating", reason=OUTSIDE, rejected=False, origin="proposal")


# --- spec §4: privileged ---------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "sudo apt update",
        "su",
        "pkexec",
        "doas",
        "run0",
        "machinectl shell",
        "machinectl shell root@",
        "//usr/bin/sudo true",
    ],
)
def test_spec4_privileged(command):
    check(command, exact="privileged", reason=ELEVATING)


@pytest.mark.parametrize("command", ["./sudo -i", "~/sudo -i", "/usr/bin/sudo-rs -i"])
def test_spec4_path_lookup_uses_the_last_part(command):
    check(command, exact="privileged", reason="elevating command: sudo")
    rejected_proposal(command, ROOT_SHELL)


# --- spec §4: destructive --------------------------------------------------------------


@pytest.mark.parametrize(
    "command,reason",
    [
        ("rm -rf build", "destructive command: rm -r"),
        ('"r"m -rf ~', "destructive command: rm -r"),
        ("ls; rm -rf ~", "destructive command: rm -r"),
        ("systemctl stop ssh", "destructive command: systemctl stop"),
        # Row 9 (derived): `{}` is a word the gate cannot read, and rm with such an
        # operand is classed like rm with a glob.
        ("find . -exec rm {} \\;", "rm with an operand the gate cannot read"),
        ("dd if=a of=b", "destructive command: dd"),
        ("mkfs.ext4 /dev/sdz1", "destructive command: mkfs.ext4"),
        ("wipefs -a /dev/sdz", "destructive command: wipefs"),
        ("shred f", "destructive command: shred"),
        ("truncate -s 0 f", "destructive command: truncate"),
        ("chmod -R 755 d", "destructive command: chmod -R"),
        ("find . -delete", "find -delete"),
        ("git clean -fd", "destructive command: git clean"),
        ("git reset --hard", "destructive command: git reset --hard"),
        ("git push --force", "destructive command: git push --force"),
        ("kill -9 -1", "kill -1"),
    ],
)
def test_spec4_destructive(command, reason):
    check(command, exact="destructive", reason=reason)


# --- spec §4: wrappers -----------------------------------------------------------------


def wrapper_prefixes() -> list[str]:
    out = []
    for row in table_doc()["command"]:
        grammars = [row, *(row.get("subcommands") or {}).values()]
        effects = set()
        for grammar in grammars:
            effects |= effect_names(grammar.get("effects"))
            for option in (grammar.get("options") or {}).values():
                effects |= effect_names(option.get("effects"))
        if "runs-command-at" in effects:
            assert row.get("prefix"), row["names"]
            out.append(row["prefix"])
    return out


def test_spec4_every_wrapper_classes_its_inner_command():
    prefixes = wrapper_prefixes()
    assert {"env", "nice", "nohup", "timeout 5", "time", "xargs", "watch"} <= set(prefixes)
    named = {"find . -exec", "sudo", "busybox", "exec", "command", "coproc"}
    assert named <= set(prefixes)
    for prefix in prefixes:
        check(f"{prefix} rm -rf x", floor="destructive", reason="rm")
        check(f"{prefix} sudo -i", exact="privileged", rejected=True, origin="proposal")
        rejected_proposal(f"{prefix} $x -i", UNREADABLE)


@pytest.mark.parametrize(
    "command",
    ["nice true", "nohup true", "timeout 5 true", "time true", "xargs true", "watch true"],
)
def test_spec4_wrappers_are_at_least_mutating(command):
    check(command, floor="mutating", reason=NA)


@pytest.mark.parametrize(
    "command",
    [
        "nice rm -rf x",
        "nohup rm -rf x",
        "timeout 5 rm -rf x",
        "time rm -rf x",
        "watch rm -rf x",
    ],
)
def test_spec4_wrappers_take_the_inner_class(command):
    check(command, exact="destructive", reason="destructive command: rm -r")


def test_spec4_named_wrappers():
    check("env rm -rf x", exact="destructive", reason="destructive command: rm -r")
    check("env - rm -rf ~", exact="destructive", reason="destructive command: rm -r")
    check("xargs $x", exact="privileged", reason=UNREADABLE)
    check("find . -exec $x {} \\;", exact="privileged", reason=UNREADABLE)
    for command in (
        "env - sudo -i",
        "env 'A=1' sudo -i",
        "env -a x sudo -i",
        "exec -a x sudo -i",
        "nice -n5 sudo -i",
        "timeout -s9 5 sudo -i",
        "stdbuf -o0 sudo -i",
        "setsid sudo -i",
        "flock /tmp/l sudo -i",
    ):
        rejected_proposal(command, ROOT_SHELL)


def test_spec4_xargs_replace_strings():
    for command in ("xargs -I% sudo % true", "xargs -o -I% sudo %"):
        rejected_proposal(command, "cannot read")
    for command in (
        "xargs -I% git reset %",
        "xargs -I% chown % bob /",
        "xargs --replace=@ chown @ x",
    ):
        check(command, floor="destructive", reason="cannot read")


def test_spec4_xargs_replace_string_inside_a_word():
    # The replace string occurs inside `sudo`; the literal word is still checked.
    for command in ("xargs -Is sudo -i", "xargs -Isudo sudo -i"):
        rejected_proposal(command, NAMES_ELEVATING)


def test_spec4_ten_nested_envs():
    command = "env " * 10 + "sudo -i"
    result = classify(command, "proposal")
    assert result.cls == "privileged" and result.rejected, result
    assert has_reason(result, "root shell") or has_reason(result, COULD_NOT), result


# --- spec §5: sudo rules ---------------------------------------------------------------


@pytest.mark.parametrize(
    "command,reason",
    [
        ("sudo -S true", "sudo -S"),
        ("sudo -p x true", "sudo -p"),
        ("sudo -A true", "sudo -A"),
        ("echo pw | sudo -S true", PIPE_INTO),
        ('sudo "-S" true', "sudo -S"),
        ("sudo $'-S' true", "sudo -S"),
        ('sudo "$P" true', "cannot read where sudo takes options"),
        ("sudo -s <<<x", PIPE_INTO),
        ("printf x | sudo -i", PIPE_INTO),
        ("echo x | sudo true", PIPE_INTO),
        ("sudo true <<<x", PIPE_INTO),
        ("sudo true <<E\nx\nE", PIPE_INTO),
        ("echo x | su", PIPE_INTO),
        ("su <<<x", PIPE_INTO),
        ("echo x | pkexec true", PIPE_INTO),
        ("pkexec true <<<x", PIPE_INTO),
        ("echo x | doas true", PIPE_INTO),
        ("doas true <<E\nx\nE", PIPE_INTO),
        ("cat <<E | sudo tee /x\nx\nE", PIPE_INTO),
        ("cat <<E | doas id\nx\nE", PIPE_INTO),
    ],
)
def test_spec5_rejected(command, reason):
    for origin in ("typed", "proposal"):
        check(command, exact="privileged", reason=reason, rejected=True, origin=origin)


@pytest.mark.parametrize(
    "command", ["sudo.ws --stdi true", "sudo --stdi true", "sudo.ws --prom=x true"]
)
def test_spec5_long_option_prefixes_rejected(command):
    # The original sudo takes any unambiguous prefix of a long option (getopt_long).
    for origin in ("typed", "proposal"):
        check(
            command, exact="privileged", reason=UNKNOWN_OPTION, rejected=True, origin=origin
        )


@pytest.mark.parametrize(
    "command",
    [
        "sudo -k true --pdca-undeclared",
        "sudo -k git -c core.pager=sh log",
        "sudo --reset-timestamp git -c core.pager=sh log",
        "sudo-rs -k git -c core.pager=sh log",
        "sudo -k bash",
    ],
)
def test_spec5_sudo_k_still_classes_the_inner_command(command):
    check(command, exact="privileged", reason="proposal", rejected=True, origin="proposal")


@pytest.mark.parametrize(
    "command", ["sudo -i", "sudo -s", "sudo su", "sudo bash", "su", "pkexec bash"]
)
def test_spec5_root_shells(command):
    rejected_proposal(command, ROOT_SHELL)
    check(command, exact="privileged", reason="interactive shell", rejected=False)


# --- decision A ------------------------------------------------------------------------


def test_decision_a():
    check("foo sudo x", exact="privileged", reason=NAMES_ELEVATING, rejected=False)
    rejected_proposal("foo sudo x", NAMES_ELEVATING)
    check("foo rm -rf x", floor="destructive", reason="names a destructive command")
    # ANSI-C words decode like any quoted word.
    rejected_proposal("$'\\x73udo' -i", ROOT_SHELL)
    check("echo pw | $'\\x73udo' -S true", exact="privileged", reason="-S", rejected=True)
    check("foo $'\\x73udo'", exact="privileged", reason=NAMES_ELEVATING)
    # bash stops an ANSI-C string at a NUL; so does the decoder.
    rejected_proposal("$'sudo\\0ignored' -i", ROOT_SHELL)
    check("$'rm\\0ignored' -rf build", exact="destructive", reason="rm -r")
    check("foo $'sudo\\0ignored'", exact="privileged", reason=NAMES_ELEVATING)


def test_decision_a_locale_quoting():
    # `$"…"` is never read: bash translates it through the catalog TEXTDOMAIN and
    # TEXTDOMAINDIR name, so it may spell any word (iteration 4: fail closed).
    rejected_proposal('$"sudo" -i', UNREADABLE)
    check('$"rm" -rf build', floor="destructive", reason=UNREADABLE)
    check('foo $"sudo"', exact="privileged", reason="cannot decode")
    rejected_proposal('foo $"sudo"', "cannot decode")


def test_decision_a_ansi_c_brace_hex():
    # bash 5.3 reads `\x{HH..}`: every hex digit, the low byte kept.
    rejected_proposal("$'\\x{73}udo' -i", ROOT_SHELL)
    check("echo pw | $'\\x{73}udo' -S true", exact="privileged", reason="-S", rejected=True)
    check("foo $'\\x{73}udo'", exact="privileged", reason=NAMES_ELEVATING)
    check("$'\\x{72}m' -rf build", exact="destructive", reason="rm -r")
    check("$'\\x{172}m' -rf build", exact="destructive", reason="rm -r")


@pytest.mark.parametrize(
    "command", ["$'\\ud800udo' -i", "foo $'\\ud800'", "env $'\\ud800' -i"]
)
def test_decision_a_undecodable_ansi_c_fails_closed(command):
    check(command, exact="privileged", reason="cannot decode", rejected=False)
    rejected_proposal(command, "cannot decode")


def test_decision_a_nonliteral_command_word():
    check("$x sudo", exact="privileged", reason=NAMES_ELEVATING, rejected=False)
    rejected_proposal("$x sudo", NAMES_ELEVATING)
    check("$x rm -rf x", exact="privileged", reason="names a destructive command")
    rejected_proposal('env "$x" sudo', NAMES_ELEVATING)


@pytest.mark.parametrize(
    "command",
    [
        "sudo bash $x",
        "sudo env $x bash",
        "sudo nice $x bash",
        "sudo xargs -o bash",
        "sudo busybox --pdca",
        "sudo script",
        "sudo strace bash",
        "sudo setpriv bash",
        "sudo runuser -u root bash",
    ],
)
def test_elevation_reaches_inner_commands(command):
    check(command, exact="privileged", reason="proposal", rejected=True, origin="proposal")


# --- decision D: a command word the gate cannot read -----------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "/usr/bin/sud? -i",
        "/usr/bin/s*do -i",
        "/usr/*/sudo -i",
        "/usr/bin/{sudo,x} -i",
        "x=sudo; $x -i",
        "$x sudo",
        "$(echo sudo) -i",
        "`echo sudo` -i",
        "${x} -i",
        '$"$x" -i',
        'env "$x" sudo',
        "find /usr/bin -name 'sud?' -exec {} -i \\;",
        "ls /usr/bin/sud? | xargs -o -I% % -i",
    ],
)
def test_decision_d_proposals_rejected(command):
    rejected_proposal(command, UNREADABLE)


@pytest.mark.parametrize(
    "command,reason",
    [
        ("/usr/bin/s*do -S true", "sudo reads the password from stdin (§5)"),
        ("$x -p '' true", "sudo with its own password prompt (§5)"),
        ("$x -A true", "sudo reads the password through an askpass program (§5)"),
        ("$x --stdin true", "sudo reads the password from stdin (§5)"),
        ("$x --stdi true", "sudo reads the password from stdin (§5)"),
        ("$x -nS true", "sudo reads the password from stdin (§5)"),
        ("$x -px true", "sudo with its own password prompt (§5)"),
        ("$x --prompt=x true", "sudo with its own password prompt (§5)"),
        ("echo pw | $x -S true", PIPE_INTO),
        ("$x -S <<<pw", PIPE_INTO),
        ("cat <<E | $x tee /x\nx\nE", PIPE_INTO),
        ("git log | $PAGER", PIPE_INTO),
        ("echo pw | /usr/bin/s*do -S true", PIPE_INTO),
    ],
)
def test_decision_d_typed_section5_rules(command, reason):
    for origin in ("typed", "proposal"):
        check(command, exact="privileged", reason=reason, rejected=True, origin=origin)


@pytest.mark.parametrize("command", ["$x -i", "$EDITOR f"])
def test_decision_d_typed_privileged_not_rejected(command):
    check(command, exact="privileged", reason=UNREADABLE, rejected=False)


@pytest.mark.parametrize("command", ["$x rm -rf x", "$(echo rm) -rf ~"])
def test_decision_d_typed_privileged(command):
    check(command, exact="privileged", reason=UNREADABLE)


def test_decision_d_locale_quoted_command_word():
    # A `$"…"` command word is unreadable whatever its text (`$"ls"` may translate to
    # `sudo`).
    rejected_proposal('$"ls" -i', UNREADABLE)
    check('$"ls" -i', exact="privileged", reason=UNREADABLE, rejected=False)
    for origin in ("typed", "proposal"):
        check(
            'echo pw | $"ls" -S true',
            exact="privileged",
            reason="sudo reads the password from stdin (§5)",
            rejected=True,
            origin=origin,
        )
        check('echo pw | $"ls" -S true', exact="privileged", reason=PIPE_INTO, origin=origin)


@pytest.mark.parametrize("command", ["sud[o] -i", "[s]udo -i", "su[d]o -i", "s[u]d[o] -i"])
def test_decision_d_bracket_glob_command_word(command):
    # tree-sitter-bash misreads an unquoted `[` in a command word (an ERROR around a
    # subscript, or a test command glued to a word); bash runs it as a glob, which may
    # match `sudo`. The command layer still sees the word, so decision D applies, not
    # only "unparseable".
    rejected_proposal(command, UNREADABLE)
    result = check(command, exact="privileged", reason=UNREADABLE)
    assert has_reason(result, "not a literal"), result


@pytest.mark.parametrize(
    "command", ["echo pw | sud[o] -S true", "echo pw | [s]udo -S true", "ls; [s]udo -S x"]
)
def test_decision_d_bracket_glob_section5(command):
    # `ls; [s]udo -S x` parses with a missing token, not an ERROR node.
    for origin in ("typed", "proposal"):
        check(
            command,
            exact="privileged",
            reason="sudo reads the password from stdin (§5)",
            rejected=True,
            origin=origin,
        )


def test_bracket_builtin_is_not_a_glob_command_word():
    # The `[` builtin and an argument glob keep their verdicts.
    for command in ("[ -f x ]", "[[ -f x ]]", "ls x[a] y"):
        result = check(command, exact="mutating", rejected=False)
        assert not has_reason(result, UNREADABLE), result


@pytest.mark.parametrize(
    "command",
    [
        "echo x | sudo tee /x < /dev/stdin",
        "echo x | $x tee /x < /dev/stdin",
        "echo x | sudo tee /x < /dev/fd/0",
        "echo x | sudo tee /x < /proc/self/fd/0",
        "echo x | sudo tee /x < //dev//stdin",
    ],
)
def test_section5_stdin_file_naming_fd0_is_a_pipe(command):
    # `< /dev/stdin` reopens the stdin the command already had: here, the pipe.
    for origin in ("typed", "proposal"):
        check(command, exact="privileged", reason=PIPE_INTO, rejected=True, origin=origin)


def test_section5_stdin_from_a_plain_file_is_not_a_pipe():
    check("sudo tee /x < input.txt", exact="privileged", reason=ELEVATING, rejected=False)


def test_decision_d_leading_tilde_is_a_path():
    # Only a leading `~`: the command layer reads it as a path, not under decision D.
    result = check("~/bin/x -i", exact="mutating", reason=OUTSIDE, rejected=False)
    assert not has_reason(result, UNREADABLE), result


# --- text effects are decision B -------------------------------------------------------


@pytest.mark.parametrize(
    "command", ["x | sh", "bash < f", "bash f.sh", 'bash -c "$v"', 'eval "$v"', ". ./f"]
)
def test_text_effects_are_decision_b(command):
    check(command, floor="destructive", reason=CANNOT_READ)


@pytest.mark.parametrize(
    "command",
    [
        "eval sudo -S true",
        "echo pw | bash -c 'sudo -S true'",
        "env -S 'sudo -S true'",
        "echo pw | script -qc 'sudo -S true'",
    ],
)
def test_text_effect_arguments_meet_section5(command):
    # Decision A's scan reads the arguments of a text-effect row too (still decision B,
    # no recursion): an elevating row named there brings its §5 rules.
    for origin in ("typed", "proposal"):
        check(
            command,
            exact="privileged",
            reason="sudo reads the password from stdin (§5)",
            rejected=True,
            origin=origin,
        )
        check(command, exact="privileged", reason=CANNOT_READ, origin=origin)


@pytest.mark.parametrize("command", ["eval sudo -i", "env -S 'sudo -i'"])
def test_text_effect_arguments_naming_sudo(command):
    rejected_proposal(command, "sudo named in code the gate cannot read")
    check(command, exact="privileged", reason=CANNOT_READ, rejected=False)


# --- bracket repair cost, coproc, and code text in option values ----------------------


@pytest.mark.parametrize(
    "unit",
    [
        "$[",
        "[$[",
        "[a]$[",
        "sud[o] -i; ",
        "{ sud[o] -i; }",
        "x [a] ",
        "f() { [s]udo; }; ",
        ";[a]",
    ],
)
def test_bracket_repair_stays_fast_at_8_kib(unit):
    # The bracket-glob repair runs on every ERROR node; 8 KiB of broken input nests
    # hundreds of them. It must not rescan the text per node (`[$[` took 19 s in v4).
    import time

    command = (unit * 8192)[:8192]
    start = time.monotonic()
    result = classify(command, "proposal")
    assert time.monotonic() - start < 5.0, unit
    assert RANK[result.cls] >= RANK["mutating"] and result.rejected, (unit, result)


def test_coproc_classes_its_command():
    # tree-sitter-bash reads `coproc cmd` as a simple command named `coproc`; its row
    # is a wrapper, so decision D and §5 reach the command word. The command reads a
    # pipe the shell writes to.
    rejected_proposal("coproc sud[o] -i", UNREADABLE)
    for origin in ("typed", "proposal"):
        check(
            "echo pw | coproc sud? -S true",
            exact="privileged",
            reason="sudo reads the password from stdin (§5)",
            rejected=True,
            origin=origin,
        )
        check(
            "coproc sudo true",
            exact="privileged",
            reason=PIPE_INTO,
            rejected=True,
            origin=origin,
        )
    check("coproc rm -rf x", exact="destructive", reason="rm -r")
    check("coproc true", exact="mutating", reason=NA, rejected=False)


@pytest.mark.parametrize(
    "command",
    [
        "{ sud[o] -i; }",
        "f() { sud[o] -i; }; f",
        "if true; then sud[o] -i; fi",
        "while true; do [s]udo -i; done",
        "( sud[o] -i )",
        "! sud[o] -i",
        "A=1 sud[o] -i",
        "true; { su[d]o -i; }",
    ],
)
def test_decision_d_bracket_glob_after_a_reserved_word(command):
    # The ERROR node starts before the command word (at `{`, `(`, `if` …): every
    # command word in the node is checked, past reserved words and assignments.
    rejected_proposal(command, UNREADABLE)


@pytest.mark.parametrize(
    "command", ["echo pw | { sud[o] -S true; }", "{ sud[o] -S true; } <<<pw"]
)
def test_decision_d_bracket_glob_in_a_group_section5(command):
    for origin in ("typed", "proposal"):
        check(
            command,
            exact="privileged",
            reason="sudo reads the password from stdin (§5)",
            rejected=True,
            origin=origin,
        )


def text_option_forms() -> list[tuple[str, str]]:
    """``(command word, option written to take an attached value)`` for every
    value-taking option with a code-text effect (runs-text, stores-code) on a parsed
    row: ``-X`` as ``-X'…'`` and ``--long`` / a one-dash long name as ``…='…'``."""
    out = []
    for row in table_doc()["command"]:
        if row.get("fixed") or not row.get("names"):
            continue
        name = row["names"][0]
        for spellings, option in (row.get("options") or {}).items():
            if option.get("value") not in ("required", "optional") or option.get("gap"):
                continue
            if not effect_names(option.get("effects")) & {"runs-text", "stores-code"}:
                continue
            for spelling in spellings.split("|"):
                if spelling.startswith("--"):
                    out.append((name, f"{spelling}="))
                elif len(spelling) == 2:
                    out.append((name, spelling))
                elif row.get("parse") == "long":
                    out.append((name, f"{spelling}="))
    return out


def test_text_option_attached_values_are_scanned():
    # The value of a text option written attached (`-S'…'`) or with `=`
    # (`--split-string='…'`) is the code; decision A's scan reads the parsed value.
    forms = text_option_forms()
    for needed in (
        ("env", "-S"),
        ("env", "--split-string="),
        ("script", "-c"),
        ("script", "--command="),
    ):
        assert needed in forms, needed
    for name, form in forms:
        rejected_proposal(
            f"{name} {form}'sudo -i'", "sudo named in code the gate cannot read"
        )
        for origin in ("typed", "proposal"):
            check(
                f"echo pw | {name} {form}'sudo -S true'",
                exact="privileged",
                reason="sudo reads the password from stdin (§5)",
                rejected=True,
                origin=origin,
            )


@pytest.mark.parametrize(
    "command",
    [
        "eval 'sud? -i'",
        "bash -c 'sud[o] -i'",
        "env -S 'sud? -i'",
        "env -S'sud? -i'",
        "eval '$x -i'",
        "bash -c 'true; /usr/bin/s*do -i'",
        "script -qc 'su{d,x}o -i'",
        "watch 'sud? -i'",
    ],
)
def test_text_unreadable_command_word_is_decision_d(command):
    # A command word in code text that the gate cannot read may be `sudo` (decision D),
    # though the text itself stays decision B.
    rejected_proposal(command, UNREADABLE)
    check(command, exact="privileged", reason=UNREADABLE)
    check(command, exact="privileged", reason=CANNOT_READ)


@pytest.mark.parametrize(
    "command",
    [
        "echo pw | eval 'sud? -S true'",
        "echo pw | bash -c 'sud[o] -S true'",
        "echo pw | env -S 'sud? -S true'",
        "eval '$x -S true'",
        "bash -c 'sud[o] -p x true'",
    ],
)
def test_text_unreadable_command_word_meets_section5(command):
    for origin in ("typed", "proposal"):
        check(command, exact="privileged", reason="(§5)", rejected=True, origin=origin)


@pytest.mark.parametrize(
    "command", ["bash -c 'ls *.c'", "python3 x.py *.csv", "perl -e 'print 1'"]
)
def test_text_scan_reads_only_command_words(command):
    # A glob that is an argument, or a file operand, is not a command word.
    result = check(command, exact="destructive", reason=CANNOT_READ, rejected=False)
    assert not has_reason(result, UNREADABLE), result


# --- decision C on table failure -------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [None, "format = 1\n[[command]\n", 'format = 2\n[[command]]\nnames = ["x"]\n', ""],
)
def test_decision_c_on_table_failure(tmp_path, monkeypatch, fresh_table, body):
    commands = fresh_table
    folder = tmp_path / commands.TARGET_ID
    folder.mkdir()
    if body is not None:
        (folder / commands.COMMANDS_FILE).write_text(body, encoding="utf-8")
    monkeypatch.setattr(commands, "TARGETS_ROOT", tmp_path)
    for command in ("ls", "rm -rf build", "sudo -i", "true", "foo sudo"):
        result = check(
            command, exact="privileged", rejected=True, reason=COULD_NOT, decision_c=True
        )
        assert result.reasons[0] == COULD_NOT, result


# --- the fixed load location -----------------------------------------------------------


def test_loader_reads_only_the_fixed_path():
    from nl_shell import targets
    from nl_shell.gate import commands

    assert commands.TARGET_ID == "ubuntu-26.04"
    assert commands.TARGETS_ROOT == targets.TARGETS_ROOT
    source = Path(commands.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned = {"environ", "getenv", "cwd", "getcwd", "home", "expanduser"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in banned, ast.unparse(node)
        if isinstance(node, ast.Name):
            assert node.id not in banned | {"open"}, node.id
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
            assert "os" not in names, ast.unparse(node)
    reads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in ("read_bytes", "read_text", "open", "readlink")
    ]
    assert len(reads) == 1, [ast.unparse(r) for r in reads]
    (load,) = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "load"]
    assert not load.args.args and not load.args.kwonlyargs and not load.args.vararg
    assert ast.unparse(reads[0]) == "path.read_bytes()"
    assigned = {
        target.id: ast.unparse(node.value)
        for node in ast.walk(load)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert assigned["root"] == "TARGETS_ROOT"
    assert assigned["path"] == "root / TARGET_ID / COMMANDS_FILE"
    module_level = {
        target.id: ast.unparse(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert module_level["TARGETS_ROOT"] == "targets.TARGETS_ROOT"
    assert module_level["COMMANDS_FILE"] == "'commands.toml'"


def test_loader_ignores_cwd_and_environment(tmp_path, monkeypatch, fresh_table):
    harmless = 'format = 1\n[[command]]\nnames = ["sudo"]\nexample = "sudo"\nfixed = true\n'
    for folder in (
        tmp_path,
        tmp_path / "targets" / "ubuntu-26.04",
        tmp_path / "nl-shell",
        tmp_path / "nl-shell" / "targets" / "ubuntu-26.04",
    ):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "commands.toml").write_text(harmless, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NL_SHELL_COMMANDS", str(tmp_path / "commands.toml"))
    monkeypatch.setenv("NL_SHELL_TARGETS", str(tmp_path / "targets"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    check("sudo -i", exact="privileged", reason="elevating command: sudo")
    check("sudo -i", exact="privileged", rejected=True, origin="proposal")


def test_loader_refuses_a_path_outside_the_root(tmp_path, monkeypatch, fresh_table):
    commands = fresh_table
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / commands.COMMANDS_FILE).write_text(
        'format = 1\n[[command]]\nnames = ["sudo"]\nexample = "sudo"\nfixed = true\n',
        encoding="utf-8",
    )
    (root / commands.TARGET_ID).symlink_to(outside)
    monkeypatch.setattr(commands, "TARGETS_ROOT", root)
    with pytest.raises(commands.CommandsError, match="outside"):
        commands.load()
    check("sudo true", exact="privileged", rejected=True, reason=COULD_NOT, decision_c=True)


# --- spec §3 builtins (floor only) -----------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "alias ll='ls -l'",
        "unalias ll",
        "source f",
        ". f",
        "eval true",
        "exec true",
        "trap - INT",
        "enable -n test",
        "set -e",
        "shopt -s nullglob",
        "bind -l",
        "complete -p",
        "hash -r",
        "builtin true",
        "command true",
        "export A=1",
        "declare A=1",
        "typeset A=1",
        "local A=1",
        "readonly A=1",
        "unset A",
    ],
)
def test_spec3_builtins(command):
    result = check(command, floor="session-altering")
    if result.cls != "session-altering":
        assert RANK[result.cls] > RANK["session-altering"], result
    assert not has_reason(result, COULD_NOT)


def test_spec3_command_v_is_not_session_altering():
    for command in ("command -v ls", "command -V ls"):
        check(command, exact="mutating", reason=NA)
    check("alias ll='ls -l'", exact="session-altering", reason="builtin alters the session")

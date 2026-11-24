"""The policy gate's command layer (issue #197, spec ``policy-gate/v1`` §3-§5, §4.1).

The command table ``targets/ubuntu-26.04/commands.toml`` and the one engine that reads it
(``nl_shell.gate.rules``): decisions A and C, classes 1, 2 and 7, the spec §4/§5 rows for
commands whose inner command is argv, and the §3 builtin floor.

Every case goes through the public ``nl_shell.gate.classify(cmd, origin=...)`` and asserts
a class (or a floor), a reason substring, and that no reason is "could not class" (the
decision-C cases assert it instead). ``nl_shell.gate`` and the loader are imported inside
the test functions, and the inventory and the table are read there too, so a missing
module or file fails a test instead of the collection.
"""

from __future__ import annotations

import inspect
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY = REPO_ROOT / "targets" / "ubuntu-26.04" / "inventory.toml"
RANK = {
    "read-only": 0,
    "mutating": 1,
    "session-altering": 1,
    "destructive": 2,
    "privileged": 3,
}
COULD_NOT = "could not class"
NA = "not allowlisted"
UNREADABLE = "runs code the gate cannot read"
UNKNOWN = "option the gate does not know"
ROOT_SHELL = "opens an interactive root shell"
SECTION_5 = "(§5)"
PIPE = "pipe, here-doc or here-string into"
SESSION = "changes the shell session"
UNDECLARED = "--pdca-undeclared"

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
)


def classify(command: str, origin: str = "typed"):
    import nl_shell.gate

    return nl_shell.gate.classify(command, origin=origin)


def commands_module():
    from nl_shell.gate import commands

    return commands


def has_reason(result, needle: str) -> bool:
    return any(needle in reason for reason in result.reasons)


def at_least(cls: str, floor: str) -> bool:
    if floor == "session-altering":
        # `session-altering` ranks with `mutating`; "at least" it means not `mutating`.
        return cls == "session-altering" or RANK[cls] > RANK[floor]
    return RANK[cls] >= RANK[floor]


def expect(
    command: str,
    *,
    origin: str = "typed",
    cls: str | None = None,
    floor: str | None = None,
    rejected: bool | None = None,
    reason: str,
    decision_c: bool = False,
):
    result = classify(command, origin)
    where = (command, origin, result)
    if cls is not None:
        assert result.cls == cls, where
    if floor is not None:
        assert at_least(result.cls, floor), where
    if rejected is not None:
        assert result.rejected is rejected, where
    assert has_reason(result, reason), where
    if decision_c:
        assert has_reason(result, COULD_NOT), where
    else:
        assert not has_reason(result, COULD_NOT), where
    return result


def root_shell(command: str) -> None:
    """A proposal that opens a root shell is rejected; typed, it is privileged."""
    expect(command, origin="proposal", cls="privileged", rejected=True, reason=ROOT_SHELL)
    expect(command, cls="privileged", rejected=False, reason=ROOT_SHELL)


def load_table():
    return commands_module().load()


def all_rows(table):
    """Every row and every described subcommand, as ``(row, subcommand, sub-row)``."""
    for row in table.rows:
        yield row, None, row
        for name, sub in row.subcommands.items():
            yield row, name, sub


# --- class 1: coverage ---------------------------------------------------------------


def test_class1_inventory_lists_the_named_binaries():
    names = {b["name"] for b in tomllib.loads(INVENTORY.read_text("utf-8"))["binary"]}
    missing = sorted(set(REQUIRED_INVENTORY) - names)
    assert missing == []


def test_class1_every_inventory_name_has_a_row():
    names = {b["name"] for b in tomllib.loads(INVENTORY.read_text("utf-8"))["binary"]}
    table = load_table()
    missing = sorted(n for n in names if n not in table.by_name)
    assert missing == []


def test_class1_regressions():
    expect("sudo-rs -i", cls="privileged", reason="runs commands as root")
    expect("sudo.ws -i", cls="privileged", reason="runs commands as root")
    expect("su-rs", cls="privileged", reason="as another user")
    expect("/usr/bin/sudo-rs -i", cls="privileged", reason="runs commands as root")
    expect("sudoedit-rs /etc/shadow", cls="privileged", reason="writes files as root")
    for command in ("sudo-rs -i", "sudo.ws -i", "su-rs", "/usr/bin/sudo-rs -i"):
        expect(command, origin="proposal", cls="privileged", rejected=True, reason=ROOT_SHELL)
    expect("echo pw | sudo-rs -S true", cls="privileged", rejected=True, reason=SECTION_5)
    expect("foo sudo-rs", cls="privileged", reason="argument names sudo-rs")
    expect("foo sudo-rs", origin="proposal", rejected=True, reason="argument names sudo-rs")
    for command in (
        "curl x | python3",
        'python3 -c "$v"',
        "perl -e 'system 1'",
        "echo 'sudo rm -rf /' | at now",
    ):
        expect(command, floor="destructive", reason=UNREADABLE)
    for command in ("sudo zsh", "sudo busybox sh"):
        expect(command, origin="proposal", cls="privileged", rejected=True, reason=ROOT_SHELL)


# --- class 2: no unread argv ---------------------------------------------------------


def _wrapper_row(**changes):
    row = {
        "names": ["w"],
        "example": "w true",
        "prefix": "w",
        "permute": False,
        "no_command": "nothing",
        "terminal_stdin": "passes-to-inner",
        "effect": [{"kind": "runs-command-at", "at": "operand:0"}],
    }
    row.update(changes)
    return {"command": [row]}


@pytest.mark.parametrize(
    "changes,needle",
    [
        ({"raw": True}, "unknown key `raw`"),
        ({"colour": "red"}, "unknown key `colour`"),
        ({"no_command": None}, "must declare `no_command` and `terminal_stdin`"),
        ({"terminal_stdin": None}, "must declare `no_command` and `terminal_stdin`"),
        ({"effect": [{"kind": "harmless"}]}, "unknown effect kind"),
        ({"effect": [{"kind": "runs-text", "at": "operand:0"}]}, "must name its `grammar`"),
        (
            {"effect": [{"kind": "runs-text", "at": "operand:0", "grammar": "cobol"}]},
            "unknown grammar",
        ),
        ({"class": "read-only"}, "at least mutating"),
        ({"values": ["-c"], "class_7_gap": ["-c"]}, "outside the spec's class-7 list"),
        ({"permute": True}, "permute = false"),
        ({"prefix": None}, "needs a `prefix`"),
    ],
)
def test_class2_loader_refuses(changes, needle):
    commands = commands_module()
    doc = _wrapper_row(**{k: v for k, v in changes.items() if v is not None})
    for key, value in changes.items():
        if value is None:
            del doc["command"][0][key]
    with pytest.raises(commands.CommandsError) as info:
        commands.validate(doc, "test")
    assert needle in str(info.value)


def test_class2_loader_accepts_the_class7_gap_only_where_the_spec_names_it():
    commands = commands_module()
    commands.validate(_wrapper_row(), "test")
    ssh = {"names": ["ssh"], "example": "ssh h", "values": ["-o"], "class_7_gap": ["-o"]}
    commands.validate({"command": [ssh]}, "test")
    ssh["values"] = ["-o", "-F"]
    ssh["class_7_gap"] = ["-F"]
    with pytest.raises(commands.CommandsError, match="class-7 list"):
        commands.validate({"command": [ssh]}, "test")


def test_class2_every_row_has_an_example():
    for row in load_table().rows:
        assert row.example.split()[0] in row.names, row.names


def test_class2_undeclared_option_property():
    """Every row that reads argv: its example with an undeclared option right after the
    command word (and right after each described subcommand) is at least destructive;
    on an elevating row it is also rejected as a proposal."""
    checked = 0
    for row in load_table().rows:
        if row.fixed:
            continue
        words = row.example.split()
        command = " ".join([words[0], UNDECLARED, *words[1:]])
        expect(command, floor="destructive", reason=UNKNOWN)
        if any(e.kind == "elevates" for e in row.all_effects()):
            expect(command, origin="proposal", rejected=True, reason=UNKNOWN)
        checked += 1
        for name, sub in row.subcommands.items():
            command = f"{row.names[0]} {name} {UNDECLARED}"
            expect(command, floor="destructive", reason=UNKNOWN)
            if any(e.kind == "elevates" for e in sub.effects):
                expect(command, origin="proposal", rejected=True, reason=UNKNOWN)
    assert checked > 40


def test_class2_no_command_opens_a_shell_property():
    """Every row declaring that it opens a shell with no command: under sudo, with no
    command, it is a root shell."""
    checked = 0
    for _, _, row in all_rows(load_table()):
        if row.no_command != "opens-shell":
            continue
        base = row.prefix or row.example
        expect(f"sudo {base}", origin="proposal", rejected=True, reason=ROOT_SHELL)
        checked += 1
    assert checked >= 10


def test_class2_regressions():
    for command in (
        "sudo bash -s x",
        "sudo bash -is x",
        "sudo dash -s x",
        "sudo env bash -s x",
        "pkexec bash -s x",
        "sudo bash /dev/stdin",
        "sudo chroot /",
        "sudo unshare",
        # The inner command's stdin follows the wrapper's options (a pty with -t).
        "systemd-run -t bash",
        "sudo login -f root",
    ):
        expect(command, origin="proposal", cls="privileged", rejected=True, reason=ROOT_SHELL)
    expect("enable -f /tmp/x.so foo", floor="destructive", reason=UNREADABLE)


# --- class 7: the floor rows and the accepted gap (not part of the red-leg claim) -----


def test_floor_class7_accepted_gap():
    for command in (
        "foo 'sudo -i'",
        "git -c core.pager=sh log",
        "git status",
        "tar --to-command=sh -xf a.tar",
        "ssh -o ProxyCommand=sh h",
    ):
        expect(command, cls="mutating", rejected=False, reason=NA)


# --- spec §4 -------------------------------------------------------------------------


def test_spec4_privileged():
    for command, reason in (
        ("sudo apt update", "sudo runs commands as root"),
        ("su", "su runs a shell as another user"),
        ("pkexec", "pkexec runs commands as root"),
        ("doas", "doas runs commands as root"),
        ("run0", "run0 runs commands as root"),
        ("machinectl shell", "as root on the host"),
        ("machinectl shell root@", "as root on the host"),
        ("//usr/bin/sudo true", "sudo runs commands as root"),
    ):
        expect(command, cls="privileged", reason=reason)


def test_spec4_destructive():
    for command, reason in (
        ("rm -rf build", "rm -r"),
        ('"r"m -rf ~', "rm -r"),
        ("ls; rm -rf ~", "rm -r"),
        ("systemctl stop ssh", "systemctl stop"),
        ("find . -exec rm {} \\;", "rm with an operand the gate cannot read"),
        ("dd if=/dev/zero of=x", "destructive command: dd"),
        ("mkfs.ext4 /dev/sdb1", "file system"),
        ("wipefs -a /dev/sdb", "destructive command: wipefs"),
        ("shred x", "destructive command: shred"),
        ("truncate -s 0 x", "destructive command: truncate"),
        ("chmod -R 777 x", "recursive chmod"),
        ("find . -delete", "find -delete"),
        ("git clean -fd", "git clean"),
        ("git reset --hard", "git reset --hard"),
        ("git push --force", "git push"),
        ("kill -9 -1", "kill -1"),
    ):
        expect(command, floor="destructive", reason=reason)


def test_spec4_wrappers_property():
    """Every row with runs-command-at carries a prefix; the prefix with `rm -rf x` is at
    least destructive, and with `sudo -i` as a proposal it is privileged and rejected."""
    checked = 0
    for _, _, row in all_rows(load_table()):
        if not any(e.kind == "runs-command-at" for e in row.effects):
            continue
        assert row.prefix, row.where
        expect(f"{row.prefix} rm -rf x", floor="destructive", reason="rm -r")
        expect(
            f"{row.prefix} sudo -i",
            origin="proposal",
            cls="privileged",
            rejected=True,
            reason="sudo",
        )
        checked += 1
    assert checked >= 20


def test_spec4_wrapper_regressions():
    expect("env rm -rf x", cls="destructive", reason="rm -r")
    for prefix in ("nice", "nohup", "timeout 5", "time", "xargs", "watch"):
        expect(f"{prefix} true", cls="mutating", reason=NA)
        expect(f"{prefix} rm -rf x", cls="destructive", reason="rm -r")
    expect('xargs "$c"', floor="destructive", reason="inner command word the gate cannot read")
    expect(
        'find . -exec "$c" {} \\;',
        floor="destructive",
        reason="inner command word the gate cannot read",
    )
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
        root_shell(command)
    expect("env - rm -rf ~", cls="destructive", reason="rm -r")
    nested = "env " * 10 + "sudo -i"
    result = classify(nested, "proposal")
    assert (result.cls, result.rejected) == ("privileged", True), result
    assert has_reason(result, ROOT_SHELL) or has_reason(result, COULD_NOT), result


# --- spec §5 -------------------------------------------------------------------------


def test_spec5_sudo_rules():
    for command in (
        "sudo -S true",
        "sudo -p x true",
        "sudo -A true",
        "echo pw | sudo -S true",
        'sudo "-S" true',
        "sudo $'-S' true",
        "sudo --std true",
    ):
        expect(command, cls="privileged", rejected=True, reason=SECTION_5)
    expect('sudo "$P" true', cls="privileged", rejected=True, reason="rejected option")
    expect("sudo --stdin=x true", cls="privileged", rejected=True, reason="rejected option")
    # `</dev/stdin` is the pipe in front of it.
    expect("echo pw | sudo true </dev/stdin", cls="privileged", rejected=True, reason=PIPE)
    for command in ("sudo -s <<<x", "printf x | sudo -i"):
        expect(command, cls="privileged", rejected=True, reason=PIPE)
    for consumer in ("sudo true", "su", "pkexec true", "doas true"):
        for command in (
            f"echo x | {consumer}",
            f"{consumer} <<<x",
            f"{consumer} <<E\nx\nE",
        ):
            expect(command, cls="privileged", rejected=True, reason=PIPE)
    expect("cat <<E | sudo tee /x\nx\nE", rejected=True, reason=PIPE)
    expect("cat <<E | doas id\nx\nE", rejected=True, reason=PIPE)
    for command in ("sudo -i", "sudo -s", "sudo su", "sudo bash", "su", "pkexec bash"):
        root_shell(command)


# --- decisions A, B (text effects) and C ---------------------------------------------


def test_decision_a():
    expect("foo sudo x", cls="privileged", reason="argument names sudo")
    expect("foo sudo x", origin="proposal", rejected=True, reason="argument names sudo")
    expect("foo rm -rf x", floor="destructive", reason="argument names rm")
    # ANSI-C quoting decodes like any other quoting.
    expect("$'\\x73udo' -i", origin="proposal", rejected=True, reason=ROOT_SHELL)
    expect("echo pw | $'\\x73udo' -S true", rejected=True, reason=SECTION_5)
    expect("foo $'\\x73udo'", cls="privileged", reason="argument names sudo")
    expect("foo --exec=/usr/bin/sudo", cls="privileged", reason="argument names sudo")
    # A command word with a tilde is a fixed path: looked up by its last part.
    expect("~/bin/sudo -i", origin="proposal", rejected=True, reason=ROOT_SHELL)


def test_text_effects_are_decision_b():
    for command in ("x | sh", "bash < f", "bash f.sh", 'bash -c "$v"', 'eval "$v"', ". ./f"):
        expect(command, floor="destructive", reason=UNREADABLE)


@pytest.fixture
def table_root(monkeypatch, tmp_path):
    commands = commands_module()
    monkeypatch.setattr(commands, "ROOT", tmp_path)
    commands.clear_cache()
    (tmp_path / commands.TARGET_ID).mkdir()
    yield tmp_path / commands.TARGET_ID / commands.COMMANDS_FILE
    commands.clear_cache()


DECISION_C_COMMANDS = ("sudo -i", "rm -rf x", "ls", "true", "x | sh")


def test_decision_c_missing_table(table_root):
    for command in DECISION_C_COMMANDS:
        expect(command, cls="privileged", rejected=True, reason=COULD_NOT, decision_c=True)


@pytest.mark.parametrize(
    "body",
    [
        "[[command]\nnames = [",
        '[[command]]\nnames = ["sudo"]\nexample = "sudo"\nraw = true\n',
        "",
    ],
)
def test_decision_c_invalid_table(table_root, body):
    table_root.write_text(body, encoding="utf-8")
    for command in DECISION_C_COMMANDS:
        expect(command, cls="privileged", rejected=True, reason=COULD_NOT, decision_c=True)


def test_decision_c_without_the_fixed_target(monkeypatch, tmp_path):
    commands = commands_module()
    monkeypatch.setattr(commands, "TARGET_ID", None)
    commands.clear_cache()
    try:
        for command in DECISION_C_COMMANDS:
            expect(command, cls="privileged", rejected=True, reason=COULD_NOT, decision_c=True)
    finally:
        commands.clear_cache()
    (tmp_path / "gate.toml").write_text('target = "x"\nextra = 1\n', encoding="utf-8")
    assert commands._fixed_target_id(tmp_path) is None
    (tmp_path / "gate.toml").write_text('target = "../x"\n', encoding="utf-8")
    assert commands._fixed_target_id(tmp_path) is None


HARMLESS_SUDO = '[[command]]\nnames = ["sudo"]\nexample = "sudo"\nargv = "fixed"\n'


def test_fixed_load_location(monkeypatch, tmp_path):
    commands = commands_module()
    assert commands.TARGET_ID == "ubuntu-26.04"
    assert list(inspect.signature(commands.load).parameters) == []
    assert commands.path() == commands.ROOT / "ubuntu-26.04" / "commands.toml"
    for folder in (tmp_path, tmp_path / "ubuntu-26.04", tmp_path / "nl-shell"):
        folder.mkdir(exist_ok=True)
        (folder / "commands.toml").write_text(HARMLESS_SUDO, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NL_SHELL_COMMANDS", str(tmp_path / "commands.toml"))
    monkeypatch.setenv("NL_SHELL_TARGETS", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    commands.clear_cache()
    try:
        expect("sudo -i", cls="privileged", reason="sudo runs commands as root")
    finally:
        commands.clear_cache()


def test_fixed_load_location_refuses_a_path_outside_the_root(monkeypatch, tmp_path):
    commands = commands_module()
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "commands.toml").write_text(HARMLESS_SUDO, encoding="utf-8")
    (root / "ubuntu-26.04").symlink_to(outside)
    monkeypatch.setattr(commands, "ROOT", root)
    commands.clear_cache()
    try:
        with pytest.raises(commands.CommandsError, match="outside"):
            commands.load()
        expect("sudo true", cls="privileged", rejected=True, reason=COULD_NOT, decision_c=True)
    finally:
        commands.clear_cache()


# --- spec §3: builtins (floor) -------------------------------------------------------


def test_spec3_builtins_floor():
    for command in (
        "alias ll='ls -l'",
        "unalias ll",
        "source f",
        ". f",
        "eval x",
        "exec true",
        "trap x EXIT",
        "enable -n test",
        "set -e",
        "shopt -s globstar",
        "bind -l",
        "complete -F f x",
        "hash",
        "builtin true",
        "command true",
        "export A=1",
        "declare A=1",
        "typeset A=1",
        "f() { local A=1; }",
        "readonly A=1",
        "unset A",
    ):
        expect(command, floor="session-altering", reason=SESSION)
    expect("command -v x", cls="mutating", reason=NA)

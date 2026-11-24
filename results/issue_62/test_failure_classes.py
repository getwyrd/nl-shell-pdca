"""Failure classes by exit code (#62).

The table uses completion results built directly (a ``session.CommandResult`` with a
snapshot whose ``$PATH`` is a temporary folder the test controls) and a fake package
lookup, so it never depends on the host's package data or programs, on sudo, or on a real
failing command. No test runs sudo, su or pkexec. The modules this issue adds are imported
inside the tests, never at module level, so the file still loads (and fails) on a tree
without them. Only the real-lookup test may skip, when the host has no command-not-found
data.
"""

import inspect
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

FAKE_PROVIDERS = {
    "htop": ["htop"],
    "cat": ["coreutils"],
    "make": ["make"],
    "env": ["coreutils"],
    "sudo": ["sudo"],
    "sudo-rs": ["sudo-rs"],
    "timeout": ["coreutils"],
    "npm": ["npm"],
    "ll": ["ll-package"],
    "mkfn": ["mkfn"],
    "echo": ["coreutils"],
}


def fake_lookup(word):
    return list(FAKE_PROVIDERS.get(word, []))


def snapshot(path="", functions=(), aliases="", disabled=""):
    from nl_shell.pty_protocol import Snapshot

    return Snapshot(
        seq=1,
        functions=tuple(functions),
        aliases=aliases,
        traps="",
        disabled_builtins=disabled,
        extdebug="",
        path=path,
        stopped_jobs=0,
        hooks="",
        variables="",
    )


def completed(status, path, pipestatus=None, ran=True, **state):
    """A ``CommandResult`` as ``Session.run`` builds it from the D record and snapshot."""
    from nl_shell.session import CommandResult

    return CommandResult(
        seq=1,
        ran=ran,
        status=status,
        pipestatus=pipestatus or (status,),
        output=b"bash: htop: command not found\n",  # attacker-shaped; must not matter
        output_truncated=False,
        snapshot=snapshot(path=path, **state),
        variables_changed=False,
    )


@pytest.fixture
def bin_dir(tmp_path):
    """An absolute, empty folder used as the session's whole ``$PATH``."""
    folder = tmp_path / "bin"
    folder.mkdir()
    return folder


def install(folder, name):
    program = folder / name
    program.write_text("#!/bin/sh\nexit 127\n", encoding="utf-8")
    program.chmod(0o755)


def classify(status, command, path, lookup=fake_lookup, **kwargs):
    from nl_shell.failure_classes import classify as real_classify

    return real_classify(completed(status, str(path), **kwargs), command, lookup)


def kind(name):
    from nl_shell.failure_classes import FailureClass

    return FailureClass[name]


# (id, status, command, class, packages, offer_correction, to_reader)
TABLE = [
    ("ok", 0, "htop", "NONE", (), False, False),
    ("not-found-known", 127, "htop", "NOT_FOUND", ("htop",), True, False),
    ("not-found-unknown", 127, "frobnicate --x", "NOT_FOUND", (), True, False),
    ("not-found-pipeline", 127, "cat f | htop", "NOT_FOUND", (), True, False),
    ("not-found-and-list", 127, "make && htop", "NOT_FOUND", (), True, False),
    ("not-found-list", 127, "true; htop", "NOT_FOUND", (), True, False),
    ("not-found-assignment", 127, "FOO=1 htop", "NOT_FOUND", (), True, False),
    ("not-found-env", 127, "env htop", "NOT_FOUND", (), True, False),
    ("not-found-substitution", 127, "echo $(htop)", "NOT_FOUND", (), True, False),
    ("not-found-backtick", 127, "echo `htop`", "NOT_FOUND", (), True, False),
    ("not-found-newline", 127, "true\nhtop", "NOT_FOUND", (), True, False),
    ("not-found-under-sudo", 127, "sudo htop", "NOT_FOUND", (), True, False),
    ("not-executable", 126, "./script.sh", "NOT_EXECUTABLE", (), True, False),
    ("interrupted", 130, "sleep 100", "INTERRUPTED", (), False, False),
    ("sigkill", 137, "big-job", "SIGNAL", (), True, False),
    ("sigterm", 143, "big-job", "SIGNAL", (), True, False),
    ("sudo-1", 1, "sudo apt update", "PRIVILEGE_WRAPPER", (), False, False),
    ("sudo-path-1", 1, "/usr/bin/sudo apt update", "PRIVILEGE_WRAPPER", (), False, False),
    ("doas-1", 1, "doas apt update", "PRIVILEGE_WRAPPER", (), False, False),
    ("pkexec-126", 126, "pkexec apt update", "PRIVILEGE_WRAPPER", (), False, False),
    ("pkexec-127", 127, "pkexec htop", "PRIVILEGE_WRAPPER", (), False, False),
    ("su-1", 1, "su -c 'apt update'", "PRIVILEGE_WRAPPER", (), False, False),
    # Other installed names of the same programs (sudo-rs, classic sudo, sudo's edit mode).
    ("sudo-rs-1", 1, "sudo-rs apt update", "PRIVILEGE_WRAPPER", (), False, False),
    ("sudo.ws-1", 1, "sudo.ws apt update", "PRIVILEGE_WRAPPER", (), False, False),
    ("sudoedit-1", 1, "sudoedit /etc/hosts", "PRIVILEGE_WRAPPER", (), False, False),
    ("sudoedit-rs-1", 1, "sudoedit-rs /etc/hosts", "PRIVILEGE_WRAPPER", (), False, False),
    ("su-rs-1", 1, "su-rs -c 'apt update'", "PRIVILEGE_WRAPPER", (), False, False),
    ("su-path-1", 1, "/usr/lib/cargo/bin/su -c x", "PRIVILEGE_WRAPPER", (), False, False),
    ("not-found-under-sudo-rs", 127, "sudo-rs htop", "NOT_FOUND", (), True, False),
    ("other-1", 1, "grep x f", "OTHER", (), True, True),
    ("other-2", 2, "ls /nope", "OTHER", (), True, True),
    ("other-100", 100, "apt-get install x", "OTHER", (), True, True),
    ("other-128", 128, "git x", "OTHER", (), True, True),
    ("other-255", 255, "ssh host", "OTHER", (), True, True),
    ("other-sudo-2", 2, "sudo ls /nope", "OTHER", (), True, True),
]


@pytest.mark.parametrize(
    "status, command, cls, packages, offer, reader",
    [row[1:] for row in TABLE],
    ids=[row[0] for row in TABLE],
)
def test_classification_table(bin_dir, status, command, cls, packages, offer, reader):
    result = classify(status, command, bin_dir)
    assert result.kind is kind(cls)
    assert result.status == status
    assert result.packages == packages
    assert result.offer_correction is offer
    assert result.to_reader is reader


def test_only_other_goes_to_the_reader(bin_dir):
    for _, status, command, cls, *_rest in TABLE:
        result = classify(status, command, bin_dir)
        assert result.to_reader is (cls == "OTHER"), (status, command)


def test_no_failure(bin_dir):
    result = classify(0, "htop", bin_dir)
    assert result.is_error is False
    assert result.message == ""


def test_not_found_suggests_the_package(bin_dir):
    result = classify(127, "htop -d 5", bin_dir)
    assert result.command_word == "htop"
    assert result.packages == ("htop",)
    assert "htop" in result.message
    assert result.is_error is True


def test_not_found_without_lookup_gives_no_suggestion(bin_dir):
    assert classify(127, "htop", bin_dir, lookup=None).packages == ()


# A 127 from a first word bash DID find came from whatever that word ran: suggesting the
# first word's package would be a confident wrong answer.
@pytest.mark.parametrize(
    "command, installed, state",
    [
        ("timeout 5 frobnicate", "timeout", {}),
        ("npm run build", "npm", {}),
        ("ll", None, {"aliases": "alias ll='ls -l --frob'\n"}),
        ("mkfn", None, {"functions": ("mkfn",)}),
        ("eval frobnicate", None, {}),
    ],
    ids=["program-on-path", "npm-script", "alias", "function", "builtin"],
)
def test_not_found_from_a_found_first_word_gives_no_suggestion(
    bin_dir, command, installed, state
):
    if installed:
        install(bin_dir, installed)
    result = classify(127, command, bin_dir, **state)
    assert result.kind is kind("NOT_FOUND")
    assert result.packages == ()
    assert result.command_word is None
    assert result.message == "Command not found."


def test_disabled_builtin_can_be_not_found(bin_dir):
    # `enable -n echo` and no echo on $PATH: bash really did not find `echo`.
    result = classify(127, "echo hi", bin_dir, disabled="enable -n echo\n")
    assert result.packages == ("coreutils",)


@pytest.mark.parametrize("path", ["", "relative/bin", "{bin}:", "{bin}::/x"])
def test_path_with_cwd_entry_gives_no_suggestion(bin_dir, path):
    # An empty or relative $PATH entry depends on the session's directory, which the
    # snapshot doesn't carry: the word may have been found, so no suggestion.
    result = classify(127, "htop", path.format(bin=bin_dir))
    assert result.packages == ()


def test_bare_done_record_gives_no_suggestion():
    from nl_shell.failure_classes import classify as real_classify
    from nl_shell.pty_protocol import Done

    result = real_classify(Done(seq=1, status=127, pipestatus=(127,)), "htop", fake_lookup)
    assert result.kind is kind("NOT_FOUND")
    assert result.packages == ()
    assert result.to_reader is False


def test_bare_done_record_classifies():
    from nl_shell.failure_classes import classify as real_classify
    from nl_shell.pty_protocol import Done

    assert real_classify(Done(1, 1, (1,)), "sudo apt update").kind is kind(
        "PRIVILEGE_WRAPPER"
    )
    assert real_classify(Done(1, 2, (2,)), "ls /nope").kind is kind("OTHER")


@pytest.mark.parametrize("status", [0, 1, 2, 127, 130])
@pytest.mark.parametrize("command", ["", "# a note", "if then"])
def test_nothing_ran_is_not_classed(bin_dir, status, command):
    # D without S (protocol §4.1): `$?` may be an earlier command's status.
    result = classify(status, command, bin_dir, ran=False)
    assert result.kind is kind("NOT_RUN")
    assert result.is_error is False
    assert result.offer_correction is False
    assert result.to_reader is False
    assert "not found" not in result.message.lower()


@pytest.mark.parametrize(
    "word",
    ["\x1b[2Jfoo", "foo‮gnp", "a" * 65, "x\x07"],
    ids=["escape", "bidi-override", "65-chars", "bell"],
)
def test_unsafe_word_reaches_no_message(bin_dir, word):
    result = classify(127, word, bin_dir, lookup=lambda w: ["htop"])
    assert result.kind is kind("NOT_FOUND")
    assert result.message == "Command not found."
    assert result.packages == ()
    assert result.command_word is None
    assert "None" not in result.message


def test_64_char_word_is_shown(bin_dir):
    word = "a" * 64
    result = classify(127, word, bin_dir, lookup=lambda w: ["htop"])
    assert result.command_word == word
    assert result.packages == ("htop",)
    assert result.message == f"Command not found: {word}. It is provided by the package htop."


def test_not_executable_message(bin_dir):
    assert "permission or noexec" in classify(126, "./script.sh", bin_dir).message


def test_interrupted_is_not_an_error(bin_dir):
    result = classify(130, "sleep 100", bin_dir)
    assert result.offer_correction is False
    assert result.is_error is False
    assert "error" not in result.message.lower()
    assert "fail" not in result.message.lower()


def test_sigkill_names_the_signal_and_the_oom_killer(bin_dir):
    result = classify(137, "big-job", bin_dir)
    assert (result.signal_number, result.signal_name) == (9, "SIGKILL")
    assert "SIGKILL" in result.message
    assert "out-of-memory" in result.message


def test_sigterm(bin_dir):
    result = classify(143, "big-job", bin_dir)
    assert (result.signal_number, result.signal_name) == (15, "SIGTERM")
    assert "SIGTERM" in result.message
    assert "out-of-memory" not in result.message


def test_sudo_failure_message_never_reruns_sudo(bin_dir):
    result = classify(1, "sudo apt update", bin_dir)
    assert result.wrapper == "sudo"
    assert "password was wrong" in result.message
    assert "may not use sudo" in result.message
    assert result.offer_correction is False
    assert result.to_reader is False
    lowered = result.message.lower()
    for phrase in ("sudo -", "sudo apt", "try again", "re-run", "rerun", "run it again"):
        assert phrase not in lowered
    # A fixed template: the same text whatever command ran under sudo.
    assert classify(1, "sudo systemctl restart x", bin_dir).message == result.message


@pytest.mark.parametrize(
    "command, wrapper, shown",
    [
        ("sudo-rs apt update", "sudo", "sudo-rs"),
        ("sudoedit /etc/hosts", "sudo", "sudoedit"),
        ("sudoedit-rs /etc/hosts", "sudo", "sudoedit-rs"),
        ("su-rs -c x", "su", "su-rs"),
    ],
)
def test_wrapper_alias_maps_to_its_program(bin_dir, command, wrapper, shown):
    result = classify(1, command, bin_dir)
    assert result.kind is kind("PRIVILEGE_WRAPPER")
    assert result.wrapper == wrapper  # consumers check the program, not the name typed
    assert result.message.startswith(f"{shown} failed with exit status 1")
    assert "password was wrong" in result.message
    assert result.offer_correction is False
    assert result.to_reader is False
    # Under an alias the 126/127 statuses stay pkexec's only.
    assert classify(126, command, bin_dir).kind is kind("NOT_EXECUTABLE")


def test_pipestatus_is_kept_and_status_is_the_last_command(bin_dir):
    result = classify(1, "false | true | grep x", bin_dir, pipestatus=(1, 0, 1))
    assert result.pipestatus == (1, 0, 1)
    assert result.status == 1


def test_bare_int_raises_type_error():
    from nl_shell.failure_classes import classify as real_classify

    with pytest.raises(TypeError):
        real_classify(127, "htop", fake_lookup)


def test_signature_takes_no_stderr_or_output():
    from nl_shell.failure_classes import classify as real_classify

    names = list(inspect.signature(real_classify).parameters)
    assert names
    for name in names:
        assert "stderr" not in name.lower()
        assert "output" not in name.lower()


def test_classifier_source_names_no_os():
    from nl_shell import failure_classes

    text = Path(failure_classes.__file__).read_text(encoding="utf-8")
    for needle in ("/var/", "/usr/", "commands.db", "ubuntu"):
        assert needle not in text.lower(), needle


# "htop\n" separates re.fullmatch from a `$`-anchored re.match, which accepts one trailing
# newline.
@pytest.mark.parametrize("name", ["HTOP", "htop; rm -rf ~", "htop\nevil", "-htop", "htop\n"])
def test_bad_provider_names_are_dropped(bin_dir, name):
    result = classify(127, "htop", bin_dir, lookup=lambda word: [name])
    assert result.kind is kind("NOT_FOUND")
    assert result.packages == ()


@pytest.mark.parametrize("name", ["libc6", "g++", "python3.12"])
def test_good_provider_names_are_kept(bin_dir, name):
    assert classify(127, "htop", bin_dir, lookup=lambda word: [name]).packages == (name,)


def test_target_loader_reads_command_provider():
    from nl_shell import targets

    target = targets.load("ubuntu-26.04")
    provider = target.command_provider
    assert provider is not None
    assert provider.format == "sqlite"
    assert Path(provider.path).is_absolute()
    assert provider.query.count("?") == 1


TARGET_BASE = """\
id = "testos-1"
display_name = "Test OS 1"
shell = "bash"
package_owner_query = ["owner-of"]

[os_release]
ID = "testos"
VERSION_ID = "1"

[sudo]
implementation = "test-sudo"
version = "1.0"
"""


def write_target(root, extra=""):
    folder = root / "testos-1"
    folder.mkdir()
    # A bare key must come before the first table, or TOML puts it inside that table.
    text = TARGET_BASE + extra if extra.startswith("[") else extra + TARGET_BASE
    (folder / "target.toml").write_text(text, encoding="utf-8")


def test_command_provider_is_optional(tmp_path):
    from nl_shell import targets

    write_target(tmp_path)
    assert targets.load("testos-1", tmp_path).command_provider is None


@pytest.mark.parametrize(
    "extra, error",
    [
        ('command_provider = "x"\n', "must be a table"),
        ('[command_provider]\nformat = "csv"\npath = "/x"\nquery = "?"\n', "not supported"),
        ('[command_provider]\nformat = "sqlite"\npath = "x.db"\nquery = "?"\n', "absolute"),
        ('[command_provider]\nformat = "sqlite"\npath = "/x"\nquery = "select 1"\n', "`?`"),
        ('[command_provider]\nformat = "sqlite"\nquery = "?"\n', "command_provider.path"),
    ],
    ids=["not-table", "format", "relative-path", "no-placeholder", "missing-path"],
)
def test_command_provider_is_validated(tmp_path, extra, error):
    from nl_shell import targets

    write_target(tmp_path, extra)
    with pytest.raises(targets.TargetError, match=error):
        targets.load("testos-1", tmp_path)


def test_provider_lookup_reads_sqlite_read_only(tmp_path):
    import sqlite3

    from nl_shell.failure_classes import provider_lookup
    from nl_shell.targets import CommandProvider

    db = tmp_path / "c.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE t (cmd TEXT, pkg TEXT)")
        conn.execute("INSERT INTO t VALUES ('htop', 'htop')")
    conn.close()
    lookup = provider_lookup(
        CommandProvider("sqlite", str(db), "SELECT pkg FROM t WHERE cmd = ?")
    )
    assert lookup("htop") == ("htop",)
    assert lookup("nope") == ()
    # Read-only: a writing query fails inside the lookup and gives nothing.
    writer = provider_lookup(
        CommandProvider("sqlite", str(db), "INSERT INTO t VALUES (?, 'x') RETURNING pkg")
    )
    assert writer("evil") == ()
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM t").fetchone() == (1,)
    conn.close()


def test_provider_lookup_without_data_returns_nothing(tmp_path):
    from nl_shell.failure_classes import provider_lookup
    from nl_shell.targets import CommandProvider

    missing = CommandProvider("sqlite", str(tmp_path / "absent.db"), "SELECT 1 WHERE ? = 1")
    assert provider_lookup(missing)("htop") == ()
    assert provider_lookup(None)("htop") == ()
    assert not (tmp_path / "absent.db").exists()


def test_real_target_lookup_finds_htop():
    from nl_shell import targets
    from nl_shell.failure_classes import provider_lookup

    provider = targets.load("ubuntu-26.04").command_provider
    assert provider is not None
    if not Path(provider.path).is_file():
        pytest.skip(f"no command-not-found data at {provider.path}")
    assert "htop" in provider_lookup(provider)("htop")


def test_real_lookup_with_session_path_skips_found_wrapper(bin_dir):
    # The reviewer's case end to end: `timeout` is on the session's $PATH, so a 127 from
    # `timeout 5 frobnicate` names no package, even with the real lookup.
    from nl_shell import targets
    from nl_shell.failure_classes import classify as real_classify
    from nl_shell.failure_classes import provider_lookup

    install(bin_dir, "timeout")
    lookup = provider_lookup(targets.load("ubuntu-26.04").command_provider)
    result = real_classify(
        completed(127, os.fspath(bin_dir)), "timeout 5 frobnicate", lookup
    )
    assert result.packages == ()
    assert "timeout" not in result.message

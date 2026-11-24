"""The persistent bash session (#101) against pty-protocol v1 (docs/design/specs/pty-protocol).

Every session test starts a real bash on a PTY; they need only bash (>= 5.1), ptyprocess
and Linux /proc: no VM, no sudo. The session modules are imported inside the fixtures and
tests, never at module level, so with them missing each test fails on its own. Every call
that waits on bash has a timeout of a few seconds, and every session is closed when its
test ends.

The letters in the section headers are the items of the success criterion in the brief of
#101 (results/issue_101/brief.md in the PDCA bundle).
"""

from __future__ import annotations

import importlib
import os
import re
import stat
import threading
import time

import pytest

START_TIMEOUT = 5.0  # starting bash and reading its baseline snapshot
RUN_TIMEOUT = 5.0  # one command

SNAPSHOT_TYPES = (b"F", b"L", b"T", b"B", b"X", b"P", b"J", b"H", b"V")


def _session_module():
    return importlib.import_module("nl_shell.session")


def _protocol_module():
    return importlib.import_module("nl_shell.pty_protocol")


class _Records:
    """Every control record a session reported, with the time it was read."""

    def __init__(self) -> None:
        self.items: list[tuple[float, bytes]] = []

    def __call__(self, line: bytes) -> None:
        self.items.append((time.monotonic(), line))

    @property
    def lines(self) -> list[bytes]:
        return [line for _, line in self.items]

    def for_command(self, seq: int) -> list[bytes]:
        """The records from the first `S seq` (or the `D`, if no `S` came) to the next `E`."""
        lines = self.lines
        start = next(
            i for i, line in enumerate(lines)
            if line == b"S %d\n" % seq or line.startswith(b"D %d " % seq)
        )
        end = next(i for i in range(start, len(lines)) if lines[i] == b"E\n")
        return lines[start : end + 1]


@pytest.fixture
def start_session(monkeypatch):
    """Start sessions for one test; close them all and check every record's framing (n).

    The session module is imported when the test calls ``start``, so with it missing the
    test fails rather than erroring in setup. ``VTE_VERSION`` is dropped so the system
    bashrc of a VTE terminal adds no prompt hook of its own.
    """
    monkeypatch.delenv("VTE_VERSION", raising=False)
    started = []

    def start(**kwargs):
        session_mod = _session_module()
        records = _Records()
        session = session_mod.Session.start(timeout=START_TIMEOUT, on_record=records, **kwargs)
        started.append((session, records))
        return session, records

    yield start
    for session, records in started:
        session.close()
    for _, records in started:
        for line in records.lines:
            assert line.endswith(b"\n") and b"\r" not in line, line


def _spy_on_pty_writes(monkeypatch) -> list[bytes]:
    """Every write the session module makes to the PTY, from now on.

    Called from the test body, not a fixture, so with the module missing the test fails
    instead of erroring in setup.
    """
    session_mod = _session_module()
    writes: list[bytes] = []
    real_write_all = session_mod._write_all

    def spy(fd, data):
        writes.append(bytes(data))
        real_write_all(fd, data)

    monkeypatch.setattr(session_mod, "_write_all", spy)
    return writes


def _run(session, command, timeout=RUN_TIMEOUT):
    return session.run(command, timeout=timeout)


def _try_run(session, command, timeout=RUN_TIMEOUT):
    """The result, or the SessionDegraded the command raised."""
    session_mod = _session_module()
    try:
        return session.run(command, timeout=timeout)
    except session_mod.SessionDegraded as exc:
        return exc


def _run_default_timeout(session, command, limit=RUN_TIMEOUT):
    """``session.run(command)`` with its default (no) timeout, in a thread.

    The test, not the session, bounds the wait: if ``run`` is still blocked after
    ``limit`` seconds the test fails, and the fixture's ``close()`` ends the thread.
    Returns the result, or the exception ``run`` raised.
    """
    outcome: list[object] = []

    def call() -> None:
        try:
            outcome.append(session.run(command))
        except Exception as exc:  # handed back to the test
            outcome.append(exc)

    worker = threading.Thread(target=call, daemon=True)
    worker.start()
    worker.join(limit)
    assert not worker.is_alive(), f"run({command!r}) with no timeout still blocked after {limit} s"
    return outcome[0]


def _pairs(records: list[bytes]) -> tuple[int, int]:
    """Distinct start numbers and done records among ``records``.

    PS0 writes `S n` once per line of a multi-line command (spec §4.1); the session treats
    repeats of the same number as one start.
    """
    starts = {line for line in records if line.startswith(b"S ")}
    dones = sum(1 for line in records if line.startswith(b"D "))
    return len(starts), dones


def _write_bashrc(text: str) -> None:
    home = os.environ["HOME"]  # the suite's temporary HOME (tests/conftest.py)
    with open(os.path.join(home, ".bashrc"), "w", encoding="utf-8") as fh:
        fh.write(text)


def _assert_refused_unsent(session, writes, command, marker=None):
    """``command`` raises SessionDegraded and nothing reaches the PTY."""
    session_mod = _session_module()
    writes.clear()
    with pytest.raises(session_mod.SessionDegraded):
        _run(session, command)
    assert writes == []
    if marker is not None:
        time.sleep(0.2)
        assert not marker.exists()


# ---- (a) state persists between commands ----------------------------------------------


def test_cd_persists_between_commands(start_session):
    session, _ = start_session()
    _run(session, "cd /tmp")
    assert _run(session, "pwd").text == "/tmp\n"


def test_export_persists_between_commands(start_session):
    session, _ = start_session()
    _run(session, "export FOO=bar")
    assert _run(session, 'printf %s "$FOO"').text == "bar"


# ---- (b) spec §Conformance vectors 1-8, 10 and 12 -----------------------------------------


def test_vector1_true_gives_start_done_and_snapshot(start_session):
    session, records = start_session()
    result = _run(session, "true")
    lines = records.for_command(1)
    assert lines[0] == b"S 1\n"
    assert lines[1] == b"D 1 0 0\n"
    assert lines[-1] == b"E\n"
    assert sorted(line[:1] for line in lines[2:-1]) == sorted(SNAPSHOT_TYPES)
    assert (result.seq, result.ran, result.status, result.pipestatus) == (1, True, 0, (0,))
    assert result.snapshot.seq == 1


def test_vector2_pipestatus(start_session):
    session, _ = start_session()
    result = _run(session, "false | true")
    assert result.status == 0
    assert result.pipestatus == (1, 0)


def test_vector3_exit_status(start_session):
    session, _ = start_session()
    result = _run(session, "(exit 3)")
    assert result.status == 3
    assert result.pipestatus == (3,)


@pytest.mark.parametrize(
    "command, printed",
    [
        (r"printf 'D 99 0 0\n'", b"D 99 0 0"),
        (r"printf '\x1b]133;D;0\x07'", b"\x1b]133;D;0\x07"),
    ],
    ids=["vector4-fake-done-record", "vector5-osc133"],
)
def test_vectors4_5_printed_records_have_no_effect(start_session, command, printed):
    session, records = start_session()
    result = _run(session, command)
    assert printed in result.output  # it went to the PTY
    dones = [line for line in records.lines if line.startswith(b"D ")]
    assert dones[1:] == [b"D 1 0 0\n"]  # after the baseline's D 0: only the real one
    assert _pairs(records.for_command(1)) == (1, 1)
    assert result.status == 0
    assert not session.degraded


def test_vector6_no_history_expansion(start_session):
    session, _ = start_session()
    assert _run(session, "echo 'done!!'").text == "done!!\n"


def test_vector7_alias_and_function_reach_the_snapshot(start_session):
    session, _ = start_session()
    assert "g" not in session.baseline.functions
    assert "ll2" not in session.baseline.aliases
    result = _run(session, "alias ll2='ls -la'; g(){ :; }")
    assert "g" in result.snapshot.functions
    assert "alias ll2='ls -la'" in result.snapshot.aliases.split("\n")


def test_vector8_replaced_prompt_command_degrades(start_session):
    session_mod = _session_module()
    session, _ = start_session()
    began = time.monotonic()
    with pytest.raises(session_mod.SessionDegraded):
        _run(session, "PROMPT_COMMAND=:")
    assert time.monotonic() - began < 5.0
    assert session.degraded
    assert session.degraded_reason
    with pytest.raises(session_mod.SessionDegraded):
        _run(session, "true")  # sticky until restart


def test_vector10_interrupt_ends_the_command(start_session):
    session, records = start_session()
    sent_at: list[float] = []
    sent: list[bool] = []

    def press_ctrl_c() -> None:
        deadline = time.monotonic() + RUN_TIMEOUT
        while b"S 1\n" not in records.lines:
            if time.monotonic() > deadline:
                return
            time.sleep(0.01)
        time.sleep(0.3)
        sent_at.append(time.monotonic())
        sent.append(session.interrupt())

    typist = threading.Thread(target=press_ctrl_c, daemon=True)
    typist.start()
    result = _run(session, "sleep 5", timeout=8.0)
    typist.join(timeout=2)
    assert sent_at, "the interrupt was never sent"
    assert sent == [True]
    assert result.status == 130
    assert result.pipestatus == (130,)
    done_at = next(t for t, line in records.items if line.startswith(b"D 1 "))
    assert done_at - sent_at[0] < 3.0
    assert not session.degraded
    assert _run(session, "echo after").text == "after\n"


def test_interrupt_at_a_prompt_writes_nothing(start_session, monkeypatch):
    pty_writes = _spy_on_pty_writes(monkeypatch)
    session, records = start_session()
    assert session.interrupt() is False  # idle, before any command
    _run(session, "true")
    pty_writes.clear()
    assert session.interrupt() is False  # idle, after a command finished
    assert pty_writes == []
    before = len(records.items)
    time.sleep(1.0)  # a Ctrl-C at the prompt would have made bash send a stray D
    assert len(records.items) == before
    assert not session.degraded
    result = _run(session, "echo still fine")
    assert (result.seq, result.text) == (2, "still fine\n")


@pytest.mark.parametrize(
    "bad",
    ["echo a\x1b[201~", "echo \x1b", "echo a\rtouch {d}/c", "echo \x07", "echo \x00",
     "echo \x01", "echo \x1f"],
    ids=["paste-end", "esc", "cr", "bel", "nul", "soh", "us"],
)
def test_vector12_forbidden_bytes_are_refused_unsent(start_session, monkeypatch, tmp_path, bad):
    pty_writes = _spy_on_pty_writes(monkeypatch)
    session_mod = _session_module()
    session, records = start_session()
    before = len(records.items)
    command = f"touch {tmp_path}/a; {bad.replace('{d}', str(tmp_path))}; touch {tmp_path}/b"
    pty_writes.clear()
    with pytest.raises(session_mod.CommandRefused):
        _run(session, command)
    assert pty_writes == []  # nothing reached the PTY
    time.sleep(0.3)
    assert len(records.items) == before
    assert list(tmp_path.iterdir()) == []
    result = _run(session, "echo ok")
    assert result.seq == 1  # nothing ran in between
    assert result.text == "ok\n"


def test_tab_and_newline_are_allowed(start_session):
    session, _ = start_session()
    assert _run(session, "printf '%s\\n' 'a\tb'\necho c").text == "a\tb\nc\n"


# ---- (c) vector 9 typed raw: the control channel closed ----------------------------------


def test_vector9_closing_fd3_degrades(start_session):
    session_mod = _session_module()
    session, _ = start_session()
    with pytest.raises(session_mod.SessionDegraded):
        _run(session, "exec 3>&-")
    assert session.degraded
    assert session.degraded_reason == "the control channel closed"


# ---- the hooks survive set -u / set -e; a snapshot that never finishes -------------------


def test_nounset_without_path_keeps_the_snapshot_whole(start_session):
    session_mod = _session_module()
    session, _ = start_session()
    result = _run_default_timeout(session, "set -u; unset PATH")
    assert isinstance(result, session_mod.CommandResult), result
    assert result.snapshot.path == ""
    assert not session.degraded
    after = _run_default_timeout(session, "echo still here")
    assert isinstance(after, session_mod.CommandResult), after
    assert after.text == "still here\n"


def test_errexit_does_not_break_the_hooks(start_session):
    session, _ = start_session()
    _run(session, "set -e")
    for command in ("true", "", "echo ok"):
        _run(session, command)
    assert _run(session, "echo still ok").text == "still ok\n"
    assert not session.degraded


def test_snapshot_cut_short_after_done_degrades(start_session):
    # A DEBUG trap (inherited by functions through `set -T`, able to skip commands under
    # extdebug) skips every hook command from the H record on: the D and the first
    # snapshot records arrive, E never does, and bash is back at its prompt.
    session_mod = _session_module()
    session, records = start_session()
    cut = (
        "shopt -s extdebug; set -T; "
        "trap '[[ $BASH_COMMAND == \"__nls_enc H\"* ]] && __cut=1; (( ! ${__cut-0} ))' DEBUG"
    )
    began = time.monotonic()
    outcome = _run_default_timeout(session, cut)
    assert time.monotonic() - began < 5.0
    assert isinstance(outcome, session_mod.SessionDegraded), outcome
    assert b"D 1 0 0\n" in records.lines
    assert records.lines[-1] != b"E\n"
    assert session.degraded_reason == (
        "the snapshot did not finish after the shell returned to a prompt"
    )


# ---- (d) one start/done pair per command; stopped jobs ------------------------------------


@pytest.mark.parametrize(
    "command, output",
    [
        ("true", ""),
        ("echo one\necho two", "one\ntwo\n"),
        ("cat <<'EOF'\nhere doc\nEOF", "here doc\n"),
        ("f() {\n  echo in f\n}\nf", "in f\n"),
    ],
    ids=["no-output", "multi-line", "here-doc", "multi-line-function"],
)
def test_one_start_done_pair_per_command(start_session, command, output):
    session, records = start_session()
    result = _run(session, command)
    lines = records.for_command(1)
    assert _pairs(lines) == (1, 1)
    assert all(line == b"S 1\n" for line in lines if line.startswith(b"S "))
    assert result.ran
    assert result.text == output
    assert _run(session, "true").seq == 2


def test_background_job_gives_one_pair_and_is_not_a_stopped_job(start_session):
    session, records = start_session()
    result = _run(session, "sleep 1 &")
    assert _pairs(records.for_command(1)) == (1, 1)
    assert result.status == 0
    assert not session.degraded
    result = _run(session, "sleep 3 &")
    assert result.snapshot.stopped_jobs == 0  # running, not stopped
    assert _run(session, "echo still here").text.endswith("still here\n")
    assert not session.degraded


def test_stopped_job_is_counted(start_session):
    session, _ = start_session()
    _run(session, "sleep 30 & kill -STOP $!")
    assert _run(session, "true").snapshot.stopped_jobs == 1
    assert _run(session, "kill -KILL %1; wait %1 2>/dev/null; true").status == 0
    assert _run(session, "true").snapshot.stopped_jobs == 0


# ---- (e) decision 5: nothing ran -------------------------------------------------------------


@pytest.mark.parametrize(
    "command, status",
    [("", 3), ("# x", 3), ("fi", 2)],
    ids=["empty-line", "comment-only", "syntax-error"],
)
def test_input_that_runs_nothing_is_reported_not_run(start_session, command, status):
    session, records = start_session()
    _run(session, "(exit 3)")
    result = _run(session, command)
    assert not result.ran
    assert result.seq == 2
    assert result.status == status  # the D record's $?
    assert _pairs(records.for_command(2)) == (0, 1)
    assert not session.degraded
    after = _run(session, "true")
    assert (after.seq, after.ran, after.status) == (3, True, 0)


def test_unclosed_quote_degrades(start_session):
    session_mod = _session_module()
    session, _ = start_session()
    began = time.monotonic()
    with pytest.raises(session_mod.SessionDegraded):
        _run(session, "echo 'abc")
    assert time.monotonic() - began < 5.0
    assert session.degraded_reason == "no done record after the shell returned to a prompt"


# ---- (f) snapshot fields, the baseline, H and V ---------------------------------------------


def test_snapshot_carries_v1_fields_and_baseline(start_session):
    session, records = start_session()
    baseline = session.baseline
    types = {line[:1] for line in records.for_command(0)}
    assert set(SNAPSHOT_TYPES) | {b"D", b"E"} == types
    assert baseline.seq == 0
    assert baseline.extdebug == "shopt -u extdebug"
    assert baseline.path == os.environ["PATH"]
    assert baseline.stopped_jobs == 0
    for name in ("PROMPT_COMMAND", "PS0", "PS1", "__nls_done", "enable-bracketed-paste"):
        assert name in baseline.hooks
    assert "LD_PRELOAD" in baseline.variables
    result = _run(session, "true")
    assert session.baseline is baseline
    assert result.snapshot.hooks == baseline.hooks
    assert not result.variables_changed


def test_loader_variable_change_is_reported(start_session):
    session, _ = start_session()
    result = _run(session, "export LD_PRELOAD=/x.so")
    assert result.variables_changed
    assert result.snapshot.variables != session.baseline.variables
    assert 'declare -x LD_PRELOAD="/x.so"' in result.snapshot.variables.split("\n")
    assert not session.degraded


def test_blank_ps0_is_not_hidden_as_not_run(start_session, tmp_path):
    session_mod = _session_module()
    session, _ = start_session()
    with pytest.raises(session_mod.SessionDegraded):
        _run(session, "PS0=")
    marker = tmp_path / "ran"
    with pytest.raises(session_mod.SessionDegraded):
        _run(session, f"touch {marker}; true")
    assert session.degraded
    assert "H differs" in session.degraded_reason
    assert not marker.exists()  # refused, not run and reported as "nothing ran"


# ---- (g) I2: a command that ran is never reported as "nothing ran" --------------------------


def _rcfile_variables(rcfile: str) -> set[str]:
    """Every shell variable the rcfile reads or assigns, by bash syntax."""
    patterns = (
        r"\$\{[#!]?([A-Za-z_]\w*)",  # ${name...}, ${#name}, ${!name}
        r"\$([A-Za-z_]\w*)",  # $name
        r"\$\(\(\s*([A-Za-z_]\w*)",  # $((name ...
        r"\(\(\s*\+\+([A-Za-z_]\w*)",  # (( ++name
        r"(?:^|[\s;(])([A-Za-z_]\w*)(?:\[[^\]]*\])?\+?=",  # name=, name[i]=, name+=
        r"\bfor\s+([A-Za-z_]\w*)\s+in\b",
        r"\bprintf\s+-v\s+([A-Za-z_]\w*)",
        r"\bread\s+(?:-\w+\s+(?:\d+\s+)?)*([A-Za-z_]\w*)",
        r"\[\[\s+-v\s+\$?([A-Za-z_]\w*)",
    )
    names: set[str] = set()
    for pattern in patterns:
        names.update(re.findall(pattern, rcfile, flags=re.MULTILINE))
    return names


def test_hook_state_vars_cover_the_rcfile():
    session_mod = _session_module()
    rcfile = session_mod.RCFILE
    listed = set(session_mod.HOOK_STATE_VARS)
    assert all(name.startswith("__nls_") for name in listed)
    found = set(re.findall(r"__nls_\w+", rcfile))
    assert found <= listed, found - listed
    assert listed <= found, listed - found
    # The hooks' own variables all carry the prefix; the others are bash's, which the
    # rcfile reads or sets on purpose. No `local`: a readonly global would make it fail.
    bash_owned = {"PIPESTATUS", "PATH", "PROMPT_COMMAND", "PS0", "PS1", "PS2", "HISTFILE"}
    variables = _rcfile_variables(rcfile)
    assert {"__nls_seq", "__nls_st", "__nls_v", "__nls_c"} <= variables  # the parser works
    stray = {name for name in variables if not name.startswith("__nls_")} - bash_owned
    assert stray == set(), stray
    assert not re.search(r"\blocal\b", rcfile)


def _hook_names():
    return _session_module().HOOK_STATE_VARS


# Each assigns the variable the value a start guard would need to suppress the S of a
# later command (the iteration-v3 reproducers): the current sequence number at every
# prompt (PS1, DEBUG trap), or the third command's number frozen with readonly.
_I2_ATTACKS = {
    "ps1-subscript": "PS1='${{__pwn[{name}=__nls_seq]-}}\\$ '",
    "readonly": "readonly {name}=$((__nls_seq + 2))",
    "debug-trap": "trap '{name}=$__nls_seq' DEBUG",
}


@pytest.mark.parametrize("attack", sorted(_I2_ATTACKS))
def test_hook_state_attacks_never_hide_a_command(start_session, tmp_path, attack):
    session_mod = _session_module()
    for name in _hook_names():
        session, _ = start_session()
        marker = tmp_path / f"{attack}-{name}"
        _try_run(session, _I2_ATTACKS[attack].format(name=name))
        _try_run(session, "true")
        third = _try_run(session, f"touch {marker}; echo printed; (exit 7)")
        if session.degraded:
            if not isinstance(third, session_mod.SessionDegraded) or third.result is None:
                # refused before the paste: it never ran
                assert not marker.exists(), (attack, name)
            continue
        assert isinstance(third, session_mod.CommandResult), (attack, name, third)
        assert (third.ran, third.status, third.text) == (True, 7, "printed\n"), (attack, name)
        assert marker.exists()
        session.close()


# ---- (h) Table A "detect" rows: degraded at that command's snapshot -------------------------

_TABLE_A = {
    "prompt-command-assigned": "PROMPT_COMMAND=\"$PROMPT_COMMAND; :\"",
    "prompt-command-array": "PROMPT_COMMAND+=(':')",
    "ps0": "PS0='x'",
    "debug-trap": "trap ':' DEBUG",
    "return-trap": "trap ':' RETURN",
    "functrace": "set -o functrace",
    "extdebug": "shopt -s extdebug",
    "histexpand": "set -H",
    "vi-mode": "set -o vi",
    "no-line-editing": "set +o emacs",
    "cr-macro": "bind '\"\\r\": \" ; touch {m}\\n\"'",
    "cr-shell-command": "bind -x '\"\\C-m\": \"touch {m}\"'",
    "paste-start-prefix-macro": "bind '\"\\e[2\": \"touch {m}\\n\"'",
    "bracketed-paste-off": "bind 'set enable-bracketed-paste off'",
    "convert-meta-on": "bind 'set convert-meta on'",
    "hook-function-redefined": "__nls_ret() { builtin return \"$1\"; }",
    "main-hook-redefined": "__f=$(declare -f __nls_done); eval \"${__f/\\{/\\{ :;}\"",
    "stdout-redirected": "exec >/dev/null",
    "stderr-redirected": "exec 2>/dev/null",
    "stdin-redirected": "exec </dev/null",
}


@pytest.mark.parametrize("change", sorted(_TABLE_A))
def test_table_a_changes_degrade_at_their_own_snapshot(start_session, monkeypatch, tmp_path,
                                                        change):
    pty_writes = _spy_on_pty_writes(monkeypatch)
    session_mod = _session_module()
    session, _ = start_session()
    assert session.baseline is not None and "emacs on" in session.baseline.hooks
    marker = tmp_path / "bound_marker"
    with pytest.raises(session_mod.SessionDegraded) as caught:
        _run(session, _TABLE_A[change].replace("{m}", str(marker)))
    # Found in the snapshot that followed this command's D, not by a later rule.
    assert caught.value.result is not None, session.degraded_reason
    assert caught.value.result.seq == 1
    _assert_refused_unsent(session, pty_writes, "echo hello", marker)
    assert not marker.exists()


# ---- (i) I3: nothing installed by confirmed input runs after the snapshot --------------------


def test_user_prompt_command_rebinding_cr_degrades_before_the_next_paste(
    start_session, monkeypatch, tmp_path
):
    pty_writes = _spy_on_pty_writes(monkeypatch)
    marker = tmp_path / "pc_marker"
    _write_bashrc(
        "__pc_runs=0\n"
        "__pc() { (( ++__pc_runs == 2 )) && bind '\"\\r\": \" ; touch "
        f"{marker}" "\\n\"'; return 0; }\n"
        "PROMPT_COMMAND=__pc\n"
    )
    session_mod = _session_module()
    session, _ = start_session()
    assert not session.degraded  # first run: nothing bound yet
    with pytest.raises(session_mod.SessionDegraded) as caught:
        _run(session, "true")  # its prompt runs the user hook a second time
    assert caught.value.result is not None  # seen in that command's own snapshot
    _assert_refused_unsent(session, pty_writes, "echo hello", marker)
    assert not marker.exists()


def _rebind_cr_function(marker) -> str:
    """Shell text defining ``__rb``, which binds CR to append ``touch marker`` to the line."""
    return "__rb() { bind '\"\\r\": \" ; touch " f"{marker}" "\\n\"'; }"


def test_user_ps1_never_runs(start_session, monkeypatch, tmp_path):
    pty_writes = _spy_on_pty_writes(monkeypatch)
    # bash 5.3's `${ cmd; }` runs cmd in the shell itself when PS1 is expanded. nl-shell
    # sets PS1 before every prompt, so neither the ~/.bashrc PS1 nor a confirmed one is
    # ever expanded (spec §1.2). Had either run, H would show CR rebound and degrade.
    marker = tmp_path / "ps1_marker"
    _write_bashrc(_rebind_cr_function(marker) + "\nPS1='${ __rb; }\\$ '\n")
    session, _ = start_session()
    for command in ("true", "PS1='${ __rb; }\\$ '", "true"):
        outcome = _try_run(session, command)
        if session.degraded:
            _assert_refused_unsent(session, pty_writes, "echo hello", marker)
            break
        assert outcome.ran
    else:
        assert _run(session, "echo 'exact  bytes'").text == "exact  bytes\n"
        assert "accept-line" in _run(session, "bind -p | grep -F '\"\\C-m\"'").text
    assert not marker.exists()


def test_xtrace_ps4_acts_only_before_the_snapshot(start_session, monkeypatch, tmp_path):
    pty_writes = _spy_on_pty_writes(monkeypatch)
    # With xtrace on, PS4 is expanded for every traced command, and `${ cmd; }` runs cmd in
    # the shell. The hook turns xtrace off for its own body, so PS4 last runs for the
    # traced call of the hook itself, before the snapshot, which then shows the change.
    marker = tmp_path / "ps4_marker"
    session_mod = _session_module()
    session, _ = start_session()
    command = _rebind_cr_function(marker) + "; PS4='${ __rb; }+ '; set -x"
    with pytest.raises(session_mod.SessionDegraded) as caught:
        _run(session, command)
    assert caught.value.result is not None  # caught at that command's own snapshot
    assert "H differs" in session.degraded_reason
    _assert_refused_unsent(session, pty_writes, "echo hello", marker)


def test_xtrace_ps4_payload_never_runs_in_a_later_command(start_session, monkeypatch, tmp_path):
    # Sign-off of iteration v4: the PS4 payload only appends to a marker (no CR rebind), so
    # nothing else in H changes. xtrace, PS4 and BASH_XTRACEFD are themselves in H (Table A
    # row "xtrace, PS4, BASH_XTRACEFD"), so the session degrades at this command's own
    # snapshot and no later command is sent, so the payload never runs again.
    pty_writes = _spy_on_pty_writes(monkeypatch)
    session_mod = _session_module()
    session, _ = start_session()
    marker = tmp_path / "ps4_payload"
    command = f"exec 9>/dev/null; BASH_XTRACEFD=9; PS4='$(echo x >> {marker})'; set -x"
    with pytest.raises(session_mod.SessionDegraded) as caught:
        _run(session, command)
    assert caught.value.result is not None, session.degraded_reason  # its own snapshot
    assert caught.value.result.seq == 1
    assert "H differs" in session.degraded_reason
    # The payload may have run for the hook's own first (traced) command, before the
    # snapshot. It must never run for a command sent afterwards.
    before = marker.read_bytes() if marker.exists() else b""
    for later in ("true", "echo hello"):
        _assert_refused_unsent(session, pty_writes, later)
    time.sleep(0.3)
    assert (marker.read_bytes() if marker.exists() else b"") == before


@pytest.mark.parametrize(
    "change",
    ["set -x", "PS4='++ '", "exec 9>/dev/null; BASH_XTRACEFD=9"],
    ids=["xtrace", "ps4", "xtrace-fd"],
)
def test_xtrace_settings_degrade_at_their_own_snapshot(start_session, monkeypatch, change):
    pty_writes = _spy_on_pty_writes(monkeypatch)
    session_mod = _session_module()
    session, _ = start_session()
    with pytest.raises(session_mod.SessionDegraded) as caught:
        _run(session, change)
    assert caught.value.result is not None, session.degraded_reason
    assert "H differs" in session.degraded_reason
    _assert_refused_unsent(session, pty_writes, "echo hello")


# ---- output boundary: what the user's prompt hook prints is not the command's output ---------


@pytest.mark.parametrize(
    "hook",
    [
        "printf 'HOOK-OUTPUT\\n'",
        # what VTE's hook in /etc/bash.bashrc prints (OSC 7, the current directory)
        "printf '\\033]7;file://host%s\\033\\\\' \"$PWD\"",
    ],
    ids=["text", "osc7"],
)
def test_user_prompt_hook_output_is_not_the_commands(start_session, hook):
    # Sign-off of iteration v4: the user's PROMPT_COMMAND runs after D, and what it printed
    # leaked into the command's output in 25 of 40 runs. Output is now cut where bash marks
    # the end of the command on the PTY itself, before D and before the user hook.
    _write_bashrc(f"__user_hook() {{ {hook}; }}\nPROMPT_COMMAND=__user_hook\n")
    session, _ = start_session()
    for i in range(30):
        assert _run(session, f"echo hello{i}").output == b"hello%d\r\n" % i
        assert _run(session, "printf abc").output == b"abc"
        assert _run(session, "true").output == b""
    assert not session.degraded


def test_system_vte_prompt_hook_output_is_not_the_commands(start_session, monkeypatch):
    # The case the v4 sign-off measured: Ubuntu's /etc/bash.bashrc sources VTE's hook when
    # VTE_VERSION is set, and that hook prints OSC 7 at every prompt. (On a host without
    # the hook this runs with no user hook at all and checks the plain case.)
    monkeypatch.setenv("VTE_VERSION", "7600")
    session, _ = start_session()
    for i in range(30):
        assert _run(session, f"echo hello{i}").output == b"hello%d\r\n" % i
    assert not session.degraded


# ---- (j) Table B: outside checks ------------------------------------------------------------


def test_changed_interrupt_character_degrades(start_session, monkeypatch, tmp_path):
    pty_writes = _spy_on_pty_writes(monkeypatch)
    session_mod = _session_module()
    session, _ = start_session()
    marker = tmp_path / "never_confirmed_to_run"
    with pytest.raises(session_mod.SessionDegraded) as caught:
        _run(session, "stty intr '|'")
    assert caught.value.result is not None
    assert "terminal settings" in session.degraded_reason
    _assert_refused_unsent(session, pty_writes, f"true || touch {marker}", marker)


def test_signals_turned_off_degrades_before_the_next_paste(start_session, monkeypatch):
    pty_writes = _spy_on_pty_writes(monkeypatch)
    session_mod = _session_module()
    session, _ = start_session()
    with pytest.raises(session_mod.SessionDegraded):
        _run(session, "stty -isig")
    assert "terminal settings" in session.degraded_reason
    _assert_refused_unsent(session, pty_writes, "true")


def test_terminal_change_from_a_background_job_degrades(start_session, monkeypatch):
    pty_writes = _spy_on_pty_writes(monkeypatch)
    session, _ = start_session()
    _run(session, "(trap '' TTOU; sleep 0.3; stty intr '|') &")
    time.sleep(1.0)
    _assert_refused_unsent(session, pty_writes, "true")
    assert "terminal settings" in session.degraded_reason


@pytest.mark.parametrize("content", ["1", None], ids=["allowed", "missing"])
def test_tiocsti_allowed_or_unknown_starts_degraded(start_session, monkeypatch, tmp_path,
                                                    content):
    pty_writes = _spy_on_pty_writes(monkeypatch)
    path = tmp_path / "legacy_tiocsti"
    if content is not None:
        path.write_text(content + "\n", encoding="ascii")
    session, _ = start_session(tiocsti_path=str(path))
    assert session.degraded
    assert str(path) in session.degraded_reason
    _assert_refused_unsent(session, pty_writes, "true")


def test_tiocsti_off_is_healthy(start_session, tmp_path):
    path = tmp_path / "legacy_tiocsti"
    path.write_text("0\n", encoding="ascii")
    session, _ = start_session(tiocsti_path=str(path))
    assert not session.degraded


def test_stopped_shell_degrades_without_hanging(start_session, monkeypatch):
    pty_writes = _spy_on_pty_writes(monkeypatch)
    session, _ = start_session()
    _run(session, "(sleep 0.3; kill -STOP $$) &")
    time.sleep(0.8)
    began = time.monotonic()
    _assert_refused_unsent(session, pty_writes, "true")
    assert time.monotonic() - began < 5.0
    assert "stopped" in session.degraded_reason


def test_shell_stopped_while_a_command_runs_degrades(start_session):
    session_mod = _session_module()
    session, _ = start_session()
    began = time.monotonic()
    outcome = _run_default_timeout(session, "(sleep 0.3; kill -STOP $$) & sleep 2")
    assert time.monotonic() - began < 5.0
    assert isinstance(outcome, session_mod.SessionDegraded), outcome
    assert "stopped" in session.degraded_reason


# ---- (k) the prompt rule (decision 7) -------------------------------------------------------


@pytest.mark.parametrize(
    "command, output",
    [
        ("x=$(sleep 2); echo hi", "hi\n"),
        ('cd "$(sleep 1.5; echo /tmp)"; pwd', "/tmp\n"),
        ("y=`sleep 1.5`; echo \"[$y]\"", "[]\n"),
    ],
    ids=["dollar-paren", "cd-substitution", "backticks"],
)
def test_slow_command_substitution_stays_healthy(start_session, command, output):
    session, _ = start_session()
    result = _run(session, command)
    assert result.text == output
    assert not session.degraded


def test_read_with_no_input_degrades(start_session):
    session_mod = _session_module()
    session, _ = start_session()
    began = time.monotonic()
    with pytest.raises(session_mod.SessionDegraded):
        _run(session, "read x")
    assert time.monotonic() - began < 5.0
    assert session.degraded_reason == "no done record after the shell returned to a prompt"


# ---- (l) decision 4: exact, reversible fields; no external programs -----------------------


def _live(session, tmp_path, expression: str) -> str:
    out = tmp_path / "live"
    _run(session, f'printf %s "{expression}" > {out}')
    return out.read_bytes().decode("utf-8")


def test_path_round_trips_exactly(start_session, tmp_path):
    session, _ = start_session()
    result = _run(session, "PATH=\"$PATH\"$':/a\\x1eb:/c\\nd:/e\\\\nf\\rg'")
    live = _live(session, tmp_path, "$PATH")
    assert "\x1e" in live and "\n" in live and "\\n" in live and "\r" in live
    assert result.snapshot.path == live
    assert not session.degraded


def test_alias_round_trips_exactly(start_session, tmp_path):
    session, _ = start_session()
    result = _run(session, "alias odd_nls=$'a\\\\b\\x1e\\nc \\'q\\''")
    live = _live(session, tmp_path, "$(alias -p)")
    assert "odd_nls" in live and "\x1e" in live and "\n" in live
    assert result.snapshot.aliases == live
    assert not session.degraded


def test_trap_round_trips_exactly(start_session, tmp_path):
    session, _ = start_session()
    result = _run(session, "trap $'echo \"x\\\\y\"\\x1e\\n: z' USR1")
    live = _live(session, tmp_path, "$(trap -p)")
    assert "USR1" in live and "\x1e" in live and "\\" in live
    assert result.snapshot.traps == live
    assert not session.degraded


@pytest.mark.parametrize(
    "setup",
    [
        "hash -p {fake}/tr tr",
        "hash -p {fake}/cksum cksum",
        "hash -p {fake}/wc wc",
        "BASH_CMDS[tr]={fake}/tr",
        "PATH={fake}:$PATH",
    ],
    ids=["hash-tr", "hash-cksum", "hash-wc", "bash-cmds-tr", "path-first"],
)
def test_fake_programs_cannot_change_the_snapshot(start_session, tmp_path, setup):
    fake = tmp_path / "fake"
    fake.mkdir()
    marker = tmp_path / "fake-ran"
    for name in ("tr", "cksum", "wc"):
        script = fake / name
        script.write_text(f"#!/bin/sh\ntouch {marker}\necho 0\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
    session, _ = start_session()
    command = setup.format(fake=fake) + "; alias evil_nls='rm -rf'; evil_fn(){ :; }"
    result = _run(session, command)
    snap = _run(session, "true").snapshot
    for s in (result.snapshot, snap):
        assert "alias evil_nls='rm -rf'" in s.aliases.split("\n")
        assert "evil_fn" in s.functions
        assert s.hooks == session.baseline.hooks
    assert not marker.exists()
    assert not session.degraded


# ---- (m) the user's ~/.bashrc ---------------------------------------------------------------


def test_bashrc_alias_and_prompt_command_run_before_the_snapshot(start_session):
    _write_bashrc(
        "alias hello_nls='echo hi'\n"
        "PROMPT_COMMAND='s=$?; alias pc_saw_status=\"$s\"; echo \"$__nls_seq $s\" >> ~/pc.log'\n"
    )
    session, _ = start_session()
    baseline_aliases = session.baseline.aliases.split("\n")
    assert "alias hello_nls='echo hi'" in baseline_aliases
    # The user's hook ran at the first prompt before the baseline was taken (decision 6).
    assert "alias pc_saw_status='0'" in baseline_aliases
    result = _run(session, "(exit 4)")
    # It ran again before this command's snapshot, and saw the command's real $?.
    assert "alias pc_saw_status='4'" in result.snapshot.aliases.split("\n")
    _run(session, "true")
    with open(os.path.join(os.environ["HOME"], "pc.log"), encoding="utf-8") as fh:
        seen = fh.read().split("\n")
    assert seen[:3] == ["0 0", "1 4", "2 0"]
    assert not session.degraded


def test_bashrc_turning_bracketed_paste_off_and_vi_mode(start_session):
    _write_bashrc("bind 'set enable-bracketed-paste off'\nset -o vi\n")
    session, records = start_session()
    if session.degraded:
        assert session.degraded_reason
        return
    result = _run(session, "echo 'a  b'\necho \"c\td\"")
    assert result.output == b"a  b\r\nc\td\r\n"
    assert _pairs(records.for_command(1)) == (1, 1)


def test_bashrc_turning_line_editing_off_still_pastes_exactly(start_session):
    _write_bashrc("set +o emacs\n")
    session, _ = start_session()
    if session.degraded:
        assert session.degraded_reason
        return
    assert _run(session, "echo 'x  y'").text == "x  y\n"


# ---- (n) no history; control-channel wiring and framing -------------------------------------


def test_histfile_is_unset(start_session):
    session, _ = start_session()
    assert _run(session, 'printf %s "${HISTFILE-unset}"').text == "unset"
    session.close()
    assert not os.path.exists(os.path.join(os.environ["HOME"], ".bash_history"))


def test_fd3_is_a_pipe(start_session):
    session, _ = start_session()
    assert _run(session, "[ -p /dev/fd/3 ] && echo fifo").text == "fifo\n"


def test_record_with_carriage_return_is_malformed():
    protocol = _protocol_module()
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_record(b"S 1\r")
    tracker = protocol.ProtocolTracker()
    tracker.feed(b"D 0 0 0\r\n")
    assert tracker.degraded
    assert "carriage return" in tracker.degraded_reason


def test_unknown_record_types_are_ignored():
    protocol = _protocol_module()
    tracker = protocol.ProtocolTracker()
    tracker.feed(b"D 0 0 0\nQ something new\n")
    assert not tracker.degraded


def test_repeated_start_record_is_one_start_but_another_number_degrades():
    protocol = _protocol_module()
    tracker = protocol.ProtocolTracker()
    baseline = b"D 0 0 0\nF \nL \nT \nB \nX \nP \nJ 0\nH h\nV \nE\n"
    tracker.feed(baseline)
    tracker.command_sent()
    tracker.feed(b"S 1\nS 1\nS 1\n")
    assert not tracker.degraded
    tracker.feed(b"S 2\n")
    assert tracker.degraded


def test_spec_reference_rcfile_is_the_one_in_use():
    session_mod = _session_module()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = os.path.join(root, "docs", "design", "specs", "pty-protocol", "v1.md")
    with open(spec, encoding="utf-8") as fh:
        text = fh.read()
    section = text[text.index("3. Reference rcfile") :]
    reference = section[section.index("```bash\n") + 8 : section.index("```\n")]
    assert session_mod.RCFILE.split("\n", 1)[1] == reference


def test_field_encoding_is_reversible():
    protocol = _protocol_module()
    assert protocol.decode_field("a\\\\n\\nb\\r") == "a\\n\nb\r"
    with pytest.raises(protocol.ProtocolError):
        protocol.decode_field("bad\\x")
    with pytest.raises(protocol.ProtocolError):
        protocol.decode_field("trailing\\")


# ---- (o) restart ----------------------------------------------------------------------------


def test_restart_after_degraded_gives_a_fresh_session(start_session):
    session_mod = _session_module()
    session, _ = start_session()
    old_baseline = session.baseline
    with pytest.raises(session_mod.SessionDegraded):
        _run(session, "PROMPT_COMMAND=:")
    session.restart(timeout=START_TIMEOUT)
    assert not session.degraded
    assert session.degraded_reason is None
    assert session.baseline is not old_baseline
    assert session.baseline.seq == 0
    result = _run(session, "echo back")
    assert (result.seq, result.text) == (1, "back\n")


# ---- (p) output capture never comes back empty from a healthy session -----------------------


@pytest.mark.parametrize(
    "change",
    ["bind 'set enable-bracketed-paste off'", "set +o emacs", "set -o vi"],
    ids=["paste-off", "no-line-editing", "vi-mode"],
)
def test_output_is_never_silently_lost(start_session, change):
    session_mod = _session_module()
    session, _ = start_session()
    _try_run(session, change)
    outcome = _try_run(session, "echo hello")
    if isinstance(outcome, session_mod.CommandResult):
        assert not (outcome.output == b"" and not session.degraded)
        assert outcome.text == "hello\n"
    else:
        assert session.degraded


# ---- captured output is bounded -------------------------------------------------------------


def test_captured_output_is_bounded_and_keeps_the_tail(start_session):
    session, _ = start_session(max_output=1000)
    result = _run(session, "printf 'x%.0s' {1..5000}; echo; echo END_MARK")
    assert result.output_truncated
    assert len(result.output) <= 1000
    assert result.text.endswith("END_MARK\n")
    assert not _run(session, "echo small").output_truncated

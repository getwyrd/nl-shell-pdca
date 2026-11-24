"""The persistent bash session (#10) against pty-protocol v1 (docs/design/specs/pty-protocol/v1.md).

Every test starts a real bash on a PTY; they need only bash (>= 5.1) and ptyprocess — no
VM, no sudo. The session module is imported inside each test, not at module level, so
with the module missing the tests fail rather than the file failing to import. Every
call that waits on bash has a timeout, and every session is closed when its test ends.
"""

from __future__ import annotations

import contextlib
import importlib
import os
import select
import shlex
import signal
import termios
import threading
import time

import pytest

START_TIMEOUT = 10.0  # starting bash and reading its first snapshot
RUN_TIMEOUT = 5.0  # one command

SNAPSHOT_TYPES = (b"F", b"L", b"T", b"B", b"X", b"P", b"J", b"H", b"V")


def _session_module():
    return importlib.import_module("nl_shell.session")


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
        """The records from `S seq` (or the D, if no S came) up to the following `E`."""
        lines = self.lines
        start = next(
            i for i, line in enumerate(lines)
            if line == b"S %d\n" % seq or line.startswith(b"D %d " % seq)
        )
        end = next(i for i in range(start, len(lines)) if lines[i] == b"E\n")
        return lines[start : end + 1]


@contextlib.contextmanager
def _session(**kwargs):
    """A started session whose records are checked for v1 framing when the test ends (j)."""
    session_mod = _session_module()
    records = _Records()
    session = session_mod.Session.start(timeout=START_TIMEOUT, on_record=records, **kwargs)
    try:
        yield session, records
    finally:
        session.close()
    for line in records.lines:
        assert line.endswith(b"\n") and b"\r" not in line, line


def _run(session, command, **kwargs):
    kwargs.setdefault("timeout", RUN_TIMEOUT)
    return session.run(command, **kwargs)


def _pairs(records: list[bytes]) -> tuple[int, int]:
    starts = sum(1 for line in records if line.startswith(b"S "))
    dones = sum(1 for line in records if line.startswith(b"D "))
    return starts, dones


class _FakeTerminal:
    """An os.openpty() pair standing in for the user's terminal.

    The session owns the slave side (as it would own /dev/tty); the test plays the user
    on the master side: it types by writing there and reads what was mirrored.
    """

    def __init__(self, rows: int = 24, cols: int = 80) -> None:
        self.master, self.slave = os.openpty()
        termios.tcsetwinsize(self.master, (rows, cols))
        self.mirrored = bytearray()
        self._stop = threading.Event()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def terminal(self):
        return _session_module().Terminal(self.slave, self.slave)

    def _read(self) -> None:
        while not self._stop.is_set():
            if select.select([self.master], [], [], 0.05)[0]:
                try:
                    self.mirrored += os.read(self.master, 65536)
                except OSError:
                    return

    def close(self) -> None:
        self._stop.set()
        self._reader.join(timeout=2)
        os.close(self.master)
        os.close(self.slave)


@contextlib.contextmanager
def _fake_terminal(**kwargs):
    term = _FakeTerminal(**kwargs)
    try:
        yield term
    finally:
        term.close()


def _after_start(records: _Records, seq: int, delay: float, action) -> threading.Thread:
    """Run `action` `delay` seconds after the session reported `S seq` (bounded wait)."""

    def body() -> None:
        deadline = time.monotonic() + RUN_TIMEOUT
        while b"S %d\n" % seq not in records.lines:
            if time.monotonic() > deadline:
                return
            time.sleep(0.01)
        time.sleep(delay)
        action()

    thread = threading.Thread(target=body, daemon=True)
    thread.start()
    return thread


# ---- (a) state persists between commands ----------------------------------------------


def test_cd_persists_between_commands():
    with _session() as (session, _):
        _run(session, "cd /tmp")
        assert _run(session, "pwd").text == "/tmp\n"


def test_export_persists_between_commands():
    with _session() as (session, _):
        _run(session, "export FOO=bar")
        assert _run(session, 'printf %s "$FOO"').text == "bar"


# ---- (b) spec §Conformance vectors 1-8 and 10 -------------------------------------------


def test_vector1_true_gives_start_done_and_snapshot():
    with _session() as (session, records):
        result = _run(session, "true")
        lines = records.for_command(1)
        assert lines[0] == b"S 1\n"
        assert lines[1] == b"D 1 0 0\n"
        assert lines[-1] == b"E\n"
        assert all(line[:1] in SNAPSHOT_TYPES for line in lines[2:-1])
        assert (result.seq, result.status, result.pipestatus) == (1, 0, (0,))
        assert result.snapshot.seq == 1


def test_vector2_pipestatus():
    with _session() as (session, _):
        result = _run(session, "false | true")
        assert result.status == 0
        assert result.pipestatus == (1, 0)


def test_vector3_exit_status():
    with _session() as (session, _):
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
def test_vectors4_5_printed_records_have_no_effect(command, printed):
    with _session() as (session, records):
        result = _run(session, command)
        assert printed in result.output  # it went to the PTY
        lines = records.for_command(1)
        assert _pairs(lines) == (1, 1)
        assert lines[1] == b"D 1 0 0\n"
        dones = [line for line in records.lines if line.startswith(b"D ")]
        assert dones[1:] == [b"D 1 0 0\n"]  # after the baseline's D 0: only the real one
        assert result.status == 0
        assert not session.degraded


def test_vector6_no_history_expansion():
    with _session() as (session, _):
        assert _run(session, "echo 'done!!'").text == "done!!\n"


def test_vector7_alias_and_function_reach_the_snapshot():
    with _session() as (session, _):
        assert "g" not in session.baseline.functions
        result = _run(session, "alias ll2='ls -la'; g(){ :; }")
        assert "g" in result.snapshot.functions
        assert any(alias.startswith("alias ll2=") for alias in result.snapshot.aliases)


def test_vector8_replaced_prompt_command_degrades():
    session_mod = _session_module()
    with _session() as (session, _):
        began = time.monotonic()
        with pytest.raises(session_mod.SessionDegraded):
            _run(session, "PROMPT_COMMAND=:")
        assert time.monotonic() - began < 3.0
        assert session.degraded
        assert "prompt" in session.degraded_reason
        with pytest.raises(session_mod.SessionDegraded):
            _run(session, "true")  # sticky until restart
        session.restart(timeout=START_TIMEOUT)
        assert not session.degraded
        assert _run(session, "echo back").text == "back\n"


def test_vector10_ctrl_c_reaches_the_command():
    with _session() as (session, records), _fake_terminal() as term:
        sent_at: list[float] = []

        def press_ctrl_c() -> None:
            sent_at.append(time.monotonic())
            os.write(term.master, b"\x03")

        typist = _after_start(records, 1, 0.5, press_ctrl_c)
        result = _run(session, "sleep 5", terminal=term.terminal(), timeout=8.0)
        typist.join(timeout=2)
        assert result.status == 130
        assert result.pipestatus == (130,)
        done_at = next(t for t, line in records.items if line.startswith(b"D 1 "))
        assert sent_at and done_at - sent_at[0] < 2.0
        assert not session.degraded


# ---- (c) vector 9: the control channel closed --------------------------------------------


def test_vector9_closing_fd3_degrades():
    session_mod = _session_module()
    with _session() as (session, _):
        with pytest.raises(session_mod.SessionDegraded):
            _run(session, "exec 3>&-")
        assert session.degraded
        assert "control channel closed" in session.degraded_reason


# ---- (d) vector 12: forbidden bytes are never sent ------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "echo a\x1b[201~",
        "echo \x1b",
        "echo a\rtouch {d}/c",
        "echo \x07",
        "echo \x00",
        "echo \x7f\x1b[200~",
    ],
    ids=["paste-end", "esc", "cr", "bel", "nul", "paste-start"],
)
def test_vector12_forbidden_bytes_are_refused_unsent(bad, tmp_path):
    session_mod = _session_module()
    with _session() as (session, records):
        before = len(records.items)
        bad = bad.replace("{d}", str(tmp_path))
        command = f"touch {tmp_path}/a; {bad}; touch {tmp_path}/b"
        with pytest.raises(session_mod.CommandRefused):
            _run(session, command)
        time.sleep(0.3)  # anything bash got would have produced records by now
        assert len(records.items) == before
        assert list(tmp_path.iterdir()) == []
        result = _run(session, "echo ok")
        assert result.seq == 1  # nothing ran in between
        assert result.text == "ok\n"


# ---- (e) vector 11: the alternate screen is mirrored, not captured ------------------------


def test_vector11_alternate_screen_is_mirrored_not_captured():
    command = (
        r"printf 'before\n\033[?1049hHIDDEN_ONE\n\033[?1049lafter1\n"
        r"\033[?47hHIDDEN_TWO\n\033[?47lafter2\n'"
    )
    with _session(term="xterm-256color") as (session, _), _fake_terminal() as term:
        result = _run(session, command, terminal=term.terminal())
        time.sleep(0.2)  # let the reader thread collect the mirror
        assert result.text == "before\nafter1\nafter2\n"
        assert b"HIDDEN_ONE" in term.mirrored and b"HIDDEN_TWO" in term.mirrored


def test_alternate_screen_capture_resumes_only_on_the_matching_reset():
    # §6.2: capture resumes on the *matching* reset. A 47 reset does not end a 1049 switch,
    # and one sequence may set several modes at once (`ESC [?1;1049h`).
    command = (
        r"printf 'a\n\033[?1049hHIDDEN_ONE\n\033[?47lSECRET2\n\033[?1049lb\n"
        r"\033[?1;1049hHIDDEN_THREE\n\033[?1049;1lc\n'"
    )
    with _session(term="xterm-256color") as (session, _), _fake_terminal() as term:
        result = _run(session, command, terminal=term.terminal())
        time.sleep(0.2)
        assert result.text == "a\nb\nc\n"
        assert b"SECRET2" in term.mirrored and b"HIDDEN_THREE" in term.mirrored


def test_alternate_screen_switch_split_across_reads():
    # The PTY can hand a switch over in pieces; feed the capture one byte at a time.
    session_mod = _session_module()
    capture = session_mod._Capture()
    stream = b"x\x1b[?01049hHID\x1b[?47lHID2\x1b[?1049ly\x1b[?25l"
    for i in range(len(stream)):
        capture.feed(stream[i : i + 1])
    capture.stop()
    assert bytes(capture.data) == b"xy\x1b[?25l"


# ---- (f) one start/done pair per command --------------------------------------------------


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
def test_one_start_done_pair_per_command(command, output):
    with _session() as (session, records):
        result = _run(session, command)
        assert _pairs(records.for_command(1)) == (1, 1)
        assert result.text == output


def test_background_job_gives_one_pair_and_is_not_a_stopped_job():
    with _session() as (session, records):
        result = _run(session, "sleep 1 &")
        assert _pairs(records.for_command(1)) == (1, 1)
        assert result.status == 0
        assert not session.degraded
        result = _run(session, "sleep 3 &")
        assert result.snapshot.stopped_jobs == 0  # running, not stopped
        assert _run(session, "echo still here").text.endswith("still here\n")
        assert not session.degraded


# ---- (g) the v1 snapshot fields, the baseline and H ---------------------------------------


def test_snapshot_carries_v1_fields_and_baseline():
    with _session() as (session, records):
        baseline = session.baseline
        first = records.for_command(0)
        types = {line[:1] for line in first}
        assert {b"F", b"L", b"T", b"B", b"X", b"P", b"J", b"H", b"V", b"E"} <= types
        assert baseline.seq == 0
        assert baseline.extdebug == "shopt -u extdebug"
        assert baseline.path == os.environ["PATH"]
        assert baseline.stopped_jobs == 0
        result = _run(session, "true")
        assert session.baseline is baseline
        assert result.snapshot.hooks_sum == baseline.hooks_sum


@pytest.mark.parametrize("change", ["PS0='x'", "PROMPT_COMMAND+=(':')"], ids=["ps0", "pc-array"])
def test_changed_hooks_degrade(change):
    session_mod = _session_module()
    with _session() as (session, _):
        with pytest.raises(session_mod.SessionDegraded):
            _run(session, change)
        assert "H differs" in session.degraded_reason


def test_replaced_done_hook_cannot_hide_state():
    # A sourced script rewrites nl-shell's own hook so that `L` leaves out a new alias,
    # while PROMPT_COMMAND and PS0 keep their text. The session must either refuse the
    # redefinition (the alias then shows up) or degrade; it may never report a false `L`.
    session_mod = _session_module()
    attack = (
        "eval \"$(declare -f __nls_done | sed 's/builtin alias -p/builtin alias -p"
        " | grep -v evil_nls/')\"; alias evil_nls='rm -rf'"
    )
    with _session() as (session, _):
        try:
            _run(session, attack)
            snapshot = _run(session, "true").snapshot
        except session_mod.SessionDegraded:
            return
        assert any(a.startswith("alias evil_nls=") for a in snapshot.aliases)
        assert not session.degraded


def test_replaced_user_prompt_command_does_not_run():
    # `__nls_user_pc` is eval'd at every prompt and is not part of PROMPT_COMMAND's text.
    session_mod = _session_module()
    marker = os.path.join(os.environ["HOME"], "pwned")
    with _session() as (session, _):
        try:
            _run(session, "__nls_user_pc='touch ~/pwned'")
            _run(session, "true")  # the previous prompt's hooks have all run by now
        except session_mod.SessionDegraded:
            return
        assert not os.path.exists(marker)
        assert not session.degraded


def test_new_function_cannot_be_hidden_from_the_snapshot():
    # The reference hook sends `F` only when a cksum kept in a shell variable changed; a
    # command that sets that variable to the new list's cksum would hide a new function.
    attack = (
        "evil_nls_fn(){ :; }; __nls_fsum=$(builtin compgen -A function | command cksum)"
    )
    with _session() as (session, _):
        result = _run(session, attack)
        assert "evil_nls_fn" in result.snapshot.functions
        assert "evil_nls_fn" in _run(session, "true").snapshot.functions


def test_oversized_numeric_field_degrades():
    # Python's int() refuses strings of more than 4300 digits; such a record is malformed
    # and must degrade the session, not raise out of it.
    protocol = importlib.import_module("nl_shell.pty_protocol")
    tracker = protocol.ProtocolTracker()
    tracker.feed(b"D " + b"9" * 5000 + b" 0 0\n")
    assert tracker.degraded
    assert "malformed" in tracker.degraded_reason
    session_mod = _session_module()
    with _session() as (session, _):
        with pytest.raises(session_mod.SessionDegraded):
            _run(session, "printf 'D %s 0 0\\n' \"$(printf '9%.0s' {1..5000})\" >&3")
        assert session.degraded
        assert "malformed" in session.degraded_reason


def test_newline_in_path_cannot_forge_the_snapshot():
    # A PATH ending in `\nJ 0\nH <h>\nV <v>\nE` must not close the snapshot early with the
    # baseline's H and V (which would hide the LD_PRELOAD set in the same command).
    with _session() as (session, _):
        base = session.baseline
        injected = f"\nJ 0\nH {base.hooks_sum}\nV {base.vars_sum}\nE\nZ"
        command = (
            "export LD_PRELOAD=/nonexistent-nls.so; PATH=\"$PATH\"$'"
            + injected.replace("\n", "\\n")
            + "'"
        )
        result = _run(session, command)
        assert result.snapshot.vars_sum != base.vars_sum  # LD_PRELOAD is visible
        assert result.snapshot.path == base.path + injected  # P arrives whole
        assert not session.degraded
        assert _run(session, "echo still fine").text.endswith("still fine\n")


def _forged_snapshot(session, seq: int) -> list[str]:
    base = session.baseline
    return [
        f"D {seq} 0 0",
        "F " + " ".join(base.functions),
        "L x",
        "T x",
        "B x",
        "X shopt -u extdebug",
        "P /usr/bin",
        "J 0",
        f"H {base.hooks_sum}",
        f"V {base.vars_sum}",
        "E",
    ]


def test_record_after_the_end_of_a_snapshot_degrades():
    # A command writes a whole snapshot to fd 3 and one more record in the same write.
    # The record after E is out of order; run() must not return the forged result.
    session_mod = _session_module()
    with _session() as (session, _):
        records = _forged_snapshot(session, 1) + ["D 1 0 0"]
        command = "printf '%s\\n' " + " ".join(shlex.quote(r) for r in records) + " >&3"
        with pytest.raises(session_mod.SessionDegraded):
            _run(session, command)
        assert "out of order" in session.degraded_reason


def test_stray_records_degrade_before_the_next_command_is_sent(tmp_path):
    # Records that arrive after run() returned (here: the real D/snapshot that follow a
    # forged one) must degrade the session before the next command reaches bash.
    session_mod = _session_module()
    marker = tmp_path / "sent"
    with _session() as (session, _):
        records = _forged_snapshot(session, 1)
        command = (
            "printf '%s\\n' " + " ".join(shlex.quote(r) for r in records) + " >&3; sleep 0.5"
        )
        with contextlib.suppress(session_mod.SessionDegraded):
            _run(session, command)  # the forged result may come back: fd 3 is #12's
        time.sleep(1.0)  # the real D 1 and its snapshot are in the pipe now
        with pytest.raises(session_mod.SessionDegraded):
            _run(session, f"touch {marker}")
        time.sleep(0.5)  # bash would have run it by now
        assert not marker.exists()
        assert "out of order" in session.degraded_reason


# ---- (h) the user's ~/.bashrc ---------------------------------------------------------------


def test_bashrc_alias_and_prompt_command_are_kept():
    home = os.environ["HOME"]  # the suite's temporary HOME (tests/conftest.py)
    with open(os.path.join(home, ".bashrc"), "w", encoding="utf-8") as fh:
        fh.write("alias hello_nls='echo hi'\n")
        fh.write('PROMPT_COMMAND=\'echo "$__nls_seq" >> ~/pc.log\'\n')
    with _session() as (session, _):
        assert any(a.startswith("alias hello_nls=") for a in session.baseline.aliases)
        _run(session, "true")
        _run(session, "true")
        # The user's PROMPT_COMMAND runs after the E record, so give it a moment.
        log = os.path.join(home, "pc.log")
        deadline = time.monotonic() + RUN_TIMEOUT
        while True:
            with open(log, encoding="utf-8") as fh:
                seen = fh.read().split()
            if len(seen) >= 3 or time.monotonic() > deadline:
                break
            time.sleep(0.05)
        # It runs at every prompt, after nl-shell's hook advanced the sequence number.
        assert seen == ["0", "1", "2"]


def test_bashrc_cannot_turn_bracketed_paste_off():
    home = os.environ["HOME"]
    with open(os.path.join(home, ".bashrc"), "w", encoding="utf-8") as fh:
        fh.write("bind 'set enable-bracketed-paste off'\nset -o vi\n")
    with _session() as (session, records):
        result = _run(session, "echo 'a  b'\necho \"c\td\"")
        assert result.output == b"a  b\r\nc\td\r\n"
        assert _pairs(records.for_command(1)) == (1, 1)
        # Still on after ~/.bashrc: readline then always marks where it hands the line to
        # bash, which is where capture starts.
        assert _run(session, "bind -v | grep -c 'enable-bracketed-paste on'").text == "1\n"


# ---- (i) no history -------------------------------------------------------------------------


def test_session_writes_no_history():
    with _session() as (session, _):
        assert _run(session, 'printf %s "${HISTFILE-unset}"').text == "unset"
    assert not os.path.exists(os.path.join(os.environ["HOME"], ".bash_history"))


# ---- (j) control-channel wiring -------------------------------------------------------------


def test_fd3_is_a_fifo_not_the_pty():
    with _session() as (session, _):
        assert _run(session, "[ -p /dev/fd/3 ] && echo fifo").text == "fifo\n"
        assert _run(session, "[ -t 3 ] || echo not-a-tty").text == "not-a-tty\n"


def test_record_with_carriage_return_is_malformed():
    protocol = importlib.import_module("nl_shell.pty_protocol")
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_record(b"S 1\r")
    tracker = protocol.ProtocolTracker()
    tracker.feed(b"D 0 0 0\r\n")
    assert tracker.degraded
    assert "carriage return" in tracker.degraded_reason


# ---- (k) terminal ownership -----------------------------------------------------------------


def test_terminal_attributes_are_restored():
    with _session() as (session, _), _fake_terminal() as term:
        before = termios.tcgetattr(term.slave)
        result = _run(session, "echo hi", terminal=term.terminal())
        assert termios.tcgetattr(term.slave) == before
        assert result.text == "hi\n"


def test_window_size_follows_sigwinch():
    with _session() as (session, records), _fake_terminal(rows=24, cols=80) as term:

        def resize() -> None:
            termios.tcsetwinsize(term.master, (40, 100))
            os.kill(os.getpid(), signal.SIGWINCH)

        resizer = _after_start(records, 1, 0.3, resize)
        result = _run(session, "sleep 1; stty size", terminal=term.terminal())
        resizer.join(timeout=2)
        assert result.text == "40 100\n"


def _holds(obj, needle: bytes, seen: set[int]) -> bool:
    if id(obj) in seen:
        return False
    seen.add(id(obj))
    if isinstance(obj, (bytes, bytearray, memoryview)):
        return needle in bytes(obj)
    if isinstance(obj, str):
        return needle.decode() in obj
    if isinstance(obj, dict):
        return any(_holds(k, needle, seen) or _holds(v, needle, seen) for k, v in obj.items())
    if isinstance(obj, (list, tuple, set, frozenset)):
        return any(_holds(item, needle, seen) for item in obj)
    if isinstance(obj, type) or callable(obj) and not hasattr(obj, "__dict__"):
        return False
    attrs = getattr(obj, "__dict__", None)
    if isinstance(attrs, dict) and _holds(attrs, needle, seen):
        return True
    for slot in getattr(type(obj), "__slots__", ()):
        if _holds(getattr(obj, slot, None), needle, seen):
            return True
    return False


def test_forwarded_input_is_never_kept():
    sentinel = b"s3ntinel-PASSWORD-7c1"
    with _session() as (session, records), _fake_terminal() as term:
        before = termios.tcgetattr(term.slave)
        typist = _after_start(
            records, 1, 0.3, lambda: os.write(term.master, sentinel + b"\n\x04")
        )
        result = _run(session, "cat > /dev/null", terminal=term.terminal())
        typist.join(timeout=2)
        time.sleep(0.2)
        assert result.status == 0  # cat read the line and the EOF: input was forwarded
        assert result.input_forwarded
        assert sentinel in term.mirrored  # the PTY echoed it to the terminal
        assert _holds(term, sentinel, set())  # the scan below does find a copy that exists
        assert sentinel not in result.output
        assert not _holds(result, sentinel, set())
        assert not _holds(session, sentinel, set())
        assert termios.tcgetattr(term.slave) == before


# ---- captured output is bounded ---------------------------------------------------------------


def test_captured_output_is_bounded_and_keeps_the_tail():
    session_mod = _session_module()
    command = "head -c 1000000 /dev/zero | tr '\\0' x; echo; echo END_MARK"
    with _session(max_output=65536) as (session, _):
        result = _run(session, command)
        assert result.output_truncated
        assert len(result.output) <= 65536
        assert result.text.endswith("END_MARK\n")
        assert not _run(session, "echo small").output_truncated
    with _session() as (session, _):
        assert session.max_output == session_mod.MAX_OUTPUT


def test_output_before_the_line_is_accepted_is_bounded():
    # Without readline's "line accepted" switch, the bytes after `S` are kept as the
    # fallback; they are bounded the same way.
    session_mod = _session_module()
    splitter = session_mod._OutputSplitter(100)
    splitter.started()
    for _ in range(100):
        splitter.feed(b"y" * 1000)
    output = splitter.finish()
    assert len(output) <= 100
    assert splitter.capture.truncated

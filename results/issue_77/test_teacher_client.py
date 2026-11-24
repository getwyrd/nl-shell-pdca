"""The model client and `--dev-teacher` (#77).

Every test talks to an in-process fake OpenAI-compatible server (stdlib `http.server`) on
127.0.0.1 or on a Unix socket; nothing leaves the host and no model runs. The modules
#77 and #143 add are imported inside the tests, so with the production change reverted
each test fails on its own assertions instead of the file failing to import.
"""

from __future__ import annotations

import http.server
import io
import json
import shutil
import socket
import socketserver
import tempfile
import threading
import time
from pathlib import Path

import pytest

from nl_shell import cli
from nl_shell.repl import Repl

TARGET_TOML = """\
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
PROMPTS_YAML = """\
system: You propose one bash command.
examples:
  - request: show disk usage
    response: '{"kind": "command", "command": "df -h", "risk": "read-only"}'
request_template: "{state}{request}"
"""
VALID = '{"kind": "command", "command": "df -h", "risk": "read-only"}'
NO_USABLE = "No usable proposal came back from the model."
OSC52_STATUS = (
    b"HTTP/1.1 500 \x1b]52;c;ZWNobyBwd25lZA==\x07\x1b[2K\rnl> fake\r\n"
)
HIDDEN = ("\x1b", "\x07", "\r")
WAIT = 5  # upper bound for any wait on a fake server thread


# --- fake server -------------------------------------------------------------------


class Fake:
    """One fake endpoint: records every request and answers with ``behaviour``."""

    def __init__(self, server, address):
        self.server = server
        self.address = address
        self.requests: list[dict] = []
        self.behaviour = ok(VALID)
        self.stop = threading.Event()

    @property
    def url(self) -> str:
        host, port = self.address
        return f"http://{host}:{port}"


class Handler(http.server.BaseHTTPRequestHandler):
    timeout = WAIT  # a handler never waits on a client longer than this

    def do_POST(self):  # noqa: N802 (http.server naming)
        fake: Fake = self.server.fake
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        fake.requests.append(
            {
                "method": "POST",
                "path": self.path,
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "body": json.loads(body),
            }
        )
        try:
            fake.behaviour(self, fake)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):  # noqa: N802
        self.server.fake.requests.append({"method": "GET", "path": self.path})
        self.send_error(404)

    def log_message(self, *args):
        pass


class TCPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    block_on_close = False


class UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    block_on_close = False


def ok(content):
    def behaviour(handler, fake):
        _send(handler, 200, json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": content}}]}
        ).encode())
    return behaviour


def raw_body(data: bytes, status: int = 200):
    def behaviour(handler, fake):
        _send(handler, status, data)
    return behaviour


def queue(*contents):
    """Answer request n with ``contents[n]``."""
    pending = list(contents)

    def behaviour(handler, fake):
        ok(pending.pop(0))(handler, fake)
    return behaviour


def _send(handler, status, data):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


@pytest.fixture
def servers():
    """Start fake servers; every one is shut down and its socket dir removed after."""
    started: list[Fake] = []
    dirs: list[str] = []

    def tcp() -> Fake:
        server = TCPServer(("127.0.0.1", 0), Handler)
        return _start(server, server.server_address)

    def unix(path: str) -> Fake:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        server = UnixServer(path, Handler)
        return _start(server, path)

    def _start(server, address) -> Fake:
        fake = Fake(server, address)
        server.fake = fake
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.05}
        )
        thread.daemon = True
        thread.start()
        started.append(fake)
        return fake

    def runtime_dir() -> str:
        # Short: a Unix socket path must fit in about 107 bytes.
        path = tempfile.mkdtemp(prefix="nls-")
        dirs.append(path)
        return path

    yield type("Servers", (), {"tcp": staticmethod(tcp), "unix": staticmethod(unix),
                               "runtime_dir": staticmethod(runtime_dir)})
    for fake in started:
        fake.stop.set()
        fake.server.shutdown()
        fake.server.server_close()
    for path in dirs:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def default_socket(servers, monkeypatch):
    """XDG_RUNTIME_DIR in a short temp dir; returns the default model socket path."""
    run = servers.runtime_dir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", run)
    return f"{run}/nl-shell/model.sock"


def messages():
    from nl_shell.prompts import Message

    return [Message("system", "You propose."), Message("user", "show disk usage")]


def client_for(fake: Fake, **kwargs):
    from nl_shell import teacher_client

    if isinstance(fake.address, str):
        endpoint = teacher_client.Endpoint("unix", fake.address)
    else:
        endpoint = teacher_client.Endpoint("http", fake.url)
    return teacher_client.TeacherClient(endpoint, **kwargs)


def failure(client) -> str:
    from nl_shell import backend

    with pytest.raises(backend.BackendError) as exc:
        client.complete(messages())
    return exc.value.reason


def scripted(lines):
    pending = list(lines)

    def read(_prompt):
        if not pending:
            raise EOFError
        return pending.pop(0)
    return read


def load_prompts(tmp_path):
    from nl_shell import prompts

    folder = tmp_path / "target"
    (folder / "prompts").mkdir(parents=True)
    (folder / "prompts" / "prompts.yaml").write_text(PROMPTS_YAML, encoding="utf-8")
    return prompts.load(folder)


def run_cli(tmp_path, monkeypatch, argv=(), lines=(), config_text=None):
    """``cli.main`` with an injected matching target, a scripted REPL and a StringIO."""
    root = tmp_path / "targets"
    folder = root / "testos-1"
    (folder / "prompts").mkdir(parents=True)
    (folder / "target.toml").write_text(TARGET_TOML, encoding="utf-8")
    (folder / "prompts" / "prompts.yaml").write_text(PROMPTS_YAML, encoding="utf-8")
    release = tmp_path / "os-release"
    release.write_text('ID=testos\nVERSION_ID="1"\n', encoding="utf-8")
    if config_text is not None:
        config_dir = Path(tmp_path / "home-config" / "nl-shell")
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").write_text(config_text, encoding="utf-8")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(config_dir.parent))
    out = io.StringIO()
    seen: dict = {}

    def interactive(cls, status_lines=(), **kwargs):
        seen["status_lines"] = [line() for line in status_lines]
        seen["kwargs"] = kwargs
        return cls(scripted(lines), out, status_lines, **kwargs)

    monkeypatch.setattr(cli.Repl, "interactive", classmethod(interactive))
    rc = cli.main(list(argv), targets_root=root, os_release_paths=[release])
    return rc, out.getvalue(), seen


# --- (a) request shape -------------------------------------------------------------


def test_request_shape(servers, default_socket):
    from nl_shell import proposal

    fake = servers.unix(default_socket)
    sent = messages()
    assert client_for(fake).complete(sent) == VALID
    assert len(fake.requests) == 1
    request = fake.requests[0]
    assert (request["method"], request["path"]) == ("POST", "/v1/chat/completions")
    body = request["body"]
    assert body["messages"] == [{"role": m.role, "content": m.content} for m in sent]
    response_format = body["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["schema"] == proposal.SCHEMA
    assert "authorization" not in request["headers"]
    assert "model" not in body


@pytest.mark.parametrize("config_text, model", [
    ('teacher_model = "m1"\n', "m1"),
    ("", None),
])
def test_teacher_model_from_config(tmp_path, monkeypatch, servers, default_socket,
                                   config_text, model):
    fake = servers.unix(default_socket)
    rc, out, _ = run_cli(tmp_path, monkeypatch, lines=["show disk usage"],
                         config_text=config_text)
    assert rc == 0
    assert "Proposed command (risk: read-only" in out
    assert len(fake.requests) == 1
    assert fake.requests[0]["body"].get("model") == model
    assert ("model" in fake.requests[0]["body"]) == (model is not None)


# --- (b) strict transport handling -------------------------------------------------


def test_http_error_status_is_rejected(servers):
    fake = servers.tcp()
    fake.behaviour = lambda handler, _fake: handler.send_error(503, "busy")
    reason = failure(client_for(fake))
    assert "503" in reason
    assert len(fake.requests) == 1


def test_redirect_is_not_followed(servers):
    fake, other = servers.tcp(), servers.tcp()

    def redirect(handler, _fake):
        handler.send_response(307)
        handler.send_header("Location", other.url + "/v1/chat/completions")
        handler.send_header("Content-Length", "0")
        handler.end_headers()

    fake.behaviour = redirect
    reason = failure(client_for(fake))
    assert "redirect" in reason
    assert len(fake.requests) == 1
    assert other.requests == []


@pytest.mark.parametrize("data", [
    b"not json",
    b'{"choices": []}',
    b"{}",
    b'{"choices": [{"message": {"content": null}}]}',
    b'{"choices": [{"message": {"content": {"kind": "command"}}}]}',
    b"[1, 2]",
])
def test_bad_body_is_rejected(servers, data):
    fake = servers.tcp()
    fake.behaviour = raw_body(data)
    reason = failure(client_for(fake))
    assert "JSON" in reason or "content" in reason
    assert len(fake.requests) == 1


def test_oversize_body_stops_reading_at_the_cap(servers):
    fake = servers.tcp()
    written = []

    def endless(handler, fake):
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        while not fake.stop.is_set() and sum(written) < 64 * 1024 * 1024:
            handler.wfile.write(b" " * 4096)
            written.append(4096)

    fake.behaviour = endless
    start = time.monotonic()
    reason = failure(client_for(fake, timeout_s=WAIT))
    assert time.monotonic() - start < WAIT
    assert "larger than" in reason
    assert len(fake.requests) == 1


def test_size_cap_override(servers):
    fake = servers.tcp()
    reason = failure(client_for(fake, max_response_bytes=10))
    assert "larger than 10 bytes" in reason


def test_server_that_never_answers_times_out(servers):
    fake = servers.tcp()
    fake.behaviour = lambda _handler, fake: fake.stop.wait(2)
    start = time.monotonic()
    reason = failure(client_for(fake, timeout_s=0.5))
    assert time.monotonic() - start < 2
    assert "within 0.5 s" in reason
    assert len(fake.requests) == 1


def slow_drip(handler, fake):
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", "100")
    handler.end_headers()
    handler.wfile.flush()
    for _ in range(100):
        if fake.stop.wait(0.2):
            return
        handler.wfile.write(b" ")
        handler.wfile.flush()


def test_slow_drip_body_hits_the_total_deadline(servers):
    fake = servers.tcp()
    fake.behaviour = slow_drip
    start = time.monotonic()
    reason = failure(client_for(fake, timeout_s=0.5))
    assert time.monotonic() - start < 2
    assert "within 0.5 s" in reason


def test_model_timeout_from_config(tmp_path):
    from nl_shell import config

    path = tmp_path / "config.toml"
    path.write_text('target = "x"\n', encoding="utf-8")
    assert config.load(path).model_timeout_s == 10
    path.write_text("[model]\ntimeout_s = 0.5\n", encoding="utf-8")
    assert config.load(path).model_timeout_s == 0.5
    path.write_text("[model]\ntimeout_s = 3\n", encoding="utf-8")
    assert config.load(path).model_timeout_s == 3
    path.write_text("[model]\ntimeout_s = 3600\n", encoding="utf-8")
    assert config.load(path).model_timeout_s == 3600
    # 1e10 once crashed the REPL with an OverflowError from the deadline timer.
    for bad in ('"10"', "true", "0", "-1", "nan", "inf", "[1]", "3600.5", "1e10"):
        path.write_text(f"[model]\ntimeout_s = {bad}\n", encoding="utf-8")
        with pytest.raises(config.ConfigError):
            config.load(path)


def test_huge_timeout_is_refused_by_the_client():
    from nl_shell import teacher_client

    endpoint = teacher_client.Endpoint("http", "http://127.0.0.1:9")
    for bad in (1e10, 0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            teacher_client.TeacherClient(endpoint, timeout_s=bad)


def test_cli_refuses_a_huge_timeout(tmp_path, monkeypatch, capsys, default_socket):
    rc, _, seen = run_cli(tmp_path, monkeypatch, lines=["show disk usage"],
                          config_text="[model]\ntimeout_s = 1e10\n")
    assert rc == 1
    assert "timeout_s" in capsys.readouterr().err
    assert seen == {}


def chunk_size_drip(handler, fake):
    """Chunked, then the chunk-size line one byte every 0.2 s, never ending it."""
    handler.wfile.write(
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Transfer-Encoding: chunked\r\n"
        b"Connection: close\r\n\r\n"
    )
    handler.wfile.flush()
    for _ in range(100):
        if fake.stop.wait(0.2):
            return
        handler.wfile.write(b"0")
        handler.wfile.flush()


@pytest.mark.parametrize("where", ["tcp", "unix"])
def test_chunk_size_drip_after_connection_close_hits_the_deadline(
    servers, default_socket, where
):
    # With `Connection: close` http.client hands the socket to the response and drops
    # it from the connection; the deadline must still cut the read.
    fake = servers.tcp() if where == "tcp" else servers.unix(default_socket)
    fake.behaviour = chunk_size_drip
    start = time.monotonic()
    reason = failure(client_for(fake, timeout_s=0.5))
    assert time.monotonic() - start < 2
    assert "within 0.5 s" in reason


def test_dns_lookup_is_inside_the_deadline(monkeypatch):
    from nl_shell import teacher_client

    released = threading.Event()

    def slow_lookup(*args, **kwargs):
        released.wait(3)
        raise socket.gaierror(socket.EAI_NONAME, "no such host")

    monkeypatch.setattr(socket, "getaddrinfo", slow_lookup)
    endpoint = teacher_client.Endpoint("http", "http://teacher.test:8080")
    start = time.monotonic()
    try:
        reason = failure(teacher_client.TeacherClient(endpoint, timeout_s=0.5))
    finally:
        released.set()
    assert time.monotonic() - start < 2
    assert "within 0.5 s" in reason


def test_connect_attempts_share_the_deadline(monkeypatch):
    from nl_shell import teacher_client

    # A listener whose backlog is full: a further connect hangs (SYN dropped).
    listener = socket.socket()
    held = []
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(0)
        address = listener.getsockname()
        first = socket.create_connection(address, timeout=WAIT)
        held.append(first)
        lookups = []

        def three_addresses(host, port, *args, **kwargs):
            lookups.append(host)
            info = (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", address)
            return [info, info, info]

        monkeypatch.setattr(socket, "getaddrinfo", three_addresses)
        endpoint = teacher_client.Endpoint("http", f"http://teacher.test:{address[1]}")
        start = time.monotonic()
        reason = failure(teacher_client.TeacherClient(endpoint, timeout_s=0.5))
        elapsed = time.monotonic() - start
    finally:
        for sock in held:
            sock.close()
        listener.close()
    assert lookups == ["teacher.test"]
    # Each of the three attempts given the full 0.5 s would take 1.5 s.
    assert elapsed < 1.2
    assert "within 0.5 s" in reason


def test_trailing_v1_in_the_url_is_not_doubled(servers):
    from nl_shell import teacher_client

    fake = servers.tcp()
    for url in (fake.url + "/v1", fake.url + "/v1/"):
        client = teacher_client.TeacherClient(teacher_client.Endpoint("http", url))
        assert client.complete(messages()) == VALID
    assert [r["path"] for r in fake.requests] == ["/v1/chat/completions"] * 2


def test_cli_uses_model_timeout(tmp_path, monkeypatch, servers, default_socket):
    fake = servers.unix(default_socket)
    fake.behaviour = slow_drip
    start = time.monotonic()
    rc, out, _ = run_cli(tmp_path, monkeypatch, lines=["show disk usage"],
                         config_text="[model]\ntimeout_s = 0.5\n")
    assert time.monotonic() - start < 2
    assert rc == 0
    assert "The model server could not be used: " in out
    assert len(fake.requests) == 1


def test_https_to_plain_http_server_is_a_tls_error(servers):
    from nl_shell import teacher_client

    fake = servers.tcp()
    port = fake.address[1]
    endpoint = teacher_client.Endpoint("https", f"https://127.0.0.1:{port}")
    reason = failure(teacher_client.TeacherClient(endpoint, timeout_s=WAIT))
    assert "TLS" in reason
    assert fake.requests == []


# --- (c) endpoint rules -------------------------------------------------------------


def test_select_endpoint_rules():
    from nl_shell.teacher_client import Endpoint, EndpointError, select_endpoint

    run = "/run/user/1000"
    sock = "/run/user/1000/nl-shell/model.sock"
    lan = "http://192.168.1.20:8080"
    loop = "http://127.0.0.1:8080"

    assert select_endpoint(None, None, run) == (Endpoint("unix", sock), [])
    endpoint, notes = select_endpoint(None, loop, run)
    assert endpoint == Endpoint("unix", sock)
    assert len(notes) == 1 and "--dev-teacher" in notes[0]
    assert select_endpoint(True, loop, run) == (Endpoint("http", loop), [])
    assert select_endpoint("http://localhost:9", loop, run) == (
        Endpoint("http", "http://localhost:9"), [])
    assert select_endpoint("https://teacher.lan", None, run) == (
        Endpoint("https", "https://teacher.lan"), [])
    for remote in (lan, "http://teacher.lan", "http://[fe80::1]:8080"):
        endpoint, notes = select_endpoint(remote, None, run)
        assert endpoint == Endpoint("http", remote)
        assert len(notes) == 1 and "SSH tunnel" in notes[0]
    for local in ("http://127.9.9.9", "http://[::1]:8080", "http://LOCALHOST"):
        assert select_endpoint(local, None, run)[1] == []
    for no_runtime in (None, "", "relative/dir"):
        assert select_endpoint(None, None, no_runtime)[0] == Endpoint("unix", None)
    for bad in ("ftp://host", "http://user:pw@host", "http://user@host", "http://",
                "http://host?x=1"):
        with pytest.raises(EndpointError):
            select_endpoint(bad, None, run)


def test_default_socket_without_flag_or_url(tmp_path, monkeypatch, servers,
                                            default_socket):
    fake = servers.unix(default_socket)
    rc, out, _ = run_cli(tmp_path, monkeypatch, lines=["show disk usage"])
    assert rc == 0
    assert "Proposed command (risk: read-only, 1 line):" in out
    assert len(fake.requests) == 1


def test_config_url_without_flag_is_refused(tmp_path, monkeypatch, capsys, servers,
                                            default_socket):
    local, teacher = servers.unix(default_socket), servers.tcp()
    rc, out, _ = run_cli(tmp_path, monkeypatch, lines=["show disk usage"],
                         config_text=f'teacher_url = "{teacher.url}"\n')
    assert rc == 0
    assert "teacher_url" in capsys.readouterr().err
    assert "Proposed command" in out
    assert len(local.requests) == 1
    assert teacher.requests == []


def test_config_url_with_bare_flag_is_used(tmp_path, monkeypatch, servers,
                                           default_socket):
    local, teacher = servers.unix(default_socket), servers.tcp()
    rc, out, _ = run_cli(tmp_path, monkeypatch, argv=["--dev-teacher"],
                         lines=["show disk usage"],
                         config_text=f'teacher_url = "{teacher.url}"\n')
    assert rc == 0
    assert "Proposed command" in out
    assert len(teacher.requests) == 1
    assert local.requests == []


def test_flag_url_wins_over_config_url(tmp_path, monkeypatch, servers, default_socket):
    configured, given = servers.tcp(), servers.tcp()
    rc, _, _ = run_cli(tmp_path, monkeypatch, argv=["--dev-teacher", given.url],
                       lines=["show disk usage"],
                       config_text=f'teacher_url = "{configured.url}"\n')
    assert rc == 0
    assert len(given.requests) == 1
    assert configured.requests == []


def test_non_loopback_http_warns_on_stderr(tmp_path, monkeypatch, capsys,
                                           default_socket):
    # No request line, so nothing connects to the (unroutable) address.
    rc, _, _ = run_cli(tmp_path, monkeypatch,
                       argv=["--dev-teacher", "http://192.0.2.1:8080"])
    assert rc == 0
    assert "SSH tunnel" in capsys.readouterr().err


# --- (d) through Repl ---------------------------------------------------------------


def test_repl_shows_the_proposal(tmp_path, servers, default_socket):
    fake = servers.unix(default_socket)
    out = io.StringIO()
    repl = Repl(scripted(["show disk usage"]), out, backend=client_for(fake),
                prompts=load_prompts(tmp_path))
    assert repl.run() == 0
    assert out.getvalue().startswith(
        "Proposed command (risk: read-only, 1 line):\n  | df -h\n"
    )


REJECTED = [
    '{"kind": "command", "command": "ls", "risk": "read-only", "extra": 1}',
    '{"kind": "command", "command": "ls"}',
    '{"kind": "command", "command": "ls", "risk": "read-only", '
    '"reason": "unclear-request"}',
    json.dumps({"kind": "command", "command": "a" * 2001, "risk": "read-only"}),
    '{"kind": "command", "command": "ls", ',
    '[{"kind": "command", "command": "ls", "risk": "read-only"}]',
]


def test_repl_rejects_bad_proposals_and_keeps_reading(
    tmp_path, servers, default_socket
):
    fake = servers.unix(default_socket)
    fake.behaviour = queue(*REJECTED, VALID)
    out = io.StringIO()
    lines = [f"request {n}" for n in range(len(REJECTED) + 1)]
    repl = Repl(scripted(lines), out, backend=client_for(fake),
                prompts=load_prompts(tmp_path))
    assert repl.run() == 0
    replies = out.getvalue().splitlines()
    assert replies[: len(REJECTED)] == [NO_USABLE] * len(REJECTED)
    assert replies[len(REJECTED)].startswith("Proposed command (risk: read-only")
    assert len(fake.requests) == len(REJECTED) + 1


def test_repl_with_no_model_server(tmp_path, default_socket):
    from nl_shell import teacher_client

    endpoint = teacher_client.Endpoint("unix", default_socket)
    out = io.StringIO()
    repl = Repl(scripted(["show disk usage", "list files here"]), out,
                backend=teacher_client.TeacherClient(endpoint),
                prompts=load_prompts(tmp_path))
    assert repl.run() == 0
    expected = f"The model server isn't running (no answer at {default_socket})."
    assert out.getvalue().splitlines() == [expected, expected]


def test_repl_with_no_runtime_dir(tmp_path, monkeypatch):
    from nl_shell import teacher_client

    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    endpoint, _ = teacher_client.select_endpoint(None, None, None)
    out = io.StringIO()
    repl = Repl(scripted(["show disk usage"]), out,
                backend=teacher_client.TeacherClient(endpoint),
                prompts=load_prompts(tmp_path))
    assert repl.run() == 0
    assert out.getvalue().startswith("The model server isn't running (no answer at ")


def control_status(handler, _fake):
    body = b"\x1b[31merror\x07\r body"
    handler.wfile.write(
        OSC52_STATUS
        + b"Content-Type: text/plain\r\n"
        + f"Content-Length: {len(body)}\r\n".encode()
        + b"Connection: close\r\n\r\n"
        + body
    )


def test_server_text_is_escaped(tmp_path, servers, default_socket):
    fake = servers.unix(default_socket)
    fake.behaviour = control_status
    reason = failure(client_for(fake))
    for char in HIDDEN:
        assert char not in reason
    assert "500" in reason

    out = io.StringIO()
    repl = Repl(scripted(["show disk usage", "list files"]), out,
                backend=client_for(fake), prompts=load_prompts(tmp_path))
    assert repl.run() == 0
    text = out.getvalue()
    for char in HIDDEN:
        assert char not in text
    lines = text.splitlines()
    assert len(lines) == 2  # one reply per request: the REPL kept reading
    assert lines[0].startswith("The model server could not be used: HTTP status 500 ")


# --- (e) :status --------------------------------------------------------------------


def test_status_names_endpoint_and_backend(tmp_path, monkeypatch, default_socket):
    from nl_shell import teacher_client

    _, _, seen = run_cli(tmp_path, monkeypatch)
    assert seen["status_lines"][-2:] == [
        f"model endpoint: {default_socket}",
        f"model backend: {teacher_client.TeacherClient.kind}",
    ]
    _, _, seen = run_cli(tmp_path / "flag", monkeypatch,
                         argv=["--dev-teacher", "http://127.0.0.1:9"])
    assert seen["status_lines"][-2] == "model endpoint: http://127.0.0.1:9"


# --- (f) no TCP on the default path -------------------------------------------------


def test_default_path_opens_no_tcp(tmp_path, monkeypatch, servers, default_socket):
    local, teacher = servers.unix(default_socket), servers.tcp()
    calls = []
    connect = socket.socket.connect
    create_connection = socket.create_connection

    def record_connect(self, address):
        calls.append((self.family, address))
        return connect(self, address)

    def record_create_connection(address, *args, **kwargs):
        calls.append((socket.AF_INET, address))
        return create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", record_connect)
    monkeypatch.setattr(socket, "create_connection", record_create_connection)
    rc, out, _ = run_cli(tmp_path, monkeypatch, lines=["show disk usage"],
                         config_text=f'teacher_url = "{teacher.url}"\n')
    assert rc == 0
    tcp = [c for c in calls if c[0] in (socket.AF_INET, socket.AF_INET6)]
    unix = [c for c in calls if c[0] == socket.AF_UNIX]
    assert tcp == []
    assert unix == [(socket.AF_UNIX, default_socket)]
    assert teacher.requests == []
    assert len(local.requests) == 1
    assert "Proposed command" in out

"""Prompts YAML, model input, the recording stub backend and the proposal parser (#16).

Natural-language input and ``@request`` go through prompts -> backend -> ``proposal/v1``
parser, and ``:context`` prints the exact model input of the last request. Every case drives
the real ``Repl`` (or the real ``cli.main``) with the recording stub as the backend.

The modules this issue adds are imported inside the tests, never at module level, so the
file still loads (and fails) on a tree without them. Reply texts are pinned as literals.
"""

import io
import json
import os
from pathlib import Path

import pytest

from nl_shell.repl import Repl

REPO = Path(__file__).resolve().parents[1]

NO_BACKEND_NATURAL_LANGUAGE = (
    "That looks like a natural-language request, but no model backend is configured: "
    "the model client arrives in M0.8 (#77)."
)
NO_BACKEND_PROPOSE = (
    "That is a one-command request (@), but no model backend is configured: "
    "the model client arrives in M0.8 (#77)."
)
NO_CONTEXT = "No model input yet: :context shows the model input of the last request."
NO_USABLE = "No usable proposal came back from the model."
NOT_RUN = "Not run: the policy gate arrives in M0.4."

SYSTEM_TEXT = "You propose one bash command.\nAnswer with JSON only."
PROMPTS_YAML = """\
system: |-
  You propose one bash command.
  Answer with JSON only.
examples:
  - request: list files
    response:
      kind: command
      command: ls -la
      risk: read-only
  - request: do the thing
    response:
      kind: clarify
      reason: unclear-request
request_template: "{state}Request: {request}"
"""
EXAMPLE_MESSAGES = [
    ("user", "Request: list files"),
    ("assistant", '{"kind": "command", "command": "ls -la", "risk": "read-only"}'),
    ("user", "Request: do the thing"),
    ("assistant", '{"kind": "clarify", "reason": "unclear-request"}'),
]

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

COMMAND_OK = '{"kind": "command", "command": "df -h", "risk": "read-only"}'

# The hidden characters (Scope 5 / criterion e), written out by the test itself.
BIDI = {0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}


def escape(text):
    """The documented escaping: hidden characters as \\xHH or \\uHHHH; LF/TAB as-is."""
    out = []
    for ch in text:
        cp = ord(ch)
        if ch in "\n\t":
            out.append(ch)
        elif cp < 0x20 or cp == 0x7F or 0x80 <= cp <= 0x9F or cp in BIDI:
            out.append(f"\\x{cp:02x}" if cp <= 0xFF else f"\\u{cp:04x}")
        else:
            out.append(ch)
    return "".join(out)


def context_form(messages):
    """The documented :context text form, rebuilt here from the recorded message list."""
    return escape("\n".join(f"--- {m.role} ---\n{m.content}" for m in messages))


def scripted(*lines):
    it = iter(lines)

    def read(_prompt):
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None

    return read


@pytest.fixture(autouse=True)
def empty_path(tmp_path, monkeypatch):
    """No executables on $PATH, so `show ...` always routes as natural language."""
    bin_dir = tmp_path / "empty-bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir))


@pytest.fixture
def target_folder(tmp_path):
    """A target folder whose prompts/prompts.yaml is PROMPTS_YAML."""
    folder = tmp_path / "targets" / "testos-1"
    (folder / "prompts").mkdir(parents=True)
    (folder / "target.toml").write_text(TARGET_TOML, encoding="utf-8")
    (folder / "prompts" / "prompts.yaml").write_text(PROMPTS_YAML, encoding="utf-8")
    return folder


@pytest.fixture
def user_prompts():
    """The user's prompts.yaml under the suite's temporary XDG_CONFIG_HOME (conftest)."""
    path = Path(os.environ["XDG_CONFIG_HOME"]) / "nl-shell" / "prompts.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def session(target_folder, *lines, responses=()):
    """Run a Repl with the stub backend and the prompts loaded from ``target_folder``."""
    from nl_shell import prompts
    from nl_shell.backend import RecordingStub

    stub = RecordingStub(responses)
    loaded = prompts.load(target_folder)
    out = io.StringIO()
    assert Repl(scripted(*lines), out, backend=stub, prompts=loaded).run() == 0
    return stub, out.getvalue()


def reply_for(target_folder, raw, line="show disk usage"):
    """The REPL's reply when the stub's raw response is ``raw``."""
    _stub, out = session(target_folder, line, responses=[raw])
    return out


def assert_order(messages, request):
    """System first, the examples in file order, the user message last."""
    assert [(m.role, m.content) for m in messages[:1]] == [("system", SYSTEM_TEXT)]
    assert [(m.role, m.content) for m in messages[1:-1]] == EXAMPLE_MESSAGES
    assert messages[-1].role == "user"
    assert messages[-1].content.endswith(request)


# (a) :context prints the exact model input ----------------------------------------------


@pytest.mark.parametrize(
    ("line", "request_text"),
    [("show disk usage", "show disk usage"), ("@show disk usage", "show disk usage")],
    ids=["natural-language", "at-request"],
)
def test_context_prints_the_model_input_of_the_last_request(
    target_folder, line, request_text
):
    stub, out = session(target_folder, line, ":context", responses=[COMMAND_OK])
    assert len(stub.inputs) == 1
    sent = stub.inputs[0]
    assert_order(sent, request_text)
    assert sent[-1].content == f"Request: {request_text}"
    proposal_reply = f"Proposed command (risk: read-only):\ndf -h\n{NOT_RUN}\n"
    assert out == proposal_reply + context_form(sent) + "\n"


def test_context_before_any_request(target_folder):
    _stub, out = session(target_folder, ":context")
    assert out == NO_CONTEXT + "\n"
    out_without_backend = io.StringIO()
    assert Repl(scripted(":context"), out_without_backend).run() == 0
    assert out_without_backend.getvalue() == NO_CONTEXT + "\n"


def test_repl_without_a_backend_says_so():
    out = io.StringIO()
    assert Repl(scripted("show disk usage", "@show disk usage", ":context"), out).run() == 0
    assert out.getvalue() == (
        f"{NO_BACKEND_NATURAL_LANGUAGE}\n{NO_BACKEND_PROPOSE}\n{NO_CONTEXT}\n"
    )


def test_default_target_prompts_load_and_build_the_model_input():
    """The shipped default layer, found through the target loader, is valid."""
    from nl_shell import prompts, proposal, targets
    from nl_shell.backend import RecordingStub

    target = targets.load("ubuntu-26.04", targets.TARGETS_ROOT)
    loaded = prompts.load(target.folder)
    assert loaded.files == (REPO / "targets" / "ubuntu-26.04" / "prompts" / "prompts.yaml",)
    stub = RecordingStub([COMMAND_OK])
    out = io.StringIO()
    repl = Repl(scripted("show disk usage", ":context"), out, backend=stub, prompts=loaded)
    assert repl.run() == 0
    sent = stub.inputs[0]
    assert sent[0].role == "system" and sent[0].content == loaded.system
    assert [m.role for m in sent[1:-1]] == ["user", "assistant"] * len(loaded.examples)
    for message in sent[2:-1:2]:
        assert not isinstance(proposal.parse(message.content), proposal.Rejected)
    assert sent[-1].role == "user" and sent[-1].content.endswith("show disk usage")
    assert out.getvalue().endswith(context_form(sent) + "\n")


# (b) the stub records every input, in order; ESC in a request ---------------------------


def test_stub_records_one_input_per_request_in_order(target_folder):
    stub, _out = session(
        target_folder,
        "show disk usage",
        "@list open ports",
        "tell me the uptime",
        responses=[COMMAND_OK] * 3,
    )
    assert isinstance(stub.inputs, list)
    assert [m[-1].content for m in stub.inputs] == [
        "Request: show disk usage",
        "Request: list open ports",
        "Request: tell me the uptime",
    ]
    for sent in stub.inputs:
        assert_order(sent, sent[-1].content[len("Request: "):])


def test_escape_in_a_request_is_sent_raw_and_shown_escaped(target_folder):
    stub, out = session(
        target_folder, "show \x1b[2J disk", ":context", responses=[COMMAND_OK]
    )
    sent = stub.inputs[0]
    assert sent[-1].content == "Request: show \x1b[2J disk"
    context = out.split(NOT_RUN + "\n", 1)[1]
    assert "\x1b" not in out
    assert context.endswith("--- user ---\nRequest: show \\x1b[2J disk\n")
    assert context == context_form(sent) + "\n"


def test_bidi_and_c1_in_a_request_are_shown_escaped(target_folder):
    stub, out = session(
        target_folder, "show ‮disk\u0085 usage", ":context", responses=[COMMAND_OK]
    )
    assert stub.inputs[0][-1].content == "Request: show ‮disk\u0085 usage"
    assert out.endswith("--- user ---\nRequest: show \\u202edisk\\x85 usage\n")


# (c) the user's prompts.yaml; malformed files refuse start-up ---------------------------


class Started:
    def __init__(self):
        self.repls = 0
        self.stub = None
        self.status_lines = None


@pytest.fixture
def start(target_folder, tmp_path, monkeypatch, capsys):
    """Run the real ``cli.main`` against ``target_folder``'s root with a matching
    os-release (as #92's tests do); the REPL gets the stub and reads ``lines``."""
    from nl_shell import cli
    from nl_shell.backend import RecordingStub

    release = tmp_path / "os-release"
    release.write_text('ID=testos\nVERSION_ID="1"\n', encoding="utf-8")

    def run(*lines, responses=()):
        started = Started()
        out = io.StringIO()

        def interactive(cls, status_lines=(), prompts=None):
            started.repls += 1
            started.stub = RecordingStub(responses)
            started.status_lines = [line() for line in status_lines]
            return Repl(
                scripted(*lines), out, status_lines, backend=started.stub, prompts=prompts
            )

        monkeypatch.setattr(Repl, "interactive", classmethod(interactive))
        code = cli.main(
            [], targets_root=target_folder.parent, os_release_paths=[release]
        )
        err = capsys.readouterr().err
        assert "Traceback" not in err
        return code, out.getvalue(), err, started

    return run


def test_user_prompts_override_the_system_prompt(start, user_prompts):
    user_prompts.write_text("system: You are the user's own prompt.\n", encoding="utf-8")
    code, out, err, started = start("show disk usage", ":context", responses=[COMMAND_OK])
    assert (code, err) == (0, "")
    sent = started.stub.inputs[0]
    assert sent[0].role == "system"
    assert sent[0].content == "You are the user's own prompt."
    # The other keys still come from the default layer, key by key.
    assert [(m.role, m.content) for m in sent[1:-1]] == EXAMPLE_MESSAGES
    assert sent[-1].content == "Request: show disk usage"
    assert "--- system ---\nYou are the user's own prompt.\n--- user ---" in out
    assert out.endswith(context_form(sent) + "\n")


@pytest.mark.parametrize(
    "text",
    [
        "system: [unclosed\n",
        "- just\n- a list\n",
        "system: 42\n",
        "system: fine\ntemperature: 0.2\n",
        '!!python/object/apply:os.system ["touch {pwned}"]\n',
    ],
    ids=["invalid-yaml", "not-a-mapping", "wrong-type", "unknown-key", "python-tag"],
)
def test_malformed_user_prompts_refuse_start_up(
    start, user_prompts, tmp_path, monkeypatch, text
):
    # A real $PATH here, so an unsafe loader running the tag's `touch` would create the
    # file (the autouse empty_path would hide that). No line is routed in this test.
    monkeypatch.setenv("PATH", os.defpath)
    pwned = tmp_path / "pwned"
    user_prompts.write_text(text.replace("{pwned}", str(pwned)), encoding="utf-8")
    code, out, err, started = start("show disk usage", responses=[COMMAND_OK])
    assert code != 0
    assert started.repls == 0  # refused before the REPL read any line
    assert out == ""
    assert str(user_prompts) in err
    assert not pwned.exists()


@pytest.mark.parametrize(
    "text",
    [
        "examples: not-a-list\n",
        "request_template: 'Request: {request} please'\n",
        "examples:\n  - request: x\n    response: {kind: command, command: ls}\n",
        "system: a\nsystem: b\n",
    ],
    ids=["examples-not-a-list", "template-not-ending-in-request", "invalid-example",
         "duplicate-key"],
)
def test_other_invalid_user_prompts_refuse_start_up(start, user_prompts, text):
    user_prompts.write_text(text, encoding="utf-8")
    code, _out, err, started = start()
    assert code != 0
    assert started.repls == 0
    assert str(user_prompts) in err


# (d) proposal/v1 §Conformance ----------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (COMMAND_OK, f"Proposed command (risk: read-only):\ndf -h\n{NOT_RUN}"),
        (
            '{"kind": "command", "command": "rm -rf ~/build", "risk": "destructive"}',
            f"Proposed command (risk: destructive):\nrm -rf ~/build\n{NOT_RUN}",
        ),
        (
            '{"kind": "clarify", "reason": "unclear-request"}',
            "The model needs more detail before it can propose a command: "
            "the request is unclear. Please say more.",
        ),
        (
            '{"kind": "clarify", "reason": "missing-information"}',
            "The model needs more detail before it can propose a command: "
            "some information is missing. Please say more.",
        ),
        (
            '{"kind": "refuse", "reason": "not-a-shell-task"}',
            "The model declined to propose a command: it is not a shell task.",
        ),
        (
            '{"kind": "refuse", "reason": "unsafe-request"}',
            "The model declined to propose a command: the request is unsafe.",
        ),
    ],
    ids=["command", "command-destructive", "clarify", "clarify-missing", "refuse",
         "refuse-unsafe"],
)
def test_valid_shapes_are_accepted(target_folder, raw, expected):
    assert reply_for(target_folder, raw) == expected + "\n"


def test_parser_returns_typed_values():
    from nl_shell import proposal

    assert proposal.parse(COMMAND_OK) == proposal.CommandProposal("df -h", "read-only")
    assert proposal.parse('{"kind": "clarify", "reason": "unclear-request"}') == (
        proposal.Decline("clarify", "unclear-request")
    )
    assert proposal.parse('{"kind": "refuse", "reason": "unsafe-request"}') == (
        proposal.Decline("refuse", "unsafe-request")
    )
    assert isinstance(proposal.parse("[]"), proposal.Rejected)


def test_command_of_exactly_2000_code_points_is_accepted(target_folder):
    command = "é" * 2000  # 2000 code points, 4000 UTF-8 bytes
    raw = json.dumps({"kind": "command", "command": command, "risk": "read-only"})
    assert reply_for(target_folder, raw) == (
        f"Proposed command (risk: read-only):\n{command}\n{NOT_RUN}\n"
    )


@pytest.mark.parametrize(
    "raw",
    [
        '{"kind": "command", "command": "df -h", "risk": "read-only", "why": "x"}',
        '{"kind": "refuse", "reason": "unsafe-request", "explanation": "no"}',
        '{"kind": "command", "command": "df -h"}',
        '{"kind": "command", "command": "df -h", "risk": "read-only", '
        '"reason": "unclear-request"}',
        '{"kind": "clarify", "command": "df -h", "reason": "unclear-request"}',
        json.dumps({"kind": "command", "command": "x" * 2001, "risk": "read-only"}),
        '{"kind": "command", "command": "df -h", "risk": "read-only"',
        "Sure! Here is the command: df -h",
        "",
        '[{"kind": "command", "command": "df -h", "risk": "read-only"}]',
        "[]",
        '{"command": "df -h", "risk": "read-only"}',
        '{"kind": "execute", "command": "df -h", "risk": "read-only"}',
        '{"kind": "command", "command": "df -h", "risk": "harmless"}',
        '{"kind": "command", "command": "", "risk": "read-only"}',
        '{"kind": "command", "command": 7, "risk": "read-only"}',
        '{"kind": "clarify"}',
        '{"kind": "refuse", "reason": "because"}',
        '{"kind": "command", "command": "ls", "command": "rm -rf ~", "risk": "read-only"}',
        '{"kind": "command", "command": "df -h", "risk": "read-only"} trailing',
        "NaN",
        '"df -h"',
    ],
    ids=[
        "extra-property",
        "extra-property-on-refuse",
        "missing-risk",
        "command-with-reason",
        "clarify-with-command",
        "command-over-2000",
        "invalid-json",
        "free-text",
        "empty",
        "json-array",
        "empty-array",
        "missing-kind",
        "unknown-kind",
        "unknown-risk",
        "empty-command",
        "command-not-a-string",
        "clarify-without-reason",
        "unknown-reason",
        "duplicate-property",
        "trailing-text",
        "nan",
        "json-string",
    ],
)
def test_invalid_responses_are_rejected_not_repaired(target_folder, raw):
    from nl_shell import proposal

    assert isinstance(proposal.parse(raw), proposal.Rejected)
    assert reply_for(target_folder, raw) == NO_USABLE + "\n"


# (e) how a proposal is shown; hidden characters in a command ----------------------------


@pytest.mark.parametrize(
    "command",
    ["for f in *.log; do\n  wc -l \"$f\"\ndone", "cut -d '\t' -f2 data.tsv"],
    ids=["multi-line", "tab"],
)
def test_newline_and_tab_in_a_command_are_shown_as_is(target_folder, command):
    raw = json.dumps({"kind": "command", "command": command, "risk": "read-only"})
    assert reply_for(target_folder, raw) == (
        f"Proposed command (risk: read-only):\n{command}\n{NOT_RUN}\n"
    )


HIDDEN = [
    ("\x1b", "esc"),
    ("\r", "cr"),
    ("\x00", "nul"),
    ("\x07", "bel"),
    ("\x0b", "vt"),
    ("\x7f", "del"),
    ("\x80", "c1-first"),
    ("\x9b", "c1-csi"),
    ("\x9f", "c1-last"),
    *[(chr(cp), f"bidi-{cp:04x}") for cp in sorted(BIDI)],
]


@pytest.mark.parametrize(
    "char", [c for c, _ in HIDDEN], ids=[name for _, name in HIDDEN]
)
def test_command_with_a_hidden_character_is_rejected(target_folder, char):
    from nl_shell import proposal

    raw = json.dumps({"kind": "command", "command": f"ls {char}x", "risk": "read-only"})
    assert isinstance(proposal.parse(raw), proposal.Rejected)
    out = reply_for(target_folder, raw)
    assert out == NO_USABLE + "\n"


def test_rlo_in_a_command_is_rejected(target_folder):
    """U+202E (RIGHT-TO-LEFT OVERRIDE), the required vector, spelled out."""
    raw = '{"kind": "command", "command": "ls \\u202e cod.exe", "risk": "read-only"}'
    assert reply_for(target_folder, raw) == NO_USABLE + "\n"


# (f) :status lists the prompt files that were loaded -------------------------------------


def test_status_lists_the_loaded_prompt_files(start, target_folder, user_prompts):
    import nl_shell

    default = target_folder / "prompts" / "prompts.yaml"
    code, out, _err, _started = start(":status")
    assert code == 0
    assert out == (
        f"nl-shell {nl_shell.__version__}\n"
        "target: testos-1 (Test OS 1)\n"
        "target matches this OS\n"
        f"prompt files: {default}\n"
    )
    user_prompts.write_text("system: mine\n", encoding="utf-8")
    code, out, _err, _started = start(":status")
    assert code == 0
    assert out.splitlines()[-1] == f"prompt files: {default}, {user_prompts}"


def test_status_says_when_no_prompt_files_were_loaded(start, target_folder):
    (target_folder / "prompts" / "prompts.yaml").unlink()
    code, out, _err, _started = start(":status", "show disk usage", responses=[COMMAND_OK])
    assert code == 0
    assert out.splitlines()[3] == "prompt files: none"
    assert out.splitlines()[4] == (
        "No prompts are loaded, so nl-shell can't ask the model: "
        "the active target has no prompts/prompts.yaml and there is no user prompts.yaml."
    )

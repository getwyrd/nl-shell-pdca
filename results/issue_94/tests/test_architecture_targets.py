"""Document relationships from ADR-0023, not runtime implementation evidence."""

from pathlib import Path
import re

import pytest


ARCHITECTURE = Path(__file__).resolve().parents[1] / "docs/design/architecture"


def chapter(name):
    return (ARCHITECTURE / name).read_text()


def normalized(text):
    return " ".join(text.split())


def consumer(text, name):
    match = re.search(
        rf"^- \*\*{re.escape(name)}[^\n]*.*?(?=^- \*\*|^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"Missing target consumer: {name}"
    return normalized(match.group())


def require(text, *facts):
    text = normalized(text)
    for fact in facts:
        assert fact in text, f"Missing documented relationship: {fact}"


def test_target_component_and_layout():
    text = chapter("05-building-block-view.md")
    require(
        text,
        'targets["Target folder<br/>targets/&lt;id&gt;/"]',
        'targets -.->|"command prompts at start-up"| backend',
        'targets -.->|"planned integration"| gate',
        "| Target folder `targets/<id>/` |",
        "Targets are not packaged yet",
        "requirements awaiting implementation",
        "Per-target VM with snapshots",
        "Components not yet built are marked",
        "*(planned)* in 5.3",
        "| PTY session, state capture, policy gate integration, confirm UI, session log | — | *(planned)* |",
    )
    assert "targets -.-> input" not in text
    rows = text.split("## 5.3 Code layout", 1)[1]
    for module in ("targets", "os_release", "gate.vectors", "prompts", "reader",
                   "command_provider"):
        matching = [row for row in rows.splitlines() if f"`nl_shell.{module}`" in row]
        assert matching, f"Missing module status: {module}"
        assert all("built" in row for row in matching)
    reader = [row for row in rows.splitlines() if "`nl_shell.reader`" in row]
    assert reader and all("not yet wired" in row for row in reader)


@pytest.mark.parametrize(
    ("name", "facts"),
    [
        ("REPL start-up", (
            "(built)", "`target.toml`", "command `prompts/`",
            "exact os-release `ID` and `VERSION_ID`", "never `ID_LIKE`",
            "`--target`", "`config.toml`", "currently produces a warning",
        )),
        ("REPL target inputs", (
            "(planned)", "`model.toml`", "SHA-256", "refuse mismatched weights",
            "`sensitive.toml`", "not built",
        )),
        ("Gate integration", (
            "(planned", "package-owner query", "`sensitive.toml`",
            "planned `allowlist.toml`", "every command must need confirmation",
            "integrations are not built", "gate-vector loading",
            "`gate-vectors.toml` is built for conformance tests",
        )),
        ("Reader module", (
            "(built, not yet wired into the REPL)", "`prompts/reader.yaml`",
            "target's `command_provider`",
        )),
        ("Installer", (
            "(planned", "`model.toml`", "download and verify weights",
            "ships every target's runtime files", "requirements awaiting implementation",
        )),
        ("Pipeline", (
            "(planned)", "`harvest.toml`", "reference VM", "`prompts/`",
            "`eval/`", "build-time material, not runtime files", "exists yet",
        )),
    ],
)
def test_target_consumer_status(name, facts):
    text = consumer(chapter("05-building-block-view.md"), name)
    require(text, *facts)
    if name == "REPL start-up":
        assert "every command" not in text


def test_planned_deployment_integrity_and_adapters():
    text = chapter("07-deployment-view.md")
    require(text, "not an assertion that these already ship")
    packaging = consumer(text, "Target packaging")
    require(packaging, "(planned", "every target's runtime files",
            "`target.toml`", "`model.toml`", "`allowlist.toml`",
            "`sensitive.toml`", "`prompts/`",
            "Build-time `harvest.toml` and `eval/` are not shipped")
    integrity = consumer(text, "Model integrity")
    require(
        integrity, "(planned)", "not stored in git or the package",
        "`model.toml` records each file's URL, size, SHA-256",
        "base model/license", "pipeline commit and dataset hash", "quantization",
        "`$XDG_DATA_HOME/nl-shell/models/`",
        "verifying SHA-256 against `model.toml` before use",
        "REPL must refuse to load weights on a hash mismatch",
        "active target's manifest",
        "Downloads happen only at install or explicit update, never at runtime",
        "requirements awaiting implementation",
    )
    adapters = consumer(text, "Personalization adapters")
    require(adapters, "(planned)", "per target and base-weight hash",
            "must not load an adapter on different weights",
            "awaiting implementation")
    require(text, "Reference system per target", "VM for that target")
    open_questions = [normalized(p) for p in text.split("\n\n") if "**[OPEN]**" in p]
    assert len(open_questions) == 2
    require(open_questions[0], "Weight URL host in `model.toml`")
    require(open_questions[1], "Package distribution channel", "resolves neither",
            "this channel nor the weights' host")
    for channel in ("GitHub", "Hugging Face", "PPA"):
        assert channel not in text


def test_target_scoped_reference_and_training():
    text = chapter("08-crosscutting-concepts.md")
    require(
        text, "active target's package", "`dpkg`", "`ubuntu-26.04`",
        "active target's package data/query",
        "command model sees only that answer, labelled untrusted",
        "reader has no PTY, no tools and no network",
        "fresh snapshot of the target's VM",
        "## 8.8 `ubuntu-26.04` target specifics",
        "For this first and currently only target",
        "Every runtime component works offline",
        "package data for the active target",
    )
    assert "local local" not in normalized(text)

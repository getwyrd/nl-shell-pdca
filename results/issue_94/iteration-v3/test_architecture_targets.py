"""Relationships in the living architecture; semantic review remains human work."""
from pathlib import Path
import re


ARCH = Path(__file__).resolve().parents[1] / "docs/design/architecture"


def chapter(name):
    return re.sub(r"\s+", " ", (ARCH / name).read_text())


def paragraph(text, start):
    assert start in text, f"Missing documented relationship: {start}"
    return text.split(start, 1)[1].split(" - **", 1)[0]


def test_target_consumers_and_status():
    text = chapter("05-building-block-view.md")
    assert 'targets["Target folder<br/>targets/&lt;id&gt;/"]' in text
    assert 'targets -.->|"command prompts at start-up"| backend' in text
    assert 'targets -.->|"planned integration"| gate' in text
    assert 'targets -.-> input' not in text
    startup = paragraph(text, "**REPL start-up (built):**")
    assert all(s in startup for s in ("`target.toml`", "`ID` and `VERSION_ID`", "`ID_LIKE`", "`prompts/`"))
    planned = paragraph(text, "**REPL target inputs (planned):**")
    assert all(s in planned for s in ("`model.toml`", "SHA-256", "refuse", "`sensitive.toml`"))
    gate = paragraph(text, "**Gate integration (planned, #12, #190):**")
    assert all(s in gate for s in ("package-owner query", "`sensitive.toml`", "`allowlist.toml`", "every command", "confirmation"))
    reader = paragraph(text, "**Reader module (built, not yet wired into the REPL):**")
    assert all(s in reader for s in ("`prompts/reader.yaml`", "`command_provider`"))
    installer = paragraph(text, "**Installer (planned, #48, #50):**")
    assert "`model.toml`" in installer
    pipeline = paragraph(text, "**Pipeline (planned):**")
    assert all(s in pipeline for s in ("`harvest.toml`", "`eval/`", "`prompts/`"))
    assert "Per-target VM with snapshots" in text
    assert "not yet packaged" in text
    assert "`nl_shell.targets`, `nl_shell.os_release`" in text
    assert "`nl_shell.gate.vectors`" in text
    assert "`nl_shell.command_provider`" in text


def test_planned_deployment_integrity_and_distribution():
    text = chapter("07-deployment-view.md")
    runtime = paragraph(text, "**Target packaging (planned, #48, #50):**")
    assert all(s in runtime for s in ("every target", "`target.toml`", "`model.toml`", "`allowlist.toml`", "`sensitive.toml`", "`gate-vectors.toml`", "`prompts/`", "`harvest.toml`", "`eval/`", "not shipped"))
    integrity = paragraph(text, "**Model integrity (planned):**")
    assert all(s in integrity for s in ("not stored in git or the package", "install or explicit update", "$XDG_DATA_HOME/nl-shell/models/", "SHA-256", "`model.toml`", "REPL must refuse", "hash mismatch", "never at runtime", "awaiting implementation"))
    adapter = paragraph(text, "**Personalization adapters (planned):**")
    assert all(s in adapter for s in ("per target and base-weight hash", "must not load", "different weights", "awaiting implementation"))
    assert "**[OPEN]** Weight URL host in `model.toml`" in text
    assert "**[OPEN]** Package distribution channel" in text
    assert "Reference system per target" in text


def test_target_provenance_and_specifics():
    text = chapter("08-crosscutting-concepts.md")
    assert "local-reference | Package-owned man pages" in text
    assert "active target's reference VM" in text
    assert "active target's package data/query (`dpkg`/`apt` for `ubuntu-26.04`)" in text
    assert "fresh snapshot of the target's VM" in text
    assert "8.8 `ubuntu-26.04` target specifics" in text
    assert "local `man`/`--help`/package data for the active target" in text

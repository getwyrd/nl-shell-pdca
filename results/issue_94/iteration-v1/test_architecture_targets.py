"""Relationships in the living architecture required by ADR-0023.

These assertions check documentation, not runtime implementation or OS facts.
"""
from pathlib import Path

import pytest

ARCH = Path(__file__).resolve().parents[1] / "docs/design/architecture"


def chapter(number):
    return next(ARCH.glob(f"{number:02}-*.md")).read_text()


@pytest.mark.parametrize("consumer", ["REPL start-up", "gate", "installer", "pipeline"])
def test_target_building_block_consumers(consumer):
    text = chapter(5)
    assert "targets/<id>/" in text
    assert consumer in text.split("### Target folder", 1)[1].split("## 5.2", 1)[0]


def test_target_status_and_harvest():
    text = chapter(5)
    status = text.split("## 5.3", 1)[1]
    for name in ["nl_shell.targets", "nl_shell.os_release", "nl_shell.gate.vectors", "nl_shell.prompts", "nl_shell.reader"]:
        row = next(line for line in status.splitlines() if name in line)
        assert "built" in row and "planned" not in row
    assert "Per-target reference VM and harvest" in text
    for name in ["model.toml", "allowlist.toml", "harvest.toml", "eval/"]:
        assert name in text
    assert "not packaged yet" in text
    assert "integrity and adapter requirements remain planned" in text


def test_deployment_manifest_and_adapter_contract():
    text = chapter(7)
    for fact in ["every target's runtime files", "planned", "not stored in git or the package", "install or explicit update", "$XDG_DATA_HOME/nl-shell/models/", "SHA-256", "refuse to load", "does not match", "per target and base-weight hash", "not loaded on different weights"]:
        assert fact in text
    open_items = [line for line in text.splitlines() if "[OPEN]" in line]
    assert any("URL host" in line and "model.toml" in line for line in open_items)
    assert any("Package distribution channel" in line for line in open_items)


def test_target_owned_reference_data_and_specifics():
    text = chapter(8)
    for fact in ["active target's package", "dpkg/apt", "ubuntu-26.04", "target's reference VM", "target's package system", "## 8.8 ubuntu-26.04 target specifics", "local-reference", "untrusted", "confirm", "offline"]:
        assert fact in text

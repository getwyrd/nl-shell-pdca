"""Relationships in the living architecture, not runtime implementation claims."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs/design/architecture"


def chapter(name):
    return (ROOT / name).read_text()


def section(text, heading):
    assert heading in text, f"Missing section: {heading}"
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def contains(text, *facts):
    for fact in facts:
        assert fact in text, f"Missing documented relationship: {fact}"


def test_target_consumers_and_status():
    doc = chapter("05-building-block-view.md")
    target = section(doc, "### Target folder")
    contains(doc, 'targets["targets/<id>/"]', "| Target folder |")
    contains(target, "REPL start-up", "ID", "VERSION_ID", "ID_LIKE",
             "Gate tests (built)", "gate-vectors.toml", "Command and reader prompts (built)",
             "Gate integration (planned, #12, #190)", "package-owner query",
             "sensitive.toml", "allowlist.toml", "Mismatch confirmation (planned, #12)",
             "Installer (planned, #48, #50)", "model.toml",
             "Pipeline (planned)", "harvest.toml", "eval/",
             "Model integrity and adapter compatibility are planned")
    layout = section(doc, "## 5.3 Code layout")
    contains(layout, "nl_shell.targets", "nl_shell.os_release", "nl_shell.gate.vectors",
             "nl_shell.prompts", "nl_shell.reader", "nl_shell.command_provider")
    assert "Remaining M0 work" not in layout
    contains(doc, "Per-target VM", "not packaged yet")


def test_deployment_manifest_integrity_and_adapters():
    doc = chapter("07-deployment-view.md")
    manifest = section(doc, "### Planned target distribution and integrity")
    contains(manifest, "every target's runtime files", "target.toml", "model.toml",
             "allowlist.toml", "sensitive.toml", "gate-vectors.toml", "prompts/",
             "harvest.toml", "eval/", "not in git or the package",
             "$XDG_DATA_HOME/nl-shell/models/", "only at install or explicit update",
             "SHA-256", "before use", "REPL must refuse", "active target's manifest",
             "per target and base-weight hash", "must not load", "different weights")
    contains(doc, "**[OPEN]** Weight URL host in `model.toml`",
             "**[OPEN]** Package distribution channel", "Reference system per target")


def test_target_scoped_reference_and_training():
    doc = chapter("08-crosscutting-concepts.md")
    contains(section(doc, "## 8.2 Taint"), "active target's", "package-owned", "local-reference")
    contains(section(doc, "## 8.5 The quarantined reader"), "active target's package",
             "dpkg/apt", "ubuntu-26.04", "untrusted", "no network")
    contains(section(doc, "## 8.7 Teacher and student"), "target's reference VM")
    contains(section(doc, "## 8.8 Ubuntu 26.04 specifics"), "`ubuntu-26.04` target")
    contains(section(doc, "## 8.9 Locally complete"), "offline", "target's package system")

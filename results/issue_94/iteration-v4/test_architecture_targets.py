"""Document relationships required by ADR-0023; runtime behavior is not tested here."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs/design/architecture"


def chapter(name):
    return (ROOT / name).read_text()


def section(text, heading, end):
    assert heading in text, f"missing {heading}"
    return text.split(heading, 1)[1].split(end, 1)[0]


def test_target_building_block_and_status():
    text = chapter("05-building-block-view.md")
    assert 'targets["Target folder' in text
    assert 'targets -.->|"command prompts (built)"| backend' in text
    assert 'targets -.->|"planned integration"| gate' in text
    assert 'targets -.-> input' not in text
    start = section(text, '- **REPL start-up (built)**', '\n- **')
    for fact in ('`target.toml`', '`ID` and `VERSION_ID`', '`ID_LIKE`', 'warning'):
        assert fact in start
    assert 'makes every command need confirmation' not in start
    pending = section(text, '- **REPL inputs (planned)**', '\n- **')
    assert '`model.toml`' in pending and '`sensitive.toml`' in pending
    gate = section(text, '- **Gate integration (planned', '\n- **')
    for fact in ('not built', 'package-owner query', '`sensitive.toml`', '`allowlist.toml`', 'every command'):
        assert fact in gate
    pipeline = section(text, '- **Pipeline (planned)**', '\n\n')
    assert 'exists yet' in pipeline and '`harvest.toml`' in pipeline and '`eval/`' in pipeline
    rows = text.split('## 5.3', 1)[1].splitlines()
    reader = [row for row in rows if '`nl_shell.reader`' in row]
    assert len(reader) == 1 and 'not yet wired' in reader[0]
    assert '`nl_shell.command_provider`' in text
    assert '| PTY session, policy gate integration, confirm UI, session log |' in text
    assert 'Reference VM and harvest per target' in text


def test_deployment_manifest_and_compatibility_are_planned():
    text = chapter('07-deployment-view.md')
    deployment = section(text, '## 7.1', 'VRAM budget')
    assert 'not an assertion that these already ship' in deployment
    for fact in ('every target', '`target.toml`', '`sensitive.toml`', '`allowlist.toml`', '`prompts/`', 'not packaged yet'):
        assert fact in deployment
    integrity = section(text, '**Model integrity (planned', '\n\n')
    for fact in ('`model.toml`', 'URL', 'size', 'SHA-256', 'not stored in git or the package', '$XDG_DATA_HOME/nl-shell/models/', 'REPL must refuse', 'awaiting implementation', 'only at install or explicit update, never at runtime'):
        assert fact in integrity
    adapter = section(text, '**Adapters (planned)**', '\n\n')
    assert 'per target and base-weight hash' in adapter
    assert 'must not load' in adapter and 'not implemented' in adapter
    questions = [line for line in text.splitlines() if '**[OPEN]**' in line]
    assert any('URL host' in line and 'model.toml' in line for line in questions)
    assert any('package distribution channel' in line for line in questions)
    assert 'Reference system per target' in text


def test_target_provenance_and_training():
    text = chapter('08-crosscutting-concepts.md')
    provenance = section(text, '| local-reference |', '\n')
    assert "target's package-owned" in provenance and "target's reference VM" in provenance
    reader = section(text, '## 8.5', '## 8.6')
    assert "active target's package data/query" in reader
    assert 'untrusted' in reader and 'no network' in reader
    training = section(text, '## 8.7', '## 8.8')
    assert "target's reference VM" in training
    assert '## 8.8 The `ubuntu-26.04` target' in text
    offline = section(text, '## 8.9', '## 8.10')
    assert "active target's package system" in offline and 'offline' in offline
    assert 'local local' not in offline

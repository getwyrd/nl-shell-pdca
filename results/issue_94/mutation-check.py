from pathlib import Path
import subprocess

root = Path("/home/eddie/nl-shell/nl-shell.pdca-wt-l0")
bundle = Path("/home/eddie/nl-shell/nl-shell-pdca/results/issue_94")
mutations = [
    ("mismatch-confirm", "05", "currently produces a warning", "makes every command need confirmation"),
    ("reader-row-built", "05", "built modules; reader not yet wired into REPL", "built"),
    ("reader-bullet-built", "05", "(built, not yet wired into the REPL)", "(built)"),
    ("repl-input-status", "05", "These inputs\n  are not built.", ""),
    ("installer-status", "05", "**Installer (planned, #48, #50):**", "**Installer:**"),
    ("gate-status", "05", "These integrations are not built;", "These integrations are built;"),
    ("pipeline-status", "05", "exists yet", "is present"),
    ("ch05-integrity-status", "05", "requirements awaiting implementation", "implemented requirements"),
    ("packaging-status", "05", "Targets are not packaged yet", "Targets are packaged"),
    ("state-capture", "05", "PTY session, state capture, policy gate integration", "PTY session, policy gate integration"),
    ("deployment-lead-in", "07", "not\nan assertion that these already ship", "already shipping"),
    ("integrity-status", "07", "These checks are requirements\n  awaiting implementation.", "These checks are built."),
    ("adapter-status", "07", "remains awaiting implementation", "is implemented"),
    ("distribution-resolution", "07", "resolves neither", "chooses"),
    ("distribution-choice", "07", "Package distribution channel (M5.4).", "Package distribution channel (M5.4): GitHub."),
]
for name, prefix, old, new in mutations:
    path = next((root / "docs/design/architecture").glob(prefix + "-*.md"))
    original = path.read_text()
    assert old in original, name
    try:
        path.write_text(original.replace(old, new))
        result = subprocess.run(
            ["/home/eddie/nl-shell/nl-shell-pdca/.venv/bin/python3",
             "-m", "pytest", "-q", "tests/test_architecture_targets.py"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        (bundle / ("mutation-" + name + ".log")).write_text(result.stdout + result.stderr)
        print(name, "exit", result.returncode, result.stdout.splitlines()[-1])
        assert result.returncode == 1, name
        assert "failed" in result.stdout, name
    finally:
        path.write_text(original)

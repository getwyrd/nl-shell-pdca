"""Pinned source identity checks; missing production data fails inside the test."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
REVISION = "eacda7020c4102729187c38c35ce28fac00365c9"
ANCHOR = "4ce7ecdff5a4da72bfef4378f027ad141b7daa28dc6b0a68f57905a6e080d960"


def blob_id(content):
    return hashlib.sha1(
        b"blob " + str(len(content)).encode("ascii") + b"\0" + content
    ).hexdigest()


def test_real_pinned_snapshot():
    snapshot = ROOT / "data" / "tldr"
    for name in ("pages.jsonl", "source.json", "LICENSE.md", "NOTICE.md"):
        assert (snapshot / name).is_file(), f"real pinned source must be shipped: {name}"
    records = [
        json.loads(line)
        for line in (snapshot / "pages.jsonl").read_text(encoding="utf-8").split("\n")
        if line
    ]
    paths = [record["path"] for record in records]
    assert paths == sorted(set(paths))
    assert len(records) == 6837
    inventory = bytearray()
    byte_count = 0
    for record in records:
        assert set(record) == {"path", "content"}
        path, content = record["path"], record["content"]
        assert isinstance(path, str) and isinstance(content, str)
        assert path.startswith(("pages/common/", "pages/linux/"))
        assert path.endswith(".md")
        content_bytes = content.encode("utf-8")
        byte_count += len(content_bytes)
        inventory.extend(f"{path}\0{100644}\0{blob_id(content_bytes)}\n".encode("utf-8"))
    assert byte_count == 4050595
    assert hashlib.sha256(inventory).hexdigest() == ANCHOR
    license_bytes = (snapshot / "LICENSE.md").read_bytes()
    assert len(license_bytes) == 1572
    assert blob_id(license_bytes) == "9b4ebcb9a886af3506c5d42f1dcf1253a520efbe"
    notice = (snapshot / "NOTICE.md").read_text(encoding="utf-8")
    for text in ("tldr-pages", "contributors", REVISION, "CC BY 4.0"):
        assert text in notice
    assert "repackag" in notice.lower()


def test_offline_export():
    script = ROOT / "scripts" / "tldr_snapshot.py"
    assert script.is_file(), "production export entry point must be shipped"
    wrapper = r'''
import json, runpy, sys
attempts = []
def audit(event, args):
    if event in {
        "socket.connect", "socket.getaddrinfo", "socket.sendto",
        "socket.gethostbyname", "socket.gethostbyaddr", "subprocess.Popen",
        "os.system", "os.exec", "os.posix_spawn", "os.spawn",
    }:
        attempts.append(event)
        raise RuntimeError("forbidden offline operation")
sys.addaudithook(audit)
script = sys.argv[1]
sys.argv = [script, "export"]
try:
    runpy.run_path(script, run_name="__main__")
finally:
    print(json.dumps(attempts), file=sys.stderr)
if attempts:
    raise RuntimeError("caught forbidden attempts")
'''
    exports = [
        subprocess.run(
            [sys.executable, "-c", wrapper, str(script)],
            cwd=ROOT, capture_output=True, timeout=30,
        )
        for _ in range(2)
    ]
    for result in exports:
        assert result.returncode == 0, result.stderr.decode("utf-8")
        assert result.stderr == b"[]\n"
    assert exports[0].stdout == exports[1].stdout
    exported = [json.loads(line) for line in exports[0].stdout.split(b"\n") if line]
    original = [
        json.loads(line)
        for line in (ROOT / "data/tldr/pages.jsonl").read_text(encoding="utf-8").split("\n")
        if line
    ]
    assert len(exported) == 6837
    assert exported == [
        dict(record, revision=REVISION, language="en", provenance="local-reference")
        for record in original
    ]
    for path in ("pages/common/tar.md", "pages/linux/apt.md"):
        assert any(record["path"] == path and "`" in record["content"] for record in exported)

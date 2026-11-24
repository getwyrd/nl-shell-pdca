"""Offline contract against real upstream bytes, independently anchored by Plan."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/tldr"
SCRIPT = ROOT / "scripts/tldr_snapshot.py"
REVISION = "eacda7020c4102729187c38c35ce28fac00365c9"
ANCHOR = "4ce7ecdff5a4da72bfef4378f027ad141b7daa28dc6b0a68f57905a6e080d960"
WRAPPER = r'''
import json, os, runpy, socket, subprocess, sys
attempts = []
events = {"socket.connect", "socket.getaddrinfo", "socket.sendto",
          "socket.gethostbyname", "socket.gethostbyaddr", "subprocess.Popen",
          "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty"}
def audit(event, args):
    if event in events:
        attempts.append(event)
        raise RuntimeError("audit blocked " + event)
sys.addaudithook(audit)
mode, script, root, report = sys.argv[1:]
try:
    if mode == "network":
        socket.socket().connect(("127.0.0.1", 9))
    elif mode == "process":
        subprocess.run([sys.executable, "-c", "pass"], check=True)
    else:
        sys.argv = [script, "export", "--root", root]
        runpy.run_path(script, run_name="__main__")
finally:
    with open(report, "w", encoding="utf-8") as output:
        json.dump(attempts, output)
'''


def blob(content):
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()


def audited(tmp_path, root=DATA, mode="export"):
    report = tmp_path / "audit.json"
    result = subprocess.run(
        [sys.executable, "-c", WRAPPER, mode, str(SCRIPT), str(root), str(report)],
        capture_output=True, timeout=30,
    )
    return result, json.loads(report.read_text(encoding="utf-8"))


def test_real_pinned_snapshot(tmp_path):
    for name in ["pages.jsonl", "source.json", "LICENSE.md", "NOTICE.md", "README.md"]:
        assert (DATA / name).is_file(), f"real pinned source must be shipped: {name}"
    assert SCRIPT.is_file(), "production export entry point must be shipped"
    records = [json.loads(line) for line in (DATA / "pages.jsonl").read_text(encoding="utf-8").split("\n") if line]
    assert len(records) == 6837
    paths = [r["path"] for r in records]
    assert paths == sorted(set(paths))
    inventory = bytearray()
    manifest = []
    for record in records:
        assert set(record) == {"path", "content"}
        assert record["path"].startswith(("pages/common/", "pages/linux/"))
        content = record["content"].encode("utf-8")
        identity = blob(content)
        inventory.extend(f'{record["path"]}\000100644\0{identity}\n'.encode("utf-8"))
        manifest.append({"path": record["path"], "bytes": len(content), "blob_sha1": identity, "sha256": hashlib.sha256(content).hexdigest()})
    assert sum(p["bytes"] for p in manifest) == 4050595
    assert hashlib.sha256(inventory).hexdigest() == ANCHOR
    metadata = json.loads((DATA / "source.json").read_text(encoding="utf-8"))
    assert metadata["pages"] == manifest
    assert metadata["revision"] == REVISION
    assert metadata["repository"] == "https://github.com/tldr-pages/tldr"
    assert metadata["prefixes"] == ["pages/common/", "pages/linux/"]
    assert metadata["language"] == "en"
    assert metadata["transformation"]
    assert metadata["inventory_sha256"] == ANCHOR
    assert metadata["corpus_sha256"] == hashlib.sha256((DATA / "pages.jsonl").read_bytes()).hexdigest()
    assert blob((DATA / "LICENSE.md").read_bytes()) == "9b4ebcb9a886af3506c5d42f1dcf1253a520efbe"
    notice = (DATA / "NOTICE.md").read_text(encoding="utf-8")
    for text in ["tldr-pages team", "contributors", REVISION, "CC BY 4.0", "repackag"]:
        assert text in notice
    by_path = {p["path"]: p for p in manifest}
    assert by_path["pages/common/tar.md"]["blob_sha1"] == "0dbcb8da7c04cbc911d6ac4b9d96ff660718ee33"
    assert by_path["pages/linux/apt.md"]["blob_sha1"] == "f5cd78e6aa90c7fdbe24e3012be943612f3f3f50"
    first, attempts = audited(tmp_path)
    assert first.returncode == 0, first.stderr.decode()
    assert attempts == []
    second, attempts = audited(tmp_path)
    assert second.returncode == 0, second.stderr.decode()
    assert attempts == []
    assert first.stdout == second.stdout
    exported = [json.loads(line) for line in first.stdout.decode("utf-8").split("\n") if line]
    assert exported == [dict(r, revision=REVISION, language="en", provenance="local-reference") for r in records]
    tar = next(r["content"] for r in exported if r["path"] == "pages/common/tar.md")
    assert "`tar " in tar and "{{" in tar


@pytest.mark.parametrize("mode,event", [("network", "socket.connect"), ("process", "subprocess.Popen")])
def test_audit_positive_controls(tmp_path, mode, event):
    result, attempts = audited(tmp_path, mode=mode)
    assert result.returncode != 0
    assert attempts == [event], result.stderr.decode("utf-8")
    assert b"audit blocked" in result.stderr


@pytest.mark.parametrize("fault", ["digest", "fabricated", "extra", "duplicate", "missing", "license", "manifest", "revision", "path"])
def test_corruption_rejected(tmp_path, fault):
    assert DATA.is_dir(), "real pinned corpus must be shipped"
    copy = tmp_path / "snapshot"
    shutil.copytree(DATA, copy)
    metadata = json.loads((copy / "source.json").read_text(encoding="utf-8"))
    records = [json.loads(line) for line in (copy / "pages.jsonl").read_text(encoding="utf-8").split("\n") if line]
    if fault == "fabricated":
        records[0]["content"] = "!" + records[0]["content"][1:]
    elif fault in {"digest", "manifest"}:
        records[0]["content"] += "\nchanged\u2028page\u2029text\u0085\n"
    elif fault == "extra":
        records[0]["trusted"] = True
    elif fault == "duplicate":
        records.insert(1, records[0])
    elif fault == "missing":
        records.pop()
    elif fault == "path":
        records[0]["path"] = "pages/common/../escape.md"
    elif fault == "license":
        (copy / "LICENSE.md").write_text("changed", encoding="utf-8")
    elif fault == "revision":
        metadata["revision"] = "0" * 40
    corpus = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records).encode("utf-8")
    (copy / "pages.jsonl").write_bytes(corpus)
    if fault != "digest":
        metadata["corpus_sha256"] = hashlib.sha256(corpus).hexdigest()
    if fault == "fabricated":
        content = records[0]["content"].encode("utf-8")
        metadata["pages"][0].update(bytes=len(content), blob_sha1=blob(content), sha256=hashlib.sha256(content).hexdigest())
    (copy / "source.json").write_text(json.dumps(metadata), encoding="utf-8")
    result, attempts = audited(tmp_path, root=copy)
    assert result.returncode != 0
    assert result.stdout == b"", "validation must finish before any page is exported"
    assert attempts == []
    assert b"invalid tldr snapshot" in result.stderr
    expected = {
        "digest": b"corpus digest mismatch",
        "fabricated": b"pinned inventory mismatch",
        "extra": b"invalid record schema",
        "duplicate": b"invalid, duplicate or unordered path",
        "missing": b"page manifest mismatch",
        "license": b"license mismatch",
        "manifest": b"page manifest mismatch",
        "revision": b"source identity mismatch",
        "path": b"invalid page path",
    }
    assert expected[fault] in result.stderr

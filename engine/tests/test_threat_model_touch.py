"""Engine tests: check-threat-model-touch.sh (advisory T2, nl-shell-pdca#11).

Run: python3 -m unittest discover -s engine/tests
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

INSTANCE = Path(__file__).resolve().parents[2]
SCRIPT = INSTANCE / "engine" / "scripts" / "check-threat-model-touch.sh"


def _diff(paths: list[str]) -> str:
    return "".join(f"diff --git a/{p} b/{p}\nnew file mode 100644\n--- /dev/null\n+++ b/{p}\n@@ -0,0 +1 @@\n+x\n"
                   for p in paths)


class ThreatModelTouch(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.bundle, ignore_errors=True)

    def _run(self, paths: list[str] | None) -> subprocess.CompletedProcess[str]:
        if paths is not None:
            (self.bundle / "patch.diff").write_text(_diff(paths), encoding="utf-8")
        return subprocess.run(["bash", str(SCRIPT)], cwd=INSTANCE, capture_output=True, text=True,
                              env={**os.environ, "PDCA_BUNDLE": str(self.bundle)})

    def test_unrelated_change_passes(self) -> None:
        r = self._run(["src/nl_shell/router.py", "tests/test_router.py"])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("no security-relevant path", r.stdout)

    def test_security_change_without_threat_model_is_unverifiable(self) -> None:
        r = self._run(["src/nl_shell/gate.py", "tests/test_gate.py"])
        self.assertEqual(r.returncode, 77, r.stdout)
        self.assertIn("src/nl_shell/gate.py", r.stdout)

    def test_security_sensitive_target_and_runtime_paths_are_unverifiable(self) -> None:
        paths = [
            "targets/ubuntu-26.04/allowlist.toml",
            "targets/ubuntu-26.04/target.toml",
            "src/nl_shell/teacher_client.py",
            "src/nl_shell/cli.py",
            "src/nl_shell/failure_classes.py",
            "src/nl_shell/render.py",
            "src/nl_shell/charsafety.py",
        ]
        for path in paths:
            with self.subTest(path=path):
                r = self._run([path])
                self.assertEqual(r.returncode, 77, r.stdout)
                self.assertIn(path, r.stdout)

    def test_spec_change_counts_as_security_relevant(self) -> None:
        r = self._run(["docs/design/specs/policy-gate/v1.md"])
        self.assertEqual(r.returncode, 77, r.stdout)

    def test_security_change_with_threat_model_passes(self) -> None:
        r = self._run(["src/nl_shell/passthrough.py", ".oss-scanner/threat_model.md"])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("threat model updated", r.stdout)

    def test_missing_patch_passes(self) -> None:
        r = self._run(None)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()

"""Integrity failures that must stop acceptance of retained research evidence."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_evidence", ROOT / "scripts/verify_evidence.py")
EVIDENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVIDENCE)


class EvidenceIntegrityTests(unittest.TestCase):
    def test_changed_coefficient_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(ROOT / "evidence", root / "evidence")
            model = root / "evidence/action_value/models/fold-0.json"
            model.write_bytes(model.read_bytes() + b" ")
            with self.assertRaisesRegex(EVIDENCE.EvidenceError, "Size mismatch"):
                EVIDENCE.verify(root)

    def test_manifest_cannot_escape_evidence_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "evidence").mkdir()
            manifest = json.loads((ROOT / "evidence/provenance.json").read_text())
            manifest["files"][0]["path"] = "../outside.json"
            (root / "evidence/provenance.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(EVIDENCE.EvidenceError, "Unsafe evidence path"):
                EVIDENCE.verify(root)


if __name__ == "__main__":
    unittest.main()

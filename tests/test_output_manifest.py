import copy
import json
import tempfile
import unittest
from pathlib import Path

from src.output_manifest import ManifestError, snapshot, verify, write_manifest


class OutputManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "gold"
        (self.root / "date=2026-11-10").mkdir(parents=True)
        (self.root / "date=2026-11-10" / "part-000.csv").write_text(
            "campaign,spend\nA,10\n", encoding="utf-8"
        )
        self.manifest_path = Path(self.temp.name) / "manifest.json"

    def test_snapshot_is_deterministic(self):
        self.assertEqual(snapshot(self.root), snapshot(self.root))
        self.assertEqual(snapshot(self.root)["algorithm"], "sha256")

    def test_atomic_write_and_verify(self):
        manifest = write_manifest(self.root, self.manifest_path)
        self.assertEqual(json.loads(self.manifest_path.read_text()), manifest)
        self.assertTrue(verify(self.root, manifest))

    def test_modified_content_fails(self):
        original = snapshot(self.root)
        (self.root / "date=2026-11-10" / "part-000.csv").write_text("different")
        self.assertFalse(verify(self.root, original))

    def test_added_file_fails(self):
        original = snapshot(self.root)
        (self.root / "extra.csv").write_text("x")
        self.assertFalse(verify(self.root, original))

    def test_removed_file_fails(self):
        original = snapshot(self.root)
        (self.root / "date=2026-11-10" / "part-000.csv").unlink()
        with self.assertRaises(ManifestError):
            verify(self.root, original)

    def test_rejects_empty_directory(self):
        empty = Path(self.temp.name) / "empty"
        empty.mkdir()
        with self.assertRaises(ManifestError):
            snapshot(empty)

    def test_rejects_symlink(self):
        (self.root / "link.csv").symlink_to(self.manifest_path)
        with self.assertRaises(ManifestError):
            snapshot(self.root)

    def test_rejects_duplicate_entries(self):
        manifest = snapshot(self.root)
        manifest["files"].append(copy.deepcopy(manifest["files"][0]))
        with self.assertRaises(ManifestError):
            verify(self.root, manifest)

    def test_rejects_unsupported_schema(self):
        manifest = snapshot(self.root)
        manifest["schema_version"] = 2
        with self.assertRaises(ManifestError):
            verify(self.root, manifest)

    def test_manifest_cannot_be_inside_output(self):
        with self.assertRaises(ManifestError):
            write_manifest(self.root, self.root / "manifest.json")


if __name__ == "__main__":
    unittest.main()

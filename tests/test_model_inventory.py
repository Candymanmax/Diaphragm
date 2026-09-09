from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from modules.adapters.registry import MODEL_DOWNLOAD_FILES
from modules.model_inventory import (
    inspect_model_inventory,
    record_model_inventory,
    remove_model_inventory,
    verify_model_inventory,
)


class ModelInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.hub = Path(self.temporary.name) / "hub"

    def _snapshot(self, model_id, revision="revision"):
        repository, _required = MODEL_DOWNLOAD_FILES[model_id]
        folder = "models--" + repository.replace("/", "--")
        snapshot = self.hub / folder / "snapshots" / revision
        snapshot.mkdir(parents=True, exist_ok=True)
        return snapshot

    def _write_model(self, model_id, revision="revision"):
        snapshot = self._snapshot(model_id, revision)
        _repository, required = MODEL_DOWNLOAD_FILES[model_id]

        for index, filename in enumerate(required, start=1):
            (snapshot / filename).write_bytes(
                (f"{model_id}-{index}" * index).encode("utf-8")
            )

        return snapshot

    def test_inventory_tracks_missing_partial_unverified_and_recorded_states(self):
        missing = inspect_model_inventory("turbo", self.hub)
        self.assertEqual(missing.state, "missing")
        self.assertEqual(missing.local_bytes, 0)

        snapshot = self._snapshot("turbo")
        required = MODEL_DOWNLOAD_FILES["turbo"][1]
        (snapshot / required[0]).write_bytes(b"partial")
        partial = inspect_model_inventory("turbo", self.hub)
        self.assertEqual(partial.state, "partial")
        self.assertEqual(partial.present_count, 1)

        for filename in required[1:]:
            (snapshot / filename).write_bytes(filename.encode("utf-8"))

        unverified = inspect_model_inventory("turbo", self.hub)
        self.assertEqual(unverified.state, "unverified")
        expected_size = sum(
            (snapshot / filename).stat().st_size for filename in required
        )
        self.assertEqual(unverified.local_bytes, expected_size)

        recorded = record_model_inventory("turbo", self.hub)
        self.assertEqual(recorded.state, "installed")
        self.assertTrue(recorded.recorded)

    def test_verification_detects_same_size_file_changes(self):
        snapshot = self._write_model("nano")
        record_model_inventory("nano", self.hub)
        filename = MODEL_DOWNLOAD_FILES["nano"][1][0]
        original = (snapshot / filename).read_bytes()
        replacement = bytes(byte ^ 1 for byte in original)
        (snapshot / filename).write_bytes(replacement)

        report = verify_model_inventory("nano", self.hub)

        self.assertFalse(report.valid)
        self.assertIn(filename, report.message)

    def test_complete_snapshot_is_preferred_over_a_partial_snapshot(self):
        complete = self._write_model("turbo", revision="complete")
        partial = self._snapshot("turbo", revision="partial")
        required = MODEL_DOWNLOAD_FILES["turbo"][1]
        (partial / required[0]).write_bytes(b"newer partial data")

        inventory = inspect_model_inventory("turbo", self.hub)

        self.assertTrue(inventory.installed)
        self.assertTrue(inventory.snapshot.samefile(complete))
        self.assertEqual(inventory.present_count, inventory.required_count)

    def test_corrupt_inventory_record_is_treated_as_unverified(self):
        self._write_model("nano")
        record = self.hub / ".diaphragm-model-inventory.json"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text("{not valid json", encoding="utf-8")

        inventory = inspect_model_inventory("nano", self.hub)

        self.assertTrue(inventory.installed)
        self.assertFalse(inventory.recorded)
        self.assertEqual(inventory.state, "unverified")

    def test_removing_original_preserves_shared_v3_files(self):
        snapshot = self._snapshot("original")
        filenames = set(MODEL_DOWNLOAD_FILES["original"][1]) | set(
            MODEL_DOWNLOAD_FILES["v3"][1]
        )

        for filename in filenames:
            (snapshot / filename).write_bytes(filename.encode("utf-8"))

        record_model_inventory("original", self.hub)
        record_model_inventory("v3", self.hub)
        remove_model_inventory("original", self.hub)

        original = inspect_model_inventory("original", self.hub)
        v3 = inspect_model_inventory("v3", self.hub)
        self.assertEqual(original.state, "missing")
        self.assertEqual(original.local_bytes, 0)
        self.assertTrue(v3.installed)

        for filename in MODEL_DOWNLOAD_FILES["v3"][1]:
            self.assertTrue((snapshot / filename).is_file())


if __name__ == "__main__":
    unittest.main()

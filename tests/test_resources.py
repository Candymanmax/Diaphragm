from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from modules.resources import (
    AdaptiveSectionPlanner,
    ResourceSnapshot,
    RuntimeProfileStore,
    is_cuda_out_of_memory,
)


def snapshot(
    device="cuda",
    free_vram_mb=5000.0,
    total_vram_mb=8192.0,
    available_ram_mb=16000.0,
):
    return ResourceSnapshot(
        active_device=device,
        cuda_available=True,
        gpu_name="Test GPU",
        total_vram_mb=total_vram_mb,
        free_vram_mb=free_vram_mb,
        allocated_vram_mb=1000.0,
        reserved_vram_mb=1200.0,
        peak_vram_mb=1400.0,
        total_system_ram_mb=32000.0,
        available_system_ram_mb=available_ram_mb,
    )


class FakeMonitor:
    def __init__(self, current_snapshot):
        self.current_snapshot = current_snapshot
        self.active_device = current_snapshot.active_device

    def snapshot(self):
        return self.current_snapshot

    def set_active_device(self, device):
        self.active_device = device


class ResourcePlannerTests(unittest.TestCase):
    def _planner(
        self,
        folder,
        current_snapshot=None,
        mode="automatic",
        manual_words=120,
        minimum_words=20,
        maximum_words=160,
        safety_margin_mb=1024,
        growth_interval=3,
    ):
        current_snapshot = current_snapshot or snapshot()
        monitor = FakeMonitor(current_snapshot)
        store = RuntimeProfileStore(Path(folder) / "profiles.json")
        planner = AdaptiveSectionPlanner(
            model_id="original",
            mode=mode,
            manual_words=manual_words,
            minimum_words=minimum_words,
            maximum_words=maximum_words,
            safety_margin_mb=safety_margin_mb,
            growth_interval=growth_interval,
            monitor=monitor,
            profile_store=store,
            after_load_snapshot=current_snapshot,
        )
        return planner, monitor, store

    def test_automatic_size_uses_free_vram_after_safety_margin(self):
        with TemporaryDirectory() as temporary:
            planner, _, _ = self._planner(temporary)

            self.assertEqual(planner.initial_words, 80)
            self.assertEqual(planner.current_words, 80)

    def test_cuda_oom_reduces_size_and_persists_gpu_profile(self):
        with TemporaryDirectory() as temporary:
            planner, _, store = self._planner(temporary)

            self.assertEqual(planner.record_oom(80), 56)
            planner.record_success(50, 5.0, 10.0)
            planner.save_profile()

            saved = store.get(planner.profile_id)
            self.assertEqual(saved["recommended_words"], 56)
            self.assertEqual(saved["smallest_oom_words"], 80)
            self.assertEqual(saved["largest_successful_words"], 50)
            self.assertEqual(saved["runs"], 1)

            next_planner, _, _ = self._planner(temporary)
            self.assertEqual(next_planner.initial_words, 56)

    def test_stable_headroom_increases_later_automatic_sections(self):
        with TemporaryDirectory() as temporary:
            planner, monitor, _ = self._planner(
                temporary,
                growth_interval=2,
            )
            monitor.current_snapshot = snapshot(free_vram_mb=4000.0)
            initial = planner.current_words

            planner.record_success(70, 4.0, 8.0)
            planner.record_success(75, 4.0, 8.0)

            self.assertGreater(planner.current_words, initial)
            self.assertEqual(planner.growth_events, 1)

    def test_short_tail_sections_do_not_inflate_the_learned_limit(self):
        with TemporaryDirectory() as temporary:
            planner, monitor, _ = self._planner(
                temporary,
                growth_interval=1,
            )
            monitor.current_snapshot = snapshot(free_vram_mb=7000.0)
            initial = planner.current_words

            planner.record_success(20, 1.0, 2.0)

            self.assertEqual(planner.current_words, initial)
            self.assertEqual(planner.growth_events, 0)

    def test_safety_margin_prevents_growth_without_headroom(self):
        with TemporaryDirectory() as temporary:
            planner, monitor, _ = self._planner(
                temporary,
                safety_margin_mb=3500,
                growth_interval=1,
            )
            monitor.current_snapshot = snapshot(free_vram_mb=3900.0)
            initial = planner.current_words

            planner.record_success(20, 1.0, 2.0)

            self.assertEqual(planner.current_words, initial)

    def test_manual_mode_keeps_the_requested_size_without_growth(self):
        with TemporaryDirectory() as temporary:
            planner, monitor, _ = self._planner(
                temporary,
                mode="manual",
                manual_words=210,
                maximum_words=160,
                growth_interval=1,
            )
            monitor.current_snapshot = snapshot(free_vram_mb=7000.0)

            planner.record_success(200, 5.0, 10.0)

            self.assertEqual(planner.initial_words, 210)
            self.assertEqual(planner.current_words, 210)

    def test_cpu_profile_uses_available_system_ram(self):
        with TemporaryDirectory() as temporary:
            cpu_snapshot = snapshot(
                device="cpu",
                free_vram_mb=None,
                total_vram_mb=None,
                available_ram_mb=3000.0,
            )
            planner, _, _ = self._planner(
                temporary,
                current_snapshot=cpu_snapshot,
            )

            self.assertEqual(planner.initial_words, 40)
            planner.save_profile()
            saved = planner.profile_store.get(planner.profile_id)
            self.assertEqual(saved["device_name"], "CPU")
            self.assertEqual(saved["total_memory_mb"], 32000.0)

    def test_wrapped_cuda_oom_is_recognized(self):
        try:
            raise RuntimeError("CUDA out of memory while allocating tensor")
        except RuntimeError as cause:
            wrapped = RuntimeError("adapter synthesis failed")
            wrapped.__cause__ = cause

        self.assertTrue(is_cuda_out_of_memory(wrapped))
        self.assertFalse(is_cuda_out_of_memory(RuntimeError("ordinary error")))


if __name__ == "__main__":
    unittest.main()

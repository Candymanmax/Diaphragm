from pathlib import Path
import ctypes
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from modules.resources import monitor as resource_monitor

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

    def test_cpu_zero_available_ram_uses_the_minimum_section_size(self):
        for available, expected in ((0, 20), (None, 120)):
            with self.subTest(available=available), TemporaryDirectory() as folder:
                planner, _, _ = self._planner(
                    folder, current_snapshot=snapshot(device="cpu", available_ram_mb=available),
                )
                self.assertEqual(planner.current_words, expected)

    def test_wrapped_cuda_oom_is_recognized(self):
        try:
            raise RuntimeError("CUDA out of memory while allocating tensor")
        except RuntimeError as cause:
            wrapped = RuntimeError("adapter synthesis failed")
            wrapped.__cause__ = cause

        self.assertTrue(is_cuda_out_of_memory(wrapped))
        self.assertFalse(is_cuda_out_of_memory(RuntimeError("ordinary error")))


class MacOSMemoryTests(unittest.TestCase):
    def library(self, free_pages=100, inactive_pages=200):
        def sysctl(name, output, size, new_value, new_size):
            self.assertEqual(name, b"hw.memsize")
            ctypes.cast(output, ctypes.POINTER(ctypes.c_uint64)).contents.value = 16*1024**3
            return 0

        def statistics(host, flavor, output, count):
            self.assertEqual(flavor, 2)
            values = ctypes.cast(output, ctypes.POINTER(ctypes.c_uint32))
            values[0] = free_pages
            values[1] = 1000  # Active pages must not contribute to available RAM.
            values[2] = inactive_pages
            values[14] = 50  # Speculative pages are already in the free count.
            return 0

        return SimpleNamespace(
            sysctlbyname=Mock(side_effect=sysctl),
            mach_host_self=Mock(return_value=123),
            mach_task_self=Mock(return_value=456),
            host_statistics=Mock(side_effect=statistics),
            mach_port_deallocate=Mock(return_value=0),
        )

    def test_native_memory_uses_the_system_page_size_and_counts_pages_once(self):
        for page_size in (4096, 16384):
            library = self.library()
            with self.subTest(page_size=page_size), patch.object(
                resource_monitor, "_macos_system_library", return_value=library
            ), patch.object(resource_monitor.os, "sysconf", return_value=page_size, create=True):
                self.assertEqual(resource_monitor._macos_memory_bytes(), (
                    16*1024**3, 300*page_size,
                ))
            library.mach_port_deallocate.assert_called_once_with(456, 123)

    def test_failed_vm_statistics_preserve_total_and_release_host_port(self):
        for failure in (5, OSError("permission denied")):
            library = self.library()
            library.host_statistics.side_effect = None
            if isinstance(failure, Exception):
                library.host_statistics.side_effect = failure
            else:
                library.host_statistics.return_value = failure
            with self.subTest(failure=failure), patch.object(
                resource_monitor, "_macos_system_library", return_value=library
            ), patch.object(resource_monitor.os, "sysconf", return_value=16384, create=True):
                self.assertEqual(resource_monitor._macos_memory_bytes(), (16*1024**3, None))
            library.mach_port_deallocate.assert_called_once_with(456, 123)

    def test_total_ram_failure_and_unavailable_api_are_safe(self):
        library = self.library()
        library.sysctlbyname.side_effect = None
        library.sysctlbyname.return_value = -1
        with patch.object(resource_monitor, "_macos_system_library", return_value=library):
            self.assertEqual(resource_monitor._macos_memory_bytes(), (None, None))
        library.mach_host_self.assert_not_called()
        with patch.object(resource_monitor, "_macos_system_library", side_effect=OSError):
            self.assertEqual(resource_monitor._macos_memory_bytes(), (None, None))

    def test_zero_available_ram_is_preserved_and_large_counters_are_bounded(self):
        for pages, expected in ((0, 0), (2**32-1, 16*1024**3)):
            with self.subTest(pages=pages), patch.object(
                resource_monitor, "_macos_system_library",
                return_value=self.library(free_pages=pages, inactive_pages=0),
            ), patch.object(resource_monitor.os, "sysconf", return_value=16384, create=True):
                self.assertEqual(resource_monitor._macos_memory_bytes(), (16*1024**3, expected))

    def test_macos_readings_refresh_and_reach_snapshot_and_planner(self):
        library = self.library(free_pages=100000, inactive_pages=100000)
        with patch.object(resource_monitor.sys, "platform", "darwin"), patch.object(
            resource_monitor, "_macos_system_library", return_value=library
        ), patch.object(resource_monitor.os, "sysconf", return_value=16384, create=True), patch(
            "torch.cuda.is_available", return_value=False
        ), patch("torch.backends.mps.is_available", return_value=False):
            monitor = resource_monitor.ResourceMonitor("cpu")
            first = monitor.snapshot()
            second = monitor.snapshot()
        self.assertEqual(library.host_statistics.call_count, 2)
        self.assertEqual(first.total_system_ram_mb, 16384)
        self.assertEqual(second.available_system_ram_mb, 3125)
        with TemporaryDirectory() as folder:
            planner = AdaptiveSectionPlanner(
                model_id="turbo", mode="automatic", manual_words=120,
                minimum_words=20, maximum_words=160, safety_margin_mb=1024,
                growth_interval=3, monitor=monitor,
                profile_store=RuntimeProfileStore(Path(folder)/"profiles.json"),
                after_load_snapshot=second,
            )
            self.assertEqual(planner.current_words, 40)
            self.assertEqual(planner.report(second)["available_system_ram_after_load_mb"], 3125)

    def test_non_macos_systems_keep_the_existing_sysconf_route(self):
        with patch.object(resource_monitor.sys, "platform", "linux"), patch.object(
            resource_monitor, "os", SimpleNamespace(
                name="posix", sysconf=lambda key: {
                    "SC_PAGE_SIZE": 4096, "SC_PHYS_PAGES": 10000,
                    "SC_AVPHYS_PAGES": 2500,
                }[key],
            )
        ), patch.object(resource_monitor, "_macos_memory_bytes") as native:
            self.assertEqual(resource_monitor._system_memory_bytes(), (40960000, 10240000))
        native.assert_not_called()


if __name__ == "__main__":
    unittest.main()

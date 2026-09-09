from __future__ import annotations

from dataclasses import asdict, dataclass
import ctypes
import os

import torch


MIB = 1024 * 1024


def _mib(value):
    if value is None:
        return None

    return round(float(value) / MIB, 1)


def _system_memory_bytes():
    """Return total and available system RAM using only the standard library."""
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)

        try:
            success = ctypes.windll.kernel32.GlobalMemoryStatusEx(
                ctypes.byref(status)
            )
        except (AttributeError, OSError):
            success = False

        if success:
            return status.total_physical, status.available_physical

    if hasattr(os, "sysconf"):
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            total_pages = os.sysconf("SC_PHYS_PAGES")
            available_pages = os.sysconf("SC_AVPHYS_PAGES")
            return (
                page_size * total_pages,
                page_size * available_pages,
            )
        except (OSError, TypeError, ValueError):
            pass

    return None, None


@dataclass(frozen=True)
class ResourceSnapshot:
    active_device: str
    cuda_available: bool
    gpu_name: str | None
    total_vram_mb: float | None
    free_vram_mb: float | None
    allocated_vram_mb: float | None
    reserved_vram_mb: float | None
    peak_vram_mb: float | None
    total_system_ram_mb: float | None
    available_system_ram_mb: float | None

    def to_dict(self):
        return asdict(self)


class ResourceMonitor:
    """Best-effort CUDA and system-memory measurements for one model session."""

    def __init__(self, active_device="cpu"):
        self.active_device = str(active_device).lower()
        self.cuda_available = bool(torch.cuda.is_available())
        self.cuda_index = 0

    def set_active_device(self, device):
        self.active_device = str(device).lower()

    def reset_peak(self):
        if not self.cuda_available:
            return

        try:
            torch.cuda.reset_peak_memory_stats(self.cuda_index)
        except (AssertionError, RuntimeError, TypeError):
            pass

    def synchronize(self):
        if self.active_device != "cuda" or not self.cuda_available:
            return

        try:
            torch.cuda.synchronize(self.cuda_index)
        except (AssertionError, RuntimeError, TypeError):
            pass

    def snapshot(self):
        total_system, available_system = _system_memory_bytes()
        gpu_name = None
        total_vram = None
        free_vram = None
        allocated = None
        reserved = None
        peak = None

        if self.cuda_available:
            try:
                gpu_name = torch.cuda.get_device_name(self.cuda_index)
                free_vram, total_vram = torch.cuda.mem_get_info(
                    self.cuda_index
                )
                allocated = torch.cuda.memory_allocated(self.cuda_index)
                reserved = torch.cuda.memory_reserved(self.cuda_index)
                peak = torch.cuda.max_memory_allocated(self.cuda_index)
            except (AssertionError, RuntimeError, TypeError):
                try:
                    properties = torch.cuda.get_device_properties(
                        self.cuda_index
                    )
                    gpu_name = properties.name
                    total_vram = properties.total_memory
                except (AssertionError, RuntimeError, TypeError):
                    pass

        return ResourceSnapshot(
            active_device=self.active_device,
            cuda_available=self.cuda_available,
            gpu_name=gpu_name,
            total_vram_mb=_mib(total_vram),
            free_vram_mb=_mib(free_vram),
            allocated_vram_mb=_mib(allocated),
            reserved_vram_mb=_mib(reserved),
            peak_vram_mb=_mib(peak),
            total_system_ram_mb=_mib(total_system),
            available_system_ram_mb=_mib(available_system),
        )


def is_cuda_out_of_memory(error):
    """Recognize direct and adapter-wrapped CUDA OOM exceptions."""
    seen = set()
    current = error
    oom_type = getattr(torch.cuda, "OutOfMemoryError", None)

    while current is not None and id(current) not in seen:
        seen.add(id(current))

        if oom_type is not None and isinstance(current, oom_type):
            return True

        message = str(current).lower()

        if "out of memory" in message and (
            "cuda" in message
            or "gpu" in message
            or "cublas" in message
        ):
            return True

        current = current.__cause__ or current.__context__

    return False

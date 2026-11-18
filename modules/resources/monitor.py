from __future__ import annotations

from dataclasses import asdict, dataclass
import ctypes
from functools import lru_cache
import gc
import os
import sys

import torch


MIB = 1024 * 1024
_HOST_VM_INFO = 2
_HOST_VM_INFO_COUNT = 15


def _mib(value):
    if value is None:
        return None

    return round(float(value) / MIB, 1)


@lru_cache(maxsize=1)
def _macos_system_library():
    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    library.sysctlbyname.argtypes = [
        ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
        ctypes.c_void_p, ctypes.c_size_t,
    ]
    library.sysctlbyname.restype = ctypes.c_int
    library.mach_host_self.argtypes = []
    library.mach_host_self.restype = ctypes.c_uint32
    library.mach_task_self.argtypes = []
    library.mach_task_self.restype = ctypes.c_uint32
    library.host_statistics.argtypes = [
        ctypes.c_uint32, ctypes.c_int, ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    library.host_statistics.restype = ctypes.c_int
    library.mach_port_deallocate.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    library.mach_port_deallocate.restype = ctypes.c_int
    return library


def _macos_memory_bytes():
    """Estimate available physical RAM from Mach's free and inactive pages."""
    total = None
    try:
        library = _macos_system_library()
        physical = ctypes.c_uint64()
        size = ctypes.c_size_t(ctypes.sizeof(physical))
        if library.sysctlbyname(b"hw.memsize", ctypes.byref(physical),
                                ctypes.byref(size), None, 0) != 0:
            return None, None
        if size.value != ctypes.sizeof(physical) or physical.value <= 0:
            return None, None
        total = physical.value
        page_size = os.sysconf("SC_PAGE_SIZE")
        if page_size <= 0:
            return total, None

        task = library.mach_task_self()
        host = library.mach_host_self()
        if not host:
            return total, None
        try:
            # The stable vm_statistics layout contains 15 natural_t fields.
            # Its first fields are free, active, inactive, and wired pages.
            statistics = (ctypes.c_uint32 * _HOST_VM_INFO_COUNT)()
            count = ctypes.c_uint32(_HOST_VM_INFO_COUNT)
            result = library.host_statistics(
                host, _HOST_VM_INFO, ctypes.byref(statistics), ctypes.byref(count),
            )
        finally:
            library.mach_port_deallocate(task, host)
        if result != 0 or count.value < 3:
            return total, None
        free_pages = statistics[0]
        inactive_pages = statistics[2]
        # Speculative pages are included in free_count. Compressed memory and
        # swap are excluded from this physical-memory headroom estimate.
        available = (free_pages + inactive_pages) * page_size
        return total, min(total, available)
    except (AttributeError, OSError, TypeError, ValueError):
        return total, None


def _system_memory_bytes():
    """Return total and available system RAM using only the standard library."""
    if sys.platform == "darwin":
        return _macos_memory_bytes()

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
    mps_available: bool = False
    mps_allocated_memory_mb: float | None = None
    mps_driver_memory_mb: float | None = None
    mps_recommended_memory_mb: float | None = None

    @property
    def accelerator_headroom_mb(self):
        if self.active_device != "mps":
            return self.free_vram_mb
        if self.mps_recommended_memory_mb is None or self.mps_driver_memory_mb is None:
            return None
        headroom = max(0.0, self.mps_recommended_memory_mb - self.mps_driver_memory_mb)
        if self.available_system_ram_mb is not None:
            headroom = min(headroom, self.available_system_ram_mb)
        return headroom

    @property
    def accelerator_memory_mb(self):
        if self.active_device == "mps":
            return self.mps_recommended_memory_mb
        return self.total_vram_mb

    def to_dict(self):
        return asdict(self)


class ResourceMonitor:
    """Best-effort CUDA, Metal, and system-memory measurements."""

    def __init__(self, active_device="cpu"):
        self.active_device = str(active_device).lower()
        self.cuda_available = bool(torch.cuda.is_available())
        self.mps_available = bool(torch.backends.mps.is_available())
        self.cuda_index = 0

    def set_active_device(self, device):
        self.active_device = str(device).lower()

    def reset_peak(self):
        if self.active_device != "cuda" or not self.cuda_available:
            return

        try:
            torch.cuda.reset_peak_memory_stats(self.cuda_index)
        except (AssertionError, RuntimeError, TypeError):
            pass

    def synchronize(self):
        if self.active_device == "mps" and self.mps_available:
            torch.mps.synchronize()
            return
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
        mps_allocated = None
        mps_driver = None
        mps_recommended = None

        if self.active_device == "mps" and self.mps_available:
            gpu_name = "Apple Metal (MPS)"
            try:
                mps_allocated = torch.mps.current_allocated_memory()
                mps_driver = torch.mps.driver_allocated_memory()
                mps_recommended = torch.mps.recommended_max_memory()
            except (AttributeError, AssertionError, RuntimeError, TypeError):
                pass

        if self.cuda_available and self.active_device != "mps":
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
            mps_available=self.mps_available,
            mps_allocated_memory_mb=_mib(mps_allocated),
            mps_driver_memory_mb=_mib(mps_driver),
            mps_recommended_memory_mb=_mib(mps_recommended),
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


def is_accelerator_out_of_memory(error, device):
    if device == "cuda":
        return is_cuda_out_of_memory(error)
    if device != "mps":
        return False
    return _mps_error_matches(error, ("out of memory",))


def _mps_error_matches(error, phrases):
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        message = str(error).lower()
        if ("mps" in message or "metal" in message) and any(p in message for p in phrases):
            return True
        error = error.__cause__ or error.__context__
    return False


def is_mps_unsupported_error(error):
    return _mps_error_matches(error, (
        "not implemented", "not currently implemented", "not supported", "does not support",
    ))


def release_device_memory(device):
    gc.collect()
    try:
        if device == "mps" and torch.backends.mps.is_available():
            torch.mps.empty_cache()
        elif device == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()
    except (AssertionError, RuntimeError):
        pass

from __future__ import annotations

from dataclasses import dataclass
import os
import sys


@dataclass(frozen=True, slots=True)
class ProcessMemorySnapshot:
    """Best-effort process working-set metrics without third-party dependencies."""

    rss_bytes: int | None
    peak_rss_bytes: int | None


def process_memory_snapshot() -> ProcessMemorySnapshot:
    """Return current/peak resident memory when exposed cheaply by the OS.

    Diagnostics must never make import fail, so unsupported platforms return
    None fields instead of raising.
    """

    if sys.platform == "win32":
        return _windows_process_memory_snapshot()
    return _posix_process_memory_snapshot()


def _windows_process_memory_snapshot() -> ProcessMemorySnapshot:
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return ProcessMemorySnapshot(None, None)

    try:
        size_t = ctypes.c_size_t

        class ProcessMemoryCountersEx(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", size_t),
                ("WorkingSetSize", size_t),
                ("QuotaPeakPagedPoolUsage", size_t),
                ("QuotaPagedPoolUsage", size_t),
                ("QuotaPeakNonPagedPoolUsage", size_t),
                ("QuotaNonPagedPoolUsage", size_t),
                ("PagefileUsage", size_t),
                ("PeakPagefileUsage", size_t),
                ("PrivateUsage", size_t),
            ]

        counters = ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)

        get_current_process = kernel32.GetCurrentProcess
        get_current_process.argtypes = ()
        get_current_process.restype = wintypes.HANDLE

        get_process_memory_info = psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCountersEx),
            wintypes.DWORD,
        )
        get_process_memory_info.restype = wintypes.BOOL

        handle = get_current_process()
        ok = get_process_memory_info(
            handle,
            ctypes.byref(counters),
            counters.cb,
        )
        if not ok:
            return ProcessMemorySnapshot(None, None)
        return ProcessMemorySnapshot(
            rss_bytes=int(counters.WorkingSetSize),
            peak_rss_bytes=int(counters.PeakWorkingSetSize),
        )
    except (
        AttributeError,
        OSError,
        OverflowError,
        TypeError,
        ValueError,
        ctypes.ArgumentError,
    ):
        return ProcessMemorySnapshot(None, None)


def _posix_process_memory_snapshot() -> ProcessMemorySnapshot:
    try:
        import resource

        getrusage = getattr(resource, "getrusage", None)
        rusage_self = getattr(resource, "RUSAGE_SELF", None)
        if not callable(getrusage) or rusage_self is None:
            return ProcessMemorySnapshot(None, None)
        usage = getrusage(rusage_self)
        peak = int(usage.ru_maxrss)
        if sys.platform != "darwin":
            peak *= 1024
        current = (
            _linux_current_rss_bytes()
            if sys.platform.startswith("linux")
            else None
        )
        # These OS counters are sampled independently. The observed current
        # resident set is itself a lower bound for the process peak.
        if current is not None:
            peak = max(peak, current)
        return ProcessMemorySnapshot(current, peak)
    except (AttributeError, ImportError, OSError, TypeError, ValueError):
        return ProcessMemorySnapshot(None, None)


def _linux_current_rss_bytes() -> int | None:
    try:
        with open("/proc/self/statm", "r", encoding="ascii") as stream:
            fields = stream.read().split()
        if len(fields) < 2:
            return None
        sysconf = getattr(os, "sysconf", None)
        if not callable(sysconf):
            return None
        return int(fields[1]) * int(sysconf("SC_PAGE_SIZE"))
    except (OSError, TypeError, ValueError):
        return None

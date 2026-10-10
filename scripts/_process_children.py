"""Enumerate direct children without a system-wide process snapshot on CI platforms."""

import ctypes
import sys
from pathlib import Path


def children(pid: int) -> list[int]:
    """Return direct child PIDs; refuse truncated or unreadable process evidence."""
    platform = sys.platform
    if platform == "darwin":
        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        list_children = library.proc_listchildpids
        list_children.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
        list_children.restype = ctypes.c_int
        capacity = 65536
        buffer = (ctypes.c_int * capacity)()
        count = list_children(pid, buffer, ctypes.sizeof(buffer))
        if count < 0:
            raise OSError(ctypes.get_errno(), "cannot enumerate child processes")
        if count >= capacity:
            raise RuntimeError("child process enumeration exceeds capacity")
        return [value for value in buffer[:count] if value > 0]
    if platform.startswith("linux"):
        try:
            tasks = list(Path(f"/proc/{pid}/task").iterdir())
        except FileNotFoundError:
            return []
        found: set[int] = set()
        for task in tasks:
            try:
                found.update(
                    int(value) for value in (task / "children").read_text().split()
                )
            except FileNotFoundError:
                continue
        return sorted(found)
    raise RuntimeError("child process enumeration is unavailable on this platform")

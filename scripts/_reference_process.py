"""Bound reference output and deadlines while reaping complete process trees."""

from __future__ import annotations

import math
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _verify_process import stop_process_tree

MAX_OUTPUT_BYTES = 1024 * 1024


def run(
    command: list[str], data: bytes, timeout: float, limit: int = MAX_OUTPUT_BYTES
) -> tuple[int, bytes, bytes, str | None]:
    """Return exit, bounded output and an explicit timeout or output-limit status."""
    if not math.isfinite(timeout) or timeout <= 0 or limit < 1:
        raise ValueError("reference bounds must be positive and finite")
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=os.name == "posix",
    )
    output, error = bytearray(), bytearray()
    lock = threading.Lock()
    exceeded = threading.Event()
    count = 0

    def collect(stream: Any, target: bytearray) -> None:
        nonlocal count
        while chunk := stream.read1(8192):
            with lock:
                available = max(0, limit - count)
                target.extend(chunk[:available])
                count += min(len(chunk), available)
                overflow = len(chunk) > available
            if overflow:
                exceeded.set()
                stop_process_tree(process)
                return

    def send() -> None:
        assert process.stdin is not None
        try:
            process.stdin.write(data)
            process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        finally:
            process.stdin.close()

    readers = [
        threading.Thread(target=collect, args=(process.stdout, output), daemon=True),
        threading.Thread(target=collect, args=(process.stderr, error), daemon=True),
        threading.Thread(target=send, daemon=True),
    ]
    for reader in readers:
        reader.start()
    status = None
    try:
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            status = "timeout"
    finally:
        stop_process_tree(process)
        for reader in readers:
            reader.join(2)
        for stream in (process.stdout, process.stderr):
            assert stream is not None
            stream.close()
    if exceeded.is_set():
        status = "limit"
    assert process.returncode is not None
    return process.returncode, bytes(output), bytes(error), status

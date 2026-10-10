"""Bound verification subprocesses and reap their workers."""

import os
import signal
import subprocess
import time
from contextlib import suppress


def stop_process_tree(proc: subprocess.Popen[str]) -> None:
    """Kill the step's process tree and reap its direct child."""
    if os.name == "posix":
        with suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
    else:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        if proc.poll() is None:
            proc.kill()
    proc.wait()


def wait_with_heartbeat(
    proc: subprocess.Popen[str], name: str, start: float, limit: float, heartbeat: float
) -> tuple[str, int]:
    """Collect output until the step's deadline; kill descendants on timeout."""
    deadline = start + limit
    try:
        while True:
            remaining = deadline - time.monotonic()
            try:
                output, _ = proc.communicate(
                    timeout=max(0.0, min(heartbeat, remaining))
                )
                return output or "", proc.returncode
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline:
                    stop_process_tree(proc)
                    output, _ = proc.communicate()
                    return (
                        output or ""
                    ) + f"\n{name}: deadline exceeded ({limit:g}s)\n", 124
                print(
                    f"[....] {name} still running "
                    f"({time.monotonic() - start:.0f}s elapsed)"
                )
    except BaseException:
        stop_process_tree(proc)
        raise

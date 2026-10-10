"""Bound verification subprocesses and reap their workers."""

from __future__ import annotations

import codecs
import io
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from weakref import WeakKeyDictionary

EXCERPT_BYTES = 32 * 1024


@dataclass
class Log:
    path: Path
    reader: threading.Thread | None = None


_LOGS: WeakKeyDictionary[subprocess.Popen[str], Log] = WeakKeyDictionary()


def start_logged(
    cmd: list[str], name: str, env: dict[str, str], root: Path, *, stream: bool
) -> subprocess.Popen[str]:
    """Spool complete step output to a unique ignored file; optionally tee it."""
    directory = root / "notes" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    prefix = re.sub(r"[^a-zA-Z0-9_-]", "-", name)[:48] + "-"
    fd, filename = tempfile.mkstemp(prefix=prefix, suffix=".log", dir=directory)
    log = Log(Path(filename))
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE if stream else output,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=os.name == "posix",
        )
    if stream:

        def tee() -> None:
            assert proc.stdout is not None
            with log.path.open("wb") as output:
                reader = cast(
                    "io.BufferedReader", cast("io.TextIOWrapper", proc.stdout).buffer
                )
                decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
                while raw := reader.read1(8192):
                    chunk = decoder.decode(raw)
                    output.write(raw)
                    output.flush()
                    with suppress(BrokenPipeError):
                        sys.stdout.write(chunk)
                        sys.stdout.flush()
                final = decoder.decode(b"", final=True)
                sys.stdout.write(final)

        log.reader = threading.Thread(target=tee, daemon=True)
        log.reader.start()
    _LOGS[proc] = log
    return proc


def excerpt(proc: subprocess.Popen[str]) -> str:
    """Return a bounded tail and the path to its persistent complete log."""
    log = _LOGS[proc]
    if log.reader is not None:
        log.reader.join(5)
    with log.path.open("rb") as output:
        output.seek(max(0, log.path.stat().st_size - EXCERPT_BYTES))
        tail = output.read(EXCERPT_BYTES).decode("utf-8", errors="replace")
    return f"[log] {log.path}\n" + tail


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
                wait = max(0.0, min(heartbeat, remaining))
                if proc in _LOGS:
                    proc.wait(timeout=wait)
                    return excerpt(proc), proc.returncode
                output, _ = proc.communicate(timeout=wait)
                return output or "", proc.returncode
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline:
                    stop_process_tree(proc)
                    if proc in _LOGS:
                        output = excerpt(proc)
                    else:
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
